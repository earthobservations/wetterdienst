# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum


class Columns(Enum):
    """Overhauled column names for metadata fields"""

    # TODO: remove columns which are only used in context of data wrangling of one of
    #  the weather services e.g. EOR or FILENAME
    STATION_ID = "station_id"  # change to local id later
    DATE = "date"
    FROM_DATE = "from_date"
    TO_DATE = "to_date"
    HEIGHT = "height"
    LATITUDE = "latitude"
    LONGITUDE = "longitude"
    NAME = "name"
    COUNTY = "county"
    STATE = "state"
    EOR = "eor"
    # Extra column names
    FILENAME = "filename"
    HAS_FILE = "has_file"
    FILEID = "fileid"
    DATE_RANGE = "date_range"
    INTERVAL = "interval"
    # Columns used for tidy data
    PARAMETER = "parameter"
    DATASET = "dataset"
    VALUE = "value"
    # Columns for quality
    QUALITY = "quality"
    # Columns used for RADOLAN
    PERIOD_TYPE = "period_type"
    DATETIME = "datetime"
    # Column for distance used by self.nearby_radius...
    DISTANCE = "distance"
    # For mosmix
    WMO_ID = "wmo_id"
    ICAO_ID = "icao_id"
    # Special columns
    QUALITY_PREFIX = "qn"
    # Columns used for interpolation
    DISTANCE_MEAN = "distance_mean"
    STATION_IDS = "station_ids"
