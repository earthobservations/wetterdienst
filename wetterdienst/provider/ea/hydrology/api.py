# Copyright (C) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import json
import logging

import polars as pl

from wetterdienst.core.timeseries.metadata import (
    DATASET_NAME_DEFAULT,
    ParameterModel,
    build_metadata_model,
)
from wetterdienst.core.timeseries.request import _DATETIME_TYPE, _PARAMETER_TYPE, _SETTINGS_TYPE, TimeseriesRequest
from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.columns import Columns
from wetterdienst.util.network import download_file

log = logging.getLogger(__file__)


EAHydrologyMetadata = {
    "name_short": "EA",
    "name_english": "Environment Agency",
    "name_local": "Environment Agency",
    "country": "United Kingdom",
    "copyright": "© Environment Agency of UK",
    "url": "https://environment.data.gov.uk/",
    "kind": "observation",
    "timezone": "Europe/London",
    "timezone_data": "Europe/London",
    "resolutions": [
        {
            "name": "15_minutes",
            "name_original": "15_minutes",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [
                {
                    "name": "observations",
                    "name_original": "observations",
                    "grouped": False,
                    "parameters": [
                        {
                            "name": "discharge",
                            "name_original": "flow",
                            "unit_type": "volume_per_time",
                            "unit": "cubic_meter_per_second",
                        },
                        {
                            "name": "groundwater_level",
                            "name_original": "groundwater_level",
                            "unit_type": "length_medium",
                            "unit": "meter",
                        },
                    ],
                }
            ],
        },
        {
            "name": "6_hour",
            "name_original": "6_hour",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [
                {
                    "name": "observations",
                    "name_original": "observations",
                    "grouped": False,
                    "parameters": [
                        {
                            "name": "discharge",
                            "name_original": "flow",
                            "unit_type": "volume_per_time",
                            "unit": "cubic_meter_per_second",
                        },
                        {
                            "name": "groundwater_level",
                            "name_original": "groundwater_level",
                            "unit_type": "length_medium",
                            "unit": "meter",
                        },
                    ],
                }
            ],
        },
        {
            "name": "daily",
            "name_original": "daily",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": False,
                    "periods": ["historical"],
                    "parameters": [
                        {
                            "name": "discharge",
                            "name_original": "flow",
                            "unit_type": "volume_per_time",
                            "unit": "cubic_meter_per_second",
                        },
                        {
                            "name": "groundwater_level",
                            "name_original": "groundwater_level",
                            "unit_type": "length_medium",
                            "unit": "meter",
                        },
                    ],
                }
            ],
        },
    ],
}
EAHydrologyMetadata = build_metadata_model(EAHydrologyMetadata, "EAHydrologyMetadata")


class EAHydrologyValues(TimeseriesValues):
    _url = "https://environment.data.gov.uk/hydrology/id/stations/{station_id}.json"

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel,
    ) -> pl.DataFrame:
        url = self._url.format(station_id=station_id)
        log.info(f"Downloading file {url}.")
        payload = download_file(url=url, settings=self.sr.stations.settings, ttl=CacheExpiry.NO_CACHE)
        measures_data = json.load(payload)["items"][0]["measures"]
        s_measures = pl.Series(name="measure", values=measures_data).to_frame()
        s_measures = s_measures.filter(
            pl.col("measure")
            .struct.field("parameterName")
            .str.to_lowercase()
            .str.replace(" ", "")
            .eq(parameter_or_dataset.name_original.lower().replace("_", "")),
        )
        try:
            measure_dict = s_measures.get_column("measure")[0]
        except IndexError:
            return pl.DataFrame()
        readings_url = f"{measure_dict['@id']}/readings.json"
        log.info(f"Downloading file {readings_url}.")
        payload = download_file(url=readings_url, settings=self.sr.stations.settings, ttl=CacheExpiry.FIVE_MINUTES)
        data = json.loads(payload.read())["items"]
        df = pl.from_dicts(data)
        df = df.select(
            pl.lit(parameter_or_dataset.name_original).alias("parameter"), pl.col("dateTime"), pl.col("value")
        )
        df = df.rename(mapping={"dateTime": Columns.DATE.value, "value": Columns.VALUE.value})
        return df.with_columns(pl.col(Columns.DATE.value).str.to_datetime(format="%Y-%m-%dT%H:%M:%S", time_zone="UTC"))


class EAHydrologyRequest(TimeseriesRequest):
    metadata = EAHydrologyMetadata
    _values = EAHydrologyValues

    _url = "https://environment.data.gov.uk/hydrology/id/stations.json"

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
        Get stations listing UK environment agency data
        :return:
        """
        log.info(f"Acquiring station listing from {self._url}")
        payload = download_file(self._url, self.settings, CacheExpiry.FIVE_MINUTES)
        data = json.load(payload)["items"]
        for station in data:
            self._transform_station(station)
        df = pl.from_dicts(data)
        # filter for stations that have wanted resolution and parameter combinations
        df_measures = (
            df.select(pl.col("notation"), pl.col("measures"))
            .explode("measures")
            .with_columns(pl.col("measures").struct.field("parameter"))
        )
        df_measures = df_measures.group_by(["notation"]).agg(pl.col("parameter").alias("parameters"))
        df_notations = df_measures.filter(
            pl.col("parameters").list.set_intersection(["flow", "level"]).len() > 0
        ).select("notation")
        df = df.join(df_notations, how="inner", on="notation")
        df = df.rename(mapping=lambda col: col.lower())
        df = df.rename(
            mapping={
                "label": Columns.NAME.value,
                "lat": Columns.LATITUDE.value,
                "long": Columns.LONGITUDE.value,
                "notation": Columns.STATION_ID.value,
                "dateopened": Columns.START_DATE.value,
                "dateclosed": Columns.END_DATE.value,
            },
        )
        df = df.with_columns(
            pl.col("start_date").str.to_datetime(format="%Y-%m-%d"),
            pl.col("end_date").str.to_datetime(format="%Y-%m-%d"),
        )
        return df.lazy()

    @staticmethod
    def _transform_station(station: dict) -> None:
        """Reduce station dictionary to required keys and format dateOpened and dateClosed."""
        required_keys = ["label", "notation", "lat", "long", "dateOpened", "dateClosed", "measures"]
        for key in list(station.keys()):
            if key not in required_keys:
                del station[key]
        if isinstance(station["dateOpened"], list):
            station["dateOpened"] = station["dateOpened"][1]
        if "dateClosed" not in station:
            station["dateClosed"] = None
