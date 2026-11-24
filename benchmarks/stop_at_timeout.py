# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Benchmark what a request that times out costs, and what the check that ends it costs a request that does not.

Run by a person, never by CI (it takes under a minute):

    uv run python -m benchmarks.stop_at_timeout                       # 100 stations of 0.1 s, a timeout of 2 s
    uv run python -m benchmarks.stop_at_timeout --stations 500 --timeout 5 --rows 10000

GH-4429: a REST or MCP request that ran into the timeout answered 504 and went on reading stations in its thread.
The server now ends that work (`wetterdienst.util.cancellation`).

**The timeout.** A local server stands in for the provider, answering each file after `--delay` seconds and counting
what it was asked. A real `DwdObservationValues` reads one file of it for each of `--stations` stations through
`download_file` (nothing cached, so each is a request) and holds `--rows` rows (daily readings of ten years by default,
so the stations that were read hold memory), behind the real REST app, with a cap of one request. The
request times out after `--timeout` seconds and is answered with its 504; what is measured, in a process of its own
for each of the two runs, is the CPU time of the server from the request to the moment its place of the cap is free,
the peak memory, the requests the provider was asked, and how long after the 504 the place was free. `before` is the
server as it was: the walk looks at the cancellation at every station, but nobody sets it (`Cancellation.set` does
nothing), which is what the code before the change did.

**A request in time.** The check is a read of a context variable and of an attribute, once for each station and
before each file. It is timed alone, and as the walk of 100 stations whose collection costs nothing, which is more
checks for the work than any real provider has: a station of a real provider is a download and a parse, milliseconds
at the least.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
import resource
import subprocess
import sys
import tempfile
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from zoneinfo import ZoneInfo

UTC = ZoneInfo("UTC")


class _Handler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:  # noqa: A002
        pass

    def do_GET(self) -> None:
        server: Any = self.server
        if self.path == "/__count":
            body = str(server.count).encode()
        else:
            with server.lock:
                server.count += 1
            time.sleep(server.delay)
            body = b"1"
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def _upstream(delay: float) -> ThreadingHTTPServer:
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    server.request_queue_size = 128
    server.delay = delay  # ty: ignore[unresolved-attribute]
    server.count = 0  # ty: ignore[unresolved-attribute]
    server.lock = threading.Lock()  # ty: ignore[unresolved-attribute]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server


def _requests_asked(url: str) -> int:
    with urllib.request.urlopen(f"{url}/__count", timeout=10) as response:  # noqa: S310
        return int(response.read())


def _rss_mb() -> float:
    out = subprocess.run(["ps", "-o", "rss=", "-p", str(os.getpid())], capture_output=True, text=True, check=True)  # noqa: S603, S607
    return int(out.stdout.strip()) / 1024


def _stub_provider(url: str, stations: int, rows: int) -> list[str]:
    import polars as pl  # noqa: PLC0415

    from wetterdienst.metadata.cache import CacheExpiry  # noqa: PLC0415
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415
    from wetterdienst.provider.dwd.observation.api import DwdObservationValues  # noqa: PLC0415
    from wetterdienst.util.network import download_file  # noqa: PLC0415

    ids = [f"{index:05d}" for index in range(stations)]
    frame = pl.DataFrame(
        {
            "resolution": ["daily"] * stations,
            "dataset": ["climate_summary"] * stations,
            "station_id": ids,
            "start_timestamp": [dt.datetime(1900, 1, 1, tzinfo=UTC)] * stations,
            "end_timestamp": [dt.datetime(2030, 1, 1, tzinfo=UTC)] * stations,
            "latitude": [50.0 + index / 1000 for index in range(stations)],
            "longitude": [8.0] * stations,
            "elevation": [100.0] * stations,
            "name": ids,
            "region": ["x"] * stations,
        }
    )

    class Values(DwdObservationValues):
        def _collect_station_parameter_or_dataset(self, station_id: str, parameter_or_dataset: object) -> pl.DataFrame:  # noqa: ARG002
            settings = self.sr.settings
            file = download_file(
                url=f"{url}/{station_id}",
                cache_dir=settings.cache_dir,
                ttl=CacheExpiry.NO_CACHE,
                client_kwargs=settings.fsspec_client_kwargs,
                cache_disable=True,
            )
            file.raise_if_exception()
            timestamps = pl.datetime_range(
                dt.datetime(2000, 1, 1, tzinfo=UTC),
                dt.datetime(2000, 1, 1, tzinfo=UTC) + dt.timedelta(days=rows - 1),
                "1d",
                time_zone="UTC",
                eager=True,
            ).alias("timestamp")
            return pl.DataFrame({"timestamp": timestamps, "parameter": "tmk", "value": 0.1})

    DwdObservationRequest._all = lambda self: frame.lazy()  # type: ignore[method-assign]  # noqa: ARG005, SLF001
    DwdObservationRequest._values = Values  # type: ignore[assignment]  # noqa: SLF001
    return ids


