# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The `Last-Modified` of a downloaded file: what `File` keeps, and what the cache keeps with a copy (GH-2567)."""

from __future__ import annotations

import datetime as dt
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

import pytest

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.util.datetime import parse_http_date
from wetterdienst.util.network import (
    NetworkFilesystemManager,
    _read_sidecar,
    _remember_last_modified,
    _write_sidecar,
    cached_copy_is_held,
    download_file,
    download_files,
)

if TYPE_CHECKING:
    import os
    from collections.abc import Iterator
    from pathlib import Path

FIRST = "Sun, 25 Oct 2026 09:00:07 GMT"
SECOND = "Sat, 24 Oct 2026 06:53:00 GMT"
THIRD = "Fri, 23 Oct 2026 07:00:00 GMT"


@pytest.mark.parametrize(
    ("header", "expected"),
    [
        ("Sun, 25 Oct 2026 09:00:07 GMT", dt.datetime(2026, 10, 25, 9, 0, 7, tzinfo=dt.UTC)),
        ("Sun, 25 Oct 2026 11:00:07 +0200", dt.datetime(2026, 10, 25, 9, 0, 7, tzinfo=dt.UTC)),
        ("  Sun, 25 Oct 2026 09:00:07 GMT ", dt.datetime(2026, 10, 25, 9, 0, 7, tzinfo=dt.UTC)),
        # the two older formats a server may still send, both GMT
        ("Sunday, 25-Oct-26 09:00:07 GMT", dt.datetime(2026, 10, 25, 9, 0, 7, tzinfo=dt.UTC)),
        ("Sun Oct 25 09:00:07 2026", dt.datetime(2026, 10, 25, 9, 0, 7, tzinfo=dt.UTC)),
    ],
)
def test_parse_http_date_reads_an_http_date_into_utc(header: str, expected: dt.datetime) -> None:
    """Every form of an HTTP-date comes out as the same aware UTC datetime."""
    assert parse_http_date(header) == expected
    assert parse_http_date(header).tzinfo is not None


@pytest.mark.parametrize(
    "header",
    [
        None,
        "",
        "   ",
        "garbage",
        "Sun, 99 Oct 2026 09:00:07 GMT",
        "2026-10-25",
        42,
        # the epoch a static server answers with when it does not know
        "Thu, 01 Jan 1970 00:00:00 GMT",
    ],
)
def test_parse_http_date_gives_none_for_what_is_no_date(header: object) -> None:
    """Absent, garbage and impossible dates are no date, and never the time of the request."""
    assert parse_http_date(header) is None


def test_parse_http_date_gives_none_for_a_date_in_the_future() -> None:
    """A file is not written in the future, so that is a clock and no date.

    Built here and not in the parameters: a test whose id holds the time of its collection is collected differently by
    two workers on either side of a second.
    """
    two_days_on = (dt.datetime.now(dt.UTC) + dt.timedelta(days=2)).strftime("%a, %d %b %Y %H:%M:%S GMT")

    assert parse_http_date(two_days_on) is None


class _Source(BaseHTTPRequestHandler):
    """A static file server whose `Last-Modified` the test can change between requests."""

    def do_GET(self) -> None:
        server = self.server
        server.requests.append(self.path)
        if server.fail:
            self.send_response(500)
            self.end_headers()
            return
        if self.path == "/redirect":
            self.send_response(302)
            self.send_header("Location", "/file.txt")
            self.send_header("Last-Modified", "Sat, 01 Aug 2026 00:00:00 GMT")  # the redirect's own is not the file's
            self.end_headers()
            return
        if self.path == "/answered-before-written":
            # the answer says it was made on the 23rd, of a file it says was written on the 25th
            body = b"x"
            self.send_response_only(200)
            self.send_header("Date", THIRD)
            self.send_header("Last-Modified", FIRST)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/answered-when-written":
            # the answer of a server that sends the time of the request as the date of the file: the two are equal
            body = b"x"
            self.send_response_only(200)
            self.send_header("Date", FIRST)
            self.send_header("Last-Modified", FIRST)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/missing":
            self.send_response(404)
            self.send_header("Last-Modified", server.last_modified or FIRST)
            self.end_headers()
            return
        body = server.body
        self.send_response(200)
        if server.last_modified is not None:
            self.send_header("Last-Modified", server.last_modified)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        """Keep the test output free of the access log."""


