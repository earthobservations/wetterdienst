# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What the review of #4444 asked and the maintainer decided, each held by a case of its own (GH-4412).

A group the window cuts is incomplete (Q1), an incomplete group may compete and says `complete` (Q3), `per=none` ranks
over the stations (Q2), the aggregates are `earliest` and `latest` (Q4); and the edges of sub-hourly periods, the
refusals before a download, the ties of floating-point sums, the names in `filter`, and the cases that mutants of the
engine passed (the aggregates a parameter allows, `totals`, the clock, the limits).
"""

from __future__ import annotations

import contextlib
import dataclasses
import datetime as dt
import pickle
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest

from tests.model.statistics_stub import DAILY, at, daily, serve_custom
from tests.ui.row_options_stub import GUST, TMIN, serve
from wetterdienst import Options
from wetterdienst.metadata.parameter_table import PARAMETERS
from wetterdienst.model import group_statistics
from wetterdienst.model.group_statistics import (
    GroupsOverLimitError,
    SeriesMeta,
    StatisticsRun,
    parse_statistics,
    refuse_for,
)
from wetterdienst.model.option_grammar import RowSelectionError, RowSelectionRefusedError
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

if TYPE_CHECKING:
    from wetterdienst.model.group_statistics import StatisticsResult

NOW = dt.datetime(2100, 1, 1, tzinfo=dt.UTC)
PARAMETER = "temperature_air_mean_2m"


def _request(start: dt.datetime | None, end: dt.datetime | None, parameter: str = DAILY, **kwargs: Any) -> Any:  # noqa: ANN401
    return DwdObservationRequest(parameters=[parameter], start=start, end=end, **kwargs).all()


def _serve(monkeypatch: pytest.MonkeyPatch, readings: Any, now: dt.datetime = NOW, **kwargs: Any) -> None:  # noqa: ANN401
    monkeypatch.setattr(group_statistics, "_now", lambda: now)
    serve_custom(monkeypatch, {"00001": readings}, parameter=kwargs.pop("parameter", PARAMETER), **kwargs)
    begin_response()


def _rows(result: StatisticsResult) -> list[dict[str, Any]]:
    return result.series_dicts()[0]["groups"]


def _codes() -> dict[str, str]:
    return {w["code"]: w["message"] for w in recorded_warnings()}


# ----------------------------------------------------------------------------------------------------------------
# Q1: a group the window cuts is incomplete, like the running year
# ----------------------------------------------------------------------------------------------------------------


def _winters(monkeypatch: pytest.MonkeyPatch) -> Any:  # noqa: ANN401
    """Make the winters 1941 to 1970 of a daily series: -5 degrees in 1963, and 1 in every other."""
    readings: dict[dt.datetime, float | None] = {}
    day = at(1940, 12, 1)
    while day < at(1970, 3, 1):
        season = day.year + (1 if day.month >= 12 else 0)
        readings[day] = -5.0 if season == 1963 and day.month in (12, 1, 2) else 1.0
        day += dt.timedelta(days=1)
    _serve(monkeypatch, readings)
    return _request(at(1941, 1, 1), dt.datetime(1969, 12, 31, 23, tzinfo=dt.UTC))


def test_a_winter_the_window_cuts_is_incomplete_and_not_the_coldest(monkeypatch: pytest.MonkeyPatch) -> None:
    """`timestamp=1941/1969` ends in December 1969: the winter 1970 is 31 of 90 days, no mean; 1963 is coldest."""
    request = _winters(monkeypatch)
    options = {"by": "year", "filter": "month=12|1|2", "year_start": 12, "sort": "mean", "first": 3}
    result = request.values().statistics("mean,count", **options)
    years = {
        row["year"]: row
        for row in _rows(request.values().statistics("mean,count", by="year", filter="month=12|1|2", year_start=12))
    }
    assert years[1970]["mean"] is None
    assert (years[1970]["searched"], years[1970]["expected"], years[1970]["complete"]) == (31, 90, False)
    assert (years[1942]["searched"], years[1942]["expected"]) == (90, 90)
    assert (years[1941]["searched"], years[1941]["complete"]) == (59, False)
    assert [row["year"] for row in _rows(result)] == [1963, 1942, 1943]
    assert "incomplete-groups" in _codes()
    usable = result.series_dicts()[0]["over_groups"]["mean"]
    assert (usable["groups"], usable["usable"]) == (30, 28)


def test_the_first_and_the_last_season_of_a_window_are_incomplete_and_not_usable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`1961/1990` with `year_start=7`: 31 seasons, of which the first and the last are cut and 29 are usable."""
    _serve(monkeypatch, daily(dt.date(1961, 1, 1), [1.0] * 10957))
    request = _request(at(1961, 1, 1), dt.datetime(1990, 12, 31, 23, tzinfo=dt.UTC))
    result = request.values().statistics("mean", by="year", year_start=7)
    rows = _rows(result)
    assert [row["year"] for row in rows if not row["complete"]] == [1961, 1991]
    assert (rows[0]["searched"], rows[0]["expected"]) == (181, 365)
    over = result.series_dicts()[0]["over_groups"]["mean"]
    assert (over["groups"], over["usable"], over["mean"]) == (31, 29, 1.0)


