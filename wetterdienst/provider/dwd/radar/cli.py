# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import sys
from pathlib import Path

import h5py
from h5netcdf import Group


def hdf5dump(thing: str, *, compact: bool = False) -> None:
    """
    Like "h5dump -n 1", but better.
    """

    blocklist = [
        "afc_status",
        "bpwr",
        "prf",
        "pulse",
        "startazA",
        "startazT",
        "startelA",
        "stopazA",
        "stopazT",
        "stopelA",
    ]

    def dumpattrs(item: Group, indent: int = 2) -> None:
        for name, value in item.attrs.items():
            if compact:
                if name in blocklist:
                    continue
            print(" " * indent, "-", name, value)  # noqa: T201

    with Path(thing).open("rb") as buffer:
        hdf = h5py.File(buffer, "r")
        for group in hdf.keys():
            print("name:", hdf[group].name)  # noqa: T201
            dumpattrs(hdf[group])
            for subgroup in hdf[group].keys():
                print("  name:", subgroup)  # noqa: T201
                dumpattrs(hdf[group][subgroup], indent=4)


def wddump() -> None:
    filename = sys.argv[1]
    hdf5dump(filename, compact=True)
