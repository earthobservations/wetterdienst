# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import logging
import pandas as pd
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Union

from wetterdienst.metadata.timezone import Timezone
from wetterdienst.provider.dwd.road_weather.download import download_road_weather_observations_parallel
from wetterdienst.provider.dwd.road_weather.fileindex import create_file_index_for_dwd_road_weather_station
from wetterdienst.provider.dwd.road_weather.metadata.dataset import DwdObservationRoadWeatherDataset
from wetterdienst.provider.dwd.road_weather.metadata.period import DwdRoadWeatherObservationPeriod
from wetterdienst.provider.dwd.road_weather.metadata.stations import DwdObservationRoadWeatherStationGroups
from wetterdienst.provider.dwd.road_weather.parser import parse_dwd_road_weather_data

log = logging.getLogger(__name__)


class DwdRoadWeatherObservationValues:
    """
    The DwdRoadWeatherObservationValues class represents a request for
    observation data from road weather stations as provided by the DWD service.
    """

    def __init__(self, period: DwdRoadWeatherObservationPeriod = DwdRoadWeatherObservationPeriod.LATEST):
        self._tz = Timezone.GERMANY
        self._data_tz = Timezone.UTC
        self.period = period

    def __eq__(self, other):
        """ Add resolution and periods """
        return super(DwdRoadWeatherObservationValues, self).__eq__(other)

    def _collect_data_for_station_group(
            self,
            road_weather_station_group: DwdObservationRoadWeatherStationGroups,
    ) -> Tuple[List[Dict[str, pd.DataFrame]], pd.DataFrame]:
        """
        Method to collect data for one specified parameter. Manages restoring,
        collection and storing of data, transformation and combination of different
        periods.

        Args:
            road_weather_station_group: subset id for which parameter is collected

        Returns:
            pandas.DataFrame for given parameter of station
        """
        remote_files = create_file_index_for_dwd_road_weather_station(
            road_weather_station_group
        )

        if self.period == DwdRoadWeatherObservationPeriod.LATEST:
            filenames_and_files = download_road_weather_observations_parallel(
                [remote_files.iloc[-1, 0]]
            )

        return parse_dwd_road_weather_data(
            filenames_and_files
        )

    def _coerce_dates(self, data: pd.DataFrame) -> pd.DataFrame:
        """Use predefined datetime format for given resolution to reduce processing
        time."""
        return None

    def _coerce_all_dataframes(self, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """ Summarize all dataframes into one general dict """
        return None

    def _create_humanized_parameters_mapping(self) -> Dict[str, str]:
        """Reduce the creation of parameter mapping of the massive amount of parameters
        by specifying the resolution."""
        return None

    def _select_required_parameters(
            self,
            data: pd.DataFrame,
            parameters: List[DwdObservationRoadWeatherDataset],
    ) -> pd.DataFrame:
        """ This does not work at the moment """
        return data.loc[:, [param.value for param in parameters]]


data, metadata = DwdRoadWeatherObservationValues()._collect_data_for_station_group(
    DwdObservationRoadWeatherStationGroups.KK)
from IPython import embed

embed()
