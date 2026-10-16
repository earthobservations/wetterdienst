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

from wetterdienst import Options
from wetterdienst.exceptions import NoInternetError, StationNotFoundError
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.provider.eccc.observation import EcccObservationRequest
from wetterdienst.provider.eccc.observation import api as eccc_api
from wetterdienst.util.network import File


@pytest.mark.remote
def test_eccc_api_stations(options_convert_units_false: Options) -> None:
    """Test fetching of ECCC stations."""
    request = EcccObservationRequest(
        parameters=[("daily", "data")],
        start="1990-01-01",
        end="1990-01-02",
        options=options_convert_units_false,
    ).filter_by_station_id(station_id=(14,))
    given_df = request.df
    expected_df = pl.DataFrame(
        [
            {
                "resolution": "daily",
                "dataset": "data",
                "station_id": "14",
                # the first daily row of the station, not its FIRST_DATE 1984-01-01 (GH-2747)
                "start_timestamp": dt.datetime(1984, 7, 1, tzinfo=ZoneInfo("UTC")),
                "end_timestamp": dt.datetime(1996, 11, 30, tzinfo=ZoneInfo("UTC")),
                # the geometry of the feature, 48 deg 52' N and 123 deg 17' W; LATITUDE and LONGITUDE (485200000,
                # -1231700000) packed degrees, minutes and seconds, which were read as degrees (GH-2942)
                "latitude": 48.86666666666667,
                "longitude": -123.28333333333333,
                "elevation": 4.0,
                "name": "ACTIVE PASS",
                "region": "BC",
            },
        ],
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_eccc_api_values(options_convert_units_false: Options) -> None:
    """Test fetching of ECCC data."""
    request = EcccObservationRequest(
        parameters=[("daily", "data")],
        start="1979-11-02",
        end="1979-11-02",
        options=options_convert_units_false,
    ).filter_by_station_id(station_id=("2",))
    given_df = request.values.all().df
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "cooling_degree_day",
                "timestamp": dt.datetime(1979, 11, 2, tzinfo=ZoneInfo(key="UTC")),
                "value": 0.0,
                "quality_flags": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "heating_degree_day",
                "timestamp": dt.datetime(1979, 11, 2, tzinfo=ZoneInfo(key="UTC")),
                "value": 11.7,
                "quality_flags": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "precipitation_amount",
                "timestamp": dt.datetime(1979, 11, 2, tzinfo=ZoneInfo(key="UTC")),
                "value": 1.0,
                "quality_flags": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "precipitation_amount_liquid",
                "timestamp": dt.datetime(1979, 11, 2, tzinfo=ZoneInfo(key="UTC")),
                "value": 1.0,
                "quality_flags": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "snow_depth_new",
                "timestamp": dt.datetime(1979, 11, 2, tzinfo=ZoneInfo(key="UTC")),
                "value": 0.0,
                "quality_flags": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "temperature_air_max_2m",
                "timestamp": dt.datetime(1979, 11, 2, tzinfo=ZoneInfo(key="UTC")),
                "value": 9.5,
                "quality_flags": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "temperature_air_mean_minmax_2m",
                "timestamp": dt.datetime(1979, 11, 2, tzinfo=ZoneInfo(key="UTC")),
                "value": 6.3,
                "quality_flags": None,
            },
            {
                "station_id": "2",
                "resolution": "daily",
                "dataset": "data",
                "parameter": "temperature_air_min_2m",
                "timestamp": dt.datetime(1979, 11, 2, tzinfo=ZoneInfo(key="UTC")),
                "value": 3.0,
                "quality_flags": None,
            },
        ],
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "timestamp": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality_flags": pl.String,
        },
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_eccc_degree_days_are_degree_days_not_day_counts(options_convert_units_false: Options) -> None:
    """Test that ECCC heating degree days hold a degree day value rather than a count of days.

    ECCC publishes the degree day total for the single day the record covers, ``18 - mean``, and not
    the number of days on which heating was required. The two were conflated once, which is what
    ``count_days_heating_degree`` used to mean here.
    """
    request = EcccObservationRequest(
        parameters=[("daily", "data")],
        start="1979-11-02",
        end="1979-11-03",
        options=options_convert_units_false,
    ).filter_by_station_id(station_id=("2",))
    df = request.values.all().df
    values = dict(df.select("parameter", "value").iter_rows())
    assert values["heating_degree_day"] == pytest.approx(18 - values["temperature_air_mean_minmax_2m"])
    # a count of days would be a whole number, and could never exceed the single day requested
    assert values["heating_degree_day"] > 1


@pytest.mark.remote
def test_eccc_hourly_returns_data(options_convert_units_false: Options) -> None:
    """Test that the hourly resolution returns data.

    It declared a copy of the *daily* field list, none of which the hourly collection publishes, so
    every hourly request came back empty. Station 4055 also exercises the station listing: it sits
    past the first 500 rows the OGC endpoint returns by default.
    """
    request = EcccObservationRequest(
        parameters=[("hourly", "data")],
        start="1972-06-01",
        end="1972-06-30",
        options=options_convert_units_false,
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
    direction = df.filter(pl.col("parameter") == "wind_direction_last_2min").get_column("value").drop_nulls()
    assert direction.max() > 36


@pytest.mark.remote
def test_eccc_monthly_returns_data(options_convert_units_false: Options) -> None:
    """Test that the monthly resolution returns data.

    It declared bulk-CSV column headers the OGC API never returns, and crashed on `LOCAL_DATE`,
    which is "2023-06" for this collection rather than a full timestamp.
    """
    request = EcccObservationRequest(
        parameters=[("monthly", "data")],
        start="2015-01-01",
        end="2016-12-31",
        options=options_convert_units_false,
    ).filter_by_station_id(station_id=("26",))
    df = request.values.all().df
    assert not df.is_empty()
    assert "temperature_air_mean_minmax_2m" in df.get_column("parameter").unique().to_list()
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
    # the first and last date of each collection, as the station list gives them (read 2026-10-13): the daily one starts
    # two days after the station, and the monthly ones are null for this station, which has monthly rows nonetheless
    "HLY_FIRST_DATE": "2013-06-11 09:00:00",
    "HLY_LAST_DATE": "2026-10-08 12:30:10",
    "DLY_FIRST_DATE": "2013-06-13 00:00:00",
    "DLY_LAST_DATE": "2026-10-08 00:00:00",
    "MLY_FIRST_DATE": None,
    "MLY_LAST_DATE": None,
}


def _as_instant(local_date: str) -> str:
    """Give a LOCAL_DATE of a monthly row ("2025-06") as the first instant of the month, as the API compares it."""
    return f"{local_date}-01 00:00:00" if len(local_date) == 7 else local_date


def _degrees(packed: int) -> float:
    """Give the decimal degrees of a position packed as degrees, minutes and seconds, ``485500000`` for 48 deg 55'."""
    magnitude = abs(packed)
    degrees, minutes, seconds = magnitude // 10**7, magnitude // 10**5 % 100, magnitude % 10**5 / 1000
    return (degrees + minutes / 60 + seconds / 3600) * (-1 if packed < 0 else 1)


