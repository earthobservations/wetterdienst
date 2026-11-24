# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What the row options choose of the values, held to an oracle that is plain Python (GH-4411).

The reader of the values (`all`, `query`), the result (`selected_rows`) and the function on a frame
(`RowSelection.apply`) must agree with each other and with a naive working-out of the same words: the readings are
a function of the station and the day (`tests/ui/row_options_stub.py`), so the answer is computed without polars.
"""

from __future__ import annotations

import datetime as dt
import operator
from dataclasses import replace
from typing import Any

import polars as pl
import pytest

from tests.ui.row_options_stub import DAYS, STATIONS, TMAX, TMIN, oracle, serve
from wetterdienst.exceptions import RequestError
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.row_selection import (
    RowSelection,
    RowSelectionRefusedError,
    RowsOverLimitError,
    Searched,
    latest_complete,
    parse_row_selection,
    searched_of,
)
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.observation import DwdObservationRequest

_COMPARE = {
    "=": operator.eq,
    "!=": operator.ne,
    "<": operator.lt,
    "<=": operator.le,
    ">": operator.gt,
    ">=": operator.ge,
}
_PARTS = {
    "year": lambda ts: ts.year,
    "month": lambda ts: ts.month,
    "day": lambda ts: ts.day,
    "hour": lambda ts: ts.hour,
}


def _rows(parameters: list[str]) -> list[dict[str, Any]]:
    rows = []
    for station in STATIONS:
        # the answer's own order: by station, by parameter name, by time
        for name in sorted(parameter.rsplit("/", 1)[1] for parameter in parameters):
            rows.extend(
                {"station_id": station, "parameter": name, "timestamp": ts, "value": value}
                for ts, value in oracle(station, name)
            )
    return rows


def _expected(  # noqa: C901
    parameters: list[str],
    *,
    filter_: list[tuple[str, str, tuple[float, ...]]] = (),
    sort: list[tuple[str, bool]] = (),
    first: int | None = None,
    by: list[str] | None = None,
) -> list[tuple[str, str, dt.datetime, float]]:
    """Work out the rows of the answer the slow way: a loop for each rule of the words."""

    def column(row: dict[str, Any], name: str) -> Any:  # noqa: ANN401
        return row[name] if name in ("value", "timestamp", "station_id") else _PARTS[name](row["timestamp"])

    def meets(row: dict[str, Any]) -> bool:
        for name, op, numbers in filter_:
            value = column(row, name)
            if op == "=":
                ok = any(value == n for n in numbers)
            elif op == "!=":
                ok = all(value != n for n in numbers)
            else:
                ok = _COMPARE[op](value, numbers[0])
            if not ok:
                return False
        return True

    rows = [row for row in _rows(parameters) if meets(row)]
    group_by = ["station_id"] if by is None else by
    if first is not None:
        groups: dict[tuple[Any, ...], list[dict[str, Any]]] = {}
        for row in rows:
            if all(column(row, name) is not None for name, _ in sort):
                groups.setdefault((row["parameter"], *(column(row, name) for name in group_by)), []).append(row)
        kept = []
        for members in groups.values():
            ordered = members
            for name, descending in reversed(sort):
                ordered = sorted(ordered, key=lambda r, n=name: column(r, n), reverse=descending)
            # a row is kept when fewer than `first` rows of its group sort strictly before it: the position of the
            # first row of its run of equal keys
            run_start = 0
            for index, row in enumerate(ordered):
                if index and any(column(row, name) != column(ordered[index - 1], name) for name, _ in sort):
                    run_start = index
                if run_start < first:
                    kept.append(row)
        rows = kept
    if sort:
        for name, descending in reversed([*sort, ("station_id", False), ("timestamp", False)]):
            rows = sorted(rows, key=lambda r, n=name: column(r, n), reverse=descending)
        rows = sorted(rows, key=lambda r: r["parameter"])
    return [(r["station_id"], r["parameter"], r["timestamp"], r["value"]) for r in rows]


def _same(got: list[Any], expected: list[Any]) -> None:
    """Assert two lists of rows are equal, naming the first row that differs (a diff of thousands of rows is slow)."""
    assert len(got) == len(expected), (len(got), len(expected))
    for index, (left, right) in enumerate(zip(got, expected, strict=True)):
        assert left == right, (index, left, right)


def _got(frame: pl.DataFrame) -> list[tuple[str, str, dt.datetime, float]]:
    return [(r["station_id"], r["parameter"], r["timestamp"], r["value"]) for r in frame.iter_rows(named=True)]


CASES = [
    pytest.param({"filter": "value<=-9"}, id="filter only keeps the order of the read"),
    pytest.param({"filter": "value>=-5,value<=-4.5"}, id="a range of two conditions"),
    pytest.param({"filter": "month=12|1|2,year!=2019", "sort": "value"}, id="lists, not-equal, sort"),
    pytest.param({"filter": "month=12,month=1"}, id="contradictory conditions: empty, no error"),
    pytest.param({"filter": "value!=1.0"}, id="not-equal never matches a gap"),
    pytest.param({"sort": "-value"}, id="sort alone"),
    pytest.param({"sort": "value", "first": 1}, id="the lowest of every station: ties kept"),
    pytest.param({"sort": "-value", "first": 3}, id="the three highest of every station"),
    pytest.param({"sort": "value", "first": 1, "by": "station_id,year"}, id="the lowest of every year"),
    pytest.param({"sort": "value", "first": 1, "by": "year"}, id="the lowest of every year over the stations"),
    pytest.param({"sort": "-value", "first": 2, "by": "none"}, id="the two highest over all stations"),
    pytest.param(
        {"filter": "month=12,day=24", "sort": "-value", "first": 1, "by": "none"}, id="24 December, the warmest"
    ),
    pytest.param(
        {"filter": "value<0", "sort": "month,day", "first": 1, "by": "none"},
        id="the earliest calendar day with a frost",
    ),
    pytest.param({"sort": "-timestamp", "first": 1}, id="the latest value of every station"),
    pytest.param({"sort": "month,-value", "first": 2, "by": "station_id,month"}, id="two keys, grouped by month"),
    pytest.param({"filter": "value>100", "sort": "value", "first": 1}, id="nothing matches"),
    pytest.param({"max_rows": 3}, id="max_rows alone keeps the first rows as they are read"),
    pytest.param({"filter": "value<=-9", "max_rows": 7}, id="max_rows after a filter"),
    pytest.param({"sort": "value", "first": 1, "max_rows": 5}, id="the lowest of every station, cut"),
    pytest.param({"sort": "-value", "first": 2, "by": "year", "max_rows": 4}, id="groups over stations, cut"),
    pytest.param({"sort": "-value", "max_rows": 10}, id="a sort alone, cut"),
]


@pytest.fixture(autouse=True)
def _stub(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve the stub network on every test of this module."""
    serve(monkeypatch)


