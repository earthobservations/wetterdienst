# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import datetime as dt
import json
import logging

import polars as pl

from wetterdienst.core.timeseries.metadata import DATASET_NAME_DEFAULT, DatasetModel, build_metadata_model
from wetterdienst.core.timeseries.request import _DATETIME_TYPE, _PARAMETER_TYPE, _SETTINGS_TYPE, TimeseriesRequest
from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.datarange import DataRange
from wetterdienst.metadata.kind import Kind
from wetterdienst.metadata.provider import Provider
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import download_file

log = logging.getLogger(__name__)

NwsObservationMetadata = {
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
                            "unit": "degree_kelvin",
                            "unit_original": "degree_celsius",
                        },
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "dewpoint",
                            "unit": "degree_kelvin",
                            "unit_original": "degree_celsius",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "winddirection",
                            "unit": "degree",
                            "unit_original": "degree",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "windspeed",
                            "unit": "meter_per_second",
                            "unit_original": "kilometer_per_hour",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "windgust",
                            "unit": "meter_per_second",
                            "unit_original": "kilometer_per_hour",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "barometricpressure",
                            "unit": "pascal",
                            "unit_original": "pascal",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "sealevelpressure",
                            "unit": "pascal",
                            "unit_original": "pascal",
                        },
                        {
                            "name": "visibility_range",
                            "name_original": "visibility",
                            "unit": "meter",
                            "unit_original": "meter",
                        },
                        {
                            "name": "temperature_air_max_2m_last_24h",
                            "name_original": "maxtemperaturelast24hours",
                            "unit": "degree_kelvin",
                            "unit_original": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m_last_24h",
                            "name_original": "mintemperaturelast24hours",
                            "unit": "degree_kelvin",
                            "unit_original": "degree_celsius",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "precipitationlasthour",
                            "unit": "kilogram_per_square_meter",
                            "unit_original": "millimeter",
                        },
                        {
                            "name": "precipitation_height_last_3h",
                            "name_original": "precipitationlast3hours",
                            "unit": "kilogram_per_square_meter",
                            "unit_original": "millimeter",
                        },
                        {
                            "name": "precipitation_height_last_6h",
                            "name_original": "precipitationlast6hours",
                            "unit": "kilogram_per_square_meter",
                            "unit_original": "millimeter",
                        },
                        {
                            "name": "humidity",
                            "name_original": "relativehumidity",
                            "unit": "percent",
                            "unit_original": "percent",
                        },
                        {
                            "name": "temperature_wind_chill",
                            "name_original": "windchill",
                            "unit": "degree_kelvin",
                            "unit_original": "degree_celsius",
                        },
                    ],
                }
            ],
        }
    ]
}
NwsObservationMetadata = build_metadata_model(NwsObservationMetadata, "NwsObservationMetadata")


class NwsObservationValues(TimeseriesValues):
    _data_tz = Timezone.UTC
    _endpoint = "https://api.weather.gov/stations/{station_id}/observations"

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: DatasetModel,  # noqa: ARG002
    ) -> pl.DataFrame:
        url = self._endpoint.format(station_id=station_id)
        log.info(f"acquiring data from {url}")
        response = download_file(url, settings=self.sr.stations.settings, ttl=CacheExpiry.FIVE_MINUTES)
        data = json.load(response)
        try:
            data = [feature["properties"] for feature in data["features"]]
        except KeyError:
            return pl.DataFrame()
        df = pl.from_dicts(
            data,
            schema={
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
        )
        df = df.rename(mapping=lambda col: col.lower())
        df = df.rename(mapping={"station": Columns.STATION_ID.value, "timestamp": Columns.DATE.value})
        df = df.unpivot(
            index=[Columns.STATION_ID.value, Columns.DATE.value],
            variable_name=Columns.PARAMETER.value,
            value_name=Columns.VALUE.value,
        )
        df = df.filter(pl.col("parameter").ne("cloudlayers"))
        return df.with_columns(
            pl.col("date")
            .map_elements(dt.datetime.fromisoformat, return_dtype=pl.Datetime)
            .cast(pl.Datetime(time_zone="UTC")),
            pl.col("value").struct.field("value").cast(pl.Float64),
            pl.lit(None, dtype=pl.Float64).alias(Columns.QUALITY.value),
        )


class NwsObservationRequest(TimeseriesRequest):
    _provider = Provider.NWS
    _kind = Kind.OBSERVATION
    _tz = Timezone.USA
    _data_range = DataRange.FIXED
    _values = NwsObservationValues
    metadata = NwsObservationMetadata

    _endpoint = "https://madis-data.ncep.noaa.gov/madisPublic1/data/stations/METARTable.txt"

    def __init__(
        self,
        parameters: _PARAMETER_TYPE,
        start_date: _DATETIME_TYPE = None,
        end_date: _DATETIME_TYPE = None,
        settings: _SETTINGS_TYPE = None,
    ):
        super().__init__(
            parameters=parameters,
            start_date=start_date,
            end_date=end_date,
            settings=settings,
        )

        self.settings.fsspec_client_kwargs.update(
            {
                "headers": {
                    "User-Agent": "wetterdienst/0.48.0",
                    "Content-Type": "application/json",
                },
            },
        )

    def _all(self) -> pl.LazyFrame:
        response = download_file(self._endpoint, self.settings, CacheExpiry.METAINDEX)
        df = pl.read_csv(source=response, has_header=False, separator="\t", infer_schema_length=0).lazy()
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
                "column_2": Columns.STATION_ID.value,
                "column_3": Columns.LATITUDE.value,
                "column_4": Columns.LONGITUDE.value,
                "column_5": Columns.HEIGHT.value,
                "column_6": Columns.NAME.value,
            },
        )
        df = df.with_columns(pl.all().str.strip_chars())
        df = df.with_columns(
            pl.col(Columns.LATITUDE.value).cast(pl.Float64),
            pl.col(Columns.LONGITUDE.value).cast(pl.Float64),
            pl.col(Columns.HEIGHT.value).cast(pl.Float64),
        )
        return df.filter(pl.col("longitude").lt(0) & pl.col("latitude").gt(0))
