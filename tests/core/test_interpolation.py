# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for interpolation."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from polars.testing import assert_frame_equal

from wetterdienst import Settings
from wetterdienst.core.interpolate import (
    _OCCURRENCE_BASED_PARAMETERS,
    apply_interpolation,
    get_valid_station_groups,
)
from wetterdienst.exceptions import StationNotFoundError
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest
from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
)

pytest.importorskip("shapely")

pytestmark = pytest.mark.slow


# ---------------------------------------------------------------------------
# Shared geometry for occurrence-threshold unit tests
# ---------------------------------------------------------------------------
# Four stations forming a 20 km x 20 km square in UTM-like coordinates.
# Station D (NW corner) is the only one that ever records a positive value.
# The target point is placed in the SW quadrant (close to A/B, away from D)
# so that it falls inside the Delaunay triangle whose nodes are ALL zero-value
# stations → occurrence index < 0.5 → zeroing is triggered for the sparse case.
# No network traffic is needed for these tests.
_STATIONS_DICT: dict = {
    "A": (490_000.0, 5_490_000.0, 14.14),  # SW corner
    "B": (510_000.0, 5_490_000.0, 14.14),  # SE corner
    "C": (510_000.0, 5_510_000.0, 14.14),  # NE corner
    "D": (490_000.0, 5_510_000.0, 14.14),  # NW corner — positive station
}
# Off-centre target, inside the triangle formed by A-B-C (all zero-value):
# occurrence index at this point ≈ 0.25 for the 1-of-4 case.
_UTM_X = 495_000.0
_UTM_Y = 5_495_000.0


def test_occurrence_threshold_zeroes_sparse_precipitation() -> None:
    """Interpolated precipitation must be zeroed when occurrence index < 0.5.

    Fewer than half of surrounding stations recorded a positive value triggers zeroing.
    """
    valid_groups = get_valid_station_groups(_STATIONS_DICT, _UTM_X, _UTM_Y)
    # Only 1 of 4 stations has precipitation → occurrence index ≈ 0.25 at centre
    row = {"A": 0.0, "B": 0.0, "C": 0.0, "D": 5.0}
    _, _, _, value, _, _ = apply_interpolation(
        row,
        _STATIONS_DICT,
        valid_groups,
        "daily",
        "climate_summary",
        "precipitation_height",
        _UTM_X,
        _UTM_Y,
        [],
    )
    assert value == 0.0, "Expected zero when fewer than half of stations have precipitation"


def test_occurrence_threshold_preserves_majority_precipitation() -> None:
    """Interpolated precipitation must be kept when the majority of surrounding stations recorded a positive value.

    Occurrence index >= 0.5 preserves the interpolated value.
    """
    valid_groups = get_valid_station_groups(_STATIONS_DICT, _UTM_X, _UTM_Y)
    # 3 of 4 stations have precipitation → occurrence index ≈ 0.75 at centre
    row = {"A": 5.0, "B": 5.0, "C": 5.0, "D": 0.0}
    _, _, _, value, _, _ = apply_interpolation(
        row,
        _STATIONS_DICT,
        valid_groups,
        "daily",
        "climate_summary",
        "precipitation_height",
        _UTM_X,
        _UTM_Y,
        [],
    )
    assert value is not None
    assert value > 0.0, "Expected positive value when majority of stations have precipitation"


def test_occurrence_threshold_not_applied_to_temperature() -> None:
    """The occurrence threshold must NOT be applied to continuous parameters such as temperature.

    A non-zero interpolated value must be preserved even when only one station has a positive reading.
    """
    valid_groups = get_valid_station_groups(_STATIONS_DICT, _UTM_X, _UTM_Y)
    row = {"A": 0.0, "B": 0.0, "C": 0.0, "D": 5.0}
    _, _, _, value, _, _ = apply_interpolation(
        row,
        _STATIONS_DICT,
        valid_groups,
        "daily",
        "climate_summary",
        "temperature_air_mean_2m",
        _UTM_X,
        _UTM_Y,
        [],
    )
    assert value is not None
    assert value > 0.0, "Temperature must not be zeroed by occurrence threshold"


def test_occurrence_threshold_applies_to_snow_depth_new() -> None:
    """The occurrence threshold must apply to snow_depth_new.

    snow_depth_new shares the zero-inflated character of precipitation.
    """
    valid_groups = get_valid_station_groups(_STATIONS_DICT, _UTM_X, _UTM_Y)
    row = {"A": 0.0, "B": 0.0, "C": 0.0, "D": 3.0}
    _, _, _, value, _, _ = apply_interpolation(
        row,
        _STATIONS_DICT,
        valid_groups,
        "daily",
        "climate_summary",
        "snow_depth_new",
        _UTM_X,
        _UTM_Y,
        [],
    )
    assert value == 0.0, "Expected zero for snow_depth_new when fewer than half of stations have new snow"


