# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What a write to a target refuses, and what it leaves behind when it fails (GH-3814).

An `if_exists` that is none of the four words is refused by every sink (a file took it for `replace`, DuckDB for
nothing at all). A NUL in a path is refused as a bad target, where each writer failed in its own way and NetCDF
wrote the file whose name is the text before it. A file is written beside its place and moved into it, so that an
error while writing leaves the file that was there as it was.
"""

from __future__ import annotations

import os
import stat
import sys
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest
from click.testing import CliRunner

from tests.model.test_results import _every_result
from wetterdienst.exceptions import ExportRefusedError
from wetterdienst.io import sinks
from wetterdienst.io.file_metadata import SIDECAR_SUFFIX
from wetterdienst.io.sinks import FILE_WRITERS
from wetterdienst.ui.cli import cli
from wetterdienst.util.url import ConnectionString, file_target_path

if TYPE_CHECKING:
    from pathlib import Path


def _result() -> Any:  # noqa: ANN401
    return _every_result()["values"]


# --- if_exists --------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("word", ["bogus", "", "Replace", "overwrite"])
def test_an_unknown_if_exists_is_refused_for_a_file_that_is_there(word: str, tmp_path: Path) -> None:
    """The file was overwritten with exit 0: the word is read by testing the three others and `replace` was the rest."""
    filename = tmp_path / "data.csv"
    filename.write_text("kept")

    with pytest.raises(ExportRefusedError, match="if_exists must be one of 'replace', 'append', 'fail', 'skip'"):
        _result().to_target(f"file://{filename}", if_exists=word)  # ty: ignore[invalid-argument-type]

    assert filename.read_text() == "kept"


def test_an_unknown_if_exists_is_refused_for_a_file_that_is_not_there(tmp_path: Path) -> None:
    """Refused whether the file is there or not, and before it is looked for."""
    with pytest.raises(ExportRefusedError, match="not 'bogus'"):
        _result().to_target(f"file://{tmp_path / 'data.csv'}", if_exists="bogus")  # ty: ignore[invalid-argument-type]

    assert list(tmp_path.iterdir()) == []


def test_an_unknown_if_exists_is_refused_for_duckdb(tmp_path: Path) -> None:
    """DuckDB matched none of its four branches, connected, wrote nothing and returned."""
    pytest.importorskip("duckdb")

    with pytest.raises(ExportRefusedError, match="not 'bogus'"):
        _result().to_target(f"duckdb:///{tmp_path / 'x.duckdb'}?table=t", if_exists="bogus")  # ty: ignore[invalid-argument-type]

    assert list(tmp_path.iterdir()) == []


def test_an_unknown_if_exists_is_refused_for_a_sql_database(tmp_path: Path) -> None:
    """Pandas refused it with its own `ValueError`, which is not a refusal the command line tells as one."""
    pytest.importorskip("sqlalchemy")

    with pytest.raises(ExportRefusedError, match="not 'bogus'"):
        _result().to_target(f"sqlite:///{tmp_path / 'x.sqlite'}?table=t", if_exists="bogus")  # ty: ignore[invalid-argument-type]


@pytest.mark.parametrize("word", ["replace", "append", "fail", "skip"])
def test_the_four_words_are_still_read(word: str, tmp_path: Path) -> None:
    """The check lets the four through: a file takes three of them and refuses `append` with its own sentence."""
    filename = tmp_path / "data.csv"
    if word == "append":
        with pytest.raises(ExportRefusedError, match="Append mode is not supported for file exports"):
            _result().to_target(f"file://{filename}", if_exists=word)
        return
    _result().to_target(f"file://{filename}", if_exists=word)
    assert filename.exists()


def test_the_command_line_refuses_an_unknown_if_exists_as_a_usage_error() -> None:
    """`--if-exists` is a choice of the four, which is why only the Python API ever took the fifth."""
    result = CliRunner().invoke(
        cli,
        ["values", "--provider=dwd", "--network=observation", "--parameters=daily/kl", "--stations=1", "--if-exists=x"],
    )

    assert result.exit_code == 2, result.output
    assert "--if-exists" in result.output


# --- a NUL in the path ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("extension", sorted(FILE_WRITERS))
def test_a_nul_in_the_path_is_refused_for_every_file_type(extension: str, tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """A bad target, told in a sentence: NetCDF wrote a file called `x`, the others raised in the writer's own way."""
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ExportRefusedError, match="NUL"):
        _result().to_target(f"file://x%00{extension}")

    assert list(tmp_path.iterdir()) == []


