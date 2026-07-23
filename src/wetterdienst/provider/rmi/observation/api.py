# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""RMI (Royal Meteorological Institute of Belgium) AWS observation provider.

RMI publishes automatic weather station (AWS) observations through an open, key-less GeoServer
WFS service (GeoJSON). Each resolution is exposed as its own feature type -- ``aws:aws_10min``,
``aws:aws_1hour`` and ``aws:aws_1day`` -- plus a station layer ``aws:aws_station``. A single
``GetFeature`` request filtered with a CQL predicate (``code = <station> AND timestamp DURING
<start>/<end>``) returns every parameter for that station in the requested window as one wide
feature per timestamp -- see https://www.geo.be/catalog/details/RMI_AWS_WFS.
"""

from __future__ import annotations

import itertools
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from urllib.parse import quote
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import DatasetModel, ParameterModel
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.rmi.observation.metadata import RmiObservationMetadata
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from collections.abc import Iterator, Sequence

    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

_BASE_URL = "https://opendata.meteo.be/service/aws/wfs"
_UTC = ZoneInfo("UTC")
# GeoServer serves the whole matched set in one page for realistic station/date windows, but
# paginate defensively (startIndex/count) so a very long range can never hit a server-side cap.
_PAGE_LIMIT = 500_000

_EMPTY_VALUES_SCHEMA = {
    "resolution": pl.String,
    "dataset": pl.String,
    "parameter": pl.String,
    "station_id": pl.String,
    "date": pl.Datetime(time_unit="us", time_zone="UTC"),
    "value": pl.Float64,
    "quality": pl.Float64,
}

_STATION_ENDPOINT = (
    f"{_BASE_URL}?service=WFS&version=2.0.0&request=GetFeature&typeNames=aws:aws_station&outputFormat=application/json"
)

_STATION_SCHEMA = pl.Schema(
    {
        "features": pl.List(
            pl.Struct(
                {
                    "geometry": pl.Struct({"coordinates": pl.List(pl.Float64)}),
                    "properties": pl.Struct(
                        {
                            "code": pl.Int64,
                            "name": pl.String,
                            "date_begin": pl.String,
                            "date_end": pl.String,
                            "altitude": pl.Float64,
                        }
                    ),
                }
            )
        ),
    }
)


def _values_schema(parameters: Sequence[ParameterModel]) -> pl.Schema:
    """Build the WFS feature schema for a dataset's parameters.

    Only the ``timestamp`` and the mapped parameter columns are declared; ``read_json`` ignores
    every other attribute (``code``, geometry, ``qc_flags``, unmapped parameters).
    """
    properties: dict[str, type[pl.DataType]] = {"timestamp": pl.String}
    for parameter in parameters:
        properties[parameter.name_original] = pl.Float64
    return pl.Schema({"features": pl.List(pl.Struct({"properties": pl.Struct(properties)}))})


class RmiObservationValues(TimeseriesValues):
    """Values class for RMI AWS observations."""

    def _iter_value_pages(
        self,
        layer: str,
        cql_filter: str,
        schema: pl.Schema,
        settings: Settings,
    ) -> Iterator[pl.DataFrame]:
        """Yield each page of WFS features (as unnested ``properties`` frames) for a query.

        Pages are walked via ``startIndex`` until a short (or empty) page marks the end; stops on
        the first download error.
        """
        for start_index in itertools.count(0, _PAGE_LIMIT):
            # `sortBy` is mandatory once `startIndex` paging is used: the feature types have no
            # primary key, so GeoServer otherwise rejects the request ("Cannot do natural order
            # without a primary key"). Sorting by timestamp also makes the paging deterministic.
            url = (
                f"{_BASE_URL}?service=WFS&version=2.0.0&request=GetFeature"
                f"&typeNames=aws:{layer}&outputFormat=application/json"
                f"&count={_PAGE_LIMIT}&startIndex={start_index}&sortBy=timestamp"
                f"&cql_filter={quote(cql_filter, safe='')}"
            )
            file = download_file(
                url=url,
                cache_dir=settings.cache_dir,
                ttl=CacheExpiry.FIVE_MINUTES,
                client_kwargs=settings.fsspec_client_kwargs,
                cache_disable=settings.cache_disable,
                use_certifi=settings.use_certifi,
            )
            if isinstance(file.content, Exception):
                # NoInternetError is already logged at debug by download_file and is an expected
                # offline condition, so don't add a warning for it; warn only on real failures.
                if not file.is_no_internet_error:
                    log.warning(f"Failed to acquire RMI data (filter {cql_filter!r}): {file.content}")
                return
            df = pl.read_json(file.content, schema=schema)
            df = df.select(pl.col("features").explode().struct.field("properties")).unnest("properties")
            if not df.is_empty():
                yield df
            if df.height < _PAGE_LIMIT:
                return

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel | DatasetModel,
    ) -> pl.DataFrame:
        if isinstance(parameter_or_dataset, DatasetModel):
            dataset = parameter_or_dataset
        elif isinstance(parameter_or_dataset, ParameterModel):
            dataset = parameter_or_dataset.dataset
        else:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        settings = cast("Settings", self.sr.stations.settings)
        start_date = self.sr.start_date
        end_date = self.sr.end_date
        if not start_date or not end_date:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        # Every RMI timestamp is a true UTC instant (label == the value CQL filters on), so the
        # window needs no margin. Normalise to UTC so the "Z" bounds are correct even for callers
        # that pass tz-aware, non-UTC dates; TimeseriesValues.query() trims to the exact range.
        start = start_date.astimezone(_UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        end = end_date.astimezone(_UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
        cql_filter = f"code = {station_id} AND timestamp DURING {start}/{end}"

        layer = dataset.resolution.name_original
        schema = _values_schema(dataset.parameters)
        frames = list(self._iter_value_pages(layer, cql_filter, schema, settings))
        if not frames:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        df = pl.concat(frames)
        # Reshape the wide feature (one column per parameter) into the long value frame. The
        # column name is already `name_original`, which `_process_dataset` filters against.
        df = df.unpivot(
            index="timestamp",
            on=[parameter.name_original for parameter in dataset.parameters],
            variable_name="parameter",
            value_name="value",
        ).drop_nulls("value")
        if df.is_empty():
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
        return df.select(
            pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            pl.col("parameter"),
            pl.lit(station_id, dtype=pl.String).alias("station_id"),
            pl.col("timestamp")
            .str.to_datetime("%Y-%m-%dT%H:%M:%SZ", time_unit="us")
            .dt.replace_time_zone("UTC")
            .alias(
                "date",
            ),
            pl.col("value").cast(pl.Float64),
            pl.lit(None, dtype=pl.Float64).alias("quality"),
        )


@dataclass
class RmiObservationRequest(TimeseriesRequest):
    """Request class for RMI (Royal Meteorological Institute of Belgium) AWS observations.

    - https://www.meteo.be/en/about-rmi/observation-network/automatische-weerstations
    - https://www.geo.be/catalog/details/RMI_AWS_WFS
    """

    metadata = RmiObservationMetadata
    _values = RmiObservationValues

    def _all(self) -> pl.LazyFrame:
        settings = cast("Settings", self.settings)
        file = download_file(
            url=_STATION_ENDPOINT,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.LazyFrame()
        df = pl.read_json(file.content, schema=_STATION_SCHEMA)
        df = df.select(pl.col("features").explode()).unnest("features")
        df = df.select(
            pl.col("properties").struct.field("code").cast(pl.String).alias("station_id"),
            pl.col("properties").struct.field("name").alias("name"),
            pl.col("geometry").struct.field("coordinates").list.get(1).alias("latitude"),
            pl.col("geometry").struct.field("coordinates").list.get(0).alias("longitude"),
            pl.col("properties").struct.field("altitude").alias("height"),
            _parse_station_datetime("date_begin").alias("start_date"),
            # a null date_end marks a still-active station
            _parse_station_datetime("date_end").alias("end_date"),
        )
        resolutions_and_datasets = {
            (parameter.dataset.resolution.name, parameter.dataset.name)
            for parameter in self.parameters
            if isinstance(parameter, ParameterModel)
        }
        if not resolutions_and_datasets:
            return pl.LazyFrame()
        data = [
            df.with_columns(
                pl.lit(resolution, pl.String).alias("resolution"),
                pl.lit(dataset, pl.String).alias("dataset"),
            )
            for resolution, dataset in resolutions_and_datasets
        ]
        df = pl.concat(data)
        return df.select(
            pl.col(col) if col in df.columns else pl.lit(None).alias(col) for col in self._base_columns
        ).lazy()


def _parse_station_datetime(field: str) -> pl.Expr:
    """Parse an RMI station ``date_begin``/``date_end`` (UTC ``Z`` instant) to a UTC datetime."""
    return (
        pl.col("properties")
        .struct.field(field)
        .str.to_datetime("%Y-%m-%dT%H:%M:%SZ", time_unit="us")
        .dt.replace_time_zone("UTC")
    )
