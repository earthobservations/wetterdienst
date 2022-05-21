# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
=====
About
=====
Example for DWD radar sites data in OPERA HDF5 (ODIM_H5) format using wetterdienst and wradlib. # noqa
Derived from https://gist.github.com/kmuehlbauer/ac990569e6ad38a49412fc74a2035c37.

See also:
- https://docs.wradlib.org/en/stable/notebooks/fileio/wradlib_radar_formats.html#OPERA-HDF5-(ODIM_H5) # noqa

This program will request the most recent complete SWEEP_PCP data
for Essen and plot the outcome with matplotlib.


=====
Setup
=====
::

    brew install gdal
    pip install wradlib

"""  # Noqa:D205,D400
import logging
import os
from itertools import chain

import matplotlib.pyplot as plt
import pytest
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


def plot(data: wrl.io.XRadVolume):
    """Plot radar data with prefixed settings."""
    # Get first sweep in volume.
    swp0 = data[0].data

    # Georeference Data.
    swp0 = swp0.pipe(wrl.georef.georeference_dataset)

    # Plot and display data using cartopy.
    fig = plt.figure(figsize=(20, 8))
    ax1 = fig.add_subplot(121, aspect="equal")
    swp0.DBZH[0].plot(x="x", y="y", ax=ax1)
    ax2 = fig.add_subplot(122, aspect="equal")
    swp0.VRADH[0].plot(x="x", y="y", ax=ax2)


def radar_info(data: wrl.io.XRadVolume):
    """Display data from radar request."""
    print(data)

    print("Keys:", data.root)


@pytest.mark.remote
def radar_scan_precip():
    """Retrieve radar sweep scan of precipitation provided by DWD."""
    request_velocity = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_PCP_VELOCITY_H,
        start_date=DwdRadarDate.MOST_RECENT,
        site=DwdRadarSite.ESS,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.POLARIMETRIC,
    )
    request_reflectivity = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_PCP_REFLECTIVITY_H,
        start_date=DwdRadarDate.MOST_RECENT,
        site=DwdRadarSite.ESS,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.POLARIMETRIC,
    )

    log.info(f"Acquiring radar SWEEP_PCP data for {DwdRadarSite.ESS} at " f"{request_velocity.start_date}")

    # Submit requests.
    results = chain(request_velocity.query(), request_reflectivity.query())

    # Collect list of buffers.
    files = [item.data for item in results]

    # Decode data using wradlib.
    data = wrl.io.open_odim(files)

    # Output debug information.
    radar_info(data)

    # Plot and display data.
    plot(data)
    if "PYTEST_CURRENT_TEST" not in os.environ:
        plt.show()


def main():
    """Run example."""
    radar_scan_precip()


if __name__ == "__main__":
    main()
