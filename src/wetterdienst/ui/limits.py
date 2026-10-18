# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The limits of the REST API: what a request may ask for, refused before anything is downloaded (GH-3065).

A request that would return more than the server allows is a 400 problem of the kind `limit-exceeded`, which
names the limit and says how to narrow the request. The limits are the `WD_RESTAPI_*` settings (the defaults are
`RESTAPI_MAX_STATIONS`, `RESTAPI_MAX_ROWS` and `RESTAPI_MAX_STREAM_ROWS` of `wetterdienst.settings`); 0 switches
one off. They hold for the REST API and the MCP tools, which are its routes; the library and the CLI have none.

- **stations**: how many stations one `values` or `history` request may read. Counted from the selection, which
  is a lookup in the station list the server already holds: a `rank` counts as that many.
- **rows**: how many rows an answer sent as one body (JSON, GeoJSON, a chart) may have, and, for a streamed answer
  (NDJSON, CSV), a higher number. There is no row to count before the download, so the rows are *estimated*, as an
  upper bound: for each station, the readings its resolution can hold between the start of its record and the end
  of it, within the window of the request, times the parameters asked for. A station whose record is not
  published is counted from an assumed start that the periods of its dataset give (`_assumed_start`), so that a
  request without a `timestamp` is held to the limit as well; `drop_nulls` or a station with less data than its
  record makes the answer smaller.

The time span of a request is bounded through the rows: a window of a year of 1-minute readings is half a million
rows for one parameter, a century of daily ones is 36,500.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from pydantic import BaseModel, ConfigDict, Field

from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import count_readings
from wetterdienst.ui.problems import ProblemError, ProblemKind

if TYPE_CHECKING:
    from collections.abc import Sequence

    from wetterdienst.model.metadata import ParameterModel
    from wetterdienst.model.result import StationsResult
    from wetterdienst.settings import Settings


class Limits(BaseModel):
    """The limits and the timeout this server holds requests to, 0 meaning none."""

    model_config = ConfigDict(extra="forbid")

    max_stations: int = Field(
        description="The most stations one `values` or `history` request may read; a `rank` counts as that many.",
    )
    max_rows: int = Field(
        description="The most rows (estimated) of an answer sent as one body: json, geojson, a chart, and the "
        "answer of `interpolate` and `summarize`.",
    )
    max_stream_rows: int = Field(
        description="The most rows (estimated) of an answer streamed as `ndjson` or `csv` by `stations` or `values`.",
    )
    timeout: float = Field(
        description="The seconds a request may take until its answer begins, and a streamed answer between "
        "two chunks, else a 504.",
    )
    max_concurrent: int = Field(
        description="The most requests under `/api` the server works on at once, else a 503 with `Retry-After`; "
        "0 for none.",
    )


def limits_of(settings: Settings) -> Limits:
    """Give the limits a server with these settings holds requests to."""
    return Limits(
        max_stations=settings.restapi_max_stations,
        max_rows=settings.restapi_max_rows,
        max_stream_rows=settings.restapi_max_stream_rows,
        timeout=settings.restapi_timeout,
        max_concurrent=settings.restapi_max_concurrent,
    )


def _refuse(limit: str, maximum: int, requested: int, message: str) -> ProblemError:
    return ProblemError(
        400,
        message,
        ProblemKind.LIMIT_EXCEEDED,
        extra={"limit": limit, "maximum": maximum, "requested": requested},
    )


def selected_station_count(stations: StationsResult) -> int:
    """Count the stations a selection reads: a ranked one stops at its `rank`, whatever the list holds."""
    from wetterdienst.model.result import StationsFilter  # noqa: PLC0415

    count = stations.df.get_column("station_id").n_unique()
    if stations._stations_filter is StationsFilter.BY_RANK and stations._rank:  # noqa: SLF001
        return min(count, stations._rank)  # noqa: SLF001
    return count


def check_station_count(count: int, limits: Limits) -> None:
    """Refuse a request that reads more stations than the limit, naming how to read fewer."""
    if limits.max_stations and count > limits.max_stations:
        message = (
            f"This request reads {count} stations, more than the {limits.max_stations} this server allows for one "
            "request. Name fewer stations, or narrow the selection: a smaller `rank`, a smaller `distance` or "
            "bounding box. Request the rest in further calls."
        )
        error = _refuse("stations", limits.max_stations, count, message)
        raise error


