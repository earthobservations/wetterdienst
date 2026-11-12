# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What a write to a target refuses (GH-3814).

An `if_exists` that is none of the four words is refused by every sink (a file took it for `replace`, DuckDB for
nothing at all). A NUL in a path is refused as a bad target, where each writer failed in its own way and NetCDF
wrote the file whose name is the text before it. (A file is still written in place: staging it beside its place and
moving it in was tried and dropped, see the pull request.)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from click.testing import CliRunner

from tests.model.test_results import _every_result
from wetterdienst.exceptions import ExportRefusedError
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


def test_the_refusal_of_a_nul_names_no_part_of_the_target() -> None:
    """A token or a password in the query or the credentials of the target is not repeated in the message."""
    target = "duckdb:///x%00.duckdb?table=t&motherduck_token=SECRET"

    with pytest.raises(ExportRefusedError) as raised:
        ConnectionString(target)

    assert "SECRET" not in str(raised.value)
    assert "x%00" not in str(raised.value)
    assert "NUL" in str(raised.value)


@pytest.mark.parametrize(
    "target",
    [
        "sqlite:///x%00.sqlite",
        "sqlite:///x%00.sqlite?table=t",
        "postgresql://u:p@h/db%00",
        # the InfluxDB forms of `docs/usage/export.md`: the database or the bucket is in the query
        "influxdb://u:p@h:8086/?database=db%00&table=t",
        "influxdb2://u:p@h:8086/?bucket=b%00&table=t",
    ],
)
def test_a_nul_in_the_database_of_a_sql_target_is_refused(target: str) -> None:
    """The same place: `sqlite:///x%00.sqlite` was a bare `ValueError` of the engine."""
    with pytest.raises(ExportRefusedError, match="NUL"):
        ConnectionString(target)


def test_an_influxdb_target_without_a_nul_is_read_as_before() -> None:
    """The check reads `database` and `bucket` and leaves the rest of the target as it was."""
    target = ConnectionString("influxdb2://u:p@h:8086/?bucket=b&table=t")

    assert (target.database, target.table, target.host, target.port) == ("b", "t", "h", 8086)


def test_a_sql_target_is_refused_before_anything_is_written(tmp_path: Path, monkeypatch) -> None:  # noqa: ANN001
    """`to_target` reads the target first, so nothing is created for it."""
    monkeypatch.chdir(tmp_path)

    with pytest.raises(ExportRefusedError, match="NUL"):
        _result().to_target("sqlite:///x%00.sqlite?table=t")

    assert list(tmp_path.iterdir()) == []


def test_delete_rows_is_refused_too() -> None:
    """The word pandas takes for SQL and the docs never offered: it worked before, and is refused with the others."""
    with pytest.raises(ExportRefusedError, match="not 'delete_rows'"):
        _result().to_target("sqlite://", if_exists="delete_rows")  # ty: ignore[invalid-argument-type]


def test_a_plain_path_with_a_nul_is_refused() -> None:
    """A path given without the scheme (`alerts` and `history` take one) is read as it is; a NUL in it is refused."""
    with pytest.raises(ExportRefusedError, match="NUL"):
        file_target_path("out/x\x00.json")
    assert file_target_path("out/x.json") == "out/x.json"


def test_the_reader_of_values_refuses_an_unknown_if_exists_before_it_downloads_a_station() -> None:
    """`TimeseriesValues.to_target` told it after the first station was downloaded, and not at all for no station."""
    from unittest import mock  # noqa: PLC0415

    from wetterdienst.model.values import TimeseriesValues  # noqa: PLC0415

    values = mock.MagicMock()
    values.query.return_value = iter([])
    values.sr.station_id = []

    with pytest.raises(ExportRefusedError, match="not 'bogus'"):
        TimeseriesValues.to_target(values, "file://x.csv", if_exists="bogus")  # ty: ignore[invalid-argument-type]

    values.query.assert_not_called()


def test_a_file_is_refused_an_unknown_if_exists_where_it_is_written(tmp_path: Path) -> None:
    """`_write_file` reads the word itself, for a caller that reaches it without `write_to_target`."""
    from wetterdienst.io.sinks import _write_file  # noqa: PLC0415

    filename = tmp_path / "data.csv"
    filename.write_text("kept")
    target = f"file://{filename}"

    with pytest.raises(ExportRefusedError, match="not 'bogus'"):
        _write_file(_result(), target, ConnectionString(target), "bogus")  # ty: ignore[invalid-argument-type]

    assert filename.read_text() == "kept"
