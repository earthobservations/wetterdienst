# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Geosphere observation data provider."""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from itertools import groupby
from typing import TYPE_CHECKING, ClassVar
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.geosphere.observation.metadata import GeosphereObservationMetadata
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from wetterdienst.model.metadata import ParameterModel

log = logging.getLogger(__name__)


class GeosphereObservationValues(TimeseriesValues):
    """Values class for geosphere observation data."""

    _endpoint = (
        "https://dataset.api.hub.geosphere.at/v1/station/historical/{dataset}?"
        "parameters={parameter}&"
        "start={start_date}&"
        "end={end_date}&"
        "station_ids={station_id}&"
        "output_format=geojson"
    )
    # dates collected from ZAMG website, end date will be set to now if not given
    _default_start_dates: ClassVar = {
        Resolution.MINUTE_10: dt.datetime(1992, 5, 20, tzinfo=ZoneInfo("UTC")),
        Resolution.HOURLY: dt.datetime(1880, 3, 31, tzinfo=ZoneInfo("UTC")),
        Resolution.DAILY: dt.datetime(1774, 12, 31, tzinfo=ZoneInfo("UTC")),
        Resolution.MONTHLY: dt.datetime(1767, 11, 30, tzinfo=ZoneInfo("UTC")),
    }

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel,
    ) -> pl.DataFrame:
        start_date = self.sr.start_date or self._default_start_dates[parameter_or_dataset.dataset.resolution.value]
        end_date = self.sr.end_date or datetime.now(ZoneInfo("UTC"))
        # add buffers
        start_date = start_date - timedelta(days=1)
        end_date = end_date + timedelta(days=1)
        url = self._endpoint.format(
            station_id=station_id,
            parameter=parameter_or_dataset.name_original,
            dataset=parameter_or_dataset.dataset.name_original,
            start_date=start_date.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%m"),
            end_date=end_date.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%m"),
        )
        file = download_file(
            url=url,
            cache_dir=self.sr.stations.settings.cache_dir,
            ttl=CacheExpiry.FIVE_MINUTES,
            client_kwargs=self.sr.settings.fsspec_client_kwargs,
            cache_disable=self.sr.settings.cache_disable,
        )
        file.raise_if_exception()
        df = pl.read_json(
            file.content,
            schema={
                "timestamps": pl.List(pl.String),
                "features": pl.List(
                    pl.Struct(
                        {
                            "properties": pl.Struct(
                                {
                                    "parameters": pl.Struct(
                                        {
                                            parameter_or_dataset.name_original: pl.Struct(
                                                {
                                                    "data": pl.List(pl.Float64),
                                                },
                                            ),
                                        },
                                    ),
                                },
                            ),
                        },
                    ),
                ),
            },
        )
        series_timestamps = df.get_column("timestamps")
        series_timestamps = series_timestamps.explode()
        df = df.select("features")
        df = df.explode("features")
        df = df.select(pl.col("features").struct.unnest())
        df = df.select(pl.col("properties").struct.field("parameters").struct.unnest())
        df = df.unpivot(
            variable_name="parameter",
            value_name="value",
        )
        df = df.with_columns(
            pl.col("value").struct.field("data").alias("value"),
        )
        df = df.explode("value")
        # adjust units for radiation parameters of 10 minute/hourly resolution from W / m² to J / cm²
        if parameter_or_dataset.dataset.resolution.value == Resolution.MINUTE_10:
            df = df.with_columns(
                pl.when(pl.col("parameter").is_in(["cglo", "chim"]))
                .then(pl.col("value") * 600 / 10000)
                .otherwise(pl.col("value"))
                .alias("value"),
            )
        elif parameter_or_dataset.dataset.resolution.value == Resolution.HOURLY:
            df = df.with_columns(
                pl.when(pl.col("parameter").eq("cglo"))
                .then(pl.col("value") * 3600 / 10000)
                .otherwise(pl.col("value"))
                .alias("value"),
            )
        return df.select(
            pl.lit(parameter_or_dataset.dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(parameter_or_dataset.dataset.name, dtype=pl.String).alias("dataset"),
            pl.col("parameter").str.to_lowercase(),
            pl.lit(station_id, dtype=pl.String).alias("station_id"),
            series_timestamps.alias("date").str.to_datetime("%Y-%m-%dT%H:%M+%Z").dt.replace_time_zone("UTC"),
            pl.col("value"),
            pl.lit(None, pl.Float64).alias("quality"),
        )


@dataclass
class GeosphereObservationRequest(TimeseriesRequest):
    """Request class for geosphere observation data."""

    metadata = GeosphereObservationMetadata
    _values = GeosphereObservationValues

    _endpoint = "https://dataset.api.hub.zamg.ac.at/v1/station/historical/{dataset}/metadata/stations"

    def _all(self) -> pl.LazyFrame:
        data = []
        for dataset, _ in groupby(self.parameters, key=lambda x: x.dataset):
            url = self._endpoint.format(dataset=dataset.name_original)
            file = download_file(
                url=url,
                cache_dir=self.settings.cache_dir,
                ttl=CacheExpiry.METAINDEX,
                client_kwargs=self.settings.fsspec_client_kwargs,
                cache_disable=self.settings.cache_disable,
            )
            file.raise_if_exception()
            df = pl.read_csv(file.content)
            df = df.lazy()
            df = df.drop("Sonnenschein", "Globalstrahlung")
            df = df.rename(
                mapping={
                    "id": "station_id",
                    "Stationsname": "name",
                    "Länge [°E]": "longitude",
                    "Breite [°N]": "latitude",
                    "Höhe [m]": "height",
                    "Startdatum": "start_date",
                    "Enddatum": "end_date",
                    "Bundesland": "state",
                },
            )
            df = df.with_columns(
                pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
                pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            )
            data.append(df)
        df = pl.concat(data)
        return df.with_columns(
            pl.col("start_date").str.to_datetime(format="%Y-%m-%d %H:%M:%S%z", time_zone="UTC"),
            pl.col("end_date").str.to_datetime(format="%Y-%m-%d %H:%M:%S%z", time_zone="UTC"),
        )
