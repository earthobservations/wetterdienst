# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What the REST API does for every request (GH-3065, GH-3087, GH-3089).

The request id, the host check, the cap on requests served at once, the request timeout, the deprecation headers and
`nosniff`:

- **`X-Request-ID`** is sent with every response: the client's own where it sent a plain one, else made here.
  The problem of an error carries it as `instance` and `request_id` (`ui.problems`).
- **The host check** (`WD_RESTAPI_ALLOWED_HOSTS`, any host by default) refuses a request whose `Host` is not listed
  with a 400 problem of the kind `host-not-allowed`, and a request to the MCP endpoint whose `Origin` names a host
  that is not listed with `origin-not-allowed`. A page of another site that a DNS name re-pointed at a local server
  reaches it with its own name in `Host`. `wetterdienst restapi` lists the loopback names for a server it starts on
  the loopback interface.
- **The cap** (`WD_RESTAPI_MAX_CONCURRENT`, 32 by default, 0 for none) counts the requests under `/api` being
  served. One past the cap is a 503 problem of the kind `server-busy`, with `Retry-After`, before anything starts.
  A request keeps its slot until its handler is done, not until its answer is sent: see the timeout. A request that
  is cancelled (an MCP client that gave up) gives it back at once, while its thread ends with the station in hand.
- **The timeout** (`WD_RESTAPI_TIMEOUT`, 60 seconds by default, 0 for none) holds for the routes under `/api`
  until the response begins: a request that has not been answered by then is a 504 problem of the kind
  `request-timeout`, with `Retry-After`. The thread of a handler cannot be cancelled, so the request is not
  either: it is left to end with its answer dropped, and keeps its slot of the cap until it has. The work is told
  to stop, though (`util.cancellation`, GH-4429): the middleware sets a flag as it answers (or as the request is
  cancelled), and the walk over the stations ends at the next station, file or listing it would begin, so the slot is
  back within the time of the station in hand and what had been fetched by then is cached for the retry. A single
  download, the parse of a file and the readings of one station are not cut. So the cap bounds the threads, which a
  timeout alone does not. Once the response has begun, the middleware leaves it alone: a streamed answer holds the
  timeout between its chunks itself, and ends its work when it times out or its client has gone (`ui.streaming`).
- **`X-Content-Type-Options: nosniff`** is sent with every response, a problem's included (`ui.problems`), unless the
  response has the header already, so that it is not sent twice (GH-3349). A `Content-Security-Policy` is not sent
  here: the answers that carry one set it themselves (`ui.restapi`).
- **`Deprecation`, `Sunset` and `Link`** are sent for what the request used and the handlers marked deprecated
  (`ui.deprecation`).
