# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Network utilities for the wetterdienst package."""

from __future__ import annotations

import asyncio
import atexit
import base64
import contextlib
import datetime as dt
import hashlib
import ipaddress
import json
import logging
import os
import re
import shutil
import sqlite3
import ssl
import tempfile
import threading
import time
import uuid
from collections.abc import AsyncIterator, Callable, Iterator, MutableMapping
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from http import HTTPStatus
from io import BytesIO
from pathlib import Path
from typing import IO, TYPE_CHECKING, Any, ClassVar, Literal, TypeVar
from urllib.parse import urljoin, urlparse, urlsplit, urlunsplit

import stamina
from aiohttp import (
    ClientConnectionError,
    ClientConnectorError,
    ClientError,
    ClientPayloadError,
    ClientResponse,
    ClientResponseError,
    ClientSSLError,
    ClientTimeout,
    TraceConfig,
    TraceRequestEndParams,
    TraceRequestRedirectParams,
    TraceRequestStartParams,
)
from aiohttp.client_reqrep import ConnectionKey
from filelock import FileLock, Timeout
from fsspec.asyn import sync, sync_wrapper
from fsspec.callbacks import DEFAULT_CALLBACK, Callback
from fsspec.exceptions import FSTimeoutError
from fsspec.implementations.cached import WholeFileCacheFileSystem
from fsspec.implementations.http import HTTPFileSystem as _HTTPFileSystem
from fsspec.utils import isfilelike

from wetterdienst.exceptions import CredentialRejectedError, DownloadError, NoInternetError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.util.datetime import parse_http_date
from wetterdienst.util.listing_cache import (
    STORE_FILENAME,
    ListingStore,
    make_private_dir,
    remove_diskcache_leftovers,
)
from wetterdienst.util.provider_hosts import clean_host, hosts_of_provider, provider_of

if TYPE_CHECKING:
    from collections.abc import Mapping
    from types import SimpleNamespace

    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

_E = TypeVar("_E", bound=BaseException)
_C = TypeVar("_C", bound=ClientConnectorError)


def _create_ssl_context(*, use_certifi: bool) -> ssl.SSLContext | None:
    """Create an SSL context optionally using certifi certificates.

    Args:
        use_certifi: If True, use certifi certificate bundle instead of system certificates.

    Returns:
        An SSL context configured with certifi certificates if requested, None otherwise.

    """
    if not use_certifi:
        return None

    import certifi  # noqa: PLC0415

    return ssl.create_default_context(cafile=certifi.where())


@dataclass
class File:
    """File object for the network utilities."""

    url: str
    """The URL of the file."""

    @property
    def filename(self) -> str:
        """The filename of the file."""
        return Path(urlparse(self.url).path).name

    """The filename of the file, if available."""
    content: BytesIO | Exception
    """The content of the file as a BytesIO object."""
    status: int
    """The status code of the file download, if available."""
    from_cache: bool = False
    """Whether the body was served from the on-disk cache rather than fetched.

    A caller that cannot use what it was given needs this to know whether asking again could
    answer differently: a cached body says nothing about what the server has now, while one that
    has just come off the wire cannot have changed in the meantime (GH-1947).
    """
    last_modified: dt.datetime | None = None
    """When the source last wrote the file, as its `Last-Modified` header says (UTC), `None` where it sent none.

    The header of the response the body in hand came from: for a file served from the cache, the one the cached copy
    came with, kept beside it (`_write_sidecar`). `None` for a copy cached before that was kept, for a header that is
    no date (`parse_http_date`) and for a failed download. Never the time of the request (GH-2567). It is the
    server's date of the file, where `cached_at` is when this library made the copy: two different times.
    """
    cached_at: float | None = None
    """When the copy the body is of was made, as `time.time()` has it, from when its download began; None where the body
    is not held in the cache (the cache is off, or the download failed). For a provider whose source dates its files, to
    tell which copy a date is of (GH-2567)."""

    def raise_if_exception(self) -> None:
        """Raise an exception if the content is not a BytesIO object.

        A failed connection -- no network, a DNS failure, a refusing host -- is raised as the
        `NoInternetError` the download stored, naming the URL, with the connection error underneath
        as its `__cause__`. It is no longer let through silently for the caller to answer with an
        empty frame, which a scheduled job cannot tell from a source with no data (GH-2640).

        Any other failure is a `DownloadError` naming the file, with the stored exception as its
        `__cause__`: a timeout's own message is empty, and a dropped connection's or a cut-short
        body's says nothing of which file it was (GH-2460).
        """
        if isinstance(self.content, NoInternetError):
            raise self.content
        if isinstance(self.content, Exception):
            raise _download_error(self.content, self.url) from self.content

    @property
    def is_no_internet_error(self) -> bool:
        """Check if the content is a NoInternetError."""
        return isinstance(self.content, NoInternetError)

    @property
    def nbytes(self) -> int:
        """Return the number of bytes in the file content, `0` when there is no body (a failed download)."""
        if isinstance(self.content, BytesIO):
            return self.content.getbuffer().nbytes
        return 0

    @property
    def is_empty(self) -> bool:
        """Check if the file has a body of zero bytes.

        A failed download has no body at all, so it is not empty: `content` is the exception and
        this is `False`. A caller that wants "failed or empty" asks for both,
        `isinstance(file.content, Exception) or file.is_empty` (GH-2563).
        """
        return isinstance(self.content, BytesIO) and self.nbytes == 0


def _without_url_secrets(url: str) -> str:
    """Give back a URL as it can be shown: with no query, no fragment and no user information.

    Either can carry a credential -- a pre-signed URL's signature, an API key, `user:password@` --
    and what this names travels to whoever asked, a remote caller of the REST API among them. Cut
    with string operations rather than parsed, so that a malformed URL cannot raise from here.
    """
    base = re.split(r"[?#]", url, maxsplit=1)[0]
    scheme, separator, rest = base.partition("://")
    if not separator:
        return base
    authority, slash, path = rest.partition("/")
    if "@" in authority:
        authority = "***@" + authority.rpartition("@")[2]
    return f"{scheme}://{authority}{slash}{path}"


#: A URL inside a text: up to the next space, quote or closing bracket, without the punctuation that ends a sentence.
_URL_IN_TEXT = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s'\"<>)\]]*[^\s'\"<>)\].,:;]")


def _without_url_secrets_in(text: str) -> str:
    """Give back a text with every URL in it as `_without_url_secrets` shows it, for a message that is logged."""
    return _URL_IN_TEXT.sub(lambda match: _without_url_secrets(match.group()), text)


def _without_query_of_response_error(error: ClientResponseError) -> None:
    """Take the query out of the URLs a `ClientResponseError` renders: those of its request and of its redirects."""
    request_info = error.request_info
    if request_info is not None:
        scrubbed = request_info._replace(
            url=request_info.url.with_query(None).with_fragment(None),
            real_url=request_info.real_url.with_query(None).with_fragment(None),
        )
        if scrubbed != request_info:
            error.request_info = scrubbed
            if error.args and error.args[0] is request_info:
                error.args = (scrubbed, *error.args[1:])
    # the responses of a redirect chain render their url and headers (`Location` among them), query included; dropped
    # as `_without_credentials` does, since the status already says that the request was redirected
    if error.history:
        error.history = ()
        if len(error.args) > 1 and error.args[1]:
            error.args = (error.args[0], (), *error.args[2:])


def _without_url_in_arg(arg: object) -> object:
    """Give back an argument of an error without the query of the URL it is or holds, if it is text or a `yarl.URL`."""
    if isinstance(arg, str):
        return _without_url_secrets_in(arg)
    with_query = getattr(arg, "with_query", None)
    if callable(with_query):
        return with_query(None).with_fragment(None)
    return arg


def _without_url_queries(error: _E) -> _E:
    """Take the query of the URL out of an error, where `str()` and `repr()` render it.

    A pre-signed URL carries its signature in the query, and the error of a download renders the URL it was
    made for: `FileNotFoundError` is the URL itself, and a `ClientResponseError` ends with `url=...`, in its
    request info as well as in the `repr` that stamina logs for a retry (GH-3341). The error is changed in
    place and handed back, as `_without_credentials` does.
    """
    if isinstance(error, ClientResponseError):
        _without_query_of_response_error(error)
        return error
    args = tuple(_without_url_in_arg(arg) for arg in error.args)
    if args != error.args:
        error.args = args
    # the errors that render an attribute instead of their args: an `OSError` its `filename`, aiohttp's invalid-URL
    # errors their `_url`, which is a string or a `yarl.URL`
    filename = getattr(error, "filename", None)
    if isinstance(filename, str):
        setattr(error, "filename", _without_url_secrets_in(filename))  # noqa: B010
    url = getattr(error, "_url", None)
    if isinstance(url, str):
        setattr(error, "_url", _without_url_secrets_in(url))  # noqa: B010
    elif hasattr(url, "with_query"):
        setattr(error, "_url", url.with_query(None).with_fragment(None))  # noqa: B010
    return error


def _download_error(error: Exception, url: str) -> DownloadError:
    """Say which file a download failed for, and why.

    The reason is built here rather than taken from the error, because the error's own message can
    hold the URL as requested, query and all: `FileNotFoundError`'s is the URL, and
    `ClientResponseError`'s ends with it. A response error is told by its status and reason phrase,
    anything else by its own message unless that is empty or holds a URL, and by the name of its
    type then.
    """
    if isinstance(error, ClientResponseError) and error.status:
        reason = f"{error.status}, message={error.message!r}"
    else:
        reason = str(error)
    if not reason or "://" in reason:
        reason = type(error).__name__
    return DownloadError(_without_url_secrets(url), reason)


def as_outage(error: Exception, url: str) -> Exception:
    """Say what a caller that reads a failed download for itself raises for it, or hand the failure back.

    For a provider that cannot go through `File.raise_if_exception` because a missing file is part
    of its protocol -- a station that does not report a parameter (a 404), a timestamp that is not
    published yet -- and answers an empty result for that, but must not answer one for a source that
    did not answer (GH-2965). The failures that are no answer are the ones `_worth_retrying` asks
    again for: a timeout, a dropped connection, a body cut short, a 5xx. They come back as the
    `DownloadError` `File.raise_if_exception` would raise, naming the file and with the failure as
    its `__cause__`. A failed connection is the `NoInternetError` it already is.

    A TLS failure -- a certificate that does not verify, a handshake that fails -- is one too, though a
    certificate is not asked again (`_worth_retrying`): the host presented what it could not be trusted with,
    which is no answer to the question, and it is the `DownloadError` that `File.raise_if_exception` raises
    for it (GH-3022). So is a redirect that was not followed (`RedirectRefusedError`, GH-3339) and a body
    refused for its size, its time or an unannounced compression (`DownloadRefusedError`, GH-3340).

    Any other failure is returned as it was, for the caller to answer as before: a 404, a 4xx such as
    a refused key or a 429 -- the source answering -- and what is no download error at all.
    """
    if isinstance(error, NoInternetError):
        return error
    refused = (ClientSSLError, ssl.SSLError, RedirectRefusedError, DownloadRefusedError)
    if _worth_retrying(error) or isinstance(error, refused):
        failure = _download_error(error, url)
        failure.__cause__ = error
        return failure
    return error


#: The statuses with which a provider says that it refuses the credential it was sent.
CREDENTIAL_REJECTED_STATUSES = frozenset({HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN})


def credential_rejected(source: str, setting: str, what: str, status: int | None = None) -> CredentialRejectedError:
    """Say that a provider refuses the credential this installation holds for it (GH-3018).

    The message names the setting to change and what it holds, never the credential: whoever runs the
    process reads it as it is, while the REST API and the MCP tools answer with a fixed sentence.

    Args:
        source: How the message calls the provider, such as ``"AEMET"``.
        setting: The name under ``WD_AUTH__`` that holds the credential, such as ``"AEMET"``.
        what: What the setting holds, such as ``"API key"``.
        status: The HTTP status of the refusal, if it came as one.

    """
    rejected = f"rejected the request with HTTP {status}" if status else "rejected the request"
    return CredentialRejectedError(f"{source} {rejected}. Check that WD_AUTH__{setting} contains a valid {what}.")


def raise_if_credential_rejected(file: File, source: str, setting: str, what: str) -> None:
    """Raise `CredentialRejectedError` for a download the provider answered with a 401 or a 403 (GH-3018).

    For a download that is sent the credential, called before `File.raise_if_exception`, which would
    raise the same answer as a `DownloadError`. A download that is not sent one, or whose address is
    pre-signed, says nothing about the credential when it is refused: that stays a download error.
    """
    if isinstance(file.content, Exception) and file.status in CREDENTIAL_REJECTED_STATUSES:
        raise credential_rejected(source, setting, what, file.status)


def _no_internet_error(url: str, error: ClientConnectorError) -> NoInternetError:
    """Say that a connection could not be made to ``url``, with the connection error underneath as its cause.

    What is stored under `__cause__` is the `OSError` aiohttp wraps (a refused connection, a failed
    name lookup), without its traceback or chain: the aiohttp error holds the connection key, which
    renders the password of a proxy named in `HTTPS_PROXY`, and its frames hold the request as
    locals (GH-2602). The URL is shown without its query and user information, which can carry a key.
    """
    cause = error.os_error.with_traceback(None)
    cause.__cause__ = None
    cause.__context__ = None
    failure = NoInternetError(f"No internet connection: could not reach {_without_url_secrets(url)} ({error})")
    failure.__cause__ = cause
    return failure


#: Second-level labels under which a country's registry hands out names directly (`gov.uk`, `data.gouv.fr`,
#: `weather.gc.ca`). Stands in for the public suffix list, which is no dependency: a host under one of them
#: belongs to the label before it, so `a.data.gouv.fr` and `b.data.gouv.fr` are one family and `x.gouv.fr` is not.
_REGISTRY_LABELS = frozenset(
    {"ac", "co", "com", "edu", "gc", "go", "gob", "gouv", "gov", "gv", "ne", "net", "or", "org"}
)


def _is_ip_address(host: str) -> bool:
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


#: Domains whose names belong to many unrelated tenants, among them names that resolve to a private address (a load
#: balancer or an endpoint of a virtual network): a host under one is its own family.
_SHARED_DOMAINS = ("amazonaws.com", "ovh.net")


def _host_family(host: str) -> str:
    """Give the part of a host name that its owner registered: `data.gouv.fr` for `static.data.gouv.fr`.

    An address, a name with a single label (`localhost`, a name on the internal network) and a name under a shared
    domain (`_SHARED_DOMAINS`) is its own family: nothing else is related to it.
    """
    host = clean_host(host)
    labels = host.split(".")
    if _is_ip_address(host) or len(labels) < 2 or host.endswith(tuple(f".{domain}" for domain in _SHARED_DOMAINS)):
        return host
    keep = 3 if len(labels) >= 3 and len(labels[-1]) == 2 and labels[-2] in _REGISTRY_LABELS else 2
    return ".".join(labels[-keep:])


def _same_family(host: str, other: str) -> bool:
    """Tell whether two hosts are one and the same, or two names under one registered domain."""
    return clean_host(host) == clean_host(other) or _host_family(host) == _host_family(other)


_DEFAULT_PORTS = {"http": 80, "https": 443}


def _in_scope(host: str, start: str | None) -> bool:
    """Tell whether a request that starts at a host may be led to another host (a link or a redirect).

    Where the start is a host of a provider (`PROVIDER_HOSTS`), the hosts of that provider are the bound, and no
    other host is in it, a sibling name under the same domain included. Any other start, a host the library does not
    know (a test server, an address a caller fetches by hand), is held to its registered domain.
    """
    hosts = hosts_of_provider(start)
    if hosts is None:
        return _same_family(host, start or "")
    return clean_host(host) in hosts


def _bound_of(start: str | None) -> str:
    """Name what a request that starts at a host is held to, for a refusal: `the hosts of nws`, `the domain of x.fr`."""
    provider = provider_of(start)
    return f"the domain of {_host_family(start or '')}" if provider is None else f"the hosts of {provider}"


def _link_refused(link: str, why: str) -> DownloadError:
    return DownloadError(_without_url_secrets(link), f"the link was not fetched, as it {why}")


def fetchable_link(link: str, base: str) -> str:
    """Give the address to fetch for a link that an answer of the provider names, or refuse it.

    A provider that follows a link out of its upstream's answer (the next page of a result, the address of the
    data, an asset) fetches whatever the answer says, unless it asks here first. A link is fetched when it names a
    host of the provider that `base`, the address the provider asked, is one of (`PROVIDER_HOSTS`: the API and the
    store its files are served from), on the port of `base` or the default one. A `base` that no provider lists
    allows the registered domain of its host.

    Anything else is refused: another scheme than http(s), user information, another port, an address or a name on
    an internal network where `base` is not one, and every other host. A link to `http` under an `https` base is
    returned as `https`, which is how the upstream's own links are written where it terminates TLS elsewhere.

    Args:
        link: The address the answer names.
        base: The address of the request that the answer came for.

    Returns:
        The address to fetch.

    Raises:
        DownloadError: If the link is refused, naming it without its query and the provider whose hosts it is not
            one of. It is the failure of the file the link stands for, as the provider raises any other, and is
            never retried.

    """
    try:
        parts = urlsplit(link)
        base_parts = urlsplit(base)
        host = clean_host(parts.hostname)
        port = parts.port
    except ValueError:
        raise _link_refused(link, "does not read as an address") from None
    if parts.scheme not in {"http", "https"} or not host:
        raise _link_refused(link, "is no http(s) address")
    if "@" in parts.netloc:
        raise _link_refused(link, "carries user information")
    if not _in_scope(host, base_parts.hostname):
        raise _link_refused(link, f"leads to {host}, which is outside {_bound_of(base_parts.hostname)}")
    scheme = "https" if base_parts.scheme == "https" else parts.scheme
    on_default = port in {None, _DEFAULT_PORTS[scheme]} and base_parts.port in {
        None,
        _DEFAULT_PORTS[base_parts.scheme],
    }
    if not (on_default or port == base_parts.port):
        raise _link_refused(link, "names another port")
    return link if scheme == parts.scheme else urlunsplit(parts._replace(scheme=scheme))