def test_occurrence_based_parameters_set_contains_all_precipitation_variants() -> None:
    """Smoke-test that _OCCURRENCE_BASED_PARAMETERS covers core precipitation and new-snow parameters."""
    required = {
        "precipitation_height",
        "precipitation_height_liquid",
        "precipitation_height_last_1h",
        "precipitation_height_last_24h",
        "precipitation_duration",
        "snow_depth_new",
        "water_equivalent_snow_depth_new",
    }
    assert required.issubset(_OCCURRENCE_BASED_PARAMETERS), (
        f"Missing from _OCCURRENCE_BASED_PARAMETERS: {required - _OCCURRENCE_BASED_PARAMETERS}"
    )


@pytest.fixture
def df_interpolated_empty() -> pl.DataFrame:
    """Provide empty DataFrame for interpolated values."""
    return pl.DataFrame(
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "distance_mean": pl.Float64,
            "taken_station_ids": pl.List(pl.String),
        },
    )


@pytest.mark.remote
def test_interpolation_temperature_air_mean_2m_hourly_by_coords(default_settings: Settings) -> None:
    """Test that the interpolation works with hourly data."""
    request = DwdObservationRequest(
        parameters=[("hourly", "temperature_air", "temperature_air_mean_2m")],
        start_date=dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 20, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    result = request.interpolate(latlon=(50.0, 8.9))
    assert result.df.shape[0] == 18001
    assert result.df.drop_nulls().shape[0] == 17914
    given_df = result.filter_by_date("2022-01-02 00:00:00+00:00")
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "f674568e",
                "resolution": "hourly",
                "dataset": "temperature_air",
                "parameter": "temperature_air_mean_2m",
                "date": dt.datetime(2022, 1, 2, tzinfo=ZoneInfo("UTC")),
                "value": 4.56,
                "distance_mean": 13.37,
                "taken_station_ids": ["02480", "04411", "07341", "00917"],
            },
        ],
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_interpolation_temperature_air_mean_2m_daily_by_station_id(default_settings: Settings) -> None:
    """Test that the interpolation works with daily data."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start_date=dt.datetime(1986, 10, 31, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(1986, 11, 1, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "6754d04d",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_mean_2m",
                "date": dt.datetime(1986, 10, 31, tzinfo=ZoneInfo("UTC")),
                "value": 6.37,
                "distance_mean": 16.99,
                "taken_station_ids": ["00072", "02074", "02638", "04703"],
            },
            {
                "station_id": "6754d04d",
                "resolution": "daily",
                "dataset": "climate_summary",
                "parameter": "temperature_air_mean_2m",
                "date": dt.datetime(1986, 11, 1, tzinfo=ZoneInfo("UTC")),
                "value": 8.7,
                "distance_mean": 0.0,
                "taken_station_ids": ["00071"],
            },
        ],
        orient="row",
    )
    for result in (
        request.interpolate(latlon=(48.2156, 8.9784)),
        request.interpolate_by_station_id(station_id="00071"),
    ):
        given_df = result.df
        assert given_df.shape[0] == 2
        assert given_df.drop_nulls().shape[0] == 2
        assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_interpolation_precipitation_height_minute_10(default_settings: Settings) -> None:
    """Test that the interpolation works with precipitation."""
    request = DwdObservationRequest(
        parameters=[("minute_10", "precipitation", "precipitation_height")],
        start_date=dt.datetime(2021, 10, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2021, 10, 5, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    result = request.interpolate(latlon=(50.0, 8.9))
    assert result.df.shape[0] == 577
    assert result.df.drop_nulls().shape[0] == 577
    given_df = result.filter_by_date("2021-10-05 00:00:00+00:00")
    expected_df = pl.DataFrame(
        [
            {
                "station_id": "f674568e",
                "resolution": "10_minutes",
                "dataset": "precipitation",
                "parameter": "precipitation_height",
                "date": dt.datetime(2021, 10, 5, tzinfo=ZoneInfo("UTC")),
                "value": 0.03,
                "distance_mean": 9.38,
                "taken_station_ids": ["04230", "02480", "04411", "07341"],
            },
        ],
        orient="row",
    )
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_interpolation_sunshine_duration_daily(default_settings: Settings) -> None:
    """Test that sunshine_duration can be interpolated (issue #1651)."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "sunshine_duration")],
        start_date=dt.datetime(2021, 6, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2021, 6, 10, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    result = request.interpolate(latlon=(50.0, 8.9))
    assert result.df.shape[0] > 0, "Expected interpolated sunshine_duration values but got none"
    assert result.df.drop_nulls().shape[0] > 0


@pytest.mark.remote
def test_interpolation_snow_depth_new_daily(default_settings: Settings) -> None:
    """Test that snow_depth_new can be interpolated and that the occurrence threshold is applied.

    Result must never be negative or spuriously positive when surrounding stations had no new snow.
    """
    request = DwdObservationRequest(
        parameters=[("daily", "precipitation_more", "snow_depth_new")],
        start_date=dt.datetime(2021, 2, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2021, 2, 10, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    result = request.interpolate(latlon=(50.0, 8.9))
    assert result.df.shape[0] > 0, "Expected interpolated snow_depth_new values but got none"
    # occurrence threshold must prevent negative or NaN values
    values = result.df.drop_nulls().get_column("value")
    assert (values >= 0).all(), "snow_depth_new interpolated values must be non-negative"


def test_not_interpolatable_parameter(default_settings: Settings, df_interpolated_empty: pl.DataFrame) -> None:
    """Test that a parameter that cannot be interpolated is handled correctly."""
    request = DwdObservationRequest(
        parameters=[("hourly", "wind", "wind_direction")],
        start_date=dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 20, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    given_df = request.interpolate(latlon=(50.0, 8.9)).df
    assert given_df.shape[0] == 0
    assert given_df.drop_nulls().shape[0] == 0
    assert_frame_equal(
        given_df,
        df_interpolated_empty,
    )


def test_not_interpolatable_dataset(default_settings: Settings, df_interpolated_empty: pl.DataFrame) -> None:
    """Test that a dataset that cannot be interpolated is handled correctly."""
    request = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "precipitation_form")],
        start_date=dt.datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 2, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    given_df = request.interpolate(latlon=(50.0, 8.9)).df
    assert given_df.shape[0] == 0
    assert given_df.drop_nulls().shape[0] == 0
    assert_frame_equal(
        given_df,
        df_interpolated_empty,
    )


@pytest.mark.remote
def test_provider_dwd_mosmix(default_settings: Settings) -> None:
    """Test a MOSMIX request with date filter."""
    request = DwdMosmixRequest(
        parameters=[("hourly", "small", "temperature_air_mean_2m")],
        start_date=dt.datetime.now(tz=ZoneInfo("UTC")) + dt.timedelta(days=1),
        end_date=dt.datetime.now(tz=ZoneInfo("UTC")) + dt.timedelta(days=8),
        settings=default_settings,
    )
    given_df = request.interpolate(latlon=(50.0, 8.9)).df
    assert given_df.get_column("value").min() >= -40  # equals -40.0°C


def test_interpolation_temperature_air_mean_2m_daily_three_floats(default_settings: Settings) -> None:
    """Test that the interpolation works with three floats."""
    stations = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start_date=dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 20, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    with pytest.raises(ValueError, match="too many values to unpack"):
        stations.interpolate(latlon=(0, 1, 2))


def test_interpolation_temperature_air_mean_2m_daily_one_floats(default_settings: Settings) -> None:
    """Test that an error is raised when not enough values are provided."""
    stations = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start_date=dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 20, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    with pytest.raises(ValueError, match="not enough values to unpack"):
        stations.interpolate(latlon=(0,))


def test_interpolation_temperature_air_mean_2m_daily_no_station_found(default_settings: Settings) -> None:
    """Test that an error is raised when no station is found."""
    stations = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start_date=dt.datetime(2020, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 20, tzinfo=ZoneInfo("UTC")),
        settings=default_settings,
    )
    with pytest.raises(StationNotFoundError, match="no station found for 00000"):
        stations.interpolate_by_station_id(station_id="00")


def test_interpolation_increased_station_distance() -> None:
    """Test that the interpolation works with increased station distance."""
    settings = Settings(ts_geo_station_distance={"precipitation_height": 25})
    request = DwdObservationRequest(
        parameters=[("hourly", "precipitation", "precipitation_height")],
        start_date=dt.datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=dt.datetime(2022, 1, 20, tzinfo=ZoneInfo("UTC")),
        settings=settings,
    )
    values = request.interpolate(latlon=(52.8, 12.9))
    assert values.df.get_column("value").sum() == 21.07


def test_interpolation_error_no_start_date() -> None:
    """Test that an error is raised when start_date is missing."""
    request = DwdObservationRequest(
        parameters=[("hourly", "precipitation", "precipitation_height")],
    )
    with pytest.raises(ValueError, match="start_date and end_date are required for interpolation"):
        request.interpolate(latlon=(52.8, 12.9))
