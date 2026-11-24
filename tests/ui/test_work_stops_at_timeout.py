# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The work of a REST or MCP request ends when its answer has timed out or its client has gone (GH-4429).

A request that ran into the timeout was answered with its 504, but its thread read on to the last station, held
its place of the cap and downloaded. The server now sets a `Cancellation` for the work of each request, and the
walk over the stations ends at the next one when it is set (`util.cancellation`).

A slow provider stands in: a real `DwdObservationValues` whose collection of a station is a stub, so that the
route, the middleware, the walk (`TimeseriesValues.query`) and the stream are the real ones. A station "is slow"
by waiting for the event of the test, never for a time: where the walk is at the timeout is then known, and a slow
runner changes nothing but how long the test takes. What is asserted is how many stations were read after the
answer, which is the station in hand at most.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import gc
import logging
import sys
import threading
import weakref
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from fastapi.testclient import TestClient

from tests.ui.test_operations import _HANG, _async_client, _first_served, _no_ambient_settings, _until  # noqa: F401
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationValues
from wetterdienst.ui import restapi
from wetterdienst.util import cancellation
from wetterdienst.util.cancellation import Cancellation, WorkAbandoned

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence
    from pathlib import Path

    from wetterdienst.model.result import ValuesResult

pytestmark = pytest.mark.usefixtures("_no_ambient_settings")

#: the stations the stub provider has
STATIONS = [f"{index:05d}" for index in range(12)]
PARAMETERS = "daily/climate_summary/temperature_air_mean_2m"