class RedirectRefusedError(ClientError):
    """A redirect that was not followed, as it left the hosts of the request's provider or stepped down to http."""


class DownloadRefusedError(ClientError):
    """A body that was not taken: too large, too slow to arrive, or compressed while its name says it is not.

    Stored by a download as the failure it met, and raised as a `DownloadError` naming the file when the
    caller asks (`File.raise_if_exception`), with this as its `__cause__`. It is no connection fault, so
    it is not asked for again.
    """


#: The most a single download may be: the body as the client sees it, after a `Content-Encoding` is
#: undone. About three times the largest file the providers serve, which is a month of five-minute
#: RADOLAN grids at 0.7 GB; a KMZ of MOSMIX-L is 84 MB. A module constant rather than a setting, as
#: nothing has asked to move it.
MAX_DOWNLOAD_BYTES = 2 * 1024**3

#: The longest a single download may take in all, from the request to the last byte. A number given
#: as a client timeout bounds each silence and not the whole (GH-2258), so a server that sends a byte
#: every few seconds would otherwise keep a download, and the slot of a REST request that waits for
#: it, for as long as it likes. An hour moves the largest file above at about 0.2 MB/s.
MAX_DOWNLOAD_SECONDS = 3600

_READ_CHUNK = 1024 * 1024


def _megabytes(size: float) -> str:
    return f"{size / 1024**2:,.4g} MB"


def _too_large(limit: int) -> DownloadRefusedError:
    return DownloadRefusedError(f"the file is larger than the {_megabytes(limit)} a download is held to")


@contextlib.asynccontextmanager
async def _within_time(seconds: float) -> AsyncIterator[None]:
    """Hold what runs inside to ``seconds`` in all, and say that it was this and not a timeout of the client."""
    try:
        async with asyncio.timeout(seconds) as scope:
            yield
    except TimeoutError:
        # the timeouts of the client (a silence on the socket) are `TimeoutError`s too, and are not this
        if not scope.expired():
            raise
        msg = f"the file took longer than the {seconds:,.0f} seconds a download is held to"
        raise DownloadRefusedError(msg) from None


async def _read_capped(response: ClientResponse, max_bytes: int) -> bytes:
    """Read the body of a response, refusing it past ``max_bytes``: at once if it says so, as it arrives if not."""
    if response.content_length is not None and response.content_length > max_bytes:
        raise _too_large(max_bytes)
    chunks = []
    received = 0
    while chunk := await response.content.read(_READ_CHUNK):
        received += len(chunk)
        if received > max_bytes:
            raise _too_large(max_bytes)
        chunks.append(chunk)
    return b"".join(chunks)


class _CappedWriter:
    """A file that refuses what is written past ``max_bytes``, for fsspec to stream a body into."""

    def __init__(self, target: IO[bytes], max_bytes: int) -> None:
        self._target = target
        self._max_bytes = max_bytes
        self._written = 0

    def write(self, data: bytes) -> int:
        self._written += len(data)
        if self._written > self._max_bytes:
            raise _too_large(self._max_bytes)
        return self._target.write(data)

    def __getattr__(self, name: str) -> object:
        # `read`, `close` and `tell` are what makes fsspec take this for a file
        return getattr(self._target, name)


class _SizeGuard(Callback):
    """A progress callback that refuses a body that says in its headers that it is larger than ``max_bytes``."""

    def __init__(self, max_bytes: int) -> None:
        super().__init__()
        self._max_bytes = max_bytes

    def set_size(self, size: int | None) -> None:
        if size is not None and size > self._max_bytes:
            raise _too_large(self._max_bytes)
        super().set_size(size)


#: What a body starts with when polars decompresses it on its own, whatever the file is called: gzip, zstd and
#: the four zlib headers.
_SELF_UNPACKING_MAGIC = (b"\x1f\x8b", b"\x28\xb5\x2f\xfd", b"\x78\x01", b"\x78\x5e", b"\x78\x9c", b"\x78\xda")
_ANNOUNCED_COMPRESSION = (".gz", ".tgz", ".z", ".zz", ".zst")


def _refuse_unannounced_compression(url: str, payload: bytes) -> None:
    """Refuse a body that is compressed while the name of the file does not say so.

    ``polars.read_csv`` unpacks a gzip, zlib or zstd body by itself, without a ceiling, so a file
    that is read as a table and arrives compressed would be inflated by whatever reads it. The
    providers that serve compressed files say so in their names and unpack them through
    `wetterdienst.util.archive`, which bounds what comes out.
    """
    if payload.startswith(_SELF_UNPACKING_MAGIC) and not urlparse(url).path.lower().endswith(_ANNOUNCED_COMPRESSION):
        msg = "the file is compressed, which a file of its name is not"
        raise DownloadRefusedError(msg)


#: What is forwarded to the host a redirect leads to, besides what `_CREDENTIAL_HEADERS` names: aiohttp itself drops
#: only `Authorization`, `Cookie` and `Proxy-Authorization`, and so sends a key in a header of any other name (AEMET's
#: `api_key`) to the next host.
_REDIRECT_DROPPED_HEADERS = frozenset({"cookie"})


#: The hosts at which a provider's platform says that it is down for maintenance, each with the service it
#: stands for. data.gouv.fr answers every request of a maintenance window, the API and the static host
#: included, with a redirect to `http://sorry.data.gouv.fr`, which answers one to https and then a 503 (GH-3400).
#: Not a host of any provider, so the check is made before the bound of the request.
_MAINTENANCE_HOSTS = {"sorry.data.gouv.fr": "data.gouv.fr"}


class UpstreamMaintenanceError(RedirectRefusedError):
    """A redirect to the page that a provider's platform shows while it is down for maintenance.

    A `DownloadError` raised from it is an outage of the provider and no fault of the request: a REST
    answer maps it as any failed download, and the test suite skips on it (`skip_if_upstream_unavailable`).
    """


def _check_redirect(response: ClientResponse, headers: MutableMapping[str, str], first_url: str) -> None:
    """Refuse a redirect that leaves the hosts of the first request's provider or steps down to http.

    Called for each redirect, with the headers aiohttp is about to send next. Where the origin changes (host, port
    or scheme), no credential header goes with it, whatever its name (`_CREDENTIAL_HEADERS`). The hosts of the provider
    that the first request's host is one of (`PROVIDER_HOSTS`) are the bound, those of its registered domain where no
    provider lists the host (`_in_scope`): a redirect that ends elsewhere is refused, so an upstream cannot lead the
    client to a host of its choosing (an internal one among them). A step from https to http is refused for every
    session, as it would send the request in clear. A refused hop is named by its host, never by its query.

    A redirect to the maintenance page of a platform (`_MAINTENANCE_HOSTS`) from a request that started at a host of
    that platform is no hop to refuse but an outage, and is told before the bound and the scheme are, so that it is
    reported as one whichever way it is asked. From a request that started anywhere else it is a redirect like any
    other: an upstream that sends a client there is not the platform being down.
    """
    location = response.headers.get("Location") or response.headers.get("URI")
    if not location:
        return
    current = str(response.url)
    try:
        target = urlsplit(urljoin(current, location))
        here = urlsplit(current)
        target_host = target.hostname
        target_port = target.port
    except ValueError:
        return  # aiohttp refuses what is no address
    if target.scheme not in {"http", "https"} or not target_host:
        return  # aiohttp refuses what is no http(s) address
    start = urlsplit(first_url).hostname
    maintained = _MAINTENANCE_HOSTS.get(clean_host(target_host))
    if maintained and _host_family(start or "") == _host_family(maintained):
        msg = f"{maintained} is in maintenance (the request was redirected to {clean_host(target_host)})"
        raise UpstreamMaintenanceError(msg)
    if not _in_scope(target_host, start):
        msg = f"a redirect to another host ({clean_host(target_host)}) outside {_bound_of(start)} was not followed"
        raise RedirectRefusedError(msg)
    if here.scheme == "https" and target.scheme == "http":
        msg = f"a redirect from https to http ({clean_host(target_host)}) was not followed"
        raise RedirectRefusedError(msg)
    origin = (target.scheme, clean_host(target_host), target_port or _DEFAULT_PORTS[target.scheme])
    if origin != (here.scheme, clean_host(here.hostname), here.port or _DEFAULT_PORTS[here.scheme]):
        for name in [name for name in headers if str(name).lower() in _CREDENTIAL_HEADERS | _REDIRECT_DROPPED_HEADERS]:
            if name in headers:  # a header that is there twice goes with its first removal
                del headers[name]


#: The key of the `Last-Modified` header in the dict a request is given to say what it saw (`trace_request_ctx`)
_LAST_MODIFIED = "last-modified"
_DATE = "date"


#: How many dates a filesystem keeps at most: `download_file` takes its own at once, so what stays are those of the
#: files another reader opened (the KML of a forecast) and nobody takes
_MAX_REMEMBERED_DATES = 256


def _remember_last_modified(registry: dict[str, dt.datetime | None], url: str, value: dt.datetime | None) -> None:
    """Note the date of a file just read, for `download_file` to take, without growing for readers that do not."""
    if len(registry) >= _MAX_REMEMBERED_DATES:
        registry.clear()
    registry[url] = value


def _last_modified_of(seen: dict[str, str | None]) -> dt.datetime | None:
    """Read the date a response says its file was written, `None` where it says none that can be taken.

    A server that sends the time it makes its answer as the `Last-Modified` of it (SMHI and FMI do) says when it was
    asked, not when the file was written, and a cache may hand such a date out after the `Date` it was made at. A
    `Last-Modified` that is the `Date` of the same response or later is no file's: a server that has no time for a file
    that is not there yet sends its own (RFC 9110 8.8.2.1), as FMI does, with the two equal to the second. A file
    written in the very second it is asked for is lost with them, which costs a date and misleads nobody.
    """
    written = parse_http_date(seen.get(_LAST_MODIFIED))
    answered = parse_http_date(seen.get(_DATE))
    if written is not None and answered is not None and written >= answered:
        return None
    return written


def _redirect_guard() -> TraceConfig:
    """Build the trace of a session that applies `_check_redirect` to every redirect it follows.

    It also hands the `Last-Modified` of the response that ends a request to the caller that passed a dict as
    `trace_request_ctx`, which is how a download learns the date of the file it fetched with no request of its own.
    """
    trace = TraceConfig()

    async def remember_first_url(_session: object, context: SimpleNamespace, params: TraceRequestStartParams) -> None:
        context.first_url = str(params.url)

    async def check_redirect(_session: object, context: SimpleNamespace, params: TraceRequestRedirectParams) -> None:
        _check_redirect(params.response, params.headers, context.first_url)

    async def note_last_modified(_session: object, context: SimpleNamespace, params: TraceRequestEndParams) -> None:
        # the response that ends the request, after any redirects: handed to whoever asked, if it asked
        seen = getattr(context, "trace_request_ctx", None)
        if isinstance(seen, dict):
            seen[_LAST_MODIFIED] = params.response.headers.get("Last-Modified")
            seen[_DATE] = params.response.headers.get("Date")

    trace.on_request_start.append(remember_first_url)
    trace.on_request_redirect.append(check_redirect)
    trace.on_request_end.append(note_last_modified)
    return trace


#: The directories that could not be used as a cache, each with the temporary one standing in for it.
#: Process-wide and held under a lock: a `FileDirCache` is built per listing and a caching filesystem
#: per thread, and neither may make a directory of its own or warn again for the same fault.
_cache_dir_fallbacks: dict[Path, Path] = {}
_cache_dir_fallback_lock = threading.Lock()

#: What failing to open or create a cache directory raises: `PermissionError` and the other
#: `OSError`s from the file system, and the `sqlite3.OperationalError` the listings store raises on
#: opening a database it cannot write ("attempt to write a readonly database").
_CACHE_DIR_ERRORS = (OSError, sqlite3.OperationalError)


def _effective_cache_dir(cache_dir: Path) -> Path:
    """Return the directory a cache is kept in: `cache_dir`, or its stand-in once it failed.

    A directory that failed is not tried again for the rest of the process.
    """
    with _cache_dir_fallback_lock:
        return _cache_dir_fallbacks.get(Path(cache_dir), Path(cache_dir))


def _fallback_cache_dir(cache_dir: Path, error: BaseException) -> Path:
    """Return the temporary directory that stands in for `cache_dir`, which `error` says is unusable.

    One per process and unusable directory, however many caches are built, and the one warning
    names the directory, the reason and what to do about it. Removed when the process that made it
    exits; a forked child leaves it alone. The request goes on; the cache is just not kept across
    runs.

    Raises:
        BaseException: `error` itself, re-raised if there is no temporary directory to make either.

    """
    from wetterdienst.settings import _remove_unless_forked  # noqa: PLC0415

    cache_dir = Path(cache_dir)
    with _cache_dir_fallback_lock:
        fallback = _cache_dir_fallbacks.get(cache_dir)
        if fallback is None:
            try:
                fallback = Path(tempfile.mkdtemp(prefix="wetterdienst-cache-"))
            except OSError:
                raise error from None
            atexit.register(_remove_unless_forked, fallback, os.getpid())
            _cache_dir_fallbacks[cache_dir] = fallback
            log.warning(
                f"the cache directory {cache_dir} cannot be used ({type(error).__name__}: {error}), "
                f"so this process caches in {fallback} instead, which is removed when it exits. "
                f"Make {cache_dir} writable for the user running wetterdienst (in the Docker image "
                "that is uid 10001: `chown -R 10001:10001` on the volume, or remove the volume), "
                "or set WD_CACHE_DIR to a writable directory, or WD_CACHE_DISABLE=true"
            )
        return fallback


# Directory names the listings cache used to create under the cache dir but never writes to any
# more. ``False`` came from ``CacheExpiry.INFINITE`` and from a disabled cache, ``0.0`` from the
# download-side filesystem registration, ``0.01`` from ``CacheExpiry.NO_CACHE``. In every one of
# those cases ``use_listings_cache`` was False, so the directory was created and then never written
# to. They are removed on the next run once nothing is left in them.
_LEGACY_LISTINGS_CACHE_DIR_NAMES = frozenset({"False", "0.0", "0.01"})
#: The name of a TTL's directory under the cache root, as ``FileDirCache`` has made it since the TTL
#: became a float: ``infinite``, ``False``, or ``str(float)`` (``300.0``, ``1e-05``). Not a bare integer,
#: which another application's directory can be called.
_LISTINGS_CACHE_DIR = re.compile(r"^(?:infinite|False|\d+\.\d+(?:e[+-]?\d+)?|\d+e[+-]?\d+)$")
_legacy_cleanup_lock = threading.Lock()
_legacy_cleanup_done: set[Path] = set()


def _remove_legacy_listings_cache_dirs(cache_root: Path, keep: str) -> None:
    """Remove what earlier versions left in the listings cache root, which this version never reads.

    * The files of ``diskcache`` (``cache.db`` and the ``.val`` files beside it, GH-3326), in every
      TTL's directory: the listings are now kept in a file of another name and format, and the
      old ones were pickles that are never opened again. Removed only once nothing has written to
      them for an hour, since an older wetterdienst may run beside this one on the same directory.
    * The empty directories ``False``, ``0.0`` and ``0.01`` that earlier versions made and never wrote to.

    Runs once per cache root per process, and is best-effort throughout: a cache directory that
    cannot be tidied is not a reason to fail the request that happened to trigger the sweep.

    Args:
        cache_root: Directory the per-TTL listings cache folders live in.
        keep: Name of the folder the caller is about to use, never removed.

    """
    with _legacy_cleanup_lock:
        if cache_root in _legacy_cleanup_done:
            return
        _legacy_cleanup_done.add(cache_root)

    try:
        directories = [d for d in cache_root.iterdir() if _LISTINGS_CACHE_DIR.match(d.name) and d.is_dir()]
    except OSError:
        return
    for directory in directories:
        if remove_diskcache_leftovers(directory, idle_for=_SUPERSEDED_GRACE_SECONDS):
            log.info(f"Removed the files of diskcache from the listings cache folder {directory}")
        if directory.name in _LEGACY_LISTINGS_CACHE_DIR_NAMES - {keep}:
            # not recursive: a folder that holds anything else is left alone
            with contextlib.suppress(OSError):
                directory.rmdir()


def _rebuild_file_dir_cache(
    listings_expiry_time: float | None,
    use_listings_cache: bool,  # noqa: FBT001
    listings_cache_location: Path | None,
) -> FileDirCache:
    """Rebuild a FileDirCache from its pickled state.

    ``FileDirCache.__init__`` takes keyword-only arguments, so unpickling needs this
    positional shim.
    """
    return FileDirCache(
        listings_expiry_time,
        use_listings_cache=use_listings_cache,
        listings_cache_location=listings_cache_location,
    )


