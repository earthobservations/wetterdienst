# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A date without a time is the whole day in Python and over REST alike (GH-3133).

The same inputs are given to a Python request as ``start`` and ``end`` and to the REST API as
``timestamp``, and both must hold the same window. The Python request is built directly; the REST API is
asked for the stations of a stubbed DWD index and tells the window it resolved in the ``metadata`` of its
answer, so nothing leaves the machine.
"""

from __future__ import annotations

import datetime as dt
from typing import Any
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from fastapi.testclient import TestClient

from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.ui.restapi import app
from wetterdienst.util.datetime import format_timestamp

_UTC = ZoneInfo("UTC")
_LAST = dt.timedelta(microseconds=1)


def _utc(*args: int) -> dt.datetime:
    return dt.datetime(*args, tzinfo=_UTC)


# (what Python is given, what REST is given as `timestamp`, the window both hold)
_SAME_INPUTS = [
    pytest.param(
        {"start": "2020-05-01", "end": "2020-05-03"},
        "2020-05-01/2020-05-03",
        (_utc(2020, 5, 1), _utc(2020, 5, 4) - _LAST),
        id="two dates: the end is the whole of the 3rd",
    ),
    pytest.param(
        {"start": "2020-05-01"},
        "2020-05-01",
        (_utc(2020, 5, 1), _utc(2020, 5, 2) - _LAST),
        id="a start alone is its day",
    ),
    pytest.param(
        {"end": "2020-05-01"},
        "2020-05-01",
        (_utc(2020, 5, 1), _utc(2020, 5, 2) - _LAST),
        id="an end alone is its day",
    ),
    pytest.param(
        {"start": "2020-05-01", "end": "2020-05-01"},
        "2020-05-01/2020-05-01",
        (_utc(2020, 5, 1), _utc(2020, 5, 2) - _LAST),
        id="one date as both bounds is its day",
    ),
    pytest.param(
        {"start": "2020-05-01T06:00:00", "end": "2020-05-03T00:00:00"},
        "2020-05-01T06:00:00/2020-05-03T00:00:00",
        (_utc(2020, 5, 1, 6), _utc(2020, 5, 3)),
        id="two datetimes stay exact, an end at midnight included",
    ),
    pytest.param(
        {"start": "2020-05-01T06:00:00", "end": "2020-05-03"},
        "2020-05-01T06:00:00/2020-05-03",
        (_utc(2020, 5, 1, 6), _utc(2020, 5, 4) - _LAST),
        id="a datetime start and a date end",
    ),
    pytest.param(
        {"start": "2020-05-01", "end": "2020-05-03T00:00:00"},
        "2020-05-01/2020-05-03T00:00:00",
        (_utc(2020, 5, 1), _utc(2020, 5, 3)),
        id="a date start and a datetime end, which stays exact",
    ),
    pytest.param(
        {"start": "2020-05-03T00:00:00+02:00"},
        "2020-05-03T00:00:00+02:00",
        (_utc(2020, 5, 2, 22), _utc(2020, 5, 2, 22)),
        id="an instant in another zone is that instant in UTC",
    ),
]


@pytest.fixture
def stubbed_index(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve one DWD station from memory, so that the REST API resolves a window and reads nothing upstream."""
    stations = pl.DataFrame(
        {
            "resolution": ["daily"],
            "dataset": ["climate_summary"],
            "station_id": ["01048"],
            "start_timestamp": [dt.datetime(1934, 1, 1, tzinfo=_UTC)],
            "end_timestamp": [None],
            "latitude": [51.1278],
            "longitude": [13.7543],
            "elevation": [227.0],
            "name": ["Dresden-Klotzsche"],
            "state": ["Sachsen"],
        },
        schema_overrides={"end_timestamp": pl.Datetime(time_zone="UTC")},
    )
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda _self: stations.lazy())


def _python_window(bounds: dict[str, Any]) -> tuple[dt.datetime | None, dt.datetime | None]:
    request = DwdObservationRequest(parameters="daily/kl", **bounds)
    return request.start, request.end


def _rest_window(timestamp: str) -> tuple[str, str]:
    response = TestClient(app).get(
        "/api/stations",
        params={
            "provider": "dwd",
            "network": "observation",
            "parameters": "daily/kl",
            "all": "true",
            "timestamp": timestamp,
            "with_metadata": "true",
        },
    )
    assert response.status_code == 200, response.text
    request = response.json()["metadata"]["request"]
    return request["start"], request["end"]


@pytest.mark.usefixtures("stubbed_index")
@pytest.mark.parametrize(("bounds", "timestamp", "window"), _SAME_INPUTS)
def test_python_and_rest_hold_the_same_window_for_the_same_inputs(
    bounds: dict[str, Any], timestamp: str, window: tuple[dt.datetime, dt.datetime]
) -> None:
    """`start`/`end` of Python and the `timestamp` of REST name one window, a date-only end covering its day."""
    assert _python_window(bounds) == window
    assert _rest_window(timestamp) == (format_timestamp(window[0]), format_timestamp(window[1]))


@pytest.mark.parametrize(
    "bound",
    [dt.date(2020, 5, 3), "2020-05-03"],
    ids=["date", "string"],
)
def test_a_date_is_the_whole_day_as_start_and_as_end(bound: dt.date | str) -> None:
    """A `datetime.date` and the string of the same date are one bound: the first instant, or the last, of the day."""
    assert _python_window({"start": bound}) == (_utc(2020, 5, 3), _utc(2020, 5, 4) - _LAST)
    assert _python_window({"start": "2020-05-01", "end": bound}) == (_utc(2020, 5, 1), _utc(2020, 5, 4) - _LAST)
    assert _python_window({"start": bound, "end": "2020-05-05"}) == (_utc(2020, 5, 3), _utc(2020, 5, 6) - _LAST)


@pytest.mark.parametrize(
    "bound",
    [
        dt.datetime(2020, 5, 3),  # noqa: DTZ001
        dt.datetime(2020, 5, 3, tzinfo=_UTC),
        "2020-05-03T00:00",
        "2020-05-03T00:00:00+00:00",
    ],
    ids=["naive datetime", "datetime", "string with a time", "string with a time and an offset"],
)
def test_a_datetime_at_midnight_is_an_instant_and_stays_exact(bound: dt.datetime | str) -> None:
    """Only a bound that names a day without a time is the day: midnight as a datetime is midnight."""
    assert _python_window({"start": "2020-05-01", "end": bound}) == (_utc(2020, 5, 1), _utc(2020, 5, 3))
    assert _python_window({"end": bound}) == (_utc(2020, 5, 3), _utc(2020, 5, 3))


def test_a_date_end_before_the_start_instant_of_the_same_day_is_not_reversed() -> None:
    """The end of a date is the end of its day, so a start inside that day is no reversed window."""
    assert _python_window({"start": "2020-05-03T12:00:00", "end": "2020-05-03"}) == (
        _utc(2020, 5, 3, 12),
        _utc(2020, 5, 4) - _LAST,
    )


def test_a_month_or_a_year_is_not_a_bound_of_python() -> None:
    """The month and year of the REST `timestamp` are its notation: `start`/`end` hold days and instants."""
    for bound in ("2020-05", "2020"):
        with pytest.raises(ValueError, match="isoformat"):
            DwdObservationRequest(parameters="daily/kl", end=bound)