def _serve_eccc(
    monkeypatch: pytest.MonkeyPatch,
    collection_properties: list[dict] | dict[str, list[dict]],
    station: dict | list[dict] | None = None,
) -> list[str]:
    """Serve the station list and the rows of the collections from the test instead of api.weather.gc.ca.

    The rows are those of every collection, or of each by its name (``climate-hourly``). They are cut the way the API
    cuts them: ``UTC_YEAR=`` keeps the rows of that year of UTC_DATE, ``datetime=a/b`` the rows whose LOCAL_DATE, which
    is Local Standard Time, lies in the window, and ``sortby=[-]FIELD&limit=n`` the first or last n rows. The station
    list is one station or several. Returns the URLs asked for.
    """
    urls: list[str] = []

    def _download(**kwargs: object) -> File:
        url = str(kwargs["url"])
        urls.append(url)
        query = dict(part.split("=", 1) for part in url.split("?", 1)[1].split("&"))
        properties = collection_properties
        if isinstance(properties, dict):
            properties = properties.get(url.split("/collections/")[1].split("/", maxsplit=1)[0], [])
        if "UTC_YEAR" in query:
            properties = [p for p in properties if p["UTC_DATE"].startswith(query["UTC_YEAR"])]
        if "datetime" in query:
            first, last = (value.replace("T", " ") for value in query["datetime"].split("/"))
            # a month is dated "2025-06", its first instant
            properties = [p for p in properties if first <= _as_instant(p["LOCAL_DATE"]) <= last]
        if "sortby" in query:
            # the first or last row by a date, as the API answers `limit=1&sortby=[-]FIELD`; a row without it comes last
            field_name = query["sortby"].lstrip("-")
            properties = sorted(
                (p for p in properties if p.get(field_name)),
                key=lambda p: p[field_name],
                reverse=query["sortby"].startswith("-"),
            )[: int(query["limit"])]
        if "climate-stations" in url:
            properties = station if isinstance(station, list) else [station or _TORONTO_STATION]
        # the geometry of a station feature is its position in decimal degrees, as the list gives it
        features = [
            {"type": "Feature", "properties": p}
            | (
                {"geometry": {"type": "Point", "coordinates": [_degrees(p["LONGITUDE"]), _degrees(p["LATITUDE"])]}}
                if "climate-stations" in url
                else {}
            )
            for p in properties
        ]
        content = json.dumps({"features": features})
        return File(url=url, content=BytesIO(content.encode()), status=200)

    monkeypatch.setattr(eccc_api, "download_file", _download)
    return urls


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
    options_convert_units_false: Options,
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
        options=options_convert_units_false,
    )
    df = request.filter_by_station_id("51459").values.all().df.sort("timestamp")
    day = start.replace(hour=0)
    assert df.select("timestamp", "value").rows() == [(day.replace(hour=hour), value) for hour, value in expected]
    # one value per instant, an hour apart: no hole and no repeat whatever the civil clock did
    assert df.get_column("timestamp").diff().drop_nulls().unique().to_list() == [dt.timedelta(hours=1)]


# Rows of Toronto Intl A (STN_ID 51459) as api.weather.gc.ca/collections/climate-daily returns them: LOCAL_DATE is the
# calendar date at 00:00:00, MEAN_TEMPERATURE the day's mean.
_TORONTO_DAILY_ROWS = [
    ("2025-01-15 00:00:00", -7.5),  # winter, civil time is EST (UTC-5)
    ("2025-03-09 00:00:00", 2.1),  # the day the civil clock springs forward
    ("2025-04-09 00:00:00", -0.3),  # summer time, EDT (UTC-4)
    ("2025-07-01 00:00:00", 24.9),
    ("2025-11-02 00:00:00", 4.6),  # the day the civil clock falls back
]


def _daily_rows() -> list[dict]:
    return [
        {"LOCAL_DATE": local, "MEAN_TEMPERATURE": value, "MEAN_TEMPERATURE_FLAG": None}
        for local, value in _TORONTO_DAILY_ROWS
    ]


@pytest.mark.parametrize(
    ("local", "expected"),
    _TORONTO_DAILY_ROWS,
    ids=["winter", "spring-forward", "summer-april", "summer-july", "fall-back"],
)
def test_eccc_daily_is_stamped_at_00_utc_of_its_date(
    monkeypatch: pytest.MonkeyPatch, options_convert_units_false: Options, local: str, expected: float
) -> None:
    """Test that a daily value is stamped at 00:00 UTC of the date, so a request for that one day returns it.

    LOCAL_DATE is a calendar date. It was read as the station's civil midnight (05:00 UTC in winter, 04:00 UTC in
    summer), and a request with start=end=day, bounded at 00:00 UTC, returned nothing for it (GH-2683).
    """
    _serve_eccc(monkeypatch, _daily_rows())
    day = local[:10]
    request = EcccObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_minmax_2m")],
        start=day,
        end=day,
        options=options_convert_units_false,
    )
    df = request.filter_by_station_id("51459").values.all().df
    midnight = dt.datetime.fromisoformat(day).replace(tzinfo=ZoneInfo("UTC"))
    assert df.select("timestamp", "value").rows() == [(midnight, expected)]


def test_eccc_daily_values_of_a_year_are_all_stamped_at_00_utc(
    monkeypatch: pytest.MonkeyPatch, options_convert_units_false: Options
) -> None:
    """Test that every daily value of a year is at 00:00 UTC, whichever side of a clock change it lies on."""
    _serve_eccc(monkeypatch, _daily_rows())
    request = EcccObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_minmax_2m")],
        start=dt.datetime(2025, 1, 1, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(2025, 12, 31, tzinfo=ZoneInfo("UTC")),
        options=options_convert_units_false,
    )
    df = request.filter_by_station_id("51459").values.all().df.sort("timestamp")
    assert df.get_column("timestamp").to_list() == [
        dt.datetime.fromisoformat(local).replace(tzinfo=ZoneInfo("UTC")) for local, _ in _TORONTO_DAILY_ROWS
    ]


@pytest.mark.parametrize("month", ["2025-01", "2025-06"], ids=["winter", "summer"])
def test_eccc_monthly_is_stamped_at_00_utc_of_the_first_of_the_month(
    monkeypatch: pytest.MonkeyPatch, options_convert_units_false: Options, month: str
) -> None:
    """Test that a month is stamped at 00:00 UTC of its first day, which a request for that day returns (GH-2683)."""
    _serve_eccc(
        monkeypatch,
        [
            {"LOCAL_DATE": "2025-01", "MEAN_TEMPERATURE": -5.4, "MEAN_TEMPERATURE_FLAG": None},
            {"LOCAL_DATE": "2025-06", "MEAN_TEMPERATURE": 20.9, "MEAN_TEMPERATURE_FLAG": None},
        ],
    )
    request = EcccObservationRequest(
        parameters=[("monthly", "data", "temperature_air_mean_minmax_2m")],
        start=f"{month}-01",
        end=f"{month}-01",
        options=options_convert_units_false,
    )
    df = request.filter_by_station_id("51459").values.all().df
    assert df.get_column("timestamp").to_list() == [
        dt.datetime.fromisoformat(f"{month}-01").replace(tzinfo=ZoneInfo("UTC"))
    ]


# The first and last day of TORONTO INTL A, given by the station list with a time of day, "2013-06-11 09:00:00" and
# "2026-10-08 12:30:10" in Local Standard Time (as FIRST_DATE and LAST_DATE are written; the dates of the daily
# collection in the list read are at 00:00), which the offset (EST, -5 h all year) would move to 14:00 UTC and 17:30 UTC
# of the same days, hours after the 00:00 UTC stamp of a daily or monthly value of that date.
_FIRST_AND_LAST_DAY_STATION = _TORONTO_STATION | {
    "DLY_FIRST_DATE": "2013-06-11 09:00:00",
    "DLY_LAST_DATE": "2026-10-08 12:30:10",
    "MLY_FIRST_DATE": "2013-06-11 09:00:00",
    "MLY_LAST_DATE": "2026-10-08 12:30:10",
}
_FIRST_AND_LAST_DAILY_ROWS = [
    {"LOCAL_DATE": "2013-06-11 00:00:00", "MEAN_TEMPERATURE": 17.2, "MEAN_TEMPERATURE_FLAG": None},
    {"LOCAL_DATE": "2013-06-12 00:00:00", "MEAN_TEMPERATURE": 18.0, "MEAN_TEMPERATURE_FLAG": None},
    {"LOCAL_DATE": "2026-10-07 00:00:00", "MEAN_TEMPERATURE": 11.4, "MEAN_TEMPERATURE_FLAG": None},
    {"LOCAL_DATE": "2026-10-08 00:00:00", "MEAN_TEMPERATURE": 12.1, "MEAN_TEMPERATURE_FLAG": None},
]
_FIRST_AND_LAST_MONTHLY_ROWS = [
    {"LOCAL_DATE": "2013-06", "MEAN_TEMPERATURE": 17.9, "MEAN_TEMPERATURE_FLAG": None},
    {"LOCAL_DATE": "2013-07", "MEAN_TEMPERATURE": 22.0, "MEAN_TEMPERATURE_FLAG": None},
    {"LOCAL_DATE": "2026-09", "MEAN_TEMPERATURE": 18.3, "MEAN_TEMPERATURE_FLAG": None},
    {"LOCAL_DATE": "2026-10", "MEAN_TEMPERATURE": 11.8, "MEAN_TEMPERATURE_FLAG": None},
]


