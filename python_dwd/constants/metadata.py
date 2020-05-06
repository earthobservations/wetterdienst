""" metdata constants """
from python_dwd.enumerations.column_names_enumeration import DWDColumns

METADATA_COLUMNS = [DWDColumns.STATION_ID.value,
                    DWDColumns.FROM_DATE.value,
                    DWDColumns.TO_DATE.value,
                    DWDColumns.STATIONHEIGHT.value,
                    DWDColumns.LATITUDE.value,
                    DWDColumns.LONGITUDE.value,
                    DWDColumns.STATIONNAME.value,
                    DWDColumns.STATE.value]

METADATA_MATCHSTRINGS = ['beschreibung', '.txt']
METADATA_1MIN_GEO_PREFIX = "Metadaten_Geographie_"
METADATA_1MIN_PAR_PREFIX = "Metadaten_Parameter_"
STATIONDATA_MATCHSTRINGS = ['produkt']
FILELIST_NAME = 'filelist'
METADATA_NAME = 'metadata'
STATIONDATA_NAME = "stationdata"
DWDDATA_NAME = "DWD_DATA"
FTP_METADATA_NAME = "meta_data"
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
