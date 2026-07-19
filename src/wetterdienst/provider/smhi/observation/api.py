# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""SMHI (Sweden) observation data provider."""

from __future__ import annotations

import json
import logging
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

# SMHI splits history into non-overlapping-by-design periods: "corrected-archive" is
# quality-controlled data up to ~3 months ago, "latest-months" covers the last ~4 months
# (still under QC). Both are fetched and merged so a request spanning the boundary gets
# complete coverage without needing to guess which period a given date range falls into.
# Minute-resolution data is different: SMHI only exposes a short rolling window for it
# (no historical archive at all), via "latest-day" instead.
_PERIODS_BY_RESOLUTION = {
    Resolution.MINUTE_1: ("latest-day",),
    Resolution.HOURLY: ("corrected-archive", "latest-months"),
    Resolution.DAILY: ("corrected-archive", "latest-months"),
    Resolution.MONTHLY: ("corrected-archive", "latest-months"),
}

# A reference parameter per resolution, used only to enumerate the station network --
# temperature is measured at virtually every station, unlike e.g. visibility or snow
# depth, so it stands in for "all stations available at this resolution".
_STATION_LIST_REFERENCE_PARAMETER_ID = {
    Resolution.MINUTE_1: "45",
    Resolution.HOURLY: "1",
    Resolution.DAILY: "2",
    Resolution.MONTHLY: "22",
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


def _fetch_csv(url: str, settings: Settings) -> bytes | Exception:
    """Download an SMHI CSV file; a 404 (station doesn't report this parameter) is routine, not an error."""
    file: File = download_file(
        url=url,
        cache_dir=settings.cache_dir,
        ttl=CacheExpiry.FIVE_MINUTES,
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
        return pl.concat(data, how="diagonal")

    def _collect_parameter(self, station_id: str, parameter: ParameterModel, settings: Settings) -> pl.DataFrame:
        periods = _PERIODS_BY_RESOLUTION[parameter.dataset.resolution.value]
        frames = []
        for period in periods:
            url = f"{_BASE_URL}/parameter/{parameter.name_original}/station/{station_id}/period/{period}/data.csv"
            payload = _fetch_csv(url, settings)
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
            df = parse_smhi_csv(payload.decode("utf-8-sig"))
            if not df.is_empty():
                frames.append(df)
        if not frames:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        df = pl.concat(frames, how="diagonal")
        # when periods overlap by design (corrected-archive/latest-months), keep one row
        # per timestamp, preferring the period fetched last (more recent QC state).
        # maintain_order=True is required for keep="last" to deterministically retain the
        # row from the last-appended (most recent) period.
        df = df.unique(subset="date", keep="last", maintain_order=True)
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
        resolutions_and_datasets = {
            (parameter.dataset.resolution.name, parameter.dataset.name)
            for parameter in self.parameters
            if isinstance(parameter, ParameterModel)
        }
        data = []
        for resolution, dataset in resolutions_and_datasets:
            reference_parameter_id = _STATION_LIST_REFERENCE_PARAMETER_ID[Resolution(resolution)]
            url = f"{_BASE_URL}/parameter/{reference_parameter_id}.json"
            payload = _fetch_csv(url, settings)
            if isinstance(payload, Exception):
                log.warning(f"Failed to fetch SMHI stations for resolution {resolution}: {payload}")
                continue
            stations = json.loads(payload.decode("utf-8-sig")).get("station", [])
            if not stations:
                continue
            df = pl.DataFrame(stations)
            df = df.select(
                pl.lit(resolution, dtype=pl.String).alias("resolution"),
                pl.lit(dataset, dtype=pl.String).alias("dataset"),
                pl.col("id").cast(pl.String).alias("station_id"),
                pl.from_epoch("from", time_unit="ms").dt.replace_time_zone("UTC").alias("start_date"),
                pl.from_epoch("to", time_unit="ms").dt.replace_time_zone("UTC").alias("end_date"),
                pl.col("latitude").cast(pl.Float64),
                pl.col("longitude").cast(pl.Float64),
                pl.col("height").cast(pl.Float64),
                pl.col("name").cast(pl.String),
            )
            data.append(df)
        if not data:
            return pl.LazyFrame()
        return pl.concat(data, how="diagonal").lazy()
