""" calculates the nearest weather station to a requested location"""
from typing import List, Union, Tuple, Optional
import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

from wetterdienst.enumerations.column_names_enumeration import DWDMetaColumns
from wetterdienst.exceptions import InvalidParameterCombination
from wetterdienst.parse_metadata import metadata_for_climate_observations
from wetterdienst.additionals.functions import (
    check_parameters,
    parse_enumeration_from_template,
    cast_to_list,
)
from wetterdienst.data_models.coordinates import Coordinates
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution

KM_EARTH_RADIUS = 6371


def get_nearby_stations(
    latitudes: Union[List[float], np.array],
    longitudes: Union[List[float], np.array],
    parameter: Union[Parameter, str],
    time_resolution: Union[TimeResolution, str],
    period_type: Union[PeriodType, str],
    num_stations_nearby: Optional[int] = None,
    max_distance_in_km: Optional[float] = None,
) -> Tuple[List[int], List[List[float]]]:
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
        max_distance_in_km: alternative filtering criteria, maximum
            distance to location in km

    Returns:
        list of stations ids for the given locations/coordinate pairs and
        a list of distances in kilometer to the weather station

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

    if not check_parameters(parameter, time_resolution, period_type):
        raise InvalidParameterCombination(
            f"The combination of {parameter.value}, {time_resolution.value}, "
            f"{period_type.value} is invalid."
        )

    if not isinstance(latitudes, list):
        latitudes = np.array(latitudes)

    if not isinstance(longitudes, list):
        latitudes = np.array(longitudes)

    coords = Coordinates(latitudes, longitudes)

    metadata = metadata_for_climate_observations(
        parameter, time_resolution, period_type
    )

    # For distance filtering make normal query including all stations
    if max_distance_in_km:
        num_stations_nearby = metadata.shape[0]

    distances, indices_nearest_neighbours = _derive_nearest_neighbours(
        metadata.LAT.values, metadata.LON.values, coords, num_stations_nearby
    )

    # Make sure go get list of lists [[dist1_1, dist1_2], [dist2_1, dist2_2]]
    if num_stations_nearby == 1:
        distances = np.array([distances])
    else:
        distances = distances.T

    if np.max(indices_nearest_neighbours.shape) > 1:
        indices_nearest_neighbours = indices_nearest_neighbours[0]

    # Require list of indices for consistency
    # Cast to np.array required for subset
    indices_nearest_neighbours = np.array(cast_to_list(indices_nearest_neighbours))

    distances_km = np.array(distances * KM_EARTH_RADIUS)

    # Filter for distance based on calculated distances
    if max_distance_in_km:
        indices_stations_in_distance = (
            np.max(distances_km, axis=1) <= max_distance_in_km
        )

        # Reduce stations to those in distance
        distances_km = distances_km[indices_stations_in_distance]
        indices_nearest_neighbours = indices_nearest_neighbours[
            indices_stations_in_distance
        ]

    return (
        metadata.loc[
            indices_nearest_neighbours, DWDMetaColumns.STATION_ID.value
        ].values.tolist(),
        distances_km.tolist(),
    )


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

    :param df: Input DataFrame containing station information.
    :return: Dictionary in GeoJSON FeatureCollection format.
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

    data = {
        "type": "FeatureCollection",
        "features": features,
    }

    return data
