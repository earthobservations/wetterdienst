# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""An MCP tool's forecast answer starts at now (GH-4025).

A forecast (a network of `kind` forecast: `dwd/mosmix`, `dwd/dmo`, `dwd/swsmos`) is the rows of a model run. The latest
MOSMIX-L or DMO run begins hours before the request was made (at 14:28 UTC its first row can be 10:00; MOSMIX-S and
SWSMOS begin at the current or the next hour). An assistant that reads the first rows of the answer reports an hour
that has passed as the forecast (the benchmark's `forecast-tokyo` case did, in three of five runs of the large tier),
and the size budget (`ui.budget`) spends its characters on those hours before the future ones.

So a tool's `values` request for a forecast network leaves out the rows stamped before the current period of their
resolution, in UTC, and says so in a warning of the `metadata` block (`forecast-from-now`) that names the `timestamp`
window of the earlier part. The cut is made before the budget, so the note is in what the budget counts and its
characters go to future hours.

The start of "now" by the resolution of the row: the current hour for an hourly forecast and for anything finer or
subdaily (a reading of an hour stamped at the start of the hour is the current one, and so is the one stamped now), the
current 6-hour period of a `6_hours` forecast, the current day of a daily one, the month of a monthly one and the year
of an annual one. Today's forecast networks are all hourly; the others are what the same rule gives.

Which requests are cut:

- no `timestamp` of the caller: every row before now;
- a `timestamp` of whole days (date precision, read off the caller's text: `2026-11-12` or `2026-11-12/2026-11-14`,
  never a time part) that contains now: the rows of today before now. The instructions tell a model to give a window,
  and a day is the window it gives. Days of the window before today are what the caller named, and stay;
- left as they are: a `timestamp` with a time part (served exactly as asked), a day window wholly in the past or in the
  future, a month or a year, a run the caller asked for by its `issue` (an older run is past by nature, and asking
  for it says so), a network of another kind, and `interpolate` and `summarize`, whose `timestamp` is required.

Only a tool's request is cut (`ui.mcp.is_tool_request`): the REST API, the command line and the library answer the
whole model run.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import replace
from typing import TYPE_CHECKING

import polars as pl

from wetterdienst.exceptions import InvalidTimeIntervalError
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.util.datetime import date_only, parse_date_window
from wetterdienst.util.response_warnings import FORECAST_FROM_NOW, record_response_warning

if TYPE_CHECKING:
    from wetterdienst.model.request import TimeseriesRequest
    from wetterdienst.model.result import ValuesResult
    from wetterdienst.ui.core import ValuesRequest


def _now() -> dt.datetime:
    """Give the time the cut is made from: a function of its own, so that a test can pin the clock."""
    return dt.datetime.now(dt.UTC)


def _start_of(resolution: str, now: dt.datetime) -> tuple[str, dt.datetime]:
    """Give the name of the period `now` is in for a resolution and where it starts, UTC."""
    hour = now.replace(minute=0, second=0, microsecond=0)
    if resolution == Resolution.HOUR_6.value:
        return "6-hour period", hour.replace(hour=hour.hour // 6 * 6)
    if resolution == Resolution.DAILY.value:
        return "day", hour.replace(hour=0)
    if resolution == Resolution.MONTHLY.value:
        return "month", hour.replace(day=1, hour=0)
    if resolution == Resolution.ANNUAL.value:
        return "year", hour.replace(month=1, day=1, hour=0)
    # hourly, finer than hourly, subdaily and a name this does not know
    return "hour", hour


def _is_day_window_around(timestamp: str, now: dt.datetime) -> bool:
    """Tell whether a caller's `timestamp` is of whole days and contains now.

    Whole days is decided from the text, not from what it parses to: a day is a string that is a date and nothing
    else (`util.datetime.date_only`), alone or as both halves of one span. A span is as the tool reads it: from the
    start of its first day to the end of its last.
    """
    halves = timestamp.split("/")
    if len(halves) > 2 or any(date_only(half) is None for half in halves):
        return False
    try:
        start, _ = parse_date_window(halves[0])
        _, end = parse_date_window(halves[-1])
    except (InvalidTimeIntervalError, ValueError, OverflowError):
        return False
    return start <= now <= end


def applies(api: type[TimeseriesRequest], request: ValuesRequest) -> bool:
    """Tell whether a tool's `values` request is one whose answer starts at now.

    A forecast network, the latest run (no `issue`, or `latest`), and either no `timestamp` of the caller or one of
    whole days that contains now.
    """
    issue = request.issue
    if api.metadata.kind != "forecast" or not (issue is None or not issue.strip() or issue.strip().lower() == "latest"):
        return False
    return not request.timestamp or _is_day_window_around(request.timestamp, _now())


def lower_bound(request: ValuesRequest) -> dt.datetime | None:
    """Give where the cut stops looking for rows to leave out: none without a `timestamp`, else the start of today.

    A day window names days, and the rows of a day before today are what the caller asked for.
    """
    if not request.timestamp:
        return None
    return _now().replace(hour=0, minute=0, second=0, microsecond=0)


def _window(first: dt.datetime, last: dt.datetime) -> str:
    """Write the `timestamp` window the tool accepts for the stamps from `first` to `last`."""
    return f"{first.astimezone(dt.UTC).isoformat()}/{last.astimezone(dt.UTC).isoformat()}"


def _amount(stamps: int, rows: int) -> str:
    """Write what was left out: `the earlier timestamp (2 rows)`, `the 4 earlier timestamps (8 rows)`."""
    row_text = f"{rows:,} row" if rows == 1 else f"{rows:,} rows"
    if stamps == 1:
        return f"the earlier timestamp ({row_text})"
    return f"the {stamps:,} earlier timestamps ({row_text})"


def _note(
    periods: dict[str, tuple[str, dt.datetime]],
    left_out: dict[str, tuple[list[dt.datetime], int]],
    *,
    left: int,
) -> str:
    """Write the note of an answer that starts at now: the start, what is left out and the window that asks for it.

    `left_out` is, for each resolution that lost rows, its timestamps and its number of rows. With one resolution the
    note has one window; with several it has one for each, since a window of one resolution can span rows of another
    that were kept, and a window asked for returns the rows of every resolution in it.
    """
    starts = sorted(set(periods.values()), key=lambda item: item[1])
    if len(starts) == 1:
        period, start = starts[0]
        where = f"the current {period} ({start.isoformat()})"
    else:
        where = (
            "the current period of each resolution ("
            + ", ".join(f"{resolution} {start.isoformat()}" for resolution, (_, start) in sorted(periods.items()))
            + ")"
        )
    stamps = {stamp for times, _ in left_out.values() for stamp in times}
    rows = sum(count for _, count in left_out.values())
    what = _amount(len(stamps), rows)
    verb = "is" if len(stamps) == 1 else "are"
    if left:
        text = f"The answer starts at {where}: {what} of the model run {verb} left out."
    else:
        text = f"The model run ends before {where}: {what} {verb} left out and none is returned."
    if len(left_out) == 1:
        times, _ = next(iter(left_out.values()))
        window = _window(times[0], times[-1])
        return f"{text} For {'it' if len(stamps) == 1 else 'them'}, ask again with `timestamp={window}`."
    windows = "; ".join(
        f"{resolution}: `timestamp={_window(times[0], times[-1])}`"
        for resolution, (times, _) in sorted(left_out.items())
    )
    return f"{text} For them, ask again by resolution, {windows}."


def forecast_from_now(result: ValuesResult, *, floor: dt.datetime | None = None) -> ValuesResult:
    """Give the result of a forecast without the rows stamped before now, and say so in a warning of the answer.

    `floor` is where the cut stops looking: a row stamped before it is kept (the days before today of a day window).
    The result as it is where no row is before now, which is no warning. Without rows left, the result has no
    `data_updated_at` (one of no rows is of no file), as for any cut that leaves none. A row has its `resolution`
    in every shape the core hands out; a frame without the column is read as hourly.
    """
    df = result.df
    if df.is_empty() or "timestamp" not in df.columns:
        return result
    now = _now()
    has_resolution = "resolution" in df.columns
    resolutions = df.get_column("resolution").unique().to_list() if has_resolution else [Resolution.HOURLY.value]
    periods = {str(resolution): _start_of(str(resolution), now) for resolution in resolutions}
    starts = {resolution: start for resolution, (_, start) in periods.items()}
    timestamp = pl.col("timestamp")
    if has_resolution:
        before = timestamp < pl.col("resolution").cast(pl.String).replace_strict(
            starts, return_dtype=pl.Datetime("us", "UTC")
        )
    else:
        before = timestamp < pl.lit(starts[Resolution.HOURLY.value], dtype=pl.Datetime("us", "UTC"))
    if floor is not None:
        before &= timestamp >= pl.lit(floor, dtype=pl.Datetime("us", "UTC"))
    before = before.fill_null(value=False)
    gone = df.filter(before)
    if gone.is_empty():
        return result
    kept = df.filter(~before)
    if has_resolution:
        left_out = {
            str(resolution): (frame.get_column("timestamp").unique().sort().to_list(), frame.height)
            for (resolution,), frame in gone.partition_by("resolution", as_dict=True).items()
        }
    else:
        left_out = {Resolution.HOURLY.value: (gone.get_column("timestamp").unique().sort().to_list(), gone.height)}
    record_response_warning(FORECAST_FROM_NOW, _note(periods, left_out, left=kept.height))
    cut = replace(result, df=kept)
    return replace(cut, data_updated_at=None) if kept.is_empty() else cut
