""" enumeration for parameter """
from enum import Enum
from typing import Dict, List

from wetterdienst.dwd.metadata.time_resolution import TimeResolution
from wetterdienst.dwd.metadata.period_type import PeriodType


class Parameter(Enum):
    """
    enumeration for different parameter/variables
    measured by dwd weather stations, listed from 1_minute to yearly resolution
    """

    # 1_minute
    PRECIPITATION = "precipitation"
    # 10_minutes - left out: wind_test
    TEMPERATURE_AIR = "air_temperature"
    TEMPERATURE_EXTREME = "extreme_temperature"
    WIND_EXTREME = "extreme_wind"
    SOLAR = "solar"
    WIND = "wind"
    # hourly
    CLOUD_TYPE = "cloud_type"
    CLOUDINESS = "cloudiness"
    DEW_POINT = "dew_point"
    PRESSURE = "pressure"
    TEMPERATURE_SOIL = "soil_temperature"
    SUNSHINE_DURATION = "sun"
    VISIBILITY = "visibility"
    WIND_SYNOPTIC = "wind_synop"
    # subdaily - left out: standard_format
    MOISTURE = "moisture"
    SOIL = "soil"
    # daily
    CLIMATE_SUMMARY = "kl"
    PRECIPITATION_MORE = "more_precip"
    WATER_EQUIVALENT = "water_equiv"
    WEATHER_PHENOMENA = "weather_phenomena"

    # Radar data

    # composites
    RADOLAN = "radolan"
    WX_REFLECTIVITY = "wx"
    RX_REFLECTIVITY = "rx"
    WN_REFLECTIVITY = "wn"
    PG_REFLECTIVITY = "pg"
    PP_REFLECTIVITY = "pp"

    # sites
    DX_REFLECTIVITY = "dx"
    LMAX_VOLUME_SCAN = "lmax"
    PE_ECHO_TOP = "pe"
    PF_REFLECTIVITY = "pf"
    PL_VOLUME_SCAN = "pl"
    PR_VELOCITY = "pr"
    PX_REFLECTIVITY = "px"
    PX250_REFLECTIVITY = "px250"
    PZ_CAPPI = "pz"
    SWEEP_VOL_PRECIPITATION_V = "sweep_pcp_v"
    SWEEP_VOL_PRECIPITATION_Z = "sweep_pcp_z"
    SWEEP_VOL_VELOCITY_V = "sweep_vol_v"
    SWEEP_VOL_VELOCITY_Z = "sweep_vol_z"


TIME_RESOLUTION_PARAMETER_MAPPING: Dict[
    TimeResolution, Dict[Parameter, List[PeriodType]]
] = {
    TimeResolution.MINUTE_1: {
        Parameter.PRECIPITATION: [
            PeriodType.HISTORICAL,
            PeriodType.RECENT,
            PeriodType.NOW,
        ],
    },
    TimeResolution.MINUTES_10: {
        Parameter.PRECIPITATION: [
            PeriodType.HISTORICAL,
            PeriodType.RECENT,
            PeriodType.NOW,
        ],
        Parameter.TEMPERATURE_AIR: [
            PeriodType.HISTORICAL,
            PeriodType.RECENT,
            PeriodType.NOW,
        ],
        Parameter.TEMPERATURE_EXTREME: [
            PeriodType.HISTORICAL,
            PeriodType.RECENT,
            PeriodType.NOW,
        ],
        Parameter.WIND_EXTREME: [
            PeriodType.HISTORICAL,
            PeriodType.RECENT,
            PeriodType.NOW,
        ],
        Parameter.SOLAR: [PeriodType.HISTORICAL, PeriodType.RECENT, PeriodType.NOW],
        Parameter.WIND: [PeriodType.HISTORICAL, PeriodType.RECENT, PeriodType.NOW],
    },
    TimeResolution.HOURLY: {
        Parameter.TEMPERATURE_AIR: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.CLOUD_TYPE: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.CLOUDINESS: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.DEW_POINT: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.PRECIPITATION: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.PRESSURE: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.TEMPERATURE_SOIL: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.SOLAR: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.SUNSHINE_DURATION: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.VISIBILITY: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.WIND: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.WIND_SYNOPTIC: [PeriodType.HISTORICAL, PeriodType.RECENT],
    },
    TimeResolution.SUBDAILY: {
        Parameter.TEMPERATURE_AIR: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.CLOUDINESS: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.MOISTURE: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.PRESSURE: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.SOIL: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.VISIBILITY: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.WIND: [PeriodType.HISTORICAL, PeriodType.RECENT],
    },
    TimeResolution.DAILY: {
        Parameter.CLIMATE_SUMMARY: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.PRECIPITATION_MORE: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.TEMPERATURE_SOIL: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.SOLAR: [PeriodType.RECENT],
        Parameter.WATER_EQUIVALENT: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.WEATHER_PHENOMENA: [PeriodType.HISTORICAL, PeriodType.RECENT],
    },
    TimeResolution.MONTHLY: {
        Parameter.CLIMATE_SUMMARY: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.PRECIPITATION_MORE: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.WEATHER_PHENOMENA: [PeriodType.HISTORICAL, PeriodType.RECENT],
    },
    TimeResolution.ANNUAL: {
        Parameter.CLIMATE_SUMMARY: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.PRECIPITATION_MORE: [PeriodType.HISTORICAL, PeriodType.RECENT],
        Parameter.WEATHER_PHENOMENA: [PeriodType.HISTORICAL, PeriodType.RECENT],
    },
}
