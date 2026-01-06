# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Enumeration for file extensions."""

from enum import Enum


class Extension(Enum):
    """Enumeration for file extensions."""

    CSV = "csv"
    H5 = "h5"
    BIN = "bin"
    ZIP = "zip"
    GZ = "gz"
    BZ2 = "bz2"
    TAR = "tar"
    TAR_GZ = "tar.gz"
    TAR_BZ2 = "tar.bz2"
