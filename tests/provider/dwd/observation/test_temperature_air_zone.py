# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the time zone of the hourly air temperature stamps of DWD observations (GH-2709)."""

import datetime as dt
import zipfile
from io import BytesIO

import polars as pl
import pytest

from tests.provider.value_stubs import stations_result
from wetterdienst import Options, Settings
from wetterdienst.metadata.period import Period
from wetterdienst.provider.dwd.observation import DwdObservationMetadata, DwdObservationRequest
from wetterdienst.provider.dwd.observation import api as dwd_observation_api
from wetterdienst.provider.dwd.observation import download as dwd_observation_download
from wetterdienst.provider.dwd.observation.download import ProductFile, download_climate_observations_data
from wetterdienst.util.network import File

_URL = "https://example.invalid/stundenwerte_TU_00222_hist.zip"

_HEADER = (
    "Stations_ID;Von_Datum;Bis_Datum;Stationsname;Parameter;Parameterbeschreibung;Einheit;"
    "Datenquelle (Strukturversion=SV);Zusatz-Info;Besonderheiten;Literaturhinweis;eor;\n"
)
_FOOTER = "Legende: FT  = Folgetag; GZ = Gesetzliche Zeit\ngenerierte: 22.04.2026 --  Deutscher Wetterdienst  --\n"


def _row(parameter: str, first: str, last: str, info: str) -> str:
    return f"222;{first};{last};Aue;{parameter};x;x;Daten der Temperatur;Stundenwerte in {info};;;eor;\n"


# What stundenwerte_TU_00222_*_hist.zip of Aue has, reduced to the periods around the changes (read 2026-10-16): the
# two parameters share one stamp column and have their own table of periods. TT_TU is MEZ (MD) from 1982 and RF_TU
# MEZ until 1990-12-31 and MEZ (MD) from 1991-01-01 (as 01048 and most of the 42 stations with two tables); both
# change to UTC on 1991-11-01, the day the MD period ends and the UTC one begins.
_METADATA = (
    _HEADER
    + _row("RF_TU", "19820101", "19901231", "MEZ")
    + _row("RF_TU", "19910101", "19911101", "MEZ (MD)")
    + _row("RF_TU", "19911101", "20010401", "UTC")
    + _row("TT_TU", "19820101", "19911101", "MEZ (MD)")
    + _row("TT_TU", "19911101", "20010401", "UTC")
    + _FOOTER
).encode("latin-1")

# the rows around the changes: the last hour of 1990, the first of 1991 (RF_TU is MEZ (MD) from the stamp 00 on),
# the last two of 1991-10-31 and the day of the change, whose stamp 00 is the last MEZ one
_PRODUCT = (
    "STATIONS_ID;MESS_DATUM;QN_9;TT_TU;RF_TU;eor\n"
    "        222;1990123123;    3;  -2.0;  81.0;eor\n"
    "        222;1991010100;    3;  -2.5;  82.0;eor\n"
    "        222;1991010101;    3;  -3.0;  83.0;eor\n"
    "        222;1991103123;    3;   5.0;  -999;eor\n"
    "        222;1991110100;    3;   4.0;  91.0;eor\n"
    "        222;1991110101;    3;   3.5;  -999;eor\n"
    "        222;1991110200;    3;   3.0;  93.0;eor\n"
).encode("latin-1")


def _archive(metadata: bytes | None, product: bytes = _PRODUCT) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        if metadata is not None:
            archive.writestr("Metadaten_Parameter_tu_stunde_00222.txt", metadata)
        archive.writestr("produkt_tu_stunde_19820101_20251231_00222.txt", product)
    return buffer.getvalue()


def _serve(monkeypatch: pytest.MonkeyPatch, archive: bytes) -> None:
    monkeypatch.setattr(
        dwd_observation_download,
        "download_files",
        lambda **_kwargs: [File(url=_URL, content=BytesIO(archive), status=200)],
    )


def _at(*args: int) -> dt.datetime:
    return dt.datetime(*args, tzinfo=dt.UTC)


