# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Météo-France SYNOP data provider."""

from __future__ import annotations

import gzip
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import IO, TYPE_CHECKING, cast
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.meteofrance.synop.metadata import MeteoFranceSynopMetadata
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from collections.abc import Iterable

    from wetterdienst.model.metadata import DatasetModel, ParameterModel
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

# "Archive Synop OMM" dataset on data.gouv.fr: one gzipped csv per year, covering all ~190
# SYNOP stations at their native 3-hourly reporting interval
_SYNOP_ENDPOINT = "https://meteofrance.s3.sbg.io.cloud.ovh.net/data/synchro_ftp/OBS/SYNOP/synop_{year}.csv.gz"
_SYNOP_STATIONS_ENDPOINT = "https://meteofrance.s3.sbg.io.cloud.ovh.net/data/synchro_ftp/OBS/SYNOP/postes_synop.geojson"
# earliest year for which a yearly archive is published
_SYNOP_ARCHIVE_START_YEAR = 1996

# explicit schema of the exact columns published by the source, read as strings throughout since
# many columns are entirely empty for a given station or year, which would otherwise lead to
# inconsistent dtype inference (e.g. an all-null column inferred as Boolean in one year and
# Float64 in another) and break the concat below. Column order matches the source CSV, as
# required by polars' `schema` argument.
_SYNOP_CSV_SCHEMA = {
    "lat": pl.String,
    "lon": pl.String,
    "geo_id_wmo": pl.String,
    "geo_id_wigos": pl.String,
    "name": pl.String,
    "reference_time": pl.String,
    "insert_time": pl.String,
    "validity_time": pl.String,
    "pmer": pl.String,
    "tend": pl.String,
    "cod_tend": pl.String,
    "dd": pl.String,
    "ff": pl.String,
    "t": pl.String,
    "td": pl.String,
    "u": pl.String,
    "vv": pl.String,
    "ww": pl.String,
    "w1": pl.String,
    "w2": pl.String,
    "n": pl.String,
    "nbas": pl.String,
    "hbas": pl.String,
    "cl": pl.String,
    "cm": pl.String,
    "ch": pl.String,
    "pres": pl.String,
    "niv_bar": pl.String,
    "geop": pl.String,
    "tend24": pl.String,
    "tn12": pl.String,
    "tn24": pl.String,
    "tx12": pl.String,
    "tx24": pl.String,
    "tminsol": pl.String,
    "sw": pl.String,
    "tw": pl.String,
    "raf10": pl.String,
    "rafper": pl.String,
    "per": pl.String,
    "etat_sol": pl.String,
    "ht_neige": pl.String,
    "ssfrai": pl.String,
    "perssfrai": pl.String,
    "rr1": pl.String,
    "rr3": pl.String,
    "rr6": pl.String,
    "rr12": pl.String,
    "rr24": pl.String,
    "phenspe1": pl.String,
    "phenspe2": pl.String,
    "phenspe3": pl.String,
    "phenspe4": pl.String,
    "nnuage1": pl.String,
    "ctype1": pl.String,
    "hnuage1": pl.String,
    "nnuage2": pl.String,
    "ctype2": pl.String,
    "hnuage2": pl.String,
    "nnuage3": pl.String,
    "ctype3": pl.String,
    "hnuage3": pl.String,
    "nnuage4": pl.String,
    "ctype4": pl.String,
    "hnuage4": pl.String,
}