class FileDirCache(MutableMapping):
    """File-based cache of directory listings for FSSPEC.

    The listings are kept as JSON in an SQLite file (`util/listing_cache.py`), one directory per
    TTL below the cache root. Safe for several threads and processes on one directory.
    """

    def __init__(
        self,
        listings_expiry_time: float | None,
        *,
        use_listings_cache: bool,
        listings_cache_location: Path | None = None,
    ) -> None:
        """Initialize the FileDirCache.

        Args:
            listings_expiry_time: Time in seconds that a listing is considered valid. A falsy
                value (as carried by ``CacheExpiry.INFINITE``, which is ``False``) means the
                listing never expires.
            use_listings_cache: If False, this cache never returns items, but always reports KeyError.
            listings_cache_location: Directory path at which the listings cache file is stored.

        """
        # ``CacheExpiry.INFINITE`` reaches us as ``False``. Map it to ``None``, the "no expiry"
        # sentinel of the store -- ``now + False == now`` made every entry born expired once, so
        # the listings cache silently never hit. Only False/None mean "never expire": a numeric 0
        # has to keep meaning "expire immediately", since silently upgrading it to "cache forever
        # on disk" fails open.
        if listings_expiry_time is None or listings_expiry_time is False:
            self.listings_expiry_time = None
        else:
            self.listings_expiry_time = float(listings_expiry_time)
        self.use_listings_cache = use_listings_cache
        self._listings_cache_location = listings_cache_location

        if not use_listings_cache:
            # Nothing will ever be stored, so don't create a cache directory for it.
            self.cache_location = None
            self._store = None
            return

        from wetterdienst.settings import default_cache_dir  # noqa: PLC0415

        subdir = "infinite" if self.listings_expiry_time is None else str(self.listings_expiry_time)
        if listings_cache_location:
            cache_root = Path(listings_cache_location)
        else:
            cache_root = default_cache_dir(appname="wetterdienst-fsspec")

        def open_store(root: Path) -> tuple[Path, ListingStore]:
            location = root / subdir
            _remove_legacy_listings_cache_dirs(location.parent, keep=location.name)
            log.info(f"Creating dircache folder at {location}")
            make_private_dir(location)
            return location, ListingStore(location / STORE_FILENAME)

        try:
            self.cache_location, self._store = open_store(_effective_cache_dir(cache_root))
        except _CACHE_DIR_ERRORS as error:
            self.cache_location, self._store = open_store(_fallback_cache_dir(cache_root, error))

    def __getitem__(self, item: str) -> list[dict]:
        """Draw item from cache."""
        value = self.get(item)
        if value is None:
            raise KeyError(item)
        return value

    def get(self, key: object, default: list[dict] | None = None) -> list[dict] | None:
        """Return the listing stored under key, or default if there is none or it has expired."""
        # ``self._store is None`` is exactly the "caching disabled" case
        store = self._store
        if store is None:
            return default
        value = store.get(key)
        return default if value is None else value

    def clear(self) -> None:
        """Clear cache."""
        store = self._store
        if store is not None:
            store.clear()

    def __len__(self) -> int:
        """Return number of items in cache."""
        store = self._store
        return 0 if store is None else store.count()

    def __contains__(self, item: object) -> bool:
        """Check if item is in cache and not expired."""
        store = self._store
        return store is not None and store.contains(item)

    def __setitem__(self, key: str, value: list[dict]) -> None:
        """Store listing in cache.

        Raises:
            ListingNotStorableError: If the key is no str or the listing would not come back from
                JSON as it went in, which is all that is stored.

        """
        store = self._store
        if store is None:
            return
        store.set(key, value, self.listings_expiry_time)

    def __delitem__(self, key: str) -> None:
        """Remove item from cache."""
        store = self._store
        if store is None or not store.delete(key):
            raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        """Iterate over keys in cache."""
        store = self._store
        return iter([] if store is None else store.keys())

    def close(self) -> None:
        """Close the database connections of every thread. The cache opens a new one when it is used again."""
        store = self._store
        if store is not None:
            store.close()

    def __reduce__(self) -> tuple:
        """Return state information for pickling."""
        return (
            _rebuild_file_dir_cache,
            (self.listings_expiry_time, self.use_listings_cache, self._listings_cache_location),
        )


class HTTPFileSystem(_HTTPFileSystem):
    """HTTPFileSystem with cache support."""

    def __init__(
        self,
        /,
        *,
        use_listings_cache: bool,
        listings_expiry_time: float,
        listings_cache_location: Path | None = None,
        use_certifi: bool = False,
        **kwargs,  # noqa: ANN003
    ) -> None:
        """Initialize the HTTPFileSystem.

        Args:
            use_listings_cache: If False, this cache never returns items, but always reports KeyError,
            listings_expiry_time: Time in seconds that a listing is considered valid. If None,
            listings_cache_location: Directory path at which the listings cache file is stored. If None,
            use_certifi: If True, use certifi certificate bundle instead of system certificates.
            *args: Additional arguments.
            **kwargs: Additional keyword arguments.

        """
        # Store use_certifi for later use
        self._use_certifi = use_certifi
        #: The `Last-Modified` of the file each url last fetched whole, for `download_file` to take
        #: (`_take_last_modified`)
        self.last_modified_of: dict[str, dt.datetime | None] = {}

        # Every session is built here, so that every request of it passes the guard on redirects
        # (`_check_redirect`), and with our SSL context where certifi is asked for
        async def get_client_with_guard(**client_kwargs):  # noqa: ANN202, ANN003
            """Create an aiohttp ClientSession that checks the redirects it follows."""
            import aiohttp  # noqa: PLC0415

            guard = _redirect_guard()
            client_kwargs["trace_configs"] = [*(client_kwargs.get("trace_configs") or ()), guard]
            if use_certifi:
                ssl_context = _create_ssl_context(use_certifi=True)
                if ssl_context is None:
                    msg = "Failed to create SSL context with certifi"
                    raise RuntimeError(msg)
                client_kwargs["connector"] = aiohttp.TCPConnector(ssl=ssl_context)
            return aiohttp.ClientSession(**client_kwargs)

        kwargs["get_client"] = get_client_with_guard

        # aiohttp >= 3.9 rejects any bare numeric timeout -- int and float alike -- so wrap one in
        # ClientTimeout. ``client_kwargs`` is optional and may legitimately be passed as None (that
        # is fsspec's own default), so check for a dict rather than for the key being present.
        #
        # A number is how long the server may stay silent: connecting, and then each wait for the
        # next bytes, the first ones included. It is not a bound on the whole request, which is
        # what ``total`` would be -- that failed a download still streaming steadily once it ran
        # past the number, so a slow link failed every file larger than that many seconds of its
        # bandwidth (GH-2258). A ClientTimeout passed in is used as it is.
        # ``connect`` as well as ``sock_connect``, because only ``connect`` covers the name lookup,
        # which ``total`` used to bound; it also counts a wait for a free pooled connection, as
        # ``total`` did.
        client_kwargs = kwargs.get("client_kwargs")
        client_kwargs = client_kwargs if isinstance(client_kwargs, dict) else {}
        timeout = client_kwargs.get("timeout")
        if isinstance(timeout, (int, float)) and not isinstance(timeout, bool):
            import aiohttp  # noqa: PLC0415

            kwargs["client_kwargs"] = {
                **client_kwargs,
                "timeout": aiohttp.ClientTimeout(total=None, connect=timeout, sock_connect=timeout, sock_read=timeout),
            }

        kwargs.update(
            {
                "use_listings_cache": use_listings_cache,
                "listings_expiry_time": listings_expiry_time,
            },
        )
        super().__init__(**kwargs)
        # Overwrite the dircache with our own file-based cache
        # we have to use kwargs here, because the parent class
        # requires them to actually activate the cache
        self.dircache = FileDirCache(
            use_listings_cache=use_listings_cache,
            listings_expiry_time=listings_expiry_time,
            listings_cache_location=listings_cache_location,
        )

    async def _cat_file(self, url: str, start: int | None = None, end: int | None = None, **kwargs) -> bytes:  # noqa: ANN003
        """Read a whole file, up to ``max_bytes`` of it (`MAX_DOWNLOAD_BYTES` unless given) and `MAX_DOWNLOAD_SECONDS`.

        Upstream reads the body in one go, however large it turns out to be and however slowly it comes.
        A range is the caller's own bound and is read as upstream reads it.
        """
        max_bytes = kwargs.pop("max_bytes", None)
        if start is not None or end is not None:
            return await super()._cat_file(url, start=start, end=end, **kwargs)
        max_bytes = MAX_DOWNLOAD_BYTES if max_bytes is None else max_bytes
        seen: dict[str, str | None] = {}
        kw = {**self.kwargs, **kwargs, "trace_request_ctx": seen}
        session = await self.set_session()
        async with _within_time(MAX_DOWNLOAD_SECONDS), session.get(self.encode_url(url), **kw) as response:
            self._raise_not_found_for_status(response, url)
            payload = await _read_capped(response, max_bytes)
        _remember_last_modified(self.last_modified_of, url, _last_modified_of(seen))
        return payload

    async def _get_file(
        self,
        rpath: str,
        lpath: str | IO[bytes],
        chunk_size: int = 5 * 2**20,
        callback: Callback = DEFAULT_CALLBACK,
        **kwargs,  # noqa: ANN003
    ) -> None:
        """Stream a file to disk, held to ``max_bytes`` (default `MAX_DOWNLOAD_BYTES`) and `MAX_DOWNLOAD_SECONDS`."""
        max_bytes = kwargs.pop("max_bytes", None)
        max_bytes = MAX_DOWNLOAD_BYTES if max_bytes is None else max_bytes
        if callback is DEFAULT_CALLBACK:
            callback = _SizeGuard(max_bytes)
        opened: IO[bytes] | None = None
        if isfilelike(lpath):
            target = lpath
        else:
            target = opened = open(str(lpath), "wb")  # noqa: ASYNC230, PTH123, SIM115
        seen: dict[str, str | None] = {}
        try:
            async with _within_time(MAX_DOWNLOAD_SECONDS):
                await super()._get_file(
                    rpath,
                    _CappedWriter(target, max_bytes),
                    chunk_size=chunk_size,
                    callback=callback,
                    trace_request_ctx=seen,
                    **kwargs,
                )
            _remember_last_modified(self.last_modified_of, rpath, _last_modified_of(seen))
        finally:
            if opened is not None:
                opened.close()

    async def _ls(self, url: str, detail: bool = True, **kwargs) -> list:  # noqa: ANN003, FBT001, FBT002
        """List a directory, going through the dircache with a single lookup.

        Overrides the upstream implementation for two reasons:

        * upstream probes ``url in self.dircache`` and then indexes it, which races with TTL
          expiry between the two calls and raises a ``KeyError`` that nothing catches,
        * upstream caches whatever shape ``detail`` asked for, so one ``detail=False`` call
          poisons every later ``detail=True`` read of the same URL. We always cache the
          detailed listing and derive the name-only view from it.
        """
        # a cached listing is always a list (possibly empty), so None is a safe "miss" sentinel
        out: list[dict] | None = self.dircache.get(url) if self.use_listings_cache else None
        if out is None:
            out = await self._ls_real(url, detail=True, **kwargs)
            # fsspec keeps a link of an https listing that leads to the same address over http, which a
            # caller then fetches in clear
            if urlsplit(url).scheme == "https":
                out = [entry for entry in out if urlsplit(entry["name"]).scheme != "http"]
            self.dircache[url] = out
        return out if detail else sorted(entry["name"] for entry in out)

    # the parent binds ``ls`` to *its* ``_ls`` function object, so the override above only
    # takes effect for callers that look ``_ls`` up dynamically (``find``/``walk``). Rebind
    # it so the plain synchronous ``ls()`` goes through our implementation too.
    ls = sync_wrapper(_ls)


#: header names a credential is sent under. `Authorization` is the standard one -- KNMI's API key,
#: met.no Frost's basic auth and Met Office's bearer token all go there -- but AEMET wants `api_key`,
#: and a header named anything else is a header this cannot know to redact: a provider that invents
#: one has to name it here for its failures to be scrubbed along with the rest.
#:
_CREDENTIAL_HEADERS = frozenset({"authorization", "proxy-authorization", "api_key", "api-key", "x-api-key"})

#: Headers that cannot change the body a server sends back, and so may be shared by every caller's
#: cached blobs. Everything else separates them.
#:
#: Named the other way round from `_CREDENTIAL_HEADERS` on purpose, because the two lists answer
#: questions whose wrong answers cost different things. Missing a credential there costs a log line;
#: missing one *here* serves one caller's body to another. A list of what matters fails open on
#: every header nobody thought of -- `Cookie`, `X-Auth-Token`, and the content-negotiation headers a
#: user can set for themselves through `WD_FSSPEC_CLIENT_KWARGS`, where `Accept-Language: de` and
#: `en` would otherwise share one directory. A list of what does *not* matter fails closed: an
#: unknown header costs a cache miss, which is a slow answer rather than a wrong one.
_CACHE_NEUTRAL_HEADERS = frozenset({"user-agent"})


def _credential_headers(client_kwargs: dict | None) -> dict[str, str] | None:
    """Read the credential-bearing headers these kwargs carry, or `None` where that cannot be read.

    aiohttp takes headers as a mapping or as a sequence of pairs, so both are read here. One
    reader, because two callers have to agree about the answer -- the scrubber that keeps a
    credential out of an error it hands back, and the cache path that keeps one caller's bodies away
    from another's -- and both fail dangerously on a false negative: one logs the header, the other
    files an authenticated body where an unauthenticated request will be given it.

    So a shape neither can read is `None`, "there may be a credential here", rather than `{}`. An
    iterator is such a shape and is deliberately not read: reading it would empty it, and what the
    caller's own request needs is still in there.
    """
    headers = (client_kwargs or {}).get("headers")
    if not headers:
        return {}
    if hasattr(headers, "items"):
        items = headers.items()
    elif isinstance(headers, (list, tuple)):
        items = headers
    else:
        return None
    try:
        return {str(name).lower(): _header_value(value) for name, value in items}
    except (AttributeError, TypeError, ValueError):
        return None


#: Names the layout of `cache_dir/fsspec`, so that a directory written under an older one can be
#: told apart from a live one by its name alone rather than by guessing from its age or contents.
#: Bump it whenever `_cache_path` changes shape, and every directory left by the previous shape is
#: reclaimed on the next run.
_CACHE_LAYOUT_VERSION = "v2"

#: Blob directories already swept of expired entries in this process. Process-wide rather than
#: thread-local, because the directory is shared by every thread while the registry naming it is not.
_swept_dirs: set[Path] = set()

#: Held across everything that opens or deletes a metadata file under `cache_dir/fsspec`: building a
#: caching filesystem, loading and saving its metadata as it downloads, sweeping one of expired
#: blobs, and reclaiming the directories nothing can reach.
#:
#: One lock over all of them rather than one each, because *building* a filesystem reads its
#: directory's metadata file and the sweep and the reclaim can delete it. On POSIX that is harmless
#: -- an unlink leaves the open handle readable -- which is why separate locks looked sufficient and
#: why this passed everywhere it was run. On Windows it is `PermissionError: [Errno 13]` out of
#: fsspec's `CacheMetadata._load`, and CI said so.
#:
#: The loads and saves are what `_LockedWholeFileCacheFileSystem` holds it for, and the saves are the
#: ones that matter: a download saves once per file, and fsspec's save reads the file, merges and
#: replaces it. Each thread of `download_files` has a filesystem of its own, but they all share the
#: one metadata file, and on Windows a read that meets another thread's replace is the same
#: `PermissionError` (GH-1990). Reentrant, because building a filesystem loads its metadata from
#: inside the lock.
_cache_dir_lock = threading.RLock()

#: How long a process waits for another one that holds the lock file of a cache directory (GH-3485). What is held
#: for is a read, a merge and a replace of one metadata file, or a sweep of one directory: well under a second for a
#: directory of thousands of entries. Ten seconds is for a machine that is swapping, not for a process that is stuck.
_CACHE_LOCK_TIMEOUT_SECONDS = 10.0

#: How long a load waits: it goes ahead without the lock whatever the answer, so it is not worth the whole timeout.
_CACHE_LOAD_WAIT_SECONDS = 1.0

#: How long a directory counts as contended after a wait for it ran out. The wait happens with `_cache_dir_lock` held
#: (see `_locked_across_processes`), so a holder that is stuck would cost every thread of this process a timeout for
#: every file it downloads. Until this has passed the lock is only tried, never waited for, and the first hold that
#: gets it ends the period. So a stuck holder costs one timeout a minute for each directory, and the threads that
#: queue behind it find the directory marked.
_CACHE_LOCK_CONTENDED_SECONDS = 60.0

#: The lock files this process has opened, by process id and path. The process id is in the key because a child made by
#: `fork` inherits the table, and a lock object that was held (or only opened) in the parent is the parent's. One object
#: per path, and not one per use, because the lock is reentrant by count on the object: a second object on the same file
#: would wait for the first one, which is this very thread, for the whole timeout.
_cache_dir_file_locks: dict[tuple[int, Path], FileLock] = {}

#: The directories whose lock a wait has given up on, until when (`time.monotonic()`). Guarded by `_cache_dir_lock`.
_cache_dirs_contended_until: dict[Path, float] = {}


def _lock_file_of(directory: Path) -> Path:
    """Name the file beside a cache directory that the processes sharing it take turns on.

    Beside it and not in it, deliberately: `clear_cache` and the reclaim remove the directory, and a lock file removed
    from under a process that waits on it is a lock two processes can hold at once (each has a different file). The
    reclaim of a directory removes its lock file once it holds the lock, which is then not named by anyone any more.
    """
    return directory.with_name(directory.name + ".lock")


