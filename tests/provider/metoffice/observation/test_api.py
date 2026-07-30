# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for Met Office (MIDAS Open) observation provider."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst.provider.metoffice.observation import MetOfficeObservationRequest
from wetterdienst.provider.metoffice.observation.parser import (
    parse_station_metadata,
    parse_values,
)

UTC = ZoneInfo("UTC")

# a busy long-running station (Lerwick, Shetland) present across most MIDAS Open datasets
LERWICK = "00009"


def _badc(header_rows: bytes, columns: str, data_rows: bytes) -> bytes:
    """Assemble a minimal BADC-CSV file: G-attribute header, a bare ``data`` line, table, trailer."""
    return header_rows + b"data\n" + columns.encode() + b"\n" + data_rows + b"end data\n"


def test_parse_station_metadata() -> None:
    """The station-metadata catalogue maps to one row per station with year-bounded dates."""
    content = _badc(
        b"Conventions,G,BADC-CSV,1\ntitle,G,Midas-open: Station site metadata\n",
        "src_id,station_name,station_file_name,historic_county,authority,"
        "station_latitude,station_longitude,station_elevation,first_year,last_year",
        b"00001,FOULA,foula,shetland,Met Office,60.154,-2.074,22,1989,2003\n",
    )
    df = parse_station_metadata(content)
    assert df.to_dicts() == [
        {
            "station_id": "00001",
            "name": "FOULA",
            "historic_county": "shetland",
            "station_file_name": "foula",
            "latitude": 60.154,
            "longitude": -2.074,
            "height": 22.0,
            "start_date": dt.datetime(1989, 1, 1, tzinfo=UTC),
            "end_date": dt.datetime(2003, 12, 31, tzinfo=UTC),
        },
    ]


def test_parse_values_collapses_multiple_report_types() -> None:
    """A day with 12h night/day readings plus a 24h reading collapses to one daily extreme.

    ``max`` for max-type, ``min`` for ``min_columns`` is idempotent over the duplication, so the
    result equals the true 24-hour value regardless of which report types a station transmits.
    """
    content = _badc(
        b"Conventions,G,BADC-CSV,1\n",
        "ob_end_time,ob_hour_count,met_domain_name,max_air_temp,max_air_temp_q,min_air_temp,min_air_temp_q",
        # night 12h (ends 09:00), full-day 24h (ends 09:00), day 12h (ends 21:00)
        b"2000-01-01 09:00:00,12,AWSDLY,4.8,6,0.3,6\n"
        b"2000-01-01 09:00:00,24,DLY3208,5.4,4,0.3,4\n"
        b"2000-01-01 21:00:00,12,AWSDLY,5.1,6,2.8,6\n",
    )
    df = parse_values(
        content,
        time_column="ob_end_time",
        columns=["max_air_temp", "min_air_temp"],
        granularity="1d",
        min_columns=frozenset({"min_air_temp"}),
    ).sort("parameter")
    assert df.to_dicts() == [
        # max over {4.8, 5.4, 5.1} == the 24h value 5.4; quality is that of the extreme row
        {"date": dt.datetime(2000, 1, 1, tzinfo=UTC), "parameter": "max_air_temp", "value": 5.4, "quality": 4.0},
        # min over {0.3, 0.3, 2.8} == 0.3
        {"date": dt.datetime(2000, 1, 1, tzinfo=UTC), "parameter": "min_air_temp", "value": 0.3, "quality": 6.0},
    ]


def test_parse_values_drops_multiday_accumulations() -> None:
    """Rows whose period-count column isn't 1 are dropped (multi-day rain accumulations)."""
    content = _badc(
        b"Conventions,G,BADC-CSV,1\n",
        "ob_date,ob_day_cnt,prcp_amt,prcp_amt_q",
        b"2000-01-01 00:00:00,31,146.7,22576\n"  # 31-day accumulation -> dropped
        b"2000-01-02 00:00:00,1,3.7,2576\n",  # genuine single-day value -> kept
    )
    df = parse_values(
        content,
        time_column="ob_date",
        columns=["prcp_amt"],
        granularity="1d",
        period_count_column="ob_day_cnt",
    )
    assert df.to_dicts() == [
        {"date": dt.datetime(2000, 1, 2, tzinfo=UTC), "parameter": "prcp_amt", "value": 3.7, "quality": 2576.0},
    ]


