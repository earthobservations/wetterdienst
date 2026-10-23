# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The empty answers of the Met Office values, collected through `values().all()` from files served offline (GH-2627).

The provider hands the core its rows and nothing else: a station-year the archive lacks, a file with no data row and a
file whose only rows are accumulations all come out as the empty long form, whatever the provider handed over.
"""

from __future__ import annotations

import datetime as dt

import polars as pl
import pytest

from tests.provider.value_stubs import _options, _settings, stations_result
from wetterdienst.model.schema import LONG_SCHEMA
from wetterdienst.provider.metoffice.observation import MetOfficeObservationRequest
from wetterdienst.provider.metoffice.observation import api as metoffice_api

_UTC = dt.UTC


def _badc(columns: str, rows: str) -> bytes:
    return f"Conventions,G,BADC-CSV,1\ndata\n{columns}\n{rows}end data\n".encode()


_STATIONS = _badc(
    "src_id,station_name,station_file_name,historic_county,authority,"
    "station_latitude,station_longitude,station_elevation,first_year,last_year",
    "00001,FOULA,foula,shetland,Met Office,60.154,-2.074,22,1989,2003\n",
)
_HEADER = "ob_date,ob_day_cnt,prcp_amt,prcp_amt_q"


def _daily_rain(monkeypatch: pytest.MonkeyPatch, values: bytes | None) -> pl.DataFrame:
    """Collect the daily rain of 00001 for 2000-01-01/02, the station-year file being `values` (None: no such file)."""

    def download(_self: object, url: str, *_args: object, **_kwargs: object) -> bytes | None:
        return _STATIONS if "station-metadata" in url else values

    monkeypatch.setattr(metoffice_api.MetOfficeObservationValues, "_token", lambda _self, _settings: "token")
    monkeypatch.setattr(metoffice_api.MetOfficeObservationValues, "_download", download)
    monkeypatch.setattr(metoffice_api, "latest_release_version", lambda *_args, **_kwargs: "202507")
    request = MetOfficeObservationRequest(
        parameters=[("daily", "rain")],
        start=dt.datetime(2000, 1, 1, tzinfo=_UTC),
        end=dt.datetime(2000, 1, 2, tzinfo=_UTC),
        settings=_settings(),
        options=_options(drop_nulls=True),
    )
    return stations_result(request, "daily", "rain", "00001").values().all().df


@pytest.mark.parametrize(
    "values",
    [
        pytest.param(None, id="no station-year file"),
        pytest.param(_badc(_HEADER, ""), id="a file with no data row"),
        pytest.param(_badc(_HEADER, "2000-01-01 00:00:00,31,41.2,2576\n"), id="only a 31-day accumulation"),
    ],
)
def test_a_station_without_rows_is_the_empty_long_form(monkeypatch: pytest.MonkeyPatch, values: bytes | None) -> None:
    """Whatever the provider hands over of a station-year without a reading, the core makes the empty long form."""
    df = _daily_rain(monkeypatch, values)
    assert df.is_empty()
    assert df.schema == pl.Schema(LONG_SCHEMA)


def test_a_station_year_with_rows_comes_out_as_the_long_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """The rows the provider hands over are given the station, resolution and dataset by the core."""
    df = _daily_rain(monkeypatch, _badc(_HEADER, "2000-01-01 00:00:00,1,3.7,2576\n2000-01-02 00:00:00,1,0.2,0\n"))
    assert df.schema == pl.Schema(LONG_SCHEMA)
    assert df["station_id"].unique().to_list() == ["00001"]
    assert df["resolution"].unique().to_list() == ["daily"]
    assert df["dataset"].unique().to_list() == ["rain"]
    assert df.sort("timestamp")["value"].to_list() == [3.7, 0.2]


def test_the_direct_irradiation_comes_out_under_the_name_of_the_energy_perpendicular_to_the_beam(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`direct_irad` is `radiation_sky_short_wave_direct_perpendicular`, an energy of the hour (GH-3316).

    The MIDAS table RO has a pyrheliometer measure it "at normal incidence", in "Kjoules/ sq metre over the observation
    period"; the global and the diffuse radiation are on a horizontal surface. The hourly file holds a 24 hour total
    beside the hour (`ob_hour_count`), which is no value of the hour. The values are the file's kJ/m2 in the unit of the
    energy type, J/cm2 (1 kJ/m2 = 0.1 J/cm2); the direct one is above the global one here, as it can be.
    """
    values = _badc(
        "ob_end_time,ob_hour_count,glbl_irad_amt,glbl_irad_amt_q,difu_irad_amt,difu_irad_amt_q,direct_irad,direct_irad_q",
        "1996-06-01 10:00:00,1,1500,1,400,1,2100,1\n1996-06-01 23:59:00,24,19000,1,5000,1,21000,1\n",
    )

    def download(_self: object, url: str, *_args: object, **_kwargs: object) -> bytes | None:
        return _STATIONS if "station-metadata" in url else values

    monkeypatch.setattr(metoffice_api.MetOfficeObservationValues, "_token", lambda _self, _settings: "token")
    monkeypatch.setattr(metoffice_api.MetOfficeObservationValues, "_download", download)
    monkeypatch.setattr(metoffice_api, "latest_release_version", lambda *_args, **_kwargs: "202507")
    request = MetOfficeObservationRequest(
        parameters=[
            ("hourly", "radiation", "radiation_global"),
            ("hourly", "radiation", "radiation_sky_short_wave_diffuse"),
            ("hourly", "radiation", "radiation_sky_short_wave_direct_perpendicular"),
        ],
        start=dt.datetime(1996, 6, 1, tzinfo=_UTC),
        end=dt.datetime(1996, 6, 2, tzinfo=_UTC),
        settings=_settings(),
        options=_options(drop_nulls=True),
    )
    df = stations_result(request, "hourly", "radiation", "00001").values().all().df
    assert dict(df.select("parameter", "value").iter_rows()) == {
        "radiation_global": 150.0,
        "radiation_sky_short_wave_diffuse": 40.0,
        "radiation_sky_short_wave_direct_perpendicular": 210.0,
    }
    assert df["timestamp"].unique().to_list() == [dt.datetime(1996, 6, 1, 10, tzinfo=_UTC)]
