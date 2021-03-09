# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum

DWD_SERVER = "https://opendata.dwd.de"
DWD_CDC_PATH = "climate_environment/CDC/"

DWD_MOSMIX_S_PATH = "weather/local_forecasts/mos/MOSMIX_S/all_stations/kml/"
DWD_MOSMIX_L_PATH = "weather/local_forecasts/mos/MOSMIX_L/all_stations/kml/"
DWD_MOSMIX_L_SINGLE_PATH = "weather/local_forecasts/mos/MOSMIX_L/single_stations/"


class DWDCDCBase(Enum):
    CLIMATE_OBSERVATIONS = "observations_germany/climate/"


DWD_FOLDER_MAIN = "./dwd_data"
DWD_FOLDER_STATION_DATA = "station_data"
DWD_FILE_STATION_DATA = "dwd_station_data"
STATION_ID_REGEX = r"(?<!\d)\d{5}(?!\d)"
DATE_RANGE_REGEX = r"(?<!\d)\d{8}_\d{8}(?!\d)"
NA_STRING = "-999"
STATION_DATA_SEP = ";"
