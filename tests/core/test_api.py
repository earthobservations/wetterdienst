# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD observation API."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

import polars as pl
import pytest

from wetterdienst import Settings
from wetterdienst.exceptions import NoParametersFoundError
from wetterdienst.provider.dwd.observation import (
    DwdObservationMetadata,
    DwdObservationRequest,
)

if TYPE_CHECKING:
    from wetterdienst.model.result import ValuesResult

_SKIP_EMPTY_LATLON = (49.19780976647141, 8.135207205143768)
# A single multi-parameter dataset keeps downloads small (one ZIP per station)
# while still allowing min/mean/max fill rates to differ across its parameters.
_SKIP_EMPTY_PARAMETERS = [("daily", "kl")]
_SKIP_EMPTY_START = "2021-01-01"
_SKIP_EMPTY_END = "2021-12-31"
_SKIP_EMPTY_THRESHOLD = 0.6
_SKIP_EMPTY_RANK = 3


def _skip_empty_get_values(criteria: str) -> ValuesResult:
    """Collect the nearest *_SKIP_EMPTY_RANK* passing stations under *criteria*.

    filter_by_rank is used directly so only a handful of station ZIPs are
    downloaded, keeping each test fast even on a cold cache.
    ts_complete=True pads the date range with nulls so fill rates are well-defined.
    """
    settings = Settings(
        ts_skip_criteria=criteria,
        ts_skip_threshold=_SKIP_EMPTY_THRESHOLD,
        ts_skip_empty=True,
        ts_complete=True,
        ts_drop_nulls=False,
    )
    try:
        return (
            DwdObservationRequest(
                parameters=_SKIP_EMPTY_PARAMETERS,
                start_date=_SKIP_EMPTY_START,
                end_date=_SKIP_EMPTY_END,
                settings=settings,
            )
            .filter_by_rank(latlon=_SKIP_EMPTY_LATLON, rank=_SKIP_EMPTY_RANK)
            .values.all()
        )
    except (OSError, asyncio.TimeoutError, IndexError) as e:
        pytest.skip(f"Network or DWD server error: {e}")


def _skip_empty_assert_fill_rate(values: ValuesResult, criteria: str, agg_expr: pl.Expr) -> None:
    """Assert that every station in *values* satisfies the fill-rate criterion.

    ts_complete pads missing dates with nulls before the skip check is applied,
    so fill rates computed from values.df match what the production code used.
    """
    if values.df.is_empty():
        pytest.skip("No data returned from DWD, possibly a network issue on this runner")

    # Verify df_stations is consistent with df.
    returned_ids = set(values.df.get_column("station_id").unique().to_list())
    assert returned_ids == set(values.df_stations.get_column("station_id").to_list()), (
        f"df_stations inconsistent with df for criteria={criteria!r}"
    )

    # For each returned station compute the aggregated fill rate across all parameters.
    fill_by_station = (
        values.df.group_by(["station_id", "parameter"])
        .agg((pl.col("value").drop_nulls().len() / pl.col("value").len()).cast(pl.Float64).alias("fill_rate"))
        .group_by("station_id")
        .agg(agg_expr.alias("criterion_fill"))
    )
    violations = fill_by_station.filter(pl.col("criterion_fill") < _SKIP_EMPTY_THRESHOLD)
    assert violations.is_empty(), (
        f"ts_skip_criteria={criteria!r} returned stations whose {criteria}(fill_rate) < {_SKIP_EMPTY_THRESHOLD}:\n"
        f"{violations}"
    )


@pytest.mark.remote
def test_api_skip_empty_stations_min() -> None:
    """Min criterion: every returned station has min(fill_rates_per_parameter) >= threshold.

    The 'min' aggregation is the strictest: a station passes only when *all* its
    parameters meet the fill-rate threshold.
    """
    values = _skip_empty_get_values("min")
    _skip_empty_assert_fill_rate(values, "min", pl.col("fill_rate").min())


@pytest.mark.remote
def test_api_skip_empty_stations_mean() -> None:
    """Mean criterion: every returned station has mean(fill_rates_per_parameter) >= threshold.

    The 'mean' aggregation is intermediate: a station passes when the average fill
    rate across parameters meets the threshold even if some individual parameters fall
    below it.
    """
    values = _skip_empty_get_values("mean")
    _skip_empty_assert_fill_rate(values, "mean", pl.col("fill_rate").mean())


@pytest.mark.remote
def test_api_skip_empty_stations_max() -> None:
    """Max criterion: every returned station has max(fill_rates_per_parameter) >= threshold.

    The 'max' aggregation is the most lenient: a station passes when *any* of its
    parameters meets the fill-rate threshold.
    """
    values = _skip_empty_get_values("max")
    _skip_empty_assert_fill_rate(values, "max", pl.col("fill_rate").max())


