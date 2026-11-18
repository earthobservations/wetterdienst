# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The source of GHCN daily: NCEI's by_station files, the AWS mirror only when NCEI fails (GH-4225, GH-4230).

NCEI's `access/` files are no source (they answered 403 and 404, and 200 again, in 2026), and the mirror's block of ids
from `USR0000CJUA` to `ZI000067991` has not been written since 2025-02-09, so the mirror is read only for a station
whose file NCEI could not give, and the answer says so.
"""

from __future__ import annotations

import gzip
import logging
from io import BytesIO
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from aiohttp import ClientResponseError

from tests.provider.value_stubs import ghcnd_by_station
from wetterdienst import Options, Settings
from wetterdienst.exceptions import DownloadError, NoInternetError, ProviderRateLimitError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest, api
from wetterdienst.util.network import File
from wetterdienst.util.response_warnings import FILE_SKIPPED, SOURCE_FALLBACK, begin_response, recorded_warnings

if TYPE_CHECKING:
    from collections.abc import Callable

NCEI = "https://www.ncei.noaa.gov/pub/data/ghcn/daily/by_station/{id}.csv.gz"
AWS = "https://noaa-ghcn-pds.s3.amazonaws.com/csv.gz/by_station/{id}.csv.gz"
_STATIONS = (
    "NLM00006260   52.0989    5.1794    1.9    DE BILT                                06260\n"
    "USW00094728  40.7789  -73.9692   42.7 NY NY CITY CNTRL PARK                 HCN 72506\n"
)
_INVENTORY = "NLM00006260  52.0989    5.1794 TMAX 1901 2026\nUSW00094728  40.7789  -73.9692 TMAX 1869 2026\n"
# rows of the file of De Bilt as NCEI has them (read 2026-11-19): the values are the tenths of the readme, the quality
# flag is blank
_DE_BILT = [
    ("NLM00006260", "20260929", "TMAX", "259", "", "", "E"),
    ("NLM00006260", "20260930", "TMAX", "245", "", "", "E"),
]
# the same two days as the mirror has them, one value different, so that a test tells which file it read
_DE_BILT_MIRROR = [
    ("NLM00006260", "20260929", "TMAX", "259", "", "", "E"),
    ("NLM00006260", "20260930", "TMAX", "240", "", "", "E"),
]


def _failed(status: int, error: Exception | None = None) -> Callable[[str], File]:
    """Give a download that failed: the status of the server, or the connection error with no status."""

    def file(url: str) -> File:
        return File(url=url, content=error or ClientResponseError(MagicMock(), (), status=status), status=status)

    return file


def _gone(url: str) -> File:
    return File(url=url, content=FileNotFoundError(url), status=404)


def _no_connection(url: str) -> File:
    return File(url=url, content=NoInternetError(url, "no connection"), status=0)


def _serve(
    monkeypatch: pytest.MonkeyPatch, *, ncei: bytes | Callable[[str], File], aws: bytes | Callable[[str], File]
) -> list[dict[str, object]]:
    """Serve the lists, the files of De Bilt from NCEI and the mirror, and return the calls the reader made."""
    calls: list[dict[str, object]] = []

    def download_file(url: str, **kwargs: object) -> File:
        calls.append({"url": url, **kwargs})
        if "ghcnd-stations" in url:
            return File(url=url, content=BytesIO(_STATIONS.encode("utf8")), status=200)
        if "ghcnd-inventory" in url:
            return File(url=url, content=BytesIO(_INVENTORY.encode("utf8")), status=200)
        body = ncei if url == NCEI.format(id="NLM00006260") else aws
        return body(url) if callable(body) else File(url=url, content=BytesIO(body), status=200)

    monkeypatch.setattr(api, "download_file", download_file)
    return calls


def _values(*, drop_nulls: bool = True, station: str = "NLM00006260", end: str = "2026-09-30") -> list:
    request = NoaaGhcnRequest(
        parameters=[("daily", "data", "temperature_air_max_2m")],
        start="2026-09-29",
        end=end,
        settings=Settings(cache_disable=True),
        options=Options(drop_nulls=drop_nulls),
    ).filter_by_station_id(station)
    return request.values().all().df.sort("timestamp")


def _asked(calls: list[dict[str, object]]) -> list[str]:
    return [str(call["url"]) for call in calls if "by_station" in str(call["url"])]


def test_the_file_of_a_station_is_ncei_s_and_kept_for_12_hours(monkeypatch: pytest.MonkeyPatch) -> None:
    """The reader asks NCEI's `pub/data/ghcn/daily/by_station/<id>.csv.gz` alone, whole record, kept for 12 hours.

    Both hosts write a file once a day; the 5 minutes of the hourly files would fetch 1.8 MB (16 MB unpacked for New
    York City Central Park) again at every request. Nothing is told when NCEI answers.
    """
    calls = _serve(monkeypatch, ncei=ghcnd_by_station(_DE_BILT), aws=ghcnd_by_station(_DE_BILT_MIRROR))
    begin_response()
    df = _values()
    assert _asked(calls) == [NCEI.format(id="NLM00006260")]
    assert {call["ttl"] for call in calls if "by_station" in str(call["url"])} == {CacheExpiry.TWELVE_HOURS}
    assert df.get_column("value").to_list() == pytest.approx([25.9, 24.5])
    assert [warning for warning in recorded_warnings() if warning["code"] == SOURCE_FALLBACK] == []


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
    rows = [*_DE_BILT, ("NLM00006260", "20261001", "TMAX", "-9999", "", "", "E")]
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
    ],
)
def test_a_file_ncei_fails_for_is_read_from_the_mirror_and_the_answer_says_so(
    monkeypatch: pytest.MonkeyPatch, failure: Callable[[str], File], why: str, caplog: pytest.LogCaptureFixture
) -> None:
    """A 404, a 5xx or a connection that cannot be made sends the reader to the mirror, with the warning.

    The warning names the station and says the values are the mirror's, which may be older. The mirror's file is its
    own URL in the cache, and NCEI is asked first at the next request, so a copy of the mirror is never served as
    NCEI's once NCEI is back.
    """
    calls = _serve(monkeypatch, ncei=failure, aws=ghcnd_by_station(_DE_BILT_MIRROR))
    begin_response()
    with caplog.at_level(logging.WARNING):
        df = _values()
    assert _asked(calls) == [NCEI.format(id="NLM00006260"), AWS.format(id="NLM00006260")]
    assert df.get_column("value").to_list() == pytest.approx([25.9, 24.0])
    (warning,) = [warning for warning in recorded_warnings() if warning["code"] == SOURCE_FALLBACK]
    assert warning["stations"] == ["NLM00006260"]
    assert why in warning["message"]
    assert "AWS mirror" in warning["message"]
    assert "older" in warning["message"]
    assert "AWS mirror" in caplog.text
    # the next request asks NCEI again, whose file is back
    calls.clear()
    _serve(monkeypatch, ncei=ghcnd_by_station(_DE_BILT), aws=ghcnd_by_station(_DE_BILT_MIRROR))
    assert _values().get_column("value").to_list() == pytest.approx([25.9, 24.5])


def test_a_429_of_ncei_is_raised_and_the_mirror_is_not_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    """A rate limit is never a reason to go to the other host (the next file meets it too): `ProviderRateLimitError`."""
    calls = _serve(monkeypatch, ncei=_failed(429), aws=ghcnd_by_station(_DE_BILT_MIRROR))
    with pytest.raises(ProviderRateLimitError):
        _values()
    assert _asked(calls) == [NCEI.format(id="NLM00006260")]


def test_a_429_of_the_mirror_is_raised_too(monkeypatch: pytest.MonkeyPatch) -> None:
    """The mirror's own limit is no file to let go either."""
    _serve(monkeypatch, ncei=_failed(503), aws=_failed(429))
    with pytest.raises(ProviderRateLimitError):
        _values()


