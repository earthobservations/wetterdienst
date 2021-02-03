# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
=====
About
=====
Example for DWD RADOLAN Composite RX using wetterdienst and wradlib.

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

"""
import logging

import matplotlib.pyplot as pl
import numpy as np
import wradlib as wrl

from wetterdienst.dwd.radar import DWDRadarData
from wetterdienst.dwd.radar.metadata import DWDRadarDate, DWDRadarParameter

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()


def plot(data: np.ndarray, attributes: dict, label: str = None):
    """
    Convenience function for plotting RADOLAN data.
    """

    # Get coordinates.
    radolan_grid_xy = wrl.georef.get_radolan_grid(900, 900)

    # Mask data.
    data = np.ma.masked_equal(data, -9999)

    # Plot with matplotlib.
    plot_radolan(data, attributes, radolan_grid_xy, clabel=label)


def plot_radolan(data: np.ndarray, attrs: dict, grid: np.dstack, clabel: str = None):
    """
    Plotting function for RADOLAN data.

    Shamelessly stolen from the wradlib RADOLAN Product Showcase documentation.
    https://docs.wradlib.org/en/stable/notebooks/radolan/radolan_showcase.html

    Thanks!
    """
    fig = pl.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, aspect="equal")
    x = grid[:, :, 0]
    y = grid[:, :, 1]
    pm = ax.pcolormesh(x, y, data, cmap="viridis", shading="auto")
    cb = fig.colorbar(pm, shrink=0.75)
    cb.set_label(clabel)
    pl.xlabel("x [km]")
    pl.ylabel("y [km]")
    pl.title(
        "{0} Product\n{1}".format(attrs["producttype"], attrs["datetime"].isoformat())
    )
    pl.xlim((x[0, 0], x[-1, -1]))
    pl.ylim((y[0, 0], y[-1, -1]))
    pl.grid(color="r")


def radar_info(data: np.ndarray, attributes: dict):
    """
    Display metadata from RADOLAN request.
    """
    log.info("Data shape: %s", data.shape)
    log.info("Attributes")

    for key, value in attributes.items():
        print(f"- {key}: {value}")


def radar_rx_example():

    log.info("Acquiring radar RX composite data")
    radolan = DWDRadarData(
        parameter=DWDRadarParameter.RX_REFLECTIVITY,
        start_date=DWDRadarDate.LATEST,
    )

    for item in radolan.collect_data():

        # Decode data using wradlib.
        log.info("Parsing radar RX composite data for %s", item.timestamp)
        data, attributes = wrl.io.read_radolan_composite(item.data)

        radar_info(data, attributes)

        # Plot and display data.
        plot(data, attributes)
        pl.show()


def main():
    radar_rx_example()


if __name__ == "__main__":
    main()
