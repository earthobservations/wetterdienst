# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""MeteoSwiss observation data provider."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import group_parameters_by_dataset
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.meteoswiss.observation.metadata import MeteoswissObservationMetadata
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from collections.abc import Iterable

    from wetterdienst.model.metadata import DatasetModel, ParameterModel
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)


class MeteoswissObservationValues(TimeseriesValues):
    """Values class for MeteoSwiss observation data."""

    # STAC item per station lists the exact assets (csv files) available for that station,
    # which is required as historical data is split into decade chunks whose exact ranges
    # vary per station.
    _item_endpoint = "https://data.geo.admin.ch/api/stac/v1/collections/ch.meteoschweiz.ogd-smn/items/{station_id}"

    # historical 10-minute/hourly data is split into decade chunks, e.g. "..._historical_2000-2009.csv";
    # the range is encoded in the filename, so those chunks that don't overlap the requested date range
    # can be skipped without an extra request, avoiding large unnecessary downloads for old stations
    _decade_pattern = re.compile(r"_historical_(\d{4})-(\d{4})\.csv$")

    def _asset_overlaps_request(self, asset_name: str) -> bool:
        """Check whether a decade-chunked historical asset overlaps the requested date range."""
        start_date, end_date = self.sr.start, self.sr.end
        if not start_date or not end_date:
            return True
        decade_match = self._decade_pattern.search(asset_name)
        if not decade_match:
            return True
        decade_start, decade_end = int(decade_match.group(1)), int(decade_match.group(2))
        # the decades are decades of UTC time stamps, the zone of the request's bounds
        start_year, end_year = start_date.year, end_date.year
        return decade_end >= start_year and decade_start <= end_year

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel | DatasetModel,
    ) -> pl.DataFrame:
        dataset = cast("DatasetModel", parameter_or_dataset)
        granularity = dataset.resolution.name_original
        station_id_lower = station_id.lower()
        settings = cast("Settings", self.sr.request.settings)
        item_url = self._item_endpoint.format(station_id=station_id_lower)
        file = download_file(
            url=item_url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.DataFrame()
        item = json.loads(file.content.read())
        assets = item.get("assets", {})
        pattern = re.compile(rf"^ogd-smn_{re.escape(station_id_lower)}_{granularity}(_.*)?\.csv$")
        urls = sorted(
            asset["href"]
            for name, asset in assets.items()
            if pattern.match(name) and self._asset_overlaps_request(name)
        )
        if not urls:
            return pl.DataFrame()
        dfs = []
        for url in urls:
            csv_file = download_file(
                url=url,
                cache_dir=settings.cache_dir,
                ttl=CacheExpiry.FIVE_MINUTES,
                client_kwargs=settings.fsspec_client_kwargs,
                cache_disable=settings.cache_disable,
                use_certifi=settings.use_certifi,
            )
            csv_file.raise_if_exception()
            if isinstance(csv_file.content, Exception):
                continue
            dfs.append(
                pl.read_csv(
                    csv_file.content,
                    separator=";",
                    encoding="windows-1252",
                    # strings throughout, whatever the file populates: the set of populated columns
                    # differs between decade-chunked historical files, and an all-null column would
                    # otherwise be inferred as Boolean in one file and Float64 in another, which
                    # breaks the concat below. The columns are named by the file's own header.
                    infer_schema=False,
                ),
            )
        if not dfs:
            return pl.DataFrame()
        df = pl.concat(dfs, how="diagonal")
        parameter_columns = [col for col in df.columns if col not in ("station_abbr", "reference_timestamp")]
        df = df.unpivot(
            on=parameter_columns,
            index=["reference_timestamp"],
            variable_name="parameter",
            value_name="value",
        )
        # the station, resolution and dataset are the core's to write (`shape_provider_frame`), and so is the
        # reading of the value as a number
        return df.select(
            pl.col("parameter").str.to_lowercase(),
            pl.col("reference_timestamp").str.to_datetime("%d.%m.%Y %H:%M", strict=False).alias("timestamp"),
            pl.col("value"),
        )


@dataclass
class MeteoswissObservationRequest(TimeseriesRequest):
    """Request class for MeteoSwiss observation data."""

    metadata = MeteoswissObservationMetadata
    _values = MeteoswissObservationValues

    _station_endpoint = "https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/ogd-smn_meta_stations.csv"

    def _all(self) -> pl.LazyFrame:
        settings = cast("Settings", self.settings)
        file = download_file(
            url=self._station_endpoint,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.LazyFrame()
        df = pl.read_csv(file.content, separator=";", encoding="windows-1252")
        df = df.lazy()
        df = df.select(
            pl.col("station_abbr").alias("station_id"),
            pl.col("station_name").alias("name"),
            pl.col("station_canton").alias("region"),
            pl.col("station_coordinates_wgs84_lat").alias("latitude"),
            pl.col("station_coordinates_wgs84_lon").alias("longitude"),
            pl.col("station_height_masl").alias("elevation"),
            pl.col("station_data_since").str.to_datetime("%d.%m.%Y", strict=False).alias("start_timestamp"),
        )
        data = []
        for dataset, _ in group_parameters_by_dataset(cast("Iterable[ParameterModel]", self.parameters)):
            data.append(
                df.with_columns(
                    pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
                    pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
                ),
            )
        return pl.concat(data)
