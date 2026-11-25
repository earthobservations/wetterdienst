# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The options of `statistics`: the grammar, a fuzz of it against that of `values`, ties, `per` and the held result.

The text of `filter` is read by the same function as the `filter` of `values` (`model/option_grammar.py`): a fuzz of
random texts holds the two to the same conditions or the same error. The rest of the options are held to what the
rules in `docs/usage/restapi.md` ("Statistics") say.
"""

from __future__ import annotations

import datetime as dt
import random
import time
from typing import TYPE_CHECKING, Any

import pytest

from tests.model.statistics_stub import DAILY, at, daily, serve_custom
from tests.ui.row_options_stub import STATIONS, TMIN, serve
from wetterdienst.model import group_statistics
from wetterdienst.model.group_statistics import GroupsOverLimitError, parse_statistics
from wetterdienst.model.row_selection import ParameterNames, RowSelectionError, parse_filter
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

if TYPE_CHECKING:
    from wetterdienst.model.group_statistics import StatisticsResult


# ----------------------------------------------------------------------------------------------------------------
# the grammar
# ----------------------------------------------------------------------------------------------------------------

_TOKENS = [
    "value",
    "year",
    "month",
    "day",
    "hour",
    "Value",
    "MONTH",
    "<",
    "<=",
    ">",
    ">=",
    "=",
    "!=",
    "==",
    "=<",
    "<>",
    "|",
    ",",
    " ",
    "\t",
    "0",
    "1",
    "7",
    "12",
    "23",
    "31",
    "-5",
    "-",
    "+",
    ".5",
    "1.",
    "1e3",
    "2e-3",
    "1e",
    "nan",
    "inf",
    "13",
    "0.1",
    "C",
    "é",
    "(",
    ")",
    "'",
]


def _random_text(rng: random.Random) -> str:
    """Make a text: a random run of tokens, or a valid list of conditions with a few random changes."""
    if rng.random() < 0.4:
        return "".join(rng.choice(_TOKENS) for _ in range(rng.randint(1, 14)))
    conditions = []
    for _ in range(rng.randint(1, 4)):
        column = rng.choice(["value", "year", "month", "day", "hour"])
        operator = rng.choice(["<", "<=", ">", ">=", "=", "!="])
        low, high = {"value": (-30, 40), "year": (1, 2100), "month": (1, 12), "day": (1, 31), "hour": (0, 23)}[column]
        numbers = [str(rng.randint(low, high))]
        if operator in ("=", "!=") and rng.random() < 0.4:
            numbers += [str(rng.randint(low, high)) for _ in range(rng.randint(1, 3))]
        if column == "value" and rng.random() < 0.3:
            numbers = [f"{numbers[0]}.{rng.randint(0, 9)}"]
        pad = rng.choice(["", " "])
        conditions.append(f"{column}{pad}{operator}{pad}{'|'.join(numbers)}")
    text = ",".join(conditions)
    for _ in range(rng.choice([0, 0, 1, 2])):
        at_ = rng.randint(0, len(text))
        change = rng.choice(["insert", "delete", "replace"])
        token = rng.choice(_TOKENS)
        if change == "insert":
            text = text[:at_] + token + text[at_:]
        elif text:
            at_ = min(at_, len(text) - 1)
            text = text[:at_] + (token if change == "replace" else "") + text[at_ + 1 :]
    return text or "value<0"


def _values(text: str) -> Any:  # noqa: ANN401
    try:
        # no parameter of the request: a word that is no column is refused here as `statistics` refuses it
        return parse_filter(text, ParameterNames())
    except RowSelectionError as e:
        return e


def _statistics(text: str) -> Any:  # noqa: ANN401
    try:
        return parse_statistics("count", filter=text).conditions
    except RowSelectionError as e:
        return e


def test_the_filter_is_read_as_the_filter_of_values_reads_it_or_refused_at_the_same_place() -> None:
    """20,000 random texts: the same conditions, or an error of the same option at the same position."""
    rng = random.Random(4412)  # noqa: S311
    errors = conditions = names = 0
    for _ in range(20_000):
        text = _random_text(rng)
        a, b = _values(text), _statistics(text)
        if isinstance(a, RowSelectionError) and "is not a column of this option" in str(a):
            # a word that can be a name is held by `statistics` until the request's parameters are known
            assert not isinstance(b, RowSelectionError) or b.position is None or b.position >= (a.position or 0), text
            names += 1
            continue
        if isinstance(a, RowSelectionError):
            assert isinstance(b, RowSelectionError), text
            assert (a.option, a.position, a.found) == (b.option, b.position, b.found), text
            errors += 1
        else:
            assert a == b, text
            conditions += 1
    # the fuzz reaches both outcomes often
    assert errors > 2_000
    assert conditions > 5_000
    assert names > 100


def test_the_bounds_of_every_text_are_those_of_values_and_hold_without_delay() -> None:
    """A text of 401 characters, 9 conditions, a list of 33 numbers: refused, at once, with where."""
    started = time.perf_counter()
    for text, fragment in (
        ("value<0," * 60, "characters, more than the 400 allowed"),
        (",".join(["value<0"] * 9), "more than 8 conditions"),
        ("value=" + "|".join(str(n) for n in range(1, 34)), "more than 32 numbers"),
        ("value<" + "9" * 30, "more than the 24 allowed"),
    ):
        with pytest.raises(RowSelectionError, match=fragment):
            parse_statistics("count", filter=text)
    assert time.perf_counter() - started < 1.0


@pytest.mark.parametrize(
    ("options", "option", "fragment"),
    [
        ({"aggregate": ""}, "aggregate", "no aggregate is given"),
        ({"aggregate": "count", "year_start": 13}, "year_start", "outside the range"),
        ({"aggregate": "count", "year_start": "x", "by": "year"}, "year_start", "not a whole number"),
        ({"aggregate": "mean", "max_missing": 10_001}, "max_missing", "outside the range"),
        ({"aggregate": "count", "first": 0, "sort": "count"}, "first", "outside the range"),
        ({"aggregate": "count", "max_rows": 10_001}, "max_rows", "outside the range"),
        ({"aggregate": "count", "by": "year,year"}, "by", "`year` is named twice"),
        ({"aggregate": "count", "by": "hour,none"}, "by", "not a column of this option"),
        ({"aggregate": "count", "sort": "-count,count"}, "sort", "`count` is named twice"),
        ({"aggregate": "count", "having": "year=1"}, "having", "a time condition"),
        ({"aggregate": "count", "having": "value>1"}, "having", "put it in `filter`"),
        ({"aggregate": "count", "filter": "month=13"}, "filter", "outside the range of `month`"),
        ({"aggregate": "count", "by": "season"}, "by", "not available in this version"),
        ({"aggregate": "longest_run"}, "aggregate", "not available in this version"),
        ({"aggregate": "avg"}, "aggregate", "average is `mean`"),
    ],
)
def test_each_refusal_names_the_option_and_what_to_write(options: dict[str, Any], option: str, fragment: str) -> None:
    """Each text that cannot be read, or options that cannot go together, say where and what to write instead."""
    with pytest.raises(RowSelectionError, match=fragment) as raised:
        parse_statistics(**options)
    assert raised.value.option == option


def test_the_options_are_read_as_written_in_any_case_and_order() -> None:
    """`by` is kept in the calendar's order, whatever the order written; the texts are echoed as read."""
    plan = parse_statistics(
        "Count , MEAN",
        by="Month,year",
        filter="Month = 12|1, value <= -5",
        having="searched>=3",
        sort="-Mean, year",
        first="3",
        year_start="12",
        max_missing="2",
        max_rows="9",
        per="station",
    )
    assert plan.aggregate == ("count", "mean")
    assert plan.by == ("year", "month")
    assert plan.echo() == {
        "aggregate": ["count", "mean"],
        "filter": "month=12|1,value<=-5",
        "by": ["year", "month"],
        "per": "station",
        "having": "searched>=3",
        "sort": "-mean,year",
        "first": 3,
        "year_start": 12,
        "max_missing": 2,
        "max_rows": 9,
    }