def check_rows(rows: int, limits: Limits, *, streamed: bool) -> None:
    """Refuse an answer of more rows than the limit of its kind, saying what to change.

    An answer sent as one body that would fit a stream is told to stream.
    """
    maximum = limits.max_stream_rows if streamed else limits.max_rows
    if not maximum or rows <= maximum:
        return
    narrow = "Ask for a shorter `timestamp` window, fewer `parameters` or fewer stations"
    if streamed:
        name, what, advice = "stream_rows", "this server streams", f"{narrow}."
    else:
        name, what = "rows", "this server sends as one answer"
        streamable = not limits.max_stream_rows or rows <= limits.max_stream_rows
        advice = (
            f"{narrow}, or use `format=ndjson` or `format=csv`, which are streamed and allow more."
            if streamable
            else f"{narrow}."
        )
    message = f"This request would return about {rows:,} rows, more than the {maximum:,} {what}. {advice}"
    error = _refuse(name, maximum, rows, message)
    raise error


#: where the record of a station is assumed to begin if its provider publishes none and the dataset has historical
#: data: before the oldest archive of that kind the library reads (IMGW's begins in 1951). It matters for the datasets
#: that need no date, as a request for the others has the window of its `timestamp`; a station list that
#: publishes its record is not estimated from this. From 1950, daily readings are about 27,000 rows a parameter
_ASSUMED_RECORD_START = dt.datetime(1950, 1, 1, tzinfo=dt.UTC)
#: how far back a dataset of recent data reaches (DWD's `recent` holds about 500 days) and one of current data (a day
#: or so), as a margin over what they hold
_ASSUMED_RECENT_SPAN = dt.timedelta(days=731)
_ASSUMED_NOW_SPAN = dt.timedelta(days=2)


def _assumed_start(periods: Sequence[Period], end: dt.datetime) -> dt.datetime | None:
    """Give where the record of a station without published bounds is assumed to begin, from the periods of its dataset.

    The widest period of the dataset counts: historical data from `_ASSUMED_RECORD_START`, recent data two years and
    current data two days before `end`. A dataset of forecasts (`future`) has no record: what it holds is bounded by
    the horizon of the model, which no limit of this module needs to count, so None.
    """
    if Period.HISTORICAL in periods:
        return _ASSUMED_RECORD_START
    if Period.RECENT in periods:
        return end - _ASSUMED_RECENT_SPAN
    if Period.NOW in periods:
        return end - _ASSUMED_NOW_SPAN
    return None


def _utc(value: dt.datetime) -> dt.datetime:
    return value if value.tzinfo else value.replace(tzinfo=dt.UTC)


def estimate_rows(stations: StationsResult) -> int:
    """Estimate, as an upper bound, the rows `values` returns for the stations selected, see this module's docstring."""
    df = stations.df
    if df.is_empty() or not stations.parameters:
        return 0
    ids = df.get_column("station_id").unique(maintain_order=True)
    if (count := selected_station_count(stations)) < ids.len():
        ids = ids.head(count)
    df = df.filter(df.get_column("station_id").is_in(ids.implode()))
    parameters_of: dict[tuple[str, str], list[ParameterModel]] = {}
    for parameter in stations.parameters:
        key = (parameter.dataset.resolution.name, parameter.dataset.name.lower())
        parameters_of.setdefault(key, []).append(parameter)
    tidy = stations.options.tidy
    window_start = _utc(stations.start) if stations.start else None
    window_end = _utc(stations.end) if stations.end else None
    has_bounds = {"start_timestamp", "end_timestamp"} <= set(df.columns)
    rows = 0
    for row in df.select(
        "resolution", "dataset", *(["start_timestamp", "end_timestamp"] if has_bounds else [])
    ).iter_rows(named=True):
        parameters = parameters_of.get((row["resolution"], row["dataset"]))
        if not parameters:
            continue
        starts = [t for t in (window_start, _utc(row["start_timestamp"]) if row.get("start_timestamp") else None) if t]
        ends = [t for t in (window_end, _utc(row["end_timestamp"]) if row.get("end_timestamp") else None) if t]
        end = min(ends or [dt.datetime.now(dt.UTC)])
        if not starts:
            # no record bounds are published and the request names no start: assumed from the dataset
            assumed = _assumed_start(parameters[0].dataset.periods, end)
            if assumed is None:
                continue
            starts = [assumed]
        readings = count_readings(parameters[0].dataset.resolution.value, max(starts), end)
        rows += (readings or 0) * (len(parameters) if tidy else 1)
    return rows


def estimate_point_rows(
    parameters: Sequence[ParameterModel], start: dt.datetime | None, end: dt.datetime | None
) -> int:
    """Estimate the rows of an answer for one point (`interpolate`, `summarize`): the readings of the window."""
    if start is None or end is None:
        return 0
    return sum(
        count_readings(parameter.dataset.resolution.value, _utc(start), _utc(end)) or 0 for parameter in parameters
    )