@pytest.mark.parametrize("rows", CASES)
@pytest.mark.parametrize("parameters", [[TMIN], [TMIN, TMAX]], ids=["one parameter", "two parameters"])
def test_the_reader_chooses_the_rows_the_oracle_does(rows: dict[str, Any], parameters: list[str]) -> None:
    """The reader chooses the rows the oracle does."""
    request = DwdObservationRequest(parameters=parameters, start="2018-01-01", end="2020-12-31")
    reader = request.all().values()
    got = reader.all(**rows)

    selection = parse_row_selection(**rows)
    assert selection is not None
    matching = _expected(
        parameters,
        filter_=[(c.column, c.operator, c.values) for c in selection.conditions],
        sort=[(k.column, k.descending) for k in selection.sort],
        first=selection.first,
        by=None if selection.by is None else list(selection.by),
    )
    # the cap is the last step: the first rows of what matched, in the order of the answer
    expected = matching if selection.max_rows is None else matching[: selection.max_rows]
    _same(_got(got.df), expected)

    # the result's own method and the function on a frame choose the same rows as the reader did station by station
    whole = request.all().values().all()
    _same(_got(whole.selected_rows(**rows).df), expected)
    _same(_got(selection.apply(whole.df)), expected)
    assert got.search is not None
    # what matched is counted before the cap, what is returned after it
    assert got.search.series.get_column("matched").sum() == len(matching)
    assert got.search.series.get_column("returned").sum() == len(expected)


def test_what_was_searched_is_counted_before_the_options_choose() -> None:
    """What was searched is counted before the options choose."""
    request = DwdObservationRequest(parameters=[TMIN], start="2018-01-01", end="2020-12-31")
    got = request.all().values().all(filter="value<=-9.5", sort="value", first=1)
    assert got.search is not None
    series = got.search.series.sort("station_id")
    for row in series.iter_rows(named=True):
        readings = oracle(row["station_id"], "temperature_air_min_2m")
        assert row["searched"] == len(readings)
        assert row["expected"] == DAYS
        assert row["first"] == readings[0][0]
        assert row["last"] == readings[-1][0]
        assert row["matched"] == sum(1 for r in got.df.iter_rows(named=True) if r["station_id"] == row["station_id"])
    report = got.search.to_dict()
    assert report["options"] == {"filter": "value<=-9.5", "sort": "value", "first": 1, "by": None, "max_rows": None}
    assert report["totals"]["series"] == 3
    assert report["totals"]["expected"] == 3 * DAYS
    assert report["totals"]["searched"] < report["totals"]["expected"]  # the gaps show


def test_an_empty_answer_still_reports_what_was_searched() -> None:
    """An empty answer still reports what was searched."""
    request = DwdObservationRequest(parameters=[TMIN], start="2018-01-01", end="2020-12-31")
    got = request.all().values().all(filter="value>100")
    assert got.df.is_empty()
    assert got.search is not None
    assert got.search.series.height == 3
    assert got.search.series.get_column("matched").sum() == 0
    assert got.search.series.get_column("searched").min() > 1000


def test_no_option_leaves_the_answer_and_its_report_as_they_were() -> None:
    """No option leaves the answer and its report as they were."""
    request = DwdObservationRequest(parameters=[TMIN], start="2018-01-01", end="2020-12-31")
    got = request.all().values().all()
    assert got.search is None
    assert request.all().values().all(filter="", sort=None).search is None


