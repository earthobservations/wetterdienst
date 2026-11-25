# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The re-check of #4444: what it found wrong and what mutants of the code passed (GH-4412).

Lists in `having`, the groups a window cuts out of a year, the candidates of `per=none` cut before the limit, the words
of `complete`, the months a window starts in, the steps of the clock, the warning that says what is in the answer.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest

from tests.model.statistics_stub import DAILY, at, daily
from tests.model.test_group_statistics_review import PARAMETER, _gappy, _request, _rows, _serve
from tests.ui.row_options_stub import GUST, TMIN, serve
from wetterdienst.metadata.resolution import Resolution, count_readings
from wetterdienst.model.group_statistics import GroupsOverLimitError, parse_statistics
from wetterdienst.model.series_report import searched_of
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.util.response_warnings import recorded_warnings

if TYPE_CHECKING:
    from wetterdienst.model.group_statistics import StatisticsResult

UTC = dt.UTC


def _codes() -> dict[str, str]:
    return {w["code"]: w["message"] for w in recorded_warnings()}


# ----------------------------------------------------------------------------------------------------------------
# R1: a list on a column of integers
# ----------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("having", "years"),
    [
        ("searched=365|90", [2019]),
        ("searched=300|90", [2020]),
        ("searched!=365|90", [2020]),
        ("expected=365|366", [2019, 2020]),
        ("expected=366|1", [2020]),
        ("count=300|365", [2019, 2020]),
        ("count=300|1", [2020]),
        ("count!=300|1", [2019]),
        ("complete=1|2", [2019]),
        ("complete=0|2", [2020]),
        ("complete=0|1", [2019, 2020]),
        ("complete!=1|5", [2020]),
    ],
)
def test_a_list_in_having_is_read_on_every_column_of_whole_numbers(
    monkeypatch: pytest.MonkeyPatch, having: str, years: list[int]
) -> None:
    """`count=90|365` was a 500 on a column of integers: a list meets `count`, `searched`, `expected`, `complete`."""
    request = _gappy(monkeypatch)
    result = request.values().statistics("count", by="year", having=having)
    assert [row["year"] for row in _rows(result)] == years


def test_a_list_in_having_is_read_on_the_mean_too(monkeypatch: pytest.MonkeyPatch) -> None:
    """The mean of 2019 is 1.0: `mean=1|3` keeps it, as a number of any kind does."""
    request = _gappy(monkeypatch)
    result = request.values().statistics("mean", by="year", having="mean=1|3")
    assert [row["year"] for row in _rows(result)] == [2019]


# ----------------------------------------------------------------------------------------------------------------
# R2: the months of a year the window cuts that lie outside it are no groups
# ----------------------------------------------------------------------------------------------------------------


def test_the_months_of_a_year_outside_the_window_are_no_groups(monkeypatch: pytest.MonkeyPatch) -> None:
    """A window of March to June by year and month: four groups, not twelve with eight of them empty."""
    _serve(monkeypatch, daily(dt.date(2010, 1, 1), [1.0] * 365))
    request = _request(at(2010, 3, 1), at(2010, 6, 30, 23))
    result = request.values().statistics("count,mean", by="year,month")
    assert [(r["year"], r["month"], r["searched"], r["expected"]) for r in _rows(result)] == [
        (2010, 3, 31, 31),
        (2010, 4, 30, 30),
        (2010, 5, 31, 31),
        (2010, 6, 30, 30),
    ]
    totals = result.totals()
    assert (totals["groups"], totals["groups_not_listed"], totals["groups_returned"]) == (4, 0, 4)
    assert {row["count"] for row in _rows(result)} == {30, 31}
    assert result.series_dicts()[0]["over_groups"]["count"]["groups"] == 4
    assert "no-values-in-groups" not in _codes()


