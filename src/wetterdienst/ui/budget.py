# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The size budget of an MCP tool's answer of rows (GH-4022, GH-4024).

The answers it holds are those of `values`, `stations`, `interpolate`, `summarize`,
`station_ids` (`fit_station_ids`: the stations that fit, with a note), `coverage` (which is no rows but nested:
`fit_coverage`) and `alerts` (`fit_alerts`, GH-4338: a warning is mostly polygon and areas, which go first, then the
least severe warnings).

An assistant reads a tool's answer in its context, and a client saves one of more than 50,000 characters to a file
instead of handing it over (Claude Code does, whatever its tokens). Two calls spilled in the transcripts: a forecast
with no window (90,000 characters and more) and a listing of every station in a bounding box (1.7 million). Neither
limit of the REST API fires for them. So a tool's answer of `values` or `stations` is cut to `ANSWER_BUDGET`
characters, and says it was, in a warning of its `metadata` block (`answer-truncated`) that names what is left out and
the `timestamp` window to ask for it. Nothing is refused: the answer keeps what fits.

The answers of `interpolate` and `summarize` are series of timestamps as those of `values` are, and are cut the same
way (`fit_values`; their `timestamp` is required, so the start of their window is the part kept). A `with_metadata`
block is kept, and the stations or timestamps are cut to make room for it; one with which not even one station or
timestamp fits is left out (when one fits without it), and so is the block of a name or of a single station, whose rows
are not cut, where it is what makes the answer over the budget.

Only a tool's request is cut (`ui.mcp.is_tool_request`). The REST API, the command line and the library answer all of
it: the app lists every station of a network, and a script reads a whole series.

The budget holds for what the client receives (`ui.mcp.structured_size`): the JSON of the answer, and for CSV and
NDJSON the JSON of the structured content, the sentence the tool puts in front of the body (it carries the licence,
the processing note and this note) and the body, with each newline and quote written as the escape it is there
(GH-4029). The note is in what is measured, so a cut answer is not over the budget by its own note.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any

import polars as pl

from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.model.row_selection import MAX_TOOL_SERIES
from wetterdienst.ui.mcp import structured_size
from wetterdienst.ui.response_metadata import (
    Counts,
    response_headers,
    response_metadata,
    station_ids_headers,
)
from wetterdienst.util.response_warnings import ANSWER_TRUNCATED, ResponseWarning, record_response_warning

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping, Sequence

    from wetterdienst.core.station_search import StationIdSearchResult
    from wetterdienst.model.group_statistics import SeriesStatistics, StatisticsPlan, StatisticsResult
    from wetterdienst.model.result import InterpolatedValuesResult, SummarizedValuesResult, ValuesResult
    from wetterdienst.provider.dwd.alerts.api import DwdWeatherAlertResult
    from wetterdienst.ui.core import InterpolationRequest, StationsRequest, SummaryRequest, ValuesRequest
    from wetterdienst.ui.response_metadata import ResponseMetadata, StationIdsMetadata, StatisticsMetadata

    _SeriesResult = ValuesResult | InterpolatedValuesResult | SummarizedValuesResult
    _SeriesRequest = ValuesRequest | InterpolationRequest | SummaryRequest
    _ListRequest = StationsRequest

log = logging.getLogger(__name__)

#: the characters of what a client receives of a tool's `values` or `stations` answer, the `metadata` block and the
#: sentence of a CSV included. A constant, not a setting: 40,000 is under the 50,000 a client spills at, with room for
#: what the client adds, and the same for every host
ANSWER_BUDGET = 40_000

#: the formats whose body a model reads as data, which the budget holds: the formats of a tool. A chart (html, svg,
#: png, jpg, webp, pdf) is none of them, and is refused before the route is called (`ui.mcp`, GH-4318)
BUDGETED_FORMATS = frozenset({"json", "geojson", "csv", "ndjson"})

#: the media types of the formats that have a sentence in front of their body (`ui.mcp.structured_size`)
_MEDIA_TYPES = {"csv": "text/csv", "ndjson": "application/x-ndjson"}

#: the characters FastMCP adds around the JSON answer of a tool: `{"result":` and `}`
_RESULT_WRAPPER = len('{"result":}')

#: the selections that are small: a name asks for a few stations, so it is never cut. A distance and a rank are not
#: among them: a wide distance lists hundreds of stations (983 within 500 km of Berlin), and a large rank asks for as
#: many (700), so both are cut to the nearest that fit (GH-4029, GH-4036)
_SMALL_SELECTIONS = frozenset({StationsFilter.BY_NAME})


@dataclass(frozen=True)
class _Attempt:
    """One cut of the answer: what it would be, and how many characters a client would receive of it."""

    content: str | bytes
    metadata: ResponseMetadata
    size: int
    note: str


def _text(content: str | bytes) -> str:
    return content if isinstance(content, str) else content.decode("utf-8")


def answer_size(content: str | bytes, request: _ListRequest | _SeriesRequest, metadata: ResponseMetadata) -> int:
    """Count the characters a client receives of an answer in `request.format`, the sentence of a CSV included."""
    return _size_in(content, request.format, metadata)


def _size_in(content: str | bytes, fmt: str, metadata: ResponseMetadata) -> int:
    """Count the characters a client receives of an answer in `fmt`, the sentence of a CSV included."""
    text = _text(content)
    if fmt in _MEDIA_TYPES:
        headers = {name.lower(): value for name, value in response_headers(metadata).items()}
        return structured_size(_MEDIA_TYPES[fmt], text, headers)
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


def _block(result: StationsResult | _SeriesResult, request: _ListRequest | _SeriesRequest) -> ResponseMetadata:
    """Build the `metadata` block of the answer to `request`."""
    return response_metadata(result, request)


def _noted(
    result: StationsResult | _SeriesResult, request: _ListRequest | _SeriesRequest, note: str
) -> ResponseMetadata:
    """Build the `metadata` block of a cut answer: its own counts, and the note beside the warnings the walk raised."""
    metadata = _block(result, request)
    warning = ResponseWarning(code=ANSWER_TRUNCATED, message=note)
    return metadata.model_copy(update={"warnings": [*metadata.warnings, warning]})


def _has_shape(request: _ListRequest | _SeriesRequest) -> bool:
    """Tell whether the request can ask for the wide shape: `values` can, `interpolate` and `summarize` cannot."""
    return hasattr(request, "shape")


def _wide_csv_hint(request: _ListRequest | _SeriesRequest) -> bool:
    """Tell whether `format=csv` with `shape=wide` is still something to suggest: not where the request is that."""
    return _has_shape(request) and not (request.format == "csv" and getattr(request, "shape", None) == "wide")


