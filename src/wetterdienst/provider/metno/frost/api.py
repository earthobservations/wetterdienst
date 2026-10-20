# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""MET Norway Frost API provider."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import TYPE_CHECKING, cast
from urllib.parse import parse_qs, urlparse

import polars as pl
from aiohttp import encode_basic_auth

from wetterdienst.exceptions import CredentialMissingError, DownloadError, NoInternetError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, LicenseModel, ParameterModel, build_metadata_model
from wetterdienst.model.quality_flags import Sentinel, join_quality_flags, null_sentinels
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.settings import Settings
from wetterdienst.util.network import (
    CREDENTIAL_REJECTED_STATUSES,
    PROBE_TIMEOUT,
    File,
    as_outage,
    download_file,
    raise_if_credential_rejected,
)

if TYPE_CHECKING:
    from wetterdienst.model.metadata import DatasetModel

log = logging.getLogger(__name__)

# the answers that say Frost refuses the client ID, as opposed to one that says it could not be asked
_FROST_REJECTED_STATUSES = frozenset({401, 403})

_MetnoFrostMetadataSpec = {
    "name_short": "MetNo Frost",
    "name_english": "Norwegian Meteorological Institute",
    "name_local": "Meteorologisk institutt",
    "country": "Norway",
    "country_code": "NO",
    "copyright": "© Norwegian Meteorological Institute (MET Norway)",
    "license": LicenseModel(
        spdx_id="CC-BY-4.0 OR NLOD-2.0",
        name="Creative Commons Attribution 4.0 International, or Norwegian Licence for Open Government Data 2.0",
        url="https://api.met.no/doc/License",
    ),
    "attribution": "Data from MET Norway",
    "url": "https://frost.met.no",
    "kind": "observation",
    "timezone": "Europe/Oslo",
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
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "max(air_temperature PT10M)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "min(air_temperature PT10M)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "humidity_relative_max",
                            "name_original": "max(relative_humidity PT10M)",
                            "unit": "percent",
                        },
                        {
                            "name": "humidity_relative_min",
                            "name_original": "min(relative_humidity PT10M)",
                            "unit": "percent",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "max(wind_speed_of_gust PT10M)",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_direction_gust_max",
                            "name_original": "max(wind_from_direction_of_gust PT10M)",
                            "unit": "degree",
                        },
                        {
                            "name": "precipitation_amount",
                            "name_original": "sum(precipitation_amount PT10M)",
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
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "temperature_air_2m",
                            "name_original": "air_temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_dew_point_2m",
                            "name_original": "dew_point_temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "humidity_relative",
                            "name_original": "relative_humidity",
                            "unit": "percent",
                        },
                        {
                            "name": "wind_speed_mean_last_10min",
                            "name_original": "wind_speed",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_direction_mean_last_10min",
                            "name_original": "wind_from_direction",
                            "unit": "degree",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "air_pressure_at_sea_level",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "surface_air_pressure",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "cloud_cover_total",
                            "name_original": "cloud_area_fraction",
                            "unit": "one_eighth",
                        },
                        {
                            "name": "radiation_global_intensity_mean",
                            "name_original": "mean(surface_downwelling_shortwave_flux_in_air PT1H)",
                            "unit": "watt_per_square_meter",
                        },
                        {
                            "name": "precipitation_amount",
                            "name_original": "sum(precipitation_amount PT1H)",
                            "unit": "millimeter",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "surface_snow_thickness",
                            "unit": "centimeter",
                        },
                    ],
                },
            ],
        },
        {
            "name": "6_hours",
            "name_original": "PT6H",
            "periods": ["historical", "recent"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "precipitation_amount",
                            "name_original": "sum(precipitation_amount PT6H)",
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
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "mean(air_temperature P1D)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "max(air_temperature P1D)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "min(air_temperature P1D)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "precipitation_amount",
                            "name_original": "sum(precipitation_amount P1D)",
                            "unit": "millimeter",
                        },
                        {
                            "name": "wind_speed_mean",
                            "name_original": "mean(wind_speed P1D)",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_speed_rolling_mean_max",
                            "name_original": "max(wind_speed P1D)",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "humidity_relative_mean",
                            "name_original": "mean(relative_humidity P1D)",
                            "unit": "percent",
                        },
                        {
                            "name": "pressure_air_sea_level_mean",
                            "name_original": "mean(air_pressure_at_sea_level P1D)",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_site_mean",
                            "name_original": "mean(surface_air_pressure P1D)",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "radiation_global_intensity_mean",
                            "name_original": "mean(surface_downwelling_shortwave_flux_in_air P1D)",
                            "unit": "watt_per_square_meter",
                        },
                        {
                            "name": "snow_depth",
                            "name_original": "surface_snow_thickness",
                            "unit": "centimeter",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "sum(duration_of_sunshine P1D)",
                            "unit": "hour",
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
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "mean(air_temperature P1M)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "max(air_temperature P1M)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "min(air_temperature P1M)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "mean(dew_point_temperature P1M)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "precipitation_amount",
                            "name_original": "sum(precipitation_amount P1M)",
                            "unit": "millimeter",
                        },
                        {
                            "name": "wind_speed_mean",
                            "name_original": "mean(wind_speed P1M)",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_speed_rolling_mean_max",
                            "name_original": "max(wind_speed P1M)",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "humidity_relative_mean",
                            "name_original": "mean(relative_humidity P1M)",
                            "unit": "percent",
                        },
                        {
                            "name": "pressure_air_sea_level_mean",
                            "name_original": "mean(air_pressure_at_sea_level P1M)",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "pressure_air_site_mean",
                            "name_original": "mean(surface_air_pressure P1M)",
                            "unit": "hectopascal",
                        },
                        {
                            "name": "cloud_cover_total_mean",
                            "name_original": "mean(cloud_area_fraction P1M)",
                            "unit": "one_eighth",
                        },
                        {
                            "name": "snow_depth_mean",
                            "name_original": "mean(surface_snow_thickness P1M)",
                            "unit": "centimeter",
                        },
                        {
                            "name": "sunshine_duration",
                            "name_original": "sum(duration_of_sunshine P1M)",
                            "unit": "hour",
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
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "mean(air_temperature P1Y)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_max_2m",
                            "name_original": "max(air_temperature P1Y)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m",
                            "name_original": "min(air_temperature P1Y)",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "precipitation_amount",
                            "name_original": "sum(precipitation_amount P1Y)",
                            "unit": "millimeter",
                        },
                        {
                            "name": "cloud_cover_total_mean",
                            "name_original": "mean(cloud_area_fraction P1Y)",
                            "unit": "one_eighth",
                        },
                    ],
                },
            ],
        },
    ],
}
MetnoFrostMetadata = build_metadata_model(_MetnoFrostMetadataSpec, "MetnoFrostMetadata")


