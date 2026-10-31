# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The daily elements of GH-3622 (ADPT, ASLP, ASTP, AWBT, AWDR, RHAV, RHMN, RHMX), read from rows NOAA wrote.

`daily_published_elements_blue_hill.csv` and `daily_published_elements_mcneil_river.csv` hold rows of the per-station
files at ncei.noaa.gov/data/global-historical-climatology-network-daily/access/ of USW00014753 (Blue Hill, MA) and
USS0054K01S (McNeil River, AK), read key-less on 2026-10-30 and cut to the columns of these elements. The values are
the tenths of the readme (degrees C, hPa), the ones NOAA writes.
"""

import datetime as dt
from pathlib import Path

import polars as pl
import pytest

from tests.provider.value_stubs import serve
from wetterdienst import Options, Settings
from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest, api
from wetterdienst.provider.noaa.ghcn.metadata import NoaaGhcnMetadata

_HERE = Path(__file__).parent
_BLUE_HILL = (_HERE / "daily_published_elements_blue_hill.csv").read_bytes()
_MCNEIL_RIVER = (_HERE / "daily_published_elements_mcneil_river.csv").read_bytes()
_STATIONS = (
    "USW00014753  42.2123  -71.1137  190.5 MA BLUE HILL LCD                                 72518\n"
    "USS0054K01S  59.0800 -154.2800   42.7 AK MCNEIL RIVER SGS                                  \n"
)
_INVENTORY = "USW00014753  42.2123  -71.1137 ADPT 2006 2009\nUSS0054K01S  59.0800 -154.2800 AWDR 2019 2026\n"
# the element of the readme, the canonical name and the unit of the model: the statistic the readme states ("Average
# ... for the day", "Minimum ...", "Maximum ...") is the one of the name (GH-2614)
_MAPPING = {
    "adpt": ("temperature_dew_point_mean_2m", "degree_celsius"),
    "aslp": ("pressure_air_sea_level_mean", "hectopascal"),
    "astp": ("pressure_air_site_mean", "hectopascal"),
    "awbt": ("temperature_wet_mean_2m", "degree_celsius"),
    "awdr": ("wind_direction_mean", "degree"),
    "rhav": ("humidity_relative_mean", "percent"),
    "rhmn": ("humidity_relative_min", "percent"),
    "rhmx": ("humidity_relative_max", "percent"),
}


def _daily(
    monkeypatch: pytest.MonkeyPatch,
    station: str,
    body: bytes,
    parameters: list[str],
    start: str,
    end: str,
    *,
    drop_nulls: bool = True,
) -> pl.DataFrame:
    serve(
        monkeypatch,
        api,
        {
            "ghcnd-stations": _STATIONS.encode("utf8"),
            "ghcnd-inventory": _INVENTORY.encode("utf8"),
            f"access/{station}": body,
        },
    )
    request = NoaaGhcnRequest(
        parameters=[("daily", "data", name) for name in parameters],
        start=start,
        end=end,
        settings=Settings(cache_disable=True),
        options=Options(drop_nulls=drop_nulls),
    ).filter_by_station_id(station)
    return request.values().all().df


@pytest.mark.parametrize(("element", "mapping"), list(_MAPPING.items()))
def test_a_daily_element_is_mapped_to_the_name_of_its_statistic(element: str, mapping: tuple[str, str]) -> None:
    """Each element is declared with the canonical name of the statistic the readme states, in the readme's unit."""
    parameter = next(p for p in NoaaGhcnMetadata["daily"].datasets[0].parameters if p.name_original == element)
    assert (parameter.name, parameter.unit) == mapping


def test_the_tenths_of_the_readme_come_back_as_degrees_and_hectopascal(monkeypatch: pytest.MonkeyPatch) -> None:
    """Blue Hill, 2006-01-01, 2006-01-02 and 2007-08-02: ADPT -50 is -5.0 degrees C, ASLP 10179 is 1017.9 hPa."""
    names = [name for name, _ in _MAPPING.values() if name != "wind_direction_mean"]
    df = _daily(monkeypatch, "USW00014753", _BLUE_HILL, names, "2006-01-01", "2007-08-02")
    first = df.filter(pl.col("timestamp") == dt.datetime(2006, 1, 1, tzinfo=dt.UTC))
    values = {row["parameter"]: row["value"] for row in first.iter_rows(named=True)}
    assert values == {
        "temperature_dew_point_mean_2m": pytest.approx(-5.0),
        "pressure_air_sea_level_mean": pytest.approx(1017.9),
        "pressure_air_site_mean": pytest.approx(991.5),
        "temperature_wet_mean_2m": pytest.approx(-4.4),
        # percent becomes the decimal fraction every provider returns it as
        "humidity_relative_mean": pytest.approx(0.96),
        "humidity_relative_min": pytest.approx(0.91),
        "humidity_relative_max": pytest.approx(1.0),
    }
    last = df.filter(pl.col("timestamp") == dt.datetime(2007, 8, 2, tzinfo=dt.UTC))
    assert {row["parameter"]: row["value"] for row in last.iter_rows(named=True)} == {
        "temperature_dew_point_mean_2m": pytest.approx(18.3),
        "pressure_air_sea_level_mean": pytest.approx(1016.3),
        "pressure_air_site_mean": pytest.approx(992.5),
        "temperature_wet_mean_2m": pytest.approx(21.1),
        "humidity_relative_mean": pytest.approx(0.61),
        "humidity_relative_min": pytest.approx(0.42),
        "humidity_relative_max": pytest.approx(0.81),
    }
    # the source flag of the summary of the day from ISD is the only flag
    assert df["quality_flags"].unique().to_list() == ["source:W"]


def test_the_average_wind_direction_of_0_is_null_beside_a_speed_of_0_and_a_bearing_beside_a_wind(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """McNeil River: a 0 beside an AWND of 0 is a calm and null with `raw:0`; beside 24 (tenths) it stays (GH-3222).

    The rows are NOAA's: 2020-11-09 AWDR 0 with AWND 24, 2023-12-19 AWDR 189 with AWND 0 (a direction beside no wind
    stays: only the 0 is a calm), 2023-12-20 AWDR 0 with AWND 0, 2025-06-30 AWDR 360 with AWND 12.
    """
    df = _daily(
        monkeypatch,
        "USS0054K01S",
        _MCNEIL_RIVER,
        ["wind_direction_mean", "wind_speed_mean"],
        "2020-11-09",
        "2025-06-30",
        drop_nulls=False,
    )
    direction = df.filter(pl.col("parameter") == "wind_direction_mean").sort("timestamp")
    assert direction.select(pl.col("timestamp").dt.date(), "value", "quality_flags").rows() == [
        (dt.date(2020, 11, 9), 0.0, "source:T"),
        (dt.date(2023, 12, 19), 189.0, "source:T"),
        (dt.date(2023, 12, 20), None, "source:T,raw:0"),
        (dt.date(2025, 6, 30), 360.0, "source:T"),
    ]
    speed = df.filter(pl.col("parameter") == "wind_speed_mean").sort("timestamp")
    assert speed["value"].to_list() == pytest.approx([2.4, 0.0, 0.0, 1.2])
    assert speed["quality_flags"].unique().to_list() == ["source:T"]