@pytest.mark.parametrize(
    ("resolution", "rows", "day", "expected"),
    [
        ("daily", _FIRST_AND_LAST_DAILY_ROWS, "2013-06-11", 17.2),
        ("daily", _FIRST_AND_LAST_DAILY_ROWS, "2026-10-08", 12.1),
        ("monthly", _FIRST_AND_LAST_MONTHLY_ROWS, "2013-06-01", 17.9),
        ("monthly", _FIRST_AND_LAST_MONTHLY_ROWS, "2026-10-01", 11.8),
    ],
    ids=["daily-first-day", "daily-last-day", "monthly-first-month", "monthly-last-month"],
)
def test_eccc_request_for_the_first_or_last_day_of_a_station_is_not_skipped(
    monkeypatch: pytest.MonkeyPatch,
    options_convert_units_false: Options,
    resolution: str,
    rows: list[dict],
    day: str,
    expected: float,
) -> None:
    """Test that a request for the day or month a station starts or ends on returns its value (GH-2730).

    The station list gave FIRST_DATE as 09:00 on the first day, local time, which is hours after 00:00 UTC (the dates of
    the collections are cut to the day or month the same way). A request for that one day ends at 00:00 UTC, so the
    station read as starting after the window and was skipped, though it has a value stamped at 00:00 UTC of the day.
    The last-day cases were never skipped, as only the start is read; they pin that.
    """
    _serve_eccc(monkeypatch, rows, _FIRST_AND_LAST_DAY_STATION)
    request = EcccObservationRequest(
        parameters=[(resolution, "data", "temperature_air_mean_minmax_2m")],
        start=day,
        end=day,
        options=options_convert_units_false,
    )
    df = request.filter_by_station_id("51459").values.all().df
    assert df.select("timestamp", "value").rows() == [
        (dt.datetime.fromisoformat(day).replace(tzinfo=ZoneInfo("UTC")), expected)
    ]


@pytest.mark.parametrize(
    ("resolution", "start", "end"),
    [
        # a date or month is stamped at 00:00 UTC of it, as the values are, whatever the zone
        ("daily", dt.datetime(2013, 6, 11, tzinfo=ZoneInfo("UTC")), dt.datetime(2026, 10, 8, tzinfo=ZoneInfo("UTC"))),
        ("monthly", dt.datetime(2013, 6, 1, tzinfo=ZoneInfo("UTC")), dt.datetime(2026, 10, 1, tzinfo=ZoneInfo("UTC"))),
        # an hour is an instant, so the station's Local Standard Time applies: EST, -5 h, in June as well (GH-2693)
        (
            "hourly",
            dt.datetime(2013, 6, 11, 14, tzinfo=ZoneInfo("UTC")),
            dt.datetime(2026, 10, 8, 17, 30, 10, tzinfo=ZoneInfo("UTC")),
        ),
    ],
)
def test_eccc_station_list_dates_are_stamped_like_the_values(
    monkeypatch: pytest.MonkeyPatch,
    options_convert_units_false: Options,
    resolution: str,
    start: dt.datetime,
    end: dt.datetime,
) -> None:
    """Test that the first and last date of a station are the stamps of its first and last value (GH-2730)."""
    _serve_eccc(monkeypatch, [], _FIRST_AND_LAST_DAY_STATION)
    request = EcccObservationRequest(
        parameters=[(resolution, "data")],
        options=options_convert_units_false,
    ).filter_by_station_id("51459")
    assert request.df.select("start_timestamp", "end_timestamp").rows() == [(start, end)]


# STN_ID 14 as the station list gives it (read 2026-10-13): FIRST_DATE is the station's, the daily collection starts six
# months later, and there are no hourly dates at all. The first row of each collection read the same day: daily
# "1984-07-01 00:00:00", monthly "1984-07", hourly none.
_STATION_14 = {
    "STN_ID": 14,
    "STATION_NAME": "STUB 14",
    "PROV_STATE_TERR_CODE": "BC",
    "LATITUDE": 490105000,
    "LONGITUDE": -1224702000,
    "TIMEZONE": "PST",
    "ELEVATION": "13.00",
    "FIRST_DATE": "1984-01-01 00:00:00",
    "LAST_DATE": "1996-11-30 00:00:00",
    "HLY_FIRST_DATE": None,
    "HLY_LAST_DATE": None,
    "DLY_FIRST_DATE": "1984-07-01 00:00:00",
    "DLY_LAST_DATE": "1996-11-30 00:00:00",
    "MLY_FIRST_DATE": "1984-01-01 00:00:00",
    "MLY_LAST_DATE": "1996-11-01 00:00:00",
}


def test_eccc_each_resolution_of_a_station_has_the_dates_of_its_own_collection(
    monkeypatch: pytest.MonkeyPatch, options_convert_units_false: Options
) -> None:
    """Test that each resolution has the dates of its own collection, and a station is not listed where it has none.

    The overall FIRST_DATE 1984-01-01 stood for the daily start, six months before the first daily row (GH-2747), and a
    station without hourly dates was listed for hourly with null dates though it has no hourly row (GH-2867).
    """
    _serve_eccc(monkeypatch, [], _STATION_14)
    request = EcccObservationRequest(
        parameters=[("hourly", "data"), ("daily", "data"), ("monthly", "data")],
        options=options_convert_units_false,
    ).filter_by_station_id("14")
    utc = ZoneInfo("UTC")
    assert request.df.sort("resolution").select("resolution", "start_timestamp", "end_timestamp").rows() == [
        ("daily", dt.datetime(1984, 7, 1, tzinfo=utc), dt.datetime(1996, 11, 30, tzinfo=utc)),
        ("monthly", dt.datetime(1984, 1, 1, tzinfo=utc), dt.datetime(1996, 11, 1, tzinfo=utc)),
    ]


@pytest.mark.parametrize(
    ("timezone", "first", "expected"),
    [
        # the code names standard time: the date is on the LST clock whatever the season (GH-2693)
        ("EST", "2013-06-11 09:00:00", dt.datetime(2013, 6, 11, 14, tzinfo=ZoneInfo("UTC"))),
        ("CST", "2018-07-01 09:00:00", dt.datetime(2018, 7, 1, 15, tzinfo=ZoneInfo("UTC"))),  # Saskatchewan has no DST
        ("MST", "2017-07-01 09:00:00", dt.datetime(2017, 7, 1, 16, tzinfo=ZoneInfo("UTC"))),
        ("PST", "2023-04-24 10:00:00", dt.datetime(2023, 4, 24, 18, tzinfo=ZoneInfo("UTC"))),
        ("AST", "2017-10-29 13:00:00", dt.datetime(2017, 10, 29, 17, tzinfo=ZoneInfo("UTC"))),
        ("NST", "2020-07-01 09:00:00", dt.datetime(2020, 7, 1, 12, 30, tzinfo=ZoneInfo("UTC"))),
        # winter, and a date before standard time was kept, where the zone has a local mean time of its own
        # (America/Toronto: -5:17:32 until 1895)
        ("EST", "2013-01-11 09:00:00", dt.datetime(2013, 1, 11, 14, tzinfo=ZoneInfo("UTC"))),
        ("EST", "1840-03-01 09:00:00", dt.datetime(1840, 3, 1, 14, tzinfo=ZoneInfo("UTC"))),
        # a station without a timezone is read as UTC
        (None, "2013-06-11 09:00:00", dt.datetime(2013, 6, 11, 9, tzinfo=ZoneInfo("UTC"))),
    ],
)
def test_eccc_station_dates_are_local_standard_time_all_year(
    monkeypatch: pytest.MonkeyPatch,
    options_convert_units_false: Options,
    timezone: str | None,
    first: str,
    expected: dt.datetime,
) -> None:
    """Test that the first hourly date of a station is converted with the fixed offset of its standard time (GH-2693).

    ECCC writes the dates on the Local Standard Time clock of the hourly LOCAL_DATE: Toronto Intl A has
    '2013-06-11 09:00:00' for a first hourly report at UTC_DATE 14:00. The civil zone of the abbreviation
    would read it as EDT and give 13:00 UTC.
    """
    _serve_eccc(monkeypatch, [], _TORONTO_STATION | {"TIMEZONE": timezone, "HLY_FIRST_DATE": first})
    request = EcccObservationRequest(
        parameters=[("hourly", "data")],
        options=options_convert_units_false,
    ).filter_by_station_id("51459")
    assert request.df.get_column("start_timestamp").to_list() == [expected]


