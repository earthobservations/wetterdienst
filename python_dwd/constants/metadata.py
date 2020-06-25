""" metdata constants """
from python_dwd.enumerations.column_names_enumeration import DWDMetaColumns

METADATA_COLUMNS = [DWDMetaColumns.STATION_ID.value,
                    DWDMetaColumns.FROM_DATE.value,
                    DWDMetaColumns.TO_DATE.value,
                    DWDMetaColumns.STATIONHEIGHT.value,
                    DWDMetaColumns.LATITUDE.value,
                    DWDMetaColumns.LONGITUDE.value,
                    DWDMetaColumns.STATIONNAME.value,
                    DWDMetaColumns.STATE.value]

METADATA_MATCHSTRINGS = ['beschreibung', '.txt']
METADATA_1MIN_GEO_PREFIX = "Metadaten_Geographie_"
METADATA_1MIN_STA_PREFIX = "Metadaten_Stationsname_"
STATIONDATA_MATCHSTRINGS = ['produkt']
FILELIST_NAME = 'filelist'
DWD_FOLDER_MAIN = './dwd_data'
DWD_FOLDER_STATION_DATA = "station_data"
DWD_FILE_STATION_DATA = "dwd_station_data"
META_DATA_FOLDER = "meta_data"
ARCHIVE_FORMAT = '.zip'
DATA_FORMAT = '.csv'
H5_FORMAT = ".h5"
DATE_FORMAT = "%Y%m%d"
STATID_REGEX = r"(?<!\d)\d{5}(?!\d)"
METADATA_FIXED_COLUMN_WIDTH = [(0, 5), (5, 14), (14, 23), (23, 38),
                               (38, 50), (50, 60), (60, 102), (102, 200)]
NA_STRING = "-999"
STATIONDATA_SEP = ";"

TRIES_TO_DOWNLOAD_FILE = 3
