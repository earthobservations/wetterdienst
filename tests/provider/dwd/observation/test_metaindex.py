# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for DWD observation meta index creation."""

import datetime as dt
import zipfile
from io import BytesIO
from unittest.mock import patch
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from wetterdienst import Settings
from wetterdienst.exceptions import MetaFileFormatError, MetaFileNotFoundError
from wetterdienst.metadata.period import Period
from wetterdienst.provider.dwd.observation import metaindex
from wetterdienst.provider.dwd.observation.api import DwdObservationRequest
from wetterdienst.provider.dwd.observation.metadata import DwdObservationMetadata
from wetterdienst.provider.dwd.observation.metaindex import (
    _create_csv_line,
    _read_meta_df_urban,
    create_meta_index_for_climate_observations,
)
from wetterdienst.util.network import File


@pytest.mark.remote
def test_meta_index_creation_success(default_settings: Settings) -> None:
    """Test the creation of a meta index for historical climate data."""
    # Existing combination of parameters
    meta_index = create_meta_index_for_climate_observations(
        dataset=DwdObservationMetadata.daily.climate_summary,
        period=Period.HISTORICAL,
        settings=default_settings,
    ).collect()
    assert not meta_index.is_empty()


@pytest.mark.remote
def test_meta_index_1mph_creation(default_settings: Settings) -> None:
    """Test the creation of a meta-index for 1-minute precipitation historical data."""
    meta_index_1mph = create_meta_index_for_climate_observations(
        dataset=DwdObservationMetadata.minute_1.precipitation,
        period=Period.HISTORICAL,
        settings=default_settings,
    ).collect()
    assert meta_index_1mph.filter(pl.col("station_id").eq("00003")).row(0) == (
        (
            "1_minute",
            "precipitation",
            "00003",
            dt.datetime(1829, 6, 1, 0, 0, tzinfo=ZoneInfo("UTC")),
            dt.datetime(2012, 4, 6, 0, 0, tzinfo=ZoneInfo("UTC")),
            202.00,
            50.7827,
            6.0941,
            "Aachen",
            "Nordrhein-Westfalen",
        )
    )


def test_create_csv_line() -> None:
    """Test the creation of a CSV line from a list of strings."""
    assert (
        _create_csv_line(["00001", "19370101", "19860630", "478", "47.8413", "8.8493", "Aach", "Baden-Württemberg"])
        == "00001,19370101,19860630,478,47.8413,8.8493,Aach,Baden-Württemberg"
    )
    assert (
        _create_csv_line(
            ["00126", "19791101", "20101130", "330", "49.5447", "10.2213", "Uffenheim", "(Schulstr.)", "Bayern"],
        )
        == "00126,19791101,20101130,330,49.5447,10.2213,Uffenheim (Schulstr.),Bayern"
    )
    assert (
        _create_csv_line(
            ["00102", "19980101", "20240514", "0", "53.8633", "8.1275", "Leuchtturm", "Alte", "Weser", "Niedersachsen"],
        )
        == "00102,19980101,20240514,0,53.8633,8.1275,Leuchtturm Alte Weser,Niedersachsen"
    )
    assert (
        _create_csv_line(
            [
                "00197",
                "19900801",
                "20240514",
                "365",
                "51.3219",
                "9.0558",
                "Arolsen-Volkhardinghausen,",
                "Bad",
                "Hessen",
            ],
        )
        == """00197,19900801,20240514,365,51.3219,9.0558,"Arolsen-Volkhardinghausen, Bad",Hessen"""
    )
    assert (
        _create_csv_line(
            ["01332", "19660701", "20240514", "471", "48.4832", "12.7241", "Falkenberg,Kr.Rottal-Inn", "Bayern"],
        )
        == """01332,19660701,20240514,471,48.4832,12.7241,"Falkenberg,Kr.Rottal-Inn",Bayern"""
    )


def test_read_meta_df_urban() -> None:
    """climate_urban station lists are parsed by content, tolerating blank date/region fields.

    The two leading lines are the header and its dashes ruler and are dropped. Data rows vary in
    token count because von_datum/bis_datum and (for the 10-minute lists) the trailing
    Bundesland/Abgabe fields are frequently left blank.
    """
    raw_lines = [
        b"Stations_id von_datum bis_datum Stationshoehe geoBreite geoLaenge Stationsname Bundesland Abgabe\n",
        b"----------- --------- --------- ------------- --------- --------- ----------- ---------- ------\n",
        # 10-minute row: blank dates and blank region
        b"13667 269 48.0006 7.8342 Freiburg-Mitte\n",
        # dates present, region still blank
        b"00399 20040701 20260724 100 52.5447 13.4046 Berlin-Alexanderplatz\n",
        # full hourly row: dates, region and a trailing "Frei" Abgabe marker
        b"13667 20080101 20260724 269 48.0006 7.8342 Freiburg-Mitte Baden-Wuerttemberg Frei\n",
        # blank line is skipped
        b"\n",
    ]
    df = _read_meta_df_urban(raw_lines).collect()
    assert df.rows() == [
        ("13667", "", "", "269", "48.0006", "7.8342", "Freiburg-Mitte", ""),
        ("00399", "20040701", "20260724", "100", "52.5447", "13.4046", "Berlin-Alexanderplatz", ""),
        ("13667", "20080101", "20260724", "269", "48.0006", "7.8342", "Freiburg-Mitte", "Baden-Wuerttemberg"),
    ]


