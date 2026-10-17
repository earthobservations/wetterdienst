# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What the REST API does for every request: the request id, the request timeout and the deprecation headers (GH-3065).

- **`X-Request-ID`** is sent with every response: the client's own where it sent a plain one, else made here.
  The problem of an error carries it as `instance` and `request_id` (`ui.problems`).
- **The timeout** (`WD_RESTAPI_TIMEOUT`, 60 seconds by default, 0 for none) holds for the routes under `/api`
  until the response begins: a request that has not been answered by then is a 504 problem of the kind
  `request-timeout`, with `Retry-After`. The work of a handler that runs in a thread of the pool cannot be
  cancelled, so it goes on until it is done and its downloads are cached for the retry. Once the response has begun,
  the middleware leaves it alone: a streamed answer holds the timeout between its chunks itself (`ui.streaming`).
- **`Deprecation`, `Sunset` and `Link`** are sent for what the request used and the handlers marked deprecated
  (`ui.deprecation`).
"""

from __future__ import annotations

import asyncio
import logging
from typing import TYPE_CHECKING

from starlette.datastructures import Headers, MutableHeaders

from wetterdienst.settings import RESTAPI_TIMEOUT, Settings
from wetterdienst.ui.deprecation import begin_deprecations, deprecation_headers
from wetterdienst.ui.problems import (
    REQUEST_ID_HEADER,
    ProblemKind,
    problem_response,
    request_id_from,
    set_request_id,
)

if TYPE_CHECKING:
    from starlette.types import ASGIApp, Message, Receive, Scope, Send

log = logging.getLogger(__name__)

#: the routes the timeout holds for: the API, not the index, the health check or the MCP transport
_TIMED_PREFIX = "/api/"


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


def timeout_detail(seconds: float) -> str:
    """Word the 504 of a request that took longer than the timeout."""
    return (
        f"The server did not answer within its request timeout of {seconds:g} seconds. Narrow the request: a shorter "
        "`timestamp` window, fewer stations or parameters, or format=ndjson or csv for a long answer. What the "
        "server had already fetched is cached, so the same request may succeed when it is made again."
    )


class RequestContextMiddleware:
    """Give each request an id, a timeout and the deprecation headers of what it used, see the module docstring."""

    def __init__(self, app: ASGIApp) -> None:
        """Wrap `app`."""
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        """Serve a request with an id, within the timeout, and with the headers of what it used that is deprecated."""
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        request_id = request_id_from(Headers(scope=scope).get(REQUEST_ID_HEADER))
        scope.setdefault("state", {})["request_id"] = request_id
        set_request_id(request_id)
        deprecations = begin_deprecations()
        seconds = request_timeout() if scope["path"].startswith(_TIMED_PREFIX) else None
        started = False
        timeout: asyncio.Timeout | None = None

        async def send_(message: Message) -> None:
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                if timeout is not None:
                    # the response has begun: what is left is a stream's, which times its own chunks
                    timeout.reschedule(None)
                _add_headers(message, request_id, deprecation_headers(deprecations))
            await send(message)

        if seconds is None:
            await self.app(scope, receive, send_)
            return
        limiter = timeout = asyncio.timeout(seconds)
        try:
            async with limiter:
                await self.app(scope, receive, send_)
        except TimeoutError:
            if started or not limiter.expired():
                raise
            # the timeout is over: the answer below is no response to hold to it
            timeout = None
            log.warning(f"Request {request_id} to {scope['path']} timed out after {seconds:g} seconds.")
            response = problem_response(scope, 504, timeout_detail(seconds), ProblemKind.REQUEST_TIMEOUT)
            await response(scope, receive, send_)


def _add_headers(message: Message, request_id: str, deprecation: dict[str, str]) -> None:
    """Add the request id and the deprecation headers to the start of a response, keeping a request id it has."""
    headers = MutableHeaders(scope=message)
    if REQUEST_ID_HEADER not in headers:
        headers[REQUEST_ID_HEADER] = request_id
    for name, value in deprecation.items():
        if name == "Link":
            # beside the licence's, not instead of it
            headers.append(name, value)
        else:
            headers[name] = value