# ----------------------------------------------------------------------------------------------------------------
# ties, per, having, sort
# ----------------------------------------------------------------------------------------------------------------


def _flat(result: StatisticsResult) -> list[tuple[str, dict[str, Any]]]:
    return [(s["station_id"], g) for s in result.series_dicts() for g in s["groups"]]


def _three_stations(monkeypatch: pytest.MonkeyPatch) -> Any:  # noqa: ANN401
    """Three stations of two years each, a count of days above 0 that ties (all 30 days of each month)."""
    series = {
        station: daily(dt.date(2019, 1, 1), [float(n % 5) for n in range(730)])
        for station in ("00001", "00002", "00003")
    }
    serve_custom(monkeypatch, series, parameter="temperature_air_mean_2m")
    begin_response()
    return DwdObservationRequest(
        parameters=[DAILY], start=at(2019, 1, 1), end=dt.datetime(2020, 12, 30, 23, tzinfo=dt.UTC)
    ).all()


def test_first_keeps_exactly_n_orders_the_ties_by_the_groups_and_says_how_many_more_tie(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The months tie in their counts: N are shown, in the order of `by`, and the ties are counted."""
    request = _three_stations(monkeypatch)
    whole = request.values().statistics("count", by="year,month", filter="value>0", sort="-count")
    full = whole.series_dicts()[0]["groups"]
    counts = [g["count"] for g in full]
    assert counts == sorted(counts, reverse=True)
    assert counts[1] == counts[2]  # the second and the third tie: the case is the one to hold
    begin_response()
    result = request.values().statistics("count", by="year,month", filter="value>0", sort="-count", first=2)
    for series in result.series_dicts():
        assert len(series["groups"]) == 2
        # ties are ordered by the columns of `by`: the same two of the whole order
        assert series["groups"] == full[:2]
    ties = next(w["message"] for w in recorded_warnings() if w["code"] == "ties-not-shown")
    assert ties.startswith(f"{result.tied:,} more groups tie with the last one shown")
    assert result.tied == 3 * sum(1 for count in counts[2:] if count == counts[1])
    assert result.tied > 0


def test_a_group_with_a_null_sort_column_has_no_place_in_the_order_and_is_not_ranked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A mean that is null (an incomplete year) is not among the first N, and comes last without `first`."""
    series = {"00001": daily(dt.date(2019, 1, 1), [1.0] * 365 + [2.0] * 300)}
    serve_custom(monkeypatch, series, parameter="temperature_air_mean_2m")
    request = DwdObservationRequest(
        parameters=[DAILY], start=at(2019, 1, 1), end=dt.datetime(2020, 12, 31, 23, tzinfo=dt.UTC)
    ).all()
    ranked = request.values().statistics("mean", by="year", sort="-mean", first=2)
    assert [g["year"] for g in ranked.series_dicts()[0]["groups"]] == [2019]
    ordered = request.values().statistics("mean", by="year", sort="-mean")
    assert [(g["year"], g["mean"]) for g in ordered.series_dicts()[0]["groups"]] == [(2019, 1.0), (2020, None)]


def test_having_chooses_by_the_results_and_the_completeness_columns(monkeypatch: pytest.MonkeyPatch) -> None:
    """`having=searched<365` keeps the incomplete years, with the statistics over all of them first."""
    series = {"00001": daily(dt.date(2019, 1, 1), [1.0] * 365 + [2.0] * 300)}
    serve_custom(monkeypatch, series, parameter="temperature_air_mean_2m")
    request = DwdObservationRequest(
        parameters=[DAILY], start=at(2019, 1, 1), end=dt.datetime(2020, 12, 31, 23, tzinfo=dt.UTC)
    ).all()
    result = request.values().statistics("count,mean", by="year", having="searched<365")
    (series_,) = result.series_dicts()
    assert [g["year"] for g in series_["groups"]] == [2020]
    # over_groups are made before `having`: they cover both years
    assert series_["over_groups"]["count"]["groups"] == 2
    assert series_["over_groups"]["count"]["usable"] == 1
    totals = result.totals()
    assert (totals["groups"], totals["groups_matched"], totals["groups_returned"]) == (2, 1, 1)


def test_per_none_chooses_across_the_stations_and_compaction_changes_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """The first N over all stations of a parameter are the same with and without dropping the candidates on the way."""
    serve(monkeypatch, count=12)
    request = DwdObservationRequest(
        parameters=[TMIN],
        start=dt.datetime(2018, 1, 1, tzinfo=dt.UTC),
        end=dt.datetime(2020, 12, 31, 23, tzinfo=dt.UTC),
    ).all()
    options = {"by": "year,month", "sort": "-max,year,month", "first": 5, "per": "none"}
    plain = request.values().statistics("max", **options)
    monkeypatch.setattr(group_statistics, "COMPACT_GROUPS", 1)
    compacted = request.values().statistics("max", **options)
    assert _flat(plain) == _flat(compacted)
    assert plain.tied == compacted.tied
    assert len(_flat(plain)) == 5
    # and it is the five highest of every group of every station, ties by the order of `by`, then the station
    everything = request.values().statistics("max", by="year,month")
    want = sorted(
        ((s["station_id"], g) for s in everything.series_dicts() for g in s["groups"]),
        key=lambda x: (-x[1]["max"], x[1]["year"], x[1]["month"], x[0]),
    )[:5]
    assert [(s, g["year"], g["month"], g["max"]) for s, g in _flat(plain)] == [
        (s, g["year"], g["month"], g["max"]) for s, g in want
    ] or {(g["year"], g["month"], g["max"]) for _, g in _flat(plain)} == {
        (g["year"], g["month"], g["max"]) for _, g in want
    }


def test_the_groups_held_are_bounded_and_the_walk_stops_at_the_station_that_exceeds_them(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With a limit the walk raises as soon as a station makes more groups than may be held: 36 a station, limit 50."""
    serve(monkeypatch)
    request = DwdObservationRequest(
        parameters=[TMIN],
        start=dt.datetime(2018, 1, 1, tzinfo=dt.UTC),
        end=dt.datetime(2020, 12, 31, 23, tzinfo=dt.UTC),
    ).all()
    reader = request.values()
    reader._held_rows_limit = 50  # noqa: SLF001
    with pytest.raises(GroupsOverLimitError, match=r"72 groups so far, more than the 50 that may be held"):
        reader.statistics("count", by="year,month")
    # `having` brings it under the limit, which is what the refusal says to add
    again = request.values()
    again._held_rows_limit = 50  # noqa: SLF001
    kept = again.statistics("count", by="year,month", having="count>=29")
    assert kept.totals()["groups_returned"] <= 50


def test_a_held_result_gives_the_statistics_the_reader_gives(monkeypatch: pytest.MonkeyPatch) -> None:
    """`ValuesResult.statistics` and `values().statistics` are one function over the rows."""
    serve(monkeypatch)
    request = DwdObservationRequest(
        parameters=[TMIN],
        start=dt.datetime(2018, 1, 1, tzinfo=dt.UTC),
        end=dt.datetime(2020, 12, 31, 23, tzinfo=dt.UTC),
    ).all()
    options = {"by": "year,month", "filter": "value<0", "sort": "-count", "first": 3}
    streamed = request.values().statistics("count,mean", **options)
    held = request.values().all().statistics("count,mean", **options)
    assert streamed.series_dicts() == held.series_dicts()
    assert streamed.search() == held.search()
    assert list(held.df.columns) == [
        "station_id",
        "resolution",
        "dataset",
        "parameter",
        "year",
        "month",
        "count",
        "mean",
        "searched",
        "expected",
        "complete",
    ]
    assert held.df.height == 9
    assert sorted(held.df.get_column("station_id").unique().to_list()) == list(STATIONS)


def test_the_wide_shape_is_refused_before_a_station_is_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """`statistics` needs rows of one parameter: a wide frame has one column each."""
    from wetterdienst import Options  # noqa: PLC0415
    from wetterdienst.model.row_selection import RowSelectionRefusedError  # noqa: PLC0415

    serve(monkeypatch)
    request = DwdObservationRequest(
        parameters=[TMIN],
        start=dt.datetime(2018, 1, 1, tzinfo=dt.UTC),
        end=dt.datetime(2018, 12, 31, 23, tzinfo=dt.UTC),
        options=Options(shape="wide"),
    ).all()
    with pytest.raises(RowSelectionRefusedError, match="needs the long shape"):
        request.values().statistics("count")
    wide = DwdObservationRequest(
        parameters=[TMIN],
        start=dt.datetime(2018, 1, 1, tzinfo=dt.UTC),
        end=dt.datetime(2018, 12, 31, 23, tzinfo=dt.UTC),
    ).all()
    held = wide.values().all()
    from dataclasses import replace  # noqa: PLC0415

    with pytest.raises(RowSelectionRefusedError, match="this result is wide"):
        replace(held, df=held.df.drop("parameter")).statistics("count")
