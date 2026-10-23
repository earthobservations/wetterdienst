# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Example for DWD radar sites data in OPERA HDF5 (ODIM_H5) format using wetterdienst and xradar.

Derived from https://gist.github.com/kmuehlbauer/ac990569e6ad38a49412fc74a2035c37.

See Also:
- https://docs.openradarscience.org/projects/xradar/en/stable/notebooks/ODIM_H5.html

This program will request the most recent complete SWEEP_PCP data for Essen and plot the outcome with matplotlib.

"""

import datetime as dt
import logging
import os
from io import BytesIO
from typing import cast

import matplotlib.pyplot as plt
import xarray as xr

from wetterdienst import Settings
from wetterdienst.provider.dwd.radar import (
    DwdRadarDataFormat,
    DwdRadarDataSubset,
    DwdRadarDate,
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
    """Return the time of the scan from the name of a sweep file, `..._dbzh_00-2026102320403400-ess-10410-hd5`."""
    return url.rsplit("-", 4)[1]


def radar_scan_precip() -> None:
    """Retrieve radar sweep scan of precipitation provided by DWD."""

    def request(
        parameter: DwdRadarParameter,
        start: DwdRadarDate | dt.datetime = DwdRadarDate.MOST_RECENT,
        end: dt.datetime | None = None,
    ) -> DwdRadarValues:
        """Return the request for a moment, by default for the most recent scan."""
        return DwdRadarValues(
            parameter=parameter,
            start=start,
            end=end,
            site=DwdRadarSite.ESS,
            fmt=DwdRadarDataFormat.HDF5,
            subset=DwdRadarDataSubset.POLARIMETRIC,
            settings=Settings(cache_disable=True),
        )

    def sweeps(values: DwdRadarValues) -> dict[str, BytesIO]:
        """Return the files of a moment by the time of their scan."""
        return {scan_stamp(cast("str", item.url)): item.data for item in values.query()}

    # MOST_RECENT is resolved against the clock when a request is made, so the velocity is asked for the window the
    # reflectivity resolved to: a 5-minute boundary falling between the two downloads must not put them in two slots.
    request_reflectivity = request(DwdRadarParameter.SWEEP_PCP_REFLECTIVITY_H)
    request_velocity = request(
        DwdRadarParameter.SWEEP_PCP_VELOCITY_H,
        start=cast("dt.datetime", request_reflectivity.start),
        end=cast("dt.datetime", request_reflectivity.end),
    )
    log.info(f"Acquiring radar SWEEP_PCP data for {DwdRadarSite.ESS} at {request_reflectivity.start}")

    # Pair the reflectivity and the velocity: they are one scan, their files carry the same time, and a scan of which
    # only one of the two is listed yet is left out, not paired with the one of another scan.
    reflectivity = sweeps(request_reflectivity)
    velocity = sweeps(request_velocity)
    scans = sorted(reflectivity.keys() & velocity.keys())

    # Sanity checks.
    if not scans:
        log.warning("No radar files found for the given constraints")
        return

    # Decode data using xradar odim backend: the two moments of one scan share their coordinates, a mismatch is an error
    data = xr.open_mfdataset(
        [reflectivity[scans[-1]], velocity[scans[-1]]],
        engine="odim",
        combine="by_coords",
        compat="no_conflicts",
        join="exact",
    )

    # Output debug information.
    print(data)

    # Plot and display data.
    plot(data)
    if "PYTEST_CURRENT_TEST" not in os.environ:
        plt.show()


def main() -> None:
    """Run example."""
    radar_scan_precip()


if __name__ == "__main__":
    main()
