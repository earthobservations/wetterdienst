# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import datetime as dt
import json
from enum import Enum
from typing import TYPE_CHECKING, Optional

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

FLOAT_9_TIMES = list[Optional[float]]


class WsvPegelParameter(DatasetTreeCore):
    class DYNAMIC(DatasetTreeCore):
        class DYNAMIC(Enum):
            STAGE = "W"
            DISCHARGE = "Q"
            RUNOFF = DISCHARGE
            TEMPERATURE_WATER = "WT"
            ELECTRIC_CONDUCTIVITY = "LF"
            CLEARANCE_HEIGHT = "DFH"
            TEMPERATURE_AIR_MEAN_2M = "LT"
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

        STAGE = DYNAMIC.STAGE
        DISCHARGE = DYNAMIC.DISCHARGE
        RUNOFF = DYNAMIC.RUNOFF
        TEMPERATURE_WATER = DYNAMIC.TEMPERATURE_WATER
        ELECTRIC_CONDUCTIVITY = DYNAMIC.ELECTRIC_CONDUCTIVITY
        CLEARANCE_HEIGHT = DYNAMIC.CLEARANCE_HEIGHT
        TEMPERATURE_AIR_MEAN_2M = DYNAMIC.TEMPERATURE_AIR_MEAN_2M
        FLOW_SPEED = DYNAMIC.FLOW_SPEED
        GROUNDWATER_LEVEL = DYNAMIC.GROUNDWATER_LEVEL
        WIND_SPEED = DYNAMIC.WIND_SPEED
        HUMIDITY = DYNAMIC.HUMIDITY
        OXYGEN_LEVEL = DYNAMIC.OXYGEN_LEVEL
        TURBIDITY = DYNAMIC.TURBIDITY
        CURRENT = DYNAMIC.CURRENT
        WIND_DIRECTION = DYNAMIC.WIND_DIRECTION
        PRECIPITATION_HEIGHT = DYNAMIC.PRECIPITATION_HEIGHT
        PRECIPITATION_INTENSITY = DYNAMIC.PRECIPITATION_INTENSITY
        WAVE_PERIOD = DYNAMIC.WAVE_PERIOD
        WAVE_HEIGHT_SIGN = DYNAMIC.WAVE_HEIGHT_SIGN
        WAVE_HEIGHT_MAX = DYNAMIC.WAVE_HEIGHT_MAX
        PH_VALUE = DYNAMIC.PH_VALUE
        CHLORID_CONCENTRATION = DYNAMIC.CHLORID_CONCENTRATION


class WsvPegelUnit(DatasetTreeCore):
    class DYNAMIC(DatasetTreeCore):
        class DYNAMIC(UnitEnum):
            STAGE = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            DISCHARGE = OriginUnit.CUBIC_METERS_PER_SECOND.value, SIUnit.CUBIC_METERS_PER_SECOND.value
            TEMPERATURE_WATER = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
            ELECTRIC_CONDUCTIVITY = OriginUnit.MICROSIEMENS_PER_CENTIMETER.value, SIUnit.SIEMENS_PER_METER.value
            CLEARANCE_HEIGHT = OriginUnit.METER.value, SIUnit.METER.value
            TEMPERATURE_AIR_MEAN_2M = OriginUnit.DEGREE_CELSIUS.value, SIUnit.DEGREE_KELVIN.value
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


class WsvPegelValues(TimeseriesValues):
    """Values class for WSV Pegelonline data"""

    _endpoint = "https://pegelonline.wsv.de/webservices/rest-api/v2/stations/{station_id}/{parameter}/measurements.json"
    # Used for getting frequency of timeseries
    _station_endpoint = "https://pegelonline.wsv.de/webservices/rest-api/v2/stations/{station_id}/{parameter}/"

    @property
    def _data_tz(self) -> Timezone:
        return Timezone.GERMANY

    def _collect_station_parameter(
        self,
        station_id: str,
        parameter: Enum,
        dataset: Enum,  # noqa: ARG002
    ) -> pl.DataFrame:
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
            response = download_file(url, self.sr.stations.settings, CacheExpiry.NO_CACHE)
        except FileNotFoundError:
            return pl.DataFrame()

        df = pl.read_json(response)
        df = df.rename(mapping={"timestamp": Columns.DATE.value, "value": Columns.VALUE.value})
        df = df.with_columns(
            pl.col(Columns.DATE.value).map_elements(dt.datetime.fromisoformat, return_dtype=pl.Datetime)
        )
        return df.with_columns(
            pl.col(Columns.DATE.value).dt.replace_time_zone(time_zone="UTC"),
            pl.lit(parameter.value.lower()).alias(Columns.PARAMETER.value),
            pl.lit(None, dtype=pl.Float64).alias(Columns.QUALITY.value),
        )

    def _fetch_frequency(
        self,
        station_id,
        parameter: Enum,
        dataset: Enum,  # noqa: ARG002
    ) -> str:
        """
        Method to get the frequency string for a station and parameter from WSV Pegelonline. The frequency is given at
        each station dict queried from the REST-API under "equidistance"
        :param station_id: station_id string
        :param parameter: parameter enumeration
        :param dataset: dataset enumeration
        :return: frequency as string e.g. "15min" -> Literal["1min", "5min", "15min", "60min"]
        """
        url = self._station_endpoint.format(station_id=station_id, parameter=parameter.value)

        response = download_file(url, self.sr.stations.settings)

        station_dict = json.load(response)

        return f"{station_dict['equidistance']}m"


