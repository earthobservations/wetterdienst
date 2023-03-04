# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import json
import math
from datetime import datetime
from enum import Enum
from typing import List, Optional, Tuple, Union

import pandas as pd

from wetterdienst.core.timeseries.request import TimeseriesRequest
from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.datarange import DataRange
from wetterdienst.metadata.kind import Kind
from wetterdienst.metadata.parameter import Parameter
from wetterdienst.metadata.period import Period, PeriodType
from wetterdienst.metadata.provider import Provider
from wetterdienst.metadata.resolution import Resolution, ResolutionType
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.metadata.unit import OriginUnit, SIUnit, UnitEnum
from wetterdienst.settings import Settings
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.network import download_file
from wetterdienst.util.parameter import DatasetTreeCore


class HubeauResolution(Enum):
    DYNAMIC = Resolution.DYNAMIC.value


class HubeauPeriod(Enum):
    HISTORICAL = Period.HISTORICAL.value


class HubeauParameter(DatasetTreeCore):
    class DYNAMIC(DatasetTreeCore):
        class DYNAMIC(Enum):
            FLOW = "Q"
            STAGE = "H"

        FLOW = DYNAMIC.FLOW
        STAGE = DYNAMIC.STAGE


class HubeauUnit(DatasetTreeCore):
    class DYNAMIC(DatasetTreeCore):
        class DYNAMIC(UnitEnum):
            FLOW = OriginUnit.LITERS_PER_SECOND.value, SIUnit.CUBIC_METERS_PER_SECOND.value
            STAGE = OriginUnit.MILLIMETER.value, SIUnit.METER.value


class HubeauValues(TimeseriesValues):
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
        response = download_file(url=url, settings=self.sr.stations.settings, ttl=CacheExpiry.METAINDEX)
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
            response = download_file(url=url, settings=self.sr.stations.settings)
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

        df[Columns.PARAMETER.value] = parameter.value.lower()

        df = df.rename(
            columns={
                "code_station": Columns.STATION_ID.value,
                "date_obs": Columns.DATE.value,
                "resultat_obs": Columns.VALUE.value,
                "code_qualification_obs": Columns.QUALITY.value,
            }
        )

        return df.loc[
            :,
            [
                Columns.STATION_ID.value,
                Columns.PARAMETER.value,
                Columns.DATE.value,
                Columns.VALUE.value,
                Columns.QUALITY.value,
            ],
        ]


class HubeauRequest(TimeseriesRequest):
    _provider = Provider.EAUFRANCE
    _kind = Kind.OBSERVATION
    _tz = Timezone.FRANCE
    _parameter_base = HubeauParameter
    _unit_base = HubeauUnit
    _resolution_type = ResolutionType.DYNAMIC
    _resolution_base = HubeauResolution
    _period_type = PeriodType.FIXED
    _period_base = Period.HISTORICAL
    _has_datasets = False
    _data_range = DataRange.FIXED
    _values = HubeauValues

    _endpoint = "https://hubeau.eaufrance.fr/api/v1/hydrometrie/referentiel/stations?format=json&en_service=true"

    def __init__(
        self,
        parameter: List[Union[str, Enum, Parameter]],
        start_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
        end_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
        settings: Optional[Settings] = None,
    ):
        super(HubeauRequest, self).__init__(
            parameter=parameter,
            resolution=Resolution.DYNAMIC,
            period=Period.HISTORICAL,
            start_date=start_date,
            end_date=end_date,
            settings=settings,
        )

    def _all(self) -> pd.DataFrame:
        """

        :return:
        """
        response = download_file(url=self._endpoint, settings=self.settings, ttl=CacheExpiry.METAINDEX)
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