@pytest.fixture
def source() -> Iterator[ThreadingHTTPServer]:
    """Serve `/file.txt` with the `Last-Modified` and body the test sets on the server."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Source)
    server.requests = []
    server.last_modified = FIRST
    server.body = b"first body"
    server.fail = False
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _url(server: ThreadingHTTPServer, path: str = "/file.txt") -> str:
    return f"http://127.0.0.1:{server.server_port}{path}"


def _utc(text: str) -> dt.datetime:
    parsed = parse_http_date(text)
    assert parsed is not None
    return parsed


def test_a_file_has_the_last_modified_of_its_response(source: ThreadingHTTPServer, tmp_path: Path) -> None:
    """Fetched without a cache, the date is the header of the response the body came with."""
    file = download_file(_url(source), cache_dir=tmp_path, ttl=CacheExpiry.NO_CACHE)

    assert file.status == 200
    assert file.last_modified == _utc(FIRST)


def test_a_file_follows_a_redirect_to_the_date_of_the_file_it_ended_at(
    source: ThreadingHTTPServer,
    tmp_path: Path,
) -> None:
    """The date is the one of the file that was read, not of the hop that led to it."""
    file = download_file(_url(source, "/redirect"), cache_dir=tmp_path, ttl=CacheExpiry.NO_CACHE)

    assert file.last_modified == _utc(FIRST)


@pytest.mark.parametrize("header", [None, "garbage"])
def test_a_file_without_a_date_has_none_and_never_the_time_of_the_request(
    header: str | None,
    source: ThreadingHTTPServer,
    tmp_path: Path,
) -> None:
    """No header, or one that is no date, is `None` however the file is fetched."""
    source.last_modified = header

    uncached = download_file(_url(source), cache_dir=tmp_path, ttl=CacheExpiry.NO_CACHE)
    cached = download_file(_url(source), cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    from_cache = download_file(_url(source), cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)

    assert uncached.last_modified is None
    assert cached.last_modified is None
    assert from_cache.from_cache is True
    assert from_cache.last_modified is None


def test_a_file_dated_after_the_answer_that_carries_it_has_no_date(
    source: ThreadingHTTPServer,
    tmp_path: Path,
) -> None:
    """A `Last-Modified` later than the `Date` of its own response is the time of a request, not of a file."""
    uncached = download_file(_url(source, "/answered-before-written"), cache_dir=tmp_path, ttl=CacheExpiry.NO_CACHE)
    cached = download_file(_url(source, "/answered-before-written"), cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)

    assert uncached.last_modified is None
    assert cached.last_modified is None


def test_a_file_dated_the_second_of_the_answer_that_carries_it_has_no_date(
    source: ThreadingHTTPServer,
    tmp_path: Path,
) -> None:
    """A `Last-Modified` equal to the `Date` is the time of the request (FMI answers so), not of a file."""
    uncached = download_file(_url(source, "/answered-when-written"), cache_dir=tmp_path, ttl=CacheExpiry.NO_CACHE)
    cached = download_file(_url(source, "/answered-when-written"), cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)

    assert uncached.last_modified is None
    assert cached.last_modified is None


def test_a_failed_download_has_no_date(source: ThreadingHTTPServer, tmp_path: Path) -> None:
    """The 404 that carries a `Last-Modified` is no file, and says no date."""
    file = download_file(_url(source, "/missing"), cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)

    assert file.status == 404
    assert file.last_modified is None


def test_a_cached_answer_keeps_the_date_of_the_copy_it_is(source: ThreadingHTTPServer, tmp_path: Path) -> None:
    """The second answer comes from the cache with the first date, while the server's header has moved on."""
    url = _url(source)
    first = download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    source.last_modified = SECOND
    source.body = b"second body"
    second = download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)

    assert first.from_cache is False
    assert first.last_modified == _utc(FIRST)
    assert second.from_cache is True
    assert second.content.read() == b"first body"
    assert second.last_modified == _utc(FIRST)
    # and it cost no request
    assert source.requests == ["/file.txt"]


