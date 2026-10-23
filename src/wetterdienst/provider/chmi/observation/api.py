# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""CHMI (Czech Hydrometeorological Institute) observation provider.

CHMI publishes historical climate observations as key-less CSV files through its open-data
portal. Station metadata comes from ``metadata/meta1.csv``. Observations are addressed per
``(station, element)``: ``daily``/``monthly``/``annual`` as one flat CSV each, ``10_minutes`` and
``hourly`` as one CSV per ``(station, element, month)`` under a year sub-directory.

See https://opendata.chmi.cz/meteorology/climate/historical_csv/ and the accompanying
``Klimatologicka_data_popis.pdf``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, cast

import polars as pl

from wetterdienst.exceptions import DownloadError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.metadata import DatasetModel, ParameterModel, group_parameters_by_dataset
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.chmi.observation.metadata import ChmiObservationMetadata
from wetterdienst.provider.chmi.observation.parser import (
    parse_chmi_stations,
    parse_chmi_values_aggregate,
    parse_chmi_values_daily,
    parse_chmi_values_subdaily,
)
from wetterdienst.util.network import download_file, list_remote_files_fsspec

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Iterator

    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

_BASE_URL = "https://opendata.chmi.cz/meteorology/climate/historical_csv"

# monthly/annual elements as (category, TIMEFUNCTION, MDFUNCTION): the daily value that is
# aggregated, and how it is aggregated over the period -- the climatological mean of daily means /
# daily maxima / daily minima, and the total for precipitation.
_AGGREGATE_ELEMENTS = {
    "T": ("temperature", "AVG", "AVG"),
    "TMA": ("temperature", "20:00", "AVG"),
    "TMI": ("temperature", "20:00", "AVG"),
    "SRA": ("precipitation", "06:00", "SUM"),
}

# Per resolution: the URL path segment, the per-file prefix, the file layout and, for each
# element, its category sub-directory plus the value-selection term(s). The element tuple is
# ``(category,)``-like: ``(category, None)`` for sub-daily (a single reading per timestamp),
# ``(category, TIMEFUNC)`` for daily, ``(category, TIMEFUNCTION, MDFUNCTION)`` for monthly/annual.
#   layout "daily"     -> one flat CSV, select by TIMEFUNC, day-truncated timestamp
#   layout "aggregate" -> one flat CSV, select by TIMEFUNCTION+MDFUNCTION, date from YEAR(+MONTH)
#   layout "subdaily"  -> one CSV per (element, month) under <path>/<category>/<year>/
_RESOLUTION_CONFIG: dict[Resolution, dict] = {
    Resolution.MINUTE_10: {
        "path": "10min",
        "prefix": "10m",
        "layout": "subdaily",
        "elements": {
            "T": ("temperature", None),
            "H": ("humidity", None),
            "P": ("air_pressure", None),
            "F": ("wind", None),
        },
    },
    Resolution.HOURLY: {
        "path": "1hour",
        "prefix": "1h",
        "layout": "subdaily",
        "elements": {"Td": ("synop", None), "SRA1H": ("precipitation", None), "P": ("synop", None)},
    },
    Resolution.DAILY: {
        "path": "daily",
        "prefix": "dly",
        "layout": "daily",
        "elements": {
            "T": ("temperature", "AVG"),
            "TMA": ("temperature", "20:00"),
            "TMI": ("temperature", "20:00"),
            "H": ("humidity", "AVG"),
            "SRA": ("precipitation", "06:00"),
            "P": ("air_pressure", "AVG"),
            "F": ("wind", "AVG"),
            "Fmax": ("wind", "00:00"),
            "SCE": ("snow", "06:00"),
            "SSV": ("sunshine", "00:00"),
        },
    },
    Resolution.MONTHLY: {
        "path": "monthly",
        "prefix": "mly",
        "layout": "aggregate",
        "has_month": True,
        "elements": _AGGREGATE_ELEMENTS,
    },
    Resolution.ANNUAL: {
        "path": "yearly",
        "prefix": "yrs",
        "layout": "aggregate",
        "has_month": False,
        "elements": _AGGREGATE_ELEMENTS,
    },
}


def _months(start: dt.datetime, end: dt.datetime) -> Iterator[tuple[int, int]]:
    """Yield ``(year, month)`` for every month in ``[start, end]`` inclusive."""
    year, month = start.year, start.month
    while (year, month) <= (end.year, end.month):
        yield year, month
        month += 1
        if month > 12:
            year, month = year + 1, 1


def _stations_with_file(config: dict, requested: set[str], settings: Settings) -> set[str]:
    """Read the ids of the stations that have a file of one of the requested elements, from their directories.

    A directory of a category lists the files ``<prefix>-<WSI>-<element>.csv`` of all stations, so it is read once for
    all the requested elements it holds, and only the categories of the requested elements are read. A station that
    has a file of any of them counts: the values step then collects the elements it has. A file of an element that
    was not requested, or that the provider does not read (``TPM``, ``API30``), counts for nothing.

    Raises:
        NoInternetError: a directory could not be listed because no connection could be made.
        DownloadError: a directory could not be listed, or the directories list no file of any requested element. A
            directory that is not there lists no file, which narrows the stations of its element away; all of them
            gone is the portal having changed, not a network without stations (GH-2519).

    """
    ids: set[str] = set()
    elements = {element: config["elements"][element] for element in requested if element in config["elements"]}
    for category in dict.fromkeys(element_config[0] for element_config in elements.values()):
        url = f"{_BASE_URL}/data/{config['path']}/{category}/"
        in_category = {element for element, element_config in elements.items() if element_config[0] == category}
        for file in list_remote_files_fsspec(url, settings, CacheExpiry.METAINDEX):
            name = file.rsplit("/", 1)[-1]
            if not (name.startswith(f"{config['prefix']}-") and name.endswith(".csv")):
                continue
            station, _, element = name.removeprefix(f"{config['prefix']}-").removesuffix(".csv").rpartition("-")
            if element in in_category:
                ids.add(station)
    if not ids:
        url = f"{_BASE_URL}/data/{config['path']}/"
        wanted = ", ".join(sorted(elements)) or "none that is read"
        raise DownloadError(
            url, f"no file of the form {config['prefix']}-<station>-<element>.csv is listed for {wanted}"
        )
    return ids


