# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD derived station data."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from dirty_equals import IsDatetime, IsDict
from polars.testing import assert_frame_equal

from wetterdienst import Settings
from wetterdienst.exceptions import InvalidEnumerationError
from wetterdienst.provider.dwd.derived.api import DwdDerivedRequest


@pytest.fixture
def expected_df() -> pl.DataFrame:
    """Provide expected DataFrame for station."""
    return pl.DataFrame(
        [
            {
                "resolution": "monthly",
                "dataset": "heating_degreedays",
                "station_id": "00433",
                "start_date": dt.datetime(1938, 1, 1, tzinfo=ZoneInfo("UTC")),
                "end_date": dt.datetime(2025, 10, 31, tzinfo=ZoneInfo("UTC")),
                "latitude": 52.4676,
                "longitude": 13.4020,
                "height": 48.0,
                "name": "Berlin-Tempelhof",
                "state": "Berlin",
            },
        ],
        orient="row",
    )


@pytest.mark.remote
@pytest.mark.parametrize(
    "period",
    [
        "historical",
        "recent",
    ],
    ids=[
        "fetching_derived_station_00433_with_period_historical",
        "fetching_derived_station_00433_with_period_recent",
    ],
)
def test_dwd_derived_stations_filter(default_settings: Settings, expected_df: pl.DataFrame, period: str) -> None:
    """Test to check station ID filter."""
    request = DwdDerivedRequest(
        parameters=("monthly", "heating_degreedays"),
        periods=period,
        settings=default_settings,
    ).filter_by_station_id(station_id="00433")
    given_df = request.df
    assert_frame_equal(given_df, expected_df)


def test_dwd_derived_stations_filter_false_period(default_settings: Settings) -> None:
    """Test to check for error on unknown period."""
    period = "hadean"
    with pytest.raises(InvalidEnumerationError) as exception_info:
        DwdDerivedRequest(
            parameters=("monthly", "heating_degreedays"),
            periods=period,
            settings=default_settings,
        ).filter_by_station_id(station_id="00433")
    assert exception_info.match(f"{period} could not be parsed from Period.")


@pytest.mark.remote
def test_dwd_derived_stations_filter_name(default_settings: Settings, expected_df: pl.DataFrame) -> None:
    """Test fetching of DWD derived stations with filter by name."""
    # Existing combination of parameters
    request = DwdDerivedRequest(
        parameters=[("monthly", "heating_degreedays")],
        periods="historical",
        settings=default_settings,
    ).filter_by_name(name="Berlin-Tempelhof")
    given_df = request.df
    assert_frame_equal(given_df, expected_df)


@pytest.mark.remote
def test_dwd_observations_stations_name_with_comma() -> None:
    """Test fetching of DWD observation stations."""
    request = DwdDerivedRequest(
        parameters=[("monthly", "heating_degreedays")],
        periods="recent",
    )
    stations = request.all()
    stations = stations.df.filter(pl.col("station_id").is_in(["00183", "03287", "04806", "19172"]))
    assert stations.to_dicts() == [
        IsDict(
            {
                "resolution": "monthly",
                "dataset": "heating_degreedays",
                "station_id": "00183",
                "start_date": dt.datetime(1936, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "end_date": IsDatetime,
                "latitude": 54.6791,
                "longitude": 13.4344,
                "height": 42.0,
                "name": "Arkona",
                "state": "Mecklenburg-Vorpommern",
            },
        ),
        IsDict(
            {
                "resolution": "monthly",
                "dataset": "heating_degreedays",
                "station_id": "03287",
                "start_date": dt.datetime(1987, 10, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "end_date": IsDatetime,
                "latitude": 49.7177,
                "longitude": 9.0997,
                "height": 453.0,
                "name": "Michelstadt-Vielbrunn",
                "state": "Hessen",
            },
        ),
        IsDict(
            {
                "resolution": "monthly",
                "dataset": "heating_degreedays",
                "station_id": "04806",
                "start_date": dt.datetime(1882, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "end_date": dt.datetime(1983, 12, 31, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "latitude": 50.7832,
                "longitude": 11.0880,
                "height": 370.0,
                "name": "Stadtilm",
                "state": "Thüringen",
            },
        ),
        IsDict(
            {
                "resolution": "monthly",
                "dataset": "heating_degreedays",
                "station_id": "19172",
                "start_date": dt.datetime(2020, 9, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
                "end_date": IsDatetime,
                "latitude": 54.0246,
                "longitude": 9.3880,
                "height": 48.0,
                "name": "Wacken",
                "state": "Schleswig-Holstein",
            },
        ),
    ]


@pytest.mark.remote
@pytest.mark.parametrize(
    (
        "station_id",
        "period",
    ),
    [
        (
            "ab123",
            "recent",
        ),
        (
            "ab123",
            "historical",
        ),
        (
            "",
            "recent",
        ),
        (
            "",
            "historical",
        ),
    ],
    ids=[
        "non_existent_dwd_derived_station_id_and_recent_period",
        "non_existent_dwd_derived_station_id_and_historical_period",
        "missing_dwd_derived_station_id_and_recent_period",
        "missing_dwd_derived_station_id_and_historical_period",
    ],
)
def test_dwd_derived_stations_filter_misentries(
    default_settings: Settings,
    station_id: str,
    period: str,
) -> None:
    """Test to check for handling of missing or incorrect parameter inputs."""
    request = DwdDerivedRequest(
        parameters=("monthly", "heating_degreedays"),
        periods=period,
        settings=default_settings,
    ).filter_by_station_id(station_id=station_id)
    assert request.df.is_empty()


def test_generate_digit_combinations() -> None:
    """Test to check digit combination generation."""
    request = DwdDerivedRequest(
        parameters=("monthly", "climate_correction_factor"),
    )
    generated_combinations = request._generate_digit_combinations(  # noqa: SLF001
        number_of_digits=1,
    )
    assert list(generated_combinations) == ["0", "1", "2", "3", "4", "5", "6", "7", "8", "9"]

    for number_of_digits in range(2, 6):
        generated_combinations = list(
            request._generate_digit_combinations(  # noqa: SLF001
                number_of_digits=number_of_digits,
            )
        )
        assert len(generated_combinations) == 10**number_of_digits
        assert all(len(combination) == number_of_digits for combination in generated_combinations)


def test_get_raw_station_data_from_plz_generator() -> None:
    """Test to check dimensions of proxy PLZ station data."""
    request = DwdDerivedRequest(
        parameters=("monthly", "climate_correction_factor"),
    )
    raw_station_data = request._get_raw_station_data_from_plz_generator().collect()  # noqa: SLF001
    assert raw_station_data.shape == (10**5, 8)