def test_eccc_unknown_timezone_code_is_an_error(
    monkeypatch: pytest.MonkeyPatch, options_convert_units_false: Options
) -> None:
    """Test that a TIMEZONE code the library has no offset for is not guessed at (GH-2693)."""
    _serve_eccc(monkeypatch, [], _TORONTO_STATION | {"TIMEZONE": "XYZ"})
    with pytest.raises(Exception, match="XYZ"):
        EcccObservationRequest(
            parameters=[("hourly", "data")],
            options=options_convert_units_false,
        ).filter_by_station_id("51459")


# WHITE ROCK CAMPBELL SCIENTIFIC (STN_ID 925) as the station list gives it (read 2026-10-13): dated from 1929, hourly
# reports from 1994-02-01. The first row of each collection read the same day: hourly UTC_DATE 1994-02-01T07:00:00,
# daily "1929-01-01 00:00:00", monthly "1929-01".
_WHITE_ROCK_STATION = {
    "STN_ID": 925,
    "STATION_NAME": "WHITE ROCK CAMPBELL SCIENTIFIC",
    "PROV_STATE_TERR_CODE": "BC",
    "LATITUDE": 490105000,
    "LONGITUDE": -1224702000,
    "TIMEZONE": "PST",
    "ELEVATION": "13.00",
    "FIRST_DATE": "1929-01-01 00:00:00",
    "LAST_DATE": "2026-10-11 12:30:11",
    "HLY_FIRST_DATE": "1994-02-01 00:00:00",
    "HLY_LAST_DATE": "2026-10-11 12:30:11",
    "DLY_FIRST_DATE": "1929-01-01 00:00:00",
    "DLY_LAST_DATE": "2026-10-11 00:00:00",
    "MLY_FIRST_DATE": "1929-01-01 00:00:00",
    "MLY_LAST_DATE": "2007-02-01 00:00:00",
}
# the first and last row of each collection of White Rock, as the API sorts them
_WHITE_ROCK_ROWS = {
    "climate-hourly": [
        {"LOCAL_DATE": "1994-01-31 23:00:00", "UTC_DATE": "1994-02-01T07:00:00"},
        {"LOCAL_DATE": "2026-10-13 14:00:00", "UTC_DATE": "2026-10-13T22:00:00"},
    ],
    "climate-daily": [{"LOCAL_DATE": "1929-01-01 00:00:00"}, {"LOCAL_DATE": "2026-10-11 00:00:00"}],
    "climate-monthly": [{"LOCAL_DATE": "1929-01"}, {"LOCAL_DATE": "2026-09"}],
}
_ALL_RESOLUTIONS = [
    ("hourly", "data", "temperature_air_2m"),
    ("daily", "data", "temperature_air_mean_minmax_2m"),
    ("monthly", "data", "temperature_air_mean_minmax_2m"),
]


def _stations_of(
    monkeypatch: pytest.MonkeyPatch,
    options: Options,
    stations: list[dict],
    parameters: list[tuple[str, ...]] | None = None,
) -> EcccObservationRequest:
    """Serve a station list and give the request for the parameters, all three resolutions by default."""
    _serve_eccc(monkeypatch, [], stations)
    return EcccObservationRequest(parameters=parameters or _ALL_RESOLUTIONS, options=options)


def _years_requested(
    monkeypatch: pytest.MonkeyPatch,
    options: Options,
    station: dict,
    rows: dict[str, list[dict]] | None = None,
    **dates: str,
) -> tuple[dict[str, list[int]], list[str]]:
    """Request the station's values and return the years asked for per collection, and the rows asked for.

    The rows of a year are cut from those served, which hold no value: the requests are what is looked at. The rows
    asked for are given as ``collection:[-]FIELD``.
    """
    urls = _serve_eccc(monkeypatch, _WHITE_ROCK_ROWS if rows is None else rows, station)
    request = EcccObservationRequest(parameters=_ALL_RESOLUTIONS, options=options, **dates)
    request.filter_by_station_id(str(station["STN_ID"])).values.all()
    years: dict[str, list[int]] = {}
    edges: list[str] = []
    for url in urls:
        if "climate-stations" in url:
            continue
        collection = url.split("/collections/")[1].split("/")[0]
        if "sortby=" in url:
            edges.append(f"{collection}:{url.split('sortby=')[1].split('&')[0]}")
            continue
        window = url.split("UTC_YEAR=")[1] if "UTC_YEAR=" in url else url.split("datetime=")[1]
        years.setdefault(collection, []).append(int(window[:4]))
    return years, edges


def test_eccc_years_of_a_request_without_dates_are_those_of_the_rows_of_each_collection(
    monkeypatch: pytest.MonkeyPatch, options_convert_units_false: Options
) -> None:
    """Test that a request without dates asks for the years from the first row of a collection on (GH-2820).

    White Rock has FIRST_DATE 1929, as its daily and monthly rows, and its first hourly row in 1994: a request asked
    for 65 hourly years in which the station has no row. The hourly and monthly years end with the last row of the
    collection, the daily ones with the station's LAST_DATE: the monthly dates of the list (MLY_LAST_DATE 2007-02) say
    nothing about the rows, the last of which is 2026-09.
    """
    years, edges = _years_requested(monkeypatch, options_convert_units_false, _WHITE_ROCK_STATION)
    assert years == {
        "climate-hourly": list(range(1994, 2027)),
        "climate-daily": list(range(1929, 2027)),
        "climate-monthly": list(range(1929, 2027)),
    }
    assert sorted(edges) == [
        "climate-daily:LOCAL_DATE",
        "climate-hourly:-UTC_DATE",
        "climate-hourly:UTC_DATE",
        "climate-monthly:-LOCAL_DATE",
        "climate-monthly:LOCAL_DATE",
    ]


def test_eccc_years_of_a_request_without_dates_reach_the_rows_before_the_first_date_of_the_station(
    monkeypatch: pytest.MonkeyPatch, options_convert_units_false: Options
) -> None:
    """Test that the years begin where the rows do, though that is before the station's first date (GH-2864).

    Station 1765 (read 2026-10-13) has FIRST_DATE and HLY_FIRST_DATE 1956-01-06 15:00 and 1321 hourly values in 1955,
    from 1955-10-01; the first daily row is of 1957-11-01.
    """
    station = _TORONTO_STATION | {
        "STN_ID": 1765,
        "FIRST_DATE": "1956-01-06 15:00:00",
        "LAST_DATE": "1992-12-01 00:00:00",
        "HLY_FIRST_DATE": "1956-01-06 15:00:00",
        "HLY_LAST_DATE": "1992-05-31 19:00:00",
        "DLY_FIRST_DATE": "1957-11-01 00:00:00",
        "DLY_LAST_DATE": "1992-05-31 00:00:00",
    }
    rows = {
        "climate-hourly": [
            {"LOCAL_DATE": "1955-10-01 01:00:00", "UTC_DATE": "1955-10-01T06:00:00"},
            {"LOCAL_DATE": "1992-05-31 19:00:00", "UTC_DATE": "1992-06-01T00:00:00"},
        ],
        "climate-daily": [{"LOCAL_DATE": "1957-11-01 00:00:00"}, {"LOCAL_DATE": "1992-05-31 00:00:00"}],
        "climate-monthly": [{"LOCAL_DATE": "1957-01"}],
    }
    years, _ = _years_requested(monkeypatch, options_convert_units_false, station, rows)
    assert years["climate-hourly"] == list(range(1955, 1993))
    assert years["climate-daily"] == list(range(1957, 1993))


