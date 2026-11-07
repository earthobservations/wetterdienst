# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""An empty directory lists as no file, and is not kept in the listings cache (GH-3819).

nginx, which DWD's server is, answers the index page of an empty directory `/x/` with no link, and `/x` with a 301 to
`/x/`. fsspec then finds no file by listing, asks for `/x`, follows the redirect and takes the page for a file: `find`
answered the directory itself as its one file, so `list_remote_files_fsspec` never returned `[]` for an empty directory
on such a server, only for one that is not there (a 404), which is what the first tests of the history served. And its
`_ls` had stored the empty listing before `find` looked at it, so a directory DWD filled again was listed empty from
our cache for the 12 hours of `CacheExpiry.METAINDEX`.

The server here is the behaviour of nginx, not a mock of the function: a request is a real one, the 301 included, and
the same listings were made against nginx 1.31.3 itself when this was written. An Apache index page is not handled: it
links its column headings (`?C=N;O=D`), which fsspec lists as files whatever the directory holds; no provider's server
answers that way.
"""

from __future__ import annotations

import logging
import sqlite3
from typing import TYPE_CHECKING

import pytest

from tests.nginx_stub import NginxLike, serving
from wetterdienst import Settings
from wetterdienst.exceptions import DownloadError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.util import network
from wetterdienst.util.listing_cache import ListingStore
from wetterdienst.util.network import (
    HTTPFileSystem,
    forget_remote_listing,
    list_remote_directory_fsspec,
    list_remote_files_fsspec,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Iterator
    from pathlib import Path

_ZIP = "tageswerte_KL_00044_hist.zip"


@pytest.fixture(params=[True, False], ids=["301", "no-301"])
def redirect(request: pytest.FixtureRequest) -> bool:
    """Whether `/x` is answered with a 301 to `/x/`, as nginx does (False: a 404, as the first tests served)."""
    return request.param


@pytest.fixture
def server(*, redirect: bool) -> Iterator[NginxLike]:
    """Run a server on a local port, and stop it."""
    with serving(redirect=redirect) as state:
        yield state


@pytest.fixture
def listing(server: NginxLike, tmp_path: Path) -> Callable[[str], list[str]]:
    """List a path of the server as the lookups do, with the metadata cache (12 hours) in a directory of its own."""
    settings = Settings(cache_dir=str(tmp_path / "cache"))

    def files(path: str) -> list[str]:
        return list_remote_files_fsspec(f"{server.base}{path}", settings=settings, cache_expiry=CacheExpiry.METAINDEX)

    return files


def test_an_empty_directory_lists_no_file(server: NginxLike, listing: Callable[[str], list[str]]) -> None:
    """`/x/` with no file is `[]`, not the directory as a file, on a server that redirects `/x` as nginx does."""
    server.directories["/empty/"] = []

    assert listing("/empty/") == []


def test_a_directory_that_was_empty_and_is_filled_is_listed_at_once(
    server: NginxLike, listing: Callable[[str], list[str]]
) -> None:
    """The empty listing is not kept: the 12 hours of `CacheExpiry.METAINDEX` do not hold it."""
    server.directories["/empty/"] = []
    assert listing("/empty/") == []

    server.directories["/empty/"] = [_ZIP]

    assert listing("/empty/") == [f"{server.base}/empty/{_ZIP}"]


def test_a_missing_directory_lists_no_file_and_is_listed_once_it_is_there(
    server: NginxLike, listing: Callable[[str], list[str]]
) -> None:
    """A 404 is the other way a directory has no file, and is not kept either."""
    assert listing("/missing/") == []

    server.directories["/missing/"] = [_ZIP]

    assert listing("/missing/") == [f"{server.base}/missing/{_ZIP}"]


def test_a_listing_with_files_is_kept(server: NginxLike, listing: Callable[[str], list[str]]) -> None:
    """What `cache_expiry` is for: the second listing makes no request."""
    server.directories["/full/"] = [_ZIP]
    assert listing("/full/") == [f"{server.base}/full/{_ZIP}"]

    server.requests.clear()

    assert listing("/full/") == [f"{server.base}/full/{_ZIP}"]
    assert server.requests == []


def test_a_url_of_a_file_lists_itself(server: NginxLike, listing: Callable[[str], list[str]]) -> None:
    """Without the `/` at its end a URL may name a file, and `find` lists it as it always did."""
    server.files.add("/plain.txt")

    assert listing("/plain.txt") == [f"{server.base}/plain.txt"]


def test_the_listing_of_a_nonempty_directory_without_the_slash_is_its_files(
    server: NginxLike, listing: Callable[[str], list[str]], *, redirect: bool
) -> None:
    """The URL of a directory with files lists them whether or not it ends in `/` (with the 301; a 404 has none)."""
    server.directories["/full/"] = [_ZIP]

    assert listing("/full") == ([f"{server.base}/full/{_ZIP}"] if redirect else [])


def test_the_directory_listing_of_an_empty_directory_is_empty_and_not_kept(
    server: NginxLike, tmp_path: Path, *, redirect: bool
) -> None:
    """`list_remote_directory_fsspec` answered `[]` too, and kept it: the directory filled again was listed empty."""
    if not redirect:
        pytest.skip("a server that answers `/x` with a 404 has no empty directory: `ls` raises, as for a missing one")
    settings = Settings(cache_dir=str(tmp_path / "cache"))
    url = f"{server.base}/empty/"
    server.directories["/empty/"] = []

    assert list_remote_directory_fsspec(url, settings, CacheExpiry.METAINDEX) == []

    server.directories["/empty/"] = [_ZIP]

    assert [entry["name"] for entry in list_remote_directory_fsspec(url, settings, CacheExpiry.METAINDEX)] == [
        f"{server.base}/empty/{_ZIP}"
    ]


# --- a page that is not the index of a directory is no empty directory ---------------------------------------------

_CDN_PAGE = (
    "<html><head><title>503 - CDN</title></head><body><h1>Service unavailable</h1>"
    '<a href="https://status.example.com/">status</a></body></html>'
)


@pytest.mark.parametrize(
    ("content_type", "body"),
    [
        pytest.param("text/html", _CDN_PAGE.encode(), id="cdn-page"),
        pytest.param("application/json", b'{"error": "unavailable"}', id="json"),
        pytest.param("text/html", b"", id="empty-body"),
    ],
)
def test_a_page_that_is_no_index_is_a_download_error_not_an_empty_directory(
    server: NginxLike, listing: Callable[[str], list[str]], content_type: str, body: bytes
) -> None:
    """An outage page answered with a 200 must never read as "no data": it is a `DownloadError`, a 502."""
    server.pages["/x/"] = (content_type, body)
    server.pages["/x"] = (content_type, body)

    with pytest.raises(DownloadError, match="not the index page of a directory"):
        listing("/x/")


#: an outage page that links to its own URL: fsspec keeps the self-link as an entry, so it lists as that directory
#: (the relative link and the absolute one, which the test completes with the address of the server)
_SELF_LINKS = [
    pytest.param("/x/", id="root-relative"),
    pytest.param("@BASE@/x/", id="absolute"),
    pytest.param("", id="empty"),
    pytest.param("./", id="dot-slash"),
    pytest.param(".", id="dot"),
    pytest.param("?retry=1", id="query"),
    pytest.param("#", id="fragment"),
]


def _outage_page_linking_to(link: str, base: str) -> bytes:
    """Write an outage page with a `retry` link to `link`, where `@BASE@` is the address of the server."""
    page = f'<html><head><title>503</title></head><body>Unavailable <a href="{link}">retry</a></body></html>'
    return page.replace("@BASE@", base).encode()


@pytest.mark.parametrize("link", _SELF_LINKS)
def test_an_outage_page_that_links_to_itself_is_not_kept_as_an_empty_directory(
    server: NginxLike, listing: Callable[[str], list[str]], link: str
) -> None:
    """The listing of an outage page with a link to itself is dropped, so the directory is listed once it is back.

    It is a `DownloadError` while the server is down, as it was. But fsspec had stored the listing of the page (the
    URL itself) before `find` looked at it, and once the server answered again the directory read as empty for the
    12 hours of `CacheExpiry.METAINDEX` (GH-3861). The link is compared as `_is_the_same_directory` does, so every
    spelling of it is the directory.
    """
    page = ("text/html", _outage_page_linking_to(link, server.base))
    server.pages["/x/"] = page
    server.pages["/x"] = page
    for _ in range(2):
        with pytest.raises(DownloadError, match="not the index page of a directory"):
            listing("/x/")

    server.pages.clear()
    server.directories["/x/"] = [_ZIP]

    assert listing("/x/") == [f"{server.base}/x/{_ZIP}"]


@pytest.mark.parametrize("link", ["/x/", "./"])
def test_the_url_without_the_slash_is_listed_once_the_server_is_back_too(
    server: NginxLike, listing: Callable[[str], list[str]], link: str, *, redirect: bool
) -> None:
    """Fsspec stored the listing of `/x` as well as that of `/x/` (and of `/x/./.` for a link to `./`)."""
    page = ("text/html", _outage_page_linking_to(link, server.base))
    server.pages["/x/"] = page
    server.pages["/x"] = page
    with pytest.raises(DownloadError, match="not the index page of a directory"):
        listing("/x/")

    server.pages.clear()
    server.directories["/x/"] = [_ZIP]

    assert listing("/x") == ([f"{server.base}/x/{_ZIP}"] if redirect else [])


def test_a_real_index_that_links_to_itself_is_an_empty_directory_and_not_kept(
    server: NginxLike, listing: Callable[[str], list[str]]
) -> None:
    """The control: an `Index of` page that links to itself is `[]`, and the directory is listed once it is filled."""
    page = ("text/html", b'<html><head><title>Index of /x/</title></head><body><a href="/x/">refresh</a></body></html>')
    server.pages["/x/"] = page
    server.pages["/x"] = page
    assert listing("/x/") == []

    server.pages.clear()
    server.directories["/x/"] = [_ZIP]

    assert listing("/x/") == [f"{server.base}/x/{_ZIP}"]


@pytest.mark.parametrize("link", ["/x/", "./", "."])
def test_a_real_index_that_links_to_itself_in_any_spelling_is_an_empty_directory_and_not_kept(
    server: NginxLike, listing: Callable[[str], list[str]], link: str
) -> None:
    """A link to `./` sends fsspec's walk into the recursion limit, which is no reason to answer anything but `[]`."""
    page = (
        "text/html",
        f'<html><head><title>Index of /x/</title></head><body><a href="{link}">refresh</a></body></html>'.encode(),
    )
    server.pages["/x/"] = page
    server.pages["/x"] = page
    assert listing("/x/") == []

    server.pages.clear()
    server.directories["/x/"] = [_ZIP]

    assert listing("/x/") == [f"{server.base}/x/{_ZIP}"]


