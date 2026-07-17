# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DMI (Danish Meteorological Institute) climate data observation provider.

DMI publishes quality-controlled climate data through an open, key-less OGC API Features
service (GeoJSON). The ``climateData`` service exposes aggregated ``stationValue`` records
that can be filtered by station, parameter, time resolution and datetime range in a single
request -- see https://opendatadocs.dmi.govcloud.dk/Data/Climate_Data.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, cast
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.metadata import DatasetModel, ParameterModel
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dmi.observation.metadata import DmiObservationMetadata
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

_BASE_URL = "https://opendataapi.dmi.dk/v2/climateData/collections"
_UTC = ZoneInfo("UTC")
# DMI accepts a limit of up to 300000 records per page; a single page therefore covers any
# realistic station/parameter/resolution/date-range combination and pagination rarely kicks
# in. DMI always returns a "next" link regardless, so pagination stops on a short page.
_PAGE_LIMIT = 300_000

_EMPTY_VALUES_SCHEMA = {
    "resolution": pl.String,
    "dataset": pl.String,
    "parameter": pl.String,
    "station_id": pl.String,
    "date": pl.Datetime(time_unit="us", time_zone="UTC"),
    "value": pl.Float64,
    "quality": pl.Float64,
}

_STATION_VALUE_SCHEMA = pl.Schema(
    {
        "features": pl.List(
            pl.Struct(
                {
                    "properties": pl.Struct(
                        {
                            "parameterId": pl.String,
                            "from": pl.String,
                            "value": pl.Float64,
                        }
                    ),
                }
            )
        ),
    }
)

_STATION_SCHEMA = pl.Schema(
    {
        "features": pl.List(
            pl.Struct(
                {
                    "geometry": pl.Struct({"coordinates": pl.List(pl.Float64)}),
                    "properties": pl.Struct(
                        {
                            "stationId": pl.String,
                            "name": pl.String,
                            "country": pl.String,
                            "stationHeight": pl.Float64,
                            "validFrom": pl.String,
                            "validTo": pl.String,
                            "created": pl.String,
                        }
                    ),
                }
            )
        ),
    }
)


