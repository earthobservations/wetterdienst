# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A station named by id that the walk does not read, for its list begins after the window, is named (GH-4522).

`station-without-rows` names it, with that reason, also where no other station has rows (a station read that came back
empty is `parameter-without-rows`'s). Where no station was read at all `no-station-read` names every one of them, and
`station-without-rows` does not tell them again. Not for an estimate.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest

from tests.model.test_no_station_read import FUTURE, OLD, _dwd, _frame
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

if TYPE_CHECKING:
    from wetterdienst.model.request import TimeseriesRequest

STATION_WITHOUT_ROWS = "station-without-rows"
NO_STATION_READ = "no-station-read"
PARAMETER_WITHOUT_ROWS = "parameter-without-rows"
WHY = (
    "the station list begins after the window's end, 2022-02-18, so by the list {} no data in it. "
    "Naming {} by id does not read {}."
)


def _rows(datasets: list[Any]) -> pl.DataFrame:
    name = datasets[0].parameters[0].name_original
    return pl.DataFrame(
        {
            "resolution": ["daily"],
            "dataset": ["climate_summary"],
            "parameter": [name],
            "timestamp": [dt.datetime(2022, 2, 18, tzinfo=dt.UTC)],
            "value": [1.0],
            "quality_flags": [None],
        },
        schema_overrides={"quality_flags": pl.String},
    )


def _walk(
    df: pl.DataFrame,
    monkeypatch: pytest.MonkeyPatch,
    *,
    with_rows: tuple[str, ...] = (),
    request: TimeseriesRequest | None = None,
    selection: StationsFilter = StationsFilter.BY_STATION_ID,
    estimate: bool = False,
) -> dict[str, list[dict[str, Any]]]:
    """Walk the named stations, those in `with_rows` reading a row, the others none, and give the warnings by code."""
    request = request or _dwd()
    result = StationsResult(request=request, df=df, _df_all=df, _stations_filter=selection)
    values = result.values()
    if estimate:
        values._window_rule_allowed = False  # noqa: SLF001
        values._warn_without_rows = False  # noqa: SLF001

    def collect(_self: object, station_id: str, datasets: list[Any]) -> pl.DataFrame:
        return _rows(datasets) if station_id in with_rows else pl.DataFrame()

    monkeypatch.setattr(type(values), "_collect_station_data", collect)
    begin_response()
    list(values.query())
    told: dict[str, list[dict[str, Any]]] = {}
    for warning in recorded_warnings():
        told.setdefault(warning["code"], []).append(dict(warning))
    return told


def test_a_late_station_is_named_where_another_was_read_without_rows(monkeypatch: pytest.MonkeyPatch) -> None:
    """A is read and has no rows (`parameter-without-rows`), B begins after the window: nothing named B before."""
    df = _frame([("A", OLD, None), ("B", FUTURE, None)])

    told = _walk(df, monkeypatch)

    (warning,) = told[STATION_WITHOUT_ROWS]
    assert warning["stations"] == ["B"]
    assert warning["message"] == f"Station B was not read: {WHY.format('it has', 'it', 'it')}"
    (parameter_warning,) = told[PARAMETER_WITHOUT_ROWS]
    assert "station A" in parameter_warning["message"]
    assert "station B" not in parameter_warning["message"]
    # one station is told once: A is read, B is not, so `no-station-read` has none to say
    assert NO_STATION_READ not in told


def test_a_late_station_alone_is_told_by_no_station_read_and_not_twice(monkeypatch: pytest.MonkeyPatch) -> None:
    """No station read: `no-station-read` names it, and `station-without-rows` does not tell it again."""
    told = _walk(_frame([("B", FUTURE, None)]), monkeypatch)

    (warning,) = told[NO_STATION_READ]
    assert warning["stations"] == ["B"]
    assert STATION_WITHOUT_ROWS not in told
    assert PARAMETER_WITHOUT_ROWS not in told


def test_several_late_stations_alone_are_told_once_by_no_station_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every named station late: the same, for all of them."""
    told = _walk(_frame([("B", FUTURE, None), ("C", FUTURE, None)]), monkeypatch)

    (warning,) = told[NO_STATION_READ]
    assert warning["stations"] == ["B", "C"]
    assert STATION_WITHOUT_ROWS not in told


def test_a_late_station_with_one_that_has_rows_is_named_with_its_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    """A has rows, B begins after the window: B is named by its reason and is not an 'empty' station."""
    df = _frame([("A", OLD, None), ("B", FUTURE, None)])

    told = _walk(df, monkeypatch, with_rows=("A",))

    (warning,) = told[STATION_WITHOUT_ROWS]
    assert warning["stations"] == ["B"]
    assert warning["message"] == f"Station B was not read: {WHY.format('it has', 'it', 'it')}"
    assert "The source holds no values" not in warning["message"]
    assert NO_STATION_READ not in told


def test_several_late_stations_are_named_together(monkeypatch: pytest.MonkeyPatch) -> None:
    """One warning, the stations in the order of the walk."""
    df = _frame([("A", OLD, None), ("B", FUTURE, None), ("C", FUTURE, None)])

    told = _walk(df, monkeypatch, with_rows=("A",))

    (warning,) = told[STATION_WITHOUT_ROWS]
    assert warning["stations"] == ["B", "C"]
    assert warning["message"] == f"Stations B, C were not read: {WHY.format('they have', 'them', 'them')}"


def test_a_late_station_and_an_empty_one_are_one_warning_naming_each_by_its_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A has rows, B is read and empty, C begins after the window: each is named once, by what it is."""
    df = _frame([("A", OLD, None), ("B", OLD, None), ("C", FUTURE, None)])

    told = _walk(df, monkeypatch, with_rows=("A",))

    (warning,) = told[STATION_WITHOUT_ROWS]
    assert warning["stations"] == ["B", "C"]
    assert warning["message"].startswith("No rows for station B on 2022-02-18. The source holds no values of it there")
    assert warning["message"].endswith(f"Station C was not read: {WHY.format('it has', 'it', 'it')}")
    assert warning["message"].count("station B") == 1
    assert "station C" not in warning["message"].replace("Station C", "")


def test_the_late_stations_named_are_capped(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ten are named in the list, the message says how many and gives the first ten."""
    df = _frame([("A", OLD, None), *[(f"{i:05d}", FUTURE, None) for i in range(12)]])

    told = _walk(df, monkeypatch, with_rows=("A",))

    (warning,) = told[STATION_WITHOUT_ROWS]
    assert warning["stations"] == [f"{i:05d}" for i in range(10)]
    assert warning["message"].startswith("12 stations, the first 10 of them 00000, 00001")
    assert "00009 were not read" in warning["message"]


@pytest.mark.parametrize("selection", [StationsFilter.BY_WMO_ID, StationsFilter.BY_WIGOS_ID, StationsFilter.BY_ICAO_ID])
def test_the_other_ways_to_name_a_station_are_the_same(
    selection: StationsFilter, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A WMO, WIGOS or ICAO id names stations as `stations` does."""
    df = _frame([("A", OLD, None), ("B", FUTURE, None)])

    told = _walk(df, monkeypatch, with_rows=("A",), selection=selection)

    (warning,) = told[STATION_WITHOUT_ROWS]
    assert warning["stations"] == ["B"]


@pytest.mark.parametrize("selection", [StationsFilter.BY_RANK, StationsFilter.ALL, StationsFilter.BY_BBOX])
def test_a_selection_that_does_not_name_its_stations_tells_none(
    selection: StationsFilter, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A rank, a box or `all` has stations left out as the ordinary case: no `station-without-rows`."""
    df = _frame([("A", OLD, None), ("B", FUTURE, None)])

    told = _walk(df, monkeypatch, with_rows=("A",), selection=selection)

    assert STATION_WITHOUT_ROWS not in told


def test_an_estimate_tells_none_of_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """`interpolate` and `summarize` switch the warnings off."""
    df = _frame([("A", OLD, None), ("B", FUTURE, None)])

    told = _walk(df, monkeypatch, with_rows=("A",), estimate=True)
    alone = _walk(_frame([("B", FUTURE, None)]), monkeypatch, estimate=True)

    assert STATION_WITHOUT_ROWS not in told
    assert not alone
