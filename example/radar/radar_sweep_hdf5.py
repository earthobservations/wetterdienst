"""
=====
About
=====
Example for DWD radar sites OPERA HDF5 (ODIM_H5) format using wetterdienst and wradlib.

See also:
- https://docs.wradlib.org/en/stable/notebooks/fileio/wradlib_radar_formats.html#OPERA-HDF5-(ODIM_H5) # noqa

This program will request the latest RADAR SWEEP_PCP_VELOCITY_H data
for Boostedt and plot the outcome with matplotlib.


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

from wetterdienst.dwd.radar import (
    DWDRadarData,
    DWDRadarDataFormat,
    DWDRadarDataSubset,
    DWDRadarDate,
    DWDRadarParameter,
    DWDRadarSite,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()


def plot(data: np.ndarray):
    """
    Convenience function for plotting radar data.
    """

    fig = pl.figure(figsize=(10, 8))
    wrl.vis.plot_ppi(data["dataset1/data1/data"], fig=fig, proj="cg")


def radar_info(data: dict):
    """
    Display data from radar request.
    """
    print("Keys:", data.keys())

    log.info("Data")
    for key, value in data.items():
        print(f"- {key}: {value}")


def radar_hdf5_example():

    log.info("Acquiring radar sweep data in HDF5")
    request = DWDRadarData(
        parameter=DWDRadarParameter.SWEEP_PCP_VELOCITY_H,
        start_date=DWDRadarDate.MOST_RECENT,
        site=DWDRadarSite.BOO,
        fmt=DWDRadarDataFormat.HDF5,
        subset=DWDRadarDataSubset.SIMPLE,
    )

    for item in request.collect_data():

        # Decode data using wradlib.
        log.info(f"Parsing radar data for {request.site} at '{item.timestamp}'")
        data = wrl.io.read_opera_hdf5(item.data)

        # Output debug information.
        radar_info(data)

        # Plot and display data.
        plot(data)
        pl.show()


def main():
    radar_hdf5_example()


if __name__ == "__main__":
    main()
