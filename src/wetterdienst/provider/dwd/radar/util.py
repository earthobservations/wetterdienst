# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Utilities for the DWD radar provider."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

from wetterdienst.util.extras import import_optional

if TYPE_CHECKING:
    from io import BytesIO

# 6-character timestamps are used for data within "RADOLAN_CDC/historical".
# Examples:
# - SF201901.tar.gz
RADAR_DT_REGEX_SHORT = r"(?<!\d)\d{6}(?!\d)"

# 10-character timestamps are used for data within
# "RADOLAN_CDC/recent", "weather/radar/radolan" and "weather/radar/sites/dx".
# Examples:
# - raa01-sf_10000-2001010050-dwd---bin.gz
# - raa00-dx_10132-2009260240-boo---bin
RADAR_DT_REGEX_MEDIUM = r"(?<!\d)\d{10}(?!\d)"

# 16-character timestamps are used for data within "weather/site".
# We are just using 12 digits here to cut off the "second" part.
# Examples:
# - rab02-tt_10132-20261022113500-deboo-hd5
# - ras07-stqual-vol5minng01_sweeph5onem_vradh_00-2020092614305700-boo-10132-hd5
# - ras07-vol5minng01_sweeph5onem_vradh_00-2020092614305700-boo-10132-hd5
RADAR_DT_REGEX_LONG = r"(?<!\d)\d{12}"

# The date and the time of the run, split by an underscore, are used for data within "weather/radar/composite".
# Examples:
# - composite_rv_20261022_1130.tar
# - composite_rv_20261022_1130_005-hd5 (a file in the tar: the lead time of the forecast in minutes follows)
RADAR_DT_REGEX_COMPOSITE = r"(?<!\d)\d{8}_\d{4}(?!\d)"


RADAR_DT_PATTERN = re.compile(
    f"{RADAR_DT_REGEX_COMPOSITE}|{RADAR_DT_REGEX_LONG}|{RADAR_DT_REGEX_MEDIUM}|{RADAR_DT_REGEX_SHORT}"
)
RADOLAN_DT_PATTERN = re.compile(f"{RADAR_DT_REGEX_SHORT}|{RADAR_DT_REGEX_MEDIUM}")


def get_date_string_from_filename(filename: str, pattern: re.Pattern) -> str | None:
    """Extract the digits of the first datetime in a filename using a regex pattern.

    The underscore of a composite's ``YYYYMMDD_HHMM`` is dropped, so that every date string is digits only.
    """
    try:
        return pattern.findall(filename)[0].replace("_", "")
    except IndexError:
        return None


def verify_hdf5(buffer: BytesIO) -> None:
    """Verify that the buffer is a valid HDF5 file."""
    h5py = import_optional("h5py", "Verifying radar HDF5", extra="radar")

    buffer.seek(0)
    try:
        nc = h5py.File(buffer, mode="r")
        nc.close()
        buffer.seek(0)
    except Exception:
        buffer.seek(0)
        raise
