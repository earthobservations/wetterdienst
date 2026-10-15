# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the time zone of the hourly sun stamps of DWD observations (GH-2816)."""

import datetime as dt
import zipfile
from io import BytesIO
from zoneinfo import ZoneInfo

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

UTC = ZoneInfo("UTC")

# Metadaten_Parameter_sd_stunde_00769.txt of stundenwerte_SD_00769_19680101_20060930_hist.zip (Bueckeburg), read
# 2026-10-15: the station changes between the two several times; the source text of the long free texts is cut
_METADATA_00769 = (
    "Stations_ID;Von_Datum;Bis_Datum;Stationsname;Parameter;Parameterbeschreibung;Einheit;"
    "Datenquelle (Strukturversion=SV);Zusatz-Info;Besonderheiten;Literaturhinweis;eor;\n"
    "769;19680101;20040630;Bückeburg;SD_SO;stdl. Sonnenscheindauer;;Daten der Sonnenscheindauer (Stundensummen) aus "
    "analogen Registrierungen (Campbell-Stokes);Stundenwerte in WOZ;;;eor;\n"
    "769;20040701;20040731;Bückeburg;SD_SO;stdl. Sonnenscheindauer;;Daten der Sonnenscheindauer (Stundensummen) "
    "generiert aus stündlichen SYNOP-Meldungen (nach 01.04.2001);Stundenwerte in UTC;Juni 2017: Im Vergleich zu "
    "Nachbarstationen teilweise zu geringe Tageswerte der Sonnenscheindauer.;;eor;\n"
    "769;20040801;20040930;Bückeburg;SD_SO;stdl. Sonnenscheindauer;;Daten der Sonnenscheindauer (Stundensummen) aus "
    "analogen Registrierungen (Campbell-Stokes);Stundenwerte in WOZ;;;eor;\n"
    "769;20041001;20041031;Bückeburg;SD_SO;stdl. Sonnenscheindauer;;Daten der Sonnenscheindauer (Stundensummen) "
    "generiert aus stündlichen SYNOP-Meldungen (nach 01.04.2001);Stundenwerte in UTC;;;eor;\n"
    "769;20041101;20060930;Bückeburg;SD_SO;stdl. Sonnenscheindauer;;Daten der Sonnenscheindauer (Stundensummen) aus "
    "analogen Registrierungen (Campbell-Stokes);Stundenwerte in WOZ;;;eor;\n"
    "Legende: FT  = Folgetag; GZ = Gesetzliche Zeit\n"
    "generiert: 22.04.2026 --  Deutscher Wetterdienst  --\n"
).encode("latin-1")

# the rows of the product file around the changes: the last WOZ hour of June, the first UTC hours of July, the last
# of July, and the first of August (the product file of the same archive)
_PRODUCT_00769 = (
    "STATIONS_ID;MESS_DATUM;QN_7;SD_SO;eor\n"
    "        769;2004063012;   10;  6.00;eor\n"
    "        769;2004070112;   10;  6.00;eor\n"
    "        769;2004073113;   10; 60.00;eor\n"
    "        769;2004080112;   10; 60.00;eor\n"
    "        769;2004081012;   10;  -999;eor\n"
).encode("latin-1")


def _archive(metadata: bytes | None, product: bytes) -> bytes:
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        if metadata is not None:
            archive.writestr("Metadaten_Parameter_sd_stunde_00769.txt", metadata)
        archive.writestr("produkt_sd_stunde_19680101_20060930_00769.txt", product)
    return buffer.getvalue()


def _serve(monkeypatch: pytest.MonkeyPatch, archive: bytes) -> None:
    monkeypatch.setattr(
        dwd_observation_download,
        "download_files",
        lambda **_kwargs: [
            File(url="https://example.invalid/stundenwerte_SD_00769_hist.zip", content=BytesIO(archive), status=200)
        ],
    )


