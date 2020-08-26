""" metdata constants """
from enum import Enum

DWD_FOLDER_MAIN = "./dwd_data"
DWD_FOLDER_STATION_DATA = "station_data"
DWD_FOLDER_RADOLAN = "radolan"

DWD_FILE_STATION_DATA = "dwd_station_data"
DWD_FILE_RADOLAN = "radolan"

STATION_ID_REGEX = r"(?<!\d)\d{5}(?!\d)"

RADOLAN_HISTORICAL_DT_REGEX = r"(?<!\d)\d{6}(?!\d)"

RADOLAN_RECENT_DT_REGEX = r"(?<!\d)\d{10}(?!\d)"

NA_STRING = "-999"
STATION_DATA_SEP = ";"


class DataFormat(Enum):
    CSV = "csv"
    H5 = "h5"
    BIN = "bin"


class ArchiveFormat(Enum):
    ZIP = "zip"
    GZ = "gz"
    TAR_GZ = "tar.gz"
