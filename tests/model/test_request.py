# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD observation data API."""

import datetime as dt
import inspect
from zoneinfo import ZoneInfo

import polars as pl
import portion
import pytest
from polars.testing import assert_frame_equal

from wetterdienst import Period, Resolution, Settings, Wetterdienst
from wetterdienst.exceptions import (
    ApiNotFoundError,
    InvalidEnumerationError,
    InvalidParameterError,
    MetadataNotFoundError,
    NoParametersFoundError,
    ReversedTimeIntervalError,
    StartDateEndDateError,
)
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
                "start_timestamp": dt.datetime(2004, 9, 1, tzinfo=ZoneInfo("UTC")),
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
                "start_timestamp": dt.datetime(2002, 1, 24, tzinfo=ZoneInfo("UTC")),
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
                "start_timestamp": dt.datetime(2005, 7, 16, tzinfo=ZoneInfo("UTC")),
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
            "start_timestamp": pl.Datetime(time_zone="UTC"),
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
    given_df = request.df.drop("end_timestamp")
    assert_frame_equal(given_df[0, :], expected_stations_df[0, :])
    values = request.values.all()
    assert_frame_equal(values.df_stations.head(1).drop("end_timestamp"), expected_stations_df.head(1))


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
    given_df = request.df.drop("end_timestamp")
    assert_frame_equal(
        given_df.head(3),
        expected_stations_df,
    )
    values = request.values.all()
    assert_frame_equal(values.df_stations.drop("end_timestamp"), expected_stations_df)


@pytest.mark.remote
def test_dwd_observation_stations_nearby_distance(
    default_request: TimeseriesRequest,
    expected_stations_df: pl.DataFrame,
) -> None:
    """Test for distance filter."""
    # Kilometers
    nearby_station = default_request.filter_by_distance(latlon=(50.0, 8.9), distance=16.13, unit="km")
    nearby_station = nearby_station.df.drop("end_timestamp")
    assert_frame_equal(nearby_station, expected_stations_df)
    # Miles
    nearby_station = default_request.filter_by_distance(latlon=(50.0, 8.9), distance=10.03, unit="mi")
    nearby_station = nearby_station.df.drop("end_timestamp")
    assert_frame_equal(nearby_station, expected_stations_df)