def _narrowing(request: _ListRequest | _SeriesRequest) -> str:
    """Write the ways to get less in one answer, leaving out the one the request already took.

    An estimate (`interpolate`, `summarize`) has no wide shape, and its CSV is about half the size of its JSON.
    """
    if not _has_shape(request):
        if request.format == "csv":
            return "To get less at a time, narrow the `timestamp` window or ask for fewer parameters."
        return (
            "To get less at a time, narrow the `timestamp` window, ask for fewer parameters, or use `format=csv`, "
            "which is about half the size."
        )
    if _wide_csv_hint(request):
        return (
            "To get less at a time, narrow the `timestamp` window, ask for fewer parameters, or use `format=csv` "
            "with `shape=wide`, which is several times smaller."
        )
    return "To get less at a time, narrow the `timestamp` window or ask for fewer parameters."


def _head(*, honest: bool) -> str:
    """Begin a note: that the answer was cut to the budget, or, where it cannot be, that it is still over it."""
    if honest:
        return f"The answer was cut as far as it goes and is still over {ANSWER_BUDGET:,} characters: "
    return f"The answer was cut to stay within {ANSWER_BUDGET:,} characters: "


def _block_left_out(characters: int) -> str:
    """Write the note of a `with_metadata` block that was left out of the answer, which is more than the budget."""
    return (
        f"The `with_metadata` block ({characters:,} characters) was left out to stay within {ANSWER_BUDGET:,} "
        "characters; read units with `coverage` or `glossary`."
    )