def test_a_page_that_links_to_dot_slash_and_to_a_file_is_not_taken_for_an_empty_directory(
    server: NginxLike, listing: Callable[[str], list[str]]
) -> None:
    """Only a page that lists nothing but itself is read as a self-link: with a file as well it is no empty directory.

    fsspec's walk never ends on the `./` link whatever else the page holds, which is older than GH-3861 and is left as
    it was (a `RecursionError`); what must not happen is the directory read as `[]` with its file left out.
    """
    page = (
        "text/html",
        (
            '<html><head><title>Index of /x/</title></head><body><a href="./">refresh</a>'
            f'<a href="{_ZIP}">z</a></body></html>'
        ).encode(),
    )
    server.pages["/x/"] = page
    server.pages["/x"] = page

    with pytest.raises(RecursionError):
        listing("/x/")


def test_the_cache_drop_of_a_self_link_listing_is_best_effort(
    server: NginxLike, listing: Callable[[str], list[str]], monkeypatch: pytest.MonkeyPatch
) -> None:
    """A cache that cannot be written (busy, read-only) is a log line: the outage is still the `DownloadError`."""

    def refuse(_self: object, _key: str) -> None:
        message = "database is locked"
        raise sqlite3.OperationalError(message)

    monkeypatch.setattr(network.FileDirCache, "__delitem__", refuse)
    page = ("text/html", _outage_page_linking_to("/x/", server.base))
    server.pages["/x/"] = page
    server.pages["/x"] = page

    with pytest.raises(DownloadError, match="not the index page of a directory"):
        listing("/x/")


