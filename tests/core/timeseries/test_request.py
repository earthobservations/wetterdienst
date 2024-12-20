import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst import Period
from wetterdienst.exceptions import StartDateEndDateError
from wetterdienst.provider.dwd.observation import (
    DwdObservationMetadata,
    DwdObservationRequest,
)


@pytest.fixture
def expected_stations_df():
    return pl.DataFrame(
        [
            {
                "station_id": "02480",
                "start_date": dt.datetime(2004, 9, 1, tzinfo=ZoneInfo("UTC")),
                "latitude": 50.0643,
                "longitude": 8.993,
                "height": 108.0,
                "name": "Kahl/Main",
                "state": "Bayern",
                "distance": 9.759384982994229,
            },
            {
                "station_id": "04411",
                "start_date": dt.datetime(2002, 1, 24, tzinfo=ZoneInfo("UTC")),
                "latitude": 49.9195,
                "longitude": 8.9672,
                "height": 155.0,
                "name": "Schaafheim-Schlierbach",
                "state": "Hessen",
                "distance": 10.160326,
            },
            {
                "station_id": "07341",
                "start_date": dt.datetime(2005, 7, 16, tzinfo=ZoneInfo("UTC")),
                "latitude": 50.0900,
                "longitude": 8.7862,
                "height": 119.0,
                "name": "Offenbach-Wetterpark",
                "state": "Hessen",
                "distance": 12.891318342515483,
            },
        ],
        schema={
            "station_id": pl.String,
            "start_date": pl.Datetime(time_zone="UTC"),
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "height": pl.Float64,
            "name": pl.String,
            "state": pl.String,
            "distance": pl.Float64,
        },
        orient="row",
    )


@pytest.fixture
def default_request(default_settings):
    return DwdObservationRequest(
        parameters=[("hourly", "temperature_air")],
        periods="historical",
        start_date=dt.datetime(2020, 1, 1),
        end_date=dt.datetime(2020, 1, 20),
        settings=default_settings,
    )


def test_dwd_observation_data_api_singe_parameter(default_settings):
    request = DwdObservationRequest(
        parameters=[("daily", "kl", "precipitation_height")],
        periods=["recent", "historical"],
        settings=default_settings,
    )

    assert request == DwdObservationRequest(
        parameters=[DwdObservationMetadata.daily.kl.precipitation_height],
        periods=[Period.HISTORICAL, Period.RECENT],
        start_date=None,
        end_date=None,
    )


def test_dwd_observation_data_whole_dataset(default_settings):
    """Test parameters given as parameter - dataset pair"""
    given = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        settings=default_settings,
    )
    assert given.parameters == [
        DwdObservationMetadata.daily.climate_summary.wind_gust_max,
        DwdObservationMetadata.daily.climate_summary.wind_speed,
        DwdObservationMetadata.daily.climate_summary.precipitation_height,
        DwdObservationMetadata.daily.climate_summary.precipitation_form,
        DwdObservationMetadata.daily.climate_summary.sunshine_duration,
        DwdObservationMetadata.daily.climate_summary.snow_depth,
        DwdObservationMetadata.daily.climate_summary.cloud_cover_total,
        DwdObservationMetadata.daily.climate_summary.pressure_vapor,
        DwdObservationMetadata.daily.climate_summary.pressure_air_site,
        DwdObservationMetadata.daily.climate_summary.temperature_air_mean_2m,
        DwdObservationMetadata.daily.climate_summary.humidity,
        DwdObservationMetadata.daily.climate_summary.temperature_air_max_2m,
        DwdObservationMetadata.daily.climate_summary.temperature_air_min_2m,
        DwdObservationMetadata.daily.climate_summary.temperature_air_min_0_05m,
    ]


@pytest.mark.remote
def test_dwd_observation_wrong_start_date_end_date(default_settings):
    # station id
    with pytest.raises(StartDateEndDateError):
        DwdObservationRequest(
            parameters=[("daily", "kl", "precipitation_height")],
            start_date="1971-01-01",
            end_date="1951-01-01",
            settings=default_settings,
        )


def test_dwd_observation_data_dates(default_settings):
    # time input
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date="1971-01-01",
        settings=default_settings,
    )
    assert request.start_date == dt.datetime(1971, 1, 1, tzinfo=ZoneInfo("UTC"))
    assert request.end_date == dt.datetime(1971, 1, 1, tzinfo=ZoneInfo("UTC"))
    assert request.periods == [Period.HISTORICAL]


@pytest.mark.remote
def test_dwd_observations_stations_filter_empty(default_request):
    # Existing combination of parameters
    request = default_request.filter_by_station_id(station_id=("FizzBuzz",))
    assert request.df.is_empty()


@pytest.mark.remote
def test_dwd_observations_stations_filter_name_empty(default_request):
    # Existing combination of parameters
    request = default_request.filter_by_name(name="FizzBuzz")
    assert request.df.is_empty()


def test_dwd_observations_multiple_datasets_tidy(default_settings):
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary"), ("daily", "precipitation_more")],
        periods="historical",
        settings=default_settings,
    )
    assert request.tidy


def test_dwd_observations_stations_wrong_types(default_request):
    with pytest.raises(TypeError):
        default_request.filter_by_station_id(name=123)

    with pytest.raises(TypeError):
        default_request.filter_by_name(name=123)


@pytest.mark.remote
def test_dwd_observation_stations_filter_by_rank_single(default_request, expected_stations_df):
    # Test for one nearest station
    request = default_request.filter_by_rank(
        latlon=(50.0, 8.9),
        rank=1,
    )
    given_df = request.df.drop("end_date")
    assert_frame_equal(given_df[0, :], expected_stations_df[0, :])
    values = request.values.all()
    assert_frame_equal(values.df_stations.head(1).drop("end_date"), expected_stations_df.head(1))


@pytest.mark.remote
def test_dwd_observation_stations_filter_by_rank_multiple(default_request, expected_stations_df):
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
def test_dwd_observation_stations_nearby_distance(default_request, expected_stations_df):
    # Kilometers
    nearby_station = default_request.filter_by_distance(latlon=(50.0, 8.9), distance=16.13, unit="km")
    nearby_station = nearby_station.df.drop("end_date")
    assert_frame_equal(nearby_station, expected_stations_df)
    # Miles
    nearby_station = default_request.filter_by_distance(latlon=(50.0, 8.9), distance=10.03, unit="mi")
    nearby_station = nearby_station.df.drop("end_date")
    assert_frame_equal(nearby_station, expected_stations_df)


@pytest.mark.remote
def test_dwd_observation_stations_bbox(default_request, expected_stations_df):
    nearby_station = default_request.filter_by_bbox(left=8.7862, bottom=49.9195, right=8.993, top=50.0900)
    nearby_station = nearby_station.df.drop("end_date")
    assert_frame_equal(nearby_station, expected_stations_df.drop("distance"))


@pytest.mark.remote
def test_dwd_observation_stations_bbox_empty(default_request):
    # Bbox
    assert default_request.filter_by_bbox(
        left=-100,
        bottom=-20,
        right=-90,
        top=-10,
    ).df.is_empty()


@pytest.mark.remote
def test_dwd_observation_stations_fail(default_request):
    # Number
    with pytest.raises(ValueError):
        default_request.filter_by_rank(
            latlon=(51.4, 9.3),
            rank=0,
        )
    # Distance
    with pytest.raises(ValueError):
        default_request.filter_by_distance(
            latlon=(51.4, 9.3),
            distance=-1,
        )
    # Bbox
    with pytest.raises(ValueError):
        default_request.filter_by_bbox(left=10, bottom=10, right=5, top=5)
