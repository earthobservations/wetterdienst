# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Where a request may be led to: the links an answer names, and the redirects that are followed (GH-3338, GH-3339)."""

from __future__ import annotations

import asyncio
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest
from multidict import CIMultiDict

from tests.conftest import skip_if_upstream_unavailable
from wetterdienst.exceptions import DownloadError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.settings import Settings
from wetterdienst.ui.core import failure_status
from wetterdienst.util.network import (
    HTTPFileSystem,
    RedirectRefusedError,
    UpstreamMaintenanceError,
    _check_redirect,
    download_file,
    fetchable_link,
    list_remote_files_fsspec,
)
from wetterdienst.util.provider_hosts import PROVIDER_HOSTS

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

#: a made-up key, sent the way AEMET sends its own
KEY = "FAKEKEY123"


class _Handler(BaseHTTPRequestHandler):
    """Answer `/redirect?to=<url>` with a 302, `/dir/` with a listing, and anything else with the headers it got."""

    def log_message(self, *args: object) -> None:
        pass

    def do_GET(self) -> None:
        server: _Server = self.server  # ty: ignore[invalid-assignment]
        server.seen.append({name.lower(): value for name, value in self.headers.items()})
        if self.path.startswith("/redirect?to="):
            self.send_response(302)
            self.send_header("Location", self.path.removeprefix("/redirect?to="))
            self.send_header("Content-Length", "0")
            self.end_headers()
            return
        if self.path == "/dir/":
            body = (
                b'<a href="/dir/inside.zip">in</a> <a href="http://127.0.0.1:%d/dir/swapped.zip">swapped</a>'
                % self.server.server_port
            )
        else:
            body = json.dumps(dict(self.headers.items())).encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html" if self.path == "/dir/" else "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class _Server(ThreadingHTTPServer):
    seen: list[dict[str, str]]


@pytest.fixture
def two_servers() -> Iterator[tuple[_Server, _Server]]:
    """Run two servers on one host and different ports: two origins of one host family."""
    servers = [_Server(("127.0.0.1", 0), _Handler) for _ in range(2)]
    threads = [threading.Thread(target=server.serve_forever, daemon=True) for server in servers]
    for server, thread in zip(servers, threads, strict=True):
        server.seen = []
        thread.start()
    try:
        yield servers[0], servers[1]
    finally:
        for server, thread in zip(servers, threads, strict=True):
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)


def _fetch(url: str, tmp_path: Path, headers: dict[str, str]) -> tuple[int, bytes | Exception]:
    file = download_file(url, tmp_path, CacheExpiry.NO_CACHE, client_kwargs={"headers": headers}, attempts=1)
    return file.status, file.content if isinstance(file.content, Exception) else file.content.read()


def test_a_key_in_a_header_of_any_name_does_not_follow_a_redirect_to_another_origin(
    two_servers: tuple[_Server, _Server], tmp_path: Path
) -> None:
    """AEMET's `api_key` is dropped where the origin changes, as aiohttp drops `Authorization`; other headers stay."""
    first, second = two_servers
    headers = {"api_key": KEY, "x-api-key": KEY, "Authorization": KEY, "Cookie": f"k={KEY}", "Accept-Language": "de"}
    url = f"http://127.0.0.1:{first.server_port}/redirect?to=http://127.0.0.1:{second.server_port}/final"
    status, body = _fetch(url, tmp_path, headers)
    assert status == 200
    assert "Accept-Language" in json.loads(body)
    assert first.seen[0]["api_key"] == KEY
    assert len(second.seen) == 1
    assert not {"api_key", "x-api-key", "authorization", "cookie"} & second.seen[0].keys()
    assert second.seen[0]["accept-language"] == "de"


def test_a_key_is_kept_by_a_redirect_within_one_origin(two_servers: tuple[_Server, _Server], tmp_path: Path) -> None:
    """A redirect to another path of the same origin is still asked with the key: the stripping is for origins."""
    first, _ = two_servers
    url = f"http://127.0.0.1:{first.server_port}/redirect?to=/final"
    status, _body = _fetch(url, tmp_path, {"api_key": KEY})
    assert status == 200
    assert [seen["api_key"] for seen in first.seen] == [KEY, KEY]


