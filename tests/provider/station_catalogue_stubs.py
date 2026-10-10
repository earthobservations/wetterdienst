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
from dataclasses import dataclass, field
from io import BytesIO
from typing import TYPE_CHECKING, Any

import polars as pl

from tests.provider.station_catalogue import COUNTRY_BBOX, Accepted
from wetterdienst import Settings
from wetterdienst.provider.dwd.road import DwdRoadRequest
from wetterdienst.provider.dwd.road import api as road_api
from wetterdienst.provider.dwd.swsmos import DwdSwsmosRequest
from wetterdienst.provider.dwd.swsmos import api as swsmos_api
from wetterdienst.provider.imgw.hydrology import ImgwHydrologyRequest
from wetterdienst.provider.imgw.hydrology import api as imgw_hydrology_api
from wetterdienst.provider.imgw.meteorology import ImgwMeteorologyRequest
from wetterdienst.provider.imgw.meteorology import api as imgw_meteorology_api
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


STUBS = [
    Stub("dwd/road 15_minutes/data", _dwd_road),
    Stub("dwd/swsmos hourly/data", _dwd_swsmos),
    Stub("imgw/hydrology daily/hydrology", _imgw_hydrology),
    Stub("imgw/meteorology daily/climate", _imgw_meteorology),
]
