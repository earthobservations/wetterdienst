# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""KOSTRA through a real download, from a local server that answers as DWD's does.

What is held is what is asked of the server (a lookup of one duration reads that table and nothing else, a second one
nothing at all) and what the library does with what it is given: a 429, a 404, a page of an outage answered as a 200,
and a copy kept in the cache that does not read.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.nginx_stub import NginxLike, serving
from wetterdienst import Settings
from wetterdienst.exceptions import DownloadError, MetaFileFormatError, ProviderRateLimitError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.dwd.kostra import DURATIONS, DwdKostraRequest
from wetterdienst.util.network import cached_file_time, download_file

from .stubs import BASE, BERLIN, MUNICH, TABLES, csv_name, csv_of, zipped

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

WAIT = 7


def _path(duration: int) -> str:
    return f"{BASE}{csv_name(duration)}.zip"


class _Dwd:
    def __init__(self, server: NginxLike, settings: Settings) -> None:
        self.server = server
        self.settings = settings

    def asked(self) -> list[str]:
        """List the files the server was asked for (GET), in order."""
        return [path.split("?")[0] for method, path in self.server.requests if method == "GET"]

    def request(self, point: tuple[float, float] = BERLIN, **arguments: int) -> DwdKostraRequest:
        return DwdKostraRequest(latitude=point[0], longitude=point[1], settings=self.settings, **arguments)