def test_eccc_hourly_and_monthly_years_end_with_the_last_row_not_with_the_last_date_of_the_station(
    monkeypatch: pytest.MonkeyPatch, options_convert_units_false: Options
) -> None:
    """Test that the hourly and the monthly years stop where the rows do (GH-2820).

    Station 1679 (read 2026-10-13) has LAST_DATE 2010-07-12 and HLY_LAST_DATE 1993-06-30 12:00: the 17 years between had
    a request each; 390 has LAST_DATE 1994-04-06 and its last monthly row is 1991-05. The daily rows are asked for to
    the LAST_DATE, as a descending sort of that collection answers with the rows without a value that it carries to the
    day of the request for many closed stations (390, 962, 2898).
    """
    station = _WHITE_ROCK_STATION | {
        "LAST_DATE": "2010-07-12 12:00:00",
        "HLY_FIRST_DATE": "1973-08-09 18:00:00",
        "HLY_LAST_DATE": "1993-06-30 12:00:00",
        "DLY_LAST_DATE": "2010-07-12 00:00:00",
    }
    rows = _WHITE_ROCK_ROWS | {
        "climate-hourly": [
            {"LOCAL_DATE": "1973-08-09 04:00:00", "UTC_DATE": "1973-08-09T12:00:00"},
            {"LOCAL_DATE": "1993-06-30 10:00:00", "UTC_DATE": "1993-06-30T18:00:00"},
        ],
        "climate-monthly": [{"LOCAL_DATE": "1929-01"}, {"LOCAL_DATE": "1991-05"}],
    }
    years, _ = _years_requested(monkeypatch, options_convert_units_false, station, rows)
    assert years["climate-hourly"] == list(range(1973, 1994))
    assert years["climate-daily"] == list(range(1929, 2011))
    assert years["climate-monthly"] == list(range(1929, 1992))


def test_eccc_a_collection_without_dates_is_not_listed_and_not_asked_for_anything(
    monkeypatch: pytest.MonkeyPatch, options_convert_units_false: Options
) -> None:
    """Test that a station without a hourly or daily first date is listed for neither, and asked for nothing (GH-2867).

    In the live list the first date is null for a station that has no value in either collection (read 2026-10-15; the
    numbers are in ``_LISTED_BY_FIRST_DATE``), where it was listed with null dates (GH-2747) and a dated request
    asked for its years. The monthly dates are null for 763 stations that have monthly values (36 of 40 drawn
    did), so monthly is always listed and asked for.
    """
    station = _WHITE_ROCK_STATION | dict.fromkeys(
        ("HLY_FIRST_DATE", "HLY_LAST_DATE", "DLY_FIRST_DATE", "DLY_LAST_DATE", "MLY_FIRST_DATE", "MLY_LAST_DATE")
    )
    urls = _serve_eccc(monkeypatch, _WHITE_ROCK_ROWS, station)
    request = EcccObservationRequest(parameters=_ALL_RESOLUTIONS, options=options_convert_units_false)
    stations = request.filter_by_station_id("925")
    assert stations.df.get_column("resolution").to_list() == ["monthly"]
    stations.values.all()
    collections = {url.split("/collections/")[1].split("/")[0] for url in urls}
    assert collections == {"climate-stations", "climate-monthly"}
    years, edges = _years_requested(monkeypatch, options_convert_units_false, station)
    assert years == {"climate-monthly": list(range(1929, 2027))}
    assert sorted(edges) == ["climate-monthly:-LOCAL_DATE", "climate-monthly:LOCAL_DATE"]


@pytest.mark.parametrize(
    ("null_columns", "unlisted", "listed", "skipped", "asked"),
    [
        (("HLY_FIRST_DATE", "HLY_LAST_DATE"), "hourly", "daily", "climate-hourly", "climate-daily"),
        (("DLY_FIRST_DATE", "DLY_LAST_DATE"), "daily", "hourly", "climate-daily", "climate-hourly"),
    ],
)
def test_eccc_only_the_collection_without_a_first_date_is_not_listed(
    monkeypatch: pytest.MonkeyPatch,
    options_convert_units_false: Options,
    null_columns: tuple[str, str],
    unlisted: str,
    listed: str,
    skipped: str,
    asked: str,
) -> None:
    """Test that the hourly and the daily collection each follow their own first date (GH-2820, GH-2867)."""
    station = _WHITE_ROCK_STATION | dict.fromkeys(null_columns)
    stations = _stations_of(monkeypatch, options_convert_units_false, [station]).all()
    assert sorted(stations.df.get_column("resolution").to_list()) == sorted([listed, "monthly"])
    assert unlisted not in stations.df.get_column("resolution").to_list()
    years, edges = _years_requested(monkeypatch, options_convert_units_false, station)
    assert skipped not in years
    assert not [edge for edge in edges if edge.startswith(skipped)]
    assert years[asked]
    assert years["climate-monthly"] == list(range(1929, 2027))


def _three_stations(null_columns: tuple[str, str]) -> list[dict]:
    """Three stations on a line of latitude, the nearest to Toronto without the dates of the collection in the list.

    The overall FIRST_DATE and LAST_DATE are the same for all three, so a start taken from them would show.
    """
    base = _TORONTO_STATION | {"FIRST_DATE": "1980-01-01 00:00:00", "LAST_DATE": "2026-10-08 00:00:00"}
    return [
        base | {"STN_ID": 1, "STATION_NAME": "NEAREST", "LATITUDE": 434036000} | dict.fromkeys(null_columns),
        base
        | {"STN_ID": 2, "STATION_NAME": "NEXT", "LATITUDE": 440036000}
        | {"HLY_FIRST_DATE": "1990-01-01 00:00:00", "DLY_FIRST_DATE": "1991-01-01 00:00:00"},
        base | {"STN_ID": 3, "STATION_NAME": "FAR", "LATITUDE": 450036000},
    ]


@pytest.mark.parametrize(
    ("resolution", "null_columns", "first"),
    [
        ("hourly", ("HLY_FIRST_DATE", "HLY_LAST_DATE"), dt.datetime(1990, 1, 1, 5, tzinfo=ZoneInfo("UTC"))),
        ("daily", ("DLY_FIRST_DATE", "DLY_LAST_DATE"), dt.datetime(1991, 1, 1, tzinfo=ZoneInfo("UTC"))),
    ],
)
def test_eccc_a_station_without_the_dates_of_a_collection_is_not_a_station_of_it(
    monkeypatch: pytest.MonkeyPatch,
    options_convert_units_false: Options,
    resolution: str,
    null_columns: tuple[str, str],
    first: dt.datetime,
) -> None:
    """Test that the listing, the ranking and the distance filter leave out a station that has no such collection.

    The nearest station of the list has no hourly (daily) dates and no row in that collection (GH-2867). It was listed
    with null dates, was the nearest station of a ranking and the only one inside a distance. Its dates in the other
    collections are unchanged, and a station that is not listed for the resolution cannot be named as the point of an
    interpolation by its id.
    """
    request = _stations_of(
        monkeypatch, options_convert_units_false, _three_stations(null_columns), [(resolution, "data")]
    )
    toronto = (_degrees(434036000), _degrees(-793750000))
    listed = request.all().df
    assert listed.get_column("station_id").to_list() == ["2", "3"]
    # the dates of the collection, not those of the station as a whole
    assert listed.get_column("start_timestamp").to_list()[0] == first
    assert request.filter_by_rank(toronto, rank=1).df.get_column("station_id").to_list() == ["2", "3"]
    assert request.filter_by_distance(toronto, distance=1).df.is_empty()
    assert request.filter_by_distance(toronto, distance=100).df.get_column("station_id").to_list() == ["2"]
    assert request.filter_by_station_id("1").df.is_empty()
    with pytest.raises(StationNotFoundError):
        request.interpolate_by_station_id("1")
    # the other resolutions are unchanged
    monthly = _stations_of(
        monkeypatch, options_convert_units_false, _three_stations(null_columns), [("monthly", "data")]
    )
    assert monthly.all().df.get_column("station_id").to_list() == ["1", "2", "3"]