class SlowProvider:
    """A provider whose stations are read in the order asked for, each waiting for its event if the test holds it.

    `read` lists the stations whose collection began, `ended` counts the walks that are over, however they ended.
    """

    def __init__(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Stand the provider in for the DWD observations, with a cache directory of its own."""
        self.read: list[str] = []
        self.ended = 0
        self.lock = threading.Lock()
        self._holds: dict[str, threading.Event] = {}
        #: the stations whose readings lie outside the window asked for, so that they yield no chunk of a stream
        self._outside: set[str] = set()
        self._arrived: dict[str, threading.Event] = {}
        #: the cancellation each station was collected under: that of the request, seen from the thread of its walk
        self.cancellations: dict[str, Cancellation | None] = {}
        #: weak references to what the walk of each request holds in its frame, to tell whether it is freed
        self.walks: list[weakref.ref[Any]] = []
        #: the walks that were read to their end, whatever came of it
        self.completed = 0
        provider = self

        class Values(DwdObservationValues):
            def query(self) -> Iterator[ValuesResult]:
                try:
                    yield from super().query()
                    with provider.lock:
                        provider.completed += 1
                finally:
                    with provider.lock:
                        provider.ended += 1

            def _collect_station_parameter_or_dataset(
                self,
                station_id: str,
                parameter_or_dataset: object,  # noqa: ARG002
            ) -> pl.DataFrame:
                with provider.lock:
                    provider.read.append(station_id)
                    provider.cancellations[station_id] = cancellation.current()
                provider.arrived(station_id).set()
                frame = sys._getframe()  # noqa: SLF001
                while frame is not None and frame.f_code.co_name != "_query_stations":
                    frame = frame.f_back  # ty: ignore[invalid-assignment]
                if frame is not None and not provider.walks:
                    provider.walks.append(weakref.ref(frame.f_locals["rows"]))
                hold = provider._holds.get(station_id)
                if hold is not None:
                    hold.wait(_HANG)
                year = 1990 if station_id in provider._outside else 2000
                return pl.DataFrame(
                    {
                        "timestamp": [dt.datetime(year, 1, 2, tzinfo=ZoneInfo("UTC"))],
                        "parameter": ["tmk"],
                        # in the unit of the source, a tenth of a degree: a plausible temperature
                        "value": [0.1],
                    },
                    schema_overrides={"timestamp": pl.Datetime("us", "UTC")},
                )

        utc = ZoneInfo("UTC")
        size = len(STATIONS)
        stations = pl.DataFrame(
            {
                "resolution": ["daily"] * size,
                "dataset": ["climate_summary"] * size,
                "station_id": STATIONS,
                "start_timestamp": [dt.datetime(1900, 1, 1, tzinfo=utc)] * size,
                "end_timestamp": [dt.datetime(2030, 1, 1, tzinfo=utc)] * size,
                "latitude": [50.0 + index / 10 for index in range(size)],
                "longitude": [8.0 + index / 10 for index in range(size)],
                "elevation": [100.0] * size,
                "name": STATIONS,
                "region": ["x"] * size,
            }
        )
        monkeypatch.setattr(DwdObservationRequest, "_all", lambda self: stations.lazy())  # noqa: ARG005
        monkeypatch.setattr(DwdObservationRequest, "_values", Values)
        monkeypatch.setenv("WD_CACHE_DIR", str(tmp_path / "cache"))

    def arrived(self, station: str) -> threading.Event:
        """Give the event that is set when the collection of `station` has begun."""
        with self.lock:
            return self._arrived.setdefault(station, threading.Event())

    def hold(self, station: str) -> None:
        """Have the collection of `station` wait until `release`."""
        self._holds[station] = threading.Event()

    def outside_window(self, *stations: str) -> None:
        """Give `stations` readings the window does not hold: the walk passes over them without a result."""
        self._outside.update(stations)

    def release(self) -> None:
        """Let every held station go."""
        for event in self._holds.values():
            event.set()

    def snapshot(self) -> list[str]:
        """Give the stations read so far."""
        with self.lock:
            return list(self.read)

    def walk_is_freed(self) -> bool:
        """Tell whether what the walk held in its frame is gone, with the collector of cycles switched off."""
        return bool(self.walks) and self.walks[0]() is None

    async def until_ended(self, walks: int = 1) -> None:
        """Wait until `walks` walks are over: their threads are done and their places of the cap are given back."""
        await _until(lambda: self.ended >= walks, f"{walks} walks ended")


@pytest.fixture
def slow(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[SlowProvider]:
    """Give the slow provider, and let every held station go at the end so that no thread outlives the test."""
    provider = SlowProvider(monkeypatch, tmp_path)
    try:
        yield provider
    finally:
        provider.release()


def _params(stations: Sequence[str], **more: str) -> dict[str, str]:
    return {
        "provider": "dwd",
        "network": "observation",
        "parameters": PARAMETERS,
        "stations": ",".join(stations),
        "timestamp": "2000-01-01/2000-01-10",
        **more,
    }


def _beyond_the_station_in_hand(slow: SlowProvider, at_timeout: Sequence[str]) -> list[str]:
    """Give the stations that were read after the timeout, other than the one that was in hand: there must be none.

    The walk ends at the check before the next station, so at most the station in hand when the answer went is read
    after it: that is one more than the stations read then, and it is the first of the ones that were not.
    """
    final = slow.snapshot()
    assert final[: len(at_timeout)] == list(at_timeout)
    return final[len(at_timeout) + 1 :]


# --- values over REST --------------------------------------------------------------------------------------------


def test_the_work_of_a_request_that_timed_out_ends_at_the_station_in_hand(
    slow: SlowProvider, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The 504 is the answer as before; the walk reads no station after the one in hand and gives its place back."""
    monkeypatch.setenv("WD_RESTAPI_MAX_CONCURRENT", "1")
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "0.3")
    slow.hold("00001")

    async def run() -> tuple[Any, list[str], int]:
        async with _async_client() as client:
            timed_out = await client.get("/api/v1/values", params=_params(STATIONS[:6]))
            at_timeout = slow.snapshot()
            # the timeout is no part of the rest of the test
            monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "60")
            slow.release()
            await slow.until_ended()
            # the place of the cap, which is one, is free again and the next request is served
            served = await _first_served_values(client)
            return timed_out, at_timeout, served

    with caplog.at_level(logging.INFO):
        timed_out, at_timeout, served = asyncio.run(run())

    assert timed_out.status_code == 504
    body = timed_out.json()
    assert body["type"] == "urn:wetterdienst:problem:request-timeout"
    assert "0.3 seconds" in body["detail"]
    assert served == 200
    # not the six stations: those after the one in hand were not read
    assert _beyond_the_station_in_hand(slow, at_timeout) == []
    assert len(slow.snapshot()) < 6
    # told as one line of info, and not as an error: the logs of a server hold the errors it has
    assert sum("stopped its work: timeout" in r.getMessage() and r.levelno == logging.INFO for r in caplog.records) == 1
    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []
    assert not any("failed after its timeout" in r.getMessage() for r in caplog.records)