class MeteoFranceSynopValues(TimeseriesValues):
    """Values class for Météo-France SYNOP data."""

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel | DatasetModel,
    ) -> pl.DataFrame:
        dataset = cast("DatasetModel", parameter_or_dataset)
        current_year = datetime.now(tz=ZoneInfo("UTC")).year
        start_date = self.sr.start_date or datetime(_SYNOP_ARCHIVE_START_YEAR, 1, 1, tzinfo=ZoneInfo("UTC"))
        end_date = self.sr.end_date or datetime.now(tz=ZoneInfo("UTC"))
        settings = cast("Settings", self.sr.stations.settings)
        parameter_columns = [parameter.name_original for parameter in dataset]
        read_columns = ["geo_id_wmo", "validity_time", *parameter_columns]
        dfs = []
        # clamp to the years actually covered by the archive: station opening dates (used as a
        # fallback start_date by e.g. the frontend) can predate 1996, and requesting a year
        # outside [1996, current_year] would 404
        first_year = max(start_date.year, _SYNOP_ARCHIVE_START_YEAR)
        last_year = min(end_date.year, current_year)
        for year in range(first_year, last_year + 1):
            file = download_file(
                url=_SYNOP_ENDPOINT.format(year=year),
                cache_dir=settings.cache_dir,
                ttl=CacheExpiry.FIVE_MINUTES if year == current_year else CacheExpiry.INFINITE,
                client_kwargs=settings.fsspec_client_kwargs,
                cache_disable=settings.cache_disable,
                use_certifi=settings.use_certifi,
            )
            if isinstance(file.content, Exception):
                if not file.is_no_internet_error:
                    # the year range above is already clamped to the archive's known coverage,
                    # so a failure here (unlike a missing-year 404) is unexpected; log it instead
                    # of silently treating this year as having no data, but keep processing the
                    # remaining years rather than aborting the whole multi-year request
                    log.warning(f"Failed to download {file.url}: {file.content}")
                continue
            with gzip.GzipFile(fileobj=file.content) as gz:
                df = pl.read_csv(cast("IO[bytes]", gz), separator=";", schema=_SYNOP_CSV_SCHEMA, columns=read_columns)
            df = df.filter(pl.col("geo_id_wmo").eq(station_id))
            if not df.is_empty():
                dfs.append(df)
        if not dfs:
            return pl.DataFrame()
        df = pl.concat(dfs, how="diagonal")
        df = df.unpivot(
            on=parameter_columns,
            index=["validity_time"],
            variable_name="parameter",
            value_name="value",
        )
        return df.select(
            pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            pl.col("parameter").str.to_lowercase(),
            pl.lit(station_id, dtype=pl.String).alias("station_id"),
            pl.col("validity_time")
            .str.to_datetime("%Y-%m-%dT%H:%M:%SZ", strict=False)
            .dt.replace_time_zone("UTC")
            .alias("date"),
            pl.col("value").cast(pl.Float64, strict=False),
            pl.lit(None, pl.Float64).alias("quality"),
        )


@dataclass
class MeteoFranceSynopRequest(TimeseriesRequest):
    """Request class for Météo-France SYNOP data."""

    metadata = MeteoFranceSynopMetadata
    _values = MeteoFranceSynopValues

    def _all(self) -> pl.LazyFrame:
        settings = cast("Settings", self.settings)
        file = download_file(
            url=_SYNOP_STATIONS_ENDPOINT,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.LazyFrame()
        collection = json.loads(file.content.read())
        rows = []
        for feature in collection.get("features", []):
            properties = feature["properties"]
            longitude, latitude = feature["geometry"]["coordinates"]
            rows.append(
                {
                    "station_id": properties["Id"],
                    "name": properties["Nom"],
                    "height": properties["Altitude"],
                    "start_date": properties["Date_ouverture"],
                    "latitude": latitude,
                    "longitude": longitude,
                },
            )
        df = pl.DataFrame(
            rows,
            schema={
                "station_id": pl.String,
                "name": pl.String,
                "height": pl.Float64,
                "start_date": pl.String,
                "latitude": pl.Float64,
                "longitude": pl.Float64,
            },
        )
        df = df.lazy()
        df = df.with_columns(
            pl.col("start_date").str.to_datetime("%Y-%m-%d", strict=False).dt.replace_time_zone("UTC"),
        )
        # self.parameters is parsed at runtime to a list[ParameterModel], but the static type of
        # the attribute is a union of input forms; cast here so the typechecker understands we
        # iterate ParameterModel instances.
        parameters = cast("Iterable[ParameterModel]", self.parameters)
        # groupby() only groups consecutive items, but parameters preserves the user-supplied
        # order, so datasets interleaved across parameters would otherwise produce duplicate
        # groups for the same dataset and duplicate station rows
        datasets = {(p.dataset.resolution.name, p.dataset.name): p.dataset for p in parameters}
        data = [
            df.with_columns(
                pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
                pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            )
            for dataset in datasets.values()
        ]
        return pl.concat(data)
