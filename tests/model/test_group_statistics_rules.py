# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The twelve rules of the completeness of `statistics`, each against a case worked out by hand (GH-4412).

A station is served from memory with a few readings a person can add up, and the answer is held to the numbers of the
hand: no oracle, no second implementation. The rules are those of `docs/usage/restapi.md` ("Statistics").
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any

import pytest

from tests.model.statistics_stub import DAILY, at, daily, serve_custom
from wetterdienst.metadata.parameter_table import PARAMETERS
from wetterdienst.model import group_statistics
from wetterdienst.model.group_statistics import SeriesMeta, StatisticsPlan, parse_statistics, refuse_for
from wetterdienst.model.row_selection import RowSelectionRefusedError
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

if TYPE_CHECKING:
    from collections.abc import Mapping

    from wetterdienst.model.group_statistics import StatisticsResult

NOW = dt.datetime(2100, 1, 1, tzinfo=dt.UTC)
PARAMETER = "temperature_air_mean_2m"


def _stats(
    monkeypatch: pytest.MonkeyPatch,
    readings: Mapping[dt.datetime, float | None],
    aggregate: str,
    *,
    window: tuple[dt.datetime | None, dt.datetime | None] = (None, None),
    now: dt.datetime = NOW,
    **options: Any,  # noqa: ANN401
) -> StatisticsResult:
    monkeypatch.setattr(group_statistics, "_now", lambda: now)
    serve_custom(monkeypatch, {"00001": readings}, parameter=PARAMETER)
    begin_response()
    request = DwdObservationRequest(parameters=[DAILY], start=window[0], end=window[1]).all()
    return request.values().statistics(aggregate, **options)


def _rows(result: StatisticsResult) -> list[dict[str, Any]]:
    assert len(result.series) == 1
    return result.series_dicts()[0]["groups"]


def _jan_2020() -> tuple[dt.datetime, dt.datetime]:
    return at(2020, 1, 1), at(2020, 1, 31, 23)


def _january_with_gaps() -> dict[dt.datetime, float | None]:
    """January 2020, the value of a day being its number: day 5 and 6 are null rows, day 7 is no row at all."""
    readings: dict[dt.datetime, float | None] = {at(2020, 1, day): float(day) for day in range(1, 32) if day != 7}
    readings[at(2020, 1, 5)] = None
    readings[at(2020, 1, 6)] = None
    return readings


def test_rule_1_a_null_and_a_missing_day_are_both_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A null the source wrote and a day with no row are missing alike: 28 of 31 days are present."""
    result = _stats(monkeypatch, _january_with_gaps(), "count,mean", window=_jan_2020(), by="month")
    (row,) = _rows(result)
    assert (row["searched"], row["expected"], row["count"], row["mean"]) == (28, 31, 28, None)


def test_rule_10_max_missing_lets_a_gap_have_its_mean(monkeypatch: pytest.MonkeyPatch) -> None:
    """With `max_missing=3` the same January has its mean over the 28 days; with 2 it has none."""
    allowed = _stats(monkeypatch, _january_with_gaps(), "mean,sum", window=_jan_2020(), by="month", max_missing=3)
    (row,) = _rows(allowed)
    assert row["sum"] == sum(range(1, 32)) - 5 - 6 - 7
    assert row["mean"] == pytest.approx((sum(range(1, 32)) - 18) / 28, abs=1e-4)
    refused = _stats(monkeypatch, _january_with_gaps(), "mean,sum", window=_jan_2020(), by="month", max_missing=2)
    (row,) = _rows(refused)
    assert (row["mean"], row["sum"]) == (None, None)


def test_rule_6_an_incomplete_group_keeps_what_the_values_there_are_say(monkeypatch: pytest.MonkeyPatch) -> None:
    """Count, min, max, earliest and latest are of the values there are; the mean and the sum are null."""
    result = _stats(monkeypatch, _january_with_gaps(), "count,min,max,earliest,latest", window=_jan_2020(), by="month")
    (row,) = _rows(result)
    assert (row["count"], row["min"], row["min_at"], row["max"], row["max_at"]) == (
        28,
        1.0,
        "2020-01-01",
        31.0,
        "2020-01-31",
    )
    assert (row["earliest"], row["earliest_at"], row["latest"], row["latest_at"]) == (
        1.0,
        "2020-01-01",
        31.0,
        "2020-01-31",
    )
    assert result.totals()["groups_incomplete"] == 1
    sums = _stats(monkeypatch, _january_with_gaps(), "mean,sum", window=_jan_2020(), by="month")
    assert (_rows(sums)[0]["mean"], _rows(sums)[0]["sum"]) == (None, None)


def test_rule_2_the_cells_of_a_group_are_the_days_that_pass_the_time_conditions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With `month=7` a year has 31 cells, whatever else the series holds: June is not looked at."""
    readings = {at(2020, 6, day): 1.0 for day in range(1, 31)} | {at(2020, 7, day): 2.0 for day in range(1, 32)}
    result = _stats(
        monkeypatch,
        readings,
        "count,mean",
        window=(at(2020, 1, 1), at(2020, 12, 31, 23)),
        by="year",
        filter="month=7",
    )
    (row,) = _rows(result)
    assert (row["year"], row["searched"], row["expected"], row["count"], row["mean"]) == (2020, 31, 31, 31, 2.0)


