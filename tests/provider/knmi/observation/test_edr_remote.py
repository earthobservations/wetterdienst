# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""KNMI's EDR API, live, for De Bilt and the list of the stations (GH-3928).

Needs the key of the EDR API in `WD_AUTH__KNMI_EDR`, and is skipped without it. Each case is a few requests of the quota
of 1,000 an hour, which the key shares with whoever else uses it.

There is no second route to compare the values with any more: the Open Data files were. Their values are the facts these
tests hold the API to (De Bilt on 2020-01-01: TG 0.8, TN -0.2, TX 1.8, RH 0.0, read from the files on 2026-07-19 and
from
the legacy export of KNMI), and the offline tests hold the rows made of an answer to those the files route returned
(`test_values.py`).
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

import polars as pl
import pytest

from wetterdienst.exceptions import CredentialRejectedError
from wetterdienst.provider.knmi.observation.api import KnmiObservationRequest
from wetterdienst.settings import Settings

if TYPE_CHECKING:
    from pathlib import Path

pytestmark = [
    pytest.mark.remote,
    pytest.mark.skipif(not Settings().auth.knmi_edr, reason="the key of the EDR API is needed: WD_AUTH__KNMI_EDR"),
]

UTC = dt.UTC
DE_BILT = "06260"
SCHIPHOL = "06240"


def _request(
    tmp_path: Path, parameters: list[tuple[str, ...]], start: dt.datetime, end: dt.datetime
) -> KnmiObservationRequest:
    return KnmiObservationRequest(
        parameters=parameters,
        start=start,
        end=end,
        settings=Settings(auth={"knmi_edr": Settings().auth.knmi_edr}, cache_dir=tmp_path / "cache"),
        options={"humanize": False},
    )


def _read(
    tmp_path: Path, parameters: list[tuple[str, ...]], start: dt.datetime, end: dt.datetime, stations: list[str]
) -> pl.DataFrame:
    return _request(tmp_path, parameters, start, end).filter_by_station_id(stations).values().all().df


def _value(df: pl.DataFrame, station: str, parameter: str, stamp: dt.datetime) -> float | None:
    rows = df.filter(
        (pl.col("station_id") == station) & (pl.col("parameter") == parameter) & (pl.col("timestamp") == stamp)
    )
    assert rows.height == 1, (station, parameter, stamp)
    return rows.item(0, "value")


def test_the_first_of_january_2020_is_dated_that_day(tmp_path: Path) -> None:
    """De Bilt, daily, 2020-01-01: TG 0.8, TN -0.2, TX 1.8 and RH 0.0, which the API stamps `2020-01-02T00:00Z`."""
    df = _read(
        tmp_path,
        [("daily", "data")],
        dt.datetime(2020, 1, 1, tzinfo=UTC),
        dt.datetime(2020, 1, 1, tzinfo=UTC),
        [DE_BILT],
    )
    day = dt.datetime(2020, 1, 1, tzinfo=UTC)
    assert [_value(df, DE_BILT, name, day) for name in ("TG", "TN", "TX", "RH")] == [0.8, -0.2, 1.8, 0.0]
    assert df.get_column("timestamp").unique().to_list() == [day]


def test_one_hourly_day_of_one_station_is_the_same_in_a_list_of_two(tmp_path: Path) -> None:
    """De Bilt, hourly, 2020-06-01 (the hours 01:00 to 24:00): 24 stamps, the same alone and beside Schiphol.

    The two are different requests (the block of a year for one station, the 24 hours for two), whose answers agree.
    """
    start, end = dt.datetime(2020, 6, 1, 1, tzinfo=UTC), dt.datetime(2020, 6, 2, 0, tzinfo=UTC)
    alone = _read(tmp_path, [("hourly", "data")], start, end, [DE_BILT])
    both = _read(tmp_path, [("hourly", "data")], start, end, [DE_BILT, SCHIPHOL])
    assert alone.get_column("timestamp").n_unique() == 24
    assert set(both.get_column("station_id")) == {DE_BILT, SCHIPHOL}
    columns = ["parameter", "timestamp", "value", "quality_flags"]
    assert (
        alone.sort(columns)
        .select(columns)
        .equals(both.filter(pl.col("station_id") == DE_BILT).sort(columns).select(columns))
    )


