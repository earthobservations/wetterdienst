# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import sys
from pathlib import Path

import pytest

from tests.conftest import ENSURE_ECCODES_PDBUFR, IS_CI, IS_LINUX

HERE = Path(__name__).parent.absolute()
EXAMPLES_DIR = HERE.parent.parent / "example"


@pytest.mark.cflake
def test_examples():
    from examples import (
        dwd_climate_summary_xarray_dump,
        dwd_describe_fields,
        mosmix_forecasts,
        observations_sql,
        observations_stations,
        plot_german_weather_stations,
        plot_hohenpeissenberg_warming_stripes,
        plot_temperature_timeseries,
    )

    assert dwd_describe_fields.main() is None
    assert mosmix_forecasts.main() is None
    if sys.version_info < (3, 12):
        assert observations_sql.main() is None
    assert observations_stations.main() is None
    assert dwd_climate_summary_xarray_dump.main() is None
    assert plot_german_weather_stations.main() is None
    assert plot_hohenpeissenberg_warming_stripes.main() is None
    assert plot_temperature_timeseries.main() is None


@pytest.mark.skipif(not ENSURE_ECCODES_PDBUFR, reason="eccodes and pdbufr required")
def test_pdbufr_examples():
    from examples import dwd_road_weather

    assert dwd_road_weather.main() is None


@pytest.mark.skipif(IS_CI and IS_LINUX, reason="stalls on Mac/Windows in CI")
@pytest.mark.cflake
def test_gaussian_example(tmp_path):
    from examples import observations_station_gaussian_model

    assert observations_station_gaussian_model.main(tmp_path) is None


@pytest.mark.cflake
def test_radar_examples():
    pytest.importorskip("wradlib")
    from examples.radar import (
        radar_composite_rw,
        radar_radolan_cdc,
        radar_radolan_rw,
        radar_scan_precip,
        radar_scan_volume,
        radar_site_dx,
        radar_sweep_hdf5,
    )

    assert radar_composite_rw.main() is None
    assert radar_radolan_cdc.main() is None
    assert radar_radolan_rw.main() is None
    assert radar_scan_precip.main() is None
    assert radar_scan_volume.main() is None
    assert radar_site_dx.main() is None
    assert radar_sweep_hdf5.main() is None
