# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the annual values the stripes of GHCN daily are made of: years built from days by the WMO rules (GH-4222).

The frames are synthetic: numbers chosen so that each rule changes the answer, and no reading of a station.
"""

from __future__ import annotations

import datetime as dt
import math
from typing import TYPE_CHECKING, Literal

import polars as pl
import pytest

from wetterdienst.ui.stripes_annual import (
    PRECIPITATION,
    TEMPERATURE_MAX,
    TEMPERATURE_MEAN,
    TEMPERATURE_MIN,
    annual_from_daily,
    annual_note,
    leave_out_failed,
    temperature_method,
)

if TYPE_CHECKING:
    from collections.abc import Iterable


def _frame(parameter: str, days: Iterable[dt.date], value: float | dict[dt.date, float | None]) -> pl.DataFrame:
    """Make the long frame of one parameter: a value for each of the days, a constant or by day."""
    days = list(days)
    values = [value.get(day) for day in days] if isinstance(value, dict) else [value] * len(days)
    return pl.DataFrame(
        {"timestamp": days, "parameter": parameter, "value": values},
        schema={"timestamp": pl.Date, "parameter": pl.String, "value": pl.Float64},
    ).with_columns(pl.col("timestamp").cast(pl.Datetime("us", "UTC")))


def _days(first: dt.date, last: dt.date) -> list[dt.date]:
    return [first + dt.timedelta(days=n) for n in range((last - first).days + 1)]


def _year(year: int) -> list[dt.date]:
    return _days(dt.date(year, 1, 1), dt.date(year, 12, 31))


def _without(days: Iterable[dt.date], *gone: dt.date) -> list[dt.date]:
    return [day for day in days if day not in set(gone)]


def _temperature(days: list[dt.date], tmax: float = 10.0, tmin: float = 0.0) -> pl.DataFrame:
    return pl.concat([_frame(TEMPERATURE_MAX, days, tmax), _frame(TEMPERATURE_MIN, days, tmin)])


def _values(frame: pl.DataFrame) -> dict[int, float | None]:
    """Read the answer as year to value."""
    return dict(
        zip(frame.get_column("timestamp").dt.year().to_list(), frame.get_column("value").to_list(), strict=True)
    )


def test_the_answer_is_the_frame_dwds_annual_values_come_in() -> None:
    """Test one row a year at 1 January 00:00 UTC, in a long frame of `timestamp` and `value`."""
    frame = annual_from_daily(_temperature(_year(2000)), "temperature")
    assert frame.columns == ["timestamp", "value"]
    assert frame.schema == pl.Schema({"timestamp": pl.Datetime("us", "UTC"), "value": pl.Float64})
    assert frame.get_column("timestamp").to_list() == [dt.datetime(2000, 1, 1, tzinfo=dt.UTC)]


def test_a_temperature_year_is_the_mean_of_the_monthly_means_not_of_the_days() -> None:
    """Test every month weighs the same: February's 29 days count as much as July's 31."""
    year = _year(2000)
    # a mean of 10 in February alone (29 days in 2000), 0 in the other months
    february = {day: (20.0 if day.month == 2 else 0.0) for day in year}
    frame = pl.concat([_frame(TEMPERATURE_MAX, year, february), _frame(TEMPERATURE_MIN, year, february)])
    (value,) = annual_from_daily(frame, "temperature").get_column("value").to_list()
    assert value == pytest.approx(20.0 / 12, abs=1e-3)
    # by the days it would be 20 * 29 / 366
    assert value != pytest.approx(20.0 * 29 / 366, abs=0.01)


def test_a_day_is_the_midrange_and_a_day_with_one_of_tmax_and_tmin_is_missing() -> None:
    """Test (TMAX + TMIN) / 2 makes the day, and one of the two alone makes none."""
    year = _year(2001)
    march = [day for day in year if day.month == 3]
    tmax = _frame(TEMPERATURE_MAX, year, 30.0)
    # no TMIN on 3 days of March: TMAX alone is no mean, those days are missing (3 of 31, so the month still counts),
    # and 11 would fail it
    tmin = _frame(TEMPERATURE_MIN, _without(year, *march[:3]), 10.0)
    assert _values(annual_from_daily(pl.concat([tmax, tmin]), "temperature")) == {2001: 20.0}
    fewer = _frame(TEMPERATURE_MIN, _without(year, *march[:22:2]), 10.0)
    assert _values(annual_from_daily(pl.concat([tmax, fewer]), "temperature")) == {2001: None}


def test_tavg_alone_makes_the_days() -> None:
    """Test a station with a TAVG and no TMAX or TMIN has its years from the TAVG."""
    frame = _frame(TEMPERATURE_MEAN, _year(1999), 7.5)
    assert _values(annual_from_daily(frame, "temperature")) == {1999: 7.5}


def test_a_tavg_beside_a_tmax_and_tmin_is_never_used_even_on_the_days_it_has() -> None:
    """Test the midrange makes every day of a station that has both, and a TAVG beside them changes nothing."""
    year = _year(1999)
    frame = pl.concat([_temperature(year, tmax=30.0, tmin=10.0), _frame(TEMPERATURE_MEAN, year, 12.0)])
    assert _values(annual_from_daily(frame, "temperature")) == {1999: 20.0}


def test_a_tavg_that_covers_part_of_the_record_makes_no_step_in_the_series() -> None:
    """Test TAVG on the second year only, 8 degrees under the midrange, does not show in that year's value."""
    days = _year(2000) + _year(2001) + _year(2002)
    frame = pl.concat([_temperature(days, tmax=30.0, tmin=10.0), _frame(TEMPERATURE_MEAN, _year(2001), 12.0)])
    assert _values(annual_from_daily(frame, "temperature")) == {2000: 20.0, 2001: 20.0, 2002: 20.0}


