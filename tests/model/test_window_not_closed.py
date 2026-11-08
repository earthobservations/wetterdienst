# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The values of a window that had not closed are told by one `window-not-closed` warning (GH-3856).

A provider that serves the value of a period still going on tells the walk over `note_open_window`, and the warning is
raised once the walk is over (`ParameterRows.warn`): one for each parameter, the first ten stations, the values at
each, and the time the earliest of the windows closes. A value left out is no "the source has no values"; a value
returned is marked in its `quality_flags`, which the provider does.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

from tests.model.test_file_skipped import _dwd_stations
from wetterdienst.model.parameter_rows import MAX_STATIONS_LISTED, ParameterRows
from wetterdienst.util.response_warnings import (
    PARAMETER_WITHOUT_ROWS,
    STATION_WITHOUT_ROWS,
    WINDOW_NOT_CLOSED,
    begin_response,
    collecting,
    note_open_window,
    recorded_warnings,
)

NAME = "daily/climate_summary/temperature_air_mean_2m"
CLOSES = dt.datetime(2026, 11, 7, 18, tzinfo=dt.UTC)


def _told(code: str = WINDOW_NOT_CLOSED) -> list[dict[str, Any]]:
    """Give the warnings of `code` that the request being served has recorded."""
    return [warning for warning in recorded_warnings() if warning["code"] == code]


def _walk(counts: dict[str, int], *, returned: bool = False, closes: dt.datetime = CLOSES) -> ParameterRows:
    """Give the walk over the stations of `counts`, each of which found that many values of an open window."""
    request = _dwd_stations(tuple(counts)).request
    rows = ParameterRows(request, None, None)
    dataset = request.metadata["daily"]["climate_summary"]
    for station, count in counts.items():
        rows.examine(station, [dataset])
        with rows.collecting(station):
            note_open_window(NAME, count, closes, returned=returned)
    return rows


def test_the_values_of_each_station_are_summed_and_told_once_with_the_closing_time() -> None:
    """Two stations, one warning, with the values at each, their sum and when the window closes (UTC)."""
    rows = _walk({"00001": 3, "00002": 5})
    begin_response()

    rows.warn()

    (warning,) = _told()
    assert warning["parameter"] == NAME
    assert warning["stations"] == ["00001", "00002"]
    assert f"8 values of {NAME} (00001 3, 00002 5) are left out of the answer" in warning["message"]
    assert "the earliest closes at 2026-11-07 18:00 UTC" in warning["message"]
    assert "They are not missing at the source" in warning["message"]


def test_one_value_is_told_in_the_singular() -> None:
    """One value reads as one."""
    rows = _walk({"00001": 1})
    begin_response()

    rows.warn()

    (warning,) = _told()
    assert f"1 value of {NAME} (00001 1) is left out of the answer" in warning["message"]
    assert "so it is partial" in warning["message"]


def test_the_earliest_closing_time_is_told() -> None:
    """Stations that found windows closing at different times: the earliest is told, whatever the order."""
    request = _dwd_stations(("00001", "00002")).request
    rows = ParameterRows(request, None, None)
    for station, closes in (("00001", CLOSES + dt.timedelta(hours=6)), ("00002", CLOSES)):
        with rows.collecting(station):
            note_open_window(NAME, 1, closes, returned=False)
    begin_response()

    rows.warn()

    (warning,) = _told()
    assert "the earliest closes at 2026-11-07 18:00 UTC" in warning["message"]


def test_a_time_with_an_offset_is_told_in_utc() -> None:
    """A closing time given in another zone is written as UTC."""
    oslo = dt.timezone(dt.timedelta(hours=1))
    rows = _walk({"00001": 1}, closes=CLOSES.astimezone(oslo))
    begin_response()

    rows.warn()

    (warning,) = _told()
    assert "closes at 2026-11-07 18:00 UTC" in warning["message"]


def test_a_value_that_is_returned_is_told_as_marked() -> None:
    """The month so far stays in the answer, and the warning names the token it is marked with."""
    rows = _walk({"00001": 2}, returned=True)
    begin_response()

    rows.warn()

    (warning,) = _told()
    assert f"2 values of {NAME} (00001 2) are of a window that had not closed" in warning["message"]
    assert "marked `completeness:Incomplete` in `quality_flags`" in warning["message"]
    assert "left out" not in warning["message"]


