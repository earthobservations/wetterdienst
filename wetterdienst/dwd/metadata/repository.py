""" german weather service ftp credentials """
from enum import Enum

DWD_SERVER = "https://opendata.dwd.de"
DWD_CDC_PATH = "climate_environment/CDC/"

DWD_MOSMIX_S_PATH = "weather/local_forecasts/mos/MOSMIX_S/all_stations/kml/"
DWD_MOSMIX_L_PATH = "weather/local_forecasts/mos/MOSMIX_L/all_stations/kml/"
DWD_MOSMIX_L_SINGLE_PATH = "weather/local_forecasts/mos/MOSMIX_L/single_stations/{station_id}/kml/"  # noqa:E501,B950


class DWDCDCBase(Enum):
    CLIMATE_OBSERVATIONS = "observations_germany/climate/"
    GRIDS_GERMANY = "grids_germany/"


DWD_FOLDER_MAIN = "./dwd_data"
DWD_FOLDER_STATION_DATA = "station_data"
DWD_FILE_STATION_DATA = "dwd_station_data"
STATION_ID_REGEX = r"(?<!\d)\d{5}(?!\d)"
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
