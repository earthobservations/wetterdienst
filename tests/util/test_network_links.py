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

from wetterdienst.exceptions import DownloadError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.settings import Settings
from wetterdienst.util.network import (
    HTTPFileSystem,
    RedirectRefusedError,
    _check_redirect,
    _session_is_keyless,
    download_file,
    fetchable_link,
    list_remote_files_fsspec,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

#: a made-up key, sent the way AEMET sends its own
KEY = "FAKEKEY123"

#: an allow-list of the spellings of the host names of S3
S3 = (
    "*.s3.amazonaws.com",
    "*.s3.*.amazonaws.com",
    "*.s3.dualstack.*.amazonaws.com",
    "*.s3-*.amazonaws.com",
    "s3.*.amazonaws.com",
    "s3.amazonaws.com",
)


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


@pytest.mark.parametrize("name", ["api_key", "Authorization", "X-Api-Key", "Cookie"])
def test_a_step_down_from_https_to_http_is_refused_for_a_request_that_carries_a_credential(name: str) -> None:
    """A request that carries a credential is not led from https to http; the hop is named by host, not by query."""
    with pytest.raises(RedirectRefusedError, match=r"https to http \(opendata.example.es\)") as refused:
        _check_redirect(
            _redirect("https://opendata.example.es/a", "http://opendata.example.es/b?sig=secret"),  # ty: ignore[invalid-argument-type]
            {name: KEY},
            "https://opendata.example.es/a",
            allow_downgrade=True,
        )
    assert "secret" not in str(refused.value)


def test_a_step_down_from_https_to_http_is_refused_unless_the_session_allows_it() -> None:
    """The session says whether it holds no credential at all, and the step is refused where it does not say so."""
    with pytest.raises(RedirectRefusedError, match="https to http"):
        _check_redirect(
            _redirect("https://opendata.example.es/a", "http://opendata.example.es/b"),  # ty: ignore[invalid-argument-type]
            {},
            "https://opendata.example.es/a",
        )


def test_a_chain_through_http_that_ends_on_https_is_followed_by_a_keyless_session() -> None:
    """A public file is reached over an http hop by some chains (GH-3398): the hops of one family are followed."""
    first = "https://www.example.fr/api/1/datasets/r/abc"
    headers = {"Accept": "*/*"}
    for here, location in [
        (first, "http://static.example.fr/resources/x.csv"),
        ("http://static.example.fr/resources/x.csv", "https://static.example.fr/resources/x.csv"),
    ]:
        _check_redirect(_redirect(here, location), headers, first, allow_downgrade=True)  # ty: ignore[invalid-argument-type]
    assert headers == {"Accept": "*/*"}


@pytest.mark.parametrize(
    ("client_kwargs", "keyless"),
    [
        ({}, True),
        ({"headers": {"User-Agent": "wetterdienst/1.0"}, "timeout": 30}, True),
        ({"headers": [("Accept", "*/*")]}, True),
        ({"headers": {"Authorization": KEY}}, False),
        ({"headers": {"API_KEY": KEY}}, False),
        ({"headers": {"cookie": "k=v"}}, False),
        ({"headers": iter([("Accept", "*/*")])}, False),
        ({"auth": ("user", "password")}, False),
        ({"cookies": {"k": "v"}}, False),
        ({"cookie_jar": object()}, False),
        ({"middlewares": (object(),)}, False),
        ({"trust_env": True}, False),
        ({"proxy": "http://proxy.example:3128"}, False),
        ({"proxy_auth": ("user", "password")}, False),
    ],
)
def test_a_session_is_keyless_only_if_it_holds_no_credential_of_any_kind(client_kwargs: dict, keyless: bool) -> None:  # noqa: FBT001
    """Headers, an `auth`, cookies, the environment (netrc, proxy) and a proxy each make a session not keyless."""
    assert _session_is_keyless(client_kwargs) is keyless


def test_a_chain_through_http_stays_in_the_family_of_the_first_request() -> None:
    """The http hop is no way out of the family: the next hop to another domain is refused, as over https."""
    first = "https://www.example.fr/api/1/datasets/r/abc"
    with pytest.raises(RedirectRefusedError, match=r"another host \(evil.example.net\)"):
        _check_redirect(
            _redirect("http://static.example.fr/x", "http://evil.example.net/x"),  # ty: ignore[invalid-argument-type]
            {},
            first,
        )
    with pytest.raises(RedirectRefusedError, match="another host"):
        _check_redirect(_redirect(first, "http://evil.example.net/x"), {}, first)  # ty: ignore[invalid-argument-type]


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


@pytest.mark.parametrize(
    ("link", "base", "allow", "fetched"),
    [
        # the same host, and the registered domain
        ("https://opendata.aemet.es/opendata/sh/abc", "https://opendata.aemet.es/opendata/api", (), None),
        ("https://static.aemet.es/x", "https://opendata.aemet.es/opendata/api", (), None),
        # http under an https base is fetched as https
        (
            "http://environment.data.gov.uk/hydrology/id/measures/x",
            "https://environment.data.gov.uk/hydrology/id/stations/y.json",
            (),
            "https://environment.data.gov.uk/hydrology/id/measures/x",
        ),
        # two names under a registry label are two families
        ("https://other.gov.uk/x", "https://environment.data.gov.uk/y", (), DownloadError),
        ("https://static.data.gouv.fr/x", "https://www.data.gouv.fr/api/1/datasets/", (), None),
        ("https://www.gouv.fr/x", "https://www.data.gouv.fr/api/1/datasets/", (), DownloadError),
        # the allow-list: https, the default port, a host or the names under a domain
        ("https://s3.example.org/f?sig=1", "https://api.example.nl/v1", ("s3.example.org",), None),
        ("https://b.s3.example.org/f", "https://api.example.nl/v1", ("*.s3.example.org",), None),
        ("https://s3.example.org/f", "https://api.example.nl/v1", ("*.s3.example.org",), DownloadError),
        ("http://s3.example.org/f", "https://api.example.nl/v1", ("s3.example.org",), DownloadError),
        ("https://s3.example.org:8443/f", "https://api.example.nl/v1", ("s3.example.org",), DownloadError),
        ("https://evil.example.org/f", "https://api.example.nl/v1", ("s3.example.org",), DownloadError),
        # what is refused outright
        ("https://example.net/x", "https://api.example.nl/v1", (), DownloadError),
        ("http://169.254.169.254/latest/meta-data/iam", "https://api.example.nl/v1", (), DownloadError),
        ("http://localhost:1/x", "https://api.example.nl/v1", (), DownloadError),
        ("file:///etc/hosts", "https://api.example.nl/v1", (), DownloadError),
        ("/etc/hosts", "https://api.example.nl/v1", (), DownloadError),
        ("https://user:pw@api.example.nl/x", "https://api.example.nl/v1", (), DownloadError),
        ("https://api.example.nl:8443/x", "https://api.example.nl/v1", (), DownloadError),
        ("https://api.example.nl:99999/x", "https://api.example.nl/v1", (), DownloadError),
        # an address is related to nothing but itself
        ("http://127.0.0.1:8000/x", "http://127.0.0.1:8000/y", (), None),
        ("http://127.0.0.2:8000/x", "http://127.0.0.1:8000/y", (), DownloadError),
        # a name under a domain that many tenants share is related to nothing but itself
        ("https://b.s3.amazonaws.com/f", "https://a.s3.amazonaws.com/y", (), DownloadError),
        ("https://x.elb.eu-west-1.amazonaws.com/f", "https://a.s3.eu-west-1.amazonaws.com/y", (), DownloadError),
        ("https://a.s3.eu-west-1.amazonaws.com/f", "https://a.s3.eu-west-1.amazonaws.com/y", (), None),
        (
            "https://b.s3.eu-west-1.amazonaws.com/f",
            "https://api.example.nl/v1",
            ("*.s3.eu-west-1.amazonaws.com",),
            None,
        ),
        (
            "https://x.elb.eu-west-1.amazonaws.com/f",
            "https://api.example.nl/v1",
            ("*.s3.eu-west-1.amazonaws.com",),
            DownloadError,
        ),
        # the spellings of the host names of S3, and no other name of amazonaws.com
        ("https://b.s3-eu-west-1.amazonaws.com/f", "https://api.example.nl/v1", S3, None),
        ("https://b.s3.dualstack.eu-west-1.amazonaws.com/f", "https://api.example.nl/v1", S3, None),
        ("https://s3.eu-west-1.amazonaws.com/b/f", "https://api.example.nl/v1", S3, None),
        ("https://s3.amazonaws.com/b/f", "https://api.example.nl/v1", S3, None),
        ("https://b.s3.amazonaws.com/f", "https://api.example.nl/v1", S3, None),
        ("https://x.elb.eu-west-1.amazonaws.com/f", "https://api.example.nl/v1", S3, DownloadError),
        ("https://vpce-1.vpce-svc-2.eu-west-1.vpce.amazonaws.com/f", "https://api.example.nl/v1", S3, DownloadError),
        ("https://s3.evil.example/f", "https://api.example.nl/v1", S3, DownloadError),
        ("https://amazonaws.com/f", "https://api.example.nl/v1", S3, DownloadError),
        # an https link under an http base is on the default port of its own scheme
        ("https://api.example.nl/x", "http://api.example.nl/v1", (), None),
    ],
)
def test_a_link_of_an_answer_is_fetched_only_where_the_provider_is_at_home(
    link: str, base: str, allow: tuple[str, ...], fetched: object
) -> None:
    """A link is fetched for the provider's own family of hosts and for its narrow allow-list."""
    if fetched is DownloadError:
        with pytest.raises(DownloadError, match="the link was not fetched"):
            fetchable_link(link, base, allow=allow)
    else:
        assert fetchable_link(link, base, allow=allow) == (fetched or link)


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


async def _guard_refuses_the_step_down(client_kwargs: dict) -> bool:
    """Drive the trace of a real session of `HTTPFileSystem` with a redirect from https to http."""
    filesystem = HTTPFileSystem(
        use_listings_cache=False, listings_expiry_time=0, client_kwargs=client_kwargs, asynchronous=True
    )
    session = await filesystem.set_session()
    try:
        trace = session.trace_configs[-1]
        headers = CIMultiDict(session.headers)
        response = _redirect("https://www.example.fr/a", "http://static.example.fr/b")
        params = SimpleNamespace(response=response, headers=headers)
        context = SimpleNamespace(first_url="https://www.example.fr/a")
        try:
            await trace.on_request_redirect[0](session, context, params)
        except RedirectRefusedError:
            return True
        return False
    finally:
        await session.close()


@pytest.mark.parametrize(
    ("client_kwargs", "refused"),
    [
        ({"headers": {"User-Agent": "wetterdienst"}}, False),
        ({"headers": {"api_key": KEY}}, True),
        ({"headers": {"User-Agent": "wetterdienst"}, "cookies": {"k": "v"}}, True),
    ],
)
def test_a_real_session_follows_the_step_down_only_without_a_credential(client_kwargs: dict, refused: bool) -> None:  # noqa: FBT001
    """The session built by the filesystem carries the guard, with the verdict of its own client kwargs."""
    assert asyncio.run(_guard_refuses_the_step_down(client_kwargs)) is refused
