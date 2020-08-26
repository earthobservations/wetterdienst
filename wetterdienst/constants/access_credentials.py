""" german weather service ftp credentials """
from enum import Enum

HTTPS_EXPRESSION = "https://"

DWD_SERVER = "opendata.dwd.de"
DWD_CDC_PATH = "climate_environment/CDC"


class DWDCDCBase(Enum):
    CLIMATE_OBSERVATIONS = "observations_germany/climate"
    GRIDS_GERMANY = "grids_germany"
