# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Datetime utilities for the wetterdienst package."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import polars as pl
from dateutil.relativedelta import relativedelta

from wetterdienst.exceptions import InvalidTimeIntervalError
from wetterdienst.metadata.resolution import Resolution

if TYPE_CHECKING:
    from collections.abc import Iterable


def round_minutes(timestamp: dt.datetime, step: int) -> dt.datetime:
    """Align timestamp to the given minute mark before tm.

    - https://stackoverflow.com/a/3464000
    Args:
        timestamp: timestamp to align
        step: minute mark to align to

    Returns:
        aligned timestamp

    """
    timestamp = timestamp.replace(second=0, microsecond=0)
    change = dt.timedelta(minutes=timestamp.minute % step)
    return timestamp - change


def raster_minutes(timestamp: dt.datetime, value: int) -> dt.datetime:
    """Align timestamp to the most recent minute mark.

    - https://stackoverflow.com/a/55013608
    - https://stackoverflow.com/a/60709050

    Args:
        timestamp: timestamp to align
        value: minute mark to align to

    Returns:
        aligned timestamp

    """
    timestamp = timestamp.replace(second=0, microsecond=0)

    if timestamp.minute < value:
        timestamp = timestamp - dt.timedelta(hours=1)

    return timestamp.replace(minute=value)


def mktimerange(
    resolution: Resolution,
    date_from: dt.datetime,
    date_to: dt.datetime | None = None,
) -> tuple[dt.datetime, dt.datetime]:
    """Compute appropriate time ranges for monthly and annual time resolutions.

    This takes into account to properly floor/ceil the date_from/date_to
    values to respective "begin of month/year" and "end of month/year" values.

    Args:
        resolution: time resolution as enumeration
        date_from: datetime string or object
        date_to: datetime string or object

    Returns:
        Tuple of two Timestamps: "date_from" and "date_to"

    """
    if date_to is None:
        date_to = date_from

    if resolution == Resolution.ANNUAL:
        date_from = date_from + relativedelta(month=1, day=1)
        date_to = date_to + relativedelta(month=12, day=31)

    elif resolution == Resolution.MONTHLY:
        date_from = date_from + relativedelta(day=1)
        date_to = date_to + relativedelta(day=31)

    else:
        msg = "mktimerange only implemented for annual and monthly time ranges"
        raise NotImplementedError(msg)

    return date_from, date_to


# How much of an instant a date string actually names. "2019" names a year, "2019-12" a month and
# "2019-12-28" a day; only a string carrying a time names a single instant.
_YEAR = "year"
_MONTH = "month"
_DAY = "day"
_INSTANT = "instant"


def date_only(date_string: str) -> dt.date | None:
    """Return the day a string names where it is a date and nothing else, else ``None``.

    "2020-05-01", "20200501" or "2020-W01-1" each name a whole day. Asking `date` rather than looking
    for a separator is what tells them from a datetime -- `datetime.fromisoformat` takes any single
    character between the two, so "2020-05-01t12" and "2020-05-01+02:00" are times of day however
    unusually they are written. A month ("2020-05") or a year ("2020") is no day, and is ``None`` too.

    Args:
        date_string: Date string to read

    Returns:
        The day, or ``None`` where the string is no date without a time

    """
    try:
        return dt.date.fromisoformat(date_string)
    except ValueError:
        return None


def _parse_date_with_precision(date_string: str) -> tuple[dt.datetime, str]:
    """Parse a date string to its first instant and the precision it was written with.

    Args:
        date_string: Date string to parse

    Returns:
        The first instant the string names and one of the precisions above

    """
    day = date_only(date_string)
    if day is not None:
        return _as_utc(dt.datetime.combine(day, dt.time())), _DAY
    try:
        date_parsed = dt.datetime.fromisoformat(date_string)
    except ValueError:
        pass
    else:
        return _as_utc(date_parsed), _INSTANT
    for fmt, precision in (("%Y-%m", _MONTH), ("%Y", _YEAR)):
        try:
            date_parsed = dt.datetime.strptime(date_string, fmt)  # noqa: DTZ007
        except ValueError:
            continue
        return _as_utc(date_parsed), precision
    msg = f"date_string {date_string} could not be parsed"
    raise InvalidTimeIntervalError(msg)


def _as_utc(date_parsed: dt.datetime) -> dt.datetime:
    """Read a timestamp without a zone as UTC."""
    if not date_parsed.tzinfo:
        return date_parsed.replace(tzinfo=ZoneInfo("UTC"))
    return date_parsed


def parse_date(date_string: str) -> dt.datetime:
    """Parse date string to datetime object.

    Supported formats:
    - iso formats supported by datetime
    - year month format e.g. 2020-10
    - year format e.g. 2020

    The first instant of what the string names, so "2020-10" is the 1st of October. Use
    ``parse_date_span`` where the rest of the month is meant too.

    Args:
        date_string: Date string to parse

    Returns:
        datetime object

    """
    return _parse_date_with_precision(date_string)[0]


