# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The errors of the REST API as RFC 9457 problems with a `type` of their own, and the request id they carry (GH-3065).

Every error body of the API is a problem. Its `type` names the kind of error and stays: a client
branches on it, where the `detail` is a sentence that may improve. The kinds are the table `PROBLEMS`, which the
page `docs/usage/restapi.md` lists and a test holds to it. The types are URNs, `urn:wetterdienst:problem:<kind>`,
which name a kind and are not addresses to fetch.

`instance` is the request the problem answers, `urn:wetterdienst:request:<id>`, and the id is also sent as the
`X-Request-ID` header of every response, the client's own where it sends one that is plain text, else made here.
`request_id` repeats the id as a member for a client that does not want to parse the URN.

`ProblemError` is an `HTTPException` that says the kind and the members beyond the standard ones, so that the
handlers which already raise one keep working; one that names no kind has the kind its status stands for.
"""

from __future__ import annotations

import logging
import re
import uuid
from contextvars import ContextVar
from dataclasses import dataclass
from enum import StrEnum
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

from fastapi import HTTPException
from starlette.responses import JSONResponse

if TYPE_CHECKING:
    from collections.abc import Mapping

    from starlette.exceptions import HTTPException as StarletteHTTPException
    from starlette.types import Scope

log = logging.getLogger(__name__)

#: the header a request id is sent in, and read from
REQUEST_ID_HEADER = "X-Request-ID"
#: a request id from a client that is let through: plain, short text; anything else is replaced by one made here
_REQUEST_ID = re.compile(r"[A-Za-z0-9._~-]{1,128}")
#: seconds a `Retry-After` of a 502, 503 or 504 says. A retry is worth making once the provider is back, and
#: the work of a request that timed out has gone on, so that its cache is warm: not a promise, a place to begin
RETRY_AFTER_SECONDS = 30
#: the statuses whose problem carries `Retry-After`: the request was valid and the same one can succeed later.
#: There is no 429: the server limits no rate, which is for the proxy in front of it
RETRY_AFTER_STATUSES = frozenset({502, 503, 504})

#: the id of the request being served, for the problems and the log lines of its handlers
_CURRENT_REQUEST_ID: ContextVar[str | None] = ContextVar("wetterdienst_request_id", default=None)


class ProblemKind(StrEnum):
    """The kinds of error the API answers, each the last part of a `type` URN."""

    INVALID_PARAMETERS = "invalid-parameters"
    REQUEST_REFUSED = "request-refused"
    LIMIT_EXCEEDED = "limit-exceeded"
    IMAGE_TOO_LARGE = "image-too-large"
    SQL_DISABLED = "sql-disabled"
    NOT_FOUND = "not-found"
    UNKNOWN_NETWORK = "unknown-network"
    METHOD_NOT_ALLOWED = "method-not-allowed"
    NOT_IMPLEMENTED = "not-implemented"
    DEPENDENCY_MISSING = "dependency-missing"
    CREDENTIAL_MISSING = "credential-missing"
    CREDENTIAL_REJECTED = "credential-rejected"
    NOT_CONFIGURED = "not-configured"
    UPSTREAM_FAILED = "upstream-failed"
    UPSTREAM_UNREACHABLE = "upstream-unreachable"
    UPSTREAM_TIMEOUT = "upstream-timeout"
    REQUEST_TIMEOUT = "request-timeout"
    INTERNAL_ERROR = "internal-error"


@dataclass(frozen=True)
class ProblemSpec:
    """What a kind of problem is: the status it is answered with and when."""

    status: int
    description: str


#: every kind, in the order the docs list them. The status is the one the kind is answered with
PROBLEMS: dict[ProblemKind, ProblemSpec] = {
    ProblemKind.INVALID_PARAMETERS: ProblemSpec(
        422,
        "A query parameter is unknown, malformed or invalid, or a selection that needs exactly one of several does "
        "not. `errors` has an entry for each invalid parameter.",
    ),
    ProblemKind.REQUEST_REFUSED: ProblemSpec(
        400,
        "The request is understood and cannot be served as phrased: a window that ends before it starts, a "
        "parameter the network does not have, a point out of range.",
    ),
    ProblemKind.LIMIT_EXCEEDED: ProblemSpec(
        400,
        "The request would return more than the server allows. `limit` names the limit (`stations`, `rows` or "
        "`stream_rows`), `maximum` its value and `requested` what the request comes to; `detail` says how to "
        "narrow it.",
    ),
    ProblemKind.IMAGE_TOO_LARGE: ProblemSpec(400, "A chart would be longer than 8192 px on a side."),
    ProblemKind.SQL_DISABLED: ProblemSpec(
        403, "The request carries a `sql` or `sql_values` filter and the server does not enable them."
    ),
    ProblemKind.NOT_FOUND: ProblemSpec(
        404, "What the request names does not exist: a station, a forecast run, a resolution or dataset, or a path."
    ),
    ProblemKind.UNKNOWN_NETWORK: ProblemSpec(
        404, "The provider and network are not served, or have no stations or values to request."
    ),
    ProblemKind.METHOD_NOT_ALLOWED: ProblemSpec(405, "The method is not allowed for the path."),
    ProblemKind.NOT_IMPLEMENTED: ProblemSpec(
        501, "The server does not implement what the request asks for, such as the station history of a network."
    ),
    ProblemKind.DEPENDENCY_MISSING: ProblemSpec(
        501, "The server lacks an optional package the request needs. Whoever runs it has to install it."
    ),
    ProblemKind.CREDENTIAL_MISSING: ProblemSpec(501, "The provider needs a credential and the server has none."),
    ProblemKind.CREDENTIAL_REJECTED: ProblemSpec(501, "The provider rejected the credential of the server."),
    ProblemKind.NOT_CONFIGURED: ProblemSpec(501, "The server is not configured to serve the request."),
    ProblemKind.UPSTREAM_FAILED: ProblemSpec(
        502, "The data provider failed or sent an answer the server cannot read. The request was valid; retry it."
    ),
    ProblemKind.UPSTREAM_UNREACHABLE: ProblemSpec(
        503, "The server could not reach the data provider (no connection). The request was valid; retry it."
    ),
    ProblemKind.UPSTREAM_TIMEOUT: ProblemSpec(
        504, "The data provider did not answer in time. The request was valid; retry it."
    ),
    ProblemKind.REQUEST_TIMEOUT: ProblemSpec(
        504,
        "The server did not answer within its request timeout. Narrow the request, or retry it: what the server "
        "had fetched is cached.",
    ),
    ProblemKind.INTERNAL_ERROR: ProblemSpec(500, "The server's own error, a defect. The cause is in the server log."),
}

_BY_STATUS: dict[int, ProblemKind] = {
    400: ProblemKind.REQUEST_REFUSED,
    403: ProblemKind.REQUEST_REFUSED,
    404: ProblemKind.NOT_FOUND,
    405: ProblemKind.METHOD_NOT_ALLOWED,
    422: ProblemKind.INVALID_PARAMETERS,
    500: ProblemKind.INTERNAL_ERROR,
    501: ProblemKind.NOT_IMPLEMENTED,
    502: ProblemKind.UPSTREAM_FAILED,
    503: ProblemKind.UPSTREAM_UNREACHABLE,
    504: ProblemKind.UPSTREAM_TIMEOUT,
}


def problem_type(kind: ProblemKind) -> str:
    """Give the `type` URN of a kind."""
    return f"urn:wetterdienst:problem:{kind.value}"


def default_kind(status_code: int) -> ProblemKind:
    """Give the kind a status stands for where the code that raised it names none: a 4xx refuses, a 5xx is our error."""
    if status_code in _BY_STATUS:
        return _BY_STATUS[status_code]
    return ProblemKind.REQUEST_REFUSED if status_code < 500 else ProblemKind.INTERNAL_ERROR


def status_phrase(status_code: int) -> str:
    """Give the phrase of a status, as RFC 9457 asks of the `title` of a problem."""
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Error"


class ProblemError(HTTPException):
    """An `HTTPException` that says which kind of problem it is, and the members beyond the standard ones."""

    def __init__(
        self,
        status_code: int,
        detail: str,
        kind: ProblemKind | None = None,
        *,
        extra: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> None:
        """Raise a problem of `kind` (the one `status_code` stands for if none), with `extra` as members."""
        super().__init__(status_code=status_code, detail=detail, headers=dict(headers) if headers else None)
        self.kind = kind or default_kind(status_code)
        self.extra = dict(extra or {})


def kind_of(exc: StarletteHTTPException) -> ProblemKind:
    """Give the kind of an `HTTPException`: its own where it is a `ProblemError`, else the one its status stands for."""
    return exc.kind if isinstance(exc, ProblemError) else default_kind(exc.status_code)


def new_request_id() -> str:
    """Make a request id."""
    return uuid.uuid4().hex


def request_id_from(header: str | None) -> str:
    """Take the id a client sent, if it is plain text of a sane length, else make one."""
    if header and _REQUEST_ID.fullmatch(header):
        return header
    return new_request_id()


def set_request_id(request_id: str) -> None:
    """Remember the id of the request being served, for the thread that serves it and the log."""
    _CURRENT_REQUEST_ID.set(request_id)


def current_request_id() -> str | None:
    """Give the id of the request being served, None outside one."""
    return _CURRENT_REQUEST_ID.get()


def problem_body(
    status_code: int,
    detail: str,
    kind: ProblemKind,
    request_id: str,
    *,
    errors: list[Any] | None = None,
    extra: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the body of a problem: the members of RFC 9457, `request_id`, then `errors` and the kind's own members."""
    problem: dict[str, Any] = {
        "type": problem_type(kind),
        "title": status_phrase(status_code),
        "status": status_code,
        "detail": detail,
        "instance": f"urn:wetterdienst:request:{request_id}",
        "request_id": request_id,
    }
    if errors:
        problem["errors"] = errors
    if extra:
        problem.update(extra)
    return problem