def test_eccc_a_collection_without_a_row_is_asked_for_no_years(
    monkeypatch: pytest.MonkeyPatch, options_convert_units_false: Options
) -> None:
    """Test that a collection which answers the first row with none is asked for no year (GH-2820).

    Station 10832 (read 2026-10-14) has HLY_FIRST_DATE 1992-12-31 17:00 and no hourly row at all.
    """
    rows = _WHITE_ROCK_ROWS | {"climate-hourly": []}
    years, edges = _years_requested(monkeypatch, options_convert_units_false, _WHITE_ROCK_STATION, rows)
    assert "climate-hourly" not in years
    assert edges.count("climate-hourly:UTC_DATE") == 1
    assert "climate-hourly:-UTC_DATE" not in edges
    assert years["climate-daily"]


def test_eccc_a_request_with_dates_asks_for_the_years_of_the_collections_the_station_is_listed_for(
    monkeypatch: pytest.MonkeyPatch, options_convert_units_false: Options
) -> None:
    """Test that a request that names both dates asks for those years in the listed collections, and no first row.

    A station without a hourly or daily first date is not listed for it (GH-2867), so a dated request is not asked for
    those either: 27490 (read 2026-10-15) has 7035 hourly rows, all of 2008, after its LAST_DATE 2007-11-30 and with
    no HLY_ dates, which a request with dates reached before and no longer does.
    """
    station = _WHITE_ROCK_STATION | {"HLY_FIRST_DATE": None, "DLY_FIRST_DATE": None}
    years, edges = _years_requested(
        monkeypatch, options_convert_units_false, station, start="2000-01-01", end="2001-12-31"
    )
    assert years == {"climate-monthly": [2000, 2001]}
    assert edges == []


def test_eccc_a_request_with_dates_reaches_the_rows_before_the_first_date_of_the_collection(
    monkeypatch: pytest.MonkeyPatch, options_convert_units_false: Options
) -> None:
    """Test that a window before HLY_FIRST_DATE is not skipped for it, the rows before it being there (GH-2864).

    27174 (read 2026-10-13) has HLY_FIRST_DATE 2013-12-10 09:00 and FIRST_DATE 1996-10-01, and 8232 hourly rows of 2010
    with values of PRECIP_AMOUNT. The station's start in the list is that of the collection (GH-2747), which a window
    that ends before it must not take for the first row: the walk skips a station by its FIRST_DATE.
    """
    station = _TORONTO_STATION | {
        "STN_ID": 27174,
        "FIRST_DATE": "1996-10-01 00:00:00",
        "HLY_FIRST_DATE": "2013-12-10 09:00:00",
    }
    rows = [{"LOCAL_DATE": "2010-06-01 00:00:00", "UTC_DATE": "2010-06-01T06:00:00", "PRECIP_AMOUNT": 0.4}]
    _serve_eccc(monkeypatch, rows, station)
    request = EcccObservationRequest(
        parameters=[("hourly", "data", "precipitation_amount")],
        start="2010-01-01",
        end="2010-12-31",
        options=options_convert_units_false,
    )
    stations = request.filter_by_station_id("27174")
    assert stations.df.get_column("start_timestamp").to_list() == [
        dt.datetime(2013, 12, 10, 14, tzinfo=ZoneInfo("UTC"))
    ]
    assert stations.values.all().df.get_column("value").to_list() == [0.4]


def test_eccc_a_window_that_ends_before_the_first_date_of_the_station_skips_it(
    monkeypatch: pytest.MonkeyPatch, options_convert_units_false: Options
) -> None:
    """Test that a window that ends before FIRST_DATE of the station still makes no request for it."""
    urls = _serve_eccc(monkeypatch, {"climate-hourly": []}, _WHITE_ROCK_STATION)
    request = EcccObservationRequest(
        parameters=[("hourly", "data", "temperature_air_2m")],
        start="1900-01-01",
        end="1900-12-31",
        options=options_convert_units_false,
    )
    assert request.filter_by_station_id("925").values.all().df.is_empty()
    assert not [url for url in urls if "climate-hourly" in url]


def test_eccc_a_request_without_dates_for_a_hand_built_result_asks_for_the_years_of_the_rows(
    monkeypatch: pytest.MonkeyPatch, options_convert_units_false: Options
) -> None:
    """Test that a result of stations built without the station list has its first row asked for, and no gate (GH-2820).

    There is no list to read a first date from, so the hourly years run from the first to the last row and the daily
    ones to the end stamped on the station's row.
    """
    urls = _serve_eccc(monkeypatch, _WHITE_ROCK_ROWS)
    request = EcccObservationRequest(
        parameters=[("hourly", "data", "temperature_air_2m"), ("daily", "data", "temperature_air_mean_minmax_2m")],
        options=options_convert_units_false,
    )
    end = dt.datetime(2000, 12, 31, tzinfo=ZoneInfo("UTC"))
    frame = pl.DataFrame(
        {
            "resolution": ["hourly", "daily"],
            "dataset": ["data", "data"],
            "station_id": ["925", "925"],
            "start_timestamp": [None, None],
            "end_timestamp": [end, end],
            "latitude": [49.0, 49.0],
            "longitude": [-122.0, -122.0],
            "elevation": [13.0, 13.0],
            "name": ["WHITE ROCK", "WHITE ROCK"],
            "region": ["BC", "BC"],
        },
        schema_overrides={
            "start_timestamp": pl.Datetime(time_zone="UTC"),
            "end_timestamp": pl.Datetime(time_zone="UTC"),
        },
    )
    stations = StationsResult(stations=request, df=frame, df_all=frame, stations_filter=StationsFilter.BY_STATION_ID)
    stations.values.all()
    hourly = [int(url.split("UTC_YEAR=")[1][:4]) for url in urls if "UTC_YEAR=" in url]
    daily = [int(url.split("datetime=")[1][:4]) for url in urls if "datetime=" in url]
    assert hourly == list(range(1994, 2027))
    assert daily == list(range(1929, 2001))


def test_eccc_a_request_without_dates_offline_raises(
    monkeypatch: pytest.MonkeyPatch, options_convert_units_false: Options
) -> None:
    """Test that a first-row request that gets no connection raises `NoInternetError`, as a year does (GH-2640)."""

    def _download(**kwargs: object) -> File:
        url = str(kwargs["url"])
        if "climate-stations" in url:
            content = json.dumps({"features": [{"type": "Feature", "properties": _WHITE_ROCK_STATION}]})
            return File(url=url, content=BytesIO(content.encode()), status=200)
        return File(url=url, content=NoInternetError("no connection"), status=0)

    monkeypatch.setattr(eccc_api, "download_file", _download)
    request = EcccObservationRequest(
        parameters=[("hourly", "data", "temperature_air_2m")], options=options_convert_units_false
    )
    with pytest.raises(NoInternetError):
        request.filter_by_station_id("925").values.all()


