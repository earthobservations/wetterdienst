# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DMI serves the month and the year still running as the value of the month and the year (GH-4087).

Read key-less on 2026-11-15: the annual `mean_temp` of 06180 for 2026 from 319 days, the monthly one of November from
15 days, both `validity: true` and `qcStatus: none` (not controlled yet), so nothing in the record says that the
period is running. The maintainer decided (2026-11-15), as for `metno/frost` (GH-3883), that `values` returns the
value marked `completeness:Incomplete` in `quality_flags` and that `interpolate` and `summarize` leave it out and
say so.

A period ends at the `to` of its record, which carries the offset of the place (`+01:00` at the Danish 06180, `+00:00`
and 06:00 at the Greenland 04220). The time of the request is `dmi_api._now`, which these tests set.
"""

from __future__ import annotations

import datetime as dt
import json

import polars as pl
import pytest

from tests.provider.dmi.observation import country_of
from tests.provider.value_stubs import _settings, serve, stations_result
from wetterdienst.model.parameter_rows import EstimateLeftOut
from wetterdienst.options import Options
from wetterdienst.provider.dmi.observation import DmiObservationRequest
from wetterdienst.provider.dmi.observation import api as dmi_api
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

UTC = dt.UTC
CODE = "window-not-closed"
DANISH = "06180"
GREENLAND = "04220"
#: November 2026 and the year 2026 are running, October 2026 and 2025 have ended
NOW = dt.datetime(2026, 11, 15, 15, 0, tzinfo=UTC)
CLOSED, RUNNING = 5.0, 9.0


def _record(
    parameter: str, start: str, end: str, value: float, count: int | None = 15, *, valid: bool = True
) -> dict[str, object]:
    record: dict[str, object] = {
        "parameterId": parameter,
        "from": start,
        "to": end,
        "value": value,
        "qcStatus": "manual",
        "validity": valid,
    }
    if count is not None:
        record["noValuesInCalculation"] = count
    return record


def _month(year: int, month: int, value: float, count: int | None = 28, parameter: str = "mean_temp") -> dict:
    """Give a month of a Danish station, from its local midnight to the next (`+01:00`, the winter offset)."""
    following = dt.date(year + (month == 12), month % 12 + 1, 1)
    return _record(
        parameter, f"{year}-{month:02d}-01T00:00:00.001000+01:00", f"{following}T00:00:00+01:00", value, count
    )


def _year(year: int, value: float, count: int | None = 365, parameter: str = "mean_temp") -> dict:
    return _record(parameter, f"{year}-01-01T00:00:00.001000+01:00", f"{year + 1}-01-01T00:00:00+01:00", value, count)


def _day(day: dt.date, value: float, end: str | None = None) -> dict:
    following = day + dt.timedelta(days=1)
    return _record("mean_temp", f"{day}T00:00:00.001000+01:00", end or f"{following}T00:00:00+01:00", value, 24)


def _at(monkeypatch: pytest.MonkeyPatch, moment: dt.datetime) -> None:
    """Serve the requests of the test at `moment`."""
    monkeypatch.setattr(dmi_api, "_now", lambda: moment)


def _request(
    monkeypatch: pytest.MonkeyPatch,
    resolution: str,
    records: list[dict[str, object]],
    start: dt.datetime,
    end: dt.datetime,
) -> DmiObservationRequest:
    serve(
        monkeypatch, dmi_api, {"stationValue": json.dumps({"features": [{"properties": r} for r in records]}).encode()}
    )
    return DmiObservationRequest(
        parameters=[(resolution, "data", "temperature_air_mean_2m")],
        start=start,
        end=end,
        settings=_settings(),
        options=Options(drop_nulls=False),
    )


def _read(
    monkeypatch: pytest.MonkeyPatch,
    resolution: str,
    records: list[dict[str, object]],
    *,
    station: str = DANISH,
    start: dt.datetime = dt.datetime(2024, 1, 1, tzinfo=UTC),
    end: dt.datetime = dt.datetime(2026, 12, 31, tzinfo=UTC),
) -> dict[dt.date, tuple[float | None, str | None]]:
    """Read the records through the reader and the core as `{date: (value, quality_flags)}`."""
    request = _request(monkeypatch, resolution, records, start, end)
    result = stations_result(request, resolution, "data", station, country=country_of(station))
    return {
        row["timestamp"].date(): (row["value"], row["quality_flags"])
        for row in result.values().all().df.iter_rows(named=True)
    }


MONTHS = [_month(2026, 10, CLOSED), _month(2026, 11, RUNNING, 15)]
YEARS = [_year(2025, CLOSED), _year(2026, RUNNING, 319)]
OCTOBER, NOVEMBER = dt.date(2026, 10, 1), dt.date(2026, 11, 1)
Y2025, Y2026 = dt.date(2025, 1, 1), dt.date(2026, 1, 1)


# --- values: the period that has not ended is returned and marked ----------------------------------------------------


@pytest.mark.parametrize(
    ("resolution", "records", "closed", "running", "closed_flags", "running_flags"),
    [
        pytest.param(
            "monthly",
            MONTHS,
            OCTOBER,
            NOVEMBER,
            "manual,validity:true,n:28",
            "manual,validity:true,n:15,completeness:Incomplete",
            id="monthly",
        ),
        pytest.param(
            "annual",
            YEARS,
            Y2025,
            Y2026,
            "manual,validity:true,n:365",
            "manual,validity:true,n:319,completeness:Incomplete",
            id="annual",
        ),
    ],
)
def test_the_running_month_and_year_are_marked_and_a_closed_one_is_not(
    monkeypatch: pytest.MonkeyPatch,
    resolution: str,
    records: list[dict[str, object]],
    closed: dt.date,
    running: dt.date,
    closed_flags: str,
    running_flags: str,
) -> None:
    """The value stays in the answer, after the count and before `raw`, and a closed period has no token."""
    _at(monkeypatch, NOW)
    begin_response()

    found = _read(monkeypatch, resolution, records)

    assert found[closed] == (CLOSED, closed_flags)
    assert found[running] == (RUNNING, running_flags)


@pytest.mark.parametrize(
    ("resolution", "records", "running"), [("monthly", MONTHS, NOVEMBER), ("annual", YEARS, Y2026)]
)
def test_the_warning_counts_the_marked_values_and_says_when_the_period_ends(
    monkeypatch: pytest.MonkeyPatch, resolution: str, records: list[dict[str, object]], running: dt.date
) -> None:
    """One `window-not-closed` for the parameter, `returned`: the value is in the answer, marked."""
    _at(monkeypatch, NOW)
    begin_response()

    _read(monkeypatch, resolution, records)

    (warning,) = [w for w in recorded_warnings() if w["code"] == CODE]
    assert warning["parameter"] == f"{resolution}/data/temperature_air_mean_2m"
    assert warning["stations"] == [DANISH]
    message = warning["message"]
    assert f"1 value of {resolution}/data/temperature_air_mean_2m ({DANISH} 1)" in message
    assert "in the answer, marked `completeness:Incomplete`" in message
    end = (
        f"{running.year + (running.month == 12)}-{running.month % 12 + 1:02d}-01"
        if resolution == "monthly"
        else f"{running.year + 1}-01-01"
    )
    # the end is the local midnight, which is 23:00 UTC of the day before
    assert f"closes at {(dt.date.fromisoformat(end) - dt.timedelta(days=1)):%Y-%m-%d} 23:00 UTC" in message


@pytest.mark.parametrize(("resolution", "records"), [("monthly", MONTHS), ("annual", YEARS)])
def test_a_request_after_the_period_ended_marks_nothing_and_says_nothing(
    monkeypatch: pytest.MonkeyPatch, resolution: str, records: list[dict[str, object]]
) -> None:
    """The same records read after the end of the year are closed."""
    _at(monkeypatch, dt.datetime(2027, 1, 1, 0, 0, tzinfo=UTC) + dt.timedelta(days=1))
    begin_response()

    found = _read(monkeypatch, resolution, records)

    assert all(flags is None or "completeness" not in flags for _, flags in found.values())
    assert [w for w in recorded_warnings() if w["code"] == CODE] == []


# --- the boundary instant ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("moment", "marked"),
    [
        # the `to` of November at 06180 is 2026-12-01T00:00:00+01:00, 23:00 UTC on 30 November
        pytest.param(dt.datetime(2026, 11, 30, 22, 59, 59, 999999, tzinfo=UTC), True, id="a microsecond before"),
        pytest.param(dt.datetime(2026, 11, 30, 23, 0, tzinfo=UTC), False, id="at the instant"),
        pytest.param(dt.datetime(2026, 11, 30, 23, 0, 0, 1, tzinfo=UTC), False, id="a microsecond after"),
        # the civil midnight is not UTC midnight: 23:30 UTC on the 30th is already December in Copenhagen
        pytest.param(dt.datetime(2026, 11, 30, 23, 30, tzinfo=UTC), False, id="after the local midnight"),
    ],
)
def test_a_month_has_ended_at_its_to_and_not_before(
    monkeypatch: pytest.MonkeyPatch, moment: dt.datetime, *, marked: bool
) -> None:
    """The period ends at the instant of `to`, with its offset: at that instant it is closed."""
    _at(monkeypatch, moment)

    flags = _read(monkeypatch, "monthly", MONTHS)[NOVEMBER][1]

    assert ("completeness:Incomplete" in flags) is marked


def test_a_greenland_month_ends_at_0600_utc_and_not_at_the_midnight_of_the_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """04220 counts its days from 06:00 UTC: on 1 December at 03:00 UTC the month of November is still running."""
    november = _record("mean_temp", "2026-11-01T06:00:00+00:00", "2026-12-01T06:00:00+00:00", RUNNING, 30)
    _at(monkeypatch, dt.datetime(2026, 12, 1, 3, 0, tzinfo=UTC))
    assert "completeness:Incomplete" in _read(monkeypatch, "monthly", [november], station=GREENLAND)[NOVEMBER][1]

    _at(monkeypatch, dt.datetime(2026, 12, 1, 6, 0, tzinfo=UTC))
    assert "completeness" not in _read(monkeypatch, "monthly", [november], station=GREENLAND)[NOVEMBER][1]


def test_a_copy_of_the_answer_made_before_the_period_ended_is_not_final(monkeypatch: pytest.MonkeyPatch) -> None:
    """The answer is cached for five minutes: one made at 22:58 UTC is no final value for the request of 23:01."""
    _at(monkeypatch, dt.datetime(2026, 11, 30, 23, 1, tzinfo=UTC))
    request = _request(
        monkeypatch, "monthly", MONTHS, dt.datetime(2026, 10, 1, tzinfo=UTC), dt.datetime(2026, 12, 31, tzinfo=UTC)
    )
    download = dmi_api.download_file

    def cached(**kwargs: object) -> object:
        file = download(**kwargs)
        file.cached_at = dt.datetime(2026, 11, 30, 22, 58, tzinfo=UTC).timestamp()
        return file

    monkeypatch.setattr(dmi_api, "download_file", cached)
    result = stations_result(request, "monthly", "data", DANISH, country="DNK")

    flags = result.values().all().df.filter(pl.col("timestamp").dt.date() == NOVEMBER)["quality_flags"].to_list()

    assert "completeness:Incomplete" in flags[0]


# --- the other resolutions and the other tokens -----------------------------------------------------------------------


@pytest.mark.parametrize("resolution", ["daily", "hourly"])
def test_a_daily_and_an_hourly_value_are_not_judged(monkeypatch: pytest.MonkeyPatch, resolution: str) -> None:
    """The day of the request has a `to` after now, and is read as it was: no token, no warning."""
    _at(monkeypatch, NOW)
    begin_response()
    if resolution == "daily":
        records = [_day(dt.date(2026, 11, 14), CLOSED), _day(dt.date(2026, 11, 15), RUNNING)]
    else:
        records = [
            _record("mean_temp", "2026-11-15T14:00:00+00:00", "2026-11-15T15:00:00+00:00", RUNNING, 6),
            _record("mean_temp", "2026-11-15T16:00:00+00:00", "2026-11-15T17:00:00+00:00", RUNNING, 6),
        ]

    found = _read(
        monkeypatch,
        resolution,
        records,
        start=dt.datetime(2026, 11, 14, tzinfo=UTC),
        end=dt.datetime(2026, 11, 16, tzinfo=UTC),
    )

    assert found
    assert all("completeness" not in (flags or "") for _, flags in found.values())
    assert [w for w in recorded_warnings() if w["code"] == CODE] == []


def test_the_mark_comes_before_the_raw_text_and_after_the_count(monkeypatch: pytest.MonkeyPatch) -> None:
    """DMI's 999 snow depth of a running month is null, keeps `raw:999` last and the mark before it."""
    snow = _record("max_snow_depth", "2026-11-01T00:00:00.001000+01:00", "2026-12-01T00:00:00+01:00", 999.0, 15)
    _at(monkeypatch, NOW)
    request = DmiObservationRequest(
        parameters=[("monthly", "data", "snow_depth_max")],
        start=dt.datetime(2026, 11, 1, tzinfo=UTC),
        end=dt.datetime(2026, 11, 30, tzinfo=UTC),
        settings=_settings(),
        options=Options(drop_nulls=False),
    )
    serve(monkeypatch, dmi_api, {"stationValue": json.dumps({"features": [{"properties": snow}]}).encode()})

    df = stations_result(request, "monthly", "data", DANISH, country="DNK").values().all().df

    assert df["quality_flags"].to_list() == ["manual,validity:true,n:15,completeness:Incomplete,raw:999"]
    assert df["value"].to_list() == [None]


