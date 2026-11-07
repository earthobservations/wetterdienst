# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the file index helpers of the IMGW providers."""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import polars as pl
import portion
import pytest

from tests.nginx_stub import NginxLike, serving
from wetterdienst import Settings
from wetterdienst.exceptions import DownloadError
from wetterdienst.provider.imgw.fileindex import keep_files_overlapping, list_files_for_interval

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

UTC = ZoneInfo("UTC")


def _kept(interval: portion.Interval) -> list[str]:
    """Name the files of 2020, 2021 and 2022 that a window keeps, each covering its year."""
    df = pl.DataFrame({"file": ["a", "b", "c"], "year": [2020, 2021, 2022]})
    start = pl.datetime(pl.col("year"), 1, 1, time_zone="UTC")
    end = pl.datetime(pl.col("year"), 12, 31, time_zone="UTC")
    return keep_files_overlapping(df, start, end, interval).get_column("file").to_list()


def test_keep_files_overlapping_includes_both_ends_of_a_period() -> None:
    """Test that a window touching the first or last instant of a period keeps its file."""
    window = portion.closed(dt.datetime(2020, 12, 31, tzinfo=UTC), dt.datetime(2021, 1, 1, tzinfo=UTC))
    assert _kept(window) == ["a", "b"]
    window = portion.closed(dt.datetime(2021, 12, 31, 1, tzinfo=UTC), dt.datetime(2022, 1, 1, tzinfo=UTC))
    assert _kept(window) == ["c"]


def test_keep_files_overlapping_compares_instants_not_wall_clocks() -> None:
    """Test that a window written in another zone cuts at the same instants as one written in UTC."""
    berlin = ZoneInfo("Europe/Berlin")
    # 2020-12-31 00:30 in Berlin is 2020-12-30 23:30 UTC, before the last instant of the file of 2020 (2020-12-31
    # 00:00 UTC); read as UTC it would be half an hour after it
    instant = dt.datetime(2020, 12, 31, 0, 30, tzinfo=berlin)
    assert _kept(portion.closed(instant, instant)) == ["a"]


def test_keep_files_overlapping_keeps_nothing_for_an_empty_window() -> None:
    """Test that a window that ends before it starts overlaps no file, however wide the files are."""
    assert _kept(portion.closed(dt.datetime(2021, 6, 1, tzinfo=UTC), dt.datetime(2021, 5, 1, tzinfo=UTC))) == []


def test_keep_files_overlapping_refuses_a_file_without_a_period() -> None:
    """Test that a file whose period is null is an error that names it, not a file left out."""
    df = pl.DataFrame({"file": ["a", "b"], "year": [2020, None]})
    start = pl.datetime(pl.col("year"), 1, 1, time_zone="UTC")
    end = pl.datetime(pl.col("year"), 12, 31, time_zone="UTC")
    window = portion.closed(dt.datetime(2020, 1, 1, tzinfo=UTC), dt.datetime(2020, 2, 1, tzinfo=UTC))
    with pytest.raises(ValueError, match=r"\['b'\]"):
        keep_files_overlapping(df, start, end, window)


def test_keep_files_overlapping_drops_a_period_that_ends_before_it_starts() -> None:
    """Test that a file whose period is empty overlaps no window, as an empty interval did."""
    df = pl.DataFrame({"file": ["a", "b"], "first": [2020, 2022], "last": [2021, 2019]})
    start = pl.datetime(pl.col("first"), 1, 1, time_zone="UTC")
    end = pl.datetime(pl.col("last"), 12, 31, time_zone="UTC")
    window = portion.closed(dt.datetime(2019, 1, 1, tzinfo=UTC), dt.datetime(2023, 1, 1, tzinfo=UTC))
    assert keep_files_overlapping(df, start, end, window).get_column("file").to_list() == ["a"]


# --- the listing of a directory, against a server that answers as nginx does (GH-3834) -------------------------------

_CDN_PAGE = (
    "<html><head><title>503 - CDN</title></head><body><h1>Service unavailable</h1>"
    '<a href="https://status.example.com/">status</a></body></html>'
)


@pytest.fixture
def server() -> Iterator[NginxLike]:
    """Serve a tree of period folders (`2023/`, `2024/`) below `/data/` as an index page for each."""
    with serving() as state:
        state.directories["/data/"] = ["2023/", "2024/"]
        state.directories["/data/2023/"] = ["2023_01_s.zip"]
        state.directories["/data/2024/"] = ["2024_01_s.zip"]
        yield state


def _list(server: NginxLike, tmp_path: Path, interval: portion.Interval | None = None) -> list[str]:
    settings = Settings(cache_dir=str(tmp_path / "cache"))
    return list_files_for_interval(f"{server.base}/data/", settings, interval)


