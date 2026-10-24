# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Send a large answer as it is built instead of holding it: NDJSON and CSV, station by station (GH-3065).

`stations` and `values` stream `format=ndjson` and `format=csv`; the JSON formats are one body, as before.

**NDJSON** (`application/x-ndjson`) is one JSON object a line, UTF-8:

1. `{"metadata": {...}}`, the `metadata` block (and, for `values` with `with_metadata`, `"settings"` beside it).
   What is not known before the first reading is the first line's best knowledge: `counts.stations` is the
   stations selected (at most `rank` of them), `counts.rows` is 0, and `warnings` are those so far.
2. One line for each row, an item of the `values` (or `stations`) of the JSON answer.
3. `{"end": {"counts": {...}, "warnings": [...]}}`, the counts of what was sent and every warning.
   A stream that ends without it was cut short. If a failure comes after the response began, whose status can no
   longer change, the last line is `{"error": <problem>}` instead.

`metadata`, `end` and `error` are the keys of the lines that are no rows; no row has one.

**CSV** is the CSV of the JSON-less answer, a header row and the rows, sent in chunks. The metadata is in the
headers (`X-Wetterdienst-*`, `Link`), which are sent before any row: `X-Wetterdienst-Rows` is left out, and the
warnings are those known before the first reading. A failure after the response began cuts the connection, as CSV
has no place to say it; the server logs it.

The first station is read before the response begins, so that a request that fails on it has the status of the
failure and not a 200. The timeout of the server holds between two chunks (`ui.middleware`).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, cast

import polars as pl
from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse

from wetterdienst.ui.render import ndjson_line
from wetterdienst.util.logging import get_one_line_logger

if TYPE_CHECKING:
    import contextvars
    from collections.abc import AsyncIterator, Callable, Iterator, Mapping

log = get_one_line_logger(__name__)

#: the formats of `stations` and `values` that are streamed
STREAM_FORMATS = frozenset({"ndjson", "csv"})
NDJSON_MEDIA_TYPE = "application/x-ndjson"
#: how many rows of a listing of stations are written at once
STATIONS_BATCH = 2_000

_DONE = object()


def ndjson_stream(
    head: Mapping[str, Any],
    frames: Iterator[pl.DataFrame],
    to_rows: Callable[[pl.DataFrame], list[dict[str, Any]]],
    finish: Callable[[int, int], Mapping[str, Any]],
    fail: Callable[[Exception], Mapping[str, Any]],
) -> Iterator[bytes]:
    """Write the lines of an NDJSON answer: the head, a line for each row of every frame, then `end` or `error`.

    `finish` is given the stations and rows sent so far and answers the `end` line's content; `fail` the problem
    of an exception, which becomes the last line.
    """
    yield ndjson_line(head)
    rows, stations = 0, set()
    try:
        for frame in frames:
            batch = to_rows(frame)
            rows += len(batch)
            if "station_id" in frame.columns:
                stations.update(frame.get_column("station_id").unique().to_list())
            if batch:
                yield b"".join(ndjson_line(row) for row in batch)
        end = finish(len(stations), rows)
    except Exception as e:  # noqa: BLE001
        yield ndjson_line({"error": fail(e)})
        return
    yield ndjson_line({"end": end})


def csv_stream(
    frames: Iterator[pl.DataFrame],
    to_csv: Callable[..., str],
    empty: Callable[[], pl.DataFrame],
    fail: Callable[[Exception], object],
) -> Iterator[bytes]:
    """Write the chunks of a CSV answer: the header with the first frame, then the rows of each.

    Every frame is written with the columns of the first, in its order: a station that lacks one has it empty,
    one that has another is written without it. `empty` gives the frame whose header is written when there are no
    rows. `fail` is told of an exception, which is raised again so that the connection is cut: the status can no
    longer change and CSV has no place to say it.
    """
    columns: list[str] | None = None
    try:
        for frame in frames:
            if columns is None:
                columns = frame.columns
                header = True
            else:
                header = False
                if frame.columns != columns:
                    frame = frame.select([pl.col(c) if c in frame.columns else pl.lit(None).alias(c) for c in columns])
            yield to_csv(frame, header=header).encode()
        if columns is None:
            yield to_csv(empty(), header=True).encode()
    except Exception as e:
        fail(e)
        raise


def frames_in_batches(frame: pl.DataFrame, size: int | None = None) -> Iterator[pl.DataFrame]:
    """Cut a frame into frames of `size` rows, for what is held already and only has to be written in pieces."""
    size = size or STATIONS_BATCH
    for offset in range(0, frame.height, size):
        yield frame.slice(offset, size)


async def _drive(
    chunks: Iterator[bytes],
    context: contextvars.Context,
    seconds: float | None,
    on_timeout: Callable[[], bytes | None],
) -> AsyncIterator[bytes]:
    """Hand the chunks to the server, each produced in a thread of the pool in the context of the request.

    The timeout holds for every chunk. When one takes longer, `on_timeout` gives the bytes that end the answer, or
    None where there is nothing to say; the thread that was producing the chunk is left to finish.
    """
    while True:
        step = run_in_threadpool(context.run, next, chunks, _DONE)
        try:
            chunk: bytes | object = await (asyncio.wait_for(step, seconds) if seconds else step)
        except TimeoutError:
            tail = on_timeout()
            if tail is not None:
                yield tail
                return
            raise
        if chunk is _DONE:
            return
        yield cast("bytes", chunk)


def stream_response(
    chunks: Iterator[bytes],
    media_type: str,
    headers: Mapping[str, str],
    *,
    context: contextvars.Context,
    timeout: float | None,
    on_timeout: Callable[[], bytes | None],
) -> StreamingResponse:
    """Answer with chunks as they are made. `context` is the request's, copied where its handler ran."""
    return StreamingResponse(_drive(chunks, context, timeout, on_timeout), media_type=media_type, headers=dict(headers))
