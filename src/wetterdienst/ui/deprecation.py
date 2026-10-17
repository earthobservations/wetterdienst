# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Mark an endpoint or a parameter of the REST API deprecated, and tell the caller who uses it (GH-3065).

The policy of the API (`docs/usage/restapi.md`): what is deprecated keeps working for at least two minor
releases, is `deprecated` in the OpenAPI document, and every response to a request that uses it carries
`Deprecation` (RFC 9745: the date it was deprecated, `@<unix time>`) and, where a date is set for its
removal, `Sunset` (RFC 8594), and a `Link` with `rel="deprecation"` to where the replacement is told.

An endpoint is marked where it is declared::

    @router.get("/old", **deprecated_route(Deprecation(since=dt.date(2026, 10, 5), sunset=dt.date(2027, 1, 1))))

A parameter is marked by the handler that reads it, when the request gives it: `mark_deprecated(...)`. The
headers are written by the middleware (`ui.middleware`), from what the request marked, so a handler that
returns any kind of response needs to do nothing else. Outside a request nothing is recorded.
"""

from __future__ import annotations

import datetime as dt
from contextvars import ContextVar
from dataclasses import dataclass
from email.utils import format_datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence


@dataclass(frozen=True)
class Deprecation:
    """What is told about a deprecated endpoint or parameter."""

    #: the day it was deprecated, which `Deprecation` says
    since: dt.date
    #: the day it may stop working, which `Sunset` says; None until one is decided
    sunset: dt.date | None = None
    #: where the replacement is told, sent as `Link: <url>; rel="deprecation"`
    link: str | None = None


_MARKED: ContextVar[list[Deprecation] | None] = ContextVar("wetterdienst_deprecations", default=None)


def begin_deprecations() -> list[Deprecation]:
    """Start recording what the request being served marks, and give the list the middleware reads it from."""
    marked: list[Deprecation] = []
    _MARKED.set(marked)
    return marked


def mark_deprecated(deprecation: Deprecation) -> None:
    """Record that the request being served uses something deprecated. Nothing is recorded outside a request."""
    marked = _MARKED.get()
    if marked is not None and deprecation not in marked:
        marked.append(deprecation)


def _midnight_utc(day: dt.date) -> dt.datetime:
    return dt.datetime.combine(day, dt.time(), tzinfo=dt.UTC)


def deprecation_headers(marked: Sequence[Deprecation]) -> dict[str, str]:
    """Give the headers for the deprecations a request used: the earliest dates, and a link for each.

    A response has one `Deprecation` and one `Sunset`, so of several it says the earliest: the first
    thing the caller has to deal with.
    """
    if not marked:
        return {}
    headers = {"Deprecation": f"@{int(_midnight_utc(min(d.since for d in marked)).timestamp())}"}
    sunsets = [d.sunset for d in marked if d.sunset is not None]
    if sunsets:
        headers["Sunset"] = format_datetime(_midnight_utc(min(sunsets)), usegmt=True)
    links = list(dict.fromkeys(d.link for d in marked if d.link))
    if links:
        headers["Link"] = ", ".join(f'<{link}>; rel="deprecation"' for link in links)
    return headers


def deprecated_route(deprecation: Deprecation) -> dict[str, Any]:
    """Give the keyword arguments that declare a route deprecated: `deprecated` in OpenAPI, and the headers on use.

    Spread into the route's decorator. A request to the route marks the deprecation, the middleware sends it.
    """
    from fastapi import Depends  # noqa: PLC0415

    def mark() -> None:
        mark_deprecated(deprecation)

    return {"deprecated": True, "dependencies": [Depends(mark)]}
