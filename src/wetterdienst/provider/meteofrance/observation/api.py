# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Météo-France observation data provider ("Données climatologiques de base")."""

from __future__ import annotations

import gzip
import json
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from typing import IO, TYPE_CHECKING, cast
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.meteofrance.observation.metadata import MeteoFranceObservationMetadata
from wetterdienst.util.network import download_file, download_files

if TYPE_CHECKING:
    from collections.abc import Iterable

    from wetterdienst.model.metadata import DatasetModel, ParameterModel
    from wetterdienst.settings import Settings
    from wetterdienst.util.network import File

log = logging.getLogger(__name__)

# "Données climatologiques de base" (daily / monthly), sharded per French department.
# data.gouv.fr dataset ids. Used to discover the exact current resource URLs at request time
# instead of hardcoding the period-bucket labels (e.g. "2025-2026"), which Météo-France shifts
# forward over time as new data becomes available.
_CLIMATE_DATASET_IDS = {
    "daily": "6569b51ae64326786e4e8e1a",
    "monthly": "6569b3d7d193b4daf2b43edc",
    "hourly": "6569b4473bedf2e7abad3b72",
    "6_minutes": "6569ad61106d1679c93cdf77",
}
_CLIMATE_RESOURCE_PREFIXES = {
    "daily": "QUOT_departement_{department}_periode_",
    "monthly": "MENS_departement_{department}_periode_",
    "hourly": "HOR_departement_{department}_periode_",
    "6_minutes": "MIN_departement_{department}_periode_",
}
# dataset name -> resource title suffix used to pick the right file group for a department;
# only "daily" splits into multiple file groups at the source, hence the empty suffixes
# elsewhere (hourly's "core"/"others" split only exists at the wetterdienst level, both read
# from the same unsplit source file)
_CLIMATE_RESOURCE_SUFFIXES = {
    "daily": {"core": "_RR-T-Vent", "others": "_autres-parametres"},
    "monthly": {"data": ""},
    "hourly": {"core": "", "others": ""},
    "6_minutes": {"data": ""},
}
_CLIMATE_DATE_COLUMNS = {"daily": "AAAAMMJJ", "monthly": "AAAAMM", "hourly": "AAAAMMJJHH", "6_minutes": "AAAAMMJJHHMN"}
_CLIMATE_DATE_FORMATS = {"daily": "%Y%m%d", "monthly": "%Y%m", "hourly": "%Y%m%d%H", "6_minutes": "%Y%m%d%H%M"}

_QUOT_RR_T_VENT_SCHEMA = {
    "NUM_POSTE": pl.String,
    "NOM_USUEL": pl.String,
    "LAT": pl.String,
    "LON": pl.String,
    "ALTI": pl.String,
    "AAAAMMJJ": pl.String,
    "RR": pl.String,
    "QRR": pl.String,
    "TN": pl.String,
    "QTN": pl.String,
    "HTN": pl.String,
    "QHTN": pl.String,
    "TX": pl.String,
    "QTX": pl.String,
    "HTX": pl.String,
    "QHTX": pl.String,
    "TM": pl.String,
    "QTM": pl.String,
    "TNTXM": pl.String,
    "QTNTXM": pl.String,
    "TAMPLI": pl.String,
    "QTAMPLI": pl.String,
    "TNSOL": pl.String,
    "QTNSOL": pl.String,
    "TN50": pl.String,
    "QTN50": pl.String,
    "DG": pl.String,
    "QDG": pl.String,
    "FFM": pl.String,
    "QFFM": pl.String,
    "FF2M": pl.String,
    "QFF2M": pl.String,
    "FXY": pl.String,
    "QFXY": pl.String,
    "DXY": pl.String,
    "QDXY": pl.String,
    "HXY": pl.String,
    "QHXY": pl.String,
    "FXI": pl.String,
    "QFXI": pl.String,
    "DXI": pl.String,
    "QDXI": pl.String,
    "HXI": pl.String,
    "QHXI": pl.String,
    "FXI2": pl.String,
    "QFXI2": pl.String,
    "DXI2": pl.String,
    "QDXI2": pl.String,
    "HXI2": pl.String,
    "QHXI2": pl.String,
    "FXI3S": pl.String,
    "QFXI3S": pl.String,
    "DXI3S": pl.String,
    "QDXI3S": pl.String,
    "HXI3S": pl.String,
    "QHXI3S": pl.String,
    "DRR": pl.String,
    "QDRR": pl.String,
    "STATUS_FXI3S": pl.String,
    "STATUS_DXI3S": pl.String,
}

