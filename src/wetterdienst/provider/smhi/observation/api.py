# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""SMHI (Sweden) observation data provider."""

from __future__ import annotations

import json
import logging
from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import polars as pl

from wetterdienst.exceptions import NoInternetError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.metadata import DatasetModel, ParameterModel
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.smhi.observation.metadata import SmhiObservationMetadata
from wetterdienst.provider.smhi.observation.parser import parse_smhi_csv
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from wetterdienst.settings import Settings
    from wetterdienst.util.network import File

log = logging.getLogger(__name__)

_BASE_URL = "https://opendata-download-metobs.smhi.se/api/version/1.0"

# SMHI splits history into two periods that overlap by design: "corrected-archive" is
# quality-controlled data up to ~3 months ago, "latest-months" covers the last ~4 months
# (still under QC), so the two share roughly a month. Both are fetched and merged --
# de-duplicating the overlap (see _collect_parameter) -- so a request spanning the boundary
# gets complete coverage without needing to guess which period a given date range falls into.
# Minute-resolution data is different: SMHI only exposes a short rolling window for it
# (no historical archive at all), via "latest-day" instead.
_PERIODS_BY_RESOLUTION = {
    Resolution.MINUTE_1: ("latest-day",),
    Resolution.HOURLY: ("corrected-archive", "latest-months"),
    Resolution.DAILY: ("corrected-archive", "latest-months"),
    Resolution.MONTHLY: ("corrected-archive", "latest-months"),
}

_EMPTY_VALUES_SCHEMA = {
    "resolution": pl.String,
    "dataset": pl.String,
    "parameter": pl.String,
    "station_id": pl.String,
    "date": pl.Datetime(time_unit="us", time_zone="UTC"),
    "value": pl.Float64,
    "quality": pl.Float64,
}


def _fetch(url: str, settings: Settings, ttl: CacheExpiry = CacheExpiry.FIVE_MINUTES) -> bytes | Exception:
    """Download an SMHI resource (CSV data or the station-list JSON), returning bytes or the error.

    Callers decide how to treat failures -- e.g. _collect_parameter suppresses a 404 (station
    doesn't report the parameter) as routine, while _all logs a station-list failure -- and set
    the cache TTL (short for rolling value data, long for the station registry).
    """
    file: File = download_file(
        url=url,
        cache_dir=settings.cache_dir,
        ttl=ttl,
        client_kwargs=settings.fsspec_client_kwargs,
        cache_disable=settings.cache_disable,
        use_certifi=settings.use_certifi,
    )
    if isinstance(file.content, Exception):
        return file.content
    return file.content.read()


