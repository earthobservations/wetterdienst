# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The empty answers of the Met Office values, collected through `values().all()` from files served offline (GH-2627).

The provider hands the core its rows and nothing else: a station-year the archive lacks, a file with no data row and a
file whose only rows are accumulations all come out as the empty long form, whatever the provider handed over.
"""

from __future__ import annotations

import dataclasses
import datetime as dt

import polars as pl
import pytest

from tests.provider.value_stubs import _day, _options, _settings, stations_result
from wetterdienst.model.schema import LONG_SCHEMA
from wetterdienst.provider.metoffice.observation import MetOfficeObservationRequest
from wetterdienst.provider.metoffice.observation import api as metoffice_api
from wetterdienst.util.response_warnings import (
    OTHER_WINDOW_LEFT_OUT,
    PARAMETER_WITHOUT_ROWS,
    begin_response,
    recorded_warnings,
)

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
    energy type, MJ/m2 (1 kJ/m2 = 0.001 MJ/m2); the direct one is above the global one here, as it can be.
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
        "radiation_global": 1.5,
        "radiation_sky_short_wave_diffuse": 0.4,
        "radiation_sky_short_wave_direct_perpendicular": 2.1,
    }
    assert df["timestamp"].unique().to_list() == [dt.datetime(1996, 6, 1, 10, tzinfo=_UTC)]


_AIR_TEMPERATURES = [
    ("daily", "temperature", "temperature_air_max_2m"),
    ("daily", "temperature", "temperature_air_min_2m"),
]


def _daily_temperature(
    monkeypatch: pytest.MonkeyPatch,
    files: dict[int, bytes],
    end: dt.datetime,
    *,
    drop_nulls: bool = True,
    parameters: list[tuple[str, str, str]] | list[tuple[str, str]] | None = None,
    start: dt.datetime = dt.datetime(2000, 1, 1, tzinfo=_UTC),
    catalogue: list[tuple[str, int]] | None = None,
    years_read: list[int] | None = None,
) -> pl.DataFrame:
    """Collect the daily temperature of 00001 from `start` to `end`, the file of each year being in `files`.

    `catalogue` gives the rows of the station in the catalogue as `(dataset, first year)`, in that order, as a request
    for several datasets has one row for each; `years_read` is given the year of every file asked for.
    """

    def download(_self: object, url: str, *_args: object, **_kwargs: object) -> bytes | None:
        if "station-metadata" in url:
            return _STATIONS
        year = int(url.split("?", maxsplit=1)[0].rsplit("_", 1)[1].removesuffix(".csv"))
        if years_read is not None:
            years_read.append(year)
        return files.get(year)

    monkeypatch.setattr(metoffice_api.MetOfficeObservationValues, "_token", lambda _self, _settings: "token")
    monkeypatch.setattr(metoffice_api.MetOfficeObservationValues, "_download", download)
    monkeypatch.setattr(metoffice_api, "latest_release_version", lambda *_args, **_kwargs: "202507")
    request = MetOfficeObservationRequest(
        parameters=parameters or _AIR_TEMPERATURES,
        start=start,
        end=end,
        settings=_settings(),
        options=_options(drop_nulls=drop_nulls),
    )
    result = stations_result(request, "daily", "temperature", "00001")
    if catalogue:
        rows = pl.concat(
            [
                result.df.with_columns(
                    pl.lit(dataset).alias("dataset"),
                    pl.lit(dt.datetime(first_year, 1, 1, tzinfo=_UTC))
                    .cast(result.df.schema["start_timestamp"])
                    .alias("start_timestamp"),
                )
                for dataset, first_year in catalogue
            ]
        )
        result = dataclasses.replace(result, df=rows, _df_all=rows)
    return result.values().all().df


_TEMPERATURE_HEADER = (
    "ob_end_time,ob_hour_count,met_domain_name,max_air_temp,max_air_temp_q,min_air_temp,min_air_temp_q"
)


def test_a_12_hour_station_has_the_09_09z_day_and_a_day_without_a_half_is_told_not_returned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The daily maximum and minimum of a 12 hour station are the 24 hours ending 09Z, in the answer and its warnings.

    The 1st reads the evening of 1999-12-31 from the file of the year before; the 3rd has its night row and no evening
    of the 2nd, so it is no row and `other-window-left-out` says so, once for each parameter, with the one date
    (GH-3137). The day row of the 3rd belongs to the 4th, which is outside the window asked for.
    """
    files = {
        1999: _badc(_TEMPERATURE_HEADER, "1999-12-31 21:00:00,12,NCM,3.0,6,1.0,6\n"),
        2000: _badc(
            _TEMPERATURE_HEADER,
            "2000-01-01 09:00:00,12,NCM,2.0,6,0.5,6\n"
            "2000-01-01 21:00:00,12,NCM,4.0,6,1.5,6\n"
            "2000-01-02 09:00:00,12,NCM,3.5,6,0.2,6\n"
            "2000-01-03 09:00:00,12,NCM,2.0,6,-0.5,6\n"
            "2000-01-03 21:00:00,12,NCM,9.0,6,-0.1,6\n",
        ),
    }
    begin_response()
    df = _daily_temperature(monkeypatch, files, end=dt.datetime(2000, 1, 3, tzinfo=_UTC))

    assert df.sort("parameter", "timestamp").select("parameter", "timestamp", "value").rows() == [
        ("temperature_air_max_2m", _day(2000, 1, 1), 3.0),
        ("temperature_air_max_2m", _day(2000, 1, 2), 4.0),
        ("temperature_air_min_2m", _day(2000, 1, 1), 0.5),
        ("temperature_air_min_2m", _day(2000, 1, 2), 0.2),
    ]
    told = [w for w in recorded_warnings() if w["code"] == OTHER_WINDOW_LEFT_OUT]
    assert sorted(w["parameter"] for w in told) == [
        "daily/temperature/temperature_air_max_2m",
        "daily/temperature/temperature_air_min_2m",
    ]
    assert all("on 1 date that is not in the answer (00001 1)" in w["message"] for w in told)
    # a day that was left out is no "the source has no values"
    assert [w for w in recorded_warnings() if w["code"] == PARAMETER_WITHOUT_ROWS] == []


