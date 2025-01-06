# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import datetime as dt

import polars as pl

from wetterdienst.core.timeseries.metadata import DATASET_NAME_DEFAULT, ParameterModel, build_metadata_model
from wetterdienst.core.timeseries.request import _DATETIME_TYPE, _PARAMETER_TYPE, _SETTINGS_TYPE, TimeseriesRequest
from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.columns import Columns
from wetterdienst.util.network import download_file

FLOAT_9_TIMES = tuple[
    float | None,
    float | None,
    float | None,
    float | None,
    float | None,
    float | None,
    float | None,
    float | None,
    float | None,
]


WsvPegelMetadata = {
    "name_short": "WSV",
    "name_english": "Federal Waterways and Shipping Administration",
    "name_local": "Wasserstraßen- und Schifffahrtsverwaltung des Bundes",
    "country": "Germany",
    "copyright": "© Wasserstraßen- und Schifffahrtsverwaltung des Bundes (WSV), Pegelonline",
    "url": "https://pegelonline.wsv.de/webservice/ueberblick",
    "kind": "observation",
    "timezone": "Europe/Berlin",
    "timezone_data": "Europe/Berlin",
    "resolutions": [
        {
            "name": "dynamic",
            "name_original": "dynamic",
            "periods": ["recent"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": False,
                    "parameters": [
                        {
                            "name": "stage",
                            "name_original": "W",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        {
                            "name": "discharge",
                            "name_original": "Q",
                            "unit_type": "volume_per_time",
                            "unit": "cubic_meter_per_second",
                        },
                        {
                            "name": "temperature_water",
                            "name_original": "WT",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "electric_conductivity",
                            "name_original": "LF",
                            "unit_type": "conductivity",
                            "unit": "microsiemens_per_centimeter",
                        },
                        {
                            "name": "clearance_height",
                            "name_original": "DFH",
                            "unit_type": "length_short",
                            "unit": "meter",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "LT",
                            "unit_type": "temperature",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "flow_speed",
                            "name_original": "VA",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "groundwater_level",
                            "name_original": "GRU",
                            "unit_type": "length_medium",
                            "unit": "meter",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "WG",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "humidity",
                            "name_original": "HL",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "oxygen_level",
                            "name_original": "O2",
                            "unit_type": "concentration",
                            "unit": "milligram_per_liter",
                        },
                        {
                            "name": "turbidity",
                            "name_original": "TR",
                            "unit_type": "turbidity",
                            "unit": "nephelometric_turbidity",
                        },
                        {
                            "name": "current",
                            "name_original": "R",
                            "unit_type": "magnetic_field_intensity",
                            "unit": "magnetic_field_strength",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "WR",
                            "unit_type": "angle",
                            "unit": "degree",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "NIEDERSCHLAG",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_intensity",
                            "name_original": "NIEDERSCHLAGSINTENSITÄT",
                            "unit_type": "precipitation_intensity",
                            "unit": "millimeter_per_hour",
                        },
                        {
                            "name": "wave_period",
                            "name_original": "TP",
                            "unit_type": "wave_period",
                            "unit": "wave_period",
                        },
                        {
                            "name": "wave_height_sign",
                            "name_original": "SIGH",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        {
                            "name": "wave_height_max",
                            "name_original": "MAXH",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        {
                            "name": "ph_value",
                            "name_original": "PH",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "chlorid_concentration",
                            "name_original": "CL",
                            "unit_type": "concentration",
                            "unit": "milligram_per_liter",
                        },
                    ],
                }
            ],
        }
    ],
}
WsvPegelMetadata = build_metadata_model(WsvPegelMetadata, "WsvPegelMetadata")


class WsvPegelValues(TimeseriesValues):
    """Values class for WSV Pegelonline data"""

    _endpoint = "https://pegelonline.wsv.de/webservices/rest-api/v2/stations/{station_id}/{parameter}/measurements.json"
    # Used for getting frequency of timeseries
    _station_endpoint = "https://pegelonline.wsv.de/webservices/rest-api/v2/stations/{station_id}/{parameter}/"

    def _collect_station_parameter_or_dataset(
        self, station_id: str, parameter_or_dataset: ParameterModel
    ) -> pl.DataFrame:
        """
        Method to collect data for station parameter from WSV Pegelonline following its open REST-API at
        https://pegelonline.wsv.de/webservices/rest-api/v2/stations/
        :param station_id: station_id string
        :param parameter: parameter enumeration
        :param dataset: dataset enumeration
        :return: pandas DataFrame with data
        """
        url = self._endpoint.format(station_id=station_id, parameter=parameter_or_dataset.name_original)

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
            pl.lit(parameter_or_dataset.name_original.lower()).alias(Columns.PARAMETER.value),
            pl.lit(None, dtype=pl.Float64).alias(Columns.QUALITY.value),
        )


class WsvPegelRequest(TimeseriesRequest):
    """Request class for WSV Pegelonline, a German river management facility and
    provider of river-based measurements for last 30 days"""

    metadata = WsvPegelMetadata
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
                return (None, None, None, None, None, None, None, None, None)

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

            return (gauge_datum, m_i, m_ii, m_iii, mnw, mw, mhw, hhw, hsw)

        response = download_file(self._endpoint, self.settings, CacheExpiry.ONE_HOUR)

        df = pl.read_json(response).lazy()
        df = df.rename(mapping={"number": "station_id", "shortname": "name", "km": "river_kilometer"})
        df = df.with_columns(
            pl.col("water").struct.field("shortname"),
            pl.col("timeseries")
            .map_elements(lambda ts_list: [t["shortname"].lower() for t in ts_list], return_dtype=pl.List(pl.String))
            .alias("ts"),
        )
        parameters = {parameter.name_original.lower() for parameter in self.parameters}
        df = df.filter(pl.col("ts").list.set_intersection(list(parameters)).list.len() > 0)
        df = df.with_columns(pl.col("timeseries").map_elements(_extract_ts, return_dtype=pl.List(pl.Float64)))
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
