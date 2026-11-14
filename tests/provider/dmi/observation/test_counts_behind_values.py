# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The count behind a DMI value: the token `n:<count>` and the check `source` of a value of too few readings (GH-4027).

Every record of DMI's `stationValue` answer carries `noValuesInCalculation`, the number of readings an aggregate was
computed from. For Greenland and the Faroe Islands DMI computes a value from however many exist, even one (DMI customer
service, 2026-11-12), so the reader serves the count as the token `n:<count>` and the core judges a daily value of
fewer than 4 readings (half of the 8 three-hourly synoptic readings of the days of Greenland before the automation,
which DMI marks valid; modern days have 24 hourly), a monthly one of fewer than 14 and a yearly one of fewer than 183
(half of the shortest period) as the check `source` does a `validity:false`: `suspect:source`, null in the mode `hard`.

The daily records are those of 04219 (Qeqertarsuaq Heliport, `mean_vapour_pressure`) that the issue names (read key-less
2026-11-12 by DMI customer service and the maintainer): 2026-01-08 0.0 with `validity:false` from 1 value, 2026-03-03
16.8 with `validity:true` from 2, 2026-04-20 0.0 with `validity:false` from 7. The others are made up, to hold the
threshold on both sides of it; the `n:8` days stand for 04360 (Tasiilaq) of 1975, 1995 and 2005, which DMI marks valid.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import TYPE_CHECKING

from tests.provider.dmi.observation import country_of
from tests.provider.value_stubs import _settings, serve, stations_result
from wetterdienst.model.source_flags import SOURCE_COUNTS, flags_of
from wetterdienst.options import Options
from wetterdienst.provider.dmi.observation import DmiObservationRequest
from wetterdienst.provider.dmi.observation import api as dmi_api
from wetterdienst.provider.dmi.observation.metadata import DmiObservationMetadata

if TYPE_CHECKING:
    import pytest

_UTC = dt.UTC
_STATION = "04219"
_VAPOUR = "mean_vapour_pressure"


