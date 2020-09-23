""" calculates the nearest weather station to a requested location"""
from _datetime import datetime
from typing import Union, Tuple, Optional

import numpy as np
import pandas as pd
import logging
from scipy.spatial import cKDTree

from wetterdienst.additionals.functions import (
    check_parameters,
    parse_enumeration_from_template,
)
from wetterdienst.additionals.time_handling import parse_datetime
from wetterdienst.data_models.coordinates import Coordinates
from wetterdienst.enumerations.column_names_enumeration import DWDMetaColumns
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution
from wetterdienst.exceptions import InvalidParameterCombination
from wetterdienst.parse_metadata import metadata_for_climate_observations

KM_EARTH_RADIUS = 6371

logger = logging.getLogger(__name__)


def get_nearby_stations_by_number(
    latitude: float,
    longitude: float,
    num_stations_nearby: int,
    parameter: Union[Parameter, str],
    time_resolution: Union[TimeResolution, str],
    period_type: Union[PeriodType, str],
    minimal_available_date: Optional[Union[datetime, str]] = None,
    maximal_available_date: Optional[Union[datetime, str]] = None,
) -> pd.DataFrame:
    """
    Provides a list of weather station ids for the requested data

    :param latitude:                Latitude of location to search for nearest
                                    weather station
    :param longitude:               Longitude of location to search for nearest
                                    weather station
    :param minimal_available_date:  Start date of timespan where measurements
                                    should be available
    :param maximal_available_date:  End date of timespan where measurements
                                    should be available
    :param parameter:               Observation measure
    :param time_resolution:         Frequency/granularity of measurement interval
    :param period_type:             Recent or historical files
    :param num_stations_nearby:     Number of stations that should be nearby

    :return:                        DataFrames with valid stations in radius per
                                    requested location

    """
    if num_stations_nearby <= 0:
        raise ValueError("'num_stations_nearby' has to be at least 1.")

    parameter = parse_enumeration_from_template(parameter, Parameter)
    time_resolution = parse_enumeration_from_template(time_resolution, TimeResolution)
    period_type = parse_enumeration_from_template(period_type, PeriodType)

    if not check_parameters(parameter, time_resolution, period_type):
        raise InvalidParameterCombination(
            f"The combination of {parameter.value}, {time_resolution.value}, "
            f"{period_type.value} is invalid."
        )

    minimal_available_date = (
        minimal_available_date
        if not minimal_available_date or isinstance(minimal_available_date, datetime)
        else parse_datetime(minimal_available_date)
    )
    maximal_available_date = (
        maximal_available_date
        if not minimal_available_date or isinstance(maximal_available_date, datetime)
        else parse_datetime(maximal_available_date)
    )

    if minimal_available_date and maximal_available_date:
        if minimal_available_date > maximal_available_date:
            raise ValueError(
                "'minimal_available_date' has to be before " "'maximal_available_date'"
            )

    coords = Coordinates(np.array(latitude), np.array(longitude))

    metadata = metadata_for_climate_observations(
        parameter, time_resolution, period_type
    )

    # Filter only for stations that have a file
    metadata = metadata[metadata[DWDMetaColumns.HAS_FILE.value].values]

    if minimal_available_date:
        metadata = metadata[
            metadata[DWDMetaColumns.FROM_DATE.value] <= minimal_available_date
        ]

    if maximal_available_date:
        metadata = metadata[
            metadata[DWDMetaColumns.TO_DATE.value] >= maximal_available_date
        ]

    metadata = metadata.reset_index(drop=True)

    distances, indices_nearest_neighbours = _derive_nearest_neighbours(
        metadata.LAT.values, metadata.LON.values, coords, num_stations_nearby
    )

    distances = pd.Series(distances)
    indices_nearest_neighbours = pd.Series(indices_nearest_neighbours)

    # If num_stations_nearby is higher then the actual amount of stations
    # further indices and distances are added which have to be filtered out
    distances = distances[: min(metadata.shape[0], num_stations_nearby)]
    indices_nearest_neighbours = indices_nearest_neighbours[
        : min(metadata.shape[0], num_stations_nearby)
    ]

    distances_km = np.array(distances * KM_EARTH_RADIUS)

    metadata_location = metadata.iloc[indices_nearest_neighbours, :].reset_index(
        drop=True
    )

    metadata_location[DWDMetaColumns.DISTANCE_TO_LOCATION.value] = distances_km

    if metadata_location.empty:
        logger.warning(
            f"No weather stations were found for coordinate "
            f"{latitude}°N and {longitude}°E "
        )

    return metadata_location


def get_nearby_stations_by_distance(
    latitude: float,
    longitude: float,
    max_distance_in_km: float,
    parameter: Union[Parameter, str],
    time_resolution: Union[TimeResolution, str],
    period_type: Union[PeriodType, str],
    minimal_available_date: Optional[Union[datetime, str]] = None,
    maximal_available_date: Optional[Union[datetime, str]] = None,
) -> pd.DataFrame:
    """
    Provides a list of weather station ids for the requested data

    :param latitude:                Latitude of location to search for nearest
                                    weather station
    :param longitude:               Longitude of location to search for nearest
                                    weather station
    :param minimal_available_date:  Start date of timespan where measurements
                                    should be available
    :param maximal_available_date:  End date of timespan where measurements
                                    should be available
    :param parameter:               Observation measure
    :param time_resolution:         Frequency/granularity of measurement interval
    :param period_type:             Recent or historical files
    :param max_distance_in_km:      Alternative filtering criteria, maximum
                                    distance to location in km

    :return:                        DataFrames with valid stations in radius per
                                    requested location
    """
    # Theoretically a distance of 0 km is possible
    if max_distance_in_km < 0:
        raise ValueError("'max_distance_in_km' has to be at least 0.0.")

    metadata = metadata_for_climate_observations(
        parameter, time_resolution, period_type
    )

    all_nearby_stations = get_nearby_stations_by_number(
        latitude,
        longitude,
        metadata.shape[0],
        parameter,
        time_resolution,
        period_type,
        minimal_available_date,
        maximal_available_date,
    )

    nearby_stations_in_distance = all_nearby_stations[
        all_nearby_stations[DWDMetaColumns.DISTANCE_TO_LOCATION.value]
        <= max_distance_in_km
    ]

    return nearby_stations_in_distance.reset_index(drop=True)


def _derive_nearest_neighbours(
    latitudes_stations: np.array,
    longitudes_stations: np.array,
    coordinates: Coordinates,
    num_stations_nearby: int = 1,
) -> Tuple[Union[float, np.ndarray], np.ndarray]:
    """
    A function that uses a k-d tree algorithm to obtain the nearest
    neighbours to coordinate pairs

    Args:
        latitudes_stations (np.array): latitude values of stations being compared to
        the coordinates
        longitudes_stations (np.array): longitude values of stations being compared to
        the coordinates
        coordinates (Coordinates): the coordinates for which the nearest neighbour
        is searched
        num_stations_nearby: Number of stations that should be nearby

    Returns:
        Tuple of distances and ranks of nearest to most distant stations
    """
    points = np.c_[np.radians(latitudes_stations), np.radians(longitudes_stations)]
    distance_tree = cKDTree(points)
    return distance_tree.query(
        coordinates.get_coordinates_in_radians(), k=num_stations_nearby
    )
