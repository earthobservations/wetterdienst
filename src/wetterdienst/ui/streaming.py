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
A wide CSV has the columns of the request, in its order, as its header is written with the first station (GH-4432).

The first station is read before the response begins, so that a request that fails on it has the status of the
failure and not a 200. The timeout of the server holds between two chunks (`ui.middleware`).

The work of a stream ends when its answer does (GH-4429): a chunk that ran into the timeout, a client that has
gone, and a response that ends for any other reason set the `Cancellation` of the request (`util.cancellation`), and
the walk that produces the chunks stops at the next station or file instead of reading on for a client that is no
longer there. A server without a timeout (`WD_RESTAPI_TIMEOUT=0`) still holds no stream to one; its streams end when
they are read to the end or their client leaves.
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any, cast

import polars as pl
from starlette.concurrency import run_in_threadpool
from starlette.responses import StreamingResponse

from wetterdienst.ui.render import ndjson_line
from wetterdienst.util.cancellation import current
from wetterdienst.util.logging import get_one_line_logger

if TYPE_CHECKING:
    import contextvars
    from collections.abc import AsyncIterator, Callable, Iterator, Mapping

    from starlette.types import Message, Receive, Scope, Send

    from wetterdienst.util.cancellation import Cancellation

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
    schema: pl.Schema | None = None,
) -> Iterator[bytes]:
    """Write the chunks of a CSV answer: the header with the first frame, then the rows of each.

    The header is written before the other frames are read, so every frame is written with the columns of the
    header, in its order. They are `schema`'s where it is given, the columns of the first frame where not. A frame
    that lacks one has it empty: the wide frame of a station has the columns of the parameters it delivers only, so
    the stream of a wide answer is given the columns of the request (`TimeseriesValues._wide_schema`), and the CSV of
    a station that has no maximum still has the column of the maximum that a later station fills (GH-4432).

    A column that the header lacks cannot be added. It is not dropped without a word: it is logged, once for each
    column, at the point the stream has reached. It is no failure to cut the connection for, which would throw away
    what was sent already, and CSV has no place to say it. `empty` gives the frame whose header is written when there
    are no rows. `fail` is told of an exception, which is raised again so that the connection is cut: the status can
    no longer change and CSV has no place to say it.
    """
    columns = schema
    sent = False
    told: set[str] = set()
    try:
        for frame in frames:
            if columns is None:
                columns = frame.schema
            yield to_csv(_with_columns(frame, columns, told), header=not sent).encode()
            sent = True
        if not sent:
            yield to_csv(empty(), header=True).encode()
    except Exception as e:
        fail(e)
        raise


def _with_columns(frame: pl.DataFrame, columns: pl.Schema, told: set[str]) -> pl.DataFrame:
    """Give the frame the columns of the header, in its order: one it lacks is null, one the header lacks is logged."""
    for column in frame.columns:
        if column not in columns and column not in told:
            told.add(column)
            log.warning(
                f"The CSV has no column {column!r}, its header was written without it: the values of it are left out."
            )
    if frame.columns == list(columns):
        return frame
    return frame.select(
        [pl.col(c) if c in frame.columns else pl.lit(None, dtype).alias(c) for c, dtype in columns.items()]
    )


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
    None where there is nothing to say; the thread that was producing the chunk is left to finish, and is told to
    end its work when the response ends (`_EndsItsWork`, GH-4429).
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
    cancellation = context.run(current)
    return _EndsItsWork(
        _drive(chunks, context, timeout, on_timeout),
        cancellation=cancellation,
        media_type=media_type,
        headers=dict(headers),
    )


class _EndsItsWork(StreamingResponse):
    """A streamed response that ends the work of its request when its client leaves or it ends (GH-4429).

    A server that speaks ASGI before 2.4 (uvicorn does) reports the client's leaving through `receive`, and the
    response then waits for the chunk in the thread to be done before it is over: the work is told to stop where the
    client's leaving is heard, not after it, or the walk would read on while the response waits for it. A server that
    speaks 2.4 learns of it by an error on the next write, and no thread is working then (the next chunk is not
    asked for until this one is written). Whatever ends the response sets it again, for a response that ended for
    another reason; after one that ended because the chunks did, there is no work left to end and it changes nothing.
    """

    def __init__(self, *args: Any, cancellation: Cancellation | None, **kwargs: Any) -> None:  # noqa: ANN401
        """Make the response, remembering the cancellation to set."""
        super().__init__(*args, **kwargs)
        self._cancellation = cancellation

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Send the response; when the client leaves or it is over, end the work that made it."""
        cancellation = self._cancellation

        async def hear() -> Message:
            message = await receive()
            if cancellation is not None and message["type"] == "http.disconnect":
                cancellation.set("client-left")
            return message

        try:
            await super().__call__(scope, hear, send)
        finally:
            if cancellation is not None:
                cancellation.set("response-ended")