def _record(
    parameter: str, start: str, end: str, value: float, count: int | None, *, valid: bool = True
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


def _day(day: str, parameter: str, value: float, count: int | None, *, valid: bool = True) -> dict[str, object]:
    """Give a day of Greenland, from 06:00 UTC of the date to 06:00 UTC of the next."""
    start = dt.date.fromisoformat(day)
    end = start + dt.timedelta(days=1)
    return _record(parameter, f"{start}T06:00:00.001000+00:00", f"{end}T06:00:00+00:00", value, count, valid=valid)


def _read(
    monkeypatch: pytest.MonkeyPatch,
    resolution: str,
    records: list[dict[str, object]],
    *,
    plausibility: dict[str, str] | None = None,
) -> dict[tuple[str, str], tuple[float | None, str | None]]:
    """Read records through the reader and the core, as `{(parameter, date): (value, quality_flags)}`."""
    serve(
        monkeypatch, dmi_api, {"stationValue": json.dumps({"features": [{"properties": r} for r in records]}).encode()}
    )
    request = DmiObservationRequest(
        parameters=[(resolution, "data")],
        start=dt.datetime(1970, 1, 1, tzinfo=_UTC),
        end=dt.datetime(2026, 12, 31, tzinfo=_UTC),
        settings=_settings(),
        options=Options(drop_nulls=False, plausibility=plausibility or {}),
    )
    df = stations_result(request, resolution, "data", _STATION, country=country_of(_STATION)).values().all().df
    return {
        (row["parameter"], row["timestamp"].date().isoformat()): (row["value"], row["quality_flags"])
        for row in df.iter_rows(named=True)
    }


_DAYS = [
    _day("2026-01-08", _VAPOUR, 0.0, 1, valid=False),
    _day("2026-03-03", _VAPOUR, 16.8, 2),
    _day("2026-04-20", _VAPOUR, 0.0, 7, valid=False),
    # a full day, a day of the 8 synoptic readings that older Greenland days are computed from (valid, not suspect),
    # the last count that is half of them, and the one below
    _day("2026-03-05", _VAPOUR, 4.1, 24),
    _day("2026-03-06", _VAPOUR, 4.2, 8),
    _day("2026-03-07", _VAPOUR, 4.0, 4),
    _day("2026-03-09", _VAPOUR, 4.3, 3),
    # the days of 04360 before the automation: the mean temperature of 8 readings, valid
    _day("1975-06-01", "mean_temp", 2.1, 8),
    _day("1975-06-02", "mean_temp", 2.6, 8),
    # DMI wrote no count
    _day("2026-03-08", _VAPOUR, 3.9, None),
    # the snow depth is read by hand once a day: its count is not the hours of the day, so it is not judged by it
    _day("2026-03-03", "snow_depth", 12.0, 1),
]


def test_the_count_is_a_token_of_the_quality_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    """The count follows `validity` as `n:<count>`, and a record without one has no token."""
    found = _read(monkeypatch, "daily", _DAYS, plausibility={"source": "soft"})
    flags = {key[1]: flags for key, (_, flags) in found.items() if key[0] == "pressure_vapor_mean"}
    assert flags["2026-03-05"] == "manual,validity:true,n:24"
    assert flags["2026-03-06"] == "manual,validity:true,n:8"
    assert flags["2026-03-08"] == "manual,validity:true"


def test_a_day_of_fewer_than_4_readings_is_suspect_and_a_synoptic_day_is_not(monkeypatch: pytest.MonkeyPatch) -> None:
    """2026-03-03 of 04219, 16.8 hPa `validity:true` from 2 values, is `suspect:source`; 4, 8 and 24 values are not."""
    found = _read(monkeypatch, "daily", _DAYS)
    vapour = {key[1]: row for key, row in found.items() if key[0] == "pressure_vapor_mean"}
    assert vapour["2026-03-03"] == (16.8, "manual,validity:true,n:2,suspect:source")
    assert vapour["2026-03-09"] == (4.3, "manual,validity:true,n:3,suspect:source")
    assert vapour["2026-03-07"] == (4.0, "manual,validity:true,n:4")
    # a day of 8 synoptic readings is a valid day of the old Greenland data, not a suspect one
    assert vapour["2026-03-06"] == (4.2, "manual,validity:true,n:8")
    assert found[("temperature_air_mean_2m", "1975-06-01")] == (2.1, "manual,validity:true,n:8")
    assert found[("temperature_air_mean_2m", "1975-06-02")] == (2.6, "manual,validity:true,n:8")
    assert vapour["2026-03-05"] == (4.1, "manual,validity:true,n:24")
    assert vapour["2026-03-08"] == (3.9, "manual,validity:true")
    # `validity:false` is judged as before, and the count is told beside it
    assert vapour["2026-01-08"] == (0.0, "manual,validity:false,n:1,suspect:source")
    assert vapour["2026-04-20"] == (0.0, "manual,validity:false,n:7,suspect:source")
    # the count of a manual reading is not read as the hours of the day
    assert found[("snow_depth_manual", "2026-03-03")] == (12.0, "manual,validity:true,n:1")


def test_the_mode_hard_of_source_nulls_a_value_of_too_few_readings_and_keeps_its_number(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With `plausibility={"source": "hard"}` the 16.8 hPa of 2 values is null, `rejected:source,raw:16.8`."""
    found = _read(monkeypatch, "daily", _DAYS, plausibility={"source": "hard"})
    vapour = {key[1]: row for key, row in found.items() if key[0] == "pressure_vapor_mean"}
    assert vapour["2026-03-03"] == (None, "manual,validity:true,n:2,rejected:source,raw:16.8")
    assert vapour["2026-03-06"] == (4.2, "manual,validity:true,n:8")
    assert found[("temperature_air_mean_2m", "1975-06-01")] == (2.1, "manual,validity:true,n:8")
    assert found[("snow_depth_manual", "2026-03-03")] == (12.0, "manual,validity:true,n:1")


def test_the_default_drops_nothing_and_the_hard_mode_drops_the_value_with_the_null_dropping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A value of 2 readings is in the answer by default (soft) and out of it, null-dropped, in the mode `hard`."""
    serve(
        monkeypatch,
        dmi_api,
        {"stationValue": json.dumps({"features": [{"properties": _DAYS[1]}]}).encode()},
    )
    for plausibility, rows in (({}, 1), ({"source": "hard"}, 0)):
        request = DmiObservationRequest(
            parameters=[("daily", "data")],
            start=dt.datetime(2026, 3, 1, tzinfo=_UTC),
            end=dt.datetime(2026, 3, 31, tzinfo=_UTC),
            settings=_settings(),
            options=Options(plausibility=plausibility),
        )
        df = stations_result(request, "daily", "data", _STATION, country="GRL").values().all().df
        assert df.height == rows, plausibility


def _month(month: str, value: float, count: int | None) -> dict[str, object]:
    year, number = (int(part) for part in month.split("-"))
    start = f"{year}-{number:02d}-01T00:00:00.001000-03:00"
    end = f"{year + (number == 12)}-{number % 12 + 1:02d}-01T00:00:00-03:00"
    return _record(_VAPOUR, start, end, value, count)


def test_a_month_of_fewer_than_14_days_is_suspect(monkeypatch: pytest.MonkeyPatch) -> None:
    """The monthly 16.8 hPa of 2026-03 of 04219 is from 1 value: suspect. 14 days, half a short month, are not."""
    records = [_month("2026-03", 16.8, 1), _month("2026-04", 5.0, 13), _month("2026-05", 5.1, 14)]
    found = _read(monkeypatch, "monthly", records)
    assert found[("pressure_vapor_mean", "2026-03-01")] == (16.8, "manual,validity:true,n:1,suspect:source")
    assert found[("pressure_vapor_mean", "2026-04-01")] == (5.0, "manual,validity:true,n:13,suspect:source")
    assert found[("pressure_vapor_mean", "2026-05-01")] == (5.1, "manual,validity:true,n:14")


def test_a_year_of_fewer_than_183_days_is_suspect(monkeypatch: pytest.MonkeyPatch) -> None:
    """183 days are half of the 365 of the shortest year: a year of 182 is suspect, one of 183 or 365 is not."""
    records = [
        _record(_VAPOUR, f"{year}-01-01T00:00:00.001000-03:00", f"{year + 1}-01-01T00:00:00-03:00", 5.0, count)
        for year, count in ((2023, 182), (2024, 183), (2025, 365))
    ]
    found = _read(monkeypatch, "annual", records)
    assert found[("pressure_vapor_mean", "2023-01-01")] == (5.0, "manual,validity:true,n:182,suspect:source")
    assert found[("pressure_vapor_mean", "2024-01-01")] == (5.0, "manual,validity:true,n:183")
    assert found[("pressure_vapor_mean", "2025-01-01")] == (5.0, "manual,validity:true,n:365")


def test_an_hourly_value_carries_its_count_and_is_not_judged_by_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """An hourly mean temperature of one reading has the token and is not judged by it."""
    record = _record("mean_temp", "2026-03-03T10:00:00+00:00", "2026-03-03T11:00:00+00:00", -4.2, 1)
    found = _read(monkeypatch, "hourly", [record])
    assert found[("temperature_air_mean_2m", "2026-03-03")] == (-4.2, "manual,validity:true,n:1")


def test_the_rules_name_the_parameters_the_dataset_declares() -> None:
    """Every parameter of a rule is a canonical name of its dataset, so a rename cannot leave a rule without effect."""
    for rule in SOURCE_COUNTS["dmi/observation"]:
        for dataset_name in rule.datasets:
            resolution, name = dataset_name.split("/")
            declared = {p.name for p in DmiObservationMetadata[resolution][name].parameters}
            assert set(rule.parameters) <= declared, (dataset_name, sorted(set(rule.parameters) - declared))
            assert flags_of("dmi/observation", dataset_name)[-1] is rule