def test_read_meta_df_urban_rejects_malformed_rows() -> None:
    """A row that breaks the content assumptions fails loudly instead of shifting every field."""
    header = [
        b"Stations_id von_datum bis_datum Stationshoehe geoBreite geoLaenge Stationsname Bundesland\n",
        b"----------- --------- --------- ------------- --------- --------- ----------- ----------\n",
    ]
    # fewer than two decimal tokens (truncated coordinates)
    with pytest.raises(MetaFileFormatError):
        _read_meta_df_urban([*header, b"13667 269 48.0006 Freiburg-Mitte\n"]).collect()
    # a decimal-valued height would otherwise be mis-read as latitude
    with pytest.raises(MetaFileFormatError):
        _read_meta_df_urban([*header, b"13667 269.5 48.0006 7.8342 Freiburg-Mitte\n"]).collect()


def test_missing_meta_file_skipped(default_settings: Settings) -> None:
    """When a period's meta file is absent, the period is skipped and the request returns empty."""
    with patch(
        "wetterdienst.provider.dwd.observation.api.create_meta_index_for_climate_observations",
        side_effect=MetaFileNotFoundError("No meta file found"),
    ):
        request = DwdObservationRequest(
            parameters=DwdObservationMetadata.minute_10.precipitation,
            settings=default_settings,
        ).all()
        assert request.df.is_empty()


def _geography_zip(station_id: str, lines: list[str]) -> BytesIO:
    """Pack a ``Metadaten_Geographie_<id>.txt`` the way DWD's 1-minute ``meta_data`` zips carry it."""
    header = "Stations_id;Stationshoehe;Geogr.Breite;Geogr.Laenge;von_datum;bis_datum;Stationsname"
    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(f"Metadaten_Geographie_{station_id}.txt", "\n".join([header, *lines]) + "\n")
    buffer.seek(0)
    return buffer


def test_meta_index_1mph_leaves_an_open_station_without_an_end(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a station still reporting has a null ``end_timestamp`` in the 1-minute precipitation index.

    DWD leaves ``bis_datum`` blank (eight spaces) on the position a station still stands at. The
    index filled that blank with the day before the call, so the end moved every day and a caller
    could not tell an open station from one that closed the day before.
    """
    base = (
        "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/1_minute/precipitation/meta_data/"
    )
    zips = {
        "01048": _geography_zip(
            "01048",
            [
                "  1048;  227.00; 51.1280; 13.7543;20120302;20190813;Dresden-Klotzsche",
                "  1048;  227.57; 51.1278; 13.7543;20190814;        ;Dresden-Klotzsche",
            ],
        ),
        "00003": _geography_zip("00003", ["     3;  202.00; 50.7827;  6.0941;18910101;20110331;Aachen"]),
    }
    file_index = pl.LazyFrame(
        {
            "filename": [f"Meta_Daten_ein_min_rr_{station_id}.zip" for station_id in zips],
            "url": [f"{base}Meta_Daten_ein_min_rr_{station_id}.zip" for station_id in zips],
        },
    )
    regions = pl.LazyFrame({"station_id": ["00003", "01048"], "region": ["Nordrhein-Westfalen", "Sachsen"]})

    def _download_files(urls: list[str], **_: object) -> list[File]:
        return [File(url=url, content=zips[url.rsplit("_", 1)[-1].removesuffix(".zip")], status=200) for url in urls]

    monkeypatch.setattr(metaindex, "_create_file_index_for_dwd_server", lambda *_, **__: file_index)
    monkeypatch.setattr(metaindex, "download_files", _download_files)
    monkeypatch.setattr(metaindex, "_create_meta_index_for_climate_observations", lambda *_, **__: regions)

    df = create_meta_index_for_climate_observations(
        dataset=DwdObservationMetadata.minute_1.precipitation,
        period=Period.HISTORICAL,
        settings=Settings(),
    ).collect()

    assert df.select("station_id", "start_timestamp", "end_timestamp").rows() == [
        ("00003", dt.datetime(1891, 1, 1, tzinfo=ZoneInfo("UTC")), dt.datetime(2011, 3, 31, tzinfo=ZoneInfo("UTC"))),
        ("01048", dt.datetime(2012, 3, 2, tzinfo=ZoneInfo("UTC")), None),
    ]
    assert df.schema["end_timestamp"] == pl.Datetime(time_zone="UTC")
