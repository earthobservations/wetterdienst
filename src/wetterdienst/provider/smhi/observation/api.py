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

from wetterdienst.exceptions import DownloadError, NoInternetError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.metadata import DatasetModel, ParameterModel
from wetterdienst.model.quality_flags import Sentinel, join_quality_flags, null_sentinels
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.smhi.observation.metadata import SmhiObservationMetadata
from wetterdienst.provider.smhi.observation.parser import parse_smhi_csv
from wetterdienst.util.network import as_outage, download_file, download_files

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

# SMHI writes a wind direction of 0 for a calm wind and north as 360. The hourly direction (parameter 3, a 10 minute
# mean) of stations 188790, 97400 and 71420 from 1985 (read 2026-10-12) reads 0 in 4879, 10,495 and 19,717 hours, of
# which 4864, 9869 and 19,713 have a wind speed of 0 (parameter 4) and the rest 1 to 3 m/s (2008 to 2013 at 97400, 1989
# at the others), falling with the speed (443, 138 and 10 hours at 1, 2 and 3 m/s at 97400) where a bearing would stay
# flat; 464, 4818 and 1358 hours read 360. The 1 minute direction (parameter 48) is a mean of the minute and exactly
# 0.000000 in the 49, 327, 46 and 233 minutes of 188790, 159880, 71420 and 92410 whose speed (parameter 47) is 0.000000,
# and in no other. SMHI documents neither, but a 0 is no bearing there, so it is null (GH-2794).
_WIND_DIRECTION_NOT_GIVEN = Sentinel("0")

# The total cloud cover (parameter 16, percent) is the oktas 0 to 8 written as 0, 13, 25, 38, 50, 63, 75, 88 and
# 100, and 113 for the 9 of an obscured sky: "Kod 9 används vid till exempel dimma och högt snödrev då molnen inte
# kan observeras" and "Kod 9 sätts till då 112,5%" (https://www.smhi.se/kunskapsbanken/meteorologi/moln/hur-mats-molnighet).
# The open data documentation does not describe it, but station 182910 reads 113 in 427 of 3,140 hours of
# `latest-months` and 140460 in 20 of 3,127 (read 2026-10-18), all with the quality `G`. It is no amount of cloud, so
# it is null (GH-3122).
_CLOUD_COVER_SKY_OBSCURED = Sentinel("113")
_CLOUD_COVER_PARAMETER = "16"

_EMPTY_VALUES_SCHEMA = {
    "resolution": pl.String,
    "dataset": pl.String,
    "parameter": pl.String,
    "station_id": pl.String,
    "timestamp": pl.Datetime(time_unit="us", time_zone="UTC"),
    "value": pl.Float64,
    "quality_flags": pl.String,
}


