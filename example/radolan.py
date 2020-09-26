"""
=====
About
=====
Example for DWD RADOLAN Composite RW/SF using wetterdienst and wradlib.
Hourly and gliding 24h sum of radar- and station-based measurements (German).

See also https://docs.wradlib.org/en/stable/notebooks/radolan/radolan_showcase.html.

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

import numpy as np
import wradlib as wrl
import matplotlib.pyplot as pl

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

from wetterdienst import DWDRadarRequest, TimeResolution


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
    fig = pl.figure(figsize=(10,8))
    ax = fig.add_subplot(111, aspect='equal')
    x = grid[:,:,0]
    y = grid[:,:,1]
    pm = ax.pcolormesh(x, y, data, cmap='viridis', shading='auto')
    cb = fig.colorbar(pm, shrink=0.75)
    cb.set_label(clabel)
    pl.xlabel("x [km]")
    pl.ylabel("y [km]")
    pl.title('{0} Product\n{1}'.format(attrs['producttype'],
                                       attrs['datetime'].isoformat()))
    pl.xlim((x[0,0],x[-1,-1]))
    pl.ylim((y[0,0],y[-1,-1]))
    pl.grid(color='r')


def radolan_info(data: np.ndarray, attributes: dict):
    """
    Display metadata from RADOLAN request.
    """
    log.info("Data shape: %s", data.shape)
    log.info("Attributes: %s", attributes)

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


def radolan_example():
    """
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
    - https://docs.wradlib.org/en/stable/notebooks/radolan/radolan_showcase.html#RADOLAN-Composite
    - Hourly: https://docs.wradlib.org/en/stable/notebooks/radolan/radolan_showcase.html#RADOLAN-RW-Product
    - Daily: https://docs.wradlib.org/en/stable/notebooks/radolan/radolan_showcase.html#RADOLAN-SF-Product

    :return:
    """

    log.info("Acquiring RADOLAN data")
    radolan = DWDRadarRequest(
        TimeResolution.DAILY,
        start_date="2020-09-04T12:00:00",
        end_date="2020-09-04T12:00:00",
        #prefer_local=True,
        #write_file=True
    )

    for item in radolan.collect_data():

        # Decode item.
        timestamp, buffer = item

        # Decode data using wradlib.
        log.info("Parsing RADOLAN composite data for %s", timestamp)
        data, attributes = wrl.io.read_radolan_composite(buffer)

        # Compute label matching RW/SF product.
        label = label_by_producttype(attributes["producttype"])

        # Plot and display data.
        plot(data, attributes, label)
        pl.show()


def main():
    radolan_example()


if __name__ == "__main__":
    main()
