# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for how a radar HDF5 request reports the files it could not verify."""

import datetime as dt
import logging
import sys
from collections.abc import Iterator
from io import BytesIO
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst import Settings
from wetterdienst.provider.dwd.radar import DwdRadarDataFormat, DwdRadarDataSubset, DwdRadarParameter, DwdRadarValues
from wetterdienst.provider.dwd.radar.api import RadarResult
from wetterdienst.provider.dwd.radar.sites import DwdRadarSite

UTC = ZoneInfo("UTC")
START = dt.datetime(2026, 10, 1, 12, 0, tzinfo=UTC)
FILES = 3


@pytest.fixture
def three_files(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve a listing of three HDF5 files and a download of an empty buffer for each, without the network."""
    base = "https://opendata.dwd.de/weather/radar/sites/sweep_vol_v/boo/hdf5"
    index = pl.DataFrame(
        {
            "filename": [f"{base}/file{i}-hd5" for i in range(FILES)],
            "datetime": [START + dt.timedelta(minutes=5 * i) for i in range(FILES)],
        },
    )

    def download(_self: DwdRadarValues, url: str) -> Iterator[RadarResult]:
        return iter([RadarResult(data=BytesIO(), url=url)])

    monkeypatch.setattr("wetterdienst.provider.dwd.radar.api.create_fileindex_radar", lambda **_: index)
    monkeypatch.setattr(DwdRadarValues, "_download_generic_data", download)


def _request() -> DwdRadarValues:
    return DwdRadarValues(
        parameter=DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
        start=START,
        end=START + dt.timedelta(minutes=30),
        site=DwdRadarSite.BOO,
        fmt=DwdRadarDataFormat.HDF5,
        subset=DwdRadarDataSubset.SIMPLE,
        settings=Settings(),
    )


@pytest.mark.usefixtures("three_files")
def test_radar_hdf5_without_h5py_says_so_once(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a missing h5py is one warning for the request, not one traceback for every file (GH-2928)."""
    monkeypatch.setitem(sys.modules, "h5py", None)

    with caplog.at_level(logging.WARNING):
        results = list(_request().query())

    # the files are returned, unverified
    assert len(results) == FILES
    records = [record for record in caplog.records if "h5py" in record.getMessage()]
    assert len(records) == 1
    assert records[0].levelno == logging.WARNING
    assert records[0].exc_info is None
    assert "pip install wetterdienst[radar]" in records[0].getMessage()
    assert "Unable to read HDF5 file" not in caplog.text
