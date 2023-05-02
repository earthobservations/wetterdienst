import datetime as dt

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst import Period, Resolution
from wetterdienst.exceptions import StartDateEndDateError
from wetterdienst.provider.dwd.observation import (
    DwdObservationDataset,
    DwdObservationParameter,
    DwdObservationPeriod,
    DwdObservationRequest,
    DwdObservationResolution,
)


@pytest.fixture
def expected_stations_df():
    return pl.DataFrame(
        [
            (
                "02480",
                dt.datetime(2004, 9, 1, tzinfo=dt.timezone.utc),
                108.0,
                50.0643,
                8.993,
                "Kahl/Main",
                "Bayern",
                9.759384982994229,
            ),
            (
                "04411",
                dt.datetime(2002, 1, 24, tzinfo=dt.timezone.utc),
                155.0,
                49.9195,
                8.9671,
                "Schaafheim-Schlierbach",
                "Hessen",
                10.156943448624304,
            ),
            (
                "07341",
                dt.datetime(2005, 7, 16, tzinfo=dt.timezone.utc),
                119.0,
                50.0900,
                8.7862,
                "Offenbach-Wetterpark",
                "Hessen",
                12.891318342515483,
            ),
        ],
        schema={
            "station_id": pl.Utf8,
            "from_date": pl.Datetime(time_zone="UTC"),
            "height": pl.Float64,
            "latitude": pl.Float64,
            "longitude": pl.Float64,
            "name": pl.Utf8,
            "state": pl.Utf8,
            "distance": pl.Float64,
        },
    )


@pytest.fixture
def default_request(default_settings):
    return DwdObservationRequest(
        parameter="temperature_air",
        resolution="hourly",
        period="historical",
        start_date=dt.datetime(2020, 1, 1),
        end_date=dt.datetime(2020, 1, 20),
        settings=default_settings,
    )


def test_dwd_observation_data_api(default_settings):
    request = DwdObservationRequest(
        parameter=["precipitation_height"],
        resolution="daily",
        period=["recent", "historical"],
        settings=default_settings,
    )

    assert request == DwdObservationRequest(
        parameter=[DwdObservationParameter.DAILY.PRECIPITATION_HEIGHT],
        resolution=Resolution.DAILY,
        period=[Period.HISTORICAL, Period.RECENT],
        start_date=None,
        end_date=None,
    )

    assert request.parameter == [
        (
            DwdObservationParameter.DAILY.CLIMATE_SUMMARY.PRECIPITATION_HEIGHT,
            DwdObservationDataset.CLIMATE_SUMMARY,
        )
    ]


@pytest.mark.remote
def test_dwd_observation_data_dataset(default_settings):
    """Request a parameter set"""
    given = DwdObservationRequest(
        parameter=["kl"], resolution="daily", period=["recent", "historical"], settings=default_settings
    ).filter_by_station_id(station_id=(1,))
    expected = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        period=[DwdObservationPeriod.HISTORICAL, DwdObservationPeriod.RECENT],
        start_date=None,
        end_date=None,
    ).filter_by_station_id(
        station_id=(1,),
    )
    assert given == expected
    given = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        period=[DwdObservationPeriod.HISTORICAL, DwdObservationPeriod.RECENT],
    ).filter_by_station_id(
        station_id=(1,),
    )
    expected = DwdObservationRequest(
        parameter=[DwdObservationDataset.CLIMATE_SUMMARY],
        resolution=DwdObservationResolution.DAILY,
        period=[DwdObservationPeriod.HISTORICAL, DwdObservationPeriod.RECENT],
        start_date=None,
        end_date=None,
    ).filter_by_station_id(
        station_id=(1,),
    )
    assert given == expected
    assert expected.parameter == [
        (
            DwdObservationDataset.CLIMATE_SUMMARY,
            DwdObservationDataset.CLIMATE_SUMMARY,
        )
    ]


def test_dwd_observation_data_parameter(default_settings):
    """Test parameter given as single value without dataset"""
    given = DwdObservationRequest(
        parameter=["precipitation_height"],
        resolution="daily",
        period=["recent", "historical"],
        settings=default_settings,
    )
    assert given.parameter == [
        (
            DwdObservationParameter.DAILY.CLIMATE_SUMMARY.PRECIPITATION_HEIGHT,
            DwdObservationDataset.CLIMATE_SUMMARY,
        )
    ]
    given = DwdObservationRequest(
        parameter=["climate_summary"], resolution="daily", period=["recent", "historical"], settings=default_settings
    )
    assert given.parameter == [(DwdObservationDataset.CLIMATE_SUMMARY, DwdObservationDataset.CLIMATE_SUMMARY)]


