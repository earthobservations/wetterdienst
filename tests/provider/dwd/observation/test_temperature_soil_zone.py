# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the time zone of the hourly soil temperature stamps of DWD observations (GH-3029)."""

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

_URL = "https://example.invalid/stundenwerte_EB_01048_hist.zip"

_HEADER = (
    "Stations_ID;Von_Datum;Bis_Datum;Stationsname;Parameter;Parameterbeschreibung;Einheit;"
    "Datenquelle (Strukturversion=SV);Zusatz-Info;Besonderheiten;Literaturhinweis;eor;\n"
)
_FOOTER = "Legende: FT  = Folgetag; GZ = Gesetzliche Zeit\ngenerierte: 22.04.2026 --  Deutscher Wetterdienst  --\n"

# the three sources of the hourly soil temperature of Dresden-Klotzsche, as stundenwerte_EB_01048_*_hist.zip words them
# (read 2026-10-23): the archive of the eMD (stamps 01, 04, ..., 22 MEZ), the three climate terms, the SYNOP bulletin
_EMD = (
    "Daten der Erdbodentemperatur aus dem Archiv des eMD (EMDS) von 1951-1991 (3,4 Terminwerte:01,07,13,19 MEZ und "
    "synoptische Haupttermine:01,04,07,10,13,16,19,22 MEZ)"
)
_TERMS = "Erdbodentemperaturen an den drei Klimaterminen ( 07, 14, 21 MOZ, ab 01.01.1987 um 07:30,14:30,21:30 MEZ) "
_SYNOP = "Erdbodentemperaturen generiert aus dem stündlichen BOT-Teil des SYNOP-Bulletins (ab  01.04.2001)."


def _row(parameter: str, first: str, last: str, source: str, info: str = "Stundenwerte") -> str:
    return f"1048;{first};{last};Dresden-Klotzsche;{parameter};x;°C;{source};{info};;;eor;\n"


# V_TE005 has all three sources. V_TE100 has an eMD period of five months in 1990 only (as at 01048) and then the
# SYNOP one, so the stamps of the one column are MEZ for one parameter and not for the other.
_METADATA = (
    _HEADER
    + _row("V_TE005", "19760409", "19911031", _EMD)
    + _row("V_TE005", "19911102", "20041231", _TERMS, "Stundenwerte ")
    + _row("V_TE005", "20010401", "20260418", _SYNOP)
    + _row("V_TE100", "19900808", "19901231", _EMD)
    + _row("V_TE100", "20010401", "20260418", _SYNOP)
    + _FOOTER
).encode("latin-1")

# the last stamps of 1985 and the first of 1986 (the terms 01, 04, ..., 22 MEZ), the last of the eMD period, the first
# of the climate terms (07, 14, 21) and the first hours of the SYNOP period
_PRODUCT = (
    "STATIONS_ID;MESS_DATUM;QN_2;V_TE002;V_TE005;V_TE010;V_TE020;V_TE050;V_TE100;eor\n"
    "       1048;1985123119;    3;  -999;   0.2;   0.3;   0.8;   2.5;-999;eor\n"
    "       1048;1985123122;    3;  -999;   0.2;   0.3;   0.7;  -999;-999;eor\n"
    "       1048;1986010101;    3;  -999;   0.1;   0.2;   0.6;   2.4;-999;eor\n"
    "       1048;1990081201;    3;  -999;  18.0;  17.0;  16.0;  14.0;  12.5;eor\n"
    "       1048;1991103122;    3;  -999;   1.7;   2.9;   4.4;  -999;-999;eor\n"
    "       1048;1991110207;    3;  -999;   2.4;   3.0;   4.0;   6.3;-999;eor\n"
    "       1048;2005010100;    3;  -999;   3.4;   3.2;   3.1;   3.2;   4.1;eor\n"
).encode("latin-1")


def _archive(metadata: bytes | None, product: bytes = _PRODUCT) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        if metadata is not None:
            archive.writestr("Metadaten_Parameter_eb_stunde_01048.txt", metadata)
        archive.writestr("produkt_eb_stunde_19760409_20251231_01048.txt", product)
    return buffer.getvalue()


def _serve(monkeypatch: pytest.MonkeyPatch, archive: bytes) -> None:
    monkeypatch.setattr(
        dwd_observation_download,
        "download_files",
        lambda **_kwargs: [File(url=_URL, content=BytesIO(archive), status=200)],
    )


def _at(*args: int) -> dt.datetime:
    return dt.datetime(*args, tzinfo=dt.UTC)