@pytest.mark.parametrize(
    ("content_type", "body"),
    [
        pytest.param("text/html", _CDN_PAGE.encode(), id="cdn-page"),
        pytest.param("application/json", b'{"error": "unavailable"}', id="json"),
    ],
)
@pytest.mark.parametrize("failure", ["slashless-404", "isfile-fails"])
def test_a_page_that_is_no_index_is_an_error_whatever_the_get_of_the_directory_without_the_slash_answers(
    server: NginxLike, listing: Callable[[str], list[str]], content_type: str, body: bytes, failure: str
) -> None:
    """`find` lists no file at all if `/x` is a 404 (it raises) or the `_isfile` GET fails (a 503): the page is read."""
    server.pages["/x/"] = (content_type, body)
    if failure == "slashless-404":
        server.statuses["/x"] = 404
    else:
        server.flaky["/x"] = [None, 503]

    with pytest.raises(DownloadError, match="not the index page of a directory"):
        listing("/x/")


@pytest.mark.parametrize("failure", ["slashless-404", "isfile-fails"])
def test_a_real_index_is_an_empty_directory_whatever_the_get_without_the_slash_answers(
    server: NginxLike, listing: Callable[[str], list[str]], failure: str
) -> None:
    """The same, with the index nginx writes for an empty directory: `[]`, and the directory is listed once filled."""
    server.directories["/x/"] = []
    if failure == "slashless-404":
        server.statuses["/x"] = 404
    else:
        server.flaky["/x"] = [None, 503]
    assert listing("/x/") == []

    server.directories["/x/"] = [_ZIP]
    server.statuses.clear()
    server.flaky.clear()

    assert listing("/x/") == [f"{server.base}/x/{_ZIP}"]


