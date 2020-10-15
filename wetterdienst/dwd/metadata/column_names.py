from enum import Enum


class DWDOrigMetaColumns(Enum):
    """ Original meta column names from DWD data """

    STATION_ID = "STATIONS_ID"
    DATE = "MESS_DATUM"
    FROM_DATE = "VON_DATUM"
    TO_DATE = "BIS_DATUM"
    FROM_DATE_ALTERNATIVE = "MESS_DATUM_BEGINN"
    TO_DATE_ALTERNATIVE = "MESS_DATUM_ENDE"
    STATION_HEIGHT = "STATIONSHOEHE"
    LATITUDE = "GEOBREITE"
    LATITUDE_ALTERNATIVE = "GEOGR.BREITE"
    LONGITUDE = "GEOLAENGE"
    LONGITUDE_ALTERNATIVE = "GEOGR.LAENGE"
    STATION_NAME = "STATIONSNAME"
    STATE = "BUNDESLAND"


class DWDMetaColumns(Enum):
    """ Overhauled column names for metadata fields """

    STATION_ID = "STATION_ID"  # change to local id later
    DATE = "DATE"
    FROM_DATE = "FROM_DATE"
    TO_DATE = "TO_DATE"
    STATION_HEIGHT = "STATION_HEIGHT"
    LATITUDE = "LAT"
    LONGITUDE = "LON"
    STATION_NAME = "STATION_NAME"
    STATE = "STATE"
    EOR = "EOR"
    # Extra column names
    FILENAME = "FILENAME"
    HAS_FILE = "HAS_FILE"
    FILEID = "FILEID"
    # Columns used for tidy data
    # Column for quality
    PARAMETER = "PARAMETER"
    ELEMENT = "ELEMENT"
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
