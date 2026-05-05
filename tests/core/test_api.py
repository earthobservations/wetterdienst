# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD observation API."""

import asyncio

import pytest

from wetterdienst import Settings
from wetterdienst.exceptions import NoParametersFoundError
from wetterdienst.model.result import ValuesResult
from wetterdienst.provider.dwd.observation import (
    DwdObservationMetadata,
    DwdObservationRequest,
)


@pytest.mark.remote
def test_api_skip_empty_stations() -> None:
    """Test that ts_skip_empty filters stations and that the three criteria are ordered.

    With two parameters (kl + solar), the fill-rate criteria satisfy
    min(f1,f2) ≤ mean(f1,f2) ≤ max(f1,f2) for any station, so:

        stations_passing_min ⊆ stations_passing_mean ⊆ stations_passing_max

    Asserting this subset ordering directly verifies that the production code
    actually applies the ts_skip_criteria setting: an implementation that
    ignored it (e.g. always using "mean") would produce identical sets for all
    three calls, making the strict-subset assertion fail whenever at least one
    station sits between the min and max thresholds.
    """

    def _get_values(criteria: str) -> ValuesResult | None:
        settings = Settings(
            ts_skip_criteria=criteria,
            ts_skip_threshold=0.6,
            ts_skip_empty=True,
            ts_complete=True,
            ts_drop_nulls=False,
        )
        try:
            return (
                DwdObservationRequest(
                    parameters=[("daily", "kl"), ("daily", "solar")],
                    start_date="2021-01-01",
                    end_date="2021-12-31",
                    settings=settings,
                )
                .filter_by_rank(latlon=(49.19780976647141, 8.135207205143768), rank=5)
                .values.all()
            )
        except (OSError, asyncio.TimeoutError, IndexError) as e:
            pytest.skip(f"Network or DWD server error: {e}")

    values_min = _get_values("min")
    values_mean = _get_values("mean")
    values_max = _get_values("max")

    if values_max is None or values_max.df.is_empty():
        pytest.skip("No data returned from DWD, possibly a network issue on this runner")

    def _station_ids(v: ValuesResult) -> set[str]:
        if v is None or v.df.is_empty():
            return set()
        return set(v.df.get_column("station_id").unique().to_list())

    ids_min = _station_ids(values_min)
    ids_mean = _station_ids(values_mean)
    ids_max = _station_ids(values_max)

    # df_stations must mirror the stations present in df for each criterion
    for label, v, ids in [("min", values_min, ids_min), ("mean", values_mean, ids_mean), ("max", values_max, ids_max)]:
        if v is not None and not v.df.is_empty():
            assert ids == set(v.df_stations.get_column("station_id").to_list()), (
                f"df_stations inconsistent with df for criteria={label!r}"
            )

    # min(f1,f2) ≤ mean(f1,f2) ≤ max(f1,f2)  →  pass_min ⊆ pass_mean ⊆ pass_max
    assert ids_min.issubset(ids_mean), (
        f"Stations passing 'min' must be a subset of those passing 'mean'.\n"
        f"  min={sorted(ids_min)}\n  mean={sorted(ids_mean)}"
    )
    assert ids_mean.issubset(ids_max), (
        f"Stations passing 'mean' must be a subset of those passing 'max'.\n"
        f"  mean={sorted(ids_mean)}\n  max={sorted(ids_max)}"
    )


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