async def _first_served_values(client: Any) -> int:  # noqa: ANN401
    """Ask for one station until the request is no longer refused for want of a place; give its status."""
    import time  # noqa: PLC0415

    deadline = time.monotonic() + _HANG
    while (status := (await client.get("/api/v1/values", params=_params(STATIONS[:1]))).status_code) == 503:
        assert time.monotonic() < deadline, "the place was not given back"
        await asyncio.sleep(0.01)
    return status


def test_a_request_that_ends_in_time_is_the_answer_it_was(slow: SlowProvider, monkeypatch: pytest.MonkeyPatch) -> None:
    """With a timeout that is not reached, every station is read and the answer holds each of them, as it did."""
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "60")
    client = TestClient(restapi.app, raise_server_exceptions=False)

    response = client.get("/api/v1/values", params=_params(STATIONS[:6]))

    assert response.status_code == 200
    assert slow.snapshot() == STATIONS[:6]
    assert {row["station_id"] for row in response.json()["values"]} == set(STATIONS[:6])


def test_a_request_with_no_timeout_is_not_cut(slow: SlowProvider, monkeypatch: pytest.MonkeyPatch) -> None:
    """`WD_RESTAPI_TIMEOUT=0` sets no end to a request: its work has none either."""
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "0")
    client = TestClient(restapi.app, raise_server_exceptions=False)

    response = client.get("/api/v1/values", params=_params(STATIONS[:6]))

    assert response.status_code == 200
    assert slow.snapshot() == STATIONS[:6]


def test_requests_in_flight_together_never_see_each_others_cancellation(
    slow: SlowProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One request times out while another is in its walk: the other is read to its end and answered."""
    slow.hold("00006")
    slow.hold("00001")
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "60")

    async def run() -> tuple[Any, Any]:
        async with _async_client() as client:
            # the long one, in its walk and held at its first station
            other = asyncio.ensure_future(client.get("/api/v1/values", params=_params(STATIONS[6:9])))
            await _until(slow.arrived("00006").is_set, "the first request in its walk")
            # the one that times out: its timeout is read as it begins
            monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "0.3")
            timed_out = await client.get("/api/v1/values", params=_params(STATIONS[:6]))
            assert timed_out.status_code == 504
            slow.release()
            await slow.until_ended(2)
            return timed_out, await other

    _, other = asyncio.run(run())

    assert other.status_code == 200
    assert {row["station_id"] for row in other.json()["values"]} == set(STATIONS[6:9])
    assert [s for s in slow.snapshot() if s in STATIONS[6:9]] == STATIONS[6:9]
    # and the one that timed out ended at the station it was at: the held one is the second, and none is read after
    assert [s for s in slow.snapshot() if s in STATIONS[:6]] in (STATIONS[:0], STATIONS[:1], STATIONS[:2])


def test_a_request_after_one_that_timed_out_is_not_cut_by_it(
    slow: SlowProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The cancellation is left with the request that had it: the thread that served it takes no part of it on."""
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "0.3")
    slow.hold("00001")

    async def run() -> Any:  # noqa: ANN401
        async with _async_client() as client:
            first = await client.get("/api/v1/values", params=_params(STATIONS[:6]))
            assert first.status_code == 504
            slow.release()
            await slow.until_ended()
            monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "60")
            return await client.get("/api/v1/values", params=_params(STATIONS[6:9]))

    second = asyncio.run(run())

    assert second.status_code == 200
    assert len(second.json()["values"]) == 3


