# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The content of a KNMI file is kept under its own name, not under its pre-signed link (GH-3927).

A file whose timestamp is older than six hours is kept for 12 hours, a younger one for 5 minutes, as KNMI may still
fill it in.

Served by a local server that stands for the Data Platform: its API (the resolve of a link) and the store the link
leads to, so that the requests made are the ones counted. The link is made anew by every resolve, as KNMI's is.
"""

from __future__ import annotations

import datetime as dt
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import TYPE_CHECKING

import pytest

from wetterdienst.exceptions import DownloadError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.knmi.observation import api
from wetterdienst.provider.knmi.observation.api import (
    _fetch_netcdf,
    _file_expiry,
    _file_key,
    _moment_of,
)
from wetterdienst.settings import Settings

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

DATASET = "hourly-observations-validated"
VERSION = "1"
FILENAME = "hourly-observations-validated-20261014-08.nc"
BODY = b"the content of the netcdf file"


class _DataPlatform(BaseHTTPRequestHandler):
    """The API (`.../files/<name>/url` answers a link) and the store (`/store/<name>` answers the content)."""

    def do_GET(self) -> None:
        server = self.server
        server.requests.append(self.path)
        if self.path.endswith("/url"):
            name = self.path.rsplit("/", 2)[-2]
            server.links += 1
            body = b'{"temporaryDownloadUrl": "http://127.0.0.1:%d/store/%s?X-Amz-Signature=secret%d"}' % (
                server.server_port,
                name.encode(),
                server.links,
            )
        elif self.path.startswith("/store/"):
            if server.store_status != 200:
                self.send_response(server.store_status)
                self.end_headers()
                return
            body = BODY
        else:
            self.send_response(404)
            self.end_headers()
            return
        self.send_response(200)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        """Keep the test output free of the access log."""


@pytest.fixture
def platform(monkeypatch: pytest.MonkeyPatch) -> Iterator[ThreadingHTTPServer]:
    """Serve the Data Platform on a local port, and have the provider ask it."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _DataPlatform)
    server.requests = []
    server.links = 0
    server.store_status = 200
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr(api, "_BASE_URL", f"http://127.0.0.1:{server.server_port}/open-data/v1")
    # one attempt is a failure: the retries of a 5xx are not what is tested
    monkeypatch.setattr(api, "_RETRY_WAIT_INITIAL_SECONDS", 0.0)
    monkeypatch.setattr(api, "_RETRY_WAIT_MAX_SECONDS", 0.0)
    try:
        yield server
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def _settings(tmp_path: Path, *, cache_disable: bool = False) -> Settings:
    return Settings(auth={"knmi": "key-for-test"}, cache_dir=tmp_path / "cache", cache_disable=cache_disable)


def _ago(**age: float) -> dt.datetime:
    return dt.datetime.now(dt.UTC) - dt.timedelta(**age)


#: The timestamp of a file that has settled, and of one KNMI may still fill in
OLD = _ago(days=2)
RECENT = _ago(hours=1)


def _fetch(settings: Settings, moment: dt.datetime | None, filename: str = FILENAME) -> bytes | Exception:
    return _fetch_netcdf(DATASET, VERSION, filename, settings, moment)


def _store_requests(platform: ThreadingHTTPServer) -> list[str]:
    return [path for path in platform.requests if path.startswith("/store/")]


def _resolve_requests(platform: ThreadingHTTPServer) -> list[str]:
    return [path for path in platform.requests if path.endswith("/url")]


def _later(monkeypatch: pytest.MonkeyPatch, **delay: float) -> None:
    """Let the clock of fsspec's metadata and of the sweep, which read `time.time`, run on by `delay`."""
    later = time.time() + dt.timedelta(**delay).total_seconds()
    monkeypatch.setattr(time, "time", lambda: later)


def test_a_second_read_of_an_old_file_makes_no_request_to_knmi(platform: ThreadingHTTPServer, tmp_path: Path) -> None:
    """The copy is found by the name of the file: no resolve and no download, though the link changes every time."""
    settings = _settings(tmp_path)

    first = _fetch(settings, OLD)
    asked = list(platform.requests)
    second = _fetch(settings, OLD)

    assert first == BODY
    assert second == BODY
    assert len(asked) == 2  # one resolve, one download
    assert platform.requests == asked
    # nor from another thread, which has a filesystem of its own that reads the metadata file again
    answers: list[object] = []
    reader = threading.Thread(target=lambda: answers.append(_fetch(settings, OLD)))
    reader.start()
    reader.join()
    assert answers == [BODY]
    assert platform.requests == asked


