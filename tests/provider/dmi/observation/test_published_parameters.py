# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The DMI parameters of GH-3622, read through `values().all()` from the records DMI serves.

`published_parameters.json` holds records of the `stationValue` collection as read key-less on 2026-10-30, trimmed to
the keys the reader uses: sunshine, radiation and cloud cover of 06041 (Skagen) and 04250 (Nuuk), the humidity extremes
of Nuuk and 06041, the manual snow depth of 28240, and the counts of days of 06041.
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
_RECORDS = json.loads((Path(__file__).parent / "published_parameters.json").read_text(encoding="utf8"))
_HOUR = 3600.0

# (resolution, DMI's parameterId) -> the canonical name and the unit it is declared in. Each is the statistic DMI's
# climate data documentation states ("Calculation Method for stationValue Parameters"): the hourly cloud cover is the
# reading at minute 0, so no mean; the humidity extremes are the highest and lowest of the hourly means; the day
# counts are of the days that pass the threshold the canonical name states (GH-2614)
_MAPPING = {
    ("hourly", "bright_sunshine"): ("sunshine_duration", "minute"),
    ("hourly", "mean_radiation"): ("radiation_global_intensity_mean", "watt_per_square_meter"),
    ("hourly", "mean_cloud_cover"): ("cloud_cover_total", "percent"),
    ("daily", "bright_sunshine"): ("sunshine_duration", "hour"),
    ("daily", "mean_cloud_cover"): ("cloud_cover_total_mean", "percent"),
    ("daily", "max_relative_hum"): ("humidity_relative_max", "percent"),
    ("daily", "min_relative_hum"): ("humidity_relative_min", "percent"),
    ("daily", "snow_depth"): ("snow_depth_manual", "centimeter"),
    ("monthly", "bright_sunshine"): ("sunshine_duration", "hour"),
    ("monthly", "mean_cloud_cover"): ("cloud_cover_total_mean", "percent"),
    ("monthly", "no_ice_days"): ("count_days_ice", "dimensionless"),
    ("monthly", "no_frost_days"): ("count_days_frost", "dimensionless"),
    ("monthly", "no_days_acc_precip_01"): ("count_days_precipitation_amount_ge_0_1mm", "dimensionless"),
    ("monthly", "no_days_acc_precip_1"): ("count_days_precipitation_amount_ge_1mm", "dimensionless"),
    ("monthly", "no_days_acc_precip_10"): ("count_days_precipitation_amount_ge_10mm", "dimensionless"),
    ("annual", "bright_sunshine"): ("sunshine_duration", "hour"),
    ("annual", "mean_cloud_cover"): ("cloud_cover_total_mean", "percent"),
    ("annual", "max_relative_hum"): ("humidity_relative_max", "percent"),
    ("annual", "min_relative_hum"): ("humidity_relative_min", "percent"),
    ("annual", "no_ice_days"): ("count_days_ice", "dimensionless"),
    ("annual", "no_frost_days"): ("count_days_frost", "dimensionless"),
    ("annual", "no_days_acc_precip_01"): ("count_days_precipitation_amount_ge_0_1mm", "dimensionless"),
    ("annual", "no_days_acc_precip_1"): ("count_days_precipitation_amount_ge_1mm", "dimensionless"),
    ("annual", "no_days_acc_precip_10"): ("count_days_precipitation_amount_ge_10mm", "dimensionless"),
}


