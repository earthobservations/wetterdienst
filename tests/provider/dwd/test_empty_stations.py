# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What every DWD network answers when its catalogue leaves no station (GH-2627).

A catalogue that is read and leaves nothing (every row filtered out, no file for any station, a list with a header
only) is no error and no network without a request: it is the empty stations frame of `STATIONS_SCHEMA`, whatever the
network's own reader built on the way. Each network is served a catalogue that leaves no station at the point where its
own reader would otherwise have a row left, and the core hands out the one empty frame of the request's columns,
dtypes included. The networks hand the core their rows and nothing else, and the shape of the empty answer is the
core's, so this is the net under that.

`dwd/dmo` is not here: no filter sits between its list and the frame, so the one way to leave no station is a list
with no row, which `tests/provider/test_empty_station_catalogues.py` serves it, as it does `dwd/mosmix` a list of the
header alone.
"""

from __future__ import annotations

import bz2
from typing import TYPE_CHECKING

import polars as pl
import pytest

from tests.provider.station_catalogue_stubs import MOSMIX_CATALOGUE, _serve
from wetterdienst import Settings
from wetterdienst.model.schema import STATIONS_SCHEMA
from wetterdienst.provider.dwd import catalogue as dwd_catalogue
from wetterdienst.provider.dwd.derived import DwdDerivedRequest
from wetterdienst.provider.dwd.derived import metaindex as derived_metaindex
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest
from wetterdienst.provider.dwd.mosmix import api as mosmix_api
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation import fileindex as dwd_fileindex
from wetterdienst.provider.dwd.observation import metaindex as dwd_metaindex
from wetterdienst.provider.dwd.phenology import DwdPhenologyRequest
from wetterdienst.provider.dwd.phenology import api as phenology_api
from wetterdienst.provider.dwd.poi import DwdPoiRequest
from wetterdienst.provider.dwd.poi import api as poi_api
from wetterdienst.provider.dwd.road import DwdRoadRequest
from wetterdienst.provider.dwd.road import api as road_api
from wetterdienst.provider.dwd.swsmos import DwdSwsmosRequest
from wetterdienst.provider.dwd.swsmos import api as swsmos_api

if TYPE_CHECKING:
    from collections.abc import Callable

    from wetterdienst.model.request import TimeseriesRequest

_HOURLY_BASE = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/historical/"

_OBSERVATION_CATALOGUE = (
    "Stations_id von_datum bis_datum Stationshoehe geoBreite geoLaenge Stationsname Bundesland Abgabe\r\n"
    "----------- --------- --------- ------------- --------- --------- ----------------------------------------- "
    "---------- ------\r\n"
    "00001 19370101 19860630            478     47.8413    8.8493 Aach                                     "
    "Baden-Württemberg                        Frei\r\n"
)
_DERIVED_CATALOGUE = (
    "Stations_id von_datum bis_datum Stationshoehe geoBreite geoLaenge Stationsname Bundesland\r\n"
    "----------- --------- --------- ------------- --------- --------- ----------------------------------------- "
    "----------\r\n"
    "18000 20240401 20261014            680     47.9736    8.5205 Donaueschingen (Landeplatz)_DUETT        "
    "Baden-Württemberg\r\n"
)
_PHENOLOGY_HEADER = (
    "Stations_id;Stationsname                               ;geograph.Breite;geograph.Laenge;Stationshoehe;"
    "Naturraumgruppe_Code;Naturraumgruppe                                           \t\t    ;Naturraum_Code;"
    "Naturraum                                                                ;Datum Stationsaufloesung;"
    "Bundesland                              ;eor;"
)
_SWSMOS_HEADER = (
    "Kennung;Name;Streckentyp (1=freie Strecke 2=Bruecke);Streckenbelag (1=Asphalt 2=Beton);Breite;Laenge;Hoehe;"
    "Flughafen;Inaktiv\n"
)


def _observation(monkeypatch: pytest.MonkeyPatch) -> TimeseriesRequest:
    # a station that is described and has no file in the directory is dropped by the reader
    monkeypatch.setattr(
        dwd_fileindex,
        "list_remote_files_fsspec",
        lambda *_args, **_kwargs: [f"{_HOURLY_BASE}KL_Tageswerte_Beschreibung_Stationen.txt"],
    )
    _serve(monkeypatch, dwd_metaindex, {"Beschreibung_Stationen": _OBSERVATION_CATALOGUE.encode("latin-1")})
    return DwdObservationRequest(
        parameters=[("daily", "climate_summary")],
        periods="historical",
        settings=Settings(cache_disable=True),
    )


def _derived(monkeypatch: pytest.MonkeyPatch) -> TimeseriesRequest:
    base = (
        "https://opendata.dwd.de/climate_environment/CDC/derived_germany/climate/hourly/duett/radiation_global/recent/"
    )
    monkeypatch.setattr(dwd_fileindex, "list_remote_files_fsspec", lambda *_args, **_kwargs: [f"{base}readme.txt"])
    _serve(monkeypatch, derived_metaindex, {"fg_duett_Beschreibung_Stationen": _DERIVED_CATALOGUE.encode("latin-1")})
    return DwdDerivedRequest(parameters=[("hourly", "radiation_global")], settings=Settings(cache_disable=True))


def _mosmix(monkeypatch: pytest.MonkeyPatch) -> TimeseriesRequest:
    # the reader's answer for a catalogue without a row (the list of the header alone is in
    # `test_empty_station_catalogues.py`)
    monkeypatch.setattr(mosmix_api, "read_mosmix_station_catalogue", lambda *_args, **_kwargs: pl.DataFrame())
    return DwdMosmixRequest(parameters=[("hourly", "small")], settings=Settings(cache_disable=True))


def _poi(monkeypatch: pytest.MonkeyPatch) -> TimeseriesRequest:
    # report files for stations the MOSMIX catalogue does not list
    _serve(monkeypatch, dwd_catalogue, {"mosmix_stationskatalog": MOSMIX_CATALOGUE.encode("latin-1")})
    base = "https://opendata.dwd.de/weather/weather_reports/poi/"
    monkeypatch.setattr(poi_api, "list_remote_files_fsspec", lambda *_args, **_kwargs: [f"{base}99999-BEOB.csv"])
    return DwdPoiRequest(parameters=[("hourly", "data")], settings=Settings(cache_disable=True))


def _phenology(monkeypatch: pytest.MonkeyPatch) -> TimeseriesRequest:
    # a header and a row that names no station, which the reader drops (a header alone is no CSV to polars)
    body = (_PHENOLOGY_HEADER + "\n" + ";" * 11 + "eor;").encode("latin-1")
    bodies = {"Stationen_Jahresmelder": body, "Stationen_Sofortmelder": body}
    _serve(monkeypatch, phenology_api, bodies)
    return DwdPhenologyRequest(
        parameters=[("annual", "annual_apple"), ("annual", "immediate_apple")],
        settings=Settings(cache_disable=True),
    )


def _road(monkeypatch: pytest.MonkeyPatch) -> TimeseriesRequest:
    # every station of the sheet is flagged `x`, out of operation
    columns = dict.fromkeys(DwdRoadRequest._column_mapping, pl.String)  # noqa: SLF001
    row = dict.fromkeys(columns, "")
    row.update({"Kennung": "A006", "GMA-Name": "Boeglum", "außer Betrieb (gemeldet)": "x", "GDS-Verzeichnis": "KK"})
    sheet = pl.DataFrame([row], schema=columns)
    monkeypatch.setattr(pl, "read_excel", lambda **_: sheet)
    _serve(monkeypatch, road_api, {"sws_stations": b""})
    return DwdRoadRequest(parameters=[("15_minutes", "data")], settings=Settings(cache_disable=True))


def _swsmos(monkeypatch: pytest.MonkeyPatch) -> TimeseriesRequest:
    # every station of the catalogue is flagged inactive
    catalogue = _SWSMOS_HEADER + "A006;Boeglum;1;1;54,889156;8,908735;2;;x\n"
    _serve(monkeypatch, swsmos_api, {"swsKatalog": bz2.compress(catalogue.encode("latin-1"))})
    return DwdSwsmosRequest(parameters=[("hourly", "data")], settings=Settings(cache_disable=True))


@pytest.mark.parametrize(
    "build",
    [_observation, _derived, _mosmix, _poi, _phenology, _road, _swsmos],
    ids=lambda build: build.__name__.lstrip("_"),
)
def test_a_catalogue_that_leaves_no_station_is_the_empty_stations_frame(
    monkeypatch: pytest.MonkeyPatch,
    build: Callable[[pytest.MonkeyPatch], TimeseriesRequest],
) -> None:
    """No station left is the empty frame of the request's columns, typed as `STATIONS_SCHEMA` types them."""
    request = build(monkeypatch)
    df = request.all().df
    assert df.is_empty()
    assert list(df.columns) == list(request._base_columns)  # noqa: SLF001
    for column, dtype in STATIONS_SCHEMA.items():
        assert df.schema[column] == dtype, column
