# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""MET Norway Frost API provider."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import TYPE_CHECKING, cast
from urllib.parse import parse_qs, urlparse

import polars as pl
from aiohttp import ClientTimeout, encode_basic_auth

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, ParameterModel, build_metadata_model
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.settings import Settings
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from wetterdienst.model.metadata import DatasetModel

log = logging.getLogger(__name__)

MetnoFrostMetadata = {
    "name_short": "MetNo Frost",
    "name_english": "Norwegian Meteorological Institute",
    "name_local": "Meteorologisk institutt",
    "country": "Norway",
    "copyright": "© Norwegian Meteorological Institute (MET Norway)",
    "url": "https://frost.met.no",
    "kind": "observation",
    "timezone": "Europe/Oslo",
    "timezone_data": "UTC",
    "auth": True,
    "resolutions": [
        {
            "name": "10_minutes",
            "name_original": "PT10M",
            "periods": ["historical", "recent"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": False,
                    "parameters": [
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "max(air_temperature PT10M)",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "min(air_temperature PT10M)",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "humidity_max",
                            "name_original": "max(relative_humidity PT10M)",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "humidity_min",
                            "name_original": "min(relative_humidity PT10M)",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "max(wind_speed_of_gust PT10M)",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_direction_gust_max",
                            "name_original": "max(wind_from_direction_of_gust PT10M)",
                            "unit_type": "angle",
                            "unit": "degree",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "sum(precipitation_amount PT10M)",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                    ],
                },
            ],
        },
        {
            "name": "hourly",
            "name_original": "PT1H",
            "periods": ["historical", "recent"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": False,
                    "parameters": [
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "air_temperature",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "dew_point_temperature",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "humidity",
                            "name_original": "relative_humidity",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "wind_speed",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "wind_from_direction",
                            "unit_type": "angle",
                            "unit": "degree",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "air_pressure_at_sea_level",
                            "unit_type": "pressure",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "surface_air_pressure",
                            "unit_type": "pressure",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "cloud_cover_total",
                            "name_original": "cloud_area_fraction",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "radiation_global",
                            "name_original": "mean(surface_downwelling_shortwave_flux_in_air PT1H)",
                            "unit_type": "power_per_area",
                            "unit": "watt_per_square_meter",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "sum(precipitation_amount PT1H)",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "surface_snow_thickness",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                    ],
                },
            ],
        },
        {
            "name": "6_hour",
            "name_original": "PT6H",
            "periods": ["historical", "recent"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": False,
                    "parameters": [
                        {
                            "name": "precipitation_height",
                            "name_original": "sum(precipitation_amount PT6H)",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                    ],
                },
            ],
        },
        {
            "name": "daily",
            "name_original": "P1D",
            "periods": ["historical", "recent"],
            "date_required": False,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": False,
                    "parameters": [
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "mean(air_temperature P1D)",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "max(air_temperature P1D)",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "min(air_temperature P1D)",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "sum(precipitation_amount P1D)",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "mean(wind_speed P1D)",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_speed_rolling_mean_max",
                            "name_original": "max(wind_speed P1D)",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "humidity",
                            "name_original": "mean(relative_humidity P1D)",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "mean(air_pressure_at_sea_level P1D)",
                            "unit_type": "pressure",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "mean(surface_air_pressure P1D)",
                            "unit_type": "pressure",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "radiation_global",
                            "name_original": "mean(surface_downwelling_shortwave_flux_in_air P1D)",
                            "unit_type": "power_per_area",
                            "unit": "watt_per_square_meter",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "surface_snow_thickness",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "sum(duration_of_sunshine P1D)",
                            "unit_type": "time",
                            "unit": "second",
                        },
                    ],
                },
            ],
        },
        {
            "name": "monthly",
            "name_original": "P1M",
            "periods": ["historical", "recent"],
            "date_required": False,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": False,
                    "parameters": [
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "mean(air_temperature P1M)",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "max(air_temperature P1M)",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "min(air_temperature P1M)",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "mean(dew_point_temperature P1M)",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "sum(precipitation_amount P1M)",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "mean(wind_speed P1M)",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_speed_rolling_mean_max",
                            "name_original": "max(wind_speed P1M)",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "humidity",
                            "name_original": "mean(relative_humidity P1M)",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "mean(air_pressure_at_sea_level P1M)",
                            "unit_type": "pressure",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "mean(surface_air_pressure P1M)",
                            "unit_type": "pressure",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "cloud_cover_total",
                            "name_original": "mean(cloud_area_fraction P1M)",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "mean(surface_snow_thickness P1M)",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "sum(duration_of_sunshine P1M)",
                            "unit_type": "time",
                            "unit": "second",
                        },
                    ],
                },
            ],
        },
        {
            "name": "annual",
            "name_original": "P1Y",
            "periods": ["historical", "recent"],
            "date_required": False,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": False,
                    "parameters": [
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "mean(air_temperature P1Y)",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "max(air_temperature P1Y)",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "min(air_temperature P1Y)",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "sum(precipitation_amount P1Y)",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "cloud_cover_total",
                            "name_original": "mean(cloud_area_fraction P1Y)",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                    ],
                },
            ],
        },
    ],
}
MetnoFrostMetadata = build_metadata_model(MetnoFrostMetadata, "MetnoFrostMetadata")