# ----------------------------------------------------------------------------------------------------------------
# Q3 and H2: incomplete groups are warned of, say `complete`, and `having` can name it
# ----------------------------------------------------------------------------------------------------------------


def _gappy(monkeypatch: pytest.MonkeyPatch) -> Any:  # noqa: ANN401
    """2019 whole, 2020 with 300 of its days: one complete year, one that is not."""
    _serve(monkeypatch, daily(dt.date(2019, 1, 1), [1.0] * 365 + [2.0] * 300))
    return _request(at(2019, 1, 1), dt.datetime(2020, 12, 31, 23, tzinfo=dt.UTC))


def test_an_incomplete_group_is_warned_of_whatever_is_asked(monkeypatch: pytest.MonkeyPatch) -> None:
    """With `count` alone, which a gap does not null: the warning is there, and says what `count` is then."""
    request = _gappy(monkeypatch)
    result = request.values().statistics("count", by="year")
    assert [row["complete"] for row in _rows(result)] == [True, False]
    message = _codes()["incomplete-groups"]
    assert message.startswith("1 groups have fewer values than expected, at 00001 Station 00001 (1)")
    assert "`complete` is false" in message
    assert "`max_missing` is 0" in message


def test_max_missing_is_taken_with_any_aggregate(monkeypatch: pytest.MonkeyPatch) -> None:
    """`max_missing=66` makes 2020 complete (299 of 366 would need 67): it is a flag of the group, not of `mean`."""
    request = _gappy(monkeypatch)
    result = request.values().statistics("count", by="year", max_missing=66)
    assert [row["complete"] for row in _rows(result)] == [True, True]
    assert "incomplete-groups" not in _codes()


def test_having_complete_keeps_the_complete_groups_and_complete_0_the_others(monkeypatch: pytest.MonkeyPatch) -> None:
    """`having=complete` is `complete=1`; both forms are echoed as read; `sort=-complete` puts the complete first."""
    request = _gappy(monkeypatch)
    complete = request.values().statistics("count", by="year", having="complete")
    assert [row["year"] for row in _rows(complete)] == [2019]
    assert complete.plan.echo()["having"] == "complete=1"
    other = request.values().statistics("count", by="year", having="complete=0")
    assert [row["year"] for row in _rows(other)] == [2020]
    both = request.values().statistics("count", by="year", having="searched>0,complete!=0")
    assert [row["year"] for row in _rows(both)] == [2019]
    ordered = request.values().statistics("count", by="year", sort="complete,year")
    assert [row["complete"] for row in _rows(ordered)] == [False, True]
    assert complete.totals()["groups_matched"] == 1
    assert complete.totals()["groups_incomplete"] == 1