def test_parse_values_scales_visibility_to_metres() -> None:
    """Visibility is stored in decametres and scaled to metres; hourly timestamps are preserved."""
    content = _badc(
        b"Conventions,G,BADC-CSV,1\n",
        "ob_time,visibility,visibility_q",
        b"2015-07-01 13:00:00,1900,6\n",  # 1900 decametres -> 19000 metres (19 km)
    )
    df = parse_values(
        content,
        time_column="ob_time",
        columns=["visibility"],
        granularity="1h",
        scale={"visibility": 10.0},
    )
    assert df.to_dicts() == [
        {
            "date": dt.datetime(2015, 7, 1, 13, 0, tzinfo=UTC),
            "parameter": "visibility",
            "value": 19000.0,
            "quality": 6.0,
        },
    ]


def test_parse_values_empty_input() -> None:
    """A file with no data rows yields an empty frame with the expected schema."""
    content = _badc(b"Conventions,G,BADC-CSV,1\n", "ob_date,prcp_amt", b"")
    df = parse_values(content, time_column="ob_date", columns=["prcp_amt"], granularity="1d")
    assert df.is_empty()
    assert df.columns == ["date", "parameter", "value", "quality"]


# ---------------------------------------------------------------------------
# Remote tests -- require a free CEDA account (WD_AUTH__CEDA=<username>:<password>).
# ---------------------------------------------------------------------------

pytest_credentials = pytest.mark.skipif(
    not MetOfficeObservationRequest.is_configured(),
    reason="CEDA credentials not set -- provide WD_AUTH__CEDA=<username>:<password>",
)


@pytest.mark.remote
@pytest_credentials
def test_metoffice_observation_stations() -> None:
    """The daily-rain catalogue resolves and contains the reference station."""
    df = (
        MetOfficeObservationRequest(parameters=[("daily", "rain", "precipitation_height")])
        .filter_by_station_id(LERWICK)
        .df
    )
    assert df.height == 1
    row = df.row(0, named=True)
    assert row["station_id"] == LERWICK
    assert row["resolution"] == "daily"
    assert row["dataset"] == "rain"
    assert row["name"]  # a non-empty station name
    assert 59.0 < row["latitude"] < 61.0  # Shetland
    assert -2.0 < row["longitude"] < -1.0


@pytest.mark.remote
@pytest_credentials
def test_metoffice_observation_values_daily_rain() -> None:
    """Daily precipitation returns one day-truncated row per day, all non-negative."""
    df = (
        MetOfficeObservationRequest(
            parameters=[("daily", "rain", "precipitation_height")],
            start_date=dt.datetime(2023, 7, 1, tzinfo=UTC),
            end_date=dt.datetime(2023, 7, 10, tzinfo=UTC),
        )
        .filter_by_station_id(LERWICK)
        .values.all()
        .df
    )
    assert not df.is_empty()
    assert df["resolution"].unique().to_list() == ["daily"]
    assert df["parameter"].unique().to_list() == ["precipitation_height"]
    # one value per day, timestamps truncated to midnight
    assert (df["date"] == df["date"].dt.truncate("1d")).all()
    assert df["date"].n_unique() == df.height
    assert df["value"].min() >= 0.0


@pytest.mark.remote
@pytest_credentials
def test_metoffice_observation_values_daily_temperature_one_row_per_day() -> None:
    """Daily temperature collapses multiple report types to a single row per day/parameter."""
    df = (
        MetOfficeObservationRequest(
            parameters=[("daily", "temperature")],
            start_date=dt.datetime(2023, 7, 1, tzinfo=UTC),
            end_date=dt.datetime(2023, 7, 5, tzinfo=UTC),
        )
        .filter_by_station_id(LERWICK)
        .values.all()
        .df
    )
    assert not df.is_empty()
    # no (date, parameter) duplicates -> report types were collapsed
    assert df.select("date", "parameter").is_unique().all()
    maxes = df.filter(pl.col("parameter") == "temperature_air_max_2m")
    mins = df.filter(pl.col("parameter") == "temperature_air_min_2m")
    if not maxes.is_empty() and not mins.is_empty():
        joined = maxes.join(mins, on="date", suffix="_min")
        assert (joined["value"] >= joined["value_min"]).all()