_QUOT_AUTRES_SCHEMA = {
    "NUM_POSTE": pl.String,
    "NOM_USUEL": pl.String,
    "LAT": pl.String,
    "LON": pl.String,
    "ALTI": pl.String,
    "AAAAMMJJ": pl.String,
    "DHUMEC": pl.String,
    "QDHUMEC": pl.String,
    "PMERM": pl.String,
    "QPMERM": pl.String,
    "PMERMIN": pl.String,
    "QPMERMIN": pl.String,
    "INST": pl.String,
    "QINST": pl.String,
    "GLOT": pl.String,
    "QGLOT": pl.String,
    "DIFT": pl.String,
    "QDIFT": pl.String,
    "DIRT": pl.String,
    "QDIRT": pl.String,
    "INFRART": pl.String,
    "QINFRART": pl.String,
    "UV": pl.String,
    "QUV": pl.String,
    "UV_INDICEX": pl.String,
    "QUV_INDICEX": pl.String,
    "SIGMA": pl.String,
    "QSIGMA": pl.String,
    "UN": pl.String,
    "QUN": pl.String,
    "HUN": pl.String,
    "QHUN": pl.String,
    "UX": pl.String,
    "QUX": pl.String,
    "HUX": pl.String,
    "QHUX": pl.String,
    "UM": pl.String,
    "QUM": pl.String,
    "DHUMI40": pl.String,
    "QDHUMI40": pl.String,
    "DHUMI80": pl.String,
    "QDHUMI80": pl.String,
    "TSVM": pl.String,
    "QTSVM": pl.String,
    "ETPMON": pl.String,
    "QETPMON": pl.String,
    "ETPGRILLE": pl.String,
    "QETPGRILLE": pl.String,
    "ECOULEMENTM": pl.String,
    "QECOULEMENTM": pl.String,
    "HNEIGEF": pl.String,
    "QHNEIGEF": pl.String,
    "NEIGETOTX": pl.String,
    "QNEIGETOTX": pl.String,
    "NEIGETOT06": pl.String,
    "QNEIGETOT06": pl.String,
    "NEIG": pl.String,
    "QNEIG": pl.String,
    "BROU": pl.String,
    "QBROU": pl.String,
    "ORAG": pl.String,
    "QORAG": pl.String,
    "GRESIL": pl.String,
    "QGRESIL": pl.String,
    "GRELE": pl.String,
    "QGRELE": pl.String,
    "ROSEE": pl.String,
    "QROSEE": pl.String,
    "VERGLAS": pl.String,
    "QVERGLAS": pl.String,
    "SOLNEIGE": pl.String,
    "QSOLNEIGE": pl.String,
    "GELEE": pl.String,
    "QGELEE": pl.String,
    "FUMEE": pl.String,
    "QFUMEE": pl.String,
    "BRUME": pl.String,
    "QBRUME": pl.String,
    "ECLAIR": pl.String,
    "QECLAIR": pl.String,
    "NB300": pl.String,
    "QNB300": pl.String,
    "BA300": pl.String,
    "QBA300": pl.String,
    "TMERMIN": pl.String,
    "QTMERMIN": pl.String,
    "TMERMAX": pl.String,
    "QTMERMAX": pl.String,
}

