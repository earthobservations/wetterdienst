# -*- coding: utf-8 -*-
# Copyright (C) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import json
import logging
from datetime import datetime
from enum import Enum
from typing import List, Optional, Union

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

log = logging.getLogger(__file__)


class EaHydrologyResolution(Enum):
    MINUTE_15 = Resolution.MINUTE_15.value
    HOUR_6 = Resolution.HOUR_6.value
    DAILY = Resolution.DAILY.value


class EaHydrologyParameter(DatasetTreeCore):
    class MINUTE_15(Enum):
        FLOW = "flow"
        GROUNDWATER_LEVEL = "groundwater_level"

    class HOUR_6(Enum):
        FLOW = "flow"
        GROUNDWATER_LEVEL = "groundwater_level"

    class DAILY(Enum):
        FLOW = "flow"
        GROUNDWATER_LEVEL = "groundwater_level"


PARAMETER_MAPPING = {"flow": "Water Flow", "groundwater_level": "Groundwater level"}


class EaHydrologyUnit(DatasetTreeCore):
    class MINUTE_15(Enum):
        FLOW = OriginUnit.CUBIC_METERS_PER_SECOND.value, SIUnit.CUBIC_METERS_PER_SECOND.value
        GROUNDWATER_LEVEL = OriginUnit.METER.value, SIUnit.METER.value

    class HOUR_6(Enum):
        FLOW = OriginUnit.CUBIC_METERS_PER_SECOND.value, SIUnit.CUBIC_METERS_PER_SECOND.value
        GROUNDWATER_LEVEL = OriginUnit.METER.value, SIUnit.METER.value

    class DAILY(Enum):
        FLOW = OriginUnit.CUBIC_METERS_PER_SECOND.value, SIUnit.CUBIC_METERS_PER_SECOND.value
        GROUNDWATER_LEVEL = OriginUnit.METER.value, SIUnit.METER.value


class EaHydrologyPeriod(Enum):
    HISTORICAL = Period.HISTORICAL.value


class EaHydrologyValues(ScalarValuesCore):
    _base_url = "https://environment.data.gov.uk/hydrology/id/stations/{station_id}.json"
    _irregular_parameters = ()
    _string_parameters = ()
    _date_parameters = ()
    _data_tz = Timezone.UK

    def _collect_station_parameter(self, station_id: str, parameter: Enum, dataset: Enum) -> pd.DataFrame:
        endpoint = self._base_url.format(station_id=station_id)
        payload = download_file(endpoint, CacheExpiry.NO_CACHE)

        measures_list = json.loads(payload.read())["items"][0]["measures"]

        if type(measures_list) == dict:
            measures_list = [measures_list]

        measures_list = pd.Series(measures_list)

        measures_list = measures_list[
            measures_list.map(
                lambda measure: measure["parameterName"].lower().replace(" ", "")
                == parameter.value.lower().replace("_", "")
            )
        ]

        try:
            measure_dict = measures_list[0]
        except IndexError:
            return pd.DataFrame()

        values_endpoint = f"{measure_dict['@id']}/readings.json"

        payload = download_file(values_endpoint, CacheExpiry.FIVE_MINUTES)

        readings = json.loads(payload.read())["items"]

        df = pd.DataFrame.from_records(readings)

        return df.loc[:, ["dateTime", "value"]].rename(
            columns={"dateTime": Columns.DATE.value, "value": Columns.VALUE.value}
        )

    def fetch_dynamic_frequency(self, station_id, parameter, dataset):
        return


class EaHydrologyRequest(ScalarRequestCore):
    endpoint = "https://environment.data.gov.uk/hydrology/id/stations.json"
    _values = EaHydrologyValues
    _unit_tree = EaHydrologyUnit
    _tz = Timezone.UK
    provider = Provider.EA
    kind = Kind.OBSERVATION
    _resolution_base = EaHydrologyResolution
    _resolution_type = ResolutionType.MULTI
    _period_type = PeriodType.FIXED
    _period_base = EaHydrologyPeriod
    _parameter_base = EaHydrologyParameter
    _data_range = DataRange.FIXED
    _has_datasets = False
    _has_tidy_data = True

    def __init__(
        self,
        parameter: EaHydrologyParameter,
        resolution: EaHydrologyResolution,
        start_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
        end_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
    ):
        super(EaHydrologyRequest, self).__init__(
            parameter=parameter,
            resolution=resolution,
            period=Period.HISTORICAL,
            start_date=start_date,
            end_date=end_date,
        )

        if self.resolution == Resolution.MINUTE_15:
            self._resolution_as_int = 900
        elif self.resolution == Resolution.HOUR_6:
            self._resolution_as_int = 3600
        else:
            self._resolution_as_int = 86400

    def _all(self) -> pd.DataFrame:
        """
        Get stations listing UK environment agency data
        :return:
        """

        def _check_parameter_and_period(
            measures: Union[dict, List[dict]], resolution_as_int: int, parameters: List[str]
        ):
            # default: daily, for groundwater stations
            if type(measures) != list:
                measures = [measures]
            return (
                pd.Series(measures)
                .map(
                    lambda measure: measure.get("period", 86400) == resolution_as_int
                    and measure["observedProperty"]["label"] in parameters
                )
                .any()
            )

        log.info(f"Acquiring station listing from {self.endpoint}")

        response = download_file(self.endpoint, CacheExpiry.FIVE_MINUTES)

        payload = json.loads(response.read())["items"]

        df = pd.DataFrame.from_dict(payload)

        parameters = [PARAMETER_MAPPING[parameter.value] for parameter, _ in self.parameter]

        df.measures.apply(_check_parameter_and_period, resolution_as_int=self._resolution_as_int, parameters=parameters)
        # filter for stations that have wanted resolution and parameter combinations
        df = df[
            df.measures.apply(
                _check_parameter_and_period, resolution_as_int=self._resolution_as_int, parameters=parameters
            )
        ]

        return df.rename(
            columns={
                "label": Columns.NAME.value,
                "lat": Columns.LATITUDE.value,
                "long": Columns.LONGITUDE.value,
                "notation": Columns.STATION_ID.value,
            }
        ).rename(columns=str.lower)
