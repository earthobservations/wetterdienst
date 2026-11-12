# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Cache headers and conditional requests for the answers that are stable (GH-3134).

Four routes say how long their answer may be reused and how to ask whether it changed: `coverage`, `providers`
and `glossary` (`CATALOGUE_CACHE_CONTROL`) and `history` (`HISTORY_CACHE_CONTROL`, where it holds rows and came with
no warning: an empty one may be a source that answered nothing for the moment). No other route does, and an error
never does: a route whose answer cannot be reasoned about carries no `Cache-Control`, `ETag` or `Last-Modified`,
so no cache keeps it.

- **`ETag`** is a weak tag (`W/"..."`) of the body of the answer, made without the one thing that differs between
  two answers to the same question: the time it was made (`retrieved_at` of the `metadata` block). Weak, because
  that is what it says: the two bodies mean the same and are not the same bytes, and a proxy that compresses an
  answer may change its bytes too. The tag covers everything else in the body, which is all there is to a request:
  its format and every option are in the query, so a request with another one is another URL with another tag,
  and none of these routes reads any other header of the request (`Accept` included), so none has a `Vary`.
  The answer is built before it is tagged: what a `304` saves is the transfer of the body, not the work of
  making it.
- **`Last-Modified`** is sent where the answer changes only with the server: `coverage`, `providers` and
  `glossary` read nothing from a provider, so they change when wetterdienst or the server's settings do, and both
  are read at start (`settings_changed_at`: the start of the process, or the change of its `.env` where that is
  later, a time that only moves forward). `history` has no such time: its source says none, so it has an `ETag` alone.
- **`304 Not Modified`** answers a `GET` whose `If-None-Match` lists the tag, or, where it has none, whose
  `If-Modified-Since` is not before `Last-Modified`, RFC 9110 13.2.2. It has no body and carries the headers that
  say how the answer is cached. It means that the copy the client holds differs from a fresh answer at most in its
  `retrieved_at`, which is when the client's copy was made: a client that wants to know it was still right now has
  the `Date` of the `304`. The `X-Wetterdienst-*` headers of the 200 are not sent again for that reason, a cache keeps
  those it has.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import threading
from dataclasses import dataclass
from email.utils import format_datetime, parsedate_to_datetime
from pathlib import Path
from typing import TYPE_CHECKING

from fastapi.responses import Response

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping

    from starlette.requests import Request

#: what the catalogue (`coverage`, `providers`, `glossary`) is sent with: it changes with a release, so a
#: client or proxy may reuse it for five minutes, which a deploy that changes it outlasts at most that long
CATALOGUE_CACHE_CONTROL = "public, max-age=300"
#: what a station's history is sent with: a source that is read at most twice a day (`CacheExpiry.METAINDEX`)
#: and changes with a new sensor or a move, so an hour on top of the server's own is no more than that
HISTORY_CACHE_CONTROL = "public, max-age=3600"

#: an entity tag in a header: the opaque tag with the quotes, without the weak prefix, which a comparison ignores
_ENTITY_TAG = re.compile(r'(?:W/)?("[^"]*")')

#: the start of this process, to the second as an HTTP date is
_STARTED = dt.datetime.now(dt.UTC).replace(microsecond=0)
_ONE_SECOND = dt.timedelta(seconds=1)