def test_the_method_is_the_midrange_where_a_day_has_both_else_tavg_else_none() -> None:
    """Test the method is told from the days read: a day with TMAX and TMIN, a TAVG alone, nothing."""
    year = _year(2003)
    assert temperature_method(_temperature(year)) == "midrange"
    assert temperature_method(pl.concat([_temperature(year), _frame(TEMPERATURE_MEAN, year, 1.0)])) == "midrange"
    assert temperature_method(_frame(TEMPERATURE_MEAN, year, 1.0)) == "tavg"
    # TMAX and TMIN that never fall on the same day have no midrange: the TAVG is what is left
    apart = pl.concat([_frame(TEMPERATURE_MAX, year[:100], 10.0), _frame(TEMPERATURE_MIN, year[100:], 0.0)])
    assert temperature_method(apart) is None
    assert temperature_method(pl.concat([apart, _frame(TEMPERATURE_MEAN, year, 5.0)])) == "tavg"
    assert temperature_method(_frame(PRECIPITATION, year, 1.0)) is None
    assert temperature_method(_temperature(year).clear()) is None


@pytest.mark.parametrize(
    ("gone", "valid"),
    [
        pytest.param(10, True, id="ten-days-missing-is-valid"),
        pytest.param(11, False, id="eleven-days-missing-is-not"),
    ],
)
def test_a_temperature_month_counts_with_at_most_10_days_missing(gone: int, valid: bool) -> None:  # noqa: FBT001
    """Test the limit is 10 missing days a month, whichever they are, when none of them are in a long run."""
    year = _year(2002)
    # every other day of March, so that no two missing days follow one another
    march = [day for day in year if day.month == 3][::2][:gone]
    frame = _temperature(_without(year, *march))
    value = _values(annual_from_daily(frame, "temperature"))[2002]
    assert (value is not None) is valid
    if valid:
        # the days that are there are all alike, so the month and the year are as well
        assert value == 5.0


@pytest.mark.parametrize(
    ("in_a_row", "valid"),
    [
        pytest.param(4, True, id="four-in-a-row-is-valid"),
        pytest.param(5, False, id="five-in-a-row-is-not"),
    ],
)
def test_a_temperature_month_counts_with_at_most_4_days_missing_in_a_row(in_a_row: int, valid: bool) -> None:  # noqa: FBT001
    """Test a run of 5 days fails the month although 5 are far fewer than 10 missing."""
    year = _year(2003)
    june = [day for day in year if day.month == 6]
    frame = _temperature(_without(year, *june[9 : 9 + in_a_row]))
    assert (_values(annual_from_daily(frame, "temperature"))[2003] is not None) is valid