def test_dwd_observation_data_parameter_dataset_pairs(default_settings):
    """Test parameters given as parameter - dataset pair"""
    given = DwdObservationRequest(
        parameter=[("climate_summary", "climate_summary")],
        resolution="daily",
        period=["recent", "historical"],
        settings=default_settings,
    )
    assert given.parameter == [(DwdObservationDataset.CLIMATE_SUMMARY, DwdObservationDataset.CLIMATE_SUMMARY)]
    given = DwdObservationRequest(
        parameter=[("precipitation_height", "precipitation_more")],
        resolution="daily",
        period=["recent", "historical"],
        settings=default_settings,
    )
    assert given.parameter == [
        (
            DwdObservationParameter.DAILY.PRECIPITATION_MORE.PRECIPITATION_HEIGHT,
            DwdObservationDataset.PRECIPITATION_MORE,
        )
    ]


@pytest.mark.remote
def test_dwd_observation_wrong_start_date_end_date(default_settings):
    # station id
    with pytest.raises(StartDateEndDateError):
        DwdObservationRequest(
            parameter=["abc"],
            resolution=DwdObservationResolution.DAILY,
            start_date="1971-01-01",
            end_date="1951-01-01",
            settings=default_settings,
        )


def test_dwd_observation_data_dates(default_settings):
    # time input
    request = DwdObservationRequest(
        parameter=["climate_summary"],
        resolution="daily",
        start_date="1971-01-01",
        settings=default_settings,
    ).filter_by_station_id(
        station_id=[1],
    )
    assert request == DwdObservationRequest(
        parameter=["climate_summary"],
        resolution="daily",
        period=[
            DwdObservationPeriod.HISTORICAL,
        ],
        start_date=dt.datetime(1971, 1, 1),
        end_date=dt.datetime(1971, 1, 1),
        settings=default_settings,
    ).filter_by_station_id(
        station_id=[1],
    )
    request = DwdObservationRequest(
        parameter=["climate_summary"],
        resolution="daily",
        period=["historical"],
        end_date="1971-01-01",
        settings=default_settings,
    ).filter_by_station_id(
        station_id=[1],
    )

    assert request == DwdObservationRequest(
        parameter=["climate_summary"],
        resolution="daily",
        period=[
            "historical",
        ],
        start_date=dt.datetime(1971, 1, 1),
        end_date=dt.datetime(1971, 1, 1),
        settings=default_settings,
    ).filter_by_station_id(
        station_id=[1],
    )

    with pytest.raises(StartDateEndDateError):
        DwdObservationRequest(
            parameter=["climate_summary"],
            resolution="daily",
            start_date="1971-01-01",
            end_date="1951-01-01",
            settings=default_settings,
        )


@pytest.mark.remote
def test_dwd_observations_stations_filter_empty(default_request):
    # Existing combination of parameters
    request = default_request.filter_by_station_id(station_id=("FizzBuzz",))
    given_df = request.df
    assert given_df.is_empty()


@pytest.mark.remote
def test_dwd_observations_stations_filter_name_empty(default_request):
    # Existing combination of parameters
    request = default_request.filter_by_name(name="FizzBuzz")
    given_df = request.df
    assert given_df.is_empty()


def test_dwd_observations_multiple_datasets_tidy(default_settings):
    request = DwdObservationRequest(
        parameter=["climate_summary", "precipitation_more"],
        resolution="daily",
        period="historical",
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
    given_df = request.df.drop(columns="to_date")
    assert_frame_equal(given_df[0, :], expected_stations_df[0, :])
    values = request.values.all()
    assert_frame_equal(values.df_stations[0, :].drop(columns="to_date"), expected_stations_df[0, :])


@pytest.mark.remote
def test_dwd_observation_stations_filter_by_rank_multiple(default_request, expected_stations_df):
    request = default_request.filter_by_rank(
        latlon=(50.0, 8.9),
        rank=3,
    )
    given_df = request.df.drop(columns="to_date")
    assert_frame_equal(
        given_df.head(3),
        expected_stations_df,
    )
    values = request.values.all()
    assert_frame_equal(values.df_stations.drop(columns="to_date"), expected_stations_df)


@pytest.mark.remote
def test_dwd_observation_stations_nearby_distance(default_request, expected_stations_df):
    # Kilometers
    nearby_station = default_request.filter_by_distance(latlon=(50.0, 8.9), distance=16.13, unit="km")
    nearby_station = nearby_station.df.drop(columns="to_date")
    assert_frame_equal(nearby_station, expected_stations_df)
    # Miles
    nearby_station = default_request.filter_by_distance(latlon=(50.0, 8.9), distance=10.03, unit="mi")
    nearby_station = nearby_station.df.drop(columns="to_date")
    assert_frame_equal(nearby_station, expected_stations_df)


@pytest.mark.remote
def test_dwd_observation_stations_bbox(default_request, expected_stations_df):
    nearby_station = default_request.filter_by_bbox(left=8.7862, bottom=49.9195, right=8.993, top=50.0900)
    nearby_station = nearby_station.df.drop(columns="to_date")
    assert_frame_equal(nearby_station, expected_stations_df.drop(columns=["distance"]))


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
