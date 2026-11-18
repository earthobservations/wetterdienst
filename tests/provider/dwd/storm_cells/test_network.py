# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The thunderstorm cells through a real listing and a real download, from a local server that answers as DWD's does.

The directory of DWD's server is nginx's index page; the files are served whole. What is held is what the library does
with the answers it is given: a 429, an outage page answered as a 200, a 404, a file that was cut short, and what is
asked of the server (`tests/nginx_stub.py` counts every request).
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pytest

from tests.nginx_stub import NginxLike, serving
from wetterdienst import Settings
from wetterdienst.exceptions import DownloadError, MetaFileFormatError, MetaFileNotFoundError, ProviderRateLimitError
from wetterdienst.provider.dwd.storm_cells import DwdStormCellsRequest

from .stubs import EMPTY_SCAN, TWO_CELLS_SCAN

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

UTC = ZoneInfo("UTC")
DIRECTORY = "/weather/radar/konrad3d/"
OLDER = "KONRAD3D_20261117T221000.xml"
NEWEST = "KONRAD3D_20261117T221500.xml"
WAIT = 7


class _Dwd:
    def __init__(self, server: NginxLike, settings: Settings) -> None:
        self.server = server
        self.settings = settings

    def asked(self, path: str) -> int:
        """Count the GETs the server met for a path."""
        return len([1 for method, asked in self.server.requests if method == "GET" and asked.split("?")[0] == path])

    def request(self, **arguments: object) -> DwdStormCellsRequest:
        return DwdStormCellsRequest(settings=self.settings, **arguments)  # ty: ignore[invalid-argument-type]


@pytest.fixture
def dwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[_Dwd]:
    """Stand in for `opendata.dwd.de/weather/radar/konrad3d/`: two scans, an empty one and one with two cells."""
    monkeypatch.setattr(
        "wetterdienst.provider.dwd.storm_cells.api._now", lambda: dt.datetime(2026, 11, 17, 22, 20, tzinfo=UTC)
    )
    with serving() as server:
        monkeypatch.setattr(
            "wetterdienst.provider.dwd.storm_cells.api.DWD_STORM_CELLS_BASE_URL", f"{server.base}{DIRECTORY[:-1]}"
        )
        server.directories[DIRECTORY] = [OLDER, NEWEST]
        for name, content in ((OLDER, EMPTY_SCAN), (NEWEST, TWO_CELLS_SCAN)):
            server.files.add(f"{DIRECTORY}{name}")
            server.contents[f"{DIRECTORY}{name}"] = content
        yield _Dwd(server, Settings(cache_dir=str(tmp_path / "cache")))


def test_the_newest_scan_is_listed_and_downloaded_once(dwd: _Dwd) -> None:
    """One request is one listing and one file, and nothing else (the older scan is not asked for)."""
    result = dwd.request().query()

    assert result.df.height == 2
    assert dwd.asked(DIRECTORY) == 1
    assert dwd.asked(f"{DIRECTORY}{NEWEST}") == 1
    assert dwd.asked(f"{DIRECTORY}{OLDER}") == 0


def test_a_second_request_is_answered_from_the_cache(dwd: _Dwd) -> None:
    """The listing is kept for a minute and a scan for half a day: nothing is asked of the server again."""
    dwd.request().query()
    dwd.server.requests.clear()

    again = dwd.request().query()

    assert again.df.height == 2
    assert dwd.server.requests == []


def test_a_timestamp_reads_the_scan_before_it(dwd: _Dwd) -> None:
    """The older scan is an empty one: the answer is the frame with no row, and the time of that scan."""
    result = dwd.request(timestamp="2026-11-17T22:12:00").query()

    assert result.df.is_empty()
    assert result.reference_time == dt.datetime(2026, 11, 15, 22, 20, tzinfo=UTC)
    assert dwd.asked(f"{DIRECTORY}{OLDER}") == 1


def test_a_429_on_the_file_is_the_rate_limit_error_asked_once(dwd: _Dwd) -> None:
    """DWD says to wait: the wait is the error's, and the file is not asked for again."""
    path = f"{DIRECTORY}{NEWEST}"
    dwd.server.statuses[path] = 429
    dwd.server.status_headers[path] = [("Retry-After", str(WAIT))]

    with pytest.raises(ProviderRateLimitError) as raised:
        dwd.request().query()

    assert raised.value.retry_after == WAIT
    assert dwd.asked(path) == 1


def test_a_429_on_the_listing_is_the_rate_limit_error(dwd: _Dwd) -> None:
    """The listing is the first request, and the first to be refused."""
    dwd.server.statuses[DIRECTORY] = 429
    dwd.server.status_headers[DIRECTORY] = [("Retry-After", str(WAIT))]

    with pytest.raises(ProviderRateLimitError) as raised:
        dwd.request().query()

    assert raised.value.retry_after == WAIT
    assert dwd.asked(DIRECTORY) == 1


def test_an_outage_page_answered_as_a_200_is_no_empty_directory(dwd: _Dwd) -> None:
    """A CDN's error page for the listing is a failure to read, and never "no scan" or a quiet sky."""
    dwd.server.pages[DIRECTORY] = ("text/html", b"<html><body>Service Unavailable</body></html>")

    with pytest.raises(DownloadError):
        dwd.request().query()


def test_a_scan_that_is_gone_since_the_listing_is_a_download_error(dwd: _Dwd) -> None:
    """A 404 on a file the listing names: the file rolled off the window in between."""
    dwd.server.statuses[f"{DIRECTORY}{NEWEST}"] = 404

    with pytest.raises(DownloadError, match=NEWEST.replace(".", r"\.")):
        dwd.request().query()


def test_a_directory_that_is_not_there_is_a_missing_file_of_dwd(dwd: _Dwd) -> None:
    """A 404 for the directory is DWD's (a 502), and no bare `FileNotFoundError` for a 500."""
    dwd.server.missing.add(DIRECTORY)

    with pytest.raises(MetaFileNotFoundError, match="no KONRAD3D directory") as raised:
        dwd.request().query()

    assert isinstance(raised.value.__cause__, FileNotFoundError)


def test_a_directory_with_no_scan_is_a_missing_file(dwd: _Dwd) -> None:
    """An empty listing is DWD's to answer for, as the missing file it is."""
    dwd.server.directories[DIRECTORY] = []

    with pytest.raises(MetaFileNotFoundError):
        dwd.request().query()


def test_a_scan_read_while_it_was_written_is_fetched_again_once_it_is_whole(dwd: _Dwd) -> None:
    """The cache would keep the half of a file for 12 hours: the next request that finds it unreadable asks again."""
    path = f"{DIRECTORY}{NEWEST}"
    dwd.server.contents[path] = TWO_CELLS_SCAN[:5000]

    with pytest.raises(MetaFileFormatError):
        dwd.request().query()
    assert dwd.asked(path) == 1

    # DWD has written the rest by now; the copy held is the half, which is read and refused, and fetched once more
    dwd.server.contents[path] = TWO_CELLS_SCAN
    result = dwd.request().query()

    assert result.df.height == 2
    assert dwd.asked(path) == 2
    # and the whole file is the copy held now
    dwd.server.requests.clear()
    assert dwd.request().query().df.height == 2
    assert dwd.asked(path) == 0
