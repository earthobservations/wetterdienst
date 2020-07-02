""" calculates the nearest weather station to a requested location"""
from typing import List, Union, Tuple
import numpy as np
from scipy.spatial import cKDTree

from wetterdienst.parse_metadata import metadata_for_dwd_data
from wetterdienst.additionals.functions import check_parameters
from wetterdienst.data_models.coordinates import Coordinates
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import \
    TimeResolution

KM_EARTH_RADIUS = 6371


def get_nearest_station(latitudes: Union[List[float], np.array],
                        longitudes: Union[List[float], np.array],
                        parameter: Union[Parameter, str],
                        time_resolution: Union[TimeResolution, str],
                        period_type: Union[PeriodType, str],
                        num_stations_nearby: int = 1) -> \
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
        num_stations_nearby: Number of stations that should be nearby 

    Returns:
        list of stations ids for the given locations/coordinate pairs and
        a list of distances in kilometer to the weather station

    """
    parameter = Parameter(parameter)
    time_resolution = TimeResolution(time_resolution)
    period_type = PeriodType(period_type)

    if not isinstance(latitudes, list):
        latitudes = np.array(latitudes)
    if not isinstance(longitudes, list):
        latitudes = np.array(longitudes)

    check_parameters(parameter, time_resolution, period_type)

    coords = Coordinates(latitudes, longitudes)

    metadata = metadata_for_dwd_data(parameter,
                                     time_resolution,
                                     period_type)

    distances, indices_nearest_neighbours = _derive_nearest_neighbours(
        metadata.LAT.values,
        metadata.LON.values,
        coords,
        num_stations_nearby)
    if np.max(indices_nearest_neighbours.shape) > 1:
        indices_nearest_neighbours = indices_nearest_neighbours[0]
    return metadata.loc[indices_nearest_neighbours, 'STATION_ID'].tolist(),\
        (distances * KM_EARTH_RADIUS).tolist()


def _derive_nearest_neighbours(latitudes_stations: np.array,
                               longitudes_stations: np.array,
                               coordinates: Coordinates,
                               num_stations_nearby: int = 1) -> Tuple[Union[float, np.ndarray], np.ndarray]:
    """
    A function that uses a k-d tree algorithm to obtain the nearest
    neighbours to coordinate pairs

    Args:
        latitudes_stations (np.array): latitude values of stations being compared to the coordinates
        longitudes_stations (np.array): longitude values of stations being compared to the coordinates
        coordinates (Coordinates): the coordinates for which the nearest neighbour is searched
        num_stations_nearby: Number of stations that should be nearby 

    Returns:
        Tuple of distances and ranks of nearest to most distant stations
    """
    points = np.c_[np.radians(latitudes_stations),
                   np.radians(longitudes_stations)]
    distance_tree = cKDTree(points)
    return distance_tree.query(
        coordinates.get_coordinates_in_radians(),
        k=num_stations_nearby)
