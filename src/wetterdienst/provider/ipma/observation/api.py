# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""IPMA (Instituto Português do Mar e da Atmosfera) observation provider.

IPMA publishes near-real-time hourly observations from its Portuguese automatic station network as
two key-less JSON feeds: a station catalogue (``stations.json``, a GeoJSON FeatureCollection) and a
single all-stations observation feed (``observations.json``) holding roughly the last day of hourly
readings. Only the ``recent`` period exists; there is no historical archive.

See ``metadata.py`` for the field/unit background and ``parser.py`` for the (wind-direction code,
``-99`` sentinel) handling.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import DatasetModel, ParameterModel
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.ipma.observation.metadata import IpmaObservationMetadata
from wetterdienst.provider.ipma.observation.parser import parse_ipma_observations, parse_ipma_stations
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

_BASE_URL = "https://api.ipma.pt/open-data/observation/meteorology/stations"
_STATIONS_URL = f"{_BASE_URL}/stations.json"
_OBSERVATIONS_URL = f"{_BASE_URL}/observations.json"

_EMPTY_VALUES_SCHEMA = {
    "resolution": pl.String,
    "dataset": pl.String,
    "parameter": pl.String,
    "station_id": pl.String,
    "date": pl.Datetime(time_unit="us", time_zone="UTC"),
    "value": pl.Float64,
    "quality": pl.Float64,
}


class IpmaObservationValues(TimeseriesValues):
    """Values class for IPMA observation data."""

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel | DatasetModel,
    ) -> pl.DataFrame:
        if isinstance(parameter_or_dataset, ParameterModel):
            dataset = parameter_or_dataset.dataset
        elif isinstance(parameter_or_dataset, DatasetModel):
            dataset = parameter_or_dataset
        else:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        settings = cast("Settings", self.sr.stations.settings)
        # one all-stations feed serves every station; a five-minute cache means the concurrent
        # per-station queries in a rank loop download it once.
        file = download_file(
            url=_OBSERVATIONS_URL,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.FIVE_MINUTES,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        if isinstance(file.content, Exception):
            if not file.is_no_internet_error:
                log.warning(f"Failed to fetch IPMA observations: {file.content}")
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
        df = parse_ipma_observations(file.content.read(), station_id=station_id)
        if df.is_empty():
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
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
class IpmaObservationRequest(TimeseriesRequest):
    """Request class for IPMA (Instituto Português do Mar e da Atmosfera) observation data."""

    metadata = IpmaObservationMetadata
    _values = IpmaObservationValues

    def _all(self) -> pl.LazyFrame:
        settings = cast("Settings", self.settings)
        file = download_file(
            url=_STATIONS_URL,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        if isinstance(file.content, Exception):
            log.warning(f"Failed to fetch IPMA station catalogue: {file.content}")
            return pl.LazyFrame()
        stations = parse_ipma_stations(file.content.read())
        if stations.is_empty():
            return pl.LazyFrame()
        # the catalogue is provider-wide; tag it with the single (resolution, dataset). Columns the
        # catalogue omits (height, start_date, end_date, state) are null-filled by all().
        resolution = self.metadata[0]
        return stations.with_columns(
            pl.lit(resolution.name, pl.String).alias("resolution"),
            pl.lit(resolution.datasets[0].name, pl.String).alias("dataset"),
        ).lazy()
