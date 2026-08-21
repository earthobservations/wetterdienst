# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""NWS observation provider."""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from urllib.parse import urlencode

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, DatasetModel, build_metadata_model
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

NwsObservationMetadata = {
    "name_short": "NWS",
    "name_english": "NOAA National Weather Service",
    "name_local": "NOAA National Weather Service",
    "country": "United States Of America",
    "copyright": "© NOAA NWS (National Weather Service), Observations",
    "url": "https://api.weather.gov/",
    "kind": "observation",
    "timezone": "America/New_York",
    "resolutions": [
        {
            "name": "hourly",
            "name_original": "hourly",
            "periods": ["recent"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "dewpoint",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "winddirection",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "windspeed",
                            "unit": "kilometer_per_hour",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "windgust",
                            "unit": "kilometer_per_hour",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "barometricpressure",
                            "unit": "pascal",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "sealevelpressure",
                            "unit": "pascal",
                        },
                        {
                            "name": "visibility_range",
                            "name_original": "visibility",
                            "unit": "meter",
                        },
                        {
                            "name": "temperature_air_max_2m_last_24h",
                            "name_original": "maxtemperaturelast24hours",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m_last_24h",
                            "name_original": "mintemperaturelast24hours",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "precipitationlasthour",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_last_3h",
                            "name_original": "precipitationlast3hours",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_last_6h",
                            "name_original": "precipitationlast6hours",
                            "unit": "millimeter",
                        },
                        {
                            "name": "humidity",
                            "name_original": "relativehumidity",
                            "unit": "percent",
                        },
                        {
                            "name": "temperature_wind_chill",
                            "name_original": "windchill",
                            "unit": "degree_celsius",
                        },
                    ],
                },
            ],
        },
    ],
}
NwsObservationMetadata = build_metadata_model(NwsObservationMetadata, "NwsObservationMetadata")