def test_a_record_without_a_count_is_marked_all_the_same(monkeypatch: pytest.MonkeyPatch) -> None:
    """The mark does not depend on the count token being there."""
    _at(monkeypatch, NOW)

    flags = _read(monkeypatch, "monthly", [_month(2026, 11, RUNNING, None)])[NOVEMBER][1]

    assert flags == "manual,validity:true,completeness:Incomplete"


# --- the count is not judged where the period is partial -------------------------------------------------------------


@pytest.mark.parametrize(
    ("resolution", "running", "closed", "count"),
    [
        pytest.param("monthly", _month(2026, 11, RUNNING, 5), _month(2026, 10, CLOSED, 5), 5, id="monthly: 5 days"),
        pytest.param("annual", _year(2026, RUNNING, 100), _year(2025, CLOSED, 100), 100, id="annual: 100 days"),
    ],
)
def test_a_running_period_is_not_suspect_for_its_count_and_a_closed_one_is(
    monkeypatch: pytest.MonkeyPatch, resolution: str, running: dict, closed: dict, count: int
) -> None:
    """A month of 5 readings or a year of 100 is `suspect:source` once it has ended, and no gap while it is running."""
    _at(monkeypatch, NOW)

    found = _read(monkeypatch, resolution, [closed, running])

    first, second = (OCTOBER, NOVEMBER) if resolution == "monthly" else (Y2025, Y2026)
    assert found[first][1] == f"manual,validity:true,n:{count},suspect:source"
    assert found[second][1] == f"manual,validity:true,n:{count},completeness:Incomplete"
    assert found[second][0] == RUNNING


