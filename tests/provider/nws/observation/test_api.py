# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for NWS (United States) observation provider."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst import Settings, __version__
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.provider.nws.observation import NwsObservationRequest
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


def _request(settings: Settings | None = None, **kwargs: object) -> NwsObservationRequest:
    """Build a request over a two-day window, which is what the endpoint is asked for."""
    return NwsObservationRequest(
        parameters=[("hourly", "data", "temperature_air_mean_2m")],
        start_date=dt.datetime(2026, 8, 20, tzinfo=UTC),
        end_date=dt.datetime(2026, 8, 21, tzinfo=UTC),
        settings=settings or Settings(),
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


def test_nws_url_names_no_window_where_the_request_carries_no_dates() -> None:
    """Test that a request without dates asks for the endpoint's own default.

    `date_required` is enforced at the CLI and the REST API but not in the Python API, so a
    request can reach the endpoint with nothing to narrow it to.
    """
    request = NwsObservationRequest(parameters=[("hourly", "data", "temperature_air_mean_2m")])

    url = _values(request)._build_url(DENVER)  # noqa: SLF001

    assert url == f"https://api.weather.gov/stations/{DENVER}/observations"


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
def test_nws_stations_report_no_height_where_the_source_reports_none() -> None:
    """Test that a missing elevation reads as null rather than as 9999 m.

    MADIS writes a missing elevation as 9999, which was cast to a float and passed on unread --
    and height is what interpolation weighs a neighbouring station by.
    """
    heights = _request().all().df.get_column("height")

    assert heights.is_null().sum() > 0
    assert heights.drop_nulls().max() < 9999


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
        parameters=[("hourly", "data", "temperature_air_mean_2m")],
        start_date=start_date,
        end_date=end_date,
    )

    df = request.filter_by_station_id([DENVER]).values.all().df

    assert not df.is_empty()
    assert df.get_column("station_id").unique().to_list() == [DENVER]
    assert df.get_column("date").min() >= start_date
    assert df.get_column("date").max() <= end_date
    # degree_celsius, as the endpoint's own unitCode says -- Denver is not outside these
    values = df.get_column("value").drop_nulls()
    assert values.min() > -50
    assert values.max() < 50
