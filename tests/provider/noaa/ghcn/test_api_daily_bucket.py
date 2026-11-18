# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The source of GHCN daily: the per-station files of the AWS bucket, as NCEI's `access/` files are gone (GH-4225)."""

from __future__ import annotations

import gzip
from io import BytesIO
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import pytest
from aiohttp import ClientResponseError

from tests.provider.value_stubs import ghcnd_by_station
from wetterdienst import Options, Settings
from wetterdienst.exceptions import ProviderRateLimitError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest, api
from wetterdienst.util.network import File
from wetterdienst.util.response_warnings import FILE_SKIPPED, begin_response, recorded_warnings

if TYPE_CHECKING:
    from collections.abc import Callable

_STATIONS = (
    "NLM00006260   52.0989    5.1794    1.9    DE BILT                                06260\n"
    "USW00094728  40.7789  -73.9692   42.7 NY NY CITY CNTRL PARK                 HCN 72506\n"
)
_INVENTORY = "NLM00006260  52.0989    5.1794 TMAX 1901 2026\nUSW00094728  40.7789  -73.9692 TMAX 1869 2026\n"
# rows of the file of De Bilt as the bucket has them (read 2026-11-18): the values are the tenths of the readme, the
# quality flag is blank
_DE_BILT = [
    ("NLM00006260", "20260929", "TMAX", "259", "", "", "E"),
    ("NLM00006260", "20260930", "TMAX", "245", "", "", "E"),
]


def _serve(monkeypatch: pytest.MonkeyPatch, files: dict[str, Callable[[], File] | bytes]) -> list[dict[str, object]]:
    """Serve the lists and the files of the stations by their name; the calls the reader made are returned."""
    calls: list[dict[str, object]] = []

    def download_file(url: str, **kwargs: object) -> File:
        calls.append({"url": url, **kwargs})
        for part, body in {
            "ghcnd-stations": _STATIONS.encode("utf8"),
            "ghcnd-inventory": _INVENTORY.encode("utf8"),
            **files,
        }.items():
            if part in url:
                return body() if callable(body) else File(url=url, content=BytesIO(body), status=200)
        msg = f"the stub serves nothing for {url}"
        raise AssertionError(msg)

    monkeypatch.setattr(api, "download_file", download_file)
    return calls


def _request(station_ids: list[str], *, start: str, end: str, drop_nulls: bool = True) -> NoaaGhcnRequest:
    return NoaaGhcnRequest(
        parameters=[("daily", "data", "temperature_air_max_2m")],
        start=start,
        end=end,
        settings=Settings(cache_disable=True),
        options=Options(drop_nulls=drop_nulls),
    ).filter_by_station_id(station_ids)


def test_the_file_of_a_station_is_the_gzipped_one_of_the_bucket_and_kept_for_12_hours(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reader asks `csv.gz/by_station/<id>.csv.gz`, whole record, so it is kept as long as the lists beside it.

    The bucket rewrites a file once a day; the 5 minutes of the hourly files would fetch 1.8 MB (16 MB unpacked for
    New York City Central Park) again at every request.
    """
    calls = _serve(monkeypatch, {"by_station/NLM00006260": ghcnd_by_station(_DE_BILT)})
    df = _request(["NLM00006260"], start="2026-09-29", end="2026-09-30").values().all().df
    (call,) = [call for call in calls if "by_station" in str(call["url"])]
    assert call["url"] == "https://noaa-ghcn-pds.s3.amazonaws.com/csv.gz/by_station/NLM00006260.csv.gz"
    assert call["ttl"] == CacheExpiry.TWELVE_HOURS
    assert df.sort("timestamp").get_column("value").to_list() == pytest.approx([25.9, 24.5])


@pytest.mark.parametrize("body", ["plain", "header"])
def test_a_file_that_is_not_gzipped_or_has_a_header_line_is_read_as_well(
    monkeypatch: pytest.MonkeyPatch, body: str
) -> None:
    """The bucket's documentation describes a header line (`ID,DATE,...`), which the files do not have: no reading."""
    text = "\n".join(",".join([*row, ""]) for row in _DE_BILT) + "\n"
    if body == "header":
        text = "ID,DATE,ELEMENT,DATA_VALUE,M_FLAG,Q_FLAG,S_FLAG,OBS_TIME\n" + text
    content = text.encode("utf8") if body == "plain" else gzip.compress(text.encode("utf8"))
    _serve(monkeypatch, {"by_station/NLM00006260": content})
    df = _request(["NLM00006260"], start="2026-09-29", end="2026-09-30").values().all().df
    assert df.sort("timestamp").get_column("value").to_list() == pytest.approx([25.9, 24.5])


def test_the_missing_value_of_the_readme_is_null_and_keeps_what_the_file_wrote(monkeypatch: pytest.MonkeyPatch) -> None:
    """A `-9999` is the readme's missing value of the `.dly` files; none of 1.3 million values read is one (2026-11-18).

    The files leave a missing reading out, so a row that writes it is null and keeps the number as `raw:-9999`, not
    -999.9 degrees.
    """
    rows = [*_DE_BILT, ("NLM00006260", "20261001", "TMAX", "-9999", "", "", "E")]
    _serve(monkeypatch, {"by_station/NLM00006260": ghcnd_by_station(rows)})
    df = (
        _request(["NLM00006260"], start="2026-09-29", end="2026-10-01", drop_nulls=False)
        .values()
        .all()
        .df.sort("timestamp")
    )
    assert df.select("value", "quality_flags").rows() == [
        (pytest.approx(25.9), "source:E"),
        (pytest.approx(24.5), "source:E"),
        (None, "source:E,raw:-9999"),
    ]


def test_a_station_the_bucket_has_no_file_for_is_left_out_with_a_warning_and_the_others_are_answered(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """A 404 is a file that is not there: `file-skipped` names the station, and the station next to it is read."""
    url = "https://noaa-ghcn-pds.s3.amazonaws.com/csv.gz/by_station/USW00094728.csv.gz"
    _serve(
        monkeypatch,
        {
            "by_station/NLM00006260": ghcnd_by_station(_DE_BILT),
            "by_station/USW00094728": lambda: File(url=url, content=FileNotFoundError(url), status=404),
        },
    )
    begin_response()
    with caplog.at_level("WARNING"):
        df = _request(["USW00094728", "NLM00006260"], start="2026-09-29", end="2026-09-30").values().all().df
    assert df.get_column("station_id").unique().to_list() == ["NLM00006260"]
    (warning,) = [warning for warning in recorded_warnings() if warning["code"] == FILE_SKIPPED]
    assert warning["stations"] == ["USW00094728"]
    assert url in caplog.text


def test_a_429_of_the_bucket_is_raised_and_not_let_go(monkeypatch: pytest.MonkeyPatch) -> None:
    """A rate limit is never a file to leave out (the next one meets it too): it is a `ProviderRateLimitError`."""
    url = "https://noaa-ghcn-pds.s3.amazonaws.com/csv.gz/by_station/NLM00006260.csv.gz"
    error = ClientResponseError(request_info=MagicMock(), history=(), status=429)
    _serve(monkeypatch, {"by_station/NLM00006260": lambda: File(url=url, content=error, status=429)})
    with pytest.raises(ProviderRateLimitError):
        _request(["NLM00006260"], start="2026-09-29", end="2026-09-30").values().all()