def test_the_mez_md_periods_are_read_per_parameter_from_the_metadata_of_the_archive(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """Test that the MEZ (MD) stamps of each parameter come from its own table of periods, and the seams from the day.

    `RF_TU` is plain MEZ before 1991, which is not shifted. On the day the MD period of `TT_TU` ends and the UTC one
    begins the clock changes after the stamp 00 (18 of 18 readings against NOAA ISD), so the period ends there.
    """
    _serve(monkeypatch, _archive(_METADATA))
    (file,) = download_climate_observations_data(
        pl.Series(["unused"]), default_settings, DwdObservationMetadata.hourly.temperature_air
    )
    assert isinstance(file, ProductFile)
    assert file.mez_md_spans == {
        "tt_tu": ((_at(1982, 1, 1, 0), _at(1991, 11, 1, 0)),),
        "rf_tu": ((_at(1991, 1, 1, 0), _at(1991, 11, 1, 0)),),
    }
    # the product file is the content, as before
    assert file.content.read() == _PRODUCT


def test_an_mez_md_period_that_begins_on_the_day_another_ends_starts_at_the_stamp_01(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """Test that the stamp 00 of the day the clock changes to MEZ (MD) is still the one of the period before.

    Fichtelberg 01358 changes from UTC to MEZ (MD) on 1991-05-11: its stamp 00 equals the NOAA ISD report of 00 UTC, its
    stamp 01 the one of 00 UTC again. An open end runs on.
    """
    metadata = (
        _HEADER + _row("TT_TU", "19910502", "19910511", "UTC") + _row("TT_TU", "19910511", "", "MEZ (MD)") + _FOOTER
    ).encode("latin-1")
    _serve(monkeypatch, _archive(metadata))
    (file,) = download_climate_observations_data(
        pl.Series(["unused"]), default_settings, DwdObservationMetadata.hourly.temperature_air
    )
    assert isinstance(file, ProductFile)
    assert file.mez_md_spans == {"tt_tu": ((_at(1991, 5, 11, 1), _at(9999, 12, 31, 23)),)}


@pytest.mark.parametrize(
    "archive",
    [
        _archive(None),
        _archive(
            (
                _HEADER + _row("TT_TU", "19820101", "19911101", "UTC") + _row("TT_TU", "19911101", "", "MEZ") + _FOOTER
            ).encode("latin-1")
        ),
        _archive(
            (_HEADER + "222;19820101;not a date;Aue;TT_TU;x;x;x;Stundenwerte in MEZ (MD);;;eor;\n" + _FOOTER).encode(
                "latin-1"
            )
        ),
    ],
    ids=["no metadata", "plain MEZ and UTC only", "unreadable date"],
)
def test_an_archive_without_an_mez_md_period_has_none(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings, archive: bytes
) -> None:
    """Test that a stamp is not shifted on a guess: no metadata, plain MEZ, UTC or a period that does not read."""
    _serve(monkeypatch, archive)
    (file,) = download_climate_observations_data(
        pl.Series(["unused"]), default_settings, DwdObservationMetadata.hourly.temperature_air
    )
    assert isinstance(file, ProductFile)
    assert file.mez_md_spans == {}


def test_the_metadata_of_other_datasets_is_not_read_for_mez_md(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """Test that the archives of the other hourly datasets are unpacked as before (the issue names air temperature)."""
    _serve(monkeypatch, _archive(_METADATA))
    (file,) = download_climate_observations_data(
        pl.Series(["unused"]), default_settings, DwdObservationMetadata.hourly.moisture
    )
    assert isinstance(file, ProductFile)
    assert file.mez_md_spans == {}


def _values(monkeypatch: pytest.MonkeyPatch, archive: bytes) -> pl.DataFrame:
    monkeypatch.setattr(
        dwd_observation_api,
        "create_file_list_for_climate_observations",
        lambda *_, **__: pl.Series([_URL]),
    )
    _serve(monkeypatch, archive)
    request = DwdObservationRequest(
        parameters=[("hourly", "temperature_air")],
        periods={Period.HISTORICAL},
        start=_at(1990, 12, 1),
        end=_at(1991, 12, 1),
        settings=Settings(cache_disable=True),
        options=Options(drop_nulls=False),
    )
    return (
        stations_result(request, "hourly", "temperature_air", "00222").values().all().df.sort("parameter", "timestamp")
    )


def test_the_values_of_an_mez_md_period_are_shifted_to_utc_per_parameter_and_carry_zone_mez(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that the MEZ (MD) stamps are returned one hour earlier, flagged `zone:mez`, per parameter (GH-2709).

    `TT_TU` and `RF_TU` share one stamp column. `RF_TU` is plain MEZ until 1990-12-31 (as returned) and MEZ (MD) from
    1991-01-01, `TT_TU` is MEZ (MD) throughout, so one row has two clocks. The change to UTC on 1991-11-01 is after the
    stamp 00; the later stamps are as they are. The quality level of the file stays first and a reading of -999 keeps
    its text last: `3,zone:mez,raw:-999` for a stamp that is shifted, `3,raw:-999` for one that is not (1991-11-01 01).
    """
    df = _values(monkeypatch, _archive(_METADATA))
    rows = {
        parameter: part.select("timestamp", "value", "quality_flags").rows()
        for (parameter,), part in df.partition_by("parameter", as_dict=True).items()
    }
    assert rows["temperature_air_2m"] == [
        (_at(1990, 12, 31, 22), -2.0, "3,zone:mez"),
        (_at(1990, 12, 31, 23), -2.5, "3,zone:mez"),
        (_at(1991, 1, 1, 0), -3.0, "3,zone:mez"),
        (_at(1991, 10, 31, 22), 5.0, "3,zone:mez"),
        (_at(1991, 10, 31, 23), 4.0, "3,zone:mez"),
        (_at(1991, 11, 1, 1), 3.5, "3"),
        (_at(1991, 11, 2, 0), 3.0, "3"),
    ]
    # the row of 1991-01-01 00 is shifted onto 1990-12-31 23, which the plain MEZ period has; it is the one that goes
    assert rows["humidity_relative"] == [
        (_at(1990, 12, 31, 23), 0.81, "3"),
        (_at(1991, 1, 1, 0), 0.83, "3,zone:mez"),
        (_at(1991, 10, 31, 22), None, "3,zone:mez,raw:-999"),
        (_at(1991, 10, 31, 23), 0.91, "3,zone:mez"),
        (_at(1991, 11, 1, 1), None, "3,raw:-999"),
        (_at(1991, 11, 2, 0), 0.93, "3"),
    ]


def test_the_values_of_an_archive_without_metadata_are_not_shifted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that an archive without `Metadaten_Parameter` keeps its stamps, as before, and has no zone flag."""
    df = _values(monkeypatch, _archive(None))
    tt = df.filter(pl.col("parameter") == "temperature_air_2m")
    assert tt.get_column("timestamp").to_list() == [
        _at(1990, 12, 31, 23),
        _at(1991, 1, 1, 0),
        _at(1991, 1, 1, 1),
        _at(1991, 10, 31, 23),
        _at(1991, 11, 1, 0),
        _at(1991, 11, 1, 1),
        _at(1991, 11, 2, 0),
    ]
    assert set(tt.get_column("quality_flags").to_list()) == {"3"}
