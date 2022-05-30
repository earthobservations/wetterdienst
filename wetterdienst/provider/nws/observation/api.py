# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import json
import logging
from enum import Enum

import pandas as pd

from wetterdienst.core.scalar.request import ScalarRequestCore
from wetterdienst.core.scalar.values import ScalarValuesCore
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.datarange import DataRange
from wetterdienst.metadata.kind import Kind
from wetterdienst.metadata.period import Period, PeriodType
from wetterdienst.metadata.provider import Provider
from wetterdienst.metadata.resolution import Resolution, ResolutionType
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.metadata.unit import OriginUnit, SIUnit, UnitEnum
from wetterdienst.settings import Settings
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import download_file
from wetterdienst.util.parameter import DatasetTreeCore

Settings.fsspec_client_kwargs["headers"] = {
    "User-Agent": "wetterdienst/0.48.0",
    "Content-Type": "application/json",
}

log = logging.getLogger(__name__)


class NwsObservationParameter(DatasetTreeCore):
    class HOURLY(Enum):
        TEMPERATURE_AIR_MEAN_200 = "temperature"
        TEMPERATURE_DEW_POINT_MEAN_200 = "dewpoint"
        WIND_DIRECTION = "winddirection"
        WIND_SPEED = "windspeed"
        WIND_GUST_MAX = "windgust"
        PRESSURE_AIR_SH = "barometricpressure"
        PRESSURE_AIR_SL = "sealevelpressure"
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


class NwsObservationUnit(DatasetTreeCore):
    class HOURLY(UnitEnum):
        TEMPERATURE_AIR_MEAN_200 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
        TEMPERATURE_DEW_POINT_MEAN_200 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
        WIND_DIRECTION = OriginUnit.DEGREE.value, SIUnit.DEGREE.value
        WIND_SPEED = OriginUnit.KILOMETER_PER_HOUR.value, SIUnit.METER_PER_SECOND.value
        WIND_GUST_MAX = OriginUnit.KILOMETER_PER_HOUR.value, SIUnit.METER_PER_SECOND.value
        PRESSURE_AIR_SH = OriginUnit.PASCAL.value, SIUnit.PASCAL.value
        PRESSURE_AIR_SL = OriginUnit.PASCAL.value, SIUnit.PASCAL.value
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


class NwsObservationValues(ScalarValuesCore):
    _string_parameters = ()
    _irregular_parameters = ()
    _date_parameters = ()
    _data_tz = Timezone.UTC
    _endpoint = "https://api.weather.gov/stations/{station_id}/observations"

    def _collect_station_parameter(self, station_id: str, parameter: Enum, dataset: Enum) -> pd.DataFrame:
        url = self._endpoint.format(station_id=station_id)
        log.info(f"acquiring data from {url}")
        response = download_file(url, CacheExpiry.FIVE_MINUTES)

        data = json.loads(response.read())
        df = pd.DataFrame.from_records(data["features"])

        if df.empty:
            return pd.DataFrame()

        df = df.properties.apply(pd.Series).rename(columns=str.lower)

        parameters = {par.value for par in NwsObservationParameter.HOURLY}
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


class NwsObservationRequest(ScalarRequestCore):
    _values = NwsObservationValues
    _unit_tree = NwsObservationUnit
    _data_range = DataRange.FIXED
    _tz = Timezone.USA
    _parameter_base = NwsObservationParameter
    _has_tidy_data = True
    _has_datasets = False
    _period_base = NwsObservationPeriod
    _period_type = PeriodType.FIXED
    _resolution_base = NwsObservationResolution
    _resolution_type = ResolutionType.FIXED
    provider = Provider.NWS
    kind = Kind.OBSERVATION
    _endpoint = "https://madis-data.ncep.noaa.gov/madisPublic1/data/stations/METARTable.txt"

    def __init__(self, parameter, start_date=None, end_date=None):
        super(NwsObservationRequest, self).__init__(
            parameter=parameter,
            resolution=Resolution.HOURLY,
            period=Period.RECENT,
            start_date=start_date,
            end_date=end_date,
        )

    def _all(self) -> pd.DataFrame:
        response = download_file(self._endpoint, CacheExpiry.METAINDEX)
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
