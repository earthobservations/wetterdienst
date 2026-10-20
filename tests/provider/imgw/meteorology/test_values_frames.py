# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The frames the core hands out for IMGW meteorology, collected through the provider's own reader (GH-2627).

No offline test collected values of this network: its tests read the files (`_parse_file`, `_parse_csv`) and the
collection was held by remote tests alone. The files are the shapes IMGW writes (a status beside every value, the
`8` of no measurement and the `9` of no phenomenon, the days `o_d` leaves out), served as the zips the provider
downloads, and `tests/provider/frames.snapshot.json` records what the core made of each: the net under moving the shaping
of the frame out of the provider.
"""

from __future__ import annotations

import datetime as dt
import zipfile
from io import BytesIO

import polars as pl
import pytest

from tests.provider.value_stubs import _day, _options, _settings, stations_result
from wetterdienst.model.schema import LONG_SCHEMA
from wetterdienst.provider.imgw.meteorology import ImgwMeteorologyRequest
from wetterdienst.provider.imgw.meteorology import api as imgw_meteorology_api
from wetterdienst.util.network import File

UTC = dt.UTC
STATION = "249180020"

# one row of `k_d`, and of `k_d_t` beside it, for KRAKOW on 2024-04-01 (the rows of test_api.py)
_K_D = '"250190390","KRAKÓW-OBSERWATORIUM","2024","04","01",26.4,"",10.9,"",18.6,"",5.5,"",10.0,"","W",0,"9"'
_K_D_T = '"250190390","KRAKÓW-OBSERWATORIUM","2024","04","01",18.6,"",60.5,"",1.7,"",7.3,""'


def _o_d_line(day: int, value: str, status: str) -> str:
    """Give one row of `o_d`: field 6 is `SMDB` and field 7 its status, the snow columns say "not measured"."""
    fields = [""] * 16
    fields[0] = STATION
    fields[1] = "WARSZOWICE"
    fields[2] = "2010"
    fields[3] = "02"
    fields[4] = f"{day:02d}"
    fields[5] = value
    fields[6] = status
    fields[8] = "0"
    fields[9] = "8"
    fields[10] = "0"
    fields[11] = "8"
    return ",".join(fields)


def _k_m_d_line(month: int, *, precipitation: str, status: str = "") -> str:
    """Give one row of `k_m_d`: every pair a value and its status, the day counts at the end carry none."""
    fields = ["0"] * 27
    fields[0] = "249180010"
    fields[1] = "PSZCZYNA"
    fields[2] = "2010"
    fields[3] = str(month)
    # absolute and mean maximum, absolute and mean minimum, mean temperature, minimum at the ground
    for position, value in zip((4, 6, 8, 10, 12, 14), ("14.2", "3.1", "-12.4", "-5.0", "-1.2", "-15.0"), strict=True):
        fields[position] = value
        fields[position + 1] = ""
    fields[16] = precipitation
    fields[17] = status
    fields[18] = "6.1"
    fields[19] = ""
    fields[22] = "21"
    fields[23] = ""
    return ",".join(fields)


def _serve(monkeypatch: pytest.MonkeyPatch, name: str, files: dict[str, str]) -> None:
    archive = BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        for member, text in files.items():
            zf.writestr(member, text.encode("latin-1"))
    url = f"https://example.invalid/{name}"
    monkeypatch.setattr(imgw_meteorology_api, "list_files_for_interval", lambda *args, **kwargs: [url])  # noqa: ARG005
    monkeypatch.setattr(
        imgw_meteorology_api,
        "download_files",
        lambda *args, **kwargs: [File(url=url, content=BytesIO(archive.getvalue()), status=200)],  # noqa: ARG005
    )


def _values(
    resolution: str,
    dataset: str,
    station_id: str,
    start: dt.datetime,
    end: dt.datetime,
    *,
    drop_nulls: bool = True,
) -> pl.DataFrame:
    request = ImgwMeteorologyRequest(
        parameters=[(resolution, dataset)],
        start=start,
        end=end,
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return stations_result(request, resolution, dataset, station_id).values().all().df


def _assert_the_long_form(df: pl.DataFrame, *, resolution: str, dataset: str, station_id: str) -> None:
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df["resolution"].unique().to_list() == [resolution]
    assert df["dataset"].unique().to_list() == [dataset]
    assert df["station_id"].unique().to_list() == [station_id]
    assert df["timestamp"].dtype == pl.Datetime("us", "UTC")


def test_imgw_meteorology_daily_precipitation_comes_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The statuses decide the nulls and the zeros, and a day the file leaves out of its month is a dry day."""
    lines = [
        _o_d_line(1, ".2", ""),
        _o_d_line(3, "2.1", ""),
        _o_d_line(5, ".0", "8"),
        _o_d_line(7, "", "9"),
        _o_d_line(9, "7.4", "Z"),
    ]
    _serve(monkeypatch, "2010_02_o.zip", {"o_d_02_2010.csv": "\n".join(lines)})
    start, end = _day(2010, 2, 1), _day(2010, 2, 28)
    df = _values("daily", "precipitation", STATION, start, end)
    _assert_the_long_form(df, resolution="daily", dataset="precipitation", station_id=STATION)
    precipitation = df.filter(pl.col("parameter").eq("precipitation_amount")).sort("timestamp")
    # the day with the status 8 is no measurement and is dropped, the 27 others are the days of the month
    assert precipitation.height == 27
    kept = precipitation.filter(pl.col("timestamp").dt.day().is_in([1, 3, 7, 9]))
    assert kept["value"].to_list() == [0.2, 2.1, 0.0, 7.4]
    assert kept["quality_flags"].to_list() == [None, None, "9", "Z"]
    everything = _values("daily", "precipitation", STATION, start, end, drop_nulls=False)
    day_5 = everything.filter(pl.col("parameter").eq("precipitation_amount"), pl.col("timestamp").dt.day().eq(5))
    assert day_5["value"].to_list() == [None]
    assert day_5["quality_flags"].to_list() == ["8"]


