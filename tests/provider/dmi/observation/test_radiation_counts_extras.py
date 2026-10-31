# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The DMI radiation of a day, month and year, the counts of days past a threshold and further parameters (GH-3622).

`published_radiation_counts_extras.json` holds records of the `stationValue` collection as read key-less on 2026-10-31,
trimmed to the keys the reader uses:

- 06041 (Skagen): the daily radiation of 2023-06-22 and 2023-06-23, that of June 2023 and of 2020, and the 24 hourly
  values of 2023-06-22 they are the sum of; 04339 (Ittoqqortoormiit): the daily radiation of 2021-01-10 and 2021-01-13
  (in the polar night, up to 284 MJ/m2, marked valid) and of 2021-06-10;
- 06180: the highest 10-minute wind speed of every day of February 2018 and the counts of windy, stormy, storm and
  hurricane days of the month; 04250 (Nuuk): the lowest temperature of every day of April 2011 and its count of cold
  days, the daily cloud cover with the clear and cloudy days of five days (among them one at exactly 80 % and one at
  exactly 20 %) and the monthly and annual counts; 06180: the snow depth and snow cover of February 2013 and its count
  of days with snow cover;
- 04339: the hourly maxima, minima and precipitation of 2025-06-09 beside the 12 and 24 hour values of 17:00 and 23:00
  UTC; 04220: a trace of -0.1 in the 12 hour precipitation; the mean vapour pressure, the greatest snow depth (24043
  and 06030) and the soil temperature at 10 cm (06197).
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
_RECORDS = json.loads(
    (Path(__file__).parent / "published_radiation_counts_extras.json").read_text(encoding="utf8"),
)

# (resolution, DMI's parameterId) -> the canonical name and the unit it is declared in
_MAPPING = {
    ("daily", "mean_radiation"): ("radiation_global", "kilojoule_per_square_meter"),
    ("monthly", "mean_radiation"): ("radiation_global", "kilojoule_per_square_meter"),
    ("annual", "mean_radiation"): ("radiation_global", "kilojoule_per_square_meter"),
    ("monthly", "no_cold_days"): ("count_days_temperature_air_min_2m_lt_minus_10c", "dimensionless"),
    ("annual", "no_cold_days"): ("count_days_temperature_air_min_2m_lt_minus_10c", "dimensionless"),
    ("monthly", "no_windy_days"): ("count_days_wind_speed_rolling_mean_max_ge_10_8mps", "dimensionless"),
    ("monthly", "no_stormy_days"): ("count_days_wind_speed_rolling_mean_max_ge_20_8mps", "dimensionless"),
    ("monthly", "no_days_w_storm"): ("count_days_wind_speed_rolling_mean_max_ge_24_5mps", "dimensionless"),
    ("monthly", "no_days_w_hurricane"): ("count_days_wind_speed_rolling_mean_max_ge_28_5mps", "dimensionless"),
    ("annual", "no_windy_days"): ("count_days_wind_speed_rolling_mean_max_ge_10_8mps", "dimensionless"),
    ("annual", "no_stormy_days"): ("count_days_wind_speed_rolling_mean_max_ge_20_8mps", "dimensionless"),
    ("annual", "no_days_w_storm"): ("count_days_wind_speed_rolling_mean_max_ge_24_5mps", "dimensionless"),
    ("annual", "no_days_w_hurricane"): ("count_days_wind_speed_rolling_mean_max_ge_28_5mps", "dimensionless"),
    ("daily", "no_clear_days"): ("count_days_cloud_cover_total_mean_lt_20pct", "dimensionless"),
    ("monthly", "no_clear_days"): ("count_days_cloud_cover_total_mean_lt_20pct", "dimensionless"),
    ("annual", "no_clear_days"): ("count_days_cloud_cover_total_mean_lt_20pct", "dimensionless"),
    ("daily", "no_cloudy_days"): ("count_days_cloud_cover_total_mean_gt_80pct", "dimensionless"),
    ("monthly", "no_cloudy_days"): ("count_days_cloud_cover_total_mean_gt_80pct", "dimensionless"),
    ("annual", "no_cloudy_days"): ("count_days_cloud_cover_total_mean_gt_80pct", "dimensionless"),
    ("monthly", "no_days_snow_cover"): ("count_days_snow_cover_gt_50pct", "dimensionless"),
    ("annual", "no_days_snow_cover"): ("count_days_snow_cover_gt_50pct", "dimensionless"),
    ("daily", "mean_vapour_pressure"): ("pressure_vapor_mean", "hectopascal"),
    ("monthly", "mean_vapour_pressure"): ("pressure_vapor_mean", "hectopascal"),
    ("annual", "mean_vapour_pressure"): ("pressure_vapor_mean", "hectopascal"),
    ("monthly", "max_snow_depth"): ("snow_depth_max", "centimeter"),
    ("annual", "max_snow_depth"): ("snow_depth_max", "centimeter"),
    ("hourly", "max_temp_12h"): ("temperature_air_max_2m_last_12h", "degree_celsius"),
    ("hourly", "min_temperature_12h"): ("temperature_air_min_2m_last_12h", "degree_celsius"),
    ("hourly", "acc_precip_past12h"): ("precipitation_amount_last_12h", "millimeter"),
    ("hourly", "acc_precip_past24h"): ("precipitation_amount_last_24h", "millimeter"),
    ("hourly", "temp_soil_10"): ("temperature_soil_mean_0_1m", "degree_celsius"),
    ("daily", "temp_soil_10"): ("temperature_soil_mean_0_1m", "degree_celsius"),
}


