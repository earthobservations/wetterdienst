# Copyright (C) 2018-2023, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
=====
About
=====

Example for DWD RADOLAN Composite RW/SF using wetterdienst and wradlib.
Hourly and gliding 24h sum of radar- and station-based measurements (German).

See also:
- https://docs.wradlib.org/en/stable/notebooks/fileio/radolan/radolan_showcase.html.

This program will request daily (RADOLAN SF) data for 2020-09-04T12:00:00
and plot the outcome with matplotlib.


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
- https://www.dwd.de/DE/leistungen/radolan/radolan_info/radolan_poster_201711_en_pdf.pdf?__blob=publicationFile&v=2
- https://opendata.dwd.de/climate_environment/CDC/grids_germany/daily/radolan/
- https://docs.wradlib.org/en/stable/notebooks/fileio/radolan/radolan_showcase.html#RADOLAN-Composite
- Hourly: https://docs.wradlib.org/en/stable/notebooks/fileio/radolan/radolan_showcase.html#RADOLAN-RW-Product
- Daily: https://docs.wradlib.org/en/stable/notebooks/fileio/radolan/radolan_showcase.html#RADOLAN-SF-Product
"""  # noqa:D205,D400,E501

import logging
import os

import matplotlib.pyplot as plt
import xarray as xr

from wetterdienst.provider.dwd.radar import (
    DwdRadarDate,
    DwdRadarParameter,
    DwdRadarValues,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()


def plot(ds: xr.Dataset, product_type: str):
    """Plot RADOLAN data.

    Shamelessly stolen from the wradlib RADOLAN Product Showcase documentation.
    https://docs.wradlib.org/en/stable/notebooks/radolan/radolan_showcase.html

    Thanks!
    """
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, aspect="equal")
    ds[product_type].plot(ax=ax, cmap="viridis", shading="auto")
    plt.title(f"{product_type} Product\n{ds.time.min().values}")
    plt.grid(color="r")


def radolan_rw_example():
    """Retrieve RADOLAN rw reflectivity data by DWD."""
    log.info("Acquiring RADOLAN RW composite data")
    radolan = DwdRadarValues(
        parameter=DwdRadarParameter.RW_REFLECTIVITY,
        start_date=DwdRadarDate.LATEST,
    )

    for item in radolan.query():
        # Decode data using wradlib.
        log.info("Parsing RADOLAN RW composite data for %s", item.timestamp)
        ds = xr.open_dataset(item.data, engine="radolan")

        product_type = list(ds.data_vars.keys())[0]

        # show Dataset
        print(ds)

        # show DataArray
        print(ds[product_type])

        # Plot and display data.
        plot(ds, product_type)
        if "PYTEST_CURRENT_TEST" not in os.environ:
            plt.show()


def main():
    """Run example."""
    radolan_rw_example()


if __name__ == "__main__":
    main()