def test_rule_3_a_station_that_began_in_march_has_an_incomplete_first_year(monkeypatch: pytest.MonkeyPatch) -> None:
    """The first year has 365 cells of which 306 are present: no mean. The second is whole."""
    readings = daily(dt.date(2019, 3, 1), [10.0] * (306 + 366))
    result = _stats(monkeypatch, readings, "count,mean", by="year")
    first, second = _rows(result)
    assert (first["year"], first["searched"], first["expected"], first["count"], first["mean"]) == (
        2019,
        306,
        365,
        306,
        None,
    )
    assert (second["year"], second["searched"], second["expected"], second["mean"]) == (2020, 366, 366, 10.0)
    usable = result.series_dicts()[0]["over_groups"]["mean"]
    assert (usable["groups"], usable["usable"]) == (2, 1)


def test_rule_3_without_a_year_a_group_runs_from_the_first_value_to_the_last(monkeypatch: pytest.MonkeyPatch) -> None:
    """`by=month` counts the cells of March from March 2019 (the first value) and of January from January 2020."""
    readings = daily(dt.date(2019, 3, 1), [10.0] * (306 + 366))
    result = _stats(monkeypatch, readings, "count", by="month")
    by_month = {row["month"]: row for row in _rows(result)}
    assert by_month[1]["expected"] == 31  # January 2020 only: January 2019 lies before the first value
    assert by_month[3]["expected"] == 62  # March of two years


def test_rule_3_a_year_that_is_not_over_is_incomplete_and_a_period_not_begun_is_no_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """At the end of June 2020 the year has 366 cells and 182 values; by month July has none, August is no group."""
    readings = daily(dt.date(2020, 1, 1), [3.0] * 182)  # to 2020-06-30
    now = dt.datetime(2020, 7, 1, 12, tzinfo=dt.UTC)
    by_year = _stats(monkeypatch, readings, "count,mean", now=now, by="year")
    (row,) = _rows(by_year)
    assert (row["searched"], row["expected"], row["mean"], row["count"]) == (182, 366, None, 182)
    by_month = _stats(
        monkeypatch, readings, "count", now=now, window=(at(2020, 1, 1), at(2020, 12, 31, 23)), by="year,month"
    )
    months = [row["month"] for row in _rows(by_month)]
    # July began at midnight and is a group with no value, after the last one: counted, not a row
    assert months == [1, 2, 3, 4, 5, 6]
    totals = by_month.totals()
    assert (totals["groups"], totals["groups_not_listed"]) == (7, 1)