def test_a_redirect_to_another_host_is_not_followed(two_servers: tuple[_Server, _Server], tmp_path: Path) -> None:
    """A redirect to a host that is not of the requested one's family is refused, and the host is never asked."""
    first, second = two_servers
    url = f"http://127.0.0.1:{first.server_port}/redirect?to=http://localhost:{second.server_port}/final"
    status, content = _fetch(url, tmp_path, {})
    assert status == 500
    assert isinstance(content, RedirectRefusedError)
    assert second.seen == []
    assert "(localhost)" in str(content)


def test_a_redirect_that_the_download_met_is_a_download_error(
    two_servers: tuple[_Server, _Server], tmp_path: Path
) -> None:
    """A refused redirect comes out of `raise_if_exception` as the `DownloadError` of the file."""
    first, second = two_servers
    url = f"http://127.0.0.1:{first.server_port}/redirect?to=http://localhost:{second.server_port}/final"
    file = download_file(url, tmp_path, CacheExpiry.NO_CACHE, attempts=1)
    with pytest.raises(DownloadError):
        file.raise_if_exception()


def _redirect(url: str, location: str) -> SimpleNamespace:
    return SimpleNamespace(url=url, headers={"Location": location})


@pytest.mark.parametrize(
    "headers", [{}, {"Accept": "*/*"}, {"api_key": KEY}, {"Authorization": KEY}, {"Cookie": "k=v"}]
)
def test_a_step_down_from_https_to_http_is_refused_for_every_request(headers: dict[str, str]) -> None:
    """Https never steps down to http, with a credential or without one; the hop is named by host, not by query."""
    with pytest.raises(RedirectRefusedError, match=r"https to http \(opendata.example.es\)") as refused:
        _check_redirect(
            _redirect("https://opendata.example.es/a", "http://opendata.example.es/b?sig=secret"),  # ty: ignore[invalid-argument-type]
            headers,
            "https://opendata.example.es/a",
        )
    assert not isinstance(refused.value, UpstreamMaintenanceError)
    assert "secret" not in str(refused.value)


def test_a_step_down_from_https_to_http_inside_the_family_is_refused() -> None:
    """The family of the first request is no licence for the step: a chain through http is refused at its hop."""
    first = "https://www.example.fr/api/1/datasets/r/abc"
    with pytest.raises(RedirectRefusedError, match=r"https to http \(static.example.fr\)"):
        _check_redirect(_redirect(first, "http://static.example.fr/resources/x.csv"), {}, first)  # ty: ignore[invalid-argument-type]


def test_a_chain_stays_in_the_family_of_the_first_request() -> None:
    """The next hop to another domain is refused, whatever the scheme the chain is on."""
    first = "https://www.example.fr/api/1/datasets/r/abc"
    with pytest.raises(RedirectRefusedError, match=r"another host \(evil.example.net\)"):
        _check_redirect(
            _redirect("http://static.example.fr/x", "http://evil.example.net/x"),  # ty: ignore[invalid-argument-type]
            {},
            first,
        )
    with pytest.raises(RedirectRefusedError, match="another host"):
        _check_redirect(_redirect(first, "https://evil.example.net/x"), {}, first)  # ty: ignore[invalid-argument-type]


@pytest.mark.parametrize(
    ("location", "kept"),
    [
        ("/b", True),
        ("https://opendata.example.es/b", True),
        ("https://opendata.example.es:8443/b", False),
        ("https://static.example.es/b", False),
    ],
)
def test_the_credentials_go_with_a_redirect_only_to_the_same_origin(location: str, kept: bool) -> None:  # noqa: FBT001
    """Over https, a redirect to the same origin keeps the key and one to another origin of the family drops it."""
    headers = {"api_key": KEY, "Accept": "*/*"}
    _check_redirect(
        _redirect("https://opendata.example.es/a", location),  # ty: ignore[invalid-argument-type]
        headers,
        "https://opendata.example.es/a",
    )
    assert ("api_key" in headers) is kept
    assert "Accept" in headers


@pytest.mark.parametrize(
    "location",
    ["https://example.net/b", "https://169.254.169.254/latest/meta-data", "https://localhost/b", "https://metadata/b"],
)
def test_a_redirect_out_of_the_family_is_refused(location: str) -> None:
    """Another registered domain, an address and a name on an internal network are refused."""
    with pytest.raises(RedirectRefusedError, match="another host"):
        _check_redirect(_redirect("https://opendata.example.es/a", location), {}, "https://opendata.example.es/a")  # ty: ignore[invalid-argument-type]


