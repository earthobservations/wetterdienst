""" metdata constants """
from python_dwd.constants.column_name_mapping import STATION_ID_NAME, FROM_DATE_NAME, TO_DATE_NAME, \
    STATIONHEIGHT_NAME, LAT_NAME, LON_NAME, STATIONNAME_NAME, STATE_NAME

METADATA_COLUMNS = [STATION_ID_NAME,
                    FROM_DATE_NAME,
                    TO_DATE_NAME,
                    STATIONHEIGHT_NAME,
                    LAT_NAME,
                    LON_NAME,
                    STATIONNAME_NAME,
                    STATE_NAME]

METADATA_MATCHSTRINGS = ['beschreibung', '.txt']
METADATA_1MIN_GEO_MATCHSTRINGS = ["metadaten", "geographie", "txt"]
METADATA_1MIN_PAR_MATCHSTRINGS = ["metadaten", "parameter", "txt"]
STATIONDATA_MATCHSTRINGS = ['produkt']
FILELIST_NAME = 'filelist'
METADATA_NAME = 'metadata'
DWDDATA_NAME = "DWD_DATA"
FTP_METADATA_NAME = "meta_data"
ARCHIVE_FORMAT = '.zip'
DATA_FORMAT = '.csv'
STATION_DATA_NC = "stationdata.nc"
DATE_FORMAT = "%Y%m%d"
STRING_STATID_COL = 2
STATID_REGEX = r"(?<!\d)\d{5}(?!\d)"
METADATA_FIXED_COLUMN_WIDTH = [(0, 5), (5, 14), (14, 23), (23, 38),
                               (38, 50), (50, 60), (60, 102), (102, 200)]
NA_STRING = "-999"
STATIONDATA_SEP = ";"


