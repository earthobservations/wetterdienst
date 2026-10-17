# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Stubs of the station catalogues, for `test_station_catalogue_stubs.py` to hold to the rules (GH-2616).

A stub is the catalogue a provider's own reader turns into stations, made from a few rows of the real list: the first
stations of it and the ones that showed a defect, copied as they are published, with the source's own encoding and
decimal separator, and the padding too where a comment does not say it was cut. Standing in for the download, it runs
the provider's own reader (`_all()` and the frame handling of `all()`), so a reader that loses a sign or drops a column
shows here without the network. What a stub serves in place of the reader's lower layer is said in its comment: the
sheet of `dwd/road` for the Excel read, the directory listings of `dwd/dmo`, `dwd/poi`, `dwd/observation` and
`dwd/derived`, the paged and the parallel downloads of `eaufrance/hubeau` and `smhi/observation`, the NetCDF file of
`knmi/observation`, which needs a key, written with h5netcdf. A comment also says
which fields a stub made up (the observations a Hubeau station's resolution is measured from, the file names of
`dwd/observation` but two) and which it left out.

To hold another provider to the rules, add a stub to `STUBS`: serve the rows through `_serve`, call the request, and
give the rows a fault the source really has if there is one, so that the rule is seen to find it. A rule finds a value
that cannot be, not one that is read wrongly: where the reader converts (the degrees and minutes of `dwd/dmo`), splits
(the names of `dwd/observation`) or picks (the WMO number of `knmi/observation`), name in `Stub.expected` what it must
give for the rows that show it, and check by mutating the reader that the stub fails.
"""

from __future__ import annotations

import bz2
import datetime as dt
import json
import tempfile
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any

import polars as pl

from tests.provider.station_catalogue import COUNTRY_BBOX, Accepted, has_encoding_damage
from wetterdienst import Settings
from wetterdienst.provider.aemet.observation import AemetObservationRequest
from wetterdienst.provider.aemet.observation import api as aemet_api
from wetterdienst.provider.chmi.observation import ChmiObservationRequest
from wetterdienst.provider.chmi.observation import api as chmi_api
from wetterdienst.provider.dmi.observation import DmiObservationRequest
from wetterdienst.provider.dmi.observation import api as dmi_api
from wetterdienst.provider.dwd import catalogue as dwd_catalogue
from wetterdienst.provider.dwd.derived import DwdDerivedRequest
from wetterdienst.provider.dwd.derived import metaindex as derived_metaindex
from wetterdienst.provider.dwd.dmo import DwdDmoRequest
from wetterdienst.provider.dwd.dmo import api as dmo_api
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest
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
from wetterdienst.provider.ea.hydrology import EAHydrologyRequest
from wetterdienst.provider.ea.hydrology import api as ea_api
from wetterdienst.provider.eaufrance.hubeau import HubeauRequest
from wetterdienst.provider.eaufrance.hubeau import api as hubeau_api
from wetterdienst.provider.eccc.observation import EcccObservationRequest
from wetterdienst.provider.eccc.observation import api as eccc_api
from wetterdienst.provider.fmi.observation import FmiObservationRequest
from wetterdienst.provider.fmi.observation import api as fmi_api
from wetterdienst.provider.geosphere.observation import GeosphereObservationRequest
from wetterdienst.provider.geosphere.observation import api as geosphere_api
from wetterdienst.provider.imgw.hydrology import ImgwHydrologyRequest
from wetterdienst.provider.imgw.hydrology import api as imgw_hydrology_api
from wetterdienst.provider.imgw.meteorology import ImgwMeteorologyRequest
from wetterdienst.provider.imgw.meteorology import api as imgw_meteorology_api
from wetterdienst.provider.ipma.observation import IpmaObservationRequest
from wetterdienst.provider.ipma.observation import api as ipma_api
from wetterdienst.provider.knmi.observation import KnmiObservationRequest
from wetterdienst.provider.knmi.observation import api as knmi_api
from wetterdienst.provider.lhmt.observation import LhmtObservationRequest
from wetterdienst.provider.lhmt.observation import api as lhmt_api
from wetterdienst.provider.meteofrance.observation import MeteoFranceObservationRequest
from wetterdienst.provider.meteofrance.observation import api as meteofrance_api
from wetterdienst.provider.meteofrance.synop import MeteoFranceSynopRequest
from wetterdienst.provider.meteofrance.synop import api as meteofrance_synop_api
from wetterdienst.provider.meteoswiss.observation import MeteoswissObservationRequest
from wetterdienst.provider.meteoswiss.observation import api as meteoswiss_api
from wetterdienst.provider.metno.frost import MetnoFrostRequest
from wetterdienst.provider.metno.frost import api as frost_api
from wetterdienst.provider.metoffice.observation import MetOfficeObservationRequest
from wetterdienst.provider.metoffice.observation import api as metoffice_api
from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest
from wetterdienst.provider.noaa.ghcn import api as ghcn_api
from wetterdienst.provider.nws.observation import NwsObservationRequest
from wetterdienst.provider.nws.observation import api as nws_api
from wetterdienst.provider.rmi.observation import RmiObservationRequest
from wetterdienst.provider.rmi.observation import api as rmi_api
from wetterdienst.provider.smhi.observation import SmhiObservationRequest
from wetterdienst.provider.smhi.observation import api as smhi_api
from wetterdienst.provider.wsv.pegel import WsvPegelRequest
from wetterdienst.provider.wsv.pegel import api as wsv_api
from wetterdienst.util.network import File

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest


@dataclass(frozen=True)
class Stub:
    """The stations a provider's reader gives for a stub of its catalogue, and what to hold them to."""

    catalogue: str
    build: Callable[[pytest.MonkeyPatch], pl.DataFrame]
    accepted: tuple[Accepted, ...] = field(default=())
    # the fields the reader must give a station, by station id: no rule can tell a position read wrongly from one that
    # is only somewhere else, as in a list published in degrees and minutes, or a name cut short
    expected: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def bbox(self) -> tuple[float, float, float, float] | None:
        """The country the catalogue is published for, if it is one."""
        return COUNTRY_BBOX.get(self.catalogue.split(" ")[0])


def _serve(monkeypatch: pytest.MonkeyPatch, module: Any, bodies: dict[str, bytes]) -> None:  # noqa: ANN401
    """Make the downloads of a provider module answer with the given bodies, by a part of the url."""

    def download_file(*, url: str, **_: object) -> File:
        for part, body in bodies.items():
            if part in url:
                return File(url=url, content=BytesIO(body), status=200)
        msg = f"the stub serves nothing for {url}"
        raise AssertionError(msg)

    monkeypatch.setattr(module, "download_file", download_file)


def _stations(request_class: type, *parameters: tuple[str, str], **kwargs: Any) -> pl.DataFrame:  # noqa: ANN401
    request = request_class(parameters=list(parameters), settings=Settings(cache_disable=True), **kwargs)
    return request.all().df


