# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD observation data API."""

import datetime as dt
import inspect
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst import Period, Settings
from wetterdienst.exceptions import StartDateEndDateError
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.provider.dwd.observation import (
    DwdObservationMetadata,
    DwdObservationRequest,
)
from wetterdienst.provider.metno.frost import MetnoFrostRequest


@pytest.fixture
def expected_stations_df() -> pl.DataFrame:
    """Provide expected stations DataFrame."""
    return pl.DataFrame(
        [
            {
                "resolution": "hourly",
                "dataset": "temperature_air",
                "station_id": "02480",
                "start_date": dt.datetime(2004, 9, 1, tzinfo=ZoneInfo("UTC")),
                "latitude": 50.0643,
                "longitude": 8.993,
                "elevation": 108.0,
                "name": "Kahl/Main",
                "region": "Bayern",
                "distance": 9.759384982994229,
            },
            {
                "resolution": "hourly",
                "dataset": "temperature_air",
                "station_id": "04411",
                "start_date": dt.datetime(2002, 1, 24, tzinfo=ZoneInfo("UTC")),
                "latitude": 49.9195,
                "longitude": 8.9672,
                "elevation": 155.0,
                "name": "Schaafheim-Schlierbach",
                "region": "Hessen",
                "distance": 10.160326,
            },
            {
                "resolution": "hourly",
                "dataset": "temperature_air",
                "station_id": "07341",
                "start_date": dt.datetime(2005, 7, 16, tzinfo=ZoneInfo("UTC")),
                "latitude": 50.0900,
                "longitude": 8.7862,
                "elevation": 119.0,
                "name": "Offenbach-Wetterpark",
                "region": "Hessen",
                "distance": 12.891318342515483,
            },
        ],
        schema={
            "resolution": pl.String,
            "dataset": pl.String,
            "station_id": pl.String,
            "start_date": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "elevation": pl.Float64,
            "name": pl.String,
            "region": pl.String,
            "distance": pl.Float64,
        },
        orient="row",
    )


@pytest.fixture
def default_request(default_settings: Settings) -> TimeseriesRequest:
    """Provide default request."""
    return DwdObservationRequest(
        parameters=[("hourly", "temperature_air")],
        periods="historical",
        start=dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(2020, 1, 20, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )


def test_dwd_observation_data_api_singe_parameter(default_settings: Settings) -> None:
    """Test parameters given as parameter - dataset pair."""
    request = DwdObservationRequest(
        parameters=[("daily", "kl", "precipitation_amount")],
        periods={"recent", "historical"},
        settings=default_settings,
    )

    assert request == DwdObservationRequest(
        parameters=[DwdObservationMetadata.daily.kl.precipitation_amount],
        periods={Period.HISTORICAL, Period.RECENT},
        start=None,
        end=None,
    )


def test_dwd_observation_data_whole_dataset(default_settings: Settings) -> None:
    """Test parameters given as parameter - dataset pair."""
    given = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        settings=default_settings,
    )
    assert given.parameters == [
        DwdObservationMetadata.daily.climate_summary.wind_gust_max,
        DwdObservationMetadata.daily.climate_summary.wind_speed,
        DwdObservationMetadata.daily.climate_summary.precipitation_amount,
        DwdObservationMetadata.daily.climate_summary.precipitation_form,
        DwdObservationMetadata.daily.climate_summary.sunshine_duration,
        DwdObservationMetadata.daily.climate_summary.snow_depth,
        DwdObservationMetadata.daily.climate_summary.cloud_cover_total,
        DwdObservationMetadata.daily.climate_summary.pressure_vapor,
        DwdObservationMetadata.daily.climate_summary.pressure_air_site,
        DwdObservationMetadata.daily.climate_summary.temperature_air_mean_2m,
        DwdObservationMetadata.daily.climate_summary.humidity_relative,
        DwdObservationMetadata.daily.climate_summary.temperature_air_max_2m,
        DwdObservationMetadata.daily.climate_summary.temperature_air_min_2m,
        DwdObservationMetadata.daily.climate_summary.temperature_air_min_0_05m,
    ]


@pytest.mark.remote
def test_dwd_observation_wrong_start_date_end_date(default_settings: Settings) -> None:
    """Test for wrong start and end date."""
    with pytest.raises(StartDateEndDateError):
        DwdObservationRequest(
            parameters=[("daily", "kl", "precipitation_amount")],
            start="1971-01-01",
            end="1951-01-01",
            settings=default_settings,
        )