def test_the_files_of_the_period_folders_are_listed(server: NginxLike, tmp_path: Path) -> None:
    """The control: with every directory an index, the files of the folders are listed, as before."""
    assert sorted(url.rsplit("/", 1)[-1] for url in _list(server, tmp_path)) == ["2023_01_s.zip", "2024_01_s.zip"]


@pytest.mark.parametrize(
    ("content_type", "body"),
    [
        pytest.param("text/html", _CDN_PAGE.encode(), id="cdn-page"),
        pytest.param("application/json", b'{"error": "unavailable"}', id="json"),
    ],
)
def test_an_outage_page_for_the_dataset_directory_is_an_error_not_no_files(
    server: NginxLike, tmp_path: Path, content_type: str, body: bytes
) -> None:
    """A 200 page that is no index of a directory read as no file at all, and so as a station without data."""
    server.pages["/data/"] = (content_type, body)
    server.pages["/data"] = (content_type, body)

    with pytest.raises(DownloadError, match="not the index page of a directory"):
        _list(server, tmp_path)


@pytest.mark.parametrize(
    "link",
    ["/data/", "@BASE@/data/", "", "./", ".", "?retry=1"],
    ids=["root-relative", "absolute", "empty", "dot-slash", "dot", "query"],
)
def test_an_outage_page_that_links_to_itself_is_an_error_not_no_files(
    server: NginxLike, tmp_path: Path, link: str
) -> None:
    """The page lists as the one directory it links to (itself): the first listing, and the second from the cache."""
    page = f'<html><head><title>503</title></head><body>Try <a href="{link}">again</a></body></html>'
    body = page.replace("@BASE@", server.base).encode()
    server.pages["/data/"] = ("text/html", body)
    server.pages["/data"] = ("text/html", body)

    for _ in range(2):
        with pytest.raises(DownloadError, match="not the index page of a directory"):
            _list(server, tmp_path)


def test_an_outage_page_for_a_period_folder_is_an_error_not_the_files_of_the_others(
    server: NginxLike, tmp_path: Path
) -> None:
    """The folder of 2023 answers a page that is no index: its files are not "none", the listing fails."""
    server.pages["/data/2023/"] = ("application/json", b'{"error": "unavailable"}')
    server.pages["/data/2023"] = ("application/json", b'{"error": "unavailable"}')

    with pytest.raises(DownloadError, match="not the index page of a directory"):
        _list(server, tmp_path)


def test_a_period_folder_that_is_an_empty_directory_has_no_files(server: NginxLike, tmp_path: Path) -> None:
    """A real index with no link is a folder with nothing in it: the files of the other folders are listed."""
    server.directories["/data/2023/"] = []

    assert [url.rsplit("/", 1)[-1] for url in _list(server, tmp_path)] == ["2024_01_s.zip"]


def test_the_outage_page_reaches_the_values_of_both_providers(
    server: NginxLike, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`_get_urls` of the hydrology and the meteorology values raise it: no file list that reads as no data."""
    from types import SimpleNamespace  # noqa: PLC0415

    from wetterdienst.provider.imgw.hydrology.api import ImgwHydrologyMetadata, ImgwHydrologyValues  # noqa: PLC0415
    from wetterdienst.provider.imgw.meteorology.api import (  # noqa: PLC0415
        ImgwMeteorologyMetadata,
        ImgwMeteorologyValues,
    )

    server.pages["/data/"] = ("application/json", b'{"error": "unavailable"}')
    server.pages["/data"] = ("application/json", b'{"error": "unavailable"}')
    settings = Settings(cache_dir=str(tmp_path / "cache"))
    monkeypatch.setattr(ImgwHydrologyValues, "_endpoint", f"{server.base}/data/")
    monkeypatch.setattr(ImgwMeteorologyValues, "_endpoint", f"{server.base}/data/")

    hydrology = ImgwHydrologyValues.__new__(ImgwHydrologyValues)
    hydrology.sr = SimpleNamespace(start=None, end=None, settings=settings)  # ty: ignore[invalid-assignment]
    with pytest.raises(DownloadError, match="not the index page of a directory"):
        hydrology._get_urls(ImgwHydrologyMetadata.daily.hydrology)  # noqa: SLF001

    meteorology = ImgwMeteorologyValues.__new__(ImgwMeteorologyValues)
    meteorology.sr = SimpleNamespace(start=None, end=None, settings=settings)  # ty: ignore[invalid-assignment]
    with pytest.raises(DownloadError, match="not the index page of a directory"):
        meteorology._get_urls(ImgwMeteorologyMetadata.daily.synop, "249180100")  # noqa: SLF001