@contextlib.contextmanager
def _locked_across_processes(directory: Path, *, otherwise: str, wait: float | None = None) -> Iterator[bool]:
    """Hold the lock of a cache directory against every other process (and thread) that shares it (GH-3485).

    `_cache_dir_lock` is taken first and kept to the end, always in that order, so that two threads cannot each hold
    one and wait for the other; and so that the lock file is only ever held by one thread of this process, which is
    what lets its count stand for reentrancy. It is held while the lock file is waited for, which is the price of that
    order (a thread that holds `_cache_dir_lock` and waits for the file lock of a thread that waits for it would
    otherwise be possible): the wait is bounded by `wait` or `_CACHE_LOCK_TIMEOUT_SECONDS`, and after one that ran out
    the directory is only tried for `_CACHE_LOCK_CONTENDED_SECONDS`, so that a stuck holder costs one timeout a minute
    and not one per file. The lock is taken around the short critical sections (the read, merge and replace of the
    metadata file; the rename of a fetched file onto its blob and the row for it; the sweep) and never around a
    download.

    The lock is `filelock`'s `flock` on POSIX and `msvcrt.locking` on Windows, and never its `SoftFileLock`
    (`fallback_to_soft=False`: a file system without `flock` answers `ENOSYS`, the lock is not taken and the caller goes
    ahead as it did before there was one, where the existence of a marker left by a process that is dead, or on another
    host, would hold every later save and sweep for good). The first two belong to the open file and are released by the
    operating system when the process ends, however it ends (`kill -9`, a crash, a reboot), so a lock file left behind
    by a dead process does not hold anything and there is no stale lock to detect. What can hold a lock for long is a
    process that is alive and stuck, which is what the timeout is for.

    Yields whether the caller may go ahead:

    * `True`: the lock is held, or it could not be taken at all (a file system without `flock`, a read-only
      directory). That is the caller's situation before there was a lock, and nothing is better done about it than
      going on.
    * `False`: another process held it past the wait. What the caller does then is its own to say (`otherwise`, for the
      log line): a save is skipped, which costs a fetch again later at worst; a sweep is left to the next process; a
      load, a drop of an entry and a clear go ahead, as they did before the lock.

    Args:
        directory: The cache directory (the one with the metadata file in it).
        otherwise: What the caller does where it does not get the lock, for the log line.
        wait: How many seconds to wait at most; the timeout where `None`. Zero tries once. A wait that runs out
            marks the directory, whoever waited.

    """
    with _cache_dir_lock:
        key = (os.getpid(), directory)
        file_lock = _cache_dir_file_locks.get(key)
        if file_lock is None:
            file_lock = _cache_dir_file_locks[key] = FileLock(
                str(_lock_file_of(directory)), thread_local=False, fallback_to_soft=False
            )
        contended = time.monotonic() < _cache_dirs_contended_until.get(directory, 0.0)
        timeout = (
            0.0
            if contended
            else _CACHE_LOCK_TIMEOUT_SECONDS
            if wait is None
            else min(wait, _CACHE_LOCK_TIMEOUT_SECONDS)
        )
        acquired = False
        proceed = True
        try:
            file_lock.acquire(timeout=timeout)
            acquired = True
            _cache_dirs_contended_until.pop(directory, None)
        except Timeout:
            proceed = False
            if timeout > 0:
                # a wait that ran out for good, not a try: the directory is marked, and the line is said once
                _cache_dirs_contended_until[directory] = time.monotonic() + _CACHE_LOCK_CONTENDED_SECONDS
                log.warning(
                    f"Gave up waiting {timeout:g} s for another process that holds {file_lock.lock_file}, so "
                    f"{otherwise}; it is only tried for the next {_CACHE_LOCK_CONTENDED_SECONDS:g} s"
                )
            else:
                log.debug(f"{file_lock.lock_file} is held by another process, so {otherwise}")
        except Exception:
            # `OSError` (a directory that cannot be written to, `ENOSYS` where there is no `flock`)
            log.debug(f"Could not lock {directory}, going on without", exc_info=True)
        try:
            yield proceed
        finally:
            if acquired:
                with contextlib.suppress(Exception):
                    file_lock.release()


def _sweep_expired_blobs(
    filesystem: WholeFileCacheFileSystem,
    cache_path: Path,
    ttl_value: float | Literal[False],
) -> None:
    """Drop blobs this directory's own TTL has already made useless.

    Once per directory per process, and never able to raise: every one of the three ways the
    obvious version of this went wrong is a way of failing a download that would otherwise have
    worked (GH-1955).

    * **A TTL that is not a positive number is not swept at all.** `CacheExpiry.INFINITE` is
      `False`, `int(False)` is `0`, and fsspec reads an expiry of zero as "everything is
      expired" -- it removes every entry. `lhmt` and both
      `meteofrance` providers use `INFINITE` for immutable archives, so the first such download
      in a fresh process would have destroyed the archive cache and re-fetched it. The read path
      gets this right (`_check_file` reads `if cfs.expiry and ...`); only the sweep did not.
    * **The directory is marked swept before the attempt, not after.** `clear_expired` raises
      for a half-written entry -- exactly the case worth surviving -- and a sweep retried on
      every `register` would fail every download for this TTL rather than the one that met it.
    * **Nothing is downloading into this directory while it runs**, which is what the sweep
      needs: a sweep beside a `download_files` thread pool could drop rows its siblings had just
      written and orphan their blobs -- the leak this exists to close.

      What guarantees that is `_swept_dirs`, not the lock: this runs on the first `register` for a
      path, and until that returns no filesystem for the directory exists for anything to download
      through. The lock the caller holds is for a narrower thing -- another thread *building* a
      filesystem for this directory reads the metadata file a sweep can delete, which on Windows is
      a `PermissionError` for the builder rather than the harmless POSIX unlink. So a sweep that is
      ever re-armed after the first one needs a new answer to the first question, and the lock alone
      will not give it one. A download takes it for each load and save of the metadata, which keeps
      the two from overlapping, and the sweep reads the file again under the same hold
      (`_refresh_metadata`), so the rows a sibling *thread* saved are merged in before it writes.
      Another *process* saving between that read and the write is kept out by the lock file of the
      directory, which `clear_expired_cache` holds for the whole of the sweep
      (`_locked_across_processes`, GH-3485): a sweep that cannot get it in time is skipped.

    Args:
        filesystem: The caching filesystem that owns this directory.
        cache_path: The directory the blobs live in, which names the sweep.
        ttl_value: The TTL behind it, as `resolve_ttl` returns it.

    """
    # `bool` is a subclass of `int`, and `CacheExpiry.INFINITE` is `False`
    if isinstance(ttl_value, bool) or not isinstance(ttl_value, (int, float)) or ttl_value <= 0:
        return
    if cache_path in _swept_dirs:
        return
    _swept_dirs.add(cache_path)
    try:
        # a second line rather than the line: the guard above already means this is positive, but
        # fsspec substitutes `self.expiry` for a falsy argument and for an `INFINITE` cache that is
        # the `0` described above, so what reaches it is said rather than left implied
        filesystem.clear_expired_cache(expiry_time=ttl_value)
    except Exception:
        log.debug(f"Failed sweeping expired blobs in {cache_path}", exc_info=True)


#: The `<NAME>` part of a blob directory: a `CacheExpiry` member name, as `resolve_ttl` returns it.
#: Written once and shared by both patterns below, which have to agree about it -- widening one and
#: not the other left a directory that `_BLOB_CACHE_DIR` recognised and `_IDENTITY_CACHE_DIR` did
#: not, so a rotated credential under a TTL whose name carries a digit was never aged out.
_TTL_NAME = r"[A-Z0-9_]+"

#: Any blob directory this module has ever written: `ttl-<NAME>` with an optional hash suffix,
#: under an optional layout prefix (the first layout had none). Matching every layout rather than
#: only the one before this is what makes `_CACHE_LAYOUT_VERSION` self-cleaning: a build reclaims
#: what any other layout wrote, in both directions, so alternating between two versions costs a
#: re-download rather than a directory that neither of them will ever collect.
#:
#: `<NAME>` is a character class rather than the `CacheExpiry` members, deliberately: the directories
#: worth reclaiming are the ones *older* builds wrote, and a TTL one of them had may since have been
#: renamed or removed. So it is written to match any enum member name a build could have produced,
#: which is wider than today's enum and cannot be pinned by a test against it. What a test does pin
#: is the other direction -- that every directory this build writes is one this recognises.
_BLOB_CACHE_DIR = re.compile(rf"^(?:v\d+-)?ttl-{_TTL_NAME}(?:-[0-9a-f]{{8}})?$")

#: A blob directory of the current layout that a *credential* names. The unsuffixed ones are named
#: by every run and their liveness is never in question; these are the only ones that can stop being
#: named while the library goes on working, because the credential they are named for has rotated.
_IDENTITY_CACHE_DIR = re.compile(rf"^{_CACHE_LAYOUT_VERSION}-ttl-{_TTL_NAME}-[0-9a-f]{{8}}$")

#: Touched whenever a directory is named, so that "nothing has asked for this in a month" can be
#: read off it. The blobs cannot answer that themselves: an archive that is read on every run and
#: written on none has file times as old as the day it was fetched.
_CACHE_USE_MARKER = ".last-used"
_UNUSED_CACHE_SECONDS = 30 * 24 * 3600

#: How recently a directory of a superseded layout must have been written to be spared. The default
#: cache dir is shared by every install for a user, so an older version may be running beside this
#: one -- a `restapi` container, another venv -- with a download in flight into the directory this
#: is about to remove. One that is genuinely in use has blobs written into it within the hour;
#: anything older is not being written to by anyone, and waiting a month to reclaim it would defeat
#: the point of reclaiming it at all.
_SUPERSEDED_GRACE_SECONDS = 3600

#: Stands in for a credential in headers that `_credential_headers` could not read. A constant, so
#: that such a caller gets one directory rather than a new one per process, and eight hex digits so
#: that it is aged out like any other directory a credential names.
_UNREADABLE_IDENTITY = hashlib.sha256(b"unreadable credential headers").hexdigest()[:8]

_reclaim_done: set[Path] = set()


def _is_superseded_layout(name: str) -> bool:
    """Whether this is a blob directory of some layout other than the one in use.

    No key this build can produce names one, so nothing can reach it to expire it -- which is the
    whole of why it is removed rather than left to a TTL.
    """
    return bool(_BLOB_CACHE_DIR.match(name)) and not name.startswith(f"{_CACHE_LAYOUT_VERSION}-")


def _mark_cache_dir_used(cache_path: Path) -> None:
    """Record that something asked for this directory, which is what keeps it from being reclaimed."""
    try:
        (cache_path / _CACHE_USE_MARKER).touch()
    except OSError:
        log.debug(f"Failed marking {cache_path} as used", exc_info=True)


def _last_used(directory: Path) -> float:
    """When this directory was last named.

    A directory with no marker counts as just used, not as never used. `_mark_cache_dir_used` is
    best-effort -- a read-only or full cache dir logs and carries on -- and the directory's own
    mtime is exactly the lie the marker exists to correct: a fully cached archive read on every run
    and written on none is a month old the day after it is fetched. So a missing marker is answered
    the same way an unreadable one is, and the directory is kept.
    """
    marker = directory / _CACHE_USE_MARKER
    try:
        return marker.stat().st_mtime
    except OSError:
        return time.time()


def _written_before(directory: Path, cutoff: float) -> bool:
    """Whether nothing has been written into this directory since `cutoff`.

    Read off the directory's own mtime, which is the right question for a layout no build of this
    version writes: what matters is whether some *other* build is writing into it right now.
    """
    try:
        return directory.stat().st_mtime < cutoff
    except OSError:
        return False


def _reclaim_unreachable_cache_dirs(fsspec_root: Path, keep: Path) -> None:
    """Remove blob directories nothing can reach any more.

    Runs once per cache root per process, and is best-effort throughout: a directory that cannot be
    removed is not a reason to fail the download that happened to trigger the sweep. Two kinds go,
    and neither holds anything that is not re-downloadable:

    * **An earlier `_cache_path` layout.** Nothing can expire these, because the key that named them
      cannot be produced by this version at all. Until `_cache_path` stopped hashing transport
      settings the User-Agent carried the version number, so every release left a full set behind:
      one developer machine held 129 directories under 98 distinct hashes and 4.3 GB in all, of
      which 115 MB was reachable (GH-1959).
    * **A credential that has rotated.** `_identity_suffix` names a directory for the credential it
      was fetched with, and Met Office mints a three-day JWT -- so that provider renames its
      directory twice a week and would otherwise leave the previous one behind for good. Aged out
      by the marker rather than by the blobs' own file times, and only ever for a directory a
      credential names: the shared ones are named on every run, and reclaiming one for looking idle
      would throw away the main cache.

    Args:
        fsspec_root: The `fsspec` directory under the cache dir that blob directories live in.
        keep: The directory the caller is about to use, never removed however it looks.

    Note:
        The caller holds `_cache_dir_lock`: this deletes directories whose metadata another thread
        may be in the middle of opening.

    """
    if fsspec_root in _reclaim_done:
        return
    _reclaim_done.add(fsspec_root)

    try:
        entries = [d for d in fsspec_root.iterdir() if d.is_dir() and d != keep]
    except OSError:
        log.debug(f"Failed listing {fsspec_root} for unreachable cache directories", exc_info=True)
        return

    now = time.time()
    idle_cutoff = now - _UNUSED_CACHE_SECONDS
    superseded_cutoff = now - _SUPERSEDED_GRACE_SECONDS
    stale = [
        directory
        for directory in entries
        if (_is_superseded_layout(directory.name) and _written_before(directory, superseded_cutoff))
        or (_IDENTITY_CACHE_DIR.match(directory.name) and _last_used(directory) < idle_cutoff)
    ]

    reclaimed = 0
    removed = 0
    for directory in stale:
        # in its own `try`, and before nothing: it is walked for a log line, and a file vanishing
        # mid-walk -- a concurrent process, fsspec writing -- used to take the `rmtree` with it and
        # leave the one directory that is actually being churned as the one never reclaimed. Cheap
        # enough to keep: blobs are few and large, so 4.3 GB is under 5000 files and a quarter of a
        # second
        try:
            reclaimed += sum(f.stat().st_size for f in directory.rglob("*") if f.is_file())
        except OSError:
            log.debug(f"Failed sizing unreachable cache directory {directory}", exc_info=True)
        # not while a process of this version is in the middle of something in it: the lock is tried, never waited for,
        # and a directory that is held is somebody's and is left (the next run that finds it idle tries again)
        with _locked_across_processes(directory, otherwise="the directory is left alone", wait=0) as free:
            if not free:
                continue
            try:
                shutil.rmtree(directory)
            except OSError:
                log.debug(f"Failed removing unreachable cache directory {directory}", exc_info=True)
                continue
        # the file the processes that shared it took turns on, once it is let go: nobody names this directory any more
        with contextlib.suppress(OSError):
            _lock_file_of(directory).unlink(missing_ok=True)
        removed += 1
    if removed:
        # what went, not what was considered: the sweep that removes nothing because every `rmtree`
        # failed used to report the whole list as reclaimed
        log.info(f"Reclaimed {reclaimed / 1e6:.1f} MB from {removed} unreachable cache directories in {fsspec_root}")


#: What is added to a blob's name for the file that keeps the `Last-Modified` it came with (GH-2567)
_SIDECAR_SUFFIX = ".lm"


def _sidecar_of(blob: Path) -> Path:
    """Name the file beside a cached blob that holds the date the source gave it."""
    return blob.with_name(blob.name + _SIDECAR_SUFFIX)


def _write_sidecar(blob: Path, last_modified: dt.datetime | None, written: os.stat_result) -> None:
    """Keep the `Last-Modified` a blob arrived with beside it, bound to the blob by its size and modification time.

    The date cannot live in fsspec's own metadata record: its save merges a record into the one on disk and keeps the
    disk's own fields, so the date of a copy fetched anew over an expired one would be the old copy's. A file of its own
    is replaced whole, with the blob it describes. It says which blob that is: the size and the modification time of
    the file as it was written (a rename keeps both), so that a blob another process put there since, or a copy cached
    before dates were kept, is a blob it does not describe. A fetch whose response gave no date writes the record with
    a null date: the copy has no date, and the record says it was made by a version that kept them
    (`_has_sidecar_record`), which is what tells it from a copy made before. Never raises: a date lost is a null, not a
    failed download.

    Written under the lock of the cache directory and only if the blob is still the file `written` describes: of two
    fetches that replace the blob one after the other, the one that comes later may write its sidecar first, and the
    earlier one then finds a blob that is not its own and leaves the sidecar of the other where it is.
    """
    sidecar = _sidecar_of(blob)
    temp = sidecar.with_name(f"{sidecar.name}.{uuid.uuid4().hex}.tmp")
    try:
        with _cache_dir_lock:
            current = blob.stat()
            if (current.st_size, current.st_mtime_ns) != (written.st_size, written.st_mtime_ns):
                return
            record = {
                "last_modified": None if last_modified is None else last_modified.isoformat(),
                "size": written.st_size,
                "mtime_ns": written.st_mtime_ns,
            }
            temp.write_text(json.dumps(record), encoding="utf-8")
            os.replace(temp, sidecar)  # noqa: PTH105
    except OSError:
        log.debug(f"Failed keeping the date of {blob}", exc_info=True)
    finally:
        with contextlib.suppress(OSError):
            temp.unlink(missing_ok=True)


def _sidecar_record(blob: Path) -> dict | None:
    """Read the record kept beside a cached blob: `None` for a blob with no sidecar, or one it does not describe."""
    try:
        record = json.loads(_sidecar_of(blob).read_text(encoding="utf-8"))
        written = blob.stat()
        if record["size"] != written.st_size or record["mtime_ns"] != written.st_mtime_ns:
            return None
    except (OSError, ValueError, KeyError, TypeError):
        return None
    return record


def _has_sidecar_record(blob: Path) -> bool:
    """Tell whether the blob was cached by a version that kept dates: a record of it, with a date or without one."""
    return _sidecar_record(blob) is not None


def _read_sidecar(blob: Path) -> dt.datetime | None:
    """Read the date a cached blob came with: `None` for a blob with no sidecar, or one it does not describe."""
    record = _sidecar_record(blob)
    try:
        value = dt.datetime.fromisoformat(record["last_modified"]) if record else None
    except (ValueError, KeyError, TypeError):
        return None
    return value.astimezone(dt.UTC) if value is not None and value.tzinfo is not None else None


def _drop_orphaned_sidecars(directory: Path) -> None:
    """Remove the sidecars whose blob is gone, which is what the sweep of an expired entry leaves of them."""
    try:
        sidecars = list(directory.glob(f"*{_SIDECAR_SUFFIX}"))
    except OSError:
        return
    for sidecar in sidecars:
        with contextlib.suppress(OSError):
            if not sidecar.with_name(sidecar.name.removesuffix(_SIDECAR_SUFFIX)).exists():
                sidecar.unlink(missing_ok=True)


def _written_after(path: Path, moment: float) -> bool:
    """Whether a file was written after `moment` (as `time.time()` has it): False for one that is not there."""
    try:
        return path.stat().st_mtime > moment
    except OSError:
        return False


def _remove_unclaimed_files(directory: Path, rows: dict[str, Any], older_than: float) -> None:
    """Remove the files of a cache directory that no row names and that are older than `older_than` seconds.

    What a sweep that removed the whole directory used to collect: a blob whose row another process's save dropped, the
    `<blob>.<uuid>.tmp` of a fetch that was killed, a `cache-<random>` of a save that was. Left alone are the metadata
    file, the marker, the blobs rows name and their sidecars. Not older than `older_than` or an hour, whichever is
    longer: the file of a fetch in flight moves only when bytes arrive, so a stalled one is older than a short TTL (or a
    timeout longer than it) and another process's sweep must not take it from under the fetch. A removal that fails is
    skipped (Windows refuses one on a file that is open).
    """
    named = {str(detail["fn"]) for detail in rows.values() if isinstance(detail, dict) and "fn" in detail}
    kept = {"cache", _CACHE_USE_MARKER}
    cutoff = time.time() - max(older_than, _SUPERSEDED_GRACE_SECONDS)
    try:
        entries = list(directory.iterdir())
    except OSError:
        return
    for entry in entries:
        name = entry.name
        if name in kept or name in named or name.removesuffix(_SIDECAR_SUFFIX) in named:
            continue
        with contextlib.suppress(OSError):
            if entry.is_file() and entry.stat().st_mtime < cutoff:
                entry.unlink(missing_ok=True)