def test_an_old_file_is_a_hit_within_twelve_hours_and_fetched_again_after(
    platform: ThreadingHTTPServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """11 hours on the copy is held, 12 hours and a minute on it is resolved and fetched again, with a new link."""
    settings = _settings(tmp_path)
    _fetch(settings, OLD)

    _later(monkeypatch, hours=11)
    assert _fetch(settings, OLD) == BODY
    assert len(_resolve_requests(platform)) == 1
    assert len(_store_requests(platform)) == 1

    _later(monkeypatch, hours=12, minutes=1)
    assert _fetch(settings, OLD) == BODY
    assert len(_resolve_requests(platform)) == 2
    assert len(_store_requests(platform)) == 2


def test_a_recent_file_is_a_hit_within_five_minutes_and_fetched_again_after(
    platform: ThreadingHTTPServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file KNMI may still fill in is kept for the five minutes it always was."""
    settings = _settings(tmp_path)
    _fetch(settings, RECENT)

    _later(monkeypatch, minutes=4)
    assert _fetch(settings, RECENT) == BODY
    assert len(_store_requests(platform)) == 1

    _later(monkeypatch, minutes=5, seconds=30)
    assert _fetch(settings, RECENT) == BODY
    assert len(_store_requests(platform)) == 2
    assert len(_resolve_requests(platform)) == 2


def test_another_file_is_a_miss(platform: ThreadingHTTPServer, tmp_path: Path) -> None:
    """The name is dataset, version and filename: the next hour is its own file."""
    settings = _settings(tmp_path)

    _fetch(settings, OLD)
    _fetch(settings, OLD, FILENAME.replace("-08", "-09"))

    assert len(_resolve_requests(platform)) == 2
    assert len(_store_requests(platform)) == 2


@pytest.mark.parametrize("moment", [OLD, RECENT], ids=["old", "recent"])
def test_cache_disable_asks_knmi_for_every_read(
    platform: ThreadingHTTPServer, tmp_path: Path, moment: dt.datetime
) -> None:
    """With the cache disabled no copy is kept, so every read resolves a link (the answer is not cached either)."""
    settings = _settings(tmp_path, cache_disable=True)

    assert _fetch(settings, moment) == BODY
    assert _fetch(settings, moment) == BODY

    assert len(_resolve_requests(platform)) == 2
    assert len(_store_requests(platform)) == 2
    assert not (tmp_path / "cache").exists() or not list((tmp_path / "cache").rglob("*.nc"))


@pytest.mark.usefixtures("platform")
def test_the_copy_is_kept_under_the_name_of_the_file_and_the_link_is_nowhere_in_its_cache(tmp_path: Path) -> None:
    """The cache of the content names the file, not the link whose signature is a secret for the hour it lasts."""
    settings = _settings(tmp_path)
    _fetch(settings, OLD)

    directory = next((tmp_path / "cache" / "fsspec").glob("*-ttl-TWELVE_HOURS"))
    held = "".join(path.read_text(errors="replace") for path in directory.iterdir() if path.is_file())

    assert _file_key(DATASET, VERSION, FILENAME) in held
    assert "/store/" not in held
    assert "X-Amz-Signature" not in held


@pytest.mark.parametrize("moment", [OLD, RECENT], ids=["old", "recent"])
def test_a_failed_download_names_the_file_and_not_the_link_and_keeps_no_copy(
    platform: ThreadingHTTPServer, tmp_path: Path, moment: dt.datetime
) -> None:
    """A store that does not answer is the `DownloadError` of the file, without the signature; nothing is kept."""
    platform.store_status = 503
    settings = _settings(tmp_path)

    failure = _fetch(settings, moment)

    assert isinstance(failure, DownloadError)
    assert FILENAME in failure.url
    assert "?" not in failure.url
    assert "secret" not in str(failure)
    assert "secret" not in repr(failure.__cause__)
    platform.store_status = 200
    assert _fetch(settings, moment) == BODY  # not served from a copy of the failure


@pytest.mark.parametrize(
    ("moment", "expected"),
    [
        pytest.param(None, CacheExpiry.FIVE_MINUTES, id="unknown"),
        pytest.param(_ago(minutes=10), CacheExpiry.FIVE_MINUTES, id="10 minutes"),
        pytest.param(_ago(hours=5, minutes=50), CacheExpiry.FIVE_MINUTES, id="just under six hours"),
        pytest.param(_ago(hours=6, minutes=10), CacheExpiry.TWELVE_HOURS, id="just over six hours"),
        pytest.param(_ago(days=30), CacheExpiry.TWELVE_HOURS, id="a month"),
        pytest.param(_ago(hours=7).replace(tzinfo=None), CacheExpiry.TWELVE_HOURS, id="without a zone"),
    ],
)
def test_the_age_of_the_timestamp_says_how_long_a_file_is_kept(
    moment: dt.datetime | None, expected: CacheExpiry
) -> None:
    """Younger than six hours is five minutes, older is twelve hours; a timestamp without a zone is UTC."""
    assert _file_expiry(moment) == expected


@pytest.mark.parametrize(
    ("filename", "moment"),
    [
        ("KMDS__OPER_P___10M_OBS_L2_202610140900.nc", dt.datetime(2026, 10, 14, 9, 0, tzinfo=dt.UTC)),
        ("hourly-observations-validated-20261014-08.nc", dt.datetime(2026, 10, 14, 8, 0, tzinfo=dt.UTC)),
        ("daily-observations-validated-20261014.nc", dt.datetime(2026, 10, 14, tzinfo=dt.UTC)),
        ("latest.nc", None),
    ],
)
def test_the_moment_of_a_file_is_read_from_its_name(filename: str, moment: dt.datetime | None) -> None:
    """The latest file of a listing is asked for by name only, and its age is read from it."""
    assert _moment_of(filename) == moment
