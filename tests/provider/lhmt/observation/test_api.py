# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for LHMT (Lithuania) observation provider."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from aiohttp import ClientPayloadError, ClientResponseError
from fsspec.exceptions import FSTimeoutError

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


def test_parse_lhmt_malformed_json_yields_empty() -> None:
    """A malformed 200 body (e.g. an HTML error page) yields an empty frame, not an exception."""
    assert parse_lhmt_observations(b"<html>rate limited</html>").is_empty()
    assert parse_lhmt_stations(b"not json").is_empty()


def test_parse_lhmt_skips_malformed_items() -> None:
    """Valid JSON with malformed items degrades to the good rows rather than raising."""
    # observations: a non-dict entry, one missing the timestamp, and one whose timestamp string is
    # malformed are all dropped; the cleanly-timestamped one stays (no exception for the bad string)
    obs = (
        b'{"station": {"code": "x"}, "observations": ['
        b'"garbage", {"airTemperature": 1.0}, '
        b'{"observationTimeUtc": "not-a-timestamp", "airTemperature": 9.9}, '
        b'{"observationTimeUtc": "2020-07-01 12:00:00", "airTemperature": 22.3}]}'
    )
    df = parse_lhmt_observations(obs)
    assert df["date"].unique().to_list() == [dt.datetime(2020, 7, 1, 12, 0, tzinfo=UTC)]
    temp = df.filter(pl.col("parameter") == "airTemperature")
    assert temp["value"].to_list() == [22.3]

    # stations: entries missing a code or coordinates are skipped; the complete one survives
    stations = (
        b'[{"name": "no code"}, {"code": "y", "coordinates": {}}, '
        b'{"code": "vilniaus-ams", "name": "Vilniaus AMS", '
        b'"coordinates": {"latitude": 54.6, "longitude": 25.1}}]'
    )
    sdf = parse_lhmt_stations(stations)
    assert sdf["station_id"].to_list() == ["vilniaus-ams"]


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        # single UTC day (start == end date) -> one day
        (dt.datetime(2020, 7, 1, tzinfo=UTC), dt.datetime(2020, 7, 1, 23, tzinfo=UTC), [dt.date(2020, 7, 1)]),
        # inclusive multi-day span -> every day incl. both ends
        (
            dt.datetime(2020, 7, 1, tzinfo=UTC),
            dt.datetime(2020, 7, 3, tzinfo=UTC),
            [dt.date(2020, 7, 1), dt.date(2020, 7, 2), dt.date(2020, 7, 3)],
        ),
        # month/year rollover
        (
            dt.datetime(2019, 12, 31, tzinfo=UTC),
            dt.datetime(2020, 1, 1, tzinfo=UTC),
            [dt.date(2019, 12, 31), dt.date(2020, 1, 1)],
        ),
        # a non-UTC start is converted to its UTC calendar date first: 01:00 in Vilnius (UTC+3) on
        # 2020-07-01 is 2020-06-30 22:00 UTC -- the PREVIOUS calendar day -- so the window must begin
        # on 2020-06-30 (a naive .date() without the UTC conversion would wrongly start on 2020-07-01)
        (
            dt.datetime(2020, 7, 1, 1, 0, tzinfo=ZoneInfo("Europe/Vilnius")),
            dt.datetime(2020, 7, 1, 12, tzinfo=UTC),
            [dt.date(2020, 6, 30), dt.date(2020, 7, 1)],
        ),
    ],
)
def test_days_covers_range_inclusive(start: dt.datetime, end: dt.datetime, expected: list[dt.date]) -> None:
    """`_days` yields every UTC calendar date in [start, end] inclusive, handling non-UTC inputs."""
    from wetterdienst.provider.lhmt.observation.api import _days  # noqa: PLC0415

    assert list(_days(start, end)) == expected


# ---------------------------------------------------------------------------
# Remote tests -- hit the live (key-less) api.meteo.lt. Historical data is stable, so exact values
# can be asserted. xfail (not hard-fail) on an outage matches the CHMI/AEMET precedent.
# ---------------------------------------------------------------------------

# scoped to the ways an upstream failure now reaches us: the providers raise transport errors
# instead of returning an empty frame, so an AssertionError here is our bug, not theirs
xfail_if_lhmt_unavailable = pytest.mark.xfail(
    raises=(FSTimeoutError, FileNotFoundError, ClientResponseError, ClientPayloadError),
    strict=False,
    reason="LHMT API intermittently unavailable",
)


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