def test_dwd_observation_data_dates(default_settings: Settings) -> None:
    """Test for dates."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start="1971-01-01",
        settings=default_settings,
    )
    assert request.start == dt.datetime(1971, 1, 1, tzinfo=ZoneInfo("UTC"))
    assert request.end == dt.datetime(1971, 1, 1, tzinfo=ZoneInfo("UTC"))
    assert request.periods == {Period.HISTORICAL}


@pytest.mark.remote
def test_dwd_observations_stations_filter_empty(default_request: TimeseriesRequest) -> None:
    """Test for empty station filters."""
    request = default_request.filter_by_station_id(station_id=("FizzBuzz",))
    assert request.df.is_empty()


@pytest.mark.remote
def test_dwd_observations_stations_filter_name_empty(default_request: TimeseriesRequest) -> None:
    """Test for empty station filters."""
    request = default_request.filter_by_name(name="FizzBuzz")
    assert request.df.is_empty()


def test_dwd_observations_stations_wrong_types(default_request: TimeseriesRequest) -> None:
    """Test for wrong types."""
    # `filter_by_station_id` took no part here: the call this used to make passed a keyword that
    # method does not have, so the `TypeError` was Python binding the arguments. It validates no
    # types of its own -- an int, a float and an object all go through -- so there is nothing of
    # its own to assert
    with pytest.raises(TypeError):
        default_request.filter_by_name(name=123)

    # `None` reached rapidfuzz, which answered it with no matches rather than a `TypeError`, so an
    # empty result came back for what is a caller's mistake rather than a name nothing is called
    with pytest.raises(TypeError):
        default_request.filter_by_name(name=None)


@pytest.mark.remote
def test_dwd_observation_stations_filter_by_rank_single(
    default_request: TimeseriesRequest,
    expected_stations_df: pl.DataFrame,
) -> None:
    """Test for one nearest station."""
    request = default_request.filter_by_rank(
        latlon=(50.0, 8.9),
        rank=1,
    )
    given_df = request.df.drop("end_date")
    assert_frame_equal(given_df[0, :], expected_stations_df[0, :])
    values = request.values.all()
    assert_frame_equal(values.df_stations.head(1).drop("end_date"), expected_stations_df.head(1))


@pytest.mark.remote
def test_dwd_observation_stations_filter_by_rank_multiple(
    default_request: TimeseriesRequest,
    expected_stations_df: pl.DataFrame,
) -> None:
    """Test for multiple nearest stations."""
    request = default_request.filter_by_rank(
        latlon=(50.0, 8.9),
        rank=3,
    )
    given_df = request.df.drop("end_date")
    assert_frame_equal(
        given_df.head(3),
        expected_stations_df,
    )
    values = request.values.all()
    assert_frame_equal(values.df_stations.drop("end_date"), expected_stations_df)


@pytest.mark.remote
def test_dwd_observation_stations_nearby_distance(
    default_request: TimeseriesRequest,
    expected_stations_df: pl.DataFrame,
) -> None:
    """Test for distance filter."""
    # Kilometers
    nearby_station = default_request.filter_by_distance(latlon=(50.0, 8.9), distance=16.13, unit="km")
    nearby_station = nearby_station.df.drop("end_date")
    assert_frame_equal(nearby_station, expected_stations_df)
    # Miles
    nearby_station = default_request.filter_by_distance(latlon=(50.0, 8.9), distance=10.03, unit="mi")
    nearby_station = nearby_station.df.drop("end_date")
    assert_frame_equal(nearby_station, expected_stations_df)


@pytest.mark.remote
def test_dwd_observation_stations_bbox(default_request: TimeseriesRequest, expected_stations_df: pl.DataFrame) -> None:
    """Test for bounding box filter."""
    nearby_station = default_request.filter_by_bbox(left=8.7862, bottom=49.9195, right=8.993, top=50.0900)
    nearby_station = nearby_station.df.drop("end_date")
    assert_frame_equal(nearby_station, expected_stations_df.drop("distance"))


@pytest.mark.remote
def test_dwd_observation_stations_bbox_empty(default_request: TimeseriesRequest) -> None:
    """Test for empty station filters."""
    # Bbox
    assert default_request.filter_by_bbox(
        left=-100,
        bottom=-20,
        right=-90,
        top=-10,
    ).df.is_empty()


@pytest.mark.remote
def test_dwd_observation_stations_fail(default_request: TimeseriesRequest) -> None:
    """Test for failing station filters."""
    # Number
    with pytest.raises(ValueError, match=r"'rank' has to be at least 1\."):
        default_request.filter_by_rank(
            latlon=(51.4, 9.3),
            rank=0,
        )
    # Distance
    with pytest.raises(ValueError, match="'distance' has to be at least 0"):
        default_request.filter_by_distance(
            latlon=(51.4, 9.3),
            distance=-1,
        )
    # Bbox
    with pytest.raises(ValueError, match="bbox left border should be smaller then right"):
        default_request.filter_by_bbox(left=10, bottom=10, right=5, top=5)


@pytest.mark.remote
def test_dwd_observation_multiple_datasets(default_settings: Settings) -> None:
    """Test for multiple parameters."""
    request = DwdObservationRequest(
        parameters=[("daily", "kl", "temperature_air_mean_2m"), ("hourly", "precipitation", "precipitation_amount")],
        settings=default_settings,
        start=dt.datetime(1900, 1, 1, tzinfo=ZoneInfo("UTC")),
        end=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
    ).filter_by_station_id(("02315", "01050", "19140"))
    assert request.parameters == [
        DwdObservationMetadata.daily.kl.temperature_air_mean_2m,
        DwdObservationMetadata.hourly.precipitation.precipitation_amount,
    ]
    df_stations = request.df
    assert df_stations.get_column("resolution").unique(maintain_order=True).sort().to_list() == ["daily", "hourly"]
    assert df_stations.get_column("dataset").unique(maintain_order=True).sort().to_list() == [
        "climate_summary",
        "precipitation",
    ]
    # station in climate_summary
    assert df_stations.filter(pl.col("station_id") == "02315").select(pl.all().exclude("end_date")).to_dicts()[0] == {
        "resolution": "daily",
        "dataset": "climate_summary",
        "station_id": "02315",
        "start_date": dt.datetime(2000, 6, 1, tzinfo=ZoneInfo("UTC")),
        "latitude": 51.7657,
        "longitude": 13.1666,
        "elevation": 78.0,
        "name": "Holzdorf-Bernsdorf",
        "region": "Brandenburg",
    }
    # station in climate_summary and temperature_air
    assert df_stations.filter(pl.col("station_id") == "01050").sort(["resolution"]).select(
        pl.all().exclude("end_date"),
    ).to_dicts() == [
        {
            "resolution": "daily",
            "dataset": "climate_summary",
            "station_id": "01050",
            "start_date": dt.datetime(1949, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
            "latitude": 51.0221,
            "longitude": 13.847,
            "elevation": 112.0,
            "name": "Dresden-Hosterwitz",
            "region": "Sachsen",
        },
        {
            "resolution": "hourly",
            "dataset": "precipitation",
            "station_id": "01050",
            "start_date": dt.datetime(2006, 4, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
            "latitude": 51.0221,
            "longitude": 13.847,
            "elevation": 112.0,
            "name": "Dresden-Hosterwitz",
            "region": "Sachsen",
        },
    ]
    # station in temperature_air
    assert df_stations.filter(pl.col("station_id") == "19140").select(pl.all().exclude("end_date")).to_dicts() == [
        {
            "resolution": "hourly",
            "dataset": "precipitation",
            "station_id": "19140",
            "start_date": dt.datetime(2020, 11, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
            "latitude": 50.9657,
            "longitude": 10.6988,
            "elevation": 278.0,
            "name": "Gotha",
            "region": "Thüringen",
        },
    ]
    df_values = request.values.all().df
    assert df_values.get_column("resolution").unique().sort().to_list() == ["daily", "hourly"]
    assert df_values.get_column("dataset").unique().sort().to_list() == [
        "climate_summary",
        "precipitation",
    ]
    assert df_values.get_column("parameter").unique().sort().to_list() == [
        "precipitation_amount",
        "temperature_air_mean_2m",
    ]
    # station in climate_summary
    df_stats = (
        df_values.group_by(["resolution", "dataset", "station_id"], maintain_order=True)
        .len(name="count")
        .sort(["resolution", "dataset", "station_id"])
    )
    assert df_stats.to_dicts() == [
        {"count": 25871, "dataset": "climate_summary", "resolution": "daily", "station_id": "01050"},
        {"count": 8610, "dataset": "climate_summary", "resolution": "daily", "station_id": "02315"},
        {"count": 151743, "dataset": "precipitation", "resolution": "hourly", "station_id": "01050"},
        {"count": 27568, "dataset": "precipitation", "resolution": "hourly", "station_id": "19140"},
    ]


def test_periods_default_to_what_the_requested_datasets_publish(default_settings: Settings) -> None:
    """Without a period the request reads every period the requested datasets publish.

    Not every period the *provider* publishes: `monthly/climate_correction_factor` is released
    under `recent` only, so a request for it must not go looking for a historical release too.
    """
    from wetterdienst.provider.dwd.derived import DwdDerivedRequest  # noqa: PLC0415

    request = DwdDerivedRequest(parameters=["monthly/climate_correction_factor"], settings=default_settings)
    assert request.periods == {Period.RECENT}
    request = DwdDerivedRequest(parameters=["monthly/soil"], settings=default_settings)
    assert request.periods == {Period.HISTORICAL, Period.RECENT}


def test_periods_unpublished_period_raises(default_settings: Settings) -> None:
    """A period none of the requested datasets publishes fails, naming what is available.

    It used to be dropped by an intersection whose empty result then read as "nothing requested",
    so asking for a period that does not exist quietly returned *every* period instead.
    """
    from wetterdienst.exceptions import NoPeriodsFoundError  # noqa: PLC0415

    with pytest.raises(NoPeriodsFoundError, match="None of the periods future is published"):
        DwdObservationRequest(parameters=["daily/kl"], periods="future", settings=default_settings)


def test_periods_partly_unpublished_period_warns(default_settings: Settings, caplog) -> None:  # noqa: ANN001
    """A period the requested datasets do not publish is skipped with a warning, not silently."""
    request = DwdObservationRequest(
        parameters=["daily/kl"],
        periods=["recent", "now"],
        settings=default_settings,
    )
    assert request.periods == {Period.RECENT}
    assert "Periods now are not published" in caplog.text


def test_periods_on_a_request_without_a_choice(default_settings: Settings) -> None:
    """Every request takes periods, including the providers that publish under a single one.

    `NoaaGhcnRequest` has no period to choose between, but used to raise `TypeError: unexpected
    keyword argument 'periods'` rather than accept the one it does publish -- which meant the CLI
    and REST API dropped `periods` for such a provider instead of answering it.
    """
    from wetterdienst.exceptions import NoPeriodsFoundError  # noqa: PLC0415
    from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest  # noqa: PLC0415

    request = NoaaGhcnRequest(parameters=["daily/data"], periods="historical", settings=default_settings)
    assert request.periods == {Period.HISTORICAL}
    with pytest.raises(NoPeriodsFoundError, match="Available periods: historical"):
        NoaaGhcnRequest(parameters=["daily/data"], periods="now", settings=default_settings)


def test_available_periods_reads_the_metadata() -> None:
    """`available_periods` is derived from the metadata, not a hand-maintained class attribute."""
    assert DwdObservationRequest.available_periods() == {Period.HISTORICAL, Period.RECENT, Period.NOW}
    assert DwdObservationRequest.available_periods() == {
        period for resolution in DwdObservationMetadata for dataset in resolution for period in dataset.periods
    }


def test_periods_derived_from_dates_stay_within_what_is_published(default_settings: Settings) -> None:
    """Periods derived from the dates are checked against the datasets like requested ones are.

    An interval reaching into today derives `now`, which `daily/kl` has no release for. The derived
    set was returned unchecked, so the request read no station index at all and reported no stations
    -- while asking for `periods="now"` outright raises for the very same datasets. Where the
    interval reaches past the newest release a dataset has, that release answers for it.
    """
    now = dt.datetime.now(tz=ZoneInfo("UTC"))
    request = DwdObservationRequest(
        parameters=["daily/kl"],
        start=now,
        end=now,
        settings=default_settings,
    )
    assert request.periods == {Period.RECENT}


def test_periods_on_a_provider_that_does_not_read_them_warns(default_settings: Settings, caplog) -> None:  # noqa: ANN001
    """Narrowing the periods of a provider that cannot narrow what it reads says so.

    SMHI publishes `hourly/data` under both historical and recent but reads both of its upstream
    files by design, so the argument is validated and then makes no difference. Accepting it in
    silence would answer a narrowed request with everything.
    """
    from wetterdienst.provider.smhi.observation import SmhiObservationRequest  # noqa: PLC0415

    request = SmhiObservationRequest(parameters=["hourly/data"], periods="historical", settings=default_settings)
    assert request.periods == {Period.HISTORICAL}
    assert "does not read its data per period" in caplog.text
    caplog.clear()
    # the three that do read them stay quiet
    DwdObservationRequest(parameters=["daily/kl"], periods="recent", settings=default_settings)
    assert "does not read its data per period" not in caplog.text


@pytest.mark.parametrize("hourly_first", [True, False])
def test_position_by_station_id_takes_an_elevation_any_resolution_knows(
    monkeypatch: pytest.MonkeyPatch,
    *,
    hourly_first: bool,
) -> None:
    """A station listed once per requested resolution answers with an elevation any of its rows knows.

    NOAA GHCN's hourly list gives no elevation for Discovery Island, CAN01012475, where its daily list
    gives 18.9 m, and the station list follows the order the parameters were named in. Reading the
    first row alone left `interpolate_by_station_id` without the station's elevation whenever hourly
    was named first. The station lists are stubbed, so nothing leaves the machine.
    """
    from types import SimpleNamespace  # noqa: PLC0415

    from wetterdienst.exceptions import StationNotFoundError  # noqa: PLC0415
    from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest  # noqa: PLC0415

    rows = {
        "hourly": {"latitude": 48.425, "longitude": -123.226, "elevation": None},
        "daily": {"latitude": 48.4246, "longitude": -123.2257, "elevation": 18.9},
    }
    order = ["hourly", "daily"] if hourly_first else ["daily", "hourly"]
    stations = pl.DataFrame(
        [{"resolution": resolution, "station_id": "CAN01012475", **rows[resolution]} for resolution in order],
        schema={
            "resolution": pl.String,
            "station_id": pl.String,
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "elevation": pl.Float64,
        },
        orient="row",
    )
    request = NoaaGhcnRequest(parameters=[(resolution, "data", "temperature_air_mean_2m") for resolution in order])
    monkeypatch.setattr(NoaaGhcnRequest, "all", lambda _self: SimpleNamespace(df=stations))
    latitude, longitude, elevation = request._get_position_by_station_id("CAN01012475")  # noqa: SLF001
    assert elevation == 18.9
    # the coordinates are the first row's, as they were: both lists give them
    assert (latitude, longitude) == (rows[order[0]]["latitude"], rows[order[0]]["longitude"])
    with pytest.raises(StationNotFoundError, match="no station found for CAN00000000"):
        request._get_position_by_station_id("CAN00000000")  # noqa: SLF001


@pytest.mark.parametrize(("old", "new"), [("start_date", "start"), ("end_date", "end")])
@pytest.mark.parametrize("request_class", [TimeseriesRequest, DwdObservationRequest])
def test_request_refuses_a_renamed_argument_by_its_new_name(
    request_class: type[TimeseriesRequest],
    old: str,
    new: str,
) -> None:
    """Test the old window argument names the new one, on the base request and on a provider's (GH-2437).

    The base class has no metadata and fails in __post_init__, so its refusal shows that the check
    runs before the dataclass __init__, not in a provider.
    """
    with pytest.raises(TypeError, match=rf"^{request_class.__name__}\(\) argument '{old}' was renamed to '{new}'$"):
        request_class(parameters=[("daily", "kl")], **{old: "2020-01-01"})


def test_request_refuses_both_renamed_arguments_at_once() -> None:
    """Test a caller passing the old pair learns of both renames from the one error (GH-2437)."""
    with pytest.raises(
        TypeError,
        match=r"^DwdObservationRequest\(\) arguments 'start_date' was renamed to 'start', "
        r"'end_date' was renamed to 'end'$",
    ):
        DwdObservationRequest(parameters=[("daily", "kl")], start_date="2020-01-01", end_date="2020-01-02")


@pytest.mark.parametrize("request_class", [TimeseriesRequest, MetnoFrostRequest, DwdObservationRequest])
def test_request_signature_names_the_window_arguments(request_class: type[TimeseriesRequest]) -> None:
    """Test help() and IPython still see a request's arguments behind the refusing __new__ (GH-2437).

    MetnoFrostRequest is no dataclass of its own, so it inherits both __new__ and __init__.
    """
    parameters = inspect.signature(request_class).parameters
    assert list(parameters)[:3] == ["parameters", "start", "end"]


def test_request_keeps_the_window_under_its_new_names() -> None:
    """Test start and end are taken by the request and read back from its stations result (GH-2437)."""
    from wetterdienst.model.result import StationsFilter, StationsResult  # noqa: PLC0415

    request = DwdObservationRequest(parameters=[("daily", "kl")], start="2020-01-01", end="2020-01-02T12:00")
    assert request.start == dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))
    assert request.end == dt.datetime(2020, 1, 2, 12, tzinfo=ZoneInfo("UTC"))
    stations = StationsResult(
        stations=request,
        df=pl.DataFrame(),
        df_all=pl.DataFrame(),
        stations_filter=StationsFilter.ALL,
    )
    assert (stations.start, stations.end) == (request.start, request.end)
