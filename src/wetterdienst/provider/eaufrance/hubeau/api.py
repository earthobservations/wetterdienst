# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Eaufrance Hubeau API."""

from __future__ import annotations

import datetime as dt
import json
import logging
import math
from dataclasses import dataclass
from itertools import pairwise
from typing import TYPE_CHECKING, Literal
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import (
    DATASET_NAME_DEFAULT,
    ParameterModel,
    build_metadata_model,
)
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
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
        "https://hubeau.eaufrance.fr/api/v2/hydrometrie/observations_tr?code_entite={station_id}"
        "&grandeur_hydro={grandeur_hydro}&sort=asc&date_debut_obs={start_date}&date_fin_obs={end_date}"
    )
    _endpoint_freq = (
        "https://hubeau.eaufrance.fr/api/v2/hydrometrie/observations_tr?code_entite={station_id}&"
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
        file = download_file(
            url=url,
            cache_dir=self.sr.stations.settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=self.sr.stations.settings.fsspec_client_kwargs,
            cache_disable=self.sr.stations.settings.cache_disable,
        )
        file.raise_if_exception()
        values_dict = json.load(file.content)["data"]
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
            file = download_file(
                url=url,
                cache_dir=self.sr.stations.settings.cache_dir,
                ttl=CacheExpiry.FIVE_MINUTES,
                client_kwargs=self.sr.stations.settings.fsspec_client_kwargs,
                cache_disable=self.sr.stations.settings.cache_disable,
            )
            file.raise_if_exception()
            df = pl.read_json(
                file.content,
                schema={
                    "data": pl.List(
                        pl.Struct(
                            {
                                "code_station": pl.String,
                                "date_obs": pl.String,
                                "resultat_obs": pl.Float64,
                                "code_qualification_obs": pl.Float64,
                            },
                        ),
                    ),
                },
            )
            df = df.explode("data")
            df = df.select(pl.col("data").struct.unnest())
            data.append(df)
        try:
            df = pl.concat(data)
        except ValueError:
            return pl.DataFrame()
        df = df.rename(
            mapping={
                "code_station": "station_id",
                "date_obs": "date",
                "resultat_obs": "value",
                "code_qualification_obs": "quality",
            },
        )
        return df.select(
            pl.lit(parameter_or_dataset.dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(parameter_or_dataset.dataset.name, dtype=pl.String).alias("dataset"),
            pl.lit(parameter_or_dataset.name_original.lower()).alias("parameter"),
            "station_id",
            pl.col("date").str.to_datetime(format="%Y-%m-%dT%H:%M:%SZ").dt.replace_time_zone("UTC"),
            "value",
            "quality",
        )


@dataclass
class HubeauRequest(TimeseriesRequest):
    """Request class for Eaufrance Hubeau data."""

    metadata = HubeauMetadata
    _values = HubeauValues

    _endpoint = "https://hubeau.eaufrance.fr/api/v2/hydrometrie/referentiel/stations?format=json&en_service=true"

    def _all(self) -> pl.LazyFrame:
        """:return:"""
        file = download_file(
            url=self._endpoint,
            cache_dir=self.settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=self.settings.fsspec_client_kwargs,
            cache_disable=self.settings.cache_disable,
        )
        file.raise_if_exception()
        df_raw = pl.read_json(
            file.content,
            schema={
                "data": pl.List(
                    pl.Struct(
                        {
                            "code_station": pl.String,
                            "libelle_station": pl.String,
                            "longitude_station": pl.Float64,
                            "latitude_station": pl.Float64,
                            "altitude_ref_alti_station": pl.Float64,
                            "libelle_departement": pl.String,
                            "date_ouverture_station": pl.String,
                            "date_fermeture_station": pl.String,
                        },
                    ),
                ),
            },
        )
        df_raw = df_raw.explode("data")
        df_raw = df_raw.with_columns(pl.col("data").struct.unnest())
        df_raw = df_raw.rename(
            mapping={
                "code_station": "station_id",
                "libelle_station": "name",
                "longitude_station": "longitude",
                "latitude_station": "latitude",
                "altitude_ref_alti_station": "height",
                "libelle_departement": "state",
                "date_ouverture_station": "start_date",
                "date_fermeture_station": "end_date",
            },
        )
        df_raw = df_raw.with_columns(
            pl.col("start_date").str.to_datetime(time_zone="UTC"),
            pl.when(pl.col("end_date").is_null())
            .then(dt.datetime.now(ZoneInfo("UTC")))
            .otherwise(pl.col("end_date").str.to_datetime(time_zone="UTC"))
            .alias("end_date"),
        )
        df_raw = df_raw.filter(
            pl.col("station_id").str.slice(offset=0, length=1).map_elements(str.isalpha, return_dtype=pl.Boolean),
        )
        # combinations of resolution and dataset
        resolutions_and_datasets = {
            (parameter.dataset.resolution.name, parameter.dataset.name) for parameter in self.parameters
        }
        data = []
        # for each combination of resolution and dataset create a new DataFrame with the columns
        for resolution, dataset in resolutions_and_datasets:
            data.append(
                df_raw.with_columns(
                    pl.lit(resolution, pl.String).alias("resolution"),
                    pl.lit(dataset, pl.String).alias("dataset"),
                ),
            )
        df = pl.concat(data)
        df = df.select(self._base_columns)
        return df.lazy()