@pytest.mark.parametrize(("resolution", "parameter_id"), list(_MAPPING))
def test_a_published_parameter_is_mapped_to_the_name_of_its_statistic(resolution: str, parameter_id: str) -> None:
    """Each parameter of GH-3622 that has a canonical name is declared with that name and DMI's unit."""
    parameters = {
        parameter.name_original: parameter for parameter in DmiObservationMetadata[resolution].datasets[0].parameters
    }
    assert parameter_id in parameters
    assert (parameters[parameter_id].name, parameters[parameter_id].unit) == _MAPPING[(resolution, parameter_id)]


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
    """Collect the dataset of a resolution for a station from the records of `published_parameters.json`.

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


def _by_hour(df: pl.DataFrame, parameter: str) -> dict[int, float]:
    frame = df.filter(pl.col("parameter") == parameter).sort("timestamp")
    return {row["timestamp"].hour: row["value"] for row in frame.iter_rows(named=True)}


def _by_day(df: pl.DataFrame, parameter: str) -> dict[dt.date, float]:
    frame = df.filter(pl.col("parameter") == parameter).sort("timestamp")
    return {row["timestamp"].date(): row["value"] for row in frame.iter_rows(named=True)}


def test_hourly_sunshine_radiation_and_cloud_cover(monkeypatch: pytest.MonkeyPatch) -> None:
    """06041 and 04250, 2024-06-03 11:00 and 12:00 UTC: minutes of sunshine, W/m2 and the cloud cover at minute 0."""
    start, end = dt.datetime(2024, 6, 3, 11, tzinfo=_UTC), dt.datetime(2024, 6, 3, 12, tzinfo=_UTC)
    df = _values(monkeypatch, "hourly", "06041", start, end)
    nuuk = _values(monkeypatch, "hourly", "04250", start, end)
    # minutes come back as seconds, the unit of `time`; the intensity stays in W/m2; the cloud cover in percent is a
    # fraction of 1, and the 10 and 40 DMI writes for 1 okta or less and 3 oktas are 0.1 and 0.4
    assert _by_hour(df, "sunshine_duration") == {11: pytest.approx(5.0 * 60), 12: pytest.approx(23.4 * 60)}
    assert _by_hour(df, "radiation_global_intensity_mean") == {11: 632.0, 12: 808.0}
    assert _by_hour(nuuk, "cloud_cover_total") == {11: pytest.approx(0.1), 12: pytest.approx(0.4)}
    assert set(df["parameter"]) == {"sunshine_duration", "radiation_global_intensity_mean"}
    assert set(nuuk["parameter"]) == {"cloud_cover_total"}
    assert set(df["resolution"]) == {"hourly"}


def test_daily_humidity_extremes_sunshine_cloud_cover_and_snow_depth(monkeypatch: pytest.MonkeyPatch) -> None:
    """04250 (06:00 to 06:00 UTC days), 06041 (local days) and 28240, which reads the snow once a day at 07:00 UTC."""
    start, end = dt.datetime(2021, 2, 12, tzinfo=_UTC), dt.datetime(2024, 6, 4, tzinfo=_UTC)
    df = _values(monkeypatch, "daily", "04250", start, end)
    assert set(df["parameter"]) == {"humidity_relative_max", "humidity_relative_min", "cloud_cover_total_mean"}
    assert _by_day(df, "humidity_relative_max") == {
        dt.date(2024, 1, 10): pytest.approx(0.99),
        dt.date(2024, 1, 11): pytest.approx(0.87),
        dt.date(2024, 1, 12): pytest.approx(0.86),
    }
    assert _by_day(df, "humidity_relative_min") == {
        dt.date(2024, 1, 10): pytest.approx(0.84),
        dt.date(2024, 1, 11): pytest.approx(0.70),
        dt.date(2024, 1, 12): pytest.approx(0.66),
    }
    assert _by_day(df, "cloud_cover_total_mean") == {
        dt.date(2024, 1, 10): pytest.approx(0.95),
        dt.date(2024, 1, 11): pytest.approx(0.94),
        dt.date(2024, 1, 12): pytest.approx(0.85),
    }
    skagen = _values(monkeypatch, "daily", "06041", start, end)
    assert _by_day(skagen, "sunshine_duration") == {
        dt.date(2024, 6, 3): pytest.approx(7.8 * _HOUR),
        dt.date(2024, 6, 4): pytest.approx(10.2 * _HOUR),
    }
    # the snow depth of the day beginning at 06:00 UTC is the reading of 07:00 UTC of that date (metObs
    # `snow_depth_man`: 4.0 on 2021-02-12, 3.0 on the 13th)
    assert _by_day(_values(monkeypatch, "daily", "28240", start, end), "snow_depth_manual") == {
        dt.date(2021, 2, 12): 4.0,
        dt.date(2021, 2, 13): 3.0,
        dt.date(2021, 2, 14): 3.0,
    }


def test_a_value_dmi_does_not_validate_keeps_its_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """The cloud cover of Nuuk in January 2024 is `validity: false`, which stays on its `quality_flags`."""
    df = _values(
        monkeypatch, "daily", "04250", dt.datetime(2024, 1, 10, tzinfo=_UTC), dt.datetime(2024, 1, 12, tzinfo=_UTC)
    )
    flags = df.filter(pl.col("parameter") == "cloud_cover_total_mean")["quality_flags"].unique().to_list()
    assert flags == ["manual,validity:false"]
    flags = df.filter(pl.col("parameter") == "humidity_relative_max")["quality_flags"].unique().to_list()
    assert flags == ["manual,validity:true"]


def test_monthly_sunshine_cloud_cover_and_counts_of_days(monkeypatch: pytest.MonkeyPatch) -> None:
    """06041, July 2023: 207.9 hours of sunshine, 23, 19 and 1 days of 0.1, 1 and 10 mm; Nuuk's cloud cover."""
    df = _values(
        monkeypatch, "monthly", "06041", dt.datetime(2023, 7, 1, tzinfo=_UTC), dt.datetime(2023, 7, 1, tzinfo=_UTC)
    )
    values = {row["parameter"]: row["value"] for row in df.iter_rows(named=True)}
    assert values == {
        "sunshine_duration": pytest.approx(207.9 * _HOUR),
        "count_days_precipitation_amount_ge_0_1mm": 23.0,
        "count_days_precipitation_amount_ge_1mm": 19.0,
        "count_days_precipitation_amount_ge_10mm": 1.0,
        "count_days_frost": 0.0,
        "count_days_ice": 0.0,
    }
    nuuk = _values(
        monkeypatch, "monthly", "04250", dt.datetime(2023, 7, 1, tzinfo=_UTC), dt.datetime(2023, 7, 1, tzinfo=_UTC)
    )
    assert {row["parameter"]: row["value"] for row in nuuk.iter_rows(named=True)} == {
        "cloud_cover_total_mean": pytest.approx(0.79)
    }


