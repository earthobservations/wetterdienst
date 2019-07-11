'''
A set of variables used to access the data and setup the environment
'''

# DWD credentials needed to access the ftp server
# main server address
DWD_SERVER = 'ftp-cdc.dwd.de'
# main path of server where station data is deposited
DWD_PATH = 'pub/CDC/observations_germany/climate'
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

# Matchstrings for detecting metadata file in list of files
METADATA_MATCHSTRINGS = ['beschreibung', '.txt']
STATIONDATA_MATCHSTRINGS = ['produkt']

# Names for files
FILELIST_NAME = 'filelist'
METADATA_NAME = 'metadata'

# File formats
ARCHIVE_FORMAT = '.zip'
DATA_FORMAT = '.csv'

# Column names that should be replaced if found in DataFrame
STATIONDATA_COLS_REPL = {'STATIONS_ID': 'STATION_ID',
                         'MESS_DATUM': 'DATE'}
METADATA_COLS_REPL = {'STATIONS_ID': 'STATION_ID',
                      'VON_DATUM': 'FROM_DATE',
                      'BIS_DATUM': 'TO_DATE',
                      'STATIONSHOEHE': 'STATIONHEIGHT',
                      'GEOBREITE': 'LAT',
                      'GEOLAENGE': 'LON',
                      'STATIONSNAME': 'STATIONNAME',
                      'BUNDESLAND': 'STATE'}

STRING_STATID_COL = {"historical": -4,
                     "recent": -2,
                     "now": -2}
