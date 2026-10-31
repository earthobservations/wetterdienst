# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The DMI sea level pressure extremes, summer days, tropical nights and heating degree days of GH-3622.

`published_extremes_counts_hdd.json` holds records of the `stationValue` collection as read key-less on 2026-10-31,
trimmed to the keys the reader uses:

- 04250 (Nuuk, Greenland): `max_pressure`, `min_pressure`, `mean_temp` and `acc_heating_degree_days_19` of the days
  2024-01-10 to 2024-01-12, and the pressure extremes, the heating degree days and the summer days of July 2023 and of
  2023;
- 06180 (Copenhagen airport, Denmark): `acc_heating_degree_days_17` and `mean_temp` of 2024-01-10 to 2024-01-12, the
  highest temperature of every day of July 2022, and the counts of days and heating degree days of that July, of July
  2023 and of 2023;
- 06070: the lowest temperature of every day of July 2018 and its count of tropical nights.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import polars as pl
import pytest

from tests.provider.value_stubs import _options, _settings, serve, stations_result
from wetterdienst.provider.dmi.observation import DmiObservationRequest
from wetterdienst.provider.dmi.observation import api as dmi_api
from wetterdienst.provider.dmi.observation.metadata import DmiObservationMetadata

_UTC = dt.UTC
_RECORDS = json.loads((Path(__file__).parent / "published_extremes_counts_hdd.json").read_text(encoding="utf8"))

# (resolution, DMI's parameterId) -> the canonical name and the unit it is declared in. The pressure extremes are the
# highest and lowest of the hourly values of `mean_pressure`, which is at sea level, so they are no
# `pressure_air_site_max`/`_min`; the counts are of the days past the threshold, which the names count from
_MAPPING = {
    ("daily", "max_pressure"): ("pressure_air_sea_level_max", "hectopascal"),
    ("daily", "min_pressure"): ("pressure_air_sea_level_min", "hectopascal"),
    ("monthly", "max_pressure"): ("pressure_air_sea_level_max", "hectopascal"),
    ("monthly", "min_pressure"): ("pressure_air_sea_level_min", "hectopascal"),
    ("annual", "max_pressure"): ("pressure_air_sea_level_max", "hectopascal"),
    ("annual", "min_pressure"): ("pressure_air_sea_level_min", "hectopascal"),
    ("monthly", "no_summer_days"): ("count_days_summer", "dimensionless"),
    ("monthly", "no_tropical_nights"): ("count_days_tropical_night", "dimensionless"),
    ("annual", "no_summer_days"): ("count_days_summer", "dimensionless"),
    ("annual", "no_tropical_nights"): ("count_days_tropical_night", "dimensionless"),
    ("daily", "acc_heating_degree_days_17"): ("heating_degree_day", "degree_celsius_day"),
    ("monthly", "acc_heating_degree_days_17"): ("heating_degree_day", "degree_celsius_day"),
    ("annual", "acc_heating_degree_days_17"): ("heating_degree_day", "degree_celsius_day"),
}


@pytest.mark.parametrize(("resolution", "parameter_id"), list(_MAPPING))
def test_a_published_parameter_is_mapped_to_the_name_of_its_statistic(resolution: str, parameter_id: str) -> None:
    """Each parameter of GH-3622 is declared with the canonical name of its statistic and DMI's unit."""
    parameters = {
        parameter.name_original: parameter for parameter in DmiObservationMetadata[resolution].datasets[0].parameters
    }
    assert (parameters[parameter_id].name, parameters[parameter_id].unit) == _MAPPING[(resolution, parameter_id)]


def test_the_hourly_resolution_has_neither_pressure_extremes_nor_counts_of_days() -> None:
    """DMI's calculation table gives the extremes "-" at the hour and the counts none: they start at the day."""
    hourly = {parameter.name_original for parameter in DmiObservationMetadata["hourly"].datasets[0].parameters}
    assert hourly & {"max_pressure", "min_pressure", "no_summer_days", "no_tropical_nights"} == set()


def test_the_heating_degree_days_of_greenland_are_not_a_second_parameter() -> None:
    """`acc_heating_degree_days_19` is read as the 17, so each resolution has one `heating_degree_day` (GH-3622)."""
    for resolution in ("daily", "monthly", "annual"):
        parameters = DmiObservationMetadata[resolution].datasets[0].parameters
        assert [parameter.name_original for parameter in parameters if parameter.name == "heating_degree_day"] == [
            "acc_heating_degree_days_17"
        ]
        assert "acc_heating_degree_days_19" not in {parameter.name_original for parameter in parameters}


