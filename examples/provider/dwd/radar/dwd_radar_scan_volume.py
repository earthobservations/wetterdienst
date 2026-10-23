# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Example for DWD radar sites data in OPERA HDF5 (ODIM_H5) format using wetterdienst and wradlib.

Derived from https://gist.github.com/kmuehlbauer/ac990569e6ad38a49412fc74a2035c37.

See Also:
- https://docs.openradarscience.org/projects/xradar/en/stable/notebooks/ODIM_H5.html

This program will request the most recent complete SWEEP_VOL data for Essen and plot the outcome with matplotlib.

"""

import datetime as dt
import logging
import os
from io import BytesIO
from typing import cast
from zoneinfo import ZoneInfo

import matplotlib.pyplot as plt
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


def plot(data: xr.Dataset) -> None:
    """Plot radar data with prefixed settings."""
    # Georeference Data.
    swp0 = data.xradar.georeference()

    # Plot and display data using cartopy.
    fig = plt.figure(figsize=(20, 8))
    ax1 = fig.add_subplot(121, aspect="equal")
    swp0.DBZH.plot(x="x", y="y", ax=ax1)
    ax2 = fig.add_subplot(122, aspect="equal")
    swp0.VRADH.plot(x="x", y="y", ax=ax2)


def scan_stamp(url: str) -> str:
    """Return the time of the scan from the name of a sweep file, `..._dbzh_03-2026102318470700-ess-10410-hd5`."""
    return url.rsplit("-", 4)[1]


def radar_scan_volume() -> None:
    """Retrieve radar sweep volume velocity h from site ESS in format HDF5 as subset polarimetric."""
    ed = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None)
    end_date = dt.datetime(ed.year, ed.month, ed.day, ed.hour, (ed.minute // 5) * 5, tzinfo=ZoneInfo("UTC"))
    # A volume starts every 5 minutes and its sweeps are dated by the minute they were scanned in, so the window is
    # one slot, closed before the minute the next volume starts in: a window closed on it would hold the first sweep
    # of the next volume next to the other sweeps of this one. The slot is the one before the last, as DWD lists the
    # sweeps of a volume up to 485 s late (`DwdRadarDate.MOST_RECENT` goes back the same way).
    start_date = end_date - dt.timedelta(minutes=10)
    last_date = end_date - dt.timedelta(minutes=5, seconds=1)
    elevations = range(10)

    log.info(f"Acquiring radar SWEEP_VOL data for {DwdRadarSite.ESS} from {start_date} to {last_date}")

    def sweeps(parameter: DwdRadarParameter, elevation: int) -> dict[str, BytesIO]:
        """Return the files of a moment and a sweep by the time of their scan."""
        request = DwdRadarValues(
            parameter=parameter,
            start=start_date,
            end=last_date,
            elevation=elevation,
            site=DwdRadarSite.ESS,
            fmt=DwdRadarDataFormat.HDF5,
            subset=DwdRadarDataSubset.POLARIMETRIC,
            settings=Settings(cache_disable=True),
        )
        return {scan_stamp(cast("str", item.url)): item.data for item in request.query()}

    # Pair the reflectivity and the velocity of a sweep: they are one scan, their files carry the same time, and a
    # sweep of which only one of the two is published yet is left out, not paired with the one of another volume.
    pairs = {}
    for el in elevations:
        reflectivity = sweeps(DwdRadarParameter.SWEEP_VOL_REFLECTIVITY_H, el)
        velocity = sweeps(DwdRadarParameter.SWEEP_VOL_VELOCITY_H, el)
        scans = sorted(reflectivity.keys() & velocity.keys())
        if scans:
            pairs[el] = (reflectivity[scans[-1]], velocity[scans[-1]])

    # Sanity checks.
    if not pairs:
        log.warning("No radar files found for the given constraints")

    # merge-open sweeps into list: the two moments of one scan share their coordinates, a mismatch is an error
    ds_list = {}
    for el, (r, v) in pairs.items():
        ds = xr.open_mfdataset(
            [r, v], engine="odim", group="sweep_0", combine="by_coords", compat="no_conflicts", join="exact"
        )
        ds_list[el] = ds

    # Fill DataTree.
    dtree = xr.DataTree(children={f"sweep_{el}": xr.DataTree(swp, name=f"sweep_{el}") for el, swp in ds_list.items()})

    # Output debug information.
    print(dtree)

    # Plot and display data for all sweeps.
    for node in dtree.groups:
        if "sweep" in node:
            plot(dtree[node].ds)
    if "PYTEST_CURRENT_TEST" not in os.environ:
        plt.show()


def main() -> None:
    """Run example."""
    radar_scan_volume()


if __name__ == "__main__":
    main()
