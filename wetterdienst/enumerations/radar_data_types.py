from enum import Enum


class RadarDataTypes(Enum):
    """ Enumeration for different Radar Data Types"""
    BUFR = "bufr"
    HDF5 = "hdf5"
    BINARY = "binary"