def test_a_month_of_the_window_with_no_value_is_a_group_and_a_month_outside_it_is_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """March, with no value, is in the window of March to June and is listed as a hole; January is not."""
    readings = daily(dt.date(2010, 4, 10), [1.0] * 30)
    _serve(monkeypatch, readings)
    request = _request(at(2010, 3, 1), at(2010, 6, 30, 23))
    result = request.values().statistics("count", by="year,month")
    months = [r["month"] for r in _rows(result)]
    assert 1 not in months
    assert 2 not in months
    assert months == [4, 5]
    assert result.totals()["groups"] == result.totals()["groups_returned"] + result.totals()["groups_not_listed"]


# ----------------------------------------------------------------------------------------------------------------
# R3: the candidates of `per=none` are cut to N before the limit says they are too many
# ----------------------------------------------------------------------------------------------------------------


def _four_stations(monkeypatch: pytest.MonkeyPatch) -> Any:  # noqa: ANN401
    from tests.model.statistics_stub import serve_custom  # noqa: PLC0415

    readings = {at(2020, 1, 1) + dt.timedelta(days=n): float(n % 7) for n in range(90)}
    monkeypatch.setattr("wetterdienst.model.group_statistics._now", lambda: dt.datetime(2100, 1, 1, tzinfo=UTC))
    serve_custom(monkeypatch, {f"0000{n}": readings for n in range(1, 5)}, parameter=PARAMETER)
    return DwdObservationRequest(parameters=[DAILY], start=at(2020, 1, 1), end=at(2020, 3, 30, 23)).all()


_OPTIONS = {"by": "month,day", "sort": "-mean", "first": 3, "per": "none", "max_missing": 400}


def test_per_none_cuts_the_candidates_before_it_refuses_them(monkeypatch: pytest.MonkeyPatch) -> None:
    """Four stations of 90 days a limit of 20 groups holds is no 400: only the first 3 stay, with every tie counted."""
    request = _four_stations(monkeypatch)
    plain = request.values().statistics("mean", **_OPTIONS)
    reader = request.values()
    reader._held_rows_limit = 20  # noqa: SLF001
    limited = reader.statistics("mean", **_OPTIONS)
    assert limited.series_dicts() == plain.series_dicts()
    # the 6 degrees of 12 days of 4 stations tie: 48, and 3 are shown
    assert limited.tied == plain.tied == 45
    assert [g["rank"] for s in limited.series_dicts() for g in s["groups"]] == [1, 2, 3]
    assert limited.totals() == plain.totals()


def test_the_limit_still_refuses_what_cannot_be_cut(monkeypatch: pytest.MonkeyPatch) -> None:
    """A `first` of 30 over a limit of 20 groups cannot stay under it: the 400, as before."""
    request = _four_stations(monkeypatch)
    reader = request.values()
    reader._held_rows_limit = 20  # noqa: SLF001
    with pytest.raises(GroupsOverLimitError):
        reader.statistics("mean", **{**_OPTIONS, "first": 30})


