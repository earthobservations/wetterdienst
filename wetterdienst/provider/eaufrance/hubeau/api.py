# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import json
import math
from enum import Enum
from typing import Tuple

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


class HubeauResolution(Enum):
    DYNAMIC = Resolution.DYNAMIC.value


class HubeauPeriod(Enum):
    HISTORICAL = Period.HISTORICAL.value


class HubeauParameter(DatasetTreeCore):
    class DYNAMIC(Enum):
        FLOW = "Q"
        STAGE = "H"


class HubeauUnit(DatasetTreeCore):
    class DYNAMIC(Enum):
        FLOW = OriginUnit.LITERS_PER_SECOND.value, SIUnit.CUBIC_METERS_PER_SECOND.value
        STAGE = OriginUnit.MILLIMETER.value, SIUnit.METER.value


class HubeauValues(ScalarValuesCore):
    _string_parameters = ()
    _irregular_parameters = ()
    _date_parameters = ()

    _data_tz = Timezone.DYNAMIC

    _endpoint = (
        "https://hubeau.eaufrance.fr/api/v1/hydrometrie/observations_tr?code_entite={station_id}"
        "&grandeur_hydro={grandeur_hydro}&sort=asc&date_debut_obs={start_date}&date_fin_obs={end_date}"
    )
    _endpoint_freq = (
        "https://hubeau.eaufrance.fr/api/v1/hydrometrie/observations_tr?code_entite={station_id}&"
        "grandeur_hydro={grandeur_hydro}&sort=asc&size=2"
    )

    @staticmethod
    def _get_hubeau_dates() -> Tuple[pd.Timestamp, pd.Timestamp]:
        """
        Method to get the Hubeau interval, which is roughly today - 30 days. We'll add another day on
        each end as buffer.
        :return:
        """
        end = pd.Timestamp.utcnow()
        start = end - pd.Timedelta(days=30)
        start = start.normalize()
        return start, end

    def fetch_dynamic_frequency(self, station_id, parameter, dataset):
        url = self._endpoint_freq.format(station_id=station_id, grandeur_hydro=parameter.value)
        response = download_file(url)
        values_dict = json.load(response)["data"]

        try:
            second_date = values_dict[1]["date_obs"]
            first_date = values_dict[0]["date_obs"]
        except IndexError:
            return "1H"

        date_diff = pd.to_datetime(second_date) - pd.to_datetime(first_date)

        minutes = int(date_diff.seconds / 60)

        return f"{minutes}min"

    def _collect_station_parameter(self, station_id: str, parameter: Enum, dataset: Enum) -> pd.DataFrame:
        """
        Method to collect data from Eaufrance Hubeau service. Requests are limited to 1000 units so eventually
        multiple requests have to be sent to get all data.

        :param station_id:
        :param parameter:
        :param dataset:
        :return:
        """
        hubeau_start, hubeau_end = self._get_hubeau_dates()
        freq = self.fetch_dynamic_frequency(station_id, parameter, dataset)
        required_date_range = pd.date_range(start=hubeau_start, end=hubeau_end, freq=freq, inclusive="both")
        periods = math.ceil(len(required_date_range) / 1000)
        request_date_range = pd.date_range(hubeau_start, hubeau_end, periods=periods)

        data = []
        for start_date, end_date in zip(request_date_range[:-1], request_date_range[1:]):
            url = self._endpoint.format(
                station_id=station_id,
                grandeur_hydro=parameter.value,
                start_date=start_date.isoformat(),
                end_date=end_date.isoformat(),
            )
            response = download_file(url)
            values_dict = json.load(response)["data"]

            df = pd.DataFrame.from_records(values_dict)

            data.append(df)

        try:
            df = pd.concat(data)
        except ValueError:
            df = pd.DataFrame(
                columns=[
                    Columns.STATION_ID.value,
                    Columns.DATE.value,
                    Columns.VALUE.value,
                    Columns.QUALITY.value,
                ]
            )

        return df.rename(
            columns={
                "code_station": Columns.STATION_ID.value,
                "date_obs": Columns.DATE.value,
                "resultat_obs": Columns.VALUE.value,
                "code_qualification_obs": Columns.QUALITY.value,
            }
        ).loc[
            :,
            [
                Columns.STATION_ID.value,
                Columns.DATE.value,
                Columns.VALUE.value,
                Columns.QUALITY.value,
            ],
        ]


class HubeauRequest(ScalarRequestCore):
    _values = HubeauValues

    _unit_tree = HubeauUnit

    _tz = Timezone.FRANCE

    _parameter_base = HubeauParameter

    _has_tidy_data = True
    _has_datasets = False

    _data_range = DataRange.FIXED

    _period_base = Period.HISTORICAL

    _resolution_type = ResolutionType.DYNAMIC
    _resolution_base = HubeauResolution

    _period_type = PeriodType.FIXED

    provider = Provider.EAUFRANCE
    kind = Kind.OBSERVATION

    _endpoint = "https://hubeau.eaufrance.fr/api/v1/hydrometrie/referentiel/stations?format=json&en_service=true"

    def __init__(self, parameter, start_date=None, end_date=None):
        super(HubeauRequest, self).__init__(
            parameter=parameter,
            resolution=Resolution.DYNAMIC,
            period=Period.HISTORICAL,
            start_date=start_date,
            end_date=end_date,
        )

    def _all(self) -> pd.DataFrame:
        """

        :return:
        """
        response = download_file(self._endpoint, CacheExpiry.METAINDEX)
        stations_dict = json.load(response)["data"]
        df = pd.DataFrame.from_records(stations_dict)

        df = df.rename(
            columns={
                "code_station": Columns.STATION_ID.value,
                "libelle_station": Columns.NAME.value,
                "longitude_station": Columns.LONGITUDE.value,
                "latitude_station": Columns.LATITUDE.value,
                "altitude_ref_alti_station": Columns.HEIGHT.value,
                "libelle_departement": Columns.STATE.value,
                "date_ouverture_station": Columns.FROM_DATE.value,
                "date_fermeture_station": Columns.TO_DATE.value,
            }
        )

        return df.loc[df[Columns.STATION_ID.value].str[0].str.isalpha(), :]