def test_the_selection_is_applied_after_the_rank_counts_its_stations() -> None:
    """A rank is filled with the stations that returned values: the options choose rows, never stations."""
    request = DwdObservationRequest(parameters=[TMIN], start="2018-01-01", end="2020-12-31")
    got = request.filter_by_rank(latlon=(53.6, 10.0), rank=2).values().all(filter="value>100")
    assert got.df.is_empty()
    assert got.search is not None
    assert sorted(got.search.series.get_column("station_id").to_list()) == ["00001", "00002"]


def test_query_gives_each_station_its_own_choice_and_refuses_what_spans_stations() -> None:
    """Query gives each station its own choice and refuses what spans stations."""
    request = DwdObservationRequest(parameters=[TMIN], start="2018-01-01", end="2020-12-31")
    stations = request.all()
    results = list(stations.values().query(sort="-value", first=1))
    assert [r.df.get_column("station_id").unique().to_list() for r in results] == [["00001"], ["00002"], ["00003"]]
    assert all(r.search is not None for r in results)
    merged = pl.concat([r.df for r in results])
    _same(sorted(_got(merged)), sorted(_got(stations.values().all(sort="-value", first=1).df)))
    with pytest.raises(RowSelectionRefusedError, match="use `all`"):
        next(stations.values().query(sort="-value", first=1, by="year"))
    assert issubclass(RowSelectionRefusedError, RequestError)


def test_value_over_parameters_of_two_units_is_refused_with_how_to_ask() -> None:
    """Value over parameters of two units is refused with how to ask."""
    gust = "daily/climate_summary/wind_gust_max"
    request = DwdObservationRequest(parameters=[TMIN, gust], start="2018-01-01", end="2020-12-31")
    reader = request.all().values()
    with pytest.raises(RowSelectionRefusedError, match=r"not in one unit.*Name one parameter") as raised:
        reader.all(filter="value<=-2")
    assert "°C" in str(raised.value)
    assert "m/s" in str(raised.value)
    # the groups of `first` are one parameter each, so a sort by value is fine, and so is a filter on the calendar
    assert reader.all(sort="value", first=1).df.height > 0
    assert reader.all(filter="month=1").df.height > 0


def test_a_selection_of_value_is_refused_in_the_wide_shape_and_the_calendar_is_not() -> None:
    """A selection of value is refused in the wide shape and the calendar is not."""
    request = DwdObservationRequest(parameters=[TMIN], start="2018-01-01", end="2020-12-31", options={"shape": "wide"})
    reader = request.all().values()
    with pytest.raises(RowSelectionRefusedError, match="not available in the wide shape"):
        reader.all(filter="value<0")
    with pytest.raises(RowSelectionRefusedError, match="not available in the wide shape"):
        reader.all(sort="value", first=1)
    got = reader.all(filter="year=2019,month=2", sort="-day", first=1)
    assert got.df.columns[:4] == ["station_id", "resolution", "dataset", "timestamp"]
    assert got.df.get_column("timestamp").dt.year().unique().to_list() == [2019]
    assert got.df.get_column("timestamp").dt.month().unique().to_list() == [2]
    assert got.df.get_column("timestamp").dt.day().unique().to_list() == [28]
    assert got.df.height == 3
    assert got.search is not None
    assert got.search.series.get_column("matched").to_list() == [1, 1, 1]


def test_calendar_parts_are_those_of_the_utc_stamp_across_the_day_boundary() -> None:
    """The year, month, day and hour of a stamp are read in UTC: 23:00 of New Year's Eve is still that year."""
    stamps = [
        dt.datetime(2020, 12, 31, 22, tzinfo=dt.UTC),
        dt.datetime(2020, 12, 31, 23, tzinfo=dt.UTC),
        dt.datetime(2021, 1, 1, 0, tzinfo=dt.UTC),
        dt.datetime(2021, 1, 1, 1, tzinfo=dt.UTC),
    ]
    frame = pl.DataFrame(
        {
            "station_id": ["1"] * 4,
            "resolution": ["hourly"] * 4,
            "dataset": ["x"] * 4,
            "parameter": ["t"] * 4,
            "timestamp": stamps,
            "value": [1.0, 2.0, 3.0, 4.0],
        },
        schema_overrides={"timestamp": pl.Datetime("us", "UTC")},
    )

    def pick(text: str) -> list[float]:
        selection = parse_row_selection(filter=text)
        assert selection is not None
        return selection.apply(frame).get_column("value").to_list()

    assert pick("year=2020") == [1.0, 2.0]
    assert pick("year=2021") == [3.0, 4.0]
    assert pick("month=12,day=31,hour=23") == [2.0]
    assert pick("month=1,day=1,hour=0") == [3.0]
    assert pick("hour=23|0") == [2.0, 3.0]


