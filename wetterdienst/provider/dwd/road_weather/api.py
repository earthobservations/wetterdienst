# -*- coding: utf-8 -*-
# Copyright (c) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import logging
from typing import Dict, List

import numpy as np
import pandas as pd

from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.provider.dwd.road_weather.download import (
    download_road_weather_observations_parallel,
)
from wetterdienst.provider.dwd.road_weather.fileindex import (
    create_file_index_for_dwd_road_weather_station,
)
from wetterdienst.provider.dwd.road_weather.metadata.dataset import (
    DwdObservationRoadWeatherDataset,
)
from wetterdienst.provider.dwd.road_weather.metadata.period import (
    DwdRoadWeatherObservationPeriod,
)
from wetterdienst.provider.dwd.road_weather.metadata.station_groups import (
    DwdObservationRoadWeatherStationGroups,
)
from wetterdienst.provider.dwd.road_weather.metaindex import (
    create_meta_index_for_road_weather,
)
from wetterdienst.provider.dwd.road_weather.parser import parse_dwd_road_weather_data
from wetterdienst.util.geo import Coordinates, derive_nearest_neighbours

log = logging.getLogger(__name__)


class DwdRoadWeatherObservationValues:
    """
    The DwdRoadWeatherObservationValues class represents a request for
    observation data from road weather stations as provided by the DWD service.
    """

    def __init__(
        self,
        period: DwdRoadWeatherObservationPeriod = DwdRoadWeatherObservationPeriod.LATEST,
    ):
        self._tz = Timezone.GERMANY
        self._data_tz = Timezone.UTC
        self.period = period

        self.metaindex = create_meta_index_for_road_weather()

        # actually new stations with group id XX are not available
        self.metaindex = self.metaindex[self.metaindex[Columns.STATION_GROUP.value] != "XX"]

    def __eq__(self, other):
        """Add resolution and periods"""
        return super(DwdRoadWeatherObservationValues, self).__eq__(other)

    def _collect_data_by_rank(
        self,
        latitude: float,
        longitude: float,
        rank: int = 1,
    ) -> pd.DataFrame:
        """
        Takes coordinates and derives the closest stations to the given location.
        These locations define the required Station Groups to download and parse the data
        """
        distances, indices_nearest_neighbours = derive_nearest_neighbours(
            self.metaindex[Columns.LATITUDE.value].values,
            self.metaindex[Columns.LONGITUDE.value].values,
            Coordinates(np.array([latitude]), np.array([longitude])),
            rank,
        )

        self.metaindex = self.metaindex.iloc[indices_nearest_neighbours.ravel(), :]

        required_station_groups = [
            DwdObservationRoadWeatherStationGroups(grp) for grp in self.metaindex[Columns.STATION_GROUP.value].unique()
        ]

        _dat = [
            self._collect_data_by_station_group(road_weather_station_group)
            for road_weather_station_group in required_station_groups
        ]
        road_weather_station_data = pd.concat(
            _dat,
        )

        return road_weather_station_data[
            road_weather_station_data.index.get_level_values("shortStationName").isin(
                self.metaindex[Columns.STATION_ID.value].tolist()
            )
        ]

    def _collect_data_by_station_name(self, station_name: str) -> pd.DataFrame:
        """Takes station_name to download and parse RoadWeather Station data"""
        self.metaindex = self.metaindex.loc[self.metaindex[Columns.NAME.value] == station_name, :]

        required_station_groups = [
            DwdObservationRoadWeatherStationGroups(grp)
            for grp in self.metaindex.loc[:, Columns.STATION_GROUP.value].drop_duplicates()
        ]

        road_weather_station_data = pd.concat(
            [
                self._collect_data_by_station_group(road_weather_station_group)
                for road_weather_station_group in required_station_groups
            ],
        )

        return road_weather_station_data[
            road_weather_station_data.index.get_level_values("shortStationName").isin(
                self.metaindex[Columns.STATION_ID.value].tolist()
            )
        ]

    def _collect_data_by_station_group(
        self,
        road_weather_station_group: DwdObservationRoadWeatherStationGroups,
    ) -> pd.DataFrame:
        """
        Method to collect data for one specified parameter. Manages restoring,
        collection and storing of data, transformation and combination of different
        periods.

        Args:
            road_weather_station_group: subset id for which parameter is collected

        Returns:
            pandas.DataFrame for given parameter of station
        """
        remote_files = create_file_index_for_dwd_road_weather_station(road_weather_station_group)

        if self.period != DwdRoadWeatherObservationPeriod.LATEST:
            raise NotImplementedError("Actually only latest as period type is supported")
        else:
            filenames_and_files = download_road_weather_observations_parallel([remote_files.iloc[-1, 0]])

        return parse_dwd_road_weather_data(filenames_and_files)

    def _coerce_dates(self, data: pd.DataFrame) -> pd.DataFrame:
        """Use predefined datetime format for given resolution to reduce processing
        time."""
        return

    def _coerce_all_dataframes(self, data: Dict[str, pd.DataFrame]) -> pd.DataFrame:
        """Summarize all dataframes into one general dict"""
        return

    def _create_humanized_parameters_mapping(self) -> Dict[str, str]:
        """Reduce the creation of parameter mapping of the massive amount of parameters
        by specifying the resolution."""
        return

    def _all(self):
        """
        returns stations dataframe

        """
        return self.metaindex

    def _select_required_parameters(
        self,
        data: pd.DataFrame,
        parameters: List[DwdObservationRoadWeatherDataset],
    ) -> pd.DataFrame:
        """This does not work at the moment"""
        return data.loc[:, [param.value for param in parameters]]