def test_an_incomplete_group_may_compete_and_the_warning_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    """A count "so far" ranks like any: the incomplete 2020 is the first of `sort=-count` or not, by its count."""
    _serve(monkeypatch, daily(dt.date(2019, 1, 1), [1.0] * 100 + [None] * 265 + [2.0] * 366))
    request = _request(at(2019, 1, 1), dt.datetime(2020, 12, 31, 23, tzinfo=dt.UTC))
    result = request.values().statistics("count", by="year", sort="-count", first=1)
    (row,) = _rows(result)
    assert (row["year"], row["count"], row["complete"]) == (2020, 366, True)
    result = request.values().statistics("count", by="year", sort="count", first=1)
    (row,) = _rows(result)
    assert (row["year"], row["count"], row["complete"]) == (2019, 100, False)
    assert "incomplete-groups" in _codes()


# ----------------------------------------------------------------------------------------------------------------
# Q4: the names of the aggregates
# ----------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(("word", "write"), [("first", "earliest"), ("last", "latest")])
def test_first_and_last_are_not_aggregates_and_say_what_to_write(word: str, write: str) -> None:
    """`first` is an option of the request (as in `values`): an aggregate of that name is refused with the new one."""
    with pytest.raises(RowSelectionError, match=rf"`{word}` is not an aggregate of this option.*`{write}`"):
        parse_statistics(word)
    assert parse_statistics(f"{write},count").aggregate == (write, "count")


def test_the_dates_of_the_report_are_first_timestamp_and_last_timestamp(monkeypatch: pytest.MonkeyPatch) -> None:
    """The series says `first_timestamp` and `last_timestamp`; the groups `earliest`, `earliest_at`, `latest`."""
    _serve(monkeypatch, daily(dt.date(2020, 1, 1), [float(n) for n in range(1, 11)]))
    request = _request(at(2020, 1, 1), at(2020, 1, 10, 23))
    series = request.values().statistics("earliest,latest", by="month").series_dicts()[0]
    assert (series["first_timestamp"], series["last_timestamp"]) == ("2020-01-01", "2020-01-10")
    assert "first" not in series
    (row,) = series["groups"]
    assert (row["earliest"], row["earliest_at"], row["latest"], row["latest_at"]) == (
        1.0,
        "2020-01-01",
        10.0,
        "2020-01-10",
    )


# ----------------------------------------------------------------------------------------------------------------
# H4: the first and the last hour of a sub-hourly period
# ----------------------------------------------------------------------------------------------------------------


def _ten_minutes(monkeypatch: pytest.MonkeyPatch, start: dt.datetime, steps: int) -> Any:  # noqa: ANN401
    readings: dict[dt.datetime, float | None] = {
        start + dt.timedelta(minutes=10 * n): float(n % 7) for n in range(steps)
    }
    _serve(monkeypatch, readings, resolution="10_minutes", dataset="temperature_air", parameter="temperature_air_2m")
    return DwdObservationRequest(parameters=["10_minutes/temperature_air/temperature_air_2m"]).all()


def test_the_first_and_the_last_hour_of_a_record_count_the_steps_they_hold(monkeypatch: pytest.MonkeyPatch) -> None:
    """A record from 00:20 to 03:30 is 20 steps: the group over it says 20 of 20, as the series does."""
    request = _ten_minutes(monkeypatch, at(2020, 3, 1, 0) + dt.timedelta(minutes=20), 20)
    result = request.values().statistics("count,mean")
    series = result.series_dicts()[0]
    assert (series["searched"], series["expected"], series["gaps"]) == (20, 20, 0)
    (row,) = series["groups"]
    assert (row["searched"], row["expected"], row["complete"]) == (20, 20, True)
    assert row["mean"] is not None
    by_hour = _rows(request.values().statistics("count", by="hour"))
    assert [(r["hour"], r["searched"], r["expected"]) for r in by_hour] == [(0, 4, 4), (1, 6, 6), (2, 6, 6), (3, 4, 4)]


