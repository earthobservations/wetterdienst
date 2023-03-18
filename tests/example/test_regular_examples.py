# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from pathlib import Path

import pytest

HERE = Path(__name__).parent.absolute()
EXAMPLES_DIR = HERE.parent.parent / "example"


@pytest.mark.cflake
def test_regular_examples():
    from example import (
        dwd_describe_fields,
        mosmix_forecasts,
        observations_sql,
        observations_stations,
    )

    assert dwd_describe_fields.main() is None
    assert mosmix_forecasts.main() is None
    assert observations_sql.main() is None
    assert observations_stations.main() is None


@pytest.mark.cflake
def test_gaussian_example(is_ci, is_linux):
    if is_ci and not is_linux:
        raise pytest.skip("stalls on Mac/Windows in CI")
    from example import observations_station_gaussian_model

    assert observations_station_gaussian_model.main() is None


@pytest.mark.cflake
def test_radar_examples():
    pytest.importorskip("wradlib")
    from example.radar import (
        radar_composite_rw,
        radar_radolan_cdc,
        radar_radolan_rw,
        radar_scan_precip,  # noqa:F401
        radar_scan_volume,  # noqa:F401
        radar_site_dx,
        radar_sweep_hdf5,
    )

    assert radar_composite_rw.main() is None
    assert radar_radolan_cdc.main() is None
    assert radar_radolan_rw.main() is None
    assert radar_site_dx.main() is None
    assert radar_sweep_hdf5.main() is None


@pytest.mark.cflake
def test_radar_examples_gdal(is_ci, is_linux_311):
    if is_ci:
        if not is_linux_311:
            pytest.skip("on CI gdal is only installed on ubuntu-latest and python 3.11")
    pytest.importorskip("wradlib")
    from example.radar import (
        radar_scan_precip,
        radar_scan_volume,
    )

    assert radar_scan_precip.main() is None
    assert radar_scan_volume.main() is None