def problem_headers(status_code: int, request_id: str, headers: Mapping[str, str] | None = None) -> dict[str, str]:
    """Give the headers of a problem: those it was raised with, the request id, and `Retry-After` where it applies."""
    given = dict(headers or {})
    lowered = {name.lower() for name in given}
    if REQUEST_ID_HEADER.lower() not in lowered:
        given[REQUEST_ID_HEADER] = request_id
    if status_code in RETRY_AFTER_STATUSES and "retry-after" not in lowered:
        given["Retry-After"] = str(RETRY_AFTER_SECONDS)
    return given


#: the media type of every error body, RFC 9457
PROBLEM_MEDIA_TYPE = "application/problem+json"


def problem_response(
    scope: Scope,
    status_code: int,
    detail: str,
    kind: ProblemKind | None = None,
    *,
    errors: list[Any] | None = None,
    extra: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Answer a failure with the problem of this API, for the request whose ASGI `scope` this is.

    An MCP tool's request is answered with the text alone, as a JSON string: FastMCP puts the body of a failed call
    into the tool error as Python writes it, and a dict would read as its repr.
    """
    from wetterdienst.ui.mcp import is_tool_request  # noqa: PLC0415

    request_id = (scope.get("state") or {}).get("request_id") or current_request_id() or new_request_id()
    given = problem_headers(status_code, request_id, headers)
    if status_code >= 500:
        # the id is what ties the log to the answer a caller reports
        log.warning(f"Request {request_id} failed with a {status_code}: {(kind or default_kind(status_code)).value}.")
    if is_tool_request(scope):
        return JSONResponse(detail, status_code=status_code, headers=given)
    body = problem_body(status_code, detail, kind or default_kind(status_code), request_id, errors=errors, extra=extra)
    return JSONResponse(body, status_code=status_code, headers=given, media_type=PROBLEM_MEDIA_TYPE)
