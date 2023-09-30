# -*- coding: utf-8 -*-
# Copyright (C) 2018-2023, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
=====
About
=====

Example for DWD RADOLAN Composite RW using wetterdienst and wradlib.

See also:
- https://docs.wradlib.org/en/stable/notebooks/radolan/radolan_showcase.html.

This program will request daily (RADOLAN SF) data for 2020-09-04T12:00:00
and plot the outcome with matplotlib.

"""  # Noqa:D205,D400
import logging
import os

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from wetterdienst.provider.dwd.radar import DwdRadarValues
from wetterdienst.provider.dwd.radar.metadata import DwdRadarDate, DwdRadarParameter

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()


def plot(ds: xr.Dataset):
    """Plot RADOLAN data.

    Shamelessly stolen from the wradlib RADOLAN Product Showcase documentation.
    https://docs.wradlib.org/en/stable/notebooks/fileio/radolan/radolan_showcase.html

    Thanks!
    """
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, aspect="equal")
    pm = ds.RW.plot(ax=ax, cmap="viridis", shading="auto")
    plt.title("{0} Product\n{1}".format(attrs["producttype"], attrs["datetime"].isoformat()))
    plt.grid(color="r")


def radar_info(ds: xr.Dataset):
    """Display metadata from RADOLAN request."""
    print(ds)


def radar_rw_example():
    """Retrieve radar rw reflectivity data by DWD."""
    log.info("Acquiring radar RW composite data")
    radolan = DwdRadarValues(
        parameter=DwdRadarParameter.RW_REFLECTIVITY,
        start_date=DwdRadarDate.LATEST,
    )

    for item in radolan.query():
        # Decode data using wradlib radolan backend to xarray.
        log.info("Parsing radar RW composite data for %s", item.timestamp)
        ds = xr.open_dataset(item.data, engine="radolan")

        radar_info(ds)

        # Plot and display data.
        plot(ds)
        if "PYTEST_CURRENT_TEST" not in os.environ:
            plt.show()


def main():
    """Run example."""
    radar_rw_example()


if __name__ == "__main__":
    main()
