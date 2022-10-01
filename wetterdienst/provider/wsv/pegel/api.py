# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import json
from datetime import datetime
from enum import Enum
from typing import List, Optional, Tuple, Union

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
from wetterdienst.metadata.unit import OriginUnit, SIUnit
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import download_file
from wetterdienst.util.parameter import DatasetTreeCore

FLOAT_9_TIMES = Tuple[
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
    float,
]


class WsvPegelParameter(DatasetTreeCore):
    class DYNAMIC(Enum):
        WATER_LEVEL = "W"
        DISCHARGE = "Q"
        RUNOFF = DISCHARGE
        TEMPERATURE_WATER = "WT"
        ELECTRIC_CONDUCTIVITY = "LF"
        CLEARANCE_HEIGHT = "DFH"
        TEMPERATURE_AIR_MEAN_200 = "LT"
        FLOW_SPEED = "VA"
        GROUNDWATER_LEVEL = "GRU"
        WIND_SPEED = "WG"
        HUMIDITY = "HL"
        OXYGEN_LEVEL = "O2"
        TURBIDITY = "TR"
        CURRENT = "R"
        WIND_DIRECTION = "WR"
        PRECIPITATION_HEIGHT = "NIEDERSCHLAG"
        PRECIPITATION_INTENSITY = "NIEDERSCHLAGSINTENSITÄT"
        WAVE_PERIOD = "TP"
        WAVE_HEIGHT_SIGN = "SIGH"
        WAVE_HEIGHT_MAX = "MAXH"
        PH_VALUE = "PH"
        CHLORID_CONCENTRATION = "CL"


class WsvPegelUnit(DatasetTreeCore):
    class DYNAMIC(Enum):
        WATER_LEVEL = OriginUnit.CENTIMETER.value, SIUnit.METER.value
        DISCHARGE = OriginUnit.CUBIC_METERS_PER_SECOND.value, SIUnit.CUBIC_METERS_PER_SECOND.value
        TEMPERATURE_WATER = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
        ELECTRIC_CONDUCTIVITY = OriginUnit.MICROSIEMENS_PER_CENTIMETER.value, SIUnit.SIEMENS_PER_METER.value
        CLEARANCE_HEIGHT = OriginUnit.METER.value, SIUnit.METER.value
        TEMPERATURE_AIR_MEAN_200 = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
        FLOW_SPEED = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value
        GROUNDWATER_LEVEL = OriginUnit.METER.value, SIUnit.METER.value
        WIND_SPEED = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value
        HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
        OXYGEN_LEVEL = OriginUnit.MILLIGRAM_PER_LITER.value, SIUnit.MILLIGRAM_PER_LITER.value
        TURBIDITY = OriginUnit.TURBIDITY.value, SIUnit.TURBIDITY.value
        CURRENT = OriginUnit.MAGNETIC_FIELD_STRENGTH.value, SIUnit.MAGNETIC_FIELD_STRENGTH.value
        WIND_DIRECTION = OriginUnit.WIND_DIRECTION.value, SIUnit.WIND_DIRECTION.value
        PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
        PRECIPITATION_INTENSITY = OriginUnit.MILLIMETER_PER_HOUR.value, SIUnit.MILLIMETER_PER_HOUR.value
        WAVE_PERIOD = OriginUnit.WAVE_PERIOD.value, SIUnit.WAVE_PERIOD.value
        WAVE_HEIGHT_SIGN = OriginUnit.CENTIMETER.value, SIUnit.METER.value
        WAVE_HEIGHT_MAX = OriginUnit.CENTIMETER.value, SIUnit.METER.value
        PH_VALUE = OriginUnit.DIMENSIONLESS.value, OriginUnit.DIMENSIONLESS.value
        CHLORID_CONCENTRATION = OriginUnit.MILLIGRAM_PER_LITER.value, OriginUnit.MILLIGRAM_PER_LITER.value


class WsvPegelResolution(Enum):
    DYNAMIC = Resolution.DYNAMIC.value


class WsvPegelPeriod(Enum):
    RECENT = Period.RECENT.value


class WsvPegelDataset(Enum):
    DYNAMIC = "DYNAMIC"


class WsvPegelValues(ScalarValuesCore):
    """Values class for WSV Pegelonline data"""

    _string_parameters = ()
    _irregular_parameters = ()
    _date_parameters = ()

    _endpoint = "https://pegelonline.wsv.de/webservices/rest-api/v2/stations/{station_id}/{parameter}/measurements.json"
    # Used for getting frequency of timeseries
    _station_endpoint = "https://pegelonline.wsv.de/webservices/rest-api/v2/stations/{station_id}/{parameter}/"

    @property
    def _data_tz(self) -> Timezone:
        return Timezone.GERMANY

    def _collect_station_parameter(self, station_id: str, parameter: Enum, dataset: Enum) -> pd.DataFrame:
        """
        Method to collect data for station parameter from WSV Pegelonline following its open REST-API at
        https://pegelonline.wsv.de/webservices/rest-api/v2/stations/
        :param station_id: station_id string
        :param parameter: parameter enumeration
        :param dataset: dataset enumeration
        :return: pandas DataFrame with data
        """
        url = self._endpoint.format(station_id=station_id, parameter=parameter.value)

        try:
            response = download_file(url, CacheExpiry.NO_CACHE)
        except FileNotFoundError:
            return pd.DataFrame()

        df = pd.read_json(response)

        df = df.rename(columns={"timestamp": Columns.DATE.value, "value": Columns.VALUE.value})

        df[Columns.PARAMETER.value] = parameter.value.lower()

        return df

    def fetch_dynamic_frequency(self, station_id, parameter: Enum, dataset: Enum) -> str:
        """
        Method to get the frequency string for a station and parameter from WSV Pegelonline. The frequency is given at
        each station dict queried from the REST-API under "equidistance"
        :param station_id: station_id string
        :param parameter: parameter enumeration
        :param dataset: dataset enumeration
        :return: frequency as string e.g. "15min" -> Literal["1min", "5min", "15min", "60min"]
        """
        url = self._station_endpoint.format(station_id=station_id, parameter=parameter.value)

        response = download_file(url)

        station_dict = json.load(response)

        return f"{station_dict['equidistance']}min"