# Frost states two codes in the element descriptions it publishes and then writes them into the
# value itself, where nothing tells them apart from a measurement:
#
# - snow depth -1 is "no snow", which is a depth of zero rather than an absent one. It reaches the
#   caller as -1 cm otherwise, and it is not rare: at SN18700 across one summer, 93 of 185 daily
#   observations are -1 against 92 measured zeros
# - cloud cover -3 and 9 both mean the cover could not be estimated, the sky being obscured. In
#   eighths those convert to -0.375 and 1.125 of the sky, the second of which looks like a
#   plausible reading rather than a code
#
# Only the elements themselves. Frost leaves the codes out of its own monthly and annual means --
# checked over nine years at SN18700, where neither mean goes negative or above eight.
_SNOW_DEPTH = "surface_snow_thickness"
_NO_SNOW = "-1"
_CLOUD_COVER = "cloud_area_fraction"
_CLOUD_COVER_NOT_ESTIMATED = ("-3", "9")
_DAILY = "daily"


def _raise_if_rejected(file: File) -> None:
    """Raise the `CredentialRejectedError` of a download that Frost answered with a 401 or a 403 (GH-2665, GH-3018)."""
    raise_if_credential_rejected(file, "Frost API", "METNO_FROST", "client ID")


def _raise_if_unanswered(file: File) -> None:
    """Raise for a download that Frost did not answer, or answered with a refusal of the client ID (GH-3022, GH-3018).

    A client ID that Frost refuses (401, 403) is the `CredentialRejectedError`, whoever runs the process has to
    replace it. A timeout, a dropped connection, a body cut short, a 5xx and a connection that could not be made
    are the `DownloadError` and the `NoInternetError` (`as_outage`): none of them is Frost saying there is no data,
    and answered as an empty frame they read as a station without data. What Frost does answer stays with the
    caller, which reads the status: a 404 and a 412 are no data, and any other 4xx is warned about.
    """
    _raise_if_rejected(file)
    if isinstance(file.content, Exception):
        failure = as_outage(file.content, file.url)
        if isinstance(failure, (NoInternetError, DownloadError)):
            raise failure