def test_a_single_hour_and_a_hole_inside_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """Within one hour 00:10 to 00:40 is 4 steps; a missing one is one gap."""
    readings = {at(2020, 3, 1) + dt.timedelta(minutes=m): 1.0 for m in (10, 20, 40)}
    _serve(monkeypatch, readings, resolution="10_minutes", dataset="temperature_air", parameter="temperature_air_2m")
    request = DwdObservationRequest(parameters=["10_minutes/temperature_air/temperature_air_2m"]).all()
    (row,) = _rows(request.values().statistics("count", by="hour"))
    assert (row["searched"], row["expected"], row["complete"]) == (3, 4, False)


# ----------------------------------------------------------------------------------------------------------------
# M1, M2, M3, M5: what is refused, before a download, and what cannot be asked
# ----------------------------------------------------------------------------------------------------------------


def test_a_value_condition_over_parameters_of_two_units_is_refused_before_a_station_is_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`value<0` over a temperature and a gust is a number of degrees and of metres per second."""
    serve(monkeypatch)
    request = DwdObservationRequest(parameters=[TMIN, GUST], start=at(2018, 1, 1), end=at(2018, 12, 31)).all()
    with pytest.raises(RowSelectionRefusedError, match="A `filter` on `value` has one number for every parameter"):
        request.values().statistics("count", filter="value<0")
    assert request.values().statistics("count", filter="month=1").series


def test_what_no_series_can_do_is_refused_before_any_station_is_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """`by=hour` of daily values is refused whether or not a station has rows, and before the first is read."""
    serve(monkeypatch)
    from wetterdienst.provider.dwd.observation.api import DwdObservationValues  # noqa: PLC0415

    reads: list[str] = []
    original = DwdObservationValues._collect_station_parameter_or_dataset  # noqa: SLF001

    def reading(self: Any, station_id: str, parameter_or_dataset: Any) -> Any:  # noqa: ANN401
        reads.append(station_id)
        return original(self, station_id, parameter_or_dataset)

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", reading)
    request = DwdObservationRequest(parameters=[TMIN], start=at(2018, 1, 1), end=at(2018, 12, 31)).all()
    with pytest.raises(RowSelectionRefusedError, match="`hour` is finer than the daily values"):
        request.values().statistics("count", by="hour")
    assert reads == []


def test_a_window_that_leaves_the_years_of_the_calendar_is_no_500(monkeypatch: pytest.MonkeyPatch) -> None:
    """`timestamp=0001/2020` with `year_start=12` and an end in year 9999 come to a refusal or an answer."""
    _serve(monkeypatch, daily(dt.date(2020, 1, 1), [1.0] * 5))
    request = _request(dt.datetime(1, 1, 1, tzinfo=dt.UTC), at(2020, 1, 5))
    with contextlib.suppress(RowSelectionRefusedError):
        request.values().statistics("count", by="year", year_start=12)
    far = _request(at(2020, 1, 1), dt.datetime(9999, 12, 31, tzinfo=dt.UTC))
    with contextlib.suppress(RowSelectionRefusedError):
        far.values().statistics("count", by="year", year_start=12)


def test_a_window_with_more_cells_than_a_group_is_counted_over_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """560 years of hourly values by year, month, day and hour are 4.9 million cells: a 400, not a gigabyte."""
    readings = {at(2020, 1, 1) + dt.timedelta(hours=h): 1.0 for h in range(48)}
    _serve(monkeypatch, readings, resolution="hourly", dataset="air_temperature", parameter="temperature_air_2m")
    request = DwdObservationRequest(
        parameters=["hourly/air_temperature/temperature_air_2m"], start=at(1500, 1, 1), end=at(2060, 12, 31)
    ).all()
    with pytest.raises(RowSelectionRefusedError, match="more than the 1,500,000 the statistics count"):
        request.values().statistics("count", by="year,month,day,hour")


# ----------------------------------------------------------------------------------------------------------------
# M6: sums that differ in the last bit tie
# ----------------------------------------------------------------------------------------------------------------


def test_sums_and_means_that_differ_in_the_last_bit_of_a_float_tie(monkeypatch: pytest.MonkeyPatch) -> None:
    """0.1 + 0.2 + 0.3 and 0.3 + 0.2 + 0.1 are 0.6000000000000001 and 0.6: one year each, and the two tie."""
    readings = daily(dt.date(2019, 1, 1), [0.1, 0.2, 0.3]) | daily(dt.date(2020, 1, 1), [0.3, 0.2, 0.1])
    _serve(monkeypatch, readings)
    request = _request(at(2019, 1, 1), at(2020, 1, 3, 23))
    result = request.values().statistics("sum", by="year", max_missing=400, sort="-sum", first=1)
    assert result.tied == 1
    json_sum = _rows(result)[0]["sum"]
    assert result.df.get_column("sum")[0] == json_sum == 0.6
    assert result.series[0].frame.get_column("sum")[0] == 0.6
    # min, max and the dated values are readings: not rounded
    reading = request.values().statistics("min,max", by="year", max_missing=400)
    assert [r["min"] for r in _rows(reading)] == [0.1, 0.1]
    assert [r["max"] for r in _rows(reading)] == [0.3, 0.3]


# ----------------------------------------------------------------------------------------------------------------
# M7: the name of a parameter in `filter`
# ----------------------------------------------------------------------------------------------------------------


def test_the_name_of_the_one_parameter_of_the_request_is_value(monkeypatch: pytest.MonkeyPatch) -> None:
    """`temperature_air_mean_2m<0` of a request for that parameter alone is `value<0`; the echo says `value<0`."""
    _serve(monkeypatch, daily(dt.date(2020, 1, 1), [-1.0, 1.0, -2.0]))
    request = _request(at(2020, 1, 1), at(2020, 1, 3, 23))
    named = request.values().statistics("count", filter="Temperature_Air_Mean_2m<0,month=1")
    assert _rows(named)[0]["count"] == 2
    assert named.plan.echo()["filter"] == "value<0,month=1"
    plain = request.values().statistics("count", filter="value<0,month=1")
    assert _rows(plain) == _rows(named)


@pytest.mark.parametrize("name", ["wind_gust_max", "temperature_air_max_2m", "precipitation_amount"])
def test_any_other_name_is_refused_with_what_to_write(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    """A name of the request's other parameter, or of any parameter, is no column: `value`, with one parameter."""
    serve(monkeypatch)
    request = DwdObservationRequest(parameters=[TMIN, GUST], start=at(2018, 1, 1), end=at(2018, 12, 31)).all()
    with pytest.raises(
        RowSelectionError, match=rf"`{name}` is no column of this option.*unless the request has that one"
    ):
        request.values().statistics("count", filter=f"{name}<0")
    assert name in PARAMETERS