def _expire(url: str, cache_dir: Path) -> None:
    """Make the entry of a url in the metadata file one written long ago, and have this thread read it.

    On disk and not in the memory of the filesystem: a thread that finds no copy reads the file again, so an entry
    that expired only in memory is a copy that is held.
    """
    filesystem = NetworkFilesystemManager.get(
        cache_dir=cache_dir, cache_expiry=CacheExpiry.ONE_HOUR, cache_disable=False
    )
    (metadata_file,) = cache_dir.rglob("cache")
    entries = json.loads(metadata_file.read_text(encoding="utf-8"))
    entries[url]["time"] = 0
    metadata_file.write_text(json.dumps(entries), encoding="utf-8")
    filesystem.load_cache()


def test_a_cached_copy_refreshed_has_the_new_date(source: ThreadingHTTPServer, tmp_path: Path) -> None:
    """A copy fetched anew over an expired one is dated by the new response, not the old copy's."""
    url = _url(source)
    download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    source.last_modified = SECOND
    source.body = b"second body"
    _expire(url, tmp_path)

    refreshed = download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    again = download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)

    assert refreshed.from_cache is False
    assert refreshed.content.read() == b"second body"
    assert refreshed.last_modified == _utc(SECOND)
    assert again.from_cache is True
    assert again.last_modified == _utc(SECOND)
    assert source.requests == ["/file.txt", "/file.txt"]


def test_a_cached_copy_refreshed_without_a_date_has_none(source: ThreadingHTTPServer, tmp_path: Path) -> None:
    """A refresh whose response states no date does not keep the date of the copy it replaced."""
    url = _url(source)
    download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    source.last_modified = None
    source.body = b"second body"
    _expire(url, tmp_path)

    refreshed = download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    again = download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)

    assert refreshed.last_modified is None
    assert again.from_cache is True
    assert again.last_modified is None


def test_a_copy_cached_before_dates_were_kept_has_none_and_not_a_guess(
    source: ThreadingHTTPServer,
    tmp_path: Path,
) -> None:
    """An entry without a sidecar answers `None`, not the time it was written."""
    url = _url(source)
    download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    sidecars = list(tmp_path.rglob("*.lm"))
    assert len(sidecars) == 1
    sidecars[0].unlink()

    second = download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)

    assert second.from_cache is True
    assert second.last_modified is None


def test_a_blob_the_sidecar_does_not_describe_has_no_date(source: ThreadingHTTPServer, tmp_path: Path) -> None:
    """A copy put there by another process since is a blob the date was not kept for."""
    url = _url(source)
    download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    (sidecar,) = tmp_path.rglob("*.lm")
    blob = sidecar.with_name(sidecar.name.removesuffix(".lm"))
    blob.write_bytes(b"another body, of another length")

    second = download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)

    assert second.from_cache is True
    assert second.content.read() == b"another body, of another length"
    assert second.last_modified is None


def test_a_sidecar_that_is_unreadable_is_no_date_and_no_failure(source: ThreadingHTTPServer, tmp_path: Path) -> None:
    """A damaged sidecar costs the date, not the download."""
    url = _url(source)
    download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    (sidecar,) = tmp_path.rglob("*.lm")
    sidecar.write_text("{not json", encoding="utf-8")

    second = download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)

    assert second.status == 200
    assert second.last_modified is None