@pytest.mark.parametrize("route", ["interpolate", "summarize"])
def test_the_work_of_an_estimate_that_timed_out_ends_at_the_station_in_hand(
    slow: SlowProvider, monkeypatch: pytest.MonkeyPatch, route: str
) -> None:
    """`interpolate` and `summarize` walk stations until they have enough: that walk ends at the timeout too.

    No station has readings in the window, so the estimate reads on from one station to the next, as it does when
    the nearest stations have none.
    """
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "0.3")
    slow.outside_window(*STATIONS)
    slow.hold("00001")
    params = {
        "provider": "dwd",
        "network": "observation",
        "parameters": PARAMETERS,
        "latitude": "50.2",
        "longitude": "8.2",
        "timestamp": "2000-01-01/2000-01-10",
    }

    async def run() -> tuple[Any, list[str]]:
        async with _async_client() as client:
            timed_out = await client.get(f"/api/v1/{route}", params=params)
            at_timeout = slow.snapshot()
            monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "60")
            slow.release()
            await slow.until_ended()
            return timed_out, at_timeout

    timed_out, at_timeout = asyncio.run(run())

    assert timed_out.status_code == 504, timed_out.text
    assert _beyond_the_station_in_hand(slow, at_timeout) == []
    assert len(slow.snapshot()) < len(STATIONS)


@pytest.fixture
def no_collector() -> Iterator[None]:
    """Switch the collector of cycles off, so that only what is freed by counting references is freed."""
    gc.collect()
    gc.disable()
    try:
        yield
    finally:
        gc.enable()


@pytest.mark.usefixtures("no_collector")
def test_the_walk_of_a_request_that_timed_out_is_freed_without_a_collection(
    slow: SlowProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """What the walk had read is freed once its place is given back: the exception that ended it keeps no frame.

    The exception crosses the worker future of the thread pool, and its traceback would hold the frames of the walk
    in a cycle that only a full collection frees (34, 66, 98 MB for three requests that timed out).
    """
    monkeypatch.setenv("WD_RESTAPI_MAX_CONCURRENT", "1")
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "0.3")
    slow.hold("00001")

    async def run() -> None:
        async with _async_client() as client:
            assert (await client.get("/api/v1/values", params=_params(STATIONS[:6]))).status_code == 504
            monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "60")
            slow.release()
            await slow.until_ended()
            assert await _first_served_values(client) == 200

    asyncio.run(run())

    assert slow.walks, "the walk was not seen"
    assert slow.walk_is_freed()


def test_the_work_ends_after_the_last_station_too(slow: SlowProvider, monkeypatch: pytest.MonkeyPatch) -> None:
    """A request with one long station times out in it: the walk ends there and is not read to its end.

    What follows the last station (the rows, the picture, the export of what was read) is made for nobody otherwise.
    """
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "0.3")
    slow.hold("00000")

    async def run() -> int:
        async with _async_client() as client:
            response = await client.get("/api/v1/values", params=_params(STATIONS[:1]))
            monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "60")
            slow.release()
            await slow.until_ended()
            return response.status_code

    assert asyncio.run(run()) == 504
    assert slow.completed == 0


@pytest.mark.parametrize("timeout", ["60", "0"])
def test_a_request_that_is_cancelled_ends_its_work(
    slow: SlowProvider, monkeypatch: pytest.MonkeyPatch, timeout: str
) -> None:
    """A client task that is cancelled (as an MCP client that gave up does) ends the work, with a timeout or without."""
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", timeout)
    slow.hold("00001")

    async def run() -> None:
        async with _async_client() as client:
            request = asyncio.ensure_future(client.get("/api/v1/values", params=_params(STATIONS[:6])))
            await _until(slow.arrived("00001").is_set, "the walk at the second station")
            request.cancel()
            await asyncio.gather(request, return_exceptions=True)
            walk = slow.cancellations["00001"]
            assert walk is not None
            # told to stop where the request was cancelled, not when the station in hand is done
            await _until(walk.is_set, "the work told to stop", 5)
            assert walk.reason == "cancelled"
            slow.release()
            await slow.until_ended()

    asyncio.run(run())

    assert slow.snapshot() == STATIONS[:2]


