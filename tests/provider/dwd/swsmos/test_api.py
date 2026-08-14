# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD SWSMOS (road weather forecast) provider."""

import bz2
import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst.provider.dwd.swsmos import DwdSwsmosRequest
from wetterdienst.provider.dwd.swsmos.api import DwdForecastDate, _read_run_csv, _run_url

UTC = ZoneInfo("UTC")


def test_read_run_csv_drops_run_timestamp_line() -> None:
    """A run file's line-2 run timestamp is dropped so the header aligns with the data rows."""
    raw = (
        b"ID;Lat;Lon;YYYYMMDDHHmm;TL;RC;TS\n"
        b"202607310700\n"  # the run-timestamp line between header and data
        b"A006;54.889156;8.908735;202607310800;17.9;1;24.2\n"
        b"A006;54.889156;8.908735;202607310900;17.6;2;25.1\n"
    )
    df = _read_run_csv(bz2.compress(raw))
    assert df.columns == ["ID", "Lat", "Lon", "YYYYMMDDHHmm", "TL", "RC", "TS"]
    assert df.height == 2  # only the two data rows, not the run-timestamp line
    assert df["TL"].to_list() == ["17.9", "17.6"]


def test_read_run_csv_too_short() -> None:
    """A file without any data rows yields an empty frame rather than raising."""
    assert _read_run_csv(bz2.compress(b"ID;TL\n202607310700\n")).is_empty()


def test_run_url() -> None:
    """The run URL is built from the issue hour (minutes/seconds are always zero)."""
    url = _run_url(dt.datetime(2026, 7, 31, 7, 0, tzinfo=UTC))
    assert url.endswith("/swsmos_20260731070000_opendata.csv.bz2")


def test_issue_defaults_to_latest() -> None:
    """Without an explicit issue, the request targets the latest model run."""
    request = DwdSwsmosRequest(parameters=[("hourly", "data")])
    assert request.issue is DwdForecastDate.LATEST


def test_issue_string_parsed_to_utc_hour() -> None:
    """An ISO issue string is floored to a UTC hour."""
    request = DwdSwsmosRequest(parameters=[("hourly", "data")], issue="2026-07-31T07:34")
    assert request.issue == dt.datetime(2026, 7, 31, 7, tzinfo=UTC)


# ---------------------------------------------------------------------------
# Remote tests -- hit the live DWD opendata server. SWSMOS is a rolling forecast, so values are
# time-dependent; assert structure/ranges. xfail on outage matches the DWD/CHMI precedent.
# ---------------------------------------------------------------------------

xfail_if_dwd_unavailable = pytest.mark.xfail(strict=False, reason="DWD opendata intermittently unavailable")


@pytest.mark.remote
@xfail_if_dwd_unavailable
def test_swsmos_stations() -> None:
    """The road-station catalogue resolves to a populated set of German stations."""
    df = DwdSwsmosRequest(parameters=[("hourly", "data")]).all().df
    assert df.height > 1000
    assert df["resolution"].unique().to_list() == ["hourly"]
    # Germany: latitudes ~47-55 N, longitudes ~6-15 E
    assert df["latitude"].min() > 47.0
    assert df["latitude"].max() < 56.0
    assert df["longitude"].min() > 5.0
    assert df["longitude"].max() < 16.0


@pytest.mark.remote
@xfail_if_dwd_unavailable
def test_swsmos_values() -> None:
    """The latest run returns an hourly forecast with the expected parameters and sane ranges."""
    request = DwdSwsmosRequest(parameters=[("hourly", "data")])
    station_id = request.all().df["station_id"][0]
    df = request.filter_by_station_id(station_id).values.all().df
    assert not df.is_empty()
    assert df["resolution"].unique().to_list() == ["hourly"]
    assert set(df["parameter"].unique().to_list()) <= {
        "temperature_air_mean_2m",
        "temperature_dew_point_mean_2m",
        "temperature_surface_mean",
        "precipitation_height_liquid",
        "precipitation_height_last_6h",
        "probability_precipitation_liquid_last_6h",
        "probability_precipitation_height_gt_5mm_last_6h",
        "road_surface_condition",
    }
    # the forecast is hourly and lies in the future of the run
    dates = df["date"].unique().sort()
    assert len(dates) > 24  # multi-day hourly horizon
    deltas = dates.diff().drop_nulls().unique().to_list()
    assert deltas == [dt.timedelta(hours=1)]
    # air temperature in a physically plausible range
    air = df.filter(pl.col("parameter") == "temperature_air_mean_2m")["value"].drop_nulls()
    assert air.min() > -40.0
    assert air.max() < 55.0
    # dew point likewise -- swsmos publishes Celsius, unlike MOSMIX's Kelvin, and the whole of
    # Germany reading above 250 would mean we had silently inherited the MOSMIX unit
    dew_point = df.filter(pl.col("parameter") == "temperature_dew_point_mean_2m")["value"].drop_nulls()
    assert dew_point.min() > -40.0
    assert dew_point.max() < 40.0
    # and it cannot exceed the air temperature it is measured against
    assert dew_point.max() <= air.max()
