# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Environment Agency hydrology API."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import ClassVar

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import (
    DATASET_NAME_DEFAULT,
    ParameterModel,
    build_metadata_model,
)
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.util.network import download_file

log = logging.getLogger(__name__)


EAHydrologyMetadata = {
    "name_short": "EA",
    "name_english": "Environment Agency",
    "name_local": "Environment Agency",
    "country": "United Kingdom",
    "copyright": "© Environment Agency of UK",
    "url": "https://environment.data.gov.uk/",
    "kind": "observation",
    "timezone": "Europe/London",
    "timezone_data": "Europe/London",
    "resolutions": [
        {
            "name": "15_minutes",
            "name_original": "15_minutes",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": False,
                    "parameters": [
                        {
                            "name": "discharge",
                            "name_original": "flow-i-900",
                            "unit_type": "volume_per_time",
                            "unit": "cubic_meter_per_second",
                        },
                        {
                            "name": "groundwater_level",
                            "name_original": "level-i-900",
                            "unit_type": "length_medium",
                            "unit": "meter",
                        },
                    ],
                },
            ],
        },
        {
            "name": "daily",
            "name_original": "daily",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": False,
                    "periods": ["historical"],
                    "parameters": [
                        {
                            "name": "discharge_max",
                            "name_original": "flow-max-86400",
                            "unit_type": "volume_per_time",
                            "unit": "cubic_meter_per_second",
                        },
                        {
                            "name": "discharge_mean",
                            "name_original": "flow-m-86400",
                            "unit_type": "volume_per_time",
                            "unit": "cubic_meter_per_second",
                        },
                        {
                            "name": "discharge_min",
                            "name_original": "flow-min-86400",
                            "unit_type": "volume_per_time",
                            "unit": "cubic_meter_per_second",
                        },
                        {
                            "name": "groundwater_level_max",
                            "name_original": "level-max-86400",
                            "unit_type": "length_medium",
                            "unit": "meter",
                        },
                        {
                            "name": "groundwater_level_min",
                            "name_original": "level-min-86400",
                            "unit_type": "length_medium",
                            "unit": "meter",
                        },
                    ],
                },
            ],
        },
    ],
}
EAHydrologyMetadata = build_metadata_model(EAHydrologyMetadata, "EAHydrologyMetadata")


