# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The frames the core hands out for IMGW hydrology's monthly values and its empty answer (GH-2627).

The daily values are held by the stub of `test_value_stubs.py`; the monthly files, which carry the extremity of the
month in a column of their own, and a station the files hold no row of, had no offline test through the core. The files
are the shapes IMGW writes, served as the zips the provider downloads, and `tests/provider/frames.snapshot.json`
records what the core made of each: the net under moving the shaping of the frame out of the provider.
"""

from __future__ import annotations

import datetime as dt
import zipfile
from io import BytesIO

import polars as pl
import pytest

from tests.provider.value_stubs import _day, _options, _settings, stations_result
from wetterdienst.model.schema import LONG_SCHEMA
from wetterdienst.provider.imgw.hydrology import ImgwHydrologyRequest
from wetterdienst.provider.imgw.hydrology import api as imgw_hydrology_api
from wetterdienst.util.network import File

UTC = dt.UTC
STATION = "149180020"


def _serve(monkeypatch: pytest.MonkeyPatch, name: str, member: str, csv: str) -> None:
    archive = BytesIO()
    with zipfile.ZipFile(archive, "w") as zf:
        zf.writestr(member, csv.encode("latin-1"))
    url = f"https://example.invalid/{name}"
    monkeypatch.setattr(imgw_hydrology_api, "list_files_for_interval", lambda *args, **kwargs: [url])  # noqa: ARG005
    monkeypatch.setattr(
        imgw_hydrology_api,
        "download_files",
        lambda *args, **kwargs: [File(url=url, content=BytesIO(archive.getvalue()), status=200)],  # noqa: ARG005
    )


def _values(resolution: str, start: dt.datetime, end: dt.datetime, *, drop_nulls: bool = True) -> pl.DataFrame:
    request = ImgwHydrologyRequest(
        parameters=[(resolution, "hydrology")],
        start=start,
        end=end,
        settings=_settings(),
        options=_options(drop_nulls),
    )
    return stations_result(request, resolution, "hydrology", STATION).values().all().df


def test_imgw_hydrology_monthly_values_come_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """A month is three rows, the minimum, the mean and the maximum, named in the parameter; 9999 is no stage."""
    # station, name, river, hydrological year, month, extremity, stage, discharge, water temperature
    csv = (
        "149180020,CHALUPKI,Odra,2023,03,1,120,10.1,5.0\n"
        "149180020,CHALUPKI,Odra,2023,03,2,141,12.5,9.9\n"
        "149180020,CHALUPKI,Odra,2023,03,3,9999,15.0,12.3\n"
    )
    _serve(monkeypatch, "mies_2023.zip", "mies_2023_03.csv", csv)
    df = _values("monthly", _day(2023, 1, 1), _day(2023, 1, 31))
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df["resolution"].unique().to_list() == ["monthly"]
    assert df["dataset"].unique().to_list() == ["hydrology"]
    assert df["station_id"].unique().to_list() == [STATION]
    assert df["timestamp"].unique().to_list() == [dt.datetime(2023, 1, 1, tzinfo=UTC)]
    by_parameter = dict(zip(df["parameter"], df["value"], strict=True))
    assert by_parameter["stage_min"] == 120.0
    assert by_parameter["discharge_mean"] == 12.5
    assert by_parameter["temperature_water_max"] == 12.3
    assert "stage_max" not in by_parameter
    everything = _values("monthly", _day(2023, 1, 1), _day(2023, 1, 31), drop_nulls=False)
    sentinel = everything.filter(pl.col("parameter").eq("stage_max"))
    assert sentinel["value"].to_list() == [None]
    assert sentinel["quality_flags"].to_list() == ["raw:9999"]


def test_imgw_hydrology_a_station_without_a_row_comes_out_as_the_empty_long_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The file holds rows of another station only: no rows, the empty long form."""
    csv = "150190130,LAGISZA,Brynica,2023,03,15,141,12.5,9.9\n"
    _serve(monkeypatch, "codz_2023_03.zip", "codz_2023_03.csv", csv)
    df = _values("daily", _day(2023, 1, 1), _day(2023, 1, 31))
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df.is_empty()
