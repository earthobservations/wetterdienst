# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import pandas as pd
from functools import reduce
from typing import List, Optional
from urllib.parse import urljoin, urlparse

from wetterdienst.metadata.extension import Extension
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.index import _create_file_index_for_dwd_server, _list_remote_files_as_dataframe
from wetterdienst.provider.dwd.metadata.column_names import DwdColumns
from wetterdienst.provider.dwd.metadata.constants import (
    DATE_RANGE_REGEX,
    STATION_ID_REGEX,
    DWDCDCBase, DWD_SERVER, DWD_ROAD_WEATHER_REPORTS,
)
from wetterdienst.provider.dwd.metadata.datetime import DatetimeFormat
from wetterdienst.provider.dwd.observation.metadata.dataset import DwdObservationDataset
from wetterdienst.provider.dwd.observation.metadata.resolution import HIGH_RESOLUTIONS
from wetterdienst.provider.dwd.road_weather.metadata.stations import DwdObservationRoadWeatherStationGroups
from wetterdienst.util.cache import fileindex_cache_twelve_hours


def create_file_index_for_dwd_road_weather_station(
        road_weather_station_group: DwdObservationRoadWeatherStationGroups
) -> pd.DataFrame:
    """
    Creates a file_index DataFrame from RoadWeather Station directory
    """
    return _list_remote_files_as_dataframe(
        reduce(
            urljoin,
            [DWD_SERVER, DWD_ROAD_WEATHER_REPORTS, road_weather_station_group.value]
        )
    )