def test_the_sweep_of_expired_copies_takes_their_sidecars(source: ThreadingHTTPServer, tmp_path: Path) -> None:
    """A blob that expires leaves no date behind."""
    url = _url(source)
    download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    filesystem = NetworkFilesystemManager.get(
        cache_dir=tmp_path, cache_expiry=CacheExpiry.ONE_HOUR, cache_disable=False
    )
    (sidecar,) = tmp_path.rglob("*.lm")
    # the entry written long ago, as the file of fsspec's metadata says it
    (metadata_file,) = tmp_path.rglob("cache")
    entries = json.loads(metadata_file.read_text(encoding="utf-8"))
    entries[url]["time"] = 0
    metadata_file.write_text(json.dumps(entries), encoding="utf-8")
    filesystem.load_cache()

    # another entry keeps the directory from being removed whole
    other = _url(source, "/other.txt")
    download_file(other, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    filesystem.clear_expired_cache(expiry_time=3600)

    assert not sidecar.exists()
    assert len(list(tmp_path.rglob("*.lm"))) == 1


def test_dropping_a_cached_file_drops_its_date(source: ThreadingHTTPServer, tmp_path: Path) -> None:
    """A copy dropped by the caller (a body that was an error) is read again, with the date of the new one."""
    from wetterdienst.util.network import drop_cached_file  # noqa: PLC0415

    url = _url(source)
    download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    drop_cached_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)

    assert list(tmp_path.rglob("*.lm")) == []

    source.last_modified = THIRD
    again = download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    assert again.last_modified == _utc(THIRD)


def test_download_files_gives_each_file_its_own_date(source: ThreadingHTTPServer, tmp_path: Path) -> None:
    """Every file of a concurrent download carries the date of its own response."""
    urls = [_url(source, f"/f{i}.txt") for i in range(4)]

    files = download_files(urls, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    again = download_files(urls, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)

    assert [file.last_modified for file in files] == [_utc(FIRST)] * 4
    assert [file.from_cache for file in again] == [True] * 4
    assert [file.last_modified for file in again] == [_utc(FIRST)] * 4


def test_the_dates_a_filesystem_remembers_are_bounded() -> None:
    """A reader that never takes its date (the KML of a forecast) does not make the dict grow for ever."""
    registry: dict[str, dt.datetime | None] = {}
    for index in range(1000):
        _remember_last_modified(registry, f"https://example.invalid/{index}", None)

    assert len(registry) <= 256
    assert registry["https://example.invalid/999"] is None


def test_a_copy_fetched_again_before_a_time_has_the_new_date_and_a_failed_refetch_leaves_the_old_copy_its_own(
    source: ThreadingHTTPServer, tmp_path: Path
) -> None:
    """`refetch_before` makes a copy made earlier be fetched again, and the date goes with the copy that is held."""
    url = _url(source)
    first = download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)
    source.last_modified = SECOND
    source.body = b"second body"
    source.fail = True

    failed = download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR, refetch_before=time.time() + 60)
    held = download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)

    assert failed.status == 500
    assert failed.last_modified is None
    # the copy that was held is read again as it was, with the date of the server for it
    assert held.from_cache is True
    assert held.content.read() == b"first body"
    assert held.last_modified == _utc(FIRST) == first.last_modified
    assert held.cached_at == first.cached_at

    source.fail = False
    refetched = download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR, refetch_before=time.time() + 60)
    after = download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.ONE_HOUR)

    assert refetched.from_cache is False
    assert refetched.content.read() == b"second body"
    assert refetched.last_modified == _utc(SECOND)
    assert after.from_cache is True
    assert after.last_modified == _utc(SECOND)
    assert after.cached_at == refetched.cached_at
    assert after.cached_at > first.cached_at