class WsvPegelRequest(ScalarRequestCore):
    """Request class for WSV Pegelonline, a German river management facility and
    provider of river-based measurements for last 30 days"""

    _tz = Timezone.GERMANY

    _endpoint = "https://pegelonline.wsv.de/webservices/rest-api/v2/stations.json?includeTimeseries=true&includeCharacteristicValues=true"  # noqa:E501

    provider = Provider.WSV
    kind = Kind.OBSERVATION

    _resolution_type = ResolutionType.DYNAMIC
    _resolution_base = WsvPegelResolution

    _period_type = PeriodType.FIXED
    _period_base = WsvPegelPeriod

    _data_range = DataRange.FIXED

    _has_datasets = False

    _parameter_base = WsvPegelParameter
    _dataset_base = WsvPegelDataset

    _unit_tree = WsvPegelUnit

    _has_tidy_data = True

    _values = WsvPegelValues

    # Characteristic/statistical values may be provided for stations_result
    characteristic_values = {
        "m_i": "first flood marking",
        "m_ii": "second flood marking",
        "m_iii": "third flood marking",
        "mnw": "mean of low water level",
        "mw": "mean of water level",
        "mhw": "mean of high water level",
        "hhw": "highest water level",
        "hsw": "highest of shipping water level",
    }

    # extend base columns of core class with those of characteristic values plus gauge zero
    _base_columns = list(ScalarRequestCore._base_columns)
    _base_columns.extend(["gauge_zero", *characteristic_values.keys()])

    def __init__(
        self,
        parameter,
        start_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
        end_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
    ):
        super(WsvPegelRequest, self).__init__(
            parameter=parameter,
            resolution=Resolution.DYNAMIC,
            period=Period.RECENT,
            start_date=start_date,
            end_date=end_date,
        )

    def _all(self):
        """
        Method to get stations_result for WSV Pegelonline. It involves reading the REST API, doing some transformations
        and adding characteristic values in extra columns if given for each station.
        :return:
        """

        def _extract_ts(
            ts_list: List[dict],
        ) -> FLOAT_9_TIMES:
            """
            Function to extract water level related information namely gauge zero and characteristic values
            from timeseries dict given for each station.
            :param ts_list: list of dictionaries with each dictionary holding information for one
                characteristic value / gauge zero
            :return: tuple with values given in exact order
            """
            ts_water = None
            for ts in ts_list:
                if ts["shortname"] == "W":
                    ts_water = ts
                    break

            if not ts_water:
                return pd.NA, pd.NA, pd.NA, pd.NA, pd.NA, pd.NA, pd.NA, pd.NA, pd.NA

            gauge_datum = ts_water.get("gaugeZero", {}).get("value", pd.NA)

            characteristic_values = ts_water.get("characteristicValues") or {}  # could be empty list so ensure dict

            if characteristic_values:
                characteristic_values = (
                    pd.DataFrame.from_dict(characteristic_values).set_index("shortname").loc[:, "value"].to_dict()
                )

            m_i = characteristic_values.get("M_I", pd.NA)
            m_ii = characteristic_values.get("M_II", pd.NA)
            m_iii = characteristic_values.get("M_III", pd.NA)
            mnw = characteristic_values.get("MNW", pd.NA)
            mw = characteristic_values.get("MW", pd.NA)
            mhw = characteristic_values.get("MHW", pd.NA)
            hhw = characteristic_values.get("HHW", pd.NA)
            hsw = characteristic_values.get("HSW", pd.NA)

            return gauge_datum, m_i, m_ii, m_iii, mnw, mw, mhw, hhw, hsw

        response = download_file(self._endpoint, CacheExpiry.ONE_HOUR)

        df = pd.read_json(response)

        df = df.rename(columns={"number": "station_id", "shortname": "name", "km": "river_kilometer"})

        df.loc[:, "water"] = df["water"].map(lambda x: x["shortname"])

        timeseries = df.pop("timeseries")

        # Get available parameters per station
        df["ts"] = timeseries.apply(lambda ts_list: {t["shortname"].lower() for t in ts_list})

        parameters = {par.value.lower() for par, ds in self.parameter}

        # Filter out stations_result that do not have any of the parameters requested
        df = df.loc[df["ts"].map(lambda par: not not par.intersection(parameters)), :]

        df[["gauge_datum", "m_i", "m_ii", "m_iii", "mnw", "mw", "mhw", "hhw", "hsw"]] = timeseries.apply(
            func=_extract_ts
        ).apply(pd.Series)

        return df
