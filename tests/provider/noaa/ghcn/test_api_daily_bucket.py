# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The source of GHCN daily: NCEI's by_station files, the AWS mirror only when NCEI fails (GH-4225, GH-4230).

NCEI's `access/` files are no source (they answered 403 and 404, and 200 again, in 2026), and the mirror's block of ids
from `USR0000CJUA` to `ZI000067991` has not been written since 2025-02-09, so the mirror is read only for a station
whose file NCEI could not give, and the answer says so, once for the request.
"""

from __future__ import annotations

import gzip
import http.server
import logging
import socket
import threading
import time
from collections.abc import Callable, Iterator
from io import BytesIO
from typing import TYPE_CHECKING
from unittest.mock import MagicMock
from urllib.parse import urlparse

import pytest
from aiohttp import ClientResponseError, ClientTimeout

from tests.provider.value_stubs import ghcnd_by_station
from wetterdienst import Options, Settings
from wetterdienst.exceptions import DownloadError, NoInternetError, ProviderRateLimitError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest, api
from wetterdienst.util.network import File
from wetterdienst.util.response_warnings import (
    FILE_SKIPPED,
    SOURCE_FALLBACK,
    begin_response,
    recorded_warnings,
)

if TYPE_CHECKING:
    from pathlib import Path

    import polars as pl

NCEI = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/by_station/{id}.csv.gz"
AWS = "https://noaa-ghcn-pds.s3.amazonaws.com/csv.gz/by_station/{id}.csv.gz"
DE_BILT = "NLM00006260"
NYC = "USW00094728"
_STATIONS = (
    f"{DE_BILT}   52.0989    5.1794    1.9    DE BILT                                06260\n"
    f"{NYC}  40.7789  -73.9692   42.7 NY NY CITY CNTRL PARK                 HCN 72506\n"
)
_INVENTORY = f"{DE_BILT}  52.0989    5.1794 TMAX 1901 2026\n{NYC}  40.7789  -73.9692 TMAX 1869 2026\n"
# rows of the file of De Bilt as NCEI has them (read 2026-11-19): the values are the tenths of the readme, the quality
# flag is blank
_DE_BILT = [
    (DE_BILT, "20260929", "TMAX", "259", "", "", "E"),
    (DE_BILT, "20260930", "TMAX", "245", "", "", "E"),
]
# the same two days as the mirror has them, one value different, so that a test tells which file it read
_DE_BILT_MIRROR = [
    (DE_BILT, "20260929", "TMAX", "259", "", "", "E"),
    (DE_BILT, "20260930", "TMAX", "240", "", "", "E"),
]
# the last days of the file of New York City Central Park in the mirror, which has not been written since 2025-02-09
_NYC_MIRROR = [
    (NYC, "20250204", "TMAX", "37", "", "", "W"),
    (NYC, "20250205", "TMAX", "22", "", "", "W"),
]
_MAINTENANCE_PAGE = b"<html><head><title>Maintenance</title></head><body><h1>Down for maintenance</h1></body></html>\n"

_Body = bytes | Callable[[str], File]


def _failed(status: int) -> Callable[[str], File]:
    """Give a download that failed with the status of the server."""

    def file(url: str) -> File:
        return File(url=url, content=ClientResponseError(MagicMock(), (), status=status), status=status)

    return file


def _gone(url: str) -> File:
    return File(url=url, content=FileNotFoundError(url), status=404)


def _no_connection(url: str) -> File:
    return File(url=url, content=NoInternetError(url, "no connection"), status=0)


def _ok(body: bytes) -> Callable[[str], File]:
    def file(url: str) -> File:
        return File(url=url, content=BytesIO(body), status=200)

    return file


def _serve(
    monkeypatch: pytest.MonkeyPatch,
    *,
    ncei: _Body | dict[str, _Body],
    aws: _Body | dict[str, _Body],
    stations: str = _STATIONS,
    inventory: str = _INVENTORY,
) -> list[dict[str, object]]:
    """Serve the lists, and the files of the stations from NCEI and from the mirror; return the calls of the reader."""
    calls: list[dict[str, object]] = []

    def pick(bodies: _Body | dict[str, _Body], url: str) -> Callable[[str], File]:
        body = bodies
        if isinstance(bodies, dict):
            body = next(body for station, body in bodies.items() if station in url)
        return body if callable(body) else _ok(body)

    def download_file(url: str, **kwargs: object) -> File:
        calls.append({"url": url, **kwargs})
        if "ghcnd-stations" in url:
            return _ok(stations.encode("utf8"))(url)
        if "ghcnd-inventory" in url:
            return _ok(inventory.encode("utf8"))(url)
        return pick(ncei if (urlparse(url).hostname or "").endswith("ncei.noaa.gov") else aws, url)(url)

    monkeypatch.setattr(api, "download_file", download_file)
    return calls


def _values(
    stations: str | list[str] = DE_BILT,
    *,
    start: str = "2026-09-29",
    end: str = "2026-09-30",
    drop_nulls: bool = True,
    settings: Settings | None = None,
) -> pl.DataFrame:
    request = NoaaGhcnRequest(
        parameters=[("daily", "data", "temperature_air_max_2m")],
        start=start,
        end=end,
        settings=settings or Settings(cache_disable=True),
        options=Options(drop_nulls=drop_nulls),
    ).filter_by_station_id(stations)
    return request.values().all().df.sort("timestamp")


def _asked(calls: list[dict[str, object]]) -> list[str]:
    return [str(call["url"]) for call in calls if "by_station" in str(call["url"])]


def _codes() -> list[str]:
    return [warning["code"] for warning in recorded_warnings()]


def test_the_file_of_a_station_is_ncei_s_and_kept_for_12_hours(monkeypatch: pytest.MonkeyPatch) -> None:
    """The reader asks NCEI's `pub/data/ghcn/daily/by_station/<id>.csv.gz` alone, whole record, kept for 12 hours.

    Both hosts write a file once a day; the 5 minutes of the hourly files would fetch 1.8 MB (16 MB unpacked for New
    York City Central Park) again at every request. NCEI is asked once and for 10 seconds of silence at most, which is
    what leaves time for the mirror inside the 60 seconds of a REST request. Nothing is told when NCEI answers.
    """
    calls = _serve(monkeypatch, ncei=ghcnd_by_station(_DE_BILT), aws=ghcnd_by_station(_DE_BILT_MIRROR))
    begin_response()
    df = _values()
    assert _asked(calls) == [NCEI.format(id=DE_BILT)]
    (call,) = [call for call in calls if "by_station" in str(call["url"])]
    assert call["ttl"] == CacheExpiry.TWELVE_HOURS
    assert call["attempts"] == 1
    timeout = call["client_kwargs"]["timeout"]
    assert isinstance(timeout, ClientTimeout)
    assert (timeout.sock_connect, timeout.sock_read) == (api.NCEI_TIMEOUT_SECONDS, api.NCEI_TIMEOUT_SECONDS)
    assert df.get_column("value").to_list() == pytest.approx([25.9, 24.5])
    assert SOURCE_FALLBACK not in _codes()


@pytest.mark.parametrize("body", ["plain", "header"])
def test_a_file_that_is_not_gzipped_or_has_a_header_line_is_read_as_well(
    monkeypatch: pytest.MonkeyPatch, body: str
) -> None:
    """The mirror's documentation describes a header line (`ID,DATE,...`), which the files do not have: no reading."""
    text = "\n".join(",".join([*row, ""]) for row in _DE_BILT) + "\n"
    if body == "header":
        text = "ID,DATE,ELEMENT,DATA_VALUE,M_FLAG,Q_FLAG,S_FLAG,OBS_TIME\n" + text
    content = text.encode("utf8") if body == "plain" else gzip.compress(text.encode("utf8"))
    _serve(monkeypatch, ncei=content, aws=b"")
    assert _values().get_column("value").to_list() == pytest.approx([25.9, 24.5])


