# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import sys

import h5py


def hdf5dump(thing, compact=False):
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

    with open(thing, "rb") as buffer:
        hdf = h5py.File(buffer, "r")

        def dumpattrs(item, indent=2):
            for name, value in item.attrs.items():
                if compact:
                    if name in blocklist:
                        continue
                print(" " * indent, "-", name, value)  # noqa: T201

        for group in hdf.keys():
            print("name:", hdf[group].name)  # noqa: T201
            dumpattrs(hdf[group])
            for subgroup in hdf[group].keys():
                print("  name:", subgroup)  # noqa: T201
                dumpattrs(hdf[group][subgroup], indent=4)


def wddump():
    filename = sys.argv[1]
    hdf5dump(filename, compact=True)
