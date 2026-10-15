# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for how a radar request turns its start and end into the files it reads."""

import datetime as dt
from collections.abc import Iterator
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst import Settings
from wetterdienst.metadata.period import Period
from wetterdienst.provider.dwd.radar import DwdRadarParameter, DwdRadarValues
from wetterdienst.provider.dwd.radar.api import RadarResult
from wetterdienst.provider.dwd.radar.metadata import DwdRadarPeriod, DwdRadarResolution

UTC = ZoneInfo("UTC")
# a zone that is not a whole hour from UTC, which moved the 50 minute mark to hh:20
INDIA = dt.timezone(dt.timedelta(hours=5, minutes=30))
BERLIN = ZoneInfo("Europe/Berlin")

BASE = "https://opendata.dwd.de/climate_environment/CDC/grids_germany/hourly/radolan"


def _radolan_index(period: Period) -> pl.DataFrame:
    """Give the rows of the file listing the requests below select from, as the reader builds them."""
    if period == Period.HISTORICAL:
        # one archive a month, dated to the first
        return pl.DataFrame(
            {
                "filename": [f"{BASE}/historical/bin/{year}/RW{year}{month:02d}.tar.gz" for year, month in _MONTHS],
                "datetime": [dt.datetime(year, month, 1, tzinfo=UTC) for year, month in _MONTHS],
            },
        )
    # one file an hour, at the 50 minute mark
    hours = [dt.datetime(2026, 10, 1, hour, 50, tzinfo=UTC) for hour in range(6)]
    return pl.DataFrame(
        {
            "filename": [f"{BASE}/recent/bin/raa01-rw_10000-{hour:%y%m%d%H%M}-dwd---bin.gz" for hour in hours],
            "datetime": hours,
        },
    )


_MONTHS = [(2019, 11), (2019, 12), (2020, 1), (2020, 2), (2020, 3)]


@pytest.fixture
def selected_urls(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Collect the urls a RADOLAN_CDC request goes on to download, without a listing or a download."""
    urls: list[str] = []

    def fileindex(*, period: Period, **_: object) -> pl.DataFrame:
        return _radolan_index(period)

    def download(_self: DwdRadarValues, url: str, _start: dt.datetime, _end: dt.datetime) -> Iterator[RadarResult]:
        urls.append(url)
        return iter(())

    monkeypatch.setattr("wetterdienst.provider.dwd.radar.api.create_fileindex_radolan_cdc", fileindex)
    monkeypatch.setattr(DwdRadarValues, "_download_radolan_data", download)
    return urls


def _historical(start: dt.datetime, end: dt.datetime | None = None) -> DwdRadarValues:
    return DwdRadarValues(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=DwdRadarResolution.HOURLY,
        period=DwdRadarPeriod.HISTORICAL,
        start=start,
        end=end,
        settings=Settings(),
    )


@pytest.mark.parametrize(
    "start",
    [
        dt.datetime(2020, 1, 1, 0, 0, tzinfo=UTC),
        dt.datetime(2020, 1, 1, 1, 0, tzinfo=BERLIN),
        dt.datetime(2020, 1, 1, 5, 30, tzinfo=INDIA),
        dt.datetime(2019, 12, 31, 18, 0, tzinfo=dt.timezone(dt.timedelta(hours=-6))),
        "2020-01-01T01:00+01:00",
        "2020-01-01T00:00",
    ],
)
def test_radolan_cdc_start_names_the_same_instant_in_any_zone(start: dt.datetime | str) -> None:
    """Test that one instant selects one file, written in UTC or in the zone of the caller (GH-2818).

    00:00 UTC on New Year's day aligns to 23:50 UTC the evening before, which is in December's
    archive. Left in its own zone, 01:00+01:00 aligned to 00:50+01:00 and was read as January's, so
    the hour before midnight was lost; +05:30 aligned to hh:20 UTC and matched no file at all.
    """
    request = DwdRadarValues(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=DwdRadarResolution.HOURLY,
        period=DwdRadarPeriod.HISTORICAL,
        start=start,
        settings=Settings(),
    )

    assert request.start == dt.datetime(2019, 12, 31, 23, 50, tzinfo=UTC)
    assert request.start.utcoffset() == dt.timedelta(0)
    assert request.end == dt.datetime(2019, 12, 31, 23, 50, 0, 1, tzinfo=UTC)


def test_radolan_cdc_end_is_converted_to_utc() -> None:
    """Test that an aware end is the instant it names, as the start is."""
    request = _historical(
        dt.datetime(2020, 1, 31, 12, tzinfo=UTC),
        dt.datetime(2020, 2, 1, 1, 30, tzinfo=BERLIN),
    )

    assert request.end == dt.datetime(2020, 2, 1, 0, 30, tzinfo=UTC)
    assert request.end.utcoffset() == dt.timedelta(0)


@pytest.mark.parametrize(
    "start", [dt.datetime(2020, 1, 1, 0, 0, tzinfo=UTC), dt.datetime(2020, 1, 1, 1, tzinfo=BERLIN)]
)
def test_radolan_cdc_historical_reads_the_archive_of_the_utc_month(
    selected_urls: list[str], start: dt.datetime
) -> None:
    """Test that the same instant reads the same archive, whatever the zone it is written in."""
    list(_historical(start).query())

    assert selected_urls == [f"{BASE}/historical/bin/2019/RW201912.tar.gz"]


def test_radolan_cdc_historical_reads_every_month_the_window_touches(selected_urls: list[str]) -> None:
    """Test that a window spanning months reads each archive, not only the one it opens in (GH-2818)."""
    list(_historical(dt.datetime(2019, 12, 31, 12, tzinfo=UTC), dt.datetime(2020, 2, 1, 12, tzinfo=UTC)).query())

    assert selected_urls == [
        f"{BASE}/historical/bin/2019/RW201912.tar.gz",
        f"{BASE}/historical/bin/2020/RW202001.tar.gz",
        f"{BASE}/historical/bin/2020/RW202002.tar.gz",
    ]


def test_radolan_cdc_recent_selects_by_the_utc_instant(selected_urls: list[str]) -> None:
    """Test that the recent files are windowed on the UTC clock they are dated on."""
    request = DwdRadarValues(
        parameter=DwdRadarParameter.RADOLAN_CDC,
        resolution=DwdRadarResolution.HOURLY,
        period=DwdRadarPeriod.RECENT,
        start=dt.datetime(2026, 10, 1, 4, 55, tzinfo=BERLIN),  # 02:55 UTC, aligned to the 02:50 mark
        end=dt.datetime(2026, 10, 1, 5, 55, tzinfo=BERLIN),  # 03:55 UTC
        settings=Settings(),
    )
    list(request.query())

    assert selected_urls == [
        f"{BASE}/recent/bin/raa01-rw_10000-{hour}-dwd---bin.gz" for hour in ("2610010250", "2610010350")
    ]