def test_a_24_hour_station_and_a_mixed_day_are_the_24_hour_row(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 24 hour station's row ending 09:00 is its day as given; a day with both kinds of row is the 24 hour row.

    The 2nd has a 24 hour row (5.0) beside the night (4.0) and the evening of the 1st (9.0), and the 2nd's own day row
    (22.3, which is the 3rd's evening) must not be the 2nd's maximum, as the old reader had it (GH-3137).
    """
    files = {
        2000: _badc(
            _TEMPERATURE_HEADER,
            "2000-01-01 09:00:00,24,DLY3208,6.0,6,1.0,6\n"
            "2000-01-01 21:00:00,12,AWSDLY,9.0,6,2.0,6\n"
            "2000-01-02 09:00:00,12,AWSDLY,4.0,6,0.5,6\n"
            "2000-01-02 09:00:00,24,DLY3208,5.0,4,0.5,4\n"
            "2000-01-02 21:00:00,12,AWSDLY,22.3,6,3.0,6\n",
        ),
    }
    df = _daily_temperature(monkeypatch, files, end=dt.datetime(2000, 1, 2, tzinfo=_UTC))

    assert df.sort("parameter", "timestamp").select("parameter", "timestamp", "value", "quality_flags").rows() == [
        ("temperature_air_max_2m", _day(2000, 1, 1), 6.0, "6"),
        ("temperature_air_max_2m", _day(2000, 1, 2), 5.0, "4"),
        ("temperature_air_min_2m", _day(2000, 1, 1), 1.0, "6"),
        ("temperature_air_min_2m", _day(2000, 1, 2), 0.5, "4"),
    ]


def test_the_catalogue_row_of_another_dataset_does_not_move_the_files_read(monkeypatch: pytest.MonkeyPatch) -> None:
    """The first year of a file is the one of the temperature row of the catalogue, not of another dataset's (GH-3137).

    A request for the daily rain and temperature has two rows for the station, and the rain row (first year 2005, first
    here) must not make the reader skip the 2000 file of the temperature, nor decide that the year before is not worth
    reading: 1999 is read, as the temperature begins in 1960, and the 1st takes the evening of 1999-12-31 from it.
    """
    files = {
        1999: _badc(_TEMPERATURE_HEADER, "1999-12-31 21:00:00,12,NCM,3.0,6,1.0,6\n"),
        2000: _badc(_TEMPERATURE_HEADER, "2000-01-01 09:00:00,12,NCM,2.0,6,0.5,6\n"),
    }
    years_read: list[int] = []
    df = _daily_temperature(
        monkeypatch,
        files,
        end=dt.datetime(2000, 12, 31, tzinfo=_UTC),
        parameters=[("daily", "rain"), *_AIR_TEMPERATURES],
        catalogue=[("rain", 2005), ("temperature", 1960)],
        years_read=years_read,
    )

    temperature = df.filter(pl.col("dataset") == "temperature")
    assert temperature.sort("parameter").select("parameter", "timestamp", "value").rows() == [
        ("temperature_air_max_2m", _day(2000, 1, 1), 3.0),
        ("temperature_air_min_2m", _day(2000, 1, 1), 0.5),
    ]
    assert 1999 in years_read
    assert 2000 in years_read


def test_the_year_before_the_first_file_of_the_station_is_not_asked_for(monkeypatch: pytest.MonkeyPatch) -> None:
    """A station whose catalogue begins in 2000 has no 1999 file, and the first day is not told as left out for it.

    The year is only ever added to the range, and not where the catalogue says there is no such file.
    """
    files = {2000: _badc(_TEMPERATURE_HEADER, "2000-01-01 09:00:00,24,DLY3208,2.0,6,0.5,6\n")}
    years_read: list[int] = []
    df = _daily_temperature(
        monkeypatch,
        files,
        end=dt.datetime(2000, 1, 1, tzinfo=_UTC),
        catalogue=[("temperature", 2000)],
        years_read=years_read,
    )

    assert sorted(set(years_read)) == [2000]
    assert df.sort("parameter")["value"].to_list() == [2.0, 0.5]


def test_only_the_parameters_asked_for_are_told_as_left_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """The dataset is read whole, and `other-window-left-out` names the parameters of the answer only (GH-3137).

    A request for the maximum alone must not name the minimum: a parameter that a provider names is one whose
    station the walk counts as explained, and the estimates count it as a source's day left out.
    """
    files = {
        2000: _badc(
            _TEMPERATURE_HEADER,
            "2000-01-02 09:00:00,12,NCM,3.5,6,0.2,6\n2000-01-03 21:00:00,12,NCM,9.0,6,1.0,6\n",
        )
    }
    begin_response()
    _daily_temperature(
        monkeypatch,
        files,
        end=dt.datetime(2000, 1, 4, tzinfo=_UTC),
        parameters=[("daily", "temperature", "temperature_air_max_2m")],
        catalogue=[("temperature", 1960)],
    )

    told = [w for w in recorded_warnings() if w["code"] == OTHER_WINDOW_LEFT_OUT]
    assert [w["parameter"] for w in told] == ["daily/temperature/temperature_air_max_2m"]
    assert "temperature_air_min_2m" not in told[0]["message"]


def test_the_grass_minimum_of_a_12_hour_station_is_its_21_09z_row_and_is_never_left_out(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The maintainer's decision (GH-3137): the 21-09Z row stands for the 09-09Z window of the grass minimum.

    No 09-21Z row has a grass minimum (the evening rows write `NA`), so at a 12 hour station the day is the night row
    ending 09:00, and the day is not left out for the evening it lacks; the air temperatures of the same rows need
    both halves, so the 1st (a night row and no evening of 1999-12-31) has the grass minimum and neither air
    temperature, which are told as left out. On the 3rd a 24 hour row wins over the night row beside it.
    """
    header = (
        "ob_end_time,ob_hour_count,met_domain_name,max_air_temp,max_air_temp_q,min_air_temp,min_air_temp_q,"
        "min_grss_temp,min_grss_temp_q"
    )
    files = {
        2000: _badc(
            header,
            "2000-01-01 09:00:00,12,NCM,2.0,6,0.5,6,-1.5,6\n"
            "2000-01-01 21:00:00,12,NCM,4.0,6,1.5,6,NA,NA\n"
            "2000-01-02 09:00:00,12,NCM,3.5,6,0.2,6,-2.5,6\n"
            "2000-01-03 09:00:00,12,NCM,3.0,6,0.1,6,-0.5,6\n"
            "2000-01-03 09:00:00,24,DLY3208,3.2,4,-0.3,4,-3.0,4\n",
        )
    }
    begin_response()
    df = _daily_temperature(
        monkeypatch,
        files,
        end=dt.datetime(2000, 1, 3, tzinfo=_UTC),
        parameters=[
            *_AIR_TEMPERATURES,
            ("daily", "temperature", "temperature_air_min_0_05m"),
        ],
    )

    grass = df.filter(pl.col("parameter") == "temperature_air_min_0_05m").sort("timestamp")
    assert grass.select("timestamp", "value", "quality_flags").rows() == [
        (_day(2000, 1, 1), -1.5, "6"),
        (_day(2000, 1, 2), -2.5, "6"),
        (_day(2000, 1, 3), -3.0, "4"),
    ]
    # the 1st has no evening before it, the 2nd has the evening of the 1st
    assert df.filter(pl.col("parameter") == "temperature_air_max_2m").sort("timestamp").select(
        "timestamp", "value"
    ).rows() == [
        (_day(2000, 1, 2), 4.0),
        (_day(2000, 1, 3), 3.2),
    ]
    told = [w for w in recorded_warnings() if w["code"] == OTHER_WINDOW_LEFT_OUT]
    assert sorted(w["parameter"] for w in told) == [
        "daily/temperature/temperature_air_max_2m",
        "daily/temperature/temperature_air_min_2m",
    ]
