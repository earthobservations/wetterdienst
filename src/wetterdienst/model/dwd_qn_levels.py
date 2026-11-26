# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The quality levels (QN) of DWD's observation products and what DWD says they mean (GH-4474).

The first token of a `dwd/observation` reading's `quality_flags` is the quality level (QN) of its row, a number.
DWD documents the levels in the `DESCRIPTION_*.pdf` (English; `BESCHREIBUNG_*.pdf` in German) of each product's
directory on the climate data centre, under "Quality Information". The wording below is that of the English document,
copied. The documents agree where they list a level, and differ in how many they list:

* the 1-, 5- and 10-minute products list 1 to 3;
* the hourly, daily and monthly products of the station network list 1, 2, 3, 5, 7, 8, 9 and 10, and say that data
  up to and including 1980 reach 5 at best and later data 10;
* the six hourly products of the urban stations list 1 and 2 only.

For the other products (the sub-daily, the annual, the 10-minute urban, the daily `weather_phenomena` and
`weather_phenomena_more`, the monthly and annual indices and weather phenomena) DWD publishes no description at all, so
no level is told for them and the legend says so: a level is never carried over from another product.

The German text of level 7 differs from the English one. The German descriptions of the daily climate data
(`BESCHREIBUNG_obsgermany-climate-daily-kl_de.pdf`) and of the hourly air temperature say "geprüft, gepflegt, nicht
korrigiert" (checked, maintained, not corrected) where the English ones say "second control done, before correction".
The English text is the one told here; `docs/data/quality-flags.md` names the German one.

`tests/model/test_dwd_qn_levels.py` holds this table to `tests/model/dwd_qn_documents.json`, a transcript of the lists
as the documents give them (read on 2026-11-26), and to the datasets the observation metadata declares.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

if TYPE_CHECKING:
    from collections.abc import Iterable

#: the climate data centre's directory of the station network and of the urban stations
_STATIONS = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate/"
_URBAN = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/climate_urban/"

#: every level the documents list, with DWD's English wording of it
LEVELS: dict[str, str] = {
    "1": "only formal control",
    "2": "controlled with individually defined criteria",
    "3": "automatic control and correction",
    "5": "historic, subjective procedures",
    "7": "second control done, before correction",
    "8": "quality control outside ROUTINE",
    "9": "not all parameters corrected",
    "10": "quality control finished, all corrections finished",
}

#: what the documents of the hourly, daily and monthly products say of the levels 5 and 10 (and so of the range)
NOTE_1980 = "Data up to and including 1980 reach 5 at best, later data 10."

_FINE = ("1", "2", "3")
_URBAN_LEVELS = ("1", "2")
_FULL = tuple(LEVELS)


class QnDocument(NamedTuple):
    """The levels one product's description lists, and the description."""

    levels: tuple[str, ...]
    url: str


def _station(path: str, name: str, levels: tuple[str, ...]) -> QnDocument:
    return QnDocument(levels, f"{_STATIONS}{path}/DESCRIPTION_{name}_en.pdf")


def _hourly(directory: str) -> QnDocument:
    return _station(f"hourly/{directory}", f"obsgermany_climate_hourly_{directory}", _FULL)


def _tenmin(directory: str, name: str | None = None) -> QnDocument:
    return _station(f"10_minutes/{directory}", name or f"obsgermany_climate_10min_{directory}", _FINE)


def _urban(directory: str, name: str) -> QnDocument:
    return QnDocument(
        _URBAN_LEVELS,
        f"{_URBAN}hourly/{directory}/recent/DESCRIPTION_obsgermany_climate_urban_hourly_{name}_recent_en.pdf",
    )


