# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DMI's snow cover, leaf moisture, grass temperature, soil temperature at 30 cm and vapour pressure deficit (GH-3622).

`published_grass_soil_leaf_snow_vpd.json` holds records of the `stationValue` collection as read key-less on 2026-11-01,
trimmed to the keys the reader uses:

- hourly, 2025-06-10 00:00 to 06:00 UTC: `leaf_moisture` of 06072, `temp_grass` and `temp_soil_30` of 06069 (the
  second is not served by the hour) and `vapour_pressure_deficit_mean` of 06066;
- daily (local days): `leaf_moisture` of 06135 for 2025-06-10 to 2025-06-12, and `temp_grass` of 06070, `temp_soil_30`
  of 06069 and `vapour_pressure_deficit_mean` of 06073 for 2025-06-11 to 2025-06-13 (the 13th is outside the window
  the tests ask for);
- daily, 2011-01-14 to 2011-01-18 (days of 06:00 to 06:00 UTC): `snow_cover` of 06180.
"""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import polars as pl
import pytest

from tests.provider.value_stubs import _settings, serve, stations_result
from wetterdienst import Options
from wetterdienst.metadata.parameter_table import PARAMETERS
from wetterdienst.provider.dmi.observation import DmiObservationRequest
from wetterdienst.provider.dmi.observation import api as dmi_api
from wetterdienst.provider.dmi.observation.metadata import DmiObservationMetadata

_UTC = dt.UTC
_RECORDS = json.loads((Path(__file__).parent / "published_grass_soil_leaf_snow_vpd.json").read_text(encoding="utf8"))

# (resolution, DMI's parameterId) -> the canonical name and the unit DMI writes it in
_MAPPING = {
    ("hourly", "temp_grass"): ("temperature_air_mean_grass_height", "degree_celsius"),
    ("daily", "temp_grass"): ("temperature_air_mean_grass_height", "degree_celsius"),
    ("daily", "temp_soil_30"): ("temperature_soil_mean_0_3m", "degree_celsius"),
    ("hourly", "leaf_moisture"): ("leaf_wetness_duration", "minute"),
    ("daily", "leaf_moisture"): ("leaf_wetness_duration", "minute"),
    ("hourly", "vapour_pressure_deficit_mean"): ("vapor_pressure_deficit_mean", "kilopascal"),
    ("daily", "vapour_pressure_deficit_mean"): ("vapor_pressure_deficit_mean", "kilopascal"),
    ("daily", "snow_cover"): ("snow_cover", "percent"),
}


@pytest.mark.parametrize(("resolution", "parameter_id"), list(_MAPPING))
def test_a_published_parameter_is_mapped_to_its_canonical_name_in_the_unit_dmi_writes(
    resolution: str, parameter_id: str
) -> None:
    """Each of the five is declared with the canonical name the maintainer chose and DMI's own unit."""
    parameters = {
        parameter.name_original: parameter for parameter in DmiObservationMetadata[resolution].datasets[0].parameters
    }
    assert (parameters[parameter_id].name, parameters[parameter_id].unit) == _MAPPING[(resolution, parameter_id)]


def test_the_five_are_served_where_dmi_publishes_them_and_nowhere_else() -> None:
    """DMI answers the four by the hour and the day, the snow cover by the day only, and none by month or year.

    The hourly `temp_soil_30` is published and not served: DMI names no source for it, so the mean of the hour that
    `temperature_soil_mean_0_3m` says is not stated (metadata comment, GH-3622); the day is DMI's average of the hours.
    """
    served = {
        resolution.name: {p.name_original for p in resolution.datasets[0].parameters}
        for resolution in DmiObservationMetadata
    }
    four = {"temp_grass", "temp_soil_30", "leaf_moisture", "vapour_pressure_deficit_mean"}
    assert four - {"temp_soil_30"} == served["hourly"] & four
    assert "snow_cover" not in served["hourly"]
    assert four | {"snow_cover"} <= served["daily"]
    for resolution in ("monthly", "annual"):
        assert (four | {"snow_cover"}) & served[resolution] == set()


def test_the_canonical_names_say_what_the_unit_type_converts_to() -> None:
    """The minutes of leaf wetness are a time, the kPa of the deficit a pressure and the percent a fraction."""
    expected = {
        "leaf_wetness_duration": "time",
        "vapor_pressure_deficit_mean": "pressure",
        "snow_cover": "fraction",
        "temperature_air_mean_grass_height": "temperature",
        "temperature_soil_mean_0_3m": "temperature",
    }
    assert {name: PARAMETERS[name].unit_type for name in expected} == expected
    for name in expected:
        assert PARAMETERS[name].description.endswith(".")


def _values(
    monkeypatch: pytest.MonkeyPatch,
    resolution: str,
    station: str,
    start: dt.datetime,
    end: dt.datetime,
    *,
    options: Options | None = None,
) -> pl.DataFrame:
    """Collect the dataset of a resolution for a station from the records of the fixture, as DMI answers by station."""

    def answer(url: str) -> bytes:
        query = parse_qs(urlparse(url).query)
        asked = query["stationId"][0]
        # DMI keeps the records whose `from` instant lies in the `datetime` interval, both ends included
        first, last = (dt.datetime.fromisoformat(instant) for instant in query["datetime"][0].split("/"))
        rows = [
            row
            for row in _RECORDS[resolution]
            if row["stationId"] == asked and first <= dt.datetime.fromisoformat(row["from"]) <= last
        ]
        return json.dumps({"features": [{"properties": row} for row in rows]}).encode()

    serve(monkeypatch, dmi_api, {"stationValue": answer})
    request = DmiObservationRequest(
        parameters=[(resolution, "data")],
        start=start,
        end=end,
        settings=_settings(),
        options=options or Options(),
    )
    return stations_result(request, resolution, "data", station).values().all().df