@pytest.mark.parametrize(("resolution", "parameter_id"), list(_MAPPING))
def test_a_published_parameter_is_mapped_to_the_name_of_its_statistic(resolution: str, parameter_id: str) -> None:
    """Each parameter of GH-3622 is declared with the canonical name of its statistic and the unit DMI writes it in."""
    parameters = {
        parameter.name_original: parameter for parameter in DmiObservationMetadata[resolution].datasets[0].parameters
    }
    assert (parameters[parameter_id].name, parameters[parameter_id].unit) == _MAPPING[(resolution, parameter_id)]


def test_the_hourly_radiation_stays_the_mean_intensity() -> None:
    """The hour is in W/m2 and a mean, the day, month and year are a sum in MJ/m2: two names, two unit types."""
    hourly = {p.name_original: p for p in DmiObservationMetadata["hourly"].datasets[0].parameters}["mean_radiation"]
    assert (hourly.name, hourly.unit) == ("radiation_global_intensity_mean", "watt_per_square_meter")
    for resolution in ("daily", "monthly", "annual"):
        parameters = {p.name_original: p for p in DmiObservationMetadata[resolution].datasets[0].parameters}
        assert parameters["mean_radiation"].unit_type == "energy_per_area"


def test_the_published_parameters_without_a_name_that_fits_are_not_served() -> None:
    """What no canonical name fits exactly is left out, with the name it would take (module comment of `metadata`)."""
    left_out = {
        "snow_cover",
        "leaf_moisture",
        "temp_grass",
        "temp_soil_30",
        "vapour_pressure_deficit_mean",
        "acc_heating_degree_days_19",
    }
    served = {
        parameter.name_original
        for resolution in DmiObservationMetadata
        for parameter in resolution.datasets[0].parameters
    }
    assert served & left_out == set()


def test_the_descriptions_state_the_thresholds_as_dmi_writes_them() -> None:
    """Each count states its threshold, `>`, `>=` or `<`, in its description."""
    expected = {
        "no_cold_days": "less than -10 °C",
        "no_windy_days": "greater than or equal to 10.8 m/s",
        "no_stormy_days": "greater than or equal to 20.8 m/s",
        "no_days_w_storm": "greater than or equal to 24.5 m/s",
        "no_days_w_hurricane": "greater than or equal to 28.5 m/s",
        "no_clear_days": "less than 20%",
        "no_cloudy_days": "greater than 80%",
        "no_days_snow_cover": "greater than 0 and snow_cover",
    }
    parameters = {p.name_original: p for p in DmiObservationMetadata["monthly"].datasets[0].parameters}
    for name, text in expected.items():
        assert text in parameters[name].description, name
    assert "MJ/m²" in parameters["mean_radiation"].description


