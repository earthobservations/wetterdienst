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
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

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


# ----------------------------------------------------------------------------------------------------------------
# S1, S3: a cell begins where its step does, and a window that begins at noon of the 1st has passed that month
# ----------------------------------------------------------------------------------------------------------------


def test_the_day_of_a_value_dated_0600_begins_at_midnight(monkeypatch: pytest.MonkeyPatch) -> None:
    """Daily values dated 06:00: each day is a group of 1 of 1, the first included (its cell begins before it)."""
    _serve(monkeypatch, {at(2020, 1, d, 6): float(d) for d in range(1, 6)})
    request = _request(None, None)
    rows = _rows(request.values().statistics("count", by="day"))
    assert [(r["day"], r["searched"], r["expected"], r["complete"]) for r in rows] == [
        (d, 1, 1, True) for d in range(1, 6)
    ]
    (row,) = _rows(request.values().statistics("count,mean"))
    assert (row["searched"], row["expected"]) == (5, 5)


def test_the_hour_of_a_value_dated_half_past_begins_on_the_hour(monkeypatch: pytest.MonkeyPatch) -> None:
    """Hourly values dated :30: each hour is a group of 1 of 1, the first included."""
    readings: dict[dt.datetime, float | None] = {at(2020, 1, 1, h) + dt.timedelta(minutes=30): 1.0 for h in range(6)}
    _serve(monkeypatch, readings, resolution="hourly", dataset="air_temperature", parameter="temperature_air_2m")
    request = DwdObservationRequest(parameters=["hourly/air_temperature/temperature_air_2m"]).all()
    rows = _rows(request.values().statistics("count", by="day,hour"))
    assert [(r["hour"], r["searched"], r["expected"], r["complete"]) for r in rows] == [
        (h, 1, 1, True) for h in range(6)
    ]


