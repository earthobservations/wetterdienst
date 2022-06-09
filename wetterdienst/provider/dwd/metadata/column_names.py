# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum


class DwdOrigColumns(Enum):
    """Original meta column names from DWD data"""

    STATION_ID = "stations_id"
    DATE = "mess_datum"
    FROM_DATE = "von_datum"
    TO_DATE = "bis_datum"
    FROM_DATE_ALTERNATIVE = "mess_datum_beginn"
    TO_DATE_ALTERNATIVE = "mess_datum_ende"
    STATION_HEIGHT = "stationshoehe"
    LATITUDE = "geobreite"
    LATITUDE_ALTERNATIVE = "geogr.breite"
    LONGITUDE = "geolaenge"
    LONGITUDE_ALTERNATIVE = "geogr.laenge"
    STATION_NAME = "stationsname"
    STATE = "bundesland"


class DwdColumns(Enum):
    """Overhauled column names for metadata fields"""

    STATION_ID = "station_id"  # change to local id later
    DATE = "date"
    FROM_DATE = "from_date"
    TO_DATE = "to_date"
    STATION_HEIGHT = "station_height"
    LATITUDE = "lat"
    LONGITUDE = "lon"
    NAME = "name"
    STATE = "state"
    EOR = "eor"
    # Extra column names
    FILENAME = "filename"
    HAS_FILE = "has_file"
    FILEID = "fileid"
    DATE_RANGE = "date_range"
    INTERVAL = "interval"
    # Columns used for tidy data
    # Column for quality
    DATASET = "dataset"
    PARAMETER = "parameter"
    VALUE = "value"
    QUALITY = "quality"
    # Columns used for RADOLAN
    PERIOD_TYPE = "period_type"
    DATETIME = "datetime"
    # Column for distance used by get_nearby_stations_...
    DISTANCE_TO_LOCATION = "distance_to_location"
    # For mosmix
    WMO_ID = "wmo_id"
    ICAO_ID = "icao_id"
