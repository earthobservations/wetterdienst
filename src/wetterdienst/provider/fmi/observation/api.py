# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""FMI (Finnish Meteorological Institute) observation provider.

FMI publishes open weather-observation data through a key-less WFS service. Station metadata
comes from the ``fmi::ef::stations`` stored query (INSPIRE EF catalogue); observations come
from the ``fmi::observations::weather::simple`` (sub-daily) and
``fmi::observations::weather::daily::simple`` (daily) stored queries, filtered by ``fmisid``,
``parameters`` and a ``starttime``/``endtime`` window.

See https://en.ilmatieteenlaitos.fi/open-data-manual and
https://en.ilmatieteenlaitos.fi/observation-stations.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, cast
from urllib.parse import urlencode

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.metadata import DatasetModel, ParameterModel
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.fmi.observation.metadata import FmiObservationMetadata
from wetterdienst.provider.fmi.observation.parser import (
    extract_exception_text,
    parse_fmi_observations,
    parse_fmi_stations,
)
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from collections.abc import Iterator

    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

_BASE_URL = "https://opendata.fmi.fi/wfs"

# The station catalogue does not vary by parameter, so a single stored query covers every
# resolution/dataset (mirroring DMI).
_STATIONS_QUERY = "fmi::ef::stations"

# FMI caps a single observation request's time span (sub-daily queries reject spans over 168
# hours outright); daily queries are not capped in practice but are chunked too for safety on
# multi-decade ranges. Consecutive windows share their boundary timestamp and the result is
# de-duplicated, so no observation is lost regardless of FMI's endtime inclusivity.
_RESOLUTION_CONFIG: dict[Resolution, dict[str, object]] = {
    Resolution.HOURLY: {
        "stored_query_id": "fmi::observations::weather::simple",
        "timestep": "60",
        "window": dt.timedelta(hours=168),
    },
    Resolution.DAILY: {
        "stored_query_id": "fmi::observations::weather::daily::simple",
        "timestep": None,
        "window": dt.timedelta(days=365),
    },
}


def _time_windows(
    start: dt.datetime,
    end: dt.datetime,
    window: dt.timedelta,
) -> Iterator[tuple[dt.datetime, dt.datetime]]:
    """Split ``[start, end]`` into ``(start, end)`` windows no longer than ``window``.

    Consecutive windows share their boundary timestamp -- the next window restarts at the
    previous window's ``stop`` rather than one step past it -- so an observation lying exactly on
    a boundary is fetched whether FMI treats ``endtime`` as inclusive or exclusive. The caller
    de-duplicates the shared boundary row.
    """
    cursor = start
    while cursor <= end:
        stop = min(cursor + window, end)
        yield cursor, stop
        if stop >= end:
            break
        cursor = stop


class FmiObservationValues(TimeseriesValues):
    """Values class for FMI observation data."""

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel | DatasetModel,
    ) -> pl.DataFrame:
        if isinstance(parameter_or_dataset, DatasetModel):
            dataset = parameter_or_dataset
        elif isinstance(parameter_or_dataset, ParameterModel):
            dataset = parameter_or_dataset.dataset
        else:
            return pl.DataFrame()

        settings = cast("Settings", self.sr.request.settings)
        start_date = self.sr.start
        end_date = self.sr.end
        if not start_date or not end_date:
            return pl.DataFrame()

        resolution = dataset.resolution.value
        config = _RESOLUTION_CONFIG[resolution]
        # FMI returns every requested parameter in one response, so ask for the whole dataset at
        # once; the raw `parameter` column then holds each parameter's name_original.
        parameter_codes = ",".join(parameter.name_original for parameter in dataset.parameters)

        frames = []
        for window_start, window_end in _time_windows(
            start_date,
            end_date,
            cast("dt.timedelta", config["window"]),
        ):
            df = self._collect_window(
                station_id=station_id,
                parameter_codes=parameter_codes,
                stored_query_id=cast("str", config["stored_query_id"]),
                timestep=cast("str | None", config["timestep"]),
                start=window_start,
                end=window_end,
                settings=settings,
            )
            if not df.is_empty():
                frames.append(df)
        if not frames:
            return pl.DataFrame()

        df = pl.concat(frames)
        # consecutive windows share their boundary timestamp (see _time_windows), so drop the
        # duplicate boundary row -- keep="first" retains the earlier window's copy.
        # the station, resolution and dataset are the core's to write (`shape_provider_frame`)
        return df.unique(subset=["parameter", "timestamp"], keep="first", maintain_order=True)

    def _collect_window(
        self,
        station_id: str,
        parameter_codes: str,
        stored_query_id: str,
        timestep: str | None,
        start: dt.datetime,
        end: dt.datetime,
        settings: Settings,
    ) -> pl.DataFrame:
        query = {
            "service": "WFS",
            "version": "2.0.0",
            "request": "getFeature",
            "storedquery_id": stored_query_id,
            "fmisid": station_id,
            "parameters": parameter_codes,
            "starttime": start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "endtime": end.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        if timestep is not None:
            query["timestep"] = timestep
        url = f"{_BASE_URL}?{urlencode(query)}"
        file = download_file(
            url=url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.FIVE_MINUTES,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        # a station reporting no data for a window yields an empty (200) response, so a failure here
        # is a real transport/HTTP one, a 404 included, and is raised: swallowed it read as a station
        # without data (GH-2461). The exception is the 400 "Unknown 'fmisid' value!" that FMI answers
        # for a few stations of its own catalogue, which have no data and are warned about. Any 400
        # is dropped, since the status is all this sees: FMI answers 400 as well for a stored query or
        # parameter it no longer has, which the warning is then the only sign of. A failed
        # connection (NoInternetError) is raised, as any other failure.
        if file.status != 400:
            file.raise_if_exception()
        if isinstance(file.content, Exception):
            log.warning(f"Failed to fetch FMI data for station {station_id}: {file.content}")
            return pl.DataFrame()
        content = file.content.read()
        df = parse_fmi_observations(content)
        # an empty result is normally a station reporting no data; distinguish a genuine server
        # error (returned as an ExceptionReport with HTTP 200) so it is not silently swallowed.
        if df.is_empty() and b"ExceptionReport" in content:
            log.warning(f"FMI returned an exception for station {station_id}: {extract_exception_text(content)}")
        return df


@dataclass
class FmiObservationRequest(TimeseriesRequest):
    """Request class for FMI (Finnish Meteorological Institute) observation data."""

    metadata = FmiObservationMetadata
    _values = FmiObservationValues

    _endpoint: ClassVar[str] = f"{_BASE_URL}?" + urlencode(
        {
            "service": "WFS",
            "version": "2.0.0",
            "request": "getFeature",
            "storedquery_id": _STATIONS_QUERY,
        },
    )

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
        # the catalogue is provider-wide; the core copies it across each requested (resolution, dataset)
        # so stations not reporting a requested parameter simply return no values.
        return parse_fmi_stations(file.content.read()).lazy()