def test_the_missing_value_of_the_readme_is_null_and_keeps_what_the_file_wrote(monkeypatch: pytest.MonkeyPatch) -> None:
    """A `-9999` is the readme's missing value of the `.dly` files; none of 1.3 million values read is one (2026-11-18).

    The files leave a missing reading out, so a row that writes it is null and keeps the number as `raw:-9999`, not
    -999.9 degrees.
    """
    rows = [*_DE_BILT, (DE_BILT, "20261001", "TMAX", "-9999", "", "", "E")]
    _serve(monkeypatch, ncei=ghcnd_by_station(rows), aws=b"")
    df = _values(drop_nulls=False, end="2026-10-01")
    assert df.select("value", "quality_flags").rows() == [
        (pytest.approx(25.9), "source:E"),
        (pytest.approx(24.5), "source:E"),
        (None, "source:E,raw:-9999"),
    ]


@pytest.mark.parametrize(
    ("failure", "why"),
    [
        pytest.param(_gone, "the file was gone", id="404"),
        pytest.param(_failed(503), "the download failed", id="503"),
        pytest.param(_failed(500), "the download failed", id="500"),
        pytest.param(_no_connection, "the download failed", id="no-connection"),
        pytest.param(_ok(_MAINTENANCE_PAGE), "an error page", id="maintenance-page"),
    ],
)
def test_a_file_ncei_fails_for_is_read_from_the_mirror_and_the_answer_says_so(
    monkeypatch: pytest.MonkeyPatch, failure: Callable[[str], File], why: str, caplog: pytest.LogCaptureFixture
) -> None:
    """A 404, a 5xx, a connection that cannot be made or a body that is no file sends the reader to the mirror.

    The warning names the station and says the values are the mirror's, which may be older. The mirror's file is its
    own URL in the cache, and NCEI is asked first at the next request, so a copy of the mirror is never served as
    NCEI's once NCEI is back.
    """
    calls = _serve(monkeypatch, ncei=failure, aws=ghcnd_by_station(_DE_BILT_MIRROR))
    begin_response()
    with caplog.at_level(logging.WARNING):
        df = _values()
    assert _asked(calls) == [NCEI.format(id=DE_BILT), AWS.format(id=DE_BILT)]
    assert df.get_column("value").to_list() == pytest.approx([25.9, 24.0])
    (warning,) = [warning for warning in recorded_warnings() if warning["code"] == SOURCE_FALLBACK]
    assert warning["stations"] == [DE_BILT]
    assert f"station {DE_BILT}" in warning["message"]
    assert why in warning["message"]
    assert "the AWS mirror" in warning["message"]
    assert "older" in warning["message"]
    assert "AWS mirror" in caplog.text
    # the next request asks NCEI again, whose file is back
    _serve(monkeypatch, ncei=ghcnd_by_station(_DE_BILT), aws=ghcnd_by_station(_DE_BILT_MIRROR))
    assert _values().get_column("value").to_list() == pytest.approx([25.9, 24.5])