def test_a_running_period_stays_in_the_hard_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """The check `source` in the mode `hard` nulls the closed year of 100 readings, not the one still running."""
    _at(monkeypatch, NOW)
    request = _request(
        monkeypatch,
        "annual",
        [_year(2025, CLOSED, 100), _year(2026, RUNNING, 100)],
        dt.datetime(2025, 1, 1, tzinfo=UTC),
        dt.datetime(2026, 12, 31, tzinfo=UTC),
    )
    request = DmiObservationRequest(
        parameters=request.parameters,
        start=request.start,
        end=request.end,
        settings=_settings(),
        options=Options(drop_nulls=False, plausibility={"source": "hard"}),
    )

    df = stations_result(request, "annual", "data", DANISH, country="DNK").values().all().df

    assert df.sort("timestamp")["value"].to_list() == [None, RUNNING]


# --- estimates leave the marked value out and say so ------------------------------------------------------------------


@pytest.mark.parametrize(
    ("resolution", "records", "running"), [("monthly", MONTHS, NOVEMBER), ("annual", YEARS, Y2026)]
)
def test_an_estimate_leaves_the_running_value_out_and_tells_it(
    monkeypatch: pytest.MonkeyPatch, resolution: str, records: list[dict[str, object]], running: dt.date
) -> None:
    """A reader that an estimate drives (`_left_out_of_estimate`) returns the closed period alone and tells the rest."""
    _at(monkeypatch, NOW)
    request = _request(
        monkeypatch, resolution, records, dt.datetime(2024, 1, 1, tzinfo=UTC), dt.datetime(2026, 12, 31, tzinfo=UTC)
    )
    values = stations_result(request, resolution, "data", DANISH, country="DNK").values()
    left_out = EstimateLeftOut()
    values._left_out_of_estimate = left_out  # noqa: SLF001
    values._warn_without_rows = False  # noqa: SLF001
    begin_response()

    df = values.all().df
    left_out.warn()

    assert running not in {row.date() for row in df["timestamp"]}
    assert CLOSED in df["value"].to_list()
    assert RUNNING not in df["value"].to_list()
    (warning,) = recorded_warnings()
    assert warning["code"] == "source-data-left-out"
    assert "was of a window that had not closed yet" in warning["message"]
    assert "for this month" in warning["message"] if resolution == "monthly" else "for this year" in warning["message"]