def test_the_periods_from_the_emd_archive_are_mez_per_parameter(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """Test that the stamps of the periods whose source is the eMD archive are MEZ, each parameter by its own table.

    The `Zusatz-Info` of these periods is only `Stundenwerte`: the zone is in the text of the source. The climate terms
    and the SYNOP periods are not MEZ.
    """
    _serve(monkeypatch, _archive(_METADATA))
    (file,) = download_climate_observations_data(
        pl.Series(["unused"]), default_settings, DwdObservationMetadata.hourly.temperature_soil
    )
    assert isinstance(file, ProductFile)
    assert file.mez_md_spans == {
        "v_te005": ((_at(1976, 4, 9, 0), _at(1991, 10, 31, 23)),),
        "v_te100": ((_at(1990, 8, 8, 0), _at(1990, 12, 31, 23)),),
    }


@pytest.mark.parametrize(
    "archive",
    [
        _archive(None),
        _archive(
            (
                _HEADER + _row("V_TE005", "20010401", "", _SYNOP) + _row("V_TE005", "19911102", "", _TERMS) + _FOOTER
            ).encode("latin-1")
        ),
        _archive((_HEADER + _row("V_TE005", "not a date", "", _EMD) + _FOOTER).encode("latin-1")),
    ],
    ids=["no metadata", "no eMD period", "unreadable date"],
)
def test_an_archive_without_a_period_from_the_emd_archive_has_no_mez(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings, archive: bytes
) -> None:
    """Test that a stamp is not shifted on a guess: no metadata, other sources, or a period that does not read."""
    _serve(monkeypatch, archive)
    (file,) = download_climate_observations_data(
        pl.Series(["unused"]), default_settings, DwdObservationMetadata.hourly.temperature_soil
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
        parameters=[("hourly", "temperature_soil")],
        periods={Period.HISTORICAL},
        start=_at(1985, 12, 1),
        end=_at(2005, 1, 2),
        settings=Settings(cache_disable=True),
        options=Options(drop_nulls=False),
    )
    return (
        stations_result(request, "hourly", "temperature_soil", "01048").values().all().df.sort("parameter", "timestamp")
    )


def test_the_values_of_the_emd_periods_are_shifted_to_utc_and_carry_zone_mez(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the stamps 01, 04, ..., 22 MEZ are returned as 00, 03, ..., 21 UTC, flagged `zone:mez` (GH-3029).

    The terms of the archive are MEZ: the stamps are the synoptic main terms 00, 03, ..., 21 UTC plus the hour. The
    climate terms (07 of 1991-11-02) and the SYNOP period are as written. A reading of -999 keeps its text last.
    """
    df = _values(monkeypatch, _archive(_METADATA))
    rows = {
        parameter: part.select("timestamp", "value", "quality_flags").rows()
        for (parameter,), part in df.partition_by("parameter", as_dict=True).items()
    }
    assert rows["temperature_soil_0_05m"] == [
        (_at(1985, 12, 31, 18), 0.2, "3,zone:mez"),
        (_at(1985, 12, 31, 21), 0.2, "3,zone:mez"),
        (_at(1986, 1, 1, 0), 0.1, "3,zone:mez"),
        (_at(1990, 8, 12, 0), 18.0, "3,zone:mez"),
        (_at(1991, 10, 31, 21), 1.7, "3,zone:mez"),
        (_at(1991, 11, 2, 7), 2.4, "3"),
        (_at(2005, 1, 1, 0), 3.4, "3"),
    ]
    # V_TE100 is MEZ only in its own period of 1990
    assert rows["temperature_soil_1m"] == [
        (_at(1985, 12, 31, 19), None, "3,raw:-999"),
        (_at(1985, 12, 31, 22), None, "3,raw:-999"),
        (_at(1986, 1, 1, 1), None, "3,raw:-999"),
        (_at(1990, 8, 12, 0), 12.5, "3,zone:mez"),
        (_at(1991, 10, 31, 22), None, "3,raw:-999"),
        (_at(1991, 11, 2, 7), None, "3,raw:-999"),
        (_at(2005, 1, 1, 0), 4.1, "3"),
    ]


def test_the_values_of_an_archive_without_metadata_are_not_shifted(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that an archive without `Metadaten_Parameter` keeps its stamps, as before, and has no zone flag."""
    df = _values(monkeypatch, _archive(None))
    soil = df.filter(pl.col("parameter") == "temperature_soil_0_05m")
    assert soil.get_column("timestamp").to_list() == [
        _at(1985, 12, 31, 19),
        _at(1985, 12, 31, 22),
        _at(1986, 1, 1, 1),
        _at(1990, 8, 12, 1),
        _at(1991, 10, 31, 22),
        _at(1991, 11, 2, 7),
        _at(2005, 1, 1, 0),
    ]
    assert set(soil.get_column("quality_flags").to_list()) == {"3"}