def parse_date_span(date_string: str) -> tuple[dt.datetime, dt.datetime | None]:
    """Parse a date string into the span of time it names.

    A date string names an instant only as precisely as it is written: "2019" is a year, "2019-12"
    a month and "2019-12-28" a day, each of which covers everything measured within it. Reading
    them as their first instant instead answers "2019-12" with the 1st of December alone, and for
    anything measured more often than daily, with midnight alone.

    Args:
        date_string: Date string to parse

    Returns:
        The first instant of the span and the first instant after it, or ``None`` for the end where
        the string carries a time and so names one instant rather than a span

    """
    start, precision = _parse_date_with_precision(date_string)
    if precision == _INSTANT:
        return start, None
    try:
        if precision == _DAY:
            return start, start + dt.timedelta(days=1)
        if precision == _MONTH:
            return start, start + relativedelta(months=1)
        return start, start + relativedelta(years=1)
    except (OverflowError, ValueError) as e:
        # a span reaching past year 9999, the last a datetime holds: `9999`, `9999-12`, `9999-12-31`
        raise InvalidTimeIntervalError(str(e)) from e


def parse_date_window(date_string: str) -> tuple[dt.datetime, dt.datetime]:
    """Parse a date string into a window closed on both sides.

    The span of ``parse_date_span``, given as the first and the last instant it covers, for callers
    that filter inclusively -- a request window does. Timestamps are stored to the microsecond, so
    stepping back one from the start of the next span leaves nothing between the two.

    Args:
        date_string: Date string to parse

    Returns:
        The first and last instant the string covers

    """
    start, end_exclusive = parse_date_span(date_string)
    if end_exclusive is None:
        return start, start
    return start, end_exclusive - dt.timedelta(microseconds=1)


def _parse_datetime_from_formats(string: str, formats: list[str]) -> dt.datetime:
    """Parse datetime from a string given a number of possible formats."""
    for fmt in formats:
        try:
            return dt.datetime.strptime(string, fmt)  # noqa: DTZ007
        except ValueError:
            pass
    msg = f"datetime could not be parsed from {string} given the formats {formats}"
    raise ValueError(msg)


# One way of writing a timestamp in every body the library hands out as text (JSON, GeoJSON, CSV),
# whichever result it comes from: ISO 8601, to the microsecond, in UTC with its offset, such as
# `2026-09-01T00:00:00.000000+00:00`. A JSON consumer then reads the same field the same way from
# values, stations, history and alerts, REST, CLI and MCP.


def format_timestamp(value: dt.datetime) -> str:
    """Write a timestamp as text in the one format of the library, e.g. `2026-09-01T00:00:00.000000+00:00`.

    A timestamp in another zone is converted to UTC, and one without a zone is read as UTC, as it is
    everywhere else in the library.
    """
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.UTC)
    return value.astimezone(dt.UTC).isoformat(timespec="microseconds")


def newest(dates: Iterable[dt.datetime]) -> dt.datetime | None:
    """Give the newest of some dates, null for none; a date without a zone is read as UTC, as everywhere else."""
    return max((d if d.tzinfo else d.replace(tzinfo=dt.UTC) for d in dates), default=None)


#: the earliest date taken for the date of an update: what a source gives before it is no date of one (an epoch, a
#: year 1 default), and an answer must not be dated by it
EARLIEST_UPDATE = dt.datetime(1990, 1, 1, tzinfo=dt.UTC)


def is_plausible_update(date: dt.datetime) -> bool:
    """Tell whether a date a source states can be the date of an update: from 1990 to a day beyond now.

    A source's clock may be a little ahead, so a day is allowed, and no more: a date that misleads is worse than none.
    """
    if date.tzinfo is None:
        date = date.replace(tzinfo=dt.UTC)
    return EARLIEST_UPDATE <= date <= dt.datetime.now(dt.UTC) + dt.timedelta(days=1)


def parse_source_date(text: object) -> dt.datetime | None:
    """Read the date a source states for an update as ISO 8601 text into UTC; null where it is no such date.

    A text that is no ISO 8601 date, one whose UTC time is out of range (`9999-12-31T23:59:59-01:00`) and one before
    1990 give none, so that a source's mistake does not fail the request. Whether the date is too late to be one of
    an update is for the one who takes it (`is_plausible_update`), which a date that is not read from text passes too.
    """
    if not isinstance(text, str):
        return None
    try:
        value = dt.datetime.fromisoformat(text)
        value = value.replace(tzinfo=dt.UTC) if value.tzinfo is None else value.astimezone(dt.UTC)
    except (ValueError, OverflowError):
        return None
    return None if value < EARLIEST_UPDATE else value


def timestamps_to_string(df: pl.DataFrame, columns: Iterable[str] | None = None) -> pl.DataFrame:
    """Write the datetime columns of a frame as text in the format of `format_timestamp`, nulls staying null.

    Args:
        df: the frame
        columns: the columns to write, which have to be datetimes; every datetime column when not given

    Returns:
        The frame with those columns as `String`.

    """
    wanted = None if columns is None else set(columns)
    expressions = []
    for name, dtype in df.schema.items():
        if not isinstance(dtype, pl.Datetime) or (wanted is not None and name not in wanted):
            continue
        # a stamp without a zone is read as UTC, as everywhere in the library
        in_utc = (
            pl.col(name).dt.replace_time_zone("UTC")
            if dtype.time_zone is None
            else pl.col(name).dt.convert_time_zone("UTC")
        )
        expressions.append(in_utc.dt.cast_time_unit("us").dt.to_string("iso:strict"))
    return df.with_columns(expressions)
