# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""WSV Pegelonline provider for water level data in Germany."""

from __future__ import annotations

from dataclasses import dataclass
from typing import ClassVar

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import DATASET_NAME_DEFAULT, ParameterModel, build_metadata_model
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
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
                },
            ],
        },
    ],
}
WsvPegelMetadata = build_metadata_model(WsvPegelMetadata, "WsvPegelMetadata")


class WsvPegelValues(TimeseriesValues):
    """Values class for WSV Pegelonline."""

    _endpoint = "https://pegelonline.wsv.de/webservices/rest-api/v2/stations/{station_id}/{parameter}/measurements.json"
    # Used for getting frequency of timeseries
    _station_endpoint = "https://pegelonline.wsv.de/webservices/rest-api/v2/stations/{station_id}/{parameter}/"

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel,
    ) -> pl.DataFrame:
        """Collect data for station parameter from WSV Pegelonline.

        REST-API at https://pegelonline.wsv.de/webservices/rest-api/v2/stations/.

        """
        url = self._endpoint.format(station_id=station_id, parameter=parameter_or_dataset.name_original)
        file = download_file(
            url=url,
            cache_dir=self.sr.stations.settings.cache_dir,
            ttl=CacheExpiry.NO_CACHE,
            client_kwargs=self.sr.stations.settings.fsspec_client_kwargs,
            cache_disable=self.sr.stations.settings.cache_disable,
        )
        if isinstance(file.content, FileNotFoundError):
            return pl.DataFrame()
        df = pl.read_json(file.content)
        df = df.rename(mapping={"timestamp": "date", "value": "value"})
        return df.with_columns(
            pl.lit(parameter_or_dataset.dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(parameter_or_dataset.dataset.name, dtype=pl.String).alias("dataset"),
            pl.lit(parameter_or_dataset.name_original.lower()).alias("parameter"),
            pl.col("date").str.to_datetime("%Y-%m-%dT%H:%M:%S%z"),
            pl.col("value"),
            pl.lit(None, dtype=pl.Float64).alias("quality"),
        )


@dataclass
class WsvPegelRequest(TimeseriesRequest):
    """Request class for WSV Pegelonline.

    Pegelonline is a German river management facility and
    provider of river-based measurements for last 30 days.
    """

    metadata = WsvPegelMetadata
    _values = WsvPegelValues

    _endpoint = (
        "https://pegelonline.wsv.de/webservices/rest-api/v2/"
        "stations.json?includeTimeseries=true&includeCharacteristicValues=true"
    )

    # Characteristic/statistical values may be provided for stations_result
    characteristic_values: ClassVar = {
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
    _base_columns: ClassVar = (
        *TimeseriesRequest._base_columns,  # noqa: SLF001
        "gauge_zero",
        *characteristic_values.keys(),
    )

    def _all(self) -> pl.LazyFrame:
        """Get stations for WSV Pegelonline.

        It involves reading the REST API, doing some transformations
        and adding characteristic values in extra columns if given for each station.
        """
        file = download_file(
            url=self._endpoint,
            cache_dir=self.settings.cache_dir,
            ttl=CacheExpiry.ONE_HOUR,
            client_kwargs=self.settings.fsspec_client_kwargs,
            cache_disable=self.settings.cache_disable,
        )
        file.raise_if_exception()
        df = pl.read_json(
            file.content,
            schema={
                "number": pl.String,
                "shortname": pl.String,
                "km": pl.Float64,
                "latitude": pl.Float64,
                "longitude": pl.Float64,
                "water": pl.Struct(
                    {
                        "shortname": pl.String,
                    },
                ),
                "timeseries": pl.List(
                    pl.Struct(
                        {
                            "shortname": pl.String,
                            "gaugeZero": pl.Struct(
                                {
                                    "value": pl.Float64,
                                },
                            ),
                            "characteristicValues": pl.List(
                                pl.Struct(
                                    {
                                        "shortname": pl.String,
                                        "value": pl.Float64,
                                    },
                                ),
                            ),
                        },
                    ),
                ),
            },
        )
        df = df.lazy()
        df = df.rename(mapping={"number": "station_id", "shortname": "name", "km": "river_kilometer"})
        df = df.with_columns(
            pl.col("water").struct.field("shortname"),
            pl.col("timeseries").list.eval(pl.element().struct.field("shortname").str.to_lowercase()).alias("ts"),
        )
        parameters = {parameter.name_original.lower() for parameter in self.parameters}
        df = df.filter(pl.col("ts").list.set_intersection(list(parameters)).list.len() > 0)
        df = df.with_columns(
            pl.col("timeseries")
            .list.eval(pl.element().filter(pl.element().struct.field("shortname") == "W"))
            .list.first()
            .alias("ts_water"),
        )
        return df.select(
            pl.lit(self.metadata[0].name, dtype=pl.String).alias("resolution"),
            pl.lit(self.metadata[0][0].name, dtype=pl.String).alias("dataset"),
            pl.all().exclude(["timeseries", "ts", "ts_water"]),
            pl.col("ts_water").struct.field("gaugeZero").struct.field("value").alias("gauge_datum"),
            pl.col("ts_water")
            .struct.field("characteristicValues")
            .list.eval(pl.element().filter(pl.element().struct.field("shortname") == "M_I"))
            .list.first()
            .struct.field("value")
            .alias("m_i"),
            pl.col("ts_water")
            .struct.field("characteristicValues")
            .list.eval(pl.element().filter(pl.element().struct.field("shortname") == "M_II"))
            .list.first()
            .struct.field("value")
            .alias("m_ii"),
            pl.col("ts_water")
            .struct.field("characteristicValues")
            .list.eval(pl.element().filter(pl.element().struct.field("shortname") == "M_III"))
            .list.first()
            .struct.field("value")
            .alias("m_iii"),
            pl.col("ts_water")
            .struct.field("characteristicValues")
            .list.eval(pl.element().filter(pl.element().struct.field("shortname") == "MNW"))
            .list.first()
            .struct.field("value")
            .alias("mnw"),
            pl.col("ts_water")
            .struct.field("characteristicValues")
            .list.eval(pl.element().filter(pl.element().struct.field("shortname") == "MW"))
            .list.first()
            .struct.field("value")
            .alias("mw"),
            pl.col("ts_water")
            .struct.field("characteristicValues")
            .list.eval(pl.element().filter(pl.element().struct.field("shortname") == "MHW"))
            .list.first()
            .struct.field("value")
            .alias("mhw"),
            pl.col("ts_water")
            .struct.field("characteristicValues")
            .list.eval(pl.element().filter(pl.element().struct.field("shortname") == "HHW"))
            .list.first()
            .struct.field("value")
            .alias("hhw"),
            pl.col("ts_water")
            .struct.field("characteristicValues")
            .list.eval(pl.element().filter(pl.element().struct.field("shortname") == "HSW"))
            .list.first()
            .struct.field("value")
            .alias("hsw"),
        )
