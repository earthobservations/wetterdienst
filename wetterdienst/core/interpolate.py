# Copyright (c) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Interpolation for weather data."""

from __future__ import annotations

import logging
from functools import lru_cache
from itertools import combinations
from queue import Queue
from typing import TYPE_CHECKING

import polars as pl
import utm
from scipy.interpolate import LinearNDInterpolator
from shapely.geometry import Point, Polygon
from tqdm import tqdm

from wetterdienst.core.util import _ParameterData, extract_station_values
from wetterdienst.metadata.parameter import Parameter
from wetterdienst.metadata.resolution import Frequency
from wetterdienst.util.logging import TqdmToLogger

if TYPE_CHECKING:
    from wetterdienst.model.request import TimeseriesRequest
    from wetterdienst.model.result import StationsResult

log = logging.getLogger(__name__)


def get_interpolated_df(request: TimeseriesRequest, latitude: float, longitude: float) -> pl.DataFrame:
    """Get the interpolated DataFrame for the given request and location."""
    utm_x, utm_y, _, _ = utm.from_latlon(latitude, longitude)
    stations_dict, param_dict = request_stations(request, latitude, longitude, utm_x, utm_y)
    return calculate_interpolation(
        utm_x, utm_y, stations_dict, param_dict, request.settings.ts_interp_use_nearby_station_distance
    )


def request_stations(
    request: TimeseriesRequest,
    latitude: float,
    longitude: float,
    utm_x: float,
    utm_y: float,
) -> tuple[dict, dict]:
    """Request the stations for the interpolation.

    Args:
        request: TimeseriesRequest object
        latitude: latitude of the point to interpolate
        longitude: longitude of the point to interpolate
        utm_x: longitude in UTM of the point to interpolate
        utm_y: latitude in UTM of the point to interpolate

    Returns:
        tuple containing the stations dict and the parameter dict

    """
    param_dict = {}
    stations_dict = {}
    parameter_names = {parameter.name for parameter in request.parameters}
    max_interp_distance = max(
        request.settings.ts_interp_station_distance[parameter_name] for parameter_name in parameter_names
    )
    stations_ranked = request.filter_by_distance(latlon=(latitude, longitude), distance=max_interp_distance)
    df_stations_ranked = stations_ranked.df
    tqdm_out = TqdmToLogger(log, level=logging.INFO)
    for station, result in tqdm(
        zip(df_stations_ranked.iter_rows(named=True), stations_ranked.values.query(), strict=False),
        total=len(df_stations_ranked),
        desc="querying stations for interpolation",
        unit="station",
        file=tqdm_out,
    ):
        valid_station_groups_exists = not get_valid_station_groups(stations_dict, utm_x, utm_y).empty()
        # check if all parameters found enough stations and the stations build a valid station group
        if len(param_dict) > 0 and all(param.finished for param in param_dict.values()) and valid_station_groups_exists:
            break
        if result.df.drop_nulls("value").is_empty():
            continue
        utm_x_station, utm_y_station = utm.from_latlon(station["latitude"], station["longitude"])[:2]
        stations_dict[station["station_id"]] = (utm_x_station, utm_y_station, station["distance"])
        apply_station_values_per_parameter(
            result.df,
            stations_ranked,
            param_dict,
            station,
            valid_station_groups_exists=valid_station_groups_exists,
        )
    return stations_dict, param_dict


