# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What the real Frost serves of a parameter measured at several heights, held to properties only (GH-3844).

Frost answers every height of a station. The reader serves the standard height where it has a value and otherwise the
nearest one, and a bearing from the height of its speed. These tests read the same hours from Frost, all heights, and
hold what the reader returns to them, whatever the values are. The windows are in the past, so Frost's answer for them
does not move. The standard heights are re-stated here from Frost's `levels=default`, not read from the reader.
"""

from __future__ import annotations

import datetime as dt
import json
from collections import defaultdict
from urllib.parse import quote

import polars as pl
import pytest
from aiohttp import encode_basic_auth

from tests.conftest import FROST_RESOLVER_ON_MACOS
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.metno.frost.api import MetnoFrostRequest
from wetterdienst.settings import Settings
from wetterdienst.util.network import download_file

UTC = dt.UTC

pytestmark = [
    pytest.mark.remote,
    pytest.mark.skipif(
        not MetnoFrostRequest.is_configured(),
        reason="MET Norway Frost credentials not set — provide WD_AUTH__METNO_FROST=<client_id>",
    ),
    FROST_RESOLVER_ON_MACOS,
]


def _raw(station: str, element: str, resolution: str, start: dt.datetime, end: dt.datetime) -> dict[dt.datetime, dict]:
    """Give Frost's readings of the element, all heights, as {time: {height: value}} (a null is no reading)."""
    settings = Settings()
    client_id, secret = settings.auth.metno_frost
    url = (
        f"https://frost.met.no/observations/v0.jsonld?sources={station}&elements={quote(element)}"
        f"&referencetime={start:%Y-%m-%dT%H:%M:%S}/{end + dt.timedelta(seconds=1):%Y-%m-%dT%H:%M:%S}"
        f"&timeresolutions={resolution}"
    )
    file = download_file(
        url=url,
        cache_dir=settings.cache_dir,
        ttl=CacheExpiry.FIVE_MINUTES,
        client_kwargs={
            **settings.fsspec_client_kwargs,
            "headers": {"Authorization": encode_basic_auth(client_id.get_secret_value(), secret.get_secret_value())},
        },
        cache_disable=settings.cache_disable,
        use_certifi=settings.use_certifi,
    )
    assert file.status == 200, f"Frost answered {file.status} for {url}"
    readings: dict[dt.datetime, dict] = defaultdict(dict)
    for entry in json.load(file.content)["data"]:
        time = dt.datetime.fromisoformat(entry["referenceTime"])
        for observation in entry["observations"]:
            if observation["elementId"] == element and observation["value"] is not None:
                readings[time][observation["level"]["value"]] = observation["value"]
    return readings


def _values(station: str, resolution: str, names: list[str], start: dt.datetime, end: dt.datetime) -> pl.DataFrame:
    return (
        MetnoFrostRequest(
            parameters=[(resolution, "data", name) for name in names],
            start=start,
            end=end,
            options={"drop_nulls": True},
        )
        .filter_by_station_id(station)
        .values()
        .all()
        .df
    )


def _height(heights: dict, standard: float) -> float:
    """Give the height that has a value: the standard one, else the nearest, the lower of two as near."""
    return min(heights, key=lambda height: (abs(height - standard), height))


def _of(df: pl.DataFrame, name: str) -> dict[dt.datetime, float]:
    return dict(df.filter(pl.col("parameter") == name).select("timestamp", "value").iter_rows())


@pytest.mark.parametrize(
    ("station", "element", "name", "standard"),
    [
        ("SN18700", "air_temperature", "temperature_air_2m", 2.0),
        ("SN17850", "air_temperature", "temperature_air_2m", 2.0),
        ("SN99990", "air_temperature", "temperature_air_2m", 2.0),
        ("SN17850", "relative_humidity", "humidity_relative", 2.0),
    ],
)
def test_metno_frost_temperature_and_humidity_are_the_2_m_reading_wherever_there_is_one(
    station: str, element: str, name: str, standard: float
) -> None:
    """Test that every hour returned has the value of the 2 m sensor, whatever the other heights say."""
    start = dt.datetime(2026, 10, 1, tzinfo=UTC)
    end = dt.datetime(2026, 10, 4, tzinfo=UTC)
    raw = _raw(station, element, "PT1H", start, end)
    df = _values(station, "hourly", [name], start, end)
    returned = _of(df, name)
    assert returned
    several = 0
    for time, value in returned.items():
        heights = raw[time]
        several += len(heights) > 1
        assert value == pytest.approx(heights[_height(heights, standard)]), f"{station} {time}"
    assert several, f"{station} has no hour with more than one height in the window"


def test_metno_frost_the_gust_of_a_platform_is_the_10_m_reading() -> None:
    """Test that the 10 minute gust of SN76959 is the 10 m sensor's, not one of the 78 or 86 m sensors."""
    start = dt.datetime(2026, 10, 2, tzinfo=UTC)
    end = dt.datetime(2026, 10, 4, tzinfo=UTC)
    raw = _raw("SN76959", "max(wind_speed_of_gust PT10M)", "PT10M", start, end)
    returned = _of(_values("SN76959", "10_minutes", ["wind_gust_max"], start, end), "wind_gust_max")
    assert returned
    several = 0
    for time, value in returned.items():
        several += len(raw[time]) > 1
        assert value == pytest.approx(raw[time][_height(raw[time], 10.0)]), time
    assert several


def test_metno_frost_a_bearing_stands_beside_the_speed_of_its_own_height() -> None:
    """Test that a bearing returned is the reading of the height its time's speed was taken from.

    SN44300 measures the wind at 10 m and 2 m. The speed is the 10 m one where that has a value, and the bearing must be
    the 10 m bearing of the same time: no bearing is returned where 10 m has none, and the 2 m one never stands beside a
    10 m speed. Calms (a bearing of 0 beside a speed of 0) and `-3` are null and not compared.
    """
    start = dt.datetime(2026, 6, 1, tzinfo=UTC)
    end = dt.datetime(2026, 6, 8, tzinfo=UTC)
    speed_raw = _raw("SN44300", "wind_speed", "PT1H", start, end)
    direction_raw = _raw("SN44300", "wind_from_direction", "PT1H", start, end)
    df = _values("SN44300", "hourly", ["wind_speed_mean_last_10min", "wind_direction_mean_last_10min"], start, end)
    speeds = _of(df, "wind_speed_mean_last_10min")
    directions = _of(df, "wind_direction_mean_last_10min")
    assert speeds
    for time, value in speeds.items():
        assert value == pytest.approx(speed_raw[time][_height(speed_raw[time], 10.0)]), time
    beside = 0
    for time, value in directions.items():
        assert time in speeds, f"a bearing without a speed at {time}"
        height = _height(speed_raw[time], 10.0)
        assert height in direction_raw[time], f"a bearing at {time} where the speed's height {height} has none"
        assert value == pytest.approx(direction_raw[time][height]), time
        beside += 1
    assert beside