def test_the_reserved_words_are_no_names() -> None:
    """The words of the aggregates, `complete` and `rank` are refused as columns of `filter`, not taken for names."""
    for word in ("count", "mean", "earliest", "latest", "complete", "rank"):
        with pytest.raises(RowSelectionError, match="is not a column of this option"):
            parse_statistics("count", filter=f"{word}<1")


# ----------------------------------------------------------------------------------------------------------------
# the other small things of the review
# ----------------------------------------------------------------------------------------------------------------


def test_the_options_left_empty_are_none_given() -> None:
    """`year_start=` and `max_missing=` empty, as an empty query parameter is."""
    plan = parse_statistics("count", year_start="", max_missing="", first="", max_rows="")
    assert (plan.year_start, plan.max_missing, plan.first, plan.max_rows) == (1, 0, None, None)


def test_the_result_with_no_series_has_the_columns_of_the_groups(monkeypatch: pytest.MonkeyPatch) -> None:
    """`df` of an answer with no station is empty with the columns and types a group has."""
    _serve(monkeypatch, {})
    request = _request(at(2020, 1, 1), at(2020, 1, 5))
    result = request.values().statistics("count,max", by="year")
    assert result.df.is_empty()
    assert list(result.df.columns) == [
        "station_id",
        "resolution",
        "dataset",
        "parameter",
        "year",
        "count",
        "max",
        "max_at",
        "searched",
        "expected",
        "complete",
    ]
    assert result.df.schema["year"] == pl.Int32
    assert result.df.schema["max_at"] == pl.Datetime("us", "UTC")
    assert result.to_csv().splitlines()[0].endswith("year,count,max,max_at,searched,expected,complete")


