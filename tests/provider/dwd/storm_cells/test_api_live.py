# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The thunderstorm cells of DWD, read from opendata.dwd.de (needs the internet)."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst.provider.dwd.storm_cells import DwdStormCellsRequest
from wetterdienst.provider.dwd.storm_cells.api import _SCHEMA
from wetterdienst.util.response_warnings import begin_response

UTC = ZoneInfo("UTC")


@pytest.mark.remote
def test_the_newest_scan_of_dwd() -> None:
    """The newest of the 48 hours: a scan of a few minutes ago, with cells or, as most are, none."""
    begin_response()

    result = DwdStormCellsRequest().query()

    assert result.df.schema == pl.Schema(_SCHEMA)
    assert result.reference_time is not None
    # a scan every 5 minutes, published 5 to 10 minutes late: an hour is a feed that has stopped, which `scan-stale`
    # tells at 20 minutes
    assert dt.datetime.now(UTC) - result.reference_time < dt.timedelta(hours=1)
    assert result.reference_time.minute % 5 == 0
    assert result.data_updated_at is not None
    assert result.data_updated_at >= result.reference_time
    for row in result.df.iter_rows(named=True):
        assert row["severity_label"] in {"weak", "moderate", "severe", "extreme"}
        assert len(row["track"]) == 12
        assert row["geometry"] is not None


@pytest.mark.remote
def test_a_place_of_germany_keeps_what_is_over_it() -> None:
    """Every cell the box of Germany keeps is one of the scan, and a point in the sea of Greenland has none of them."""
    everywhere = DwdStormCellsRequest(track=False, geometry="centroid").query()
    germany = DwdStormCellsRequest(
        left=5.0, bottom=47.0, right=16.0, top=55.5, track=False, geometry="centroid"
    ).query()
    greenland = DwdStormCellsRequest(latitude=72.0, longitude=-40.0, distance=100.0).query()

    assert set(germany.df["code"]) <= set(everywhere.df["code"])
    assert greenland.df.is_empty()
