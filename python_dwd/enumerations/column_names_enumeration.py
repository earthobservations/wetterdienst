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

    # Daily climate summary
    FX = "FX"
    FM = "FM"
    RSK = "RSK"
    RSKF = "RSKF"
    SDK = "SDK"
    SHK_TAG = "SHK_TAG"
    NM = "NM"
    VPM = "VPM"
    PM = "PM"
    TMK = "TMK"
    UPM = "UPM"
    TXK = "TXK"
    TNK = "TNK"
    TGK = "TGK"


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

    # Daily climate summary
    FX = "WIND_GUST_MAX"
    FM = "WIND_VELOCITY"
    RSK = "PRECIPITATION_HEIGHT"
    RSKF = "PRECIPITATION_FORM"
    SDK = "SUNSHINE_DURATION"
    SHK_TAG = "SNOW_DEPTH"
    NM = "CLOUD_COVER"
    VPM = "VAPOR_PRESSURE"
    PM = "PRESSURE"
    TMK = "TEMPERATURE"
    UPM = "HUMIDITY"
    TXK = "TEMPERATURE_MAX_200"
    TNK = "TEMPERATURE_MIN_200"
    TGK = "TEMPERATURE_MIN_005"
