# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD observation examples."""

from pathlib import Path, PureWindowsPath

import pytest

from tests.conftest import BUFR_AVAILABLE, IS_CI, IS_LINUX, IS_PYTHON_3_10, IS_WINDOWS
from wetterdienst.util.url import ConnectionString


@pytest.mark.xfail(IS_CI and IS_WINDOWS, reason="fails on Windows in CI")
@pytest.mark.cflake
def test_examples() -> None:
    """Test DWD observation examples."""
    from examples.provider.dwd.mosmix import dwd_mosmix_forecasts  # noqa: PLC0415
    from examples.provider.dwd.observation import (  # noqa: PLC0415
        dwd_obs_climate_summary_duckdb_dump,
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
    assert dwd_obs_interpolate.main() is None
    assert dwd_obs_plot_german_weather_stations.main() is None
    assert dwd_obs_plot_hohenpeissenberg_warming_stripes.main() is None
    assert dwd_obs_plot_temperature_timeseries.main() is None
    assert dwd_obs_stations_filter_by_examples.main() is None
    assert dwd_obs_summarize.main() is None
    assert dwd_obs_values_sql.main() is None


@pytest.mark.skipif(IS_PYTHON_3_10, reason="zarr not supported in Python 3.10")
@pytest.mark.cflake
def test_examples_zarr() -> None:
    """Test DWD observation examples with Zarr.

    Zarr is not supported in Python 3.10, so this test is skipped.
    """
    from examples.provider.dwd.observation import dwd_obs_climate_summary_zarr_dump  # noqa: PLC0415

    assert dwd_obs_climate_summary_zarr_dump.main() is None


@pytest.mark.cflake
def test_examples_failing_describe_fields() -> None:
    """Test DWD observation describe fields for daily climate data."""
    from examples.provider.dwd.observation import dwd_obs_climate_summary_describe_fields  # noqa: PLC0415

    assert dwd_obs_climate_summary_describe_fields.main() is None


@pytest.mark.skipif(IS_CI and IS_WINDOWS, reason="problem with storage on Windows in CI")
@pytest.mark.skipif(not BUFR_AVAILABLE, reason="eccodes and pdbufr required")
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


@pytest.mark.cflake
def test_the_duckdb_example_writes_outside_the_repository_under_pytest() -> None:
    """Running the examples must not leave the working tree dirty.

    The dump is a smoke test here rather than an artifact -- it writes one station's values and
    throws them away -- but it used to write to the tracked file, so every test run modified a 1.3
    MB binary in the repository. That has twice been committed by accident along with unrelated
    work, which is how it was noticed.
    """
    import subprocess  # noqa: PLC0415

    from examples.provider.dwd.observation import dwd_obs_climate_summary_duckdb_dump  # noqa: PLC0415

    tracked = Path("examples/provider/dwd/dwd_obs_daily_climate_summary.duckdb")
    before = subprocess.run(  # noqa: S603
        ["git", "status", "--porcelain", "--", str(tracked)],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    assert dwd_obs_climate_summary_duckdb_dump.main() is None

    after = subprocess.run(  # noqa: S603
        ["git", "status", "--porcelain", "--", str(tracked)],  # noqa: S607
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    assert after == before, f"the example modified {tracked}"


@pytest.mark.parametrize(
    "path",
    [
        Path("/var/folders/rk/dwd_obs_daily_climate_summary.duckdb"),
        PureWindowsPath(r"C:\Users\RUNNER~1\AppData\Local\Temp\dwd_obs_daily_climate_summary.duckdb"),
    ],
    ids=["posix-absolute", "windows-absolute"],
)
def test_the_duckdb_example_addresses_the_file_it_was_given(path: Path) -> None:
    r"""Read the example's own target back the way ``to_target`` reads it.

    The wrong slash count is silent on POSIX -- a doubled ``//`` still resolves -- so running the
    example here would not catch it coming back. On Windows it is ``Cannot open file "//C:\..."``,
    DuckDB reading the leftover slash as a UNC share, and the matrix is where that shows up.
    """
    from examples.provider.dwd.observation import dwd_obs_climate_summary_duckdb_dump  # noqa: PLC0415

    target = dwd_obs_climate_summary_duckdb_dump.duckdb_target(path, "stations")

    connspec = ConnectionString(target)
    assert connspec.database == str(path)
    assert connspec.table == "stations"