def test_a_refusal_of_ncei_is_not_told_to_be_tried_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 403 is a refusal that stays: the warning says it was refused and does not advise trying again later."""
    _serve(monkeypatch, ncei=_failed(403), aws=ghcnd_by_station(_DE_BILT_MIRROR))
    begin_response()
    _values()
    (warning,) = [warning for warning in recorded_warnings() if warning["code"] == SOURCE_FALLBACK]
    assert "the download was refused" in warning["message"]
    assert "Try again later" not in warning["message"]
    assert "report it to the provider" in warning["message"]


def test_a_failure_that_may_heal_is_told_to_be_tried_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 503 may be gone later: the warning says so."""
    _serve(monkeypatch, ncei=_failed(503), aws=ghcnd_by_station(_DE_BILT_MIRROR))
    begin_response()
    _values()
    (warning,) = [warning for warning in recorded_warnings() if warning["code"] == SOURCE_FALLBACK]
    assert warning["message"].endswith("Try again later.")


def test_a_429_of_ncei_is_raised_and_the_mirror_is_not_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    """A rate limit is never a reason to go to the other host (the next file meets it too): `ProviderRateLimitError`."""
    calls = _serve(monkeypatch, ncei=_failed(429), aws=ghcnd_by_station(_DE_BILT_MIRROR))
    with pytest.raises(ProviderRateLimitError):
        _values()
    assert _asked(calls) == [NCEI.format(id=DE_BILT)]


def test_a_429_of_the_mirror_is_raised_too(monkeypatch: pytest.MonkeyPatch) -> None:
    """The mirror's own limit is no file to let go either."""
    _serve(monkeypatch, ncei=_failed(503), aws=_failed(429))
    with pytest.raises(ProviderRateLimitError):
        _values()