def test_a_copy_without_a_record_of_its_date_is_fetched_once_more_and_one_with_a_record_never(
    source: ThreadingHTTPServer, tmp_path: Path
) -> None:
    """The copy of a version that kept no dates is told by having no record at all: one fetch more, whatever the time.

    A server that sends no date leaves a record of that too, so the copies it gave are not fetched again and again.
    """
    source.last_modified = None
    url = _url(source)

    def read() -> object:
        return download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.INFINITE, refetch_undated=True)

    # a copy made by this version, the server having sent no date: a record with a null date
    first = read()
    again = [read() for _ in range(3)]
    assert (first.from_cache, [file.from_cache for file in again]) == (False, [True, True, True])
    assert source.requests == ["/file.txt"]
    (sidecar,) = tmp_path.rglob("*.lm")
    assert json.loads(sidecar.read_text(encoding="utf-8"))["last_modified"] is None

    # a copy made by the version before: no record at all
    sidecar.unlink()
    refetched = read()
    after = [read() for _ in range(3)]

    assert refetched.from_cache is False
    assert [file.from_cache for file in after] == [True, True, True]
    assert source.requests == ["/file.txt", "/file.txt"]
    assert len(list(tmp_path.rglob("*.lm"))) == 1


def test_a_copy_with_a_date_is_not_fetched_once_more_for_it(source: ThreadingHTTPServer, tmp_path: Path) -> None:
    """A copy that has its date, the one fetch more having given it, is held as any."""
    url = _url(source)
    download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.INFINITE)
    held = download_file(url, cache_dir=tmp_path, ttl=CacheExpiry.INFINITE, refetch_undated=True)

    assert held.from_cache is True
    assert held.last_modified == _utc(FIRST)
    assert source.requests == ["/file.txt"]


def test_a_copy_held_is_told_from_one_that_is_not(source: ThreadingHTTPServer, tmp_path: Path) -> None:
    """`cached_copy_is_held` says whether a download with these arguments would be served from the cache."""
    url = _url(source)
    held = {"cache_dir": tmp_path, "ttl": CacheExpiry.ONE_HOUR}

    assert cached_copy_is_held(url, **held) is False
    download_file(url, **held)
    assert cached_copy_is_held(url, **held) is True
    assert cached_copy_is_held(url, tmp_path, CacheExpiry.NO_CACHE) is False
    assert cached_copy_is_held(url, tmp_path, CacheExpiry.ONE_HOUR, cache_disable=True) is False


@pytest.mark.parametrize("later_first", [True, False])
def test_a_sidecar_of_a_fetch_whose_blob_was_replaced_since_is_not_written(
    tmp_path: Path, *, later_first: bool
) -> None:
    """Two fetches replace one blob in turn: the sidecar of the one that is no longer the blob never covers the other.

    A replaces the blob, B replaces it, and then the sidecars are written, in either order: only the one of B (the blob
    now) is kept. Without the check the sidecar of A, written last, replaces that of B, and blob B then reads no date at
    all: a date is lost, none is wrong, as the sidecar says which blob it is of.
    """
    blob = tmp_path / "blob"
    stat_of_a = _replace(blob, b"the body of A")
    stat_of_b = _replace(blob, b"the body of B, which is longer")
    writes = [(_utc(SECOND), stat_of_b), (_utc(FIRST), stat_of_a)]

    for date, stat in writes if later_first else reversed(writes):
        _write_sidecar(blob, date, stat)

    assert _read_sidecar(blob) == _utc(SECOND)


def _replace(blob: Path, body: bytes) -> os.stat_result:
    """Put a body where the blob is, as a fetch does, by renaming a file of its own onto it, and give its stat."""
    temp = blob.with_name(f"{blob.name}.{len(body)}.tmp")
    temp.write_bytes(body)
    written = temp.stat()
    temp.replace(blob)
    return written


def test_a_sidecar_is_not_written_for_a_blob_that_is_gone(tmp_path: Path) -> None:
    """A copy swept away before its date was written has no date to keep, and nothing fails."""
    blob = tmp_path / "blob"
    written = _replace(blob, b"body")
    blob.unlink()

    _write_sidecar(blob, _utc(FIRST), written)

    assert list(tmp_path.iterdir()) == []
