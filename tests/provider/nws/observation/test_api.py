# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for NWS (United States) observation provider."""

import base64
import datetime as dt
import json
from io import BytesIO
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from tests.provider.value_stubs import serve, stations_result
from wetterdienst import Options, Settings, __version__
from wetterdienst.exceptions import DownloadError
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.model.schema import STATIONS_SCHEMA
from wetterdienst.provider.nws.observation import NwsObservationRequest
from wetterdienst.provider.nws.observation import api as nws_api
from wetterdienst.provider.nws.observation.api import _HALF_HOUR, NwsObservationValues
from wetterdienst.util.network import File

UTC = ZoneInfo("UTC")
DENVER = "KDEN"
# listed by MADIS at coordinates a western-hemisphere box excludes: the Aleutians lie beyond the
# antimeridian, Pago Pago below the equator and Tinian east of the prime meridian
OUTSIDE_THE_BOX = ["PASY", "PAHT", "KAHT", "PAAH", "NSTU", "PGNT"]
# American stations MADIS files under a state code, which the country column cannot catch
FILED_UNDER_A_STATE_CODE = ["PHBK", "TIST", "TISX"]
# Peru and Guatemala, which the country column gives the codes a reader may take for Puerto Rico
# and Guam; and the two British rows among the four the column marks `VI`
NOT_AMERICAN = ["SPIM", "MGGT", "TQPF", "TUPJ"]


def _values(request: NwsObservationRequest) -> NwsObservationValues:
    """Bind a values object to a request without going near the network."""
    return NwsObservationValues(
        sr=StationsResult(
            request=request,
            df=pl.DataFrame(),
            _df_all=pl.DataFrame(),
            _stations_filter=StationsFilter.ALL,
        ),
    )


def _request(
    settings: Settings | None = None, options: Options | None = None, **kwargs: object
) -> NwsObservationRequest:
    """Build a request over a two-day window, which is what the endpoint is asked for."""
    return NwsObservationRequest(
        parameters=[("hourly", "data", "temperature_air_2m")],
        start=dt.datetime(2026, 8, 20, tzinfo=UTC),
        end=dt.datetime(2026, 8, 21, tzinfo=UTC),
        settings=settings or Settings(),
        options=options,
        **kwargs,
    )


def test_nws_request_leaves_the_settings_it_was_given_alone() -> None:
    """Test that building a request does not rewrite the settings every other request shares.

    The provider used to stamp its own headers onto `Settings.fsspec_client_kwargs` in
    `__post_init__`, replacing the User-Agent wetterdienst builds from its version with a literal
    `wetterdienst/0.48.0` and adding a `Content-Type` no GET has any use for. Settings are shared,
    so a DWD request made after an NWS one went out under NWS's headers and a version that was
    already dozens of releases old.
    """
    settings = Settings()
    headers_before = dict(settings.fsspec_client_kwargs["headers"])

    _request(settings)

    assert settings.fsspec_client_kwargs["headers"] == headers_before
    # the version the package is actually at, read at runtime rather than written down -- which is
    # how the literal it replaced came to name a release eighty-five behind
    assert settings.fsspec_client_kwargs["headers"]["User-Agent"].startswith(f"wetterdienst/{__version__}")


def test_nws_url_narrows_to_the_window_the_request_asked_for() -> None:
    """Test that the request's own window is passed to the endpoint rather than post-filtered.

    Asked for nothing in particular the endpoint answers with its whole rolling week, close to a
    megabyte, however little of it the request wanted. The window is widened by half an hour on both sides, so
    that the report kept for the hour at its edge does not depend on where the window is cut (GH-2857).
    """
    url = _values(_request())._build_url(DENVER)  # noqa: SLF001

    assert url.startswith(f"https://api.weather.gov/stations/{DENVER}/observations?")
    assert "start=2026-08-19T23%3A30%3A00Z" in url
    assert "end=2026-08-21T00%3A30%3A00Z" in url


@pytest.mark.parametrize(
    ("start", "end"),
    [
        pytest.param(
            dt.datetime(2026, 8, 19, 18, tzinfo=ZoneInfo("America/Denver")),
            dt.datetime(2026, 8, 20, 18, tzinfo=ZoneInfo("America/Denver")),
            id="named zone",
        ),
        pytest.param("2026-08-19T18:00-06:00", "2026-08-20T18:00-06:00", id="fixed offset"),
    ],
)
def test_nws_url_names_the_window_in_utc_whatever_zone_it_was_asked_in(
    start: str | dt.datetime, end: str | dt.datetime
) -> None:
    """Test that a window asked in Denver time reaches the endpoint as the UTC instants it stands for (GH-2682).

    18:00 in Denver (UTC-6 in August) is 00:00 UTC of the next day, so the wall clock of the bounds as written
    is not what the endpoint, which reads `Z`, must be sent. It is sent half an hour either side of them (GH-2857).
    """
    request = NwsObservationRequest(parameters=[("hourly", "data", "temperature_air_2m")], start=start, end=end)

    url = _values(request)._build_url(DENVER)  # noqa: SLF001

    assert "start=2026-08-19T23%3A30%3A00Z" in url
    assert "end=2026-08-21T00%3A30%3A00Z" in url


def test_nws_url_names_no_window_where_the_request_carries_no_dates() -> None:
    """Test that a request without dates asks for the endpoint's own default, a page of 500 observations.

    `date_required` is enforced at the CLI and the REST API but not in the Python API, so a
    request can reach the endpoint with nothing to narrow it to.
    """
    request = NwsObservationRequest(parameters=[("hourly", "data", "temperature_air_2m")])

    url = _values(request)._build_url(DENVER)  # noqa: SLF001

    assert url == f"https://api.weather.gov/stations/{DENVER}/observations?limit=500"


