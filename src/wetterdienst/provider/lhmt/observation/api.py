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
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.lhmt.observation.metadata import LhmtObservationMetadata
from wetterdienst.provider.lhmt.observation.parser import parse_lhmt_observations, parse_lhmt_stations
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from collections.abc import Iterator

    from wetterdienst.model.metadata import DatasetModel, ParameterModel
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

_BASE_URL = "https://api.meteo.lt/v1"
_STATIONS_URL = f"{_BASE_URL}/stations"


def _days(start: dt.datetime, end: dt.datetime) -> Iterator[dt.date]:
    """Yield each UTC calendar date in ``[start, end]`` inclusive.

    Observation days are UTC, the zone of the request's bounds, so the bounds' dates are the days.
    """
    day = start.date()
    last = end.date()
    while day <= last:
        yield day
        day += dt.timedelta(days=1)


class LhmtObservationValues(TimeseriesValues):
    """Values class for LHMT observation data."""

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel | DatasetModel,  # noqa: ARG002
    ) -> pl.DataFrame:
        # the per-day endpoint requires a date range to address the days to fetch
        if not self.sr.start or not self.sr.end:
            return pl.DataFrame()

        settings = cast("Settings", self.sr.request.settings)
        frames = []
        for day in _days(self.sr.start, self.sr.end):
            content = self._download_day(station_id, day, settings)
            if content is None:
                continue
            df = parse_lhmt_observations(content)
            if not df.is_empty():
                frames.append(df)
        return pl.concat(frames) if frames else pl.DataFrame()

    def _download_day(self, station_id: str, day: dt.date, settings: Settings) -> bytes | None:
        url = f"{_BASE_URL}/stations/{station_id}/observations/{day.isoformat()}"
        # a settled past day is immutable, so it can be cached indefinitely; only the current (still
        # filling) day needs a short cache. This keeps repeated historical queries off the network
        # and well under the api.meteo.lt request-rate limit.
        ttl = CacheExpiry.FIVE_MINUTES if day >= dt.datetime.now(dt.UTC).date() else CacheExpiry.INFINITE
        file = download_file(
            url=url,
            cache_dir=settings.cache_dir,
            ttl=ttl,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        # a day before the station's record is a 404 and simply contributes no rows; any other
        # failure -- a timeout, a 5xx after the retries -- is an outage, which swallowed would read as
        # a day without observations (GH-2461). A failed connection raises at the first day, so that
        # the request does not wait for the connection to fail once per remaining day (GH-2620, GH-2640)
        if file.status != 404:
            file.raise_if_exception()
        if isinstance(file.content, Exception):
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
        # the catalogue is one required file, so any failure of it -- a 404 included -- is an outage,
        # which swallowed would read as a network without stations (GH-2519). A failed connection
        # (NoInternetError) is raised as well (GH-2640)
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.LazyFrame()
        # the catalogue is provider-wide; the core tags it with the single (resolution, dataset)
        return parse_lhmt_stations(file.content.read()).lazy()
