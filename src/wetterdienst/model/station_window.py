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
- **Not cut.** A station *named by id* (`stations`, a WMO, WIGOS or ICAO id) is exempt from the end of the rule alone:
  a closed one is read and, with no data in the window, told (`station-without-rows`, `parameter-without-rows`), but
  one whose list begins after the window is left out by the walk's own `_begins_after_window`, as it was, so no request
  is made for it. The count of the limit skips exactly those (`named_station_ids_read`, which asks the walk's
  predicate). A `rank` is as it was: counted as its rank, walked by the start of the list alone (it stops when it has
  its stations, and a station without data in the window does not take a place). A name is matched among the stations
  the window leaves (`filter_by_name`), by the buffer of the request, and walked by the start of the list alone.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, cast

import polars as pl

from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.parameter_rows import MAX_STATIONS_LISTED, _window
from wetterdienst.model.result import StationsFilter
from wetterdienst.util.logging import get_one_line_logger
from wetterdienst.util.response_warnings import (
    NO_STATION_READ,
    STATIONS_OUTSIDE_WINDOW,
    recorded_warnings,
    warn_response,
)

if TYPE_CHECKING:
    from collections.abc import Callable

    from wetterdienst.model.result import StationsResult

log = get_one_line_logger(__name__)

#: how many of the stations left out the warning names
MAX_LISTED = 10

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
    return getattr(request, "station_list_bounds_hold", True) and getattr(request, "end", None) is not None


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


def named_station_ids_read(stations: StationsResult) -> list[str] | None:
    """Give the ids of the named stations the walk reads, in the order of the list, or None for any other selection.

    A station named by id is exempt from the end of the rule, and left out by the walk only where its list begins after
    the window: `TimeseriesValues._begins_after_window`, asked here, the walk's own predicate and not a copy, so
    that the count is the reads. None where there is no window to begin after.
    """
    request = getattr(stations, "request", None)
    if stations._stations_filter not in NAMED_BY_ID or getattr(request, "end", None) is None:  # noqa: SLF001
        return None
    values = stations.values()
    return [
        cast("str", station_id)
        for (station_id,), meta in stations.df.group_by(["station_id"], maintain_order=True)
        if not values._begins_after_window(meta)  # noqa: SLF001
    ]


def stations_read(stations: StationsResult) -> list[str] | None:
    """Give the ids of the stations a window reads, by the rule or for the named stations, None where it cuts none."""
    if stations._stations_filter in NAMED_BY_ID:  # noqa: SLF001
        return named_station_ids_read(stations)
    return station_ids_read(stations)


def window_cut_stations(stations: StationsResult) -> bool:
    """Say whether the window left out at least one station of the selection: the count is then below the list."""
    read = stations_read(stations)
    return read is not None and len(read) < stations.df.get_column("station_id").n_unique()


def _names(ids: list[str]) -> str:
    shown = ids[:MAX_LISTED]
    return ", ".join(shown) + (f", and {len(ids) - len(shown)} more" if len(ids) > len(shown) else "")


