# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
=====
About
=====

Example for DWD radar sites OPERA HDF5 (ODIM_H5) format using wetterdienst and wradlib.

See also:
- https://docs.wradlib.org/en/stable/notebooks/fileio/wradlib_radar_formats.html#OPERA-HDF5-(ODIM_H5) # noqa

This program will request the latest RADAR SWEEP_PCP_VELOCITY_H data
for Boostedt and plot the outcome with matplotlib.

"""  # Noqa:D205,D400
import logging
import os

import matplotlib.pyplot as plt
import numpy as np
import wradlib as wrl

from wetterdienst.provider.dwd.radar import (
    DwdRadarDataFormat,
    DwdRadarDataSubset,
    DwdRadarDate,
    DwdRadarParameter,
    DwdRadarSite,
    DwdRadarValues,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()


def plot(data: np.ndarray):
    """Plot radar data with prefixed settings."""
    fig = plt.figure(figsize=(10, 8))
    wrl.vis.plot_ppi(data["dataset1/data1/data"], fig=fig, proj="cg")


def radar_info(data: dict):
    """Display data from radar request."""
    print("Keys:", data.keys())

    log.info("Data")
    for key, value in data.items():
        print(f"- {key}: {value}")


def radar_hdf5_example():
    """Retrieve HDF5 data by DWD as example."""
    log.info("Acquiring radar sweep data in HDF5")
    request = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_PCP_VELOCITY_H,
        start_date=DwdRadarDate.MOST_RECENT,
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.SIMPLE,
    )

    for item in request.query():

        # Decode data using wradlib.
        log.info(f"Parsing radar data for {request.site} at '{item.timestamp}'")
        data = wrl.io.read_opera_hdf5(item.data)

        # Output debug information.
        radar_info(data)

        # Plot and display data.
        plot(data)
        if "PYTEST_CURRENT_TEST" not in os.environ:
            plt.show()


def main():
    """Run example."""
    radar_hdf5_example()


if __name__ == "__main__":
    main()