def test_a_503_for_the_directory_without_the_slash_is_an_outage_not_an_empty_directory(
    server: NginxLike, listing: Callable[[str], list[str]]
) -> None:
    """A server that fails the second page of the listing is down, and says so with a `DownloadError`."""
    server.directories["/x/"] = []
    server.statuses["/x"] = 503

    with pytest.raises(DownloadError):
        listing("/x/")


def test_the_title_of_an_index_is_index_of_a_path_not_index_of_a_word(
    server: NginxLike, listing: Callable[[str], list[str]]
) -> None:
    """A maintenance page titled "Index of services" is no index of a directory."""
    page = ("text/html", b"<html><head><title>Index of services - maintenance</title></head><body></body></html>")
    server.pages["/x/"] = page
    server.pages["/x"] = page

    with pytest.raises(DownloadError, match="not the index page of a directory"):
        listing("/x/")


def test_a_real_index_with_no_link_is_an_empty_directory(
    server: NginxLike, listing: Callable[[str], list[str]]
) -> None:
    """The control of the above: the index page nginx writes for an empty directory."""
    server.directories["/x/"] = []

    assert listing("/x/") == []


# --- no empty listing is kept, a subdirectory's included -----------------------------------------------------------


def test_an_empty_year_directory_is_listed_once_it_is_filled(
    server: NginxLike, listing: Callable[[str], list[str]], *, redirect: bool
) -> None:
    """DWD's `historical/2022/`: the tree lists `2023` and an empty `2024`; the next call has the files of both."""
    if not redirect:
        pytest.skip("fsspec lists a subdirectory without its `/` and relies on the 301 to it, as nginx answers")
    server.directories["/tree/"] = ["2023/", "2024/"]
    server.directories["/tree/2023/"] = [_ZIP]
    server.directories["/tree/2024/"] = []
    assert listing("/tree/") == [f"{server.base}/tree/2023/{_ZIP}"]

    server.directories["/tree/2024/"] = [_ZIP]

    assert listing("/tree/") == [f"{server.base}/tree/2023/{_ZIP}", f"{server.base}/tree/2024/{_ZIP}"]