class ChmiObservationValues(TimeseriesValues):
    """Values class for CHMI observation data."""

    def _download(self, url: str, settings: Settings, station_id: str) -> bytes | None:
        file = download_file(
            url=url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.TWELVE_HOURS,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        # a station that does not measure an element (or has no data for a month) has no file, which
        # is a 404 and routine; any other failure -- a timeout, a 5xx after the retries -- is an
        # outage, which swallowed would read as a station that does not measure the element (GH-2461)
        if file.status != 404:
            file.raise_if_exception()
        if isinstance(file.content, Exception):
            log.debug(f"No CHMI file {url} for station {station_id}: {file.content}")
            return None
        return file.content.read()

    def _collect_element(
        self,
        station_id: str,
        element: str,
        element_config: tuple,
        config: dict,
        settings: Settings,
    ) -> list[pl.DataFrame]:
        layout = config["layout"]
        category = element_config[0]
        if layout == "subdaily":
            frames = []
            # the month files are named by UTC calendar month, which is the zone of the request's bounds
            for year, month in _months(cast("dt.datetime", self.sr.start), cast("dt.datetime", self.sr.end)):
                url = (
                    f"{_BASE_URL}/data/{config['path']}/{category}/{year}/"
                    f"{config['prefix']}-{station_id}-{element}-{year}{month:02d}.csv"
                )
                content = self._download(url, settings, station_id)
                if content is not None:
                    df = parse_chmi_values_subdaily(content, element=element)
                    if not df.is_empty():
                        frames.append(df)
            return frames
        url = f"{_BASE_URL}/data/{config['path']}/{category}/{config['prefix']}-{station_id}-{element}.csv"
        content = self._download(url, settings, station_id)
        if content is None:
            return []
        if layout == "daily":
            df = parse_chmi_values_daily(content, element=element, timefunc=element_config[1])
        else:
            df = parse_chmi_values_aggregate(
                content,
                element=element,
                timefunc=element_config[1],
                mdfunc=element_config[2],
                has_month=config["has_month"],
            )
        return [df] if not df.is_empty() else []

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel | DatasetModel,
    ) -> pl.DataFrame:
        if isinstance(parameter_or_dataset, DatasetModel):
            dataset = parameter_or_dataset
            parameters = list(parameter_or_dataset.parameters)
        elif isinstance(parameter_or_dataset, ParameterModel):
            dataset = parameter_or_dataset.dataset
            parameters = [parameter_or_dataset]
        else:
            return pl.DataFrame()

        settings = cast("Settings", self.sr.request.settings)
        config = _RESOLUTION_CONFIG[dataset.resolution.value]
        # the sub-daily files are partitioned by month, so a date range is required to address them
        if config["layout"] == "subdaily" and (not self.sr.start or not self.sr.end):
            return pl.DataFrame()

        frames: list[pl.DataFrame] = []
        for parameter in parameters:
            element_config = config["elements"].get(parameter.name_original)
            if element_config is None:
                continue
            frames.extend(self._collect_element(station_id, parameter.name_original, element_config, config, settings))
        if not frames:
            return pl.DataFrame()

        # the station, resolution and dataset are the core's to write (`shape_provider_frame`)
        return pl.concat(frames)


@dataclass
class ChmiObservationRequest(TimeseriesRequest):
    """Request class for CHMI (Czech Hydrometeorological Institute) observation data."""

    metadata = ChmiObservationMetadata
    _values = ChmiObservationValues

    _endpoint: ClassVar[str] = f"{_BASE_URL}/metadata/meta1.csv"

    def _all(self) -> pl.LazyFrame:
        settings = cast("Settings", self.settings)
        file = download_file(
            url=self._endpoint,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        # the catalogue is one required file, so any failure of it -- a 404 included -- is an outage,
        # which swallowed would read as a network without stations (GH-2519). A failed connection
        # (NoInternetError) is raised as well (GH-2640)
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.LazyFrame()
        catalogue = parse_chmi_stations(file.content.read())
        if catalogue.is_empty():
            return pl.LazyFrame()
        # `meta1.csv` is one list for every resolution and element, and lists stations that have no file of the
        # requested ones (GH-3259, GH-3295): the daily, monthly and annual stations are narrowed to those whose files
        # of the requested parameters the directories list. The sub-daily files are one for each month, under a
        # directory for each year (a listing of every year, 1.6 MB each, for every request), so the 10 minute and
        # hourly stations stay the whole list.
        frames = []
        for dataset, parameters in group_parameters_by_dataset(
            parameter for parameter in self.parameters if isinstance(parameter, ParameterModel)
        ):
            config = _RESOLUTION_CONFIG[dataset.resolution.value]
            stations = catalogue
            if config["layout"] != "subdaily":
                with_file = _stations_with_file(config, {parameter.name_original for parameter in parameters}, settings)
                stations = stations.filter(pl.col("station_id").is_in(with_file))
            frames.append(
                stations.with_columns(
                    pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
                    pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
                )
            )
        return pl.concat(frames).lazy() if frames else pl.LazyFrame()
