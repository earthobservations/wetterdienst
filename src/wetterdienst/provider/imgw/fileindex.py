# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""File index helpers for IMGW providers.

IMGW's file server groups the actual data files (zips) into per-period subdirectories, e.g.::

    dobowe/klimat/2023/2023_01_k.zip
    dobowe/klimat/1951_1955/1951_k.zip

Subdirectory names are either a single year (``YYYY``) or a year range (``YYYY_YYYY``) and always cover
exactly the date range of the files within. Since every IMGW dataset requires a date range to be given,
this lets us list only the subdirectories that can possibly contain matching files instead of recursively
walking the entire (fairly deep and wide) directory tree on every request.
"""

from __future__ import annotations

import datetime as dt
import re
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import polars as pl
import portion

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.util.network import list_remote_directory_fsspec

if TYPE_CHECKING:
    from wetterdienst.settings import Settings

_FOLDER_PATTERN = re.compile(r"^(?P<start>\d{4})(?:_(?P<end>\d{4}))?$")
# fallback interval for folder names that don't match the expected pattern, so we never silently drop data
_ALWAYS_OVERLAPS = portion.closed(
    dt.datetime.min.replace(tzinfo=ZoneInfo("UTC")),
    dt.datetime.max.replace(tzinfo=ZoneInfo("UTC")),
)


def _folder_interval(folder_name: str) -> portion.Interval:
    """Parse the date interval covered by an IMGW period folder name (``YYYY`` or ``YYYY_YYYY``)."""
    match = _FOLDER_PATTERN.match(folder_name.rstrip("/").rsplit("/", 1)[-1])
    if not match:
        return _ALWAYS_OVERLAPS
    year_start = int(match.group("start"))
    year_end = int(match.group("end") or year_start)
    return portion.closed(
        dt.datetime(year_start, 1, 1, tzinfo=ZoneInfo("UTC")),
        dt.datetime(year_end, 12, 31, tzinfo=ZoneInfo("UTC")),
    )


def list_files_for_interval(
    url: str,
    settings: Settings,
    interval: portion.Interval | None,
    cache_expiry: CacheExpiry = CacheExpiry.FILEINDEX,
) -> list[str]:
    """List all file urls below ``url``, only descending into period folders that overlap ``interval``.

    If ``interval`` is None, all period folders are listed (equivalent to a full recursive listing).
    """
    entries = list_remote_directory_fsspec(url, settings, cache_expiry)
    files = [entry["name"] for entry in entries if entry["type"] == "file"]
    folders = [entry["name"] for entry in entries if entry["type"] == "directory"]
    if interval is not None:
        folders = [folder for folder in folders if _folder_interval(folder).overlaps(interval)]
    for folder in folders:
        folder_entries = list_remote_directory_fsspec(folder, settings, cache_expiry)
        files.extend(entry["name"] for entry in folder_entries if entry["type"] == "file")
    return files


def keep_files_overlapping(
    df_files: pl.DataFrame,
    start: pl.Expr,
    end: pl.Expr,
    interval: portion.Interval,
) -> pl.DataFrame:
    """Keep the files whose period, from ``start`` to ``end`` (both included), overlaps ``interval``.

    ``start`` and ``end`` are expressions on the columns of ``df_files`` that give the first and last instant a file
    covers, read from its name. A name they cannot be read from is an error, not a file to leave out: a period
    that is not there has nothing to compare, and dropping the file would drop its data without a word.
    """
    df_files = df_files.with_columns(start.alias("start_timestamp"), end.alias("end_timestamp"))
    unreadable = df_files.filter(pl.col("start_timestamp").is_null() | pl.col("end_timestamp").is_null())
    if not unreadable.is_empty():
        msg = f"Cannot read the period of IMGW file(s) from their names: {unreadable.get_column('file').to_list()}"
        raise ValueError(msg)
    if interval.empty:
        return df_files.clear()
    # the instants are compared, whatever zone the request's bounds are written in
    upper = pl.lit(interval.upper).dt.convert_time_zone("UTC")
    lower = pl.lit(interval.lower).dt.convert_time_zone("UTC")
    # a period that ends before it starts is empty, and overlaps nothing
    return df_files.filter(
        (pl.col("start_timestamp") <= pl.col("end_timestamp"))
        & (pl.col("start_timestamp") <= upper)
        & (pl.col("end_timestamp") >= lower)
    )
