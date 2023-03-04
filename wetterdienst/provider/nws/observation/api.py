# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import json
import logging
from datetime import datetime
from enum import Enum
from typing import List, Optional, Union

import pandas as pd

from wetterdienst.core.timeseries.request import TimeseriesRequest
from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.datarange import DataRange
from wetterdienst.metadata.kind import Kind
from wetterdienst.metadata.parameter import Parameter
from wetterdienst.metadata.period import Period, PeriodType
from wetterdienst.metadata.provider import Provider
from wetterdienst.metadata.resolution import Resolution, ResolutionType
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.metadata.unit import OriginUnit, SIUnit, UnitEnum
from wetterdienst.settings import Settings
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import download_file
from wetterdienst.util.parameter import DatasetTreeCore

log = logging.getLogger(__name__)


class NwsObservationParameter(DatasetTreeCore):
    class HOURLY(DatasetTreeCore):
        class HOURLY(Enum):
            TEMPERATURE_AIR_MEAN_200 = "temperature"
            TEMPERATURE_DEW_POINT_MEAN_200 = "dewpoint"
            WIND_DIRECTION = "winddirection"
            WIND_SPEED = "windspeed"
            WIND_GUST_MAX = "windgust"
            PRESSURE_AIR_SITE = "barometricpressure"
            PRESSURE_AIR_SEA_LEVEL = "sealevelpressure"
            VISIBILITY_RANGE = "visibility"
            TEMPERATURE_AIR_MAX_200_LAST_24H = "maxtemperaturelast24hours"
            TEMPERATURE_AIR_MIN_200_LAST_24H = "mintemperaturelast24hours"
            PRECIPITATION_HEIGHT = "precipitationlasthour"
            PRECIPITATION_HEIGHT_LAST_3H = "precipitationlast3hours"
            PRECIPITATION_HEIGHT_LAST_6H = "precipitationlast6hours"
            HUMIDITY = "relativehumidity"
            TEMPERATURE_WIND_CHILL = "windchill"
            # HEAT_INDEX = "heatIndex" noqa: E800
            # cloudLayers group
            # CLOUD_BASE = "cloudLayers" noqa: E800

        TEMPERATURE_AIR_MEAN_200 = HOURLY.TEMPERATURE_AIR_MEAN_200
        TEMPERATURE_DEW_POINT_MEAN_200 = HOURLY.TEMPERATURE_DEW_POINT_MEAN_200
        WIND_DIRECTION = HOURLY.WIND_DIRECTION
        WIND_SPEED = HOURLY.WIND_SPEED
        WIND_GUST_MAX = HOURLY.WIND_GUST_MAX
        PRESSURE_AIR_SITE = HOURLY.PRESSURE_AIR_SITE
        PRESSURE_AIR_SEA_LEVEL = HOURLY.PRESSURE_AIR_SEA_LEVEL
        VISIBILITY_RANGE = HOURLY.VISIBILITY_RANGE
        TEMPERATURE_AIR_MAX_200_LAST_24H = HOURLY.TEMPERATURE_AIR_MAX_200_LAST_24H
        TEMPERATURE_AIR_MIN_200_LAST_24H = HOURLY.TEMPERATURE_AIR_MIN_200_LAST_24H
        PRECIPITATION_HEIGHT = HOURLY.PRECIPITATION_HEIGHT
        PRECIPITATION_HEIGHT_LAST_3H = HOURLY.PRECIPITATION_HEIGHT_LAST_3H
        PRECIPITATION_HEIGHT_LAST_6H = HOURLY.PRECIPITATION_HEIGHT_LAST_6H
        HUMIDITY = HOURLY.HUMIDITY
        TEMPERATURE_WIND_CHILL = HOURLY.TEMPERATURE_WIND_CHILL


class NwsObservationUnit(DatasetTreeCore):
    class HOURLY(DatasetTreeCore):
        class HOURLY(UnitEnum):
            TEMPERATURE_AIR_MEAN_200 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_DEW_POINT_MEAN_200 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            WIND_DIRECTION = OriginUnit.DEGREE.value, SIUnit.DEGREE.value
            WIND_SPEED = OriginUnit.KILOMETER_PER_HOUR.value, SIUnit.METER_PER_SECOND.value
            WIND_GUST_MAX = OriginUnit.KILOMETER_PER_HOUR.value, SIUnit.METER_PER_SECOND.value
            PRESSURE_AIR_SITE = OriginUnit.PASCAL.value, SIUnit.PASCAL.value
            PRESSURE_AIR_SEA_LEVEL = OriginUnit.PASCAL.value, SIUnit.PASCAL.value
            VISIBILITY_RANGE = OriginUnit.METER.value, SIUnit.METER.value
            TEMPERATURE_AIR_MAX_200_LAST_24H = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_AIR_MIN_200_LAST_24H = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
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

    def _collect_station_parameter(self, station_id: str, parameter: Enum, dataset: Enum) -> pd.DataFrame:
        url = self._endpoint.format(station_id=station_id)
        log.info(f"acquiring data from {url}")
        response = download_file(url, settings=self.sr.stations.settings, ttl=CacheExpiry.FIVE_MINUTES)

        data = json.loads(response.read())
        df = pd.DataFrame.from_records(data["features"])

        if df.empty:
            return pd.DataFrame()

        df = df.properties.apply(pd.Series).rename(columns=str.lower)

        parameters = {par.value for par in NwsObservationParameter.HOURLY.HOURLY}
        parameters.add("cloudlayers")
        parameters = parameters.intersection(df.columns)

        df = df.loc[:, ["station", "timestamp", *parameters]].melt(
            id_vars=["timestamp"],
            var_name=Columns.PARAMETER.value,
            value_name=Columns.VALUE.value,
            value_vars=parameters,
        )

        cloud_mask = df.parameter == "cloudlayers"
        df_cloud = df.loc[cloud_mask, :].explode("value")
        df = df.loc[~cloud_mask, :]
        df.value = df.value.map(lambda x: x["value"])
        df_cloud_parameters = df_cloud.pop("value").apply(pd.Series)
        df_cloud = pd.concat([df_cloud, df_cloud_parameters], axis=1)
        df_cloud = df_cloud.melt(
            id_vars=["timestamp"], var_name=Columns.PARAMETER.value, value_vars=["base"], value_name=Columns.VALUE.value
        )
        df_cloud.parameter = df_cloud.parameter.map({"base": "cloud_base_m"})
        df_cloud.value = df_cloud.value.map(lambda x: x["value"] if type(x) == dict else x)
        df = pd.concat([df, df_cloud], ignore_index=True)
        return df.rename(columns={"timestamp": Columns.DATE.value})


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
        parameter: List[Union[str, NwsObservationParameter, Parameter]],
        start_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
        end_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
        settings: Optional[Settings] = None,
    ):
        super(NwsObservationRequest, self).__init__(
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
                }
            }
        )

    def _all(self) -> pd.DataFrame:
        response = download_file(self._endpoint, self.settings, CacheExpiry.METAINDEX)
        df = pd.read_csv(response, header=None, sep="\t")
        mask_us = df.iloc[:, 6] == "US"
        df = df.loc[mask_us, 1:5]
        df.columns = [
            Columns.STATION_ID.value,
            Columns.LATITUDE.value,
            Columns.LONGITUDE.value,
            Columns.HEIGHT.value,
            Columns.NAME.value,
        ]
        mask_geo = (df.longitude < 0) & (df.latitude > 0)  # limit stations to those actually (approx) in the US area
        return df[mask_geo]
