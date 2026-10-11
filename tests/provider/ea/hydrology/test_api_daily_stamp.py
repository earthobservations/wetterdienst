# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the stamp of Environment Agency hydrology daily values."""

from __future__ import annotations

import datetime as dt
import json
from io import BytesIO
from typing import TYPE_CHECKING, Any
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import pytest

from tests.provider.ea.hydrology.test_api import (
    MEASURE_URL,
    STATION_URL,
    STATIONS_URL,
    _measure,
    _station,
    _values_for,
)
from wetterdienst.provider.ea.hydrology import EAHydrologyRequest
from wetterdienst.provider.ea.hydrology import api as ea_api
from wetterdienst.util.network import File

if TYPE_CHECKING:
    from wetterdienst import Settings

# Readings of flow-m-86400 at station 052d0819-2a32-47df-9b99-c243c9c8235b, as the readings endpoint answers them: the
# daily mean is dated 09:00 of the day it names, whose 24 h run from there to 09:00 of the next day.
_READINGS = [
    {"dateTime": "2025-06-10T09:00:00", "value": 0.448, "quality": "Good"},
    {"dateTime": "2025-06-11T09:00:00", "value": 0.359, "quality": "Good"},
    {"dateTime": "2025-06-12T09:00:00", "value": 0.304, "quality": "Good"},
]


def _serve(
    monkeypatch: pytest.MonkeyPatch, notation: str = "flow-m-86400", readings_items: list[dict] | None = None
) -> None:
    station_id = "0004"
    listing = json.dumps({"items": [_station(station_id, [notation])]}).encode()
    station = json.dumps({"items": [{"measures": [_measure(station_id, notation)]}]}).encode()
    readings = json.dumps({"items": readings_items or _READINGS}).encode()
    readings_url = f"{MEASURE_URL.format(notation=f'{station_id}-{notation}-m3s-qualified')}/readings.json"

    def _download(**kwargs: Any) -> File:  # noqa: ANN401
        url = kwargs["url"]
        if url == STATIONS_URL:
            body = listing
        elif url == STATION_URL.format(station_id=station_id):
            body = station
        elif url.startswith(readings_url):
            body = readings
        else:
            msg = f"unexpected request to {url}"
            raise AssertionError(msg)
        return File(url=url, content=BytesIO(body), status=200)

    monkeypatch.setattr(ea_api, "download_file", _download)


@pytest.mark.parametrize("day", ["2025-06-10", "2025-06-11", "2025-06-12"])
def test_ea_daily_is_stamped_at_00_utc_of_the_day_it_names(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings, day: str
) -> None:
    """Test that a daily value is stamped at 00:00 UTC of its day, so a request for that one day returns it.

    The reading is dated D 09:00 and covers the 24 h from there, and was stamped so: a request with start=end=D,
    bounded at 00:00 UTC, returned nothing for it (GH-2683).
    """
    _serve(monkeypatch)
    request = EAHydrologyRequest(
        parameters=[("daily", "data", "discharge_mean")], start=day, end=day, settings=default_settings
    )
    df = request.all().values.all().df
    midnight = dt.datetime.fromisoformat(day).replace(tzinfo=ZoneInfo("UTC"))
    assert df.get_column("timestamp").to_list() == [midnight]
    assert df.get_column("value").to_list() == [{"2025-06-10": 0.448, "2025-06-11": 0.359, "2025-06-12": 0.304}[day]]


# Readings of flow-max-86400 at the same station: the maximum is dated at the instant of the extreme inside the 24 h
# from 09:00 of the day D it names to 09:00 of D+1, so 06-04T03:30 is the maximum of 06-03, 06-05T07:00 that of 06-04
# and 06-05T13:30 that of 06-05; two readings of one calendar date belong to two days.
_MAX_READINGS = [
    {"dateTime": "2025-06-04T03:30:00", "value": 1.096, "quality": "Good"},
    {"dateTime": "2025-06-05T07:00:00", "value": 0.93, "quality": "Good"},
    {"dateTime": "2025-06-05T13:30:00", "value": 1.316, "quality": "Good"},
]


@pytest.mark.parametrize(
    ("day", "expected"),
    [("2025-06-03", 1.096), ("2025-06-04", 0.93), ("2025-06-05", 1.316)],
)
def test_ea_daily_maximum_is_filed_under_the_day_of_its_window(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings, day: str, expected: float
) -> None:
    """Test that a maximum dated at the instant of its extreme is stamped at 00:00 UTC of the day its window names.

    Taking the date of the instant gave 06-05 two readings, one of which the deduplication dropped, and left 06-03
    with none (GH-2683).
    """
    _serve(monkeypatch, "flow-max-86400", _MAX_READINGS)
    request = EAHydrologyRequest(
        parameters=[("daily", "data", "discharge_max")], start=day, end=day, settings=default_settings
    )
    df = request.all().values.all().df
    midnight = dt.datetime.fromisoformat(day).replace(tzinfo=ZoneInfo("UTC"))
    assert df.get_column("timestamp").to_list() == [midnight]
    assert df.get_column("value").to_list() == [expected]


def test_ea_daily_readings_are_asked_for_up_to_09_of_the_day_after_the_window(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """Test that the readings request reaches the maximum of the window's last day, dated up to 09:00 after its end.

    The 24 h of the last day D run to D+1 09:00 and a maximum is dated at its instant inside them, so a request
    bound of D+1 00:00 left out the maximum of 2025-06-03 dated 2025-06-04T03:30 (GH-2683).
    """
    values, parameter = _values_for(
        ("daily", "data", "discharge_max"),
        default_settings,
        monkeypatch,
        start=dt.datetime(2025, 6, 3, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(2025, 6, 3, tzinfo=ZoneInfo("UTC")),
    )
    url = values._readings_url(MEASURE_URL.format(notation="x"), parameter)  # noqa: SLF001
    query = parse_qs(urlparse(url).query)
    assert query["mineq-dateTime"] == ["2025-06-02T00:00:00"]
    assert query["maxeq-dateTime"] == ["2025-06-04T09:00:00"]