def _frost_time(value: datetime) -> str:
    """Give a request bound as Frost reads it: the text of its UTC wall clock.

    Frost takes the time of `referencetime` as UTC and has no way to be told otherwise. The bounds
    of a request are UTC, whatever zone they were given in (GH-2681, GH-2682), so their wall clock is
    the one to write down.
    """
    return value.strftime("%Y-%m-%dT%H:%M:%S")


def _frost_end_exclusive(value: datetime, resolution: str) -> datetime:
    """Give the exclusive end Frost needs to return the stamp at the end of a closed window.

    Frost's intervals are open-ended: "[t0,t1>, i.e. representing times later than or equal to t0 and earlier
    than t1" (https://frost.met.no/concepts2.html), while the window of a request is closed at both ends. An
    end sent unchanged lost the value stamped at it, the 00:00 reading of a one-hour request or the month that
    starts at it (GH-2746). A second later names it; what lies beyond the window is cut off by the framework.

    A daily value belongs to the date of its stamp, which is the date of the reading for an instantaneous element
    (`_stamp_days`), so a request whose end is 00:00 UTC of a date asks for the whole of that date, the 06:00 UTC
    reading of the snow depth being its value (GH-2729): its end is 00:00 UTC of the date after. The end is UTC, as
    the bounds of a request are.
    """
    if resolution == _DAILY:
        return value.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
    return value + timedelta(seconds=1)


def _frost_end(value: datetime, resolution: str) -> str:
    """Give the end of a request as Frost reads it (see `_frost_end_exclusive`)."""
    return _frost_time(_frost_end_exclusive(value, resolution))


def _stamp_days(df: pl.DataFrame, resolution: str) -> pl.DataFrame:
    """Stamp a daily value at 00:00 UTC of the day it belongs to (GH-2729).

    Frost stores a daily value with a date only, `referenceTime` `<date>T00:00`, except for an instantaneous
    observation, which "is stored with date and time" and whose `referenceTime` "is equal to the observation
    time" (https://frost.met.no/concepts2.html). Of the daily elements that is `surface_snow_thickness`,
    stamped at the time of its reading, so it sat besides the other daily parameters at a time of its own, which
    a window of whole days, as the one of a request for a day, does not keep (GH-2683 for SMHI). The reading
    on a date belongs to that date; the other daily stamps are at 00:00 UTC already.

    ``resolution`` is the name of the resolution the frame was collected for: the frame has no column of it, the core
    writes that (`shape_provider_frame`).
    """
    if resolution != _DAILY:
        return df
    return df.with_columns(pl.col("timestamp").dt.truncate("1d"))