@pytest.mark.parametrize("timeout", ["60", "0"])
def test_a_tool_that_the_assistant_gave_up_on_ends_its_work(
    slow: SlowProvider, monkeypatch: pytest.MonkeyPatch, timeout: str
) -> None:
    """The assistant's own timeout of a tool call cancels it, and the walk of its request stops at its station."""
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", timeout)
    slow.hold("00001")

    async def call() -> None:
        async with Client(build_mcp_server(restapi.app)) as client:
            with pytest.raises(Exception, match=r"(?i)timed out|timeout"):
                await client.call_tool("values", _params(STATIONS[:6]), timeout=0.5, raise_on_error=False)
            walk = slow.cancellations.get("00001")
            assert walk is not None
            await _until(walk.is_set, "the work told to stop", 10)
            assert walk.reason == "cancelled"
            slow.release()
            await slow.until_ended()

    asyncio.run(call())

    assert slow.snapshot() == STATIONS[:2]


def test_the_end_of_the_work_that_nobody_ordered_is_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """A `WorkAbandoned` of a request whose answer is not gone is a defect: it is not hidden as the end of an answer."""
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "60")

    def abandoned(**_kwargs: object) -> None:
        reason = "nobody asked for this"
        raise WorkAbandoned(reason)

    monkeypatch.setattr(restapi, "get_values", abandoned)

    async def run() -> None:
        async with _async_client() as client:
            await client.get("/api/v1/values", params=_params(STATIONS[:1]))

    with pytest.raises(BaseException) as raised:  # noqa: PT011
        asyncio.run(run())
    assert "nobody asked for this" in repr(raised.value) or isinstance(raised.value, WorkAbandoned)


def test_the_first_reason_to_stop_stays() -> None:
    """Whoever ends the work first says why: a later reason (the response's end after a timeout) does not replace it."""
    cancel = Cancellation()
    assert cancel.reason is None
    assert not cancel.is_set()
    cancel.set("timeout")
    cancel.set("response-ended")
    assert (cancel.reason, cancel.is_set()) == ("timeout", True)
    with pytest.raises(WorkAbandoned, match="timeout"):
        cancel.check()


# --- streams -----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("fmt", ["ndjson", "csv"])
def test_the_work_of_a_stream_that_timed_out_ends_at_the_station_in_hand(
    slow: SlowProvider, monkeypatch: pytest.MonkeyPatch, fmt: str
) -> None:
    """A chunk that takes longer than the timeout ends the stream, and the walk behind it reads no more stations.

    The timeout is two seconds, as in the stream tests of `test_operations.py`: the station that is held is the
    chunk that is too late, and the ones before it are read at once.
    """
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "2")
    slow.hold("00002")
    # the held station and those after it have no rows in the window: the chunk that is too late is one `next` of the
    # walk, which passes over them one after the other, and the check between them is the only thing that can stop it
    # (nothing asks for another chunk once the stream has ended)
    slow.outside_window(*STATIONS[2:6])
    client = TestClient(restapi.app, raise_server_exceptions=False)

    response = client.get("/api/v1/values", params=_params(STATIONS[:6], format=fmt))
    at_timeout = slow.snapshot()
    slow.release()

    async def ended() -> None:
        await slow.until_ended()

    asyncio.run(ended())
    assert response.status_code == 200
    if fmt == "ndjson":
        assert '"urn:wetterdienst:problem:request-timeout"' in response.text.splitlines()[-1]
    assert at_timeout == STATIONS[:3]
    assert slow.snapshot() == STATIONS[:3]