def test_eccc_the_years_of_the_last_hours_of_the_utc_year_follow_the_last_hourly_row(
    monkeypatch: pytest.MonkeyPatch, options_convert_units_false: Options
) -> None:
    """Test that the hourly rows stamped into the next UTC year are asked for, those of 22:00 on 31 December in EST.

    The station ends at 22:00 on 31 December 2014 in EST, which is 2015-01-01 03:00 UTC: the hourly rows, stamped from
    UTC_DATE, reach into 2015 while the daily ones end in 2014 (GH-2730).
    """
    station = _TORONTO_STATION | {
        "FIRST_DATE": "2013-12-31 21:00:00",
        "LAST_DATE": "2014-12-31 22:00:00",
        "HLY_FIRST_DATE": "2013-12-31 21:00:00",
        "HLY_LAST_DATE": "2014-12-31 22:00:00",
        "DLY_FIRST_DATE": "2013-12-31 00:00:00",
        "DLY_LAST_DATE": "2014-12-31 00:00:00",
    }
    rows = {
        "climate-hourly": [
            {"LOCAL_DATE": "2013-12-31 21:00:00", "UTC_DATE": "2014-01-01T02:00:00"},
            {"LOCAL_DATE": "2014-12-31 22:00:00", "UTC_DATE": "2015-01-01T03:00:00"},
        ],
        "climate-daily": [{"LOCAL_DATE": "2013-12-31 00:00:00"}, {"LOCAL_DATE": "2014-12-31 00:00:00"}],
    }
    urls = _serve_eccc(monkeypatch, rows, station)
    EcccObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_minmax_2m"), ("hourly", "data", "temperature_air_2m")],
        options=options_convert_units_false,
    ).filter_by_station_id("51459").values.all()
    assert [url.split("UTC_YEAR=")[1].split("&")[0] for url in urls if "UTC_YEAR=" in url] == ["2014", "2015"]
    assert [url.split("datetime=")[1][:4] for url in urls if "datetime=" in url] == ["2013", "2014"]


def test_eccc_daily_year_window_is_the_calendar_year_of_local_date(
    monkeypatch: pytest.MonkeyPatch, options_convert_units_false: Options
) -> None:
    """Test that the rows of a year are asked for as the calendar year of LOCAL_DATE, not a window moved by the zone."""
    urls = _serve_eccc(monkeypatch, _daily_rows())
    EcccObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_minmax_2m")],
        start="2025-01-15",
        end="2025-01-15",
        options=options_convert_units_false,
    ).filter_by_station_id("51459").values.all()
    windows = [url.split("datetime=")[1].split("&")[0] for url in urls if "climate-daily" in url]
    assert windows == ["2025-01-01T00:00:00/2025-12-31T23:59:59"]