def test_rule_4_more_values_than_cells_make_expected_unknown_and_the_group_complete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A source finer than its resolution (a second reading on January 5) has 32 values for 31 days: no `expected`."""
    readings: dict[dt.datetime, float | None] = {at(2020, 1, day): 1.0 for day in range(1, 32)}
    readings[at(2020, 1, 5, 12)] = 9.0
    result = _stats(monkeypatch, readings, "count,mean", window=_jan_2020(), by="month")
    (row,) = _rows(result)
    assert (row["searched"], row["expected"], row["count"], row["mean"]) == (32, None, 32, 1.25)
    assert result.series_dicts()[0]["expected"] is None
    unknown = next(w["message"] for w in recorded_warnings() if w["code"] == "completeness-unknown")
    assert unknown.startswith("How many values a group should have is not known for 1 series, at 00001 Station 00001")


def test_rule_5_the_gap_that_is_allowed_is_exactly_max_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A year at the end of December 28 lacks 3 days that are not there yet: `max_missing=3` gives it a mean."""
    readings = daily(dt.date(2020, 1, 1), [4.0] * 363)  # to 2020-12-28
    now = dt.datetime(2020, 12, 28, 12, tzinfo=dt.UTC)
    for allowed, mean in ((3, 4.0), (2, None)):
        result = _stats(monkeypatch, readings, "mean", now=now, by="year", max_missing=allowed)
        (row,) = _rows(result)
        assert (row["searched"], row["expected"], row["mean"]) == (363, 366, mean)


def test_rule_7_values_and_no_match_is_zero_and_no_value_is_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """January has values and none below 0: count 0, sum 0, mean null. February has no value at all: all null."""
    readings = {at(2020, 1, day): 2.0 for day in range(1, 32)} | {at(2020, 3, day): 5.0 for day in range(1, 32)}
    result = _stats(
        monkeypatch,
        readings,
        "count,sum,mean,min,earliest",
        window=(at(2020, 1, 1), at(2020, 3, 31, 23)),
        by="month",
        filter="value<0",
    )
    january, february, march = _rows(result)
    assert (january["count"], january["sum"], january["mean"], january["min"], january["earliest"]) == (
        0,
        0.0,
        None,
        None,
        None,
    )
    assert (january["searched"], january["expected"]) == (31, 31)
    assert (february["count"], february["sum"], february["mean"], february["searched"], february["expected"]) == (
        None,
        None,
        None,
        0,
        29,
    )
    assert march["count"] == 0


def test_rule_7_the_zero_groups_belong_to_the_mean_of_the_counts(monkeypatch: pytest.MonkeyPatch) -> None:
    """Of three years only one has a tropical night: the mean of the yearly counts is 1/3, not 1."""
    readings: dict[dt.datetime, float | None] = {}
    for year, tropical in ((2018, 0), (2019, 0), (2020, 3)):
        for day in range(365 + (year % 4 == 0)):
            stamp = at(year, 1, 1) + dt.timedelta(days=day)
            readings[stamp] = 21.0 if day < tropical else 12.0
    result = _stats(
        monkeypatch,
        readings,
        "count",
        window=(at(2018, 1, 1), at(2020, 12, 31, 23)),
        by="year",
        filter="value>=20",
    )
    assert [row["count"] for row in _rows(result)] == [0, 0, 3]
    assert result.series_dicts()[0]["over_groups"]["count"]["mean"] == 1.0
    assert result.series_dicts()[0]["over_groups"]["count"]["usable"] == 3


