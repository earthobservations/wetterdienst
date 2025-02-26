# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""NWS observation provider."""

from __future__ import annotations

import logging

import polars as pl

from wetterdienst.core.timeseries.metadata import DATASET_NAME_DEFAULT, DatasetModel, build_metadata_model
from wetterdienst.core.timeseries.request import _DATETIME_TYPE, _PARAMETER_TYPE, _SETTINGS_TYPE, TimeseriesRequest
from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.util.network import download_file

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
    "timezone_data": "UTC",
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
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "dewpoint",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "winddirection",
                            "unit_type": "angle",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "windspeed",
                            "unit_type": "speed",
                            "unit": "kilometer_per_hour",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "windgust",
                            "unit_type": "speed",
                            "unit": "kilometer_per_hour",
                        },
                        {
                            "name": "pressure_air_site",
                            "name_original": "barometricpressure",
                            "unit_type": "pressure",
                            "unit": "pascal",
                        },
                        {
                            "name": "pressure_air_sea_level",
                            "name_original": "sealevelpressure",
                            "unit_type": "pressure",
                            "unit": "pascal",
                        },
                        {
                            "name": "visibility_range",
                            "name_original": "visibility",
                            "unit_type": "length_medium",
                            "unit": "meter",
                        },
                        {
                            "name": "temperature_air_max_2m_last_24h",
                            "name_original": "maxtemperaturelast24hours",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_air_min_2m_last_24h",
                            "name_original": "mintemperaturelast24hours",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "precipitationlasthour",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_last_3h",
                            "name_original": "precipitationlast3hours",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_height_last_6h",
                            "name_original": "precipitationlast6hours",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "humidity",
                            "name_original": "relativehumidity",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "temperature_wind_chill",
                            "name_original": "windchill",
                            "unit_type": "temperature",
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

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: DatasetModel,
    ) -> pl.DataFrame:
        url = self._endpoint.format(station_id=station_id)
        log.info(f"acquiring data from {url}")
        response = download_file(url, settings=self.sr.stations.settings, ttl=CacheExpiry.FIVE_MINUTES)
        df = pl.read_json(
            response,
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
        df = df.explode("features")
        df = df.select(pl.col("features").struct.field("properties"))
        df = df.select(pl.col("properties").struct.unnest())
        df = df.rename(str.lower)
        df = df.rename(mapping={"station": "station_id", "timestamp": "date"})
        df = df.unpivot(
            index=["station_id", "date"],
            variable_name="parameter",
            value_name="value",
        )
        df = df.filter(pl.col("parameter").ne("cloudlayers"))
        return df.with_columns(
            pl.lit(parameter_or_dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(parameter_or_dataset.name, dtype=pl.String).alias("dataset"),
            pl.col("date").str.to_datetime(format="%Y-%m-%dT%H:%M:%S%z"),
            pl.col("value").struct.field("value").cast(pl.Float64),
            pl.lit(None, dtype=pl.Float64).alias("quality"),
        )


class NwsObservationRequest(TimeseriesRequest):
    """Request class for NWS observation."""

    metadata = NwsObservationMetadata
    _values = NwsObservationValues

    _endpoint = "https://madis-data.ncep.noaa.gov/madisPublic1/data/stations/METARTable.txt"

    def __init__(
        self,
        parameters: _PARAMETER_TYPE,
        start_date: _DATETIME_TYPE = None,
        end_date: _DATETIME_TYPE = None,
        settings: _SETTINGS_TYPE = None,
    ) -> None:
        """Initialize the NWS observation request.

        Args:
            parameters: parameters to request
            start_date: start date
            end_date: end date
            settings: settings

        """
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
                "column_2": "station_id",
                "column_3": "latitude",
                "column_4": "longitude",
                "column_5": "height",
                "column_6": "name",
            },
        )
        df = df.with_columns(pl.all().str.strip_chars())
        df = df.with_columns(
            pl.lit(self.metadata[0].name, dtype=pl.String).alias("resolution"),
            pl.lit(self.metadata[0][0].name, dtype=pl.String).alias("dataset"),
            pl.col("latitude").cast(pl.Float64),
            pl.col("longitude").cast(pl.Float64),
            pl.col("height").cast(pl.Float64),
        )
        return df.filter(pl.col("longitude").lt(0) & pl.col("latitude").gt(0))
