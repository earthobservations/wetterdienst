# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The size budget of an MCP tool's `values` and `stations` answer (GH-4022).

An assistant reads a tool's answer in its context, and a client saves one of more than 50,000 characters to a file
instead of handing it over (Claude Code does, whatever its tokens). Two calls spilled in the transcripts: a forecast
with no window (90,000 characters and more) and a listing of every station in a bounding box (1.7 million). Neither
limit of the REST API fires for them. So a tool's answer of `values` or `stations` is cut to `ANSWER_BUDGET`
characters, and says it was, in a warning of its `metadata` block (`answer-truncated`) that names what is left out and
the `timestamp` window to ask for it. Nothing is refused: the answer keeps what fits.

Only a tool's request is cut (`ui.mcp.is_tool_request`). The REST API, the command line and the library answer all of
it: the app lists every station of a network, and a script reads a whole series.

The budget holds for what the client receives (`ui.mcp.structured_size`): the JSON of the answer, and for CSV and
NDJSON the sentence the tool puts in front of the body, which carries the licence, the processing note and this
note. The note is in what is measured, so a cut answer is not over the budget by its own note.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

import polars as pl

from wetterdienst.model.result import StationsFilter
from wetterdienst.ui.mcp import structured_size
from wetterdienst.ui.response_metadata import response_headers, response_metadata
from wetterdienst.util.response_warnings import ANSWER_TRUNCATED, ResponseWarning, record_response_warning

if TYPE_CHECKING:
    from collections.abc import Callable

    from wetterdienst.model.result import StationsResult, ValuesResult
    from wetterdienst.ui.core import StationsRequest, ValuesRequest
    from wetterdienst.ui.response_metadata import ResponseMetadata

log = logging.getLogger(__name__)

#: the characters of what a client receives of a tool's `values` or `stations` answer, the `metadata` block and the
#: sentence of a CSV included. A constant, not a setting: 40,000 is under the 50,000 a client spills at, with room for
#: what the client adds, and the same for every host
ANSWER_BUDGET = 40_000

#: the formats whose body a model reads as data, which the budget holds. A chart (html, svg, png, jpg, webp, pdf) is
#: markup or an image that is not read as rows and is not repeated in the structured content
BUDGETED_FORMATS = frozenset({"json", "geojson", "csv", "ndjson"})

#: the media types of the formats that have a sentence in front of their body (`ui.mcp.structured_size`)
_MEDIA_TYPES = {"csv": "text/csv", "ndjson": "application/x-ndjson"}

#: the characters FastMCP adds around the JSON answer of a tool: `{"result":` and `}`
_RESULT_WRAPPER = len('{"result":}')

#: the selections that are small: a rank, a distance or a name asks for a few stations, so they are never cut
_SMALL_SELECTIONS = frozenset({StationsFilter.BY_RANK, StationsFilter.BY_DISTANCE, StationsFilter.BY_NAME})

_NARROWING = (
    "To get less at a time, narrow the `timestamp` window, ask for fewer parameters, or use `format=csv` with "
    "`shape=wide`, which is several times smaller."
)


@dataclass(frozen=True)
class _Attempt:
    """One cut of the answer: what it would be, and how many characters a client would receive of it."""

    content: str | bytes
    metadata: ResponseMetadata
    size: int
    note: str


def _text(content: str | bytes) -> str:
    return content if isinstance(content, str) else content.decode("utf-8")


def answer_size(content: str | bytes, request: StationsRequest | ValuesRequest, metadata: ResponseMetadata) -> int:
    """Count the characters a client receives of an answer in `request.format`, the sentence of a CSV included."""
    text = _text(content)
    if request.format in _MEDIA_TYPES:
        headers = {name.lower(): value for name, value in response_headers(metadata).items()}
        return structured_size(_MEDIA_TYPES[request.format], text, headers)
    # the structured content is the JSON FastMCP parsed and hands on compact, as the `result` of an object (the schema
    # of the tool is a union): the body may be indented (`pretty`), have a space after each of its separators (the
    # REST API writes `, ` and `: `) or have written each character that is not ASCII as an escape (`json`)
    return len(json.dumps(json.loads(text), separators=(",", ":"), ensure_ascii=False)) + _RESULT_WRAPPER


def _largest(low: int, high: int, fits: Callable[[int], bool], guess: int) -> int | None:
    """Find the largest `n` between `low` and `high` for which `fits(n)` is true, None if there is none.

    `fits` is true for the small and false for the large. The first probe is at `guess`, which a proportion of the
    sizes gives, so that an answer that is twice the budget does not begin by cutting at its middle.
    """
    best = None
    first = True
    while low <= high:
        probe = min(max(guess, low), high) if first else (low + high) // 2
        first = False
        if fits(probe):
            best = probe
            low = probe + 1
        else:
            high = probe - 1
    return best