_MENSQ_SCHEMA = {
    "NUM_POSTE": pl.String,
    "NOM_USUEL": pl.String,
    "LAT": pl.String,
    "LON": pl.String,
    "ALTI": pl.String,
    "AAAAMM": pl.String,
    "RR": pl.String,
    "QRR": pl.String,
    "NBRR": pl.String,
    "RR_ME": pl.String,
    "RRAB": pl.String,
    "QRRAB": pl.String,
    "RRABDAT": pl.String,
    "NBJRR1": pl.String,
    "NBJRR5": pl.String,
    "NBJRR10": pl.String,
    "NBJRR30": pl.String,
    "NBJRR50": pl.String,
    "NBJRR100": pl.String,
    "PMERM": pl.String,
    "QPMERM": pl.String,
    "NBPMERM": pl.String,
    "PMERMINAB": pl.String,
    "QPMERMINAB": pl.String,
    "PMERMINABDAT": pl.String,
    "TX": pl.String,
    "QTX": pl.String,
    "NBTX": pl.String,
    "TX_ME": pl.String,
    "TXAB": pl.String,
    "QTXAB": pl.String,
    "TXDAT": pl.String,
    "TXMIN": pl.String,
    "QTXMIN": pl.String,
    "TXMINDAT": pl.String,
    "NBJTX0": pl.String,
    "NBJTX25": pl.String,
    "NBJTX30": pl.String,
    "NBJTX35": pl.String,
    "NBJTXI20": pl.String,
    "NBJTXI27": pl.String,
    "NBJTXS32": pl.String,
    "TN": pl.String,
    "QTN": pl.String,
    "NBTN": pl.String,
    "TN_ME": pl.String,
    "TNAB": pl.String,
    "QTNAB": pl.String,
    "TNDAT": pl.String,
    "TNMAX": pl.String,
    "QTNMAX": pl.String,
    "TNMAXDAT": pl.String,
    "NBJTN5": pl.String,
    "NBJTN10": pl.String,
    "NBJTNI10": pl.String,
    "NBJTNI15": pl.String,
    "NBJTNI20": pl.String,
    "NBJTNS20": pl.String,
    "NBJTNS25": pl.String,
    "NBJGELEE": pl.String,
    "TAMPLIM": pl.String,
    "QTAMPLIM": pl.String,
    "TAMPLIAB": pl.String,
    "QTAMPLIAB": pl.String,
    "TAMPLIABDAT": pl.String,
    "NBTAMPLI": pl.String,
    "TM": pl.String,
    "QTM": pl.String,
    "NBTM": pl.String,
    "TMM": pl.String,
    "QTMM": pl.String,
    "NBTMM": pl.String,
    "NBJTMS24": pl.String,
    "TMMIN": pl.String,
    "QTMMIN": pl.String,
    "TMMINDAT": pl.String,
    "TMMAX": pl.String,
    "QTMMAX": pl.String,
    "TMMAXDAT": pl.String,
    "UNAB": pl.String,
    "QUNAB": pl.String,
    "UNABDAT": pl.String,
    "NBUN": pl.String,
    "UXAB": pl.String,
    "QUXAB": pl.String,
    "UXABDAT": pl.String,
    "NBUX": pl.String,
    "UMM": pl.String,
    "QUMM": pl.String,
    "NBUM": pl.String,
    "TSVM": pl.String,
    "QTSVM": pl.String,
    "NBTSVM": pl.String,
    "ETP": pl.String,
    "QETP": pl.String,
    "FXIAB": pl.String,
    "QFXIAB": pl.String,
    "DXIAB": pl.String,
    "QDXIAB": pl.String,
    "FXIDAT": pl.String,
    "NBJFF10": pl.String,
    "NBJFF16": pl.String,
    "NBJFF28": pl.String,
    "NBFXI": pl.String,
    "FXI3SAB": pl.String,
    "QFXI3SAB": pl.String,
    "DXI3SAB": pl.String,
    "QDXI3SAB": pl.String,
    "FXI3SDAT": pl.String,
    "NBJFXI3S10": pl.String,
    "NBJFXI3S16": pl.String,
    "NBJFXI3S28": pl.String,
    "NBFXI3S": pl.String,
    "FXYAB": pl.String,
    "QFXYAB": pl.String,
    "DXYAB": pl.String,
    "QDXYAB": pl.String,
    "FXYABDAT": pl.String,
    "NBJFXY8": pl.String,
    "NBJFXY10": pl.String,
    "NBJFXY15": pl.String,
    "NBFXY": pl.String,
    "FFM": pl.String,
    "QFFM": pl.String,
    "NBFFM": pl.String,
    "INST": pl.String,
    "QINST": pl.String,
    "NBINST": pl.String,
    "NBSIGMA0": pl.String,
    "NBSIGMA20": pl.String,
    "NBSIGMA80": pl.String,
    "GLOT": pl.String,
    "QGLOT": pl.String,
    "NBGLOT": pl.String,
    "DIFT": pl.String,
    "QDIFT": pl.String,
    "NBDIFT": pl.String,
    "DIRT": pl.String,
    "QDIRT": pl.String,
    "NBDIRT": pl.String,
    "HNEIGEFTOT": pl.String,
    "QHNEIGEFTOT": pl.String,
    "HNEIGEFAB": pl.String,
    "QHNEIGEFAB": pl.String,
    "HNEIGEFDAT": pl.String,
    "NBHNEIGEF": pl.String,
    "NBJNEIG": pl.String,
    "NBJHNEIGEF1": pl.String,
    "NBJHNEIGEF5": pl.String,
    "NBJHNEIGEF10": pl.String,
    "NBJSOLNG": pl.String,
    "NEIGETOTM": pl.String,
    "QNEIGETOTM": pl.String,
    "NEIGETOTAB": pl.String,
    "QNEIGETOTAB": pl.String,
    "NEIGETOTABDAT": pl.String,
    "NBJNEIGETOT1": pl.String,
    "NBJNEIGETOT10": pl.String,
    "NBJNEIGETOT30": pl.String,
    "NBJGREL": pl.String,
    "NBJORAG": pl.String,
    "NBJBROU": pl.String,
}

