# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""An MCP tool's forecast answer without a window starts at now (GH-4025).

A forecast (a network of `kind` forecast: `dwd/mosmix`, `dwd/dmo`, `dwd/swsmos`) is the rows of a model run, which
begins a few hours before the request was made: at 14:28 UTC the latest MOSMIX run's first row is 10:00. An assistant
that reads the first rows of the answer reports an hour that has passed as the forecast (the benchmark's
`forecast-tokyo` case did, in three of five runs of the large tier), and the size budget (`ui.budget`) spends its
characters on those hours before the future ones.

So a tool's `values` request for a forecast network with no `timestamp` of the caller leaves out the rows stamped
before the current period of their resolution, in UTC, and says so in a warning of the `metadata` block
(`forecast-from-now`) that names the `timestamp` window of the earlier part. The cut is made before the budget, so the
note is in what the budget counts and its characters go to future hours.

The start of "now" by the resolution of the row: the current hour for an hourly forecast and for anything finer or
subdaily (a reading of an hour stamped at the start of the hour is the current one, and so is the one stamped now), the
current 6-hour period of a `6_hours` forecast, the current day of a daily one, the month of a monthly one and the year
of an annual one. Today's forecast networks are all hourly; the others are what the same rule gives.

Left as they are: a request with a `timestamp` (the caller chose the part), a run the caller asked for by its `issue`
(an older run is past by nature, and asking for it says so), a network of another kind, and `interpolate` and
`summarize`, whose `timestamp` is required. Only a tool's request is cut (`ui.mcp.is_tool_request`): the REST API,
the command line and the library answer the whole model run.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import replace
from typing import TYPE_CHECKING

import polars as pl

from wetterdienst.metadata.resolution import Resolution
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


def applies(api: type[TimeseriesRequest], request: ValuesRequest) -> bool:
    """Tell whether a tool's `values` request is one whose answer starts at now.

    A forecast network, no `timestamp` of the caller and the latest run (no `issue`, or `latest`).
    """
    issue = request.issue
    return (
        api.metadata.kind == "forecast"
        and not request.timestamp
        and (issue is None or not issue.strip() or issue.strip().lower() == "latest")
    )


def _window(first: dt.datetime, last: dt.datetime) -> str:
    """Write the `timestamp` window the tool accepts for the stamps from `first` to `last`."""
    return f"{first.astimezone(dt.UTC).isoformat()}/{last.astimezone(dt.UTC).isoformat()}"


def _note(periods: dict[str, tuple[str, dt.datetime]], stamps: list[dt.datetime], rows: int, *, left: int) -> str:
    """Write the note of an answer that starts at now: the start, what is left out and the window that asks for it."""
    starts = sorted({(period, start) for period, start in periods.values()}, key=lambda item: item[1])
    if len(starts) == 1:
        period, start = starts[0]
        where = f"the current {period} ({start.isoformat()})"
    else:
        where = (
            "the current period of each resolution ("
            + ", ".join(f"{resolution} {start.isoformat()}" for resolution, (_, start) in sorted(periods.items()))
            + ")"
        )
    count = f"{len(stamps):,} earlier timestamps ({rows:,} rows)" if len(stamps) > 1 else f"{rows:,} earlier rows"
    if left:
        text = f"The answer starts at {where}: the {count} of the model run are left out."
    else:
        text = f"The model run ends before {where}: its {count} are left out and none is returned."
    return f"{text} For them, ask again with `timestamp={_window(stamps[0], stamps[-1])}`."


def forecast_from_now(result: ValuesResult) -> ValuesResult:
    """Give the result of a forecast without the rows stamped before now, and say so in a warning of the answer.

    The result as it is where no row is before now, which is no warning. Without rows left, the result has no
    `data_updated_at` (one of no rows is of no file), as for any cut that leaves none. A row has its `resolution`
    in every shape the core hands out; a frame without the column is read as hourly.
    """
    df = result.df
    if df.is_empty() or "timestamp" not in df.columns:
        return result
    now = _now()
    resolutions = (
        df.get_column("resolution").unique().to_list() if "resolution" in df.columns else [Resolution.HOURLY.value]
    )
    periods = {str(resolution): _start_of(str(resolution), now) for resolution in resolutions}
    starts = {resolution: start for resolution, (_, start) in periods.items()}
    if "resolution" in df.columns:
        before = pl.col("timestamp") < pl.col("resolution").cast(pl.String).replace_strict(
            starts, return_dtype=pl.Datetime("us", "UTC")
        )
    else:
        before = pl.col("timestamp") < pl.lit(starts[Resolution.HOURLY.value], dtype=pl.Datetime("us", "UTC"))
    left_out = df.filter(before.fill_null(value=False))
    if left_out.is_empty():
        return result
    kept = df.filter(~before.fill_null(value=False))
    stamps = left_out.get_column("timestamp").unique().sort().to_list()
    note = _note(periods, stamps, left_out.height, left=kept.height)
    record_response_warning(FORECAST_FROM_NOW, note)
    cut = replace(result, df=kept)
    return replace(cut, data_updated_at=None) if kept.is_empty() else cut
