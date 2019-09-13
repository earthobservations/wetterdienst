""" metdata constants """
METADATA_1MIN_COLUMNS = ["STATION_ID",
                         "FROM_DATE",
                         "TO_DATE",
                         "STATIONHEIGHT",
                         "LAT",
                         "LON",
                         "STATIONNAME"]
METADATA_MATCHSTRINGS = ['beschreibung', '.txt']
METADATA_1MIN_GEO_MATCHSTRINGS = ["metadaten", "geographie"]
METADATA_1MIN_PAR_MATCHSTRINGS = ["metadaten", "parameter"]
STATIONDATA_MATCHSTRINGS = ['produkt']
FILELIST_NAME = 'filelist'
METADATA_NAME = 'metadata'
FTP_METADATA_NAME = "meta_data"
ARCHIVE_FORMAT = '.zip'
DATA_FORMAT = '.csv'
# Column specifications used for fixed-width-file (pandas.read_fwf)
# All metadata files seem to have the same fixed column widths
METADATA_COLSPECS = [(0, 5), (5, 14), (14, 23), (23, 38), (38, 50), (50, 60), (60, 102), (102, 200)]