def test_the_month_of_a_value_dated_0600_of_the_1st_is_a_group_of_1_of_1(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monthly values dated 06:00 of the 1st: every month, January included, is 1 of 1."""
    _serve(
        monkeypatch, {at(2020, m, 1, 6): float(m) for m in range(1, 7)}, resolution="monthly", dataset="climate_summary"
    )
    request = DwdObservationRequest(parameters=["monthly/climate_summary/temperature_air_mean_2m"]).all()
    rows = _rows(request.values().statistics("count", by="month"))
    assert [(r["month"], r["searched"], r["expected"], r["complete"]) for r in rows] == [
        (m, 1, 1, True) for m in range(1, 7)
    ]


def test_the_first_hour_of_a_record_that_begins_at_0010_lacks_its_first_step(monkeypatch: pytest.MonkeyPatch) -> None:
    """A year whole: hour 0 of a 10-minute record from 00:10 is 5 of 6, incomplete, with an `expected`."""
    readings: dict[dt.datetime, float | None] = {
        at(2020, 3, 1) + dt.timedelta(minutes=10 * n): 1.0 for n in range(1, 19)
    }
    _serve(monkeypatch, readings, resolution="10_minutes", dataset="temperature_air", parameter="temperature_air_2m")
    request = DwdObservationRequest(parameters=["10_minutes/temperature_air/temperature_air_2m"]).all()
    rows = _rows(request.values().statistics("count", by="year,month,day,hour"))
    first = rows[0]
    assert (first["hour"], first["searched"], first["expected"], first["complete"]) == (0, 5, 6, False)
    assert all(r["expected"] is not None for r in rows)


def test_a_window_from_0030_to_0220_has_3_6_and_3_steps_in_its_hours(monkeypatch: pytest.MonkeyPatch) -> None:
    """The first and the last hour of a window are cut where it begins and ends: each has its `expected`."""
    readings: dict[dt.datetime, float | None] = {
        at(2020, 3, 1) + dt.timedelta(minutes=10 * n): 1.0 for n in range(1, 19)
    }
    _serve(monkeypatch, readings, resolution="10_minutes", dataset="temperature_air", parameter="temperature_air_2m")
    request = DwdObservationRequest(
        parameters=["10_minutes/temperature_air/temperature_air_2m"],
        start=dt.datetime(2020, 3, 1, 0, 30, tzinfo=UTC),
        end=dt.datetime(2020, 3, 1, 2, 20, tzinfo=UTC),
    ).all()
    rows = _rows(request.values().statistics("count", by="hour"))
    assert [(r["hour"], r["searched"], r["expected"], r["complete"]) for r in rows] == [
        (0, 3, 3, True),
        (1, 6, 6, True),
        (2, 3, 3, True),
    ]


def test_a_monthly_window_from_noon_of_the_1st_is_11_of_11_for_the_group_as_for_the_series(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Values for February to December in a window from 2019-01-01T12:00: the group says what the series does."""
    _serve(monkeypatch, {at(2019, m, 1): 1.0 for m in range(2, 13)}, resolution="monthly", dataset="climate_summary")
    request = DwdObservationRequest(
        parameters=["monthly/climate_summary/temperature_air_mean_2m"],
        start=dt.datetime(2019, 1, 1, 12, tzinfo=UTC),
        end=at(2019, 12, 31),
    ).all()
    result = request.values().statistics("count,mean")
    series = result.series_dicts()[0]
    (row,) = series["groups"]
    assert (series["searched"], series["expected"]) == (11, 11)
    assert (row["searched"], row["expected"], row["complete"]) == (11, 11, True)


# ----------------------------------------------------------------------------------------------------------------
# S6: a name is suggested for a misspelling only, and `complete` is a flag
# ----------------------------------------------------------------------------------------------------------------


def test_another_quantity_is_not_suggested_for_a_name_in_a_request_for_the_mean(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`temperature_air_min_2m<0` is not a typo of the mean's name: the refusal says what to write, with no name."""
    _serve(monkeypatch, daily(dt.date(2020, 1, 1), [1.0, 2.0]))
    request = _request(at(2020, 1, 1), at(2020, 1, 2, 23))
    with pytest.raises(ValueError, match="is not a parameter of this request") as refused:
        request.values().statistics("count", filter="temperature_air_min_2m<0")
    assert "did you mean" not in str(refused.value).lower()
    assert "write `value`" in str(refused.value)
    with pytest.raises(ValueError, match="Did you mean temperature_air_mean_2m") as typo:
        request.values().statistics("count", filter="temperature_air_mean_2n<0")
    assert "is not a parameter of this request" not in str(typo.value)


@pytest.mark.parametrize(
    ("having", "word"),
    [("complete=maybe", "maybe"), ("complete=1|maybe", "maybe"), ("count>1,complete!=perhaps", "perhaps")],
)
def test_complete_with_a_word_that_is_no_flag_says_what_the_flag_takes(
    monkeypatch: pytest.MonkeyPatch, having: str, word: str
) -> None:
    """`complete=maybe` is refused with its position and `1, 0, true, yes, false or no`; no unit of the values."""
    request = _gappy(monkeypatch)
    with pytest.raises(ValueError, match="`complete` is a flag, not a quantity") as refused:
        request.values().statistics("count", by="year", having=having)
    text = str(refused.value)
    assert "1, 0, true, yes, false or no" in text
    assert "unit of the values" not in text
    assert getattr(refused.value, "position", None) == having.index(word) + 1


# ----------------------------------------------------------------------------------------------------------------
# what mutants passed (the numbers are the reviewer's)
# ----------------------------------------------------------------------------------------------------------------


def test_a_group_with_more_values_than_cells_has_no_expected_the_others_have(monkeypatch: pytest.MonkeyPatch) -> None:
    """(10) Rule 4 at the group: January, with a day read twice, has no `expected`; February and March are counted."""
    readings: dict[dt.datetime, float | None] = {at(2020, 1, d): 1.0 for d in range(1, 32)}
    readings[at(2020, 1, 1, 18)] = 2.0
    readings.update({at(2020, 2, d): 1.0 for d in range(1, 11)})
    readings.update({at(2020, 3, d): 1.0 for d in range(1, 32)})
    _serve(monkeypatch, readings)
    request = _request(None, None)
    rows = _rows(request.values().statistics("count", by="month"))
    assert [(r["month"], r["searched"], r["expected"], r["complete"]) for r in rows] == [
        (1, 32, None, True),
        (2, 10, 29, False),
        (3, 31, 31, True),
    ]
    assert "completeness-unknown" in _codes()


def test_a_held_result_names_the_unit_the_reader_names(monkeypatch: pytest.MonkeyPatch) -> None:
    """(31) Cloud cover is 1/8 as the source has it and % converted: a held result says what the reader says."""
    from wetterdienst import Options  # noqa: PLC0415

    _serve(monkeypatch, daily(dt.date(2020, 1, 1), [1.0, 2.0, 3.0]), parameter="cloud_cover_total_mean")
    for options, unit in ((Options(convert_units=False), "1/8"), (Options(), "%")):
        request = _request(
            at(2020, 1, 1),
            at(2020, 1, 3, 23),
            parameter="daily/climate_summary/cloud_cover_total_mean",
            options=options,
        )
        reader = request.values().statistics("mean").series_dicts()[0]["unit"]
        held = request.values().all().statistics("mean").series_dicts()[0]["unit"]
        assert held == reader == unit


def test_the_series_of_per_none_are_listed_by_their_best_group(monkeypatch: pytest.MonkeyPatch) -> None:
    """(47) The station read first has the lowest mean: it comes last; the ranks are 1, 2, 3 in that order."""
    from tests.model.statistics_stub import serve_custom  # noqa: PLC0415

    monkeypatch.setattr("wetterdienst.model.group_statistics._now", lambda: dt.datetime(2100, 1, 1, tzinfo=UTC))
    series = {
        station: {at(2020, 1, 1) + dt.timedelta(days=n): value for n in range(366)}
        for station, value in (("00001", 1.0), ("00002", 9.0), ("00003", 5.0))
    }
    serve_custom(monkeypatch, series, parameter=PARAMETER)
    request = DwdObservationRequest(parameters=[DAILY], start=at(2020, 1, 1), end=at(2020, 12, 31, 23)).all()
    result = request.values().statistics("mean", by="year", sort="-mean", first=3, per="none")
    listed = result.series_dicts()
    assert [s["station_id"] for s in listed] == ["00002", "00003", "00001"]
    assert [g["rank"] for s in listed for g in s["groups"]] == [1, 2, 3]


def test_the_df_and_the_rows_have_complete_as_a_boolean(monkeypatch: pytest.MonkeyPatch) -> None:
    """(70) `complete` is a true or a false in the frame and in the rows, not a 1 or a 0."""
    request = _gappy(monkeypatch)
    result = request.values().statistics("count", by="year")
    assert result.df.schema["complete"] == pl.Boolean
    assert result.df.get_column("complete").to_list() == [True, False]
    assert [row["complete"] for row in _rows(result)] == [True, False]
    assert all(type(row["complete"]) is bool for row in _rows(result))


def test_the_totals_count_the_groups_returned_after_every_cut(monkeypatch: pytest.MonkeyPatch) -> None:
    """(73) `groups_returned` is what the series hold: after `max_rows`, after `head`, and with none."""
    request = _gappy(monkeypatch)
    whole = request.values().statistics("count", by="year")
    assert whole.totals()["groups_returned"] == whole.totals()["groups"] == 2
    capped = request.values().statistics("count", by="year", max_rows=1)
    totals = capped.totals()
    assert (totals["groups_returned"], totals["groups_matched"], totals["groups"]) == (1, 2, 2)
    assert whole.head(1).totals()["groups_returned"] == 1
    none = request.values().statistics("count", by="year", having="count>9999")
    assert none.totals()["groups_returned"] == 0


def test_a_monthly_value_dated_0600_is_for_values_as_it_was(monkeypatch: pytest.MonkeyPatch) -> None:
    """(113) Only `statistics` count a value of the 1st at 06:00 as its month's: `values` report as they always did."""
    _serve(monkeypatch, {at(2020, m, 1, 6): 1.0 for m in range(1, 13)}, resolution="monthly", dataset="climate_summary")
    request = DwdObservationRequest(parameters=["monthly/climate_summary/temperature_air_mean_2m"]).all()
    result = request.values().all(filter="value>=0")
    assert result.search is not None
    assert result.search.series.get_column("expected").to_list() == [None]


# ----------------------------------------------------------------------------------------------------------------
# `gaps-allowed`: a group that lacks values is in the answer because `max_missing` says so
# ----------------------------------------------------------------------------------------------------------------


def test_a_group_with_gaps_that_max_missing_lets_in_is_warned_of_with_its_counts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """2020 lacks 66 days (300 of 366): `max_missing=66` ranks it, and the warning says how many and why."""
    request = _gappy(monkeypatch)
    result = request.values().statistics("mean", by="year", sort="-mean", max_missing=66)
    assert [row["complete"] for row in _rows(result)] == [True, True]
    message = _codes()["gaps-allowed"]
    assert message.startswith("1 group lacks 66 values and is ranked because `max_missing` is 66")
    assert "`complete` is true, which says no more than `max_missing` lack" in message
    assert "Keep `max_missing` at 0" in message


def test_without_a_ranking_the_group_is_in_the_answer_not_ranked(monkeypatch: pytest.MonkeyPatch) -> None:
    """No `sort`: nothing is ranked, and the warning says the group is in the answer."""
    request = _gappy(monkeypatch)
    request.values().statistics("mean", by="year", max_missing=66)
    assert "is in the answer because `max_missing` is 66" in _codes()["gaps-allowed"]


def test_several_groups_are_counted_with_the_most_and_all_they_lack(monkeypatch: pytest.MonkeyPatch) -> None:
    """Two years of 200 days lack 165 and 166 values: '2 groups lack up to 166 values (331 in all)'."""
    request = _two_short_years(monkeypatch)
    request.values().statistics("sum", by="year", sort="-sum", max_missing=400)
    message = _codes()["gaps-allowed"]
    assert message.startswith("2 groups lack up to 166 values (331 in all) and are ranked because `max_missing` is 400")
    assert "their `mean` and `sum`" in message


def test_a_year_that_is_not_over_is_a_group_that_lacks_its_days_to_come(monkeypatch: pytest.MonkeyPatch) -> None:
    """The running year, 182 days short on 1 July, is let in by `max_missing=400`: the warning counts it."""
    _serve(monkeypatch, daily(dt.date(2020, 1, 1), [1.0] * 182), now=dt.datetime(2020, 7, 1, 12, tzinfo=UTC))
    request = _request(at(2020, 1, 1), at(2020, 6, 30, 23))
    request.values().statistics("mean", by="year", sort="-mean", max_missing=400)
    assert _codes()["gaps-allowed"].startswith("1 group lacks 184 values and is ranked")


@pytest.mark.parametrize(
    "options",
    [
        {"max_missing": 0},
        {"max_missing": 400, "having": "searched>=365"},
        {"max_missing": 400, "filter": "year=2019"},
    ],
)
def test_no_group_that_lacks_values_in_the_answer_is_no_warning(
    monkeypatch: pytest.MonkeyPatch, options: dict[str, int | str]
) -> None:
    """Quiet with `max_missing` 0, and quiet where the groups that remain have every value, whatever it is."""
    request = _gappy(monkeypatch)
    request.values().statistics("mean", by="year", sort="-mean", **options)
    assert "gaps-allowed" not in _codes()


def test_a_group_with_no_value_at_all_is_not_one_that_is_ranked(monkeypatch: pytest.MonkeyPatch) -> None:
    """A month inside the record with no value has no mean to rank: it lacks values, but is none the warning counts."""
    readings = {**{at(2020, 1, d): 1.0 for d in range(1, 32)}, **{at(2020, 3, d): 1.0 for d in range(1, 32)}}
    _serve(monkeypatch, readings)
    request = _request(None, None)
    rows = _rows(request.values().statistics("mean", by="month", max_missing=400))
    assert [(r["month"], r["searched"], r["mean"]) for r in rows] == [(1, 31, 1.0), (2, 0, None), (3, 31, 1.0)]
    assert "gaps-allowed" not in _codes()


def test_a_group_whose_expected_is_not_known_is_not_one_that_lacks(monkeypatch: pytest.MonkeyPatch) -> None:
    """More values than cells makes `expected` null: nothing is known to lack, so there is no warning."""
    readings: dict[dt.datetime, float | None] = {at(2020, 1, d): 1.0 for d in range(1, 32)}
    readings[at(2020, 1, 1, 18)] = 2.0
    readings.update({at(2020, 2, d): 1.0 for d in range(1, 11)})
    _serve(monkeypatch, readings)
    request = _request(None, None)
    request.values().statistics("count", by="month", max_missing=0, having="searched>=32")
    assert "gaps-allowed" not in _codes()


def test_the_warnings_of_a_cut_are_restated_or_dropped(monkeypatch: pytest.MonkeyPatch) -> None:
    """A cut that keeps 2019 only holds no group that lacks values: `gaps-allowed` goes, `incomplete-groups` says 0."""
    from wetterdienst.ui.budget import _restated_warnings  # noqa: PLC0415

    request = _gappy(monkeypatch)
    result = request.values().statistics("mean", by="year", max_missing=66)
    warnings = recorded_warnings()
    assert {"gaps-allowed"} <= {w["code"] for w in warnings}
    whole = _restated_warnings(result.plan, result, warnings)
    assert [w["message"] for w in whole if w["code"] == "gaps-allowed"] == [_codes()["gaps-allowed"]]
    cut = result.head(1)
    assert [row["year"] for row in _rows(cut)] == [2019]
    restated = _restated_warnings(result.plan, cut, warnings)
    assert "gaps-allowed" not in {w["code"] for w in restated}
    assert len(restated) == len(warnings) - 1


# ----------------------------------------------------------------------------------------------------------------
# the last look: a window that begins inside a month, the advice of `gaps-allowed`, what mutants passed
# ----------------------------------------------------------------------------------------------------------------


def test_a_window_that_begins_inside_a_month_has_no_group_for_that_month(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monthly values for December 2018 to December 2019 in a window from 2018-11-15: 13 groups, not 14, and no hole."""
    readings = {at(2018, 12, 1): 1.0, **{at(2019, m, 1): 1.0 for m in range(1, 13)}}
    _serve(monkeypatch, readings, resolution="monthly", dataset="climate_summary")
    request = DwdObservationRequest(
        parameters=["monthly/climate_summary/temperature_air_mean_2m"],
        start=dt.datetime(2018, 11, 15, tzinfo=UTC),
        end=at(2019, 12, 31),
    ).all()
    result = request.values().statistics("count", by="year,month")
    rows = _rows(result)
    assert [(r["year"], r["month"]) for r in rows] == [(2018, 12), *[(2019, m) for m in range(1, 13)]]
    assert result.totals()["groups"] == result.totals()["groups_not_listed"] + len(rows) == 13
    assert "no-values-in-groups" not in _codes()


def test_a_window_that_begins_inside_a_year_has_no_group_for_that_year_of_annual_values(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Annual values for 2019 and 2020 in a window from 2018-06-01: 2018 is no group."""
    _serve(monkeypatch, {at(2019, 1, 1): 1.0, at(2020, 1, 1): 2.0}, resolution="annual", dataset="climate_summary")
    request = DwdObservationRequest(
        parameters=["annual/climate_summary/temperature_air_mean_2m"],
        start=dt.datetime(2018, 6, 1, tzinfo=UTC),
        end=at(2020, 12, 31),
    ).all()
    result = request.values().statistics("count", by="year")
    assert [r["year"] for r in _rows(result)] == [2019, 2020]
    assert result.totals()["groups"] == 2


def test_a_month_a_window_begins_at_midnight_of_is_a_group_and_one_it_begins_in_is_not(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """From 2018-12-01 the month of December is in; from 2018-12-01T12:00 it has passed (as `values` count it)."""
    readings = {at(2019, m, 1): 1.0 for m in range(1, 4)}
    for start, groups in ((at(2018, 12, 1), 4), (dt.datetime(2018, 12, 1, 12, tzinfo=UTC), 3)):
        _serve(monkeypatch, readings, resolution="monthly", dataset="climate_summary")
        request = DwdObservationRequest(
            parameters=["monthly/climate_summary/temperature_air_mean_2m"], start=start, end=at(2019, 3, 31)
        ).all()
        result = request.values().statistics("count", by="year,month")
        assert [r["month"] for r in _rows(result)] == [1, 2, 3]
        assert result.totals()["groups"] == groups, start


@pytest.mark.parametrize(
    ("aggregate", "sort", "mentions_mean", "advice"),
    [
        (
            "count",
            "-count",
            False,
            "To rank only groups that have every value, use `having=complete` with `max_missing` 0.",
        ),
        (
            "min,max",
            "-max",
            False,
            "To rank only groups that have every value, use `having=complete` with `max_missing` 0.",
        ),
        (
            "earliest,latest",
            None,
            False,
            "To rank only groups that have every value, use `having=complete` with `max_missing` 0.",
        ),
        ("mean", "-mean", True, "Keep `max_missing` at 0 to rank only groups that have every value."),
        ("count,sum", "-sum", True, "Keep `max_missing` at 0 to rank only groups that have every value."),
    ],
)
def test_the_advice_of_gaps_allowed_is_for_what_was_asked(
    monkeypatch: pytest.MonkeyPatch,
    aggregate: str,
    sort: str | None,
    mentions_mean: bool,  # noqa: FBT001
    advice: str,
) -> None:
    """`count`, `min`, `max`, `earliest` and `latest` do not depend on `max_missing`: only `complete` does."""
    request = _gappy(monkeypatch)
    request.values().statistics(aggregate, by="year", sort=sort, max_missing=66)
    message = _codes()["gaps-allowed"]
    assert ("`mean` and `sum` are of the values there are" in message) is mentions_mean
    assert message.endswith(advice)
    assert "`complete` is true, which says no more than `max_missing` lack" in message
    assert message.count("Keep `max_missing` at 0") == int(mentions_mean)


def test_one_value_is_singular(monkeypatch: pytest.MonkeyPatch) -> None:
    """A group that lacks one value: '1 value', and for two such groups 'up to 1 value (2 in all)'."""
    readings = {
        **{at(2019, 1, 1) + dt.timedelta(days=n): 1.0 for n in range(364)},
        **{at(2020, 1, 1) + dt.timedelta(days=n): 1.0 for n in range(365)},
    }
    _serve(monkeypatch, readings)
    request = _request(at(2019, 1, 1), dt.datetime(2020, 12, 31, 23, tzinfo=UTC))
    request.values().statistics("mean", by="year", sort="-mean", max_missing=1, filter="year=2019")
    assert _codes()["gaps-allowed"].startswith("1 group lacks 1 value and is ranked because `max_missing` is 1:")
    begin_response()
    request.values().statistics("mean", by="year", sort="-mean", max_missing=1)
    assert _codes()["gaps-allowed"].startswith("2 groups lack up to 1 value (2 in all) and are ranked")


# ---- what mutants passed ----------------------------------------------------------------------------------------


def _nulls(stamps: list[dt.datetime]) -> pl.DataFrame:
    return pl.DataFrame(
        {
            "station_id": ["00001"] * len(stamps),
            "resolution": ["daily"] * len(stamps),
            "dataset": ["climate_summary"] * len(stamps),
            "parameter": ["temperature_air_mean_2m"] * len(stamps),
            "timestamp": stamps,
            "value": [None] * len(stamps),
        },
        schema_overrides={"timestamp": pl.Datetime("us", "UTC"), "value": pl.Float64},
    )


def test_a_series_with_no_value_is_expected_over_a_window_in_the_past_and_not_over_one_in_the_future() -> None:
    """(13) All missing over a past window is 31 expected of 0 searched; over a future one nothing is known."""
    now = dt.datetime(2100, 1, 1, tzinfo=UTC)
    frame = _nulls([at(2020, 1, d) for d in range(1, 6)])
    (past,) = searched_of(frame, (at(2020, 1, 1), at(2020, 1, 31)), now).to_dicts()
    assert (past["searched"], past["expected"], past["gaps"]) == (0, 31, None)
    (future,) = searched_of(frame, (at(2200, 1, 1), at(2200, 1, 31)), now).to_dicts()
    assert (future["searched"], future["expected"], future["gaps"]) == (0, None, None)
    (ever,) = searched_of(frame, (None, None), now).to_dicts()
    assert (ever["searched"], ever["expected"]) == (0, None)
    (live,) = searched_of(frame, (at(2020, 1, 1), at(2020, 1, 31)), now, forecast=True).to_dicts()
    assert live["expected"] is None


def test_a_held_result_gives_the_whole_answer_the_reader_gives(monkeypatch: pytest.MonkeyPatch) -> None:
    """(31) Series, units, groups and totals of a result already read are those of the reader, in both unit modes."""
    from wetterdienst import Options  # noqa: PLC0415

    readings = {at(2020, 1, 1) + dt.timedelta(days=n): float(n % 9) for n in range(120)}
    _serve(monkeypatch, readings)
    for options in (
        Options(convert_units=False),
        Options(),
        Options(unit_targets={"temperature": "degree_fahrenheit"}),
    ):
        request = _request(at(2020, 1, 1), at(2020, 4, 29, 23), options=options)
        for aggregates in ("count,mean,sum,min,max", "earliest,latest,count"):
            reader = request.values().statistics(aggregates, by="year,month", max_missing=40)
            held = request.values().all().statistics(aggregates, by="year,month", max_missing=40)
            assert held.series_dicts() == reader.series_dicts()
            assert held.totals() == reader.totals()
            assert held.df.equals(reader.df)


def test_the_series_of_per_none_are_listed_parameter_by_parameter_by_their_best_group(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """(47) Two parameters: the request's order, and within one the series whose best group ranks first."""
    serve(monkeypatch, count=5)
    request = DwdObservationRequest(parameters=[TMIN, GUST], start=at(2018, 1, 1), end=at(2020, 12, 31, 23)).all()
    result = request.values().statistics("max", by="year,month", sort="-max", first=8, per="none")
    listed = result.series_dicts()
    parameters = [s["parameter"] for s in listed]
    assert parameters == sorted(parameters, key=lambda name: [TMIN, GUST].index(f"daily/climate_summary/{name}"))
    for parameter in dict.fromkeys(parameters):
        block = [s for s in listed if s["parameter"] == parameter]
        best = [min(g["rank"] for g in s["groups"]) for s in block]
        assert best == sorted(best)
        assert sorted(g["rank"] for s in block for g in s["groups"]) == list(range(1, 9))


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"max_rows": 5},
        {"having": "count>=360"},
        {"sort": "-count", "first": 4},
        {"sort": "-count", "first": 4, "per": "none"},
        {"sort": "-count", "first": 4, "per": "none", "max_rows": 3},
        {"having": "count>9999"},
    ],
)
def test_groups_returned_is_what_the_series_hold_in_every_shape(
    monkeypatch: pytest.MonkeyPatch, options: dict[str, Any]
) -> None:
    """(73) `groups_returned`, the frame and the rows of the series are one number, whatever cut the answer."""
    serve(monkeypatch, count=4)
    request = DwdObservationRequest(parameters=[TMIN], start=at(2018, 1, 1), end=at(2020, 12, 31, 23)).all()
    result = request.values().statistics("count", by="year", max_missing=400, **options)
    returned = result.totals()["groups_returned"]
    assert returned == result.df.height == sum(len(s["groups"]) for s in result.series_dicts())
    assert result.totals()["groups_matched"] >= returned
    assert result.totals()["series"] == 4