#: the description of every product of `dwd/observation` that has one, by `resolution/dataset` as the library names it
DOCUMENTS: dict[str, QnDocument] = {
    "1_minute/precipitation": _station("1_minute/precipitation", "obsgermany-climate-1min-rr", _FINE),
    "5_minutes/precipitation": _station("5_minutes/precipitation", "obsgermany-climate-5min-rr", _FINE),
    "10_minutes/precipitation": _tenmin("precipitation", "obsgermany-climate-10min-precipitation"),
    "10_minutes/solar": _tenmin("solar"),
    "10_minutes/temperature_air": _tenmin("air_temperature"),
    "10_minutes/temperature_extreme": _tenmin("extreme_temperature"),
    "10_minutes/wind": _tenmin("wind"),
    "10_minutes/wind_extreme": _tenmin("extreme_wind"),
    "hourly/cloud_type": _hourly("cloud_type"),
    "hourly/cloudiness": _hourly("cloudiness"),
    "hourly/dew_point": _hourly("dew_point"),
    "hourly/moisture": _hourly("moisture"),
    "hourly/precipitation": _hourly("precipitation"),
    "hourly/pressure": _hourly("pressure"),
    "hourly/solar": _hourly("solar"),
    "hourly/sun": _hourly("sun"),
    "hourly/temperature_air": _hourly("air_temperature"),
    "hourly/temperature_soil": _hourly("soil_temperature"),
    "hourly/visibility": _hourly("visibility"),
    "hourly/weather_phenomena": _hourly("weather_phenomena"),
    "hourly/wind": _hourly("wind"),
    "hourly/wind_extreme": _hourly("extreme_wind"),
    "hourly/wind_synoptic": _hourly("wind_synop"),
    "hourly/urban_temperature_air": _urban("air_temperature", "tu"),
    "hourly/urban_precipitation": _urban("precipitation", "precipitation"),
    "hourly/urban_pressure": _urban("pressure", "pressure"),
    "hourly/urban_temperature_soil": _urban("soil_temperature", "soil_temperature"),
    "hourly/urban_sun": _urban("sun", "sun"),
    "hourly/urban_wind": _urban("wind", "wind"),
    "daily/climate_summary": _station("daily/kl", "obsgermany-climate-daily-kl", _FULL),
    "daily/precipitation_more": _station("daily/more_precip", "obsgermany-climate-daily-more_precip", _FULL),
    "daily/solar": _station("daily/solar", "obsgermany-climate-daily-solar", _FULL),
    "daily/temperature_soil": _station("daily/soil_temperature", "obsgermany-climate-daily-soil_temperature", _FULL),
    "daily/water_equivalent": _station("daily/water_equiv", "f62e277b-00f5-4be8-95a4-0c598d869e5a", _FULL),
    "monthly/climate_summary": _station("monthly/kl", "obsgermany-climate-monthly-kl", _FULL),
    "monthly/precipitation_more": _station("monthly/more_precip", "obsgermany-climate-monthly-more_precip", _FULL),
}

#: the datasets with a quality column of `dwd/observation` for which DWD publishes no description of the levels
UNDOCUMENTED: tuple[str, ...] = (
    "10_minutes/urban_temperature_air",
    "10_minutes/urban_temperature_extreme",
    "10_minutes/urban_wind_extreme",
    "10_minutes/urban_precipitation",
    "10_minutes/urban_pressure",
    "10_minutes/urban_temperature_soil",
    "10_minutes/urban_solar",
    "10_minutes/urban_wind",
    "subdaily/cloudiness",
    "subdaily/moisture",
    "subdaily/pressure",
    "subdaily/soil",
    "subdaily/temperature_air",
    "subdaily/visibility",
    "subdaily/wind",
    "subdaily/wind_extreme",
    "daily/weather_phenomena",
    "daily/weather_phenomena_more",
    "monthly/climate_indices",
    "monthly/precipitation_indices",
    "monthly/weather_phenomena",
    "annual/climate_indices",
    "annual/climate_summary",
    "annual/precipitation_indices",
    "annual/precipitation_more",
    "annual/weather_phenomena",
)


class QnLevels(NamedTuple):
    """The levels of the datasets an answer reads: those DWD lists, where, and the datasets it lists none for."""

    levels: list[str]
    urls: list[str]
    undocumented: list[str]


def qn_levels(datasets: Iterable[str]) -> QnLevels:
    """Give the levels DWD lists for the datasets (`resolution/dataset`), in DWD's order, once each.

    A level two products both list has the same wording in both (the test holds the table to that), so it is told once.
    The datasets DWD publishes no description for are named in `undocumented`; a dataset the table does not know is
    left out of all three (a dataset without a quality column, which a test keeps the table complete against).
    """
    wanted = list(dict.fromkeys(datasets))
    documents = [DOCUMENTS[dataset] for dataset in wanted if dataset in DOCUMENTS]
    levels = {level for document in documents for level in document.levels}
    return QnLevels(
        levels=[level for level in LEVELS if level in levels],
        urls=sorted({document.url for document in documents}),
        undocumented=[dataset for dataset in wanted if dataset in UNDOCUMENTED],
    )