def _last_modified_registry(filesystem: object) -> dict[str, dt.datetime | None] | None:
    """Give the dict of `Last-Modified` dates that a filesystem, or the one it wraps, keeps for `download_file`."""
    registry = getattr(getattr(filesystem, "fs", filesystem), "last_modified_of", None)
    return registry if isinstance(registry, dict) else None


def _take_last_modified(filesystem: object, url: str) -> dt.datetime | None:
    """Take the date the filesystem noted for the file it just read, once: `None` where it noted none."""
    registry = _last_modified_registry(filesystem)
    return None if registry is None else registry.pop(url, None)


def _metadata_stamp(filesystem: WholeFileCacheFileSystem) -> tuple[int, int, int] | None:
    """Name the state of the metadata file by what the file system says of it: modification time, size, inode.

    `None` for a file that is not there. The inode is in it because a save replaces the file.
    """
    try:
        status = (Path(filesystem.storage[-1]) / "cache").stat()
    except OSError:
        return None
    return status.st_mtime_ns, status.st_size, status.st_ino


def _entry_time(detail: object) -> float:
    """Read when an entry of the metadata was made: 0 for one that says nothing usable, which any other beats."""
    try:
        return float(detail["time"]) if isinstance(detail, dict) else 0.0
    except (KeyError, TypeError, ValueError):
        return 0.0


def _refresh_metadata(filesystem: WholeFileCacheFileSystem) -> None:
    """Bring what a caching filesystem holds up to what the metadata file says now, where that has moved.

    Skipped where the file is the one this filesystem last read or wrote (`_metadata_stamp`, taken by its `load_cache`
    and `save_cache`): a miss on an unchanged file is free, which matters for a directory of tens of thousands of
    entries (the file is megabytes) that is asked about each file before it is fetched. Otherwise the file is read
    and *merged* into what is held, as fsspec's own save merges: an entry only this filesystem holds is kept (another
    process may have written the file from a read older than that entry, and the next save of this filesystem writes
    it back, as it does on a filesystem that never reloaded), and where both hold one the later `time` wins.

    A read that fails leaves the view as it was, which is what a lookup that only asks is to go on with. That is for a
    failure that passes: on Windows the file is not readable while another process replaces it (`PermissionError`). A
    file that is cut short stays an error, as it was: the save of the next fetch reads it too.
    """
    try:
        with _cache_dir_lock:
            if filesystem._wd_metadata_stamp == _metadata_stamp(filesystem):  # noqa: SLF001
                return
            held = filesystem._metadata.cached_files[-1]  # noqa: SLF001
            filesystem.load_cache()
            fresh = filesystem._metadata.cached_files[-1]  # noqa: SLF001
            # a record of the file that has no usable `time` counts as 0, so that it never raises once the view is
            # replaced (the stamp would then keep the entries only this filesystem held from being read back)
            for key, detail in held.items():
                if key not in fresh or _entry_time(fresh[key]) < _entry_time(detail):
                    fresh[key] = detail
    except Exception:
        log.debug("Could not read the cache metadata again, keeping what is held", exc_info=True)


def _held_in_view(filesystem: object, url: str) -> Literal[False] | tuple[dict[str, Any], str]:
    """Say whether a caching filesystem's view of the metadata holds a copy of a url, without a reload of its own.

    fsspec's own read of the file after `cache_check` (10 s) can still run inside it. False for a filesystem that does
    not cache.
    """
    if isinstance(filesystem, WholeFileCacheFileSystem):
        return WholeFileCacheFileSystem._check_file(filesystem, url)  # noqa: SLF001
    return False


class _LockedWholeFileCacheFileSystem(WholeFileCacheFileSystem):
    """A `WholeFileCacheFileSystem` that reads and writes its metadata file under `_cache_dir_lock`.

    Overrides every method of fsspec's that reaches the metadata file: `load_cache` and
    `save_cache` are what a download goes through, `pop_from_cache` is how MOSMIX drops a truncated
    run, `clear_expired_cache` is the sweep, and `clear_cache` deletes the file along with the
    blobs. fsspec resolves all five on the class rather than on the instance, so an override here is
    what its own internal calls reach as well. `_check_file`, which fsspec asks the view, is
    overridden to read the file again where the view holds no usable copy (GH-3452).

    `_open` is overridden for another reason: to fetch a missing file without fsspec's `exists`
    probe, and to record it only once it has arrived (GH-2467). It reaches the metadata file through
    `save_cache`, under the lock like every other caller.
    """

    def load_cache(self) -> None:
        """Read the metadata file, with no other thread or process in the middle of replacing it.

        A load goes ahead when the lock file of the directory is held by another process for longer than the timeout:
        it is what it did before there was one, and a read that meets a replace is at worst the `PermissionError`
        that `_refresh_metadata` already survives.
        """
        with _locked_across_processes(
            Path(self.storage[-1]), otherwise="the metadata is read without it", wait=_CACHE_LOAD_WAIT_SECONDS
        ):
            # before the read: a file replaced during it then differs from the stamp, and is read again
            stamp = _metadata_stamp(self)
            super().load_cache()
            self._wd_metadata_stamp = stamp

    def save_cache(self) -> None:
        """Read, merge and replace the metadata file, with no other thread or process reading or replacing it.

        The read-merge-write is one step for the lock file of the directory (GH-3485): a row another process saved
        between the read and the replace was lost to it, and on Windows the replace (`os.replace` in fsspec's
        `atomic_write`) is a `PermissionError` while another process has the file open, which a reader in this lock
        does not. Where another process holds the lock past the timeout the save is skipped: the entry stays in this
        filesystem's view, the blob stays where it is, and the file is fetched again by whoever needs it next.
        """
        with _locked_across_processes(
            Path(self.storage[-1]), otherwise="the save of the metadata is skipped"
        ) as proceed:
            if not proceed:
                return
            super().save_cache()
            self._wd_metadata_stamp = _metadata_stamp(self)

    def _check_file(
        self, path: str, refetch_before: float | None = None
    ) -> Literal[False] | tuple[dict[str, Any], str]:
        """Say whether the cache holds an unexpired copy of a file, reading the metadata file again where it is not.

        fsspec keeps one filesystem per thread ident and arguments, and an ident is handed out again once its thread
        has ended, so a thread can hold a filesystem that other threads (or processes) have cached into since it last
        read the file: it reads it only when built and after `cache_check` (10 s). Such a view says no to a copy that
        is there, and the file is fetched again (GH-3452). A hit costs nothing more than before; a miss reads the
        file again if it has changed since this filesystem read or wrote it (`_refresh_metadata`). So does a copy
        older than `refetch_before`, which another thread may have fetched again since. The view is asked again once
        it has been refreshed, and also where it was not: another thread on this very filesystem may have moved it
        while this one looked.
        """
        held = super()._check_file(path)
        if held and not (refetch_before is not None and held[0]["time"] < refetch_before):
            return held
        _refresh_metadata(self)
        return super()._check_file(path)

    def pop_from_cache(self, path: str) -> None:
        """Drop one entry from the metadata file, which saves it, and the date kept beside its blob.

        Not skipped where the lock file is held past the timeout: the entry is dropped because its file is no good,
        and keeping it would serve that file again.
        """
        with _locked_across_processes(Path(self.storage[-1]), otherwise="the entry is dropped without it"):
            if not self._metadata.check_file(self._strip_protocol(path), None):
                # the copy may be one another thread cached since this view was read, which is then not dropped
                _refresh_metadata(self)
            blob = Path(self.storage[-1]) / self._mapper(self._strip_protocol(path))
            super().pop_from_cache(path)
            with contextlib.suppress(OSError):
                _sidecar_of(blob).unlink(missing_ok=True)

    def clear_expired_cache(self, expiry_time: float | None = None) -> None:
        """Drop the expired entries from the metadata file and their blobs and dates, and nothing else (GH-3467).

        fsspec's own sweep removes the whole directory when it ends with no entry in the snapshot it holds, and the
        snapshot of a process that starts on an empty directory is empty whatever the processes that started beside it
        have written since. That took their copies, and the directory from under them: `FileExistsError` where one
        was making it, copies fetched again. So the directory stays. The metadata file is read again first, so that a
        row another process has written since is swept as it is rather than missed. An empty snapshot expires no
        entry, and a snapshot with nothing expired in it is not written back. One with every entry expired is written
        back empty, which fsspec's does not do because it removes the directory.

        That removal was also the only thing that collected the files no row names (a blob whose row was lost, the
        `<blob>.<uuid>.tmp` of a fetch that was killed), so those are collected here: the ones older than the expiry
        and than an hour (`_remove_unclaimed_files`), which keeps the file of a fetch that is stalled but not dead.

        The sweep holds the lock file of the directory from the read to the last removal, so that no other process
        saves a row between the read and the write (GH-3485); one that cannot get it within the timeout leaves the
        sweep to the next process, which is what a sweep that did not run costs. A blob whose file was written within
        the expiry is not removed even where its row says it expired: a process that fetches again renames the new
        file onto the blob and saves the row under the same lock (`_open`), so the sweep sees both or neither, except
        where that process did not get the lock in time and went ahead without it, and the old row is then all the
        sweep can see. It is collected by a later sweep if no row comes to name it.
        """
        directory = Path(self.storage[-1])
        with _locked_across_processes(directory, otherwise="the sweep is skipped") as proceed:
            if not proceed:
                return
            self._check_cache()
            # what another process has written since this was read is part of what is swept, not lost to it
            _refresh_metadata(self)
            held = self._metadata.cached_files[-1]
            expiry = expiry_time or self.expiry
            # no expiry is no expiry, as `_check_file` reads it: fsspec's reads a zero as "all of it has expired"
            if not expiry:
                return
            if any(time.time() - _entry_time(detail) > expiry for detail in held.values()):
                # fsspec annotates the expiry an int; a float is compared the same
                expired_blobs, now_empty = self._metadata.clear_expired(expiry)  # ty: ignore[invalid-argument-type]
                written_since = time.time() - expiry
                for blob in expired_blobs:
                    if _written_after(Path(blob), written_since):
                        continue
                    # a blob another handle holds open is left to the next sweep (Windows: `PermissionError`)
                    with contextlib.suppress(OSError):
                        Path(blob).unlink(missing_ok=True)
                if now_empty:
                    # `clear_expired` writes the file only when something is left in it
                    self._metadata._save({}, str(directory / "cache"))  # noqa: SLF001
                self._cache_size = None
            _remove_unclaimed_files(directory, self._metadata.cached_files[-1], expiry)
            _drop_orphaned_sidecars(directory)

    def clear_cache(self) -> None:
        """Delete the directory, metadata file and all, and load the empty metadata back.

        Not skipped where the lock file is held past the timeout, because it was asked for. The lock file is beside
        the directory, so it is not deleted with it.
        """
        with _locked_across_processes(Path(self.storage[-1]), otherwise="the cache is cleared without it"):
            super().clear_cache()

    def _open(self, path: str, mode: str = "rb", **kwargs) -> object:  # noqa: ANN003
        """Open the cached copy of a file, fetching it first when the cache does not hold one.

        fsspec's own `_open` asks the remote filesystem whether the file `exists` before fetching
        it, and HTTP's `exists` answers `False` for any status of 400 or above and for a refused
        connection. A 503 or a server that is down then came back as the `FileNotFoundError` a
        404 raises, and `download_file` reported a missing file for a failure (GH-2467). Fetched
        straight away instead, the error is the one the download met: `FileNotFoundError` for a
        404, which HTTP's `get_file` raises itself, and the aiohttp error for anything else. A cache
        miss also costs one GET rather than two.

        The entry is recorded once the whole body has arrived, where fsspec records it first. A
        download that fails before the body neither refreshes an expired entry nor touches the blob
        behind it, and one that aiohttp sees cut short leaves no entry claiming a fresh copy of what
        it wrote for a retry to read back. The body is written to a file of its own and renamed onto
        the blob once whole, so a concurrent fetch of the same file never finds it half-written and
        a failed one removes what it wrote (GH-2493).

        The copy fetched is the one opened, rather than handing back to fsspec's `_open` to find it
        again: if it had gone in between, that would probe and record-first all over.
        """
        if "r" not in mode or "+" in mode:
            # writing goes through fsspec's own temporary file; wetterdienst only ever reads
            return super()._open(path, mode=mode, **kwargs)
        # the ceiling `download_file` was given, for the fetch below; the filesystem holds the default
        fetch_kwargs = {"max_bytes": kwargs.pop("max_bytes")} if "max_bytes" in kwargs else {}
        # the time (as `time.time()` has it) before which a copy is no longer the file: a copy made earlier is fetched
        # again, and is replaced only once the new one is whole, so that a fetch that fails leaves it where it was
        refetch_before = kwargs.pop("refetch_before", None)
        # a copy that no version which kept dates made (it has no record of one, not even of a missing date) is fetched
        # again, once: the new one has the record
        refetch_undated = kwargs.pop("refetch_undated", False)
        # that `download_file` has just asked `_check_file`, which reads the metadata file again where it finds no
        # usable copy: asking it again here would be the cost of a big directory a second time. Anyone else who opens
        # a file (the reader of a forecast does) has not asked
        checked = kwargs.pop("checked", False)
        path = self._strip_protocol(path)
        cached = super()._check_file(path) if checked else self._check_file(path, refetch_before)
        if cached and refetch_before is not None and cached[0]["time"] < refetch_before:
            cached = False
        if cached and refetch_undated and not _has_sidecar_record(Path(cached[1])):
            cached = False
        # where the date of what is read is left for `download_file` (`_take_last_modified`): on the filesystem this
        # one wraps, because an attribute of this one is not found where `__getattribute__` answers for the wrapped
        registry = _last_modified_registry(self)
        if cached:
            _, blob = cached
            if registry is not None:
                _remember_last_modified(registry, path, _read_sidecar(Path(blob)))
        else:
            # inline rather than a helper method: this class's `__getattribute__` hands any method
            # name fsspec does not list to the wrapped filesystem, which has no such method.
            # `_mkcache` again, as fsspec does before its fetch: a sweep elsewhere may have removed
            # the directory since `_check_file` made it
            self._mkcache()
            blob = str(Path(self.storage[-1]) / self._mapper(path))
            # a file of its own beside the blob, renamed onto it once the body is whole: a fetch of
            # the same url in another thread or process never sees this one's half-written file,
            # and a body that fails part-way leaves nothing behind (GH-2493)
            temp = f"{blob}.{uuid.uuid4().hex}.tmp"
            # the copy is as old as its body is, which the server began to send when this was asked for: a body that
            # takes a while to arrive holds what the file was at the start of it, not at the end (fsspec stamps the
            # entry when the fetch is over)
            started = time.time()
            try:
                self.fs.get_file(path, temp, **fetch_kwargs)
                # the date this fetch brought, and the file as written, which is what names the blob it becomes
                last_modified = None if registry is None else registry.get(path)
                written = Path(temp).stat()
                # the rename onto the blob and the row that names it are one step for the lock file of the directory
                # (GH-3485): a sweep of another process that reads the old row between the two would delete the new
                # file, and the row saved next would then name nothing. The lock is for these two and not for the
                # download, which is over. Where it is not got in time the rename is done all the same, as before the
                # lock, and the sweep's check of the file's time is what protects it
                with _locked_across_processes(
                    Path(self.storage[-1]), otherwise="the rename and the row go ahead without it"
                ):
                    try:
                        os.replace(temp, blob)  # noqa: PTH105
                    except PermissionError:
                        # Windows refuses to replace a blob another handle holds open. That blob is a
                        # whole copy, put there by the same kind of rename, so it is left alone and
                        # this read is served from the file just fetched, in memory because that file
                        # cannot be removed while open. No entry is recorded: it would call the blob,
                        # which still holds the older copy, fresh, so the next read fetches again
                        log.debug(f"Could not replace {blob}, serving {path} from the fetched copy", exc_info=True)
                        # `open` has turned a text mode into a binary one by now and wraps the handle itself
                        return BytesIO(Path(temp).read_bytes())
                    # the record and its save as one step for the lock: a thread that reads the metadata file again
                    # replaces what the filesystem holds, and keeps the entries it held only after that, so one that
                    # came between the record and the line that sets its time would find the entry missing (a
                    # filesystem used by more than one thread: the reader of a forecast moves threads)
                    self._make_local_details(path)
                    self._metadata.cached_files[-1][path]["time"] = started
                    self.save_cache()
                # after the entry: a copy is dated once the cache holds it. Written whether or not this fetch had a
                # date, so that a copy fetched anew over an older one does not keep the older one's
                _write_sidecar(Path(blob), last_modified, written)
            finally:
                # best effort: an unlink that fails must not replace the bytes in hand or the error
                # the download met, which is what the caller's status and retry go by
                with contextlib.suppress(OSError):
                    Path(temp).unlink(missing_ok=True)
        return Path(blob).open(mode)


def _check_cache_dir_writable(cache_path: Path) -> None:
    """Make `cache_path` and write a file into it, which is removed again.

    fsspec makes the directory when it builds a caching filesystem and would only meet an unusable
    one at the first download, as a failed request; this meets it where it can be answered. Kept
    apart from the building, so that a fault of fsspec's own (loading the metadata file) is not
    taken for one of the directory.

    Raises:
        OSError: If `cache_path` cannot be created or written to.

    """
    make_private_dir(cache_path)
    with tempfile.TemporaryFile(dir=cache_path):
        pass


