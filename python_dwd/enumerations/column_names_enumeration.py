"""
-*- coding: utf-8 -*-

Copyright (c) 2020, Benjamin Gutzmann, Aachen, Germany
All rights reserved.
Modification, redistribution and use in source and binary
forms, with or without modification, are not permitted
without prior written approval by the copyright holder.
"""
from enum import Enum


class DWDOrigColumns(Enum):
    """ Original column names from DWD data """
    STATION_ID = "STATIONS_ID"
    DATE = "MESS_DATUM"
    FROM_DATE = "VON_DATUM"
    TO_DATE = "BIS_DATUM"
    STATIONHEIGHT = "STATIONSHOEHE"
    LATITUDE = "GEOBREITE"
    LATITUDE_ALTERNATIVE = "GEOGR.BREITE"
    LONGITUDE = "GEOLAENGE"
    LONGITUDE_ALTERNATIVE = "GEOGR.LAENGE"
    STATIONNAME = "STATIONSNAME"
    STATE = "BUNDESLAND"


class DWDColumns(Enum):
    """ Overhauled column names for the library """
    STATION_ID = "STATION_ID"
    DATE = "DATE"
    FROM_DATE = "FROM_DATE"
    TO_DATE = "TO_DATE"
    STATIONHEIGHT = "STATIONHEIGHT"
    LATITUDE = "LAT"
    LONGITUDE = "LON"
    STATIONNAME = "STATIONNAME"
    STATE = "STATE"
    EOR = "EOR"
    # Extra column names
    FILENAME = "FILENAME"
    HAS_FILE = "HAS_FILE"
    FILEID = "FILEID"