@pytest.mark.remote
def test_dwd_observation_stations_bbox(default_request: TimeseriesRequest, expected_stations_df: pl.DataFrame) -> None:
    """Test for bounding box filter."""
    nearby_station = default_request.filter_by_bbox(left=8.7862, bottom=49.9195, right=8.993, top=50.0900)
    nearby_station = nearby_station.df.drop("end_timestamp")
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
    assert df_stations.filter(pl.col("station_id") == "02315").select(pl.all().exclude("end_timestamp")).to_dicts()[
        0
    ] == {
        "resolution": "daily",
        "dataset": "climate_summary",
        "station_id": "02315",
        "start_timestamp": dt.datetime(2000, 6, 1, tzinfo=ZoneInfo("UTC")),
        "latitude": 51.7657,
        "longitude": 13.1666,
        "elevation": 78.0,
        "name": "Holzdorf-Bernsdorf",
        "region": "Brandenburg",
    }
    # station in climate_summary and temperature_air
    assert df_stations.filter(pl.col("station_id") == "01050").sort(["resolution"]).select(
        pl.all().exclude("end_timestamp"),
    ).to_dicts() == [
        {
            "resolution": "daily",
            "dataset": "climate_summary",
            "station_id": "01050",
            "start_timestamp": dt.datetime(1949, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
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
            "start_timestamp": dt.datetime(2006, 4, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
            "latitude": 51.0221,
            "longitude": 13.847,
            "elevation": 112.0,
            "name": "Dresden-Hosterwitz",
            "region": "Sachsen",
        },
    ]
    # station in temperature_air
    assert df_stations.filter(pl.col("station_id") == "19140").select(pl.all().exclude("end_timestamp")).to_dicts() == [
        {
            "resolution": "hourly",
            "dataset": "precipitation",
            "station_id": "19140",
            "start_timestamp": dt.datetime(2020, 11, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
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
    parameter_of = {"hourly": "temperature_air_2m", "daily": "temperature_air_mean_2m"}
    request = NoaaGhcnRequest(parameters=[(resolution, "data", parameter_of[resolution]) for resolution in order])
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
        match=r"^DwdObservationRequest\(\) arguments 'start_date' and 'end_date' were renamed to 'start' and 'end'$",
    ):
        DwdObservationRequest(parameters=[("daily", "kl")], start_date="2020-01-01", end_date="2020-01-02")


@pytest.mark.parametrize("request_class", [TimeseriesRequest, MetnoFrostRequest, DwdObservationRequest])
def test_request_signature_names_the_window_arguments(request_class: type[TimeseriesRequest]) -> None:
    """Test help() and IPython still see a request's arguments behind the refusing __new__ (GH-2437).

    MetnoFrostRequest is no dataclass of its own, so it inherits both __new__ and __init__.
    """
    parameters = inspect.signature(request_class).parameters
    assert list(parameters)[:3] == ["parameters", "start", "end"]


def test_request_keeps_the_window_under_its_new_names(default_settings: Settings) -> None:
    """Test start and end are taken by the request and read back from its stations result (GH-2437)."""
    from wetterdienst.model.result import StationsFilter, StationsResult  # noqa: PLC0415

    request = DwdObservationRequest(
        parameters=[("daily", "kl")], start="2020-01-01", end="2020-01-02T12:00", settings=default_settings
    )
    assert request.start == dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC"))
    assert request.end == dt.datetime(2020, 1, 2, 12, tzinfo=ZoneInfo("UTC"))
    stations = StationsResult(
        stations=request,
        df=pl.DataFrame(),
        df_all=pl.DataFrame(),
        stations_filter=StationsFilter.ALL,
    )
    assert (stations.start, stations.end) == (request.start, request.end)


def test_request_refuses_a_reversed_window_in_its_own_terms() -> None:
    """Test a Python caller still gets the request's wording and the exception it caught before (GH-2478).

    The REST API and the MCP tools word the same refusal in terms of their `timestamp`; they tell it
    apart by the subclass, which stays a `StartDateEndDateError`.
    """
    with pytest.raises(ReversedTimeIntervalError, match="'start' must be smaller or equal to 'end'") as raised:
        TimeseriesRequest.convert_timestamps("2020-06-30", "2020-06-01")
    assert isinstance(raised.value, StartDateEndDateError)
    # no "Error: " of its own: the command line prefixes one to every usage error (GH-2513)
    assert str(raised.value) == "'start' must be smaller or equal to 'end'."


def test_request_refuses_an_unknown_parameter_by_default() -> None:
    """Test that an unknown parameter among valid ones is refused with its close match, not skipped (GH-2636)."""
    with pytest.raises(InvalidParameterError) as raised:
        DwdObservationRequest(parameters=["daily/kl/temperature_air_mean_2m", "daily/klx"])
    message = str(raised.value)
    assert "'klx'. Did you mean 'kl'?" in message
    # the way out is named for the caller who can take it
    assert "on_unknown='warn'" in message


def test_request_on_unknown_warn_goes_on_with_the_parameters_that_resolve(caplog: pytest.LogCaptureFixture) -> None:
    """Test that on_unknown="warn" keeps the old behaviour: a warning, and the rest (GH-2636)."""
    request = DwdObservationRequest(
        parameters=["daily/kl/temperature_air_mean_2m", "daily/foo"],
        on_unknown="warn",
    )
    assert [parameter.name for parameter in request.parameters] == ["temperature_air_mean_2m"]
    assert "daily/foo not found" in caplog.text


def test_request_on_unknown_warn_still_needs_one_parameter() -> None:
    """Test that nothing resolving is an error whichever way unknown parameters are handled (GH-2636)."""
    with pytest.raises(NoParametersFoundError):
        DwdObservationRequest(parameters=["daily/foo"], on_unknown="warn")
    with pytest.raises(InvalidParameterError):
        DwdObservationRequest(parameters=["daily/foo"])


def test_request_refuses_an_on_unknown_it_does_not_know() -> None:
    """Test that a misspelt on_unknown is not taken for the default (GH-2636)."""
    with pytest.raises(InvalidEnumerationError, match="Valid values: raise, warn"):
        DwdObservationRequest(parameters="daily/kl", on_unknown="skip")  # ty: ignore[invalid-argument-type]


def test_request_accepts_the_resolution_as_its_member() -> None:
    """Test that `Resolution`, which the package exports, works in the parameter tuple (GH-2636)."""
    by_member = DwdObservationRequest(parameters=(Resolution.DAILY, "kl"))
    by_name = DwdObservationRequest(parameters=("daily", "kl"))
    assert by_member.parameters == by_name.parameters
    assert by_member.parameters


def test_request_periods_error_lists_the_valid_values() -> None:
    """Test that an unknown period is answered with the periods there are (GH-2636)."""
    with pytest.raises(InvalidEnumerationError) as raised:
        DwdObservationRequest(parameters="daily/kl", periods="foo")
    assert str(raised.value) == "foo could not be parsed from Period. Valid values: historical, recent, now, future"


@pytest.mark.parametrize("bound", [2020, 2020.5, True, dt.date(2020, 1, 1), b"2020-01-01", ["2020-01-01"]])
@pytest.mark.parametrize("argument", ["start", "end"])
def test_request_refuses_a_date_that_is_neither_a_string_nor_a_datetime(argument: str, bound: object) -> None:
    """Test that `start=2020` is a TypeError saying so, not an AttributeError about tzinfo (GH-2636)."""
    with pytest.raises(TypeError, match=rf"{argument} must be a str or a datetime, got {type(bound).__name__}"):
        DwdObservationRequest(parameters="daily/kl", **{argument: bound})  # ty: ignore[invalid-argument-type]
    with pytest.raises(TypeError, match=argument):
        TimeseriesRequest.convert_timestamps(**{"start": None, "end": None, argument: bound})  # ty: ignore[invalid-argument-type]


def test_request_end_alone_is_the_whole_window() -> None:
    """Test that `end` without `start` is one instant, as `start` without `end` is, and as the CLI reads it (GH-2636).

    Refusing it would break `--end` of the command line, which is documented and tested to be a
    single-point date, and the two bounds would no longer be read alike.
    """
    request = DwdObservationRequest(parameters="daily/kl", end="2020-01-05")
    assert request.start == request.end == dt.datetime(2020, 1, 5, tzinfo=ZoneInfo("UTC"))
    assert DwdObservationRequest(parameters="daily/kl", start="2020-01-05").end == request.end


def test_discover_refuses_a_resolution_or_dataset_the_provider_does_not_have() -> None:
    """Test that a name that matches nothing raises, where it answered an empty dict (GH-2636)."""
    with pytest.raises(
        MetadataNotFoundError, match=r"Resolution 'foo' not found in DwdObservationMetadata.*Available resolutions"
    ):
        DwdObservationRequest.discover(resolutions="foo")
    with pytest.raises(
        MetadataNotFoundError, match=r"Dataset 'foo' not found in DwdObservationMetadata.*Available datasets"
    ):
        DwdObservationRequest.discover(datasets="foo")
    # a dataset of another resolution is not found in the one asked for
    with pytest.raises(MetadataNotFoundError, match=r"Dataset 'dew_point' not found.*for resolutions daily"):
        DwdObservationRequest.discover(resolutions="daily", datasets="dew_point")
    # one name that is wrong among others that are right
    with pytest.raises(MetadataNotFoundError, match="Resolution 'foo'"):
        DwdObservationRequest.discover(resolutions=["daily", "foo"])


def test_discover_still_narrows_to_what_is_named() -> None:
    """Test that names that exist, by either name and in either resolution, are answered as before (GH-2636)."""
    assert list(DwdObservationRequest.discover(resolutions="daily", datasets="kl")) == ["daily"]
    assert list(DwdObservationRequest.discover(resolutions=["daily", "hourly"], datasets="kl")) == ["daily"]
    assert list(DwdObservationRequest.discover(resolutions=Resolution.DAILY)) == ["daily"]


def test_get_network_names_raises_what_the_constructor_raises() -> None:
    """Test that an unknown provider is an `ApiNotFoundError` in both, not a bare KeyError in one (GH-2636)."""
    with pytest.raises(ApiNotFoundError, match="No API available for provider foo"):
        Wetterdienst("foo", "bar")
    with pytest.raises(ApiNotFoundError, match=r"No API available for provider foo. Available providers: aemet, "):
        Wetterdienst.get_network_names("foo")
    assert "observation" in Wetterdienst.get_network_names(" DWD ")


def _count_station_index_builds(monkeypatch: pytest.MonkeyPatch) -> list[None]:
    """Stub DWD observation's station index with three stations and record each time it is built.

    `_all` is what reads the station description files and builds the file index upstream, so a
    call to it is a full station index built; nothing leaves the machine.
    """
    built = []
    stations = pl.DataFrame(
        {
            "resolution": ["daily"] * 3,
            "dataset": ["climate_summary"] * 3,
            "station_id": ["01048", "01050", "01051"],
            "start_timestamp": [dt.datetime(1934, 1, 1, tzinfo=ZoneInfo("UTC"))] * 3,
            "end_timestamp": [dt.datetime(2026, 10, 1, tzinfo=ZoneInfo("UTC"))] * 3,
            "latitude": [51.1278, 51.0221, 50.9800],
            "longitude": [13.7543, 13.8470, 13.9500],
            "elevation": [228.0, 119.0, 300.0],
            "name": ["Dresden-Klotzsche", "Dresden-Hosterwitz", "Dresden-Elsewhere"],
            "region": ["Sachsen"] * 3,
        },
    )

    def _all(_self: DwdObservationRequest) -> pl.LazyFrame:
        built.append(None)
        return stations.lazy()

    monkeypatch.setattr(DwdObservationRequest, "_all", _all)
    return built


@pytest.mark.parametrize(
    ("method", "kwargs", "expected"),
    [
        ("filter_by_station_id", {"station_id": "01048"}, ["01048"]),
        ("filter_by_name", {"name": "Dresden-Klotzsche"}, ["01048"]),
        # the rank limits value collection later on, not the stations listed
        ("filter_by_rank", {"latlon": (51.05, 13.74), "rank": 2}, ["01050", "01048", "01051"]),
        # every station in reach, not one: it ranks with filter_by_rank at rank 1
        ("filter_by_distance", {"latlon": (51.05, 13.74), "distance": 10}, ["01050", "01048"]),
        ("filter_by_bbox", {"left": 13.7, "bottom": 51.0, "right": 13.8, "top": 51.2}, ["01048"]),
        ("filter_by_sql", {"sql": "station_id = '01048'"}, ["01048"]),
    ],
)
def test_station_filters_build_the_station_index_once(
    monkeypatch: pytest.MonkeyPatch,
    default_settings: Settings,
    method: str,
    kwargs: dict,
    expected: list[str],
) -> None:
    """Test each station filter builds the station index once and hands that frame to df_all (GH-2475).

    They built it again for the result's df_all, and filter_by_distance four times. df_all stays
    the full station list as all() gives it: filter_by_rank's distance column is not added to it.
    """
    built = _count_station_index_builds(monkeypatch)
    request = DwdObservationRequest(parameters=[("daily", "climate_summary")], settings=default_settings)

    result = getattr(request, method)(**kwargs)

    assert len(built) == 1
    assert result.df.get_column("station_id").to_list() == expected
    assert_frame_equal(result.df_all, request.all().df)


def test_filter_by_distance_without_stations_finds_none(
    monkeypatch: pytest.MonkeyPatch,
    default_settings: Settings,
) -> None:
    """Test a distance filter over an empty station list answers with no stations (GH-2475).

    It ranked by the number of stations, which is 0 here, and so raised "'rank' has to be at least
    1." for a rank the caller never gave.
    """
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda _self: pl.LazyFrame())
    request = DwdObservationRequest(parameters=[("daily", "climate_summary")], settings=default_settings)

    result = request.filter_by_distance(latlon=(51.05, 13.74), distance=10)

    assert result.df.is_empty()
    assert result.df_all.is_empty()


@pytest.mark.parametrize(
    ("method", "kwargs"),
    [
        ("interpolate", {"latlon": (51.05, 13.74)}),
        ("summarize", {"latlon": (51.05, 13.74)}),
        # the position is read off the same station list: it used to be a third build
        ("interpolate_by_station_id", {"station_id": "01048"}),
        ("summarize_by_station_id", {"station_id": "01048"}),
    ],
)
def test_estimates_build_the_station_index_once(
    monkeypatch: pytest.MonkeyPatch,
    default_settings: Settings,
    method: str,
    kwargs: dict,
) -> None:
    """Test interpolate and summarize build the station index once, where they built it twice (GH-2506).

    The real core runs, with the stations' values read as none. It ranks the stations with
    `filter_by_distance` and the request builds its frame of the stations taken (`df_all`) off the
    same station list, which each used to build on its own (GH-2475 took six builds to two, and
    `_by_station_id` read the position off a third).
    """
    from wetterdienst.model.values import TimeseriesValues  # noqa: PLC0415

    if method.startswith("interpolate"):
        pytest.importorskip("wetterdienst.core.interpolate")
    built = _count_station_index_builds(monkeypatch)
    monkeypatch.setattr(TimeseriesValues, "query", lambda _self: iter([]))
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start="2020-01-01",
        end="2020-01-02",
        settings=default_settings,
    )

    result = getattr(request, method)(**kwargs)

    assert len(built) == 1
    assert_frame_equal(result.stations.df_all, request.all().df)


def test_interpolate_refuses_a_point_utm_cannot_place_before_building_the_station_index(
    monkeypatch: pytest.MonkeyPatch,
    default_settings: Settings,
) -> None:
    """Test a point beyond UTM is refused without building the station index (GH-2506).

    The request hands the core the station list, so it has to refuse the point first, as the core
    did before the list was built there.
    """
    from wetterdienst.exceptions import LocationOutOfRangeError  # noqa: PLC0415

    pytest.importorskip("wetterdienst.core.interpolate")
    built = _count_station_index_builds(monkeypatch)
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start="2020-01-01",
        end="2020-01-02",
        settings=default_settings,
    )

    with pytest.raises(LocationOutOfRangeError):
        request.interpolate(latlon=(89.0, 13.74))

    assert built == []


_VILNIUS = ZoneInfo("Europe/Vilnius")
_BERLIN = ZoneInfo("Europe/Berlin")
_UTC = ZoneInfo("UTC")
# 2025-03-30 is the day Vilnius moves to summer time (03:00 EET -> 04:00 EEST, UTC+2 -> UTC+3), so its midnight
# and its last hour carry different offsets: 00:00 is 22:00 UTC the day before, 23:00 is 20:00 UTC.
_VILNIUS_DAY_START = dt.datetime(2025, 3, 29, 22, tzinfo=_UTC)
_VILNIUS_DAY_END = dt.datetime(2025, 3, 30, 20, tzinfo=_UTC)


@pytest.mark.parametrize(
    ("start", "end"),
    [
        pytest.param(
            dt.datetime(2025, 3, 30, 0, tzinfo=_VILNIUS),
            dt.datetime(2025, 3, 30, 23, tzinfo=_VILNIUS),
            id="named zone",
        ),
        pytest.param("2025-03-30T00:00+02:00", "2025-03-30T23:00+03:00", id="fixed offset"),
        pytest.param("2025-03-29T22:00:00", "2025-03-30T20:00:00", id="naive string is UTC"),
        pytest.param(
            dt.datetime(2025, 3, 29, 22),  # noqa: DTZ001
            dt.datetime(2025, 3, 30, 20),  # noqa: DTZ001
            id="naive datetime is UTC",
        ),
        pytest.param(_VILNIUS_DAY_START, _VILNIUS_DAY_END, id="UTC"),
        pytest.param(
            dt.datetime(2025, 3, 29, 23, tzinfo=_BERLIN),
            dt.datetime(2025, 3, 30, 22, tzinfo=_BERLIN),
            id="another named zone, with its own transition on the day",
        ),
    ],
)
def test_convert_timestamps_gives_utc_whatever_zone_the_bounds_came_in(
    start: str | dt.datetime,
    end: str | dt.datetime,
) -> None:
    """A bound in any zone becomes the same instant in UTC, so the UTC values can be compared with it (GH-2682)."""
    converted_start, converted_end = TimeseriesRequest.convert_timestamps(start, end)
    assert (converted_start, converted_end) == (_VILNIUS_DAY_START, _VILNIUS_DAY_END)
    assert converted_start.tzinfo == _UTC
    assert converted_end.tzinfo == _UTC
    # the zone itself, which is what polars compares a column's dtype against
    assert str(converted_start.tzinfo) == str(converted_end.tzinfo) == "UTC"


def test_convert_timestamps_with_one_bound_gives_it_to_both_in_utc() -> None:
    """The bound that was left out takes the other one, already converted (GH-2682)."""
    bound = dt.datetime(2025, 3, 30, 0, tzinfo=_VILNIUS)
    assert TimeseriesRequest.convert_timestamps(bound, None) == (_VILNIUS_DAY_START, _VILNIUS_DAY_START)
    assert TimeseriesRequest.convert_timestamps(None, bound) == (_VILNIUS_DAY_START, _VILNIUS_DAY_START)
    assert TimeseriesRequest.convert_timestamps(None, None) == (None, None)


def test_convert_timestamps_orders_bounds_by_instant_not_by_wall_clock() -> None:
    """A window is reversed when its end is earlier as an instant, whatever the clocks of its two zones say."""
    # 04:00 in Vilnius (summer time, UTC+3) is 01:00 UTC; the wall clock reads later than 02:00 UTC
    start = dt.datetime(2025, 3, 30, 2, tzinfo=_UTC)
    end = dt.datetime(2025, 3, 30, 4, tzinfo=_VILNIUS)
    with pytest.raises(ReversedTimeIntervalError):
        TimeseriesRequest.convert_timestamps(start, end)
    # the same wall clocks the other way round are a window of one hour
    assert TimeseriesRequest.convert_timestamps(end, start) == (
        dt.datetime(2025, 3, 30, 1, tzinfo=_UTC),
        dt.datetime(2025, 3, 30, 2, tzinfo=_UTC),
    )


def test_request_keeps_its_window_in_utc_for_a_named_zone(default_settings: Settings) -> None:
    """The window a request holds is UTC (GH-2682)."""
    request = DwdObservationRequest(
        parameters=[("hourly", "air_temperature", "temperature_air_2m")],
        start=dt.datetime(2025, 3, 30, 0, tzinfo=_VILNIUS),
        end=dt.datetime(2025, 3, 30, 23, tzinfo=_VILNIUS),
        settings=default_settings,
    )
    assert (request.start, request.end) == (_VILNIUS_DAY_START, _VILNIUS_DAY_END)
    assert str(request.start.tzinfo) == str(request.end.tzinfo) == "UTC"


def test_dwd_periods_follow_the_instant_of_a_bound_in_a_named_zone(
    default_settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DWD reads the periods off the interval in Europe/Berlin; a bound in another zone keeps its instant (GH-2682).

    The recent period is fixed to begin at midnight Berlin on 2025-06-01, which is 01:00 Vilnius. A bound
    read at 00:30 *Vilnius* is 23:30 Berlin on 2025-05-31, before it; the same wall clock read in Berlin
    is after it. Reading the wall clock of a bound as Berlin time, which is what ignoring its zone does,
    would put both inside.
    """
    recent = portion.closed(dt.datetime(2025, 6, 1, tzinfo=_BERLIN), dt.datetime(2025, 6, 10, tzinfo=_BERLIN))
    monkeypatch.setattr(DwdObservationRequest, "_recent_interval", property(lambda self: recent))  # noqa: ARG005

    def periods(bound: dt.datetime) -> set[Period]:
        return DwdObservationRequest(
            parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
            start=bound,
            end=bound,
            settings=default_settings,
        ).periods

    just_before = dt.datetime(2025, 6, 1, 0, 30, tzinfo=_VILNIUS)  # 23:30 Berlin on 2025-05-31
    just_after = dt.datetime(2025, 6, 1, 0, 30, tzinfo=_BERLIN)
    assert periods(just_before) == {Period.HISTORICAL}
    assert periods(just_after) == {Period.HISTORICAL, Period.RECENT}
    # the instants spelled in UTC and in a fixed offset select the same
    assert periods(just_before.astimezone(_UTC)) == periods(just_before)
    assert periods(dt.datetime(2025, 5, 31, 23, 30, tzinfo=dt.timezone(dt.timedelta(hours=2)))) == periods(just_before)