# the aggregates a parameter allows: the cases mutants of the engine passed
_CODE = next(
    k for k, p in PARAMETERS.items() if p.aggregation == "code" and p.unit_type not in ("angle", "significant_weather")
)


@pytest.mark.parametrize(
    ("name", "resolution", "aggregate", "allowed"),
    [
        (_CODE, "hourly", "mean", False),
        (_CODE, "hourly", "max", False),
        (_CODE, "hourly", "earliest", True),
        ("sun_zenith_angle", "hourly", "mean", True),
        ("wind_direction", "hourly", "max", False),
        ("precipitation_amount_last_1h", "hourly", "sum", True),
        ("precipitation_amount_last_1h", "10_minutes", "sum", False),
        ("precipitation_amount_last_3h", "hourly", "sum", False),
        ("precipitation_amount_last_24h", "daily", "sum", True),
        ("evapotranspiration_last_24h", "hourly", "sum", False),
        ("evaporation_amount_multiday", "daily", "sum", False),
        ("precipitation_amount_since_last_routine_report", "hourly", "sum", False),
        ("temperature_air_2m", "10_minutes", "sum", False),
        ("temperature_air_2m", "6_hours", "sum", False),
        ("temperature_air_2m", "hourly", "sum", True),
        ("temperature_air_mean_2m", "daily", "sum", True),
    ],
)
def test_the_aggregates_a_parameter_allows_by_name_and_resolution(
    name: str, resolution: str, aggregate: str, *, allowed: bool
) -> None:
    """A code, a direction and a window of its own overlapping its neighbours have no mean, extreme or sum."""
    meta = SeriesMeta.of_canonical(name, "u")
    plan = parse_statistics(aggregate)
    if allowed:
        refuse_for(plan, meta, resolution)
    else:
        with pytest.raises(RowSelectionRefusedError, match="Invalid `aggregate`"):
            refuse_for(plan, meta, resolution)


def test_a_tie_is_warned_of_and_no_tie_is_not(monkeypatch: pytest.MonkeyPatch) -> None:
    """The counts 1, 2 and 3 are all different: `first=1` shows one and says nothing of ties."""
    readings = (
        daily(dt.date(2019, 1, 1), [1.0])
        | daily(dt.date(2020, 1, 1), [1.0] * 2)
        | daily(dt.date(2021, 1, 1), [1.0] * 3)
    )
    _serve(monkeypatch, readings)
    request = _request(at(2019, 1, 1), at(2021, 1, 3, 23))
    result = request.values().statistics("count", by="year", sort="-count", first=1, max_missing=400)
    assert [r["year"] for r in _rows(result)] == [2021]
    assert result.tied == 0
    assert "ties-not-shown" not in _codes()