def test_a_station_neither_source_has_is_left_out_with_a_warning_and_the_others_are_answered(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Both 404: a file that is not there. `file-skipped` names the station, and the station next to it is read."""
    _serve(
        monkeypatch,
        ncei={NYC: _gone, DE_BILT: ghcnd_by_station(_DE_BILT)},
        aws={NYC: _gone, DE_BILT: ghcnd_by_station(_DE_BILT_MIRROR)},
    )
    begin_response()
    with caplog.at_level(logging.WARNING):
        df = _values([NYC, DE_BILT])
    assert df.get_column("station_id").unique().to_list() == [DE_BILT]
    (warning,) = [warning for warning in recorded_warnings() if warning["code"] == FILE_SKIPPED]
    assert warning["stations"] == [NYC]
    assert "the file was gone" in warning["message"]
    assert SOURCE_FALLBACK not in _codes()


@pytest.mark.parametrize(
    ("ncei", "aws", "raises"),
    [
        pytest.param(_failed(503), _gone, DownloadError, id="503-then-404"),
        pytest.param(_no_connection, _gone, NoInternetError, id="no-connection-then-404"),
        pytest.param(_failed(403), _gone, DownloadError, id="403-then-404"),
        pytest.param(_ok(_MAINTENANCE_PAGE), _gone, DownloadError, id="maintenance-page-then-404"),
        pytest.param(_gone, _failed(503), DownloadError, id="404-then-503"),
        pytest.param(_gone, _no_connection, NoInternetError, id="404-then-no-connection"),
        pytest.param(_failed(503), _failed(500), DownloadError, id="503-then-500"),
        pytest.param(_no_connection, _no_connection, NoInternetError, id="no-connection-at-both"),
        pytest.param(_failed(503), _ok(_MAINTENANCE_PAGE), DownloadError, id="503-then-maintenance-page"),
        pytest.param(_gone, _ok(_MAINTENANCE_PAGE), DownloadError, id="404-then-maintenance-page"),
        pytest.param(_ok(_MAINTENANCE_PAGE), _ok(_MAINTENANCE_PAGE), DownloadError, id="maintenance-page-at-both"),
    ],
)
def test_only_a_404_of_both_is_a_skip_every_other_failure_is_raised(
    monkeypatch: pytest.MonkeyPatch, ncei: Callable[[str], File], aws: Callable[[str], File], raises: type[Exception]
) -> None:
    """The pre-GH-4230 rule holds: a 404 is a station without a file, any other failure raises, never `file-skipped`."""
    _serve(monkeypatch, ncei=ncei, aws=aws)
    begin_response()
    with pytest.raises(raises):
        _values()
    assert FILE_SKIPPED not in _codes()


@pytest.mark.parametrize(
    ("ncei", "aws", "names", "message"),
    [
        pytest.param(_failed(503), _no_connection, "NCEI", "503", id="ncei-answered"),
        pytest.param(_no_connection, _failed(503), "mirror", "amazonaws", id="mirror-answered"),
    ],
)
def test_where_both_fail_the_failure_that_answered_is_the_one_raised(
    monkeypatch: pytest.MonkeyPatch,
    ncei: Callable[[str], File],
    aws: Callable[[str], File],
    names: str,
    message: str,
) -> None:
    """NCEI 503 and the mirror unreachable: NCEI's 503; NCEI unreachable and the mirror 503: the mirror's."""
    _serve(monkeypatch, ncei=ncei, aws=aws)
    with pytest.raises((DownloadError, NoInternetError)) as raised:
        _values()
    assert message in str(raised.value), names


def test_a_mirror_whose_body_is_no_file_is_a_download_error_that_names_its_file(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NCEI has no file of the station and the mirror's body is a maintenance page: a `DownloadError` of the mirror."""
    _serve(monkeypatch, ncei=_gone, aws=_ok(_MAINTENANCE_PAGE))
    with pytest.raises(DownloadError, match=r"noaa-ghcn-pds.*no table of readings"):
        _values()


# one station that fell back is explained: no "the source has no values" beside "may be older" (the class of IMGW #4219)


@pytest.mark.parametrize("stations", [[NYC], [DE_BILT, NYC]], ids=["one-station", "two-ids"])
def test_a_station_read_from_the_mirror_is_not_told_to_have_no_values(
    monkeypatch: pytest.MonkeyPatch, stations: list[str]
) -> None:
    """NCEI at 503, the mirror's file of NYC ends 2025-02-05 and the window is 2026-11: `source-fallback` says why.

    `parameter-without-rows` ("the source has no values ... try another station") and `station-without-rows` would
    contradict it: what the mirror lacks is the days it has not been written since, not days the source does not hold.
    The second id has rows in the window; the first has none, and is not named as a station without rows either.
    """
    _serve(
        monkeypatch,
        ncei=_failed(503),
        aws={NYC: ghcnd_by_station(_NYC_MIRROR), DE_BILT: ghcnd_by_station(_DE_BILT_MIRROR)},
    )
    begin_response()
    df = _values(stations, start="2026-09-29", end="2026-11-13")
    assert df.get_column("station_id").unique().to_list() == ([DE_BILT] if DE_BILT in stations else [])
    assert _codes() == [SOURCE_FALLBACK]
    (warning,) = recorded_warnings()
    assert warning["stations"] == stations


def test_a_failure_of_ncei_is_remembered_for_the_walk_and_told_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """NCEI is asked at the first station only; the others go straight to the mirror, and one warning names them all."""
    calls = _serve(
        monkeypatch,
        ncei=_failed(503),
        aws={NYC: ghcnd_by_station(_NYC_MIRROR), DE_BILT: ghcnd_by_station(_DE_BILT_MIRROR)},
    )
    begin_response()
    _values([DE_BILT, NYC])
    assert _asked(calls) == [NCEI.format(id=DE_BILT), AWS.format(id=DE_BILT), AWS.format(id=NYC)]
    (warning,) = [warning for warning in recorded_warnings() if warning["code"] == SOURCE_FALLBACK]
    assert warning["stations"] == [DE_BILT, NYC]
    assert "The files of stations NLM00006260, USW00094728 were" in warning["message"]
    # the next request asks NCEI again
    calls.clear()
    begin_response()
    _values([DE_BILT, NYC])
    assert _asked(calls)[0] == NCEI.format(id=DE_BILT)


def test_a_404_of_ncei_is_no_outage_and_the_next_station_is_asked_of_ncei(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station NCEI has no file of says nothing of the others, so the walk keeps asking NCEI."""
    calls = _serve(
        monkeypatch,
        ncei={DE_BILT: _gone, NYC: ghcnd_by_station(_NYC_MIRROR)},
        aws={DE_BILT: ghcnd_by_station(_DE_BILT_MIRROR), NYC: ghcnd_by_station(_NYC_MIRROR)},
    )
    begin_response()
    _values([DE_BILT, NYC], start="2025-02-04", end="2025-02-05")
    assert _asked(calls) == [NCEI.format(id=DE_BILT), AWS.format(id=DE_BILT), NCEI.format(id=NYC)]


def test_the_warning_of_many_stations_is_one_and_lists_the_first_ten() -> None:
    """Twelve stations fell back: one warning with the number and ten ids, not a message for each station."""
    from wetterdienst.model.parameter_rows import MAX_STATIONS_LISTED, ParameterRows  # noqa: PLC0415
    from wetterdienst.util.response_warnings import SkipCause, note_source_fallback  # noqa: PLC0415

    rows = ParameterRows(MagicMock(), None, None)
    ids = [f"USW{number:08d}" for number in range(12)]
    begin_response()
    for station in ids:
        with rows.collecting(station):
            note_source_fallback(station, SkipCause.FAILED, primary="NCEI", secondary="the mirror")
    rows.warn()
    (warning,) = [warning for warning in recorded_warnings() if warning["code"] == SOURCE_FALLBACK]
    assert warning["stations"] == ids[:MAX_STATIONS_LISTED]
    assert "12 stations, the first 10 of them USW00000000" in warning["message"]
    assert len(warning["message"]) < 600


def test_an_estimate_tells_the_fallback_once_and_only_for_the_stations_it_used() -> None:
    """`interpolate` and `summarize` count the stations read from the mirror in one `source-fallback`, not each.

    The station the estimate stopped at and did not use (`forget`) is not counted.
    """
    from wetterdienst.model.parameter_rows import EstimateLeftOut  # noqa: PLC0415
    from wetterdienst.util.response_warnings import SkipCause  # noqa: PLC0415

    left_out = EstimateLeftOut()
    begin_response()
    for station in ("A", "B", "C"):
        left_out.collected(station)
        left_out.fell_back(station, SkipCause.FAILED, "NCEI", "the mirror")
    left_out.forget("C")
    left_out.warn()
    (warning,) = recorded_warnings()
    assert warning["code"] == SOURCE_FALLBACK
    assert warning["stations"] == ["A", "B"]
    assert "stations A, B" in warning["message"]
    # nothing was left out: no `source-data-left-out`
    assert [w["code"] for w in recorded_warnings()] == [SOURCE_FALLBACK]


# the time budget: a NCEI that hangs costs its timeout once, and the mirror is asked inside the 60 seconds of REST


@pytest.fixture
def hanging_ncei_and_a_mirror(monkeypatch: pytest.MonkeyPatch) -> Iterator[dict[str, object]]:
    """Serve NCEI's URL from a socket that accepts and never answers, and the mirror's from a local HTTP server."""
    hanging = socket.socket()
    hanging.bind(("127.0.0.1", 0))
    hanging.listen()
    held: list[socket.socket] = []
    stop = threading.Event()

    def accept() -> None:
        hanging.settimeout(0.1)
        while not stop.is_set():
            try:
                held.append(hanging.accept()[0])
            except OSError:
                continue

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            station = self.path.strip("/").removesuffix(".csv.gz")
            body = ghcnd_by_station([(station, row[1], *row[2:]) for row in _DE_BILT_MIRROR])
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args: object) -> None:
            pass

    mirror = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threads = [threading.Thread(target=accept, daemon=True), threading.Thread(target=mirror.serve_forever, daemon=True)]
    for thread in threads:
        thread.start()
    monkeypatch.setattr(
        api, "GHCND_BY_STATION_URL", f"http://127.0.0.1:{hanging.getsockname()[1]}/{{station_id}}.csv.gz"
    )
    monkeypatch.setattr(
        api, "GHCND_BY_STATION_MIRROR_URL", f"http://127.0.0.1:{mirror.server_port}/{{station_id}}.csv.gz"
    )
    monkeypatch.setattr(api, "NCEI_TIMEOUT_SECONDS", 0.5)
    try:
        yield {"held": held}
    finally:
        stop.set()
        mirror.shutdown()
        mirror.server_close()
        for connection in held:
            connection.close()
        hanging.close()


def test_a_hanging_ncei_costs_its_timeout_once_for_a_walk(
    monkeypatch: pytest.MonkeyPatch, hanging_ncei_and_a_mirror: dict[str, object]
) -> None:
    """NCEI accepts the connection and never answers: one attempt of 0.5 s (10 s in production), then the mirror.

    Three stations in a walk: the first pays the timeout, the others are not asked of NCEI (one connection was
    accepted), and every file is read from the mirror, so the whole is far inside the 60 seconds of a REST request,
    where two attempts of 30 seconds were not.
    """
    ids = [DE_BILT, "NLM00006261", "NLM00006262"]
    lists = "".join(
        f"{station}   52.0989    5.1794    1.9    STATION {station[-2:]}                          06260\n"
        for station in ids
    )
    inventory = "".join(f"{station}  52.0989    5.1794 TMAX 1901 2026\n" for station in ids)
    real = api.download_file

    def download_file(url: str, **kwargs: object) -> File:
        if "ghcnd-stations" in url:
            return File(url=url, content=BytesIO(lists.encode("utf8")), status=200)
        if "ghcnd-inventory" in url:
            return File(url=url, content=BytesIO(inventory.encode("utf8")), status=200)
        return real(url, **kwargs)

    monkeypatch.setattr(api, "download_file", download_file)
    begin_response()
    started = time.monotonic()
    df = _values(ids)
    elapsed = time.monotonic() - started
    assert df.get_column("station_id").unique().sort().to_list() == sorted(ids)
    assert len(hanging_ncei_and_a_mirror["held"]) == 1
    assert elapsed < 10
    (warning,) = [warning for warning in recorded_warnings() if warning["code"] == SOURCE_FALLBACK]
    assert warning["stations"] == ids


# a body that is no file must not stay in the cache: it was held for the whole expiry like any 200


class _LocalSource:
    """A local HTTP server for one source, whose answer a test changes between two requests and whose hits it counts."""

    def __init__(self) -> None:
        self.status = 200
        self.body = b""
        self.hits = 0
        source = self

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                source.hits += 1
                self.send_response(source.status)
                self.send_header("Content-Length", str(len(source.body)))
                self.end_headers()
                self.wfile.write(source.body)

            def log_message(self, *args: object) -> None:
                pass

        self.server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.server.server_port}/{{station_id}}.csv.gz"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def close(self) -> None:
        self.server.shutdown()
        self.server.server_close()


@pytest.fixture
def local_sources(monkeypatch: pytest.MonkeyPatch) -> Iterator[tuple[_LocalSource, _LocalSource]]:
    """NCEI's and the mirror's URL, served from two local servers, to be read through the real cache."""
    ncei, mirror = _LocalSource(), _LocalSource()
    monkeypatch.setattr(api, "GHCND_BY_STATION_URL", ncei.url)
    monkeypatch.setattr(api, "GHCND_BY_STATION_MIRROR_URL", mirror.url)
    real = api.download_file

    def download_file(url: str, **kwargs: object) -> File:
        if "ghcnd-stations" in url:
            return _ok(_STATIONS.encode("utf8"))(url)
        if "ghcnd-inventory" in url:
            return _ok(_INVENTORY.encode("utf8"))(url)
        return real(url, **kwargs)

    monkeypatch.setattr(api, "download_file", download_file)
    try:
        yield ncei, mirror
    finally:
        ncei.close()
        mirror.close()


def test_a_maintenance_page_of_ncei_is_not_kept_in_the_cache(
    local_sources: tuple[_LocalSource, _LocalSource], tmp_path: Path
) -> None:
    """NCEI answers 200 with an HTML page, the next request finds its real file: read from NCEI, with no fallback.

    The page was cached for 12 hours like any 200, so the next request read it back without asking NCEI, fell back to
    the mirror again and said so, though NCEI had recovered minutes later. Run against a real cache directory.
    """
    ncei, mirror = local_sources
    ncei.body = _MAINTENANCE_PAGE
    mirror.body = ghcnd_by_station(_DE_BILT_MIRROR)
    settings = Settings(cache_dir=tmp_path / "cache")
    begin_response()
    df = _values(settings=settings)
    assert df.get_column("value").to_list() == pytest.approx([25.9, 24.0])
    (warning,) = [warning for warning in recorded_warnings() if warning["code"] == SOURCE_FALLBACK]
    assert "an error page" in warning["message"]
    assert (ncei.hits, mirror.hits) == (1, 1)
    # NCEI is back
    ncei.body = ghcnd_by_station(_DE_BILT)
    begin_response()
    df = _values(settings=settings)
    assert df.get_column("value").to_list() == pytest.approx([25.9, 24.5])
    assert SOURCE_FALLBACK not in _codes()
    assert (ncei.hits, mirror.hits) == (2, 1)
    # and its file is kept now: a third request does not ask again
    _values(settings=settings)
    assert (ncei.hits, mirror.hits) == (2, 1)


def test_an_unreadable_body_of_the_mirror_is_not_kept_in_the_cache_either(
    local_sources: tuple[_LocalSource, _LocalSource], tmp_path: Path
) -> None:
    """NCEI has no file and the mirror's body is a maintenance page: a `DownloadError`, and not for the whole expiry."""
    ncei, mirror = local_sources
    ncei.status = 404
    mirror.body = _MAINTENANCE_PAGE
    settings = Settings(cache_dir=tmp_path / "cache")
    with pytest.raises(DownloadError, match="no table of readings"):
        _values(settings=settings)
    assert mirror.hits == 1
    # the mirror is back
    mirror.body = ghcnd_by_station(_DE_BILT_MIRROR)
    begin_response()
    df = _values(settings=settings)
    assert df.get_column("value").to_list() == pytest.approx([25.9, 24.0])
    assert mirror.hits == 2
    assert [warning["code"] for warning in recorded_warnings()] == [SOURCE_FALLBACK]