def _fetch(url: str, settings: Settings, ttl: CacheExpiry = CacheExpiry.FIVE_MINUTES) -> bytes | Exception:
    """Download an SMHI resource (CSV data or the station-list JSON), returning bytes or the error.

    Callers decide how to treat failures -- e.g. _collect_parameter suppresses a 404 (station
    doesn't report the parameter) as routine -- and set the cache TTL (short for rolling value
    data, long for the station registry).
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

        settings = cast("Settings", self.sr.request.settings)
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
                # parameter -- routine, since not every SMHI station measures everything. A failed
                # connection is raised (GH-2640): every later request would fail the same way, and
                # an outage must not read as a station without data. Nor must a timeout, a dropped
                # connection, a body cut short or a 5xx, which are raised as the `DownloadError`
                # they are (GH-2965). Any other failure is an unexpected answer worth surfacing
                # rather than silently dropping the data.
                failure = as_outage(payload, url)
                if isinstance(failure, (NoInternetError, DownloadError)):
                    raise failure
                if not isinstance(payload, FileNotFoundError):
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
        if parameter.dataset.resolution.value == Resolution.DAILY:
            # A daily value is stamped at 00:00 UTC of the day it names. Snow depth is the one daily file with a
            # 'Tid (UTC)' column, '06:00:00' for "momentanvärde, 1 gång/dygn, kl 06" (an instantaneous value once a
            # day at 06), and so came at 06:00 UTC besides the others at 00:00, which a request for that one day
            # dropped (GH-2683). The reading of 06:00 UTC on a date belongs to that date.
            df = df.with_columns(pl.col("timestamp").dt.truncate("1d"))
        # when periods overlap by design (corrected-archive/latest-months), keep one row per
        # timestamp. corrected-archive is the finalized quality-controlled version and is
        # fetched (and appended) first, so keep="first" prefers it over the still-under-QC
        # latest-months value; maintain_order=True makes that deterministic.
        df = df.unique(subset="timestamp", keep="first", maintain_order=True)
        # the 0 of a wind direction and the 113 of a cloud cover are mapped before the value is read as a number, and
        # stay as a `raw:` token
        sentinels = (_WIND_DIRECTION_NOT_GIVEN,) if parameter.name.startswith("wind_direction") else ()
        if parameter.name_original == _CLOUD_COVER_PARAMETER:
            sentinels = (_CLOUD_COVER_SKY_OBSCURED,)
        value, raw = null_sentinels(pl.col("value"), *sentinels)
        return df.select(
            pl.lit(parameter.dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(parameter.dataset.name, dtype=pl.String).alias("dataset"),
            pl.lit(parameter.name_original, dtype=pl.String).alias("parameter"),
            pl.lit(station_id, dtype=pl.String).alias("station_id"),
            pl.col("timestamp"),
            value.cast(pl.Float64, strict=False).alias("value"),
            join_quality_flags(pl.col("quality_flags"), raw=raw),
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
        # registry is metadata, so it's cached at the long METAINDEX TTL. The per-parameter
        # station lists are independent, so fetch them concurrently.
        parameters = [parameter for parameter in self.parameters if isinstance(parameter, ParameterModel)]
        if not parameters:
            return pl.LazyFrame()
        files = download_files(
            urls=[f"{_BASE_URL}/parameter/{parameter.name_original}.json" for parameter in parameters],
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        # each parameter's station list is required, so any failure of one -- a 404 included -- is an
        # outage, which swallowed would read as a parameter without stations, and the rest would
        # answer as a catalogue that is partial (GH-2599). A failed connection (NoInternetError) is
        # raised as well (GH-2640)
        for file in files:
            file.raise_if_exception()
        frames_by_group: defaultdict[tuple[str, str], list[pl.DataFrame]] = defaultdict(list)
        for parameter, file in zip(parameters, files, strict=True):
            if isinstance(file.content, Exception):
                # narrows the type; `raise_if_exception` has raised for any failed download
                msg = str(file.content) or type(file.content).__name__
                raise DownloadError(file.url, msg) from file.content
            stations = json.loads(file.content.read().decode("utf-8-sig")).get("station", [])
            if not stations:
                continue
            df = pl.DataFrame(stations).select(
                pl.lit(parameter.dataset.resolution.name, dtype=pl.String).alias("resolution"),
                pl.lit(parameter.dataset.name, dtype=pl.String).alias("dataset"),
                pl.col("id").cast(pl.String).alias("station_id"),
                pl.from_epoch("from", time_unit="ms").dt.replace_time_zone("UTC").alias("start_timestamp"),
                pl.from_epoch("to", time_unit="ms").dt.replace_time_zone("UTC").alias("end_timestamp"),
                pl.col("latitude").cast(pl.Float64),
                pl.col("longitude").cast(pl.Float64),
                pl.col("height").cast(pl.Float64).alias("elevation"),
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
                pl.col("start_timestamp").min(),
                pl.col("end_timestamp").max(),
                pl.col("latitude").first(),
                pl.col("longitude").first(),
                pl.col("elevation").first(),
                pl.col("name").first(),
            )
            for frames in frames_by_group.values()
        ]
        if not data:
            return pl.LazyFrame()
        return pl.concat(data).lazy()
