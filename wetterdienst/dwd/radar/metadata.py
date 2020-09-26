from enum import Enum
from wetterdienst import Parameter


class RadarDataTypes(Enum):
    """ Enumeration for different Radar Data Types"""

    BUFR = "bufr"
    HDF5 = "hdf5"
    BINARY = "binary"


RADAR_PARAMETERS_SITES = [
    Parameter.DX_REFLECTIVITY,
    Parameter.LMAX_VOLUME_SCAN,
    Parameter.PE_ECHO_TOP,
    Parameter.PF_REFLECTIVITY,
    Parameter.PX_REFLECTIVITY,
    Parameter.PL_VOLUME_SCAN,
    Parameter.PR_VELOCITY,
    Parameter.PX250_REFLECTIVITY,
    Parameter.PZ_CAPPI,
    Parameter.SWEEP_VOL_PRECIPITATION_V,
    Parameter.SWEEP_VOL_PRECIPITATION_Z,
    Parameter.SWEEP_VOL_VELOCITY_V,
    Parameter.SWEEP_VOL_VELOCITY_Z,
]
RADAR_PARAMETERS_COMPOSITES = [
    Parameter.PP_REFLECTIVITY,
    Parameter.PG_REFLECTIVITY,
    Parameter.WX_REFLECTIVITY,
    Parameter.WN_REFLECTIVITY,
    Parameter.RX_REFLECTIVITY,
]
RADAR_PARAMETERS_WITH_HDF5 = [
    Parameter.SWEEP_VOL_PRECIPITATION_V,
    Parameter.SWEEP_VOL_PRECIPITATION_Z,
    Parameter.SWEEP_VOL_VELOCITY_V,
    Parameter.SWEEP_VOL_VELOCITY_Z,
]