@pytest.fixture
def example_provider(monkeypatch: pytest.MonkeyPatch) -> None:
    """Register a provider of three hosts: its API, a store of files and a bucket of a shared domain."""
    monkeypatch.setitem(
        PROVIDER_HOSTS, "example", ("api.example.nl", "store.example.org", "bucket.s3.eu-west-1.amazonaws.com")
    )


@pytest.mark.parametrize(
    ("link", "base", "fetched"),
    [
        # the hosts of the provider, whichever of them the request started at
        ("https://api.example.nl/v1/next?page=2", "https://api.example.nl/v1", None),
        ("https://store.example.org/f?sig=1", "https://api.example.nl/v1", None),
        ("https://api.example.nl/v1/x", "https://store.example.org/f", None),
        ("https://bucket.s3.eu-west-1.amazonaws.com/f?X-Amz-Signature=s", "https://api.example.nl/v1", None),
        ("https://API.example.nl./v1/x", "https://api.example.nl/v1", None),
        # http under an https base is fetched as https
        ("http://store.example.org/f", "https://api.example.nl/v1", "https://store.example.org/f"),
        # no other host: not a sibling name of a host, nor one of its registered domain, nor of a shared one
        ("https://www.example.nl/x", "https://api.example.nl/v1", DownloadError),
        ("https://sibling.api.example.nl/x", "https://api.example.nl/v1", DownloadError),
        ("https://example.nl/x", "https://api.example.nl/v1", DownloadError),
        ("https://other.example.org/f", "https://api.example.nl/v1", DownloadError),
        ("https://other-bucket.s3.eu-west-1.amazonaws.com/f", "https://api.example.nl/v1", DownloadError),
        ("https://bucket.s3.eu-central-1.amazonaws.com/f", "https://api.example.nl/v1", DownloadError),
        ("https://x.elb.eu-west-1.amazonaws.com/f", "https://api.example.nl/v1", DownloadError),
        ("https://api.example.nl.example.org/x", "https://api.example.nl/v1", DownloadError),
        # what is refused outright, at a host of the provider as at any other
        ("https://example.net/x", "https://api.example.nl/v1", DownloadError),
        ("http://192.0.2.1/latest/meta-data/iam", "https://api.example.nl/v1", DownloadError),
        ("http://localhost:1/x", "https://api.example.nl/v1", DownloadError),
        ("file:///etc/hosts", "https://api.example.nl/v1", DownloadError),
        ("/etc/hosts", "https://api.example.nl/v1", DownloadError),
        ("https://user:pw@api.example.nl/x", "https://api.example.nl/v1", DownloadError),
        ("https://api.example.nl:8443/x", "https://api.example.nl/v1", DownloadError),
        ("https://api.example.nl:99999/x", "https://api.example.nl/v1", DownloadError),
        ("https://store.example.org:8443/f", "https://api.example.nl/v1", DownloadError),
        # an https link under an http base is on the default port of its own scheme
        ("https://api.example.nl/x", "http://api.example.nl/v1", None),
    ],
)
def test_a_link_of_an_answer_is_fetched_only_at_the_hosts_of_its_provider(
    example_provider: None,  # noqa: ARG001
    link: str,
    base: str,
    fetched: object,
) -> None:
    """A link is fetched at the hosts that the provider of the request lists, over https, and nowhere else."""
    if fetched is DownloadError:
        with pytest.raises(DownloadError, match="the link was not fetched"):
            fetchable_link(link, base)
    else:
        assert fetchable_link(link, base) == (fetched or link)