async def _timed_out_request(args: argparse.Namespace) -> dict[str, Any]:
    import httpx2  # noqa: PLC0415

    from wetterdienst.ui import restapi  # noqa: PLC0415
    from wetterdienst.ui.middleware import RequestContextMiddleware  # noqa: PLC0415

    ids = _stub_provider(args.upstream, args.stations, args.rows)
    client = httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=restapi.app, raise_app_exceptions=False), base_url="http://testserver"
    )
    params = {
        "provider": "dwd",
        "network": "observation",
        "parameters": "daily/climate_summary/temperature_air_mean_2m",
        "stations": ",".join(ids),
        "timestamp": f"2000-01-01/{(dt.date(2000, 1, 1) + dt.timedelta(days=args.rows - 1)).isoformat()}",
    }
    # warm up the app and the imports outside the measurement: a request that is answered at once
    await client.get("/api/v1/version")
    middleware: Any = restapi.app.middleware_stack
    while middleware is not None and not isinstance(middleware, RequestContextMiddleware):
        middleware = getattr(middleware, "app", None)
    if middleware is None:
        msg = "the middleware of the app was not found"
        raise RuntimeError(msg)

    cpu_before = resource.getrusage(resource.RUSAGE_SELF)
    began = time.monotonic()
    response = await client.get("/api/v1/values", params=params)
    answered = time.monotonic()
    asked_at_answer = _requests_asked(args.upstream)
    while middleware.in_flight:  # noqa: ASYNC110 -- the count is the middleware's own, there is no event to wait for
        await asyncio.sleep(0.005)
    free = time.monotonic()
    cpu_after = resource.getrusage(resource.RUSAGE_SELF)
    rss = _rss_mb()
    # what is asked of the provider after the place is free would be asked by something that is still running
    await asyncio.sleep(1.0)
    return {
        "status": response.status_code,
        "answered_s": round(answered - began, 2),
        "slot_free_after_answer_s": round(free - answered, 2),
        "cpu_s": round(
            cpu_after.ru_utime + cpu_after.ru_stime - cpu_before.ru_utime - cpu_before.ru_stime,
            2,
        ),
        "peak_rss_mb": round(cpu_after.ru_maxrss / (1024 * 1024 if sys.platform == "darwin" else 1024), 1),
        "rss_mb": round(rss, 1),
        "provider_requests_at_answer": asked_at_answer,
        "provider_requests_in_all": _requests_asked(args.upstream),
    }


def _worker(args: argparse.Namespace) -> None:
    os.environ["WD_RESTAPI_TIMEOUT"] = str(args.timeout)
    os.environ["WD_RESTAPI_MAX_CONCURRENT"] = "1"
    os.environ["WD_CACHE_DIR"] = tempfile.mkdtemp(prefix="wd-bench-")
    if args.mode == "before":
        from wetterdienst.util.cancellation import Cancellation  # noqa: PLC0415

        Cancellation.set = lambda self, reason: None  # type: ignore[method-assign]  # noqa: ARG005
    print(json.dumps(asyncio.run(_timed_out_request(args))))


def _timeout_benchmark(args: argparse.Namespace) -> None:
    server = _upstream(args.delay)
    url = f"http://127.0.0.1:{server.server_port}"
    print(
        f"{args.stations} stations of {args.delay:g} s each ({args.stations * args.delay:g} s to read them all), "
        f"timeout {args.timeout:g} s, a cap of one request"
    )
    rows = {}
    for mode in ("before", "after"):
        # let the work of the run before end: its requests are not the next run's
        time.sleep(args.delay * 2)
        with server.lock:  # ty: ignore[unresolved-attribute]
            server.count = 0  # ty: ignore[unresolved-attribute]
        out = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-m",
                "benchmarks.stop_at_timeout",
                "--worker",
                mode,
                "--stations",
                str(args.stations),
                "--timeout",
                str(args.timeout),
                "--rows",
                str(args.rows),
                "--upstream",
                url,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        rows[mode] = json.loads(out.stdout.strip().splitlines()[-1])
    keys = list(rows["before"])
    print(f"{'':32}{'before':>12}{'after':>12}")
    for key in keys:
        print(f"{key:32}{rows['before'][key]!s:>12}{rows['after'][key]!s:>12}")
    server.shutdown()