_HOR_SCHEMA = {
    "NUM_POSTE": pl.String,
    "NOM_USUEL": pl.String,
    "LAT": pl.String,
    "LON": pl.String,
    "ALTI": pl.String,
    "AAAAMMJJHH": pl.String,
    "RR1": pl.String,
    "QRR1": pl.String,
    "DRR1": pl.String,
    "QDRR1": pl.String,
    "FF": pl.String,
    "QFF": pl.String,
    "DD": pl.String,
    "QDD": pl.String,
    "FXY": pl.String,
    "QFXY": pl.String,
    "DXY": pl.String,
    "QDXY": pl.String,
    "HXY": pl.String,
    "QHXY": pl.String,
    "FXI": pl.String,
    "QFXI": pl.String,
    "DXI": pl.String,
    "QDXI": pl.String,
    "HXI": pl.String,
    "QHXI": pl.String,
    "FF2": pl.String,
    "QFF2": pl.String,
    "DD2": pl.String,
    "QDD2": pl.String,
    "FXI2": pl.String,
    "QFXI2": pl.String,
    "DXI2": pl.String,
    "QDXI2": pl.String,
    "HXI2": pl.String,
    "QHXI2": pl.String,
    "FXI3S": pl.String,
    "QFXI3S": pl.String,
    "DXI3S": pl.String,
    "QDXI3S": pl.String,
    "HFXI3S": pl.String,
    "QHFXI3S": pl.String,
    "T": pl.String,
    "QT": pl.String,
    "TD": pl.String,
    "QTD": pl.String,
    "TN": pl.String,
    "QTN": pl.String,
    "HTN": pl.String,
    "QHTN": pl.String,
    "TX": pl.String,
    "QTX": pl.String,
    "HTX": pl.String,
    "QHTX": pl.String,
    "DG": pl.String,
    "QDG": pl.String,
    "T10": pl.String,
    "QT10": pl.String,
    "T20": pl.String,
    "QT20": pl.String,
    "T50": pl.String,
    "QT50": pl.String,
    "T100": pl.String,
    "QT100": pl.String,
    "TNSOL": pl.String,
    "QTNSOL": pl.String,
    "TN50": pl.String,
    "QTN50": pl.String,
    "TCHAUSSEE": pl.String,
    "QTCHAUSSEE": pl.String,
    "DHUMEC": pl.String,
    "QDHUMEC": pl.String,
    "U": pl.String,
    "QU": pl.String,
    "UN": pl.String,
    "QUN": pl.String,
    "HUN": pl.String,
    "QHUN": pl.String,
    "UX": pl.String,
    "QUX": pl.String,
    "HUX": pl.String,
    "QHUX": pl.String,
    "DHUMI40": pl.String,
    "QDHUMI40": pl.String,
    "DHUMI80": pl.String,
    "QDHUMI80": pl.String,
    "TSV": pl.String,
    "QTSV": pl.String,
    "PMER": pl.String,
    "QPMER": pl.String,
    "PSTAT": pl.String,
    "QPSTAT": pl.String,
    "PMERMIN": pl.String,
    "QPMERMIN": pl.String,
    "GEOP": pl.String,
    "QGEOP": pl.String,
    "N": pl.String,
    "QN": pl.String,
    "NBAS": pl.String,
    "QNBAS": pl.String,
    "CL": pl.String,
    "QCL": pl.String,
    "CM": pl.String,
    "QCM": pl.String,
    "CH": pl.String,
    "QCH": pl.String,
    "N1": pl.String,
    "QN1": pl.String,
    "C1": pl.String,
    "QC1": pl.String,
    "B1": pl.String,
    "QB1": pl.String,
    "N2": pl.String,
    "QN2": pl.String,
    "C2": pl.String,
    "QC2": pl.String,
    "B2": pl.String,
    "QB2": pl.String,
    "N3": pl.String,
    "QN3": pl.String,
    "C3": pl.String,
    "QC3": pl.String,
    "B3": pl.String,
    "QB3": pl.String,
    "N4": pl.String,
    "QN4": pl.String,
    "C4": pl.String,
    "QC4": pl.String,
    "B4": pl.String,
    "QB4": pl.String,
    "VV": pl.String,
    "QVV": pl.String,
    "DVV200": pl.String,
    "QDVV200": pl.String,
    "WW": pl.String,
    "QWW": pl.String,
    "W1": pl.String,
    "QW1": pl.String,
    "W2": pl.String,
    "QW2": pl.String,
    "SOL": pl.String,
    "QSOL": pl.String,
    "SOLNG": pl.String,
    "QSOLNG": pl.String,
    "TMER": pl.String,
    "QTMER": pl.String,
    "VVMER": pl.String,
    "QVVMER": pl.String,
    "ETATMER": pl.String,
    "QETATMER": pl.String,
    "DIRHOULE": pl.String,
    "QDIRHOULE": pl.String,
    "HVAGUE": pl.String,
    "QHVAGUE": pl.String,
    "PVAGUE": pl.String,
    "QPVAGUE": pl.String,
    "HNEIGEF": pl.String,
    "QHNEIGEF": pl.String,
    "NEIGETOT": pl.String,
    "QNEIGETOT": pl.String,
    "TSNEIGE": pl.String,
    "QTSNEIGE": pl.String,
    "TUBENEIGE": pl.String,
    "QTUBENEIGE": pl.String,
    "HNEIGEFI3": pl.String,
    "QHNEIGEFI3": pl.String,
    "HNEIGEFI1": pl.String,
    "QHNEIGEFI1": pl.String,
    "ESNEIGE": pl.String,
    "QESNEIGE": pl.String,
    "CHARGENEIGE": pl.String,
    "QCHARGENEIGE": pl.String,
    "GLO": pl.String,
    "QGLO": pl.String,
    "GLO2": pl.String,
    "QGLO2": pl.String,
    "DIR": pl.String,
    "QDIR": pl.String,
    "DIR2": pl.String,
    "QDIR2": pl.String,
    "DIF": pl.String,
    "QDIF": pl.String,
    "DIF2": pl.String,
    "QDIF2": pl.String,
    "UV": pl.String,
    "QUV": pl.String,
    "UV2": pl.String,
    "QUV2": pl.String,
    "UV_INDICE": pl.String,
    "QUV_INDICE": pl.String,
    "INFRAR": pl.String,
    "QINFRAR": pl.String,
    "INFRAR2": pl.String,
    "QINFRAR2": pl.String,
    "INS": pl.String,
    "QINS": pl.String,
    "INS2": pl.String,
    "QINS2": pl.String,
    "TLAGON": pl.String,
    "QTLAGON": pl.String,
    "TVEGETAUX": pl.String,
    "QTVEGETAUX": pl.String,
    "ECOULEMENT": pl.String,
    "QECOULEMENT": pl.String,
    "STATUS_FXI3S": pl.String,
    "STATUS_DXI3S": pl.String,
}