@pytest.mark.parametrize(
    ("link", "base", "fetched"),
    [
        # a host that no provider lists is held to its registered domain, as a registry label is read
        ("https://opendata.example-b.es/opendata/sh/abc", "https://opendata.example-a.es/opendata/api", DownloadError),
        ("https://static.example.es/x", "https://opendata.example.es/opendata/api", None),
        ("https://other.gov.uk/x", "https://environment.example.gov.uk/y", DownloadError),
        ("https://static.example.gouv.fr/x", "https://www.example.gouv.fr/api/1/datasets/", None),
        ("https://www.gouv.fr/x", "https://www.example.gouv.fr/api/1/datasets/", DownloadError),
        # an address is related to nothing but itself
        ("http://127.0.0.1:8000/x", "http://127.0.0.1:8000/y", None),
        ("http://127.0.0.2:8000/x", "http://127.0.0.1:8000/y", DownloadError),
        # a name under a domain that many tenants share is related to nothing but itself
        ("https://b.s3.amazonaws.com/f", "https://a.s3.amazonaws.com/y", DownloadError),
        ("https://x.elb.eu-west-1.amazonaws.com/f", "https://a.s3.eu-west-1.amazonaws.com/y", DownloadError),
        ("https://a.s3.eu-west-1.amazonaws.com/f", "https://a.s3.eu-west-1.amazonaws.com/y", None),
    ],
)
def test_a_link_at_a_host_of_no_provider_is_fetched_only_within_its_registered_domain(
    link: str, base: str, fetched: object
) -> None:
    """The fallback for an address the library does not list (a test server, an address fetched by hand)."""
    if fetched is DownloadError:
        with pytest.raises(DownloadError, match="the link was not fetched"):
            fetchable_link(link, base)
    else:
        assert fetchable_link(link, base) == (fetched or link)


def test_a_refused_link_names_the_host_and_the_provider(example_provider: None) -> None:  # noqa: ARG001
    """The error says which host was refused and whose hosts it is none of."""
    with pytest.raises(DownloadError, match=r"leads to other\.example\.net, which is outside the hosts of example"):
        fetchable_link("https://other.example.net/f", "https://api.example.nl/v1")


def test_a_refusal_at_a_host_of_no_provider_names_the_domain_it_is_held_to() -> None:
    """For a host that no provider lists, a refused link and a refused redirect name the domain of the request."""
    with pytest.raises(
        DownloadError, match=r"leads to other\.example\.org, which is outside the domain of example\.es"
    ):
        fetchable_link("https://other.example.org/f", "https://opendata.example.es/api")
    first = "https://opendata.example.es/a"
    with pytest.raises(
        RedirectRefusedError, match=r"another host \(other\.example\.org\) outside the domain of example\.es"
    ):
        _check_redirect(_redirect(first, "https://other.example.org/b"), {}, first)  # ty: ignore[invalid-argument-type]


@pytest.mark.parametrize(
    ("first", "location", "followed"),
    [
        ("https://api.example.nl/a", "https://store.example.org/b", True),
        ("https://store.example.org/a", "https://api.example.nl/b", True),
        ("https://api.example.nl/a", "https://bucket.s3.eu-west-1.amazonaws.com/b?X-Amz-Signature=s", True),
        ("https://api.example.nl/a", "/b", True),
        ("https://api.example.nl/a", "https://www.example.nl/b", False),
        ("https://api.example.nl/a", "https://other.example.org/b", False),
        ("https://store.example.org/a", "https://x.elb.eu-west-1.amazonaws.com/b", False),
        ("https://api.example.nl/a", "https://192.0.2.1/latest/meta-data", False),
        ("https://api.example.nl/a", "https://localhost/b", False),
    ],
)
def test_a_redirect_is_followed_only_to_the_hosts_of_the_provider(
    example_provider: None,  # noqa: ARG001
    first: str,
    location: str,
    followed: bool,  # noqa: FBT001
) -> None:
    """A redirect from a host of a provider leads to another of its hosts, as a link does, and to no other."""
    here = _redirect(first, location)
    if followed:
        _check_redirect(here, {}, first)  # ty: ignore[invalid-argument-type]
    else:
        with pytest.raises(RedirectRefusedError, match=r"another host \(.+\) outside the hosts of example"):
            _check_redirect(here, {}, first)  # ty: ignore[invalid-argument-type]


def test_a_refused_link_is_named_without_its_query() -> None:
    """A pre-signed link carries a signature in its query, which the error does not repeat."""
    with pytest.raises(DownloadError) as error:
        fetchable_link("https://example.net/f?X-Amz-Signature=secret", "https://api.example.nl/v1")
    assert "secret" not in str(error.value)
    assert "example.net/f" in str(error.value)