def _day(year: int, month: int, day: int, hour: int = 0) -> dt.datetime:
    return dt.datetime(year, month, day, hour, tzinfo=_UTC)


def _by_time(df: pl.DataFrame, parameter: str) -> dict[dt.datetime, float]:
    frame = df.filter(pl.col("parameter") == parameter).sort("timestamp")
    return {row["timestamp"]: row["value"] for row in frame.iter_rows(named=True)}


def test_the_hourly_values_come_back_in_the_default_units(monkeypatch: pytest.MonkeyPatch) -> None:
    """Minutes of leaf wetness are seconds, the kPa of the deficit hPa; the degrees stay degrees.

    The records of 06069 hold the hourly `temp_soil_30` as well, and it is not returned.

    06072 had a wet leaf for 35 of the minutes of 00:00 UTC and for all 60 of 01:00 on 2025-06-10, and 06066 a deficit
    of 0.1 kPa, 0.0 at 02:00, which is 1.0 and 0.0 hPa.
    """
    start, end = _day(2025, 6, 10), _day(2025, 6, 10, 6)
    leaf = _values(monkeypatch, "hourly", "06072", start, end)
    assert set(leaf["parameter"]) == {"leaf_wetness_duration"}
    assert _by_time(leaf, "leaf_wetness_duration")[_day(2025, 6, 10)] == 35 * 60.0
    assert _by_time(leaf, "leaf_wetness_duration")[_day(2025, 6, 10, 1)] == 60 * 60.0
    deficit = _values(monkeypatch, "hourly", "06066", start, end)
    assert set(deficit["parameter"]) == {"vapor_pressure_deficit_mean"}
    assert _by_time(deficit, "vapor_pressure_deficit_mean") == pytest.approx(
        {_day(2025, 6, 10, hour): 0.0 if hour == 2 else 1.0 for hour in range(7)}
    )
    grass = _values(monkeypatch, "hourly", "06069", start, end)
    assert set(grass["parameter"]) == {"temperature_air_mean_grass_height"}
    assert _by_time(grass, "temperature_air_mean_grass_height")[_day(2025, 6, 10, 6)] == 11.4


def test_the_values_are_what_dmi_wrote_in_its_own_units_when_asked_not_to_convert(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the conversion the minutes, the kPa and the percent are the numbers of DMI's records."""
    options = Options(convert_units=False)
    start, end = _day(2025, 6, 10), _day(2025, 6, 10, 6)
    leaf = _values(monkeypatch, "hourly", "06072", start, end, options=options)
    assert sorted(leaf["value"].to_list()) == sorted(
        row["value"] for row in _RECORDS["hourly"] if row["stationId"] == "06072"
    )
    deficit = _values(monkeypatch, "hourly", "06066", start, end, options=options)
    assert sorted(deficit["value"].to_list()) == sorted(
        row["value"] for row in _RECORDS["hourly"] if row["stationId"] == "06066"
    )
    snow = _values(monkeypatch, "daily", "06180", _day(2011, 1, 14), _day(2011, 1, 18), options=options)
    assert sorted(snow["value"].to_list()) == [0.0, 1.0, 49.0, 74.0, 99.0]


def test_the_daily_values_are_stamped_by_the_local_day(monkeypatch: pytest.MonkeyPatch) -> None:
    """06135, 2025-06-10 to 12: 1332, 39 and 364 minutes of a wet leaf, DMI's day from local midnight to midnight.

    A record `from` 2025-06-11T00:00:00.001000+02:00 `to` 2025-06-12T00:00:00+02:00 is the 11th.
    """
    start, end = _day(2025, 6, 10), _day(2025, 6, 12)
    leaf = _values(monkeypatch, "daily", "06135", start, end)
    assert _by_time(leaf, "leaf_wetness_duration") == {
        _day(2025, 6, 10): 1332 * 60.0,
        _day(2025, 6, 11): 39 * 60.0,
        _day(2025, 6, 12): 364 * 60.0,
    }
    deficit = _values(monkeypatch, "daily", "06073", start, end)
    assert _by_time(deficit, "vapor_pressure_deficit_mean") == pytest.approx(
        {_day(2025, 6, 11): 4.0, _day(2025, 6, 12): 4.0}
    )
    grass = _values(monkeypatch, "daily", "06070", start, end)
    assert _by_time(grass, "temperature_air_mean_grass_height") == {_day(2025, 6, 11): 15.3, _day(2025, 6, 12): 19.3}
    soil = _values(monkeypatch, "daily", "06069", start, end)
    assert _by_time(soil, "temperature_soil_mean_0_3m") == {_day(2025, 6, 11): 13.6, _day(2025, 6, 12): 13.8}


def test_the_snow_cover_is_a_percent_returned_as_a_decimal_of_the_day_it_begins(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """06180, January 2011: 99 % on the 14th, 74 % on the 15th, 49 %, 1 % and 0 %; days of 06:00 to 06:00 UTC.

    The record of the 14th is `from` 2011-01-14T06:00:00+00:00 `to` 2011-01-15T06:00:00+00:00, and 99 is a value like
    98, no code.
    """
    df = _values(monkeypatch, "daily", "06180", _day(2011, 1, 14), _day(2011, 1, 18))
    assert set(df["parameter"]) == {"snow_cover"}
    assert _by_time(df, "snow_cover") == pytest.approx(
        {
            _day(2011, 1, 14): 0.99,
            _day(2011, 1, 15): 0.74,
            _day(2011, 1, 16): 0.49,
            _day(2011, 1, 17): 0.01,
            _day(2011, 1, 18): 0.0,
        }
    )
    assert set(df["quality_flags"]) == {"manual,validity:true"}
