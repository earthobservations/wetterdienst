# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""`--with-metadata` reaches `--target`, and the `.json` of `history --target` is read in any case (GH-3704, GH-3693).

The fetch is stubbed with the results of `tests/model/test_results.py`, so that the command writes a real file offline.
"""

from __future__ import annotations

import json
import logging
from dataclasses import replace
from typing import TYPE_CHECKING

import polars as pl
import pytest
from click.testing import CliRunner

from tests.model.test_results import _every_result
from tests.ui.cli.test_cli_history import _history_to_target
from wetterdienst.io.file_metadata import BLOCK_KEY, SIDECAR_SUFFIX
from wetterdienst.ui.cli import cli

if TYPE_CHECKING:
    from pathlib import Path

    from click.testing import Result

_COMMANDS = {
    "stations": ("stations", "get_stations", ["--parameters=daily/kl"]),
    "values": ("values", "get_values", ["--parameters=daily/kl/temperature_air_mean_2m", "--periods=recent"]),
}


def _invoke(monkeypatch: pytest.MonkeyPatch, command: str, target: str, *extra: str) -> Result:
    """Run `stations` or `values` for one station with the fetch stubbed out to a result, writing to `target`."""
    name, getter, parameters = _COMMANDS[command]
    result = _every_result()[name]
    monkeypatch.setattr(f"wetterdienst.ui.cli.{getter}", lambda **_kwargs: result)
    return CliRunner().invoke(
        cli,
        [
            name,
            "--provider=dwd",
            "--network=observation",
            *parameters,
            "--stations=01048",
            f"--target={target}",
            *extra,
        ],
    )


@pytest.mark.parametrize("command", _COMMANDS)
@pytest.mark.parametrize("extension", [".csv", ".json", ".geojson"])
def test_with_metadata_writes_the_sidecar_beside_a_bare_file(
    command: str, extension: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A file target is written as `to_target(..., with_metadata=True)` writes it: a sidecar with the heavy parts."""
    filename = tmp_path / f"out{extension}"
    result = _invoke(monkeypatch, command, f"file://{filename}", "--with-metadata")
    assert result.exit_code == 0, result.output
    sidecar = tmp_path / f"out{extension}{SIDECAR_SUFFIX}"
    block = json.loads(sidecar.read_text(encoding="utf-8"))
    assert block["provider"]
    assert block["retrieved_at"]
    assert "parameters" in block
    assert sorted(path.name for path in tmp_path.iterdir()) == sorted([filename.name, sidecar.name])


@pytest.mark.parametrize("command", _COMMANDS)
def test_a_bare_file_has_no_sidecar_without_with_metadata(
    command: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The flag is what asks for the sidecar: without it the file is written as before."""
    result = _invoke(monkeypatch, command, f"file://{tmp_path / 'out.csv'}")
    assert result.exit_code == 0, result.output
    assert [path.name for path in tmp_path.iterdir()] == ["out.csv"]


@pytest.mark.parametrize("command", _COMMANDS)
def test_with_metadata_adds_the_heavy_parts_to_a_parquet_file(
    command: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A Parquet file holds the light block always, and the units and the quality legend with the flag."""
    light, heavy = tmp_path / "light.parquet", tmp_path / "heavy.parquet"
    assert _invoke(monkeypatch, command, f"file://{light}").exit_code == 0
    assert _invoke(monkeypatch, command, f"file://{heavy}", "--with-metadata").exit_code == 0
    assert "parameters" not in json.loads(pl.read_parquet_metadata(light)[BLOCK_KEY])
    assert "parameters" in json.loads(pl.read_parquet_metadata(heavy)[BLOCK_KEY])
    # the block is in the file: no sidecar
    assert sorted(path.name for path in tmp_path.iterdir()) == ["heavy.parquet", "light.parquet"]


@pytest.mark.parametrize("command", _COMMANDS)
def test_with_metadata_for_a_database_target_is_refused_before_anything_is_written(
    command: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """The library's refusal is told in its words, as a one-line error with exit 1, and no database is created."""
    database = tmp_path / "obs.duckdb"
    with caplog.at_level(logging.ERROR):
        result = _invoke(monkeypatch, command, f"duckdb:///{database}?table=weather", "--with-metadata")
    assert result.exit_code == 1
    assert "with_metadata writes the metadata beside a file target (file://...)" in caplog.text
    assert "Failed to export" not in caplog.text
    assert not database.exists()


@pytest.mark.parametrize(
    ("command", "getter", "arguments"),
    [
        ("stations", "get_stations", ["--parameters=daily/kl", "--all"]),
        ("values", "get_values", ["--parameters=daily/kl/temperature_air_mean_2m", "--stations=01048"]),
        (
            "interpolate",
            "get_interpolate",
            [
                "--parameters=daily/kl/temperature_air_mean_2m",
                "--latitude=51",
                "--longitude=13",
                "--timestamp=2020-01-01",
            ],
        ),
        (
            "summarize",
            "get_summarize",
            [
                "--parameters=daily/kl/temperature_air_mean_2m",
                "--latitude=51",
                "--longitude=13",
                "--timestamp=2020-01-01",
            ],
        ),
    ],
)
def test_with_metadata_for_a_database_target_is_refused_before_the_fetch(
    command: str,
    getter: str,
    arguments: list[str],
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The refusal depends on the target and the flag alone, so nothing is downloaded before it (GH-3711)."""
    fetched: list[str] = []

    def _fetch(**_kwargs: object) -> None:
        fetched.append(command)
        msg = "the request was fetched"
        raise AssertionError(msg)

    monkeypatch.setattr(f"wetterdienst.ui.cli.{getter}", _fetch)
    database = tmp_path / "obs.duckdb"
    with caplog.at_level(logging.ERROR):
        result = CliRunner().invoke(
            cli,
            [
                command,
                "--provider=dwd",
                "--network=observation",
                *arguments,
                f"--target=duckdb:///{database}?table=weather",
                "--with-metadata",
            ],
        )
    assert fetched == []
    assert result.exit_code == 1
    assert "with_metadata writes the metadata beside a file target (file://...)" in caplog.text
    assert not database.exists()


def test_with_metadata_for_a_database_target_is_refused_for_an_empty_result_too(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """An empty result writes nothing, but the combination is invalid whatever the data: it is refused all the same."""
    result = _every_result()["stations"]
    empty = replace(result, df=result.df.clear())
    monkeypatch.setattr("wetterdienst.ui.cli.get_stations", lambda **_kwargs: empty)
    with caplog.at_level(logging.ERROR):
        invoked = CliRunner().invoke(
            cli,
            [
                "stations",
                "--provider=dwd",
                "--network=observation",
                "--parameters=daily/kl",
                "--all",
                f"--target=duckdb:///{tmp_path / 'obs.duckdb'}?table=weather",
                "--with-metadata",
            ],
        )
    assert invoked.exit_code == 1
    assert "has no file to write it beside" in caplog.text


def test_history_target_matches_its_extension_in_any_case(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """`--target file://h.JSON` is a .json file, as `_write_file` reads an extension for `values` and `stations`."""
    target = tmp_path / "history.JSON"
    result = _history_to_target(monkeypatch, f"file://{target}")
    assert result.exit_code == 0, result.output
    assert json.loads(target.read_text())["histories"] == []
