# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What a RADOLAN RW file holds, read as ODIM HDF5 (GH-3298).

DWD names the RADOLAN files `bin` and publishes them as ODIM HDF5, which `wradlib.io.read_radolan_header` does not
read: it raises a `UnicodeDecodeError` on the first byte of the file, 0x89.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from io import BytesIO

    from h5py import Group


def attribute_timestamp(group: Group, date: str, time: str) -> dt.datetime:
    """Read a date and a time attribute of an ODIM group (`YYYYMMDD`, `hhmmss`, UTC) as one datetime."""
    stamp = group.attrs[date].decode() + group.attrs[time].decode()
    return dt.datetime.strptime(stamp, "%Y%m%d%H%M%S").replace(tzinfo=ZoneInfo("UTC"))


def assert_rw_file(data: BytesIO, radar_locations: list[str]) -> dt.datetime:
    """Assert that `data` is the RW of RADOLAN, the hourly sum of the precipitation, and return the time it ends.

    The radars that took part are the nodes of the composite, `deasb`, `deboo`, ...
    """
    import h5py  # noqa: PLC0415

    with h5py.File(data, mode="r") as f:
        assert f.attrs["Conventions"] == b"ODIM_H5/V2_3"
        assert f["what"].attrs["object"] == b"COMP"
        assert f["dataset1/what"].attrs["product"] == b"COMP"
        assert f["dataset1/what"].attrs["prodname"] == b"RW"
        assert f["how"].attrs["software"] == b"RADOLAN"

        # the accumulation of the hour, in steps of 0.1 mm, 1 km x 1 km
        quantity = f["dataset1/data1/what"].attrs
        assert quantity["quantity"] == b"ACRR"
        assert quantity["gain"] == 0.1
        assert quantity["offset"] == 0
        assert f["dataset1/data1/data"].shape == (1200, 1100)
        assert f["where"].attrs["xsize"] == 1100
        assert f["where"].attrs["ysize"] == 1200

        nodes = [node.strip("'") for node in f["how"].attrs["nodes"].decode().split(",")]
        assert len(nodes) >= 10
        assert {node.removeprefix("de") for node in nodes} <= set(radar_locations)

        # the hour before the time of the file
        end = attribute_timestamp(f["dataset1/what"], "enddate", "endtime")
        assert end - attribute_timestamp(f["dataset1/what"], "startdate", "starttime") == dt.timedelta(hours=1)
        assert end == attribute_timestamp(f["what"], "date", "time")
        return end