def test_the_totals_are_unknown_where_one_series_is_unknown_and_count_the_stations_with_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`expected` and `gaps` of the totals are null with a series that has none; a station with no value is read."""
    readings: dict[dt.datetime, float | None] = {at(2020, 1, day): 1.0 for day in range(1, 32)}
    readings[at(2020, 1, 5, 12)] = 9.0
    monkeypatch.setattr(group_statistics, "_now", lambda: NOW)
    serve_custom(
        monkeypatch,
        {"00001": readings, "00002": {}, "00003": daily(dt.date(2020, 1, 1), [1.0] * 31)},
        parameter=PARAMETER,
    )
    begin_response()
    request = DwdObservationRequest(parameters=[DAILY], start=at(2020, 1, 1), end=at(2020, 1, 31, 23)).all()
    totals = request.values().statistics("count", by="month").totals()
    assert (totals["stations_read"], totals["stations_with_values"], totals["series"]) == (3, 2, 2)
    assert (totals["expected"], totals["gaps"]) == (None, None)
    assert totals["searched"] == 32 + 31


def test_the_walk_yields_no_rows_and_a_station_with_nothing_but_nulls_is_a_series_with_no_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The walk yields no rows (the groups are the run's); with the nulls kept a series has no value."""
    nulls: dict[dt.datetime, float | None] = {at(2020, 1, day): None for day in range(1, 6)}
    monkeypatch.setattr(group_statistics, "_now", lambda: NOW)
    serve_custom(monkeypatch, {"00001": nulls}, parameter=PARAMETER)
    begin_response()
    request = DwdObservationRequest(
        parameters=[DAILY], start=at(2020, 1, 1), end=at(2020, 1, 5, 23), options=Options(drop_nulls=False)
    ).all()
    reader = request.values()
    run = StatisticsRun.for_stations(request, parse_statistics("count", by="month"), unit_symbol=reader._unit_symbol)  # noqa: SLF001
    heights = [result.df.height for result in reader._walk(None, run)]  # noqa: SLF001
    assert heights == [0]
    result = run.finish(request, stations_read=1)
    (series,) = result.series
    assert (series.searched, series.groups, series.not_listed) == (0, 1, 1)
    assert series.frame.is_empty()
    assert result.totals()["groups_not_listed"] == 1
    assert result.totals()["stations_with_values"] == 0


def test_a_group_begins_when_its_first_cell_is_the_moment_of_now(monkeypatch: pytest.MonkeyPatch) -> None:
    """August begins at 2020-08-01T00:00: at exactly that moment it is a group, a moment before it is not."""
    readings = daily(dt.date(2020, 1, 1), [1.0] * 213)  # to 2020-07-31
    for now, months in (
        (dt.datetime(2020, 8, 1, tzinfo=dt.UTC), 8),
        (dt.datetime(2020, 7, 31, 23, 59, 59, tzinfo=dt.UTC), 7),
    ):
        _serve(monkeypatch, readings, now=now)
        request = _request(at(2020, 1, 1), at(2020, 12, 31, 23))
        groups = request.values().statistics("count", by="year,month").totals()["groups"]
        assert groups == months


def test_a_station_of_a_forecast_network_has_no_expected(monkeypatch: pytest.MonkeyPatch) -> None:
    """The kind of the network decides: a forecast's groups are complete by default and the warning says so."""
    _serve(monkeypatch, daily(dt.date(2020, 1, 1), [1.0] * 5))
    request = _request(at(2020, 1, 1), at(2020, 1, 5, 23))
    monkeypatch.setattr(request.request.metadata, "kind", "forecast")
    result = request.values().statistics("count", by="month")
    series = result.series_dicts()[0]
    assert (series["expected"], series["groups"][0]["expected"]) == (None, None)
    assert "completeness-unknown" in _codes()


def test_the_dates_of_sub_daily_values_are_written_to_the_minute(monkeypatch: pytest.MonkeyPatch) -> None:
    """`max_at` of hourly values is `2020-03-01T05:00Z`, of daily ones `2020-03-01`."""
    readings = {at(2020, 3, 1, h): float(h) for h in range(24)}
    _serve(monkeypatch, readings, resolution="hourly", dataset="air_temperature", parameter="temperature_air_2m")
    request = DwdObservationRequest(
        parameters=["hourly/air_temperature/temperature_air_2m"], start=at(2020, 3, 1), end=at(2020, 3, 1, 23)
    ).all()
    (row,) = _rows(request.values().statistics("min,max,earliest", by="month"))
    assert (row["max"], row["max_at"], row["min_at"], row["earliest_at"]) == (
        23.0,
        "2020-03-01T23:00Z",
        "2020-03-01T00:00Z",
        "2020-03-01T00:00Z",
    )