def warn_left_out(
    stations: StationsResult, read: list[str], begins_after_window: Callable[[pl.DataFrame], bool]
) -> set[str]:
    """Tell, as one `stations-outside-window` warning, the stations of the selection the rule leaves out (GH-4426).

    Without it a selection that the rule cuts to nothing is an answer with no rows and no word, which reads like a
    request that failed. It says how many of how many, why (the list's own bounds), and names the first ten of each
    kind. Of the two kinds, the stations whose list ends before the window can be read by naming them by id, and the
    ones whose list begins after it (`begins_after_window`, the walk's predicate) cannot: the advice is for the first.
    Gives the ids it left out (the warning names the first ten), which `no-station-read` does not tell again.
    """
    listed = stations.df.get_column("station_id").unique(maintain_order=True).to_list()
    kept = set(read)
    left = [station for station in listed if station not in kept]
    if not left:
        return set()
    late_ids = {
        station_id
        for (station_id,), meta in stations.df.group_by(["station_id"], maintain_order=True)
        if station_id not in kept and begins_after_window(meta)
    }
    ended = [station for station in left if station not in late_ids]
    late = [station for station in left if station in late_ids]
    resolutions = set(stations.df.get_column("resolution").to_list()) if "resolution" in stations.df.columns else set()
    lag = STATION_END_LAG_ANNUAL.days if resolutions == {Resolution.ANNUAL.value} else STATION_END_LAG.days
    total, count = len(listed), len(left)
    if total == 1:
        head = "The one station of the selection is not read"
    else:
        head = f"{count} of the {total} stations of the selection {'are' if count > 1 else 'is'} not read"
    ends = f"ends more than {lag} days before the window"
    begins = "begins after the window"
    one = count == 1
    its, it_has, it = ("its", "it has", "it") if one else ("their", "they have", "them")
    if not late:
        message = (
            f"{head}: {its} station list {ends} ({_names(ended)}), so {it_has} no data in it by the list. "
            f"Name the station{'' if one else 's'} by id (`stations`) to read {it} anyway."
        )
    elif not ended:
        message = (
            f"{head}: {its} station list {begins} ({_names(late)}), so {it_has} no data in it by the list. "
            f"Naming {it} by id does not read {it}."
        )
    else:
        few = len(ended) == 1
        message = (
            f"{head}: {len(ended)} whose station list {ends} ({_names(ended)}), and {len(late)} whose list {begins} "
            f"({_names(late)}); by the list they have no data in it. Name the station{'' if few else 's'} that ended "
            f"by id (`stations`) to read {'it' if few else 'them'} anyway; a station whose list {begins} is not read "
            "even then."
        )
    warn_response(log, STATIONS_OUTSIDE_WINDOW, message, stations=left[:MAX_LISTED])
    return set(left)


#: what an empty selection of each kind says it matched nothing of (`warn_no_station_read`)
_EMPTY_SELECTION = {
    StationsFilter.BY_NAME: "no station matches the name",
    StationsFilter.BY_BBOX: "no station lies in the bounding box",
    StationsFilter.BY_DISTANCE: "no station lies within the distance",
    StationsFilter.BY_RANK: "no station with a position was found for the rank",
    StationsFilter.BY_SQL: "no station matches the SQL filter",
    StationsFilter.BY_REGION: "no station is listed under the region",
}
#: the warnings that already say why a selection holds no station
_EXPLAINS_EMPTY = frozenset({"unknown-station", "positions-unavailable"})


def warn_no_station_read(
    stations: StationsResult,
    late: list[str],
    *,
    selected: int,
    covered: set[str],
) -> None:
    """Tell, as one `no-station-read` warning, that a walk read to its end read no station (GH-4510).

    Without it the answer has no rows and no word, which reads like a request that failed. Two causes, each worded
    for itself. `late` is the stations of the selection the walk left out because their list begins after the window
    (`TimeseriesValues._begins_after_window`: stations named by id, the candidates of a `rank`, ECCC); `selected` is
    how many stations the selection holds, 0 for one that matched none (a name, a box, a distance, a region, an SQL
    filter). `covered` is the ids `stations-outside-window` named: a station it told is not told twice, so nothing is
    said where it explains every one of them. A selection by id that holds no station has `unknown-station` already,
    and a search by place on a network without positions `positions-unavailable`.
    """
    named = stations._stations_filter in NAMED_BY_ID  # noqa: SLF001
    window = _window(stations.start, stations.end)
    if selected == 0:
        if named or _EXPLAINS_EMPTY & {warning["code"] for warning in recorded_warnings()}:
            return
        kind = _EMPTY_SELECTION.get(stations._stations_filter)  # noqa: SLF001
        why = f"{kind[0].upper()}{kind[1:]}" if kind else "The network lists no station for the requested parameters"
        warn_response(
            log,
            NO_STATION_READ,
            f"The selection holds no station, so no station was read and the answer has no rows{window}: {why}. "
            "The request did not fail.",
        )
        return
    uncovered = [station for station in late if station not in covered]
    if not uncovered:
        return
    count = len(uncovered)
    one = count == 1
    names = ", ".join(uncovered[:MAX_STATIONS_LISTED])
    if count > MAX_STATIONS_LISTED:
        names += f", and {count - MAX_STATIONS_LISTED} more"
    head = (
        f"No station was read: the station list of {names} begins after the window{window}, so by the list "
        f"{'it has' if one else 'they have'} no data in it. The answer has no rows because of that, not because the "
        "request failed."
    )
    if named:
        head += f" Naming {'it' if one else 'them'} by id does not read {'it' if one else 'them'}."
    warn_response(log, NO_STATION_READ, head, stations=uncovered[:MAX_STATIONS_LISTED])
