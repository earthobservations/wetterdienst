# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Eaufrance Hubeau API."""

from __future__ import annotations

import datetime as dt
import json
import logging
import math
from itertools import pairwise
from typing import TYPE_CHECKING, Literal
from zoneinfo import ZoneInfo

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

if TYPE_CHECKING:
    from collections.abc import Iterator


log = logging.getLogger(__name__)

REQUIRED_ENTRIES = [
    "code_station",
    "libelle_station",
    "longitude_station",
    "latitude_station",
    "altitude_ref_alti_station",
    "libelle_departement",
    "date_ouverture_station",
    "date_fermeture_station",
]


HubeauMetadata = {
    "name_short": "Eaufrance",
    "name_english": "Eaufrance",
    "name_local": "Eaufrance",
    "country": "France",
    "copyright": "© Eaufrance",
    "url": "https://www.eaufrance.fr/",
    "kind": "observation",
    "timezone": "Europe/Paris",
    "timezone_data": "dynamic",
    "resolutions": [
        {
            "name": "dynamic",
            "name_original": "dynamic",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": False,
                    "parameters": [
                        {
                            "name": "discharge",
                            "name_original": "Q",
                            "unit_type": "volume_per_time",
                            "unit": "liter_per_second",
                        },
                        {
                            "name": "stage",
                            "name_original": "H",
                            "unit_type": "length_short",
                            "unit": "millimeter",
                        },
                    ],
                },
            ],
        },
    ],
}
HubeauMetadata = build_metadata_model(HubeauMetadata, "HubeauMetadata")


class HubeauValues(TimeseriesValues):
    """Values class for Eaufrance Hubeau data."""

    _endpoint = (
        "https://hubeau.eaufrance.fr/api/v1/hydrometrie/observations_tr?code_entite={station_id}"
        "&grandeur_hydro={grandeur_hydro}&sort=asc&date_debut_obs={start_date}&date_fin_obs={end_date}"
    )
    _endpoint_freq = (
        "https://hubeau.eaufrance.fr/api/v1/hydrometrie/observations_tr?code_entite={station_id}&"
        "grandeur_hydro={grandeur_hydro}&sort=asc&size=2"
    )

    def _get_hubeau_dates(
        self,
        station_id: str,
        parameter: ParameterModel,
    ) -> Iterator[tuple[dt.datetime, dt.datetime]]:
        """Get the dates for the Hubeau API request."""
        freq, freq_unit = self._get_dynamic_frequency(station_id, parameter)
        end = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None)
        start = end - dt.timedelta(days=30)
        delta = end - start
        if freq_unit == "m":
            data_delta = dt.timedelta(minutes=freq)
        elif freq_unit == "H":
            data_delta = dt.timedelta(hours=freq)
        else:
            msg = f"Unknown frequency unit {freq_unit}"
            raise KeyError(msg)
        n_dates = delta / data_delta
        periods = math.ceil(n_dates / 1000)
        request_date_range = pl.datetime_range(start=start, end=end, interval=delta / periods, eager=True)
        return pairwise(request_date_range)

    def _get_dynamic_frequency(
        self,
        station_id: str,
        parameter: ParameterModel,
    ) -> tuple[int, Literal["m", "H"]]:
        url = self._endpoint_freq.format(station_id=station_id, grandeur_hydro=parameter.name_original)
        log.info(f"Downloading file {url}.")
        response = download_file(url=url, settings=self.sr.stations.settings, ttl=CacheExpiry.METAINDEX)
        values_dict = json.load(response)["data"]
        try:
            second_date = values_dict[1]["date_obs"]
            first_date = values_dict[0]["date_obs"]
        except IndexError:
            return 1, "H"
        date_diff = dt.datetime.fromisoformat(second_date) - dt.datetime.fromisoformat(first_date)
        minutes = int(date_diff.seconds / 60)
        return minutes, "m"

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel,
    ) -> pl.DataFrame:
        """Collect data from Hubeau API.

        Requests are limited to 1000 units so eventually multiple requests have to be sent to get all data.
        """
        data = []
        for start_date, end_date in self._get_hubeau_dates(station_id=station_id, parameter=parameter_or_dataset):
            url = self._endpoint.format(
                station_id=station_id,
                grandeur_hydro=parameter_or_dataset.name_original,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
            )
            log.info(f"Downloading file {url}.")
            response = download_file(url=url, settings=self.sr.stations.settings)
            data_dict = json.load(response)["data"]
            df = pl.DataFrame(data_dict, orient="row")
            data.append(df)

        try:
            df = pl.concat(data)
        except ValueError:
            df = pl.DataFrame(
                schema={
                    Columns.STATION_ID.value: pl.String,
                    Columns.DATE.value: pl.Datetime(time_zone="UTC"),
                    Columns.VALUE.value: pl.Float64,
                    Columns.QUALITY.value: pl.Float64,
                },
            )
        else:
            df = df.with_columns(pl.col("date_obs").map_elements(dt.datetime.fromisoformat, return_dtype=pl.Datetime))
            df = df.with_columns(pl.col("date_obs").dt.replace_time_zone("UTC"))

        df = df.with_columns(pl.lit(parameter_or_dataset.name_original.lower()).alias(Columns.PARAMETER.value))

        df = df.rename(
            mapping={
                "code_station": Columns.STATION_ID.value,
                "date_obs": Columns.DATE.value,
                "resultat_obs": Columns.VALUE.value,
                "code_qualification_obs": Columns.QUALITY.value,
            },
        )

        return df.select(
            pl.col(Columns.STATION_ID.value),
            pl.col(Columns.PARAMETER.value),
            pl.col(Columns.DATE.value),
            pl.col(Columns.VALUE.value),
            pl.col(Columns.QUALITY.value),
        )