def test_nws_stations_reads_the_columns_of_the_metar_table_by_their_position(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the headerless station table is read by column position, whichever polars reads it.

    The table has no header, so the readers name the columns by position. polars 1 counts those
    names from ``column_1`` and polars 2 from ``column_0``; the rows are the shape of the live table.
    """
    table = (
        "0000000000\t03PS\t40.85\t -77.91\t  320\tBELLEFONTE, PA      \tUS\tMTR\n"
        "0000000000\tEDDF\t50.03\t   8.57\t  111\tFRANKFURT           \tDE\tMTR\n"
        "0000000000\tPASY\t52.72\t 174.11\t 9999\tEARECKSON AS        \tUS\tMTR\n"
    )
    serve(monkeypatch, nws_api, {"METARTable.txt": table.encode()})
    df = _request(Settings(cache_disable=True)).all().df
    assert df.select("station_id", "latitude", "longitude", "elevation", "name").rows() == [
        ("03PS", 40.85, -77.91, 320.0, "BELLEFONTE, PA"),
        ("PASY", 52.72, 174.11, None, "EARECKSON AS"),
    ]


def test_nws_stations_of_a_table_without_an_american_station_are_the_empty_frame(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A table that lists no American station is a network without stations, typed as the stations frame is."""
    table = "0000000000\tEDDF\t50.03\t   8.57\t  111\tFRANKFURT           \tDE\tMTR\n"
    serve(monkeypatch, nws_api, {"METARTable.txt": table.encode()})
    df = _request(Settings(cache_disable=True)).all().df
    assert df.is_empty()
    assert df.schema == STATIONS_SCHEMA


@pytest.mark.remote
def test_nws_stations_keeps_the_stations_a_western_hemisphere_box_excludes() -> None:
    """Test that US territory is not dropped for lying in the wrong hemisphere.

    The station list was narrowed to `longitude < 0 and latitude > 0` on top of the country
    column, which decides nationality by hemisphere: the Aleutians west of Amchitka, American
    Samoa and Tinian all fall outside that box and are United States territory all the same.

    Whether any of the six currently reports is a separate question, and mostly they do not --
    which is true of about a third of this station list and is not what the box was doing.
    """
    df = _request().all().df
    station_ids = df.get_column("station_id").to_list()

    assert set(OUTSIDE_THE_BOX).issubset(station_ids)
    # the box guarded nothing else: every listed station carries usable coordinates
    assert df.get_column("latitude").is_null().sum() == 0
    assert df.get_column("longitude").is_null().sum() == 0
    assert df.filter(df.get_column("latitude").abs().gt(90)).is_empty()
    assert df.filter(df.get_column("longitude").abs().gt(180)).is_empty()


@pytest.mark.remote
def test_nws_stations_holds_the_stations_filed_under_a_state_code() -> None:
    """Test that the three American stations the country column misses are listed, and no others.

    MADIS files Barking Sands and the two US Virgin Islands airports under a state code instead of
    a country code. They are named one by one because the column cannot be read as a state code in
    general: `PR` in it is Peru and `GU` is Guatemala, and two of its four `VI` rows are British.
    """
    station_ids = _request().all().df.get_column("station_id").to_list()

    assert set(FILED_UNDER_A_STATE_CODE).issubset(station_ids)
    assert not set(NOT_AMERICAN).intersection(station_ids)


@pytest.mark.remote
def test_nws_stations_report_no_elevation_where_the_source_reports_none() -> None:
    """Test that a missing elevation reads as null rather than as 9999 m.

    MADIS writes a missing elevation as 9999, which was cast to a float and passed on unread --
    and interpolation brings a neighbouring station's readings from its elevation to the point's.
    """
    elevations = _request().all().df.get_column("elevation")

    assert elevations.is_null().sum() > 0
    assert elevations.drop_nulls().max() < 9999


@pytest.mark.remote
def test_nws_values_returns_the_requested_window_only() -> None:
    """Test that values arrive for the requested window and carry the declared units.

    The window is taken relative to now rather than written down: the endpoint keeps a rolling
    week and answers an older window with nothing at all, so a fixed date would pass until it
    aged a week and then fail for a reason that has nothing to do with the code.
    """
    end_date = dt.datetime.now(tz=UTC).replace(minute=0, second=0, microsecond=0)
    start_date = end_date - dt.timedelta(days=2)
    request = NwsObservationRequest(
        parameters=[("hourly", "data", "temperature_air_2m")],
        start=start_date,
        end=end_date,
    )

    df = request.filter_by_station_id([DENVER]).values().all().df

    assert not df.is_empty()
    assert df.get_column("station_id").unique().to_list() == [DENVER]
    assert df.get_column("timestamp").min() >= start_date
    assert df.get_column("timestamp").max() <= end_date
    # one reading for each full hour, stamped with it, not the 12 an hour the endpoint serves (GH-2857)
    stamps = df.get_column("timestamp").to_list()
    assert {stamp.minute for stamp in stamps} == {0}
    assert len(stamps) == len(set(stamps)) <= 2 * 24 + 1
    # degree_celsius, as the endpoint's own unitCode says -- Denver is not outside these
    values = df.get_column("value").drop_nulls()
    assert values.min() > -50
    assert values.max() < 50


def test_nws_values_carry_the_madis_quality_control_flag_of_each_quantity(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the `qualityControl` of a quantity is returned verbatim in `quality_flags` (GH-2018, GH-2758).

    Every observation value is `{value, unitCode, qualityControl}` and the flag was dropped with the unit. The
    OpenAPI schema (api.weather.gov/openapi.json, QuantitativeValue.qualityControl): "the quality control flag from
    the MADIS system", one of Z, C, S, V, X, Q, G, B, T; MADIS (madis.ncep.noaa.gov/madis_sfc_qc_notes.shtml): "Z -
    Preliminary, no QC", "C - Coarse pass, passed level 1", "S - Screened, passed levels 1 and 2", "V - Verified,
    passed levels 1, 2, and 3", "X - Rejected/erroneous, failed level 1", "Q - Questioned, passed level 1, failed
    2 or 3", "G - Subjective good", "B - Subjective bad". The live endpoint answered for KJFK on 2026-10-11 with V on
    temperature and Z, S or C on wind gust; the readings here are made up, the shape and the flags are its own.
    """
    features = [
        {
            "properties": {
                "station": "https://api.weather.gov/stations/KDEN",
                "timestamp": f"2026-08-20T{hour:02d}:00:00+00:00",
                "temperature": {"unitCode": "wmoUnit:degC", "value": temperature, "qualityControl": flag},
                "windGust": {"unitCode": "wmoUnit:km_h-1", "value": None, "qualityControl": "Z"},
            }
        }
        for hour, temperature, flag in ((1, 16, "V"), (2, 15, "S"), (3, None, "Z"))
    ]
    serve(monkeypatch, nws_api, {"/observations": json.dumps({"features": features}).encode()})
    request = _request(Settings(cache_disable=True), Options(drop_nulls=False))
    sr = stations_result(request, "hourly", "data", "KDEN")
    df = NwsObservationValues(sr=sr).all().df
    temperature = df.filter(pl.col("parameter") == "temperature_air_2m").sort("timestamp")
    assert temperature.select("value", "quality_flags").rows() == [(16.0, "V"), (15.0, "S"), (None, "Z")]
    assert "quality" not in df.columns
    assert "quality_flag" not in df.columns


def test_nws_values_null_the_wind_direction_of_a_calm_and_keep_north(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the direction 0 of a METAR `00000KT` is null with `raw:0`, and 360 and a speed of 0 are not (GH-2794).

    The observations of KBOS on 2026-10-12 (api.weather.gov/stations/KBOS/observations): 12:54Z `36005KT` has a
    direction of 360 (V) beside 9.36 km/h, 14:54Z `00000KT` one of 0 (V) beside 0, and 15:54Z `VRB05KT` one of null (Z)
    beside 9.36. The NWS METAR decode key: "00000KT for calm".
    """
    quantity = {"unitCode": "wmoUnit:degree_(angle)"}
    speed = {"unitCode": "wmoUnit:km_h-1", "qualityControl": "V"}
    features = [
        {
            "properties": {
                "station": "https://api.weather.gov/stations/KBOS",
                "timestamp": f"2026-10-12T{hour}:54:00+00:00",
                "windDirection": {**quantity, "value": direction, "qualityControl": flag},
                "windSpeed": {**speed, "value": wind_speed},
            }
        }
        for hour, direction, flag, wind_speed in ((12, 360, "V", 9.36), (14, 0, "V", 0), (15, None, "Z", 9.36))
    ]
    serve(monkeypatch, nws_api, {"/observations": json.dumps({"features": features}).encode()})
    request = NwsObservationRequest(
        parameters=[
            ("hourly", "data", "wind_direction_mean_last_2min"),
            ("hourly", "data", "wind_speed_mean_last_2min"),
        ],
        start=dt.datetime(2026, 10, 12, tzinfo=UTC),
        end=dt.datetime(2026, 10, 13, tzinfo=UTC),
        settings=Settings(cache_disable=True),
        options=Options(drop_nulls=False),
    )
    sr = stations_result(request, "hourly", "data", "KBOS")
    df = NwsObservationValues(sr=sr).all().df
    direction = df.filter(pl.col("parameter") == "wind_direction_mean_last_2min").sort("timestamp")
    assert direction.select("value", "quality_flags").rows() == [(360.0, "V"), (None, "V,raw:0"), (None, "Z")]
    wind_speed = df.filter(pl.col("parameter") == "wind_speed_mean_last_2min").sort("timestamp")
    # a speed of 0 is a reading, and 9.36 km/h arrives as 2.6 m/s
    assert wind_speed.select("value", "quality_flags").rows() == [(2.6, "V"), (0.0, "V"), (2.6, "V")]


def test_nws_values_keep_the_fractions_of_the_quantities_that_carry_them(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a fraction is no longer truncated on the read: 0.8 mm stays 0.8 and 28.4 mm stays 28.4 (GH-2849).

    The observation JSON was read with an integer schema for the gust, the pressures, the visibility and the
    precipitation, and polars truncates when it reads a float as an integer: 0.8 mm of rain read as 0, 1.8 as 1,
    4.8 as 4 and 28.4 as 28. The readings are those of api.weather.gov/stations/{id}/observations (read 2026-10-13,
    KBOS, KDEN, KSEA, KMIA and KORD, 500 observations each): precipitation 0.8 (1 h), 1.3 (3 h) and 28.4 (6 h), the
    gust 35.172 km/h, the pressure 101760.98 Pa and the visibility 16093.44 m. The direction is read as a float too:
    2406 of 2406 readings are whole degrees, which the endpoint (a number) does not promise.
    """

    def quantity(unit_code: str, value: float) -> dict[str, object]:
        return {"unitCode": unit_code, "value": value, "qualityControl": "V"}

    readings = {
        "windDirection": quantity("wmoUnit:degree_(angle)", 60),
        "windGust": quantity("wmoUnit:km_h-1", 35.172),
        "barometricPressure": quantity("wmoUnit:Pa", 101760.98),
        "seaLevelPressure": quantity("wmoUnit:Pa", 101760.5),
        "visibility": quantity("wmoUnit:m", 16093.44),
        "precipitationLastHour": quantity("wmoUnit:mm", 0.8),
        "precipitationLast3Hours": quantity("wmoUnit:mm", 1.3),
        "precipitationLast6Hours": quantity("wmoUnit:mm", 28.4),
    }
    properties = {"station": "https://api.weather.gov/stations/KBOS", "timestamp": "2026-10-12T12:54:00+00:00"}
    features = [{"properties": {**properties, **readings}}]
    serve(monkeypatch, nws_api, {"/observations": json.dumps({"features": features}).encode()})
    request = NwsObservationRequest(
        parameters=[("hourly", "data")],
        start=dt.datetime(2026, 10, 12, tzinfo=UTC),
        end=dt.datetime(2026, 10, 13, tzinfo=UTC),
        settings=Settings(cache_disable=True),
        options=Options(drop_nulls=False),
    )
    sr = stations_result(request, "hourly", "data", "KBOS")
    df = NwsObservationValues(sr=sr).all().df
    values = dict(df.select("parameter", "value").rows())
    assert values["wind_direction_mean_last_2min"] == 60.0
    # the gust arrives in km/h and is returned in m/s, the pressures arrive in Pa and are returned in hPa
    assert values["wind_gust_max_last_10min"] == pytest.approx(35.172 / 3.6)
    # `barometricPressure` is the altimeter setting, `seaLevelPressure` the one with the temperatures observed
    assert values["pressure_air_site_reduced"] == pytest.approx(1017.6098)
    assert values["pressure_air_sea_level"] == pytest.approx(1017.605)
    assert values["visibility"] == pytest.approx(16093.44)
    assert values["precipitation_amount_since_last_routine_report"] == pytest.approx(0.8)
    assert values["precipitation_amount_last_3h"] == pytest.approx(1.3)
    assert values["precipitation_amount_last_6h"] == pytest.approx(28.4)


# The observations of KDEN from 2026-10-14 11:30Z to 2026-10-15 12:30Z that carry the `precipitationLastHour` key, the
# METAR and SPECI reports of api.weather.gov/stations/KDEN/observations (read 2026-10-15), as (time, whether the report
# has a `rawMessage`, temperature in degree Celsius, sea level pressure in Pa, precipitation of the last hour in mm).
# The routine METAR is the one at :53; the others are SPECI (17:20, 17:30, 18:49, 20:30, 23:12, ...) and reports at
# other minutes. A quarter of the reports have an empty `rawMessage`, and one is filed at a minute of the 5-minute grid
# (00:05), with no sea level pressure.
KDEN_REPORTS = (
    ("10-14 11:53", True, 6.7, 101650, 0.3),
    ("10-14 12:53", False, 6.7, 101720, 0),
    ("10-14 13:23", False, 6.7, None, None),
    ("10-14 13:40", False, 6.1, None, None),
    ("10-14 13:43", False, 6.1, None, None),
    ("10-14 13:53", True, 6.1, 101710, 0),
    ("10-14 14:53", True, 6.1, 101770, 0.3),
    ("10-14 15:53", False, 6.1, 101780, 0),
    ("10-14 16:53", True, 6.7, 101750, 0),
    ("10-14 17:20", True, 6.7, None, 0),
    ("10-14 17:30", True, 6.7, None, 0),
    ("10-14 17:53", True, 6.7, 101690, 0),
    ("10-14 18:49", True, 7, None, 0),
    ("10-14 18:53", True, 6.7, 101600, 0),
    ("10-14 19:20", False, 7.2, None, 0),
    ("10-14 19:34", False, 7.2, None, 0),
    ("10-14 19:53", False, 7.2, 101500, 0),
    ("10-14 20:30", True, 6.7, None, 0.3),
    ("10-14 20:53", True, 6.7, 101480, 0.3),
    ("10-14 21:18", False, 7.2, None, 0),
    ("10-14 21:20", False, 7.2, None, 0),
    ("10-14 21:53", False, 7.8, 101420, 0),
    ("10-14 22:53", True, 8.3, 101420, None),
    ("10-14 23:12", True, 8.3, None, None),
    ("10-14 23:26", False, 7.8, None, 0),
    ("10-14 23:42", False, 7.8, None, 0),
    ("10-14 23:50", False, 8, None, 0),
    ("10-14 23:53", False, 7.8, 101370, 0),
    ("10-15 00:05", False, 7.2, None, None),
    ("10-15 00:53", True, 7.2, 101400, None),
    ("10-15 01:53", True, 6.7, 101480, None),
    ("10-15 02:15", True, 6.7, None, None),
    ("10-15 02:53", True, 6.7, 101550, None),
    ("10-15 03:39", True, 6.7, None, None),
    ("10-15 03:53", True, 6.7, 101600, None),
    ("10-15 04:36", True, 6.1, None, None),
    ("10-15 04:53", True, 6.1, 101670, None),
    ("10-15 05:11", False, 6.1, None, None),
    ("10-15 05:53", True, 6.1, 101700, None),
    ("10-15 05:56", True, 5.6, None, None),
    ("10-15 06:10", True, 5.6, None, None),
    ("10-15 06:53", True, 5.6, 101740, None),
    ("10-15 07:42", False, 5.6, None, None),
    ("10-15 07:53", False, 5.6, 101760, None),
    ("10-15 08:07", False, 5.6, None, None),
    ("10-15 08:19", True, 5.6, None, None),
    ("10-15 08:53", True, 5, 101870, None),
    ("10-15 09:53", False, 4.4, 101940, None),
    ("10-15 10:53", False, 5, 102060, None),
    ("10-15 11:27", True, 5, None, None),
    ("10-15 11:53", True, 5, 102210, None),
)
# the full hours the day keeps for the window of 2026-10-14 12:00Z to 2026-10-15 12:00Z, 25 of them, each with the
# report kept for it: the one nearest to the full hour, which is the routine METAR at :53 but for 00:05 and 05:56,
# which lie nearer to the full hour than the METAR does
KDEN_KEPT = (
    ("10-14 12:00", "10-14 11:53"),
    ("10-14 13:00", "10-14 12:53"),
    ("10-14 14:00", "10-14 13:53"),
    ("10-14 15:00", "10-14 14:53"),
    ("10-14 16:00", "10-14 15:53"),
    ("10-14 17:00", "10-14 16:53"),
    ("10-14 18:00", "10-14 17:53"),
    ("10-14 19:00", "10-14 18:53"),
    ("10-14 20:00", "10-14 19:53"),
    ("10-14 21:00", "10-14 20:53"),
    ("10-14 22:00", "10-14 21:53"),
    ("10-14 23:00", "10-14 22:53"),
    ("10-15 00:00", "10-15 00:05"),
    ("10-15 01:00", "10-15 00:53"),
    ("10-15 02:00", "10-15 01:53"),
    ("10-15 03:00", "10-15 02:53"),
    ("10-15 04:00", "10-15 03:53"),
    ("10-15 05:00", "10-15 04:53"),
    ("10-15 06:00", "10-15 05:56"),
    ("10-15 07:00", "10-15 06:53"),
    ("10-15 08:00", "10-15 07:53"),
    ("10-15 09:00", "10-15 08:53"),
    ("10-15 10:00", "10-15 09:53"),
    ("10-15 11:00", "10-15 10:53"),
    ("10-15 12:00", "10-15 11:53"),
)


def _stamp(text: str) -> dt.datetime:
    """Read `10-14 11:53` as a UTC instant of 2026."""
    return dt.datetime.strptime(f"2026-{text}", "%Y-%m-%d %H:%M").replace(tzinfo=UTC)


def _observation(timestamp: dt.datetime, temperature: float, *, report: bool, **quantities: float | None) -> dict:
    """Write an observation the way the endpoint serves it, with the quantities it is given.

    A report carries the `precipitationLastHour` key, a 5-minute row leaves it out. A quantity that is `None` is
    served as a null value with the flag of the endpoint's unmeasured quantities.
    """

    def quantity(unit_code: str, value: float | None) -> dict[str, object]:
        return {"unitCode": unit_code, "value": value, "qualityControl": "V" if value is not None else "Z"}

    properties = {
        "station": "https://api.weather.gov/stations/KDEN",
        "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
        "temperature": quantity("wmoUnit:degC", temperature),
    }
    if "sea_level_pressure" in quantities:
        properties["seaLevelPressure"] = quantity("wmoUnit:Pa", quantities["sea_level_pressure"])
    if report:
        properties["precipitationLastHour"] = quantity("wmoUnit:mm", quantities.get("precipitation"))
    return {"properties": properties}


def _kden_day() -> list[dict]:
    """Serve KDEN for 2026-10-14 11:30Z to 2026-10-15 12:30Z: the reports above and a 5-minute row at each grid minute.

    The reports are as the endpoint served them. The 5-minute rows are generated (the endpoint serves one at every
    multiple of five minutes that carries no report), with the temperature of the report before them in whole
    degrees, as the 5-minute rows of KDEN have it (4,056 of 4,056 rows of ten stations, 2026-10-15).
    """
    reports = {_stamp(text): (temperature, pressure, rain) for text, _, temperature, pressure, rain in KDEN_REPORTS}
    observations = []
    temperature = 7.0
    time = _stamp("10-14 11:30")
    while time <= _stamp("10-15 12:30"):
        if time in reports:
            temperature, pressure, rain = reports[time]
            observations.append(
                _observation(time, temperature, report=True, sea_level_pressure=pressure, precipitation=rain),
            )
        elif time.minute % 5 == 0:
            observations.append(_observation(time, float(round(temperature)), report=False))
        time += dt.timedelta(minutes=1)
    # the endpoint answers the latest first
    return observations[::-1]


def _serve_observations(monkeypatch: pytest.MonkeyPatch, observations: list[dict]) -> None:
    serve(monkeypatch, nws_api, {"/observations": json.dumps({"features": observations}).encode()})


def _hourly(
    parameters: list[str], start: dt.datetime, end: dt.datetime, options: Options | None = None
) -> pl.DataFrame:
    request = NwsObservationRequest(
        parameters=[("hourly", "data", parameter) for parameter in parameters],
        start=start,
        end=end,
        settings=Settings(cache_disable=True),
        options=options,
    )
    sr = stations_result(request, "hourly", "data", "KDEN")
    return NwsObservationValues(sr=sr).all().df


def test_nws_hourly_keeps_one_report_an_hour(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a day of 5-minute rows, METAR and SPECI is one reading for each hour, the nearest report (GH-2857).

    The endpoint serves about 12 observations an hour, and `hourly` returned all of them. The day is KDEN's from
    2026-10-14 12:00Z to 2026-10-15 12:00Z, with the half hour on either side that is asked for: 342 observations,
    291 5-minute rows and 51 reports, of which 25 are the routine METAR at :53 and the others SPECI or at other minutes.
    """
    observations = _kden_day()
    assert len(observations) == 342
    _serve_observations(monkeypatch, observations)

    df = _hourly(
        ["temperature_air_2m", "pressure_air_sea_level", "precipitation_amount_since_last_routine_report"],
        _stamp("10-14 12:00"),
        _stamp("10-15 12:00"),
        Options(drop_nulls=False),
    )

    temperature = df.filter(pl.col("parameter") == "temperature_air_2m").sort("timestamp")
    # one row for each full hour, stamped with it
    assert temperature.get_column("timestamp").to_list() == [_stamp(hour) for hour, _ in KDEN_KEPT]
    # each carries the reading of the report kept for its hour, with its tenth of a degree where the report has one
    reports = {text: (temperature, pressure, rain) for text, _, temperature, pressure, rain in KDEN_REPORTS}
    assert temperature.get_column("value").to_list() == [reports[report][0] for _, report in KDEN_KEPT]
    # the reports that lie nearer to the full hour than the METAR carry no sea level pressure, which the METAR does:
    # the hour takes it from the METAR (05:53 for 06:00) or from the 5-minute row that has it (23:53 for 00:00), GH-3480
    pressure = dict(df.filter(pl.col("parameter") == "pressure_air_sea_level").select("timestamp", "value").rows())
    assert pressure[_stamp("10-14 15:00")] == pytest.approx(1017.7)
    assert pressure[_stamp("10-15 06:00")] == pytest.approx(1017.0)
    assert pressure[_stamp("10-15 00:00")] == pytest.approx(1013.7)
    precipitation = dict(
        df.filter(pl.col("parameter") == "precipitation_amount_since_last_routine_report")
        .select("timestamp", "value")
        .rows()
    )
    assert precipitation[_stamp("10-14 15:00")] == pytest.approx(0.3)


def test_nws_hourly_precipitation_is_the_running_total_of_the_report_that_closes_the_hour(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the precipitation is the METAR's running total, named for what it is, not an hourly amount (GH-2841).

    The reports of api.weather.gov/stations/KORD/observations (read 2026-10-16, the stub stands in for the station)
    from 2026-10-15 22:51 to 23:51: the amounts of the precipitation group restart at 22:54 and grow to the 17.5 mm of
    the METAR of 23:51 (`P0069`, with the 6-hour amount of 22.9 mm in `60090`). An hour holds the one report kept for
    it, the METAR of 23:51 for 00:00, so the amounts of the reports in between do not come beside it, and the name says
    that the amount is the one since the last routine report, no precipitation of the last hour.
    """
    amounts = {"22:51": 4.3, "22:54": 0.8, "23:06": 8.4, "23:38": 17.3, "23:42": 17.5, "23:51": 17.5}
    observations = [
        _observation(_stamp(f"10-15 {time}"), 14.0, report=True, precipitation=amount)
        for time, amount in amounts.items()
    ]
    _serve_observations(monkeypatch, observations)

    df = _hourly(["precipitation_amount_since_last_routine_report"], _stamp("10-16 00:00"), _stamp("10-16 00:00"))

    assert df.select("parameter", "timestamp", "value").rows() == [
        ("precipitation_amount_since_last_routine_report", _stamp("10-16 00:00"), 17.5),
    ]


def test_nws_hourly_fills_the_full_hour_grid_that_skip_empty_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a station that reported every hour is complete on the full-hour grid, and not skipped (GH-2857).

    `skip_empty` counts the hours a station has a value for. Rows at :53 and :05 would fall in 23 of the 25 hours of
    the day (00:05 and 00:53 share the hour 00:00, 11:53 is cut off), below the default threshold of 0.95, and the
    station would be skipped as incomplete.
    """
    _serve_observations(monkeypatch, _kden_day())

    df = _hourly(
        ["temperature_air_2m"],
        _stamp("10-14 12:00"),
        _stamp("10-15 12:00"),
        Options(skip_empty=True, skip_threshold=1.0),
    )

    assert df.height == len(KDEN_KEPT)


def _serve_window(monkeypatch: pytest.MonkeyPatch, observations: list[dict]) -> None:
    """Serve the observations between the `start` and `end` of the url, as the endpoint answers them."""

    def between(url: str) -> bytes:
        query = parse_qs(urlparse(url).query)
        start, end = (
            dt.datetime.strptime(query[key][0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC) for key in ("start", "end")
        )
        features = [
            feature
            for feature in observations
            if start <= dt.datetime.fromisoformat(feature["properties"]["timestamp"]) <= end
        ]
        return json.dumps({"features": features}).encode()

    serve(monkeypatch, nws_api, {"/observations": between})


def test_nws_hourly_does_not_depend_on_where_the_window_is_cut(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the report an hour keeps is the same whichever window asks for it (GH-2857).

    The endpoint answers the observations between the `start` and `end` it is sent, as here. The window of 14:00 to
    16:00 reaches the endpoint as 13:30 to 16:30, so the METAR of 13:53 is there to be the report of the hour of
    14:00. Sent as 14:00 it would not be, and the 5-minute row of 14:00 would be kept instead, which the window from
    12:00 never keeps.
    """
    _serve_window(monkeypatch, _kden_day())
    wide = _hourly(["temperature_air_2m"], _stamp("10-14 12:00"), _stamp("10-14 16:00")).sort("timestamp")
    short = _hourly(["temperature_air_2m"], _stamp("10-14 14:00"), _stamp("10-14 16:00")).sort("timestamp")

    assert wide.get_column("timestamp").to_list() == [_stamp(hour) for hour, _ in KDEN_KEPT[:5]]
    assert short.select("timestamp", "value").rows() == wide.select("timestamp", "value").rows()[2:]
    assert short.get_column("value").to_list()[0] == 6.1


def test_nws_hourly_keeps_the_report_just_after_the_end_of_the_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the endpoint is asked past the end: the SPECI of 16:02 is the report of 16:00 (GH-2857).

    The window ends at 16:00 and the METAR of 15:53 is 7 minutes from the full hour, the SPECI of 16:02 two. Sent
    as 16:00 the endpoint would not serve the SPECI, and the METAR would be kept for an hour the longer window
    gives to the SPECI.
    """
    observations = [
        _observation(_stamp("10-14 15:53"), 10.0, report=True),
        _observation(_stamp("10-14 16:02"), 11.0, report=True),
    ]
    _serve_window(monkeypatch, observations)

    df = _hourly(["temperature_air_2m"], _stamp("10-14 15:00"), _stamp("10-14 16:00"))

    assert df.select("timestamp", "value").rows() == [(_stamp("10-14 16:00"), 11.0)]


def test_nws_hourly_url_asks_for_the_half_hour_around_the_window(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the endpoint is asked for the observations that decide which report the edge hours keep (GH-2857)."""
    urls: list[str] = []

    def download_file(*args: str, url: str | None = None, **_: object) -> File:
        urls.append(url or args[0])
        return File(url=urls[-1], content=BytesIO(json.dumps({"features": []}).encode()), status=200)

    monkeypatch.setattr(nws_api, "download_file", download_file)
    _hourly(["temperature_air_2m"], _stamp("10-14 12:00"), _stamp("10-14 16:00"))

    assert urls == [
        (
            "https://api.weather.gov/stations/KDEN/observations"
            "?start=2026-10-14T11%3A30%3A00Z&end=2026-10-14T16%3A30%3A00Z&limit=500"
        )
    ]


@pytest.mark.parametrize(
    ("served", "kept"),
    [
        pytest.param(
            [("14:54", True), ("14:55", False), ("15:00", False), ("15:05", False)],
            [("15:00", 0)],
            id="a report over the 5-minute row at the full hour",
        ),
        pytest.param([("14:57", True), ("15:03", True)], [("15:00", 0)], id="two reports as near: the earlier"),
        pytest.param([("14:58", True), ("15:03", True)], [("15:00", 0)], id="the nearer of two reports"),
        pytest.param([("14:54", True), ("15:02", True)], [("15:00", 1)], id="a SPECI nearer the hour than the METAR"),
        pytest.param([("14:30", True), ("15:29", True)], [("15:00", 1)], id="14:30 belongs to 15:00"),
        pytest.param([("14:30", True), ("15:30", True)], [("15:00", 0), ("16:00", 1)], id="15:30 belongs to 16:00"),
        pytest.param(
            [("16:50", False), ("16:55", False), ("17:00", False), ("17:05", False)],
            [("17:00", 2)],
            id="no report: the 5-minute row nearest the hour",
        ),
        pytest.param(
            [("16:20", False), ("16:35", False), ("16:55", False)],
            [("16:00", 0), ("17:00", 2)],
            id="no report: one 5-minute row for each hour",
        ),
        pytest.param(
            [("17:20", True), ("17:25", False), ("17:35", False)],
            [("17:00", 0), ("18:00", 2)],
            id="a report far from the hour, and the next hour",
        ),
    ],
)
def test_nws_hourly_report_rules(
    monkeypatch: pytest.MonkeyPatch, served: list[tuple[str, bool]], kept: list[tuple[str, int]]
) -> None:
    """Test which observation an hour keeps, and that it is stamped with the hour (GH-2857).

    A report, then the one nearest to the full hour, then the earlier. The observation served at position `index`
    has the temperature 10 + `index`, so the value says which one was kept.
    """
    observations = [
        _observation(_stamp(f"10-14 {time}"), 10.0 + index, report=report)
        for index, (time, report) in enumerate(served)
    ]
    _serve_observations(monkeypatch, observations)
    df = _hourly(["temperature_air_2m"], _stamp("10-14 00:00"), _stamp("10-14 23:59")).sort("timestamp")
    assert df.select("timestamp", "value").rows() == [(_stamp(f"10-14 {hour}"), 10.0 + index) for hour, index in kept]


def _raw_observation(timestamp: dt.datetime, *, report: bool = False, **quantities: tuple[float | None, str]) -> dict:
    """Write an observation of the endpoint with the quantities named by their key, each as `(value, flag)`.

    A quantity that is not named is left out, as the endpoint leaves out what a row does not carry. A report carries the
    `precipitationLastHour` key, as the endpoint writes it, with the value it is given or none.
    """
    properties: dict[str, object] = {
        "station": "https://api.weather.gov/stations/KDEN",
        "timestamp": timestamp.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
    }
    for key, (value, flag) in quantities.items():
        properties[key] = {"unitCode": "wmoUnit:x", "value": value, "qualityControl": flag}
    if report:
        properties.setdefault("precipitationLastHour", {"unitCode": "wmoUnit:mm", "value": None, "qualityControl": "Z"})
    return {"properties": properties}


def _hour_of(monkeypatch: pytest.MonkeyPatch, observations: list[dict], parameters: list[str]) -> dict:
    """Serve the observations and give `{parameter: (value, quality_flags)}` of the one hour, 15:00, they fall in."""
    _serve_observations(monkeypatch, observations)
    df = _hourly(parameters, _stamp("10-14 15:00"), _stamp("10-14 15:00"), Options(drop_nulls=False))
    assert df.get_column("timestamp").unique().to_list() == [_stamp("10-14 15:00")]
    return {row[0]: row[1:] for row in df.select("parameter", "value", "quality_flags").rows()}


def test_nws_hourly_fills_the_gap_of_the_kept_report_from_the_verified_row_of_the_hour(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a METAR without a temperature takes the 5-minute row's, with the flag of that row (GH-3480).

    Measured on live data (15 stations, 5 days, read 2026-10-28): in 31 of 1,697 station-hours the METAR kept had no
    temperature (MADIS flag `Z`, no control) while a 5-minute row of the same hour had one (flag `V`), e.g. KSEA
    2026-10-24 20:53 (METAR, no temperature) and 21:00 (5-minute row, 12 degC). The readings here are made up.
    """
    observations = [
        _raw_observation(_stamp("10-14 14:53"), report=True, temperature=(None, "Z"), dewpoint=(5.0, "S")),
        _raw_observation(_stamp("10-14 15:00"), temperature=(12.0, "V"), dewpoint=(None, "Z")),
    ]
    got = _hour_of(monkeypatch, observations, ["temperature_air_2m", "temperature_dew_point_2m"])
    # the temperature is the 5-minute row's with its flag, not the `Z` of the report; the dew point the report has stays
    assert got == {"temperature_air_2m": (12.0, "V"), "temperature_dew_point_2m": (5.0, "S")}


def test_nws_hourly_fills_every_quantity_of_the_list_and_none_of_the_others(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test which quantities a gap is filled for: the core ones, not the wind direction, the gust and the wind chill.

    A METAR leaves the direction of a variable wind out, the gust when there is none, and the wind chill is there in
    the cold only (GH-3480), so the null is the report's own answer; a value of a row up to 30 minutes away is not.
    """
    filled = {
        "temperature": "temperature_air_2m",
        "dewpoint": "temperature_dew_point_2m",
        "relativeHumidity": "humidity_relative",
        "barometricPressure": "pressure_air_site_reduced",
        "seaLevelPressure": "pressure_air_sea_level",
        "visibility": "visibility",
        "windSpeed": "wind_speed_mean_last_2min",
        "precipitationLast3Hours": "precipitation_amount_last_3h",
        "precipitationLast6Hours": "precipitation_amount_last_6h",
    }
    not_filled = {
        "windDirection": "wind_direction_mean_last_2min",
        "windGust": "wind_gust_max_last_10min",
        "windChill": "temperature_wind_chill",
    }
    quantities = {**filled, **not_filled}
    # readings in the plausible range of each quantity, in the endpoint's units
    readings = {"relativeHumidity": 70.0, "barometricPressure": 84000.0, "seaLevelPressure": 101000.0}
    readings |= {"visibility": 10000.0, "windDirection": 270.0, "windGust": 30.0}
    observations = [
        _raw_observation(_stamp("10-14 14:53"), report=True, **dict.fromkeys(quantities, (None, "Z"))),
        _raw_observation(_stamp("10-14 15:00"), **{key: (readings.get(key, 7.0), "V") for key in quantities}),
    ]
    got = _hour_of(monkeypatch, observations, list(quantities.values()))
    # every quantity of the list comes from the 5-minute row, with its flag
    assert {parameter: got[parameter][1] for parameter in filled.values()} == dict.fromkeys(filled.values(), "V")
    assert all(got[parameter][0] is not None for parameter in filled.values())
    unfilled = {parameter: got[parameter] for parameter in not_filled.values()}
    assert unfilled == dict.fromkeys(not_filled.values(), (None, "Z"))


def test_nws_hourly_fills_a_precipitation_sum_the_kept_report_lacks_from_another_report(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a precipitation sum the kept report lacks comes from another report of the hour (GH-3480).

    The 6-hour amount is filed in the synoptic METAR only; a SPECI nearer to the full hour displaces that METAR and
    used to take the amount with it (KDEN, the 00Z METAR at 23:53 against the SPECI at 00:05).
    """
    observations = [
        _raw_observation(_stamp("10-14 14:53"), report=True, precipitationLast6Hours=(0.8, "V")),
        _raw_observation(
            _stamp("10-14 15:02"), report=True, precipitationLastHour=(0.3, "V"), precipitationLast6Hours=(None, "Z")
        ),
    ]
    got = _hour_of(
        monkeypatch,
        observations,
        ["precipitation_amount_since_last_routine_report", "precipitation_amount_last_6h"],
    )
    assert got == {
        "precipitation_amount_since_last_routine_report": (0.3, "V"),
        "precipitation_amount_last_6h": (0.8, "V"),
    }


def test_nws_hourly_keeps_the_value_the_kept_report_has(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a value of the kept report is never replaced, however good the other row's flag or distance is."""
    observations = [
        _raw_observation(_stamp("10-14 14:53"), report=True, temperature=(11.7, "Z")),
        _raw_observation(_stamp("10-14 15:00"), temperature=(12.0, "V")),
    ]
    assert _hour_of(monkeypatch, observations, ["temperature_air_2m"]) == {"temperature_air_2m": (11.7, "Z")}


def test_nws_hourly_of_an_hour_with_one_observation_has_nothing_to_fill_from(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the only observation of an hour keeps its gap and its flag."""
    observations = [_raw_observation(_stamp("10-14 14:53"), report=True, temperature=(None, "Z"))]
    assert _hour_of(monkeypatch, observations, ["temperature_air_2m"]) == {"temperature_air_2m": (None, "Z")}


def test_nws_hourly_without_a_donor_keeps_the_gap(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that where no other row of the hour has the quantity, or has it as null, the gap stays."""
    observations = [
        _raw_observation(_stamp("10-14 14:53"), report=True, temperature=(None, "Z")),
        _raw_observation(_stamp("10-14 15:00"), temperature=(None, "Z")),
        _raw_observation(_stamp("10-14 15:05")),
    ]
    assert _hour_of(monkeypatch, observations, ["temperature_air_2m"]) == {"temperature_air_2m": (None, "Z")}


@pytest.mark.parametrize(
    ("donors", "expected"),
    [
        pytest.param([("15:00", 1.0, False), ("14:55", 2.0, False)], 1.0, id="the nearest to the full hour"),
        pytest.param([("14:50", 1.0, False), ("15:10", 2.0, False)], 1.0, id="as near: the earlier"),
        pytest.param([("14:50", 1.0, False), ("15:10", 2.0, True)], 2.0, id="as near: a report over a 5-minute row"),
        pytest.param([("14:50", 1.0, True), ("15:10", 2.0, True)], 1.0, id="as near, both reports: the earlier"),
        pytest.param([("14:40", 1.0, False), ("15:10", 2.0, False)], 2.0, id="10 minutes are nearer than 20"),
    ],
)
def test_nws_hourly_fill_takes_the_nearest_row_of_the_hour(
    monkeypatch: pytest.MonkeyPatch, donors: list[tuple[str, float, bool]], expected: float
) -> None:
    """Test which row a gap is filled from: the nearest to the full hour, a report over a 5-minute row, the earlier.

    The report kept is the one at 14:58, the nearest report to the full hour, and has no temperature.
    """
    observations = [_raw_observation(_stamp("10-14 14:58"), report=True, temperature=(None, "Z"))]
    observations += [
        _raw_observation(_stamp(f"10-14 {time}"), report=report, temperature=(value, "V"))
        for time, value, report in donors
    ]
    assert _hour_of(monkeypatch, observations, ["temperature_air_2m"]) == {"temperature_air_2m": (expected, "V")}


def test_nws_hourly_fill_takes_each_quantity_from_its_own_nearest_row(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a quantity the nearest row lacks is taken from the next one, quantity by quantity."""
    observations = [
        _raw_observation(_stamp("10-14 14:53"), report=True, temperature=(None, "Z"), dewpoint=(None, "Z")),
        _raw_observation(_stamp("10-14 15:00"), temperature=(12.0, "V")),
        _raw_observation(_stamp("10-14 15:05"), temperature=(13.0, "V"), dewpoint=(4.0, "V")),
    ]
    got = _hour_of(monkeypatch, observations, ["temperature_air_2m", "temperature_dew_point_2m"])
    assert got == {"temperature_air_2m": (12.0, "V"), "temperature_dew_point_2m": (4.0, "V")}


def test_nws_hourly_of_a_station_without_observations_is_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a station the endpoint holds nothing for still returns an empty frame (GH-2857)."""
    _serve_observations(monkeypatch, [])
    assert _hourly(["temperature_air_2m"], _stamp("10-14 00:00"), _stamp("10-14 23:59")).is_empty()


def _three_days() -> list[dict]:
    """Give KDEN's observations of 2026-10-12 to 2026-10-14 as the endpoint serves them: 936, newest first.

    A 5-minute row at every multiple of five minutes, and a report at :53 beside it, as in ``KDEN_REPORTS``. The
    temperature of a report is a tenth of a degree and that of a 5-minute row a whole one, so the value says which
    of the two an hour kept.
    """
    observations = []
    time = _stamp("10-12 00:00")
    while time < _stamp("10-15 00:00"):
        if time.minute == 53:
            observations.append(_observation(time, 5.3 + time.hour / 100, report=True))
        elif time.minute % 5 == 0:
            observations.append(_observation(time, float(5 + time.hour // 12), report=False))
        time += dt.timedelta(minutes=1)
    return observations[::-1]


def _cursor(stamp: str) -> str:
    """Give the cursor the endpoint names for a page whose oldest observation is ``stamp``: ``{"s": stamp}``."""
    return base64.urlsafe_b64encode(json.dumps({"s": stamp}, separators=(",", ":")).encode()).decode()


def _serve_pages(monkeypatch: pytest.MonkeyPatch, observations: list[dict]) -> list[str]:
    """Serve the observations the way the endpoint pages them, and return the URLs asked for.

    The newest 500 observations of the window, newest first, with ``pagination.next`` naming a cursor on the stamp
    of the oldest of them. The cursor walks backwards, strictly older than its stamp, honours a ``start`` and
    takes no ``end`` (read 2026-10-17); a page that is the last one names a ``next`` as well (KBOS, 81 rows).
    """
    urls: list[str] = []

    def download_file(*args: str, url: str | None = None, **_: object) -> File:
        urls.append(url or args[0])
        query = parse_qs(urlparse(urls[-1]).query)
        rows = sorted(observations, key=lambda o: o["properties"]["timestamp"], reverse=True)
        if "cursor" in query:
            before = json.loads(base64.urlsafe_b64decode(query["cursor"][0]))["s"]
            rows = [o for o in rows if o["properties"]["timestamp"] < before]
        elif "end" in query:
            end = dt.datetime.strptime(query["end"][0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
            rows = [o for o in rows if dt.datetime.fromisoformat(o["properties"]["timestamp"]) <= end]
        if "start" in query:
            start = dt.datetime.strptime(query["start"][0], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC)
            rows = [o for o in rows if dt.datetime.fromisoformat(o["properties"]["timestamp"]) >= start]
        page = rows[:500]
        body: dict[str, object] = {"features": page}
        if page:
            body["pagination"] = {
                "next": f"https://api.weather.gov/stations/KDEN/observations?cursor={_cursor(page[-1]['properties']['timestamp'])}"
            }
        return File(url=urls[-1], content=BytesIO(json.dumps(body).encode()), status=200)

    monkeypatch.setattr(nws_api, "download_file", download_file)
    return urls


def test_nws_hourly_follows_the_pages_of_a_window_of_more_than_500_observations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a window of three days is read to its start, not to the newest 500 observations (GH-2994).

    936 observations are about 40 hours at 12 an hour for the first page, which was all the provider read; the
    hourly rows were those of the last 40 hours.
    """
    urls = _serve_pages(monkeypatch, _three_days())

    df = _hourly(["temperature_air_2m"], _stamp("10-12 00:00"), _stamp("10-14 23:00")).sort("timestamp")

    assert df.get_column("timestamp").to_list() == [_stamp("10-12 00:00") + dt.timedelta(hours=h) for h in range(72)]
    # every hour keeps its report, the METAR of :53 of the hour before, whichever page it is on; the first hour has
    # none in the data and keeps a 5-minute row
    assert df.get_column("value").to_list() == pytest.approx([5.0] + [5.3 + ((h - 1) % 24) / 100 for h in range(1, 72)])
    assert len(urls) == 2
    assert "cursor" not in urls[0]
    assert "cursor=" in urls[1]


def test_nws_hourly_names_the_start_of_the_window_to_the_cursor(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the cursor URL is sent the `start` of the window, as it carries no window of its own (GH-2994).

    Alone it walks on past the start to the end of the week the endpoint keeps (KBOS, 3 hours: 34 rows, then a
    cursor that answered 500 rows older than the window).
    """
    urls = _serve_pages(monkeypatch, _three_days())

    _hourly(["temperature_air_2m"], _stamp("10-12 00:00"), _stamp("10-14 23:00"))

    assert parse_qs(urlparse(urls[1]).query)["start"] == ["2026-10-11T23:30:00Z"]


def test_nws_hourly_reads_one_page_of_a_window_that_a_page_holds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a page shorter than the limit is the last one, though it names a next page (GH-2994).

    A window of 3 hours of KBOS held 34 rows and a `next` (read 2026-10-17).
    """
    urls = _serve_pages(monkeypatch, _three_days())

    df = _hourly(["temperature_air_2m"], _stamp("10-14 20:00"), _stamp("10-14 23:00"))

    assert df.height == 4
    assert len(urls) == 1


def test_nws_hourly_stops_at_a_page_that_ends_in_the_window_start(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a full page whose oldest observation is the start of the window is not followed (GH-2994)."""
    observations = _three_days()
    urls = _serve_pages(monkeypatch, observations)
    # 500 observations back from the newest end at this stamp, which the request names as its start less half an hour
    oldest = dt.datetime.fromisoformat(observations[499]["properties"]["timestamp"])

    df = _hourly(["temperature_air_2m"], oldest + _HALF_HOUR, _stamp("10-14 23:00"))

    assert not df.is_empty()
    assert len(urls) == 1


def test_nws_hourly_reads_the_report_of_an_hour_that_two_pages_split(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the observations of the pages are thinned together: an hour has one row, its report (GH-2994).

    The first page ends at the 500th observation, in the middle of an hour whose 5-minute rows are on one page and
    whose METAR is on the other.
    """
    observations = _three_days()
    urls = _serve_pages(monkeypatch, observations)
    boundary = dt.datetime.fromisoformat(observations[499]["properties"]["timestamp"])

    df = _hourly(["temperature_air_2m"], _stamp("10-12 00:00"), _stamp("10-14 23:00"))

    assert len(urls) == 2
    hour = (boundary + _HALF_HOUR).replace(minute=0, second=0, microsecond=0)
    assert df.filter(pl.col("timestamp") == hour).height == 1
    assert df.height == df.get_column("timestamp").n_unique()
    assert all(value != round(value) for value in df.sort("timestamp").get_column("value").to_list()[1:])


def test_nws_hourly_without_dates_reads_the_pages_to_the_end_of_the_week(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a request without dates, which the Python API allows, is not cut at 500 observations (GH-2994)."""
    urls = _serve_pages(monkeypatch, _three_days())
    request = NwsObservationRequest(
        parameters=[("hourly", "data", "temperature_air_2m")],
        settings=Settings(cache_disable=True),
    )

    df = NwsObservationValues(sr=stations_result(request, "hourly", "data", "KDEN")).all().df

    # the 72 hours and 00:00 of the day after, the hour of the METAR of 23:53
    assert df.height == 73
    assert len(urls) == 2
    assert "start" not in urls[1]


def test_nws_hourly_does_not_follow_a_cursor_that_repeats(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that an endpoint that answers a page with its own address ends the walk instead of looping (GH-2994)."""
    urls: list[str] = []
    page = _three_days()[:500]
    own = "https://api.weather.gov/stations/KDEN/observations?cursor=eyJzIjoiMjAyNi0xMC0xMlQxMjo1NDowMCswMDowMCJ9"

    def download_file(*args: str, url: str | None = None, **_: object) -> File:
        urls.append(url or args[0])
        body = json.dumps({"features": page, "pagination": {"next": own}})
        return File(url=urls[-1], content=BytesIO(body.encode()), status=200)

    monkeypatch.setattr(nws_api, "download_file", download_file)
    _hourly(["temperature_air_2m"], _stamp("10-12 00:00"), _stamp("10-14 23:00"))

    assert len(urls) == 2


@pytest.mark.parametrize(
    "foreign",
    [
        "http://192.0.2.1/latest/meta-data/iam",
        "https://forecast.weather.gov/x",
        "https://api.weather.gov.example.org/x",
    ],
)
def test_nws_hourly_does_not_follow_a_cursor_to_another_host(monkeypatch: pytest.MonkeyPatch, foreign: str) -> None:
    """Test that `pagination.next` is followed at the hosts of NWS and no other, a sibling name included (GH-3339)."""
    urls: list[str] = []

    def download_file(*args: str, url: str | None = None, **_: object) -> File:
        urls.append(url or args[0])
        rows = sorted(_three_days(), key=lambda o: o["properties"]["timestamp"], reverse=True)[:500]
        body = {"features": rows, "pagination": {"next": foreign}}
        return File(url=urls[-1], content=BytesIO(json.dumps(body).encode()), status=200)

    monkeypatch.setattr(nws_api, "download_file", download_file)

    with pytest.raises(DownloadError, match="the link was not fetched"):
        _hourly(["temperature_air_2m"], _stamp("10-12 00:00"), _stamp("10-14 23:00"))

    assert len(urls) == 1
