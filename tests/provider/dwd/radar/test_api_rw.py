# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for RADOLAN RW, which DWD names `bin` and publishes as ODIM HDF5 (GH-3298).

The file in `files/` is the real one of 2026-10-22 20:40 UTC, 50 kB (DWD's open data,
https://opendata.dwd.de/weather/radar/radolan/rw/), the listing lines of the real one of that evening.
"""

from __future__ import annotations

import datetime as dt
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import pytest

from tests.provider.dwd.radar.odim import assert_rw_file
from wetterdienst.provider.dwd.radar import DwdRadarDate, DwdRadarParameter, DwdRadarValues
from wetterdienst.util.network import File

if TYPE_CHECKING:
    from wetterdienst import Settings
    from wetterdienst.metadata.cache import CacheExpiry

UTC = ZoneInfo("UTC")
URL = "https://opendata.dwd.de/weather/radar/radolan/rw"
NAMES = [
    "raa01-rw_10000-2610222030-dwd---bin.hdf5",
    "raa01-rw_10000-2610222040-dwd---bin.hdf5",
    "raa01-rw_10000-2610222050-dwd---bin.hdf5",
    "raa01-rw_10000-latest-dwd---bin.hdf5",
]
FILE = Path(__file__).parent / "files" / "raa01-rw_10000-2610222040-dwd---bin.hdf5"


@pytest.fixture(autouse=True)
def served(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Serve the listing above and the one file of it that is held, and take down what is downloaded."""
    downloaded: list[str] = []

    def list_remote_files(url: str, settings: Settings, cache_expiry: CacheExpiry) -> list[str]:  # noqa: ARG001
        return [f"{url.rstrip('/')}/{name}" for name in NAMES]

    def download_file(url: str, ttl: CacheExpiry, **_: object) -> File:  # noqa: ARG001
        downloaded.append(url)
        return File(url=url, content=BytesIO(FILE.read_bytes()), status=200)

    monkeypatch.setattr("wetterdienst.provider.dwd.radar.index.list_remote_files_fsspec", list_remote_files)
    monkeypatch.setattr("wetterdienst.provider.dwd.radar.api.download_file", download_file)
    return downloaded


def test_a_rw_file_is_the_hour_of_precipitation_in_odim_hdf5(served: list[str], radar_locations: list[str]) -> None:
    """Test that the RW file is ODIM HDF5, not RADOLAN binary, and that the request hands it over as DWD wrote it."""
    pytest.importorskip("h5py")

    results = list(DwdRadarValues(parameter=DwdRadarParameter.RW_REFLECTIVITY, start="2026-10-22 20:43").query())

    assert served == [f"{URL}/raa01-rw_10000-2610222040-dwd---bin.hdf5"]
    assert len(results) == 1
    assert results[0].data.getvalue()[:8] == b"\x89HDF\r\n\x1a\n"
    assert results[0].timestamp == dt.datetime(2026, 10, 22, 20, 40, tzinfo=UTC)
    assert assert_rw_file(results[0].data, radar_locations) == results[0].timestamp


def test_the_latest_rw_file_is_read_as_the_dated_ones_are(served: list[str], radar_locations: list[str]) -> None:
    """Test that the file named latest, which DWD replaces, is read as ODIM HDF5 as well."""
    pytest.importorskip("h5py")

    results = list(DwdRadarValues(parameter=DwdRadarParameter.RW_REFLECTIVITY, start=DwdRadarDate.LATEST).query())

    assert served == [f"{URL}/raa01-rw_10000-latest-dwd---bin.hdf5"]
    assert len(results) == 1
    assert assert_rw_file(results[0].data, radar_locations) == dt.datetime(2026, 10, 22, 20, 40, tzinfo=UTC)