_MIN_SCHEMA = {
    "NUM_POSTE": pl.String,
    "NOM_USUEL": pl.String,
    "LAT": pl.String,
    "LON": pl.String,
    "ALTI": pl.String,
    "AAAAMMJJHHMN": pl.String,
    "RR": pl.String,
    "QRR": pl.String,
}

_CLIMATE_SCHEMAS = {
    ("daily", "core"): _QUOT_RR_T_VENT_SCHEMA,
    ("daily", "others"): _QUOT_AUTRES_SCHEMA,
    ("monthly", "data"): _MENSQ_SCHEMA,
    ("hourly", "core"): _HOR_SCHEMA,
    ("hourly", "others"): _HOR_SCHEMA,
    ("6_minutes", "data"): _MIN_SCHEMA,
}


def _department_from_station_id(station_id: str) -> str:
    """Get the French department code from an 8-digit NUM_POSTE station id."""
    return station_id[:3] if station_id[:2] in ("97", "98") else station_id[:2]


def _parse_climate_date(date_column: pl.Expr, resolution_name: str) -> pl.Expr:
    """Parse a resolution's raw date column into a UTC datetime.

    polars' strptime requires a minute whenever an hour is present in the format string, but
    "hourly"'s AAAAMMJJHH has no minute component, so it's padded in before parsing.
    """
    date_format = _CLIMATE_DATE_FORMATS[resolution_name]
    if resolution_name == "hourly":
        date_column = date_column + "00"
        date_format += "%M"
    return date_column.str.to_datetime(date_format, strict=False).dt.replace_time_zone("UTC")