_EMPTY_VALUES_SCHEMA = {
    "resolution": pl.String,
    "dataset": pl.String,
    "parameter": pl.String,
    "station_id": pl.String,
    "date": pl.Datetime(time_unit="us", time_zone="UTC"),
    "value": pl.Float64,
    "quality": pl.Float64,
}


class MetnoFrostValues(TimeseriesValues):
    """Values class for MET Norway Frost API."""

    _observations_url = (
        "https://frost.met.no/observations/v0.jsonld"
        "?sources={station_id}"
        "&elements={element}"
        "&referencetime={start}/{end}"
        "&timeresolutions={time_resolution}"
    )
    _available_time_series_url = (
        "https://frost.met.no/observations/availableTimeSeries/v0.jsonld"
        "?sources={station_id}"
        "&elements={element}"
        "&timeresolutions={time_resolution}"
    )
    _observations_url_ts = (
        "https://frost.met.no/observations/v0.jsonld"
        "?sources={source_id}"
        "&elements={element}"
        "&referencetime={start}/{end}"
        "&timeresolutions={time_resolution}"
        "&timeseriesids={ts_id}"
        "&performancecategories={perf_cats}"
        "&exposurecategories={expo_cats}"
    )

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel | DatasetModel,
    ) -> pl.DataFrame:
        from wetterdienst.model.metadata import ParameterModel  # noqa: PLC0415

        if not isinstance(parameter_or_dataset, ParameterModel):
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
        start_date = self.sr.start_date
        end_date = self.sr.end_date
        if not start_date or not end_date:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        settings = self.sr.settings
        url = self._observations_url.format(
            station_id=station_id,
            element=parameter_or_dataset.name_original,
            start=start_date.strftime("%Y-%m-%dT%H:%M:%S"),
            end=end_date.strftime("%Y-%m-%dT%H:%M:%S"),
            time_resolution=parameter_or_dataset.dataset.resolution.name_original,
        )
        client_kwargs = {**settings.fsspec_client_kwargs}
        if settings.auth.metno_frost:
            client_kwargs["headers"] = {
                **client_kwargs.get("headers", {}),
                "Authorization": encode_basic_auth(*settings.auth.metno_frost),
            }
        log.info(f"Acquiring data from {url}")
        file = download_file(
            url=url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.FIVE_MINUTES,
            client_kwargs=client_kwargs,
            cache_disable=settings.cache_disable,
        )
        if file.is_no_internet_error or file.is_empty:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
        # 412: no data for this station/element/period combination
        if file.status == 412:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
        # 404: element may require specific time-series parameters (e.g. historical synoptic data)
        if file.status == 404:
            return self._collect_via_time_series_discovery(
                station_id, parameter_or_dataset, start_date, end_date, settings, client_kwargs
            )
        if isinstance(file.content, Exception):
            log.warning(f"Failed to download {url}: {file.content}")
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        df = pl.read_json(file.content)
        if "data" not in df.columns:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        df = df.select(pl.col("data").explode())
        df = df.unnest("data")
        # columns: sourceId, referenceTime, observations (list of structs)
        df = df.with_columns(
            pl.col("referenceTime")
            .str.to_datetime(format="%Y-%m-%dT%H:%M:%S%.fZ", time_unit="us")
            .dt.replace_time_zone("UTC"),
        )
        df = df.explode("observations")
        df = df.unnest("observations")
        # keep only matching elementId (the Frost response may include multiple elements)
        df = df.filter(pl.col("elementId").eq(parameter_or_dataset.name_original))
        return df.select(
            pl.lit(parameter_or_dataset.dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(parameter_or_dataset.dataset.name, dtype=pl.String).alias("dataset"),
            pl.lit(parameter_or_dataset.name_original, dtype=pl.String).alias("parameter"),
            pl.lit(station_id, dtype=pl.String).alias("station_id"),
            pl.col("referenceTime").alias("date"),
            pl.col("value").cast(pl.Float64),
            pl.col("qualityCode").cast(pl.Float64).alias("quality"),
        )

    def _collect_via_time_series_discovery(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel,
        start_date: datetime,
        end_date: datetime,
        settings: Settings,
        client_kwargs: dict,
    ) -> pl.DataFrame:
        """Fall back to availableTimeSeries discovery when the direct query returns 404.

        Some historical/synoptic elements require specific timeseriesids, performancecategories,
        and exposurecategories parameters that can only be discovered via the availableTimeSeries
        endpoint.
        """
        element = parameter_or_dataset.name_original
        resolution = parameter_or_dataset.dataset.resolution.name_original

        avail_url = self._available_time_series_url.format(
            station_id=station_id,
            element=element,
            time_resolution=resolution,
        )
        log.info(f"Discovering time series via {avail_url}")
        avail_file = download_file(
            url=avail_url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.ONE_HOUR,
            client_kwargs=client_kwargs,
            cache_disable=settings.cache_disable,
        )
        if avail_file.is_no_internet_error or avail_file.is_empty or isinstance(avail_file.content, Exception):
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        ts_list = json.loads(avail_file.content.read()).get("data", [])
        frames = []
        for ts in ts_list:
            valid_from = datetime.fromisoformat(ts["validFrom"].rstrip("Z")).replace(tzinfo=timezone.utc)
            valid_to_str = ts.get("validTo")
            valid_to = (
                datetime.fromisoformat(valid_to_str.rstrip("Z")).replace(tzinfo=timezone.utc)
                if valid_to_str
                else end_date
            )
            range_start = max(start_date, valid_from)
            range_end = min(end_date, valid_to)
            if range_start > range_end:
                continue

            params = parse_qs(urlparse(ts["uri"]).query)
            obs_url = self._observations_url_ts.format(
                source_id=params.get("sources", [station_id])[0],
                element=element,
                start=range_start.strftime("%Y-%m-%dT%H:%M:%S"),
                end=range_end.strftime("%Y-%m-%dT%H:%M:%S"),
                time_resolution=resolution,
                ts_id=params.get("timeseriesids", ["0"])[0],
                perf_cats=params.get("performancecategories", [""])[0],
                expo_cats=params.get("exposurecategories", [""])[0],
            )
            log.info(f"Acquiring data from {obs_url}")
            obs_file = download_file(
                url=obs_url,
                cache_dir=settings.cache_dir,
                ttl=CacheExpiry.FIVE_MINUTES,
                client_kwargs=client_kwargs,
                cache_disable=settings.cache_disable,
            )
            if obs_file.is_no_internet_error or obs_file.is_empty or obs_file.status in (404, 412):
                continue
            if isinstance(obs_file.content, Exception):
                log.warning(f"Failed to download {obs_url}: {obs_file.content}")
                continue

            df = pl.read_json(obs_file.content)
            if "data" not in df.columns:
                continue
            df = df.select(pl.col("data").explode()).unnest("data")
            df = df.with_columns(
                pl.col("referenceTime")
                .str.to_datetime(format="%Y-%m-%dT%H:%M:%S%.fZ", time_unit="us")
                .dt.replace_time_zone("UTC"),
            )
            df = df.explode("observations").unnest("observations")
            df = df.filter(pl.col("elementId").eq(element))
            frames.append(
                df.select(
                    pl.lit(parameter_or_dataset.dataset.resolution.name, dtype=pl.String).alias("resolution"),
                    pl.lit(parameter_or_dataset.dataset.name, dtype=pl.String).alias("dataset"),
                    pl.lit(element, dtype=pl.String).alias("parameter"),
                    pl.lit(station_id, dtype=pl.String).alias("station_id"),
                    pl.col("referenceTime").alias("date"),
                    pl.col("value").cast(pl.Float64),
                    pl.col("qualityCode").cast(pl.Float64).alias("quality"),
                )
            )

        if not frames:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
        return pl.concat(frames, how="diagonal_relaxed")


def _probe_frost_credentials(settings: Settings) -> bool:
    """Probe the Frost API; result is cached on disk for ONE_HOUR via download_file."""
    if not settings.auth.metno_frost:
        return False
    client_kwargs = {**settings.fsspec_client_kwargs}
    client_kwargs.setdefault("headers", {})["Authorization"] = encode_basic_auth(*settings.auth.metno_frost)
    client_kwargs.setdefault("timeout", ClientTimeout(total=5))
    file = download_file(
        url="https://frost.met.no/sources/v0.jsonld?ids=SN18700&fields=id",
        cache_dir=settings.cache_dir,
        ttl=CacheExpiry.ONE_HOUR,
        client_kwargs=client_kwargs,
        cache_disable=settings.cache_disable,
    )
    return not file.is_no_internet_error and not isinstance(file.content, Exception) and file.status == 200


class MetnoFrostRequest(TimeseriesRequest):
    """Request class for MET Norway Frost API."""

    metadata = MetnoFrostMetadata
    _values = MetnoFrostValues

    _sources_url = "https://frost.met.no/sources/v0.jsonld?types=SensorSystem&fields=id,name,validFrom,validTo,geometry,county,countryCode,masl"

    @classmethod
    def is_configured(cls) -> bool:  # noqa: D102
        return bool(Settings().auth.metno_frost)

    @classmethod
    def is_valid(cls, settings: Settings | None = None) -> bool:  # noqa: D102
        return _probe_frost_credentials(settings or Settings())

    def __post_init__(self) -> None:  # noqa: D105
        super().__post_init__()
        settings = cast("Settings", self.settings)
        if not settings.auth.metno_frost:
            msg = (
                "MET Norway Frost API requires authentication. "
                "Register a free client ID at https://frost.met.no/auth/requestCredentials.html "
                "and set WD_AUTH__METNO_FROST=<client_id> (env var) "
                "or Settings(auth={'metno_frost': '<client_id>'}) (Python)."
            )
            raise ValueError(msg)

    def _all(self) -> pl.LazyFrame:
        settings = cast("Settings", self.settings)
        client_kwargs = {**settings.fsspec_client_kwargs}
        if settings.auth.metno_frost:
            client_kwargs["headers"] = {
                **client_kwargs.get("headers", {}),
                "Authorization": encode_basic_auth(*settings.auth.metno_frost),
            }
        file = download_file(
            url=self._sources_url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=client_kwargs,
            cache_disable=settings.cache_disable,
        )
        if isinstance(file.content, Exception):
            if file.status in {401, 403}:
                msg = (
                    f"Frost API rejected the request with HTTP {file.status}. "
                    "Check that WD_AUTH__METNO_FROST contains a valid client ID."
                )
                raise PermissionError(msg)
            log.warning(f"Failed to fetch Frost stations ({file.status}): {file.content}")
            return pl.LazyFrame()

        df = pl.read_json(file.content)
        df = df.select(pl.col("data").explode())
        df = df.unnest("data")
        # geometry.coordinates: [longitude, latitude, elevation?]
        df = df.with_columns(
            pl.col("geometry").struct.field("coordinates").list.get(0).alias("longitude"),
            pl.col("geometry").struct.field("coordinates").list.get(1).alias("latitude"),
            pl.col("geometry")
            .struct.field("coordinates")
            .list.get(2, null_on_oob=True)
            .cast(pl.Float64)
            .alias("_elevation"),
        )
        df = df.with_columns(
            pl.when(pl.col("masl").is_not_null()).then(pl.col("masl")).otherwise(pl.col("_elevation")).alias("height"),
        )
        if "validTo" not in df.columns:
            df = df.with_columns(pl.lit(None, dtype=pl.String).alias("validTo"))
        df = df.with_columns(
            pl.col("validFrom")
            .str.to_datetime(format="%Y-%m-%dT%H:%M:%S%.fZ", time_unit="us")
            .dt.replace_time_zone("UTC")
            .alias("start_date"),
            pl.when(pl.col("validTo").is_not_null())
            .then(
                pl.col("validTo")
                .str.to_datetime(format="%Y-%m-%dT%H:%M:%S%.fZ", time_unit="us")
                .dt.replace_time_zone("UTC")
            )
            .otherwise(pl.lit(None, dtype=pl.Datetime(time_unit="us", time_zone="UTC")))
            .alias("end_date"),
        )
        df = df.rename({"id": "station_id", "name": "name", "county": "state", "countryCode": "country"})
        resolutions_and_datasets = {
            (parameter.dataset.resolution.name, parameter.dataset.name)
            for parameter in self.parameters
            if isinstance(parameter, ParameterModel)
        }
        data = []
        for resolution, dataset in resolutions_and_datasets:
            data.append(
                df.with_columns(
                    pl.lit(resolution, pl.String).alias("resolution"),
                    pl.lit(dataset, pl.String).alias("dataset"),
                ).lazy(),
            )
        if not data:
            return pl.LazyFrame()
        return pl.concat(data).select(self._base_columns)
