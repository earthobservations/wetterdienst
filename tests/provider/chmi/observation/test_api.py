# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for CHMI observation provider."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst.provider.chmi.observation import ChmiObservationRequest
from wetterdienst.provider.chmi.observation.parser import (
    parse_chmi_stations,
    parse_chmi_values_aggregate,
    parse_chmi_values_daily,
    parse_chmi_values_subdaily,
)

CHEB = "0-20000-0-11406"
UTC = ZoneInfo("UTC")


def test_parse_chmi_stations_collapses_periods() -> None:
    """A relocated station collapses to one row: latest position, full extent, active end_date null."""
    content = (
        b"WSI,GH_ID,BEGIN_DATE,END_DATE,FULL_NAME,GEOGR1,GEOGR2,ELEVATION,\n"
        b"0-X,GA,1961-01-01T00:00Z,2000-12-31T23:59Z,Cheb,12.30,50.00,458,\n"
        b"0-X,GA,2001-01-01T00:00Z,3999-12-31T23:59Z,Cheb,12.391389,50.068333,483,\n"
    )
    df = parse_chmi_stations(content)
    assert df.to_dicts() == [
        {
            "station_id": "0-X",
            "name": "Cheb",
            "latitude": 50.068333,  # GEOGR2 of the most recent (active) period
            "longitude": 12.391389,  # GEOGR1 of the most recent period
            "height": 483.0,
            "start_date": dt.datetime(1961, 1, 1, tzinfo=UTC),  # earliest BEGIN_DATE
            "end_date": None,  # END_DATE year 3999 -> active -> null
        },
    ]


def test_parse_chmi_values_daily_selects_timefunc_and_truncates() -> None:
    """Daily parsing keeps only the requested TIMEFUNC and normalises the timestamp to the day."""
    content = (
        b"STATION,ELEMENT,TIMEFUNC,DT,VALUE,FLAG,QUALITY,\n"
        b"0-X,T,AVG,2020-01-01T00:00Z,-3.0,,0.0,\n"
        b"0-X,T,20:00,2020-01-01T20:00Z,-1.0,,0.0,\n"  # different TIMEFUNC -> excluded
        b"0-X,T,AVG,2020-01-02T00:00Z,-2.0,,0.0,\n"
    )
    df = parse_chmi_values_daily(content, element="T", timefunc="AVG")
    assert df.to_dicts() == [
        {"date": dt.datetime(2020, 1, 1, tzinfo=UTC), "parameter": "T", "value": -3.0},
        {"date": dt.datetime(2020, 1, 2, tzinfo=UTC), "parameter": "T", "value": -2.0},
    ]
    # a 20:00-term reading is truncated back to the calendar day (not kept at 20:00)
    df_max = parse_chmi_values_daily(content, element="T", timefunc="20:00")
    assert df_max.to_dicts() == [{"date": dt.datetime(2020, 1, 1, tzinfo=UTC), "parameter": "T", "value": -1.0}]


def test_parse_chmi_values_subdaily_keeps_native_timestamp() -> None:
    """Sub-daily parsing keeps the native timestamp (no TIMEFUNC, no truncation)."""
    content = (
        b"STATION,ELEMENT,DT,VALUE,FLAG,QUALITY,\n"
        b"0-X,T,2020-01-01T00:00Z,-2.8,,0.0,\n"
        b"0-X,T,2020-01-01T00:10Z,-2.7,,0.0,\n"
    )
    df = parse_chmi_values_subdaily(content, element="T")
    assert df.to_dicts() == [
        {"date": dt.datetime(2020, 1, 1, 0, 0, tzinfo=UTC), "parameter": "T", "value": -2.8},
        {"date": dt.datetime(2020, 1, 1, 0, 10, tzinfo=UTC), "parameter": "T", "value": -2.7},
    ]


