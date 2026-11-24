# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""`--sql-values` of the command line, offline: the SQL filters stay where the caller is the host's own user.

The REST API and the MCP tools take no SQL (GHSA-332g-7w2w-4w59); `values`, `interpolate` and `summarize` of the
command line still cut the rows of their answer with `--sql-values`. The stations of the request are stood in, so the
real getters of `wetterdienst.ui.core` and the real DuckDB filter run on rows of which some must go.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import replace
from types import SimpleNamespace
from typing import TYPE_CHECKING

import polars as pl
import pytest
from click.testing import CliRunner

from tests.ui.test_restapi import _values_result_of_shape
from wetterdienst.model.result import InterpolatedValuesResult, SummarizedValuesResult
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.ui import core
from wetterdienst.ui.cli import cli

if TYPE_CHECKING:
    from wetterdienst.model.result import ValuesResult

duckdb = pytest.importorskip("duckdb")

pytestmark = pytest.mark.sql

_PARAMETER = "daily/climate_summary/temperature_air_mean_2m"


def _stations_result() -> ValuesResult:
    """Give the stations of one station, with the request the metadata is read off."""
    base = _values_result_of_shape("long")
    request = DwdObservationRequest(parameters=[("daily", "climate_summary", "temperature_air_mean_2m")])
    return replace(base, stations=replace(base.stations, request=request))


def _three_values() -> ValuesResult:
    """Give three readings of 1, 2 and 3, of which a clause on the value must cut some."""
    base = _stations_result()
    rows = [
        {
            "station_id": "01048",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "timestamp": dt.datetime(2026, 1, day, tzinfo=dt.UTC),
            "value": float(day),
            "quality_flags": None,
        }
        for day in (1, 2, 3)
    ]
    df = pl.DataFrame(rows, schema_overrides={"timestamp": pl.Datetime(time_zone="UTC")}, orient="row")
    return replace(base, df=df)


def _three_estimates(kind: type[InterpolatedValuesResult | SummarizedValuesResult]) -> object:
    """Give three estimates of 1, 2 and 3 for a point, as an interpolation or a summary writes them."""
    base = _stations_result()
    placed = replace(
        base.stations,
        df=base.stations.df.with_columns(
            pl.lit(5.0).alias("distance"), pl.lit(None, dtype=pl.Float64).alias("elevation_difference")
        ),
    )
    rows = []
    for day in (1, 2, 3):
        row = {
            "station_id": "a87d0e9bb6fb2b4b",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "timestamp": dt.datetime(2026, 1, day, tzinfo=dt.UTC),
            "value": float(day),
        }
        rows.append(
            {**row, "distance_mean": 5.0, "taken_station_ids": ["01048"]}
            if kind is InterpolatedValuesResult
            else {**row, "distance": 5.0, "taken_station_id": "01048"}
        )
    df = pl.DataFrame(rows, schema_overrides={"timestamp": pl.Datetime(time_zone="UTC")}, orient="row")
    return kind(stations=placed, df=df, latlon=(51.1, 13.8))


class _Reader:
    """Stand in for the reader of a station selection: `.all()` is the values it was given."""

    def __init__(self, result: ValuesResult) -> None:
        self._result = result

    def all(self) -> ValuesResult:
        return self._result


def _serve_values(monkeypatch: pytest.MonkeyPatch, result: ValuesResult) -> None:
    """Make `get_values` read `result` from the selected stations, and filter it as it does."""
    stations = SimpleNamespace(values=lambda: _Reader(result))
    monkeypatch.setattr(core, "get_stations", lambda **_kwargs: stations)


def _serve_estimates(monkeypatch: pytest.MonkeyPatch, result: object) -> None:
    """Make `get_interpolate` and `get_summarize` estimate `result` for any point or station, and filter it."""

    def estimate(*_args: object, **_kwargs: object) -> object:
        return result

    request = SimpleNamespace(
        interpolate=estimate, interpolate_by_station_id=estimate, summarize=estimate, summarize_by_station_id=estimate
    )
    monkeypatch.setattr(core, "_get_stations_request", lambda **_kwargs: request)


