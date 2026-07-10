# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""MeteoSwiss observation data provider."""

from __future__ import annotations

import json
import logging
import re
from dataclasses import dataclass
from itertools import groupby
from typing import TYPE_CHECKING, ClassVar, cast

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.meteoswiss.observation.metadata import MeteoswissObservationMetadata
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from wetterdienst.model.metadata import DatasetModel, ParameterModel
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)


class MeteoswissObservationValues(TimeseriesValues):
    """Values class for MeteoSwiss observation data."""

    # STAC item per station lists the exact assets (csv files) available for that station,
    # which is required as historical data is split into decade chunks whose exact ranges
    # vary per station.
    _item_endpoint = "https://data.geo.admin.ch/api/stac/v1/collections/ch.meteoschweiz.ogd-smn/items/{station_id}"

    # explicit, per-granularity schema of the exact columns published by the source API
    # (https://data.geo.admin.ch/ch.meteoschweiz.ogd-smn/), read as strings throughout since the
    # set of populated columns differs between decade-chunked historical files, which would
    # otherwise lead to inconsistent dtype inference (e.g. an all-null column inferred as Boolean
    # in one file and Float64 in another) and break the concat below. Column order matches the
    # source CSV, as required by polars' `schema` argument.
    _csv_schemas: ClassVar = {
        "t": {
            "station_abbr": pl.String,
            "reference_timestamp": pl.String,
            "tre200s0": pl.String,
            "tre005s0": pl.String,
            "tresurs0": pl.String,
            "xchills0": pl.String,
            "ure200s0": pl.String,
            "tde200s0": pl.String,
            "pva200s0": pl.String,
            "prestas0": pl.String,
            "pp0qnhs0": pl.String,
            "pp0qffs0": pl.String,
            "ppz850s0": pl.String,
            "ppz700s0": pl.String,
            "fkl010z1": pl.String,
            "fve010z0": pl.String,
            "fkl010z0": pl.String,
            "dkl010z0": pl.String,
            "wcc006s0": pl.String,
            "fu3010z0": pl.String,
            "fkl010z3": pl.String,
            "fu3010z1": pl.String,
            "fu3010z3": pl.String,
            "rre150z0": pl.String,
            "htoauts0": pl.String,
            "gre000z0": pl.String,
            "ods000z0": pl.String,
            "oli000z0": pl.String,
            "olo000z0": pl.String,
            "osr000z0": pl.String,
            "sre000z0": pl.String,
            "tso005s0": pl.String,
            "tso010s0": pl.String,
            "tso020s0": pl.String,
        },
        "h": {
            "station_abbr": pl.String,
            "reference_timestamp": pl.String,
            "tre200h0": pl.String,
            "tre200hn": pl.String,
            "tre200hx": pl.String,
            "tre005h0": pl.String,
            "tre005hn": pl.String,
            "ure200h0": pl.String,
            "pva200h0": pl.String,
            "tde200h0": pl.String,
            "prestah0": pl.String,
            "pp0qffh0": pl.String,
            "pp0qnhh0": pl.String,
            "ppz700h0": pl.String,
            "ppz850h0": pl.String,
            "fkl010h1": pl.String,
            "dkl010h0": pl.String,
            "fkl010h0": pl.String,
            "fu3010h0": pl.String,
            "fu3010h1": pl.String,
            "fkl010h3": pl.String,
            "fu3010h3": pl.String,
            "wcc006h0": pl.String,
            "fve010h0": pl.String,
            "rre150h0": pl.String,
            "htoauths": pl.String,
            "gre000h0": pl.String,
            "oli000h0": pl.String,
            "olo000h0": pl.String,
            "osr000h0": pl.String,
            "ods000h0": pl.String,
            "sre000h0": pl.String,
            "erefaoh0": pl.String,
            "tso005hs": pl.String,
            "tso010hs": pl.String,
            "tso020hs": pl.String,
        },
        "d": {
            "station_abbr": pl.String,
            "reference_timestamp": pl.String,
            "tre200d0": pl.String,
            "tre200dx": pl.String,
            "tre200dn": pl.String,
            "tre005d0": pl.String,
            "tre005dx": pl.String,
            "tre005dn": pl.String,
            "ure200d0": pl.String,
            "pva200d0": pl.String,
            "prestad0": pl.String,
            "pp0qffd0": pl.String,
            "ppz850d0": pl.String,
            "ppz700d0": pl.String,
            "pp0qnhd0": pl.String,
            "fkl010d0": pl.String,
            "fkl010d1": pl.String,
            "fu3010d0": pl.String,
            "fu3010d1": pl.String,
            "fkl010d3": pl.String,
            "fu3010d3": pl.String,
            "wcc006d0": pl.String,
            "rre150d0": pl.String,
            "rka150d0": pl.String,
            "htoautd0": pl.String,
            "gre000d0": pl.String,
            "oli000d0": pl.String,
            "olo000d0": pl.String,
            "osr000d0": pl.String,
            "ods000d0": pl.String,
            "sre000d0": pl.String,
            "sremaxdv": pl.String,
            "erefaod0": pl.String,
            "xcd000d0": pl.String,
            "dkl010d0": pl.String,
            "xno000d0": pl.String,
            "xno012d0": pl.String,
            "rreetsd0": pl.String,
            "tso005d0": pl.String,
            "tso010d0": pl.String,
            "tso020d0": pl.String,
        },
        "m": {
            "station_abbr": pl.String,
            "reference_timestamp": pl.String,
            "tre200m0": pl.String,
            "tre200mx": pl.String,
            "tre200mn": pl.String,
            "tre005m0": pl.String,
            "tre005mn": pl.String,
            "tre005mx": pl.String,
            "ure200m0": pl.String,
            "pva200m0": pl.String,
            "prestam0": pl.String,
            "pp0qffm0": pl.String,
            "ppz850m0": pl.String,
            "ppz700m0": pl.String,
            "pp0qnhm0": pl.String,
            "fkl010m0": pl.String,
            "fkl010m1": pl.String,
            "fu3010m0": pl.String,
            "fu3010m1": pl.String,
            "rre150m0": pl.String,
            "gre000m0": pl.String,
            "oli000m0": pl.String,
            "olo000m0": pl.String,
            "osr000m0": pl.String,
            "sre000m0": pl.String,
            "sremaxmv": pl.String,
            "erefaom0": pl.String,
            "xcd000m0": pl.String,
            "xno000m0": pl.String,
            "xno012m0": pl.String,
            "rreetsm0": pl.String,
            "tso005m0": pl.String,
            "tso010m0": pl.String,
            "tso020m0": pl.String,
            "tnd00nm0": pl.String,
            "tnd00xm0": pl.String,
            "tnd20nm0": pl.String,
            "tnd25xm0": pl.String,
            "tnd30xm0": pl.String,
            "tnd35xm0": pl.String,
        },
        "y": {
            "station_abbr": pl.String,
            "reference_timestamp": pl.String,
            "tre200y0": pl.String,
            "tre200yx": pl.String,
            "tre200yn": pl.String,
            "tre005y0": pl.String,
            "tre005yx": pl.String,
            "tre005yn": pl.String,
            "ure200y0": pl.String,
            "pva200y0": pl.String,
            "prestay0": pl.String,
            "pp0qffy0": pl.String,
            "ppz850y0": pl.String,
            "ppz700y0": pl.String,
            "pp0qnhy0": pl.String,
            "fkl010y0": pl.String,
            "fkl010y1": pl.String,
            "fu3010y1": pl.String,
            "fu3010y0": pl.String,
            "rre150y0": pl.String,
            "gre000y0": pl.String,
            "oli000y0": pl.String,
            "olo000y0": pl.String,
            "osr000y0": pl.String,
            "sre000y0": pl.String,
            "sremaxyv": pl.String,
            "erefaoy0": pl.String,
            "xcd000y0": pl.String,
            "xno000y0": pl.String,
            "xno012y0": pl.String,
            "rreetsy0": pl.String,
            "tso005y0": pl.String,
            "tso010y0": pl.String,
            "tso020y0": pl.String,
            "tnd00ny0": pl.String,
            "tnd00xy0": pl.String,
            "tnd20ny0": pl.String,
            "tnd25xy0": pl.String,
            "tnd30xy0": pl.String,
            "tnd35xy0": pl.String,
        },
    }

    # historical 10-minute/hourly data is split into decade chunks, e.g. "..._historical_2000-2009.csv";
    # the range is encoded in the filename, so those chunks that don't overlap the requested date range
    # can be skipped without an extra request, avoiding large unnecessary downloads for old stations
    _decade_pattern = re.compile(r"_historical_(\d{4})-(\d{4})\.csv$")

    def _asset_overlaps_request(self, asset_name: str) -> bool:
        """Check whether a decade-chunked historical asset overlaps the requested date range."""
        start_date, end_date = self.sr.start_date, self.sr.end_date
        if not start_date or not end_date:
            return True
        decade_match = self._decade_pattern.search(asset_name)
        if not decade_match:
            return True
        decade_start, decade_end = int(decade_match.group(1)), int(decade_match.group(2))
        return decade_end >= start_date.year and decade_start <= end_date.year

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel | DatasetModel,
    ) -> pl.DataFrame:
        dataset = cast("DatasetModel", parameter_or_dataset)
        granularity = dataset.resolution.name_original
        station_id_lower = station_id.lower()
        settings = cast("Settings", self.sr.stations.settings)
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
        schema = self._csv_schemas[granularity]
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
                    schema=schema,
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
        return df.select(
            pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            pl.col("parameter").str.to_lowercase(),
            pl.lit(station_id, dtype=pl.String).alias("station_id"),
            pl.col("reference_timestamp")
            .str.to_datetime("%d.%m.%Y %H:%M", strict=False)
            .dt.replace_time_zone("UTC")
            .alias("date"),
            pl.col("value").cast(pl.Float64, strict=False),
            pl.lit(None, pl.Float64).alias("quality"),
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
            pl.col("station_canton").alias("state"),
            pl.col("station_coordinates_wgs84_lat").alias("latitude"),
            pl.col("station_coordinates_wgs84_lon").alias("longitude"),
            pl.col("station_height_masl").alias("height"),
            pl.col("station_data_since")
            .str.to_datetime("%d.%m.%Y", strict=False)
            .dt.replace_time_zone("UTC")
            .alias("start_date"),
        )
        data = []
        for dataset, _ in groupby(self.parameters, key=lambda x: x.dataset):
            data.append(
                df.with_columns(
                    pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
                    pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
                ),
            )
        return pl.concat(data)
