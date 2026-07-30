# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for LHMT (Lithuania) observation provider."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst.provider.lhmt.observation import LhmtObservationRequest
from wetterdienst.provider.lhmt.observation.parser import (
    parse_lhmt_observations,
    parse_lhmt_stations,
)

UTC = ZoneInfo("UTC")
VILNIUS = "vilniaus-ams"


def test_parse_lhmt_stations() -> None:
    """The station list maps to one row per station with coordinates from the nested object."""
    content = (
        b'[{"code": "vilniaus-ams", "name": "Vilniaus AMS", '
        b'"coordinates": {"latitude": 54.625992, "longitude": 25.107064}}]'
    )
    df = parse_lhmt_stations(content)
    assert df.to_dicts() == [
        {
            "station_id": "vilniaus-ams",
            "name": "Vilniaus AMS",
            "latitude": 54.625992,
            "longitude": 25.107064,
        },
    ]


def test_parse_lhmt_observations() -> None:
    """Observations become long rows; unmapped fields are dropped and missing values stay null."""
    content = (
        b'{"station": {"code": "vilniaus-ams"}, "observations": ['
        b'{"observationTimeUtc": "2020-07-01 12:00:00", "airTemperature": 22.3, '
        b'"feelsLikeTemperature": 22.3, "windSpeed": 4.7, "windGust": 12.3, "windDirection": 261, '
        b'"cloudCover": 63, "seaLevelPressure": 1007.4, "relativeHumidity": 52, '
        b'"precipitation": null, "snowDepth": 0, "conditionCode": "cloudy"}]}'
    )
    df = parse_lhmt_observations(content)
    by_param = {row["parameter"]: row["value"] for row in df.to_dicts()}
    assert by_param == {
        "airTemperature": 22.3,
        "windSpeed": 4.7,
        "windGust": 12.3,
        "windDirection": 261.0,
        "cloudCover": 63.0,
        "seaLevelPressure": 1007.4,
        "relativeHumidity": 52.0,
        "precipitation": None,  # null passes through as null (no sentinel)
        "snowDepth": 0.0,
    }
    # feelsLikeTemperature and conditionCode are intentionally not mapped
    assert "feelsLikeTemperature" not in by_param
    assert "conditionCode" not in by_param
    assert df["date"].to_list() == [dt.datetime(2020, 7, 1, 12, 0, tzinfo=UTC)] * len(df)


def test_parse_lhmt_observations_empty() -> None:
    """A day with no observations yields an empty frame with the expected schema."""
    content = b'{"station": {"code": "vilniaus-ams"}, "observations": []}'
    df = parse_lhmt_observations(content)
    assert df.is_empty()
    assert df.columns == ["date", "parameter", "value"]


# ---------------------------------------------------------------------------
# Remote tests -- hit the live (key-less) api.meteo.lt. Historical data is stable, so exact values
# can be asserted. xfail (not hard-fail) on an outage matches the CHMI/AEMET precedent.
# ---------------------------------------------------------------------------

xfail_if_lhmt_unavailable = pytest.mark.xfail(strict=False, reason="LHMT API intermittently unavailable")


@pytest.mark.remote
@xfail_if_lhmt_unavailable
def test_lhmt_observation_stations() -> None:
    """The station catalogue resolves to Lithuanian stations, including Vilnius."""
    df = LhmtObservationRequest(parameters=[("hourly", "data")]).all().df
    assert df.height > 40
    assert df["resolution"].unique().to_list() == ["hourly"]
    assert VILNIUS in df["station_id"].to_list()
    # Lithuania: latitudes ~53.9-56.4 N, longitudes ~21-26.8 E
    assert df["latitude"].min() > 53.0
    assert df["latitude"].max() < 57.0
    assert df["longitude"].min() > 20.0
    assert df["longitude"].max() < 27.0


@pytest.mark.remote
@xfail_if_lhmt_unavailable
def test_lhmt_observation_values() -> None:
    """Historical hourly values at Vilnius for 2020-07-01 match the api.meteo.lt reference values."""
    df = (
        LhmtObservationRequest(
            parameters=[("hourly", "data")],
            start_date=dt.datetime(2020, 7, 1, tzinfo=UTC),
            end_date=dt.datetime(2020, 7, 1, 23, tzinfo=UTC),
        )
        .filter_by_station_id(VILNIUS)
        .values.all()
        .df
    )
    assert not df.is_empty()
    assert df["resolution"].unique().to_list() == ["hourly"]

    def value_at(parameter: str, hour: int) -> float:
        return df.filter(
            pl.col("parameter") == parameter,
            pl.col("date") == dt.datetime(2020, 7, 1, hour, tzinfo=UTC),
        )["value"].item()

    assert value_at("temperature_air_mean_2m", 12) == pytest.approx(22.3)
    assert value_at("wind_speed", 12) == pytest.approx(4.7)
    assert value_at("wind_direction", 12) == pytest.approx(261.0)
    assert value_at("pressure_air_sea_level", 12) == pytest.approx(1007.4)
    # humidity is converted from percent to the default decimal target (52 % -> 0.52)
    assert value_at("humidity", 12) == pytest.approx(0.52)