def test_the_ties_are_counted_for_the_last_key_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station that beats the key the ties dropped earlier had makes those ties no ties of the N-th group."""
    from tests.model.statistics_stub import serve_custom  # noqa: PLC0415

    low = {at(2020, 1, 1) + dt.timedelta(days=n): 1.0 for n in range(30)}
    high = {at(2020, 1, 1) + dt.timedelta(days=n): 5.0 for n in range(2)}
    monkeypatch.setattr("wetterdienst.model.group_statistics._now", lambda: dt.datetime(2100, 1, 1, tzinfo=UTC))
    serve_custom(monkeypatch, {"00001": low, "00002": low, "00003": high}, parameter=PARAMETER)
    request = DwdObservationRequest(parameters=[DAILY], start=at(2020, 1, 1), end=at(2020, 1, 30, 23)).all()
    options = {"by": "day", "sort": "-mean", "first": 3, "per": "none", "max_missing": 400}
    plain = request.values().statistics("mean", **options)
    reader = request.values()
    reader._held_rows_limit = 10  # noqa: SLF001
    limited = reader.statistics("mean", **options)
    assert limited.series_dicts() == plain.series_dicts()
    # two 5.0 and then the 1.0 of two stations x 30 days: 60 tie for the third place
    assert limited.tied == plain.tied == 59


# ----------------------------------------------------------------------------------------------------------------
# R4: `complete` is read as a flag in words
# ----------------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("having", "years"),
    [
        ("complete", [2019]),
        ("COMPLETE", [2019]),
        (" Complete ", [2019]),
        ("complete=true", [2019]),
        ("complete=TRUE", [2019]),
        ("complete=yes", [2019]),
        ("complete=false", [2020]),
        ("complete=no", [2020]),
        ("complete!=false", [2019]),
        ("complete!=no", [2019]),
        ("complete=true|false", [2019, 2020]),
        ("complete=1", [2019]),
        ("complete=0", [2020]),
        ("complete,count>=1", [2019]),
    ],
)
def test_complete_is_a_flag_in_words(monkeypatch: pytest.MonkeyPatch, having: str, years: list[int]) -> None:
    """`having=complete=true|yes|false|no` is `complete=1|0`, as the bare word is `complete=1`."""
    request = _gappy(monkeypatch)
    result = request.values().statistics("count", by="year", having=having)
    assert [row["year"] for row in _rows(result)] == years


def test_the_echo_of_complete_written_in_words_is_the_number() -> None:
    """The options are echoed as they were read: `complete=true` is `complete=1`."""
    plan = parse_statistics("count", by="year", having="complete=yes")
    assert plan.echo()["having"] == "complete=1"
    assert parse_statistics("count", by="year", having="complete=no").echo()["having"] == "complete=0"


# ----------------------------------------------------------------------------------------------------------------
# R6: a window that starts at noon of the 1st has passed that month; a value dated 06:00 of the 1st is that month's
# ----------------------------------------------------------------------------------------------------------------


def _monthly(stamps: list[dt.datetime]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "station_id": ["00001"] * len(stamps),
            "resolution": ["monthly"] * len(stamps),
            "dataset": ["climate_summary"] * len(stamps),
            "parameter": ["temperature_air_mean_2m"] * len(stamps),
            "timestamp": stamps,
            "value": [1.0] * len(stamps),
        },
        schema_overrides={"timestamp": pl.Datetime("us", "UTC")},
    )


def test_a_monthly_window_from_noon_of_the_1st_expects_the_months_after_it() -> None:
    """11 monthly values from February to December of a window that begins 2019-01-01T12:00: 11 of 11 (as `values`)."""
    frame = _monthly([at(2019, month, 1) for month in range(2, 13)])
    window = (dt.datetime(2019, 1, 1, 12, tzinfo=UTC), at(2019, 12, 31, 23))
    now = dt.datetime(2100, 1, 1, tzinfo=UTC)
    (row,) = searched_of(frame, window, now).to_dicts()
    assert (row["searched"], row["expected"], row["gaps"]) == (11, 11, 0)
    # the statistics ask the same of a window, whatever they say of a value's own stamp
    (row,) = searched_of(frame, window, now, stamped_on_the_day=True).to_dicts()
    assert (row["searched"], row["expected"], row["gaps"]) == (11, 11, 0)


def test_a_monthly_value_dated_off_midnight_is_counted_by_the_statistics_only() -> None:
    """Twelve values dated 06:00 of the 1st: 12 of 12 for the statistics; `values` keeps counting as it always did."""
    frame = _monthly([at(2020, month, 1, 6) for month in range(1, 13)])
    now = dt.datetime(2100, 1, 1, tzinfo=UTC)
    (row,) = searched_of(frame, (None, None), now, stamped_on_the_day=True).to_dicts()
    assert (row["searched"], row["expected"], row["gaps"]) == (12, 12, 0)
    (row,) = searched_of(frame, (None, None), now).to_dicts()
    assert row["expected"] is None


@pytest.mark.parametrize(
    ("resolution", "start", "end", "own", "plain"),
    [
        (Resolution.MONTHLY, dt.datetime(2019, 1, 1, 12, tzinfo=UTC), at(2019, 12, 1), 12, 11),
        (Resolution.MONTHLY, dt.datetime(2019, 1, 2, tzinfo=UTC), at(2019, 12, 1), 11, 11),
        (Resolution.MONTHLY, at(2019, 1, 1), at(2019, 12, 1), 12, 12),
        (Resolution.ANNUAL, dt.datetime(2019, 1, 1, 6, tzinfo=UTC), at(2021, 1, 1), 3, 2),
        (Resolution.ANNUAL, dt.datetime(2019, 3, 1, tzinfo=UTC), at(2021, 1, 1), 2, 2),
        (Resolution.DAILY, dt.datetime(2019, 1, 1, 6, tzinfo=UTC), at(2019, 1, 3), 2, 2),
    ],
)
def test_count_readings_counts_a_stamp_of_the_1st_only_where_it_is_a_value(
    resolution: Resolution, start: dt.datetime, end: dt.datetime, own: int, plain: int
) -> None:
    """The start of a window that is past the anchor has not got that month; a value's own stamp is that month's."""
    assert count_readings(resolution, start, end) == plain
    assert count_readings(resolution, start, end, own_stamp=True) == own


# ----------------------------------------------------------------------------------------------------------------
# R7: the warning says how many of the groups are in the answer
# ----------------------------------------------------------------------------------------------------------------


def _two_short_years(monkeypatch: pytest.MonkeyPatch) -> Any:  # noqa: ANN401
    readings = {**daily(dt.date(2019, 1, 1), [1.0] * 200), **daily(dt.date(2020, 1, 1), [2.0] * 200)}
    _serve(monkeypatch, readings)
    return _request(at(2019, 1, 1), dt.datetime(2020, 12, 31, 23, tzinfo=UTC))


def test_the_incomplete_warning_says_how_many_are_in_the_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two incomplete years, none of them kept by `having=complete`: '0 of them in this answer'."""
    request = _two_short_years(monkeypatch)
    assert request.values().statistics("count", by="year", having="complete").series_dicts()[0]["groups"] == []
    message = _codes()["incomplete-groups"]
    assert message.startswith("2 groups have fewer values than expected")
    assert "(0 of them in this answer)" in message
    assert "their `mean` and `sum`" in message