def test_imgw_meteorology_daily_climate_comes_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """Both files of a zip are read, the one of the climate and its temperature, humidity, wind and cloud cover."""
    _serve(monkeypatch, "2024_04_k.zip", {"k_d_04_2024.csv": _K_D, "k_d_t_04_2024.csv": _K_D_T})
    df = _values("daily", "climate", "250190390", _day(2024, 4, 1), _day(2024, 4, 1))
    _assert_the_long_form(df, resolution="daily", dataset="climate", station_id="250190390")
    assert df["timestamp"].unique().to_list() == [dt.datetime(2024, 4, 1, tzinfo=UTC)]
    by_parameter = dict(zip(df["parameter"], df["value"], strict=True))
    assert by_parameter["humidity_relative_mean"] == 0.605
    assert by_parameter["temperature_air_max_2m"] == 26.4


def test_imgw_meteorology_monthly_climate_comes_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The months of a file are the monthly rows, stamped at the first of the month."""
    lines = [_k_m_d_line(1, precipitation="31.4"), _k_m_d_line(2, precipitation=".0", status="8")]
    _serve(monkeypatch, "2010_m_k.zip", {"k_m_d_2010.csv": "\n".join(lines)})
    df = _values("monthly", "climate", "249180010", _day(2010, 1, 1), _day(2010, 3, 1))
    _assert_the_long_form(df, resolution="monthly", dataset="climate", station_id="249180010")
    assert sorted(df["timestamp"].unique().to_list()) == [
        dt.datetime(2010, 1, 1, tzinfo=UTC),
        dt.datetime(2010, 2, 1, tzinfo=UTC),
    ]
    rain = df.filter(pl.col("parameter").eq("precipitation_amount"))
    assert rain["value"].to_list() == [31.4]


def test_imgw_meteorology_a_station_without_a_row_comes_out_as_the_empty_long_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The file holds rows of another station only: no rows, the empty long form."""
    _serve(monkeypatch, "2010_02_o.zip", {"o_d_02_2010.csv": _o_d_line(1, ".2", "").replace(STATION, "250000000")})
    df = _values("daily", "precipitation", STATION, _day(2010, 2, 1), _day(2010, 2, 28))
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df.is_empty()