class SmhiObservationValues(TimeseriesValues):
    """Values class for SMHI observation data."""

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel | DatasetModel,
    ) -> pl.DataFrame:
        if isinstance(parameter_or_dataset, DatasetModel):
            parameters = parameter_or_dataset.parameters
        elif isinstance(parameter_or_dataset, ParameterModel):
            parameters = [parameter_or_dataset]
        else:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        settings = cast("Settings", self.sr.stations.settings)
        data = []
        for parameter in parameters:
            df = self._collect_parameter(station_id, parameter, settings)
            if not df.is_empty():
                data.append(df)
        if not data:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
        return pl.concat(data)

    def _collect_parameter(self, station_id: str, parameter: ParameterModel, settings: Settings) -> pl.DataFrame:
        periods = _PERIODS_BY_RESOLUTION[parameter.dataset.resolution.value]
        frames = []
        for period in periods:
            url = f"{_BASE_URL}/parameter/{parameter.name_original}/station/{station_id}/period/{period}/data.csv"
            payload = _fetch(url, settings)
            if isinstance(payload, Exception):
                # a 404 (FileNotFoundError) just means this station doesn't report this
                # parameter -- routine, since not every SMHI station measures everything -- and
                # a NoInternetError is already logged at debug upstream. Anything else is an
                # unexpected failure worth surfacing rather than silently dropping the data.
                if not isinstance(payload, (FileNotFoundError, NoInternetError)):
                    log.warning(
                        f"Failed to fetch SMHI parameter {parameter.name_original} for station {station_id}: {payload}",
                    )
                continue
            try:
                df = parse_smhi_csv(payload.decode("utf-8-sig"))
            except Exception as exc:  # noqa: BLE001
                # a single malformed CSV block shouldn't abort the whole (multi-station,
                # multi-parameter) query -- skip it and keep going.
                log.warning(
                    f"Failed to parse SMHI CSV for parameter {parameter.name_original} "
                    f"station {station_id} period {period}: {exc}",
                )
                continue
            if not df.is_empty():
                frames.append(df)
        if not frames:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        df = pl.concat(frames)
        # when periods overlap by design (corrected-archive/latest-months), keep one row per
        # timestamp. corrected-archive is the finalized quality-controlled version and is
        # fetched (and appended) first, so keep="first" prefers it over the still-under-QC
        # latest-months value; maintain_order=True makes that deterministic.
        df = df.unique(subset="date", keep="first", maintain_order=True)
        return df.select(
            pl.lit(parameter.dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(parameter.dataset.name, dtype=pl.String).alias("dataset"),
            pl.lit(parameter.name_original, dtype=pl.String).alias("parameter"),
            pl.lit(station_id, dtype=pl.String).alias("station_id"),
            pl.col("date"),
            pl.col("value").cast(pl.Float64, strict=False),
            pl.lit(None, pl.Float64).alias("quality"),
        )


@dataclass
class SmhiObservationRequest(TimeseriesRequest):
    """Request class for SMHI observation data."""

    metadata = SmhiObservationMetadata
    _values = SmhiObservationValues

    def _all(self) -> pl.LazyFrame:
        settings = cast("Settings", self.settings)
        # SMHI publishes the station list per parameter (parameter/<id>.json), and station
        # coverage differs by parameter (not every station reporting e.g. snow depth also
        # reports temperature). Fetch each requested parameter's own station list and union
        # them per (resolution, dataset), rather than using a single reference parameter that
        # would omit stations measuring the requested parameter but not the reference. The
        # registry is metadata, so it's cached at the long METAINDEX TTL.
        frames_by_group: defaultdict[tuple[str, str], list[pl.DataFrame]] = defaultdict(list)
        for parameter in self.parameters:
            if not isinstance(parameter, ParameterModel):
                continue
            url = f"{_BASE_URL}/parameter/{parameter.name_original}.json"
            payload = _fetch(url, settings, ttl=CacheExpiry.METAINDEX)
            if isinstance(payload, Exception):
                log.warning(f"Failed to fetch SMHI stations for parameter {parameter.name_original}: {payload}")
                continue
            stations = json.loads(payload.decode("utf-8-sig")).get("station", [])
            if not stations:
                continue
            df = pl.DataFrame(stations).select(
                pl.lit(parameter.dataset.resolution.name, dtype=pl.String).alias("resolution"),
                pl.lit(parameter.dataset.name, dtype=pl.String).alias("dataset"),
                pl.col("id").cast(pl.String).alias("station_id"),
                pl.from_epoch("from", time_unit="ms").dt.replace_time_zone("UTC").alias("start_date"),
                pl.from_epoch("to", time_unit="ms").dt.replace_time_zone("UTC").alias("end_date"),
                pl.col("latitude").cast(pl.Float64),
                pl.col("longitude").cast(pl.Float64),
                pl.col("height").cast(pl.Float64),
                pl.col("name").cast(pl.String),
            )
            frames_by_group[(parameter.dataset.resolution.name, parameter.dataset.name)].append(df)
        # collapse the per-parameter station lists to one row per station within each group,
        # spanning the full reporting range (earliest start, latest end) across the requested
        # parameters at that station.
        data = [
            pl.concat(frames)
            .group_by("station_id")
            .agg(
                pl.col("resolution").first(),
                pl.col("dataset").first(),
                pl.col("start_date").min(),
                pl.col("end_date").max(),
                pl.col("latitude").first(),
                pl.col("longitude").first(),
                pl.col("height").first(),
                pl.col("name").first(),
            )
            for frames in frames_by_group.values()
        ]
        if not data:
            return pl.LazyFrame()
        return pl.concat(data).lazy()
