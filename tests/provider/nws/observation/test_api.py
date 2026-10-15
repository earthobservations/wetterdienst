# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for NWS (United States) observation provider."""

import datetime as dt
import json
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from tests.provider.value_stubs import serve, stations_result
from wetterdienst import Options, Settings, __version__
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.provider.nws.observation import NwsObservationRequest
from wetterdienst.provider.nws.observation import api as nws_api
from wetterdienst.provider.nws.observation.api import NwsObservationValues

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
            stations=request,
            df=pl.DataFrame(),
            df_all=pl.DataFrame(),
            stations_filter=StationsFilter.ALL,
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
    megabyte, however little of it the request wanted.
    """
    url = _values(_request())._build_url(DENVER)  # noqa: SLF001

    assert url.startswith(f"https://api.weather.gov/stations/{DENVER}/observations?")
    assert "start=2026-08-20T00%3A00%3A00Z" in url
    assert "end=2026-08-21T00%3A00%3A00Z" in url


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
    is not what the endpoint, which reads `Z`, must be sent.
    """
    request = NwsObservationRequest(parameters=[("hourly", "data", "temperature_air_2m")], start=start, end=end)

    url = _values(request)._build_url(DENVER)  # noqa: SLF001

    assert "start=2026-08-20T00%3A00%3A00Z" in url
    assert "end=2026-08-21T00%3A00%3A00Z" in url


def test_nws_url_names_no_window_where_the_request_carries_no_dates() -> None:
    """Test that a request without dates asks for the endpoint's own default.

    `date_required` is enforced at the CLI and the REST API but not in the Python API, so a
    request can reach the endpoint with nothing to narrow it to.
    """
    request = NwsObservationRequest(parameters=[("hourly", "data", "temperature_air_2m")])

    url = _values(request)._build_url(DENVER)  # noqa: SLF001

    assert url == f"https://api.weather.gov/stations/{DENVER}/observations"


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

    df = request.filter_by_station_id([DENVER]).values.all().df

    assert not df.is_empty()
    assert df.get_column("station_id").unique().to_list() == [DENVER]
    assert df.get_column("timestamp").min() >= start_date
    assert df.get_column("timestamp").max() <= end_date
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
        parameters=[("hourly", "data", "wind_direction"), ("hourly", "data", "wind_speed")],
        start=dt.datetime(2026, 10, 12, tzinfo=UTC),
        end=dt.datetime(2026, 10, 13, tzinfo=UTC),
        settings=Settings(cache_disable=True),
        options=Options(drop_nulls=False),
    )
    sr = stations_result(request, "hourly", "data", "KBOS")
    df = NwsObservationValues(sr=sr).all().df
    direction = df.filter(pl.col("parameter") == "wind_direction").sort("timestamp")
    assert direction.select("value", "quality_flags").rows() == [(360.0, "V"), (None, "V,raw:0"), (None, "Z")]
    wind_speed = df.filter(pl.col("parameter") == "wind_speed").sort("timestamp")
    # a speed of 0 is a reading, and 9.36 km/h arrives as 2.6 m/s
    assert wind_speed.select("value", "quality_flags").rows() == [(2.6, "V"), (0.0, "V"), (2.6, "V")]


def test_nws_values_keep_the_fractions_of_the_quantities_that_carry_them(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a fraction is no longer truncated on the read: 0.8 mm stays 0.8 and 28.4 mm stays 28.4 (GH-2849).

    The observation JSON was read with an integer schema for the gust, the pressures, the visibility, the 24-hour
    extremes and the precipitation, and polars truncates when it reads a float as an integer: 0.8 mm of rain read as
    0, 1.8 as 1, 4.8 as 4 and 28.4 as 28. The readings are those of api.weather.gov/stations/{id}/observations
    (read 2026-10-13, KBOS, KDEN, KSEA, KMIA and KORD, 500 observations each): precipitation 0.8 (1 h), 1.3 (3 h)
    and 28.4 (6 h), the gust 35.172 km/h, the pressure 101760.98 Pa and the visibility 16093.44 m. The 24-hour
    extremes were null in all of those 2500 observations (and in those of 35 more stations), so their fractions are
    the tenths of a degree a METAR 24-hour group writes, not a reading seen on the endpoint. The direction is read as
    a float too: 2406 of 2406 readings are whole degrees, which the endpoint (a number) does not promise.
    """

    def quantity(unit_code: str, value: float) -> dict[str, object]:
        return {"unitCode": unit_code, "value": value, "qualityControl": "V"}

    readings = {
        "windDirection": quantity("wmoUnit:degree_(angle)", 60),
        "windGust": quantity("wmoUnit:km_h-1", 35.172),
        "barometricPressure": quantity("wmoUnit:Pa", 101760.98),
        "seaLevelPressure": quantity("wmoUnit:Pa", 101760.5),
        "visibility": quantity("wmoUnit:m", 16093.44),
        "maxTemperatureLast24Hours": quantity("wmoUnit:degC", 21.7),
        "minTemperatureLast24Hours": quantity("wmoUnit:degC", 12.2),
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
    assert values["wind_direction"] == 60.0
    # the gust arrives in km/h and is returned in m/s, the pressures arrive in Pa and are returned in hPa
    assert values["wind_gust_max"] == pytest.approx(35.172 / 3.6)
    assert values["pressure_air_site"] == pytest.approx(1017.6098)
    assert values["pressure_air_sea_level"] == pytest.approx(1017.605)
    assert values["visibility"] == pytest.approx(16093.44)
    assert values["temperature_air_max_2m_last_24h"] == pytest.approx(21.7)
    assert values["temperature_air_min_2m_last_24h"] == pytest.approx(12.2)
    assert values["precipitation_amount"] == pytest.approx(0.8)
    assert values["precipitation_amount_last_3h"] == pytest.approx(1.3)
    assert values["precipitation_amount_last_6h"] == pytest.approx(28.4)