"""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from starlette.datastructures import Headers, MutableHeaders

from wetterdienst.settings import RESTAPI_MAX_CONCURRENT, RESTAPI_TIMEOUT, Settings
from wetterdienst.ui.deprecation import begin_deprecations, deprecation_headers
from wetterdienst.ui.problems import (
    CONTENT_TYPE_OPTIONS_HEADER,
    NOSNIFF,
    REQUEST_ID_HEADER,
    ProblemKind,
    problem_response,
    request_id_from,
    set_request_id,
)
from wetterdienst.util.cancellation import Cancellation, WorkAbandoned, cancellable
from wetterdienst.util.hosts import host_of_header, host_of_origin, is_allowed
from wetterdienst.util.logging import get_one_line_logger

if TYPE_CHECKING:
    from starlette.responses import JSONResponse
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

    from wetterdienst.ui.deprecation import Deprecation

log = get_one_line_logger(__name__)

#: the routes the timeout and the cap hold for: the API, not the index, the probes or the MCP transport
#: (`/mcp/v1` and its alias `/mcp`); the tools call the API in process, so their requests are held to them
_TIMED_PREFIX = "/api/"
#: the MCP endpoint, `/mcp/v1` and its alias `/mcp`, whose `Origin` is checked as well
_MCP_PATH = "/mcp"
#: the liveness probe and the readiness probe, which the host check and the cap leave alone
_PROBE_PATHS = ("/health", "/ready")


def request_timeout() -> float | None:
    """Read the timeout of the server in seconds, None for none.

    A malformed setting is the server's to fix and it refuses to start with one (`_RefuseInvalidSettings`); the
    default holds here should one be changed while it runs.
    """
    try:
        seconds = Settings().restapi_timeout
    except Exception:  # noqa: BLE001
        seconds = RESTAPI_TIMEOUT
    return seconds or None


#: the routes of a point request, which name no stations and have no ndjson (GH-3590)
_POINT_ROUTES = ("interpolate", "summarize")


def is_point_route(path: str) -> bool:
    """Tell whether a request path is that of `interpolate` or `summarize`, under `/api` or `/api/v1`."""
    return path.rstrip("/").rsplit("/", 1)[-1] in _POINT_ROUTES


def timeout_detail(seconds: float, *, tool: bool = False, point: bool = False) -> str:
    """Word the 504 of a request that took longer than the timeout.

    An MCP tool's answer is one body whatever its format, so it is not told to stream (GH-3464). `interpolate` and
    `summarize` (`point`) name no stations and have no ndjson, and their csv is not streamed: they are told a shorter
    window or fewer parameters, over REST and through a tool (GH-3590).
    """
    if point:
        advice = "a shorter `timestamp` window or fewer `parameters`"
    elif tool:
        advice = "a shorter `timestamp` window, fewer stations or parameters"
    else:
        advice = "a shorter `timestamp` window, fewer stations or parameters, or format=ndjson or csv for a long answer"
    return (
        f"The server did not answer within its request timeout of {seconds:g} seconds. Narrow the request: {advice}. "
        "What the server had already fetched is cached, so the same request may succeed when it is made again."
    )


def busy_detail(maximum: int) -> str:
    """Word the 503 of a request past the cap on requests served at once."""
    return (
        f"The server is working on {maximum} requests, as many as it allows at once. This one was not started: "
        "retry it after the time `Retry-After` gives."
    )


def host_detail(host: str | None) -> str:
    """Word the 400 of a request whose `Host` is not allowed, without repeating what the client sent."""
    what = "has no Host header" if host is None else "names a host this server does not answer to"
    return (
        f"The request {what}. This server answers to the hosts it was configured with "
        "(WD_RESTAPI_ALLOWED_HOSTS); reach it by one of those names."
    )


def origin_detail() -> str:
    """Word the 400 of a request to the MCP endpoint whose `Origin` is not allowed."""
    return (
        "The Origin of the request is not a host this server answers to (WD_RESTAPI_ALLOWED_HOSTS), so a page of "
        "that origin cannot use the MCP endpoint."
    )


class _Serving:
    """The settings a request is served under, read once for it."""

    __slots__ = ("allowed_hosts", "max_concurrent", "timeout")

    def __init__(self) -> None:
        try:
            settings = Settings()
            self.timeout: float | None = settings.restapi_timeout or None
            self.max_concurrent: int = settings.restapi_max_concurrent
            self.allowed_hosts: tuple[str, ...] = settings.restapi_allowed_hosts
        except Exception:  # noqa: BLE001
            # the server refuses to start with malformed settings; the defaults hold should one change while it runs
            self.timeout = RESTAPI_TIMEOUT or None
            self.max_concurrent = RESTAPI_MAX_CONCURRENT
            self.allowed_hosts = ()

    @classmethod
    def unrestricted(cls) -> _Serving:
        """Give the settings of a route that is held to none: no host check, no cap, no timeout."""
        serving = cls.__new__(cls)
        serving.timeout, serving.max_concurrent, serving.allowed_hosts = None, 0, ()
        return serving


class _Exchange:
    """One request and its answer: what the app is given to read and send with, and whether the client was answered.

    After a timeout the client has its 504 and is gone, but the request goes on in its thread: what it still receives
    is a disconnect, and what it still sends nobody reads.
    """

    def __init__(
        self, scope: Scope, receive: Receive, send: Send, request_id: str, deprecations: list[Deprecation]
    ) -> None:
        self.scope = scope
        self.request_id = request_id
        self.client_receive = receive
        self.client_send = send
        self.deprecations = deprecations
        #: set when the response begins
        self.started = asyncio.Event()
        #: whether the client was answered with the timeout's 504
        self.dropped = False
        #: set when the answer is gone, for the work of the request to end (`util.cancellation`)
        self.cancellation = Cancellation()

    async def send(self, message: Message) -> None:
        """Send to the client, with the request id and the deprecation headers, unless it was answered already."""
        if message["type"] == "http.response.start":
            self.started.set()
            if not self.dropped:
                _add_headers(message, self.request_id, deprecation_headers(self.deprecations))
        if not self.dropped:
            await self.client_send(message)

    async def receive(self) -> Message:
        """Receive from the client, or a disconnect where it was answered and has nothing more to say."""
        return {"type": "http.disconnect"} if self.dropped else await self.client_receive()


class RequestContextMiddleware:
    """Give each request an id, check its host, hold it to the cap and the timeout, see the module docstring."""

    def __init__(self, app: ASGIApp) -> None:
        """Wrap `app`."""
        self.app = app
        #: the requests under `/api` in progress, those whose answer was dropped after the timeout included
        self.in_flight = 0
        #: the requests that went on after their timeout, kept so that the loop does not drop them while they run
        self._abandoned: set[asyncio.Task[None]] = set()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Serve a request: id, host check, cap, timeout and the headers of what it used that is deprecated."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = Headers(scope=scope)
        request_id = request_id_from(headers.get(REQUEST_ID_HEADER))
        scope.setdefault("state", {})["request_id"] = request_id
        set_request_id(request_id)
        # a probe addresses the server by an address or a service name of its own, and its route reads no setting the
        # request is held to: it is let through
        serving = _Serving() if scope["path"] not in _PROBE_PATHS else _Serving.unrestricted()
        if refusal := self._refuse_host(scope, headers, serving.allowed_hosts):
            await refusal(scope, receive, send)
            return
        deprecations = begin_deprecations()
        counted = scope["path"].startswith(_TIMED_PREFIX)
        cap = serving.max_concurrent if counted else 0
        if cap and self.in_flight >= cap:
            log.warning(f"Request {request_id} to {scope['path']} refused: {cap} requests are being served.")
            response = problem_response(scope, 503, busy_detail(cap), ProblemKind.SERVER_BUSY)
            await response(scope, receive, send)
            return
        exchange = _Exchange(scope, receive, send, request_id, deprecations)
        if not counted:
            await self.app(scope, exchange.receive, exchange.send)
            return
        self.in_flight += 1
        await self._serve_within(exchange, serving.timeout)

    async def _serve_within(self, exchange: _Exchange, seconds: float | None) -> None:
        """Serve a request of the API within the timeout (None: for ever), and answer a 504 when the timeout is over.

        The app runs as a task of its own, so that the timeout can answer without cancelling it: a handler in a thread
        cannot be cancelled, and the place of the request is its to give back when it is done. Without a timeout it is
        a task of its own all the same: a cancellation of the request that anyio makes (an MCP client that gave up) is
        not delivered to a handler that awaits its thread until the thread is done, so the work is told to stop from
        here, where it is heard at once.
        """
        from wetterdienst.ui.mcp import is_tool_request  # noqa: PLC0415

        scope = exchange.scope
        # the task copies the context it is made in: the work of the request, in the threads it starts, sees the
        # cancellation of this request and of no other
        with cancellable(exchange.cancellation):
            task = asyncio.ensure_future(self._run_app(exchange))
        waiter = asyncio.ensure_future(exchange.started.wait())
        task.add_done_callback(lambda finished: self._finished(finished, exchange.request_id, scope["path"]))
        try:
            await asyncio.wait({task, waiter}, timeout=seconds, return_when=asyncio.FIRST_COMPLETED)
            if seconds is not None and not task.done() and not exchange.started.is_set():
                # the timeout is over: the answer below is no response to hold to it
                exchange.dropped = True
                exchange.cancellation.set("timeout")
                self._abandoned.add(task)
                log.warning(f"Request {exchange.request_id} to {scope['path']} timed out after {seconds:g} seconds.")
                detail = timeout_detail(seconds, tool=is_tool_request(scope), point=is_point_route(scope["path"]))
                response = problem_response(scope, 504, detail, ProblemKind.REQUEST_TIMEOUT)
                await response(scope, exchange.client_receive, exchange.client_send)
                return
            # the response has begun: what is left is a stream's, which times its own chunks
            await task
        except asyncio.CancelledError:
            task.cancel()
            exchange.cancellation.set("cancelled")
            raise
        finally:
            waiter.cancel()

    async def _run_app(self, exchange: _Exchange) -> None:
        """Run the app for a request of the API; the end of its work, when its answer was gone, is no failure."""
        try:
            await self.app(exchange.scope, exchange.receive, exchange.send)
        except WorkAbandoned as gone:
            if not exchange.cancellation.is_set():
                # nobody ended this work: it is a defect, not the end of an answer that is gone
                raise
            # the exception crossed the worker future of the thread pool, and its traceback holds the frames of the
            # walk, which hold what it had read: a cycle that only a full collection frees, for every request that
            # timed out. Nothing reads the traceback, so it is cut here, and the context with it
            gone.__traceback__ = None
            gone.__context__ = None
            # the answer was given (the 504) or the client has gone: nothing is left to say, and it is no error
            log.info(
                f"Request {exchange.request_id} to {exchange.scope['path']} stopped its work: "
                f"{exchange.cancellation.reason}."
            )

    def _finished(self, task: asyncio.Task[None], request_id: str, path: str) -> None:
        """Give the slot back when the request is done, and say why one that nobody was waiting for failed."""
        self.in_flight -= 1
        abandoned = task in self._abandoned
        self._abandoned.discard(task)
        if task.cancelled():
            return
        error = task.exception()
        if abandoned and error is not None:
            log.warning(f"Request {request_id} to {path} failed after its timeout: {type(error).__name__}.")

    @staticmethod
    def _refuse_host(scope: Scope, headers: Headers, allowed: tuple[str, ...]) -> JSONResponse | None:
        """Answer a request whose `Host` is not allowed, or an MCP request whose `Origin` is not, with a 400."""
        from wetterdienst.ui.mcp import is_tool_request  # noqa: PLC0415

        # a tool's request to the REST app is made in process, with a Host of its own, and no client can mark one
        if not allowed or is_tool_request(scope):
            return None
        host = host_of_header(headers.get("host"))
        if not is_allowed(host, allowed):
            return problem_response(scope, 400, host_detail(host), ProblemKind.HOST_NOT_ALLOWED)
        path = scope["path"]
        origin = headers.get("origin")
        on_mcp = path == _MCP_PATH or path.startswith(f"{_MCP_PATH}/")
        if origin is not None and on_mcp and not is_allowed(host_of_origin(origin), allowed):
            return problem_response(scope, 400, origin_detail(), ProblemKind.ORIGIN_NOT_ALLOWED)
        return None


def _add_headers(message: Message, request_id: str, deprecation: dict[str, str]) -> None:
    """Add the request id, `nosniff` and the deprecation headers to the start of a response, keeping those it has."""
    headers = MutableHeaders(scope=message)
    if CONTENT_TYPE_OPTIONS_HEADER not in headers:
        headers[CONTENT_TYPE_OPTIONS_HEADER] = NOSNIFF
    if REQUEST_ID_HEADER not in headers:
        headers[REQUEST_ID_HEADER] = request_id
    for name, value in deprecation.items():
        if name == "Link":
            # beside the licence's, not instead of it
            headers.append(name, value)
        else:
            headers[name] = value
