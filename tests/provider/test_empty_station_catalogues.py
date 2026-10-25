# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A catalogue that lists no station is the empty stations frame, through the reader of each provider (GH-2627).

The stubs of `station_catalogue_stubs.py` serve a few rows of the real list; these serve the same list with no row that
the request keeps, so that the readers of the providers named here, which shape what they build before the core does,
are held to the one answer whatever they make of a frame without rows: no station, in the columns and dtypes of
`STATIONS_SCHEMA` (a provider's own columns after them).
"""

from __future__ import annotations

import json
from io import BytesIO
from typing import TYPE_CHECKING, Any

import pytest

from tests.provider.station_catalogue_stubs import _serve, _stations, meteofrance_registry_bodies
from wetterdienst import Settings
from wetterdienst.model.schema import STATIONS_SCHEMA
from wetterdienst.provider.dmi.observation import DmiObservationRequest
from wetterdienst.provider.dmi.observation import api as dmi_api
from wetterdienst.provider.dwd import catalogue as dwd_catalogue
from wetterdienst.provider.dwd.dmo import DwdDmoRequest
from wetterdienst.provider.dwd.dmo import api as dmo_api
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest
from wetterdienst.provider.ea.hydrology import EAHydrologyRequest
from wetterdienst.provider.ea.hydrology import api as ea_api
from wetterdienst.provider.eaufrance.hubeau import HubeauRequest
from wetterdienst.provider.eaufrance.hubeau import api as hubeau_api
from wetterdienst.provider.eccc.observation import EcccObservationRequest
from wetterdienst.provider.eccc.observation import api as eccc_api
from wetterdienst.provider.meteofrance.observation import MeteoFranceObservationRequest
from wetterdienst.provider.meteofrance.observation import api as meteofrance_api
from wetterdienst.provider.meteofrance.synop import MeteoFranceSynopRequest
from wetterdienst.provider.meteofrance.synop import api as meteofrance_synop_api
from wetterdienst.provider.meteoswiss.observation import MeteoswissObservationRequest
from wetterdienst.provider.meteoswiss.observation import api as meteoswiss_api
from wetterdienst.provider.metno.frost import MetnoFrostRequest
from wetterdienst.provider.metno.frost import api as frost_api
from wetterdienst.provider.rmi.observation import RmiObservationRequest
from wetterdienst.provider.rmi.observation import api as rmi_api
from wetterdienst.provider.smhi.observation import SmhiObservationRequest
from wetterdienst.provider.smhi.observation import api as smhi_api
from wetterdienst.util.network import File

if TYPE_CHECKING:
    from collections.abc import Callable

    import polars as pl


def _json(body: Any) -> bytes:  # noqa: ANN401
    return json.dumps(body).encode("utf8")


def _ea_hydrology(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    _serve(monkeypatch, ea_api, {"stations.json": _json({"items": []})})
    return _stations(EAHydrologyRequest, ("15_minutes", "data"))


def _eccc(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    # a list of stations none of which has an hourly collection: the list has rows, the request keeps none
    properties = {
        "STN_ID": 2,
        "STATION_NAME": "CHEMAINUS BARE POINT",
        "PROV_STATE_TERR_CODE": "BC",
        "TIMEZONE": "PST",
        "ELEVATION": "3.00",
        "FIRST_DATE": "1979-01-01 00:00:00",
        "LAST_DATE": "1979-12-31 00:00:00",
        "HLY_FIRST_DATE": None,
        "HLY_LAST_DATE": None,
        "DLY_FIRST_DATE": "1979-11-01 00:00:00",
        "DLY_LAST_DATE": "1979-12-31 00:00:00",
        "MLY_FIRST_DATE": "1979-01-01 00:00:00",
        "MLY_LAST_DATE": "1979-12-01 00:00:00",
        "HAS_MONTHLY_SUMMARY": "Y",
    }
    feature = {
        "type": "Feature",
        "properties": properties,
        "geometry": {"type": "Point", "coordinates": [-123.7, 48.9]},
    }
    _serve(
        monkeypatch,
        eccc_api,
        {"climate-stations/items": _json({"type": "FeatureCollection", "features": [feature]})},
    )
    return _stations(EcccObservationRequest, ("hourly", "data"))


def _smhi(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    body = _json({"station": []})

    def download_files(*, urls: list[str], **_: object) -> list[File]:
        return [File(url=url, content=BytesIO(body), status=200) for url in urls]

    monkeypatch.setattr(smhi_api, "download_files", download_files)
    return _stations(SmhiObservationRequest, ("hourly", "data"))


def _hubeau(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    _serve(monkeypatch, hubeau_api, {"referentiel/stations": _json({"data": []})})
    return _stations(HubeauRequest, ("5_minutes", "data"))


def _hubeau_nothing_to_measure(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    # a station that has published nothing is listed under no resolution, so the catalogue has a row and the request
    # keeps none
    station = {
        "code_site": "F7000001",
        "code_station": "F700000102",
        "libelle_station": "La Seine à Paris - Austerlitz",
        "longitude_station": 2.365510635,
        "latitude_station": 48.84468962,
        "altitude_ref_alti_station": 25.92,
        "code_systeme_alti_site": 3,
        "date_ouverture_station": "1990-01-01T00:00:00Z",
        "date_fermeture_station": None,
        "libelle_departement": "PARIS",
    }
    bodies = {
        "referentiel/stations": _json({"data": [station]}),
        "referentiel/sites": _json({"data": [{"code_site": "F7000001", "altitude_site": 26.0}]}),
        "observations_tr": _json({"data": []}),
    }
    _serve(monkeypatch, hubeau_api, bodies)
    return _stations(HubeauRequest, ("5_minutes", "data"))


def _meteofrance_observation(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    header = (
        "id,name,long_name,named_place,station_type,basin,lon,lat,alt,start_date,end_date,is_open,is_public,"
        "department_id,is_daily,is_hourly,is_minutely\n"
    )
    _serve(monkeypatch, meteofrance_api, meteofrance_registry_bodies(header))
    return _stations(MeteoFranceObservationRequest, ("daily", "core"))


def _meteofrance_synop(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    _serve(
        monkeypatch,
        meteofrance_synop_api,
        {"postes_synop": _json({"type": "FeatureCollection", "features": []})},
    )
    return _stations(MeteoFranceSynopRequest, ("subdaily", "data"))


def _meteoswiss(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    header = (
        "station_abbr;station_name;station_canton;station_wigos_id;station_type_de;station_type_fr;station_type_it;"
        "station_type_en;station_dataowner;station_data_since;station_height_masl;station_height_barometer_masl;"
        "station_coordinates_lv95_east;station_coordinates_lv95_north;station_coordinates_wgs84_lat;"
        "station_coordinates_wgs84_lon;station_exposition_de;station_exposition_fr;station_exposition_it;"
        "station_exposition_en;station_url_de;station_url_fr;station_url_it;station_url_en\r\n"
    )
    _serve(monkeypatch, meteoswiss_api, {"ogd-smn_meta_stations": header.encode("windows-1252")})
    return _stations(MeteoswissObservationRequest, ("daily", "data"))


def _dmi(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    _serve(monkeypatch, dmi_api, {"station/items": _json({"type": "FeatureCollection", "features": []})})
    return _stations(DmiObservationRequest, ("hourly", "data"))


def _rmi(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    _serve(monkeypatch, rmi_api, {"aws_station": _json({"type": "FeatureCollection", "features": []})})
    return _stations(RmiObservationRequest, ("10_minutes", "data"))


def _metno_frost(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    _serve(monkeypatch, frost_api, {"sources/v0.jsonld": _json({"data": []})})
    request = MetnoFrostRequest(
        parameters=[("hourly", "data")],
        settings=Settings(cache_disable=True, auth={"metno_frost": ("stub-client", "stub-secret")}),
    )
    return request.all().df


# the header and the rule of the fixed-width list of DWD, and no row under them
_FIXED_WIDTH_HEADER = (
    "ID    ICAO NAME                 LAT    LON     ELEV\n----- ---- -------------------- -----  ------- -----\n"
)


def _dwd_dmo(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    _serve(monkeypatch, dmo_api, {"dmo_stationsliste_txt": _FIXED_WIDTH_HEADER.encode("latin-1")})
    monkeypatch.setattr(dmo_api, "list_remote_directory_fsspec", lambda *_args, **_kwargs: [])
    return _stations(DwdDmoRequest, ("hourly", "icon"))


def _dwd_mosmix(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    _serve(monkeypatch, dwd_catalogue, {"mosmix_stationskatalog": _FIXED_WIDTH_HEADER.encode("latin-1")})
    return _stations(DwdMosmixRequest, ("hourly", "small"))


CASES: dict[str, Callable[[pytest.MonkeyPatch], pl.DataFrame]] = {
    "dmi/observation": _dmi,
    "dwd/dmo, a list of the header alone": _dwd_dmo,
    "dwd/mosmix, a list of the header alone": _dwd_mosmix,
    "ea/hydrology": _ea_hydrology,
    "eccc/observation, a list with no hourly station": _eccc,
    "smhi/observation": _smhi,
    "eaufrance/hubeau": _hubeau,
    "eaufrance/hubeau, a station with nothing to measure": _hubeau_nothing_to_measure,
    "meteofrance/observation": _meteofrance_observation,
    "meteofrance/synop": _meteofrance_synop,
    "meteoswiss/observation": _meteoswiss,
    "metno/frost": _metno_frost,
    "rmi/observation": _rmi,
}


@pytest.mark.parametrize("name", CASES)
def test_a_catalogue_without_a_station_is_the_empty_stations_frame(name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """Give no station, in the columns and dtypes of `STATIONS_SCHEMA`, for a list the request keeps no row of."""
    stations = CASES[name](monkeypatch)
    assert stations.height == 0, name
    assert {column: dtype for column, dtype in stations.schema.items() if column in STATIONS_SCHEMA} == dict(
        STATIONS_SCHEMA
    ), name
    assert [column for column in stations.columns if column in STATIONS_SCHEMA] == list(STATIONS_SCHEMA), name
