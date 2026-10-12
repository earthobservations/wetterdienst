# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the wind direction 0 of SMHI, which is no bearing (GH-2794)."""

import datetime as dt
import json
from io import BytesIO
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst import Options, Settings
from wetterdienst.provider.smhi.observation import SmhiObservationRequest
from wetterdienst.provider.smhi.observation import api as smhi_api
from wetterdienst.util.network import File

UTC = ZoneInfo("UTC")

# Rows of Abisko Aut (188790) as SMHI writes them (the footnote columns after "Kvalitet" are left out, checked
# 2026-10-12): the hourly direction (parameter 3, "medelvärde 10 min, 1 gång/tim") is 0 at 2019-01-18 04:00 and 08:00,
# where the wind speed (parameter 4) is 0.0, and 360 at 2019-03-15 11:00; the 1 minute direction (parameter 48, "1
# minuts medel varje minut") is the mean of the minute, 0.000000 at 09:07 of 2026-10-12 with a speed of 0.000000.
_HOURLY = (
    "Datum;Tid (UTC);Vindriktning;Kvalitet\n"
    "2019-01-18;03:00:00;208;G\n"
    "2019-01-18;04:00:00;0;G\n"
    "2019-01-18;08:00:00;0;G\n"
    "2019-03-15;11:00:00;360;G\n"
)
_MINUTE = "Datum;Tid (UTC);Vindriktning;Kvalitet\n2026-10-12;09:06:00;12.856694;G\n2026-10-12;09:07:00;0.000000;G\n"
_STATION = {
    "id": 188790,
    "name": "Abisko Aut",
    "latitude": 68.3538,
    "longitude": 18.8164,
    "height": 392.235,
    "from": 1538352000000,
    "to": 1791727200000,
}


def _serve(monkeypatch: pytest.MonkeyPatch, files: dict[str, str]) -> None:
    """Serve the station list and the files of one station, by the part of their url."""

    def download_files(urls: list[str], **_: object) -> list[File]:
        body = json.dumps({"station": [_STATION]}).encode()
        return [File(url=url, content=BytesIO(body), status=200) for url in urls]

    def download_file(url: str, **_: object) -> File:
        for part, text in files.items():
            if part in url:
                return File(url=url, content=BytesIO(text.encode()), status=200)
        return File(url=url, content=FileNotFoundError(url), status=404)

    monkeypatch.setattr(smhi_api, "download_files", download_files)
    monkeypatch.setattr(smhi_api, "download_file", download_file)


def _values(resolution: str, parameter: str, start: dt.datetime, end: dt.datetime) -> pl.DataFrame:
    request = SmhiObservationRequest(
        parameters=[(resolution, "data", parameter)],
        start=start,
        end=end,
        settings=Settings(cache_disable=True),
        options=Options(drop_nulls=False),
    )
    return request.filter_by_station_id("188790").values.all().df.sort("timestamp")


def test_smhi_hourly_wind_direction_of_0_is_null_and_360_is_north(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the hourly direction 0 is null with `raw:0` beside the quality code, and 360 stays (GH-2794)."""
    _serve(monkeypatch, {"parameter/3/station/188790/period/corrected-archive": _HOURLY})
    df = _values(
        "hourly",
        "wind_direction_last_10min",
        dt.datetime(2019, 1, 18, tzinfo=UTC),
        dt.datetime(2019, 3, 16, tzinfo=UTC),
    )
    assert df.select("value", "quality_flags").rows() == [
        (208.0, "G"),
        (None, "G,raw:0"),
        (None, "G,raw:0"),
        (360.0, "G"),
    ]


def test_smhi_1_minute_wind_direction_of_0_is_null_as_the_source_writes_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the 1 minute direction `0.000000` is null, and keeps the text SMHI wrote in `raw:` (GH-2794)."""
    _serve(monkeypatch, {"parameter/48/station/188790/period/latest-day": _MINUTE})
    df = _values(
        "1_minute",
        "wind_direction",
        dt.datetime(2026, 10, 12, 9, tzinfo=UTC),
        dt.datetime(2026, 10, 12, 10, tzinfo=UTC),
    )
    assert df.select("value", "quality_flags").rows() == [(12.8567, "G"), (None, "G,raw:0.000000")]


def test_smhi_wind_speed_of_0_is_a_reading(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that only a direction is mapped: the 0.0 of a wind speed stays, without a `raw:` token (GH-2794)."""
    speed = "Datum;Tid (UTC);Vindhastighet;Kvalitet\n2019-01-18;04:00:00;0.0;G\n2019-01-18;05:00:00;1.5;G\n"
    _serve(monkeypatch, {"parameter/4/station/188790/period/corrected-archive": speed})
    df = _values(
        "hourly",
        "wind_speed_last_10min",
        dt.datetime(2019, 1, 18, tzinfo=UTC),
        dt.datetime(2019, 1, 19, tzinfo=UTC),
    )
    assert df.select("value", "quality_flags").rows() == [(0.0, "G"), (1.5, "G")]
