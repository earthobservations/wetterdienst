from enum import Enum


class RadarDataType(Enum):
    """ Enumeration for different Radar Data Types"""

    BUFR = "bufr"
    HDF5 = "hdf5"
    BINARY = "binary"


class RadarParameter(Enum):

    # Composites
    # https://docs.wradlib.org/en/stable/notebooks/fileio/wradlib_radar_formats.html#German-Weather-Service:-RADOLAN-(quantitative)-composit  # noqa:E501,B950

    # https://opendata.dwd.de/weather/radar/composit/
    # TODO: "FX" was missing here. OTOH, "pp" doesn't
    #       seem to be present on opendata.dwd.de.
    FX_REFLECTIVITY = "fx"
    PG_REFLECTIVITY = "pg"
    # PP_REFLECTIVITY = "pp"
    WX_REFLECTIVITY = "wx"
    WN_REFLECTIVITY = "wn"
    RX_REFLECTIVITY = "rx"

    # https://opendata.dwd.de/weather/radar/radolan/
    RW_REFLECTIVITY = "rw"
    RY_REFLECTIVITY = "ry"
    SF_REFLECTIVITY = "sf"

    # Sites
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
    SWEEP_VOL_PRECIPITATION_V = "sweep_pcp_v"
    SWEEP_VOL_PRECIPITATION_Z = "sweep_pcp_z"
    SWEEP_VOL_VELOCITY_V = "sweep_vol_v"
    SWEEP_VOL_VELOCITY_Z = "sweep_vol_z"

    # https://opendata.dwd.de/climate_environment/CDC/grids_germany/daily/radolan/
    # https://opendata.dwd.de/climate_environment/CDC/grids_germany/hourly/radolan/
    # https://opendata.dwd.de/climate_environment/CDC/grids_germany/5_minutes/radolan/
    RADOLAN_GRID = "radolan_grid"


RADAR_PARAMETERS_SITES = [
    RadarParameter.DX_REFLECTIVITY,
    RadarParameter.LMAX_VOLUME_SCAN,
    RadarParameter.PE_ECHO_TOP,
    RadarParameter.PF_REFLECTIVITY,
    RadarParameter.PX_REFLECTIVITY,
    RadarParameter.PL_VOLUME_SCAN,
    RadarParameter.PR_VELOCITY,
    RadarParameter.PX250_REFLECTIVITY,
    RadarParameter.PZ_CAPPI,
    RadarParameter.SWEEP_VOL_PRECIPITATION_V,
    RadarParameter.SWEEP_VOL_PRECIPITATION_Z,
    RadarParameter.SWEEP_VOL_VELOCITY_V,
    RadarParameter.SWEEP_VOL_VELOCITY_Z,
]
RADAR_PARAMETERS_COMPOSITES = [
    # RadarParameter.PP_REFLECTIVITY,
    RadarParameter.FX_REFLECTIVITY,
    RadarParameter.PG_REFLECTIVITY,
    RadarParameter.WX_REFLECTIVITY,
    RadarParameter.WN_REFLECTIVITY,
    RadarParameter.RX_REFLECTIVITY,
]
RADAR_PARAMETERS_WITH_HDF5 = [
    RadarParameter.SWEEP_VOL_PRECIPITATION_V,
    RadarParameter.SWEEP_VOL_PRECIPITATION_Z,
    RadarParameter.SWEEP_VOL_VELOCITY_V,
    RadarParameter.SWEEP_VOL_VELOCITY_Z,
]
RADAR_PARAMETERS_RADOLAN = [
    RadarParameter.RW_REFLECTIVITY,
    RadarParameter.RY_REFLECTIVITY,
    RadarParameter.SF_REFLECTIVITY,
]
