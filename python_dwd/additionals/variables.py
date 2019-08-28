'''
A set of variables used to access the data and setup the environment
---------------------------------------------------------------------
In the following lines we have defined several keys to 
- how we access
- how we name it (files, columns in dataframes, etc.)
- how we rename it (german to english)
- what strings to look for when searching for files like metadata/
stationdata
- what fileendings we expect
- and others
This helps us to maintain this library - firstly for ourselves to
change certain things in a way we want it e.g. to name columns 
differently and to prepare for future changes where one expected name
may have altered through updated filestructures on the ftp server.
Therefor we want to keep our functions free of those hard-coded names
and instead use our variables as they are defined in this file.
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

# Column names of 1min metadata
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

# The following list of names can be found inside the files on the server
# Original column names
'''
The following list of names can be found inside the files on the server.
They are part of the header and represent diffrent type of data. To
work with the data we will translate the columns to an english version.
Thus once set here, the scripts can understand how to work with the files
and also provide oversight for everybody by using english names. The
original column names should only be changed if the data has changed!
'''
# Original column names
ORIG_STATION_ID_NAME = "STATIONS_ID"
ORIG_DATE_NAME = "MESS_DATUM"
ORIG_FROM_DATE_NAME = "VON_DATUM"
ORIG_TO_DATE_NAME = "BIS_DATUM"
ORIG_STATIONHEIGHT_NAME = "STATIONSHOEHE"
ORIG_LAT_NAME = "GEOBREITE"
ORIG_LAT_ALT_NAME = "GEOGR.BREITE"
ORIG_LON_NAME = "GEOLAENGE"
ORIG_LON_ALT_NAME = "GEOGR.LAENGE"
ORIG_STATIONNAME_NAME = "STATIONSNAME"
ORIG_STATE_NAME = "BUNDESLAND"

# English column names (can be changed for personal reasons)
STATION_ID_NAME = "STATION_ID"
DATE_NAME = "DATE"
FROM_DATE_NAME = "FROM_DATE"
TO_DATE_NAME = "TO_DATE"
STATIONHEIGHT_NAME = "STATIONHEIGHT"
LAT_NAME = "LAT"
LON_NAME = "LON"
STATIONNAME_NAME = "STATIONNAME"
STATE_NAME = "STATE"

# Here we build a dictionary for the use of changing columnnames of any dataframe
COLS_REPL = {ORIG_STATION_ID_NAME: STATION_ID_NAME,
             ORIG_DATE_NAME: DATE_NAME,
             ORIG_FROM_DATE_NAME: FROM_DATE_NAME,
             ORIG_TO_DATE_NAME: TO_DATE_NAME,
             ORIG_STATIONHEIGHT_NAME: STATIONHEIGHT_NAME,
             ORIG_LAT_NAME: LAT_NAME,
             ORIG_LAT_ALT_NAME: LAT_NAME,
             ORIG_LON_NAME: LON_NAME,
             ORIG_LON_ALT_NAME: LON_NAME,
             ORIG_STATIONNAME_NAME: STATIONNAME_NAME,
             ORIG_STATE_NAME: STATE_NAME}

# Additional column names
# FILENAME is used for naming the column of filelist where filenames are stored
FILENAME_NAME = "FILENAME"
# HAS_FILE is used for naming the column that stores the information if a file
# is available online.
HAS_FILE_NAME = "HAS_FILE"
# FILEID is used to name the column in which the id of the file is stored
FILEID_NAME = "FILEID"

# Position/number of parts of filenames depending on filetype
STRING_STATID_COL = {"historical": -4,
                     "recent": -2,
                     "now": -2}