def test_a_directory_with_only_an_empty_subdirectory_is_listed_once_it_is_filled(
    server: NginxLike, listing: Callable[[str], list[str]], *, redirect: bool
) -> None:
    """The listing is `[]` while the subdirectory is empty, and the files once it is not."""
    if not redirect:
        pytest.skip("fsspec lists a subdirectory without its `/` and relies on the 301 to it, as nginx answers")
    server.directories["/only/"] = ["inner/"]
    server.directories["/only/inner/"] = []
    assert listing("/only/") == []

    server.directories["/only/inner/"] = [_ZIP]

    assert listing("/only/") == [f"{server.base}/only/inner/{_ZIP}"]


def test_an_empty_listing_that_an_older_version_stored_is_a_miss(
    server: NginxLike, listing: Callable[[str], list[str]], tmp_path: Path
) -> None:
    """The cache of a version that stored `[]` for an empty directory does not answer it empty for 12 hours.

    That version kept the listing of an empty directory, and a directory filled since was listed empty (and the
    directory itself as a file) until the entry expired. Written here as that version wrote it, into the same store.
    """
    server.directories["/old/"] = [_ZIP]
    url = f"{server.base}/old/"
    cache = HTTPFileSystem(
        use_listings_cache=True,
        listings_expiry_time=CacheExpiry.METAINDEX.value,
        listings_cache_location=str(tmp_path / "cache"),
    ).dircache
    assert cache._store is not None  # noqa: SLF001
    cache._store.set(url, [], CacheExpiry.METAINDEX.value)  # noqa: SLF001

    assert url not in cache
    assert listing("/old/") == [f"{server.base}/old/{_ZIP}"]


# --- the listing of a directory's entries reads the page the same way (GH-3834) ------------------------------------


@pytest.fixture
def entries(server: NginxLike, tmp_path: Path) -> Callable[[str], list[dict]]:
    """List the entries of a path of the server as `imgw`, `dwd/dmo` and `dwd/alerts` do."""
    settings = Settings(cache_dir=str(tmp_path / "cache"))

    def listed(path: str) -> list[dict]:
        return list_remote_directory_fsspec(
            f"{server.base}{path}", settings=settings, cache_expiry=CacheExpiry.METAINDEX
        )

    return listed


@pytest.mark.parametrize(
    ("content_type", "body"),
    [
        pytest.param("text/html", _CDN_PAGE.encode(), id="cdn-page"),
        pytest.param("application/json", b'{"error": "unavailable"}', id="json"),
        pytest.param("text/html", b"", id="empty-body"),
        pytest.param(
            "text/html",
            b"<html><head><title>Index of services - maintenance</title></head><body></body></html>",
            id="index-of-a-word",
        ),
    ],
)
def test_a_directory_page_that_is_no_index_is_a_download_error_not_no_entries(
    server: NginxLike, entries: Callable[[str], list[dict]], content_type: str, body: bytes
) -> None:
    """`list_remote_directory_fsspec` answered `[]` for an outage page that came with a 200: now a `DownloadError`."""
    server.pages["/x/"] = (content_type, body)
    server.pages["/x"] = (content_type, body)

    with pytest.raises(DownloadError, match="not the index page of a directory"):
        entries("/x/")


@pytest.mark.parametrize("link", _SELF_LINKS)
def test_an_outage_page_that_links_to_itself_is_a_download_error_not_the_directory_as_an_entry(
    server: NginxLike, entries: Callable[[str], list[dict]], link: str
) -> None:
    """A link of the page to its own URL, however it is written, lists as that directory and is no more an index.

    fsspec joins the link to the URL as it stands (`./` is `/x/./`, `.` is `/x/.`), so the entries are compared by host
    and normalised path. The listing is not kept: once the server is back the directory is listed at once.
    """
    body = _outage_page_linking_to(link, server.base)
    server.pages["/x/"] = ("text/html", body)
    server.pages["/x"] = ("text/html", body)
    for _ in range(2):
        with pytest.raises(DownloadError, match="not the index page of a directory"):
            entries("/x/")

    server.pages.clear()
    server.directories["/x/"] = [_ZIP]

    assert [entry["name"] for entry in entries("/x/")] == [f"{server.base}/x/{_ZIP}"]