class DmiObservationValues(TimeseriesValues):
    """Values class for DMI climate data observations."""

    _resolution_to_time_resolution: ClassVar[dict[Resolution, str]] = {
        Resolution.HOURLY: "hour",
        Resolution.DAILY: "day",
        Resolution.MONTHLY: "month",
        Resolution.ANNUAL: "year",
    }

    @staticmethod
    def _date_expression(resolution: Resolution) -> pl.Expr:
        """Build the ``date`` column expression from DMI's ``from`` timestamp.

        DMI labels each aggregate by the start of its period. Hourly data is aligned to UTC
        (``from`` carries a ``+00:00`` offset), so it is parsed and normalised to UTC directly.
        Day/month/year aggregates use *local civil* period boundaries (``from`` carries the
        station's local offset, e.g. ``2023-06-02T00:00:00.001000+02:00``). Their civil date
        is taken straight from the leading characters of the string -- this is timezone
        independent and therefore correct for Danish, Greenlandic and Faroese stations alike
        -- and stamped at UTC midnight of that civil date, matching the codebase convention
        of expressing nominal calendar dates as UTC.
        """
        if resolution == Resolution.HOURLY:
            return pl.col("from").str.to_datetime("%Y-%m-%dT%H:%M:%S%z", time_unit="us").dt.convert_time_zone("UTC")
        year = pl.col("from").str.slice(0, 4).cast(pl.Int32)
        if resolution == Resolution.DAILY:
            month = pl.col("from").str.slice(5, 2).cast(pl.Int32)
            day = pl.col("from").str.slice(8, 2).cast(pl.Int32)
            local = pl.date(year, month, day)
        elif resolution == Resolution.MONTHLY:
            month = pl.col("from").str.slice(5, 2).cast(pl.Int32)
            local = pl.date(year, month, 1)
        else:  # ANNUAL
            local = pl.date(year, 1, 1)
        return local.cast(pl.Datetime(time_unit="us")).dt.replace_time_zone("UTC")

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
        resolution = dataset.resolution.value
        time_resolution = self._resolution_to_time_resolution[resolution]
        # DMI matches its datetime filter against each aggregate's `from` *instant*. For
        # day/month/year aggregates `from` is the local civil period start, which sits a few
        # hours off the UTC-midnight label this provider assigns (e.g. a Danish summer day
        # starts at 22:00Z the previous day). Widen the requested window by a day on each side
        # so no boundary period is dropped for that offset; TimeseriesValues.query() trims the
        # result back to the exact requested range by the assigned `date`. Normalise to UTC so
        # the "Z" filter is true even for already-tz-aware, non-UTC callers.
        start = (start_date.astimezone(_UTC) - dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        end = (end_date.astimezone(_UTC) + dt.timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")

        # DMI returns every parameter for the station in one response; keep only the ones
        # mapped in this dataset's metadata (their raw parameterId is name_original).
        known_parameters = {parameter.name_original for parameter in dataset.parameters}

        records = []
        offset = 0
        while True:
            url = (
                f"{_BASE_URL}/stationValue/items?stationId={station_id}"
                f"&timeResolution={time_resolution}&datetime={start}/{end}"
                f"&limit={_PAGE_LIMIT}&offset={offset}"
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
                log.warning(f"Failed to acquire DMI data for station {station_id}: {file.content}")
                break
            df = pl.read_json(file.content, schema=_STATION_VALUE_SCHEMA)
            df = df.select(pl.col("features").explode().struct.field("properties")).unnest("properties")
            number_returned = df.height
            if number_returned:
                records.append(df)
            if number_returned < _PAGE_LIMIT:
                break
            offset += _PAGE_LIMIT

        if not records:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)

        df = pl.concat(records)
        df = df.filter(pl.col("parameterId").is_in(known_parameters))
        if df.is_empty():
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
        return df.select(
            pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            pl.col("parameterId").alias("parameter"),
            pl.lit(station_id, dtype=pl.String).alias("station_id"),
            self._date_expression(resolution).alias("date"),
            pl.col("value").cast(pl.Float64),
            pl.lit(None, dtype=pl.Float64).alias("quality"),
        )


@dataclass
class DmiObservationRequest(TimeseriesRequest):
    """Request class for DMI (Danish Meteorological Institute) climate data observations.

    - https://www.dmi.dk/friedata/
    - https://opendatadocs.dmi.govcloud.dk/Data/Climate_Data
    """

    metadata = DmiObservationMetadata
    _values = DmiObservationValues

    _endpoint = f"{_BASE_URL}/station/items?limit={_PAGE_LIMIT}"

    def _all(self) -> pl.LazyFrame:
        settings = cast("Settings", self.settings)
        file = download_file(
            url=self._endpoint,
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
            pl.col("properties").struct.field("stationId").alias("station_id"),
            pl.col("properties").struct.field("name").alias("name"),
            pl.col("properties").struct.field("country").alias("state"),
            pl.col("geometry").struct.field("coordinates").list.get(1).alias("latitude"),
            pl.col("geometry").struct.field("coordinates").list.get(0).alias("longitude"),
            pl.col("properties").struct.field("stationHeight").alias("height"),
            pl.col("properties")
            .struct.field("validFrom")
            .str.to_datetime("%Y-%m-%dT%H:%M:%SZ", time_unit="us")
            .dt.replace_time_zone("UTC")
            .alias("start_date"),
            pl.col("properties")
            .struct.field("validTo")
            .str.to_datetime("%Y-%m-%dT%H:%M:%SZ", time_unit="us")
            .dt.replace_time_zone("UTC")
            .alias("end_date"),
            pl.col("properties").struct.field("created").alias("created"),
        )
        # DMI lists a station once per validity period. Collapse to one row per station: keep
        # the most recent metadata (name, coordinates, height) and span the full active range
        # (earliest validFrom; a null validTo on any record means "still active" -> null).
        df = df.sort("created", descending=True)
        df = df.group_by("station_id").agg(
            pl.col("name").first(),
            pl.col("state").first(),
            pl.col("latitude").first(),
            pl.col("longitude").first(),
            pl.col("height").first(),
            pl.col("start_date").min(),
            pl.when(pl.col("end_date").is_null().any())
            .then(None)
            .otherwise(pl.col("end_date").max())
            .alias("end_date"),
        )
        resolutions_and_datasets = {
            (parameter.dataset.resolution.name, parameter.dataset.name)
            for parameter in self.parameters
            if isinstance(parameter, ParameterModel)
        }
        if not resolutions_and_datasets:
            return pl.LazyFrame()
        data = []
        for resolution, dataset in resolutions_and_datasets:
            data.append(
                df.with_columns(
                    pl.lit(resolution, pl.String).alias("resolution"),
                    pl.lit(dataset, pl.String).alias("dataset"),
                ),
            )
        df = pl.concat(data)
        return df.select(
            pl.col(col) if col in df.columns else pl.lit(None).alias(col) for col in self._base_columns
        ).lazy()