def apply_station_values_per_parameter(
    result_df: pl.DataFrame,
    stations_ranked: StationsResult,
    param_dict: dict,
    station: dict,
    *,
    valid_station_groups_exists: bool,
) -> None:
    """Apply the station values to the parameter data.

    Args:
        result_df: DataFrame containing the station values
        stations_ranked: stations_result with stations ranked by distance
        param_dict: dict containing the parameter data
        station: dict containing the station data
        min_gain_of_value_pairs: minimum gain of value pairs to add a station
        num_additional_stations: number of additional stations to add if the gain is not reached
        valid_station_groups_exists: bool indicating if valid station groups exist

    Returns:
        None - the parameter data is updated in place

    """
    for parameter in stations_ranked.stations.parameters:
        if parameter.name not in stations_ranked.stations.interpolatable_parameters:
            log.info(f"parameter {parameter.name} can not be interpolated")
            continue
        ts_interpolation_station_distance = stations_ranked.stations.settings.ts_interp_station_distance
        if station["distance"] > ts_interpolation_station_distance[parameter.name.lower()]:
            log.info(f"Station for parameter {parameter.name} is too far away")
            continue
        if (parameter.dataset.resolution.name, parameter.dataset.name, parameter.name) in param_dict and param_dict[
            parameter.dataset.resolution.name,
            parameter.dataset.name,
            parameter.name,
        ].finished:
            continue
        # Filter only for exact parameter
        result_series_param = result_df.filter(
            pl.col("resolution").eq(parameter.dataset.resolution.name),
            pl.col("dataset").eq(parameter.dataset.name),
            pl.col("parameter").eq(parameter.name),
        )
        if result_series_param.drop_nulls("value").is_empty():
            continue
        if (parameter.dataset.resolution.name, parameter.dataset.name, parameter.name) not in param_dict:
            frequency = Frequency[parameter.dataset.resolution.value.name].value
            df = pl.DataFrame(
                {
                    "date": pl.datetime_range(
                        start=stations_ranked.stations.start_date,
                        end=stations_ranked.stations.end_date,
                        interval=frequency,
                        time_zone="UTC",
                        eager=True,
                    ).dt.round(frequency),
                },
                orient="col",
            )
            param_dict[parameter.dataset.resolution.name, parameter.dataset.name, parameter.name] = _ParameterData(df)
        result_series_param = (
            param_dict[parameter.dataset.resolution.name, parameter.dataset.name, parameter.name]
            .values.select("date")
            .join(result_series_param, on="date", how="left")
        )
        result_series_param = result_series_param.get_column("value")
        result_series_param = result_series_param.rename(station["station_id"])
        extract_station_values(
            param_dict[parameter.dataset.resolution.name, parameter.dataset.name, parameter.name],
            result_series_param,
            min_gain_of_value_pairs=stations_ranked.settings.ts_interp_min_gain_of_value_pairs,
            num_additional_stations=stations_ranked.settings.ts_interp_num_additional_stations,
            valid_station_groups_exists=valid_station_groups_exists,
        )


def calculate_interpolation(
    utm_x: float,
    utm_y: float,
    stations_dict: dict,
    param_dict: dict,
    use_nearby_station_distance: float,
) -> pl.DataFrame:
    """Calculate the interpolation for the given data.

    Args:
        utm_x: longitude in UTM
        utm_y: latitude in UTM
        stations_dict: dict containing the station data including the location
        param_dict: dict containing the parameter data
        use_nearby_station_distance: distance in km to use nearby stations for interpolation

    Returns:
        DataFrame containing the interpolated data

    """
    data = [
        pl.DataFrame(
            schema={
                "date": pl.Datetime(time_zone="UTC"),
                "resolution": pl.String,
                "dataset": pl.String,
                "parameter": pl.String,
                "value": pl.Float64,
                "distance_mean": pl.Float64,
                "taken_station_ids": pl.List(inner=pl.String),
            },
        ),
    ]
    valid_station_groups = get_valid_station_groups(stations_dict, utm_x, utm_y)
    nearby_stations = [
        station_id for station_id, (_, _, distance) in stations_dict.items() if distance < use_nearby_station_distance
    ]
    for (resolution, dataset, parameter), param_data in param_dict.items():
        param_df = pl.DataFrame({"date": param_data.values.get_column("date")})
        results = []
        for row in param_data.values.select(pl.all().exclude("date")).iter_rows(named=True):
            results.append(
                apply_interpolation(
                    row,
                    stations_dict,
                    valid_station_groups,
                    resolution,
                    dataset,
                    parameter,
                    utm_x,
                    utm_y,
                    nearby_stations,
                ),
            )
        results = pl.DataFrame(
            results,
            schema={
                "resolution": pl.String,
                "dataset": pl.String,
                "parameter": pl.String,
                "value": pl.Float64,
                "distance_mean": pl.Float64,
                "taken_station_ids": pl.List(inner=pl.String),
            },
            orient="row",
        )
        param_df = pl.concat([param_df, results], how="horizontal")
        data.append(param_df)
    df = pl.concat(data)
    df = df.with_columns(pl.col("value").round(2), pl.col("distance_mean").round(2))
    return df.sort(
        by=[
            "resolution",
            "dataset",
            "parameter",
            "date",
        ],
    )