def _values_note(
    *,
    request: _SeriesRequest,
    kept: int,
    total: int,
    stamps: list[dt.datetime],
    count: int,
    start: bool,
    window: str | None,
    within: int | None = None,
    lead: str = "",
    honest: bool = False,
) -> str:
    """Write the note of a `values` answer cut to its first (`start`) or last `count` of `stamps` timestamps.

    `within` is the number of rows of the single timestamp that was cut through, where one timestamp alone is more
    than the budget. The next window is a `timestamp` the tool accepts: it begins at the first timestamp left out and
    ends where the caller's window did (or with the last timestamp of the answer, where they gave none). `lead` is
    what was said of the `with_metadata` block that was left out, `honest` that even so the answer is over the budget.
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
    head = f"{lead} {_head(honest=honest)}" if lead else _head(honest=honest)
    if within is not None:
        returned = "only the first row is" if kept == 1 else f"only the first {kept:,} rows are"
        hint = (
            ", or use `format=csv` with `shape=wide`, which is several times smaller" if _wide_csv_hint(request) else ""
        )
        text = (
            f"{head}one timestamp ({_iso(kept_stamps[0])}) alone holds {within:,} rows and {returned} returned, "
            f"of {total:,} rows in all. A `timestamp` window cannot split a timestamp: ask for fewer parameters or "
            f"stations{hint}."
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
            else f" For the earlier part, ask again with `timestamp={rest}`."
        )
    return f"{text} {_narrowing(request)}"


def _made(
    result: StationsResult | _SeriesResult,
    request: _ListRequest | _SeriesRequest,
    frame: pl.DataFrame,
    note: str,
    render: Callable[[Any, ResponseMetadata, Any], str | bytes],
) -> _Attempt:
    """Make the answer for `frame` of `result`, with `note` in its warnings, and count what a client receives.

    An estimate lists the stations its rows were made from, so one cut down lists those of the rows that are left.
    """
    cut = replace(result, df=frame)
    if not isinstance(cut, StationsResult):
        cut = cut._with_stations_of_rows()  # noqa: SLF001
    metadata = _noted(cut, request, note)
    content = render(cut, metadata, request)
    return _Attempt(content, metadata, answer_size(content, request, metadata), note)


def _lean(request: Any) -> Any:  # noqa: ANN401
    """Give the request without its `with_metadata`: the units, the quality legend and the settings are left out."""
    return request.model_copy(update={"with_metadata": False})


def _without_block(
    result: StationsResult | _SeriesResult,
    request: _ListRequest | _SeriesRequest,
    render: Callable[[Any, ResponseMetadata, Any], str | bytes],
    fit: Callable[[Any, int, str], _Attempt] | None,
) -> tuple[_Attempt, Any] | None:
    """Try an answer that is over the budget with its `with_metadata` block again without the block.

    The block (the units, the quality legend and the settings of every dataset asked for) can be tens of thousands of
    characters: with it not even the smallest cut, one timestamp or one station, may fit, although without it many do.
    The request is made without `with_metadata`, the answer is fitted again by `fit(request, size, lead)` (`lead` is
    the note of what was left out) and, where it fits the budget now, given back with that request. None where the
    request has no block, or where leaving it out does not help either, which `fit_*` then tells as it is. Without a
    `fit` the rows are not cut: the answer is the whole one without the block, or none.
    """
    if not getattr(request, "with_metadata", False):
        return None
    empty = result.df.head(0)
    lean = _lean(request)
    block = _made(result, request, empty, "", render).size - _made(result, lean, empty, "", render).size
    lead = _block_left_out(block)
    whole = _made(result, lean, result.df, lead, render)
    fitted = whole if whole.size <= ANSWER_BUDGET or fit is None else fit(lean, whole.size, lead)
    return (fitted, lean) if fitted.size <= ANSWER_BUDGET else None


def _fit_values(
    result: _SeriesResult,
    request: _SeriesRequest,
    render: Callable[[Any, ResponseMetadata, Any], str | bytes],
    size: int,
    *,
    lead: str,
    honest: bool,
) -> _Attempt:
    """Find the longest cut of a `values` result that fits the budget, or the smallest cut where none does."""
    df = result.df
    stamps = df.get_column("timestamp").drop_nulls().unique().sort().to_list()
    window = request.timestamp
    start = True if window or not stamps else _start_is_nearer_now(stamps[0], stamps[-1])
    total = df.height
    count_all = len(stamps)

    def attempt(frame: pl.DataFrame, count: int, within: int | None = None) -> _Attempt:
        note = _values_note(
            request=request,
            kept=frame.height,
            total=total,
            stamps=stamps,
            count=count,
            start=start,
            window=window,
            within=within,
            lead=lead,
            honest=honest,
        )
        return _made(result, request, frame, note, render)

    tried: dict[int, _Attempt] = {}

    def fits(count: int) -> bool:
        boundary = stamps[count - 1] if start else stamps[count_all - count]
        cut = df.filter(pl.col("timestamp") <= boundary if start else pl.col("timestamp") >= boundary)
        tried[count] = attempt(cut, count)
        return tried[count].size <= ANSWER_BUDGET

    best = _largest(1, count_all - 1, fits, max(1, count_all * ANSWER_BUDGET // size)) if count_all > 1 else None
    if best is not None:
        return tried[best]
    # one timestamp is more than the budget: cut through it, keeping what fits of its rows
    rows = df.filter(pl.col("timestamp") == (stamps[0] if start else stamps[-1]))
    partial: dict[int, _Attempt] = {}

    def fits_rows(count: int) -> bool:
        partial[count] = attempt(rows.head(count), 1, within=rows.height)
        return partial[count].size <= ANSWER_BUDGET

    kept = _largest(1, max(1, rows.height - 1), fits_rows, max(1, rows.height * ANSWER_BUDGET // size))
    return partial[kept if kept is not None else 1]


def _rows_note(*, result: _SeriesResult, kept: int, total: int, lead: str, honest: bool) -> str:
    """Write the note of an answer of chosen rows (`filter`, `sort`, `first`) cut to its first `kept` of `total` rows.

    The rows are cut in the order of the answer, so what is kept is what `sort` puts first, and the note says how many
    rows matched in all and how many values were searched, so that the cut is not mistaken for the whole.
    """
    search = getattr(result, "search", None)
    options = search.selection.echo() if search is not None else {}
    order = f", in the order of the answer (sort={options['sort']})" if options.get("sort") else ", in their order"
    head = f"{lead} {_head(honest=honest)}" if lead else _head(honest=honest)
    searched = (
        f" {int(search.series.get_column('searched').sum()):,} values were searched."
        if search is not None and search.series.height
        else ""
    )
    matched = search.matched_total if search is not None else total
    if kept == 1 and total == 1:
        returned = "the only row is"
    elif matched > total:
        # `max_rows` cut the answer already (`rows-capped`): `total` is what it returned, `matched` what matched
        returned = (
            f"the first {kept:,} of the {total:,} rows returned ({matched:,} matched; `max_rows` is "
            f"{options['max_rows']}) are"
        )
    else:
        returned = f"the first {kept:,} of {total:,} matched rows are"
    # what would make fewer rows, without advice that cannot work (a `first` of 1 or a `max_rows` of 1 keeps no less)
    ways = []
    if options.get("first") is not None and int(options["first"]) > 1:
        ways.append("a smaller `first`")
    if options.get("max_rows") is None or int(options["max_rows"]) > 1:
        ways.append("a `max_rows`" if options.get("max_rows") is None else "a smaller `max_rows`")
    ways += ["a narrower `filter`" if options.get("filter") else "a `filter`", "fewer parameters and stations"]
    advice = ", ".join(ways[:-1]) + f", or {ways[-1]}"
    return f"{head}{returned} returned{order}; the rest are left out.{searched} For fewer rows ask for {advice}."


def _fit_rows(
    result: _SeriesResult,
    request: _SeriesRequest,
    render: Callable[[Any, ResponseMetadata, Any], str | bytes],
    size: int,
    *,
    lead: str,
    honest: bool,
) -> _Attempt:
    """Find the most rows, from the first, of an answer of chosen rows that fit the budget, or the first one."""
    df = result.df
    total = df.height

    def attempt(count: int) -> _Attempt:
        note = _rows_note(result=result, kept=count, total=total, lead=lead, honest=honest)
        return _made(result, request, df.head(count), note, render)

    tried: dict[int, _Attempt] = {}

    def fits(count: int) -> bool:
        tried[count] = attempt(count)
        return tried[count].size <= ANSWER_BUDGET

    best = _largest(1, total - 1, fits, max(1, total * ANSWER_BUDGET // size)) if total > 1 else None
    if best is not None:
        return tried[best]
    # not even one row fits: the first is kept, which the report of what was searched may be most of
    return tried.get(1) or attempt(1)


def fit_values(
    result: _SeriesResult,
    request: _SeriesRequest,
    content: str | bytes,
    metadata: ResponseMetadata,
    render: Callable[[Any, ResponseMetadata, Any], str | bytes],
) -> tuple[str | bytes, ResponseMetadata]:
    """Cut the answer of a `values`, `interpolate` or `summarize` tool call to the budget at a timestamp; say so.

    The answer is unchanged where it fits. The `timestamp` of an estimate is required, so the start of its window is
    the part that is kept and the note's next window continues it.

    Without a `timestamp` from the caller the end nearest to now is kept: the start of a forecast, the latest part of
    a record. With one, its start is kept, so that the next window of the note continues it. At least one whole
    timestamp is kept, and a timestamp is cut through only where one alone is more than the budget.

    Where even the smallest cut (one timestamp) is over the budget with the `with_metadata` block and fits without it
    (the units and the quality legend of a dataset can be 40,000 characters), the block is left out, and the note says
    so. Where it is over without the block too, the note says it is still over. `render` writes the
    answer for a cut result, its block and the request; `content` and `metadata` are the whole answer.
    """
    if request.format not in BUDGETED_FORMATS or result.df.is_empty() or "timestamp" not in result.df.columns:
        return content, metadata
    size = answer_size(content, request, metadata)
    if size <= ANSWER_BUDGET:
        return content, metadata
    asked = request
    # an answer of rows chosen by the request is cut in its own order, the first rows kept, and says how many matched;
    # any other is a series of timestamps and is cut at one
    fit = _fit_rows if getattr(result, "search", None) is not None else _fit_values
    chosen = fit(result, asked, render, size, lead="", honest=False)
    search = getattr(result, "search", None)
    if chosen.size > ANSWER_BUDGET and search is not None and search.listed > 0:
        # the series of the report go before the rows do: the totals stay, and `series_omitted` counts them
        lean_result = replace(result, search=replace(search, listed=0))
        chosen_lean = fit(lean_result, asked, render, size, lead="", honest=False)
        if chosen_lean.size < chosen.size:
            result, chosen = lean_result, chosen_lean
    if chosen.size > ANSWER_BUDGET and (
        dropped := _without_block(
            result,
            request,
            render,
            lambda lean, whole, lead: fit(result, lean, render, whole, lead=lead, honest=False),
        )
    ):
        chosen, asked = dropped
    if chosen.size > ANSWER_BUDGET:
        chosen = fit(result, asked, render, chosen.size, lead="", honest=True)
    record_response_warning(ANSWER_TRUNCATED, chosen.note)
    log.info(
        f"Cut a {request.route} answer of {result.df.height} rows to {chosen.metadata.counts.rows} to stay within the "
        "budget."
    )
    return chosen.content, chosen.metadata


def _stations_note(
    *,
    count: int,
    total: int,
    lead: str,
    honest: bool,
    distance: float | None = None,
    rank: int | None = None,
    farthest: float | None = None,
) -> str:
    """Write the note of a stations answer cut to its first `count` of `total` stations.

    The stations of a `distance` are in the order of their distance, so the ones kept are the nearest: `distance` is
    the one asked for, `farthest` the distance in km of the last station returned, which says what a smaller
    `distance` would still keep. So are the stations of a `rank` (GH-4036), whose note gives the number asked for
    instead of a distance.
    """
    head = f"{lead} {_head(honest=honest)}" if lead else _head(honest=honest)
    if distance is not None or rank is not None:
        returned = (
            "the nearest station is returned, nearest first"
            if count == 1
            else f"the nearest {count:,} of {total:,} stations are returned, nearest first"
        )
        reach = f" (the farthest returned is {farthest:,.1f} km away)" if farthest is not None else ""
        if rank is not None:
            return (
                f"{head}{returned}{reach}. {rank:,} stations were asked for with `rank`; ask again with a smaller "
                "`rank`."
            )
        return (
            f"{head}{returned}{reach}. {total:,} stations lie within {distance:,.10g} km of the point; ask again "
            "with a smaller `distance`, or with `rank` for the nearest few."
        )
    returned = "the first station is" if count == 1 else f"the first {count:,} of {total:,} stations are"
    first = f"{head}{returned} returned, in the provider's list order (usually by "
    return (
        f"{first}station id, not by place, so they are not a sample of the area). {total:,} stations match; narrow "
        "with latitude, longitude and `rank` or `distance`, or `name`."
    )


def _fit_stations(
    result: StationsResult,
    request: _ListRequest,
    render: Callable[[Any, ResponseMetadata, Any], str | bytes],
    size: int,
    *,
    lead: str,
    honest: bool,
) -> _Attempt:
    """Find the most stations of a listing that fit the budget, or the first one where none does."""
    df = result.df
    ids = df.get_column("station_id").unique(maintain_order=True)
    count_all = len(ids)
    # the nearest stations are the first of a search by distance or by rank, whose rows are in the order of their
    # distance
    distance = (
        getattr(request, "distance", None)
        if result._stations_filter is StationsFilter.BY_DISTANCE  # noqa: SLF001
        else None
    )
    rank = result._rank if result._stations_filter is StationsFilter.BY_RANK else None  # noqa: SLF001
    nearest = distance is not None or rank is not None
    tried: dict[int, _Attempt] = {}

    def fits(count: int) -> bool:
        cut = df.filter(pl.col("station_id").is_in(ids.head(count).implode()))
        far = cut.get_column("distance").max() if nearest and "distance" in cut.columns else None
        farthest = float(far) if isinstance(far, int | float) else None
        note = _stations_note(
            count=count,
            total=count_all,
            lead=lead,
            honest=honest,
            distance=distance,
            rank=rank,
            farthest=farthest,
        )
        tried[count] = _made(result, request, cut, note, render)
        return tried[count].size <= ANSWER_BUDGET

    best = _largest(1, count_all - 1, fits, max(1, count_all * ANSWER_BUDGET // size))
    # where not even one station fits, the first is kept: the probes ended at it
    return tried[best if best is not None else 1]


def _leave_block_out(
    result: StationsResult,
    request: _ListRequest,
    render: Callable[[Any, ResponseMetadata, Any], str | bytes],
) -> tuple[str | bytes, ResponseMetadata] | None:
    """Give a few stations' answer again without its `with_metadata` block, where only that makes it fit the budget.

    A name asks for a few stations, so the rows are never cut; the block (the units and the quality legend of every
    dataset asked for) can be tens of thousands of characters on its own. None where there is
    no block to leave out, or where the answer is over the budget without it as well.
    """
    dropped = _without_block(result, request, render, None)
    if dropped is None:
        return None
    chosen, _ = dropped
    record_response_warning(ANSWER_TRUNCATED, chosen.note)
    log.info(
        f"Left the with_metadata block out of a stations answer of {result.df.height} rows to stay within the budget."
    )
    return chosen.content, chosen.metadata


def fit_stations(
    result: StationsResult,
    request: _ListRequest,
    content: str | bytes,
    metadata: ResponseMetadata,
    render: Callable[[StationsResult, ResponseMetadata, Any], str | bytes],
) -> tuple[str | bytes, ResponseMetadata]:
    """Cut the answer of a `stations` tool call to the budget, keeping the first stations.

    The answer is unchanged where it fits. A name asks for a few stations, and so does one station: their rows are
    left as they are (only a `with_metadata` block that is over the budget on its own is left out, with a note).
    Otherwise (all stations, a bounding box, a distance, a rank, ids) the stations that fit
    are kept, in list order (for a distance or a rank the nearest first, which is its order), and the note says how
    many match (or were asked for) and what narrows them. The block is kept and the stations are cut to make room for
    it: only where even one station is over the budget with the block, and fits without it, is the block left out,
    and the note says so. So a larger `rank` never returns fewer stations (GH-4036).
    `render` writes the answer for a cut result, its block and the request; `content` and `metadata` are the whole
    answer.
    """
    if request.format not in BUDGETED_FORMATS:
        return content, metadata
    size = answer_size(content, request, metadata)
    if size <= ANSWER_BUDGET:
        return content, metadata
    if result._stations_filter in _SMALL_SELECTIONS or result.df.get_column("station_id").n_unique() < 2:  # noqa: SLF001
        return _leave_block_out(result, request, render) or (content, metadata)
    # the stations the selection found stay in the answer's counts when the stations are cut (GH-4472)
    result = replace(result, _matched=metadata.counts.stations_matched)
    asked = request
    chosen = _fit_stations(result, asked, render, size, lead="", honest=False)
    if chosen.size > ANSWER_BUDGET and (
        dropped := _without_block(
            result,
            request,
            render,
            lambda lean, whole, lead: _fit_stations(result, lean, render, whole, lead=lead, honest=False),
        )
    ):
        chosen, asked = dropped
    if chosen.size > ANSWER_BUDGET:
        chosen = _fit_stations(result, asked, render, chosen.size, lead="", honest=True)
    record_response_warning(ANSWER_TRUNCATED, chosen.note)
    log.info(
        f"Cut a stations answer of {result.df.height} rows to {chosen.metadata.counts.stations} stations "
        "to stay within the budget."
    )
    return chosen.content, chosen.metadata


# --- station ids --------------------------------------------------------------------------------------------------


def _station_ids_size(content: str | bytes, fmt: str, metadata: StationIdsMetadata) -> int:
    """Count the characters a client receives of a `station_ids` answer in `fmt`, the sentence of a CSV included."""
    text = _text(content)
    if fmt in _MEDIA_TYPES:
        headers = {name.lower(): value for name, value in station_ids_headers(metadata).items()}
        return structured_size(_MEDIA_TYPES[fmt], text, headers)
    return len(json.dumps(json.loads(text), separators=(",", ":"), ensure_ascii=False)) + _RESULT_WRAPPER


def fit_station_ids(
    result: StationIdSearchResult,
    fmt: str,
    content: str | bytes,
    metadata: StationIdsMetadata,
    render: Callable[[StationIdSearchResult], tuple[str | bytes, StationIdsMetadata]],
) -> tuple[str | bytes, StationIdsMetadata]:
    """Cut the answer of a `station_ids` tool call to the budget, keeping the first stations, with a note.

    The answer is unchanged where it fits. Otherwise the rows that fit are kept, in the order of the answer (provider,
    network, station id), and the `answer-truncated` warning of its block says how many there are and to ask again with
    fewer ids. The block is the part that does not shrink (a few thousand characters: each network asked, each
    provider's licence); where not even one row fits with it the first is kept and the note says that the answer is
    still over the budget. `render` writes the answer for a cut result.
    """
    size = _station_ids_size(content, fmt, metadata)
    if size <= ANSWER_BUDGET:
        return content, metadata
    total = result.df.height
    tried: dict[int, tuple[str | bytes, StationIdsMetadata, int]] = {}

    def attempt(count: int, *, honest: bool) -> bool:
        note = (
            f"{_head(honest=honest)}the first {count:,} of {total:,} stations are returned, in the order of the answer "
            "(provider, network, station id). Ask again with fewer ids."
            if count > 1
            else f"{_head(honest=honest)}the first of {total:,} stations is returned. Ask again with fewer ids."
        )
        cut = replace(
            result,
            df=result.df.head(count),
            matched=total,
            warnings=[*result.warnings, {"code": ANSWER_TRUNCATED, "message": note}],
        )
        body, block = render(cut)
        tried[count] = (body, block, _station_ids_size(body, fmt, block))
        return tried[count][2] <= ANSWER_BUDGET

    best = _largest(1, total - 1, lambda count: attempt(count, honest=False), max(1, total * ANSWER_BUDGET // size))
    if best is None:
        # not even one row fits beside the block: the first is kept, and the note says the answer is still over
        attempt(1, honest=True)
        best = 1
    body, block, _ = tried[best]
    log.info(f"Cut a station_ids answer of {total} rows to {best} to stay within the budget.")
    return body, block


# --- statistics ---------------------------------------------------------------------------------------------------


def _cut_statistics(result: StatisticsResult, groups: int) -> tuple[StatisticsResult, int, int]:
    """Keep the first `groups` groups of the answer (by rank under `per=none`), and the series that hold them.

    A series left with no group is left out (the totals still count it). Gives the cut result, the groups it holds and
    the series it lists.
    """
    cut = result.head(groups, drop_empty=True)
    return cut, sum(s.frame.height for s in cut.series), len(cut.series)


def _first_series(result: StatisticsResult, count: int) -> list[SeriesStatistics]:
    """Give the `count` series an answer lists first, in the order the answer has them: those with a group.

    Under `per=none` the series with the best groups, by rank over all parameters (the order `head` cuts groups in), so
    that the series of one parameter are not all taken before another parameter's best; otherwise the first.
    """
    held = [series for series in result.series if series.frame.height]
    if result.plan.per_station:
        return held[:count]
    order = {key: n for n, key in enumerate(dict.fromkeys((s.resolution, s.dataset, s.parameter) for s in held))}
    ranked = sorted(
        enumerate(held),
        key=lambda item: (
            item[1].frame.get_column("rank").min(),
            order[(item[1].resolution, item[1].dataset, item[1].parameter)],
            item[0],
        ),
    )
    chosen = {n for n, _ in ranked[:count]}
    return [series for n, series in enumerate(held) if n in chosen]


def _statistics_note(
    plan: StatisticsPlan,
    *,
    shown: int,
    total: int,
    in_base: int,
    series: int,
    listed: int,
    many: bool,
    where: str,
    head: str,
) -> str:
    """Say what a tool's answer left out: groups cut to the budget, series capped, or series with no group."""
    if shown < in_base:
        return (
            f"{head}the first {shown:,} of {total:,} groups{where} are returned, in the answer's "
            "order; `metadata.search.totals` and `over_groups` cover all of them. "
            "Narrow with `having`, `first` or `filter`."
        )
    if many and plan.per_station:
        return (
            f"The answer lists the first {series:,} of {listed:,} series that have a group, in the order the "
            "stations were read; `per=none` ranks across the stations. `metadata.search.totals` covers all of "
            "them. Name fewer stations or parameters for the others."
        )
    if many:
        return (
            f"The answer lists {series:,} of {listed:,} series that have a group, the series with the best "
            "groups; `metadata.search.totals` covers all of them. Name fewer stations or parameters for the others."
        )
    if plan.having:
        return (
            "No group of the series left out met `having`; they are not listed, and `metadata.search.totals` "
            "counts them."
        )
    return (
        "The series with no group are left out of the answer; `metadata.search.totals` counts them. "
        "Name fewer stations or parameters to see the others."
    )


def _restated_warnings(
    plan: StatisticsPlan, cut: StatisticsResult, warnings: Sequence[ResponseWarning]
) -> list[ResponseWarning]:
    """Give the warnings of an answer for a cut of it: those that count its groups say how many are still in it."""
    from wetterdienst.model.group_statistics import (  # noqa: PLC0415
        GAPS_ALLOWED,
        INCOMPLETE_GROUPS,
        gaps_allowed_message,
        gaps_allowed_of,
        restate_incomplete,
    )

    shown_incomplete = sum(int(s.frame.get_column("_incomplete").sum()) for s in cut.series)
    allowed = gaps_allowed_of(cut.series)
    restated: list[ResponseWarning] = []
    for w in warnings:
        if w["code"] == INCOMPLETE_GROUPS:
            w = ResponseWarning(**{**w, "message": restate_incomplete(w["message"], shown_incomplete)})
        elif w["code"] == GAPS_ALLOWED:
            # the groups that are left in the answer, which may be none of them
            if not allowed[0]:
                continue
            message = gaps_allowed_message(*allowed, plan)
            w = ResponseWarning(**{**w, "message": message})
        restated.append(w)
    return restated


def fit_statistics(
    result: StatisticsResult,
    fmt: str,
    content: str | bytes,
    metadata: StatisticsMetadata,
    render: Callable[[StatisticsResult, StatisticsMetadata], tuple[str | bytes, StatisticsMetadata]],
) -> tuple[str | bytes, StatisticsMetadata]:
    """Cut the answer of a `statistics` tool call to the budget, keeping the first groups in the order of the answer.

    An answer lists at most `MAX_TOOL_SERIES` series that have a group, each with a header of its own (under `per=none`
    those with the best groups over all parameters); one of more says so, and is not a cut to the budget. Where it fits
    it is otherwise unchanged. Otherwise the first groups that fit are kept, in the order the answer has them (the order
    of `sort`, or the columns of `by`, series by series; by rank under `per=none`), and the `answer-truncated` warning
    of its block says how many of how many are shown. What the block and each series' `over_groups` say covers all the
    groups: the totals of `metadata.search` (with `groups_returned`, the groups shown) and the statistics over the
    groups are not cut, only the rows. Where not even one group fits beside them the first is kept and the note says
    that the answer is still over the budget. `render` writes the answer for a cut result and the block it is given.
    """
    size = _size_in(content, fmt, metadata)
    held = [series for series in result.series if series.frame.height]
    many = len(held) > MAX_TOOL_SERIES
    if size <= ANSWER_BUDGET and not many:
        return content, metadata
    if many:
        chosen = _first_series(result, MAX_TOOL_SERIES)
        base = replace(
            result,
            series=chosen,
            left_out=[*result.left_out, *(s for s in result.series if not any(s is c for c in chosen))],
        )
    else:
        base = result
    total = sum(series.frame.height for series in result.series)
    in_base = sum(series.frame.height for series in base.series)
    tried: dict[int, tuple[str | bytes, StatisticsMetadata, int]] = {}

    def attempt(count: int, *, honest: bool) -> bool:
        cut, shown, series = _cut_statistics(base, count)
        where = f" of the first {series:,} of {len(held):,} series" if series < len(held) else ""
        note = _statistics_note(
            result.plan,
            shown=shown,
            total=total,
            in_base=in_base,
            series=series,
            listed=len(held),
            many=many,
            where=where,
            head=_head(honest=honest),
        )
        warnings = _restated_warnings(result.plan, cut, metadata.warnings)
        search = metadata.search
        if search is not None:
            search = search.model_copy(update={"totals": search.totals.model_copy(update={"groups_returned": shown})})
        block = metadata.model_copy(
            update={
                "counts": Counts(stations=len({s.station_id for s in cut.series}), rows=shown),
                "search": search,
                "warnings": [*warnings, ResponseWarning(code=ANSWER_TRUNCATED, message=note)],
            }
        )
        body, block = render(cut, block)
        tried[count] = (body, block, _size_in(body, fmt, block))
        return tried[count][2] <= ANSWER_BUDGET

    # the groups of the series listed, all of them, where they fit: only the series were cut
    if attempt(in_base, honest=False):
        body, block, _ = tried[in_base]
        return body, block
    best = _largest(1, in_base - 1, lambda count: attempt(count, honest=False), max(1, in_base * ANSWER_BUDGET // size))
    if best is None:
        attempt(1, honest=True)
        best = 1
    body, block, _ = tried[best]
    log.info(f"Cut a statistics answer of {total} groups to {best} to stay within the budget.")
    return body, block


# --- coverage -----------------------------------------------------------------------------------------------------


def coverage_size(coverage: Mapping[str, Any]) -> int:
    """Count the characters a client receives of a `coverage` answer: its compact JSON, the structured content."""
    return len(json.dumps(coverage, separators=(",", ":"), ensure_ascii=False))


def _without_descriptions(coverage: Mapping[str, Any]) -> dict[str, Any]:
    """Give the coverage with the `description` of every parameter null: the shape stays, the long text goes."""
    return {
        resolution: {
            **body,
            "datasets": {
                name: {
                    **dataset,
                    "parameters": [{**parameter, "description": None} for parameter in dataset["parameters"]],
                }
                for name, dataset in body["datasets"].items()
            },
        }
        for resolution, body in coverage.items()
    }


def _datasets_of(coverage: Mapping[str, Any]) -> list[tuple[str, str]]:
    """List the `(resolution, dataset)` of a coverage in the order the network has them."""
    return [(resolution, name) for resolution, body in coverage.items() for name in body["datasets"]]


def _first_datasets(coverage: Mapping[str, Any], keep: list[tuple[str, str]]) -> dict[str, Any]:
    """Give the coverage with the datasets of `keep` only; a resolution left with none stays, with no datasets."""
    wanted = set(keep)
    return {
        resolution: {**body, "datasets": {n: d for n, d in body["datasets"].items() if (resolution, n) in wanted}}
        for resolution, body in coverage.items()
    }


def _noted_coverage(coverage: Mapping[str, Any], note: str) -> dict[str, Any]:
    """Put the note in the `description` of the first resolution, the one place the shape of the answer has for text.

    The answer is keyed by resolution, has no `metadata` block, and its schema forbids a key beside the resolutions,
    so the note cannot go where it goes in the other tools' answers. The note is in what is counted.
    """
    first = next(iter(coverage))
    original = coverage[first]["description"]
    return {**coverage, first: {**coverage[first], "description": f"{note}\n\n{original}" if original else note}}


def _too_big_alone(coverage: Mapping[str, Any]) -> list[tuple[str, str]]:
    """List the datasets whose answer for `datasets=<name>` and `resolutions=<resolution>` is over the budget.

    That is the answer a caller gets by following the advice of the note, so where it is over the budget no advice to
    ask for the dataset can give its descriptions: they do not fit in one answer.
    """
    return [
        (resolution, name)
        for resolution, body in coverage.items()
        for name, dataset in body["datasets"].items()
        if coverage_size({resolution: {**body, "datasets": {name: dataset}}}) > ANSWER_BUDGET
    ]


def _ask_for_a_dataset(big: list[tuple[str, str]], *, the_rest: bool) -> str:
    """Write how to get the full detail of one dataset, and which datasets it cannot be had of."""
    text = "Ask for one dataset with `datasets=<name>` and `resolutions=<resolution>` for its full detail" + (
        " (or with `resolutions=` alone for a resolution)" if the_rest else ""
    )
    if not big:
        return f"{text}."
    names = ", ".join(f"{resolution}/{dataset}" for resolution, dataset in big)
    which = "its" if len(big) == 1 else "their"
    each = "" if len(big) == 1 else " each"
    return (
        f"{text}, but not of {names}: the descriptions of {which} parameters are{each} more than that on their own. "
        "`glossary` says what a parameter means."
    )


def _coverage_note(
    *,
    left: list[tuple[str, str]],
    total: int,
    big: list[tuple[str, str]],
    parameters: int = 0,
    within: tuple[str, int, int] | None = None,
    honest: bool = False,
) -> str:
    """Write the note of a `coverage` answer whose parameter descriptions are left out, and whose datasets may be cut.

    `left` are the datasets left out, `total` those of the network (of the filter asked) and `big` those that alone,
    with their descriptions, are over the budget, which asking for the dataset cannot give either. `parameters` is the
    number of those of the one dataset that the answer is, `within` the dataset that alone was more than the budget
    without them, with the parameters returned of it and the number it has.
    """
    text = f"{_head(honest=honest)}the `description` of each parameter is left out (null)"
    if within is not None:
        name, kept, count = within
        returned = "only its first parameter is" if kept == 1 else f"only its first {kept:,} parameters are"
        text += (
            f"; the dataset `{name}` alone is more than that, and {returned} returned, of {count:,}: the others are "
            "not available through this tool"
        )
    if left:
        names = ", ".join(f"{resolution}/{dataset}" for resolution, dataset in left)
        kept_count = total - len(left)
        text += (
            f"; {kept_count:,} of {total:,} datasets {'is' if kept_count == 1 else 'are'} returned, whole and in the "
            f"order of the network. The {len(left):,} left out {'is' if len(left) == 1 else 'are'}: {names}. "
        )
        return text + _ask_for_a_dataset(big, the_rest=True)
    if within is not None:
        return f"{text}. `glossary` says what a parameter means."
    if total == 1:
        # asking for the one dataset again would answer the same
        return (
            f"{text}: the descriptions of its {parameters:,} parameters together are more than that. `glossary` says "
            "what a parameter means."
        )
    return f"{text}. {_ask_for_a_dataset(big, the_rest=False)}"


def fit_coverage(coverage: Mapping[str, Any]) -> tuple[Mapping[str, Any], str | None]:
    """Cut a `coverage` tool answer to the budget in steps, each only where the one before is still over it (GH-4024).

    1. The answer as it is, where it fits. 2. The `description` of each parameter null (the long text of a
    parameter is most of a big network), and the note says to ask `datasets=<name>` for the detail of one dataset,
    unless that answer is over the budget too (the answer is that one dataset already, or it alone is over it): the
    note then says so and points to `glossary`. 3. Whole datasets in the order of the network, as many as fit, and the
    note names those left out and how to ask for them. 4. Where the first dataset alone is more than the budget, the
    first of its parameters that fit, and the note says how many and that the others are not available. The shape is
    that of the REST answer: the keys are the same, a `description` is null, a resolution may have no datasets.
    Returns the answer and its note, None where nothing was cut; the note is in the first resolution's `description`
    and counts toward the size.
    """
    size = coverage_size(coverage)
    if size <= ANSWER_BUDGET or not coverage:
        return coverage, None
    lean = _without_descriptions(coverage)
    datasets = _datasets_of(lean)
    total = len(datasets)
    big = _too_big_alone(coverage)
    only = len(lean[datasets[0][0]]["datasets"][datasets[0][1]]["parameters"]) if total == 1 else 0
    note = _coverage_note(left=[], total=total, big=big, parameters=only)
    if coverage_size(noted := _noted_coverage(lean, note)) <= ANSWER_BUDGET:
        return noted, note
    cut: dict[int, tuple[dict[str, Any], str]] = {}

    def fits(count: int) -> bool:
        text = _coverage_note(left=datasets[count:], total=total, big=big)
        cut[count] = (_noted_coverage(_first_datasets(lean, datasets[:count]), text), text)
        return coverage_size(cut[count][0]) <= ANSWER_BUDGET

    best = _largest(1, total - 1, fits, max(1, total * ANSWER_BUDGET // size)) if total > 1 else None
    if best is not None:
        return cut[best]
    # the first dataset alone is more than the budget: keep the first of its parameters that fit
    resolution, name = datasets[0]
    parameters = lean[resolution]["datasets"][name]["parameters"]
    partial: dict[int, tuple[dict[str, Any], str]] = {}

    def fits_parameters(count: int, *, honest: bool = False) -> bool:
        text = _coverage_note(
            left=datasets[1:],
            total=total,
            big=big,
            within=(f"{resolution}/{name}", count, len(parameters)),
            honest=honest,
        )
        first = _first_datasets(lean, datasets[:1])
        first[resolution]["datasets"][name] = {**first[resolution]["datasets"][name], "parameters": parameters[:count]}
        partial[count] = (_noted_coverage(first, text), text)
        return coverage_size(partial[count][0]) <= ANSWER_BUDGET

    kept = _largest(1, max(1, len(parameters) - 1), fits_parameters, max(1, len(parameters) * ANSWER_BUDGET // size))
    if kept is None:
        kept = 1
        fits_parameters(kept, honest=True)
    return partial[kept]


# --- alerts -------------------------------------------------------------------------------------------------------

#: how bad a warning is, as CAP words it (`severity`), the worst first; a value that is none of them goes last
_SEVERITIES = ("extreme", "severe", "moderate", "minor")
#: how soon a warning acts (`urgency`), the soonest first
_URGENCIES = ("immediate", "expected", "future", "past")
#: how many of the warnings left out a note names
_NAMED_LEFT_OUT = 8
#: the most areas that match a `name` that are kept for a warning where all of them are too many. A kept area is an
#: area name and its warn cell id, about 40 characters, so 25 are about 1,000 characters: the 1.1 to 1.6 KB of a slimmed
#: warning plus that is 2.5 KB, so 15 warnings of a storm day still fit the budget, where a name that matches 1,500
#: areas of each is 60 KB
AREA_CAP = 25


def _worst_first(df: pl.DataFrame) -> pl.DataFrame:
    """Sort the warnings: the most severe first, then the most urgent, then the earliest onset; ties keep their order.

    Those for the place asked for need no sorting first, since a request for a place holds only them.
    """

    def rank(column: str, order: tuple[str, ...]) -> pl.Expr:
        return (
            pl.col(column)
            .str.to_lowercase()
            .replace_strict({word: index for index, word in enumerate(order)}, default=len(order), return_dtype=pl.Int8)
        )

    return df.sort(
        [rank("severity", _SEVERITIES), rank("urgency", _URGENCIES), pl.col("onset")],
        nulls_last=True,
        maintain_order=True,
    )


def _matching_areas(df: pl.DataFrame, name: str | None) -> tuple[list[list[str]], list[list[str]]]:
    """Give, for each warning, the area names and the warn cell ids that match the `name`; empty lists without one.

    A name that is no id matches the words of an area's name, one of digits the warn cell id.
    """
    from wetterdienst.provider.dwd.alerts.place import names_match  # noqa: PLC0415

    def keep(column: str, *, by_name: bool) -> list[list[str]]:
        return [
            [
                item
                for item in items or []
                if name is not None and (names_match([item], [], name) if by_name else names_match([], [item], name))
            ]
            for items in df.get_column(column).to_list()
        ]

    return keep("area_names", by_name=True), keep("warncell_ids", by_name=False)


def _slimmed(df: pl.DataFrame, areas: tuple[list[list[str]], list[list[str]]], cap: int | None) -> pl.DataFrame:
    """Give the warnings without their polygon and areas: `geometry` null, the lists those of `areas` or empty.

    A warning is mostly those three columns (a warning for a coast lists 1,700 areas). `areas` are those that match the
    name, of which `cap` are kept for each warning where it is given.
    """
    names, cells = ([match[:cap] for match in matches] for matches in areas)
    return df.with_columns(
        pl.lit(None, dtype=pl.String).alias("geometry"),
        pl.Series("area_names", names, dtype=pl.List(pl.String)),
        pl.Series("warncell_ids", cells, dtype=pl.List(pl.String)),
    )


def _cut_result(result: DwdWeatherAlertResult, df: pl.DataFrame) -> DwdWeatherAlertResult:
    """Give the result of the same snapshot with the warnings of `df`: the date of its data is still that of all."""
    return type(result)(
        df=df,
        granularity=result.granularity,
        language=result.language,
        snapshot=result.snapshot,
        snapshot_updated_at=result.data_updated_at,
        name_matched=result.name_matched,
    )


def _left_out_warnings(df: pl.DataFrame) -> str:
    """Name the warnings left out, `event (severity)`, as many as the note names, and how many more there are."""
    named = [f"{row['event']} ({row['severity']})" for row in df.head(_NAMED_LEFT_OUT).iter_rows(named=True)]
    more = df.height - len(named)
    return ", ".join(named) + (f" and {more:,} more" if more else "")


def _capped_warnings(df: pl.DataFrame, areas: tuple[list[list[str]], list[list[str]]], cap: int) -> str:
    """Name the warnings that have more matching areas than `cap`, `event (n match)`, as many as a note names."""
    counts = [
        (event, max(len(names), len(cells)))
        for event, names, cells in zip(df.get_column("event").to_list(), *areas, strict=True)
    ]
    over = [f"{event} ({count:,} match)" for event, count in counts if count > cap]
    shown = ", ".join(over[:_NAMED_LEFT_OUT])
    return shown + (f" and {len(over) - _NAMED_LEFT_OUT:,} more" if len(over) > _NAMED_LEFT_OUT else "")


def _alerts_note(
    *,
    shown: int,
    left_out: pl.DataFrame,
    name: str | None,
    point: bool,
    capped: str = "",
    cap: int | None = None,
    honest: bool = False,
) -> str:
    """Write the note of an `alerts` answer cut to the budget: what is left of a warning, which are, how to ask.

    `shown` is the number of warnings returned and `left_out` the rows of the others, `name` the name of the request
    and `point` whether it has a point. `cap` is the number of matching areas kept for each warning where they were
    capped, and `capped` the warnings that have more.
    """
    if cap is not None:
        areas = f"the first {cap:,} of the areas that match the name are kept for each warning, and {capped} have more"
    elif name is not None:
        areas = "the areas that match the name are kept"
    elif point:
        areas = "no area is listed"
    else:
        areas = (
            "no area is listed: these are the warnings in force somewhere in Germany, and the answer does not say where"
        )
    text = (
        f"{_head(honest=honest)}the polygon (`geometry`) and the lists of areas (`area_names`, `warncell_ids`) of each "
        f"warning are left out ({areas}); they are not available through this tool, the REST API, the command line and "
        "Python give them. "
    )
    placed = point or name is not None
    if left_out.is_empty():
        text += "The warning is returned." if shown == 1 else f"All {shown:,} warnings are returned."
        return (
            text if placed else f"{text} Pass a place (`latitude` and `longitude`, or `name`) for the warnings for it."
        )
    count = left_out.height
    words = "the first warning is" if shown == 1 else f"the first {shown:,} warnings are"
    text += (
        f"Of {shown + count:,} warnings {words} returned, the most severe first (then the most urgent, then the "
        f"earliest onset). The {count:,} left out {'is' if count == 1 else 'are'}: {_left_out_warnings(left_out)}. "
    )
    if name is not None:
        advice = "Ask for a smaller place: a more specific `name`, one area or its warn cell id."
    elif point:
        advice = "Ask for a smaller place: add a `name` of one area to the point (both must hold)."
    else:
        advice = "Pass a place, a point (`latitude` and `longitude`) or a `name`, for the warnings for it alone."
    return text + advice


def fit_alerts(
    result: DwdWeatherAlertResult,
    fmt: str,
    content: str | bytes,
    metadata: ResponseMetadata,
    render: Callable[[DwdWeatherAlertResult, ResponseMetadata], str],
    *,
    name: str | None = None,
    point: bool = False,
) -> tuple[str | bytes, ResponseMetadata]:
    """Cut an `alerts` tool answer to the budget in steps, each only where the one before is still over it (GH-4338).

    A warning is mostly its polygon and the areas it is issued for: one for a coast is 80,000 characters, and the
    answer for Kiel on 2026-11-23 was 184,612 for three warnings, so no warning can be kept with them and the answer
    fit. 1. The answer as it is, where it fits. 2. Every warning without its `geometry` and its lists of areas (for a
    `name`, the areas that match it are kept), everything else of it as it is: a few thousand characters each. 3. For a
    `name` that matches many areas (1,500 in a coast's warning), only the first `AREA_CAP` of them for each warning, the
    note naming the warnings that have more. 4. Where that is still over the budget, as many of those warnings as fit,
    whole, the most severe first (then the most urgent, then the earliest onset). A request for a place holds the
    warnings for it only, so none needs to go first for it. The `answer-truncated` warning of the block says what was
    left out of each warning, names the warnings left out and says how to ask for a narrower answer. Where not even one
    warning fits the worst is kept and the note says that the answer is still over the budget. `render` writes the
    answer of a cut result with the block it is given; `name` is the name of the request and `point` whether it has a
    point.
    """
    if _size_in(content, fmt, metadata) <= ANSWER_BUDGET or result.df.is_empty():
        return content, metadata
    ordered = _worst_first(result.df)
    areas = _matching_areas(ordered, name)
    total = ordered.height
    # the caps to try: none, then `AREA_CAP` where a warning has more matching areas than that
    caps: list[int | None] = [None]
    if any(len(match) > AREA_CAP for matches in areas for match in matches):
        caps.append(AREA_CAP)
    tried: dict[tuple[int | None, int], tuple[str, ResponseMetadata, int]] = {}

    def attempt(count: int, cap: int | None, *, honest: bool = False) -> bool:
        slim = _slimmed(ordered, areas, cap)
        note = _alerts_note(
            shown=count,
            left_out=slim.slice(count),
            name=name,
            point=point,
            capped=_capped_warnings(ordered, areas, cap) if cap is not None else "",
            cap=cap,
            honest=honest,
        )
        block = metadata.model_copy(
            update={
                "counts": metadata.counts.model_copy(update={"rows": count}),
                "warnings": [*metadata.warnings, ResponseWarning(code=ANSWER_TRUNCATED, message=note)],
            }
        )
        body = render(_cut_result(result, slim.head(count)), block)
        tried[cap, count] = (body, block, _size_in(body, fmt, block))
        return tried[cap, count][2] <= ANSWER_BUDGET

    # all the warnings first, with the caps in turn; the last cap is the one that drops warnings if it must
    cap = caps[-1]
    best = total if any(attempt(total, each) for each in caps) else None
    if best is not None:
        cap = next(each for each in caps if tried[each, total][2] <= ANSWER_BUDGET)
    elif total > 1:
        # from the size of the slimmed answer, which the warnings are cut from, and not of the unslimmed one, whose
        # polygons and areas would put the first probe near 1
        guess = max(1, total * ANSWER_BUDGET // tried[cap, total][2])
        best = _largest(1, total - 1, lambda count: attempt(count, cap), guess)
    if best is None:
        # not even the worst warning fits, slimmed as it is: it is kept, and the note says the answer is still over
        attempt(1, cap, honest=True)
        best = 1
    body, block, _ = tried[cap, best]
    log.info(f"Cut an alerts answer of {total} warnings to {best} to stay within the budget.")
    return body, block