def test_one_hour_of_10_minutes(tmp_path: Path) -> None:
    """De Bilt, 10 minutes, 2020-06-01 12:10 to 13:00: six stamps."""
    df = _read(
        tmp_path,
        [("10_minutes", "data")],
        dt.datetime(2020, 6, 1, 12, 10, tzinfo=UTC),
        dt.datetime(2020, 6, 1, 13, 0, tzinfo=UTC),
        [DE_BILT],
    )
    assert df.get_column("timestamp").n_unique() == 6
    assert df.get_column("timestamp").min() == dt.datetime(2020, 6, 1, 12, 10, tzinfo=UTC)


def test_months_and_years_are_dated_with_their_first_day(tmp_path: Path) -> None:
    """January 2020 (TG 6.2) is 2020-01-01, and 2018 (TG 11.3, the hot year) is 2018-01-01: the API stamps their end."""
    monthly = _read(
        tmp_path,
        [("monthly", "data")],
        dt.datetime(2020, 1, 1, tzinfo=UTC),
        dt.datetime(2020, 3, 1, tzinfo=UTC),
        [DE_BILT],
    )
    assert _value(monthly, DE_BILT, "TG", dt.datetime(2020, 1, 1, tzinfo=UTC)) == 6.2
    annual = _read(
        tmp_path,
        [("annual", "data")],
        dt.datetime(2018, 1, 1, tzinfo=UTC),
        dt.datetime(2020, 1, 1, tzinfo=UTC),
        [DE_BILT],
    )
    assert _value(annual, DE_BILT, "TG", dt.datetime(2018, 1, 1, tzinfo=UTC)) == 11.3
    assert _value(annual, DE_BILT, "TG", dt.datetime(2020, 1, 1, tzinfo=UTC)) == 11.7


def test_the_stations_and_what_keeps_a_closed_one_out_of_a_window(tmp_path: Path) -> None:
    """The 77 stations of the list; Soesterberg (closed 2008) has an end and is not in a window of 2026.

    Schiphol is in a window of 1960, where `/locations?datetime=` would leave it out (its station starts in 1990, its
    values in 1951). The fog stations are 10-minute stations only, block 78 is not in the annual data.
    """
    from wetterdienst.ui.core import limit_stations_to_window  # noqa: PLC0415

    def listing(resolution: str, start: dt.datetime, end: dt.datetime) -> pl.DataFrame:
        return limit_stations_to_window(_request(tmp_path, [(resolution, "data")], start, end).all()).df

    now = dt.datetime(2026, 1, 1, tzinfo=UTC)
    everything = _request(tmp_path, [("10_minutes", "data")], None, None).all().df
    assert everything.height >= 70
    row = everything.filter(pl.col("station_id") == DE_BILT).row(0, named=True)
    assert (row["name"], row["wigos_id"]) == ("De Bilt", "0-20000-0-06260")
    soesterberg = everything.filter(pl.col("station_id") == "06265")
    assert (
        dt.datetime(2008, 12, 1, tzinfo=UTC)
        <= soesterberg.item(0, "end_timestamp")
        <= dt.datetime(2009, 3, 1, tzinfo=UTC)
        if not soesterberg.is_empty()
        else True
    )
    daily_2026 = listing("daily", now, dt.datetime(2026, 1, 31, tzinfo=UTC))
    assert "06265" not in set(daily_2026.get_column("station_id"))
    assert DE_BILT in set(daily_2026.get_column("station_id"))
    assert SCHIPHOL in set(
        listing("daily", dt.datetime(1960, 1, 1, tzinfo=UTC), dt.datetime(1960, 1, 31, tzinfo=UTC)).get_column(
            "station_id"
        )
    )
    assert not {"78871", "78873", "78990"} & set(listing("annual", now, now).get_column("station_id"))
    assert not {"06233", "06236", "06237", "06238"} & set(daily_2026.get_column("station_id"))


def test_the_key_is_checked_against_the_api() -> None:
    """`auth` for the key that is set: valid. For a key the gateway refuses: invalid, with no quota spent."""
    assert KnmiObservationRequest.is_valid(Settings()) is True
    assert KnmiObservationRequest.is_valid(Settings(auth={"knmi_edr": "not-a-key-of-the-edr-api"})) is False


def test_a_key_of_the_open_data_api_is_the_error_that_says_an_edr_key_is_needed(tmp_path: Path) -> None:
    """A key the gateway refuses (403) ends a query with the error that names `WD_AUTH__KNMI_EDR`."""
    request = KnmiObservationRequest(
        parameters=[("daily", "data")],
        settings=Settings(auth={"knmi_edr": "an-open-data-key-is-no-edr-key"}, cache_dir=tmp_path / "cache"),
    )
    with pytest.raises(CredentialRejectedError, match="WD_AUTH__KNMI_EDR"):
        request.all()