def test_annual_humidity_extremes_sunshine_cloud_cover_and_counts_of_days(monkeypatch: pytest.MonkeyPatch) -> None:
    """06041, 2023, and Nuuk's cloud cover: the annual humidity extremes the dataset left out, and the year's counts."""
    df = _values(
        monkeypatch, "annual", "06041", dt.datetime(2023, 1, 1, tzinfo=_UTC), dt.datetime(2023, 1, 1, tzinfo=_UTC)
    )
    values = {row["parameter"]: row["value"] for row in df.iter_rows(named=True)}
    assert values == {
        "humidity_relative_max": pytest.approx(0.998),
        "humidity_relative_min": pytest.approx(0.527),
        "sunshine_duration": pytest.approx(1853.1 * _HOUR),
        "count_days_precipitation_amount_ge_0_1mm": 194.0,
        "count_days_precipitation_amount_ge_1mm": 124.0,
        "count_days_precipitation_amount_ge_10mm": 23.0,
        "count_days_frost": 36.0,
        "count_days_ice": 6.0,
    }
    nuuk = _values(
        monkeypatch, "annual", "04250", dt.datetime(2023, 1, 1, tzinfo=_UTC), dt.datetime(2023, 1, 1, tzinfo=_UTC)
    )
    assert {row["parameter"]: row["value"] for row in nuuk.iter_rows(named=True)} == {
        "cloud_cover_total_mean": pytest.approx(0.80)
    }


def test_a_cloud_cover_above_the_whole_sky_is_null_and_keeps_its_text(monkeypatch: pytest.MonkeyPatch) -> None:
    """MetObs documents 112 for a sky obscured by fog beside the 0 to 100: it is no cloud cover (made-up record).

    No record of DMI's climate data carries it (68,107 hourly values of 2019 and 93,519 daily ones of 2011 to 2025
    read on 2026-10-30), so the 112 of 2024-06-03 12:00 is made up, beside the real 100 of an overcast sky.
    """
    records = [
        {**_RECORDS["hourly"][4], "value": 100.0},
        {**_RECORDS["hourly"][5], "value": 112.0},
    ]
    df = _values(
        monkeypatch,
        "hourly",
        "04250",
        dt.datetime(2024, 6, 3, 11, tzinfo=_UTC),
        dt.datetime(2024, 6, 3, 12, tzinfo=_UTC),
        drop_nulls=False,
        records=records,
    ).sort("timestamp")
    assert df.select("value", "quality_flags").rows() == [
        (1.0, "manual,validity:true"),
        (None, "manual,validity:true,raw:112"),
    ]
