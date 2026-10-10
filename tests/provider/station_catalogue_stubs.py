# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Stubs of the station catalogues, for `test_station_catalogue_stubs.py` to hold to the rules (GH-2616).

A stub is the catalogue a provider's own reader turns into stations, made from a few rows of the real list: the first
stations of it and the ones that showed a defect, copied as they are published, with the source's own padding,
encoding and decimal separator. Standing in for the download, it runs the provider's own reader (`_all()` and the
frame handling of `all()`), so a reader that loses a sign or drops a column shows here without the network.

To hold another provider to the rules, add a stub to `STUBS`: serve the rows through `_serve`, call the request, and
give the rows a fault the source really has if there is one, so that the rule is seen to find it.
"""

from __future__ import annotations

import bz2
import datetime as dt
import json
from dataclasses import dataclass, field
from io import BytesIO
from typing import TYPE_CHECKING, Any

import polars as pl

from tests.provider.station_catalogue import COUNTRY_BBOX, Accepted
from wetterdienst import Settings
from wetterdienst.provider.chmi.observation import ChmiObservationRequest
from wetterdienst.provider.chmi.observation import api as chmi_api
from wetterdienst.provider.dwd import catalogue as dwd_catalogue
from wetterdienst.provider.dwd.mosmix import DwdMosmixRequest
from wetterdienst.provider.dwd.road import DwdRoadRequest
from wetterdienst.provider.dwd.road import api as road_api
from wetterdienst.provider.dwd.swsmos import DwdSwsmosRequest
from wetterdienst.provider.dwd.swsmos import api as swsmos_api
from wetterdienst.provider.geosphere.observation import GeosphereObservationRequest
from wetterdienst.provider.geosphere.observation import api as geosphere_api
from wetterdienst.provider.imgw.hydrology import ImgwHydrologyRequest
from wetterdienst.provider.imgw.hydrology import api as imgw_hydrology_api
from wetterdienst.provider.imgw.meteorology import ImgwMeteorologyRequest
from wetterdienst.provider.imgw.meteorology import api as imgw_meteorology_api
from wetterdienst.provider.ipma.observation import IpmaObservationRequest
from wetterdienst.provider.ipma.observation import api as ipma_api
from wetterdienst.provider.lhmt.observation import LhmtObservationRequest
from wetterdienst.provider.lhmt.observation import api as lhmt_api
from wetterdienst.provider.noaa.ghcn import NoaaGhcnRequest
from wetterdienst.provider.noaa.ghcn import api as ghcn_api
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
    # the time the dates of the stations are held against; a stub whose rows end around the present fixes it, so that
    # it does not change its verdict with the calendar
    now: dt.datetime | None = None

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


def _stations(request_class: type, *parameters: tuple[str, str]) -> pl.DataFrame:
    request = request_class(parameters=list(parameters), settings=Settings(cache_disable=True))
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
    inventory = (
        "BR000269000  -2.9830  -69.5830 PRCP 1979 1996\n"
        "FRE00104116  43.1881    0.0000 TMAX 1946 2026\n"
        "GM000010147  53.6350    9.9900 TMAX 1891 2026\n"
        "GME00102292  51.4358   12.2414 TMAX 1934 2026\n"
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


def _dwd_mosmix(monkeypatch: pytest.MonkeyPatch) -> pl.DataFrame:
    # positions are degrees and minutes (`44.50` is 44°50'), west and south signed
    catalogue = (
        "ID    ICAO NAME                 LAT    LON     ELEV\n"
        "----- ---- -------------------- -----  ------- -----\n"
        "01001 ENJA JAN MAYEN             70.56   -8.40    10\n"
        "03772 EGLL LONDON                51.29   -0.27    24\n"
        "07510 LFBD BORDEAUX              44.50   -0.42    49\n"
        "10147 EDDH HAMBURG-FU.           53.38   10.00    16\n"
        "23205 ---- NAR?JAN-MAR           67.38   53.01   139\n"
        "72520 KPIT PITTSBURGH INT.       40.30  -80.13   367\n"
    )
    _serve(monkeypatch, dwd_catalogue, {"mosmix_stationskatalog": catalogue.encode("latin-1")})
    return _stations(DwdMosmixRequest, ("hourly", "small"))


def question_mark_in_the_name(row: dict[str, Any]) -> bool:
    """Say whether a name is damaged by a question mark and by nothing worse."""
    return "?" in row["name"] and not any(damage in row["name"] for damage in ("\ufffd", "Ã", "Â", "â€"))


# a source that writes a character it cannot encode as a question mark leaves a name such as NAR?JAN-MAR or IPIRANGA(?)
QUESTION_MARK = "the source writes a character it could not encode as a question mark"
GHCN_NO_POSITION = Accepted(
    "coordinates_missing",
    "the list gives the BOGUS and the NAME AND LOC UNKN placeholders 0, 0 and the two historic Russian stations "
    "latitudes of 135 and 104; none has a position (GH-2380), and a station without one is picked by no search",
    where=lambda row: row["name"].startswith(("BOGUS ", "NAME AND LOC")) or row["station_id"].startswith("RUU71-"),
)
GHCN_NAMES = Accepted(
    "name_encoding", f"the list names stations IPIRANGA(?) and alike: {QUESTION_MARK}", question_mark_in_the_name
)
GHCN_DAILY_END = Accepted(
    "date_in_the_future",
    "the end of a station that reports this year is 31 December of this year (GH-2643)",
    where=lambda row: row["end_timestamp"].year == dt.datetime.now(dt.UTC).year,
)

STUBS = [
    Stub(
        "dwd/mosmix hourly/small",
        _dwd_mosmix,
        (Accepted("name_encoding", f"the station catalogue of DWD: {QUESTION_MARK}", question_mark_in_the_name),),
    ),
    Stub("ipma/observation hourly/data", _ipma),
    Stub("lhmt/observation hourly/data", _lhmt),
    Stub("noaa/ghcn hourly/data", _ghcn_hourly, (GHCN_NO_POSITION, GHCN_NAMES)),
    Stub(
        "noaa/ghcn daily/data",
        _ghcn_daily,
        (
            # the end the stub's rows get is 31 December 2026, which is in the future only before then
            Accepted(GHCN_DAILY_END.rule, GHCN_DAILY_END.reason, where=lambda row: row["end_timestamp"].year == 2026),
            GHCN_NAMES,
        ),
        now=dt.datetime(2026, 10, 10, tzinfo=dt.UTC),
    ),
    Stub("geosphere/observation daily/data", _geosphere),
    Stub(
        "chmi/observation daily/data",
        _chmi,
        (
            Accepted(
                "name_encoding",
                "the list names the station `Nová Lhota  ?` in its last period (1976 to 1980), the source's own value",
                where=lambda row: row["station_id"] == "0-203-0-41302035001",
            ),
        ),
    ),
    Stub("dwd/road 15_minutes/data", _dwd_road),
    Stub("dwd/swsmos hourly/data", _dwd_swsmos),
    Stub("imgw/hydrology daily/hydrology", _imgw_hydrology),
    Stub("imgw/meteorology daily/climate", _imgw_meteorology),
]