def test_ties_of_the_last_row_are_kept_and_the_order_is_fully_determined() -> None:
    """Ties of the last row are kept and the order is fully determined."""
    stamps = [dt.datetime(2020, 1, d, tzinfo=dt.UTC) for d in (1, 2, 3, 4, 5)]
    frame = pl.DataFrame(
        {
            "station_id": ["b", "a", "b", "a", "a"],
            "resolution": ["daily"] * 5,
            "dataset": ["x"] * 5,
            "parameter": ["t"] * 5,
            "timestamp": stamps,
            "value": [1.0, 1.0, 2.0, 1.0, 3.0],
        },
        schema_overrides={"timestamp": pl.Datetime("us", "UTC")},
    )
    selection = parse_row_selection(sort="value", first=1, by="none")
    assert selection is not None
    got = selection.apply(frame)
    # three rows tie for the lowest: ordered by station, then timestamp, whatever order they were read in
    assert got.select("station_id", pl.col("timestamp").dt.day().alias("d")).rows() == [("a", 2), ("a", 4), ("b", 1)]
    shuffled = frame.sample(fraction=1.0, shuffle=True, seed=3)
    assert selection.apply(shuffled).equals(got)


def test_a_null_has_no_place_in_the_order_and_never_matches() -> None:
    """A null has no place in the order and never matches."""
    stamps = [dt.datetime(2020, 1, d, tzinfo=dt.UTC) for d in (1, 2, 3)]
    frame = pl.DataFrame(
        {
            "station_id": ["a"] * 3,
            "resolution": ["daily"] * 3,
            "dataset": ["x"] * 3,
            "parameter": ["t"] * 3,
            "timestamp": stamps,
            "value": [None, 5.0, 7.0],
        },
        schema_overrides={"timestamp": pl.Datetime("us", "UTC"), "value": pl.Float64},
    )
    first = parse_row_selection(sort="value", first=1)
    assert first is not None
    assert first.apply(frame).get_column("value").to_list() == [5.0]
    for text in ("value!=5", "value<=100", "value>=-100", "value=5|7"):
        selection = parse_row_selection(filter=text)
        assert selection is not None
        assert None not in selection.apply(frame).get_column("value").to_list()
    # a sort alone keeps the null, last, in either direction
    for text in ("value", "-value"):
        selection = parse_row_selection(sort=text)
        assert selection is not None
        assert selection.apply(frame).get_column("value").to_list()[-1] is None


def test_the_selection_of_a_station_then_of_the_whole_is_the_selection_of_the_whole() -> None:
    """The property `first` over stations rests on: the first rows of a group are among those of its parts."""
    import random  # noqa: PLC0415

    rng = random.Random(11)  # noqa: S311
    rows = []
    for index in range(600):
        rows.append(
            {
                "station_id": rng.choice("abcd"),
                "resolution": "daily",
                "dataset": "x",
                "parameter": rng.choice("tw"),
                "timestamp": dt.datetime(
                    2000 + rng.randint(0, 5), rng.randint(1, 12), rng.randint(1, 28), tzinfo=dt.UTC
                ),
                "value": float(rng.randint(0, 6)),
            }
        )
        _ = index
    frame = pl.DataFrame(rows, schema_overrides={"timestamp": pl.Datetime("us", "UTC")}).unique(
        ["station_id", "parameter", "timestamp"]
    )
    for text in (
        {"sort": "value", "first": 2, "by": "year"},
        {"sort": "-value", "first": 3, "by": "none"},
        {"sort": "month,-value", "first": 1, "by": "month"},
        {"filter": "value>=2", "sort": "value", "first": 2, "by": "station_id"},
    ):
        selection = parse_row_selection(**text)
        assert isinstance(selection, RowSelection)
        parts = [selection.reduce_station(part) for _, part in frame.group_by("station_id", maintain_order=True)]
        assert selection.finish(parts).equals(selection.apply(frame)), text


def test_a_walk_whose_choice_stays_in_a_station_is_stopped_at_the_limit_it_was_given() -> None:
    """The rows chosen are the answer, so more than may be held is known after a station, not after the last."""
    request = DwdObservationRequest(parameters=[TMIN], start="2018-01-01", end="2020-12-31")
    reader = request.all().values()
    reader._held_rows_limit = 500  # noqa: SLF001
    with pytest.raises(RowsOverLimitError) as raised:
        reader.all(sort="value", first=1, by="station_id,year,month,day")
    # one station holds about 1,000 readings: stopped there, with the stations after it not read
    assert 500 < raised.value.rows < 1500
    assert raised.value.maximum == 500
    assert issubclass(RowsOverLimitError, RequestError)
    # a choice that fits is not stopped, and none is where no limit is given
    assert request.all().values().all(sort="value", first=1).df.height > 0
    # groups that span stations are made again once the held rows reach the limit (here 10), and refused if what
    # is left is more: the tie of every station's lowest value is 17 rows
    reader._held_rows_limit = 10  # noqa: SLF001
    with pytest.raises(RowsOverLimitError) as spanning:
        reader.all(sort="value", first=1, by="none")
    assert spanning.value.maximum == 10
    reader._held_rows_limit = 100  # noqa: SLF001
    assert reader.all(sort="value", first=1, by="none").df.height > 0


