# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the stamp of Environment Agency hydrology daily values."""

from __future__ import annotations

import datetime as dt
import json
from io import BytesIO
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import pytest

from tests.provider.ea.hydrology.test_api import MEASURE_URL, STATION_URL, STATIONS_URL, _measure, _station
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


def _serve(monkeypatch: pytest.MonkeyPatch) -> None:
    station_id = "0004"
    notation = "flow-m-86400"
    listing = json.dumps({"items": [_station(station_id, [notation])]}).encode()
    station = json.dumps({"items": [{"measures": [_measure(station_id, notation)]}]}).encode()
    readings = json.dumps({"items": _READINGS}).encode()
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
