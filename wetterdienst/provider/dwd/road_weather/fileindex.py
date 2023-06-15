# -*- coding: utf-8 -*-
# Copyright (c) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from functools import reduce
from urllib.parse import urljoin

import pandas as pd

from wetterdienst.provider.dwd.index import _list_remote_files_as_dataframe
from wetterdienst.provider.dwd.metadata.constants import (
    DWD_ROAD_WEATHER_REPORTS,
    DWD_SERVER,
)
from wetterdienst.provider.dwd.road_weather.metadata.station_groups import (
    DwdObservationRoadWeatherStationGroups,
)


def create_file_index_for_dwd_road_weather_station(
    road_weather_station_group: DwdObservationRoadWeatherStationGroups,
) -> pd.DataFrame:
    """
    Creates a file_index DataFrame from RoadWeather Station directory
    """
    return _list_remote_files_as_dataframe(
        reduce(
            urljoin,
            [DWD_SERVER, DWD_ROAD_WEATHER_REPORTS, road_weather_station_group.value],
        )
    )