def _decode_sentinels(df: pl.DataFrame) -> pl.DataFrame:
    """Turn Frost's in-band codes into the value they stand for, before anything reads them.

    The code stays beside the value as the last token of `quality_flags`, `0,raw:-1`, written as Frost documents the
    code: the value is a JSON number, so its text is not at hand (GH-2759).
    """
    value, raw = null_sentinels(
        pl.col("value"),
        Sentinel(_NO_SNOW, where=pl.col("parameter") == _SNOW_DEPTH, to=0.0),
        Sentinel(*_CLOUD_COVER_NOT_ESTIMATED, where=pl.col("parameter") == _CLOUD_COVER),
        text=False,
    )
    quality = pl.col("quality_flags") if "quality_flags" in df.columns else None
    return df.with_columns(value.alias("value"), join_quality_flags(quality, raw=raw))


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
        from wetterdienst.model.metadata import DatasetModel, ParameterModel  # noqa: PLC0415

        if isinstance(parameter_or_dataset, DatasetModel):
            dataset = parameter_or_dataset
            parameters = parameter_or_dataset.parameters
        elif isinstance(parameter_or_dataset, ParameterModel):
            dataset = parameter_or_dataset.dataset
            parameters = [parameter_or_dataset]
        else:
            return pl.DataFrame()

        start_date = self.sr.start
        end_date = self.sr.end
        if not start_date or not end_date:
            return pl.DataFrame()

        settings = self.sr.settings
        client_kwargs = {**settings.fsspec_client_kwargs}
        if settings.auth.metno_frost:
            client_id, secret = settings.auth.metno_frost
            client_kwargs["headers"] = {
                **client_kwargs.get("headers", {}),
                "Authorization": encode_basic_auth(client_id.get_secret_value(), secret.get_secret_value()),
            }

        # Fetch all elements of the dataset in a single request instead of one request per
        # parameter. The Frost API accepts a comma-separated `elements` list and returns
        # observations for all of them together.
        elements = ",".join(parameter.name_original for parameter in parameters)
        url = self._observations_url.format(
            station_id=station_id,
            element=elements,
            start=_frost_time(start_date),
            end=_frost_end(end_date, dataset.resolution.name),
            time_resolution=dataset.resolution.name_original,
        )
        log.info(f"Acquiring data from {url}")
        file = download_file(
            url=url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.FIVE_MINUTES,
            client_kwargs=client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        # the status is read before the generic failure warning below: a 404 or 412 says there is
        # nothing (or that a fallback applies), not that the request failed
        # 412: no data for this station/elements/period combination
        _raise_if_unanswered(file)
        if file.status == 412:
            return pl.DataFrame()
        # 404: one or more elements may require specific time-series parameters (e.g.
        # historical synoptic data). Fall back to resolving each requested parameter individually.
        if file.status == 404:
            return self._collect_after_batch_404(
                station_id, dataset, parameters, start_date, end_date, settings, client_kwargs
            )
        if isinstance(file.content, Exception):
            log.warning(f"Failed to download {url}: {file.content}")
            return pl.DataFrame()
        # a 200 with no body
        if file.is_empty:
            return pl.DataFrame()

        df = pl.read_json(file.content)
        if "data" not in df.columns:
            return pl.DataFrame()

        df = df.select(pl.col("data").explode(empty_as_null=True))
        df = df.unnest("data")
        # columns: sourceId, referenceTime, observations (list of structs)
        df = df.with_columns(
            pl.col("referenceTime")
            .str.to_datetime(format="%Y-%m-%dT%H:%M:%S%.fZ", time_unit="us")
            .dt.replace_time_zone("UTC"),
        )
        df = df.explode("observations", empty_as_null=True)
        df = df.unnest("observations")
        return _stamp_days(
            _decode_sentinels(
                df.select(
                    pl.col("elementId").alias("parameter"),
                    pl.col("referenceTime").alias("timestamp"),
                    pl.col("value"),
                    pl.col("qualityCode").cast(pl.Int64).cast(pl.String).alias("quality_flags"),
                ),
            ),
            dataset.resolution.name,
        )

    def _collect_after_batch_404(
        self,
        station_id: str,
        dataset: DatasetModel,
        batched: list[ParameterModel],
        start_date: datetime,
        end_date: datetime,
        settings: Settings,
        client_kwargs: dict,
    ) -> pl.DataFrame:
        """Resolve the requested parameters one by one after the request for `batched` 404'd.

        Only the parameters that were asked for: the batch fetched the whole dataset, but its extra
        rows are dropped later, so resolving them would spend requests on nothing. A batch of one
        element is the single request itself, which just 404'd, so that goes straight to discovery.
        """
        requested = {
            parameter.name_original
            for parameter in self.sr.parameters
            if (parameter.dataset.resolution.name, parameter.dataset.name) == (dataset.resolution.name, dataset.name)
        }
        resolve = self._collect_via_time_series_discovery if len(batched) == 1 else self._collect_single_parameter
        frames = [
            resolve(station_id, parameter, start_date, end_date, settings, client_kwargs)
            for parameter in batched
            if parameter.name_original in requested
        ]
        frames = [frame for frame in frames if not frame.is_empty()]
        return pl.concat(frames, how="diagonal_relaxed") if frames else pl.DataFrame()

    def _collect_single_parameter(
        self,
        station_id: str,
        parameter: ParameterModel,
        start_date: datetime,
        end_date: datetime,
        settings: Settings,
        client_kwargs: dict,
    ) -> pl.DataFrame:
        """Fetch a single parameter directly, falling back to time-series discovery on 404.

        Used when a batched multi-element request 404s, to resolve each parameter
        individually (some historical/synoptic elements require time-series discovery,
        see `_collect_via_time_series_discovery`).
        """
        url = self._observations_url.format(
            station_id=station_id,
            element=parameter.name_original,
            start=_frost_time(start_date),
            end=_frost_end(end_date, parameter.dataset.resolution.name),
            time_resolution=parameter.dataset.resolution.name_original,
        )
        log.info(f"Acquiring data from {url}")
        file = download_file(
            url=url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.FIVE_MINUTES,
            client_kwargs=client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        # the status before the body, as in `_collect_station_parameter_or_dataset`
        # 412: no data for this station/element/period combination
        _raise_if_unanswered(file)
        if file.status == 412:
            return pl.DataFrame()
        # 404: element may require specific time-series parameters (e.g. historical synoptic data)
        if file.status == 404:
            return self._collect_via_time_series_discovery(
                station_id, parameter, start_date, end_date, settings, client_kwargs
            )
        if isinstance(file.content, Exception):
            log.warning(f"Failed to download {url}: {file.content}")
            return pl.DataFrame()
        # a 200 with no body
        if file.is_empty:
            return pl.DataFrame()

        df = pl.read_json(file.content)
        if "data" not in df.columns:
            return pl.DataFrame()

        df = df.select(pl.col("data").explode(empty_as_null=True))
        df = df.unnest("data")
        df = df.with_columns(
            pl.col("referenceTime")
            .str.to_datetime(format="%Y-%m-%dT%H:%M:%S%.fZ", time_unit="us")
            .dt.replace_time_zone("UTC"),
        )
        df = df.explode("observations", empty_as_null=True)
        df = df.unnest("observations")
        # keep only matching elementId (the Frost response may include multiple elements)
        df = df.filter(pl.col("elementId").eq(parameter.name_original))
        return _stamp_days(
            _decode_sentinels(
                df.select(
                    pl.lit(parameter.name_original, dtype=pl.String).alias("parameter"),
                    pl.col("referenceTime").alias("timestamp"),
                    pl.col("value"),
                    pl.col("qualityCode").cast(pl.Int64).cast(pl.String).alias("quality_flags"),
                ),
            ),
            parameter.dataset.resolution.name,
        )

    def _collect_via_time_series_discovery(  # noqa: C901
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
        resolution_name = parameter_or_dataset.dataset.resolution.name

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
            use_certifi=settings.use_certifi,
        )
        # as for the observations below, a 404 or 412 says there is nothing, not that the request failed
        _raise_if_unanswered(avail_file)
        if avail_file.status in (404, 412):
            return pl.DataFrame()
        if isinstance(avail_file.content, Exception):
            log.warning(f"Failed to download {avail_url}: {avail_file.content}")
            return pl.DataFrame()
        if avail_file.is_empty:
            return pl.DataFrame()

        ts_list = json.loads(avail_file.content.read()).get("data", [])
        frames = []
        for ts in ts_list:
            valid_from = datetime.fromisoformat(ts["validFrom"].rstrip("Z")).replace(tzinfo=UTC)
            valid_to_str = ts.get("validTo")
            valid_to = (
                datetime.fromisoformat(valid_to_str.rstrip("Z")).replace(tzinfo=UTC) if valid_to_str else end_date
            )
            range_start = max(start_date, valid_from)
            range_end = min(end_date, valid_to)
            # a series that starts after the end but on its date, as a daily snow depth read at 06:00 UTC, has
            # values in the window (GH-2729)
            if range_start >= _frost_end_exclusive(range_end, resolution_name):
                continue

            params = parse_qs(urlparse(ts["uri"]).query)
            obs_url = self._observations_url_ts.format(
                source_id=params.get("sources", [station_id])[0],
                element=element,
                start=_frost_time(range_start),
                end=_frost_end(range_end, resolution_name),
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
                use_certifi=settings.use_certifi,
            )
            _raise_if_unanswered(obs_file)
            if obs_file.status in (404, 412):
                continue
            if isinstance(obs_file.content, Exception):
                log.warning(f"Failed to download {obs_url}: {obs_file.content}")
                continue
            if obs_file.is_empty:
                continue

            df = pl.read_json(obs_file.content)
            if "data" not in df.columns:
                continue
            df = df.select(pl.col("data").explode(empty_as_null=True)).unnest("data")
            df = df.with_columns(
                pl.col("referenceTime")
                .str.to_datetime(format="%Y-%m-%dT%H:%M:%S%.fZ", time_unit="us")
                .dt.replace_time_zone("UTC"),
            )
            df = df.explode("observations", empty_as_null=True).unnest("observations")
            df = df.filter(pl.col("elementId").eq(element))
            frames.append(
                _stamp_days(
                    _decode_sentinels(
                        df.select(
                            pl.lit(element, dtype=pl.String).alias("parameter"),
                            pl.col("referenceTime").alias("timestamp"),
                            pl.col("value"),
                            pl.col("qualityCode").cast(pl.Int64).cast(pl.String).alias("quality_flags"),
                        ),
                    ),
                    resolution_name,
                )
            )

        if not frames:
            return pl.DataFrame()
        return pl.concat(frames, how="diagonal_relaxed")


def _probe_frost_credentials(settings: Settings) -> bool | None:
    """Probe the Frost API, once and for `PROBE_TIMEOUT_SECONDS`; an acceptance is cached on disk for ONE_MINUTE.

    Returns False only for the answers that say the client ID is refused (HTTP 401 and 403), True for
    a 200, and None for any other outcome -- no network, a failed TLS verification, a timeout, a 429,
    a 5xx -- which says nothing about the credentials.

    Only a 200 is cached: Frost answers a refusal or a failure with an HTTP error status, which
    `download_file` does not keep. It is kept for a minute and not an hour (GH-2750), so a client ID
    that is revoked stops reading `True` within the minute.
    """
    if not settings.auth.metno_frost:
        return False
    client_id, secret = settings.auth.metno_frost
    # a fresh headers dict, as every other authenticated provider builds: `{**settings...}` copies
    # one level, so `setdefault("headers", {})[...] = ...` wrote the Authorization header into the
    # dict `Settings` holds. Every later request from that `Settings` -- any provider, not only
    # this one -- then carried met.no's basic auth, which since GH-1959 also moves its blobs off
    # the shared cache directory onto a credential-named one
    client_kwargs = {
        **settings.fsspec_client_kwargs,
        "headers": {
            **settings.fsspec_client_kwargs.get("headers", {}),
            "Authorization": encode_basic_auth(client_id.get_secret_value(), secret.get_secret_value()),
        },
        # bounded: this is asked while a page waits for it (GH-2564)
        "timeout": PROBE_TIMEOUT,
    }
    file = download_file(
        url="https://frost.met.no/sources/v0.jsonld?ids=SN18700&fields=id",
        cache_dir=settings.cache_dir,
        ttl=CacheExpiry.ONE_MINUTE,
        client_kwargs=client_kwargs,
        cache_disable=settings.cache_disable,
        use_certifi=settings.use_certifi,
        attempts=1,
    )
    if file.status in CREDENTIAL_REJECTED_STATUSES:
        return False
    if not isinstance(file.content, Exception) and file.status == 200:
        return True
    log.warning("Could not check the Frost credentials (status %s): %s", file.status, file.content)
    return None


class MetnoFrostRequest(TimeseriesRequest):
    """Request class for MET Norway Frost API."""

    metadata = MetnoFrostMetadata
    _values = MetnoFrostValues

    _sources_url = "https://frost.met.no/sources/v0.jsonld?types=SensorSystem&fields=id,name,validFrom,validTo,geometry,county,countryCode,masl"

    @classmethod
    def is_configured(cls) -> bool:  # noqa: D102
        return bool(Settings().auth.metno_frost)

    @classmethod
    def is_valid(cls, settings: Settings | None = None) -> bool | None:  # noqa: D102
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
            raise CredentialMissingError(msg)

    def _all(self) -> pl.LazyFrame:
        settings = cast("Settings", self.settings)
        client_kwargs = {**settings.fsspec_client_kwargs}
        if settings.auth.metno_frost:
            client_id, secret = settings.auth.metno_frost
            client_kwargs["headers"] = {
                **client_kwargs.get("headers", {}),
                "Authorization": encode_basic_auth(client_id.get_secret_value(), secret.get_secret_value()),
            }
        file = download_file(
            url=self._sources_url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        _raise_if_rejected(file)
        # the catalogue is one required file, so any other failure of it -- a 404 included -- is an
        # outage, which swallowed would read as a network without stations (GH-2599). A failed
        # connection (NoInternetError) is raised as well (GH-2640)
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.LazyFrame()

        df = pl.read_json(file.content)
        df = df.select(pl.col("data").explode(empty_as_null=True)).drop_nulls()
        if df.is_empty():
            # `{"data": []}` is a list without a source, a column of nulls that cannot be unnested
            return pl.LazyFrame()
        df = df.unnest("data")
        # geometry.coordinates: [longitude, latitude, elevation?]. 24 of the 2235 sources (2026-10-19) have
        # no geometry and no position in any other field: ships, rigs and gliders (SN76999 SCARABEO 8,
        # SN20930 POLARSTERN, SN20957 SG644 GLIDER), which move. They stay in the list with a null position,
        # as the GHCN placeholders do (GH-2655): no distance search, interpolation or summary picks them
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
            pl.when(pl.col("masl").is_not_null())
            .then(pl.col("masl"))
            .otherwise(pl.col("_elevation"))
            .alias("elevation"),
        )
        if "validTo" not in df.columns:
            df = df.with_columns(pl.lit(None, dtype=pl.String).alias("validTo"))
        df = df.with_columns(
            pl.col("validFrom")
            .str.to_datetime(format="%Y-%m-%dT%H:%M:%S%.fZ", time_unit="us")
            .alias("start_timestamp"),
            # a station still in service has no validTo, which parses to null
            pl.col("validTo").str.to_datetime(format="%Y-%m-%dT%H:%M:%S%.fZ", time_unit="us").alias("end_timestamp"),
        )
        df = df.rename({"id": "station_id", "name": "name", "county": "region", "countryCode": "country"})
        # Frost pads some names with a blank (`KVANNDALEN `), which a comparison of the name misses
        df = df.select(
            "station_id",
            pl.col("name").str.strip_chars(),
            "region",
            "latitude",
            "longitude",
            "elevation",
            "start_timestamp",
            "end_timestamp",
        )
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
        return pl.concat(data)