def _dwd_swsmos(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    catalogue = (
        "Kennung;Name;Streckentyp (1=freie Strecke 2=Bruecke);Streckenbelag (1=Asphalt 2=Beton);Breite;Laenge;Hoehe;"
        "Flughafen;Inaktiv\n"
        "A006;Boeglum;1;1;54,889156;8,908735;2;;\n"
        "C671;AD Südost ;1;1;53,508902;10,066938;4;A;\n"
        "H232;Darup ;1;1;51,932306;7,281613;150;;\n"
        "H266;Guetersloh ;1;1;51,854598;8,324234;76;;\n"
    )
    _serve(monkeypatch, swsmos_api, {"swsKatalog": bz2.compress(catalogue.encode("latin-1"))})
    return _stations(DwdSwsmosRequest, ("hourly", "data"))


def _dwd_road(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    def row(station_id: str, name: str, region: str, lat: str, lon: str, elevation: str, group: str) -> dict[str, str]:
        return {
            "Kennung": station_id,
            "GMA-Name": name,
            "Bundesland  ": region,
            "Straße / Fahrtrichtung": "L5S",
            "Strecken-kilometer 100 m": "2",
            'Streckentyp (Register "Typen")': "1",
            'Streckenlage (Register "Typen")': "2",
            'Streckenbelag (Register "Typen")': "1",
            "Breite (Dezimalangabe)": lat,
            "Länge (Dezimalangabe)": lon,
            "Höhe in m über NN": elevation,
            "GDS-Verzeichnis": group,
            "außer Betrieb (gemeldet)": "",
        }

    sheet = pl.DataFrame(
        [
            row("A006", "Boeglum", "SH", "54.8892", "8.9087", "2", "KK"),
            row("H232", "Darup ", "NW", "51.91667", "7.26667", "155", "KM"),
            row("H266", "Guetersloh ", "NW", "51.854598", "8.324234", "74", "KM"),
        ],
        schema=dict.fromkeys(road_api.DwdRoadRequest._column_mapping, pl.String),  # noqa: SLF001
    )
    # the reader takes the workbook as it comes, so what it is served is the sheet it reads
    monkeypatch.setattr(pl, "read_excel", lambda **_: sheet)
    _serve(monkeypatch, road_api, {"sws_stations": b""})
    return _stations(DwdRoadRequest, ("15_minutes", "data"))


def _imgw_meteorology(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    catalogue = (
        "LP.;Kod 9-znakowy;Nazwa stacji;Rzeka;Rok założenia;Szerokość geograficzna;Długość geograficzna;"
        "Wysokość n.p.m.\r\n"
        "1;249170080;Dzierżkowice;Opawa (112);2024;49 59 32;17 50 47;270\r\n"
        "2;249180010;Pszczyna;Pszczynka (2116);1954;49 59 44;18 55 09;270\r\n"
        "84;249190890;RADZIECHOWY ;Soła (2132);2008;49 38 55;19 09 20;395\r\n"
        "539;252180290;Tuliszków ;Powa (18352);2005;52 04 04;18 16 07;111\r\n"
    )
    _serve(monkeypatch, imgw_meteorology_api, {"kody_stacji": catalogue.encode("utf8")})
    return _stations(ImgwMeteorologyRequest, ("daily", "climate"))


def _imgw_hydrology(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    catalogue = (
        "LP.;Kod 9-znakowy;Nazwa stacji;Rzeka;Rok założenia;Szerokość geograficzna;Długość geograficzna;"
        "Rzędna zera wodowskazu;Kilometr biegu rzeki\r\n"
        "1;149180010;Krzyżanowice;Odra (1);1927;49 59 37;18 17 14;184.806;713.04\r\n"
        "55;149190360;LUDŹMIERZ ;Lepietnica (2141156);1922;49 28 07;19 58 32;596.044;0.27\r\n"
        "58;149190390;LUDŹMIERZ;Wielki Rogoźnik (214116);1924;49 27 34;19 59 12;592.828;0.4\r\n"
    )
    _serve(monkeypatch, imgw_hydrology_api, {"kody_stacji": catalogue.encode("utf8")})
    return _stations(ImgwHydrologyRequest, ("daily", "hydrology"))


def _chmi(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    catalogue = (
        "WSI,GH_ID,BEGIN_DATE,END_DATE,FULL_NAME,GEOGR1,GEOGR2,ELEVATION,\n"
        "0-20000-0-11406,L3CHEB01,1863-10-01T00:00Z,1919-12-31T23:59Z,Cheb,12.362892,50.076212,458,\n"
        "0-20000-0-11406,L3CHEB01,1933-05-07T00:00Z,1938-04-30T23:59Z,Cheb,12.3889,50.0739,471,\n"
        "0-20000-0-11406,L3CHEB01,2001-01-01T00:00Z,3999-12-31T23:59Z,Cheb,12.391389,50.068333,483,\n"
        "0-203-0-20303032003,O1JAVR01,2010-12-09T00:00Z,2023-03-22T10:20Z,Třinec  Oldřichovice  Javorový ,"
        "18.627222,49.628333,930,\n"
        "0-203-0-20303032003,O1JAVR01,2025-04-03T16:00Z,3999-12-31T23:59Z,Třinec  Oldřichovice  Javorový ,"
        "18.627222,49.628333,930,\n"
        "0-203-0-41302035001,B1NLHO01,1957-02-01T00:00Z,1959-11-30T23:59Z,Nová Lhota,17.5947,48.8614,500,\n"
        "0-203-0-41302035001,B1NLHO01,1976-07-20T00:00Z,1980-06-30T23:59Z,Nová Lhota  ?,17.6133,48.8736,420,\n"
    )
    _serve(monkeypatch, chmi_api, {"meta1.csv": catalogue.encode("utf8")})
    return _stations(ChmiObservationRequest, ("daily", "data"))


def _geosphere(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    catalogue = (
        "id,Synopstationsnummer,Stationsname,Länge [°E],Breite [°N],Höhe [m],Startdatum,Enddatum,Bundesland,"
        "Sonnenschein,Globalstrahlung,Synop,Verknüpfungsnummer,Startdatum Teilzeitreihe,Enddatum Teilzeitreihe,"
        "zusammengesetzt\n"
        "1,,Aflenz,15.24069,47.54594,783.2,1983-05-01 00:00:00+00:00,2100-12-31 00:00:00+00:00,Steiermark,"
        "True,True,,,,,ja\n"
        "500,11021,Litschau,15.03831,48.95464,557.6,1983-11-01 00:00:00+00:00,2100-12-31 00:00:00+00:00,"
        "Niederösterreich,True,True,,57,1983-11-01 00:00:00+00:00,,nein\n"
        "2,,Aigen im Ennstal,14.13826,47.53278,641.0,1939-03-01 00:00:00+00:00,2100-12-31 00:00:00+00:00,"
        "Steiermark,True,True,,,,,ja\n"
        "12,,Baden,16.235556,48.011391,244.8,1954-04-01 00:00:00+00:00,2012-05-31 23:59:59+00:00,"
        "Niederösterreich,True,False,,,,,ja\n"
    )
    _serve(monkeypatch, geosphere_api, {"metadata/stations": catalogue.encode("utf8")})
    return _stations(GeosphereObservationRequest, ("daily", "data"))


def _ghcn_hourly(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    catalogue = (
        "GHCN_ID,LATITUDE,LONGITUDE,ELEVATION,STATE,NAME,GSN,(US)HCN_(US)CRN,WMO_ID,ICAO,ISO_CODE\n"
        "GMI0000EDDH,53.6304,9.9882,16.1,,HAMBURG,,,,EDDH,DE\n"
        "FRU65344001,43.188,0.0,360.0,,TARBES-LOURDES-PYRENEES,,,,,FR\n"
        "UKU68-00010,51.48,0.0,48.5,,GREENWICH ROYAL OBSERVATORY,,,,,GB\n"
        "ARM00087500,0.0,0.0,-999.0,,BOGUS ARGENTINEAN,,,87500,,AR\n"
        "ARM00087869,0.0,0.0,-999.0,,NAME AND LOC UNKN,,,87869,,AR\n"
        "BRA00822001,-2.983,-69.583,-999.0,,IPIRANGA(?),,,,,BR\n"
        "RUU71-00102,135.117,48.8,-999.9,,CHABAROWKA,,,,,XX\n"
        "RUU71-00113,104.367,52.283,-999.9,,IRKUTSK,,,,,XX\n"
    )
    _serve(monkeypatch, ghcn_api, {"ghcnh-station-list": catalogue.encode("utf8")})
    return _stations(NoaaGhcnRequest, ("hourly", "data"))


def _ghcn_daily(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    stations = (
        "BR000269000  -2.9830  -69.5830    0.0    IPIRANGA(?)                            82200\n"
        "FRE00104116  43.1881    0.0000  360.0    TARBES - OSSUN                         07621\n"
        "GM000010147  53.6350    9.9900   11.0    HAMBURG FUHLSBUETTEL           GSN     10147\n"
        "GME00102292  51.4358   12.2414  131.0    LEIPZIG-SCHKEUDITZ                     10469\n"
    )
    # the stations that report this year have no end, so the rule against an end in the future holds them (GH-2643)
    this_year = dt.datetime.now(dt.UTC).year
    inventory = (
        "BR000269000  -2.9830  -69.5830 PRCP 1979 1996\n"
        f"FRE00104116  43.1881    0.0000 TMAX 1946 {this_year}\n"
        f"GM000010147  53.6350    9.9900 TMAX 1891 {this_year}\n"
        f"GME00102292  51.4358   12.2414 TMAX 1934 {this_year}\n"
    )
    _serve(
        monkeypatch,
        ghcn_api,
        {"ghcnd-stations": stations.encode("utf8"), "ghcnd-inventory": inventory.encode("utf8")},
    )
    return _stations(NoaaGhcnRequest, ("daily", "data"))


def _ipma(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    def feature(station_id: int, name: str, lon: float, lat: float) -> dict[str, Any]:
        return {
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "type": "Feature",
            "properties": {"idEstacao": station_id, "localEstacao": name},
        }

    catalogue = [
        feature(1210881, "Olhão, EPPO", -7.821, 37.033),
        feature(1210883, "Tavira", -7.62050375, 37.12166968),
        feature(6210817, "Ponte de Sôr / Aeródromo", -8.05417, 39.21536),
    ]
    _serve(monkeypatch, ipma_api, {"stations.json": json.dumps(catalogue).encode("utf8")})
    return _stations(IpmaObservationRequest, ("hourly", "data"))


def _lhmt(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    catalogue = [
        {"code": "akmenes-ams", "name": "Akmenės AMS", "coordinates": {"latitude": 56.24992, "longitude": 22.73081}},
        {"code": "alytaus-ams", "name": "Alytaus AMS", "coordinates": {"latitude": 54.412435, "longitude": 24.063274}},
        {"code": "anyksciu-ams", "name": "Anykščių AMS", "coordinates": {"latitude": 55.51735, "longitude": 25.1178}},
    ]
    _serve(monkeypatch, lhmt_api, {"/stations": json.dumps(catalogue).encode("utf8")})
    return _stations(LhmtObservationRequest, ("hourly", "data"))


# positions are degrees and minutes (`44.50` is 44°50'), west and south signed
MOSMIX_CATALOGUE = (
    "ID    ICAO NAME                 LAT    LON     ELEV\n"
    "----- ---- -------------------- -----  ------- -----\n"
    "01001 ENJA JAN MAYEN             70.56   -8.40    10\n"
    "03772 EGLL LONDON                51.29   -0.27    24\n"
    "07510 LFBD BORDEAUX              44.50   -0.42    49\n"
    "10147 EDDH HAMBURG-FU.           53.38   10.00    16\n"
    " A191 ---- WAGERSROTT            54.40    9.49    40\n"
    "23205 ---- NAR?JAN-MAR           67.38   53.01   139\n"
    "72520 KPIT PITTSBURGH INT.       40.30  -80.13   367\n"
)


def _dwd_mosmix(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    _serve(monkeypatch, dwd_catalogue, {"mosmix_stationskatalog": MOSMIX_CATALOGUE.encode("latin-1")})
    return _stations(DwdMosmixRequest, ("hourly", "small"))


def _aemet(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    # the inventory needs a key, so it is served in place of the download of `_fetch_datos`; the names and ids are
    # those the list pads with blanks (GH-2654), the positions and provinces worded after the list's own shape
    # (degrees, minutes and seconds with the hemisphere)
    def row(station_id: str, name: str, region: str, lat: str, lon: str, elevation: str) -> dict[str, str]:
        return {
            "indicativo": station_id,
            "nombre": name,
            "provincia": region,
            "altitud": elevation,
            "latitud": lat,
            "longitud": lon,
            "indsinop": "",
        }

    catalogue = [
        row("2847X", "PEDROSILLO DE LOS AIRES   ", "SALAMANCA", "405512N", "060328W", "888"),
        row("2863C", "PEDRAZA DE ALBA  ", "SALAMANCA", "405347N", "053022W", "840"),
        row("3195", "MADRID, RETIRO", "MADRID", "402441N", "034040W", "667"),
        row("B434X", "PORTOCOLOM  ", "ILLES BALEARS", "391259N", "031218E", "5"),
        row("C314Z", "VALLEHERMOSO, ALTO IGUALERO  ", "SANTA CRUZ DE TENERIFE", "281134N", "172221W", "790"),
    ]
    payload = json.dumps(catalogue).encode("latin-1")
    monkeypatch.setattr(aemet_api, "_fetch_datos", lambda *_args, **_kwargs: payload)
    request = AemetObservationRequest(
        parameters=[("daily", "data")], settings=Settings(cache_disable=True, auth={"aemet": "stub"})
    )
    return request.all().df


def _metoffice(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    # the archive needs a CEDA login, so the token and the release are given and the catalogue is served in the
    # BADC-CSV of the archive; the names are those the list pads with a blank (GH-2654), the rest worded after it
    catalogue = (
        "Conventions,G,BADC-CSV,1\n"
        "data\n"
        "src_id,station_name,station_file_name,historic_county,authority,"
        "station_latitude,station_longitude,station_elevation,first_year,last_year\n"
        '00470,"GARSTON, BUILDING RESEARCH ",garston-bre,hertfordshire,Met Office,51.69,-0.37,85,1952,1976\n'
        "01316,PORTLAND ,portland,dorset,Met Office,50.54,-2.45,12,1941,2003\n"
        "04857,BRAISEWORTH HALL ,braiseworth-hall,suffolk,Met Office,52.33,1.13,45,1969,2005\n"
        "12812,STONETHWAITE ,stonethwaite,cumbria,Met Office,54.5,-3.15,150,1960,2009\n"
        "end data\n"
    )
    monkeypatch.setattr(metoffice_api, "get_ceda_token", lambda _settings: "token")
    monkeypatch.setattr(metoffice_api, "latest_release_version", lambda _settings, _token: "202607")
    _serve(monkeypatch, metoffice_api, {"station-metadata": catalogue.encode("utf8")})
    return _stations(MetOfficeObservationRequest, ("daily", "rain"))


def _metno_frost(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    # the list needs a client, so a stub of one is given; the names are those the list pads with a blank (GH-2654),
    # the rest worded after it (ids with their `SN` prefix, the stamps as ISO text, the position as lon, lat)
    def source(station_id: str, name: str, county: str, lon: float, lat: float, masl: int) -> dict[str, Any]:
        return {
            "id": station_id,
            "name": name,
            "validFrom": "2000-01-01T00:00:00.000Z",
            "geometry": {"@type": "Point", "coordinates": [lon, lat]},
            "county": county,
            "countryCode": "NO",
            "masl": masl,
        }

    catalogue = {
        "data": [
            source("SN18700", "OSLO - BLINDERN", "OSLO", 10.72, 59.94, 94),
            source("SN46380", "KVANNDALEN ", "VESTLAND", 6.62, 60.88, 388),
            source("SN46530", "VIVASSDALEN ", "VESTLAND", 6.4, 61.02, 54),
        ]
    }
    _serve(monkeypatch, frost_api, {"sources/v0.jsonld": json.dumps(catalogue).encode("utf8")})
    request = MetnoFrostRequest(
        parameters=[("hourly", "data")],
        settings=Settings(cache_disable=True, auth={"metno_frost": ("stub-client", "stub-secret")}),
    )
    return request.all().df


def question_mark_in_the_name(row: dict[str, Any]) -> bool:
    """Say whether a name is damaged by a question mark and by nothing worse."""
    return "?" in row["name"] and not has_encoding_damage(row["name"], question_marks=False)


# a source that writes a character it cannot encode as a question mark leaves a name such as NAR?JAN-MAR or IPIRANGA(?)
QUESTION_MARK = "the source writes a character it could not encode as a question mark"
GHCN_NO_POSITION = Accepted(
    "coordinates_missing",
    "the list gives the BOGUS and the NAME AND LOC UNKN placeholders 0, 0 and the two historic Russian stations "
    "latitudes of 135 and 104; none has a position (GH-2380), and a station without one is picked by no search",
    where=lambda row: (
        (row["name"] or "").startswith(("BOGUS ", "NAME AND LOC")) or (row["station_id"] or "").startswith("RUU71-")
    ),
)
GHCN_NAMES = Accepted(
    "name_encoding", f"the list names stations IPIRANGA(?) and alike: {QUESTION_MARK}", question_mark_in_the_name
)

DWD_NAMES = Accepted("name_encoding", f"the station catalogue of DWD: {QUESTION_MARK}", question_mark_in_the_name)
CHMI_NAME = Accepted(
    "name_encoding",
    "the list names the station `Nová Lhota  ?` in its last period (1976 to 1980), the source's own value",
    where=lambda row: row["station_id"] == "0-203-0-41302035001",
)

# the stations of the Environment Agency's hydrology listing (`?_limit=20000`, 9537 stations on 2026-10-15) that are
# not of the common shape, trimmed to the fields the reader reads and `colocatedStation` (GH-2933). "Beach's Mill"
# has two spellings of its name, so `label` is an array there, and "Udford" has closed twice, so `dateClosed` is;
# of the 9537 stations 1 has each, and 821 have a `colocatedStation` array, which the reader does not read. "Banks
# Road" has no position and no `easting` or `northing`, "Burton Coggles" has a measure with no `period`, and "Beer
# Football Ground" is a borehole
EA_HYDROLOGY_LISTING = [
    {
        "label": ["Beach's Mill", "Beach'S Mill"],
        "notation": "fcdd7420-c000-4db7-99fa-3835a65372fe",
        "easting": 569009,
        "northing": 207165,
        "lat": 51.737703,
        "long": 0.446302,
        "dateOpened": "1962-04-01",
        "measures": [
            {
                "@id": "http://environment.data.gov.uk/hydrology/id/measures/fcdd7420-c000-4db7-99fa-3835a65372fe-flow-i-900-m3s-qualified",
                "parameter": "flow",
                "period": 900,
                "valueStatistic": {"@id": "http://environment.data.gov.uk/reference/def/core/instantaneous"},
            },
            {
                "@id": "http://environment.data.gov.uk/hydrology/id/measures/fcdd7420-c000-4db7-99fa-3835a65372fe-flow-min-86400-m3s-qualified",
                "parameter": "flow",
                "period": 86400,
                "valueStatistic": {"@id": "http://environment.data.gov.uk/reference/def/core/minimum"},
            },
            {
                "@id": "http://environment.data.gov.uk/hydrology/id/measures/fcdd7420-c000-4db7-99fa-3835a65372fe-flow-m-86400-m3s-qualified",
                "parameter": "flow",
                "period": 86400,
                "valueStatistic": {"@id": "http://environment.data.gov.uk/reference/def/core/mean"},
            },
            {
                "@id": "http://environment.data.gov.uk/hydrology/id/measures/fcdd7420-c000-4db7-99fa-3835a65372fe-level-i-900-m-qualified",
                "parameter": "level",
                "period": 900,
                "valueStatistic": {"@id": "http://environment.data.gov.uk/reference/def/core/instantaneous"},
            },
            {
                "@id": "http://environment.data.gov.uk/hydrology/id/measures/fcdd7420-c000-4db7-99fa-3835a65372fe-flow-max-86400-m3s-qualified",
                "parameter": "flow",
                "period": 86400,
                "valueStatistic": {"@id": "http://environment.data.gov.uk/reference/def/core/maximum"},
            },
            {
                "@id": "http://environment.data.gov.uk/hydrology/id/measures/fcdd7420-c000-4db7-99fa-3835a65372fe-level-min-86400-m-qualified",
                "parameter": "level",
                "period": 86400,
                "valueStatistic": {"@id": "http://environment.data.gov.uk/reference/def/core/minimum"},
            },
            {
                "@id": "http://environment.data.gov.uk/hydrology/id/measures/fcdd7420-c000-4db7-99fa-3835a65372fe-level-max-86400-m-qualified",
                "parameter": "level",
                "period": 86400,
                "valueStatistic": {"@id": "http://environment.data.gov.uk/reference/def/core/maximum"},
            },
        ],
    },
    {
        "label": "Udford",
        "notation": "ab5db73f-059e-4d10-9b92-5a640db3c1ab",
        "easting": 357570,
        "northing": 530450,
        "lat": 54.667313,
        "long": -2.659359,
        "dateOpened": "1976-01-06",
        "dateClosed": ["2015-01-31", "2024-03-14"],
        "colocatedStation": [
            {"@id": "http://environment.data.gov.uk/hydrology/id/stations/ab5db73f-059e-4d10-9b92-5a640db3c1ab_762007"}
        ],
        "measures": [
            {
                "@id": "http://environment.data.gov.uk/hydrology/id/measures/ab5db73f-059e-4d10-9b92-5a640db3c1ab-level-i-900-m-qualified",
                "parameter": "level",
                "period": 900,
                "valueStatistic": {"@id": "http://environment.data.gov.uk/reference/def/core/instantaneous"},
            },
            {
                "@id": "http://environment.data.gov.uk/hydrology/id/measures/ab5db73f-059e-4d10-9b92-5a640db3c1ab-flow-i-900-m3s-qualified",
                "parameter": "flow",
                "period": 900,
                "valueStatistic": {"@id": "http://environment.data.gov.uk/reference/def/core/instantaneous"},
            },
            {
                "@id": "http://environment.data.gov.uk/hydrology/id/measures/ab5db73f-059e-4d10-9b92-5a640db3c1ab-level-max-86400-m-qualified",
                "parameter": "level",
                "period": 86400,
                "valueStatistic": {"@id": "http://environment.data.gov.uk/reference/def/core/maximum"},
            },
            {
                "@id": "http://environment.data.gov.uk/hydrology/id/measures/ab5db73f-059e-4d10-9b92-5a640db3c1ab-flow-m-86400-m3s-qualified",
                "parameter": "flow",
                "period": 86400,
                "valueStatistic": {"@id": "http://environment.data.gov.uk/reference/def/core/mean"},
            },
            {
                "@id": "http://environment.data.gov.uk/hydrology/id/measures/ab5db73f-059e-4d10-9b92-5a640db3c1ab-level-min-86400-m-qualified",
                "parameter": "level",
                "period": 86400,
                "valueStatistic": {"@id": "http://environment.data.gov.uk/reference/def/core/minimum"},
            },
            {
                "@id": "http://environment.data.gov.uk/hydrology/id/measures/ab5db73f-059e-4d10-9b92-5a640db3c1ab-flow-max-86400-m3s-qualified",
                "parameter": "flow",
                "period": 86400,
                "valueStatistic": {"@id": "http://environment.data.gov.uk/reference/def/core/maximum"},
            },
            {
                "@id": "http://environment.data.gov.uk/hydrology/id/measures/ab5db73f-059e-4d10-9b92-5a640db3c1ab-flow-min-86400-m3s-qualified",
                "parameter": "flow",
                "period": 86400,
                "valueStatistic": {"@id": "http://environment.data.gov.uk/reference/def/core/minimum"},
            },
        ],
    },
    {
        "label": "Beer Football Ground",
        "notation": "3e7d8886-824c-4c3b-80d3-038758ba3179",
        "easting": 311900,
        "northing": 98773,
        "lat": 50.781813,
        "long": -3.25102,
        "dateOpened": "2016-04-19",
        "measures": [
            {
                "@id": "http://environment.data.gov.uk/hydrology/id/measures/3e7d8886-824c-4c3b-80d3-038758ba3179-gw-logged-i-subdaily-mAOD-qualified",
                "parameter": "level",
                "period": 900,
                "valueStatistic": {"@id": "http://environment.data.gov.uk/reference/def/core/instantaneous"},
            }
        ],
    },
    {
        "label": "Banks Road",
        "notation": "32f5b1ea-29f7-4d6c-b473-a9e5da0e59d1_U30028",
        "dateOpened": "1999-08-22",
        "measures": [
            {
                "@id": "http://environment.data.gov.uk/hydrology/id/measures/32f5b1ea-29f7-4d6c-b473-a9e5da0e59d1_U30028-flow-min-86400-m3s-qualified",
                "parameter": "flow",
                "period": 86400,
                "valueStatistic": {"@id": "http://environment.data.gov.uk/reference/def/core/minimum"},
            },
            {
                "@id": "http://environment.data.gov.uk/hydrology/id/measures/32f5b1ea-29f7-4d6c-b473-a9e5da0e59d1_U30028-flow-max-86400-m3s-qualified",
                "parameter": "flow",
                "period": 86400,
                "valueStatistic": {"@id": "http://environment.data.gov.uk/reference/def/core/maximum"},
            },
            {
                "@id": "http://environment.data.gov.uk/hydrology/id/measures/32f5b1ea-29f7-4d6c-b473-a9e5da0e59d1_U30028-flow-m-86400-m3s-qualified",
                "parameter": "flow",
                "period": 86400,
                "valueStatistic": {"@id": "http://environment.data.gov.uk/reference/def/core/mean"},
            },
            {
                "@id": "http://environment.data.gov.uk/hydrology/id/measures/32f5b1ea-29f7-4d6c-b473-a9e5da0e59d1_U30028-flow-i-900-m3s-qualified",
                "parameter": "flow",
                "period": 900,
                "valueStatistic": {"@id": "http://environment.data.gov.uk/reference/def/core/instantaneous"},
            },
        ],
    },
    {
        "label": "Burton Coggles",
        "notation": "c7e13884-4a02-4df3-b184-09aea28cf8e8_3_020",
        "easting": 498965,
        "northing": 325135,
        "lat": 52.814674,
        "long": -0.533054,
        "dateOpened": "1974-07-30",
        "colocatedStation": [
            {"@id": "http://environment.data.gov.uk/hydrology/id/stations/c7e13884-4a02-4df3-b184-09aea28cf8e8"}
        ],
        "measures": [
            {
                "@id": "http://environment.data.gov.uk/hydrology/id/measures/c7e13884-4a02-4df3-b184-09aea28cf8e8_3_020-gw-logged-i-subdaily-mAOD-qualified",
                "parameter": "level",
                "period": 900,
                "valueStatistic": {"@id": "http://environment.data.gov.uk/reference/def/core/instantaneous"},
            },
            {
                "@id": "http://environment.data.gov.uk/hydrology/id/measures/c7e13884-4a02-4df3-b184-09aea28cf8e8_3_020-gw-dipped-i-mAOD-qualified",
                "parameter": "level",
                "valueStatistic": {"@id": "http://environment.data.gov.uk/reference/def/core/instantaneous"},
            },
        ],
    },
    {
        "label": "Siddington",
        "notation": "0a037c75-cb02-4c6f-a717-a8a1132b132e_SU09_56",
        "easting": 404065,
        "northing": 199885,
        "lat": 51.697692,
        "long": -1.942576,
        "dateClosed": "1982-11-11",
        "colocatedStation": [
            {"@id": "http://environment.data.gov.uk/hydrology/id/stations/0a037c75-cb02-4c6f-a717-a8a1132b132e"}
        ],
        "measures": [
            {
                "@id": "http://environment.data.gov.uk/hydrology/id/measures/0a037c75-cb02-4c6f-a717-a8a1132b132e_SU09_56-gw-dipped-i-mAOD-qualified",
                "parameter": "level",
                "valueStatistic": {"@id": "http://environment.data.gov.uk/reference/def/core/instantaneous"},
            }
        ],
    },
]
EA_NO_POSITION = Accepted(
    "coordinates_missing",
    "the listing gives the station Banks Road no position, the only one of 9537; a station without one is picked by "
    "no search, and its readings are still reached by its id (GH-2933)",
    where=lambda row: row["station_id"] == "32f5b1ea-29f7-4d6c-b473-a9e5da0e59d1_U30028",
)


def _ea_hydrology(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    _serve(monkeypatch, ea_api, {"stations.json": json.dumps({"items": EA_HYDROLOGY_LISTING}).encode("utf8")})
    return _stations(EAHydrologyRequest, ("15_minutes", "data"))


def _dwd_poi(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    # the stations are those of the MOSMIX catalogue that have a report file, whose name pads an id of four characters
    # with an underscore (`A191_-BEOB.csv`, as listed on 2026-10-15)
    _serve(monkeypatch, dwd_catalogue, {"mosmix_stationskatalog": MOSMIX_CATALOGUE.encode("latin-1")})
    base = "https://opendata.dwd.de/weather/weather_reports/poi/"
    files = [f"{base}{station_id:_<5}-BEOB.csv" for station_id in ("01001", "10147", "A191", "23205")]
    monkeypatch.setattr(poi_api, "list_remote_files_fsspec", lambda *_args, **_kwargs: files)
    return _stations(DwdPoiRequest, ("hourly", "data"))


# the position the reader must give a station of `dwd/dmo`, in decimal degrees: the list writes degrees and minutes
# (`70.56` is 70 degrees 56 minutes, which is 70.93), and no rule can tell 70.93 from 70.56. A station DWD publishes at
# the wrong place is expected at the place it is (GH-2646, GH-2897)
DMO_POSITIONS: dict[str, tuple[float, float]] = {
    "01001": (70.93, -8.67),  # JAN MAYEN: minutes behind whole degrees, a west longitude
    "03377": (53.17, -0.52),  # WADDINGTON, published `.31` east for 0.52 west
    "03772": (51.48, -0.45),  # LONDON: `-.27`, the minus before the missing whole degrees
    "08286": (39.95, -0.07),  # CASTELLON DE LA PLAN: `. 4` is 4 minutes and not 40, published east for west
    "08370": (38.78, 0.17),  # JAVEA, published `-.10` west for 0.17 east
    "43599": (-0.68, 73.15),  # GAN: a south latitude of minutes only
    "61226": (16.27, -0.05),  # GAO: `.-3`, the minus behind the point, which is 3 minutes west
    "63705": (0.05, 32.45),  # ENTEBBE: a latitude `. 3`, 3 minutes with a blank for the tens
    "82106": (-0.13, -67.07),  # SAO GABRIEL CACHOEI: `.-8` south of the equator
    "F9424": (-22.15, -49.07),  # BAURU, published 22.15 north for south
    "P0563": (51.87, -0.37),  # LONDON LUTON, published `.22` east for 0.37 west
}
DMO_EXPECTED = {
    station_id: {"latitude": latitude, "longitude": longitude}
    for station_id, (latitude, longitude) in DMO_POSITIONS.items()
}


def _dwd_dmo(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    # `dmo_stationsliste_txt.asc` (2026-10-15, 5811 stations), the rows that showed a defect: a position with no whole
    # degrees (`.31`, `-.27`), a blank for the tens of minutes (`. 4`, `. 3`) and a minus behind the point (`.-3`,
    # `.-8`), which the sign of a west or south position is lost with (GH-2897), and the stations DWD publishes at the
    # wrong place (GH-2646). The list is no country's, so the rules hold these rows to a position that is there and
    # on Earth, and `DMO_POSITIONS` to where it is
    catalogue = (
        "ID    ICAO NAME                 LAT    LON     ELEV\r\n"
        "----- ---- -------------------- -----  ------- -----\r\n"
        "01001 ENJA JAN MAYEN             70.56   -8.40    10\r\n"
        "01025 ---- TROMSOE               69.41   18.55    10\r\n"
        "03377 ---- WADDINGTON            53.10     .31    68\r\n"
        "03768 ---- FARNBOROUGH           51.17     .46    65\r\n"
        "03772 EGLL LONDON                51.29    -.27    24\r\n"
        "08286 LECN CASTELLON DE LA PLAN  39.57     . 4    36\r\n"
        "08370 ---- JAVEA/YUNTAMIEN       38.47    -.10    15\r\n"
        "10147 EDDH HAMBURG-FU.           53.38   10.00    16\r\n"
        "43599 VRGN GAN                    -.41   73.09     2\r\n"
        "61226 GAGO GAO                   16.16     .-3   265\r\n"
        "63705 HUEN ENTEBBE                 . 3   32.27  1155\r\n"
        "82106 SBUA SAO GABRIEL CACHOEI     .-8  -67.04    90\r\n"
        "F9424 SBAE BAURU/AREALVA APT.    22.09  -49.04   594\r\n"
        "P0563 EGGW LONDON LUTON          51.52     .22   160\r\n"
    )
    _serve(monkeypatch, dmo_api, {"dmo_stationsliste_txt": catalogue.encode("latin-1")})
    # the product forecasts for the stations that have a directory, here every one the list names
    ids = [line[:5] for line in catalogue.splitlines()[2:]]
    directories = [{"name": f"single_stations/{station_id}/"} for station_id in ids]
    monkeypatch.setattr(dmo_api, "list_remote_directory_fsspec", lambda *_args, **_kwargs: directories)
    return _stations(DwdDmoRequest, ("hourly", "icon"))


# what the reader must give of the stations of `dwd/observation`, read from the lines of its stub: the name is every
# word between the position and the region, and a trailing `Frei` is no part of either
OBSERVATION_EXPECTED: dict[str, dict[str, Any]] = {
    "00001": {
        "name": "Aach",
        "region": "Baden-Württemberg",
        "elevation": 478.0,
        "latitude": 47.8413,
        "longitude": 8.8493,
    },
    "00011": {"name": "Donaueschingen (Landeplatz)", "region": "Baden-Württemberg", "elevation": 680.0},
    "00197": {"name": "Arolsen-Volkhardinghausen, Bad", "region": "Hessen", "latitude": 51.3219, "longitude": 9.0558},
    "00314": {"name": "Kubschütz, Kr. Bautzen", "region": "Sachsen", "latitude": 51.1604, "longitude": 14.5042},
    "01332": {"name": "Falkenberg,Kr.Rottal-Inn", "region": "Bayern", "latitude": 48.4832, "longitude": 12.7241},
    "03657": {"name": "Nümbrecht auf dem Lindchen", "region": "Nordrhein-Westfalen", "elevation": 341.0},
}


def _dwd_observation(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    # `KL_Tageswerte_Beschreibung_Stationen.txt` (2026-10-15) with the blanks its lines are padded to a thousand
    # characters with cut off: names with blanks, commas and umlauts, a row with no `Frei`, and stations that report
    # today
    catalogue = (
        "Stations_id von_datum bis_datum Stationshoehe geoBreite geoLaenge Stationsname Bundesland Abgabe\r\n"
        "----------- --------- --------- ------------- --------- --------- ----------------------------------------- "
        "---------- ------\r\n"
        "00001 19370101 19860630            478     47.8413    8.8493 Aach                                     "
        "Baden-Württemberg                        Frei\r\n"
        "00003 18910101 20110331            202     50.7827    6.0941 Aachen                                   "
        "Nordrhein-Westfalen                      Frei\r\n"
        "00011 19800901 20261013            680     47.9736    8.5205 Donaueschingen (Landeplatz)              "
        "Baden-Württemberg                        Frei\r\n"
        "00106 19710101 20061201            500     51.7976   10.4429 Altenau                                  "
        "Niedersachsen\r\n"
        "00197 19900801 20261013            365     51.3219    9.0558 Arolsen-Volkhardinghausen, Bad           "
        "Hessen                                   Frei\r\n"
        "00314 18631201 20261013            234     51.1604   14.5042 Kubschütz, Kr. Bautzen                   "
        "Sachsen                                  Frei\r\n"
        "01332 19660701 20261013            471     48.4832   12.7241 Falkenberg,Kr.Rottal-Inn                 "
        "Bayern                                   Frei\r\n"
        "03657 19830601 20150831            341     50.9081    7.5543 Nümbrecht auf dem Lindchen               "
        "Nordrhein-Westfalen                      Frei\r\n"
    )
    # the directory lists the description and a file for each station, named `tageswerte_KL_<id>_<from>_<to>_hist.zip`
    # (the names of 00001 and 00003 as listed, the others worded after them), but for Altenau (00106), which has none
    # in the directory (2026-10-15): the reader drops a station that is described and has no file
    base = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/daily/kl/historical/"
    files = [f"{base}KL_Tageswerte_Beschreibung_Stationen.txt"]
    for line in catalogue.splitlines()[2:]:
        if line.startswith("00106"):
            continue
        files.append(f"{base}tageswerte_KL_{line[:5]}_{line[6:14]}_{line[15:23]}_hist.zip")
    monkeypatch.setattr(dwd_fileindex, "list_remote_files_fsspec", lambda *_args, **_kwargs: files)
    _serve(monkeypatch, dwd_metaindex, {"Beschreibung_Stationen": catalogue.encode("latin-1")})
    return _stations(DwdObservationRequest, ("daily", "climate_summary"), periods="historical")


def _dwd_derived(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    # `fg_duett_Beschreibung_Stationen.txt` (2026-10-15), whose stations are named `<name>_DUETT`, with the blanks its
    # lines are padded with cut off
    catalogue = (
        "Stations_id von_datum bis_datum Stationshoehe geoBreite geoLaenge Stationsname Bundesland\r\n"
        "----------- --------- --------- ------------- --------- --------- ----------------------------------------- "
        "----------\r\n"
        "18000 20240401 20261014            680     47.9736    8.5205 Donaueschingen (Landeplatz)_DUETT        "
        "Baden-Württemberg\r\n"
        "18001 20240401 20261014             44     52.9336    8.2370 Großenkneten_DUETT                       "
        "Niedersachsen\r\n"
        "18008 20240401 20261014              0     53.8633    8.1275 Leuchtturm Alte Weser_DUETT              "
        "Niedersachsen\r\n"
        "18020 20240401 20261014            365     51.3219    9.0558 Arolsen-Volkhardinghausen, Bad_DUETT     "
        "Hessen\r\n"
    )
    _serve(monkeypatch, derived_metaindex, {"fg_duett_Beschreibung_Stationen": catalogue.encode("latin-1")})
    # a file for each station, `stundenwerte_duett_FG_<id>_akt.zip` as listed
    base = (
        "https://opendata.dwd.de/climate_environment/CDC/derived_germany/climate/hourly/duett/radiation_global/recent/"
    )
    files = [f"{base}stundenwerte_duett_FG_{station_id}_akt.zip" for station_id in ("18000", "18001", "18008", "18020")]
    monkeypatch.setattr(dwd_fileindex, "list_remote_files_fsspec", lambda *_args, **_kwargs: files)
    return _stations(DwdDerivedRequest, ("hourly", "radiation_global"))


def _dwd_phenology(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    # `PH_Beschreibung_Phaenologie_Stationen_Jahresmelder.txt` and `..._Sofortmelder.txt` (2026-10-15), the values of
    # five rows as published, laid out again with narrower padding (the lines are padded to 800 characters):
    # positions in decimal degrees, the day a station was dissolved empty while it runs, the header with the stray
    # tab inside "Naturraumgruppe", latin-1
    header = (
        "Stations_id;Stationsname                               ;geograph.Breite;geograph.Laenge;Stationshoehe;"
        "Naturraumgruppe_Code;Naturraumgruppe                                           \t\t    ;Naturraum_Code;"
        "Naturraum                                                                ;Datum Stationsaufloesung;"
        "Bundesland                              ;eor;"
    )

    def row(*fields: str) -> str:
        station_id, name, lat, lon, elevation, group_code, group, area_code, area, closed, region = fields
        return (
            f"{station_id:<22};{name:<40};{lat:>12}    ;{lon:>10}     ;{elevation:>5}       ;{group_code};{group:<60};"
            f"{area_code};{area:<80};{closed:<23};{region:<40};eor;"
        )

    annual = [
        header,
        row(
            *("07501", "Flensburg, kreisfreie Stadt Flensburg", "54.7833", "9.4333", "25", "70"),
            *("Schleswig-Holsteinisches Hügelland", "7000", "Angeln", "31.12.1999", "Schleswig-Holstein"),
        ),
        row(
            *("07532", "Norder-Hever-Koog", "54.4000", "8.7667", "2", "68"),
            *(
                "Schleswig-Holsteinische Marschen (und Nordseeinseln)",
                "6830",
                "Eiderstedter Marsch",
                "",
                "Schleswig-Holstein",
            ),
        ),
        row(
            *("08382", "Bederkesa, Bad", "53.6283", "8.8324", "10", "63"),
            *("Stader Geest", "6330", "Wesermünder Geest", "", "Niedersachsen"),
        ),
    ]
    immediate = [
        header,
        row(
            *("07502", "Kiel-Pries", "54.4000", "10.1500", "25", "70"),
            *("Schleswig-Holsteinisches Hügelland", "7020", "Ostholsteinisches Hügel- und Seenland"),
            *("31.12.1998", "Schleswig-Holstein"),
        ),
        row(
            *("09455", "König, Bad", "49.7333", "9.0000", "180", "14"),
            *("Odenwald, Spessart und Südrhön", "1440", "Sandsteinodenwald", "", "Hessen"),
        ),
    ]
    bodies = {
        "Stationen_Jahresmelder": "\n".join(annual).encode("latin-1"),
        "Stationen_Sofortmelder": "\r\n".join(immediate).encode("latin-1"),
    }
    _serve(monkeypatch, phenology_api, bodies)
    return _stations(DwdPhenologyRequest, ("annual", "annual_apple"), ("annual", "immediate_apple"))


def _dmi(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    # `climateData/collections/station/items` (2026-10-15), trimmed to the properties the reader reads: DMI lists a
    # station once for each period of its metadata, 1063 stations in 4666 records, of which these are the first and
    # the last record of Københavns Lufthavn and Skagen Fyr and all the records of Pituffik and Qaanaaq, oldest first.
    # The reader takes the one still open (`validTo` null): the earlier records of Pituffik and Qaanaaq have neither the
    # elevation nor the position and name of the later ones, and `created` is the same on all records of a station
    # (see GH-2946)
    def feature(
        station_id: str,
        name: str,
        country: str,
        lon: float,
        lat: float,
        height: float | None,
        valid: tuple[str, str | None],
    ) -> dict[str, Any]:
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "stationId": station_id,
                "name": name,
                "country": country,
                "stationHeight": height,
                "validFrom": valid[0],
                "validTo": valid[1],
                "created": "2026-09-30T11:59:36Z" if station_id in {"04202", "04205"} else "2026-09-30T11:59:37Z",
            },
        }

    catalogue = {
        "type": "FeatureCollection",
        "features": [
            feature(
                "06180",
                "Københavns Lufthavn",
                "DNK",
                12.6455,
                55.614,
                5.0,
                ("1983-06-16T00:00:00Z", "2019-01-15T13:34:48Z"),
            ),
            feature("06180", "Københavns Lufthavn", "DNK", 12.6454, 55.614, 5.0, ("2024-11-14T16:10:37Z", None)),
            feature(
                "06041", "Skagen Fyr", "DNK", 10.6318, 57.7363, 3.2, ("1953-01-01T00:00:00Z", "2000-12-14T00:00:00Z")
            ),
            feature("06041", "Skagen Fyr", "DNK", 10.6316, 57.7364, 3.2, ("2019-01-30T15:42:23Z", None)),
            feature(
                "04202", "Pituffik", "GRL", -68.75, 76.5333, None, ("1948-12-31T00:00:00Z", "2006-10-16T00:00:00Z")
            ),
            feature(
                "04202", "Pituffik", "GRL", -68.7031, 76.5311, 76.5, ("2006-10-16T00:00:00Z", "2019-01-15T13:34:47Z")
            ),
            feature("04202", "Pituffik", "GRL", -68.7031, 76.5311, 77.0, ("2019-01-15T13:34:47Z", None)),
            feature("04205", "Qaanaaq", "GRL", -69.2, 77.4833, None, ("1964-01-01T00:00:00Z", "1980-07-01T00:00:00Z")),
            feature(
                "04205",
                "Mittarfik Qaanaaq",
                "GRL",
                -69.3744,
                77.4853,
                16.0,
                ("1980-07-01T00:00:00Z", "2019-01-15T13:34:47Z"),
            ),
            feature("04205", "Mittarfik Qaanaaq", "GRL", -69.3744, 77.4853, 16.0, ("2019-01-15T13:34:47Z", None)),
        ],
    }
    _serve(monkeypatch, dmi_api, {"station/items": json.dumps(catalogue).encode("utf8")})
    return _stations(DmiObservationRequest, ("daily", "data"))


def _eccc(monkeypatch: pytest.MonkeyPatch, resolution: str) -> pl.DataFrame:
    # `collections/climate-stations/items` (2026-10-15), five of the 8435 features trimmed to the properties the reader
    # reads, with the dates of the collections as published (Chemainus and Carway have no hourly collection, Alert A no
    # daily and no monthly one, Gladman Point no monthly dates). A station is listed for hourly and daily only if the
    # list gives its collection a first date, and with the dates of that collection (GH-2867), and for monthly only if
    # `HAS_MONTHLY_SUMMARY` is `Y` (GH-3006): Alert A has `N`, Gladman Point `Y` with no monthly date, as 763 stations
    # do (monthly rows nonetheless). `LATITUDE` and `LONGITUDE`
    # are packed degrees, minutes and seconds (`485500000` is 48 deg 55'), while the geometry of the feature is decimal
    # degrees (GH-2942); `ELEVATION` is text, and null for a station without one
    keys = ("FIRST", "LAST", "HLY_FIRST", "HLY_LAST", "DLY_FIRST", "DLY_LAST", "MLY_FIRST", "MLY_LAST")

    def feature(
        station_id: int,
        name: str,
        region: str,
        packed: tuple[int, int],
        zone: str,
        elevation: str | None,
        dates: tuple[str | None, ...],
        geometry: list[float],
        monthly_summary: str = "Y",
    ) -> dict[str, Any]:
        return {
            "type": "Feature",
            "properties": {
                "STN_ID": station_id,
                "STATION_NAME": name,
                "PROV_STATE_TERR_CODE": region,
                "LATITUDE": packed[0],
                "LONGITUDE": packed[1],
                "TIMEZONE": zone,
                "ELEVATION": elevation,
                **{f"{key}_DATE": date for key, date in zip(keys, dates, strict=True)},
                "HAS_MONTHLY_SUMMARY": monthly_summary,
            },
            "geometry": {"type": "Point", "coordinates": geometry},
        }

    catalogue = {
        "type": "FeatureCollection",
        "features": [
            feature(
                2,
                "CHEMAINUS BARE POINT",
                "BC",
                (485500000, -1234200000),
                "PST",
                "3.00",
                (
                    *("1979-01-01 00:00:00", "1979-12-31 00:00:00", None, None),
                    *("1979-11-01 00:00:00", "1979-12-31 00:00:00", "1979-01-01 00:00:00", "1979-12-01 00:00:00"),
                ),
                [-123.7, 48.916666666666664],
            ),
            feature(
                52,
                "ESQUIMALT HARBOUR",
                "BC",
                (482555100, -1232621600),
                "PST",
                "3.00",
                (
                    *("1957-01-01 00:00:00", "2026-10-12 12:30:10", "1994-02-01 00:00:00", "2026-10-12 12:30:10"),
                    *("1957-10-01 00:00:00", "2026-10-12 00:00:00", "1957-01-01 00:00:00", "2005-09-01 00:00:00"),
                ),
                [-123.43933333333334, 48.43197222222222],
            ),
            feature(
                2219,
                "CARWAY",
                "AB",
                (485959010, -1132234000),
                "MST",
                "1354.00",
                (
                    *("1914-01-01 00:00:00", "2011-11-30 00:00:00", None, None),
                    *("1914-08-01 00:00:00", "2011-11-30 00:00:00", "1914-01-01 00:00:00", "2007-11-01 00:00:00"),
                ),
                [-113.37611111111111, 48.999725],
            ),
            feature(
                7559,
                "ALERT A",
                "NU",
                (823100000, -621700000),
                "AST",
                "30.50",
                (
                    *("1988-04-01 05:00:00", "2026-10-13 12:30:10", "1988-04-01 05:00:00", "2026-10-13 12:30:10"),
                    *(None, None, None, None),
                ),
                [-62.28333333333333, 82.51666666666667],
                monthly_summary="N",
            ),
            feature(
                10904,
                "GLADMAN POINT",
                "NU",
                (684049000, -974841000),
                "CST",
                None,
                (
                    *("1992-12-22 00:00:00", "1993-04-27 11:00:00", "1992-12-31 18:00:00", "1993-04-27 11:00:00"),
                    *("1992-12-22 00:00:00", "1993-03-15 00:00:00", None, None),
                ),
                [-97.81138888888889, 68.68027777777777],
            ),
        ],
    }
    _serve(monkeypatch, eccc_api, {"climate-stations/items": json.dumps(catalogue).encode("utf8")})
    return _stations(EcccObservationRequest, (resolution, "data"))


def _eccc_hourly(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    return _eccc(monkeypatch, "hourly")


def _eccc_daily(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    return _eccc(monkeypatch, "daily")


def _eccc_monthly(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    return _eccc(monkeypatch, "monthly")


FMI_ANTARCTICA = Accepted(
    "coordinates_outside_country",
    "Antarktis Aboa is the Finnish research station in Antarctica",
    where=lambda row: row["station_id"] == "112275",
)


def _fmi(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    # `fmi::ef::stations` (2026-10-15), 439 facilities of which these four, cut down to the elements the reader reads
    # (the `gml:id` shortened to the station id); the position is `lat lon`, a station still in service ends in
    # `indeterminatePosition="now"`, and Helsinki Vuosaaren satama has no region
    def facility(station_id: str, name: str, region: str | None, position: str, begin: str) -> str:
        region_name = (
            f'<gml:name codeSpace="http://xml.fmi.fi/namespace/location/region">{region}</gml:name>' if region else ""
        )
        return f"""
  <wfs:member>
    <ef:EnvironmentalMonitoringFacility gml:id="WFS-{station_id}">
      <gml:identifier codeSpace="http://xml.fmi.fi/namespace/stationcode/fmisid">{station_id}</gml:identifier>
      <gml:name codeSpace="http://xml.fmi.fi/namespace/locationcode/name">{name}</gml:name>
      {region_name}
      <ef:representativePoint>
        <gml:Point gml:id="point-1" axisLabels="Lat Long" srsName="http://www.opengis.net/def/crs/EPSG/0/4258">
          <gml:pos>{position}</gml:pos>
        </gml:Point>
      </ef:representativePoint>
      <ef:operationalActivityPeriod>
        <ef:OperationalActivityPeriod gml:id="oap-1-1">
          <ef:activityTime>
            <gml:TimePeriod gml:id="oap-tp-1-1">
              <gml:beginPosition>{begin}</gml:beginPosition>
              <gml:endPosition indeterminatePosition="now"/>
            </gml:TimePeriod>
          </ef:activityTime>
        </ef:OperationalActivityPeriod>
      </ef:operationalActivityPeriod>
    </ef:EnvironmentalMonitoringFacility>
  </wfs:member>"""

    members = "".join(
        [
            facility("100539", "Kemi Ajos", "Kemi", "65.673370 24.515260", "1922-06-14T00:00:00Z"),
            facility("100540", "Raahe Lapaluoto", "Raahe", "64.666300 24.407080", "1922-06-15T00:00:00Z"),
            facility("104089", "Helsinki Vuosaaren satama", None, "60.221730 25.179811", "2016-01-01T00:00:00Z"),
            facility("112275", "Antarktis Aboa", "AQ", "-73.050000 -13.383330", "2003-11-25T00:00:00Z"),
        ]
    )
    catalogue = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<wfs:FeatureCollection xmlns:wfs="http://www.opengis.net/wfs/2.0" '
        'xmlns:xlink="http://www.w3.org/1999/xlink" xmlns:gml="http://www.opengis.net/gml/3.2" '
        'xmlns:ef="http://inspire.ec.europa.eu/schemas/ef/4.0">'
        f"{members}\n</wfs:FeatureCollection>"
    )
    _serve(monkeypatch, fmi_api, {"ef%3A%3Astations": catalogue.encode("utf8")})
    return _stations(FmiObservationRequest, ("hourly", "data"))


def _meteoswiss(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    # `ogd-smn_meta_stations.csv` (2026-10-15), four of its 159 rows as published: semicolon-separated, windows-1252,
    # CRLF, dates as `DD.MM.YYYY`, the barometer height empty for Oberageri
    header = (
        "station_abbr;station_name;station_canton;station_wigos_id;station_type_de;station_type_fr;station_type_it;"
        "station_type_en;station_dataowner;station_data_since;station_height_masl;station_height_barometer_masl;"
        "station_coordinates_lv95_east;station_coordinates_lv95_north;station_coordinates_wgs84_lat;"
        "station_coordinates_wgs84_lon;station_exposition_de;station_exposition_fr;station_exposition_it;"
        "station_exposition_en;station_url_de;station_url_fr;station_url_it;station_url_en"
    )
    types = (
        "Automatische Wetterstationen - Messwerte;Stations météorologiques automatiques - Valeurs mesurées;"
        "Stazioni meteorologiche automatiche - Valori misurati;Automatic weather stations - Measurement values"
    )
    pages = (
        "https://www.meteoschweiz.admin.ch/service-und-publikationen/applikationen/messwerte-und-messnetze.html",
        "https://www.meteosuisse.admin.ch/services-et-publications/applications/valeurs-mesurees-et-reseaux-de-mesure.html",
        "https://www.meteosvizzera.admin.ch/servizi-e-pubblicazioni/applicazioni/valori-attuali-e-reti-di-misura.html",
        "https://www.meteoswiss.admin.ch/services-and-publications/applications/measurement-values-and-measuring-networks.html",
    )

    def row(*fields: str) -> str:
        abbr, name, canton, wigos, owner, since, height, barometer, east, north, lat, lon, *exposition = fields
        urls = ";".join(f"{page}#param=messnetz-automatisch&station={abbr}" for page in pages)
        return (
            f"{abbr};{name};{canton};0-20000-0-{wigos};{types};{owner};{since};{height};{barometer};{east};{north};"
            f"{lat};{lon};{';'.join(exposition)};{urls}"
        )

    rows = [
        row(
            *("ABO", "Adelboden", "BE", "06735", "MeteoSchweiz, SLF", "01.01.1901", "1321.0", "1326.0"),
            *("2609372.0", "1148939.0", "46.491703", "7.560703"),
            *("Südosthang", "Versant sud-est", "Versante sud-orientale", "south-eastern oriented slope"),
        ),
        row(
            *("AEG", "Oberägeri", "ZG", "06676", "MeteoSchweiz", "01.02.1993", "724.0", ""),
            *("2688729.0", "1220956.0", "47.133636", "8.608206", "Ebene", "Plaine", "Pianura", "plain"),
        ),
        row(
            *("GSB", "Col du Grand St-Bernard", "VS", "06717", "MeteoSchweiz", "01.01.1818", "2472.0", "2488.0"),
            *("2579191.0", "1079754.0", "45.869092", "7.170683", "Passlage", "Col", "Passo", "pass"),
        ),
        row(
            *("SMA", "Zürich / Fluntern", "ZH", "06660", "MeteoSchweiz", "01.01.1864", "604.0", "605.0"),
            *("2685223.0", "1248410.0", "47.381003", "8.567194"),
            *("Südhang", "Versant sud", "Versante meridionale", "southern oriented slope"),
        ),
    ]
    catalogue = "\r\n".join([header, *rows]) + "\r\n"
    _serve(monkeypatch, meteoswiss_api, {"ogd-smn_meta_stations": catalogue.encode("windows-1252")})
    return _stations(MeteoswissObservationRequest, ("daily", "data"))


def _rmi(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    # `aws:aws_station` (2026-10-15), four of the 14 stations: a position is `[lon, lat]`, a station in service has no
    # `date_end`, and the one of De Haan has a code of eight digits and a WIGOS id of another scheme
    def feature(
        code: int, name: str, lon: float, lat: float, begin: str, altitude: float, wigos: str
    ) -> dict[str, Any]:
        return {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {
                "code": code,
                "name": name,
                "date_begin": begin,
                "date_end": None,
                "altitude": altitude,
                "wigos_id": wigos,
            },
        }

    catalogue = {
        "type": "FeatureCollection",
        "features": [
            feature(6414, "BEITEM", 3.122, 50.904, "2003-07-26T00:10:00Z", 24.8, "0-20000-0-06414"),
            feature(6447, "UCCLE", 4.358, 50.797, "2003-12-01T00:00:00Z", 100.6, "0-20000-0-06447"),
            feature(6438, "STABROEK", 4.364, 51.325, "2012-08-05T00:00:00Z", 4, "0-20000-0-06438"),
            feature(10101002, "DE HAAN", 3.074, 51.28, "2025-03-06T00:00:00Z", 3.66, "0-056-101-01002"),
        ],
    }
    _serve(monkeypatch, rmi_api, {"aws_station": json.dumps(catalogue).encode("utf8")})
    return _stations(RmiObservationRequest, ("10_minutes", "data"))


def _smhi(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    # `parameter/1.json` (2026-10-15), trimmed to the fields the reader reads: `from` and `to` are milliseconds since
    # the epoch (before 1970 negative), and a station in service has `to` of the last update; Kiruna is listed
    # with a height of 0.0, where the airport of the same town is at 459 m
    def station(key: int, name: str, height: float, lat: float, lon: float, start: int, end: int) -> dict[str, Any]:
        return {
            "key": str(key),
            "id": key,
            "name": name,
            "height": height,
            "latitude": lat,
            "longitude": lon,
            "active": end > 1_700_000_000_000,
            "from": start,
            "to": end,
            "updated": end,
        }

    catalogue = {
        "station": [
            station(1, "Akalla", 23.0, 59.5, 17.8, 1356998400000, 1367366399000),
            station(188800, "Abisko", 393.38, 68.3538, 18.8166, -1798761600000, 1580515199000),
            station(85600, "Adelsnäs", 97.0, 58.1998, 15.9802, -1530662400000, -283975200000),
            station(97400, "Stockholm-Arlanda Flygplats", 42.0, 59.6269, 17.9545, 1201824000000, 1792026000000),
            station(25080, "Kiruna", 0.0, 67.8565, 20.2937, 1765443900000, 1792026000000),
        ]
    }
    body = json.dumps(catalogue).encode("utf8")

    def download_files(*, urls: list[str], **_: object) -> list[File]:
        return [File(url=url, content=BytesIO(body), status=200) for url in urls]

    monkeypatch.setattr(smhi_api, "download_files", download_files)
    return _stations(SmhiObservationRequest, ("hourly", "data"))


def _hubeau(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    # the referential of stations and the one of sites (2026-10-15), of which these are the stations of the Seine at
    # Paris (two stations of one site, with one position), the Garonne at La Reole, one without an altitude and a
    # system of altitude, and Goyaves in Guadeloupe (overseas); the observations, which a station's resolution is
    # measured from, are made up: one every five minutes for each
    def station(
        site: str,
        station_id: str,
        name: str,
        position: tuple[float, float],
        zero: float | None,
        system: int | None,
        opened: str,
        department: str,
    ) -> dict[str, Any]:
        return {
            "code_site": site,
            "code_station": station_id,
            "libelle_station": name,
            "longitude_station": position[0],
            "latitude_station": position[1],
            "altitude_ref_alti_station": zero,
            "code_systeme_alti_site": system,
            "date_ouverture_station": f"{opened}T00:00:00Z",
            "date_fermeture_station": None,
            "libelle_departement": department,
        }

    stations = [
        station(
            *("F7000001", "F700000102", "La Seine à Paris - Austerlitz - station limni - secours CT"),
            *((2.365510635, 48.84468962), 25.92, 3, "1990-01-01", "PARIS"),
        ),
        station(
            *("F7000001", "F700000103", "La Seine à Paris - Austerlitz [>2006] - Station débitmétrique"),
            *((2.365510635, 48.84468962), 25.92, 3, "2006-01-26", "PARIS"),
        ),
        station(
            *("O9190010", "O919001001", "La Garonne à la Réole"),
            *((-0.034612117, 44.579311754), 6.251, 1, "1990-01-01", "GIRONDE"),
        ),
        station(
            *("O9195617", "O919561701", "[La Bassanne] à Savignac"),
            *((-0.105816239, 44.520636408), None, None, "1998-05-14", "GIRONDE"),
        ),
        station(
            *("10110001", "1011000101", "La Grande Rivière à Goyaves à Petit-Bourg [Barbotteau]"),
            *((-61.658989597, 16.189402471), 0.0139, 0, "2012-11-11", "GUADELOUPE"),
        ),
    ]
    sites = [
        {"code_site": "F7000001", "altitude_site": 26.0},
        {"code_site": "O9190010", "altitude_site": 15.0},
        {"code_site": "O9195617", "altitude_site": 34.0},
        {"code_site": "10110001", "altitude_site": 133.81},
    ]
    observations = [
        {"code_station": row["code_station"], "date_obs": f"2026-10-15T01:{minute:02d}:00Z"}
        for row in stations
        for minute in range(0, 30, 5)
    ]
    bodies = {
        "referentiel/stations": json.dumps({"data": stations}).encode("utf8"),
        "referentiel/sites": json.dumps({"data": sites}).encode("utf8"),
        "observations_tr": json.dumps({"data": observations}).encode("utf8"),
    }
    _serve(monkeypatch, hubeau_api, bodies)
    return _stations(HubeauRequest, ("5_minutes", "data"))


WSV_NO_POSITION = Accepted(
    "coordinates_missing",
    "PEGELONLINE publishes no position for these gauges, among them those of the Austrian Danube",
)
WSV_TIEL = Accepted(
    "coordinates_outside_country",
    "PEGELONLINE lists TIEL, a gauge on the Waal in the Netherlands",
    where=lambda row: row["station_id"] == "123456781",
)


def _wsv(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    # `stations.json?includeTimeseries=true&includeCharacteristicValues=true` (2026-10-15), trimmed to what the reader
    # reads: CELLE as it is published, two of the 57 gauges without a position (DORDRECHT, and KORNEUBURG on the
    # Austrian Danube), and TIEL, a gauge in the Netherlands. A gauge is listed under the resolution of the
    # `equidistance` of its water level: 15 minutes for CELLE and KORNEUBURG, 10 for the others
    def gauge(number: str, name: str, km: float, water: str, position: dict[str, float], extra: dict[str, Any]) -> dict:
        return {
            "number": number,
            "shortname": name,
            "km": km,
            **position,
            "water": {"shortname": water},
            "timeseries": [{"shortname": "W", **extra}],
        }

    values = [("M_I", 300.0), ("HHW", 528.0), ("M_II", 340.0), ("NNW", 50.0), ("MNW", 117.0), ("MW", 192.0)]
    values += [("HSW", 310.0), ("MHW", 412.0), ("M_III", 400.0)]
    celle = {
        "equidistance": 15,
        "gaugeZero": {"value": 31.82, "unit": "m. ü. NN"},
        "characteristicValues": [{"shortname": key, "value": value} for key, value in values],
    }
    korneuburg = {
        "equidistance": 15,
        "gaugeZero": {"value": 159.87, "unit": "m ü. A."},
        "characteristicValues": [{"shortname": "RNW", "value": 191.0}, {"shortname": "HSW", "value": 549.0}],
    }
    bare = {"equidistance": 10, "gaugeZero": None, "characteristicValues": []}
    catalogue = [
        gauge("48300105", "CELLE", 1.74, "ALLER", {"latitude": 52.622706, "longitude": 10.062164}, celle),
        gauge("42013", "KORNEUBURG", 1941.5, "DONAU", {}, korneuburg),
        gauge("123456785", "DORDRECHT", 975.0, "ALTE_MAAS", {}, bare),
        gauge("123456781", "TIEL", 913.5, "WAAL", {"latitude": 51.900532, "longitude": 5.455684}, bare),
    ]
    _serve(monkeypatch, wsv_api, {"stations.json": json.dumps(catalogue).encode("utf8")})
    return _stations(WsvPegelRequest, ("10_minutes", "data"), ("15_minutes", "data"))


def _nws(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    # `METARTable.txt` of MADIS (2026-10-15), tab-separated with the columns padded: the world's METAR stations, of
    # which the reader keeps those of `US` and the three of the Virgin Islands and Hawaii it files under a state
    # code (PHBK, TIST, TISX); a missing elevation is 9999
    catalogue = (
        "0000072565\tKDEN\t39.83\t-104.66\t 1655\tDENVER/DENVER INTER, CO\tUS\tMTR\n"
        "0000074486\tKJFK\t40.65\t -73.78\t    7\tNEW YORK/JF KENN, NY\tUS\tMTR\n"
        "0000070273\tPANC\t61.17\t-150.02\t   40\tANCHORAGE INTL ARPT, AK\tUS\tMTR\n"
        "0000000000\tK37W\t35.38\t -78.73\t 9999\tERWIN-HARNETT, NC   \tUS\tMTR\n"
        "0000091162\tPHBK\t22.07\t-159.78\t    5\tBARKING SANDS ARPT, HI\tHI\tMTR\n"
        "0000078543\tTIST\t18.33\t -64.97\t   67\tST. THOMAS/KING, VI \tVI\tMTR\n"
        "0000078547\tTISX\t17.70\t -64.81\t   17\tST.CROIX/HAMILTN, VI\tVI\tMTR\n"
        "0000010147\tEDDH\t53.63\t  10.00\t   16\tHAMBURG-FUHLSBUETTEL\tDL\tMTR\n"
    )
    _serve(monkeypatch, nws_api, {"METARTable": catalogue.encode("latin-1")})
    return _stations(NwsObservationRequest, ("hourly", "data"))


# the station id of `knmi/observation` is the WMO number at the end of the WSI, the height keeps its sign
KNMI_EXPECTED: dict[str, dict[str, Any]] = {
    "06209": {"wigos_id": "0-20000-0-06209", "name": "IJmond", "latitude": 52.465, "longitude": 4.518},
    "06260": {"wigos_id": "0-20000-0-06260", "name": "De Bilt", "latitude": 52.1, "longitude": 5.18, "elevation": 1.9},
    "06344": {"name": "Rotterdam Airport", "elevation": -4.3},
    "06392": {"name": "Horst", "latitude": 51.486836, "longitude": 6.056189},
}


def _knmi(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    # the list is the station axis of the latest NetCDF file of a resolution, which needs the API key, so the file is
    # written with h5netcdf in the shape the reader reads (stations keyed by WSI, `stationname`, `lat`, `lon`,
    # `height`) and served in place of the download. The rows are those of the key-less station table that
    # `daggegevens.knmi.nl` prints above its data (2026-10-15, `stns=ALL`: the first two stations, De Bilt, Rotterdam
    # Airport at a height of -4.3 m, and Horst with a position of six decimals): the legacy
    # number 260 of De Bilt is the 06260 of its WSI. The names and positions of the NetCDF files themselves could not
    # be read without a key
    import pytest  # noqa: PLC0415

    h5netcdf = pytest.importorskip("h5netcdf", reason="h5netcdf not installed")
    h5py = pytest.importorskip("h5py", reason="h5py not installed")
    stations = [
        ("0-20000-0-06209", "IJmond", 52.465, 4.518, 0.0),
        ("0-20000-0-06210", "VALKENBURG VK", 52.171, 4.430, -0.2),
        ("0-20000-0-06260", "De Bilt", 52.100, 5.180, 1.9),
        ("0-20000-0-06344", "Rotterdam Airport", 51.962, 4.447, -4.3),
        ("0-20000-0-06392", "Horst", 51.486836, 6.056189, 21.88),
    ]
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "stations.nc"
        with h5netcdf.File(path, "w") as file:
            file.dimensions = {"station": len(stations)}
            string_dtype = h5py.string_dtype()
            station = file.create_variable("station", ("station",), dtype=string_dtype)
            station[:] = [wsi for wsi, *_ in stations]
            stationname = file.create_variable("stationname", ("station",), dtype=string_dtype)
            stationname[:] = [name for _, name, *_ in stations]
            for column, index in {"lat": 2, "lon": 3, "height": 4}.items():
                variable = file.create_variable(column, ("station",), dtype="f8")
                variable[:] = [row[index] for row in stations]
        payload = path.read_bytes()
    monkeypatch.setattr(knmi_api, "_latest_filename", lambda *_args: "latest.nc")
    monkeypatch.setattr(knmi_api, "_fetch_netcdf", lambda *_args: payload)
    request = KnmiObservationRequest(
        parameters=[("daily", "data")], settings=Settings(cache_disable=True, auth={"knmi": "stub"})
    )
    return request.all().df


# the region of `meteofrance/observation` is the département's code as the station id writes it: the registry's `9` of
# the Ariège is `09`, an overseas one has three digits, and Corsica's two départements, 2A and 2B, are both `20`
METEOFRANCE_EXPECTED: dict[str, dict[str, Any]] = {
    "29293001": {"region": "29"},
    "09224001": {"region": "09"},
    "20023400": {"region": "20"},
    "97228006": {"region": "972"},
    "98719002": {"region": "987"},
}


def _meteofrance_observation(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    # the station registry of data.gouv.fr (2026-10-15), 14,729 stations of which these: many have no start date,
    # a closed one has an end, and the overseas departments have codes of three digits. Its `department_id` has no
    # leading zero (`9`), and the 351 stations of Corsica, 2A and 2B, all have `20`
    catalogue = (
        "id,name,long_name,named_place,station_type,basin,lon,lat,alt,start_date,end_date,is_open,is_public,"
        "department_id,is_daily,is_hourly,is_minutely\n"
        "29293001,TREGUNC,TREGUNC,KERLEOGUY,1,J451,-3.868833,47.841333,25,2003-12-01,,true,true,29,true,true,true\n"
        "09224001,PAILHES-SPC,,,5,,1.443,43.102167,287,,,true,true,9,true,true,false\n"
        "20023400,ASCO-STAGNU,ASCO (ASCO-STAGNU),Stagnu,4,Y710,8.922667,42.402667,1434,1983-12-12,,true,true,20,"
        "true,true,false\n"
        "72061001,LA CHAPELLE D A,LA CHAPELLE-D'ALIGNE (LA CHAPELLE D A),LES GRINGUENIERES,4,M153,-0.216667,"
        "47.716667,50,1951-04-01,1993-09-30,true,true,72,true,false,false\n"
        "97228006,STE MARIE PEROU,SAINTE-MARIE (STE MARIE PEROU),PEROU DDST,2,NR,-61.024167,14.761167,200,"
        "1993-02-20,,true,true,972,true,true,true\n"
        "98719002,MANGAREVA TAKU,GAMBIER (MANGAREVA TAKU),TAKU,4,NR,-134.96,-23.098333,134,1966-07-01,1968-05-31,"
        "false,true,987,true,true,false\n"
    )
    _serve(monkeypatch, meteofrance_api, {"5ec141e4-3650-4365-82b1-db459efe690c": catalogue.encode("utf8")})
    return _stations(MeteoFranceObservationRequest, ("daily", "core"))


def _meteofrance_synop(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    # `postes_synop.geojson` (2026-10-15), 187 stations of which these; a position is `[lon, lat]`, and the list
    # reaches the French territories in the Indian Ocean and Antarctica
    def feature(station_id: str, name: str, altitude: int, opened: str, lon: float, lat: float) -> dict[str, Any]:
        return {
            "type": "Feature",
            "properties": {"Id": station_id, "Nom": name, "Altitude": altitude, "Date_ouverture": opened},
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
        }

    catalogue = {
        "type": "FeatureCollection",
        "features": [
            feature("07002", "BOULOGNE-SEM", 73, "1947-01-01", 1.599667, 50.7325),
            feature("07149", "ORLY", 86, "1921-03-01", 2.397, 48.718),
            feature("61968", "GLORIEUSES", 3, "1960-01-01", 47.289667, -11.582667),
            feature("78897", "LE RAIZET AERO", 11, "1950-01-01", -61.516333, 16.264),
            feature("89642", "DUMONT D'URVILLE", 43, "1956-01-18", 140.001, -66.663167),
        ],
    }
    _serve(monkeypatch, meteofrance_synop_api, {"postes_synop": json.dumps(catalogue).encode("utf8")})
    return _stations(MeteoFranceSynopRequest, ("subdaily", "data"))


STUBS = [
    Stub("aemet/observation daily/data", _aemet),
    Stub("dmi/observation daily/data", _dmi),
    Stub("fmi/observation hourly/data", _fmi, (FMI_ANTARCTICA,)),
    Stub("meteoswiss/observation daily/data", _meteoswiss),
    Stub("rmi/observation 10_minutes/data", _rmi),
    Stub("smhi/observation hourly/data", _smhi),
    Stub("eaufrance/hubeau 5_minutes/data", _hubeau),
    Stub("wsv/pegel 10_minutes+15_minutes/data", _wsv, (WSV_NO_POSITION, WSV_TIEL)),
    Stub("nws/observation hourly/data", _nws),
    Stub("meteofrance/observation daily/core", _meteofrance_observation, expected=METEOFRANCE_EXPECTED),
    Stub("meteofrance/synop subdaily/data", _meteofrance_synop),
    Stub(
        "eccc/observation hourly/data",
        _eccc_hourly,
        # the hourly collection of Esquimalt Harbour starts 1994-02-01 00:00 PST, the station in 1957
        expected={
            "52": {"start_timestamp": dt.datetime(1994, 2, 1, 8, tzinfo=dt.UTC)},
            "7559": {"start_timestamp": dt.datetime(1988, 4, 1, 9, tzinfo=dt.UTC)},
        },
    ),
    Stub(
        "eccc/observation daily/data",
        _eccc_daily,
        expected={"52": {"start_timestamp": dt.datetime(1957, 10, 1, tzinfo=dt.UTC)}},
    ),
    Stub("eccc/observation monthly/data", _eccc_monthly),
    Stub("dwd/mosmix hourly/small", _dwd_mosmix, (DWD_NAMES,)),
    Stub("dwd/poi hourly/data", _dwd_poi, (DWD_NAMES,)),
    Stub("dwd/dmo hourly/icon", _dwd_dmo, expected=DMO_EXPECTED),
    Stub("dwd/observation daily/climate_summary", _dwd_observation, expected=OBSERVATION_EXPECTED),
    Stub("dwd/derived hourly/radiation_global", _dwd_derived),
    Stub("dwd/phenology annual/annual_apple", _dwd_phenology),
    Stub("ipma/observation hourly/data", _ipma),
    Stub("lhmt/observation hourly/data", _lhmt),
    Stub("knmi/observation daily/data", _knmi, expected=KNMI_EXPECTED),
    Stub("metno/frost hourly/data", _metno_frost),
    Stub("metoffice/observation daily/rain", _metoffice),
    Stub("noaa/ghcn hourly/data", _ghcn_hourly, (GHCN_NO_POSITION, GHCN_NAMES)),
    Stub(
        "noaa/ghcn daily/data",
        _ghcn_daily,
        (GHCN_NAMES,),
    ),
    Stub("geosphere/observation daily/data", _geosphere),
    Stub(
        "chmi/observation daily/data",
        _chmi,
        (CHMI_NAME,),
    ),
    Stub("dwd/road 15_minutes/data", _dwd_road),
    Stub("dwd/swsmos hourly/data", _dwd_swsmos),
    Stub("ea/hydrology 15_minutes/data", _ea_hydrology, (EA_NO_POSITION,)),
    Stub("imgw/hydrology daily/hydrology", _imgw_hydrology),
    Stub("imgw/meteorology daily/climate", _imgw_meteorology),
]
