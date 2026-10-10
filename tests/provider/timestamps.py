# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What every provider's ``timestamp`` column has to look like, and the check for it."""

import polars as pl

#: the one type the ``timestamp`` column has, whichever provider it comes from and whether the frame
#: holds values, interpolated values or a summary: UTC, to the microsecond. A source that stamps in
#: local time or in nanoseconds is converted by its provider, not passed on.
TIMESTAMP_DTYPE = pl.Datetime(time_unit="us", time_zone="UTC")


def timestamp_problem(df: pl.DataFrame) -> str | None:
    """Say what is wrong with the ``timestamp`` column of a result frame, or None when nothing is.

    A frame without the column is not judged: a request that collected nothing may hand back a bare
    frame, and that has no timestamp to be wrong.
    """
    if "timestamp" not in df.columns:
        return None
    dtype = df.schema["timestamp"]
    if dtype == TIMESTAMP_DTYPE:
        return None
    return f"the timestamp column is {dtype}, not {TIMESTAMP_DTYPE}"
