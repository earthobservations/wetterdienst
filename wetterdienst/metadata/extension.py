# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum


class Extension(Enum):
    CSV = "csv"
    H5 = "h5"
    BIN = "bin"
    ZIP = "zip"
    GZ = "gz"
    BZ2 = "bz2"
    TAR_GZ = "tar.gz"
    TAR_BZ2 = "tar.bz2"