_APACHE_SORT_LINKS = (
    '<a href="?C=N;O=D">Name</a><a href="?C=M;O=A">Last modified</a><a href="?C=S;O=A">Size</a>'
    '<a href="/">Parent Directory</a>'
)


def test_an_apache_index_of_an_empty_directory_has_no_entries(
    server: NginxLike, entries: Callable[[str], list[dict]]
) -> None:
    """Its sort links (`?C=N;O=D`) are the directory itself: a real `Index of` page with nothing else lists nothing."""
    page = (
        "text/html",
        (
            f"<html><head><title>Index of /x</title></head><body><h1>Index of /x</h1>{_APACHE_SORT_LINKS}</body></html>"
        ).encode(),
    )
    server.pages["/x/"] = page
    server.pages["/x"] = page

    assert entries("/x/") == []


def test_an_apache_index_with_a_file_keeps_its_entries_sort_links_included(
    server: NginxLike, entries: Callable[[str], list[dict]]
) -> None:
    """The sort links do not make a listing with a file one that lists nothing: it is left as fsspec gave it."""
    page = (
        "text/html",
        (
            f"<html><head><title>Index of /x</title></head><body><h1>Index of /x</h1>{_APACHE_SORT_LINKS}"
            f'<a href="{_ZIP}">{_ZIP}</a></body></html>'
        ).encode(),
    )
    server.pages["/x/"] = page
    server.pages["/x"] = page

    names = [entry["name"] for entry in entries("/x/")]

    assert f"{server.base}/x/{_ZIP}" in names


def test_a_real_index_that_links_to_itself_has_no_entries(
    server: NginxLike, entries: Callable[[str], list[dict]]
) -> None:
    """The self-link is no entry of a page that is an index: `[]`, not the directory as its own entry."""
    page = ("text/html", b'<html><head><title>Index of /x/</title></head><body><a href="/x/">refresh</a></body></html>')
    server.pages["/x/"] = page
    server.pages["/x"] = page

    assert entries("/x/") == []


def test_a_real_index_with_no_link_has_no_entries(
    server: NginxLike, entries: Callable[[str], list[dict]], *, redirect: bool
) -> None:
    """The control: nginx's index page of an empty directory is `[]`, and the directory is listed once it is filled."""
    if not redirect:
        pytest.skip("a server that answers `/x` with a 404 has no empty directory: `ls` raises, as for a missing one")
    server.directories["/x/"] = []
    assert entries("/x/") == []

    server.directories["/x/"] = [_ZIP]

    assert [entry["name"] for entry in entries("/x/")] == [f"{server.base}/x/{_ZIP}"]


@pytest.mark.usefixtures("server")
def test_a_missing_directory_is_still_a_file_not_found_error(entries: Callable[[str], list[dict]]) -> None:
    """A 404 is not "no entries" for this function, as its docstring says."""
    with pytest.raises(FileNotFoundError):
        entries("/missing/")


def test_a_listing_with_entries_reads_no_second_page(server: NginxLike, entries: Callable[[str], list[dict]]) -> None:
    """The page is read only where the listing is empty: a directory with entries costs the request it always did."""
    server.directories["/full/"] = [_ZIP]

    assert [entry["name"] for entry in entries("/full/")] == [f"{server.base}/full/{_ZIP}"]
    assert server.requests == [("GET", "/full/")]


def test_a_url_without_the_slash_is_left_as_it_is(server: NginxLike, entries: Callable[[str], list[dict]]) -> None:
    """A URL that ends in no `/` may name a file: its page is not asked to be an index, as for the other listing."""
    server.pages["/plain"] = ("application/json", b'{"ok": true}')

    assert entries("/plain") == []


# --- a listing that is dropped from the cache (GH-3834) ------------------------------------------------------------


def test_a_listing_that_is_forgotten_is_asked_for_again(server: NginxLike, tmp_path: Path) -> None:
    """The directory had files and no description: its listing is dropped, so the one DWD fills is seen at once."""
    settings = Settings(cache_dir=str(tmp_path / "cache"))
    url = f"{server.base}/half/"
    server.directories["/half/"] = [_ZIP]
    assert len(list_remote_files_fsspec(url, settings, CacheExpiry.METAINDEX)) == 1
    server.directories["/half/"] = [_ZIP, "KL_Beschreibung_Stationen.txt"]

    # the listing is kept: the control of what forgetting changes
    assert len(list_remote_files_fsspec(url, settings, CacheExpiry.METAINDEX)) == 1

    forget_remote_listing(url, settings, CacheExpiry.METAINDEX)

    assert len(list_remote_files_fsspec(url, settings, CacheExpiry.METAINDEX)) == 2