def test_the_incomplete_warning_counts_the_groups_that_are_in_the_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both years are in the answer: '2 of them'."""
    request = _two_short_years(monkeypatch)
    request.values().statistics("count", by="year")
    assert "(2 of them in this answer)" in _codes()["incomplete-groups"]


def test_one_incomplete_group_is_a_group_that_has(monkeypatch: pytest.MonkeyPatch) -> None:
    """One group: 'has', 'its', and whether it is in the answer."""
    request = _gappy(monkeypatch)
    request.values().statistics("count", by="year", having="complete")
    message = _codes()["incomplete-groups"]
    assert message.startswith("1 group has fewer values than expected")
    assert "(it is not in this answer)" in message
    assert "its `mean` and `sum` are null" in message
    assert "groups" not in message.split(":")[0]


# ----------------------------------------------------------------------------------------------------------------
# the steps of the clock: a window from 00:05 to 03:00 of 10-minute values
# ----------------------------------------------------------------------------------------------------------------


def test_a_window_of_minutes_counts_the_steps_of_the_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """Values at 00:10 to 03:00 in a window of 00:05 to 03:00: 5, 6, 6 and 1 steps, all there, all complete."""
    readings: dict[dt.datetime, float | None] = {
        at(2020, 3, 1) + dt.timedelta(minutes=10 * n): float(n) for n in range(1, 19)
    }
    _serve(monkeypatch, readings, resolution="10_minutes", dataset="temperature_air", parameter="temperature_air_2m")
    request = DwdObservationRequest(
        parameters=["10_minutes/temperature_air/temperature_air_2m"],
        start=dt.datetime(2020, 3, 1, 0, 5, tzinfo=UTC),
        end=dt.datetime(2020, 3, 1, 3, 0, tzinfo=UTC),
    ).all()
    result: StatisticsResult = request.values().statistics("count,mean", by="hour")
    assert [(r["hour"], r["searched"], r["expected"], r["complete"]) for r in _rows(result)] == [
        (0, 5, 5, True),
        (1, 6, 6, True),
        (2, 6, 6, True),
        (3, 1, 1, True),
    ]
    whole = request.values().statistics("count,mean")
    (row,) = _rows(whole)
    assert (row["searched"], row["expected"], row["complete"]) == (18, 18, True)


# ----------------------------------------------------------------------------------------------------------------
# the refusal of a name the request has
# ----------------------------------------------------------------------------------------------------------------


def test_values_refuses_the_source_name_as_statistics_does(monkeypatch: pytest.MonkeyPatch) -> None:
    """`tmk`, the name in the source, is no column of `filter` in `values` either: both say which names are."""
    from tests.model.test_group_statistics_review import at as at_  # noqa: PLC0415

    readings = {at_(2020, 1, d): -1.0 for d in range(1, 10)}
    _serve(monkeypatch, readings)
    request = _request(at(2020, 1, 1), at(2020, 1, 20), parameter=f"daily/climate_summary/{PARAMETER}")
    with pytest.raises(ValueError, match="`tmk` is not a column") as in_values:
        request.values().all(filter="tmk<0")
    with pytest.raises(ValueError, match="`tmk` is no column") as in_statistics:
        request.values().statistics("count", filter="tmk<0")
    assert "temperature_air_mean_2m" in str(in_values.value)
    assert "write `value`" in str(in_statistics.value)


def test_the_two_parameters_of_a_request_are_named_without_a_did_you_mean(monkeypatch: pytest.MonkeyPatch) -> None:
    """The refusal of `wind_gust_max<0` with two parameters in the request says why, and does not suggest itself."""
    serve(monkeypatch)
    request = DwdObservationRequest(parameters=[TMIN, GUST], start=at(2018, 1, 1), end=at(2018, 12, 31)).all()
    with pytest.raises(ValueError, match="is a parameter of this request") as refused:
        request.values().statistics("count", filter="wind_gust_max<0")
    assert "did you mean" not in str(refused.value).lower()
    assert "ask for it alone" in str(refused.value)
    with pytest.raises(ValueError, match="Did you mean") as typo:
        request.values().statistics("count", filter="wind_gust_mx<0")
    assert "wind_gust_max" in str(typo.value)


# ----------------------------------------------------------------------------------------------------------------
# what mutants passed: the series left out of the list still count in the warnings, and floats tie by their rounding
# ----------------------------------------------------------------------------------------------------------------


def test_the_series_left_out_of_a_per_none_answer_are_still_warned_of(monkeypatch: pytest.MonkeyPatch) -> None:
    """Four stations whose January lacks a day: `first=1` lists one series, the warning counts the incomplete four."""
    from tests.model.statistics_stub import serve_custom  # noqa: PLC0415
    from wetterdienst.util.response_warnings import begin_response  # noqa: PLC0415

    readings = {at(2020, 1, 1) + dt.timedelta(days=n): float(n % 7) for n in range(90) if n != 10}
    monkeypatch.setattr("wetterdienst.model.group_statistics._now", lambda: dt.datetime(2100, 1, 1, tzinfo=UTC))
    serve_custom(monkeypatch, {f"0000{n}": readings for n in range(1, 5)}, parameter=PARAMETER)
    begin_response()
    request = DwdObservationRequest(parameters=[DAILY], start=at(2020, 1, 1), end=at(2020, 3, 30, 23)).all()
    result = request.values().statistics("count", by="month", sort="-count", first=1, per="none")
    assert len(result.series) == 1
    assert len(result.left_out) == 3
    message = _codes()["incomplete-groups"]
    assert message.startswith("4 groups have fewer values than expected")
    assert "00004" in message
    assert "of them in this answer)" in message


def test_two_sums_that_differ_in_the_last_bit_of_a_float_tie_only_because_they_are_rounded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The same four numbers in two orders add to 1.3 and 1.2999999999999998: the months tie, rounded to six places."""
    first, second = [0.1, 0.2, 0.3, 0.7], [0.1, 0.7, 0.3, 0.2]
    assert pl.Series(first).sum() != pl.Series(second).sum()
    readings = {
        at(2020, month, day + 1): value
        for month, values in ((1, first), (2, second))
        for day, value in enumerate(values)
    }
    _serve(monkeypatch, readings, parameter="precipitation_amount")
    request = _request(at(2020, 1, 1), at(2020, 2, 4, 23), parameter="daily/climate_summary/precipitation_amount")
    result = request.values().statistics("sum", by="month", sort="-sum", first=1, max_missing=60)
    assert result.tied == 1
    assert _rows(result)[0]["sum"] == 1.3