def get_valid_station_groups(stations_dict: dict, utm_x: float, utm_y: float) -> Queue:
    """Get all valid station groups that cover the given point.

    Args:
        stations_dict: dict containing the station data including the location
        utm_x: longitude in UTM
        utm_y: latitude in UTM

    Returns:
        Queue containing the valid station groups

    """
    point = Point(utm_x, utm_y)
    valid_groups = Queue()
    # get all combinations of 4 stations
    for station_group in combinations(stations_dict.keys(), 4):
        coords = [(stations_dict[s][0], stations_dict[s][1]) for s in station_group]
        pol = Polygon(coords)
        if pol.covers(point):
            valid_groups.put(station_group)
    return valid_groups


@lru_cache
def get_station_group_ids(valid_station_groups: Queue, vals_index: frozenset) -> list:
    """Get the station group ids that are a subset of the given values."""
    for item in valid_station_groups.queue:
        if set(item).issubset(vals_index):
            return list(item)
    return []


def apply_interpolation(
    row: dict,
    stations_dict: dict,
    valid_station_groups: Queue,
    resolution: str,
    dataset: str,
    parameter: str,
    utm_x: float,
    utm_y: float,
    nearby_stations: list[str],
) -> tuple[str, str, str, float | None, float | None, list[str]]:
    """Apply interpolation to a row of data.

    Args:
        row: dict containing the data across collected stations for a specific date
        stations_dict: dict containing the station data including the location
        valid_station_groups: Queue containing the valid station groups to use for interpolation
        resolution: resolution name
        dataset: dataset name
        parameter: parameter name
        utm_x: longitude in UTM
        utm_y: latitude in UTM
        nearby_stations: list of nearby stations

    Returns:
        tuple containing the resolution name, dataset name, parameter name, interpolated value, mean distance of the
        stations used for interpolation and the station ids used for interpolation

    """
    if nearby_stations:
        valid_values = {s: v for s, v in row.items() if s in nearby_stations and v is not None}
        if valid_values:
            first_station = next(iter(valid_values.keys()))
            return (
                resolution,
                dataset,
                parameter,
                valid_values[first_station],
                stations_dict[first_station][2],
                [first_station],
            )
    vals = {s: v for s, v in row.items() if v is not None}
    station_group_ids = get_station_group_ids(valid_station_groups, frozenset(vals))
    vals = {s: v for s, v in vals.items() if s in station_group_ids} if station_group_ids else None
    if not vals or len(vals) < 4:
        return resolution, dataset, parameter, None, None, []
    xs, ys, distances = map(list, zip(*[stations_dict[station_id] for station_id in station_group_ids], strict=False))
    distance_mean = sum(distances) / len(distances)
    f = LinearNDInterpolator(points=(xs, ys), values=list(vals.values()))
    value = f(utm_x, utm_y)
    if parameter == Parameter.PRECIPITATION_HEIGHT.name.lower():
        f_index = LinearNDInterpolator(points=(xs, ys), values=[float(v > 0) for v in list(vals.values())])
        value_index = f_index(utm_x, utm_y)
        value = value if value_index >= 0.5 else 0
    return resolution, dataset, parameter, value, distance_mean, station_group_ids