@pytest.mark.usefixtures("no_collector")
@pytest.mark.parametrize("fmt", ["ndjson", "csv"])
def test_the_walk_of_a_stream_that_timed_out_is_freed_without_a_collection(
    slow: SlowProvider, monkeypatch: pytest.MonkeyPatch, fmt: str
) -> None:
    """As for a request: the stream's walk keeps nothing alive once its work has ended."""
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "2")
    slow.hold("00002")
    slow.outside_window(*STATIONS[2:6])
    client = TestClient(restapi.app, raise_server_exceptions=False)

    client.get("/api/v1/values", params=_params(STATIONS[:6], format=fmt))
    slow.release()

    async def freed() -> None:
        await slow.until_ended()
        await _until(slow.walk_is_freed, "the walk freed", 10)

    asyncio.run(freed())


def test_the_work_of_a_stream_whose_client_has_gone_ends_at_the_station_in_hand(
    slow: SlowProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The client leaves while the walk is at a station: the stations after it are not read for nobody.

    Driven as uvicorn does for an ASGI of the version it speaks (2.3), where the server learns of the client's leaving
    from `receive`.
    """
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "0")
    slow.hold("00002")
    slow.outside_window(*STATIONS[2:6])

    async def run() -> None:
        sent: list[dict[str, Any]] = []

        async def receive() -> dict[str, Any]:
            # the client has read the first rows and leaves while the walk waits at the third station
            await _until(slow.arrived("00002").is_set, "the walk at the third station")
            return {"type": "http.disconnect"}

        async def send(message: dict[str, Any]) -> None:
            sent.append(message)

        async def let_go_once_told_to_stop() -> None:
            # the walk is held at the third station, and is let go when the server has told it to stop, as the server
            # does where it hears the client leave: not before, or the test would let it read on by itself
            await _until(
                lambda: (c := slow.cancellations.get("00002")) is not None and c.is_set(), "the work told to stop", 5
            )
            assert slow.cancellations["00002"].reason == "client-left"
            slow.release()

        scope = {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": "1.1",
            "method": "GET",
            "scheme": "http",
            "path": "/api/v1/values",
            "raw_path": b"/api/v1/values",
            "root_path": "",
            "query_string": "&".join(f"{k}={v}" for k, v in _params(STATIONS[:6], format="ndjson").items()).encode(),
            "headers": [(b"host", b"testserver")],
            "client": ("127.0.0.1", 1234),
            "server": ("testserver", 80),
        }
        try:
            await asyncio.gather(restapi.app(scope, receive, send), let_go_once_told_to_stop())
        finally:
            slow.release()
        await slow.until_ended()

    asyncio.run(run())

    assert slow.snapshot() == STATIONS[:3]


# --- MCP ---------------------------------------------------------------------------------------------------------


def test_the_work_of_a_tool_that_timed_out_ends_at_the_station_in_hand(
    slow: SlowProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The tool's error is the 504 of the request as it was, and its walk stops as a REST request's does."""
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "0.3")
    slow.hold("00001")

    async def call() -> tuple[Any, list[str]]:
        async with Client(build_mcp_server(restapi.app)) as client:
            result = await client.call_tool("values", _params(STATIONS[:6]), raise_on_error=False)
            at_timeout = slow.snapshot()
            monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "60")
            slow.release()
            await slow.until_ended()
            return result, at_timeout

    result, at_timeout = asyncio.run(call())

    assert result.is_error
    assert "HTTP error 504" in result.content[0].text
    assert "request timeout of 0.3 seconds" in result.content[0].text
    assert _beyond_the_station_in_hand(slow, at_timeout) == []
    assert len(slow.snapshot()) < 6


# --- no effect without a server ----------------------------------------------------------------------------------