def test_a_nul_in_the_path_of_a_duckdb_target_is_refused(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """The path of a DuckDB file is read as a file target's is."""
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ExportRefusedError, match="NUL"):
        ConnectionString("duckdb:///x%00.duckdb?table=t")


def test_a_nul_in_the_path_is_refused_where_the_path_is_read() -> None:
    """`file_target_path` is read by the command line before it fetches, as well as by the sinks."""
    with pytest.raises(ExportRefusedError, match="NUL"):
        file_target_path("file://out/x%00.json")
    assert file_target_path("file://out/x%2500.json") == "out/x%00.json"


@pytest.mark.parametrize(
    ("args", "target"),
    [
        pytest.param(
            ["history", "--provider=dwd", "--network=observation", "--parameters=daily/kl", "--all"],
            "file://x%00.json",
            id="history",
        ),
        pytest.param(["alerts"], "file://x%00.json", id="alerts"),
    ],
)
def test_the_commands_that_write_the_file_themselves_refuse_a_nul_before_they_fetch(
    args: list[str], target: str
) -> None:
    """Exit 1 with a line, the code a `--target` that cannot be written has, and no traceback; nothing is fetched."""
    result = CliRunner().invoke(cli, [*args, f"--target={target}"])

    assert result.exit_code == 1, result.output
    assert "NUL" in result.output
    assert "Traceback" not in result.output
    assert isinstance(result.exception, SystemExit), repr(result.exception)


# --- a write that fails leaves what was there -------------------------------------------------------------------------


def _names(directory: Path) -> list[str]:
    return sorted(path.name for path in directory.iterdir())


@pytest.mark.parametrize("extension", sorted(set(FILE_WRITERS) - {".zarr"}))
def test_every_file_type_is_written_to_its_place_and_nothing_is_left_beside_it(extension: str, tmp_path: Path) -> None:
    """The file is written next to its place and moved in, for every type: only the file is there afterwards."""
    filename = tmp_path / f"data{extension}"
    filename.write_bytes(b"older")

    _result().to_target(f"file://{filename}")

    assert _names(tmp_path) == [filename.name]
    assert filename.read_bytes() != b"older"