class WsvPegelRequest(TimeseriesRequest):
    """Request class for WSV Pegelonline, a German river management facility and
    provider of river-based measurements for last 30 days"""

    _provider = Provider.WSV
    _kind = Kind.OBSERVATION
    _tz = Timezone.GERMANY
    _dataset_base = WsvPegelDataset
    _parameter_base = WsvPegelParameter
    _unit_base = WsvPegelUnit
    _resolution_type = ResolutionType.DYNAMIC
    _resolution_base = WsvPegelResolution
    _period_type = PeriodType.FIXED
    _period_base = WsvPegelPeriod
    _has_datasets = False
    _data_range = DataRange.FIXED
    _values = WsvPegelValues

    _endpoint = (
        "https://pegelonline.wsv.de/webservices/rest-api/v2/"
        "stations.json?includeTimeseries=true&includeCharacteristicValues=true"
    )

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
    _base_columns = list(TimeseriesRequest._base_columns)
    _base_columns.extend(["gauge_zero", *characteristic_values.keys()])

    def __init__(
        self,
        parameter: str | WsvPegelParameter | Parameter | Sequence[str | WsvPegelParameter | Parameter],
        start_date: str | dt.datetime | None = None,
        end_date: str | dt.datetime | None = None,
        settings: Settings | None = None,
    ):
        super().__init__(
            parameter=parameter,
            resolution=Resolution.DYNAMIC,
            period=Period.RECENT,
            start_date=start_date,
            end_date=end_date,
            settings=settings,
        )

    def _all(self) -> pl.LazyFrame:
        """
        Method to get stations_result for WSV Pegelonline. It involves reading the REST API, doing some transformations
        and adding characteristic values in extra columns if given for each station.
        :return:
        """

        def _extract_ts(
            ts_list: list[dict],
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
                return [None, None, None, None, None, None, None, None, None]

            gauge_datum = ts_water.get("gaugeZero", {}).get("value", None)

            # can be empty list or list with Nones -> ensure dict
            characteristic_values = ts_water.get("characteristicValues")
            characteristic_values = characteristic_values if isinstance(characteristic_values, dict) else {}

            if characteristic_values:
                characteristic_values = pl.DataFrame(characteristic_values).select(["shortname", "value"]).to_dict()

            m_i = characteristic_values.get("M_I", None)
            m_ii = characteristic_values.get("M_II", None)
            m_iii = characteristic_values.get("M_III", None)
            mnw = characteristic_values.get("MNW", None)
            mw = characteristic_values.get("MW", None)
            mhw = characteristic_values.get("MHW", None)
            hhw = characteristic_values.get("HHW", None)
            hsw = characteristic_values.get("HSW", None)

            return [gauge_datum, m_i, m_ii, m_iii, mnw, mw, mhw, hhw, hsw]

        response = download_file(self._endpoint, self.settings, CacheExpiry.ONE_HOUR)

        df = pl.read_json(response).lazy()
        df = df.rename(mapping={"number": "station_id", "shortname": "name", "km": "river_kilometer"})
        df = df.with_columns(pl.col("water").struct.field("shortname"))
        df = df.select(
            pl.all(),
            pl.col("timeseries")
            .map_elements(lambda ts_list: {t["shortname"].lower() for t in ts_list}, return_dtype=pl.List(pl.String))
            .alias("ts"),
        )
        parameters = {par.value.lower() for par, ds in self.parameter}
        df = df.filter(pl.col("ts").list.set_intersection(list(parameters)).list.len() > 0)
        df = df.with_columns(pl.col("timeseries").map_elements(_extract_ts, return_dtype=pl.Array(pl.Float64, 9)))
        return df.select(
            pl.all().exclude(["timeseries", "ts"]),
            pl.col("timeseries").list.get(0).alias("gauge_datum"),
            pl.col("timeseries").list.get(1).alias("m_i"),
            pl.col("timeseries").list.get(2).alias("m_ii"),
            pl.col("timeseries").list.get(3).alias("m_iii"),
            pl.col("timeseries").list.get(4).alias("mnw"),
            pl.col("timeseries").list.get(5).alias("mw"),
            pl.col("timeseries").list.get(6).alias("mhw"),
            pl.col("timeseries").list.get(7).alias("hhw"),
            pl.col("timeseries").list.get(8).alias("hsw"),
        )
