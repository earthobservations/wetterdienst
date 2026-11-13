# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The size budget of an MCP tool's answer of rows (GH-4022, GH-4024).

The answers it holds are those of `values`, `stations`, `interpolate`, `summarize`, the stripes' stations and
`coverage` (which is no rows but nested: `fit_coverage`).

An assistant reads a tool's answer in its context, and a client saves one of more than 50,000 characters to a file
instead of handing it over (Claude Code does, whatever its tokens). Two calls spilled in the transcripts: a forecast
with no window (90,000 characters and more) and a listing of every station in a bounding box (1.7 million). Neither
limit of the REST API fires for them. So a tool's answer of `values` or `stations` is cut to `ANSWER_BUDGET`
characters, and says it was, in a warning of its `metadata` block (`answer-truncated`) that names what is left out and
the `timestamp` window to ask for it. Nothing is refused: the answer keeps what fits.

The answers of `interpolate` and `summarize` are series of timestamps as those of `values` are, and are cut the same
way (`fit_values`; their `timestamp` is required, so the start of their window is the part kept). The stripes' stations
are a list of stations as those of `stations` are, with no way to select (`fit_stations`; the note tells how to
name a place instead). A `with_metadata` block that is more than the budget on its own is left out of an answer that
is cut or that would be without it, and of one of a name.

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
from wetterdienst.ui.core import StripesStationsRequest
from wetterdienst.ui.mcp import structured_size
from wetterdienst.ui.response_metadata import response_headers, response_metadata, result_metadata
from wetterdienst.util.response_warnings import ANSWER_TRUNCATED, ResponseWarning, record_response_warning

if TYPE_CHECKING:
    from collections.abc import Callable, Mapping

    from wetterdienst.model.result import InterpolatedValuesResult, SummarizedValuesResult, ValuesResult
    from wetterdienst.ui.core import InterpolationRequest, StationsRequest, SummaryRequest, ValuesRequest
    from wetterdienst.ui.response_metadata import ResponseMetadata

    _SeriesResult = ValuesResult | InterpolatedValuesResult | SummarizedValuesResult
    _SeriesRequest = ValuesRequest | InterpolationRequest | SummaryRequest
    _ListRequest = StationsRequest | StripesStationsRequest

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


def _block(result: StationsResult | _SeriesResult, request: _ListRequest | _SeriesRequest) -> ResponseMetadata:
    """Build the `metadata` block of the answer to `request`: the climate stripes' request names no provider, DWD's."""
    if isinstance(request, StripesStationsRequest):
        return result_metadata(result, provider="dwd", network="observation", heavy=False)
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
    fit: Callable[[Any, int, str], _Attempt],
) -> tuple[_Attempt, Any] | None:
    """Try an answer that is over the budget with its `with_metadata` block again without the block.

    The block (the units, the quality legend and the settings of every dataset asked for) can be tens of thousands of
    characters: with it not even the smallest cut, one timestamp or one station, may fit, although without it many do.
    The request is made without `with_metadata`, the answer is fitted again by `fit(request, size, lead)` (`lead` is
    the note of what was left out) and, where it fits the budget now, given back with that request. None where the
    request has no block, or where leaving it out does not help either, which `fit_*` then tells as it is.
    """
    if not getattr(request, "with_metadata", False):
        return None
    empty = result.df.head(0)
    lean = _lean(request)
    block = _made(result, request, empty, "", render).size - _made(result, lean, empty, "", render).size
    lead = _block_left_out(block)
    whole = _made(result, lean, result.df, lead, render)
    fitted = whole if whole.size <= ANSWER_BUDGET else fit(lean, whole.size, lead)
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
    chosen = _fit_values(result, asked, render, size, lead="", honest=False)
    if chosen.size > ANSWER_BUDGET and (
        dropped := _without_block(
            result,
            request,
            render,
            lambda lean, whole, lead: _fit_values(result, lean, render, whole, lead=lead, honest=False),
        )
    ):
        chosen, asked = dropped
    if chosen.size > ANSWER_BUDGET:
        chosen = _fit_values(result, asked, render, chosen.size, lead="", honest=True)
    record_response_warning(ANSWER_TRUNCATED, chosen.note)
    log.info(
        f"Cut a {request.route} answer of {result.df.height} rows to {chosen.metadata.counts.rows} to stay within the "
        "budget."
    )
    return chosen.content, chosen.metadata


def _stations_note(
    *,
    request: _ListRequest,
    count: int,
    total: int,
    lead: str,
    honest: bool,
    distance: float | None = None,
    rank: int | None = None,
    farthest: float | None = None,
) -> str:
    """Write the note of a stations answer cut to its first `count` of `total` stations.

    The list of the climate stripes' stations has no selection to narrow with: a place goes to the stripes' tools as
    a `name`, which they match themselves, and `stations` finds a station near a point. The stations of a `distance`
    are in the order of their distance, so the ones kept are the nearest: `distance` is the one asked for, `farthest`
    the distance in km of the last station returned, which says what a smaller `distance` would still keep. So are
    the stations of a `rank` (GH-4036), whose note gives the number asked for instead of a distance.
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
    if isinstance(request, StripesStationsRequest):
        only_active = "" if request.active else " `active=true` lists only the stations that still report."
        return (
            f"{first}station id, not by place). {total:,} stations have data for the {request.kind} stripes. To get "
            "one station, give the station's name (often its town's) as `name` to `stripes_values` or "
            "`stripes_image`, which match it themselves, or find a station with `stations` (`name`, or latitude, "
            f"longitude and `rank`).{only_active}"
        )
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
            request=request,
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

    A name asks for a few stations, so the rows are never cut; the block (the units and the
    quality legend of every dataset asked for) can be tens of thousands of characters on its own. None where there is
    no block to leave out, or where the answer is over the budget without it as well.
    """
    dropped = _without_block(
        result, request, render, lambda lean, _, lead: _made(result, lean, result.df, lead, render)
    )
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
    """Cut the answer of a `stations` or `stripes_stations` tool call to the budget, keeping the first stations.

    The answer is unchanged where it fits. A name asks for a few stations, and so does one station: their rows are
    left as they are (only a `with_metadata` block that is over the budget on its own is left out, with a note).
    Otherwise (all stations, a bounding box, a distance, a rank, `sql`, ids, the stripes' list) the stations that fit
    are kept, in list order (for a distance or a rank the nearest first, which is its order), and the note says how
    many match (or were asked for) and what narrows them. Where even one station is over
    the budget with the `with_metadata` block and fits without it, the block is left out, and the note says so.
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
    if result._stations_filter is StationsFilter.BY_RANK and (  # noqa: SLF001
        left_out := _leave_block_out(result, request, render)
    ):
        # a rank whose rows fit without the `with_metadata` block keeps them all: only the block goes (GH-4036)
        return left_out
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