def _get_climate_resources(resolution_name: str, settings: Settings) -> list[dict]:
    """Fetch (and cache) the resource listing published for a climatological dataset.

    Resource URLs are discovered at request time via the data.gouv.fr dataset API instead of
    being hardcoded, since Météo-France periodically shifts the period-bucket labels (e.g.
    "2025-2026" becomes "2025-2027") as new data becomes available.
    """
    dataset_id = _CLIMATE_DATASET_IDS[resolution_name]
    url = f"https://www.data.gouv.fr/api/1/datasets/{dataset_id}/"
    file = download_file(
        url=url,
        cache_dir=settings.cache_dir,
        ttl=CacheExpiry.METAINDEX,
        client_kwargs=settings.fsspec_client_kwargs,
        cache_disable=settings.cache_disable,
        use_certifi=settings.use_certifi,
    )
    file.raise_if_exception()
    if isinstance(file.content, Exception):
        return []
    return json.loads(file.content.read()).get("resources", [])


def _match_department_resources(resources: list[dict], prefix: str, suffix: str) -> list[dict]:
    """Filter resources by department (prefix) and file group (suffix)."""
    pattern = re.compile(rf"^{re.escape(prefix)}.*{re.escape(suffix)}$")
    return [resource for resource in resources if pattern.match(resource["title"])]


def _resource_year_range(resource: dict) -> tuple[int, int]:
    """Get the year range embedded in a resource title, e.g. (1950, 2024) for "...1950-2024".

    A "avant-YYYY" ("before YYYY") title only embeds its end year, with an effectively unbounded
    start.
    """
    years = [int(year) for year in re.findall(r"\d{4}", resource["title"])]
    if not years:
        return 1, 9999
    if "avant" in resource["title"]:
        return 1, years[0]
    return min(years), max(years)


def _resource_max_year(resource: dict) -> int:
    """Get the most recent year embedded in a resource title, e.g. 2026 for "...2025-2026"."""
    return _resource_year_range(resource)[1]


def _resource_cache_ttl(resource: dict) -> CacheExpiry:
    """Cache period buckets that may still receive updates for a shorter time."""
    current_year = datetime.now(tz=ZoneInfo("UTC")).year
    return CacheExpiry.FIVE_MINUTES if _resource_max_year(resource) >= current_year - 1 else CacheExpiry.INFINITE


def _resource_overlaps_request(resource: dict, start_date: datetime | None, end_date: datetime | None) -> bool:
    """Check whether a period-bucket resource can contain any data within the requested range.

    Météo-France's climatological archives shard each department into a handful of multi-decade
    period buckets (e.g. one alone can decompress to 100+ MB); skipping buckets that clearly fall
    outside the requested date range avoids downloading/parsing them at all.
    """
    if start_date is None or end_date is None:
        return True
    min_year, max_year = _resource_year_range(resource)
    return max_year >= start_date.year and min_year <= end_date.year