def test_runs_are_counted_in_their_month_so_two_short_ones_over_the_turn_of_a_month_count() -> None:
    """Test 3 missing days at the end of January and 3 at the start of February are two runs of 3, not one of 6."""
    year = _year(2004)
    gone = [dt.date(2004, 1, 29), dt.date(2004, 1, 30), dt.date(2004, 1, 31), dt.date(2004, 2, 1), dt.date(2004, 2, 2)]
    frame = _temperature(_without(year, *gone))
    assert _values(annual_from_daily(frame, "temperature"))[2004] == 5.0


def test_missing_days_of_a_month_are_counted_by_the_month_not_the_year() -> None:
    """Test 10 missing days in each of two months are fine: the limit is a month's."""
    year = _year(2005)
    gone = [day for month in (3, 4) for day in [d for d in year if d.month == month][::2][:10]]
    assert _values(annual_from_daily(_temperature(_without(year, *gone)), "temperature"))[2005] == 5.0


def test_a_year_needs_all_12_months_and_a_failed_year_is_a_gap_between_the_others() -> None:
    """Test one month that fails makes the year a gap, which is a row with no value, not a missing row."""
    days = _year(2000) + _year(2001) + _year(2002)
    # 2001 loses 11 days of a month
    frame = _temperature(_without(days, *[day for day in _year(2001) if day.month == 8][:11]))
    assert _values(annual_from_daily(frame, "temperature")) == {2000: 5.0, 2001: None, 2002: 5.0}


def test_a_year_with_no_day_at_all_between_the_others_is_a_gap() -> None:
    """Test a year the station has no row for is a row of no value, so that the stripes show the hole."""
    frame = _temperature(_year(1990) + _year(1993))
    assert _values(annual_from_daily(frame, "temperature")) == {1990: 5.0, 1991: None, 1992: None, 1993: 5.0}


def test_the_years_a_record_does_not_cover_whole_are_gaps() -> None:
    """Test a record that starts in July, or has not reached December, has no value for its first and last year."""
    days = _days(dt.date(1999, 7, 1), dt.date(2002, 9, 30))
    assert _values(annual_from_daily(_temperature(days), "temperature")) == {
        1999: None,
        2000: 5.0,
        2001: 5.0,
        2002: None,
    }


def test_the_years_after_the_last_row_are_not_made_up() -> None:
    """Test the answer ends at the year of the last row, and starts at the year of the first."""
    frame = _temperature(_year(2010) + _year(2011))
    assert list(_values(annual_from_daily(frame, "temperature"))) == [2010, 2011]


@pytest.mark.parametrize(
    ("count", "valid"),
    [pytest.param(10, True, id="ten"), pytest.param(11, False, id="eleven")],
)
def test_a_value_that_is_no_number_is_a_missing_day(count: int, valid: bool) -> None:  # noqa: FBT001
    """Test null, NaN and an infinity make no day: 10 of them are a valid month, 11 are not."""
    year = _year(2006)
    march = [day for day in year if day.month == 3][::2]
    bad = [None, math.nan, math.inf]
    tmax = _frame(
        TEMPERATURE_MAX, year, dict.fromkeys(year, 10.0) | {day: bad[n % 3] for n, day in enumerate(march[:count])}
    )
    frame = pl.concat([tmax, _frame(TEMPERATURE_MIN, year, 0.0)])
    assert (_values(annual_from_daily(frame, "temperature"))[2006] is not None) is valid


def test_a_precipitation_month_counts_only_when_every_day_has_a_value() -> None:
    """Test one missing day fails the month, and the year with it, which the temperature would have taken."""
    year = _year(2007)
    complete = _frame(PRECIPITATION, year, 2.0)
    assert _values(annual_from_daily(complete, "precipitation")) == {2007: pytest.approx(2.0 * 365)}
    one_gone = _frame(PRECIPITATION, _without(year, dt.date(2007, 5, 17)), 2.0)
    assert _values(annual_from_daily(one_gone, "precipitation")) == {2007: None}
    # the same day on the temperature side is a valid month
    assert _values(annual_from_daily(_temperature(_without(year, dt.date(2007, 5, 17))), "temperature")) == {2007: 5.0}


def test_a_precipitation_year_is_the_sum_of_the_monthly_sums_and_a_dry_day_is_a_value() -> None:
    """Test the sum of the 12 months, with the days of 0 mm counting as measured."""
    year = _year(2008)
    # 1 mm on the first day of each month, 0 on all others
    firsts = {day: (1.0 if day.day == 1 else 0.0) for day in year}
    assert _values(annual_from_daily(_frame(PRECIPITATION, year, firsts), "precipitation")) == {2008: 12.0}


