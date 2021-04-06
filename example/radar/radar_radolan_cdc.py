# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
=====
About
=====
Example for DWD RADOLAN Composite RW/SF using wetterdienst and wradlib.
Hourly and gliding 24h sum of radar- and station-based measurements (German).

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


=======
Details
=======
RADOLAN: Radar Online Adjustment
Radar based quantitative precipitation estimation

RADOLAN Composite RW/SF
Hourly and gliding 24h sum of radar- and station-based measurements (German)

The routine procedure RADOLAN (Radar-Online-Calibration) provides area-wide,
spatially and temporally high-resolution quantitative precipitation data in
real-time for Germany.

- https://www.dwd.de/EN/Home/_functions/aktuelles/2019/20190820_radolan.html
- https://www.dwd.de/DE/leistungen/radolan/radolan_info/radolan_poster_201711_en_pdf.pdf?__blob=publicationFile&v=2  # noqa
- https://opendata.dwd.de/climate_environment/CDC/grids_germany/daily/radolan/
- https://docs.wradlib.org/en/stable/notebooks/radolan/radolan_showcase.html#RADOLAN-Composite # noqa
- Hourly: https://docs.wradlib.org/en/stable/notebooks/radolan/radolan_showcase.html#RADOLAN-RW-Product # noqa
- Daily: https://docs.wradlib.org/en/stable/notebooks/radolan/radolan_showcase.html#RADOLAN-SF-Product # noqa
"""
import logging
import os

import matplotlib.pyplot as plt
import numpy as np
import wradlib as wrl

from wetterdienst.provider.dwd.radar import (
    DwdRadarParameter,
    DwdRadarPeriod,
    DwdRadarResolution,
    DwdRadarValues,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()


def plot(data: np.ndarray, attributes: dict, label: str):
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
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, aspect="equal")
    x = grid[:, :, 0]
    y = grid[:, :, 1]
    pm = ax.pcolormesh(x, y, data, cmap="viridis", shading="auto")
    cb = fig.colorbar(pm, shrink=0.75)
    cb.set_label(clabel)
    plt.xlabel("x [km]")
    plt.ylabel("y [km]")
    plt.title(
        "{0} Product\n{1}".format(attrs["producttype"], attrs["datetime"].isoformat())
    )
    plt.xlim((x[0, 0], x[-1, -1]))
    plt.ylim((y[0, 0], y[-1, -1]))
    plt.grid(color="r")


def radolan_info(data: np.ndarray, attributes: dict):
    """
    Display metadata from RADOLAN request.
    """
    log.info("Data shape: %s", data.shape)
    log.info("Attributes:")

    for key, value in attributes.items():
        print(f"- {key}: {value}")


def label_by_producttype(producttype: str) -> str:
    """
    Compute label for RW/SF product.

    :param producttype: Either RW or SF.
    :return: Label for plot.
    """
    if producttype == "RW":
        label = "mm * h-1"
    elif producttype == "SF":
        label = "mm * 24h-1"
    else:
        label = None
    return label


def radolan_grid_example():

    log.info("Acquiring RADOLAN_CDC data")
    radolan = DwdRadarValues(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=DwdRadarResolution.DAILY,
        period=DwdRadarPeriod.RECENT,
        start_date="2020-09-04T12:00:00",
        end_date="2020-09-04T12:00:00",
    )

    for item in radolan.query():

        # Decode data using wradlib.
        log.info("Parsing RADOLAN_CDC composite data for %s", item.timestamp)
        data, attributes = wrl.io.read_radolan_composite(item.data)

        # Compute label matching RW/SF product.
        label = label_by_producttype(attributes["producttype"])

        # Plot and display data.
        plot(data, attributes, label)
        if "PYTEST_CURRENT_TEST" not in os.environ:
            plt.show()


def main():
    radolan_grid_example()


if __name__ == "__main__":
    main()
