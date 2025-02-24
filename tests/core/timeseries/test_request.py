# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD observation data API."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst import Period, Settings
from wetterdienst.core.timeseries.request import TimeseriesRequest
from wetterdienst.exceptions import StartDateEndDateError
from wetterdienst.provider.dwd.observation import (
    DwdObservationMetadata,
    DwdObservationRequest,
)


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
                "height": 108.0,
                "name": "Kahl/Main",
                "state": "Bayern",
                "distance": 9.759384982994229,
            },
            {
                "resolution": "hourly",
                "dataset": "temperature_air",
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
                "resolution": "hourly",
                "dataset": "temperature_air",
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
            "resolution": pl.String,
            "dataset": pl.String,
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
def default_request(default_settings: Settings) -> TimeseriesRequest:
    """Provide default request."""
    return DwdObservationRequest(
        parameters=[("hourly", "temperature_air")],
        periods="historical",
        start_date=dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2020, 1, 20, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )


def test_dwd_observation_data_api_singe_parameter(default_settings: Settings) -> None:
    """Test parameters given as parameter - dataset pair."""
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


def test_dwd_observation_data_whole_dataset(default_settings: Settings) -> None:
    """Test parameters given as parameter - dataset pair."""
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
def test_dwd_observation_wrong_start_date_end_date(default_settings: Settings) -> None:
    """Test for wrong start and end date."""
    with pytest.raises(StartDateEndDateError):
        DwdObservationRequest(
            parameters=[("daily", "kl", "precipitation_height")],
            start_date="1971-01-01",
            end_date="1951-01-01",
            settings=default_settings,
        )


def test_dwd_observation_data_dates(default_settings: Settings) -> None:
    """Test for dates."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        start_date="1971-01-01",
        settings=default_settings,
    )
    assert request.start_date == dt.datetime(1971, 1, 1, tzinfo=ZoneInfo("UTC"))
    assert request.end_date == dt.datetime(1971, 1, 1, tzinfo=ZoneInfo("UTC"))
    assert request.periods == [Period.HISTORICAL]


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


def test_dwd_observations_multiple_datasets_tidy(default_settings: Settings) -> None:
    """Test for multiple datasets."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary"), ("daily", "precipitation_more")],
        periods="historical",
        settings=default_settings,
    )
    assert request.tidy


def test_dwd_observations_stations_wrong_types(default_request: TimeseriesRequest) -> None:
    """Test for wrong types."""
    with pytest.raises(TypeError):
        default_request.filter_by_station_id(name=123)

    with pytest.raises(TypeError):
        default_request.filter_by_name(name=123)


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
    with pytest.raises(ValueError, match="'rank' has to be at least 1."):
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
        parameters=[("daily", "kl", "temperature_air_mean_2m"), ("hourly", "precipitation", "precipitation_height")],
        settings=default_settings,
        start_date=dt.datetime(1900, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2024, 1, 1, tzinfo=ZoneInfo("UTC")),
    ).filter_by_station_id(("02315", "01050", "19140"))
    assert request.parameters == [
        DwdObservationMetadata.daily.kl.temperature_air_mean_2m,
        DwdObservationMetadata.hourly.precipitation.precipitation_height,
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
        "height": 78.0,
        "name": "Holzdorf-Bernsdorf",
        "state": "Brandenburg",
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
            "height": 112.0,
            "name": "Dresden-Hosterwitz",
            "state": "Sachsen",
        },
        {
            "resolution": "hourly",
            "dataset": "precipitation",
            "station_id": "01050",
            "start_date": dt.datetime(2006, 4, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
            "latitude": 51.0221,
            "longitude": 13.847,
            "height": 112.0,
            "name": "Dresden-Hosterwitz",
            "state": "Sachsen",
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
            "height": 278.0,
            "name": "Gotha",
            "state": "Thüringen",
        },
    ]
    df_values = request.values.all().df
    assert df_values.get_column("resolution").unique().sort().to_list() == ["daily", "hourly"]
    assert df_values.get_column("dataset").unique().sort().to_list() == [
        "climate_summary",
        "precipitation",
    ]
    assert df_values.get_column("parameter").unique().sort().to_list() == [
        "precipitation_height",
        "temperature_air_mean_2m",
    ]
    # station in climate_summary
    df_stats = (
        df_values.group_by(["resolution", "dataset", "station_id"], maintain_order=True)
        .count()
        .sort(["resolution", "dataset", "station_id"])
    )
    assert df_stats.to_dicts() == [
        {"count": 25871, "dataset": "climate_summary", "resolution": "daily", "station_id": "01050"},
        {"count": 8610, "dataset": "climate_summary", "resolution": "daily", "station_id": "02315"},
        {"count": 151743, "dataset": "precipitation", "resolution": "hourly", "station_id": "01050"},
        {"count": 27568, "dataset": "precipitation", "resolution": "hourly", "station_id": "19140"},
    ]
