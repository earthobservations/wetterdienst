# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""CLI for DWD radar data."""

import sys
from pathlib import Path

import h5py
from h5netcdf import Group


def hdf5dump(thing: str, *, compact: bool = False) -> None:
    """Like "h5dump -n 1", but better."""
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
            if compact and name in blocklist:
                continue
            print(" " * indent, "-", name, value)  # noqa: T201

    with Path(thing).open("rb") as buffer:
        hdf = h5py.File(buffer, "r")
        for group in hdf:
            print("name:", hdf[group].name)  # noqa: T201
            dumpattrs(hdf[group])
            for subgroup in hdf[group]:
                print("  name:", subgroup)  # noqa: T201
                dumpattrs(hdf[group][subgroup], indent=4)


def wddump() -> None:
    """Dump the contents of a Wetterdienst HDF5 file."""
    filename = sys.argv[1]
    hdf5dump(filename, compact=True)