class NetworkFilesystemManager:
    """Manage multiple FSSPEC instances keyed by cache expiration time.

    Each thread gets its own set of filesystem instances to avoid thread-safety
    issues with WholeFileCacheFileSystem's in-memory metadata cache.
    """

    _thread_local: ClassVar[threading.local] = threading.local()

    @classmethod
    def _get_filesystems(cls) -> dict[str, HTTPFileSystem | WholeFileCacheFileSystem]:
        """Return the per-thread filesystem registry."""
        if not hasattr(cls._thread_local, "filesystems"):
            cls._thread_local.filesystems = {}
        return cls._thread_local.filesystems

    @staticmethod
    def _registry_key(
        cache_dir: Path,
        cache_expiry: CacheExpiry,
        client_kwargs: dict | None,
        *,
        cache_disable: bool,
        use_certifi: bool,
    ) -> str:
        """Name a filesystem by everything `register` builds it from.

        Everything, because `register` runs only for a key that is new -- so whatever the key
        leaves out, the first caller in a thread decides for every later one. `cache_dir`,
        `cache_disable` and `use_certifi` were all left out. `CacheExpiry.METAINDEX` being an alias
        of `TWELVE_HOURS`, any earlier metaindex download from any provider was enough to leave a
        caching filesystem under that key, and a later request made with caching disabled, or
        against a different `WD_CACHE_DIR`, was then served by it (GH-1947).

        This names the instance in memory and nothing on disk. Where the blobs live is
        `_cache_path`, and the two answer different questions: an instance is separated by
        everything it is *built* from, a blob only by what changes the bytes a server sends back.
        `use_certifi` and a timeout are the clearest case -- they decide how the request is made and
        nothing about what comes back, so they name an instance and must not name a directory.
        """
        ttl_name, _ = NetworkFilesystemManager.resolve_ttl(cache_expiry)
        parts = [
            # through `resolve_ttl`, as `_cache_path` reads it: the two agree today only because
            # that function returns the name verbatim, and a key that reads an input its own way is
            # how this drifted in the first place
            f"ttl-{ttl_name}",
            NetworkFilesystemManager._client_kwargs_suffix(client_kwargs),
            f"-dir-{hashlib.sha256(str(cache_dir).encode()).hexdigest()[:8]}",
            "-nocache" if cache_disable else "",
            "-certifi" if use_certifi else "",
        ]
        return "".join(parts)

    @staticmethod
    def _cache_path(cache_dir: Path, cache_expiry: CacheExpiry, client_kwargs: dict | None) -> Path:
        """Where the blobs for this TTL live.

        Separated by the TTL, and by *who is asking* -- never by how the asking is done. This used
        to hash the whole of `client_kwargs`, which mixes the two: an `Authorization` header decides
        what a server sends back, where a timeout, a proxy and a User-Agent decide nothing about it.
        The default User-Agent carries the version number, so the directory was renamed by every
        release and the cache re-downloaded from empty; nothing reads the old name again and, until
        `_reclaim_unreachable_cache_dirs`, nothing removed it either (GH-1959).
        """
        ttl_name, _ = NetworkFilesystemManager.resolve_ttl(cache_expiry)
        suffix = NetworkFilesystemManager._identity_suffix(client_kwargs)
        return Path(cache_dir) / "fsspec" / f"{_CACHE_LAYOUT_VERSION}-ttl-{ttl_name}{suffix}"

    @staticmethod
    def _client_kwargs_suffix(client_kwargs: dict | None) -> str:
        """Return a short stable hash suffix that distinguishes different client_kwargs.

        Through `_header_value`, one level in, so that two secrets do not hash alike: `str()` of a
        dict of `SecretStr` renders every one of them as `**********`. This key names the filesystem
        *instance*, and `register` runs only for a key that is new -- so a collision here hands the
        second caller the first caller's filesystem, built with the first caller's `Authorization`
        header (GH-1947). That is worse than the cache directory collision it also caused.
        """
        if not client_kwargs:
            return ""
        try:
            serialized = json.dumps(
                {key: _stable_repr(value) for key, value in sorted(client_kwargs.items())},
                sort_keys=True,
            )
            return "-" + hashlib.sha256(serialized.encode()).hexdigest()[:8]
        except Exception:  # noqa: BLE001
            return ""

    @staticmethod
    def _identity_suffix(client_kwargs: dict | None) -> str:
        """Name the credential these kwargs carry, and nothing else about them.

        Empty for an unauthenticated request, which is most of them: the DWD and every other open
        provider then share one directory per TTL whose name never moves. Two different API keys
        still get two directories, because a body fetched with one is not a body the other may be
        handed back.

        A credential that rotates -- Met Office mints a three-day JWT -- renames the directory with
        it, and the previous one is left holding blobs nothing will ask for again. Keying on the
        long-lived credential instead would spare that, but `Settings.auth` is not visible from
        here; so the cost is paid and then collected, by `_reclaim_unreachable_cache_dirs`, rather
        than left to accumulate. Sharing one directory between two keys is the one thing not on
        offer: every provider here authenticates rather than selects with its credential, but a
        cache is a bad place to bet on that staying true.
        """
        carried = _credential_headers(client_kwargs)
        if carried is None:
            # headers in a shape this cannot read. Never the shared directory: returning "" here
            # would file an authenticated body exactly where an unauthenticated request looks for
            # one. A directory of its own, the same one every time, is the safe answer
            return f"-{_UNREADABLE_IDENTITY}"
        varying = {name: value for name, value in carried.items() if name not in _CACHE_NEUTRAL_HEADERS}
        if not varying:
            return ""
        return "-" + hashlib.sha256(json.dumps(varying, sort_keys=True).encode()).hexdigest()[:8]

    @staticmethod
    def resolve_ttl(cache_expiry: CacheExpiry) -> tuple[str, float | int | Literal[False]]:
        """Resolve the cache expiration time.

        Args:
            cache_expiry: The cache expiration time.

        Returns:
            The cache expiration time as name and value.

        """
        return cache_expiry.name, cache_expiry.value

    @classmethod
    def register(
        cls,
        cache_dir: Path,
        cache_expiry: CacheExpiry = CacheExpiry.NO_CACHE,
        client_kwargs: dict | None = None,
        *,
        cache_disable: bool,
        use_certifi: bool = False,
    ) -> None:
        """Register a new filesystem instance for a given cache expiration time.

        Args:
            cache_dir: The cache directory to use for the filesystem.
            cache_expiry: The cache expiration time.
            client_kwargs: Additional keyword arguments for the client.
            cache_disable: If True, the cache is disabled.
            use_certifi: If True, use certifi certificate bundle instead of system certificates.

        Returns:
            None

        """
        _, ttl_value = cls.resolve_ttl(cache_expiry)
        key = cls._registry_key(
            cache_dir, cache_expiry, client_kwargs, cache_disable=cache_disable, use_certifi=use_certifi
        )
        fs = HTTPFileSystem(
            use_listings_cache=False,
            client_kwargs=client_kwargs,
            listings_expiry_time=0.0,  # not relevant for the download of files
            # inert while use_listings_cache is False, but keeps the listings cache out of the
            # platformdirs fallback location should it ever be enabled here
            listings_cache_location=cache_dir,
            use_certifi=use_certifi,
        )

        if cache_disable or cache_expiry == CacheExpiry.NO_CACHE:
            filesystem_effective = fs
        else:
            # the directory that failed once is not tried again: its stand-in is named from here on
            real_cache_dir = cls._cache_path(_effective_cache_dir(cache_dir), cache_expiry, client_kwargs)
            # built inside the lock, not merely tidied inside it: building reads this directory's
            # metadata file, and the sweep and the reclaim below delete metadata files. On POSIX an
            # unlink leaves an open handle readable and this was invisible; on Windows the builder
            # gets `PermissionError` from fsspec's `CacheMetadata._load`
            with _cache_dir_lock:
                try:
                    _check_cache_dir_writable(real_cache_dir)
                except _CACHE_DIR_ERRORS as error:
                    real_cache_dir = cls._cache_path(_fallback_cache_dir(cache_dir, error), cache_expiry, client_kwargs)
                    _check_cache_dir_writable(real_cache_dir)
                filesystem_effective = _LockedWholeFileCacheFileSystem(
                    fs=fs,
                    cache_storage=str(real_cache_dir),
                    expiry_time=int(ttl_value),
                )
                # the tidying is before the registry assignment below, and none of it able to raise: a
                # cache that cannot be tidied must still be a cache that can be read.
                #
                # The mark goes after the sweep. The order no longer matters much: the sweep used to remove the
                # whole directory and the marker with it (GH-3467), and a missing marker counts as a directory
                # just used (`_last_used`), so that was never the way a live cache was reclaimed
                _sweep_expired_blobs(filesystem_effective, real_cache_dir, ttl_value)
                _mark_cache_dir_used(real_cache_dir)
                _reclaim_unreachable_cache_dirs(real_cache_dir.parent, keep=real_cache_dir)
        cls._get_filesystems()[key] = filesystem_effective

    @classmethod
    def get(
        cls,
        cache_dir: Path,
        cache_expiry: CacheExpiry = CacheExpiry.NO_CACHE,
        client_kwargs: dict | None = None,
        *,
        cache_disable: bool,
        use_certifi: bool = False,
    ) -> HTTPFileSystem | WholeFileCacheFileSystem:
        """Get a filesystem instance for a given cache expiration time.

        Args:
            cache_dir: The cache directory to use for the filesystem.
            cache_expiry: The cache expiration time.
            client_kwargs: Additional keyword arguments for the client.
            cache_disable: If True, the cache is disabled
            use_certifi: If True, use certifi certificate bundle instead of system certificates.

        Returns:
            The filesystem instance.

        """
        key = cls._registry_key(
            cache_dir, cache_expiry, client_kwargs, cache_disable=cache_disable, use_certifi=use_certifi
        )
        if key not in cls._get_filesystems():
            cls.register(
                cache_dir=cache_dir,
                cache_expiry=cache_expiry,
                client_kwargs=client_kwargs,
                cache_disable=cache_disable,
                use_certifi=use_certifi,
            )
        return cls._get_filesystems()[key]


#: The ``reason`` of an ``ssl.SSLError`` that a server throws now and then and does not throw twice in a row.
#: Not ``SSLV3_ALERT_HANDSHAKE_FAILURE``: a server with no cipher in common, or one that wants a client
#: certificate, sends it on every attempt, and asking again only waits for the same answer.
_TRANSIENT_TLS_REASONS = frozenset(
    {
        # the peer answered the ClientHello with something that is no TLS: a load balancer or a web tier
        # that is restarting or overloaded
        "WRONG_VERSION_NUMBER",
        # a session-resumption ticket the server no longer honours
        "INVALID_SESSION_ID",
        # alerts that say the server failed, not that it refuses the client or its certificate
        "SSLV3_ALERT_UNEXPECTED_MESSAGE",
        "SSLV3_ALERT_BAD_RECORD_MAC",
        "TLSV1_ALERT_INTERNAL_ERROR",
    },
)


def _is_transient_tls_failure(error: BaseException) -> bool:
    """Whether a TLS failure is a handshake hiccup of the server, which asking again can get past (GH-3533).

    A failure that arrives as the aiohttp ``ClientSSLError`` is read by the ``ssl.SSLError`` underneath.
    What it says is decided by its type and its ``reason``, which OpenSSL sets, not by its message:

    - never a certificate that does not verify (``ssl.SSLCertVerificationError``, which is also
      ``ssl.CertificateError``): an untrusted, expired or self-signed certificate or a name that does not
      match is the same on every attempt, and it is a matter of configuration or of security that a retry
      must not mask (GH-2618);
    - an ``ssl.SSLError`` whose ``reason`` is one of ``_TRANSIENT_TLS_REASONS``: the web server of
      ``www.dwd.de`` throws ``WRONG_VERSION_NUMBER`` and ``INVALID_SESSION_ID`` now and then, and answers
      the same request a minute later;
    - a connection cut in the middle of the handshake (``ssl.SSLEOFError``) or closed by the peer
      (``ssl.SSLZeroReturnError``): a blip, as a dropped connection is. Through aiohttp and asyncio a server
      that closes after the ClientHello arrives as a ``ClientConnectorError`` with a ``ConnectionResetError``,
      which is asked again as a dropped connection, so on the paths of this library this branch is not
      reached; it stays as a guard for an ``ssl.SSLError`` that is let out as it is.

    Any other TLS failure is not asked for again: a protocol or a cipher the two cannot agree on (the
    ``SSLV3_ALERT_HANDSHAKE_FAILURE`` of a server with no cipher in common, or one that wants a client
    certificate) is a configuration, and so is a certificate the server refuses to accept.
    """
    if isinstance(error, ClientSSLError):
        error = error.os_error
    if isinstance(error, ssl.SSLCertVerificationError):
        return False
    if isinstance(error, (ssl.SSLEOFError, ssl.SSLZeroReturnError)):
        return True
    return isinstance(error, ssl.SSLError) and getattr(error, "reason", None) in _TRANSIENT_TLS_REASONS


def _worth_retrying(error: Exception) -> bool:
    """Whether a failed post is worth a second attempt.

    A response that arrived is an answer, and a 401 will not become a 200 by asking again -- unless
    the server said the fault was its own. A 502 or a 503 from a token endpoint is a blip, and the
    request that meets it is the one least able to afford failing: a token is minted once every
    three days, and a mint that fails empties a whole query rather than one file of it.

    A 429 is deliberately not retried. The endpoints that rate-limit are rate-limiting a free
    account, and asking again a tenth of a second later is how that gets worse rather than better;
    it comes back as the answer it is, for the caller to report.

    Nor is a TLS failure that is the same on every attempt: a certificate that does not verify, or a
    handshake the two cannot agree on. The same server presents the same certificate, so asking again
    returns the same error after a delay and a retry warning (GH-2618). A handshake that the server
    only fumbled -- a wrong version number, an invalid session id -- is a blip like
    any other and is asked again (``_is_transient_tls_failure``, GH-3533). aiohttp's ``ClientSSLError`` is
    a ``ClientConnectorError``, so it would pass the test for a failed connection below whatever it is;
    the listings raise the ``ssl.SSLError`` underneath, which is none of the exceptions below. Both are
    decided here.
    """
    if isinstance(error, (ClientSSLError, ssl.SSLError)):
        return _is_transient_tls_failure(error)
    # ClientPayloadError is a body that stopped arriving mid-read, which is the same kind of blip
    # as a connection that never carried one -- and it is no subclass of ClientConnectionError
    if isinstance(error, (ClientConnectionError, ClientPayloadError, FSTimeoutError, TimeoutError)):
        return True
    return isinstance(error, ClientResponseError) and error.status >= HTTPStatus.INTERNAL_SERVER_ERROR


def _worth_retrying_download(error: Exception) -> bool:
    """Whether a failed download is worth a second attempt.

    The same answer as for a post, plus the missing file fsspec raises for a 404 -- a file index is
    read minutes before the files it names are fetched, and a listing can race a publication either
    way, so a download asks once more before believing a file is not there.
    """
    return isinstance(error, FileNotFoundError) or _worth_retrying(error)


def _worth_retrying_listing(error: Exception) -> bool:
    """Whether a failed listing is worth another attempt: the same answer as for a post.

    A connection or a timeout that failed, a body that stopped arriving, a 5xx, a TLS handshake the
    server fumbled. Not a certificate that does not verify (see ``_worth_retrying``), and not what is
    no blip either: a directory that is not there (``FileNotFoundError``), a 4xx, or a programming
    error such as a ``ValueError``, all of which the retry used to repeat as it repeated every
    exception (GH-2618).
    """
    return _worth_retrying(error)


def _scrubbed_connector_error(error: ClientConnectorError) -> ClientConnectorError:
    """Return a connector error with nothing on it that leads to a proxy's credentials.

    The connection key loses the proxy's userinfo and ``proxy_auth``, the traceback goes, and that
    of ``os_error``: a refusing proxy's key names no credentials, so ``_without_proxy_credentials``
    leaves that error's frames alone, and their locals hold ``proxy_auth`` and the encoded
    ``Proxy-Authorization`` header. So does the chain. Plain offline errors lose theirs as well,
    which costs little: the message names the host, and ``os_error`` is still there (GH-2602).
    """
    failure = _without_proxy_credentials(error).with_traceback(None)
    failure.os_error.with_traceback(None)
    failure.__cause__ = None
    failure.__context__ = None
    return failure


def _bare_tls_failure(error: ClientSSLError) -> OSError:
    """Return the ``ssl.SSLError`` under an aiohttp TLS failure, with nothing on it that leads back to ``error``.

    The aiohttp error holds the connection key, which renders the password of a proxy named in
    ``HTTPS_PROXY``, and its traceback frames hold the request as locals. So the traceback is dropped
    and ``__cause__`` and ``__context__`` are cleared. The caller raises the result outside its
    ``except`` block, because raising in it would set ``error`` as ``__context__`` again.
    """
    failure = error.os_error.with_traceback(None)
    failure.__cause__ = None
    failure.__context__ = None
    return failure


#: How often a listing that failed in a way worth asking again is attempted in all.
_LISTING_ATTEMPTS = 3


_T = TypeVar("_T")