def test_rule_8_groups_before_the_first_and_after_the_last_value_are_counted_not_rows(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A window of 2019 to 2021 over a record of 2020 has three groups of which one is a row; a hole is a row."""
    readings = daily(dt.date(2020, 1, 1), [1.0] * 366)
    result = _stats(monkeypatch, readings, "count,mean", window=(at(2019, 1, 1), at(2021, 12, 31, 23)), by="year")
    assert [row["year"] for row in _rows(result)] == [2020]
    totals = result.totals()
    assert (totals["groups"], totals["groups_not_listed"]) == (3, 2)
    assert result.series_dicts()[0]["over_groups"]["mean"]["groups"] == 3
    # a hole inside the record is a row: 2020 has data in January and December only, by month
    holes = daily(dt.date(2020, 1, 1), [1.0] * 31) | daily(dt.date(2020, 12, 1), [1.0] * 31)
    by_month = _stats(monkeypatch, holes, "count", window=(at(2020, 1, 1), at(2020, 12, 31, 23)), by="month")
    rows = _rows(by_month)
    assert [row["month"] for row in rows] == list(range(1, 13))
    assert [row["count"] for row in rows] == [31, *([None] * 10), 31]
    assert by_month.totals()["groups_not_listed"] == 0


def test_rule_8_the_warnings_say_what_was_not_listed_and_what_is_incomplete(monkeypatch: pytest.MonkeyPatch) -> None:
    """`no-values-in-groups` and `incomplete-groups` are told, once, with the sums."""
    readings = daily(dt.date(2020, 1, 1), [1.0] * 100)
    result = _stats(monkeypatch, readings, "mean", window=(at(2019, 1, 1), at(2021, 12, 31, 23)), by="year")
    assert result.totals()["groups_not_listed"] == 2
    codes = {warning["code"]: warning["message"] for warning in recorded_warnings()}
    assert "2 groups lie before the first or after the last value" in codes["no-values-in-groups"]
    assert "1 group has fewer values than expected" in codes["incomplete-groups"]
    assert "`max_missing` is 0" in codes["incomplete-groups"]


def test_rule_11_a_year_is_named_by_the_year_its_season_ends_in(monkeypatch: pytest.MonkeyPatch) -> None:
    """With `year_start=12` December 2023 to February 2024 is 2024, in `by` and in `filter`."""
    readings: dict[dt.datetime, float | None] = {}
    day = at(2022, 11, 1)
    while day < at(2024, 4, 1):
        readings[day] = {12: 5.0, 1: 7.0, 2: 9.0}.get(day.month, 1.0) if day >= at(2023, 12, 1) else 1.0
        day += dt.timedelta(days=1)
    window = (at(2022, 11, 1), at(2024, 3, 31, 23))
    winters = _stats(
        monkeypatch, readings, "mean,count", window=window, by="year", filter="month=12|1|2", year_start=12
    )
    by_year = {row["year"]: row for row in _rows(winters)}
    assert by_year[2024]["expected"] == 31 + 31 + 29
    assert by_year[2024]["mean"] == pytest.approx((31 * 5 + 31 * 7 + 29 * 9) / 91, abs=1e-4)
    assert by_year[2023]["mean"] == 1.0
    # the first and the last season the record covers only in part are incomplete: 2023 begins in November 2022 (whole
    # winter 2022/23 is there), and the season of 2022 has only the December that was not recorded
    assert 2022 not in by_year
    december = _stats(
        monkeypatch, readings, "count", window=window, by="year", filter="year=2024,month=12", year_start=12
    )
    (row,) = _rows(december)
    assert (row["year"], row["count"], row["expected"]) == (2024, 31, 31)


def test_rule_12_hourly_values_have_24_cells_a_day_in_utc(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two days of hourly values: by hour each hour of the day has 2 cells, by day each day has 24."""
    readings = {
        at(2020, 3, day, hour): float(hour) for day in (1, 2) for hour in range(24) if not (day == 2 and hour == 5)
    }
    monkeypatch.setattr(group_statistics, "_now", lambda: NOW)
    serve_custom(
        monkeypatch,
        {"00001": readings},
        resolution="hourly",
        dataset="air_temperature",
        parameter="temperature_air_2m",
    )
    request = DwdObservationRequest(
        parameters=["hourly/air_temperature/temperature_air_2m"], start=at(2020, 3, 1), end=at(2020, 3, 2, 23)
    ).all()
    by_hour = request.values().statistics("count,mean", by="hour")
    rows = _rows(by_hour)
    assert [row["hour"] for row in rows] == list(range(24))
    assert all(row["expected"] == 2 for row in rows)
    assert rows[5]["searched"] == 1
    assert rows[5]["mean"] is None
    assert rows[6]["mean"] == 6.0
    by_day = request.values().statistics("count", by="day")
    assert [(row["day"], row["searched"], row["expected"]) for row in _rows(by_day)] == [(1, 24, 24), (2, 23, 24)]


def test_a_station_of_minutes_costs_hours_of_cells(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ten-minute readings count 6 cells to the hour: a day has 144, and one missing reading is one gap."""
    readings = {at(2020, 3, 1) + dt.timedelta(minutes=10 * step): float(step % 7) for step in range(144) if step != 10}
    monkeypatch.setattr(group_statistics, "_now", lambda: NOW)
    serve_custom(
        monkeypatch,
        {"00001": readings},
        resolution="10_minutes",
        dataset="temperature_air",
        parameter="temperature_air_2m",
    )
    request = DwdObservationRequest(
        parameters=["10_minutes/temperature_air/temperature_air_2m"],
        start=at(2020, 3, 1),
        end=dt.datetime(2020, 3, 1, 23, 59, 59, tzinfo=dt.UTC),
    ).all()
    (row,) = _rows(request.values().statistics("count", by="day"))
    assert (row["searched"], row["expected"]) == (143, 144)


def test_rule_5_a_series_whose_completeness_is_not_known_is_computed_and_told() -> None:
    """Where the report has no `expected` (a forecast), the group is complete by default, and the warning says so."""
    import polars as pl  # noqa: PLC0415

    plan = parse_statistics("mean", by="month")
    frame = pl.DataFrame(
        {"timestamp": [at(2020, 1, day) for day in range(1, 11)], "value": [float(day) for day in range(1, 11)]},
        schema_overrides={"timestamp": pl.Datetime("us", "UTC")},
    )
    meta = SeriesMeta("temperature_air_2m", "°C", "temperature", None)
    series = group_statistics._SeriesIn("A", "hourly", "x", "temperature_air_2m", meta, frame, forecast=True)  # noqa: SLF001
    report = {
        "name": None,
        "searched": 10,
        "expected": None,
        "gaps": None,
        "first": at(2020, 1, 1),
        "last": at(2020, 1, 10),
    }
    stats = group_statistics.reduce_series(plan, series, report, (None, None), NOW)
    (row,) = stats.frame.iter_rows(named=True)
    assert (row["mean"], row["expected"], row["searched"]) == (5.5, None, 10)
    assert stats.unknown_completeness


# ----------------------------------------------------------------------------------------------------------------
# what a parameter allows
# ----------------------------------------------------------------------------------------------------------------


def _meta(name: str, unit: str = "-") -> SeriesMeta:
    return SeriesMeta.of_canonical(name, unit)


def _plan(aggregate: str, **options: Any) -> StatisticsPlan:  # noqa: ANN401
    return parse_statistics(aggregate, **options)


@pytest.mark.parametrize(
    ("parameter", "unit", "aggregate", "resolution", "allowed", "sum_unit"),
    [
        ("precipitation_amount", "mm", "sum", "daily", True, None),
        ("temperature_air_mean_2m", "°C", "sum", "daily", True, "°Cd"),
        ("temperature_air_2m", "°C", "sum", "hourly", True, "°Ch"),
        ("temperature_air_mean_2m", "°C", "sum", "monthly", False, None),
        ("pressure_air_site", "hPa", "sum", "hourly", False, None),
        ("humidity_relative", "%", "sum", "hourly", False, None),
        ("wind_direction", "°", "mean", "hourly", False, None),
        ("wind_direction", "°", "count", "hourly", True, None),
        ("wind_direction", "°", "earliest", "hourly", True, None),
        ("precipitation_amount_last_3h", "mm", "sum", "hourly", False, None),
        ("count_days_frost", "-", "sum", "annual", True, None),
        ("count_days_frost", "-", "mean", "annual", True, None),
        ("temperature_air_mean_2m", "°C", "max", "daily", True, None),
    ],
)
def test_what_a_parameter_allows_comes_from_its_own_metadata(
    parameter: str, unit: str, aggregate: str, resolution: str, *, allowed: bool, sum_unit: str | None
) -> None:
    """Directions and codes have no mean or extreme; a sum is for amounts, counts and, daily or hourly, temperatures."""
    plan = _plan(aggregate)
    if allowed:
        units = refuse_for(plan, _meta(parameter, unit), resolution)
        if aggregate == "sum":
            assert units["sum"] == (sum_unit or unit)
        elif aggregate == "count":
            assert units["count"] is None
    else:
        with pytest.raises(RowSelectionRefusedError, match=r"Invalid `aggregate`.*Allowed here: count"):
            refuse_for(plan, _meta(parameter, unit), resolution)


def test_every_canonical_parameter_is_judged_and_the_judgement_follows_its_own_metadata() -> None:
    """All of them are judged (none raises other than a refusal); count, earliest and latest are allowed for each."""
    refused = {"mean": 0, "sum": 0, "min": 0}
    for name, parameter in PARAMETERS.items():
        meta = SeriesMeta(name, "u", parameter.unit_type, parameter.aggregation)
        for resolution in ("daily", "monthly"):
            for aggregate in ("count", "earliest", "latest", "min", "max", "mean", "sum"):
                try:
                    refuse_for(_plan(aggregate), meta, resolution)
                except RowSelectionRefusedError:
                    assert aggregate not in ("count", "earliest", "latest")
                    refused[aggregate if aggregate in refused else "min"] += 1
    assert refused["sum"] > refused["mean"] > 0


def test_a_column_finer_than_the_resolution_is_refused() -> None:
    """`by=hour` of daily values, `month` of annual ones, `year_start` of annual ones."""
    meta = _meta("temperature_air_mean_2m", "°C")
    with pytest.raises(RowSelectionRefusedError, match="`hour` is finer than the daily values"):
        refuse_for(_plan("mean", by="hour"), meta, "daily")
    with pytest.raises(RowSelectionRefusedError, match=r"Invalid `filter`: `month` is finer than the annual values"):
        refuse_for(_plan("mean", filter="month=7"), meta, "annual")
    with pytest.raises(RowSelectionRefusedError, match="no seasons"):
        refuse_for(_plan("mean", by="year", year_start=7), meta, "annual")
    refuse_for(_plan("mean", by="year,month,day", filter="hour=12"), meta, "hourly")


def test_calendar_resolutions_count_their_cells_by_the_calendar(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monthly values: a year has 12 cells; annual values: one a year in the window, narrowed by `year` conditions."""
    monthly = {
        at(year, month, 1): float(month)
        for year in (2019, 2020)
        for month in range(1, 13)
        if (year, month) != (2019, 6)
    }
    monkeypatch.setattr(group_statistics, "_now", lambda: NOW)
    serve_custom(monkeypatch, {"00001": monthly}, resolution="monthly", dataset="climate_summary", parameter=PARAMETER)
    request = DwdObservationRequest(
        parameters=["monthly/climate_summary/temperature_air_mean_2m"], start=at(2019, 1, 1), end=at(2020, 12, 31, 23)
    ).all()
    first, second = _rows(request.values().statistics("count,mean", by="year"))
    assert (first["year"], first["searched"], first["expected"], first["count"], first["mean"]) == (
        2019,
        11,
        12,
        11,
        None,
    )
    assert (second["year"], second["searched"], second["expected"]) == (2020, 12, 12)
    assert second["mean"] == pytest.approx(6.5)
    summer = _rows(request.values().statistics("count", by="year", filter="month=6|7"))
    assert [(row["searched"], row["expected"]) for row in summer] == [(1, 2), (2, 2)]
    with pytest.raises(RowSelectionRefusedError, match="`day` is finer than the monthly values"):
        request.values().statistics("count", by="day")

    annual = {at(year, 1, 1): float(year - 2000) for year in range(2015, 2021) if year != 2017}
    serve_custom(
        monkeypatch, {"00001": annual}, resolution="annual", dataset="climate_indices", parameter="count_days_frost"
    )
    request = DwdObservationRequest(
        parameters=["annual/climate_indices/count_days_frost"], start=at(2015, 1, 1), end=at(2020, 12, 31, 23)
    ).all()
    (whole,) = _rows(request.values().statistics("count,mean,sum"))
    assert (whole["searched"], whole["expected"], whole["count"], whole["mean"], whole["sum"]) == (5, 6, 5, None, None)
    (allowed,) = _rows(request.values().statistics("mean,sum", max_missing=1))
    assert allowed["sum"] == 15 + 16 + 18 + 19 + 20
    assert allowed["mean"] == pytest.approx((15 + 16 + 18 + 19 + 20) / 5)
    (recent,) = _rows(request.values().statistics("count", filter="year>=2018"))
    assert (recent["searched"], recent["expected"]) == (3, 3)
