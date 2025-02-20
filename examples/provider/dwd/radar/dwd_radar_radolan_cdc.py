# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Example for DWD RADOLAN Composite RW/SF using wetterdienst and wradlib.

Hourly and gliding 24h sum of radar- and station-based measurements (German).

See Also:
- https://docs.wradlib.org/en/stable/notebooks/radolan/radolan_showcase.html.

This program will request daily (RADOLAN SF) data for 2020-09-04T12:00:00 and plot the outcome with matplotlib.

Details
-------

RADOLAN: Radar Online Adjustment
Radar based quantitative precipitation estimation

RADOLAN Composite RW/SF
Hourly and gliding 24h sum of radar- and station-based measurements (German)

The routine procedure RADOLAN (Radar-Online-Calibration) provides area-wide, spatially and temporally high-resolution
quantitative precipitation data in real-time for Germany.

- https://www.dwd.de/EN/Home/_functions/aktuelles/2019/20190820_radolan.html
- https://www.dwd.de/DE/leistungen/radolan/radolan_info/radolan_poster_201711_en_pdf.pdf?__blob=publicationFile&v=2
- https://opendata.dwd.de/climate_environment/CDC/grids_germany/daily/radolan/
- https://docs.wradlib.org/en/stable/notebooks/fileio/radolan/radolan_showcase.html#RADOLAN-Composite
- Hourly: https://docs.wradlib.org/en/stable/notebooks/fileio/radolan/radolan_showcase.html#RADOLAN-RW-Product
- Daily: https://docs.wradlib.org/en/stable/notebooks/fileio/radolan/radolan_showcase.html#RADOLAN-SF-Product

"""

import logging
import os

import matplotlib.pyplot as plt
import xarray as xr

from wetterdienst.provider.dwd.radar import (
    DwdRadarParameter,
    DwdRadarPeriod,
    DwdRadarResolution,
    DwdRadarValues,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()


def plot(ds: xr.Dataset, product_type: str) -> None:
    """Plot RADOLAN data.

    Shamelessly stolen from the wradlib RADOLAN Product Showcase documentation.
    https://docs.wradlib.org/en/stable/notebooks/fileio/radolan/radolan_showcase.html

    Thanks!
    It's a pleasure!
    """
    fig = plt.figure(figsize=(10, 8))
    ax = fig.add_subplot(111, aspect="equal")
    ds[product_type].plot(ax=ax, cmap="viridis", shading="auto")
    plt.title(f"{product_type} Product\n{ds.time.min().values}")
    plt.grid(color="r")


def radolan_grid_example() -> None:
    """Retrieve radolan cdc gridded data by DWD."""
    log.info("Acquiring RADOLAN_CDC data")
    radolan = DwdRadarValues(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=DwdRadarResolution.DAILY,
        period=DwdRadarPeriod.HISTORICAL,
        start_date="2020-09-04T12:00:00",
        end_date="2020-09-04T12:00:00",
    )

    for item in radolan.query():
        # Decode data using wradlib.
        log.info("Parsing RADOLAN_CDC composite data for %s", item.timestamp)
        ds = xr.open_dataset(item.data, engine="radolan")

        # Get the product type
        # We only have one data variable with name == product_type
        product_type = next(iter(ds.data_vars.keys()))

        # show Dataset
        print(ds)

        # show DataArray
        print(ds[product_type])

        # Plot and display data.
        plot(ds, product_type)
        if "PYTEST_CURRENT_TEST" not in os.environ:
            plt.show()


def main() -> None:
    """Run example."""
    radolan_grid_example()


if __name__ == "__main__":
    main()
