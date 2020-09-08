""" enumeration for parameter """
from enum import Enum


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
