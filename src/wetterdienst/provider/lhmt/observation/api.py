# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""LHMT (Lietuvos hidrometeorologijos tarnyba) observation provider.

LHMT publishes hourly observations from its Lithuanian station network through the key-less
``api.meteo.lt`` JSON REST API: a station list (``/v1/stations``) and per-station, per-day
observation days (``/v1/stations/{code}/observations/{YYYY-MM-DD}``). History reaches back to
roughly 2016.

See ``metadata.py`` for the field/unit background and ``parser.py`` for the response shapes.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import DatasetModel, ParameterModel
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.lhmt.observation.metadata import LhmtObservationMetadata
from wetterdienst.provider.lhmt.observation.parser import parse_lhmt_observations, parse_lhmt_stations
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from collections.abc import Iterator

    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

_BASE_URL = "https://api.meteo.lt/v1"
_STATIONS_URL = f"{_BASE_URL}/stations"

_EMPTY_VALUES_SCHEMA = {
    "resolution": pl.String,
    "dataset": pl.String,
    "parameter": pl.String,
    "station_id": pl.String,
    "date": pl.Datetime(time_unit="us", time_zone="UTC"),
    "value": pl.Float64,
    "quality": pl.Float64,
}


def _days(start: dt.datetime, end: dt.datetime) -> Iterator[dt.date]:
    """Yield each UTC calendar date in ``[start, end]`` inclusive (observation days are UTC)."""
    day = start.astimezone(dt.timezone.utc).date()
    last = end.astimezone(dt.timezone.utc).date()
    while day <= last:
        yield day
        day += dt.timedelta(days=1)


class LhmtObservationValues(TimeseriesValues):
    """Values class for LHMT observation data."""

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

        # the per-day endpoint requires a date range to address the days to fetch
        if not self.sr.start_date or not self.sr.end_date:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        settings = cast("Settings", self.sr.stations.settings)
        frames = []
        for day in _days(self.sr.start_date, self.sr.end_date):
            content = self._download_day(station_id, day, settings)
            if content is None:
                continue
            df = parse_lhmt_observations(content)
            if not df.is_empty():
                frames.append(df)
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

    def _download_day(self, station_id: str, day: dt.date, settings: Settings) -> bytes | None:
        url = f"{_BASE_URL}/stations/{station_id}/observations/{day.isoformat()}"
        # a settled past day is immutable, so it can be cached indefinitely; only the current (still
        # filling) day needs a short cache. This keeps repeated historical queries off the network
        # and well under the api.meteo.lt request-rate limit.
        ttl = CacheExpiry.FIVE_MINUTES if day >= dt.datetime.now(dt.timezone.utc).date() else CacheExpiry.INFINITE
        file = download_file(
            url=url,
            cache_dir=settings.cache_dir,
            ttl=ttl,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        # a day before the station's record has no file, which is a 404 and routine; an outage
        # is not, and used to contribute no rows in exactly the same way
        file.raise_unless_absent()
        if isinstance(file.content, Exception):
            if not file.is_no_internet_error:
                log.debug(f"No LHMT data for {station_id} on {day}: {file.content}")
            return None
        return file.content.read()


@dataclass
class LhmtObservationRequest(TimeseriesRequest):
    """Request class for LHMT (Lietuvos hidrometeorologijos tarnyba) observation data."""

    metadata = LhmtObservationMetadata
    _values = LhmtObservationValues

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
        # a catalogue that failed to download is not an empty catalogue -- returning one
        # turns an outage into "this provider has no stations", which no caller can tell
        # apart from the real thing. Only a missing connection stays soft.
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            log.warning("No internet connection while fetching the LHMT station catalogue")
            return pl.LazyFrame()
        stations = parse_lhmt_stations(file.content.read())
        if stations.is_empty():
            return pl.LazyFrame()
        resolution = self.metadata[0]
        return stations.with_columns(
            pl.lit(resolution.name, pl.String).alias("resolution"),
            pl.lit(resolution.datasets[0].name, pl.String).alias("dataset"),
        ).lazy()