def _list_with_retries(list_once: Callable[[], _T], url: str) -> _T:
    """Attempt a listing as often as the policy says, and raise what is left as the error it is.

    The one place both listings go through (GH-3004). A failure the retry asks again for is raised once
    the attempts are used up:

    - a connection that could not be made (``ClientConnectorError``) is a ``NoInternetError``, naming
      the URL (GH-2640);
    - one the server cut or never finished -- a reset, a dropped connection, a body that stopped
      arriving, a timeout, a 5xx -- and an HTTP error status are a ``DownloadError`` naming the URL,
      with the failure as its ``__cause__``, as ``File.raise_if_exception`` raises them for a download
      (GH-2460). ``timed_out`` finds a timeout under it, so the REST API answers a 504 for it.

    A TLS failure -- a certificate that does not verify, a handshake that fails -- is a ``DownloadError``
    too, with the bare ``ssl.SSLError`` as its ``__cause__``, as it is for a download (GH-3099); the REST
    API answers a 502 for it, not a 500. A certificate failure is asked for once, and so is a handshake
    the two cannot agree on; a handshake the server fumbled (``_is_transient_tls_failure``, GH-3533) is
    asked for as often as a reset is.

    Not a ``FileNotFoundError``, which is asked for once and raised as it is, and not a programming
    error. What is raised is raised outside the ``except`` blocks below, so that the aiohttp error is
    no ``__context__`` of it: it holds the connection key, which renders the password of a proxy named
    in ``HTTPS_PROXY``.
    """
    offline: ClientConnectorError | None = None
    failed: Exception | None = None
    try:
        # a retry context rather than a `stamina.retry` decorator: the decorator hands the call's
        # arguments to stamina's retry hook, which attaches them to its log record as
        # `extra["stamina.kwargs"]` -- the live `Settings`, proxy password included, for a handler that
        # serialises a pydantic object by its fields (GH-2904). A context has no arguments to hand over.
        # The same policy as before: stamina's default time budget, `_LISTING_ATTEMPTS` attempts.
        for attempt in stamina.retry_context(on=_worth_retrying_listing, attempts=_LISTING_ATTEMPTS):
            with attempt:
                return list_once()
    except ClientConnectorError as e:
        offline = e
    except ssl.SSLError as e:
        # the listings raise the bare error under a ``ClientSSLError``; an ``ssl.SSLError`` that
        # fsspec lets out as it is takes the same way
        failed = e
    except Exception as e:
        if not (_worth_retrying_listing(e) or isinstance(e, (ClientResponseError, RedirectRefusedError))):
            raise
        failed = e
    if offline is not None:
        raise _no_internet_error(url, offline)
    if failed is not None:
        failure = _download_error(failed, url)
        failure.__cause__ = failed.with_traceback(None)
        raise failure
    msg = "unreachable"
    raise AssertionError(msg)


def list_remote_files_fsspec(
    url: str, settings: Settings, cache_expiry: CacheExpiry = CacheExpiry.FILEINDEX
) -> list[str]:
    """Create a listing of all files of a given path on the server.

    The default ttl with ``CacheExpiry.FILEINDEX`` is "5 minutes".

    Args:
        url: The URL to list files from.
        settings: The settings to use for the listing.
        cache_expiry: The cache expiration time.

    Returns:
        A list of all files on the server, or no files if the directory is not there

    Raises:
        NoInternetError: If no connection could be made after three attempts (no network, a DNS
            failure, a refusing host), naming the URL, the connection error as its ``__cause__``.
            A directory that is not there is an answer, `[]`; being offline is not (GH-2640).
        DownloadError: If the server answered badly: a connection reset or dropped, a timeout, a
            broken body, or an HTTP error status other than 404, naming the URL, the failure as its
            ``__cause__`` (GH-3004). A reset, a timeout, a broken body or a 5xx is asked for three
            times before it is raised, so is a TLS handshake the server fumbled (a wrong version
            number, an invalid session id, GH-3533); a 4xx once. A certificate that does not verify
            is raised at the first attempt, with the ``ssl.SSLError`` as its ``__cause__``: asking
            again would meet the same certificate (GH-3099).

    """
    return _list_with_retries(lambda: _list_files_once(url, settings, cache_expiry), url)


def _list_files_once(url: str, settings: Settings, cache_expiry: CacheExpiry) -> list[str]:
    """Attempt ``list_remote_files_fsspec`` once; the caller asks again where the policy says so."""
    shown = _without_url_secrets(url)
    use_cache = not (settings.cache_disable or cache_expiry is CacheExpiry.NO_CACHE)
    fs = HTTPFileSystem(
        use_listings_cache=use_cache,
        listings_expiry_time=not settings.cache_disable and cache_expiry.value,
        listings_cache_location=settings.cache_dir,
        client_kwargs=settings.fsspec_client_kwargs,
        use_certifi=settings.use_certifi,
    )
    try:
        # `find` walks with `on_error="omit"` by default, which catches `(FileNotFoundError,
        # OSError)` and returns nothing -- and aiohttp's `ClientOSError` is an `OSError`. So a
        # connection reset mid-walk was swallowed inside fsspec, never reached the retry wrapping
        # this call, and arrived at the caller as an empty directory would. Every provider that
        # lists then had to decide what an empty list meant, and none of them could (GH-1947).
        #
        # Raised instead, and the two told apart here: a directory that is not there is an answer,
        # and callers have always had it as `[]`; anything else is a failure to read, which a
        # caller should hear about rather than infer, after the retry around this where it can help
        return fs.find(url, on_error="raise")
    except FileNotFoundError:
        return []
    except ClientSSLError as e:
        # a certificate that does not verify, or a TLS protocol failure: the host answered, so this
        # is not being offline, and `[]` would hand the caller an empty directory with no hint of
        # why (see `download_file`, GH-2553). A subclass of `ClientConnectorError`, hence before it.
        # What is raised is the `ssl.SSLError` underneath, as a download stores it: the aiohttp
        # error holds the connection key, which renders the password of a proxy named in
        # `HTTPS_PROXY`, and its traceback frames hold the request as locals. Raised below, outside
        # this block, because raising in it would set the aiohttp error as `__context__`, which
        # `from None` hides from a printed traceback but not from anything that walks the chain
        log.info(f"Failed to list {shown}.")
        tls_failure = _bare_tls_failure(e)
    except ClientConnectorError as e:
        # being offline: a refusing proxy or host, a DNS failure, a reset during the connect. Not an
        # empty directory -- an offline library answered `[]`, which every caller then had to read
        # as a source with no files (GH-2640). Kept as the connector error, scrubbed of a proxy's
        # credentials, so that the retry around this asks again as it does for a download; the
        # caller turns what is left after the last attempt into a `NoInternetError`. Raised below,
        # outside this block, for the reason given above
        tls_failure = _scrubbed_connector_error(e)
    except ClientResponseError as e:
        # an HTTP error status. One that a proxy answered carries the `Proxy-Authorization` header
        # aiohttp built from its credentials in the request info, and the retry around this logs the repr
        # of whatever leaves here, so it is scrubbed before it does (GH-2603)
        raise _without_credentials(e, sent_credentials=False) from None
    # raised, and the retry around this asks again only where `_worth_retrying_listing` says it can
    # help: not for a certificate that does not verify, which is the same on every attempt (GH-2618)
    raise tls_failure


def list_remote_directory_fsspec(
    url: str, settings: Settings, cache_expiry: CacheExpiry = CacheExpiry.FILEINDEX
) -> list[dict]:
    """List the immediate contents (files and subdirectories) of a given path on the server, non-recursively.

    Unlike ``list_remote_files_fsspec``, this does not descend into subdirectories, which is useful for
    servers exposing a deeply nested directory tree where the folder names themselves carry enough
    information (e.g. a date range) to decide which subdirectories are actually worth descending into.

    Args:
        url: The URL to list the contents of.
        settings: The settings to use for the listing.
        cache_expiry: The cache expiration time.

    Returns:
        A list of fsspec detail dicts (with "name" and "type" keys, among others) for each entry.

    Raises:
        NoInternetError: If no connection could be made after three attempts, as for
            ``list_remote_files_fsspec`` (GH-2640).
        DownloadError: If the server answered badly or a TLS check failed, as for
            ``list_remote_files_fsspec`` (GH-3004, GH-3099).
        FileNotFoundError: If the directory is not there. Unlike ``list_remote_files_fsspec``, this
            does not return no entries. A missing directory is asked for once.

    """
    return _list_with_retries(lambda: _list_directory_once(url, settings, cache_expiry), url)


def _list_directory_once(url: str, settings: Settings, cache_expiry: CacheExpiry) -> list[dict]:
    """Attempt ``list_remote_directory_fsspec`` once; the caller asks again where the policy says so."""
    shown = _without_url_secrets(url)
    use_cache = not (settings.cache_disable or cache_expiry is CacheExpiry.NO_CACHE)
    fs = HTTPFileSystem(
        use_listings_cache=use_cache,
        listings_expiry_time=not settings.cache_disable and cache_expiry.value,
        listings_cache_location=settings.cache_dir,
        client_kwargs=settings.fsspec_client_kwargs,
        use_certifi=settings.use_certifi,
    )
    failure: OSError
    try:
        return fs.ls(url, detail=True)
    except ClientSSLError as e:
        # as in `list_remote_files_fsspec`: the host answered, so a failing certificate or handshake
        # is raised as the bare `ssl.SSLError` underneath rather than let out as the aiohttp error,
        # whose repr renders the password of a proxy named in `HTTPS_PROXY`. Raised below, outside this
        # block, so `e` is not its `__context__`
        log.info(f"Failed to list {shown}.")
        failure = _bare_tls_failure(e)
    except ClientConnectorError as e:
        # any other connector failure -- a refusing proxy, a DNS failure, a reset during the connect --
        # keeps its type for the retry around this, which treats it as any failure to read, and the
        # caller turns what is left after the last attempt into a `NoInternetError`. Scrubbed of a
        # proxy's credentials (GH-2602). Raised below for the same reason as above
        failure = _scrubbed_connector_error(e)
    except ClientResponseError as e:
        # an HTTP error status, scrubbed as in `list_remote_files_fsspec` (GH-2603)
        raise _without_credentials(e, sent_credentials=False) from None
    # raised, and the retry around this asks again only where `_worth_retrying_listing` says it can
    # help: not for a certificate that does not verify, which is the same on every attempt (GH-2618)
    raise failure


#: How long a probe of a provider's credentials may take in all, connecting and reading the answer.
#: A probe is asked while someone waits for a page, so it gives up where a download that is going to
#: be read would not (GH-2564). A total, which a numeric client timeout is not (it bounds each
#: silence, GH-2258): the answer to a probe is a few hundred bytes, so there is no slow link to fail.
PROBE_TIMEOUT_SECONDS = 5
PROBE_TIMEOUT = ClientTimeout(total=PROBE_TIMEOUT_SECONDS)


def download_file(
    url: str,
    cache_dir: Path,
    ttl: CacheExpiry = CacheExpiry.NO_CACHE,
    client_kwargs: dict | None = None,
    *,
    cache_disable: bool = False,
    use_certifi: bool = False,
    attempts: int = 2,
    max_bytes: int | None = None,
    refetch_before: float | None = None,
    refetch_undated: bool = False,
) -> File:
    """Download a specified file from the server.

    A body is taken up to `MAX_DOWNLOAD_BYTES` and a download up to `MAX_DOWNLOAD_SECONDS` in all. One that
    runs past either is refused, and is stored as the failure of the download: a `DownloadError` for the
    caller of `File.raise_if_exception`, which is not asked for again. A body that is compressed while the
    name of the file does not say so is refused too, as whatever reads it as a table would inflate it
    without a ceiling.

    Args:
        url: The URL of the file to download.
        cache_dir: The cache directory to use for the filesystem.
        ttl: The cache expiration time.
        client_kwargs: Additional keyword arguments for the client.
        cache_disable: If True, the cache is disabled.
        use_certifi: If True, use certifi certificate bundle instead of system certificates.
        attempts: How often a failure worth retrying is tried. One is a download that is not asked
            again, which a check of a credential wants: it is a question about now, and an answer
            late is worth no more than none.
        max_bytes: The most the body may be, `MAX_DOWNLOAD_BYTES` if not given. A body held in the cache is
            returned as it is, whatever its size: the ceiling is for what is fetched.
        refetch_before: A time, as `time.time()` has it, before which a copy held in the cache is fetched again, for a
            file that is known to have changed since. The copy stays where it is until the new one has arrived, so a
            download that fails is a failure and the copy is still held for a call without this to be served from.
        refetch_undated: Whether a copy that no version which kept the date of a download (`File.last_modified`) made is
            fetched again, once. Such a copy has no record of its date beside it, not even of a missing one, where a
            copy made since has one, so the new copy is held for good. Held in the same way as for `refetch_before`.

    Returns:
        A BytesIO object containing the downloaded file.

    """
    filesystem = NetworkFilesystemManager.get(
        cache_dir=cache_dir,
        cache_expiry=ttl,
        client_kwargs=client_kwargs,
        cache_disable=cache_disable,
        use_certifi=use_certifi,
    )
    # the "about to" marker the info line below used to be, kept at debug because the info line now
    # waits until it knows which it is. Something has to name the url before the cache probe runs:
    # `_mkcache` can raise on a read-only cache dir, no handler below catches that, and for a
    # credentialed request `_without_credentials` drops the traceback -- so without this the caller
    # gets a `PermissionError` naming neither the file nor the request
    # a url is logged without its query: a pre-signed one carries its signature there (GH-3341)
    shown = _without_url_secrets(url)
    log.debug(f"Fetching file {shown}")
    # knmi sends its API key, metno frost its basic auth and metoffice its bearer token this way,
    # and aiohttp merges those headers into the request info it hangs on an error
    sent_credentials = _sends_credentials(client_kwargs)
    try:
        # a 429 is not asked again: the providers that rate-limit are rate-limiting a free
        # account, and a second request a tenth of a second later is how that gets worse. What is
        # worth asking twice, `_worth_retrying_download` says, and it says the same as a post does.
        # Two attempts and no time budget: stamina's default of 45 seconds would deny the second
        # attempt to a download that streamed for longer than that before failing, and a numeric
        # timeout no longer ends an attempt after that many seconds (GH-2258)
        for attempt in stamina.retry_context(on=_worth_retrying_download, attempts=attempts, timeout=None):
            with attempt:
                try:
                    # asked per attempt and before the read, because reading is what populates the
                    # cache -- and because an attempt that re-downloads after a cached read failed
                    # must not inherit the first attempt's answer. `_check_file` is how
                    # `WholeFileCacheFileSystem` says whether it holds an unexpired copy; a plain
                    # filesystem has no such question and always says no.
                    #
                    # Inside the `try`, because it reaches the disk: `_mkcache` can raise on a
                    # read-only or full cache dir and the metadata load on a truncated file, and an
                    # exception escaping here carries a traceback whose frame holds `client_kwargs`
                    # -- the Authorization header -- which is exactly what the handler below drops
                    held = (
                        filesystem._check_file(url, refetch_before)  # noqa: SLF001
                        if isinstance(filesystem, _LockedWholeFileCacheFileSystem)
                        else getattr(filesystem, "_check_file", lambda _url: False)(url)
                    )
                    served_from_cache = (
                        bool(held)
                        and not (refetch_before is not None and held[0]["time"] < refetch_before)
                        and not (refetch_undated and not _has_sidecar_record(Path(held[1])))
                    )
                    # said after the probe rather than before it, because before it this could only
                    # guess -- and it guessed "Downloading" for every cache hit, which is the one
                    # thing a reader of the log could already tell was not happening. Said per
                    # attempt, so a retry that goes to the network after a cached read failed reads
                    # as the two different things it is
                    log.info(
                        f"Reading file {shown} from cache" if served_from_cache else f"Downloading file {shown}",
                    )
                    fetch_kwargs: dict[str, float] = {} if max_bytes is None else {"max_bytes": max_bytes}
                    if isinstance(filesystem, _LockedWholeFileCacheFileSystem):
                        fetch_kwargs["checked"] = True
                    if refetch_before is not None and isinstance(filesystem, WholeFileCacheFileSystem):
                        fetch_kwargs["refetch_before"] = refetch_before
                    if refetch_undated and isinstance(filesystem, WholeFileCacheFileSystem):
                        fetch_kwargs["refetch_undated"] = True
                    payload = filesystem.cat_file(url, **fetch_kwargs)
                    _refuse_unannounced_compression(url, payload)
                except Exception as e:  # noqa: BLE001 -- re-raised, never swallowed
                    # scrubbed here as well as on the way out, because stamina's retry hook logs
                    # ``repr(caused_by)`` on the first failure -- and that repr renders the request
                    # info, header and all, before any of the handlers below are reached
                    raise _without_credentials(e, sent_credentials=sent_credentials) from None
                log.info(f"Read file {shown} from cache" if served_from_cache else f"Downloaded file {shown}")
                copy = _held_in_view(filesystem, url)
                return File(
                    url=url,
                    content=BytesIO(payload),
                    status=200,
                    from_cache=served_from_cache,
                    last_modified=_take_last_modified(filesystem, url),
                    cached_at=float(copy[0]["time"]) if copy else None,
                )
    except Exception as e:
        failed = _failed_file(url, e, sent_credentials=sent_credentials)
        if failed is None:
            raise
        return failed
    msg = "unreachable"
    raise AssertionError(msg)


def _failed_file(url: str, error: Exception, *, sent_credentials: bool = False) -> File | None:
    """Say what a download that failed with ``error`` stores: the one place that tells a failure by its kind.

    The `File` a failed `download_file` returns, whose `raise_if_exception` raises the `NoInternetError` or
    `DownloadError` of it. A reader that fetches through fsspec itself and not through `download_file` (`KMLReader`)
    asks it too, so that the same failure is the same error whichever of them met it. None for what is no failed
    download: a programming error, which is raised as it is.
    """
    shown = _without_url_secrets(url)
    if isinstance(error, FileNotFoundError):
        log.info(f"Failed to download file {shown}.")
        return File(url=url, content=_without_credentials(error, sent_credentials=sent_credentials), status=404)
    if isinstance(error, FSTimeoutError):
        log.info(f"Failed to download file {shown}.")
        return File(url=url, content=_without_credentials(error, sent_credentials=sent_credentials), status=408)
    if isinstance(error, ClientSSLError):
        # a certificate that does not verify, or a TLS protocol failure such as an alert: the host
        # answered, so this is not being offline. (A connection the server drops mid-handshake is
        # a plain `ClientConnectorError` and stays the offline answer.) A subclass of
        # `ClientConnectorError`, hence before it. What is stored is the `ssl.SSLError` underneath,
        # not `e`: that holds the connection key, which renders the password of a proxy named in
        # `HTTPS_PROXY` in its repr. And it is stored without its traceback, whose frames hold the
        # request -- its headers and the proxy's credentials -- as locals
        log.info(f"Failed to download file {shown}.")
        return File(
            url=url,
            content=error.os_error.with_traceback(None),
            status=500,
        )
    if isinstance(error, ClientConnectorError):
        log.info(f"No internet connection while downloading file {shown}.")
        return File(url=url, content=_no_internet_error(url, error), status=503)
    if isinstance(error, ClientResponseError):
        log.info(f"Failed to download file {shown}.")
        return File(
            url=url,
            content=_without_credentials(error, sent_credentials=sent_credentials),
            status=error.status or 500,
        )
    if isinstance(error, ClientError):
        # ClientPayloadError among them, and every other aiohttp client failure -- a dropped
        # keep-alive connection (ServerDisconnectedError), a reset, too many redirects. Caught as
        # the base class so that none of them leaves by way of a traceback through this frame, where
        # the caller's client kwargs, credentials included, are a local
        log.info(f"Failed to download file {shown}.")
        return File(url=url, content=_without_credentials(error, sent_credentials=sent_credentials), status=500)
    if isinstance(error, TimeoutError):
        # the builtin one, which a whole-request timeout of the client raises as it is (`ServerTimeoutError`, a
        # `ClientError`, is the one above)
        log.info(f"Failed to download file {shown}.")
        return File(url=url, content=_without_credentials(error, sent_credentials=sent_credentials), status=408)
    return None


