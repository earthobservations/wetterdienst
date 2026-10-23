# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Utilities for the DWD radar provider."""

from __future__ import annotations

import datetime as dt
import logging
import re
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

from wetterdienst.exceptions import MissingDependencyError
from wetterdienst.util.extras import import_optional

if TYPE_CHECKING:
    from io import BytesIO

log = logging.getLogger(__name__)

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

# The date and the time of the run, split by a T, are used for data within "weather/radar/konrad3d"; the two digits of
# the seconds are cut off, as the long timestamps' are.
# Examples:
# - KONRAD3D_20261022T130500.xml
RADAR_DT_REGEX_KONRAD3D = r"(?<!\d)\d{8}T\d{4}(?=\d{2}(?!\d))"


RADAR_DT_PATTERN = re.compile(
    f"{RADAR_DT_REGEX_COMPOSITE}|{RADAR_DT_REGEX_KONRAD3D}|{RADAR_DT_REGEX_LONG}|{RADAR_DT_REGEX_MEDIUM}"
    f"|{RADAR_DT_REGEX_SHORT}"
)
RADOLAN_DT_PATTERN = re.compile(f"{RADAR_DT_REGEX_SHORT}|{RADAR_DT_REGEX_MEDIUM}")


def get_date_string_from_filename(filename: str, pattern: re.Pattern) -> str | None:
    """Extract the digits of the first datetime in a filename using a regex pattern.

    The underscore of a composite's ``YYYYMMDD_HHMM`` and the T of KONRAD3D's ``YYYYMMDDThhmm`` are dropped, so that
    every date string is digits only.
    """
    try:
        return pattern.findall(filename)[0].replace("_", "").replace("T", "")
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


# The start of a file of the ODIM HDF5 format, and of a DX file, which is binary behind a header of text
_HDF5_SIGNATURE = b"\x89HDF\r\n\x1a\n"
# `DX` DDHHMM, the id of the site (five digits), MMYY and `BY`: `DX222110101321026BY31755VS 2CO0CD4CS0EP...` is the
# 22nd of October 2026, 21:10 UTC, of the site 10132; the file name `raa00-dx_10132-2610222110-boo---bin` says the same
_DX_HEADER = re.compile(rb"DX(\d{2})(\d{2})(\d{2})\d{5}(\d{2})(\d{2})BY")
# the time of the first event of the XML of the mesocyclones, `<time time-coordinate="UTC">2026-10-22T16:10:00</time>`,
# which is the run (as in the four largest files of 2026-10-20 to 22, read 2026-10-22); a run with no event has none
_XML_EVENT_TIME = re.compile(rb'<time time-coordinate="UTC">(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})</time>')


def read_scan_time(buffer: BytesIO) -> dt.datetime | None:
    """Read the time a radar file says it is of from its content, in UTC, for a file whose name has none.

    An ODIM HDF5 file has it in the `date` and `time` of its `/what` group (the sweeps of the precipitation scan, the
    composites and the site products), a DX file in its header, the XML of the mesocyclones in the time of its first
    event (a run with no event says none). Any other file says none, and a file that cannot be read has none to give:
    both answer `None`.

    Args:
        buffer: the file, read from the start; it is rewound before it is handed back

    Returns:
        the time of the file, or None where it says none

    Raises:
        MissingDependencyError: for an HDF5 file, as h5py (the `radar` extra) reads it

    """
    buffer.seek(0)
    head = buffer.read(32)
    buffer.seek(0)
    try:
        if head.startswith(_HDF5_SIGNATURE):
            return _read_odim_time(buffer)
        if head.lstrip().startswith(b"<?xml"):
            event = _XML_EVENT_TIME.search(buffer.read())
            return (
                None
                if event is None
                else dt.datetime.fromisoformat(event.group(1).decode()).replace(tzinfo=ZoneInfo("UTC"))
            )
        match = _DX_HEADER.match(head)
        if match is None:
            return None
        day, hour, minute, month, year = (int(group) for group in match.groups())
        return dt.datetime(2000 + year, month, day, hour, minute, tzinfo=ZoneInfo("UTC"))
    except MissingDependencyError:
        raise
    except (
        Exception
    ):  # h5py raises more than OSError and KeyError at a damaged file, a LATEST query must not fail on one
        log.debug("The time of the radar file cannot be read from it", exc_info=True)
        return None
    finally:
        buffer.seek(0)


def _read_odim_time(buffer: BytesIO) -> dt.datetime:
    """Read `/what` `date` and `time` of an ODIM HDF5 file: `b"20261022"` and `b"211000"`, UTC."""
    h5py = import_optional("h5py", "Reading the time of a radar HDF5 file", extra="radar")
    with h5py.File(buffer, mode="r") as hdf:
        what = hdf["what"].attrs
        date, time = (
            value.decode() if isinstance(value, bytes) else str(value) for value in (what["date"], what["time"])
        )
    return dt.datetime.strptime(f"{date}{time}", "%Y%m%d%H%M%S").replace(tzinfo=ZoneInfo("UTC"))