def _download_climate_resources(resources: list[dict], settings: Settings) -> dict[str, File]:
    """Download resources concurrently (grouped by cache ttl), keyed by url.

    A handful of downloads commonly fail transiently when many requests go out at once (e.g.
    server-side rate limiting) even after download_file's own retries, so failed ones get one
    more, less concurrent attempt rather than silently dropping their data from the result.
    """
    files_by_url: dict[str, File] = {}
    resources_by_ttl: dict[CacheExpiry, list[dict]] = {}
    for resource in resources:
        resources_by_ttl.setdefault(_resource_cache_ttl(resource), []).append(resource)
    for ttl, ttl_resources in resources_by_ttl.items():
        urls = [resource["url"] for resource in ttl_resources]
        files = download_files(
            urls=urls,
            cache_dir=settings.cache_dir,
            ttl=ttl,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        files_by_url.update(zip(urls, files, strict=True))
        # retrying is only worthwhile for likely-transient failures; a missing connection or a
        # genuinely nonexistent resource (404) will just fail again immediately
        failed_urls = [
            url
            for url, file in files_by_url.items()
            if url in urls
            and isinstance(file.content, Exception)
            and not file.is_no_internet_error
            and file.status != 404
        ]
        if failed_urls:
            log.info(f"Retrying {len(failed_urls)} file(s) that failed to download.")
            for url in failed_urls:
                files_by_url[url] = download_file(
                    url=url,
                    cache_dir=settings.cache_dir,
                    ttl=ttl,
                    client_kwargs=settings.fsspec_client_kwargs,
                    cache_disable=settings.cache_disable,
                    use_certifi=settings.use_certifi,
                )
    return files_by_url


# Météo-France's canonical station metadata registry (~14.7k stations, ~2MB single CSV), built
# from their internal API. Used for station identity/coordinates/start_date/end_date instead of
# scanning every department's climatological archive (up to ~300 files, tens of GB decompressed
# in total) just to derive the same information -- this registry already publishes exact per
# station start_date/end_date directly. It covers a broader set of stations than actually have
# downloadable daily/monthly records in the archives scanned by _collect_station_parameter_or_dataset
# below (e.g. very recently opened stations, or station types outside that archive's curation);
# querying one of those returns an empty result, same as any other station without data for a
# requested parameter.
# data.gouv.fr's stable "latest resource" redirect for this dataset's single CSV resource,
# rather than the dated static.data.gouv.fr path it currently points to (which changes whenever
# Météo-France republishes the file, like the period-bucket labels in the climate archives above)
_STATIONS_REGISTRY_URL = "https://www.data.gouv.fr/api/1/datasets/r/5ec141e4-3650-4365-82b1-db459efe690c"
_STATIONS_REGISTRY_SCHEMA = {
    "id": pl.String,
    "name": pl.String,
    "long_name": pl.String,
    "named_place": pl.String,
    "station_type": pl.String,
    "basin": pl.String,
    "lon": pl.String,
    "lat": pl.String,
    "alt": pl.String,
    "start_date": pl.String,
    "end_date": pl.String,
    "is_open": pl.String,
    "is_public": pl.String,
    "department_id": pl.String,
    "is_daily": pl.String,
    "is_hourly": pl.String,
    "is_minutely": pl.String,
}


class MeteoFranceObservationValues(TimeseriesValues):
    """Values class for Météo-France observation data."""

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel | DatasetModel,
    ) -> pl.DataFrame:
        dataset = cast("DatasetModel", parameter_or_dataset)
        resolution_name = dataset.resolution.name
        settings = cast("Settings", self.sr.stations.settings)
        department = _department_from_station_id(station_id)
        resources = _get_climate_resources(resolution_name, settings)
        prefix = _CLIMATE_RESOURCE_PREFIXES[resolution_name].format(department=department)
        suffix = _CLIMATE_RESOURCE_SUFFIXES[resolution_name][dataset.name]
        matches = _match_department_resources(resources, prefix, suffix)
        # a department's period buckets can each decompress to 100+ MB; skip any that clearly
        # fall outside the requested date range instead of downloading/parsing them regardless
        matches = [
            resource
            for resource in matches
            if _resource_overlaps_request(resource, self.sr.start_date, self.sr.end_date)
        ]
        if not matches:
            return pl.DataFrame()
        schema = _CLIMATE_SCHEMAS[resolution_name, dataset.name]
        date_column = _CLIMATE_DATE_COLUMNS[resolution_name]
        parameter_columns = [parameter.name_original for parameter in dataset]
        read_columns = ["NUM_POSTE", date_column, *parameter_columns]
        files_by_url = _download_climate_resources(matches, settings)
        dfs = []
        for resource in matches:
            file = files_by_url[resource["url"]]
            if isinstance(file.content, Exception):
                if not file.is_no_internet_error:
                    # _download_climate_resources already retried this once; a failure surviving
                    # that is unexpected, so log it instead of silently treating this bucket as
                    # having no data, but keep processing the remaining buckets
                    log.warning(f"Failed to download {file.url}: {file.content}")
                continue
            with gzip.GzipFile(fileobj=file.content) as gz:
                df = pl.read_csv(cast("IO[bytes]", gz), separator=";", schema=schema, columns=read_columns)
            df = df.filter(pl.col("NUM_POSTE").eq(station_id))
            if not df.is_empty():
                dfs.append(df)
        if not dfs:
            return pl.DataFrame()
        df = pl.concat(dfs, how="diagonal")
        df = df.unpivot(
            on=parameter_columns,
            index=[date_column],
            variable_name="parameter",
            value_name="value",
        )
        return df.select(
            pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            # kept as published (e.g. "RR", "TN"), matching the case of name_original in the
            # metadata below; the base class matches requested parameters against this column
            # using an exact, case-sensitive comparison against parameter.name_original
            pl.col("parameter"),
            pl.lit(station_id, dtype=pl.String).alias("station_id"),
            _parse_climate_date(pl.col(date_column), resolution_name).alias("date"),
            pl.col("value").cast(pl.Float64, strict=False),
            pl.lit(None, pl.Float64).alias("quality"),
        )


