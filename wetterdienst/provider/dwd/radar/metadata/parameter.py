# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from enum import Enum


class DwdRadarParameter(Enum):
    """
    All available radar moments.
    """

    # /composites
    # https://docs.wradlib.org/en/stable/notebooks/fileio/wradlib_radar_formats.html#German-Weather-Service:-RADOLAN-(quantitative)-composit  # noqa:B950,E501

    # https://opendata.dwd.de/weather/radar/composite/
    HG_REFLECTIVITY = "hg"
    PG_REFLECTIVITY = "pg"
    RV_REFLECTIVITY = "rv"
    WN_REFLECTIVITY = "wn"

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
    # https://docs.wradlib.org/en/stable/notebooks/fileio/wradlib_radar_formats.html#German-Weather-Service:-DX-format
    DX_REFLECTIVITY = "dx"
    LMAX_VOLUME_SCAN = "lmax"
    PE_ECHO_TOP = "pe"
    PF_REFLECTIVITY = "pf"
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
    DwdRadarParameter.HG_REFLECTIVITY,
    DwdRadarParameter.PG_REFLECTIVITY,
    DwdRadarParameter.RV_REFLECTIVITY,
    DwdRadarParameter.WN_REFLECTIVITY,
]
RADAR_PARAMETERS_RADOLAN = [
    DwdRadarParameter.RW_REFLECTIVITY,
    DwdRadarParameter.RY_REFLECTIVITY,
    DwdRadarParameter.SF_REFLECTIVITY,
]
RADAR_PARAMETERS_RADVOR = [
    DwdRadarParameter.RE_REFLECTIVITY,
    DwdRadarParameter.RQ_REFLECTIVITY,
]
RADAR_PARAMETERS_SITES = [
    DwdRadarParameter.DX_REFLECTIVITY,
    DwdRadarParameter.LMAX_VOLUME_SCAN,
    DwdRadarParameter.PE_ECHO_TOP,
    DwdRadarParameter.PF_REFLECTIVITY,
    DwdRadarParameter.PX_REFLECTIVITY,
    DwdRadarParameter.PR_VELOCITY,
    DwdRadarParameter.PX250_REFLECTIVITY,
    DwdRadarParameter.PZ_CAPPI,
    DwdRadarParameter.SWEEP_PCP_VELOCITY_H,
    DwdRadarParameter.SWEEP_PCP_REFLECTIVITY_H,
    DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
    DwdRadarParameter.SWEEP_VOL_REFLECTIVITY_H,
]
RADAR_PARAMETERS_SWEEPS = [
    DwdRadarParameter.SWEEP_PCP_VELOCITY_H,
    DwdRadarParameter.SWEEP_PCP_REFLECTIVITY_H,
    DwdRadarParameter.SWEEP_VOL_VELOCITY_H,
    DwdRadarParameter.SWEEP_VOL_REFLECTIVITY_H,
]


class DwdRadarDate(Enum):
    """
    Enumeration for pointing to different radar dates.
    """

    LATEST = "latest"
    CURRENT = "current"
    MOST_RECENT = "most_recent"


class DwdRadarDataFormat(Enum):
    """
    Radar data formats.
    """

    BINARY = "binary"
    BUFR = "bufr"
    HDF5 = "hdf5"


class DwdRadarDataSubset(Enum):
    """
    HDF5 subset types for radar sweep data.

    https://opendata.dwd.de/weather/radar/sites/sweep_pcp_v/boo/hdf5/
    """

    SIMPLE = "simple"
    POLARIMETRIC = "polarimetric"