_VALUES = [
    "values",
    "--provider=dwd",
    "--network=observation",
    f"--parameters={_PARAMETER}",
    "--stations=01048",
    "--timestamp=2026-01-01/2026-01-03",
    "--format=json",
]
_ESTIMATE = [
    "--provider=dwd",
    "--network=observation",
    f"--parameters={_PARAMETER}",
    "--latitude=51.1",
    "--longitude=13.8",
    "--timestamp=2026-01-01/2026-01-03",
    "--format=json",
]


def _values_of(output: str) -> list[float]:
    """Read the values of a JSON answer of the command line, in the order it gives them."""
    return [row["value"] for row in json.loads(output)["values"]]


@pytest.mark.parametrize(
    ("argv", "serve"),
    [
        pytest.param(_VALUES, lambda m: _serve_values(m, _three_values()), id="values"),
        pytest.param(
            ["interpolate", *_ESTIMATE],
            lambda m: _serve_estimates(m, _three_estimates(InterpolatedValuesResult)),
            id="interpolate",
        ),
        pytest.param(
            ["summarize", *_ESTIMATE],
            lambda m: _serve_estimates(m, _three_estimates(SummarizedValuesResult)),
            id="summarize",
        ),
    ],
)
class TestSqlValues:
    """The command line cuts the rows of a values, an interpolation and a summary with `--sql-values`."""

    def test_the_rows_that_do_not_match_are_cut(
        self, argv: list[str], serve: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The rows a clause does not match are not in the answer; without the clause every row is."""
        serve(monkeypatch)
        everything = CliRunner().invoke(cli, argv)
        cut = CliRunner().invoke(cli, [*argv, "--sql-values=value > 1.5"])

        assert everything.exit_code == 0, everything.output
        assert _values_of(everything.stdout) == [1.0, 2.0, 3.0]
        assert cut.exit_code == 0, cut.output
        assert _values_of(cut.stdout) == [2.0, 3.0]

    def test_a_clause_that_matches_nothing_leaves_no_row(
        self, argv: list[str], serve: object, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A clause that matches no row is an answer with none, not a failure."""
        serve(monkeypatch)

        result = CliRunner().invoke(cli, [*argv, "--sql-values=value > 100"])

        assert result.exit_code == 0, result.output
        assert _values_of(result.stdout) == []

    @pytest.mark.parametrize("clause", ["nope = 1", "value >", "value > 1 ORDER BY value"])
    def test_a_clause_duckdb_refuses_is_a_usage_error(
        self,
        argv: list[str],
        serve: object,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
        clause: str,
    ) -> None:
        """A clause DuckDB refuses is one line and exit 2, as a mistyped option is, with no traceback."""
        serve(monkeypatch)

        with caplog.at_level(logging.ERROR):
            result = CliRunner().invoke(cli, [*argv, f"--sql-values={clause}"])

        assert result.exit_code == 2, result.output
        assert "Error: " in result.stderr
        assert "Traceback" not in result.output
        assert not [record for record in caplog.records if record.levelno >= logging.ERROR]


def test_a_duckdb_older_than_the_floor_is_one_line_with_what_to_install(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The filter refuses an old DuckDB before it uses it, and the command line logs that as one line, exit 1."""
    _serve_values(monkeypatch, _three_values())
    monkeypatch.setattr(duckdb, "__version__", "1.5.2")

    with caplog.at_level(logging.ERROR):
        result = CliRunner().invoke(cli, [*_VALUES, "--sql-values=value > 1.5"])

    assert result.exit_code == 1, result.output
    (message,) = [record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR]
    assert message.startswith("Filtering with SQL needs DuckDB 1.5.3 or newer, found 1.5.2.")
    assert "pip install --upgrade 'duckdb>=1.5.3'" in message
    assert all(record.exc_info is None for record in caplog.records)