def test_what_piles_up_over_groups_that_span_stations_is_made_again_without_changing_the_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The choice is made again over what piled up, and the rows are those of the choice made once."""
    request = DwdObservationRequest(parameters=[TMIN], start="2018-01-01", end="2020-12-31")
    expected = request.all().values().all(sort="-value", first=3, by="year")
    monkeypatch.setattr(TimeseriesValues, "_COMPACT_CELLS", 1)
    compacted = request.all().values().all(sort="-value", first=3, by="year")
    _same(_got(compacted.df), _got(expected.df))
    assert compacted.search is not None
    assert compacted.search.series.get_column("matched").sum() == expected.df.height


def _series_frame(resolution: str, stamps: list[dt.datetime]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "station_id": ["1"] * len(stamps),
            "resolution": [resolution] * len(stamps),
            "dataset": ["x"] * len(stamps),
            "parameter": ["t"] * len(stamps),
            "timestamp": stamps,
            "value": [1.0] * len(stamps),
        },
        schema_overrides={"timestamp": pl.Datetime("us", "UTC")},
    )


def _days(first: dt.date, last: dt.date) -> list[dt.datetime]:
    return [
        dt.datetime.combine(first + dt.timedelta(days=n), dt.time(), dt.UTC) for n in range((last - first).days + 1)
    ]


def _utc(*parts: int) -> dt.datetime:
    return dt.datetime(*parts, tzinfo=dt.UTC)


NOW = _utc(2026, 11, 24, 12, 34)


def _report(frame: pl.DataFrame, window: tuple[dt.datetime | None, dt.datetime | None]) -> dict[str, Any]:
    return searched_of(frame, window, NOW).row(0, named=True)


def test_without_a_window_what_is_expected_is_the_span_of_the_values() -> None:
    """From the first value to the last; the gaps are the same number."""
    stamps = [s for s in _days(dt.date(2020, 1, 1), dt.date(2020, 1, 31)) if s.day not in (5, 6)]
    row = _report(_series_frame("daily", stamps), (None, None))
    assert (row["searched"], row["expected"], row["gaps"]) == (29, 31, 2)


def test_a_year_that_is_not_over_is_incomplete_up_to_the_last_complete_day() -> None:
    """The window is 2026; the series ends on 20 November, and yesterday (the 23rd) is the last day it could have."""
    row = _report(
        _series_frame("daily", _days(dt.date(2026, 1, 1), dt.date(2026, 11, 20))),
        (_utc(2026, 1, 1), _utc(2026, 12, 31)),
    )
    assert (row["searched"], row["expected"], row["gaps"]) == (324, 327, 0)
    # not the future: a window that is over is counted to its own end
    row = _report(
        _series_frame("daily", _days(dt.date(2025, 1, 1), dt.date(2025, 12, 31))),
        (_utc(2025, 1, 1), _utc(2025, 12, 31)),
    )
    assert (row["searched"], row["expected"], row["gaps"]) == (365, 365, 0)


def test_a_window_before_the_start_of_the_data_counts_the_years_it_asks_for() -> None:
    """The window begins in 2017, the station in 2018: a year is missing from what the request covers, not the span."""
    row = _report(
        _series_frame("daily", _days(dt.date(2018, 1, 1), dt.date(2018, 12, 31))),
        (_utc(2017, 1, 1), _utc(2018, 12, 31)),
    )
    assert (row["searched"], row["expected"], row["gaps"]) == (365, 730, 0)


def test_a_station_that_ended_before_the_window_does_is_incomplete() -> None:
    """The window is 2000 to 2010 and the station stops in 2005: the rest is missing from what the request covers."""
    row = _report(
        _series_frame("daily", _days(dt.date(2000, 1, 1), dt.date(2005, 12, 31))),
        (_utc(2000, 1, 1), _utc(2010, 12, 31)),
    )
    assert (row["searched"], row["expected"], row["gaps"]) == (2192, 4018, 0)
    assert row["last"] == _utc(2005, 12, 31)


def test_a_window_in_the_future_is_a_forecasts_and_has_no_past_to_miss() -> None:
    """A window that begins after the last complete reading has no gap to count: the span of the values is it."""
    stamps = [_utc(2026, 12, 1, hour) for hour in range(24)]
    row = _report(_series_frame("hourly", stamps), (_utc(2026, 12, 1), _utc(2026, 12, 1, 23, 59)))
    assert (row["searched"], row["expected"], row["gaps"]) == (24, 24, 0)


def test_the_last_complete_reading_of_a_resolution_is_the_one_before_the_one_running() -> None:
    """Yesterday for days, the hour before this one, last month, last year; none where there is no fixed step."""
    assert latest_complete(Resolution.DAILY, NOW) == _utc(2026, 11, 23)
    assert latest_complete(Resolution.HOURLY, NOW) == _utc(2026, 11, 24, 11)
    assert latest_complete(Resolution.MINUTE_10, NOW) == _utc(2026, 11, 24, 12, 20)
    assert latest_complete(Resolution.MONTHLY, NOW) == _utc(2026, 10, 1)
    assert latest_complete(Resolution.MONTHLY, _utc(2026, 1, 3)) == _utc(2025, 12, 1)
    assert latest_complete(Resolution.ANNUAL, NOW) == _utc(2025, 1, 1)
    assert latest_complete(Resolution.SUBDAILY, NOW) is None


def test_a_resolution_with_no_step_expects_nothing_and_a_finer_source_makes_no_count() -> None:
    """Null where the step is unknown, and where more values were found than the step holds."""
    row = _report(_series_frame("subdaily", [_utc(2020, 1, 1, 6), _utc(2020, 1, 1, 12)]), (None, None))
    assert (row["expected"], row["gaps"]) == (None, None)
    half_hours = [_utc(2020, 1, 1) + dt.timedelta(minutes=30 * n) for n in range(10)]
    row = _report(_series_frame("hourly", half_hours), (None, None))
    assert (row["searched"], row["expected"], row["gaps"]) == (10, None, None)


def test_max_rows_cuts_the_answer_last_and_never_what_is_counted() -> None:
    """The rows are the first of the answer's order over all stations; matched, searched and expected stay whole."""
    request = DwdObservationRequest(parameters=[TMIN, TMAX], start="2018-01-01", end="2020-12-31")
    whole = request.all().values().all(sort="value", first=1)
    capped = request.all().values().all(sort="value", first=1, max_rows=2)
    assert whole.search is not None
    assert capped.search is not None
    assert _got(capped.df) == _got(whole.df)[:2]
    assert capped.search.series.get_column("matched").to_list() == whole.search.series.get_column("matched").to_list()
    assert capped.search.series.get_column("searched").to_list() == whole.search.series.get_column("searched").to_list()
    assert capped.search.series.get_column("returned").sum() == 2
    report = capped.search.to_dict()
    totals = report["totals"]
    assert isinstance(totals, dict)
    assert totals["returned"] == 2
    assert totals["matched"] == whole.df.height
    assert report["options"]["max_rows"] == 2  # ty: ignore[invalid-argument-type, not-subscriptable]