def test_parse_chmi_values_aggregate_pins_both_functions() -> None:
    """Monthly/annual parsing must pin TIMEFUNCTION *and* MDFUNCTION to select a single series."""
    monthly = (
        b"STATION,ELEMENT,YEAR,MONTH,TIMEFUNCTION,MDFUNCTION,VALUE,FLAG_REPEAT,FLAG_INTERRUPTED,\n"
        b"0-X,T,2020,1,AVG,AVG,1.1,,,\n"
        b"0-X,T,2020,1,AVG,MAX,8.0,,,\n"  # same TIMEFUNCTION, different MDFUNCTION -> excluded
        b"0-X,T,2020,1,AVG,MIN,-9.0,,,\n"
    )
    df = parse_chmi_values_aggregate(monthly, element="T", timefunc="AVG", mdfunc="AVG", has_month=True)
    assert df.to_dicts() == [{"date": dt.datetime(2020, 1, 1, tzinfo=UTC), "parameter": "T", "value": 1.1}]

    # precipitation must select the SUM (monthly total), not another MDFUNCTION
    precip = (
        b"STATION,ELEMENT,YEAR,MONTH,TIMEFUNCTION,MDFUNCTION,VALUE,FLAG_REPEAT,FLAG_INTERRUPTED,\n"
        b"0-X,SRA,2020,1,06:00,SUM,21.3,,,\n"
        b"0-X,SRA,2020,1,06:00,MAX,7.0,,,\n"
    )
    df_precip = parse_chmi_values_aggregate(precip, element="SRA", timefunc="06:00", mdfunc="SUM", has_month=True)
    assert df_precip.to_dicts() == [{"date": dt.datetime(2020, 1, 1, tzinfo=UTC), "parameter": "SRA", "value": 21.3}]


def test_parse_chmi_values_aggregate_annual_has_no_month() -> None:
    """Annual files carry no MONTH column; the date is the year start."""
    annual = (
        b"STATION,ELEMENT,YEAR,TIMEFUNCTION,MDFUNCTION,VALUE,FLAG_REPEAT,FLAG_INTERRUPTED,\n0-X,T,2018,AVG,AVG,9.7,,,\n"
    )
    df = parse_chmi_values_aggregate(annual, element="T", timefunc="AVG", mdfunc="AVG", has_month=False)
    assert df.to_dicts() == [{"date": dt.datetime(2018, 1, 1, tzinfo=UTC), "parameter": "T", "value": 9.7}]


# CHMI's open-data portal is a live third-party service; xfail rather than a hard failure keeps a
# transient blip from blocking CI/merges, matching the AEMET/FMI precedent.
xfail_if_chmi_unavailable = pytest.mark.xfail(strict=False, reason="CHMI server intermittently unavailable")


def _values(resolution: str, start: dt.datetime, end: dt.datetime) -> pl.DataFrame:
    return (
        ChmiObservationRequest(
            parameters=[(resolution, "data")],
            start_date=start,
            end_date=end,
        )
        .filter_by_station_id(CHEB)
        .values.all()
        .df
    )


def _value_of(df: pl.DataFrame, parameter: str, date: dt.datetime) -> float:
    return df.filter(pl.col("parameter").eq(parameter), pl.col("date").eq(date)).get_column("value").item()


@pytest.mark.remote
@xfail_if_chmi_unavailable
def test_chmi_observation_stations() -> None:
    """Station metadata for Cheb matches the CHMI catalogue."""
    request = ChmiObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
    ).filter_by_station_id(CHEB)
    df = request.df
    assert df.select(pl.exclude("latitude", "longitude", "start_date", "end_date", "height")).to_dicts() == [
        {
            "resolution": "daily",
            "dataset": "data",
            "station_id": CHEB,
            "name": "Cheb",
            "state": None,
        },
    ]
    assert df["latitude"].item() == pytest.approx(50.068333)
    assert df["longitude"].item() == pytest.approx(12.391389)
    assert df["height"].item() == pytest.approx(483.0)
    assert df["start_date"].item() == dt.datetime(1863, 10, 1, tzinfo=UTC)
    assert df["end_date"].item() is None


@pytest.mark.remote
@xfail_if_chmi_unavailable
def test_chmi_observation_values_10_minutes() -> None:
    """10-minute values at Cheb for 2020-01-01 00:00 match the CHMI reference values."""
    df = _values("10_minutes", dt.datetime(2020, 1, 1, tzinfo=UTC), dt.datetime(2020, 1, 1, 0, 10, tzinfo=UTC))
    when = dt.datetime(2020, 1, 1, tzinfo=UTC)
    assert _value_of(df, "temperature_air_mean_2m", when) == pytest.approx(-2.8)
    assert _value_of(df, "humidity", when) == pytest.approx(0.92)
    assert _value_of(df, "pressure_air_site", when) == pytest.approx(975.8)
    assert _value_of(df, "wind_speed", when) == pytest.approx(1.3)


