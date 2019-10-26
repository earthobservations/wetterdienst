""" enumeration for time_resoltution """
from enum import Enum


class TimeResolution(Enum):
    """
        enumeration for granularity/resolution of the weather
        observations stored on dwd server
    """
    MINUTE_1 = "1_minute"
    MINUTE_10 = "10_minutes"
    HOURLY = "hourly"
    DAILY = "daily"
    MONTHLY = "monthly"
    ANNUAL = "annual"


TIMERESOLUTION_WORDLISTS = {
    TimeResolution.MINUTE_1: [["1"], ["min"]],
    TimeResolution.MINUTE_10: [["10"], ["min"]],
    TimeResolution.HOURLY: [["hour", "stünd"]],
    TimeResolution.DAILY: [["day", "tag", "daily", "täg"]],
    TimeResolution.MONTHLY: [["month", "monat"]],
    TimeResolution.ANNUAL: [["year", "jahr", "annual", "jähr"]]
}
