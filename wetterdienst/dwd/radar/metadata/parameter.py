from enum import Enum


class DWDRadarParameter(Enum):
    """
    All available radar moments.
    """

    # /composites
    # https://docs.wradlib.org/en/stable/notebooks/fileio/wradlib_radar_formats.html#German-Weather-Service:-RADOLAN-(quantitative)-composit  # noqa:E501,B950

    # https://opendata.dwd.de/weather/radar/composit/
    FX_REFLECTIVITY = "fx"
    PG_REFLECTIVITY = "pg"
    WX_REFLECTIVITY = "wx"
    WN_REFLECTIVITY = "wn"
    RX_REFLECTIVITY = "rx"

    # /radolan
    # https://opendata.dwd.de/weather/radar/radolan/
    RW_REFLECTIVITY = "rw"
    RY_REFLECTIVITY = "ry"
    SF_REFLECTIVITY = "sf"

    # /radvor
    # https://opendata.dwd.de/weather/radar/radvor/
    RE_REFLECTIVITY = "re"
    RQ_REFLECTIVITY = "rq"

    # /sites
    # https://opendata.dwd.de/weather/radar/sites/
    # https://docs.wradlib.org/en/stable/notebooks/fileio/wradlib_radar_formats.html#German-Weather-Service:-DX-format  # noqa:E501,B950
    DX_REFLECTIVITY = "dx"
    LMAX_VOLUME_SCAN = "lmax"
    PE_ECHO_TOP = "pe"
    PF_REFLECTIVITY = "pf"
    PL_VOLUME_SCAN = "pl"
    PR_VELOCITY = "pr"
    PX_REFLECTIVITY = "px"
    PX250_REFLECTIVITY = "px250"
    PZ_CAPPI = "pz"

    # OPERA HDF5 (ODIM_H5)
    # https://docs.wradlib.org/en/stable/notebooks/fileio/wradlib_radar_formats.html#HDF5
    SWEEP_PCP_VELOCITY_H = "sweep_pcp_v"
    SWEEP_PCP_REFLECTIVITY_H = "sweep_pcp_z"
    SWEEP_VOL_VELOCITY_H = "sweep_vol_v"
    SWEEP_VOL_REFLECTIVITY_H = "sweep_vol_z"

    # https://opendata.dwd.de/climate_environment/CDC/grids_germany/daily/radolan/
    # https://opendata.dwd.de/climate_environment/CDC/grids_germany/hourly/radolan/
    # https://opendata.dwd.de/climate_environment/CDC/grids_germany/5_minutes/radolan/
    RADOLAN_CDC = "radolan_cdc"


RADAR_PARAMETERS_COMPOSITES = [
    DWDRadarParameter.FX_REFLECTIVITY,
    DWDRadarParameter.PG_REFLECTIVITY,
    DWDRadarParameter.WX_REFLECTIVITY,
    DWDRadarParameter.WN_REFLECTIVITY,
    DWDRadarParameter.RX_REFLECTIVITY,
]
RADAR_PARAMETERS_RADOLAN = [
    DWDRadarParameter.RW_REFLECTIVITY,
    DWDRadarParameter.RY_REFLECTIVITY,
    DWDRadarParameter.SF_REFLECTIVITY,
]
RADAR_PARAMETERS_RADVOR = [
    DWDRadarParameter.RE_REFLECTIVITY,
    DWDRadarParameter.RQ_REFLECTIVITY,
]
RADAR_PARAMETERS_SITES = [
    DWDRadarParameter.DX_REFLECTIVITY,
    DWDRadarParameter.LMAX_VOLUME_SCAN,
    DWDRadarParameter.PE_ECHO_TOP,
    DWDRadarParameter.PF_REFLECTIVITY,
    DWDRadarParameter.PX_REFLECTIVITY,
    DWDRadarParameter.PL_VOLUME_SCAN,
    DWDRadarParameter.PR_VELOCITY,
    DWDRadarParameter.PX250_REFLECTIVITY,
    DWDRadarParameter.PZ_CAPPI,
    DWDRadarParameter.SWEEP_PCP_VELOCITY_H,
    DWDRadarParameter.SWEEP_PCP_REFLECTIVITY_H,
    DWDRadarParameter.SWEEP_VOL_VELOCITY_H,
    DWDRadarParameter.SWEEP_VOL_REFLECTIVITY_H,
]
RADAR_PARAMETERS_SWEEPS = [
    DWDRadarParameter.SWEEP_PCP_VELOCITY_H,
    DWDRadarParameter.SWEEP_PCP_REFLECTIVITY_H,
    DWDRadarParameter.SWEEP_VOL_VELOCITY_H,
    DWDRadarParameter.SWEEP_VOL_REFLECTIVITY_H,
]


class DWDRadarDate(Enum):
    """
    Enumeration for pointing to different radar dates.
    """

    LATEST = "latest"
    CURRENT = "current"
    MOST_RECENT = "most_recent"


class DWDRadarDataFormat(Enum):
    """
    Radar data formats.
    """

    BINARY = "binary"
    BUFR = "bufr"
    HDF5 = "hdf5"


class DWDRadarDataSubset(Enum):
    """
    HDF5 subset types for radar sweep data.

    https://opendata.dwd.de/weather/radar/sites/sweep_pcp_v/boo/hdf5/
    """

    SIMPLE = "simple"
    POLARIMETRIC = "polarimetric"
