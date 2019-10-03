""" metdata constants """
METADATA_1MIN_COLUMNS = ["STATION_ID",
                         "FROM_DATE",
                         "TO_DATE",
                         "STATIONHEIGHT",
                         "LAT",
                         "LON",
                         "STATIONNAME"]
METADATA_MATCHSTRINGS = ['beschreibung', '.txt']
METADATA_1MIN_GEO_MATCHSTRINGS = ["metadaten", "geographie", "txt"]
METADATA_1MIN_PAR_MATCHSTRINGS = ["metadaten", "parameter", "txt"]
STATIONDATA_MATCHSTRINGS = ['produkt']
FILELIST_NAME = 'filelist'
METADATA_NAME = 'metadata'
FTP_METADATA_NAME = "meta_data"
ARCHIVE_FORMAT = '.zip'
DATA_FORMAT = '.csv'
DATE_FORMAT = "%Y%m%d"
STRING_STATID_COL = 2
METADATA_FIXED_COLUMN_WIDTH = [(0, 5), (5, 14), (14, 23), (23, 38),
                               (38, 50), (50, 60), (60, 102), (102, 200)]