class _Epoch:
    """When the server, as the catalogue reads it, last changed: a mark that only moves forward.

    The catalogue is a function of the code and the settings. The code is the process, and the environment is fixed
    for one, but a `.env` is read by every request, so an edit reaches the answers without a restart. The mark is
    the start of the process or the change of that file, whichever is later, and it moves forward, by at least a
    second, whenever the file is not what the last request saw: edited, replaced by an older one, or gone. An older
    file or none changes what the catalogue says (`configured` of a credential) as much as a newer one does, and a
    `Last-Modified` that went back would let a client holding the earlier answer be told by `If-Modified-Since` that
    it is current.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._changed = _STARTED
        self._seen: object = None
        self._first = True

    def changed_at(self) -> dt.datetime:
        """Give the time of the last change this process has seen."""
        try:
            stat = Path(".env").stat()
        except OSError:
            seen, modified = None, None
        else:
            seen = (stat.st_mtime_ns, stat.st_size)
            modified = dt.datetime.fromtimestamp(stat.st_mtime, dt.UTC).replace(microsecond=0)
        with self._lock:
            if self._first:
                self._first = False
                self._changed = max(self._changed, modified or _STARTED)
            elif seen != self._seen:
                now = dt.datetime.now(dt.UTC).replace(microsecond=0)
                self._changed = max(self._changed + _ONE_SECOND, now, modified or _STARTED)
            self._seen = seen
            return self._changed


_EPOCH = _Epoch()


def settings_changed_at() -> dt.datetime:
    """Give the time the server, as the catalogue reads it, last changed: it started, or its `.env` changed."""
    return _EPOCH.changed_at()


def weak_etag(content: str | bytes, *, ignoring: Iterable[str] = ()) -> str:
    """Tag a body, leaving out the texts in `ignoring` (the time of the answer), as a weak entity tag."""
    data = content.encode() if isinstance(content, str) else content
    for text in ignoring:
        if text:
            data = data.replace(text.encode(), b"")
    return f'W/"{hashlib.blake2b(data, digest_size=16).hexdigest()}"'


def _matches(header: str, etag: str) -> bool:
    """Tell whether an `If-None-Match` lists a tag, compared weakly (RFC 9110 8.8.3.2), or is `*`."""
    if header.strip() == "*":
        return True
    wanted = _ENTITY_TAG.search(etag)
    return wanted is not None and any(listed == wanted.group(1) for listed in _ENTITY_TAG.findall(header))


def _not_modified_since(header: str, last_modified: dt.datetime) -> bool:
    """Tell whether an `If-Modified-Since` is no earlier than the time of the last change; a bad date is not."""
    try:
        since = parsedate_to_datetime(header)
    except (TypeError, ValueError, OverflowError):
        # an offset or a year that does not fit in a date raises the third
        return False
    if since.tzinfo is None:
        since = since.replace(tzinfo=dt.UTC)
    return last_modified <= since


@dataclass(frozen=True)
class Validators:
    """The headers an answer is cached by, and whether the request already holds that answer."""

    headers: dict[str, str]
    matched: bool

    def not_modified(self) -> Response:
        """Answer that the client's copy is still right: no body, the headers that say how it is cached."""
        return Response(status_code=304, headers=self.headers)


def validators(
    request: Request,
    content: str | bytes,
    *,
    cache_control: str,
    last_modified: dt.datetime | None = None,
    ignoring: Iterable[str] = (),
) -> Validators:
    """Work out the cache headers of an answer, and whether the request's conditions say it holds the answer.

    `ignoring` are the texts of the body that differ with the time it was made (`retrieved_at`). The conditions are
    those of a `GET` (RFC 9110 13.2.2): `If-None-Match` decides where it is sent, whatever `If-Modified-Since` says,
    and `If-Modified-Since` only where there is a `Last-Modified` to compare it with.
    """
    etag = weak_etag(content, ignoring=ignoring)
    headers = {"ETag": etag, "Cache-Control": cache_control}
    if last_modified is not None:
        headers["Last-Modified"] = format_datetime(last_modified, usegmt=True)
    if (listed := request.headers.get("if-none-match")) is not None:
        matched = _matches(listed, etag)
    elif last_modified is not None and (since := request.headers.get("if-modified-since")) is not None:
        matched = _not_modified_since(since, last_modified)
    else:
        matched = False
    return Validators(headers, matched)


def cached_json(
    request: Request,
    content: str | bytes,
    *,
    cache_control: str,
    last_modified: dt.datetime | None = None,
    ignoring: Iterable[str] = (),
    headers: Mapping[str, str] | None = None,
) -> Response:
    """Answer with JSON and its cache headers, or with the 304 where the request holds it already.

    `headers` are the headers beyond the cache's that the 200 carries; the 304 leaves them out.
    """
    checked = validators(request, content, cache_control=cache_control, last_modified=last_modified, ignoring=ignoring)
    if checked.matched:
        return checked.not_modified()
    return Response(content=content, media_type="application/json", headers={**(headers or {}), **checked.headers})