@pytest.mark.parametrize(
    ("base", "kept"),
    [
        ("https://h.example/d/", ["https://h.example/d/a.zip"]),
        ("http://h.example/d/", ["http://h.example/d/b.zip", "https://h.example/d/a.zip"]),
    ],
)
def test_an_https_listing_does_not_keep_a_link_that_steps_down_to_http(
    monkeypatch: pytest.MonkeyPatch, base: str, kept: list[str]
) -> None:
    """Fsspec keeps an `http://` link under an `https://` listing, which a caller would fetch in clear."""

    async def listing(_self: object, _url: str, detail: bool = True, **_kwargs: object) -> list[dict]:  # noqa: ARG001, FBT001, FBT002
        return [
            {"name": name, "size": None, "type": "file"}
            for name in ("https://h.example/d/a.zip", "http://h.example/d/b.zip")
        ]

    monkeypatch.setattr(HTTPFileSystem.__mro__[1], "_ls_real", listing)
    filesystem = HTTPFileSystem(use_listings_cache=False, listings_expiry_time=0)
    assert filesystem.ls(base, detail=False) == kept


def test_a_redirect_between_two_names_of_a_shared_domain_is_refused() -> None:
    """A bucket of a shared domain is not related to another name of it, which can resolve to a private address."""
    first = "https://bucket.s3.eu-west-1.amazonaws.com/f"
    with pytest.raises(RedirectRefusedError, match="another host"):
        _check_redirect(_redirect(first, "https://internal.elb.eu-west-1.amazonaws.com/f"), {}, first)  # ty: ignore[invalid-argument-type]


def test_a_credential_header_that_is_there_twice_is_dropped_without_an_error() -> None:
    """The multi-dict of aiohttp removes every value of a name at once, so the second of its keys is already gone."""
    from multidict import CIMultiDict  # noqa: PLC0415

    headers = CIMultiDict([("api_key", KEY), ("API_KEY", KEY), ("Accept", "*/*")])
    _check_redirect(
        _redirect("https://a.example.es/a", "https://b.example.es/b"),  # ty: ignore[invalid-argument-type]
        headers,  # ty: ignore[invalid-argument-type]
        "https://a.example.es/a",
    )
    assert list(headers) == ["Accept"]


def test_a_listing_that_met_a_refused_redirect_is_a_download_error(
    two_servers: tuple[_Server, _Server], tmp_path: Path
) -> None:
    """A directory listing raises the `DownloadError` of the redirect it did not follow, not the aiohttp error."""
    first, second = two_servers
    url = f"http://127.0.0.1:{first.server_port}/redirect?to=http://localhost:{second.server_port}/dir/"
    with pytest.raises(DownloadError):
        list_remote_files_fsspec(url, Settings(cache_dir=tmp_path, cache_disable=True))
    assert second.seen == []


async def _guard_answers(client_kwargs: dict, first_url: str, here: str, location: str) -> Exception | None:
    """Drive the trace of a real session of `HTTPFileSystem` with one redirect, and return what it refused with."""
    filesystem = HTTPFileSystem(
        use_listings_cache=False, listings_expiry_time=0, client_kwargs=client_kwargs, asynchronous=True
    )
    session = await filesystem.set_session()
    try:
        trace = session.trace_configs[-1]
        params = SimpleNamespace(response=_redirect(here, location), headers=CIMultiDict(session.headers))
        try:
            await trace.on_request_redirect[0](session, SimpleNamespace(first_url=first_url), params)
        except RedirectRefusedError as error:
            return error
        return None
    finally:
        await session.close()


#: the sessions a caller can build: without a credential, with the environment (netrc, proxy), with a key or cookies
_SESSIONS = [
    {"headers": {"User-Agent": "wetterdienst-research"}},
    {"headers": {"User-Agent": "wetterdienst-research"}, "trust_env": True},
    {"headers": {"api_key": KEY}},
    {"headers": {"User-Agent": "wetterdienst-research"}, "cookies": {"k": "v"}},
]


@pytest.mark.parametrize("client_kwargs", _SESSIONS)
def test_a_real_session_refuses_the_step_down_from_https_to_http(client_kwargs: dict) -> None:
    """The session built by the filesystem carries the guard, and none of its kinds follows the step down."""
    refused = asyncio.run(
        _guard_answers(
            client_kwargs, "https://www.example.fr/a", "https://www.example.fr/a", "http://static.example.fr/b"
        )
    )
    assert isinstance(refused, RedirectRefusedError)
    assert not isinstance(refused, UpstreamMaintenanceError)
    assert "https to http (static.example.fr)" in str(refused)