@pytest.mark.parametrize("extension", sorted(set(FILE_WRITERS) - {".zarr"}))
def test_a_writer_that_fails_leaves_the_file_that_was_there(extension: str, tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """A full disk is an error in the middle of the writer: the file was cut to nothing before, and is kept now."""
    filename = tmp_path / f"data{extension}"
    filename.write_bytes(b"older")

    def failing(_result: object, filepath: str, **_: object) -> None:
        with open(filepath, "wb") as handle:  # noqa: PTH123
            handle.write(b"half of the new")
        msg = "No space left on device"
        raise OSError(msg)

    monkeypatch.setitem(FILE_WRITERS, extension, failing)

    with pytest.raises(OSError, match="No space left"):
        _result().to_target(f"file://{filename}")

    assert filename.read_bytes() == b"older"
    assert _names(tmp_path) == [filename.name]


def test_a_writer_that_fails_leaves_no_file_where_there_was_none(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """A new file is not there half written either."""

    def failing(_result: object, filepath: str, **_: object) -> None:
        with open(filepath, "wb") as handle:  # noqa: PTH123
            handle.write(b"half")
        msg = "boom"
        raise RuntimeError(msg)

    monkeypatch.setitem(FILE_WRITERS, ".csv", failing)

    with pytest.raises(RuntimeError, match="boom"):
        _result().to_target(f"file://{tmp_path / 'data.csv'}")

    assert _names(tmp_path) == []


def test_a_sidecar_that_fails_leaves_the_file_that_was_there_and_no_new_one(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """The main file was written first, and stayed, new, beside a sidecar that was not there or was the old one."""
    filename = tmp_path / "data.csv"
    sidecar = tmp_path / f"data.csv{SIDECAR_SUFFIX}"
    filename.write_text("older")
    sidecar.write_text("older sidecar")

    def failing(_block: object, _filepath: object) -> None:
        msg = "No space left on device"
        raise OSError(msg)

    monkeypatch.setattr(sinks, "write_sidecar", failing)

    with pytest.raises(OSError, match="No space left"):
        _result().to_target(f"file://{filename}", with_metadata=True)

    assert filename.read_text() == "older"
    assert sidecar.read_text() == "older sidecar"
    assert _names(tmp_path) == [filename.name, sidecar.name]


def test_a_sidecar_that_fails_leaves_no_file_where_there_was_none(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """A write with its sidecar is both files or neither."""

    def failing(_block: object, _filepath: object) -> None:
        msg = "No space left on device"
        raise OSError(msg)

    monkeypatch.setattr(sinks, "write_sidecar", failing)

    with pytest.raises(OSError, match="No space left"):
        _result().to_target(f"file://{tmp_path / 'data.csv'}", with_metadata=True)

    assert _names(tmp_path) == []


def test_a_file_with_its_sidecar_is_both_files_in_place(tmp_path: Path) -> None:
    """What succeeded before succeeds: the file and `<file>.metadata.json`, and nothing else."""
    filename = tmp_path / "data.csv"

    _result().to_target(f"file://{filename}", with_metadata=True)

    assert _names(tmp_path) == [filename.name, f"{filename.name}{SIDECAR_SUFFIX}"]
    assert pl.read_csv(filename).height


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_a_file_that_is_replaced_keeps_its_mode(tmp_path: Path) -> None:
    """Writing on the file kept its mode; a new file gets the umask's, so the mode is carried over."""
    filename = tmp_path / "data.csv"
    filename.write_text("older")
    filename.chmod(0o640)

    _result().to_target(f"file://{filename}")

    assert stat.S_IMODE(filename.stat().st_mode) == 0o640


@pytest.mark.skipif(sys.platform == "win32", reason="symbolic links need a privilege on Windows")
def test_a_link_is_written_through(tmp_path: Path) -> None:
    """The file a link points at is replaced, and the link stays a link, as it did when the file was written on."""
    real = tmp_path / "real.csv"
    real.write_text("older")
    link = tmp_path / "link.csv"
    link.symlink_to(real)

    _result().to_target(f"file://{link}")

    assert link.is_symlink()
    assert os.path.realpath(link) == str(real.resolve())
    assert real.read_text() != "older"
    assert _names(tmp_path) == ["link.csv", "real.csv"]


def test_a_zarr_store_is_still_written_where_it_is(tmp_path: Path) -> None:
    """A Zarr store is a directory of files: it is written in place, as before, and a second group joins it."""
    pytest.importorskip("zarr")
    store = tmp_path / "data.zarr"

    _result().to_target(f"file://{store}")

    assert store.is_dir()
    assert _names(tmp_path) == ["data.zarr"]


def test_a_target_that_cannot_be_replaced_is_an_error_and_leaves_nothing_beside_it(tmp_path: Path) -> None:
    """A directory in the place of the file (on Windows, a file held open) is the error of the replace."""
    (tmp_path / "data.csv").mkdir()

    with pytest.raises(OSError):  # noqa: PT011
        _result().to_target(f"file://{tmp_path / 'data.csv'}")

    assert _names(tmp_path) == ["data.csv"]
