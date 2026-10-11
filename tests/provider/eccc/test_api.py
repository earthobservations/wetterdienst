# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for ECCC API."""

import datetime as dt
import json
from io import BytesIO
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from tests.conftest import skip_if_upstream_unavailable
from wetterdienst import Settings
from wetterdienst.provider.eccc.observation import EcccObservationRequest
from wetterdienst.provider.eccc.observation import api as eccc_api
from wetterdienst.util.network import File


@skip_if_upstream_unavailable()
@pytest.mark.remote
def test_eccc_api_stations(settings_convert_units_false: Settings) -> None:
    """Test fetching of ECCC stations."""
    request = EcccObservationRequest(
        parameters=[("daily", "data")],
        start="1990-01-01",
        end="1990-01-02",
        settings=settings_convert_units_false,
    ).filter_by_station_id(station_id=(14,))
    given_df = request.df
    expected_df = pl.DataFrame(
        [
            {
                "resolution": "daily",
                "dataset": "data",
                "station_id": "14",
                "start_timestamp": dt.datetime(1984, 1, 1, hour=8, tzinfo=ZoneInfo("UTC")),
                "end_timestamp": dt.datetime(1996, 11, 30, hour=8, tzinfo=ZoneInfo("UTC")),
                "latitude": 48.52,
                "longitude": -123.17,
                "elevation": 4.0,
                "name": "ACTIVE PASS",
                "region": "BC",
            },
        ],
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


@skip_if_upstream_unavailable()
@pytest.mark.remote
def test_eccc_api_values(settings_convert_units_false: Settings) -> None:
    """Test fetching of ECCC data."""
    request = EcccObservationRequest(
        parameters=[("daily", "data")],
        start="1979-11-02",
        end="1979-11-03",
        settings=settings_convert_units_false,
    ).filter_by_station_id(station_id=("2",))
    given_df = request.values.all().df
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "cooling_degree_day",
                "timestamp": dt.datetime(1979, 11, 2, 8, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 0.0,
                "quality": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "heating_degree_day",
                "timestamp": dt.datetime(1979, 11, 2, 8, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 11.7,
                "quality": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "precipitation_amount",
                "timestamp": dt.datetime(1979, 11, 2, 8, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 1.0,
                "quality": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "precipitation_amount_liquid",
                "timestamp": dt.datetime(1979, 11, 2, 8, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 1.0,
                "quality": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "snow_depth_new",
                "timestamp": dt.datetime(1979, 11, 2, 8, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 0.0,
                "quality": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "temperature_air_max_2m",
                "timestamp": dt.datetime(1979, 11, 2, 8, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 9.5,
                "quality": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "temperature_air_mean_2m",
                "timestamp": dt.datetime(1979, 11, 2, 8, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 6.3,
                "quality": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "temperature_air_min_2m",
                "timestamp": dt.datetime(1979, 11, 2, 8, 0, tzinfo=ZoneInfo(key="UTC")),
                "value": 3.0,
                "quality": None,
            },
        ],
        schema={
            "station_id": pl.Enum(["2"]),
            "resolution": pl.Enum(["daily"]),
            "dataset": pl.Enum(["data"]),
            "parameter": pl.Enum(
                [
                    "cooling_degree_day",
                    "heating_degree_day",
                    "precipitation_amount",
                    "precipitation_amount_liquid",
                    "snow_depth_new",
                    "temperature_air_max_2m",
                    "temperature_air_mean_2m",
                    "temperature_air_min_2m",
                ]
            ),
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        },
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


@skip_if_upstream_unavailable()
@pytest.mark.remote
def test_eccc_degree_days_are_degree_days_not_day_counts(settings_convert_units_false: Settings) -> None:
    """Test that ECCC heating degree days hold a degree day value rather than a count of days.

    ECCC publishes the degree day total for the single day the record covers, ``18 - mean``, and not
    the number of days on which heating was required. The two were conflated once, which is what
    ``count_days_heating_degree`` used to mean here.
    """
    request = EcccObservationRequest(
        parameters=[("daily", "data")],
        start="1979-11-02",
        end="1979-11-03",
        settings=settings_convert_units_false,
    ).filter_by_station_id(station_id=("2",))
    df = request.values.all().df
    values = dict(df.select("parameter", "value").iter_rows())
    assert values["heating_degree_day"] == pytest.approx(18 - values["temperature_air_mean_2m"])
    # a count of days would be a whole number, and could never exceed the single day requested
    assert values["heating_degree_day"] > 1


@skip_if_upstream_unavailable()
@pytest.mark.remote
def test_eccc_hourly_returns_data(settings_convert_units_false: Settings) -> None:
    """Test that the hourly resolution returns data.

    It declared a copy of the *daily* field list, none of which the hourly collection publishes, so
    every hourly request came back empty. Station 4055 also exercises the station listing: it sits
    past the first 500 rows the OGC endpoint returns by default.
    """
    request = EcccObservationRequest(
        parameters=[("hourly", "data")],
        start="1972-06-01",
        end="1972-06-30",
        settings=settings_convert_units_false,
    ).filter_by_station_id(station_id=("4055",))
    df = request.values.all().df
    assert not df.is_empty()
    values = dict(df.drop_nulls("value").select("parameter", "value").iter_rows())
    assert "temperature_air_2m" in values
    # June has 720 hours; a single unpaged request returns 500 features for the whole *year*, so
    # truncation shows up here as a couple of dozen timestamps rather than a few hundred
    assert df.get_column("timestamp").unique().len() > 500
    # kPa, not hPa -- an hPa reading would be around 988
    pressure = df.filter(pl.col("parameter") == "pressure_air_site").get_column("value").drop_nulls()
    assert 80 < pressure.max() < 110
    # published in tens of degrees; without the decode every bearing sits inside 0..36
    direction = df.filter(pl.col("parameter") == "wind_direction").get_column("value").drop_nulls()
    assert direction.max() > 36


@skip_if_upstream_unavailable()
@pytest.mark.remote
def test_eccc_monthly_returns_data(settings_convert_units_false: Settings) -> None:
    """Test that the monthly resolution returns data.

    It declared bulk-CSV column headers the OGC API never returns, and crashed on `LOCAL_DATE`,
    which is "2023-06" for this collection rather than a full timestamp.
    """
    request = EcccObservationRequest(
        parameters=[("monthly", "data")],
        start="2015-01-01",
        end="2016-12-31",
        settings=settings_convert_units_false,
    ).filter_by_station_id(station_id=("26",))
    df = request.values.all().df
    assert not df.is_empty()
    assert "temperature_air_mean_2m" in df.get_column("parameter").unique().to_list()
    # one row per month over the two years requested, so the year-month date parsed
    dates = df.get_column("timestamp").unique()
    assert dates.len() == 24


# Rows of Toronto Intl A (STN_ID 51459) as api.weather.gc.ca/collections/climate-hourly returns them: LOCAL_DATE is
# Local Standard Time ("Date/Time (LST)" in ECCC's bulk CSV), UTC_DATE is LOCAL_DATE plus the standard offset (5 h)
# all year, also while the civil clock is on daylight time.
_TORONTO_HOURLY_ROWS = [
    # an ordinary summer day, civil time is EDT (UTC-4)
    ("2025-07-01 09:00:00", "2025-07-01T14:00:00", 25.9),
    ("2025-07-01 10:00:00", "2025-07-01T15:00:00", 25.5),
    ("2025-07-01 11:00:00", "2025-07-01T16:00:00", 26.5),
    ("2025-07-01 12:00:00", "2025-07-01T17:00:00", 28.5),
    ("2025-07-01 13:00:00", "2025-07-01T18:00:00", 28.3),
    # the day the civil clock springs forward: 02:00 LST does not exist on it
    ("2025-03-09 00:00:00", "2025-03-09T05:00:00", -3.1),
    ("2025-03-09 01:00:00", "2025-03-09T06:00:00", -3.4),
    ("2025-03-09 02:00:00", "2025-03-09T07:00:00", -3.1),
    ("2025-03-09 03:00:00", "2025-03-09T08:00:00", -2.8),
    ("2025-03-09 04:00:00", "2025-03-09T09:00:00", -2.7),
    # the day the civil clock falls back: 01:00 civil time happens twice, LST 01:00 once
    ("2025-11-01 23:00:00", "2025-11-02T04:00:00", 3.2),
    ("2025-11-02 00:00:00", "2025-11-02T05:00:00", 3.5),
    ("2025-11-02 01:00:00", "2025-11-02T06:00:00", 1.1),
    ("2025-11-02 02:00:00", "2025-11-02T07:00:00", 1.0),
    ("2025-11-02 03:00:00", "2025-11-02T08:00:00", 1.1),
]
_TORONTO_STATION = {
    "STN_ID": 51459,
    "STATION_NAME": "TORONTO INTL A",
    "PROV_STATE_TERR_CODE": "ON",
    "LATITUDE": 434036000,
    "LONGITUDE": -793750000,
    "TIMEZONE": "EST",
    "ELEVATION": "173.40",
    "FIRST_DATE": "2013-06-11 09:00:00",
    "LAST_DATE": "2026-10-08 12:30:10",
}


def _serve_eccc(monkeypatch: pytest.MonkeyPatch, collection_properties: list[dict]) -> None:
    """Serve the station list and one collection's rows from the test instead of api.weather.gc.ca."""

    def _download(**kwargs: object) -> File:
        url = str(kwargs["url"])
        properties = [_TORONTO_STATION] if "climate-stations" in url else collection_properties
        content = json.dumps({"features": [{"type": "Feature", "properties": p} for p in properties]})
        return File(url=url, content=BytesIO(content.encode()), status=200)

    monkeypatch.setattr(eccc_api, "download_file", _download)


@pytest.mark.parametrize(
    ("start", "end", "expected"),
    [
        (
            dt.datetime(2025, 7, 1, 14, tzinfo=ZoneInfo("UTC")),
            dt.datetime(2025, 7, 1, 18, tzinfo=ZoneInfo("UTC")),
            [(14, 25.9), (15, 25.5), (16, 26.5), (17, 28.5), (18, 28.3)],
        ),
        (
            dt.datetime(2025, 3, 9, 5, tzinfo=ZoneInfo("UTC")),
            dt.datetime(2025, 3, 9, 9, tzinfo=ZoneInfo("UTC")),
            [(5, -3.1), (6, -3.4), (7, -3.1), (8, -2.8), (9, -2.7)],
        ),
        (
            dt.datetime(2025, 11, 2, 4, tzinfo=ZoneInfo("UTC")),
            dt.datetime(2025, 11, 2, 8, tzinfo=ZoneInfo("UTC")),
            [(4, 3.2), (5, 3.5), (6, 1.1), (7, 1.0), (8, 1.1)],
        ),
    ],
    ids=["summer", "spring-forward", "fall-back"],
)
def test_eccc_hourly_is_stamped_at_the_instant_of_utc_date(
    monkeypatch: pytest.MonkeyPatch,
    settings_convert_units_false: Settings,
    start: dt.datetime,
    end: dt.datetime,
    expected: list[tuple[int, float]],
) -> None:
    """Test that hourly values are stamped with the instant of the row's UTC_DATE, not LOCAL_DATE read as civil time.

    ECCC's hourly LOCAL_DATE is Local Standard Time, which does not follow daylight saving. Read as the
    station's civil time (EDT in July) every value came an hour early, the LST 02:00 of the spring day
    got no timestamp at all, and the UTC hour after the autumn change (06:00) was a hole (GH-2675).
    """
    rows = [
        {"LOCAL_DATE": local, "UTC_DATE": utc, "TEMP": value, "TEMP_FLAG": None}
        for local, utc, value in _TORONTO_HOURLY_ROWS
    ]
    _serve_eccc(monkeypatch, rows)
    request = EcccObservationRequest(
        parameters=[("hourly", "data", "temperature_air_2m")],
        start=start,
        end=end,
        settings=settings_convert_units_false,
    )
    df = request.filter_by_station_id("51459").values.all().df.sort("timestamp")
    day = start.replace(hour=0)
    assert df.select("timestamp", "value").rows() == [(day.replace(hour=hour), value) for hour, value in expected]
    # one value per instant, an hour apart: no hole and no repeat whatever the civil clock did
    assert df.get_column("timestamp").diff().drop_nulls().unique().to_list() == [dt.timedelta(hours=1)]


def test_eccc_daily_stays_at_local_civil_midnight(
    monkeypatch: pytest.MonkeyPatch, settings_convert_units_false: Settings
) -> None:
    """Test that daily values are still stamped at the station's civil midnight in UTC.

    The hourly stamps come from UTC_DATE (GH-2675); the daily collection shares the reader but its
    LOCAL_DATE is a calendar date, so it is localised as before: 05:00 UTC in winter, 04:00 in summer.
    """
    _serve_eccc(
        monkeypatch,
        [
            {"LOCAL_DATE": "2025-01-15 00:00:00", "MEAN_TEMPERATURE": -7.5, "MEAN_TEMPERATURE_FLAG": None},
            {"LOCAL_DATE": "2025-07-01 00:00:00", "MEAN_TEMPERATURE": 24.9, "MEAN_TEMPERATURE_FLAG": None},
        ],
    )
    request = EcccObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_2m")],
        start=dt.datetime(2025, 1, 1, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(2025, 12, 31, tzinfo=ZoneInfo("UTC")),
        settings=settings_convert_units_false,
    )
    df = request.filter_by_station_id("51459").values.all().df.sort("timestamp")
    assert df.select("timestamp", "value").rows() == [
        (dt.datetime(2025, 1, 15, 5, tzinfo=ZoneInfo("UTC")), -7.5),
        (dt.datetime(2025, 7, 1, 4, tzinfo=ZoneInfo("UTC")), 24.9),
    ]
