# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the NOAA Global Historical Climatology Network (GHCN) API."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst import Settings
from wetterdienst.provider.noaa.ghcn import NoaaGhcnMetadata, NoaaGhcnRequest


@pytest.mark.remote
@pytest.mark.slow
@pytest.mark.parametrize(
    ("start_date", "end_date"),
    [
        (dt.datetime(2015, 1, 1, tzinfo=ZoneInfo("UTC")), dt.datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC"))),
        (dt.datetime(2015, 1, 1, 1, tzinfo=ZoneInfo("UTC")), dt.datetime(2022, 1, 1, 1, tzinfo=ZoneInfo("UTC"))),
        (dt.datetime(2015, 1, 1, 1, 1, tzinfo=ZoneInfo("UTC")), dt.datetime(2022, 1, 1, 1, 1, tzinfo=ZoneInfo("UTC"))),
        (
            dt.datetime(2015, 1, 1, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
            dt.datetime(2022, 1, 1, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
        ),
    ],
)
def test_api_amsterdam(start_date: dt.datetime, end_date: dt.datetime, default_settings: Settings) -> None:
    """Test fetching of Amsterdam weather data."""
    request = NoaaGhcnRequest(
        parameters=[NoaaGhcnMetadata.daily.data.temperature_air_mean_2m],
        start=start_date,
        end=end_date,
        settings=default_settings,
    ).filter_by_name("DE BILT")
    given_df = request.values.all().df
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "NLM00006260",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "temperature_air_mean_2m",
                "timestamp": dt.datetime(2021, 1, 2, tzinfo=ZoneInfo("UTC")),
                "value": 3.7,
                # Global Summary of the Day (source S), a daily mean made of hourly values (measurement H): the
                # readme.txt's "H = for TMAX/TMIN/TAVG represents highest or lowest hourly temperature (TMAX or
                # TMIN) or the average of hourly values (TAVG)" and "S = Global Summary of the Day"; no check failed
                "quality_flags": "measurement:H,source:S",
            },
        ],
        schema={
            "station_id": pl.Enum(["NLM00006260"]),
            "resolution": pl.Enum(["daily"]),
            "dataset": pl.Enum(["data"]),
            "parameter": pl.Enum(["temperature_air_mean_2m"]),
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality_flags": pl.String,
        },
        orient="row",
    )
    assert_frame_equal(
        given_df.filter(pl.col("timestamp").eq(dt.datetime(2021, 1, 2, tzinfo=ZoneInfo("UTC")))),
        expected_df,
    )


@pytest.mark.remote
@pytest.mark.slow
def test_api_hourly_neustrelitz(default_settings: Settings) -> None:
    """Hourly (GHCNh) values parse with correct timestamps from the ISO date column."""
    request = NoaaGhcnRequest(
        parameters=[NoaaGhcnMetadata.hourly.data.temperature_air_2m],
        start=dt.datetime(1977, 1, 1, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(1977, 2, 1, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    ).filter_by_station_id("GMA00092791")  # Neustrelitz, Germany -- non-US, immutable historical data
    given_df = request.values.all().df
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "GMA00092791",
                "resolution": "hourly",
                "dataset": "data",
                "parameter": "temperature_air_2m",
                "timestamp": dt.datetime(1977, 1, 10, 2, tzinfo=ZoneInfo("UTC")),
                "value": 1.0,
                "quality_flags": None,
            },
        ],
        schema={
            "station_id": pl.Enum(["GMA00092791"]),
            "resolution": pl.Enum(["hourly"]),
            "dataset": pl.Enum(["data"]),
            "parameter": pl.Enum(["temperature_air_2m"]),
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality_flags": pl.String,
        },
        orient="row",
    )
    assert_frame_equal(
        given_df.filter(pl.col("timestamp").eq(dt.datetime(1977, 1, 10, 2, tzinfo=ZoneInfo("UTC")))),
        expected_df,
    )


def test_api_hourly_wind_direction_999_is_no_direction(monkeypatch: pytest.MonkeyPatch) -> None:
    """GHCNh writes 999 where no wind direction was given; it is no direction, while 999 hPa is a pressure (GH-2672).

    Rows of GHCNh_ACM00078861_por.psv (Antigua): 1942-01-17 02:00 reads 999 with code C (calm) and a wind speed of 0.0,
    1942-01-28 14:00 reads 999 with no code and a wind speed of 4.1. The documentation words the missing precipitation
    as -9999.
    """
    from tests.provider.value_stubs import serve  # noqa: PLC0415
    from wetterdienst.provider.noaa.ghcn import api  # noqa: PLC0415

    stations = (
        b"GHCN_ID,LATITUDE,LONGITUDE,ELEVATION,STATE,NAME,GSN,(US)HCN_(US)CRN,WMO_ID,ICAO,ISO_CODE\n"
        b"ACM00078861,17.1167,-61.7833,10.0,,COOLIDGE FIELD ANTIGUA,,,78861,,AG\n"
    )
    settings = Settings(cache_disable=True)
    metadata = NoaaGhcnRequest(parameters=[("hourly", "data")], settings=settings).metadata
    columns = [parameter.name_original for parameter in metadata["hourly"]["data"]]
    rows = {
        2: {"wind_direction": "999", "wind_speed": "0.0", "sea_level_pressure": "999.0", "precipitation": "-9999"},
        3: {"wind_direction": "0", "wind_speed": "0.0", "sea_level_pressure": "1001.5", "precipitation": "0.0"},
        4: {"wind_direction": "90", "wind_speed": "4.1", "sea_level_pressure": "1001.0", "precipitation": "0.2"},
        5: {"wind_direction": "999", "wind_speed": "4.1", "sea_level_pressure": "1000.0", "precipitation": "-9999.0"},
    }
    lines = ["|".join(["STATION", "DATE", *columns])]
    for hour, row in rows.items():
        cells = [row.get(column, "") for column in columns]
        lines.append("|".join(["ACM00078861", f"1942-01-17T{hour:02d}:00:00", *cells]))
    serve(monkeypatch, api, {"ghcnh-station-list": stations, "GHCNh_ACM00078861": "\n".join(lines).encode("utf8")})
    request = NoaaGhcnRequest(
        parameters=[("hourly", "data")],
        start=dt.datetime(1942, 1, 17, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(1942, 1, 18, tzinfo=ZoneInfo("UTC")),
        settings=settings,
    ).filter_by_station_id("ACM00078861")
    df = request.values.all().df.with_columns(pl.col("parameter").cast(pl.String))

    def column(parameter: str) -> list[tuple[int, float]]:
        frame = df.filter(pl.col("parameter").eq(parameter)).sort("timestamp")
        return list(
            zip(frame.get_column("timestamp").dt.hour().to_list(), frame.get_column("value").to_list(), strict=True)
        )

    # the hours without a direction have no row, as with every missing value
    assert column("wind_direction") == [(3, 0.0), (4, 90.0)]
    assert column("wind_speed") == [(2, 0.0), (3, 0.0), (4, 4.1), (5, 4.1)]
    assert column("pressure_air_sea_level") == [(2, 999.0), (3, 1001.5), (4, 1001.0), (5, 1000.0)]
    assert column("precipitation_amount") == [(3, 0.0), (4, 0.2)]