def _overhead_benchmark(stations: int = 100, repeats: int = 3) -> None:
    import contextvars  # noqa: PLC0415

    import polars as pl  # noqa: PLC0415

    from wetterdienst.model import values as values_module  # noqa: PLC0415
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415
    from wetterdienst.provider.dwd.observation.api import DwdObservationValues  # noqa: PLC0415
    from wetterdienst.settings import Settings  # noqa: PLC0415
    from wetterdienst.util import cancellation  # noqa: PLC0415

    os.environ["WD_CACHE_DIR"] = tempfile.mkdtemp(prefix="wd-bench-")
    calls = 2_000_000
    for label, active in (("no request (Python, CLI)", None), ("a request's, not set", cancellation.Cancellation())):
        context = contextvars.copy_context()
        if active is not None:
            context.run(cancellation._CURRENT.set, active)  # noqa: SLF001
        began = time.perf_counter()
        context.run(lambda: [cancellation.check() for _ in range(calls)])
        print(f"check() with {label}: {(time.perf_counter() - began) / calls * 1e9:.0f} ns a call")

    class Values(DwdObservationValues):
        def _collect_station_parameter_or_dataset(self, station_id: str, parameter_or_dataset: object) -> pl.DataFrame:  # noqa: ARG002
            return pl.DataFrame(
                {"timestamp": [dt.datetime(2000, 1, 2, tzinfo=UTC)], "parameter": ["tmk"], "value": [0.1]},
                schema_overrides={"timestamp": pl.Datetime("us", "UTC")},
            )

    ids = [f"{index:05d}" for index in range(stations)]
    frame = pl.DataFrame(
        {
            "resolution": ["daily"] * stations,
            "dataset": ["climate_summary"] * stations,
            "station_id": ids,
            "start_timestamp": [dt.datetime(1900, 1, 1, tzinfo=UTC)] * stations,
            "end_timestamp": [dt.datetime(2030, 1, 1, tzinfo=UTC)] * stations,
            "latitude": [50.0] * stations,
            "longitude": [8.0] * stations,
            "elevation": [100.0] * stations,
            "name": ids,
            "region": ["x"] * stations,
        }
    )
    DwdObservationRequest._all = lambda self: frame.lazy()  # type: ignore[method-assign]  # noqa: ARG005, SLF001
    DwdObservationRequest._values = Values  # type: ignore[assignment]  # noqa: SLF001
    request = DwdObservationRequest(
        parameters=["daily/climate_summary/temperature_air_mean_2m"],
        start="2000-01-01",
        end="2000-01-10",
        settings=Settings(cache_dir=os.environ["WD_CACHE_DIR"]),
    )

    def walk() -> float:
        began = time.perf_counter()
        request.filter_by_station_id(ids).values().all()
        return time.perf_counter() - began

    def best(*, checking: bool) -> float:
        original = values_module.check_cancelled
        if not checking:
            values_module.check_cancelled = lambda: None
        try:
            walk()
            return min(walk() for _ in range(repeats))
        finally:
            values_module.check_cancelled = original

    with_check, without_check = best(checking=True), best(checking=False)
    print(
        f"walk of {stations} stations that cost nothing, best of {repeats}: "
        f"{with_check * 1e3:.1f} ms with the check, {without_check * 1e3:.1f} ms without "
        f"({(with_check - without_check) / stations * 1e6:+.1f} us a station)"
    )


def main() -> None:
    """Run the benchmarks."""
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])  # ty: ignore[possibly-missing-attribute]
    parser.add_argument("--stations", type=int, default=100)
    parser.add_argument("--timeout", type=float, default=2.0)
    parser.add_argument("--delay", type=float, default=0.1)
    parser.add_argument("--rows", type=int, default=3650, help="the rows of each station")
    parser.add_argument("--worker", choices=["before", "after"], help=argparse.SUPPRESS)
    parser.add_argument("--upstream", help=argparse.SUPPRESS)
    parser.add_argument("--skip-overhead", action="store_true")
    args = parser.parse_args()
    if args.worker:
        args.mode = args.worker
        _worker(args)
        return
    _timeout_benchmark(args)
    if not args.skip_overhead:
        _overhead_benchmark()


if __name__ == "__main__":
    main()
