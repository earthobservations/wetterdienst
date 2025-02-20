# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Geosphere observation data provider."""

from __future__ import annotations

import datetime as dt
import json
import logging
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, ClassVar
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.core.timeseries.request import _DATETIME_TYPE, _PARAMETER_TYPE, _SETTINGS_TYPE, TimeseriesRequest
from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.geosphere.observation.metadata import GeosphereObservationMetadata
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from wetterdienst.core.timeseries.metadata import DatasetModel

log = logging.getLogger(__name__)


class GeosphereObservationValues(TimeseriesValues):
    """Values class for geosphere observation data."""

    _endpoint = (
        "https://dataset.api.hub.geosphere.at/v1/station/historical/{dataset}?"
        "parameters={parameters}&"
        "start={start_date}&"
        "end={end_date}&"
        "station_ids={station_id}&"
        "output_format=geojson"
    )
    # dates collected from ZAMG website, end date will be set to now if not given
    _default_start_dates: ClassVar = {
        Resolution.MINUTE_10: dt.datetime(1992, 5, 20, tzinfo=ZoneInfo("UTC")),
        Resolution.HOURLY: dt.datetime(1880, 3, 31, tzinfo=ZoneInfo("UTC")),
        Resolution.DAILY: dt.datetime(1774, 12, 31, tzinfo=ZoneInfo("UTC")),
        Resolution.MONTHLY: dt.datetime(1767, 11, 30, tzinfo=ZoneInfo("UTC")),
    }

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: DatasetModel,
    ) -> pl.DataFrame:
        start_date = self.sr.start_date or self._default_start_dates[parameter_or_dataset.resolution.value]
        end_date = self.sr.end_date or datetime.now(ZoneInfo("UTC"))
        # add buffers
        start_date = start_date - timedelta(days=1)
        end_date = end_date + timedelta(days=1)
        parameters = [parameter.name_original for parameter in parameter_or_dataset.parameters]
        url = self._endpoint.format(
            station_id=station_id,
            parameters=",".join(parameters),
            dataset=parameter_or_dataset.name_original,
            start_date=start_date.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%m"),
            end_date=end_date.astimezone(ZoneInfo("UTC")).strftime("%Y-%m-%dT%H:%m"),
        )
        log.info(f"Downloading file {url}.")
        response = download_file(url=url, settings=self.sr.stations.settings, ttl=CacheExpiry.FIVE_MINUTES)
        data_raw = json.loads(response.read())
        timestamps = data_raw.pop("timestamps")
        data = {"date": timestamps}
        for par, par_dict in data_raw["features"][0]["properties"]["parameters"].items():
            data[par] = par_dict["data"]
        df = pl.DataFrame(data, orient="col")
        df = df.unpivot(
            index=["date"],
            variable_name="parameter",
            value_name="value",
        )
        # adjust units for radiation parameters of 10 minute/hourly resolution from W / m² to J / cm²
        if parameter_or_dataset.resolution.value == Resolution.MINUTE_10:
            df = df.with_columns(
                pl.when(pl.col("parameter").is_in(["cglo", "chim"]))
                .then(pl.col("value") * 600 / 10000)
                .otherwise(pl.col("value"))
                .alias("value"),
            )
        elif parameter_or_dataset.resolution.value == Resolution.HOURLY:
            df = df.with_columns(
                pl.when(pl.col("parameter").eq("cglo"))
                .then(pl.col("value") * 3600 / 10000)
                .otherwise(pl.col("value"))
                .alias("value"),
            )
        return df.with_columns(
            pl.col("date").str.to_datetime("%Y-%m-%dT%H:%M+%Z").dt.replace_time_zone("UTC"),
            pl.col("parameter").str.to_lowercase(),
            pl.lit(station_id).alias("station_id"),
            pl.lit(None, pl.Float64).alias("quality"),
        )


class GeosphereObservationRequest(TimeseriesRequest):
    """Request class for geosphere observation data."""

    metadata = GeosphereObservationMetadata
    _values = GeosphereObservationValues

    _endpoint = "https://dataset.api.hub.zamg.ac.at/v1/station/historical/{dataset}/metadata/stations"

    def __init__(
        self,
        parameters: _PARAMETER_TYPE,
        start_date: _DATETIME_TYPE = None,
        end_date: _DATETIME_TYPE = None,
        settings: _SETTINGS_TYPE = None,
    ) -> None:
        """Initialize the GeosphereObservationRequest class.

        Args:
            parameters: requested parameters
            start_date: start date of the requested data
            end_date: end date of the requested data
            settings: settings for the request

        """
        super().__init__(
            parameters=parameters,
            start_date=start_date,
            end_date=end_date,
            settings=settings,
        )

    def _all(self) -> pl.LazyFrame:
        dataset = self.parameters[0].dataset
        url = self._endpoint.format(dataset=dataset.name_original)
        log.info(f"Downloading file {url}.")
        response = download_file(url=url, settings=self.settings, ttl=CacheExpiry.METAINDEX)
        df = pl.read_csv(response).lazy()
        df = df.drop("Sonnenschein", "Globalstrahlung")
        df = df.rename(
            mapping={
                "id": "station_id",
                "Stationsname": "name",
                "Länge [°E]": "longitude",
                "Breite [°N]": "latitude",
                "Höhe [m]": "height",
                "Startdatum": "start_date",
                "Enddatum": "end_date",
                "Bundesland": "state",
            },
        )
        return df.with_columns(
            pl.col("start_date").str.to_datetime(),
            pl.col("end_date").str.to_datetime(),
        )