def _values(
    monkeypatch: pytest.MonkeyPatch,
    resolution: str,
    station: str,
    start: dt.datetime,
    end: dt.datetime,
    *,
    drop_nulls: bool = True,
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
        options=_options(drop_nulls),
    )
    return stations_result(request, resolution, "data", station).values().all().df


def _day(year: int, month: int, day: int, hour: int = 0) -> dt.datetime:
    return dt.datetime(year, month, day, hour, tzinfo=_UTC)


def _by_day(df: pl.DataFrame, parameter: str) -> dict[dt.date, float]:
    frame = df.filter(pl.col("parameter") == parameter).sort("timestamp")
    return {row["timestamp"].date(): row["value"] for row in frame.iter_rows(named=True)}


def _by_parameter(df: pl.DataFrame) -> dict[str, float]:
    return {row["parameter"]: row["value"] for row in df.iter_rows(named=True)}


def _source(resolution: str, station: str, parameter: str, prefix: str = "") -> list[dict]:
    return [
        row
        for row in _RECORDS[resolution]
        if row["stationId"] == station and row["parameterId"] == parameter and row["from"].startswith(prefix)
    ]


def test_the_radiation_of_a_day_is_the_megajoules_dmi_writes_times_a_thousand(monkeypatch: pytest.MonkeyPatch) -> None:
    """06041, 2023-06-22: DMI's 25.4 MJ/m2 is 25,400 kJ/m2, which the default unit returns as 2,540 J/cm2.

    A clear day of June in Denmark brings 15 to 30 MJ/m2. The 24 hourly means of the day, in W/m2, sum to the same
    energy: 25.40196 MJ/m2 (each is the mean over an hour of 3,600 s).
    """
    hourly = _source("hourly", "06041", "mean_radiation")
    assert len(hourly) == 24
    assert sum(row["value"] for row in hourly) * 3600 / 1e6 == pytest.approx(25.4, abs=0.01)
    df = _values(monkeypatch, "daily", "06041", _day(2023, 6, 22), _day(2023, 6, 23))
    assert set(df["parameter"]) == {"radiation_global"}
    assert _by_day(df, "radiation_global") == {dt.date(2023, 6, 22): 2540.0, dt.date(2023, 6, 23): 2420.0}
    assert all(15 <= row["value"] / 100 <= 30 for row in df.iter_rows(named=True))


def test_the_radiation_of_a_month_and_a_year_is_converted_the_same_way(monkeypatch: pytest.MonkeyPatch) -> None:
    """06041: DMI's June 2023 and year 2020 are written in MJ/m2 and returned as 100 times that in J/cm2."""
    month = _source("monthly", "06041", "mean_radiation")
    year = _source("annual", "06041", "mean_radiation")
    assert len(month) == len(year) == 1
    june = _values(monkeypatch, "monthly", "06041", _day(2023, 6, 1), _day(2023, 6, 1))
    assert _by_parameter(june)["radiation_global"] == pytest.approx(month[0]["value"] * 100)
    y2020 = _values(monkeypatch, "annual", "06041", _day(2020, 1, 1), _day(2020, 1, 1))
    assert _by_parameter(y2020)["radiation_global"] == pytest.approx(year[0]["value"] * 100)
    assert _by_parameter(y2020)["radiation_global"] == pytest.approx(447_690.0)


def test_the_hourly_radiation_is_not_converted(monkeypatch: pytest.MonkeyPatch) -> None:
    """The hour stays a mean intensity in W/m2: no factor."""
    df = _values(monkeypatch, "hourly", "06041", _day(2023, 6, 21, 22), _day(2023, 6, 22, 21))
    assert set(df["parameter"]) == {"radiation_global_intensity_mean"}
    assert sorted(df["value"].to_list()) == sorted(row["value"] for row in _source("hourly", "06041", "mean_radiation"))