def test_eccc_hourly_year_window_follows_utc_date_not_the_civil_zone(
    monkeypatch: pytest.MonkeyPatch, options_convert_units_false: Options
) -> None:
    """Test that the first hour of a UTC year is fetched where ECCC's zone is not the civil one of the position.

    FORT ST. JOHN A (50837) is stated as PST (UTC-8) while the time zone of its position, which the library
    uses for a window of LOCAL_DATE, is Dawson Creek's UTC-7 all year. The first hour of 2025 UTC is
    LOCAL_DATE 2024-12-31 16:00, which a window starting at 17:00 local does not reach. The request is
    cut by UTC_YEAR instead, the year of the stamps (GH-2675).
    """
    station = {
        "STN_ID": 50837,
        "STATION_NAME": "FORT ST. JOHN A",
        "PROV_STATE_TERR_CODE": "BC",
        "LATITUDE": 561418000,
        "LONGITUDE": -1204425000,
        "TIMEZONE": "PST",
        "ELEVATION": "694.90",
        "FIRST_DATE": "2012-12-03 23:00:00",
        "LAST_DATE": "2026-10-08 12:30:10",
        # a station is listed for hourly values by its hourly first date (GH-2867)
        "HLY_FIRST_DATE": "2012-12-03 23:00:00",
        "HLY_LAST_DATE": "2026-10-08 12:30:10",
    }
    rows = [
        {"LOCAL_DATE": local, "UTC_DATE": utc, "TEMP": value, "TEMP_FLAG": None}
        for local, utc, value in [
            ("2024-12-31 15:00:00", "2024-12-31T23:00:00", -14.6),
            ("2024-12-31 16:00:00", "2025-01-01T00:00:00", -14.9),
            ("2024-12-31 17:00:00", "2025-01-01T01:00:00", -15.0),
        ]
    ]
    _serve_eccc(monkeypatch, rows, station)
    request = EcccObservationRequest(
        parameters=[("hourly", "data", "temperature_air_2m")],
        start=dt.datetime(2025, 1, 1, 0, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(2025, 1, 1, 1, tzinfo=ZoneInfo("UTC")),
        options=options_convert_units_false,
    )
    df = request.filter_by_station_id("50837").values.all().df.sort("timestamp")
    assert df.select("timestamp", "value").rows() == [
        (dt.datetime(2025, 1, 1, 0, tzinfo=ZoneInfo("UTC")), -14.9),
        (dt.datetime(2025, 1, 1, 1, tzinfo=ZoneInfo("UTC")), -15.0),
    ]


def test_eccc_daily_carries_the_flag_of_each_value_in_quality_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a value's `*_FLAG` letter is kept verbatim in `quality_flags` (GH-2018, GH-2758).

    The flags were fetched, joined on as `quality` and then replaced by a null Float64, so a missing (`M`),
    estimated (`E`) or trace (`T`) day looked like any other. Rows as api.weather.gc.ca/collections/climate-daily
    returns them for 50430 in 2023 (checked 2026-10-11): an unflagged value has a null flag, and a flag can sit on
    a null value (`M`) or on a value (`T` on a precipitation of 0.0).

    ECCC's Technical Documentation (climate.weather.gc.ca/doc/Technical_Documentation.pdf, "Table of flags"):
    "M  Missing", "E  Estimated", "T  Trace; value is zero", blank "Valid data".
    """
    rows = [
        {
            "LOCAL_DATE": "2023-01-01 00:00:00",
            "MEAN_TEMPERATURE": -5.0,
            "MEAN_TEMPERATURE_FLAG": None,
            "TOTAL_PRECIPITATION": 0.0,
            "TOTAL_PRECIPITATION_FLAG": "T",
        },
        {
            "LOCAL_DATE": "2023-01-02 00:00:00",
            "MEAN_TEMPERATURE": None,
            "MEAN_TEMPERATURE_FLAG": "M",
            "TOTAL_PRECIPITATION": 1.2,
            "TOTAL_PRECIPITATION_FLAG": "E",
        },
    ]
    _serve_eccc(monkeypatch, rows)
    request = EcccObservationRequest(
        parameters=[
            ("daily", "data", "temperature_air_mean_minmax_2m"),
            ("daily", "data", "precipitation_amount"),
        ],
        start="2023-01-01",
        end="2023-01-02",
        # nulls kept, or the missing day's row, which holds only its `M`, would be dropped
        options=Options(convert_units=False, drop_nulls=False),
    )
    df = request.filter_by_station_id("51459").values.all().df
    assert df.schema["quality_flags"] == pl.String
    assert "quality" not in df.columns
    assert "quality_flag" not in df.columns
    assert df.sort("parameter", "timestamp").select("parameter", "value", "quality_flags").rows() == [
        ("precipitation_amount", 0.0, "T"),
        ("precipitation_amount", 1.2, "E"),
        ("temperature_air_mean_minmax_2m", -5.0, None),
        ("temperature_air_mean_minmax_2m", None, "M"),
    ]


def test_eccc_daily_gust_of_0_is_not_a_gust_and_a_direction_of_0_is_no_bearing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the 0 of a gust ECCC does not report, and the direction 0 beside a reported speed, are null (GH-2615).

    Rows taken from api.weather.gc.ca/collections/climate-daily (checked 2026-10-12): ALERT 1975-07-01 is below
    the 31 km/h the stations report from and has 0 and 0, no flag, where the bulk CSV writes "<31"; 1975-07-06 is a gust
    of 60 km/h from 200 degrees (20 tens of degrees); ST CATHARINES A 1974-11-26 has 42 km/h and a direction of 0. The
    glossary: "The stations do not report if less than 31 km/h" and "36 means 360 degrees true", so north is not 0.
    """
    rows = [
        {"LOCAL_DATE": "1975-07-01 00:00:00", "SPEED_MAX_GUST": 0, "DIRECTION_MAX_GUST": 0},
        {"LOCAL_DATE": "1975-07-06 00:00:00", "SPEED_MAX_GUST": 60, "DIRECTION_MAX_GUST": 20},
        {"LOCAL_DATE": "1975-07-09 00:00:00", "SPEED_MAX_GUST": 42, "DIRECTION_MAX_GUST": 0},
    ]
    _serve_eccc(
        monkeypatch,
        rows,
        station={**_TORONTO_STATION, "FIRST_DATE": "1950-01-01 00:00:00", "DLY_FIRST_DATE": "1950-01-01 00:00:00"},
    )
    request = EcccObservationRequest(
        parameters=[("daily", "data", "wind_gust_max"), ("daily", "data", "wind_direction_gust_max")],
        start="1975-07-01",
        end="1975-07-09",
        options=Options(convert_units=False, drop_nulls=False),
    )
    df = request.filter_by_station_id("51459").values.all().df
    assert df.sort("parameter", "timestamp").select("parameter", "value", "quality_flags").rows() == [
        ("wind_direction_gust_max", None, "raw:0"),
        ("wind_direction_gust_max", 200.0, None),
        ("wind_direction_gust_max", None, "raw:0"),
        ("wind_gust_max", None, "raw:0"),
        ("wind_gust_max", 60.0, None),
        ("wind_gust_max", 42.0, None),
    ]


def test_eccc_hourly_wind_direction_of_0_is_a_calm_and_null_and_36_is_north(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the hourly direction 0 is null with `raw:0`, and 31 and 36 are 310 and 360 degrees (GH-2794).

    Rows of Toronto Intl A (STN_ID 51459) from api.weather.gc.ca/collections/climate-hourly (checked 2026-10-12):
    2019-01-01 08:00Z has a direction of 31 (tens of degrees) beside 29 km/h, 2019-01-05 06:00Z one of 36 beside
    12 km/h, and 2019-01-08 22:00Z one of 0 beside 0 km/h. The glossary: "36 means 360 degrees true ... A value of
    zero (0) denotes a calm wind." The speed of 0 is a reading.
    """
    rows = [
        {
            "LOCAL_DATE": local,
            "UTC_DATE": utc,
            "WIND_DIRECTION": direction,
            "WIND_DIRECTION_FLAG": None,
            "WIND_SPEED": speed,
            "WIND_SPEED_FLAG": None,
        }
        for local, utc, direction, speed in (
            ("2019-01-01 03:00:00", "2019-01-01T08:00:00", 31, 29),
            ("2019-01-05 01:00:00", "2019-01-05T06:00:00", 36, 12),
            ("2019-01-08 17:00:00", "2019-01-08T22:00:00", 0, 0),
        )
    ]
    _serve_eccc(monkeypatch, rows)
    request = EcccObservationRequest(
        parameters=[("hourly", "data", "wind_direction_last_2min"), ("hourly", "data", "wind_speed")],
        start=dt.datetime(2019, 1, 1, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(2019, 1, 9, tzinfo=ZoneInfo("UTC")),
        options=Options(convert_units=False, drop_nulls=False),
    )
    df = request.filter_by_station_id("51459").values.all().df
    assert df.sort("parameter", "timestamp").select("parameter", "value", "quality_flags").rows() == [
        ("wind_direction_last_2min", 310.0, None),
        ("wind_direction_last_2min", 360.0, None),
        ("wind_direction_last_2min", None, "raw:0"),
        ("wind_speed", 29.0, None),
        ("wind_speed", 12.0, None),
        ("wind_speed", 0.0, None),
    ]


def test_eccc_monthly_has_no_flags_and_so_null_quality_flags(
    monkeypatch: pytest.MonkeyPatch, options_convert_units_false: Options
) -> None:
    """Test that monthly rows, which ECCC publishes without flags, come back with null `quality_flags`."""
    _serve_eccc(monkeypatch, [{"LOCAL_DATE": "2025-01", "MEAN_TEMPERATURE": -5.4}])
    request = EcccObservationRequest(
        parameters=[("monthly", "data", "temperature_air_mean_minmax_2m")],
        start="2025-01-01",
        end="2025-01-01",
        options=options_convert_units_false,
    )
    df = request.filter_by_station_id("51459").values.all().df
    assert df.schema["quality_flags"] == pl.String
    assert df.get_column("quality_flags").to_list() == [None]
    assert df.get_column("value").to_list() == [-5.4]


def test_eccc_collects_the_years_of_a_station_with_the_in_memory_engine(
    monkeypatch: pytest.MonkeyPatch,
    options_convert_units_false: Options,
    collect_engines: dict[str, list[str | None]],
) -> None:
    """Test that the collect of the years of a station, an unpivot and a join, asks for the in-memory engine.

    polars 2 runs it on the streaming engine unless told otherwise, which took 0.81 s against 0.21 s for 60 years of
    daily rows of one station, with the same rows (GH-2781); 26 years of hourly rows took the same on both. The
    collect of a page comes before it and is cheap on either engine, so the one asserted on is the last.
    """
    _serve_eccc(monkeypatch, _daily_rows())
    request = EcccObservationRequest(
        parameters=[("daily", "data", "temperature_air_mean_minmax_2m")],
        start="2025-01-15",
        end="2025-01-15",
        options=options_convert_units_false,
    )
    assert not request.filter_by_station_id("51459").values.all().df.is_empty()
    assert collect_engines["provider/eccc/observation/api.py"][-1] == "in-memory"


def test_eccc_station_position_is_the_geometry_of_the_feature(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station is placed where the geometry of its feature says, not where `LATITUDE` and `LONGITUDE` read as degrees.

    The two properties pack degrees, minutes and seconds into one integer (`485500000` is 48 deg 55' 00", `-1234200000`
    123 deg 42' 00" west), the geometry of the same feature is decimal degrees. Divided by 10^7 the properties gave
    48.55 / -123.42 for CHEMAINUS BARE POINT, 0.37 degrees south and 0.28 east of the geometry, and CARWAY on the
    Alberta border at 49 deg N was placed in Montana. Rows as the list gave them on 2026-10-15 (GH-2942).
    """
    stations = [
        (2, "CHEMAINUS BARE POINT", 485500000, -1234200000, [-123.7, 48.916666666666664]),
        (14, "ACTIVE PASS", 485200000, -1231700000, [-123.28333333333333, 48.86666666666667]),
        (2219, "CARWAY", 485959010, -1132234000, [-113.37611111111111, 48.999725]),
    ]
    catalogue = {
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "STN_ID": station_id,
                    "STATION_NAME": name,
                    "PROV_STATE_TERR_CODE": "BC",
                    "LATITUDE": latitude,
                    "LONGITUDE": longitude,
                    "TIMEZONE": "PST",
                    "ELEVATION": "4.00",
                    # a station is listed for daily values by its daily first date (GH-2867)
                    "DLY_FIRST_DATE": "1990-01-01 00:00:00",
                    "DLY_LAST_DATE": "2000-01-01 00:00:00",
                },
                "geometry": {"type": "Point", "coordinates": coordinates},
            }
            for station_id, name, latitude, longitude, coordinates in stations
        ]
    }
    body = json.dumps(catalogue).encode()
    monkeypatch.setattr(
        eccc_api, "download_file", lambda **kwargs: File(url=kwargs["url"], content=BytesIO(body), status=200)
    )
    df = EcccObservationRequest(parameters=[("daily", "data")]).all().df
    assert df.sort("station_id").select("station_id", "latitude", "longitude").rows() == [
        ("14", 48.86666666666667, -123.28333333333333),
        ("2", 48.916666666666664, -123.7),
        ("2219", 48.999725, -113.37611111111111),
    ]
