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
    cast_to_list,
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


def get_nearby_stations(
    latitude: float,
    longitude: float,
    minimal_available_date: Union[datetime, str],
    maximal_available_date: Union[datetime, str],
    parameter: Union[Parameter, str],
    time_resolution: Union[TimeResolution, str],
    period_type: Union[PeriodType, str],
    num_stations_nearby: Optional[int] = None,
    max_distance_in_km: Optional[float] = None
) -> pd.DataFrame:
    """
    Provides a list of weather station ids for the requested data
    Args:
        latitude: latitude of location to search for nearest
            weather station
        longitude: longitude of location to search for nearest
            weather station
        minimal_available_date: Start date of timespan where measurements
            should be available
        maximal_available_date: End date of timespan where measurements
            should be available
        parameter: observation measure
        time_resolution: frequency/granularity of measurement interval
        period_type: recent or historical files
        num_stations_nearby: Number of stations that should be nearby
        max_distance_in_km: alternative filtering criteria, maximum
            distance to location in km

    Returns:
        DataFrames with valid Stations in radius per requested location

    """
    if (num_stations_nearby and max_distance_in_km) and (
        num_stations_nearby and max_distance_in_km
    ):
        raise ValueError("Either set 'num_stations_nearby' or 'max_distance_in_km'.")

    if num_stations_nearby == 0:
        raise ValueError("'num_stations_nearby' has to be at least 1.")

    parameter = parse_enumeration_from_template(parameter, Parameter)
    time_resolution = parse_enumeration_from_template(time_resolution, TimeResolution)
    period_type = parse_enumeration_from_template(period_type, PeriodType)
    minimal_available_date = (
        minimal_available_date
        if isinstance(minimal_available_date, datetime)
        else parse_datetime(minimal_available_date)
    )
    maximal_available_date = (
        maximal_available_date
        if isinstance(maximal_available_date, datetime)
        else parse_datetime(maximal_available_date)
    )

    if not check_parameters(parameter, time_resolution, period_type):
        raise InvalidParameterCombination(
            f"The combination of {parameter.value}, {time_resolution.value}, "
            f"{period_type.value} is invalid."
        )

    coords = Coordinates(np.array(latitude), np.array(longitude))

    metadata = metadata_for_climate_observations(
        parameter, time_resolution, period_type
    )

    metadata = metadata[
        (metadata[DWDMetaColumns.FROM_DATE.value] <= minimal_available_date)
        & (metadata[DWDMetaColumns.TO_DATE.value] >= maximal_available_date)
    ].reset_index(drop=True)

    # For distance filtering make normal query including all stations
    if max_distance_in_km:
        num_stations_nearby = metadata.shape[0]

    distances, indices_nearest_neighbours = _derive_nearest_neighbours(
        metadata.LAT.values, metadata.LON.values, coords, num_stations_nearby
    )

    # Require list of indices for consistency
    # Cast to np.array required for subset
    indices_nearest_neighbours = np.array(cast_to_list(indices_nearest_neighbours))
    distances_km = np.array(distances * KM_EARTH_RADIUS)

    # Filter for distance based on calculated distances
    if max_distance_in_km:
        _in_max_distance_indices = np.where(distances_km <= max_distance_in_km)[0]
        indices_nearest_neighbours = indices_nearest_neighbours[
            _in_max_distance_indices
        ]
        distances_km = distances_km[_in_max_distance_indices]

    metadata_location = metadata.loc[
        indices_nearest_neighbours
        if isinstance(indices_nearest_neighbours, (list, np.ndarray))
        else [indices_nearest_neighbours],
        :,
    ]
    metadata_location["DISTANCE_TO_LOCATION"] = distances_km

    if metadata_location.empty:
        logger.warning(
            f"No weather station was found for coordinate "
            f"{latitude}°N and {longitude}°E "
        )

    return metadata_location


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


def stations_to_geojson(df: pd.DataFrame) -> dict:
    """
    Convert DWD station information into GeoJSON format.

    Args:
        df: Input DataFrame containing station information.

    Return:
         Dictionary in GeoJSON FeatureCollection format.
    """
    df = df.rename(columns=str.lower)

    features = []
    for _, station in df.iterrows():
        features.append(
            {
                "type": "Feature",
                "properties": {
                    "id": station["station_id"],
                    "name": station["station_name"],
                    "state": station["state"],
                    "from_date": station["from_date"].isoformat(),
                    "to_date": station["to_date"].isoformat(),
                    "has_file": station["has_file"],
                },
                "geometry": {
                    # WGS84 is implied and coordinates represent decimal degrees ordered
                    # as "longitude, latitude [,elevation]" with z expressed as metres
                    # above mean sea level per WGS84.
                    # -- http://wiki.geojson.org/RFC-001
                    "type": "Point",
                    "coordinates": [
                        station["lon"],
                        station["lat"],
                        station["station_height"],
                    ],
                },
            }
        )

    return {
        "type": "FeatureCollection",
        "features": features,
    }
