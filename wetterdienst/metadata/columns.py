# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum


class Columns(Enum):
    """ Overhauled column names for metadata fields """

    # TODO: remove columns which are only used in context of data wrangling of one of
    #  the weather services e.g. EOR or FILENAME
    STATION_ID = "STATION_ID"  # change to local id later
    DATE = "DATE"
    FROM_DATE = "FROM_DATE"
    TO_DATE = "TO_DATE"
    HEIGHT = "HEIGHT"
    LATITUDE = "LATITUDE"
    LONGITUDE = "LONGITUDE"
    STATION_NAME = "STATION_NAME"
    STATE = "STATE"
    EOR = "EOR"
    # Extra column names
    FILENAME = "FILENAME"
    HAS_FILE = "HAS_FILE"
    FILEID = "FILEID"
    DATE_RANGE = "DATE_RANGE"
    INTERVAL = "INTERVAL"
    # Columns used for tidy data
    # Column for quality
    PARAMETER = "PARAMETER"
    PARAMETER_SET = "PARAMETER_SET"
    VALUE = "VALUE"
    QUALITY = "QUALITY"
    # Columns used for RADOLAN
    PERIOD_TYPE = "PERIOD_TYPE"
    DATETIME = "DATETIME"
    # Column for distance used by get_nearby_stations_...
    DISTANCE_TO_LOCATION = "DISTANCE_TO_LOCATION"
    # For mosmix
    WMO_ID = "WMO_ID"
    ICAO_ID = "ICAO_ID"
