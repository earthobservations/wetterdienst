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
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.metadata import DatasetModel, ParameterModel
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.chmi.observation.metadata import ChmiObservationMetadata
from wetterdienst.provider.chmi.observation.parser import (
    parse_chmi_stations,
    parse_chmi_values_aggregate,
    parse_chmi_values_daily,
    parse_chmi_values_subdaily,
)
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Iterator

    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

_UTC = ZoneInfo("UTC")
_BASE_URL = "https://opendata.chmi.cz/meteorology/climate/historical_csv"

_EMPTY_VALUES_SCHEMA = {
    "resolution": pl.String,
    "dataset": pl.String,
    "parameter": pl.String,
    "station_id": pl.String,
    "date": pl.Datetime(time_unit="us", time_zone="UTC"),
    "value": pl.Float64,
    "quality": pl.Float64,
}

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
        if isinstance(file.content, Exception):
            # a station that does not measure an element (or has no data for a month) has no file
            if not file.is_no_internet_error:
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
            # the month files are named by UTC calendar month; normalise so a tz-aware, non-UTC
            # request date near a month boundary still selects the correct file
            start = cast("dt.datetime", self.sr.start_date).astimezone(_UTC)
            end = cast("dt.datetime", self.sr.end_date).astimezone(_UTC)
            for year, month in _months(start, end):
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
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        settings = cast("Settings", self.sr.stations.settings)
        config = _RESOLUTION_CONFIG[dataset.resolution.value]
        # the sub-daily files are partitioned by month, so a date range is required to address them
        if config["layout"] == "subdaily" and (not self.sr.start_date or not self.sr.end_date):
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        frames: list[pl.DataFrame] = []
        for parameter in parameters:
            element_config = config["elements"].get(parameter.name_original)
            if element_config is None:
                continue
            frames.extend(self._collect_element(station_id, parameter.name_original, element_config, config, settings))
        if not frames:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        df = pl.concat(frames)
        return df.select(
            pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            pl.col("parameter"),
            pl.lit(station_id, dtype=pl.String).alias("station_id"),
            pl.col("date"),
            pl.col("value"),
            pl.lit(None, dtype=pl.Float64).alias("quality"),
        )


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
        if isinstance(file.content, Exception):
            log.warning(f"Failed to fetch CHMI station catalogue: {file.content}")
            return pl.LazyFrame()
        stations = parse_chmi_stations(file.content.read())
        if stations.is_empty():
            return pl.LazyFrame()

        # the catalogue is provider-wide; replicate it across each requested (resolution, dataset)
        # so stations not reporting a requested parameter simply return no values.
        resolutions_and_datasets = {
            (parameter.dataset.resolution.name, parameter.dataset.name)
            for parameter in self.parameters
            if isinstance(parameter, ParameterModel)
        }
        if not resolutions_and_datasets:
            return pl.LazyFrame()
        data = [
            stations.with_columns(
                pl.lit(resolution, pl.String).alias("resolution"),
                pl.lit(dataset, pl.String).alias("dataset"),
            )
            for resolution, dataset in resolutions_and_datasets
        ]
        # TimeseriesRequest.all() selects _base_columns and fills any the catalogue omits (state)
        # with null, so no explicit padding is needed here.
        return pl.concat(data).lazy()