@dataclass
class MeteoFranceObservationRequest(TimeseriesRequest):
    """Request class for Météo-France observation data."""

    metadata = MeteoFranceObservationMetadata
    _values = MeteoFranceObservationValues

    def _all(self) -> pl.LazyFrame:
        # self.parameters is parsed at runtime to a list[ParameterModel], but the static type of
        # the attribute is a union of input forms; cast here so the typechecker understands we
        # iterate ParameterModel instances.
        parameters = cast("Iterable[ParameterModel]", self.parameters)
        stations_df = self._climate_stations(cast("Settings", self.settings))
        if stations_df.is_empty():
            return pl.LazyFrame()
        # groupby() only groups consecutive items, but parameters preserves the user-supplied
        # order, so datasets interleaved across parameters (e.g. [core, others, core]) would
        # otherwise produce duplicate groups for the same dataset and duplicate station rows
        datasets = {(p.dataset.resolution.name, p.dataset.name): p.dataset for p in parameters}
        data = [
            stations_df.lazy().with_columns(
                pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
                pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            )
            for dataset in datasets.values()
        ]
        return pl.concat(data)

    @staticmethod
    def _climate_stations(settings: Settings) -> pl.DataFrame:
        """Build the station list from Météo-France's canonical station metadata registry."""
        file = download_file(
            url=_STATIONS_REGISTRY_URL,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.DataFrame()
        df = pl.read_csv(file.content, schema=_STATIONS_REGISTRY_SCHEMA)
        return df.select(
            pl.col("id").alias("station_id"),
            pl.col("name"),
            pl.col("lat").cast(pl.Float64, strict=False).alias("latitude"),
            pl.col("lon").cast(pl.Float64, strict=False).alias("longitude"),
            pl.col("alt").cast(pl.Float64, strict=False).alias("height"),
            pl.col("start_date").str.to_datetime("%Y-%m-%d", strict=False).dt.replace_time_zone("UTC"),
            # nullable: still-open stations (the vast majority) have no end_date, matching how
            # the frontend already treats a missing end_date as "still reporting"
            pl.col("end_date").str.to_datetime("%Y-%m-%d", strict=False).dt.replace_time_zone("UTC"),
        )