def test_a_radiation_no_day_can_bring_is_null_and_keeps_the_text_dmi_wrote(monkeypatch: pytest.MonkeyPatch) -> None:
    """04339, polar night of January 2021: 278.6 and 135.8 MJ/m2 are marked valid, but no sun brings 60 MJ/m2 a day."""
    df = _values(monkeypatch, "daily", "04339", _day(2021, 1, 10), _day(2021, 6, 10), drop_nulls=False).sort(
        "timestamp"
    )
    # 2021-06-10 is a day of the midnight sun at 70 degrees north, 22.4 MJ/m2 by DMI, inside the bound
    [june] = _source("daily", "04339", "mean_radiation", "2021-06-10")
    assert june["value"] == 22.4
    assert df.select("value", "quality_flags").rows() == [
        (None, "manual,validity:true,rejected:range,raw:278.6"),
        (None, "manual,validity:true,rejected:range,raw:135.8"),
        (2240.0, "manual,validity:true"),
    ]


def test_the_windy_days_of_dmi_are_the_days_at_or_above_10_8_ms_of_the_ten_minute_maximum(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """06180, February 2018: 5 windy days by DMI, the days with a 10-minute mean of 10.8 m/s or more, where 4 are above.

    The count is of `max_wind_speed_10min` (the daily maximum of the 10-minute mean), not of the daily mean wind
    speed the parameter list of DMI's documentation names: the calculation table says "max_win_speed_10min is
    greater or equal to 10.8 m/s". The daily records and the monthly count are DMI's own.
    """
    maxima = [row["value"] for row in _source("daily", "06180", "max_wind_speed_10min", "2018-02")]
    assert len(maxima) == 28
    assert sum(value >= 10.8 for value in maxima) == 5
    assert sum(value > 10.8 for value in maxima) == 4
    monthly = _values(monkeypatch, "monthly", "06180", _day(2018, 2, 1), _day(2018, 2, 1))
    assert _by_parameter(monthly) == {
        "count_days_wind_speed_rolling_mean_max_ge_10_8mps": 5.0,
        "count_days_wind_speed_rolling_mean_max_ge_20_8mps": 0.0,
        "count_days_wind_speed_rolling_mean_max_ge_24_5mps": 0.0,
        "count_days_wind_speed_rolling_mean_max_ge_28_5mps": 0.0,
    }


def test_the_cold_days_of_dmi_are_the_days_below_minus_10_not_at_or_below(monkeypatch: pytest.MonkeyPatch) -> None:
    """04250, April 2011: 16 cold days by DMI, the days with a minimum below -10.0 °C, where 17 are at or below it."""
    minima = [row["value"] for row in _source("daily", "04250", "min_temp", "2011-04")]
    assert len(minima) == 30
    assert sum(value < -10 for value in minima) == 16
    assert sum(value <= -10 for value in minima) == 17
    monthly = _values(monkeypatch, "monthly", "04250", _day(2011, 4, 1), _day(2011, 4, 1))
    assert _by_parameter(monthly)["count_days_temperature_air_min_2m_lt_minus_10c"] == 16.0


def test_the_clear_and_cloudy_days_of_dmi_are_below_20_and_above_80_percent(monkeypatch: pytest.MonkeyPatch) -> None:
    """04250: a day of exactly 20 % is no clear day and a day of exactly 80 % no cloudy one, as DMI's 1 and 0 say."""
    clouds = {row["from"]: row["value"] for row in _source("daily", "04250", "mean_cloud_cover")}
    assert 20.0 in clouds.values()
    assert 80.0 in clouds.values()
    df = _values(monkeypatch, "daily", "04250", _day(2011, 1, 1), _day(2026, 1, 1))
    clear = _by_day(df, "count_days_cloud_cover_total_mean_lt_20pct")
    cloudy = _by_day(df, "count_days_cloud_cover_total_mean_gt_80pct")
    assert len(clear) == len(cloudy) == len(clouds)
    # the cloud cover comes back as a fraction
    cover = {day: round(value * 100, 6) for day, value in _by_day(df, "cloud_cover_total_mean").items()}
    assert dict(clear) == {day: float(cover[day] < 20) for day in cover}
    assert dict(cloudy) == {day: float(cover[day] > 80) for day in cover}
    assert clear[next(day for day, value in cover.items() if value == 20.0)] == 0.0
    assert cloudy[next(day for day, value in cover.items() if value == 80.0)] == 0.0
    monthly = _values(monkeypatch, "monthly", "04250", _day(2011, 4, 1), _day(2011, 4, 1))
    assert set(_by_parameter(monthly)) >= {
        "count_days_cloud_cover_total_mean_lt_20pct",
        "count_days_cloud_cover_total_mean_gt_80pct",
    }


def test_the_days_with_snow_cover_of_dmi_have_a_snow_depth_above_0_and_a_cover_above_50(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """06180, February 2013: DMI's count is that of the days with snow_depth > 0 and snow_cover > 50 (percent)."""
    depth = {row["from"]: row["value"] for row in _source("daily", "06180", "snow_depth", "2013-02")}
    cover = {row["from"]: row["value"] for row in _source("daily", "06180", "snow_cover", "2013-02")}
    counted = sum(depth[day] > 0 and cover[day] > 50 for day in depth.keys() & cover.keys())
    monthly = _values(monkeypatch, "monthly", "06180", _day(2013, 2, 1), _day(2013, 2, 1))
    assert counted == _by_parameter(monthly)["count_days_snow_cover_gt_50pct"] == 15.0


def test_the_extremes_and_sums_of_12_and_24_hours_are_stamped_by_the_end_of_their_window(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """04339, June 2025: the 12 hour extremes of the 18 UTC report are those of the 12 hourly values before it.

    DMI's `from` of the report is 17:00 (`to` 18:00), the start of the last hour of the window, and the value is
    stamped 18:00, the end of the window, as dwd/poi, meteofrance/synop and noaa/ghcn stamp theirs. The precipitation
    of 12 and 24 hours is the gauge's own reading and within a few tenths of a millimetre of the sum of the hourly
    values of the window (0.7 and 9.4 mm of the reports of 2025-06-27 06:00 and 18:00 UTC).
    """
    rows = {(row["parameterId"], row["from"]): row["value"] for row in _source_all("hourly", "04339")}

    def hours(report: dt.datetime, count: int, parameter: str) -> list[float]:
        """Give the hourly values of the `count` hours that end with the report, stamped by DMI's `from`."""
        return [rows[(parameter, (report - dt.timedelta(hours=h + 1)).isoformat())] for h in range(count)]

    df = _values(monkeypatch, "hourly", "04339", _day(2025, 6, 9), _day(2025, 6, 27, 23))
    at = {
        (row["parameter"], row["timestamp"]): row["value"]
        for row in df.iter_rows(named=True)
        if row["parameter"].endswith(("_last_12h", "_last_24h"))
    }
    report = _day(2025, 6, 9, 18)
    assert rows[("max_temp_12h", "2025-06-09T17:00:00+00:00")] == at[("temperature_air_max_2m_last_12h", report)]
    assert at[("temperature_air_max_2m_last_12h", report)] == max(hours(report, 12, "max_temp_w_date"))
    assert at[("temperature_air_min_2m_last_12h", report)] == min(hours(report, 12, "min_temp"))
    assert _day(2025, 6, 9, 17) not in {stamp for _, stamp in at}
    for key, end, count, published in (
        ("precipitation_amount_last_12h", _day(2025, 6, 27, 6), 12, 0.7),
        ("precipitation_amount_last_24h", _day(2025, 6, 27, 18), 24, 9.4),
    ):
        assert at[(key, end)] == published
        assert sum(hours(end, count, "acc_precip")) == pytest.approx(published, abs=0.31)
    # a request that starts at the report returns it, though DMI's `from` is an hour before the start
    edge = _values(monkeypatch, "hourly", "04339", report, report)
    assert {row["parameter"] for row in edge.iter_rows(named=True)} >= {
        "temperature_air_max_2m_last_12h",
        "temperature_air_min_2m_last_12h",
    }


def _source_all(resolution: str, station: str) -> list[dict]:
    return [row for row in _RECORDS[resolution] if row["stationId"] == station]


def test_a_trace_in_the_12_hour_precipitation_is_zero_and_keeps_its_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """04220, report of 2014-01-01 06:00 UTC: DMI documents -0.1 as the code of a trace for acc_precip_past12h too."""
    df = _values(monkeypatch, "hourly", "04220", _day(2014, 1, 1, 6), _day(2014, 1, 1, 6), drop_nulls=False)
    assert df.select("parameter", "value", "quality_flags").rows() == [
        ("precipitation_amount_last_12h", 0.0, "manual,validity:true,raw:-0.1"),
    ]


def test_the_vapour_pressure_is_the_mean_in_hpa_and_one_that_is_no_reading_is_null(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """04301 daily and monthly, and the years 2023 of 06011 (kept) and 04219 (109.3 hPa, marked valid, is null)."""
    day = _values(monkeypatch, "daily", "04301", _day(2025, 6, 16), _day(2025, 6, 17))
    source = _source("daily", "04301", "mean_vapour_pressure")
    assert _by_day(day, "pressure_vapor_mean") == {
        dt.date.fromisoformat(row["from"][:10]): row["value"] for row in source
    }
    assert sorted(_by_day(day, "pressure_vapor_mean").values()) == [4.1, 4.5]
    assert _by_parameter(_values(monkeypatch, "annual", "06011", _day(2023, 1, 1), _day(2023, 1, 1))) == {
        "pressure_vapor_mean": 10.6
    }
    bad = _values(monkeypatch, "annual", "04219", _day(2023, 1, 1), _day(2023, 1, 1), drop_nulls=False)
    assert bad.select("value", "quality_flags").rows() == [(None, "manual,validity:true,rejected:range,raw:109.3")]


def test_the_greatest_snow_depth_is_in_cm_and_the_999_of_dmi_is_no_depth(monkeypatch: pytest.MonkeyPatch) -> None:
    """06030, January 2011: 105 cm stays; 24043, September 2020 and the year 2020: 999.0 is null with `raw:999`."""
    kept = _values(monkeypatch, "monthly", "06030", _day(2011, 1, 1), _day(2011, 1, 1))
    assert _by_parameter(kept) == {"snow_depth_max": 105.0}
    for resolution, when in (("monthly", _day(2020, 9, 1)), ("annual", _day(2020, 1, 1))):
        df = _values(monkeypatch, resolution, "24043", when, when, drop_nulls=False)
        assert df.select("parameter", "value", "quality_flags").rows() == [
            ("snow_depth_max", None, "manual,validity:true,raw:999")
        ]


def test_the_soil_temperature_at_10_cm_is_the_mean_of_the_hour_and_of_the_day(monkeypatch: pytest.MonkeyPatch) -> None:
    """06197: the hourly means of 2024-06-26 14:00 and 15:00 UTC and the daily means of 2025-06-17 and 2025-06-18."""
    hours = _values(monkeypatch, "hourly", "06197", _day(2024, 6, 26, 14), _day(2024, 6, 26, 15))
    assert set(hours["parameter"]) == {"temperature_soil_mean_0_1m"}
    assert sorted(hours["value"].to_list()) == sorted(
        row["value"] for row in _source("hourly", "06197", "temp_soil_10")
    )
    days = _values(monkeypatch, "daily", "06197", _day(2025, 6, 17), _day(2025, 6, 18))
    assert sorted(days["value"].to_list()) == sorted(row["value"] for row in _source("daily", "06197", "temp_soil_10"))