def cached_copy_is_held(
    url: str,
    cache_dir: Path,
    ttl: CacheExpiry = CacheExpiry.NO_CACHE,
    client_kwargs: dict | None = None,
    *,
    cache_disable: bool = False,
    use_certifi: bool = False,
) -> bool:
    """Tell whether the cache holds a copy of a url that a download with these arguments would serve.

    Takes the arguments the download was made with, because they name the cache it went to. False where nothing is
    cached (`NO_CACHE`, `cache_disable`) and where the cache cannot be read: never raises.
    """
    try:
        filesystem = NetworkFilesystemManager.get(
            cache_dir=cache_dir,
            cache_expiry=ttl,
            client_kwargs=client_kwargs,
            cache_disable=cache_disable,
            use_certifi=use_certifi,
        )
        return isinstance(filesystem, WholeFileCacheFileSystem) and bool(filesystem._check_file(url))  # noqa: SLF001
    except Exception:  # noqa: BLE001 -- best effort, a copy not seen is a download made
        return False


def drop_cached_file(
    url: str,
    cache_dir: Path,
    ttl: CacheExpiry = CacheExpiry.NO_CACHE,
    client_kwargs: dict | None = None,
    *,
    cache_disable: bool = False,
    use_certifi: bool = False,
) -> None:
    """Delete the copy `download_file` cached for a url, so that the next call asks the server again.

    For a download that arrived (status 200) but whose body the caller found to be a failure -- a
    provider that reports an error in the body of an HTTP 200. The cache holds such a body for the
    whole `ttl` like any other, and the caller would read the failure back without asking.

    Takes the arguments the download was made with, because they name the cache it went to: a
    different `ttl` or different `client_kwargs` is a different directory. Nothing happens when the
    download was not cached (`NO_CACHE`, `cache_disable`) or when nothing is held for the url. Only
    the cached copy is deleted: fsspec keeps the line in its metadata file, which no longer counts
    as a hit once the copy is gone.
    Never raises: a cache that cannot be written to has not kept the failure either.
    """
    try:
        filesystem = NetworkFilesystemManager.get(
            cache_dir=cache_dir,
            cache_expiry=ttl,
            client_kwargs=client_kwargs,
            cache_disable=cache_disable,
            use_certifi=use_certifi,
        )
        if not isinstance(filesystem, WholeFileCacheFileSystem):
            return
        filesystem.pop_from_cache(url)
    except Exception:  # noqa: BLE001 -- best effort, the entry expires on its own
        log.debug("Could not drop %s from the cache", _without_url_secrets(url), exc_info=False)


def cached_file_time(
    url: str,
    cache_dir: Path,
    ttl: CacheExpiry = CacheExpiry.NO_CACHE,
    client_kwargs: dict | None = None,
    *,
    cache_disable: bool = False,
    use_certifi: bool = False,
) -> float | None:
    """Tell when the copy `download_file` holds for a url was made, as `time.time()` has it; None where none is held.

    Takes the arguments the download was made with, as `drop_cached_file` does, since they name the cache. Read from
    the metadata file, merged into this thread's memory of it, where the file has changed: the copy was most likely
    made by another thread.
    Never raises: a cache that cannot be read holds no copy.
    """
    try:
        filesystem = NetworkFilesystemManager.get(
            cache_dir=cache_dir,
            cache_expiry=ttl,
            client_kwargs=client_kwargs,
            cache_disable=cache_disable,
            use_certifi=use_certifi,
        )
        if not isinstance(filesystem, WholeFileCacheFileSystem):
            return None
        _refresh_metadata(filesystem)
        held = _held_in_view(filesystem, url)
        return float(held[0]["time"]) if held else None
    except Exception:  # noqa: BLE001 -- best effort: no copy known is no date from it
        log.debug("Could not read the time of the copy of %s", _without_url_secrets(url), exc_info=False)
        return None


def _header_value(value: object) -> str:
    """Read a header value as the string it stands for, not as the string it prints as.

    `SecretStr` prints as `**********`, and `Settings.auth` has held credentials as `SecretStr`
    since GH-1937. So `str()` alone maps every secret to one value: two API keys would hash alike
    and share a blob directory, which is the one thing separating on a credential exists to stop.
    """
    reveal = getattr(value, "get_secret_value", None)
    return str(reveal() if callable(reveal) else value)


def _stable_repr(value: object) -> object:
    """Render one client-kwargs value for hashing, reading a mapping's own values properly.

    `headers` is the mapping that matters: rendered with `str()` as a whole, a dict of `SecretStr`
    is a string of masks and two different credentials are one value.
    """
    items = getattr(value, "items", None)
    if callable(items):
        return {str(name): _header_value(item) for name, item in items()}
    return _header_value(value)


def _sends_credentials(client_kwargs: dict | None) -> bool:
    """Whether these client kwargs carry a credential in a header.

    Headers this cannot read count as carrying one: scrubbing a failure that held no credential
    costs a traceback, where not scrubbing one that did puts the header in a log.
    """
    carried = _credential_headers(client_kwargs)
    if carried is None:
        return True
    return any(name in _CREDENTIAL_HEADERS for name in carried)


def _without_credentials(error: _E, *, sent_credentials: bool) -> _E:
    """Keep the credential of an authenticated request out of the error it produced.

    Two places hold it, neither of them ``str(error)`` -- which is what makes it easy to miss:

    - the request info aiohttp hangs on a ``ClientResponseError``, and on its ``args``, which is
      what a ``repr`` renders, and
    - the traceback, whose frames in this module have the header, its encoding and the caller's
      client kwargs as locals. That is what ``pytest --showlocals`` prints and what an error
      reporter capturing frame locals sends.

    The error is handed back to a caller to log, raise or store, so both are dealt with before it
    travels. The query of the URL it names goes too, wherever the error renders it
    (`_without_url_queries`). The traceback is dropped only for a request that carried credentials: for every other
    one it is worth more than it costs.

    A third place is the connection key of a ``ClientConnectorError``, which holds the password of
    a proxy. That one is scrubbed whatever ``sent_credentials`` says: it is not a header the caller
    passed, and a proxy named in ``HTTPS_PROXY`` is read by aiohttp where this cannot see it. The
    same goes for a credential header that aiohttp adds to the request info of a response error
    itself (``Proxy-Authorization`` on a ``ClientHttpProxyError``, or on a 5xx from an ``http://``
    target behind a proxy; ``Authorization`` from an ``auth=`` or the userinfo of the target): a
    response error whose request info holds one is scrubbed, and its traceback dropped, whatever
    ``sent_credentials`` says (GH-2592).
    """
    error = _without_url_queries(error)
    if isinstance(error, ClientConnectorError):
        error = _without_proxy_credentials(error)
    if sent_credentials:
        error = error.with_traceback(None)
    # only a response error carries request info; a timeout or a dropped connection has none, and
    # for those the traceback was the whole of the exposure
    if not isinstance(error, ClientResponseError):
        return error
    request_info = error.request_info
    if request_info is None:
        return error
    carried = [name for name in request_info.headers if str(name).lower() in _CREDENTIAL_HEADERS]
    if not carried:
        return error
    # kept for a failure with nothing to scrub; here its frames hold the request, header included
    error = error.with_traceback(None)
    headers = request_info.headers.copy()
    for name in carried:
        # assignment replaces every entry of that name rather than adding one
        headers[name] = "<redacted>"
    # rebuilt as the same (immutable) mapping type the request info was given, without naming it.
    # The userinfo goes from the urls too: for a CONNECT the real url is the proxy's, password included
    scrubbed = request_info._replace(
        headers=type(request_info.headers)(headers),
        url=request_info.url.with_user(None),
        real_url=request_info.real_url.with_user(None),
    )
    error.request_info = scrubbed
    # the history is the responses of a redirect chain, each holding its own copy of the request and
    # so of the header. Dropped rather than rebuilt: what a redirected request has to say is that it
    # was redirected, which the status already says, and ClientResponse keeps its request info
    # behind a property with no setter
    error.history = ()
    # aiohttp builds args as (request_info, history); rewritten only where that still holds, rather
    # than assuming the first element of any subclass's args is the request info
    if error.args and error.args[0] is request_info:
        error.args = (scrubbed, (), *error.args[2:])
    return error


def _without_proxy_credentials(error: _C) -> _C:
    """Strip the proxy's userinfo and ``proxy_auth`` from the connection key of a connector error.

    aiohttp raises ``ClientConnectorError(connection_key, os_error)``, so the key is in its ``args``
    and an exception's ``repr`` renders them: ``proxy_auth=BasicAuth(login=..., password=...)``,
    and ``proxy`` as a URL that keeps the ``user:secret@`` it was given. Stamina logs that repr on
    the first failure of a retried download or post, at WARNING (GH-2582).

    Rewritten in place, as the request info of a response error is, because the subclasses
    (``ClientConnectorCertificateError`` among them) are built from differing arguments. A key that
    names no proxy credentials is left alone, traceback included. One that does loses its
    traceback, whose frames hold that key as a local.
    """
    key = getattr(error, "_conn_key", None)
    if not isinstance(key, ConnectionKey):
        return error
    proxy = key.proxy
    if key.proxy_auth is None and (proxy is None or (proxy.user is None and proxy.password is None)):
        return error
    scrubbed = key._replace(
        proxy=None if proxy is None else proxy.with_user(None),  # also drops the password
        proxy_auth=None,
    )
    error._conn_key = scrubbed  # noqa: SLF001
    if error.args and error.args[0] is key:
        error.args = (scrubbed, *error.args[1:])
    return error.with_traceback(None)


# How long a post waits on a silent server when the caller's ``client_kwargs`` does not say.
# Settings carries a default of the same length, so this stands in only for a caller that passes
# none at all -- who would otherwise get aiohttp's own, five minutes for the whole request.
_POST_TIMEOUT_SECONDS = 30.0


def post_file(
    url: str,
    *,
    auth: tuple[str, str] | None = None,
    client_kwargs: dict | None = None,
    use_certifi: bool = False,
) -> File:
    """Post to a URL and return the response body.

    The download path cannot express this: ``download_file`` is a GET through a caching filesystem,
    where minting a token is a POST whose answer must never be cached. It still goes through
    fsspec's HTTP filesystem -- its event loop, its aiohttp session, its SSL handling and the
    caller's client settings -- so one HTTP stack serves every request the package makes rather
    than a second client being carried for one of them.

    Failures come back as a ``File`` carrying the exception and a status, the same shape
    ``download_file`` returns them in, so a caller decides what a failed exchange means rather than
    having an exception thrown through it. A redirect is not followed and arrives as itself, so a
    caller that expected a body should read ``File.status`` before the content.

    A request that fails the way a server does -- a 5xx, a dropped connection, a body that stops
    arriving -- is made a second time, which assumes the post is one that may safely be made twice.
    That holds for asking an endpoint for a token, which is what this exists for; a post that
    *changes* something at the other end wants a caller that knows a 500 may arrive after the change
    was applied.

    Args:
        url: The URL to post to.
        auth: Username and password for HTTP basic auth, if the endpoint wants them.
        client_kwargs: Additional keyword arguments for the client, ``timeout`` among them.
        use_certifi: If True, use certifi certificate bundle instead of system certificates.

    Returns:
        A File holding the response body, or the exception that stopped it.

    """
    filesystem = HTTPFileSystem(
        use_listings_cache=False,
        listings_expiry_time=0,
        use_certifi=use_certifi,
        # a default for a caller that set none, rather than an argument of its own: every caller
        # here passes ``Settings.fsspec_client_kwargs``, which always carries a timeout, so a
        # separate parameter could be passed and never take effect
        client_kwargs={"timeout": _POST_TIMEOUT_SECONDS, **(client_kwargs or {})},
    )
    # RFC 7617 by hand rather than through aiohttp: its ``BasicAuth`` and the ``auth=`` parameter are
    # both deprecated for removal in aiohttp 4, and its replacement (``encode_basic_auth``) is newer
    # than the aiohttp any given install carries. Sent per request, so credentials never reach
    # ``client_kwargs`` -- which is hashed into the filesystem cache key.
    headers = None
    if auth:
        headers = {"Authorization": f"Basic {base64.b64encode(':'.join(auth).encode()).decode('ascii')}"}
    sent_credentials = headers is not None or _sends_credentials(client_kwargs)

    async def _post() -> tuple[int, bytes]:
        session = await filesystem.set_session()
        # A POST is not repeated as a POST across a redirect: aiohttp would follow it as a GET and
        # answer with whatever that returned -- an HTML login page reads as a 200 with an
        # unparseable body, where the 302 says plainly what happened. So the redirect is the answer.
        async with session.post(url, headers=headers, allow_redirects=False) as response:
            response.raise_for_status()
            return response.status, await response.read()

    shown = _without_url_secrets(url)
    log.info(f"Posting to {shown}")
    try:
        # fsspec keeps one filesystem instance -- and so one aiohttp session and its keep-alive
        # pool -- for the life of the process, where a token is minted days apart. The first attempt
        # can therefore pick a pooled connection the server closed hours ago, which the second gets
        # to retry on a fresh one. What else is worth asking twice, `_worth_retrying` says. No time
        # budget, as for a download: a numeric timeout bounds connecting and each silence, not the
        # attempt, so one can outlast stamina's default of 45 seconds and leave no room (GH-2258)
        for attempt in stamina.retry_context(on=_worth_retrying, attempts=2, timeout=None):
            with attempt:
                try:
                    status, payload = sync(filesystem.loop, _post)
                except Exception as e:  # noqa: BLE001 -- re-raised, never swallowed
                    # load-bearing, not belt and braces: stamina's retry hook logs
                    # ``repr(caused_by)``, which renders an aiohttp error's request info -- and a
                    # 5xx is retried here, so that repr is of an error carrying the Authorization
                    # header this function just built. This is the only thing keeping it out of the
                    # retry log
                    raise _without_credentials(e, sent_credentials=sent_credentials) from None
                log.info(f"Posted to {shown}")
                return File(url=url, content=BytesIO(payload), status=status)
        msg = "unreachable"
        raise AssertionError(msg)
    except ClientResponseError as e:
        log.info(f"Failed to post to {shown}.")
        return File(url=url, content=_without_credentials(e, sent_credentials=sent_credentials), status=e.status or 500)
    except ClientSSLError as e:
        # not being offline, and stored as the error underneath: see `download_file`
        log.info(f"Failed to post to {shown}.")
        return File(
            url=url,
            content=e.os_error.with_traceback(None),
            status=500,
        )
    except ClientConnectorError as e:
        log.info(f"No internet connection while posting to {shown}.")
        return File(url=url, content=_no_internet_error(url, e), status=503)
    except (FSTimeoutError, TimeoutError) as e:
        log.info(f"Failed to post to {shown}.")
        return File(url=url, content=_without_credentials(e, sent_credentials=sent_credentials), status=408)
    except ClientError as e:
        # every other aiohttp client failure -- a dropped keep-alive connection
        # (ServerDisconnectedError), a reset, a broken payload. Caught as the base class rather than
        # named one by one, because the promise made above is that a failure comes back as a File.
        log.info(f"Failed to post to {shown}.")
        return File(url=url, content=_without_credentials(e, sent_credentials=sent_credentials), status=500)


def download_files(
    urls: list[str],
    cache_dir: Path,
    ttl: CacheExpiry = CacheExpiry.NO_CACHE,
    client_kwargs: dict | None = None,
    *,
    cache_disable: bool = False,
    use_certifi: bool = False,
    refetch_before: Mapping[str, float] | None = None,
) -> list[File]:
    """Download multiple files from the server concurrently.

    `refetch_before` names, by url, the time before which the copy held of a file is fetched again (`download_file`).
    """
    noun = "file" if len(urls) == 1 else "files"
    # what is wanted, not what will happen: which of these the cache answers is not known until each
    # one has been asked, and the line below says it once they all have
    log.info(f"Fetching {len(urls)} {noun}.")
    with ThreadPoolExecutor() as p:
        files = list(
            p.map(
                lambda file: download_file(
                    url=file,
                    cache_dir=cache_dir,
                    ttl=ttl,
                    client_kwargs=client_kwargs,
                    cache_disable=cache_disable,
                    use_certifi=use_certifi,
                    refetch_before=(refetch_before or {}).get(file),
                ),
                urls,
            ),
        )
    # a failure comes back as a `File` carrying the exception rather than raising, so counting the
    # list as fetched would say three files arrived where three 404s did -- the same untrue thing
    # this line exists to stop saying one level down
    failed = sum(1 for file in files if isinstance(file.content, Exception))
    arrived = len(files) - failed
    counted = f"{arrived} of {len(files)} {noun}" if failed else f"{len(files)} {noun}"
    # and the cache is only worth a count where there was one: this is the only caller that passes
    # `NO_CACHE`, and "0 from cache" there reads as "the cache held none of them" rather than as
    # "nothing was going to be cached"
    if cache_disable or ttl is CacheExpiry.NO_CACHE:
        log.info(f"Fetched {counted}, uncached.")
    else:
        cached = sum(1 for file in files if file.from_cache)
        log.info(f"Fetched {counted}, {cached} from cache.")
    return files