@pytest.fixture
def dwd(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[_Dwd]:
    """Stand in for the `tab/` directory of KOSTRA-DWD-2020 on `opendata.dwd.de`, with the 22 tables."""
    with serving() as server:
        monkeypatch.setattr(
            "wetterdienst.provider.dwd.kostra.metadata.DWD_KOSTRA_BASE_URL",
            f"{server.base}{BASE.removesuffix('/tab/')}",
        )
        for duration in DURATIONS:
            server.files.add(_path(duration))
            server.contents[_path(duration)] = TABLES[f"{csv_name(duration)}.zip"]
        yield _Dwd(server, Settings(cache_dir=str(tmp_path / "cache")))


def test_a_duration_asks_for_its_table_alone(dwd: _Dwd) -> None:
    """One duration is one file of the 22, which is 0.7 MB of the real ones."""
    result = dwd.request(duration=60).query()

    assert result.df.height == 9
    assert dwd.asked() == [_path(60)]


def test_a_second_lookup_is_answered_from_the_cache(dwd: _Dwd) -> None:
    """The files are static, so another cell of the same duration asks the server for nothing."""
    dwd.request(duration=60).query()
    dwd.server.requests.clear()

    again = dwd.request(MUNICH, duration=60).query()

    assert again.cell.index_rc == "203167"
    assert dwd.server.requests == []


def test_without_a_duration_the_22_tables_are_asked_for_once_each(dwd: _Dwd) -> None:
    """The whole table of a cell is 22 files, fetched together; the next lookup, of any cell, is the cache's."""
    result = dwd.request().query()

    assert result.df.height == 22 * 9
    assert sorted(dwd.asked()) == sorted(_path(duration) for duration in DURATIONS)

    dwd.server.requests.clear()
    assert dwd.request(MUNICH).query().df.height == 22 * 9
    assert dwd.request(duration=5).query().df.height == 9
    assert dwd.server.requests == []


def test_a_table_read_for_one_duration_is_kept_for_the_whole_table(dwd: _Dwd) -> None:
    """A lookup of 60 minutes first and of everything later asks for 21 files, not 22."""
    dwd.request(duration=60).query()
    dwd.server.requests.clear()

    dwd.request().query()

    assert _path(60) not in dwd.asked()
    assert len(dwd.asked()) == 21


def test_a_429_is_the_rate_limit_error_asked_once(dwd: _Dwd) -> None:
    """DWD says to wait: the wait is the error's, and the file is not asked for again."""
    dwd.server.statuses[_path(60)] = 429
    dwd.server.status_headers[_path(60)] = [("Retry-After", str(WAIT))]

    with pytest.raises(ProviderRateLimitError) as raised:
        dwd.request(duration=60).query()

    assert raised.value.retry_after == WAIT
    assert dwd.asked() == [_path(60)]


def test_a_table_that_is_gone_is_a_download_error(dwd: _Dwd) -> None:
    """A 404 is DWD's to answer for (a 502), naming the file, and no empty answer."""
    dwd.server.statuses[_path(60)] = 404

    with pytest.raises(DownloadError, match=csv_name(60)):
        dwd.request(duration=60).query()


def test_one_table_missing_of_the_22_fails_the_whole_answer(dwd: _Dwd) -> None:
    """A table of the 22 that cannot be had is no answer with a duration missing from it."""
    dwd.server.statuses[_path(1440)] = 503

    with pytest.raises(DownloadError):
        dwd.request().query()


def test_an_outage_page_answered_as_a_200_is_never_data(dwd: _Dwd) -> None:
    """A CDN's error page in place of the zip is a failure to read it: DWD's, a 502."""
    dwd.server.contents[_path(60)] = b"<html><body>Service Unavailable</body></html>"

    with pytest.raises(MetaFileFormatError, match="no readable zip archive"):
        dwd.request(duration=60).query()


def _cached(dwd: _Dwd, duration: int) -> float | None:
    """Tell when the cache made its copy of a table, None where it holds none."""
    return cached_file_time(
        f"{dwd.server.base}{_path(duration)}",
        cache_dir=dwd.settings.cache_dir,
        ttl=CacheExpiry.ONE_WEEK,
        client_kwargs=dwd.settings.fsspec_client_kwargs,
        cache_disable=dwd.settings.cache_disable,
        use_certifi=dwd.settings.use_certifi,
    )


def test_an_outage_page_is_not_kept_in_the_cache(dwd: _Dwd) -> None:
    """The cache would serve the page for a week: it is dropped as it is refused, and the next request asks DWD."""
    dwd.server.contents[_path(60)] = b"<html><body>Service Unavailable</body></html>"
    with pytest.raises(MetaFileFormatError):
        dwd.request(duration=60).query()
    assert dwd.asked() == [_path(60)]
    assert _cached(dwd, 60) is None

    dwd.server.contents[_path(60)] = TABLES[f"{csv_name(60)}.zip"]
    result = dwd.request(duration=60).query()

    assert result.df.height == 9
    assert dwd.asked() == [_path(60), _path(60)]
    # and the table is the copy held now
    assert _cached(dwd, 60) is not None
    dwd.server.requests.clear()
    assert dwd.request(duration=60).query().df.height == 9
    assert dwd.server.requests == []


def test_a_page_kept_by_an_older_request_is_fetched_again_once(dwd: _Dwd) -> None:
    """A copy made before pages were dropped (an outage page kept for a week) is asked for again, once."""
    page = b"<html><body>Service Unavailable</body></html>"
    dwd.server.contents[_path(60)] = page
    # what an older version left in the cache: the page, as a download of a 200
    held = download_file(
        f"{dwd.server.base}{_path(60)}",
        cache_dir=dwd.settings.cache_dir,
        ttl=CacheExpiry.ONE_WEEK,
        client_kwargs=dwd.settings.fsspec_client_kwargs,
    )
    assert held.status == 200
    assert _cached(dwd, 60) is not None
    dwd.server.requests.clear()

    # DWD has the table again: the copy held is read and refused, and the file asked for once more
    dwd.server.contents[_path(60)] = TABLES[f"{csv_name(60)}.zip"]
    assert dwd.request(duration=60).query().df.height == 9
    assert dwd.asked() == [_path(60)]
    assert _cached(dwd, 60) is not None


def test_a_value_that_is_no_number_is_not_kept_in_the_cache_either(dwd: _Dwd) -> None:
    """A table of the right layout with a text in the row of the cell is refused like any other, and dropped."""
    good = TABLES[f"{csv_name(60)}.zip"]
    bad = zipped(csv_of(60).replace(b";48,9;", b";n/a;"), csv_name(60))
    dwd.server.contents[_path(60)] = bad

    with pytest.raises(MetaFileFormatError, match="no number"):
        dwd.request(duration=60).query()
    assert _cached(dwd, 60) is None

    dwd.server.contents[_path(60)] = good
    assert dwd.request(duration=60).query().df.height == 9
    assert dwd.asked() == [_path(60), _path(60)]


def test_a_429_is_raised_before_the_other_failure_of_the_22_tables(dwd: _Dwd) -> None:
    """A table that is gone (a 404) and a limit (a 429): the limit is the answer, as the next request meets it too."""
    dwd.server.statuses[_path(5)] = 404
    dwd.server.statuses[_path(1440)] = 429
    dwd.server.status_headers[_path(1440)] = [("Retry-After", str(WAIT))]

    with pytest.raises(ProviderRateLimitError) as raised:
        dwd.request().query()

    assert raised.value.retry_after == WAIT