def test_a_window_in_the_future_has_no_groups_and_is_no_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station with no value in a window that has not begun: no series, no group, no crash, nothing searched."""
    _serve(monkeypatch, daily(dt.date(2020, 1, 1), [1.0] * 30))
    request = _request(at(2200, 1, 1), at(2200, 12, 31, 23))
    result = request.values().statistics("count,mean", by="year")
    assert result.series_dicts() == []
    totals = result.totals()
    assert (totals["groups"], totals["searched"], totals["groups_returned"]) == (0, 0, 0)
    assert result.df.height == 0


def test_the_statistics_over_the_groups_are_rounded_to_six_places(monkeypatch: pytest.MonkeyPatch) -> None:
    """Three months of means 1/3, 1/3 and 2/3: the mean of the groups is 0.444444, not 0.4444443333."""
    readings = {
        **{at(2020, 1, d): v for d, v in ((1, 0.0), (2, 0.0), (3, 1.0))},
        **{at(2020, 2, d): v for d, v in ((1, 0.0), (2, 0.0), (3, 1.0))},
        **{at(2020, 3, d): v for d, v in ((1, 1.0), (2, 1.0), (3, 0.0))},
    }
    _serve(monkeypatch, readings)
    request = _request(at(2020, 1, 1), at(2020, 3, 3, 23))
    result = request.values().statistics("mean", by="month", max_missing=60)
    over = result.series_dicts()[0]["over_groups"]["mean"]
    assert (over["min"], over["max"], over["mean"]) == (0.333333, 0.666667, 0.444444)


def test_to_csv_without_its_header_is_the_rows_alone(monkeypatch: pytest.MonkeyPatch) -> None:
    """`include_header=False` leaves the column names out and nothing else."""
    request = _gappy(monkeypatch)
    result = request.values().statistics("count", by="year")
    with_header = result.to_csv().splitlines()
    without = result.to_csv(include_header=False).splitlines()
    assert without == with_header[1:]
    assert len(without) == 2
    assert "year" in with_header[0]


def test_a_held_result_has_the_units_of_the_reader(monkeypatch: pytest.MonkeyPatch) -> None:
    """The statistics of a result already read name the same unit as those of the reader."""
    _serve(monkeypatch, daily(dt.date(2020, 1, 1), [1.0, 2.0, 3.0]))
    request = _request(at(2020, 1, 1), at(2020, 1, 3, 23))
    reader = request.values().statistics("mean")
    held = request.values().all().statistics("mean")
    assert held.series_dicts()[0]["unit"] == reader.series_dicts()[0]["unit"] == "°C"


def test_the_months_of_a_window_that_starts_in_one_begin_with_the_next(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monthly values from April: a window from the middle of March has 9 months to 2020-12 (March's has gone by)."""
    readings = {at(2020, month, 1): float(month) for month in range(4, 13)}
    _serve(monkeypatch, readings, resolution="monthly", dataset="climate_summary", parameter=PARAMETER)
    request = DwdObservationRequest(
        parameters=["monthly/climate_summary/temperature_air_mean_2m"],
        start=dt.datetime(2020, 3, 15, tzinfo=UTC),
        end=at(2020, 12, 31),
    ).all()
    (row,) = _rows(request.values().statistics("count,mean"))
    assert (row["searched"], row["expected"], row["complete"]) == (9, 9, True)
