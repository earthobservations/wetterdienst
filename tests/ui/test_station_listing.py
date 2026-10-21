# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for what a stations listing is cut down to: the window it is asked for and the rank of a name (GH-2635)."""

import datetime as dt
from types import SimpleNamespace
from typing import Any

import polars as pl
import pytest

from wetterdienst.model.request import DEFAULT_NAME_RANK, DEFAULT_NAME_RANK_LISTING
from wetterdienst.model.result import StationsFilter, StationsResult
from wetterdienst.options import Options
from wetterdienst.ui import core
from wetterdienst.ui.core import StationsRequest, ValuesRequest

_BASE = {"provider": "dwd", "network": "observation", "parameters": "daily/kl"}


def _utc(date: str) -> dt.datetime:
    return dt.datetime.fromisoformat(date).replace(tzinfo=dt.UTC)


def _listing(
    rows: list[tuple[str, str, dt.datetime | None, dt.datetime | None]],
    window: tuple[str, str] | None,
    options: Options | None = None,
) -> StationsResult:
    """Build a stations listing of (station_id, resolution, start, end) rows, for a window of two dates or none."""
    df = pl.DataFrame(
        {
            "station_id": [row[0] for row in rows],
            "resolution": [row[1] for row in rows],
            "start_timestamp": [row[2] for row in rows],
            "end_timestamp": [row[3] for row in rows],
        },
        schema={
            "station_id": pl.String,
            "resolution": pl.String,
            "start_timestamp": pl.Datetime(time_zone="UTC"),
            "end_timestamp": pl.Datetime(time_zone="UTC"),
        },
    )
    start, end = (None, None) if window is None else (_utc(date) for date in window)
    request: Any = SimpleNamespace(start=start, end=end, options=options or Options())
    return StationsResult(request=request, df=df, _df_all=df, _stations_filter=StationsFilter.ALL)


def test_a_window_keeps_the_rows_whose_record_overlaps_it() -> None:
    """A row is kept unless it started after the window or ended before it; an unpublished bound says nothing."""
    rows = [
        ("inside", "daily", _utc("2000-01-01"), _utc("2021-01-01")),
        ("closed", "daily", _utc("1900-01-01"), _utc("1920-12-31")),
        ("later", "daily", _utc("2021-01-01"), _utc("2022-01-01")),
        ("open end", "daily", _utc("2000-01-01"), None),
        ("open start", "daily", None, _utc("2021-01-01")),
        ("unpublished", "daily", None, None),
        # the edges of the window are in it
        ("ends on the first day", "daily", _utc("2000-01-01"), _utc("2020-05-01")),
        ("starts on the last day", "daily", _utc("2020-05-31"), None),
    ]

    listing = core.limit_stations_to_window(_listing(rows, ("2020-05-01", "2020-05-31")))

    assert listing.df.get_column("station_id").to_list() == [
        row[0] for row in rows if row[0] not in {"closed", "later"}
    ]


def test_a_window_forgives_the_lag_of_the_end_an_index_states() -> None:
    """A station still reporting ends the day before in a daily index, and the year before last in an annual one."""
    rows = [
        # the index of a station still reporting, one and two days short of the window
        ("daily, 1 day", "daily", _utc("2000-01-01"), _utc("2026-10-15")),
        ("daily, 2 days", "daily", _utc("2000-01-01"), _utc("2026-10-14")),
        ("daily, 3 days", "daily", _utc("2000-01-01"), _utc("2026-10-13")),
        # a month and a year are not a fixed span: the monthly index ends at the first of the last month
        ("monthly, 1 month", "monthly", _utc("2000-01-01"), _utc("2026-09-01")),
        ("monthly, 4 months", "monthly", _utc("2000-01-01"), _utc("2026-06-01")),
        ("annual, 1 year", "annual", _utc("2000-01-01"), _utc("2025-01-01")),
        ("annual, 3 years", "annual", _utc("2000-01-01"), _utc("2023-01-01")),
        # a resolution the table does not know has the day-level lag
        ("subdaily, 3 days", "subdaily", _utc("2000-01-01"), _utc("2026-10-13")),
    ]

    listing = core.limit_stations_to_window(_listing(rows, ("2026-10-16", "2026-10-16")))

    assert listing.df.get_column("station_id").to_list() == [
        "daily, 1 day",
        "daily, 2 days",
        "monthly, 1 month",
        "annual, 1 year",
    ]


def test_a_listing_without_a_window_is_left_as_it_is() -> None:
    """No window, no filter: every row stays, whatever its record says."""
    rows = [("closed", "daily", _utc("1900-01-01"), _utc("1920-12-31")), ("open", "daily", None, None)]
    assert core.limit_stations_to_window(_listing(rows, None)).df.height == 2


def test_a_window_filters_the_rows_of_a_station_by_dataset() -> None:
    """A station asked for two datasets has a row for each, and the one whose record misses the window goes."""
    rows = [
        ("00001", "daily", _utc("1950-01-01"), _utc("2026-10-15")),
        ("00001", "hourly", _utc("2001-01-01"), _utc("2005-01-01")),
    ]

    listing = core.limit_stations_to_window(_listing(rows, ("2020-05-01", "2020-05-31")))

    assert listing.df.get_column("resolution").to_list() == ["daily"]


def test_a_name_defaults_to_the_best_five_in_a_listing_and_the_best_one_in_a_fetch(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The rank a name is looked up with comes from the kind of request, an explicit one winning."""
    taken: list[int] = []

    class Request:
        def filter_by_name(self, name: str, rank: int, threshold: float, df_all: pl.DataFrame | None = None) -> str:  # noqa: ARG002
            taken.append(rank)
            return "stations"

    monkeypatch.setattr(core, "_get_stations_request", lambda **_kwargs: Request())
    base = {**_BASE, "name": "Dresden"}
    asked: list[tuple[type[StationsRequest | ValuesRequest], dict[str, int]]] = [
        (StationsRequest, {}),
        (ValuesRequest, {}),
        (StationsRequest, {"rank": 2}),
        (ValuesRequest, {"rank": 3}),
    ]
    for model, extra in asked:
        core.get_stations(None, model.model_validate({**base, **extra}), None, None)  # ty: ignore[invalid-argument-type]

    assert taken == [DEFAULT_NAME_RANK_LISTING, DEFAULT_NAME_RANK, 2, 3]
    assert (DEFAULT_NAME_RANK_LISTING, DEFAULT_NAME_RANK) == (5, 1)