class NwsObservationValues(TimeseriesValues):
    """Values class for NWS observation."""

    _endpoint = "https://api.weather.gov/stations/{station_id}/observations"
    # the API answers ISO 8601 instants and reads them back the same way
    _date_format = "%Y-%m-%dT%H:%M:%SZ"

    def _build_url(self, station_id: str) -> str:
        """Address the observations of a station, narrowed to the window the request asked for.

        Asked for nothing in particular the endpoint answers with its whole retention, which is a
        rolling week of some 180 readings -- close to a megabyte to answer for a single day. It
        clips a window to what it still holds rather than refusing one that reaches further back,
        so naming the request's own window costs nothing and returns the same readings.

        A request carries no dates unless it is made to: `date_required` is enforced at the CLI and
        the REST API but not in the Python API, and without them there is no window to name.
        """
        url = self._endpoint.format(station_id=station_id)
        if not self.sr.start_date or not self.sr.end_date:
            return url
        query = urlencode(
            {
                "start": self.sr.start_date.astimezone(dt.timezone.utc).strftime(self._date_format),
                "end": self.sr.end_date.astimezone(dt.timezone.utc).strftime(self._date_format),
            },
        )
        return f"{url}?{query}"

    def _collect_station_parameter_or_dataset(  # ty: ignore[invalid-method-override]
        self,
        station_id: str,
        parameter_or_dataset: DatasetModel,
    ) -> pl.DataFrame:
        settings = cast("Settings", self.sr.stations.settings)
        url = self._build_url(station_id)
        log.info(f"acquiring data from {url}")
        file = download_file(
            url=url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.FIVE_MINUTES,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        file.raise_if_exception()
        # not dead after the raise above: `raise_if_exception` lets a NoInternetError through
        # silently, so that a request made offline yields an empty frame rather than an error
        if isinstance(file.content, Exception):
            return pl.DataFrame()
        df = pl.read_json(
            file.content,
            schema={
                "features": pl.List(
                    pl.Struct(
                        {
                            "properties": pl.Struct(
                                {
                                    "station": pl.String,
                                    "timestamp": pl.String,
                                    "temperature": pl.Struct(
                                        [
                                            pl.Field("value", pl.Float64),
                                        ],
                                    ),
                                    "dewpoint": pl.Struct(
                                        [
                                            pl.Field("value", pl.Float64),
                                        ],
                                    ),
                                    "windDirection": pl.Struct(
                                        [
                                            pl.Field("value", pl.Int64),
                                        ],
                                    ),
                                    "windSpeed": pl.Struct(
                                        [
                                            pl.Field("value", pl.Float64),
                                        ],
                                    ),
                                    "windGust": pl.Struct(
                                        [
                                            pl.Field("value", pl.Int32),
                                        ],
                                    ),
                                    "barometricPressure": pl.Struct(
                                        [
                                            pl.Field("value", pl.Int64),
                                        ],
                                    ),
                                    "seaLevelPressure": pl.Struct(
                                        [
                                            pl.Field("value", pl.Int64),
                                        ],
                                    ),
                                    "visibility": pl.Struct(
                                        [
                                            pl.Field("value", pl.Int64),
                                        ],
                                    ),
                                    "maxTemperatureLast24Hours": pl.Struct([pl.Field("value", pl.Int32)]),
                                    "minTemperatureLast24Hours": pl.Struct([pl.Field("value", pl.Int32)]),
                                    "precipitationLastHour": pl.Struct(
                                        [
                                            pl.Field("value", pl.Int64),
                                        ],
                                    ),
                                    "precipitationLast3Hours": pl.Struct(
                                        [
                                            pl.Field("value", pl.Int64),
                                        ],
                                    ),
                                    "precipitationLast6Hours": pl.Struct(
                                        [
                                            pl.Field("value", pl.Int64),
                                        ],
                                    ),
                                    "relativeHumidity": pl.Struct(
                                        [
                                            pl.Field("value", pl.Float64),
                                        ],
                                    ),
                                    "windChill": pl.Struct(
                                        [
                                            pl.Field("value", pl.Float64),
                                        ],
                                    ),
                                },
                            ),
                        },
                    ),
                ),
            },
        )
        df = df.explode("features", empty_as_null=True)
        df = df.select(pl.col("features").struct.field("properties"))
        df = df.select(pl.col("properties").struct.unnest())
        df = df.rename(str.lower)
        df = df.rename(mapping={"station": "station_id", "timestamp": "date"})
        df = df.unpivot(
            index=["station_id", "date"],
            variable_name="parameter",
            value_name="value",
        )
        return df.with_columns(
            pl.lit(parameter_or_dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(parameter_or_dataset.name, dtype=pl.String).alias("dataset"),
            pl.col("date").str.to_datetime(format="%Y-%m-%dT%H:%M:%S%z"),
            pl.col("value").struct.field("value").cast(pl.Float64),
            pl.lit(None, dtype=pl.Float64).alias("quality"),
        )


@dataclass
class NwsObservationRequest(TimeseriesRequest):
    """Request class for NWS observation."""

    metadata = NwsObservationMetadata
    _values = NwsObservationValues

    # the station list is METAR only and comes from MADIS rather than from api.weather.gov, whose
    # own listing runs to some fifty thousand stations across four hundred cursor-paged requests --
    # mostly mesonet sites the observations endpoint of this provider is not asked for
    _endpoint = "https://madis-data.ncep.noaa.gov/madisPublic1/data/stations/METARTable.txt"

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
        df = pl.read_csv(source=file.content, has_header=False, separator="\t", infer_schema_length=0).lazy()
        # the table is the global METAR listing; api.weather.gov serves the United States alone.
        # Column 7 is the country, which is all that narrows it -- no coordinate box is laid over
        # the result, since one drops the stations that sit the far side of the antimeridian or
        # below the equator: the Aleutians west of Amchitka, Pago Pago and Tinian all read as
        # somewhere else while api.weather.gov answers for every one of them
        df = df.filter(pl.col("column_7").eq("US"))
        df = df.select(
            pl.col("column_2"),
            pl.col("column_3"),
            pl.col("column_4"),
            pl.col("column_5"),
            pl.col("column_6"),
        )
        df = df.rename(
            mapping={
                "column_2": "station_id",
                "column_3": "latitude",
                "column_4": "longitude",
                "column_5": "height",
                "column_6": "name",
            },
        )
        df = df.with_columns(pl.all().str.strip_chars())
        return df.with_columns(
            pl.lit(self.metadata[0].name, dtype=pl.String).alias("resolution"),
            pl.lit(self.metadata[0][0].name, dtype=pl.String).alias("dataset"),
            pl.col("latitude").cast(pl.Float64),
            pl.col("longitude").cast(pl.Float64),
            pl.col("height").cast(pl.Float64),
        )