def test_forgetting_a_listing_that_is_not_kept_is_nothing(server: NginxLike, tmp_path: Path) -> None:
    """A listing that was never made, or a disabled cache, is no error."""
    url = f"{server.base}/never/"

    forget_remote_listing(url, Settings(cache_dir=str(tmp_path / "cache")), CacheExpiry.METAINDEX)
    forget_remote_listing(url, Settings(cache_disable=True), CacheExpiry.METAINDEX)
    forget_remote_listing(url, Settings(cache_dir=str(tmp_path / "cache")), CacheExpiry.NO_CACHE)


@pytest.mark.parametrize(
    "error",
    [
        sqlite3.OperationalError("database is locked"),
        sqlite3.OperationalError("attempt to write a readonly database"),
        OSError("disk"),
    ],
    ids=["busy", "read-only", "os"],
)
def test_a_cache_that_cannot_drop_a_listing_is_told_in_the_log_and_is_no_failure(
    server: NginxLike,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    error: Exception,
) -> None:
    """`ListingStore.delete` can raise (busy, read-only): the forget is best effort, so it is a log line, not a 500."""
    settings = Settings(cache_dir=str(tmp_path / "cache"))
    url = f"{server.base}/half/"
    server.directories["/half/"] = [_ZIP]
    list_remote_files_fsspec(url, settings, CacheExpiry.METAINDEX)

    def failing(_store: object, _key: object) -> bool:
        raise error

    monkeypatch.setattr(ListingStore, "delete", failing)

    with caplog.at_level(logging.WARNING):
        forget_remote_listing(url, settings, CacheExpiry.METAINDEX)

    assert [
        record.getMessage() for record in caplog.records if "Could not drop the cached listing" in record.getMessage()
    ]


def test_a_cache_that_cannot_be_opened_to_drop_a_listing_is_no_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """The filesystem that holds the cache may fail to be built (a directory that cannot be made): told, not raised."""

    def failing(*_args: object, **_kwargs: object) -> None:
        msg = "read-only file system"
        raise OSError(msg)

    monkeypatch.setattr(network, "HTTPFileSystem", failing)

    with caplog.at_level(logging.WARNING):
        forget_remote_listing(
            "https://example.com/x/", Settings(cache_dir=str(tmp_path / "cache")), CacheExpiry.METAINDEX
        )

    assert [record for record in caplog.records if "Could not open the listings cache" in record.getMessage()]


@pytest.mark.parametrize(
    ("names", "url", "nothing"),
    [
        pytest.param([], "https://h/x/", True, id="no-entry"),
        pytest.param(
            ["https://h/x/", "https://h/x/./", "https://h/x/.", "https://h/x/?C=N;O=D"],
            "https://h/x/",
            True,
            id="itself",
        ),
        pytest.param(["https://other/x/"], "https://h/x/", False, id="another-host"),
        pytest.param(["https://h/x/", "https://h/x/file.zip"], "https://h/x/", False, id="a-file-as-well"),
        pytest.param(["https://h/x/.."], "https://h/x/", False, id="the-parent"),
        pytest.param(["https://h/x/sub/"], "https://h/x/", False, id="a-subdirectory"),
        pytest.param(["https://h/x"], "https://h/x", False, id="no-slash-names-maybe-a-file"),
        pytest.param([], "https://h/x", False, id="no-slash-no-entry"),
    ],
)
def test_a_listing_lists_nothing_where_every_entry_is_the_directory_itself(
    names: list[str], url: str, *, nothing: bool
) -> None:
    """What `_lists_nothing` takes for the directory and what it does not (host, normalised path, a URL with a `/`)."""
    assert network._lists_nothing(url, [{"name": name} for name in names]) is nothing  # noqa: SLF001
