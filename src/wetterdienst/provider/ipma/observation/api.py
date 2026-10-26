# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""IPMA (Instituto Português do Mar e da Atmosfera) observation provider.

IPMA publishes near-real-time hourly observations from its Portuguese automatic station network as
two key-less JSON feeds: a station catalogue (``stations.json``, a bare array of GeoJSON Feature objects) and a
single all-stations observation feed (``observations.json``) holding roughly the last day of hourly
readings. Only the ``recent`` period exists; there is no historical archive.

See ``metadata.py`` for the field/unit background and ``parser.py`` for the (wind-direction code,
``-99`` sentinel) handling.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.ipma.observation.metadata import IpmaObservationMetadata
from wetterdienst.provider.ipma.observation.parser import (
    extract_ipma_station_observations,
    parse_ipma_observations_feed,
    parse_ipma_stations,
)
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from wetterdienst.model.metadata import DatasetModel, ParameterModel
    from wetterdienst.settings import Settings

_BASE_URL = "https://api.ipma.pt/open-data/observation/meteorology/stations"
_STATIONS_URL = f"{_BASE_URL}/stations.json"
_OBSERVATIONS_URL = f"{_BASE_URL}/observations.json"


class IpmaObservationValues(TimeseriesValues):
    """Values class for IPMA observation data."""

    def _observations_feed(self) -> dict | None:
        """Download and deserialise the all-stations feed once, memoised on the values instance.

        A single ``observations.json`` holds every station, so parsing it per station (once per
        ``_collect_station_parameter_or_dataset`` call in a rank loop) would re-run ``json.loads`` over
        the whole payload N times. The parsed feed is cached here so it is deserialised exactly once
        per query. A failure to fetch the feed raises, a failed connection (``NoInternetError``) included
        (GH-2640), and is not cached, so that it is attempted again.
        """
        cached = getattr(self, "_feed_cache", None)
        if cached is not None:
            return cached
        settings = cast("Settings", self.sr.request.settings)
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
        # one feed holds every station, so any failure of it -- a 404 included -- is an outage, not
        # a station without data, and is raised (GH-2461), a failed connection (NoInternetError) too
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return None
        feed = parse_ipma_observations_feed(file.content.read())
        self._feed_cache = feed
        # when IPMA last wrote the feed, which every station of the query is read from (GH-2567)
        self._feed_written = file.last_modified
        return feed

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel | DatasetModel,  # noqa: ARG002
    ) -> pl.DataFrame:
        feed = self._observations_feed()
        if feed is None:
            return pl.DataFrame()
        df = extract_ipma_station_observations(feed, station_id=station_id)
        if not df.is_empty():
            self._note_data_updated(getattr(self, "_feed_written", None))
        return df


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
        # the catalogue is one required file, so any failure of it -- a 404 included -- is an outage,
        # which swallowed would read as a network without stations (GH-2519). A failed connection
        # (NoInternetError) is raised as well (GH-2640)
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.LazyFrame()
        # the catalogue is provider-wide; the core tags it with the single (resolution, dataset)
        return parse_ipma_stations(file.content.read()).lazy()
