# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
=====
About
=====

Example for DWD radar sites DX using wetterdienst and wradlib.

The German Weather Service uses the DX file format to encode
local radar sweeps. DX data are in polar coordinates.

See also:
- https://docs.wradlib.org/en/stable/notebooks/fileio/legacy/read_dx.html

This program will request the latest RADAR DX data
for Boostedt and plot the outcome with matplotlib.

"""  # noqa:D205,D400,E501

import logging
import os

import matplotlib.pyplot as plt
import numpy as np
import wradlib as wrl
import xarray as xr

from wetterdienst.provider.dwd.radar import (
    DwdRadarDate,
    DwdRadarParameter,
    DwdRadarSite,
    DwdRadarValues,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()


def plot(data: xr.DataArray):
    """Plot radar data with prefixed settings."""
    fig = plt.figure(figsize=(10, 8))
    data.wrl.vis.plot(fig=fig, crs="cg")


def radar_info(data: np.ndarray, metadata: dict):
    """Display metadata from radar request."""
    log.info("Data shape: %s", data.shape)

    log.info("Metadata")
    for key, value in metadata.items():
        print(f"- {key}: {value}")


def radar_dx_example():
    """Retrieve radar dx reflectivity data by DWD."""
    log.info("Acquiring radar DX data")
    request = DwdRadarValues(
        parameter=DwdRadarParameter.DX_REFLECTIVITY,
        start_date=DwdRadarDate.LATEST,
        site=DwdRadarSite.BOO,
    )

    for item in request.query():
        # Decode data using wradlib.
        log.info(f"Parsing radar data for {request.site} at '{item.timestamp}'")
        data, metadata = wrl.io.read_dx(item.data)

        da = wrl.georef.create_xarray_dataarray(data).wrl.georef.georeference()

        # Output debug information.
        radar_info(data, metadata)

        # Plot and display data.
        plot(da)
        if "PYTEST_CURRENT_TEST" not in os.environ:
            plt.show()


def main():
    """Run example."""
    radar_dx_example()


if __name__ == "__main__":
    main()