def test_python_has_no_deadline_and_the_server_leaves_none_behind(
    slow: SlowProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A walk in Python reads every station, before a request and after one that timed out in the same thread."""
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "0.3")
    slow.hold("00001")

    def walk() -> int:
        request = DwdObservationRequest(parameters=[PARAMETERS], start="2000-01-01", end="2000-01-10")
        return len(request.filter_by_station_id(STATIONS[3:6]).values().all().df)

    assert cancellation.current() is None
    assert walk() == 3

    async def run() -> None:
        async with _async_client() as client:
            assert (await client.get("/api/v1/values", params=_params(STATIONS[:6]))).status_code == 504
            # the cancellation of that request is its own: this context has none
            assert cancellation.current() is None
            slow.release()
            await slow.until_ended()

    asyncio.run(run())
    slow.read.clear()

    assert cancellation.current() is None
    assert walk() == 3
    assert slow.snapshot() == STATIONS[3:6]


def test_the_cancellations_of_nested_scopes_are_each_their_own() -> None:
    """A scope inside a scope sees its own cancellation, the outer one again after it, and none outside both."""
    outer, inner = Cancellation(), Cancellation()
    with cancellation.cancellable(outer):
        outer.set("timeout")
        with cancellation.cancellable(inner):
            cancellation.check()
            assert cancellation.current() is inner
        assert cancellation.current() is outer
        with pytest.raises(WorkAbandoned):
            cancellation.check()
    assert cancellation.current() is None
    cancellation.check()


def test_a_thread_that_copies_the_context_sees_its_request_and_one_that_does_not_sees_none() -> None:
    """The threads of the server run in a copy of the context of the request; a pool's own threads are not given it."""
    import contextvars  # noqa: PLC0415

    seen: dict[str, Cancellation | None] = {}
    mine = Cancellation()

    def look(name: str) -> None:
        seen[name] = cancellation.current()

    with cancellation.cancellable(mine):
        context = contextvars.copy_context()
        for _name, target in (("copied", lambda: context.run(look, "copied")), ("plain", lambda: look("plain"))):
            thread = threading.Thread(target=target)
            thread.start()
            thread.join()

    assert seen == {"copied": mine, "plain": None}


# --- the rows of an interpolation, and the listings -------------------------------------------------------------


def test_the_rows_of_an_interpolation_are_not_all_calculated_once_the_answer_is_gone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The interpolation of a long series is one calculation per timestamp: it ends between two of them."""
    from tests.ui.test_geo_bounds import _ring_of_stations  # noqa: PLC0415
    from wetterdienst.core import interpolate  # noqa: PLC0415
    from wetterdienst.core.util import _ParameterData  # noqa: PLC0415

    stations = _ring_of_stations(6)
    rows = 60
    timestamps = [dt.datetime(2020, 1, 1, tzinfo=dt.UTC) + dt.timedelta(days=day) for day in range(rows)]
    param_dict = {
        ("daily", "climate_summary", "temperature_air_mean_2m"): _ParameterData(
            values=pl.DataFrame({"timestamp": timestamps, **{station: [1.0] * rows for station in stations}})
        )
    }
    calculated: list[int] = []
    cancel = Cancellation()
    apply = interpolate.apply_interpolation

    def counting(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        calculated.append(1)
        if len(calculated) == 3:
            cancel.set("timeout")
        return apply(*args, **kwargs)

    monkeypatch.setattr(interpolate, "apply_interpolation", counting)

    with cancellation.cancellable(cancel), pytest.raises(WorkAbandoned):
        interpolate.calculate_interpolation(0.0, 0.0, stations, param_dict, None)

    # the one in hand when it was set was finished, and the 56 that were left were not begun
    assert len(calculated) == 3
    # and with no cancellation every row is calculated
    calculated.clear()
    assert interpolate.calculate_interpolation(0.0, 0.0, stations, param_dict, None).height == rows
    assert len(calculated) == rows


def test_a_listing_is_not_begun_for_a_request_whose_answer_is_gone(tmp_path: Path) -> None:
    """The listing of a directory asks the server for nothing once the answer is gone."""
    from wetterdienst.settings import Settings  # noqa: PLC0415
    from wetterdienst.util.network import list_remote_directory_fsspec, list_remote_files_fsspec  # noqa: PLC0415

    cancel = Cancellation()
    cancel.set("timeout")
    settings = Settings(cache_dir=tmp_path / "cache")
    # nothing listens at the address: a listing that was begun would be a `NoInternetError`, not the end of the work
    for listing in (list_remote_files_fsspec, list_remote_directory_fsspec):
        with cancellation.cancellable(cancel), pytest.raises(WorkAbandoned):
            listing("http://127.0.0.1:1/dir/", settings)
