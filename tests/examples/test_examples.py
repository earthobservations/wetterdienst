# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD observation examples."""

from pathlib import Path

import pytest

from tests.conftest import ENSURE_ECCODES_PDBUFR, IS_CI, IS_LINUX, IS_WINDOWS


@pytest.mark.xfail(IS_CI and IS_WINDOWS, reason="fails on Windows in CI")
@pytest.mark.cflake
def test_examples() -> None:
    """Test DWD observation examples."""
    from examples.provider.dwd.mosmix import dwd_mosmix_forecasts  # noqa: PLC0415
    from examples.provider.dwd.observation import (  # noqa: PLC0415
        dwd_obs_climate_summary_duckdb_dump,
        dwd_obs_climate_summary_zarr_dump,
        dwd_obs_interpolate,
        dwd_obs_plot_german_weather_stations,
        dwd_obs_plot_hohenpeissenberg_warming_stripes,
        dwd_obs_plot_temperature_timeseries,
        dwd_obs_stations_filter_by_examples,
        dwd_obs_summarize,
        dwd_obs_values_sql,
    )

    assert dwd_mosmix_forecasts.main() is None
    assert dwd_obs_climate_summary_duckdb_dump.main() is None
    assert dwd_obs_climate_summary_zarr_dump.main() is None
    assert dwd_obs_interpolate.main() is None
    assert dwd_obs_plot_german_weather_stations.main() is None
    assert dwd_obs_plot_hohenpeissenberg_warming_stripes.main() is None
    assert dwd_obs_plot_temperature_timeseries.main() is None
    assert dwd_obs_stations_filter_by_examples.main() is None
    assert dwd_obs_summarize.main() is None
    assert dwd_obs_values_sql.main() is None


@pytest.mark.xfail
@pytest.mark.cflake
def test_examples_failing_describe_fields() -> None:
    """Test DWD observation describe fields for daily climate data."""
    from examples.provider.dwd.observation import dwd_obs_climate_summary_describe_fields  # noqa: PLC0415

    assert dwd_obs_climate_summary_describe_fields.main() is None


@pytest.mark.skipif(IS_CI and IS_WINDOWS, reason="problem with storage on Windows in CI")
@pytest.mark.skipif(not ENSURE_ECCODES_PDBUFR, reason="eccodes and pdbufr required")
@pytest.mark.xfail
def test_pdbufr_examples() -> None:
    """Test DWD observation PDBUFR examples."""
    from examples.provider.dwd.road import dwd_road_validation  # noqa: PLC0415

    assert dwd_road_validation.main() is None


@pytest.mark.skipif(IS_CI and IS_LINUX, reason="stalls on Mac/Windows in CI")
@pytest.mark.cflake
def test_gaussian_example(tmp_path: Path) -> None:
    """Test DWD observation Gaussian model example."""
    from examples.provider.dwd.observation import dwd_obs_gaussian_model  # noqa: PLC0415

    assert dwd_obs_gaussian_model.main(tmp_path) is None


@pytest.mark.xfail(reason="UnicodeDecodeError: invalid start byte")
@pytest.mark.cflake
def test_radar_examples() -> None:
    """Test DWD radar examples."""
    pytest.importorskip("wradlib")

    from examples.provider.dwd.radar import (  # noqa: PLC0415
        dwd_radar_composite_rw,
        dwd_radar_radolan_cdc,
        dwd_radar_radolan_rw,
        dwd_radar_scan_precip,
        dwd_radar_scan_volume,
        dwd_radar_site_dx,
        dwd_radar_sweep_hdf5,
    )

    assert dwd_radar_composite_rw.main() is None
    assert dwd_radar_radolan_cdc.main() is None
    assert dwd_radar_radolan_rw.main() is None
    assert dwd_radar_scan_precip.main() is None
    assert dwd_radar_scan_volume.main() is None
    assert dwd_radar_site_dx.main() is None
    assert dwd_radar_sweep_hdf5.main() is None