@pytest.mark.parametrize("client_kwargs", _SESSIONS)
@pytest.mark.parametrize(
    ("first_url", "here"),
    [
        ("https://www.data.gouv.fr/api/1/datasets/r/abc", "https://www.data.gouv.fr/api/1/datasets/r/abc"),
        ("https://static.data.gouv.fr/resources/x.csv", "https://static.data.gouv.fr/resources/x.csv"),
        ("https://www.data.gouv.fr/api/1/datasets/r/abc", "http://sorry.data.gouv.fr/"),
    ],
)
def test_a_redirect_to_the_maintenance_page_of_data_gouv_is_an_outage_for_every_session(
    client_kwargs: dict, first_url: str, here: str
) -> None:
    """data.gouv.fr in maintenance answers every request with a 302 to http://sorry.data.gouv.fr (GH-3400)."""
    refused = asyncio.run(_guard_answers(client_kwargs, first_url, here, "http://sorry.data.gouv.fr"))
    assert isinstance(refused, UpstreamMaintenanceError)
    assert str(refused) == "data.gouv.fr is in maintenance (the request was redirected to sorry.data.gouv.fr)"


def test_the_maintenance_page_is_told_whatever_its_scheme_and_whoever_asked() -> None:
    """An https location, a name in capitals and a request of another provider's host are the same outage."""
    for first, location in [
        ("https://www.data.gouv.fr/a", "https://sorry.data.gouv.fr/"),
        ("https://www.data.gouv.fr/a", "http://SORRY.data.gouv.fr./"),
        ("https://example.org/a", "http://sorry.data.gouv.fr/"),
    ]:
        with pytest.raises(UpstreamMaintenanceError, match=r"data\.gouv\.fr is in maintenance"):
            _check_redirect(_redirect(first, location), {}, first)  # ty: ignore[invalid-argument-type]


def test_another_sorry_host_is_no_maintenance_page() -> None:
    """Only the page of data.gouv.fr is told; a host of another name is judged as any other redirect."""
    with pytest.raises(RedirectRefusedError, match="another host") as refused:
        _check_redirect(
            _redirect("https://www.data.gouv.fr/a", "https://sorry.example.net/"),  # ty: ignore[invalid-argument-type]
            {},
            "https://www.data.gouv.fr/a",
        )
    assert not isinstance(refused.value, UpstreamMaintenanceError)


@pytest.fixture
def maintenance_chain() -> Iterator[tuple[_Server, str]]:
    """Run a server that answers every request with a 302 to http://sorry.data.gouv.fr, as data.gouv.fr does."""

    class Maintenance(BaseHTTPRequestHandler):
        def log_message(self, *args: object) -> None:
            pass

        def do_GET(self) -> None:
            self.send_response(302)
            self.send_header("Location", "http://sorry.data.gouv.fr")
            self.send_header("Content-Length", "0")
            self.end_headers()

    server = _Server(("127.0.0.1", 0), Maintenance)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, f"http://127.0.0.1:{server.server_port}/api/1/datasets/r/abc"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


@pytest.mark.parametrize("client_kwargs", [{}, {"trust_env": True}])
def test_a_download_met_by_the_maintenance_redirect_is_a_download_error_of_an_outage(
    maintenance_chain: tuple[_Server, str], tmp_path: Path, client_kwargs: dict
) -> None:
    """The redirect comes out of `raise_if_exception` as a `DownloadError` that names data.gouv.fr, and skips tests."""
    _, url = maintenance_chain
    file = download_file(url, tmp_path, CacheExpiry.NO_CACHE, client_kwargs=client_kwargs, attempts=1)
    assert isinstance(file.content, UpstreamMaintenanceError)
    with pytest.raises(DownloadError, match=r"data\.gouv\.fr is in maintenance") as raised:
        file.raise_if_exception()
    assert isinstance(raised.value.__cause__, UpstreamMaintenanceError)
    assert "sorry.data.gouv.fr" in str(raised.value)
    assert failure_status(raised.value) == 502
    with pytest.raises(pytest.skip.Exception, match="upstream did not answer"), skip_if_upstream_unavailable():
        raise raised.value