class HubeauRequest(TimeseriesRequest):
    """Request class for Eaufrance Hubeau data."""

    metadata = HubeauMetadata
    _values = HubeauValues

    _endpoint = "https://hubeau.eaufrance.fr/api/v1/hydrometrie/referentiel/stations?format=json&en_service=true"

    def __init__(
        self,
        parameters: _PARAMETER_TYPE,
        start_date: _DATETIME_TYPE = None,
        end_date: _DATETIME_TYPE = None,
        settings: _SETTINGS_TYPE = None,
    ) -> None:
        """Initialize the HubeauRequest class.

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
        """:return:"""
        log.info(f"Downloading file {self._endpoint}.")
        response = download_file(url=self._endpoint, settings=self.settings, ttl=CacheExpiry.METAINDEX)
        data = json.load(response)["data"]
        for entry in data:
            keys = list(entry.keys())
            for key in keys:
                if key not in REQUIRED_ENTRIES:
                    entry.pop(key)

        df = pl.LazyFrame(data)

        df = df.rename(
            mapping={
                "code_station": Columns.STATION_ID.value,
                "libelle_station": Columns.NAME.value,
                "longitude_station": Columns.LONGITUDE.value,
                "latitude_station": Columns.LATITUDE.value,
                "altitude_ref_alti_station": Columns.HEIGHT.value,
                "libelle_departement": Columns.STATE.value,
                "date_ouverture_station": Columns.START_DATE.value,
                "date_fermeture_station": Columns.END_DATE.value,
            },
        )

        df = df.with_columns(
            pl.col(Columns.START_DATE.value).map_elements(dt.datetime.fromisoformat, return_dtype=pl.Datetime),
            pl.when(pl.col(Columns.END_DATE.value).is_null())
            .then(dt.datetime.now(ZoneInfo("UTC")).date())
            .alias(Columns.END_DATE.value)
            .cast(pl.Datetime),
        )

        return df.filter(
            pl.col(Columns.STATION_ID.value)
            .str.slice(offset=0, length=1)
            .map_elements(str.isalpha, return_dtype=pl.Boolean),
        )
