'''
A set of variables used to access the data and setup the environment
'''

# DWD credentials needed to access the ftp server
# main server address
DWD_SERVER = 'opendata.dwd.de'
# main path of server where station data is deposited
DWD_PATH = 'climate_environment/CDC/observations_germany/climate'
# possible user name
DWD_USER = 'anonymous'
# possible password
DWD_PASSWORD = ''

# Folder name for main folder
MAIN_FOLDER = './dwd_data'
# Folder name for metadata folder
SUB_FOLDER_METADATA = 'metadata'
# Folder name for stationdata folder
SUB_FOLDER_STATIONDATA = 'stationdata'

#
METADATA_1MIN_COLUMNS = ["STATION_ID",
                         "FROM_DATE",
                         "TO_DATE",
                         "STATIONHEIGHT",
                         "LAT",
                         "LON",
                         "STATIONNAME"]

# Matchstrings for detecting metadata file in list of files
METADATA_MATCHSTRINGS = ['beschreibung', '.txt']
METADATA_1MIN_GEO_MATCHSTRINGS = ["metadaten", "geographie"]
METADATA_1MIN_PAR_MATCHSTRINGS = ["metadaten", "parameter"]
STATIONDATA_MATCHSTRINGS = ['produkt']

# Names for files
FILELIST_NAME = 'filelist'
METADATA_NAME = 'metadata'

# Name of metadata folder on ftp server
FTP_METADATA_NAME = "meta_data"

# File formats
ARCHIVE_FORMAT = '.zip'
DATA_FORMAT = '.csv'

# Ceveral other names appearing inside created files
FILENAME_NAME = "FILENAME"
STATION_ID_NAME = "STATION_ID"
DATE_NAME = "DATE"
HAS_FILE_NAME = "HAS_FILE"
FILEID_NAME = "FILEID"

# Column names that should be replaced if found in DataFrame
STATIONDATA_COLS_REPL = {'STATIONS_ID': 'STATION_ID',
                         'MESS_DATUM': 'DATE'}

METADATA_COLS_REPL = {'STATIONS_ID': 'STATION_ID',
                      'VON_DATUM': 'FROM_DATE',
                      'BIS_DATUM': 'TO_DATE',
                      'STATIONSHOEHE': 'STATIONHEIGHT',
                      'GEOBREITE': 'LAT',
                      "GEOGR.BREITE": "LAT",
                      'GEOLAENGE': 'LON',
                      "GEOGR.LAENGE": "LON",
                      'STATIONSNAME': 'STATIONNAME',
                      'BUNDESLAND': 'STATE'}

# Position/number of parts of filenames depending on filetype
STRING_STATID_COL = {"historical": -4,
                     "recent": -2,
                     "now": -2}