def test_max_rows_holds_no_more_than_the_answer_while_the_stations_are_read() -> None:
    """A station is cut to it as it is read (the cap cannot need more), and what matched at the rest is counted."""
    request = DwdObservationRequest(parameters=[TMIN], start="2018-01-01", end="2020-12-31")
    stations = request.all()
    results = list(stations.values().query(filter="value>=-100", max_rows=3))
    assert [r.df.height for r in results] == [3, 3, 3]
    assert all(r.search is not None for r in results)
    assert [int(r.search.series.get_column("matched").sum()) for r in results if r.search] == [
        len(oracle(station, "temperature_air_min_2m")) for station in STATIONS
    ]


def test_selected_rows_of_a_result_cut_like_the_reader_and_say_so(caplog: pytest.LogCaptureFixture) -> None:
    """The method of the result and the reader give the same rows, the same counts and the same warning."""
    request = DwdObservationRequest(parameters=[TMIN], start="2018-01-01", end="2020-12-31")
    whole = request.all().values().all()
    with caplog.at_level("INFO"):
        got = whole.selected_rows(sort="-value", max_rows=4)
    assert _got(got.df) == _got(request.all().values().all(sort="-value", max_rows=4).df)
    assert got.search is not None
    assert got.search.series.get_column("returned").sum() == 4
    assert got.search.series.get_column("matched").sum() == whole.df.height
    assert any("matched rows are returned" in message and "rows-capped" in message for message in _warnings(caplog))