@pytest.mark.remote
def test_api_skip_empty_stations_equal_on_any_skip_criteria_with_one_parameter(
    settings_drop_nulls_false_complete_true_skip_empty_true: Settings,
) -> None:
    """Test that the same station is returned regardless of the skip criteria.

    When only one parameter is requested, min/mean/max fill rates are identical,
    so all three criteria must return the same station.
    """
    settings = settings_drop_nulls_false_complete_true_skip_empty_true
    settings.ts_skip_threshold = 0.9

    # Pin the nearest station ID once so that all three criteria calls below are
    # guaranteed to evaluate the exact same station.  Using filter_by_rank(rank=1)
    # for each criteria call independently would allow the skip logic to silently
    # fall through to a *different* second-nearest station when the nearest one is
    # skipped, making the comparison meaningless.
    try:
        nearest_station = (
            DwdObservationRequest(
                parameters=[("daily", "climate_summary", "sunshine_duration")],
                start_date="1990-01-01",
                end_date="2021-12-31",
                settings=settings,
            )
            .filter_by_rank(latlon=(49.19780976647141, 8.135207205143768), rank=1)
            .df.get_column("station_id")
            .head(1)
            .item()
        )
    except (OSError, asyncio.TimeoutError, IndexError, ValueError) as e:
        pytest.skip(f"Network or DWD server error during station lookup: {e}")

    def _get_values(criteria: str) -> ValuesResult:
        settings.ts_skip_criteria = criteria
        return (
            DwdObservationRequest(
                parameters=[("daily", "climate_summary", "sunshine_duration")],
                start_date="1990-01-01",
                end_date="2021-12-31",
                settings=settings,
            )
            .filter_by_station_id(station_id=[nearest_station])
            .values.all()
        )

    try:
        values_min = _get_values("min")
        values_mean = _get_values("mean")
        values_max = _get_values("max")
    except (OSError, asyncio.TimeoutError, IndexError) as e:
        pytest.skip(f"Network or DWD server error: {e}")

    if values_min.df.is_empty() and values_mean.df.is_empty() and values_max.df.is_empty():
        pytest.skip("No data returned from DWD, possibly a network issue on this runner")

    # With a single parameter min/mean/max of the fill-rate series are identical,
    # so all three criteria must agree on whether to return or skip the station.
    assert values_min.df.is_empty() == values_mean.df.is_empty() == values_max.df.is_empty(), (
        f"Expected all three skip criteria to agree for station {nearest_station} with a "
        f"single parameter, but got: min_empty={values_min.df.is_empty()}, "
        f"mean_empty={values_mean.df.is_empty()}, max_empty={values_max.df.is_empty()}"
    )
    if not values_min.df.is_empty():
        # df_stations must be consistent for each result
        assert values_min.df_stations.get_column("station_id").to_list() == [nearest_station]
        assert values_mean.df_stations.get_column("station_id").to_list() == [nearest_station]
        assert values_max.df_stations.get_column("station_id").to_list() == [nearest_station]


@pytest.mark.remote
def test_api_drop_nulls(default_settings: Settings) -> None:
    """Test that null values are dropped."""
    request = DwdObservationRequest(
        parameters=[
            ("minute_10", "temperature_air"),
            ("minute_10", "precipitation"),
        ],
        start_date="2021-01-01",
        end_date="2021-12-31",
        settings=default_settings,
    ).filter_by_rank(latlon=(49.19780976647141, 8.135207205143768), rank=20)
    values = next(request.values.query())
    assert values.df.shape[0] == 52193


def test_api_no_valid_parameters(default_settings: Settings) -> None:
    """Test that an error is raised when no valid parameters are found."""
    with pytest.raises(NoParametersFoundError):
        DwdObservationRequest(
            parameters=[
                ("daily", "abc"),
            ],
            settings=default_settings,
        )


def test_api_partly_valid_parameters(default_settings: Settings, caplog: pytest.LogCaptureFixture) -> None:
    """Test that invalid parameters are ignored."""
    request = DwdObservationRequest(
        parameters=[
            ("daily", "temperature_air"),
            ("daily", "wind"),
            ("daily", "precipitation"),
            ("daily", "solar"),
        ],
        settings=default_settings,
    )
    assert "daily/wind not found in DwdObservationMetadata" in caplog.text
    assert "daily/precipitation not found in DwdObservationMetadata" in caplog.text
    assert request.parameters == [*DwdObservationMetadata.daily.solar]
