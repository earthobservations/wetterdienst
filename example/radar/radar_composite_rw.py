# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
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


=====
Setup
=====
::

    brew install gdal
    pip install wradlib

"""  # Noqa:D205,D400
import logging
import os

import matplotlib.pyplot as plt
import numpy as np
import wradlib as wrl

from wetterdienst.provider.dwd.radar import DwdRadarValues
from wetterdienst.provider.dwd.radar.metadata import DwdRadarDate, DwdRadarParameter

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()


def plot(data: np.ndarray, attributes: dict, label: str = None):
    """Plot RADOLAN data with prefixed settings."""
    # Get coordinates.
    radolan_grid_xy = wrl.georef.get_radolan_grid(900, 900)

    # Mask data.
    data = np.ma.masked_equal(data, -9999)

    # Plot with matplotlib.
    plot_radolan(data, attributes, radolan_grid_xy, clabel=label)


def plot_radolan(data: np.ndarray, attrs: dict, grid: np.dstack, clabel: str = None):
    """Plot RADOLAN data.

    Shamelessly stolen from the wradlib RADOLAN Product Showcase documentation.
    https://docs.wradlib.org/en/stable/notebooks/radolan/radolan_showcase.html

    Thanks!
    """
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, aspect="equal")
    x = grid[:, :, 0]
    y = grid[:, :, 1]
    pm = ax.pcolormesh(x, y, data, cmap="viridis", shading="auto")
    cb = fig.colorbar(pm, shrink=0.75)
    cb.set_label(clabel)
    plt.xlabel("x [km]")
    plt.ylabel("y [km]")
    plt.title("{0} Product\n{1}".format(attrs["producttype"], attrs["datetime"].isoformat()))
    plt.xlim((x[0, 0], x[-1, -1]))
    plt.ylim((y[0, 0], y[-1, -1]))
    plt.grid(color="r")


def radar_info(data: np.ndarray, attributes: dict):
    """Display metadata from RADOLAN request."""
    log.info("Data shape: %s", data.shape)
    log.info("Attributes")

    for key, value in attributes.items():
        print(f"- {key}: {value}")


def radar_rw_example():
    """Retrieve radar rw reflectivity data by DWD."""
    log.info("Acquiring radar RW composite data")
    radolan = DwdRadarValues(
        parameter=DwdRadarParameter.RW_REFLECTIVITY,
        start_date=DwdRadarDate.LATEST,
    )

    for item in radolan.query():

        # Decode data using wradlib.
        log.info("Parsing radar RW composite data for %s", item.timestamp)
        data, attributes = wrl.io.read_radolan_composite(item.data)

        radar_info(data, attributes)

        # Plot and display data.
        plot(data, attributes)
        if "PYTEST_CURRENT_TEST" not in os.environ:
            plt.show()


def main():
    """Run example."""
    radar_rw_example()


if __name__ == "__main__":
    main()
