# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the stamp of SMHI daily values."""

import datetime as dt
import json
from io import BytesIO
from zoneinfo import ZoneInfo

import pytest

from wetterdienst import Settings
from wetterdienst.provider.smhi.observation import SmhiObservationRequest
from wetterdienst.provider.smhi.observation import api as smhi_api
from wetterdienst.provider.smhi.observation.parser import parse_smhi_csv
from wetterdienst.util.network import File

UTC = ZoneInfo("UTC")

# Rows of station 98230 (Stockholm-Observatoriekullen A), period corrected-archive, as SMHI writes them (the footnote
# columns after "Kvalitet" are left out). The daily means and the sums have 'Representativt dygn', the snow depth is
# an instantaneous value "kl 06" with a 'Datum' and a 'Tid (UTC)' of its own.
_FROM_TO = "Från Datum Tid (UTC);Till Datum Tid (UTC);Representativt dygn;{name};Kvalitet\n"
_FILES = {
    "parameter/2/": _FROM_TO.format(name="Lufttemperatur")
    + "2025-03-29 00:00:01;2025-03-30 00:00:00;2025-03-29;8.8;Y\n"
    + "2025-03-30 00:00:01;2025-03-31 00:00:00;2025-03-30;6.7;Y\n"
    + "2025-03-31 00:00:01;2025-04-01 00:00:00;2025-03-31;6.5;Y\n",
    "parameter/5/": _FROM_TO.format(name="Nederbördsmängd")
    + "2025-03-29 06:00:01;2025-03-30 06:00:00;2025-03-29;0.0;G\n"
    + "2025-03-30 06:00:01;2025-03-31 06:00:00;2025-03-30;0.0;G\n"
    + "2025-03-31 06:00:01;2025-04-01 06:00:00;2025-03-31;0.0;G\n",
    "parameter/19/": _FROM_TO.format(name="Lufttemperatur")
    + "2025-03-29 18:00:01;2025-03-30 18:00:00;2025-03-30;2.5;Y\n"
    + "2025-03-30 18:00:01;2025-03-31 18:00:00;2025-03-31;3.3;Y\n"
    + "2025-03-31 18:00:01;2025-04-01 18:00:00;2025-04-01;2.7;Y\n",
    "parameter/20/": _FROM_TO.format(name="Lufttemperatur")
    + "2025-03-29 18:00:01;2025-03-30 18:00:00;2025-03-30;9.9;Y\n"
    + "2025-03-30 18:00:01;2025-03-31 18:00:00;2025-03-31;10.4;Y\n"
    + "2025-03-31 18:00:01;2025-04-01 18:00:00;2025-04-01;14.6;Y\n",
    "parameter/8/": "Datum;Tid (UTC);Snödjup;Kvalitet\n"
    "2025-03-29;06:00:00;0.00;G\n"
    "2025-03-30;06:00:00;0.00;G\n"
    "2025-03-31;06:00:00;0.00;G\n",
}
_STATION = {
    "id": 98230,
    "name": "Stockholm-Observatoriekullen A",
    "latitude": 59.3417,
    "longitude": 18.0549,
    "height": 43.133,
    "from": 1738368000000,
    "to": 1791727200000,
}


def _serve(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve the station lists and the daily files of one station from the test."""

    def download_files(urls: list[str], **_: object) -> list[File]:
        body = json.dumps({"station": [_STATION]}).encode()
        return [File(url=url, content=BytesIO(body), status=200) for url in urls]

    def download_file(url: str, **_: object) -> File:
        if "corrected-archive" in url:
            for part, text in _FILES.items():
                if part in url:
                    return File(url=url, content=BytesIO(text.encode()), status=200)
        return File(url=url, content=FileNotFoundError(url), status=404)

    monkeypatch.setattr(smhi_api, "download_files", download_files)
    monkeypatch.setattr(smhi_api, "download_file", download_file)


def test_smhi_snow_depth_file_is_stamped_at_its_06_utc_reading_by_the_parser() -> None:
    """Test the premise: the parser gives the snow depth the instant of the reading, 06:00 UTC of its date.

    The stamp of the daily value is made from that in the values, where the day is taken.
    """
    df = parse_smhi_csv(_FILES["parameter/8/"])
    assert df.get_column("timestamp").to_list() == [dt.datetime(2025, 3, day, 6, tzinfo=UTC) for day in (29, 30, 31)]


@pytest.mark.parametrize("day", ["2025-03-30", "2025-03-31"])
def test_smhi_daily_values_are_stamped_at_00_utc_of_their_day_snow_depth_too(
    monkeypatch: pytest.MonkeyPatch, day: str
) -> None:
    """Test that a request for one day returns all five daily parameters, snow depth among them.

    Snow depth is "momentanvärde, 1 gång/dygn, kl 06" and its file has a 'Tid (UTC)' of 06:00:00, so it was stamped
    06:00 UTC besides the others at 00:00 UTC, and a request for one day dropped it (GH-2683). The reading of 06:00 UTC
    on a date belongs to that date.
    """
    _serve(monkeypatch)
    request = SmhiObservationRequest(
        parameters=[("daily", "data")], start=day, end=day, settings=Settings(cache_disable=True)
    ).filter_by_station_id("98230")
    df = request.values().all().df
    midnight = dt.datetime.fromisoformat(day).replace(tzinfo=UTC)
    assert df.get_column("timestamp").unique().to_list() == [midnight]
    assert sorted(df.get_column("parameter").cast(str).to_list()) == [
        "precipitation_amount",
        "snow_depth",
        "temperature_air_max_2m",
        "temperature_air_mean_2m",
        "temperature_air_min_2m",
    ]
