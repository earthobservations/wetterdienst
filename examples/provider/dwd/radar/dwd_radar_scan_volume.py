# Copyright (C) 2018-2023, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
=====
About
=====

Example for DWD radar sites data in OPERA HDF5 (ODIM_H5) format using wetterdienst and wradlib. # noqa
Derived from https://gist.github.com/kmuehlbauer/ac990569e6ad38a49412fc74a2035c37.

See also:
- https://docs.openradarscience.org/projects/xradar/en/stable/notebooks/ODIM_H5.html # noqa

This program will request the most recent complete SWEEP_VOL data
for Essen and plot the outcome with matplotlib.

"""  # Noqa:D205,D400

import datetime as dt
import logging
import os
from zoneinfo import ZoneInfo

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from wetterdienst import Settings
from wetterdienst.provider.dwd.radar import (
    DwdRadarDataFormat,
    DwdRadarDataSubset,
    DwdRadarParameter,
    DwdRadarSite,
    DwdRadarValues,
)

logging.basicConfig(level=logging.INFO)
log = logging.getLogger()


def plot(data: xr.Dataset):
    """Plot radar data with prefixed settings."""
    # Georeference Data.
    swp0 = data.xradar.georeference()

    # Plot and display data using cartopy.
    fig = plt.figure(figsize=(20, 8))
    ax1 = fig.add_subplot(121, aspect="equal")
    swp0.DBZH.plot(x="x", y="y", ax=ax1)
    ax2 = fig.add_subplot(122, aspect="equal")
    swp0.VRADH.plot(x="x", y="y", ax=ax2)


def radar_scan_volume():
    """Retrieve radar sweep volume velocity h from site ESS in format HDF5 as subset polarimetric."""

    ed = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None)
    end_date = dt.datetime(ed.year, ed.month, ed.day, ed.hour, (ed.minute // 5) * 5)
    start_date = end_date - dt.timedelta(minutes=5)
    elevations = range(10)

    results_velocity = []
    results_reflectivity = []

    for el in elevations:
        request_velocity = DwdRadarValues(
            parameter=DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
            start_date=start_date,
            end_date=end_date,
            elevation=el,
            site=DwdRadarSite.ESS,
            fmt=DwdRadarDataFormat.HDF5,
            subset=DwdRadarDataSubset.POLARIMETRIC,
            settings=Settings(cache_disable=True),
        )
        request_reflectivity = DwdRadarValues(
            parameter=DwdRadarParameter.SWEEP_VOL_REFLECTIVITY_H,
            start_date=start_date,
            end_date=end_date,
            elevation=el,
            site=DwdRadarSite.ESS,
            fmt=DwdRadarDataFormat.HDF5,
            subset=DwdRadarDataSubset.POLARIMETRIC,
            settings=Settings(cache_disable=True),
        )

        # Submit requests.
        results_velocity.append(request_velocity.query())
        results_reflectivity.append(request_reflectivity.query())

    log.info(f"Acquiring radar SWEEP_VOL data for {DwdRadarSite.ESS} at elevation {request_velocity.elevation}")

    # Collect list of buffers.
    volume_velocity = []
    for item1 in results_velocity:
        files = []
        for item2 in item1:
            files.append(item2.data)
        volume_velocity.append(files)
    volume_velocity = [v[-1:] for v in volume_velocity]
    volume_velocity = np.array(volume_velocity).T.tolist()

    volume_reflectivity = []
    for item1 in results_reflectivity:
        files = []
        for item2 in item1:
            files.append(item2.data)
        volume_reflectivity.append(files)
    volume_reflectivity = [v[-1:] for v in volume_reflectivity]
    volume_reflectivity = np.array(volume_reflectivity).T.tolist()

    # Sanity checks.
    if not volume_reflectivity[0] and not volume_velocity[0]:
        log.warning("No radar files found for the given constraints")

    # merge-open sweeps into list
    ds_list = []
    for r, v in zip(volume_reflectivity[0], volume_velocity[0]):
        ds = xr.open_mfdataset([r, v], engine="odim", group="sweep_0")
        ds_list.append(ds)

    # Fill DataTree.
    dtree = xr.DataTree(children={f"sweep_{i}": xr.DataTree(swp, name=f"sweep_{i}") for i, swp in enumerate(ds_list)})

    # Output debug information.
    print(dtree)

    # Plot and display data for all sweeps.
    for node in dtree.groups:
        if "sweep" in node:
            plot(dtree[node].ds)
    if "PYTEST_CURRENT_TEST" not in os.environ:
        plt.show()


def main():
    """Run example."""
    radar_scan_volume()


if __name__ == "__main__":
    main()