def test_only_the_first_ten_stations_are_listed_and_the_message_says_how_many_more() -> None:
    """A request for a whole network names ten stations and the number of the others, and sums all of them."""
    stations = {f"{number:05d}": number for number in range(1, 13)}
    rows = _walk(stations)
    begin_response()

    rows.warn()

    (warning,) = _told()
    first = list(stations)[:MAX_STATIONS_LISTED]
    assert warning["stations"] == first
    assert f"{sum(stations.values())} values of" in warning["message"]
    assert ", ".join(f"{station} {stations[station]}" for station in first) + ", and 2 more)" in warning["message"]


def test_a_parameter_left_out_is_not_told_as_one_without_rows_and_its_station_is_explained() -> None:
    """The source has the values: neither `parameter-without-rows` nor `station-without-rows` says it has none."""
    request = _dwd_stations(("00001", "00002")).request
    rows = ParameterRows(request, None, None, asked=["00001", "00002"])
    dataset = request.metadata["daily"]["climate_summary"]
    for station in ("00001", "00002"):
        rows.examine(station, [dataset])
        with rows.collecting(station):
            if station == "00001":
                note_open_window(NAME, 1, CLOSES, returned=False)
    rows.returned("00002")
    begin_response()

    rows.warn()

    assert [w["parameter"] for w in _told()] == [NAME]
    assert _told(PARAMETER_WITHOUT_ROWS) == []
    assert _told(STATION_WITHOUT_ROWS) == []


def test_a_parameter_returned_marked_is_no_reason_to_stay_silent_about_a_gap() -> None:
    """Values that were returned explain nothing: a station without rows is still told, and the parameter named."""
    request = _dwd_stations(("00001", "00002")).request
    rows = ParameterRows(request, None, None, asked=["00001", "00002"])
    dataset = request.metadata["daily"]["climate_summary"]
    for station in ("00001", "00002"):
        rows.examine(station, [dataset])
        with rows.collecting(station):
            if station == "00001":
                note_open_window(NAME, 1, CLOSES, returned=True)
    rows.returned("00001")
    begin_response()

    rows.warn()

    (warning,) = _told(STATION_WITHOUT_ROWS)
    assert warning["stations"] == ["00002"]


def test_nothing_is_told_where_no_window_was_open() -> None:
    """A walk that was told nothing says nothing."""
    request = _dwd_stations(("00001",)).request
    rows = ParameterRows(request, None, None)
    with rows.collecting("00001"):
        pass
    begin_response()

    rows.warn()

    assert _told() == []


def test_a_disabled_walk_says_nothing() -> None:
    """A walk that is not to warn (an estimate) does not tell the open windows either."""
    request = _dwd_stations(("00001",)).request
    rows = ParameterRows(request, None, None, enabled=False)
    with rows.collecting("00001"):
        note_open_window(NAME, 4, CLOSES, returned=False)
    begin_response()

    rows.warn()

    assert _told() == []


def test_the_hook_reaches_the_walk_that_is_collecting_and_no_other() -> None:
    """The callback is the block's alone: restored to the outer walk after an inner one, gone after both."""
    told: list[tuple[str, int, dt.datetime, bool]] = []
    other: list[tuple[str, int, dt.datetime, bool]] = []

    with collecting(lambda _: None, None, None, lambda *args: told.append(args)):
        note_open_window("a", 1, CLOSES, returned=False)
        with collecting(lambda _: None, None, None, lambda *args: other.append(args)):
            note_open_window("b", 2, CLOSES, returned=True)
        note_open_window("c", 3, CLOSES, returned=False)
    note_open_window("d", 4, CLOSES, returned=False)

    assert told == [("a", 1, CLOSES, False), ("c", 3, CLOSES, False)]
    assert other == [("b", 2, CLOSES, True)]


def test_the_hook_ignores_a_count_that_is_not_a_value_and_is_silent_outside_a_walk() -> None:
    """A count of 0 or less is not noted; the library as a library has no walk and does not raise."""
    told: list[tuple[str, int, dt.datetime, bool]] = []

    with collecting(lambda _: None, None, None, lambda *args: told.append(args)):
        note_open_window("a", 0, CLOSES, returned=False)
        note_open_window("a", -2, CLOSES, returned=False)
    note_open_window("a", 3, CLOSES, returned=False)
    with collecting(lambda _: None):
        note_open_window("a", 3, CLOSES, returned=False)

    assert told == []
