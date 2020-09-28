"""
=====
About
=====
Example for DWD radar sites DX using wetterdienst and wradlib.

The German Weather Service uses the DX file format to encode
local radar sweeps. DX data are in polar coordinates.

See also:
- https://docs.wradlib.org/en/stable/notebooks/fileio/wradlib_radar_formats.html#German-Weather-Service:-DX-format
- https://docs.wradlib.org/en/stable/notebooks/fileio/wradlib_reading_dx.html

This program will request the latest RADAR DX data
for Boostedt and plot the outcome with matplotlib.


=====
Setup
=====
::

    brew install gdal
    pip install wradlib

"""
import logging
from tempfile import NamedTemporaryFile

import numpy as np
import wradlib as wrl
import matplotlib.pyplot as pl

from wetterdienst.dwd.radar.metadata import RadarParameter, RadarDate
from wetterdienst.dwd.radar.sites import RadarSite

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()

from wetterdienst import DWDRadarRequest


def plot(data: np.ndarray):
    """
    Convenience function for plotting radar data.
    """

    fig = pl.figure(figsize=(10, 8))
    im = wrl.vis.plot_ppi(data, fig=fig, proj='cg')


def radar_info(data: np.ndarray, metadata: dict):
    """
    Display metadata from radara request.
    """
    log.info("Data shape: %s", data.shape)
    #log.info("Metadata: %s", metadata)

    log.info("Metadata")
    for key, value in metadata.items():
        print(f"- {key}: {value}")


def radar_dx_example():

    log.info("Acquiring radar DX data")
    request = DWDRadarRequest(
        parameter=RadarParameter.DX_REFLECTIVITY,
        start_date=RadarDate.LATEST,
        site=RadarSite.BOO,
    )

    for item in request.collect_data():

        # Decode data using wradlib.
        log.info(f"Parsing radar data for {request.site} at '{item.timestamp}'")

        tempfile = NamedTemporaryFile()
        tempfile.write(item.data.read())
        data, metadata = wrl.io.read_dx(tempfile.name)

        # FIXME: Make this work.
        #data, metadata = wrl.io.read_dx(buffer.read())

        # Output debug information.
        radar_info(data, metadata)

        # Plot and display data.
        plot(data)
        pl.show()


def main():
    radar_dx_example()


if __name__ == "__main__":
    main()
