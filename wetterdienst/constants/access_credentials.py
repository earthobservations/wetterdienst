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
