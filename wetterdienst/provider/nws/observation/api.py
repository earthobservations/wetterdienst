# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import datetime as dt
import json
import logging
from enum import Enum
from typing import TYPE_CHECKING

import polars as pl

from wetterdienst.core.timeseries.request import TimeseriesRequest
from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.datarange import DataRange
from wetterdienst.metadata.kind import Kind
from wetterdienst.metadata.period import Period, PeriodType
from wetterdienst.metadata.provider import Provider
from wetterdienst.metadata.resolution import Resolution, ResolutionType
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.metadata.unit import OriginUnit, SIUnit, UnitEnum
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import download_file
from wetterdienst.util.parameter import DatasetTreeCore

if TYPE_CHECKING:
    from collections.abc import Sequence

    from wetterdienst.metadata.parameter import Parameter
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)


class NwsObservationParameter(DatasetTreeCore):
    class HOURLY(DatasetTreeCore):
        class HOURLY(Enum):
            TEMPERATURE_AIR_MEAN_2M = "temperature"
            TEMPERATURE_DEW_POINT_MEAN_2M = "dewpoint"
            WIND_DIRECTION = "winddirection"
            WIND_SPEED = "windspeed"
            WIND_GUST_MAX = "windgust"
            PRESSURE_AIR_SITE = "barometricpressure"
            PRESSURE_AIR_SEA_LEVEL = "sealevelpressure"
            VISIBILITY_RANGE = "visibility"
            TEMPERATURE_AIR_MAX_2M_LAST_24H = "maxtemperaturelast24hours"
            TEMPERATURE_AIR_MIN_2M_LAST_24H = "mintemperaturelast24hours"
            PRECIPITATION_HEIGHT = "precipitationlasthour"
            PRECIPITATION_HEIGHT_LAST_3H = "precipitationlast3hours"
            PRECIPITATION_HEIGHT_LAST_6H = "precipitationlast6hours"
            HUMIDITY = "relativehumidity"
            TEMPERATURE_WIND_CHILL = "windchill"
            # HEAT_INDEX = "heatIndex" noqa: E800
            # cloudLayers group
            # CLOUD_BASE = "cloudLayers" noqa: E800

        TEMPERATURE_AIR_MEAN_2M = HOURLY.TEMPERATURE_AIR_MEAN_2M
        TEMPERATURE_DEW_POINT_MEAN_2M = HOURLY.TEMPERATURE_DEW_POINT_MEAN_2M
        WIND_DIRECTION = HOURLY.WIND_DIRECTION
        WIND_SPEED = HOURLY.WIND_SPEED
        WIND_GUST_MAX = HOURLY.WIND_GUST_MAX
        PRESSURE_AIR_SITE = HOURLY.PRESSURE_AIR_SITE
        PRESSURE_AIR_SEA_LEVEL = HOURLY.PRESSURE_AIR_SEA_LEVEL
        VISIBILITY_RANGE = HOURLY.VISIBILITY_RANGE
        TEMPERATURE_AIR_MAX_2M_LAST_24H = HOURLY.TEMPERATURE_AIR_MAX_2M_LAST_24H
        TEMPERATURE_AIR_MIN_2M_LAST_24H = HOURLY.TEMPERATURE_AIR_MIN_2M_LAST_24H
        PRECIPITATION_HEIGHT = HOURLY.PRECIPITATION_HEIGHT
        PRECIPITATION_HEIGHT_LAST_3H = HOURLY.PRECIPITATION_HEIGHT_LAST_3H
        PRECIPITATION_HEIGHT_LAST_6H = HOURLY.PRECIPITATION_HEIGHT_LAST_6H
        HUMIDITY = HOURLY.HUMIDITY
        TEMPERATURE_WIND_CHILL = HOURLY.TEMPERATURE_WIND_CHILL


class NwsObservationUnit(DatasetTreeCore):
    class HOURLY(DatasetTreeCore):
        class HOURLY(UnitEnum):
            TEMPERATURE_AIR_MEAN_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_DEW_POINT_MEAN_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            WIND_DIRECTION = OriginUnit.DEGREE.value, SIUnit.DEGREE.value
            WIND_SPEED = OriginUnit.KILOMETER_PER_HOUR.value, SIUnit.METER_PER_SECOND.value
            WIND_GUST_MAX = OriginUnit.KILOMETER_PER_HOUR.value, SIUnit.METER_PER_SECOND.value
            PRESSURE_AIR_SITE = OriginUnit.PASCAL.value, SIUnit.PASCAL.value
            PRESSURE_AIR_SEA_LEVEL = OriginUnit.PASCAL.value, SIUnit.PASCAL.value
            VISIBILITY_RANGE = OriginUnit.METER.value, SIUnit.METER.value
            TEMPERATURE_AIR_MAX_2M_LAST_24H = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_2M_LAST_24H = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_HEIGHT_LAST_3H = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_HEIGHT_LAST_6H = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
            TEMPERATURE_WIND_CHILL = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value


class NwsObservationResolution(Enum):
    HOURLY = Resolution.HOURLY.value


class NwsObservationPeriod(Enum):
    RECENT = Period.RECENT.value


class NwsObservationValues(TimeseriesValues):
    _data_tz = Timezone.UTC
    _endpoint = "https://api.weather.gov/stations/{station_id}/observations"

    def _collect_station_parameter(
        self,
        station_id: str,
        parameter: Enum,  # noqa: ARG002
        dataset: Enum,  # noqa: ARG002
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
    _parameter_base = NwsObservationParameter
    _unit_base = NwsObservationUnit
    _resolution_base = NwsObservationResolution
    _resolution_type = ResolutionType.FIXED
    _period_type = PeriodType.FIXED
    _period_base = NwsObservationPeriod
    _has_datasets = False
    _data_range = DataRange.FIXED
    _values = NwsObservationValues

    _endpoint = "https://madis-data.ncep.noaa.gov/madisPublic1/data/stations/METARTable.txt"

    def __init__(
        self,
        parameter: str | NwsObservationParameter | Parameter | Sequence[str | NwsObservationParameter | Parameter],
        start_date: str | dt.datetime | None = None,
        end_date: str | dt.datetime | None = None,
        settings: Settings | None = None,
    ):
        super().__init__(
            parameter=parameter,
            resolution=Resolution.HOURLY,
            period=Period.RECENT,
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