def test_a_precipitation_value_that_is_null_is_a_missing_day() -> None:
    """Test a day that is in the file with no value fails the month, as a day that is not in it does."""
    year = _year(2009)
    frame = _frame(PRECIPITATION, year, dict.fromkeys(year, 1.0) | {dt.date(2009, 2, 3): None})
    assert _values(annual_from_daily(frame, "precipitation")) == {2009: None}


def test_the_kinds_read_their_own_parameters_only() -> None:
    """Test the temperature does not read a precipitation and the precipitation not a temperature."""
    year = _year(2010)
    frame = pl.concat([_temperature(year), _frame(PRECIPITATION, year, 1.0)])
    assert _values(annual_from_daily(frame, "temperature")) == {2010: 5.0}
    assert _values(annual_from_daily(frame, "precipitation")) == {2010: 365.0}
    assert annual_from_daily(_temperature(year), "precipitation").is_empty()
    assert annual_from_daily(_frame(PRECIPITATION, year, 1.0), "temperature").is_empty()


def test_no_days_are_no_years() -> None:
    """Test a station with no rows gives an empty frame of the schema, which the stripes refuse as having no data."""
    empty = pl.DataFrame(
        schema={"timestamp": pl.Datetime("us", "UTC"), "parameter": pl.String, "value": pl.Float64},
    )
    for kind in ("temperature", "precipitation"):
        frame = annual_from_daily(empty, kind)
        assert frame.is_empty()
        assert frame.schema == pl.Schema({"timestamp": pl.Datetime("us", "UTC"), "value": pl.Float64})


def test_a_year_is_rounded_to_three_decimals() -> None:
    """Test the mean of tenths does not come out as a float's tail."""
    year = _year(2011)
    frame = pl.concat([_frame(TEMPERATURE_MAX, year, 10.1), _frame(TEMPERATURE_MIN, year, 0.2)])
    (value,) = annual_from_daily(frame, "temperature").get_column("value").to_list()
    assert value == 5.15


@pytest.mark.parametrize(
    ("flags", "kept"),
    [
        pytest.param(None, True, id="no-flag"),
        pytest.param("source:S", True, id="only-a-source"),
        pytest.param("measurement:H,source:S", True, id="measurement-and-source"),
        pytest.param("raw:-9999", True, id="raw-text-of-a-sentinel"),
        pytest.param("G", False, id="failed-a-check"),
        pytest.param("G,source:S", False, id="failed-a-check-and-a-source"),
        pytest.param("measurement:H,I,source:S", False, id="failed-after-a-measurement-flag"),
    ],
)
def test_a_value_that_failed_a_check_of_the_source_is_left_out(flags: str | None, kept: bool) -> None:  # noqa: FBT001
    """Test only a plain code in `quality_flags`, the source's QFLAG, takes the value: the other tokens say how."""
    frame = pl.DataFrame(
        {"value": [3.0], "quality_flags": [flags]}, schema={"value": pl.Float64, "quality_flags": pl.String}
    )
    assert leave_out_failed(frame).get_column("value").to_list() == [3.0 if kept else None]


def test_a_frame_without_quality_flags_is_kept_as_it_is() -> None:
    """Test a source that gives no flags leaves its values alone."""
    frame = pl.DataFrame({"value": [1.0]})
    assert leave_out_failed(frame).equals(frame)


@pytest.mark.parametrize(
    ("kind", "method"),
    [("temperature", "midrange"), ("temperature", "tavg"), ("precipitation", None)],
)
def test_the_note_says_the_rules_in_ascii(
    kind: Literal["temperature", "precipitation"], method: Literal["midrange", "tavg"] | None
) -> None:
    """Test the sentence names the standard, the rule of the kind, the method and that a year that fails is a gap."""
    note = annual_note(kind, method)
    assert note.isascii()
    assert "WMO-No. 1203" in note
    assert "a year that fails is a gap" in note
    if kind == "precipitation":
        assert "only when complete" in note
        assert "sum of its monthly sums" in note
        return
    assert "at most 10 days missing and at most 4 in a row" in note
    assert "mean of its monthly means" in note
    if method == "midrange":
        assert "a day is the midrange of TMAX and TMIN, which is no 24-hour mean" in note
        assert "(TAVG is not used)" in note
    else:
        assert "a day is the source's TAVG, as the station has no day with both TMAX and TMIN" in note
