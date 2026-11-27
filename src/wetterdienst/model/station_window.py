# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Which stations of a selection a window reads: the one rule of the size limit, the walk and the fetch-ahead (GH-4426).

A `values` request for a day reads every station its selection holds, and the size limit counts them, though most of a
list may have closed long before the day: of the 114 stations of DWD's daily list in a box on the North Sea, 50 can
have a reading on 2022-02-18. The one rule here says which stations *can*: the stations of the list whose record
overlaps the window, by the bounds the list publishes. The count of the limit (`ui.limits.selected_station_count`), the
walk of `TimeseriesValues` and its fetch-ahead (`_files_ahead`) all ask it, so the count is exactly the stations read.

- **The rule.** A station is read, and counted, if its list start is on or before the window's end (a null start
  counts), and its list end is null or lies at most the *lag* before the window's start: 366 days, 732 for annual data.
  It is fixed. It is never the `station_window_end_buffer` of the request or any other option: with a buffer of 0 a
  window on today has no station "ending in time", and the count would have been 0 for a request that reads them all.
  A station asked for several datasets has a row for each, and is read if any one row passes (it is then read for all
  its datasets): the count is of stations, not of datasets read.
- **No bounds, no cut.** A list that publishes none (`noaa/ghcn` hourly, `imgw`) has every station counted and read.
- **Opted out.** A network whose list start is not the first value declares `station_list_bounds_hold = False` and why
  (`TimeseriesRequest.station_list_bounds_note`): ECCC's list start is after the first value for most stations, so the
  list cannot say who has data. Its stations are all counted, and the walk reads what it read before (its own
  `_begins_after_window`).
- **Not cut.** A station *named by id* (`stations`, a WMO, WIGOS or ICAO id) is never cut by the window: it is read
  and, with no data in the window, told (`station-without-rows`). A `rank` is as it was: counted as its rank, walked
  by the start of the list alone (it stops when it has its stations, and a station without data in the window does
  not take a place). A name is matched among the stations the window leaves (`filter_by_name`), by the buffer of the
  request, and walked by the start of the list alone.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, cast

import polars as pl

from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.result import StationsFilter

if TYPE_CHECKING:
    from wetterdienst.model.result import StationsResult

#: how long before the start of a window a station's list end may lie and the station still be read for it. Longer than
#: what a list's end lags a station that is still reporting (days for DWD's daily list), and a station that closed
#: within the year is still counted. Fixed: never an option of the request
STATION_END_LAG = dt.timedelta(days=366)
#: the lag for annual data, whose list ends are whole years (DWD's annual index ends the year before last)
STATION_END_LAG_ANNUAL = dt.timedelta(days=732)

#: the selections that name their stations: never cut by the window
NAMED_BY_ID = frozenset(
    {StationsFilter.BY_STATION_ID, StationsFilter.BY_WMO_ID, StationsFilter.BY_WIGOS_ID, StationsFilter.BY_ICAO_ID}
)
#: the selections that are not counted by the rule: a rank is counted as its rank and walked by the start alone, a name
#: is cut by `filter_by_name` already
NOT_RULED = frozenset({StationsFilter.BY_RANK, StationsFilter.BY_NAME})


def rule_applies(stations: StationsResult) -> bool:
    """Say whether the rule cuts the stations of this selection: it has a window, bounds to read and no exemption."""
    if stations._stations_filter in NAMED_BY_ID or stations._stations_filter in NOT_RULED:  # noqa: SLF001
        return False
    request = getattr(stations, "request", None)
    if not getattr(request, "station_list_bounds_hold", True) or getattr(request, "end", None) is None:
        return False
    return "start_timestamp" in stations.df.columns


def can_have_data_in_window(df: pl.DataFrame, start: dt.datetime | None, end: dt.datetime) -> pl.Series:
    """Give, for each row of a station list, whether its bounds leave the window open: the rule on one row.

    The start is compared exactly (a list's start is the first reading, and does not move); the end by the lag.
    A bound the list does not publish states nothing, so the row passes. Without a `start` only the start of the list
    is asked.
    """
    expression = pl.col("start_timestamp").is_null() | (pl.col("start_timestamp") <= end)
    if start is not None and "end_timestamp" in df.columns:
        if "resolution" in df.columns:
            lag = pl.col("resolution").replace_strict(
                {Resolution.ANNUAL.value: STATION_END_LAG_ANNUAL},
                default=STATION_END_LAG,
                return_dtype=pl.Duration("us"),
            )
        else:
            lag = pl.lit(STATION_END_LAG, dtype=pl.Duration("us"))
        expression = expression & (pl.col("end_timestamp").is_null() | (pl.col("end_timestamp") + lag >= start))
    return df.select(expression.alias("passes")).get_column("passes")


def station_ids_read(stations: StationsResult) -> list[str] | None:
    """Give the ids of the stations the rule leaves, in the order of the list, or None where it cuts none.

    A station is left if any of its rows passes (`can_have_data_in_window`). None, not the whole list, for a selection
    the rule does not cut, so that a caller does not have to tell the two apart by a length.
    """
    if not rule_applies(stations):
        return None
    df = stations.df
    start = stations.start
    end = cast("dt.datetime", stations.end)
    passing = df.filter(can_have_data_in_window(df, start, end))
    return passing.get_column("station_id").unique(maintain_order=True).to_list()
