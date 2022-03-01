# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum
from io import BytesIO

import pandas as pd

from wetterdienst import Kind, Period, Provider, Resolution
from wetterdienst.core.scalar.request import ScalarRequestCore
from wetterdienst.core.scalar.values import ScalarValuesCore
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.datarange import DataRange
from wetterdienst.metadata.period import PeriodType
from wetterdienst.metadata.resolution import ResolutionType
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.metadata.unit import OriginUnit, SIUnit
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import NetworkFilesystemManager
from wetterdienst.util.parameter import DatasetTreeCore


class WsvPegelParameter(DatasetTreeCore):
    class DYNAMIC(Enum):
        WATER_LEVEL = "W"
        DISCHARGE = "Q"
        RUNOFF = DISCHARGE


class WsvPegelUnit(DatasetTreeCore):
    class DYNAMIC(Enum):
        WATER_LEVEL = OriginUnit.CENTIMETER.value, SIUnit.METER.value
        DISCHARGE = OriginUnit.CUBIC_METERS_PER_SECOND.value, SIUnit.CUBIC_METERS_PER_SECOND.value


class WsvPegelResolution(Enum):
    DYNAMIC = Resolution.DYNAMIC.value


class WsvPegelDataset(Enum):
    DYNAMIC = "DYNAMIC"


class WsvPegelValues(ScalarValuesCore):
    _string_parameters = ()
    _integer_parameters = ()
    _irregular_parameters = ()
    _date_parameters = ()

    _endpoint = "https://pegelonline.wsv.de/webservices/rest-api/v2/stations/{station_id}/{parameter}/measurements.json"
    _fs = NetworkFilesystemManager.get(CacheExpiry.NO_CACHE)

    @property
    def _data_tz(self) -> Timezone:
        return Timezone.GERMANY

    def _collect_station_parameter(self, station_id: str, parameter: Enum, dataset: Enum) -> pd.DataFrame:
        url = self._endpoint.format(station_id=station_id, parameter=parameter.value)

        try:
            response = self._fs.cat(url)
        except FileNotFoundError:
            return pd.DataFrame()

        df = pd.read_json(BytesIO(response))

        df = df.rename(columns={"timestamp": Columns.DATE.value, "value": Columns.VALUE.value})

        df[Columns.PARAMETER.value] = parameter.value.lower()

        return df


class WsvPegelRequest(ScalarRequestCore):
    _tz = Timezone.GERMANY

    # _endpoint = "https://pegelonline.wsv.de/webservices/rest-api/v2/stations.json"
    _endpoint = "https://pegelonline.wsv.de/webservices/rest-api/v2/stations.json?includeTimeseries=true&includeCharacteristicValues=true"
    _fs = NetworkFilesystemManager.get(CacheExpiry.ONE_HOUR)

    provider = Provider.WSV
    kind = Kind.OBSERVATION

    _resolution_type = ResolutionType.DYNAMIC
    _resolution_base = WsvPegelResolution

    _period_type = PeriodType.FIXED
    _period_base = Period.RECENT

    _data_range = DataRange.FIXED

    _has_datasets = False

    _parameter_base = WsvPegelParameter
    _dataset_base = WsvPegelDataset

    _unit_tree = WsvPegelUnit

    _has_tidy_data = True

    _values = WsvPegelValues

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

    _base_columns = list(ScalarRequestCore._base_columns)
    _base_columns.extend(["gauge_zero", "m_i", "m_ii", "m_iii", "mnw", "mw", "mhw", "hhw", "hsw"])

    def __init__(self, parameter):
        super(WsvPegelRequest, self).__init__(parameter=parameter, resolution=Resolution.DYNAMIC, period=Period.RECENT)

    def _all(self):
        def _extract_ts(ts_list: list[dict]) -> pd.DataFrame:
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

        response = self._fs.cat(self._endpoint)

        df = pd.read_json(BytesIO(response))

        df = df.rename(columns={"number": "station_id", "shortname": "name", "km": "river_kilometer"})

        df.loc[:, "water"] = df["water"].map(lambda x: x["shortname"])

        timeseries = df.pop("timeseries")

        df["ts"] = timeseries.apply(lambda ts_list: {t["shortname"].lower() for t in ts_list})

        parameters = {par.value.lower() for par, ds in self.parameter}

        df = df.loc[df["ts"].map(lambda par: not not par.intersection(parameters)), :]

        df[["gauge_datum", "m_i", "m_ii", "m_iii", "mnw", "mw", "mhw", "hhw", "hsw"]] = timeseries.apply(
            func=_extract_ts
        ).apply(pd.Series)

        return df


if __name__ == "__main__":
    stations = WsvPegelRequest(WsvPegelParameter.DYNAMIC.WATER_LEVEL).filter_by_station_id("48900237")
    print(stations.df)

    values = next(stations.values.query())
    print(values.df)
