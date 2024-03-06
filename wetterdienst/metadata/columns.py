# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum


class Columns(Enum):
    """Overhauled column names for metadata fields"""

    STATION_ID = "station_id"  # change to local id later
    DATE = "date"
    START_DATE = "start_date"
    END_DATE = "end_date"
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
    # Columns used for long data format
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
    # Columns used for interpolation/summary
    DISTANCE_MEAN = "distance_mean"
    TAKEN_STATION_IDS = "taken_station_ids"
    TAKEN_STATION_ID = "taken_station_id"
    # for road weather
    ROAD_NAME = "road_name"
    ROAD_TYPE = "road_type"
    ROAD_SURFACE_TYPE = "road_surface_type"
    STATION_GROUP = "station_group"
    ROAD_SECTOR = "road_sector"
    ROAD_SURROUNDINGS_TYPE = "road_surroundings_type"
