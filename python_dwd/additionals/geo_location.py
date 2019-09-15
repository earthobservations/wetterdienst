""" caclualtes the nearest weather station to a requested location"""
from typing import List, Union, Tuple

import numpy as np
from scipy.spatial import cKDTree

from python_dwd.additionals.functions import check_parameters
from python_dwd.data_models.coordinates import Coordinates
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import \
    TimeResolution
from python_dwd.metadata_dwd import metadata_for_dwd_data

KM_EARTH_RADIUS = 6371


def get_nearest_station(latitudes: Union[List[float], np.array],
                        longitudes: Union[List[float], np.array],
                        parameter: Parameter,
                        time_resolution: TimeResolution,
                        period_type: PeriodType) -> \
        Tuple[List[int], List[float]]:
    """
    Provides a list of weather station ids for the requested data
    Args:
        latitudes: latitudes of locations to search for nearest
            weather station
        longitudes: longitudes of locations to search for nearest
            weather station
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files

    Returns:
        list of stations ids for the given locations/coordinate pairs and
        a list of distances in kilometer to the weather station

    """
    if not isinstance(latitudes, list):
        latitudes = np.array(latitudes)
    if not isinstance(longitudes, list):
        latitudes = np.array(longitudes)

    check_parameters(parameter, time_resolution, period_type)

    coords = Coordinates(latitudes, longitudes)

    metadata = metadata_for_dwd_data(parameter,
                                     time_resolution,
                                     period_type)

    distances, indices_nearest_neighbours = derive_nearest_neighbours(
        metadata.LAT.values,
        metadata.LON.values,
        coords)

    return metadata.loc[indices_nearest_neighbours, 'STATION_ID'].tolist(),\
           (distances * KM_EARTH_RADIUS).tolist()


def derive_nearest_neighbours(latitudes_stations: np.array,
                              longitudes_stations: np.array,
                              coordinates: Coordinates):
    """
    uses a k-d tree algorhtym to obtain the nearest
    neighbours to coordinate pairs

    """
    points = np.c_[np.radians(latitudes_stations),
                   np.radians(longitudes_stations)]
    distance_tree = cKDTree(points)
    return distance_tree.query(
        coordinates.get_coordinates_in_radians())