def test_the_description_of_the_heating_degree_days_states_the_base_of_each_country() -> None:
    """The one parameter has a base per country, which its description states at every resolution."""
    for resolution in ("daily", "monthly", "annual"):
        parameters = DmiObservationMetadata[resolution].datasets[0].parameters
        description = next(parameter for parameter in parameters if parameter.name == "heating_degree_day").description
        assert "17 °C in Denmark" in description
        assert "19 °C in Greenland" in description


def _values(
    monkeypatch: pytest.MonkeyPatch,
    resolution: str,
    station: str,
    start: dt.datetime,
    end: dt.datetime,
    *,
    drop_nulls: bool = True,
    records: list[dict] | None = None,
) -> pl.DataFrame:
    """Collect the dataset of a resolution for a station from the records of `published_extremes_counts_hdd.json`.

    DMI answers the records of the `stationId` of the request, as the mock does: a station gets its own rows only.
    """
    rows = records if records is not None else _RECORDS[resolution]

    def answer(url: str) -> bytes:
        asked = parse_qs(urlparse(url).query)["stationId"][0]
        return json.dumps({"features": [{"properties": row} for row in rows if row["stationId"] == asked]}).encode()

    serve(monkeypatch, dmi_api, {"stationValue": answer})
    request = DmiObservationRequest(
        parameters=[(resolution, "data")],
        start=start,
        end=end,
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return stations_result(request, resolution, "data", station).values().all().df


def _by_day(df: pl.DataFrame, parameter: str) -> dict[dt.date, float]:
    frame = df.filter(pl.col("parameter") == parameter).sort("timestamp")
    return {row["timestamp"].date(): row["value"] for row in frame.iter_rows(named=True)}


def _by_parameter(df: pl.DataFrame) -> dict[str, float]:
    return {row["parameter"]: row["value"] for row in df.iter_rows(named=True)}


def test_daily_pressure_extremes_and_heating_degree_days_of_greenland(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nuuk, 2024-01-10 to 2024-01-12 (06:00 to 06:00 UTC days): hPa at sea level, and heating degree days, base 19."""
    df = _values(
        monkeypatch, "daily", "04250", dt.datetime(2024, 1, 10, tzinfo=_UTC), dt.datetime(2024, 1, 12, tzinfo=_UTC)
    )
    assert set(df["parameter"]) == {
        "pressure_air_sea_level_max",
        "pressure_air_sea_level_mean",
        "pressure_air_sea_level_min",
        "heating_degree_day",
        "temperature_air_mean_2m",
    }
    # the highest and lowest hourly means of the day, between which the mean of the day lies (1004.0, 1022.6, 1024.9)
    assert _by_day(df, "pressure_air_sea_level_max") == {
        dt.date(2024, 1, 10): 1018.6,
        dt.date(2024, 1, 11): 1024.3,
        dt.date(2024, 1, 12): 1026.3,
    }
    assert _by_day(df, "pressure_air_sea_level_min") == {
        dt.date(2024, 1, 10): 987.4,
        dt.date(2024, 1, 11): 1019.3,
        dt.date(2024, 1, 12): 1022.8,
    }
    # `acc_heating_degree_days_19` comes out as `heating_degree_day`: 19 minus the mean temperature of the day
    hdd = _by_day(df, "heating_degree_day")
    assert hdd == {dt.date(2024, 1, 10): 21.9, dt.date(2024, 1, 11): 23.4, dt.date(2024, 1, 12): 20.4}
    mean = _by_day(df, "temperature_air_mean_2m")
    assert {day: round(hdd[day] + mean[day], 1) for day in hdd} == dict.fromkeys(hdd, 19.0)


def test_daily_heating_degree_days_of_denmark(monkeypatch: pytest.MonkeyPatch) -> None:
    """Copenhagen airport, local days of 2024-01-11 to 2024-01-13: `acc_heating_degree_days_17`, base 17."""
    df = _values(
        monkeypatch, "daily", "06180", dt.datetime(2024, 1, 11, tzinfo=_UTC), dt.datetime(2024, 1, 13, tzinfo=_UTC)
    )
    assert set(df["parameter"]) == {"heating_degree_day", "temperature_air_mean_2m"}
    hdd = _by_day(df, "heating_degree_day")
    assert hdd == {dt.date(2024, 1, 11): 16.0, dt.date(2024, 1, 12): 18.3, dt.date(2024, 1, 13): 15.0}
    mean = _by_day(df, "temperature_air_mean_2m")
    assert {day: round(hdd[day] + mean[day], 1) for day in hdd} == dict.fromkeys(hdd, 17.0)


def test_monthly_counts_pressure_extremes_and_heating_degree_days(monkeypatch: pytest.MonkeyPatch) -> None:
    """July 2023: Nuuk has the pressure extremes and base 19, 06180 the counts of days and base 17."""
    start = end = dt.datetime(2023, 7, 1, tzinfo=_UTC)
    nuuk = _values(monkeypatch, "monthly", "04250", start, end)
    assert _by_parameter(nuuk) == {
        "pressure_air_sea_level_max": 1024.7,
        "pressure_air_sea_level_min": 1002.9,
        "heating_degree_day": 340.4,
        "count_days_summer": 0.0,
    }
    copenhagen = _values(monkeypatch, "monthly", "06180", start, end)
    assert _by_parameter(copenhagen) == {
        "heating_degree_day": 16.1,
        "count_days_summer": 1.0,
        "count_days_tropical_night": 0.0,
    }


def test_annual_counts_pressure_extremes_and_heating_degree_days(monkeypatch: pytest.MonkeyPatch) -> None:
    """2023: the year's pressure extremes of Nuuk, base 19 summing to 6,727.5, and the counts of 06180, base 17."""
    start = end = dt.datetime(2023, 1, 1, tzinfo=_UTC)
    assert _by_parameter(_values(monkeypatch, "annual", "04250", start, end)) == {
        "pressure_air_sea_level_max": 1036.4,
        "pressure_air_sea_level_min": 969.0,
        "heating_degree_day": 6727.5,
        "count_days_summer": 0.0,
    }
    assert _by_parameter(_values(monkeypatch, "annual", "06180", start, end)) == {
        "heating_degree_day": 2663.4,
        "count_days_summer": 6.0,
        "count_days_tropical_night": 0.0,
    }


def test_the_summer_days_of_dmi_are_the_days_above_25_degrees_not_at_or_above(monkeypatch: pytest.MonkeyPatch) -> None:
    """06180, July 2022: 6 summer days by DMI, the days with a maximum above 25.0 °C, where 7 are at 25.0 or above.

    This is the edge between DMI's "more than 25 °C" and the "at least 25 degrees" of `count_days_summer`: the day at
    exactly 25.0 °C is not counted. The daily maxima and the monthly count are DMI's own records.
    """
    daily = _values(
        monkeypatch, "daily", "06180", dt.datetime(2022, 7, 1, tzinfo=_UTC), dt.datetime(2022, 7, 31, tzinfo=_UTC)
    )
    maxima = list(_by_day(daily, "temperature_air_max_2m").values())
    assert len(maxima) == 31
    assert sum(value > 25.0 for value in maxima) == 6
    assert sum(value >= 25.0 for value in maxima) == 7
    monthly = _values(
        monkeypatch, "monthly", "06180", dt.datetime(2022, 7, 1, tzinfo=_UTC), dt.datetime(2022, 7, 1, tzinfo=_UTC)
    )
    assert _by_parameter(monthly) == {"count_days_summer": 6.0}


def test_the_tropical_nights_of_dmi_are_the_days_above_20_degrees_not_at_or_above(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """06070, July 2018: no tropical night by DMI, the days with a minimum above 20.0 °C, where one day is at 20.0."""
    daily = _values(
        monkeypatch, "daily", "06070", dt.datetime(2018, 7, 1, tzinfo=_UTC), dt.datetime(2018, 7, 31, tzinfo=_UTC)
    )
    minima = list(_by_day(daily, "temperature_air_min_2m").values())
    assert len(minima) == 31
    assert sum(value > 20.0 for value in minima) == 0
    assert sum(value >= 20.0 for value in minima) == 1
    monthly = _values(
        monkeypatch, "monthly", "06070", dt.datetime(2018, 7, 1, tzinfo=_UTC), dt.datetime(2018, 7, 1, tzinfo=_UTC)
    )
    assert _by_parameter(monthly) == {"count_days_tropical_night": 0.0}


def test_a_pressure_outside_the_physical_range_is_null_and_keeps_its_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """A highest pressure of 1500 hPa at sea level is no reading (made-up record beside the real 1018.6 of Nuuk)."""
    real, *_ = (
        row for row in _RECORDS["daily"] if row["stationId"] == "04250" and row["parameterId"] == "max_pressure"
    )
    records = [real, {**real, "from": "2024-01-11T06:00:00+00:00", "to": "2024-01-12T06:00:00+00:00", "value": 1500.0}]
    df = _values(
        monkeypatch,
        "daily",
        "04250",
        dt.datetime(2024, 1, 10, tzinfo=_UTC),
        dt.datetime(2024, 1, 11, tzinfo=_UTC),
        drop_nulls=False,
        records=records,
    ).sort("timestamp")
    assert df.select("value", "quality_flags").rows() == [
        (1018.6, "manual,validity:true"),
        (None, "manual,validity:true,raw:1500"),
    ]
