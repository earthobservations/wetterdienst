from enum import Enum


class DatetimeFormat(Enum):
    YMD = "%Y%m%d"
    YMDHM = "%Y%m%d%H%M"
    YMDHMS = "%Y%m%d%H%M%S"
    YMDH_COLUMN_M = "%Y%m%d%H:%M"
    YMD_TIME_H = "%Y-%m-%dT%H"

    # For RADOLAN file datetime parsing
    YM = "%Y%m"
    ymdhm = "%y%m%d%H%M"


_METADATA = {
    "name_short": "DWD",
    "name_english": "German Weather Service",
    "name_local": "Deutscher Wetterdienst",
    "country": "Germany",
    "copyright": "© Deutscher Wetterdienst (DWD), Climate Data Center (CDC)",
    "url": "https://opendata.dwd.de/climate_environment/CDC/",
}
