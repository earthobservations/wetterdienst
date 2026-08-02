# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for IPMA (Portugal) observation provider."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst.provider.ipma.observation import IpmaObservationRequest
from wetterdienst.provider.ipma.observation.parser import (
    extract_ipma_station_observations,
    parse_ipma_observations,
    parse_ipma_observations_feed,
    parse_ipma_stations,
)

UTC = ZoneInfo("UTC")


def test_parse_ipma_stations() -> None:
    """The GeoJSON catalogue maps to one row per station; coordinates come from the geometry."""
    content = (
        b'[{"geometry": {"type": "Point", "coordinates": [-9.1333, 38.7667]}, "type": "Feature", '
        b'"properties": {"idEstacao": 1200579, "localEstacao": "Lisboa (Geof\xc3\xadsico)"}}]'
    )
    df = parse_ipma_stations(content)
    assert df.to_dicts() == [
        {
            "station_id": "1200579",
            "name": "Lisboa (Geofísico)",
            "latitude": 38.7667,
            "longitude": -9.1333,
        },
    ]


def test_parse_ipma_stations_feature_collection() -> None:
    """A standard GeoJSON FeatureCollection wrapper is accepted as well as the bare array."""
    content = (
        b'{"type": "FeatureCollection", "features": [{"geometry": {"type": "Point", '
        b'"coordinates": [-9.1333, 38.7667]}, "type": "Feature", '
        b'"properties": {"idEstacao": 1200579, "localEstacao": "Lisboa"}}]}'
    )
    df = parse_ipma_stations(content)
    assert df.to_dicts() == [
        {"station_id": "1200579", "name": "Lisboa", "latitude": 38.7667, "longitude": -9.1333},
    ]


def test_parse_ipma_observations_feed_extract_multiple_stations() -> None:
    """The feed is deserialised once and reused to extract each station independently."""
    content = b'{"2026-07-29T14:00": {"1200579": {"temperatura": 27.5}, "1210881": {"temperatura": 19.0}}}'
    feed = parse_ipma_observations_feed(content)
    assert set(feed["2026-07-29T14:00"]) == {"1200579", "1210881"}
    first = extract_ipma_station_observations(feed, station_id="1200579")
    second = extract_ipma_station_observations(feed, station_id="1210881")
    assert first.filter(pl.col("parameter") == "temperatura")["value"].to_list() == [27.5]
    assert second.filter(pl.col("parameter") == "temperatura")["value"].to_list() == [19.0]


def test_parse_ipma_observations_feed_rejects_non_object() -> None:
    """A payload that is not a JSON object yields an empty feed rather than raising."""
    assert parse_ipma_observations_feed(b"[]") == {}


def test_parse_ipma_observations_sentinel_and_wind_code() -> None:
    """-99 sentinels become null and the wind-direction code is converted to degrees."""
    content = (
        b'{"2026-07-29T14:00": {"1200579": {'
        b'"temperatura": 27.5, "humidade": 54.0, "pressao": 1018.6, '
        b'"intensidadeVento": 3.1, "intensidadeVentoKM": 11.2, "idDireccVento": 4, '
        b'"precAcumulada": -99.0, "radiacao": 3151.3}}}'
    )
    df = parse_ipma_observations(content, station_id="1200579")
    by_param = {row["parameter"]: row["value"] for row in df.to_dicts()}
    assert by_param["temperatura"] == 27.5
    assert by_param["humidade"] == 54.0
    assert by_param["pressao"] == 1018.6
    assert by_param["intensidadeVento"] == 3.1
    assert by_param["idDireccVento"] == 135.0  # code 4 == SE == 135°
    assert by_param["precAcumulada"] is None  # -99 sentinel -> null
    assert by_param["radiacao"] == 3151.3
    # intensidadeVentoKM is not a mapped parameter -> not emitted
    assert "intensidadeVentoKM" not in by_param
    assert df["date"].to_list() == [dt.datetime(2026, 7, 29, 14, 0, tzinfo=UTC)] * len(df)


@pytest.mark.parametrize(
    ("code", "expected_degrees"),
    [
        (0, None),  # calm / no direction -> null (not 0°)
        (1, 0.0),  # N
        (2, 45.0),  # NE
        (3, 90.0),  # E
        (4, 135.0),  # SE
        (5, 180.0),  # S
        (6, 225.0),  # SW
        (7, 270.0),  # W
        (8, 315.0),  # NW
        (9, 0.0),  # N (alias of 1)
    ],
)
def test_parse_ipma_observations_wind_direction_codes(code: int, expected_degrees: float | None) -> None:
    """Every IPMA wind-direction code 0-9 maps to the expected degrees (0/calm -> null, 9 aliases N)."""
    content = f'{{"2026-07-29T14:00": {{"1200579": {{"idDireccVento": {code}}}}}}}'.encode()
    df = parse_ipma_observations(content, station_id="1200579")
    wind = df.filter(pl.col("parameter") == "idDireccVento")
    assert wind["value"].to_list() == [expected_degrees]


def test_parse_ipma_observations_skips_absent_station() -> None:
    """A station that reported nothing for a timestamp is skipped."""
    content = b'{"2026-07-29T14:00": {"9999999": {"temperatura": 20.0}}}'
    df = parse_ipma_observations(content, station_id="1200579")
    assert df.is_empty()


# ---------------------------------------------------------------------------
# Remote tests -- hit the live (key-less) IPMA feed. It is a rolling ~1-day window, so values
# are time-dependent; assert structure/ranges rather than exact numbers. xfail (not hard-fail) on an
# outage keeps a transient blip from blocking CI, matching the CHMI/AEMET precedent.
# ---------------------------------------------------------------------------

xfail_if_ipma_unavailable = pytest.mark.xfail(strict=False, reason="IPMA API intermittently unavailable")


@pytest.mark.remote
@xfail_if_ipma_unavailable
def test_ipma_observation_stations() -> None:
    """The station catalogue resolves to a populated set of Portuguese stations."""
    df = IpmaObservationRequest(parameters=[("hourly", "data")]).all().df
    assert df.height > 100
    assert df["resolution"].unique().to_list() == ["hourly"]
    # mainland Portugal + Azores/Madeira: latitudes ~30-42 N, longitudes ~-32 to -6 E
    assert df["latitude"].min() > 29.0
    assert df["latitude"].max() < 43.0
    assert df["longitude"].min() > -32.0
    assert df["longitude"].max() < -5.0


@pytest.mark.remote
@xfail_if_ipma_unavailable
def test_ipma_observation_values() -> None:
    """A station returns recent hourly values with sane ranges and 45°-quantised wind direction."""
    request = IpmaObservationRequest(
        parameters=[("hourly", "data")],
        start_date=dt.datetime.now(UTC) - dt.timedelta(hours=24),
        end_date=dt.datetime.now(UTC),
    )
    station_id = request.all().df["station_id"][0]
    df = request.filter_by_station_id(station_id).values.all().df
    assert not df.is_empty()
    assert df["resolution"].unique().to_list() == ["hourly"]
    assert set(df["parameter"].unique().to_list()) <= {
        "temperature_air_mean_2m",
        "humidity",
        "pressure_air_sea_level",
        "wind_speed",
        "wind_direction",
        "precipitation_height",
        "radiation_global",
    }
    # wind direction is emitted in degrees, quantised to the 8-point compass (multiples of 45)
    wind = df.filter(pl.col("parameter") == "wind_direction").drop_nulls("value")
    assert all(v % 45 == 0 for v in wind["value"].to_list())