def _warnings(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Give the messages of the log records that carry a response warning, each with its code in front."""
    return [f"{r.response_warning} {r.getMessage()}" for r in caplog.records if hasattr(r, "response_warning")]


def test_max_rows_in_the_wide_shape_counts_the_rows_of_the_wide_frame() -> None:
    """A wide row is one timestamp: the rows of the answer are the rows it has, which `counts.rows` says."""
    request = DwdObservationRequest(parameters=[TMIN], start="2018-01-01", end="2020-12-31", options={"shape": "wide"})
    got = request.all().values().all(filter="month=2", max_rows=5)
    assert got.df.height == 5
    assert got.search is not None
    assert got.search.series.get_column("returned").sum() == 5
    assert got.search.series.get_column("matched").sum() > 5


def test_the_walk_holds_no_more_than_max_rows_of_the_rows_it_reads(monkeypatch: pytest.MonkeyPatch) -> None:
    """Over a choice that stays in a station the frames that are joined have `max_rows` rows in all, not the read."""
    seen: list[int] = []
    finish = RowSelection.finish

    def watching(self: RowSelection, frames: Any, schema: Any = None) -> pl.DataFrame:  # noqa: ANN401
        seen.append(sum(frame.height for frame in frames))
        return finish(self, frames, schema)

    monkeypatch.setattr(RowSelection, "finish", watching)
    request = DwdObservationRequest(parameters=[TMIN], start="2018-01-01", end="2020-12-31")
    got = request.all().values().all(filter="value>=-100", max_rows=5)
    assert seen == [5]
    assert got.df.height == 5
    assert got.search is not None
    assert got.search.series.get_column("matched").sum() == sum(
        len(oracle(station, "temperature_air_min_2m")) for station in STATIONS
    )


def test_a_series_with_a_step_coarser_than_its_resolution_has_no_gaps_to_count() -> None:
    """A maximum of the last 12 hours has a value every 12 hours in an hourly dataset: 11 of 12 hours are no gap."""
    stamps = [_utc(2026, 11, 20) + dt.timedelta(hours=12 * n) for n in range(20)]
    row = _report(_series_frame("hourly", stamps), (None, None))
    assert (row["searched"], row["expected"], row["gaps"]) == (20, None, None)
    # with a window too, and the usual step is the median: a series that merely misses some hours keeps its counts
    row = _report(_series_frame("hourly", stamps), (_utc(2026, 11, 20), _utc(2026, 11, 30)))
    assert (row["expected"], row["gaps"]) == (None, None)
    hours = [s for s in (_utc(2026, 11, 20) + dt.timedelta(hours=n) for n in range(48)) if s.hour not in (3, 4)]
    row = _report(_series_frame("hourly", hours), (None, None))
    assert (row["searched"], row["expected"], row["gaps"]) == (44, 48, 4)
    # calendar resolutions are measured against their own step: a month is no coarser than a month
    months = [_utc(2020, m, 1) for m in (1, 2, 3, 5, 6)]
    assert _report(_series_frame("monthly", months), (None, None))["gaps"] == 1


def test_a_forecast_has_no_expected_values_and_no_gaps() -> None:
    """Counted over the horizon of a run it would invent gaps: both are null for a forecast network."""
    stamps = [_utc(2026, 11, 25) + dt.timedelta(hours=n) for n in range(24) if n not in (5, 6)]
    row = searched_of(_series_frame("hourly", stamps), (None, None), NOW, forecast=True).row(0, named=True)
    assert (row["searched"], row["expected"], row["gaps"]) == (22, None, None)


def test_values_found_outside_the_window_widen_what_is_covered_never_narrow_it() -> None:
    """A reading before the window's start or after its end is a value that was searched: counted, never lost."""
    inside = _series_frame("daily", _days(dt.date(2020, 1, 10), dt.date(2020, 1, 20)))
    # values from the 10th on, a window that starts on the 15th: what the request covers begins at the first value
    row = _report(inside, (_utc(2020, 1, 15), _utc(2020, 1, 31)))
    assert (row["searched"], row["expected"]) == (11, 22)
    # values to the 20th, a window that ends on the 12th: what is covered runs to the last value
    row = _report(inside, (_utc(2020, 1, 1), _utc(2020, 1, 12)))
    assert (row["searched"], row["expected"]) == (11, 20)


def test_station_names_come_from_the_stations_and_a_missing_one_is_null() -> None:
    """The name of a station is in each series, null where the provider has none."""
    frame = pl.concat(
        [
            _series_frame("daily", _days(dt.date(2020, 1, 1), dt.date(2020, 1, 3))).with_columns(station_id=pl.lit(i))
            for i in ("1", "2")
        ]
    )
    rows = searched_of(frame, (None, None), NOW, names={"1": "Alpha"}).select("station_id", "name").rows()
    assert rows == [("1", "Alpha"), ("2", None)]


def test_a_wide_frame_is_counted_per_parameter_column() -> None:
    """The report of a wide result counts the values of each parameter column, not zero."""
    wide = pl.DataFrame(
        {
            "station_id": ["1"] * 4,
            "resolution": ["daily"] * 4,
            "dataset": ["x"] * 4,
            "timestamp": _days(dt.date(2020, 1, 1), dt.date(2020, 1, 4)),
            "a": [1.0, None, 3.0, 4.0],
            "a_quality_flags": ["1"] * 4,
            "b": [None, None, 3.0, 4.0],
            "b_quality_flags": ["1"] * 4,
        },
        schema_overrides={"timestamp": pl.Datetime("us", "UTC")},
    )
    rows = searched_of(wide, (None, None), NOW).sort("parameter").select("parameter", "searched", "gaps").rows()
    assert rows == [("a", 3, 1), ("b", 2, 0)]


def test_selected_rows_counts_what_the_result_holds_wide_or_cut() -> None:
    """A wide result reports its values; a result already cut to a few rows reports those, not the read it came from."""
    request = DwdObservationRequest(parameters=[TMIN], start="2018-01-01", end="2020-12-31", options={"shape": "wide"})
    wide = request.all().values().all()
    report = wide.selected_rows(filter="month=2").search
    assert report is not None
    assert report.series.get_column("searched").sum() == sum(
        len(oracle(station, "temperature_air_min_2m")) for station in STATIONS
    )
    long_request = DwdObservationRequest(parameters=[TMIN], start="2018-01-01", end="2020-12-31")
    cut = long_request.all().values().all().selected_rows(sort="value", first=1, max_rows=7)
    again = cut.selected_rows(sort="-value")
    assert again.search is not None
    assert again.search.series.get_column("searched").sum() == 7
    assert again.search.matched_total == 7


def test_returned_rows_are_counted_for_the_series_they_belong_to() -> None:
    """Counts of a frame whose stations are in another order than the report's land on the series they belong to."""
    series = searched_of(_series_frame("daily", _days(dt.date(2020, 1, 1), dt.date(2020, 1, 4))))
    two = pl.concat([series, series.with_columns(station_id=pl.lit("2"))])
    report = Searched(series=two, selection=parse_row_selection(max_rows=3), window=(None, None))
    answer = pl.concat(
        [
            _series_frame("daily", _days(dt.date(2020, 1, 1), dt.date(2020, 1, 3))).with_columns(
                station_id=pl.lit("2")
            ),
            _series_frame("daily", _days(dt.date(2020, 1, 1), dt.date(2020, 1, 1))),
        ]
    )
    counted = report.with_matched(answer).series
    assert counted.select("station_id", "matched", "returned").rows() == [("1", 1, 1), ("2", 3, 3)]
    assert report.with_returned(answer.head(2)).series.select("station_id", "returned").rows() == [("1", 0), ("2", 2)]


def test_a_report_lists_at_most_its_cap_and_counts_the_rest() -> None:
    """The first 100 series are listed, `series_omitted` counts the others, and the totals are of all."""
    frame = pl.concat(
        [
            _series_frame("daily", _days(dt.date(2020, 1, 1), dt.date(2020, 1, 2))).with_columns(
                station_id=pl.lit(f"{n:03d}")
            )
            for n in range(130)
        ]
    )
    report = Searched(
        series=searched_of(frame, (None, None), NOW),
        selection=parse_row_selection(sort="value", first=1),
        window=(None, None),
    ).with_matched(frame)
    listed = report.to_dict()
    assert len(listed["series"]) == 100  # ty: ignore[invalid-argument-type]
    assert listed["series_omitted"] == 30
    assert listed["totals"]["series"] == 130  # ty: ignore[invalid-argument-type]
    assert listed["totals"]["searched"] == 260  # ty: ignore[invalid-argument-type]
    few = replace(report, listed=20).to_dict()
    assert (len(few["series"]), few["series_omitted"]) == (20, 110)  # ty: ignore[invalid-argument-type]
    assert few["totals"]["series"] == 130  # ty: ignore[invalid-argument-type]


def test_a_group_of_missing_values_alone_keeps_no_row() -> None:
    """A row without a value has no place in the order: a group of nothing else keeps nothing, however many `first`."""
    frame = _series_frame("daily", _days(dt.date(2020, 1, 1), dt.date(2020, 1, 3))).with_columns(
        value=pl.lit(None, pl.Float64)
    )
    for first in (1, 3):
        selection = parse_row_selection(sort="value", first=first)
        assert selection is not None
        assert selection.apply(frame).is_empty()
    mixed = pl.concat([frame.head(2), _series_frame("daily", [_utc(2020, 1, 9)])])
    selection = parse_row_selection(sort="value", first=3)
    assert selection is not None
    assert selection.apply(mixed).get_column("value").to_list() == [1.0]


def test_filtered_results_keep_no_report_of_rows_they_do_not_hold() -> None:
    """`filtered_by_date` and `filtered_by_sql` leave the rows that a report counted: the new result has none."""
    request = DwdObservationRequest(parameters=[TMIN], start="2018-01-01", end="2020-12-31")
    got = request.all().values().all(sort="value", first=1)
    assert got.search is not None
    assert got.filtered_by_date("2019").search is None
    assert got.filtered_by_date("2019").df.height <= got.df.height


def test_the_groups_that_span_stations_are_chosen_again_when_what_is_held_doubles(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The work is of the order of the rows read: the held rows are chosen again at doubling heights."""
    serve(monkeypatch, 40)
    seen: list[int] = []
    finish = RowSelection.finish

    def watching(self: RowSelection, frames: Any, schema: Any = None) -> pl.DataFrame:  # noqa: ANN401
        seen.append(sum(frame.height for frame in frames))
        return finish(self, frames, schema)

    monkeypatch.setattr(RowSelection, "finish", watching)
    monkeypatch.setattr(TimeseriesValues, "_COMPACT_CELLS", 300)
    request = DwdObservationRequest(parameters=[TMIN], start="2018-01-01", end="2020-12-31")
    got = request.all().values().all(sort="-value", first=1, by="year")
    # one choice at the end and a few on the way (the held rows reach 300 and then twice what was left), not forty
    assert 2 <= len(seen) <= 10, seen
    assert max(seen[:-1]) < 2000
    assert got.search is not None
    expected = request.all().values().all().selected_rows(sort="-value", first=1, by="year")
    assert _got(got.df) == _got(expected.df)


def test_many_stations_cut_to_max_rows_never_hold_more_than_a_few_times_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """Each station keeps up to `max_rows` rows; the held rows are cut to the first of the answer when they double."""
    serve(monkeypatch, 60)
    seen: list[int] = []
    finish = RowSelection.finish

    def watching(self: RowSelection, frames: Any, schema: Any = None) -> pl.DataFrame:  # noqa: ANN401
        seen.append(sum(frame.height for frame in frames))
        return finish(self, frames, schema)

    monkeypatch.setattr(RowSelection, "finish", watching)
    request = DwdObservationRequest(parameters=[TMIN], start="2018-01-01", end="2020-12-31")
    got = request.all().values().all(sort="-value", first=1000, by="station_id,month", max_rows=100)
    assert max(seen) <= 4 * 100, seen
    expected = (
        request.all().values().all().selected_rows(sort="-value", first=1000, by="station_id,month", max_rows=100)
    )
    assert _got(got.df) == _got(expected.df)
