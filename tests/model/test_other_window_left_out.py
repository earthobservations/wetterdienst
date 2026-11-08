# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The dates a provider leaves out for another window are told by one `other-window-left-out` warning (GH-3832).

Frost keeps two series of the daily and the monthly precipitation sum, 06-06 UTC and 18-18 UTC, and the reader returns
the first. A date that only the other series has is left out, and the answer says so: the source holds values there, so
it is no `parameter-without-rows`. The warning is raised from the walk (`ParameterRows.warn`), over the hook of the
provider (`note_left_out`), with the limits the docs promise: one for each parameter, the first ten stations, and the
dates at each.
"""

from __future__ import annotations

from typing import Any

from tests.model.test_file_skipped import _dwd_stations
from wetterdienst.model.parameter_rows import MAX_STATIONS_LISTED, ParameterRows
from wetterdienst.util.response_warnings import (
    OTHER_WINDOW_LEFT_OUT,
    PARAMETER_WITHOUT_ROWS,
    begin_response,
    collecting,
    note_left_out,
    recorded_warnings,
)

NAME = "daily/climate_summary/temperature_air_mean_2m"
BECAUSE = "these dates are of another series"


def _told(code: str = OTHER_WINDOW_LEFT_OUT) -> list[dict[str, Any]]:
    """Give the warnings of `code` that the request being served has recorded."""
    return [warning for warning in recorded_warnings() if warning["code"] == code]


def _walk(left_out: dict[str, int]) -> ParameterRows:
    """Give the walk over the stations of `left_out`, each of which left that many dates of `NAME` out."""
    request = _dwd_stations(tuple(left_out)).request
    rows = ParameterRows(request, None, None)
    dataset = request.metadata["daily"]["climate_summary"]
    for station, count in left_out.items():
        rows.examine(station, [dataset])
        with rows.collecting(station):
            note_left_out(NAME, count, BECAUSE)
    return rows


def test_the_dates_of_each_station_are_summed_and_told_once() -> None:
    """Two stations, one warning, with the dates at each and their sum; the clause of the provider ends the sentence."""
    rows = _walk({"00001": 3, "00002": 5})
    begin_response()

    rows.warn()

    (warning,) = _told()
    assert warning["parameter"] == NAME
    assert warning["stations"] == ["00001", "00002"]
    assert (
        "on 8 dates that are not in the answer (00001 3, 00002 5): these dates are of another series."
        in warning["message"]
    )


def test_one_date_is_told_in_the_singular() -> None:
    """One date at one station reads as one."""
    rows = _walk({"00001": 1})
    begin_response()

    rows.warn()

    (warning,) = _told()
    assert "on 1 date that is not in the answer (00001 1)" in warning["message"]


def test_only_the_first_ten_stations_are_listed_and_the_message_says_how_many_more() -> None:
    """A request for a whole network names ten stations and the number of the others, and sums all of them."""
    stations = {f"{number:05d}": number for number in range(1, 13)}
    rows = _walk(stations)
    begin_response()

    rows.warn()

    (warning,) = _told()
    first = list(stations)[:MAX_STATIONS_LISTED]
    assert warning["stations"] == first
    # the sum is of all 12 stations (78), the list of ten, and the rest is counted
    assert f"on {sum(stations.values())} dates that are not in the answer" in warning["message"]
    assert ", ".join(f"{station} {stations[station]}" for station in first) + ", and 2 more)" in warning["message"]
    assert "00011" not in warning["message"]
    assert "00012" not in warning["message"]


def test_exactly_ten_stations_say_nothing_of_more() -> None:
    """Ten stations are all listed and there is no "and 0 more"."""
    rows = _walk({f"{number:05d}": 1 for number in range(1, 11)})
    begin_response()

    rows.warn()

    (warning,) = _told()
    assert len(warning["stations"]) == MAX_STATIONS_LISTED
    assert "more)" not in warning["message"]


def test_a_parameter_the_provider_named_is_not_told_as_one_without_rows() -> None:
    """The station has values of the parameter: `parameter-without-rows` says nothing of it, the new warning does."""
    rows = _walk({"00001": 2})
    begin_response()

    rows.warn()

    assert [w["parameter"] for w in _told()] == [NAME]
    assert _told(PARAMETER_WITHOUT_ROWS) == []


def test_nothing_is_told_where_nothing_was_left_out() -> None:
    """A walk that was told nothing says nothing, and `parameter-without-rows` is what it was."""
    request = _dwd_stations(("00001",)).request
    rows = ParameterRows(request, None, None)
    rows.examine("00001", [request.metadata["daily"]["climate_summary"]])
    with rows.collecting("00001"):
        pass
    begin_response()

    rows.warn()

    assert _told() == []
    assert [w["parameter"] for w in _told(PARAMETER_WITHOUT_ROWS)] == ["daily/climate_summary"]


def test_a_disabled_walk_says_nothing() -> None:
    """A walk that is not to warn (an estimate) does not tell the dates left out either."""
    request = _dwd_stations(("00001",)).request
    rows = ParameterRows(request, None, None, enabled=False)
    with rows.collecting("00001"):
        note_left_out(NAME, 4, BECAUSE)
    begin_response()

    rows.warn()

    assert _told() == []


# the hook of the provider


def test_the_hook_reaches_the_walk_that_is_collecting_and_no_other() -> None:
    """The callback is the block's alone: restored to the outer walk after an inner one, gone after both."""
    told: list[tuple[str, int, str]] = []
    other: list[tuple[str, int, str]] = []

    with collecting(lambda *_: None, None, lambda *args: told.append(args)):
        note_left_out("a", 1, "x")
        with collecting(lambda *_: None, None, lambda *args: other.append(args)):
            note_left_out("b", 2, "y")
        note_left_out("c", 3, "z")
    note_left_out("d", 4, "w")

    assert told == [("a", 1, "x"), ("c", 3, "z")]
    assert other == [("b", 2, "y")]


def test_the_hook_ignores_a_count_that_is_not_a_date() -> None:
    """No dates, no warning: a count of 0 or less is not noted."""
    told: list[tuple[str, int, str]] = []

    with collecting(lambda *_: None, None, lambda *args: told.append(args)):
        note_left_out("a", 0, "x")
        note_left_out("a", -2, "x")

    assert told == []


def test_the_hook_is_silent_outside_a_walk_and_where_the_walk_does_not_listen() -> None:
    """The library as a library has no walk, and a walk of another kind has no callback: neither raises."""
    note_left_out("a", 3, "x")
    with collecting(lambda *_: None):
        note_left_out("a", 3, "x")
