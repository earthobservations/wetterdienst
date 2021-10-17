# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from pathlib import Path

import pytest

from example import (
    dwd_describe_fields,
    mosmix_forecasts,
    observations_sql,
    observations_stations,
)

THIS = Path(__name__).parent.absolute()
EXAMPLES_DIR = THIS.parent.parent / "example"

EXAMPLES = (
    mosmix_forecasts,
    observations_sql,
    observations_stations,
    dwd_describe_fields,
)


@pytest.mark.cflake
@pytest.mark.parametrize("example", EXAMPLES)
def test_regular_examples(example):
    assert example.main() is None


@pytest.mark.cflake
def test_radar_examples():

    pytest.importorskip("osgeo.gdal")

    from example.radar import (
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