def _iso(value: dt.datetime) -> str:
    """Write a timestamp as the `timestamp` argument takes it, in UTC with its offset."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=dt.UTC)
    return value.astimezone(dt.UTC).isoformat()


def _start_is_nearer_now(first: dt.datetime, last: dt.datetime) -> bool:
    """Tell whether the first timestamp of an answer is nearer to now than its last: a forecast, not a record."""
    now = dt.datetime.now(dt.UTC)
    first, last = (value if value.tzinfo else value.replace(tzinfo=dt.UTC) for value in (first, last))
    return abs(first - now) <= abs(last - now)


def _noted(
    result: StationsResult | ValuesResult, request: StationsRequest | ValuesRequest, note: str
) -> ResponseMetadata:
    """Build the `metadata` block of a cut answer: its own counts, and the note beside the warnings the walk raised."""
    metadata = response_metadata(result, request)
    warning = ResponseWarning(code=ANSWER_TRUNCATED, message=note)
    return metadata.model_copy(update={"warnings": [*metadata.warnings, warning]})


def _values_note(
    *,
    kept: int,
    total: int,
    stamps: list[dt.datetime],
    count: int,
    start: bool,
    window: str | None,
    within: int | None = None,
) -> str:
    """Write the note of a `values` answer cut to its first (`start`) or last `count` of `stamps` timestamps.

    `within` is the number of rows of the single timestamp that was cut through, where one timestamp alone is more
    than the budget. The next window is a `timestamp` the tool accepts: it begins at the first timestamp left out and
    ends where the caller's window did (or with the last timestamp of the answer, where they gave none).
    """
    total_stamps = len(stamps)
    kept_stamps = stamps[:count] if start else stamps[total_stamps - count :]
    left_out = total_stamps - count
    if left_out:
        if start:
            rest = f"{_iso(stamps[count])}/{window.split('/')[-1] if window else _iso(stamps[-1])}"
        else:
            rest = f"{_iso(stamps[0])}/{_iso(stamps[left_out - 1])}"
    else:
        rest = None
    head = f"The answer was cut to stay within {ANSWER_BUDGET:,} characters: "
    if within is not None:
        text = (
            f"{head}one timestamp ({_iso(kept_stamps[0])}) alone holds {within:,} rows and only the first "
            f"{kept:,} of them are returned, of {total:,} rows in all. A `timestamp` window cannot split a "
            "timestamp: ask for fewer parameters or stations, or use `format=csv` with `shape=wide`, which is "
            "several times smaller."
        )
        if rest:
            what = "the rest" if start else "the earlier part"
            text += f" The other {left_out:,} timestamps are left out; {what} is `timestamp={rest}`."
        return text
    kept_range = f"from {_iso(kept_stamps[0])} to {_iso(kept_stamps[-1])}"
    which = (
        "the start of the window is kept"
        if window
        else f"the {'start' if start else 'end'} is kept, as it is nearest to now"
    )
    text = (
        f"{head}{kept:,} of {total:,} rows are returned, {kept_range} ({count:,} of {total_stamps:,} timestamps; "
        f"{which})."
    )
    if rest:
        text += (
            f" For the rest, ask again with `timestamp={rest}`."
            if start
            else f" The earlier part is `timestamp={rest}`."
        )
    return f"{text} {_NARROWING}"


def fit_values(
    result: ValuesResult,
    request: ValuesRequest,
    content: str | bytes,
    metadata: ResponseMetadata,
    render: Callable[[ValuesResult, ResponseMetadata], str | bytes],
) -> tuple[str | bytes, ResponseMetadata]:
    """Cut the answer of a `values` tool call to the budget at a timestamp, and say so; unchanged where it fits.

    Without a `timestamp` from the caller the end nearest to now is kept: the start of a forecast, the latest part of
    a record. With one, its start is kept, so that the next window of the note continues it. At least one whole
    timestamp is kept, and a timestamp is cut through only where one alone is more than the budget. `render` writes
    the answer for a cut result and its block; `content` and `metadata` are the whole answer.
    """
    if request.format not in BUDGETED_FORMATS or result.df.is_empty() or "timestamp" not in result.df.columns:
        return content, metadata
    size = answer_size(content, request, metadata)
    if size <= ANSWER_BUDGET:
        return content, metadata
    df = result.df
    stamps = df.get_column("timestamp").drop_nulls().unique().sort().to_list()
    window = request.timestamp
    start = True if window or not stamps else _start_is_nearer_now(stamps[0], stamps[-1])
    total = df.height
    count_all = len(stamps)

    def attempt(cut: pl.DataFrame, count: int, within: int | None = None) -> _Attempt:
        cut_result = replace(result, df=cut)
        note = _values_note(
            kept=cut.height, total=total, stamps=stamps, count=count, start=start, window=window, within=within
        )
        cut_metadata = _noted(cut_result, request, note)
        return _Attempt(render(cut_result, cut_metadata), cut_metadata, 0, note)

    def measured(made: _Attempt) -> _Attempt:
        return replace(made, size=answer_size(made.content, request, made.metadata))

    def whole(count: int) -> _Attempt:
        boundary = stamps[count - 1] if start else stamps[count_all - count]
        cut = df.filter(pl.col("timestamp") <= boundary if start else pl.col("timestamp") >= boundary)
        return measured(attempt(cut, count))

    tried: dict[int, _Attempt] = {}

    def fits(count: int) -> bool:
        tried[count] = whole(count)
        return tried[count].size <= ANSWER_BUDGET

    best = _largest(1, count_all - 1, fits, max(1, count_all * ANSWER_BUDGET // size)) if count_all > 1 else None
    if best is not None:
        chosen = tried[best]
    else:
        # one timestamp is more than the budget: cut through it, keeping what fits of its rows
        only = stamps[0] if start else stamps[-1]
        rows = df.filter(pl.col("timestamp") == only)
        partial: dict[int, _Attempt] = {}

        def fits_rows(count: int) -> bool:
            partial[count] = measured(attempt(rows.head(count), 1, within=rows.height))
            return partial[count].size <= ANSWER_BUDGET

        kept = _largest(1, max(1, rows.height - 1), fits_rows, max(1, rows.height * ANSWER_BUDGET // size))
        chosen = partial[kept if kept is not None else 1]
    record_response_warning(ANSWER_TRUNCATED, chosen.note)
    log.info(f"Cut a values answer of {total} rows to {chosen.metadata.counts.rows} to stay within the budget.")
    return chosen.content, chosen.metadata


def fit_stations(
    result: StationsResult,
    request: StationsRequest,
    content: str | bytes,
    metadata: ResponseMetadata,
    render: Callable[[StationsResult, ResponseMetadata], str | bytes],
) -> tuple[str | bytes, ResponseMetadata]:
    """Cut the answer of a `stations` tool call to the budget, keeping the first stations; unchanged where it fits.

    A rank, a distance or a name asks for a few stations and is left as it is. Otherwise (all stations, a bounding
    box, `sql`, ids) the stations that fit are kept, in list order, and the note says how many match and what narrows
    them. `render` writes the answer for a cut result and its block; `content` and `metadata` are the whole answer.
    """
    if request.format not in BUDGETED_FORMATS or result._stations_filter in _SMALL_SELECTIONS:  # noqa: SLF001
        return content, metadata
    size = answer_size(content, request, metadata)
    if size <= ANSWER_BUDGET:
        return content, metadata
    df = result.df
    ids = df.get_column("station_id").unique(maintain_order=True)
    count_all = len(ids)
    if count_all < 2:
        return content, metadata

    tried: dict[int, _Attempt] = {}

    def fits(count: int) -> bool:
        cut = df.filter(pl.col("station_id").is_in(ids.head(count).implode()))
        cut_result = replace(result, df=cut)
        note = (
            f"The answer was cut to stay within {ANSWER_BUDGET:,} characters: the first {count:,} of {count_all:,} "
            f"stations are returned, in list order. {count_all:,} stations match; narrow with latitude, longitude and "
            "`rank` or `distance`, or `name`."
        )
        cut_metadata = _noted(cut_result, request, note)
        made = _Attempt(render(cut_result, cut_metadata), cut_metadata, 0, note)
        tried[count] = replace(made, size=answer_size(made.content, request, made.metadata))
        return tried[count].size <= ANSWER_BUDGET

    best = _largest(1, count_all - 1, fits, max(1, count_all * ANSWER_BUDGET // size))
    # where not even one station fits, the first is kept: the probes ended at it
    chosen = tried[best if best is not None else 1]
    record_response_warning(ANSWER_TRUNCATED, chosen.note)
    log.info(
        f"Cut a stations answer of {count_all} stations to {chosen.metadata.counts.stations} to stay within the budget."
    )
    return chosen.content, chosen.metadata
