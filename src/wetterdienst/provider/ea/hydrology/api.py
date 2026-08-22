# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Environment Agency hydrology API."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

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

if TYPE_CHECKING:
    from wetterdienst.settings import Settings

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
                            "unit": "cubic_meter_per_second",
                        },
                        {
                            "name": "groundwater_level",
                            "name_original": "level-i-900",
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
                            "unit": "cubic_meter_per_second",
                        },
                        {
                            "name": "discharge_mean",
                            "name_original": "flow-m-86400",
                            "unit": "cubic_meter_per_second",
                        },
                        {
                            "name": "discharge_min",
                            "name_original": "flow-min-86400",
                            "unit": "cubic_meter_per_second",
                        },
                        {
                            "name": "groundwater_level_max",
                            "name_original": "level-max-86400",
                            "unit": "meter",
                        },
                        {
                            "name": "groundwater_level_min",
                            "name_original": "level-min-86400",
                            "unit": "meter",
                        },
                    ],
                },
            ],
        },
    ],
}
EAHydrologyMetadata = build_metadata_model(EAHydrologyMetadata, "EAHydrologyMetadata")


def _measure_parameter(parameter: ParameterModel) -> str:
    """Give the parameter of the EA measure a wetterdienst parameter is taken from.

    A measure is notated `{parameter}-{statistic}-{period}`, so `flow-i-900` is the flow measured
    every 900 seconds and `level-max-86400` the daily maximum level. The station listing names the
    parameter and the period of each measure but not the statistic, which is why the leading token
    is read off the notation rather than the notation matched whole.

    Derived from the notation the metadata already carries so that renaming a wetterdienst
    parameter cannot separate the two: the map this replaces still keyed the 15-minute parameters
    as `discharge_instant` and `groundwater_level_instant`, names the metadata had long since
    dropped, and every 15-minute request died on the lookup.
    """
    return parameter.name_original.split("-")[0]


# the period of each measure, in seconds, and the resolution it is served under. Read off the
# trailing token of the notations the metadata declares, so a resolution added there is served
# without a second table having to learn its period.
_RESOLUTIONS_BY_PERIOD: dict[str, str] = {
    parameter.name_original.split("-")[-1]: resolution.name
    for resolution in EAHydrologyMetadata
    for dataset in resolution
    for parameter in dataset.parameters
}


class EAHydrologyValues(TimeseriesValues):
    """Values class for Environment Agency hydrology data."""

    _url = "https://environment.data.gov.uk/hydrology/id/stations/{station_id}.json"

    def _collect_station_parameter_or_dataset(  # ty: ignore[invalid-method-override]
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel,
    ) -> pl.DataFrame:
        """Collect data for a station, parameter or dataset."""
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.sr.stations.settings)
        url = self._url.format(station_id=station_id)
        file = download_file(
            url=url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.NO_CACHE,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.DataFrame()
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
        df_measures = df_measures.explode("items", empty_as_null=True)
        df_measures = df_measures.select(pl.col("items").struct.field("measures"))
        df_measures = df_measures.explode("measures", empty_as_null=True)
        df_measures = df_measures.select(pl.col("measures").struct.unnest())
        df_measures = df_measures.with_columns(
            pl.col("period").cast(pl.String).replace(_RESOLUTIONS_BY_PERIOD).alias("resolution"),
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
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.FIVE_MINUTES,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.DataFrame()
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
        df = df.explode("items", empty_as_null=True)
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

    def _all(self) -> pl.LazyFrame:
        """Acquire all stations and filter for stations that have wanted resolution and parameter combinations."""
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.settings)
        file = download_file(
            url=self._url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.FIVE_MINUTES,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.LazyFrame()
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
        df = df.select(pl.col("items").explode(empty_as_null=True).struct.unnest())
        df = df.explode("measures", empty_as_null=True)
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
            pl.col("resolution").cast(pl.String).replace(_RESOLUTIONS_BY_PERIOD),
        )
        df = df.drop_nulls("resolution")
        resolution_parameter_keys = {
            f"{parameter.dataset.resolution.name}/{_measure_parameter(parameter)}"
            for parameter in self.parameters
            if isinstance(parameter, ParameterModel)
        }
        result = df.collect(background=False)
        if not isinstance(result, pl.DataFrame):
            msg = "Expected DataFrame, got InProcessQuery"
            raise TypeError(msg)
        df = result.filter(
            pl.concat_str(["resolution", "parameter"], separator="/").is_in(resolution_parameter_keys),
        )
        df = df.lazy()
        df = df.select(
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
        # the listing carries one row per measure, so a station recording two of the requested
        # parameters -- or, at daily, two statistics of one of them, which share the parameter and
        # the period the listing reports -- arrives once per measure. Left in, the duplicates make
        # `filter_by_rank` answer with more stations than were asked for
        return df.unique(subset=["resolution", "dataset", "station_id"], keep="first", maintain_order=True)