def test_a_station_neither_source_has_is_left_out_with_a_warning_and_the_others_are_answered(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Both 404: a file that is not there. `file-skipped` names the station, and the station next to it is read."""
    gone = _gone

    def download_file(url: str, **_kwargs: object) -> File:
        if "ghcnd-stations" in url:
            return File(url=url, content=BytesIO(_STATIONS.encode("utf8")), status=200)
        if "ghcnd-inventory" in url:
            return File(url=url, content=BytesIO(_INVENTORY.encode("utf8")), status=200)
        if "USW00094728" in url:
            return gone(url)
        return File(url=url, content=BytesIO(ghcnd_by_station(_DE_BILT)), status=200)

    monkeypatch.setattr(api, "download_file", download_file)
    begin_response()
    with caplog.at_level(logging.WARNING):
        both = NoaaGhcnRequest(
            parameters=[("daily", "data", "temperature_air_max_2m")],
            start="2026-09-29",
            end="2026-09-30",
            settings=Settings(cache_disable=True),
        ).filter_by_station_id(["USW00094728", "NLM00006260"])
        df = both.values().all().df
    assert df.get_column("station_id").unique().to_list() == ["NLM00006260"]
    (warning,) = [warning for warning in recorded_warnings() if warning["code"] == FILE_SKIPPED]
    assert warning["stations"] == ["USW00094728"]
    assert "the file was gone" in warning["message"]
    assert [warning for warning in recorded_warnings() if warning["code"] == SOURCE_FALLBACK] == []


def test_a_station_ncei_failed_for_and_the_mirror_has_no_file_of_is_let_go_for_ncei_s_cause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """NCEI 503, mirror 404: the file may exist at NCEI, so the cause is a failed download, which may heal."""
    _serve(monkeypatch, ncei=_failed(503), aws=_gone)
    begin_response()
    df = _values()
    assert df.is_empty()
    (warning,) = [warning for warning in recorded_warnings() if warning["code"] == FILE_SKIPPED]
    assert "the download failed" in warning["message"]


def test_a_mirror_that_fails_after_a_404_of_ncei_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    """NCEI has no file and the mirror cannot be read: not told as a station without data, raised."""
    _serve(monkeypatch, ncei=_gone, aws=_failed(503))
    with pytest.raises(DownloadError):
        _values()


def test_no_connection_to_either_is_raised(monkeypatch: pytest.MonkeyPatch) -> None:
    """An offline library is not a station without data (GH-2640)."""
    _serve(monkeypatch, ncei=_no_connection, aws=_no_connection)
    with pytest.raises(NoInternetError):
        _values()
