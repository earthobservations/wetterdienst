# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD observation API."""

import re
from typing import Literal

import pytest
from dirty_equals import IsApprox

from wetterdienst import Options, Settings
from wetterdienst.exceptions import InvalidParameterError, NoParametersFoundError
from wetterdienst.model.result import ValuesResult
from wetterdienst.provider.dwd.observation import (
    DwdObservationMetadata,
    DwdObservationRequest,
)


@pytest.mark.remote
@pytest.mark.parametrize(
    ("skip_criteria", "expected_stations"),
    [("min", ["05906", "04928"]), ("mean", ["05426", "04177"]), ("max", ["00377", "05426"])],
)
def test_api_skip_empty_stations(
    skip_criteria: Literal["min", "mean", "max"],
    expected_stations: list[str],
) -> None:
    """Test that empty stations are skipped."""
    options = Options(
        skip_criteria=skip_criteria,
        skip_threshold=0.6,
        skip_empty=True,
        drop_nulls=False,
    )
    request = DwdObservationRequest(
        parameters=[("daily", "kl"), ("daily", "solar")],
        start="2021-01-01",
        end="2021-12-31",
        options=options,
    ).filter_by_rank(latlon=(49.19780976647141, 8.135207205143768), rank=2)
    values = request.values().all()
    assert (
        values.df.get_column("station_id").gather(0).to_list()
        != request.df.get_column("station_id").gather(0).to_list()
    )  # not supposed to be the first station of the list
    assert values.df.get_column("station_id").unique(maintain_order=True).to_list() == expected_stations
    assert values.df_stations.get_column("station_id").unique(maintain_order=True).to_list() == expected_stations


@pytest.mark.remote
def test_api_skip_empty_stations_equal_on_any_skip_criteria_with_one_parameter(
    options_skip_empty_true: Options,
) -> None:
    """Test that the same station is returned when only one parameter is requested."""

    def _get_values(options: Options) -> ValuesResult:
        return (
            DwdObservationRequest(
                parameters=[("daily", "climate_summary", "sunshine_duration")],
                start="1990-01-01",
                end="2021-12-31",
                options=options,
            )
            .filter_by_rank(latlon=(49.19780976647141, 8.135207205143768), rank=1)
            .values()
            .all()
        )

    expected_station = ["05426"]

    values = _get_values(options_skip_empty_true.replace(skip_threshold=0.9, skip_criteria="min"))
    assert values.df.get_column("station_id").unique().to_list() == expected_station
    assert values.df_stations.get_column("station_id").to_list() == expected_station

    values = _get_values(options_skip_empty_true.replace(skip_threshold=0.9, skip_criteria="mean"))
    assert values.df.get_column("station_id").unique(maintain_order=True).to_list() == expected_station
    assert values.df_stations.get_column("station_id").to_list() == expected_station

    values = _get_values(options_skip_empty_true.replace(skip_threshold=0.9, skip_criteria="max"))
    assert values.df.get_column("station_id").unique(maintain_order=True).to_list() == expected_station
    assert values.df_stations.get_column("station_id").to_list() == expected_station


@pytest.mark.remote
def test_api_drop_nulls(default_settings: Settings) -> None:
    """Test that null values are dropped."""
    request = DwdObservationRequest(
        parameters=[
            ("minute_10", "temperature_air"),
            ("minute_10", "precipitation"),
        ],
        start="2021-01-01",
        end="2021-12-31",
        settings=default_settings,
    ).filter_by_rank(latlon=(49.19780976647141, 8.135207205143768), rank=20)
    values = next(request.values().query())
    assert values.df.shape[0] == IsApprox(52193, delta=5000)


def test_api_no_valid_parameters(default_settings: Settings) -> None:
    """Test that a parameter that does not exist is refused, naming it, by default (GH-2636)."""
    with pytest.raises(InvalidParameterError, match=re.escape("daily/abc not found in DwdObservationMetadata")):
        DwdObservationRequest(
            parameters=[
                ("daily", "abc"),
            ],
            settings=default_settings,
        )


def test_api_no_valid_parameters_with_on_unknown_warn(default_settings: Settings) -> None:
    """Test that an error is raised when no valid parameters are found, however unknown ones are handled.

    The message names the concrete request, not the abstract base, so it says which provider and
    network the parameters were looked for in.
    """
    with pytest.raises(
        NoParametersFoundError,
        match=re.escape("No valid parameters could be parsed from [('daily', 'abc')] for DwdObservationRequest"),
    ):
        DwdObservationRequest(
            parameters=[
                ("daily", "abc"),
            ],
            settings=default_settings,
            on_unknown="warn",
        )


def test_api_no_valid_parameters_from_iterator(default_settings: Settings) -> None:
    """Test that the message names the values an iterator held, not the iterator it consumed."""
    with pytest.raises(
        NoParametersFoundError,
        match=re.escape("No valid parameters could be parsed from ['daily/abc'] for DwdObservationRequest"),
    ):
        DwdObservationRequest(parameters=iter(["daily/abc"]), settings=default_settings, on_unknown="warn")


def test_api_partly_valid_parameters(default_settings: Settings, caplog: pytest.LogCaptureFixture) -> None:
    """Test that on_unknown="warn" ignores the invalid parameters, as every request did before (GH-2636)."""
    request = DwdObservationRequest(
        parameters=[
            ("daily", "temperature_air"),
            ("daily", "wind"),
            ("daily", "precipitation"),
            ("daily", "solar"),
        ],
        settings=default_settings,
        on_unknown="warn",
    )
    assert "daily/wind not found in DwdObservationMetadata" in caplog.text
    assert "daily/precipitation not found in DwdObservationMetadata" in caplog.text
    assert request.parameters == [*DwdObservationMetadata.daily.solar]