class EAHydrologyValues(TimeseriesValues):
    """Values class for Environment Agency hydrology data."""

    _url = "https://environment.data.gov.uk/hydrology/id/stations/{station_id}.json"

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel,
    ) -> pl.DataFrame:
        """Collect data for a station, parameter or dataset."""
        url = self._url.format(station_id=station_id)
        file = download_file(
            url=url,
            cache_dir=self.sr.stations.settings.cache_dir,
            ttl=CacheExpiry.NO_CACHE,
            client_kwargs=self.sr.stations.settings.fsspec_client_kwargs,
            cache_disable=self.sr.stations.settings.cache_disable,
        )
        file.raise_if_exception()
        df_measures = pl.read_json(
            file.content,
            schema={
                "items": pl.List(
                    pl.Struct(
                        {
                            "measures": pl.List(
                                pl.Struct(
                                    {
                                        "parameterName": pl.String,
                                        "parameter": pl.String,
                                        "period": pl.Int64,
                                        "@id": pl.String,
                                    },
                                ),
                            ),
                        },
                    ),
                ),
            },
        )
        df_measures = df_measures.explode("items")
        df_measures = df_measures.select(pl.col("items").struct.field("measures"))
        df_measures = df_measures.explode("measures")
        df_measures = df_measures.select(pl.col("measures").struct.unnest())
        df_measures = df_measures.with_columns(
            pl.col("period")
            .cast(pl.String)
            .replace(
                {
                    900: "15_minutes",
                    86400: "daily",
                },
            )
            .alias("resolution"),
        )
        df_measures = df_measures.filter(
            pl.col("resolution").eq(parameter_or_dataset.dataset.resolution.name)
            & pl.col("@id").str.contains(parameter_or_dataset.name_original),
        )
        try:
            readings_id_url = df_measures.get_column("@id")[0]
        except IndexError:
            return pl.DataFrame()
        readings_url = f"{readings_id_url}/readings.json"
        file = download_file(
            url=readings_url,
            cache_dir=self.sr.stations.settings.cache_dir,
            ttl=CacheExpiry.FIVE_MINUTES,
            client_kwargs=self.sr.stations.settings.fsspec_client_kwargs,
            cache_disable=self.sr.stations.settings.cache_disable,
        )
        file.raise_if_exception()
        df = pl.read_json(
            file.content,
            schema={
                "items": pl.List(
                    pl.Struct(
                        {
                            "dateTime": pl.String,
                            "value": pl.Float64,
                            "quality": pl.String,
                        },
                    ),
                ),
            },
        )
        df = df.explode("items")
        df = df.select(pl.col("items").struct.unnest())
        return df.select(
            pl.lit(parameter_or_dataset.dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(parameter_or_dataset.dataset.name, dtype=pl.String).alias("dataset"),
            pl.lit(parameter_or_dataset.name_original).alias("parameter"),
            pl.lit(station_id, dtype=pl.String).alias("station_id"),
            pl.col("dateTime").str.to_datetime(format="%Y-%m-%dT%H:%M:%S", time_zone="UTC").alias("date"),
            pl.col("value"),
            pl.lit(None, dtype=pl.Float64).alias("quality"),
        )


@dataclass
class EAHydrologyRequest(TimeseriesRequest):
    """Request class for Environment Agency hydrology data."""

    metadata = EAHydrologyMetadata
    _values = EAHydrologyValues

    _url = "https://environment.data.gov.uk/hydrology/id/stations.json"

    _parameter_core_name_map: ClassVar = {
        # 15 minutes
        "discharge_instant": "flow",
        "groundwater_level_instant": "level",
        # daily
        "discharge_max": "flow",
        "discharge_mean": "flow",
        "discharge_min": "flow",
        "groundwater_level_max": "level",
        "groundwater_level_min": "level",
    }

    def _all(self) -> pl.LazyFrame:
        """Acquire all stations and filter for stations that have wanted resolution and parameter combinations."""
        file = download_file(
            url=self._url,
            cache_dir=self.settings.cache_dir,
            ttl=CacheExpiry.FIVE_MINUTES,
            client_kwargs=self.settings.fsspec_client_kwargs,
            cache_disable=self.settings.cache_disable,
        )
        file.raise_if_exception()
        df = pl.read_json(
            file.content,
            schema={
                "items": pl.List(
                    pl.Struct(
                        {
                            "label": pl.String,
                            "notation": pl.String,
                            "easting": pl.Int64,
                            "northing": pl.Int64,
                            "lat": pl.Float64,
                            "long": pl.Float64,
                            "dateOpened": pl.String,
                            "dateClosed": pl.String,
                            "measures": pl.List(
                                pl.Struct(
                                    [
                                        pl.Field("parameter", pl.String),
                                        pl.Field("period", pl.Int64),
                                    ],
                                ),
                            ),
                        },
                    ),
                ),
            },
        )
        df = df.lazy()
        df = df.select(pl.col("items").explode().struct.unnest())
        df = df.explode("measures")
        df = df.with_columns(pl.col("measures").struct.unnest())
        df = df.rename(
            mapping={
                "label": "name",
                "lat": "latitude",
                "long": "longitude",
                "notation": "station_id",
                "dateOpened": "start_date",
                "dateClosed": "end_date",
                "period": "resolution",
            },
        )
        df = df.with_columns(
            pl.col("resolution").cast(pl.String),
        )
        df = df.with_columns(
            pl.col("resolution").replace(
                {
                    "900": "15_minutes",
                    "86400": "daily",
                },
            ),
        )
        df = df.drop_nulls("resolution")
        resolution_parameter_pairs = {
            (parameter.dataset.resolution.name, self._parameter_core_name_map[parameter.name])
            for parameter in self.parameters
        }
        df = df.collect()
        df = df.filter(
            pl.concat_list(["resolution", "parameter"]).map_elements(
                lambda rp: tuple(rp) in resolution_parameter_pairs,
                return_dtype=pl.Boolean,
            )
        )
        df = df.lazy()
        return df.select(
            "resolution",
            pl.lit(DATASET_NAME_DEFAULT, dtype=pl.String).alias("dataset"),
            "station_id",
            pl.col("start_date").str.to_datetime(format="%Y-%m-%d"),
            pl.col("end_date").str.to_datetime(format="%Y-%m-%d"),
            "latitude",
            "longitude",
            pl.lit(None, pl.Float64).alias("height"),
            "name",
            pl.lit(None, pl.String).alias("state"),
        )