@pytest.mark.remote
@xfail_if_chmi_unavailable
def test_chmi_observation_values_hourly() -> None:
    """Hourly values at Cheb for 2020-01-01 00:00 match the CHMI reference values."""
    df = _values("hourly", dt.datetime(2020, 1, 1, tzinfo=UTC), dt.datetime(2020, 1, 1, 1, tzinfo=UTC))
    when = dt.datetime(2020, 1, 1, tzinfo=UTC)
    assert _value_of(df, "temperature_dew_point_mean_2m", when) == pytest.approx(-3.9)
    assert _value_of(df, "pressure_air_site", when) == pytest.approx(975.8)
    assert _value_of(df, "precipitation_height", when) == pytest.approx(0.0)


@pytest.mark.remote
@xfail_if_chmi_unavailable
def test_chmi_observation_values_daily() -> None:
    """Daily values at Cheb for 2020-01-01 match the CHMI reference values."""
    df = _values("daily", dt.datetime(2020, 1, 1, tzinfo=UTC), dt.datetime(2020, 1, 2, tzinfo=UTC))
    when = dt.datetime(2020, 1, 1, tzinfo=UTC)
    assert df["station_id"].unique().to_list() == [CHEB]
    assert _value_of(df, "temperature_air_mean_2m", when) == pytest.approx(-3.0)
    assert _value_of(df, "temperature_air_max_2m", when) == pytest.approx(1.5)
    assert _value_of(df, "temperature_air_min_2m", when) == pytest.approx(-6.9)
    assert _value_of(df, "precipitation_height", when) == pytest.approx(0.0)
    assert _value_of(df, "wind_speed", when) == pytest.approx(0.8)
    assert _value_of(df, "wind_gust_max", when) == pytest.approx(3.7)
    assert _value_of(df, "pressure_air_site", when) == pytest.approx(974.9)
    assert _value_of(df, "snow_depth", when) == pytest.approx(0.0)
    # CHMI reports humidity in percent; wetterdienst stores it as a fraction
    assert _value_of(df, "humidity", when) == pytest.approx(0.92)
    # CHMI reports sunshine in hours; wetterdienst stores it in seconds (5.9 h -> 21240 s)
    assert _value_of(df, "sunshine_duration", when) == pytest.approx(21240.0)


@pytest.mark.remote
@xfail_if_chmi_unavailable
def test_chmi_observation_values_monthly() -> None:
    """Monthly values at Cheb for 2020-01 match the CHMI reference values (means and sum)."""
    df = _values("monthly", dt.datetime(2020, 1, 1, tzinfo=UTC), dt.datetime(2020, 1, 2, tzinfo=UTC))
    when = dt.datetime(2020, 1, 1, tzinfo=UTC)
    assert _value_of(df, "temperature_air_mean_2m", when) == pytest.approx(1.1)
    assert _value_of(df, "temperature_air_max_2m", when) == pytest.approx(3.7)
    assert _value_of(df, "temperature_air_min_2m", when) == pytest.approx(-1.5)
    # precipitation is the monthly total (MDFUNCTION SUM), not an average
    assert _value_of(df, "precipitation_height", when) == pytest.approx(21.3)


@pytest.mark.remote
@xfail_if_chmi_unavailable
def test_chmi_observation_values_annual() -> None:
    """Annual values at Cheb for 2018 match the CHMI reference values (means and sum)."""
    df = _values("annual", dt.datetime(2018, 1, 1, tzinfo=UTC), dt.datetime(2018, 1, 2, tzinfo=UTC))
    when = dt.datetime(2018, 1, 1, tzinfo=UTC)
    assert _value_of(df, "temperature_air_mean_2m", when) == pytest.approx(9.7)
    assert _value_of(df, "temperature_air_max_2m", when) == pytest.approx(14.9)
    assert _value_of(df, "temperature_air_min_2m", when) == pytest.approx(5.0)
    assert _value_of(df, "precipitation_height", when) == pytest.approx(465.6)