def test_the_periods_in_true_solar_time_are_read_from_the_metadata_of_the_archive(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """Test that the periods DWD calls `Stundenwerte in WOZ` are read from the archive, as they are at no fixed date.

    Of the 636 historical archives of hourly sun (read 2026-10-15), 528 have WOZ periods; those of 140 of them end on
    2001-03-31, but 172 stations have one that runs on, to 2006, and 00769 changes back and forth by the month.
    """
    _serve(monkeypatch, _archive(_METADATA_00769, _PRODUCT_00769))
    (file,) = download_climate_observations_data(
        pl.Series(["unused"]), default_settings, DwdObservationMetadata.hourly.sun
    )
    assert isinstance(file, ProductFile)
    assert file.woz_spans == (
        (dt.date(1968, 1, 1), dt.date(2004, 6, 30)),
        (dt.date(2004, 8, 1), dt.date(2004, 9, 30)),
        (dt.date(2004, 11, 1), dt.date(2006, 9, 30)),
    )
    # the product file is the content, as before
    assert file.content.read() == _PRODUCT_00769


@pytest.mark.parametrize("archive", [_archive(None, _PRODUCT_00769)], ids=["no metadata"])
def test_an_archive_without_metadata_has_no_periods_in_true_solar_time(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings, archive: bytes
) -> None:
    """Test that a stamp is not called WOZ on a guess where the archive has no metadata."""
    _serve(monkeypatch, archive)
    (file,) = download_climate_observations_data(
        pl.Series(["unused"]), default_settings, DwdObservationMetadata.hourly.sun
    )
    assert isinstance(file, ProductFile)
    assert file.woz_spans == ()


def test_the_metadata_of_other_datasets_is_not_read(
    monkeypatch: pytest.MonkeyPatch, default_settings: Settings
) -> None:
    """Test that the archives of the other datasets are unpacked as before, without a read of their metadata."""
    _serve(monkeypatch, _archive(_METADATA_00769, _PRODUCT_00769))
    (file,) = download_climate_observations_data(
        pl.Series(["unused"]), default_settings, DwdObservationMetadata.hourly.solar
    )
    assert isinstance(file, ProductFile)
    assert file.woz_spans == ()


def test_the_values_of_a_period_in_true_solar_time_carry_zone_woz(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the hourly sun stamps of a WOZ period are returned unshifted and flagged `zone:woz` (GH-2816).

    DWD's `Metadaten_Parameter` names the periods of 00769 `Stundenwerte in WOZ` (to 2004-06-30, then 08-01 to 09-30)
    and `Stundenwerte in UTC` (07-01 to 07-31). Neither stamp nor value is changed (the value is in seconds: 6
    minutes are 360), as the true solar hour of a station is no whole hour from UTC. The quality level of the file
    stays first and a reading of -999 keeps its text last: `10,zone:woz,raw:-999`.
    """
    archive = _archive(_METADATA_00769, _PRODUCT_00769)
    monkeypatch.setattr(
        dwd_observation_api,
        "create_file_list_for_climate_observations",
        lambda *_, **__: pl.Series(["https://example.invalid/stundenwerte_SD_00769_hist.zip"]),
    )
    _serve(monkeypatch, archive)
    request = DwdObservationRequest(
        parameters=[("hourly", "sun")],
        periods={Period.HISTORICAL},
        start=dt.datetime(2004, 6, 30, tzinfo=UTC),
        end=dt.datetime(2004, 8, 31, tzinfo=UTC),
        settings=Settings(cache_disable=True),
        options=Options(drop_nulls=False),
    )
    df = stations_result(request, "hourly", "sun", "00769").values.all().df.sort("timestamp")
    assert df.select("timestamp", "value", "quality_flags").rows() == [
        (dt.datetime(2004, 6, 30, 12, tzinfo=UTC), 360.0, "10,zone:woz"),
        (dt.datetime(2004, 7, 1, 12, tzinfo=UTC), 360.0, "10"),
        (dt.datetime(2004, 7, 31, 13, tzinfo=UTC), 3600.0, "10"),
        (dt.datetime(2004, 8, 1, 12, tzinfo=UTC), 3600.0, "10,zone:woz"),
        (dt.datetime(2004, 8, 10, 12, tzinfo=UTC), None, "10,zone:woz,raw:-999"),
    ]