def _summarize(monkeypatch: pytest.MonkeyPatch, resolution: str, records: list[dict[str, object]]) -> pl.DataFrame:
    """Summarize the parameter at a point beside 06180 from a catalogue of that station alone."""
    station = {
        "geometry": {"coordinates": [12.5, 55.6]},
        "properties": {
            "stationId": DANISH,
            "name": "Kastrup",
            "country": "DNK",
            "wmoStationId": DANISH,
            "stationHeight": 5.0,
            "validFrom": "1953-01-01T00:00:00Z",
            "validTo": None,
            "created": "2020-01-01T00:00:00Z",
        },
    }
    serve(
        monkeypatch,
        dmi_api,
        {
            "station/items": json.dumps({"features": [station]}).encode(),
            "stationValue": json.dumps({"features": [{"properties": r} for r in records]}).encode(),
        },
    )
    request = DmiObservationRequest(
        parameters=[(resolution, "data", "temperature_air_mean_2m")],
        start=dt.datetime(2025, 1, 1, tzinfo=UTC),
        end=dt.datetime(2026, 12, 31, tzinfo=UTC),
        settings=_settings(),
    )
    return request.summarize((55.61, 12.51)).df


@pytest.mark.parametrize(
    ("resolution", "records", "running"), [("monthly", MONTHS, NOVEMBER), ("annual", YEARS, Y2026)]
)
def test_summarize_takes_the_closed_value_and_none_of_the_running_one(
    monkeypatch: pytest.MonkeyPatch, resolution: str, records: list[dict[str, object]], running: dt.date
) -> None:
    """The partial value is not in the summary, and the answer tells that it was left out."""
    _at(monkeypatch, NOW)
    begin_response()

    df = _summarize(monkeypatch, resolution, records)

    values = {row["timestamp"].date(): row["value"] for row in df.iter_rows(named=True)}
    assert RUNNING not in values.values()
    assert values.get(running) is None
    assert CLOSED in values.values()
    (warning,) = recorded_warnings()
    assert warning["code"] == "source-data-left-out"
    assert "of a window that had not closed yet" in warning["message"]


def test_summarize_over_closed_periods_says_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Asked after the year ended, the summary has the value of 2026 and no warning."""
    _at(monkeypatch, dt.datetime(2027, 2, 1, tzinfo=UTC))
    begin_response()

    df = _summarize(monkeypatch, "annual", YEARS)

    assert RUNNING in df["value"].to_list()
    assert recorded_warnings() == []
