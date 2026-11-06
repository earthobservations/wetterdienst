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

from typing import TYPE_CHECKING

import pytest

from tests.nginx_stub import NginxLike, serving
from wetterdienst import Settings
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.util.network import list_remote_directory_fsspec, list_remote_files_fsspec

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
