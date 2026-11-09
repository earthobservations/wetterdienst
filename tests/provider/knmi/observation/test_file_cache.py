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

import polars as pl
import pytest

from wetterdienst.exceptions import DownloadError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.knmi.observation import api
from wetterdienst.provider.knmi.observation.api import (
    KnmiObservationRequest,
    _end_of,
    _fetch_netcdf,
    _file_expiry,
    _file_key,
    _filename_for,
    _forgotten_if_unreadable,
)
from wetterdienst.settings import Settings

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

DATASET = "hourly-observations-validated"
VERSION = "1"
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


#: The time the provider takes the age of a file against, pinned: a name built from the wall clock would be older
#: than six hours once the clock passed the top of an hour
NOW = dt.datetime(2026, 11, 9, 12, 30, tzinfo=dt.UTC)


@pytest.fixture(autouse=True)
def _pinned_now(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin what `_file_expiry` reads as now, and nothing else: `time.time` stays the clock of the cache (`_later`)."""
    monkeypatch.setattr(api, "_now", lambda: NOW)


def _ago(**age: float) -> dt.datetime:
    return NOW - dt.timedelta(**age)


def _hourly(**age: float) -> str:
    """Name the hourly file of the hour that began `age` ago (to the hour), which ends an hour after it."""
    start = _ago(**age).replace(minute=0, second=0, microsecond=0)
    return _filename_for(Resolution.HOURLY, start)


#: A file that has settled, and one KNMI may still fill in
OLD = _hourly(days=2)
RECENT = _hourly(hours=1)
#: Named for 06:00 against a now of 12:30: the name is 6.5 hours old, the stamp of its values (an hour on) 5.5: young.
#: The name is older than six hours, which is what an age taken from the name alone would go by
NAMED_BEYOND_SIX_HOURS = _hourly(hours=6)
#: Named for 05:00: its end is 6.5 hours old, settled
ENDED_BEYOND_SIX_HOURS = _hourly(hours=7)


def _fetch(settings: Settings, filename: str = OLD) -> bytes | Exception:
    return _fetch_netcdf(DATASET, VERSION, filename, settings)


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
    _fetch(settings, _hourly(days=3))

    assert len(_resolve_requests(platform)) == 2
    assert len(_store_requests(platform)) == 2


@pytest.mark.parametrize("filename", [OLD, RECENT], ids=["old", "recent"])
def test_cache_disable_asks_knmi_for_every_read(platform: ThreadingHTTPServer, tmp_path: Path, filename: str) -> None:
    """With the cache disabled no copy is kept, so every read resolves a link (the answer is not cached either)."""
    settings = _settings(tmp_path, cache_disable=True)

    assert _fetch(settings, filename) == BODY
    assert _fetch(settings, filename) == BODY

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

    assert _file_key(DATASET, VERSION, OLD) in held
    assert "/store/" not in held
    assert "X-Amz-Signature" not in held


@pytest.mark.parametrize("filename", [OLD, RECENT], ids=["old", "recent"])
def test_a_failed_download_names_the_file_and_not_the_link_and_keeps_no_copy(
    platform: ThreadingHTTPServer, tmp_path: Path, filename: str
) -> None:
    """A store that does not answer is the `DownloadError` of the file, without the signature; nothing is kept."""
    platform.store_status = 503
    settings = _settings(tmp_path)

    failure = _fetch(settings, filename)

    assert isinstance(failure, DownloadError)
    assert filename in failure.url
    assert "?" not in failure.url
    assert "secret" not in str(failure)
    assert "secret" not in repr(failure.__cause__)
    platform.store_status = 200
    assert _fetch(settings, filename) == BODY  # not served from a copy of the failure


@pytest.mark.parametrize(
    ("end", "expected"),
    [
        pytest.param(None, CacheExpiry.FIVE_MINUTES, id="unknown"),
        pytest.param(_ago(minutes=10), CacheExpiry.FIVE_MINUTES, id="10 minutes"),
        pytest.param(_ago(hours=5, minutes=50), CacheExpiry.FIVE_MINUTES, id="just under six hours"),
        pytest.param(_ago(hours=6, minutes=10), CacheExpiry.TWELVE_HOURS, id="just over six hours"),
        pytest.param(_ago(days=30), CacheExpiry.TWELVE_HOURS, id="a month"),
        pytest.param(_ago(hours=7).replace(tzinfo=None), CacheExpiry.TWELVE_HOURS, id="without a zone"),
    ],
)
def test_the_age_of_the_end_says_how_long_a_file_is_kept(end: dt.datetime | None, expected: CacheExpiry) -> None:
    """Ended less than six hours ago is five minutes, earlier is twelve hours; a time without a zone is UTC."""
    assert _file_expiry(end) == expected


@pytest.mark.parametrize(
    ("filename", "end"),
    [
        # the 10-minute name is the end of its interval
        ("KMDS__OPER_P___10M_OBS_L2_202610140900.nc", dt.datetime(2026, 10, 14, 9, 0, tzinfo=dt.UTC)),
        # the hourly name is the start of its hour, whose values are stamped with its end
        ("hourly-observations-validated-20261014-08.nc", dt.datetime(2026, 10, 14, 9, 0, tzinfo=dt.UTC)),
        # the daily name is its date, and the day ends at the next midnight
        ("daily-observations-validated-20261014.nc", dt.datetime(2026, 10, 15, tzinfo=dt.UTC)),
        ("latest.nc", None),
    ],
)
def test_the_end_of_a_file_is_read_from_its_name(filename: str, end: dt.datetime | None) -> None:
    """The age of a file is the age of the end of its interval, taken from its name in one place."""
    assert _end_of(filename) == end


def test_an_hourly_file_named_beyond_six_hours_ago_whose_stamp_is_younger_is_kept_for_five_minutes(
    platform: ThreadingHTTPServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The name says 6 to 7 hours, the stamp of its values 5 to 6: KNMI may still fill it in, so 5 minutes."""
    settings = _settings(tmp_path)
    assert _file_expiry(_end_of(NAMED_BEYOND_SIX_HOURS)) == CacheExpiry.FIVE_MINUTES
    assert _file_expiry(_end_of(ENDED_BEYOND_SIX_HOURS)) == CacheExpiry.TWELVE_HOURS

    _fetch(settings, NAMED_BEYOND_SIX_HOURS)
    _later(monkeypatch, minutes=4)
    _fetch(settings, NAMED_BEYOND_SIX_HOURS)
    assert len(_store_requests(platform)) == 1
    _later(monkeypatch, minutes=5, seconds=30)
    _fetch(settings, NAMED_BEYOND_SIX_HOURS)
    assert len(_store_requests(platform)) == 2


def test_a_body_that_is_no_netcdf_is_not_kept_for_the_next_read(
    platform: ThreadingHTTPServer, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A 200 whose body the reader cannot open (BODY is no NetCDF) is dropped, not served until it expires."""
    # the reader of the body, which is missing without the knmi extra: that is no failure of the body
    pytest.importorskip("h5netcdf", reason="h5netcdf not installed")
    pytest.importorskip("h5py", reason="h5py not installed")
    monkeypatch.setattr(
        KnmiObservationRequest,
        "_station_frame",
        staticmethod(lambda *_args: pl.DataFrame({"station_id": ["06260"], "name": ["De Bilt"]})),
    )

    def read() -> None:
        request = KnmiObservationRequest(
            parameters=[("daily", "data", "temperature_air_mean_2m")],
            start=dt.datetime(2020, 1, 1, tzinfo=dt.UTC),
            end=dt.datetime(2020, 1, 1, tzinfo=dt.UTC),
            settings=_settings(tmp_path),
        )
        request.filter_by_station_id("06260").values().all()

    for expected in (1, 2):
        with pytest.raises(OSError, match="signature"):  # h5py: the body is no HDF5 file
            read()
        assert len(_store_requests(platform)) == expected


def _unreadable(settings: Settings, filename: str) -> None:
    with _forgotten_if_unreadable(DATASET, VERSION, filename, settings):
        msg = "no file"
        raise ValueError(msg)


def test_the_copy_of_a_file_is_dropped_whichever_age_chose_its_directory(
    platform: ThreadingHTTPServer, tmp_path: Path
) -> None:
    """`_forgotten_if_unreadable` drops the copy of either expiry and raises what the reader raised."""
    settings = _settings(tmp_path)
    for filename in (OLD, RECENT):
        assert _fetch(settings, filename) == BODY
        with pytest.raises(ValueError, match="no file"):
            _unreadable(settings, filename)
        assert _fetch(settings, filename) == BODY
    assert len(_store_requests(platform)) == 4
