# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
=====
About
=====

Example for DWD radar sites data in OPERA HDF5 (ODIM_H5) format using wetterdienst and wradlib. # noqa
Derived from https://gist.github.com/kmuehlbauer/ac990569e6ad38a49412fc74a2035c37.

See also:
- https://docs.wradlib.org/en/stable/notebooks/fileio/wradlib_radar_formats.html#OPERA-HDF5-(ODIM_H5) # noqa

This program will request the most recent complete SWEEP_VOL data
for Essen and plot the outcome with matplotlib.

"""  # Noqa:D205,D400
import logging
import os
from itertools import chain

import matplotlib.pyplot as plt
import wradlib as wrl
import xarray as xr

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


def plot(data: xr.Dataset):
    """Plot radar data with prefixed settings."""
    # Get first sweep in volume.
    swp0 = data.isel({"time": 0})

    # Georeference Data.
    swp0 = swp0.pipe(wrl.georef.georeference_dataset)

    # Plot and display data using cartopy.
    fig = plt.figure(figsize=(20, 8))
    ax1 = fig.add_subplot(121, aspect="equal")
    swp0.DBZH.plot(x="x", y="y", ax=ax1)
    ax2 = fig.add_subplot(122, aspect="equal")
    swp0.VRADH.plot(x="x", y="y", ax=ax2)


def radar_scan_volume():
    """Retrieve radar sweep volume velocity h from site ESS in format HDF5 as subset polarimetric."""
    request_velocity = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
        start_date=DwdRadarDate.MOST_RECENT,
        site=DwdRadarSite.ESS,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.POLARIMETRIC,
    )
    request_reflectivity = DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_VOL_REFLECTIVITY_H,
        start_date=DwdRadarDate.MOST_RECENT,
        site=DwdRadarSite.ESS,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.POLARIMETRIC,
    )

    log.info(f"Acquiring radar SWEEP_VOL data for {DwdRadarSite.ESS} at " f"{request_velocity.start_date}")

    # Submit requests.
    results = chain(request_velocity.query(), request_reflectivity.query())

    # Collect list of buffers.
    files = [item.data for item in results]

    # Sanity checks.
    if not files:
        log.warning("No radar files found for the given constraints")

    # Decode data using wradlib.
    data = wrl.io.open_odim_mfdataset(files)

    # Output debug information.
    print(data)

    # Plot and display data.
    plot(data)
    if "PYTEST_CURRENT_TEST" not in os.environ:
        plt.show()


def main():
    """Run example."""
    radar_scan_volume()


if __name__ == "__main__":
    main()