def test_the_groups_held_may_equal_the_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    """A limit of 3 groups is met by 3 groups (not exceeded) and refused by 4."""
    _serve(monkeypatch, daily(dt.date(2020, 1, 1), [1.0] * 91))
    request = _request(at(2020, 1, 1), at(2020, 3, 31, 23))
    reader = request.values()
    reader._held_rows_limit = 3  # noqa: SLF001
    assert reader.statistics("count", by="month").totals()["groups"] == 3
    over = request.values()
    over._held_rows_limit = 3  # noqa: SLF001
    with pytest.raises(GroupsOverLimitError, match="91 groups so far, more than the 3"):
        over.statistics("count", by="month,day")
    reader = _request(at(2020, 1, 1), at(2020, 1, 31, 23)).values()
    reader._held_rows_limit = 1  # noqa: SLF001
    assert reader.statistics("count", by="month").totals()["groups"] == 1


def test_compaction_drops_candidates_and_keeps_every_tie(monkeypatch: pytest.MonkeyPatch) -> None:
    """With compaction on every station the answer is that of none, with ties at the N-th, and it did run."""
    serve(monkeypatch, count=9)
    request = DwdObservationRequest(parameters=[TMIN], start=at(2018, 1, 1), end=at(2020, 12, 31, 23)).all()
    options = {"by": "year", "sort": "-count", "first": 4, "per": "none", "max_missing": 400}
    plain = request.values().statistics("count", **options)
    calls = []
    original = StatisticsRun._compact  # noqa: SLF001
    monkeypatch.setattr(StatisticsRun, "_compact", lambda self: (calls.append(1), original(self))[1])
    monkeypatch.setattr(group_statistics, "COMPACT_GROUPS", 1)
    compacted = request.values().statistics("count", **options)
    assert calls
    assert compacted.series_dicts() == plain.series_dicts()
    assert compacted.tied == plain.tied


def test_the_groups_limit_error_is_a_request_error_that_pickles() -> None:
    """A `RequestError` (a `ValueError`) with the groups and the limit as attributes, and what to do in its message."""
    error = GroupsOverLimitError(72, 50)
    assert isinstance(error, ValueError)
    assert (error.groups, error.maximum) == (72, 50)
    assert "72 groups so far, more than the 50 that may be held" in str(error)
    again = pickle.loads(pickle.dumps(error))  # noqa: S301
    assert (again.groups, again.maximum, str(again)) == (72, 50, str(error))


def test_the_result_is_what_the_library_promises() -> None:
    """The fields and the public methods of a `StatisticsResult`, as the results of `values` are pinned."""
    from wetterdienst.model.group_statistics import StatisticsResult  # noqa: PLC0415

    assert [f.name for f in dataclasses.fields(StatisticsResult)] == [
        "stations",
        "plan",
        "series",
        "left_out",
        "window",
        "stations_read",
        "tied",
        "capped",
        "data_updated_at",
        "warnings_made",
    ]
    fields = {f.name for f in dataclasses.fields(StatisticsResult)}
    methods = sorted(n for n in dir(StatisticsResult) if not n.startswith("_") and n not in fields)
    assert methods == [
        "df",
        "groups_ndjson",
        "head",
        "rows_of",
        "search",
        "series_dicts",
        "to_csv",
        "to_dict",
        "to_json",
        "to_ndjson",
        "totals",
        "warn",
    ]


def test_a_monthly_value_dated_off_midnight_is_its_months(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monthly values dated 06:00 of the 1st: a year has 12 of 12, not 11 (the first month ceiled away)."""
    readings = {at(2020, month, 1, 6): float(month) for month in range(1, 13)}
    _serve(monkeypatch, readings, resolution="monthly", dataset="climate_summary", parameter=PARAMETER)
    request = DwdObservationRequest(parameters=["monthly/climate_summary/temperature_air_mean_2m"]).all()
    (row,) = _rows(request.values().statistics("count,mean", by="year"))
    assert (row["searched"], row["expected"], row["complete"]) == (12, 12, True)
