# Copyright (c) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
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

from wetterdienst.core.timeseries.tools import _ParameterData, extract_station_values
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.parameter import Parameter
from wetterdienst.metadata.resolution import Frequency
from wetterdienst.util.logging import TqdmToLogger

if TYPE_CHECKING:
    from wetterdienst.core.timeseries.request import TimeseriesRequest
    from wetterdienst.core.timeseries.result import StationsResult

log = logging.getLogger(__name__)


def get_interpolated_df(request: TimeseriesRequest, latitude: float, longitude: float) -> pl.DataFrame:
    utm_x, utm_y, _, _ = utm.from_latlon(latitude, longitude)
    stations_dict, param_dict = request_stations(request, latitude, longitude, utm_x, utm_y)
    return calculate_interpolation(utm_x, utm_y, stations_dict, param_dict, request.interp_use_nearby_station_until_km)


def request_stations(
    request: TimeseriesRequest,
    latitude: float,
    longitude: float,
    utm_x: float,
    utm_y: float,
) -> tuple[dict, dict]:
    param_dict = {}
    stations_dict = {}
    distance = max(request.settings.ts_interpolation_station_distance.values())
    stations_ranked = request.filter_by_distance(latlon=(latitude, longitude), distance=distance)
    df_stations_ranked = stations_ranked.df
    tqdm_out = TqdmToLogger(log, level=logging.INFO)
    for station, result in tqdm(
        zip(df_stations_ranked.iter_rows(named=True), stations_ranked.values.query()),
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
        utm_x, utm_y = utm.from_latlon(station["latitude"], station["longitude"])[:2]
        stations_dict[station["station_id"]] = (utm_x, utm_y, station["distance"])
        apply_station_values_per_parameter(result.df, stations_ranked, param_dict, station, valid_station_groups_exists)
    return stations_dict, param_dict


def apply_station_values_per_parameter(
    result_df: pl.DataFrame,
    stations_ranked: StationsResult,
    param_dict: dict,
    station: dict,
    *,
    valid_station_groups_exists: bool,
) -> None:
    for parameter in stations_ranked.stations.parameters:
        if parameter.name not in stations_ranked.stations.interpolatable_parameters:
            log.info(f"parameter {parameter.name} can not be interpolated")
            continue
        ts_interpolation_station_distance = stations_ranked.stations.settings.ts_interpolation_station_distance
        if station["distance"] > ts_interpolation_station_distance.get(
            parameter.name.lower(),
            ts_interpolation_station_distance["default"],
        ):
            log.info(f"Station for parameter {parameter.name} is too far away")
            continue
        if (parameter.dataset.name, parameter.name) in param_dict and param_dict[
            (parameter.dataset.name, parameter.name)
        ].finished:
            continue
        # Filter only for exact parameter
        result_series_param = result_df.filter(
            pl.col(Columns.DATASET.value).eq(parameter.dataset.name), pl.col(Columns.PARAMETER.value).eq(parameter.name)
        )
        if result_series_param.drop_nulls("value").is_empty():
            continue
        if (parameter.dataset.name, parameter.name) not in param_dict:
            frequency = Frequency[parameter.dataset.resolution.value.name].value
            df = pl.DataFrame(
                {
                    Columns.DATE.value: pl.datetime_range(
                        start=stations_ranked.stations.start_date,
                        end=stations_ranked.stations.end_date,
                        interval=frequency,
                        time_zone="UTC",
                        eager=True,
                    ).dt.round(frequency),
                },
                orient="col",
            )
            param_dict[(parameter.dataset.name, parameter.name)] = _ParameterData(df)
        result_series_param = (
            param_dict[(parameter.dataset.name, parameter.name)]
            .values.select("date")
            .join(result_series_param, on="date", how="left")
        )
        result_series_param = result_series_param.get_column(Columns.VALUE.value)
        result_series_param = result_series_param.rename(station["station_id"])
        extract_station_values(
            param_dict[(parameter.dataset.name, parameter.name)], result_series_param, valid_station_groups_exists
        )


def calculate_interpolation(
    utm_x: float,
    utm_y: float,
    stations_dict: dict,
    param_dict: dict,
    use_nearby_station_until_km: float,
) -> pl.DataFrame:
    data = [
        pl.DataFrame(
            schema={
                Columns.DATE.value: pl.Datetime(time_zone="UTC"),
                Columns.DATASET.value: pl.String,
                Columns.PARAMETER.value: pl.String,
                Columns.VALUE.value: pl.Float64,
                Columns.DISTANCE_MEAN.value: pl.Float64,
                Columns.TAKEN_STATION_IDS.value: pl.List(inner=pl.String),
            },
        ),
    ]
    valid_station_groups = get_valid_station_groups(stations_dict, utm_x, utm_y)
    nearby_stations = [
        "S" + station_id
        for station_id, (_, _, distance) in stations_dict.items()
        if distance < use_nearby_station_until_km
    ]
    for (dataset, parameter), param_data in param_dict.items():
        param_df = pl.DataFrame({Columns.DATE.value: param_data.values.get_column(Columns.DATE.value)})
        results = []
        for row in param_data.values.select(pl.all().exclude("date")).iter_rows(named=True):
            results.append(
                apply_interpolation(
                    row, stations_dict, valid_station_groups, dataset, parameter, utm_x, utm_y, nearby_stations
                ),
            )
        results = pl.DataFrame(
            results,
            schema={
                Columns.DATASET.value: pl.String,
                Columns.PARAMETER.value: pl.String,
                Columns.VALUE.value: pl.Float64,
                Columns.DISTANCE_MEAN.value: pl.Float64,
                Columns.TAKEN_STATION_IDS.value: pl.List(inner=pl.String),
            },
            orient="row",
        )
        param_df = pl.concat([param_df, results], how="horizontal")
        data.append(param_df)
    df = pl.concat(data)
    df = df.with_columns(pl.col(Columns.VALUE.value).round(2), pl.col(Columns.DISTANCE_MEAN.value).round(2))
    return df.sort(
        by=[
            Columns.DATASET.value,
            Columns.PARAMETER.value,
            Columns.DATE.value,
        ],
    )


def get_valid_station_groups(stations_dict: dict, utm_x: float, utm_y: float) -> Queue:
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
    for item in valid_station_groups.queue:
        if set(item).issubset(vals_index):
            return list(item)
    return []


def apply_interpolation(
    row: dict,
    stations_dict: dict,
    valid_station_groups: Queue,
    dataset: str,
    parameter: str,
    utm_x: float,
    utm_y: float,
    nearby_stations: list[str],
) -> tuple[str, str, float | None, float | None, list[str]]:
    """
    Interpolation function that is being applied over each row of the accumulated data of different stations.
    :param row: row with values of each station
    :param stations_dict: station dictionary with latlon pairs
    :param valid_station_groups: list of valid station groups
    :param dataset: dataset of interpolated location
    :param parameter: parameter that is interpolated
    :param utm_x: utm x of interpolated location
    :param utm_y: utm y of interpolated location
    :param nearby_stations: list of nearby stations, propagated in the caller and if existing no interpolation is done
    :return:
    """
    if nearby_stations:
        valid_values = {s: v for s, v in row.items() if s in nearby_stations and v is not None}
        if valid_values:
            first_station = list(valid_values.keys())[0]
            return (
                dataset,
                parameter,
                valid_values[first_station],
                stations_dict[first_station[1:]][2],
                [first_station[1:]],
            )
    vals = {s: v for s, v in row.items() if v is not None}
    station_group_ids = get_station_group_ids(valid_station_groups, frozenset([s[1:] for s in vals.keys()]))
    if station_group_ids:
        station_group_ids_with_s = ["S" + s for s in station_group_ids]
        vals = {s: v for s, v in vals.items() if s in station_group_ids_with_s}
    else:
        vals = None
    if not vals or len(vals) < 4:
        return dataset, parameter, None, None, []
    xs, ys, distances = map(list, zip(*[stations_dict[station_id] for station_id in station_group_ids]))
    distance_mean = sum(distances) / len(distances)
    f = LinearNDInterpolator(points=(xs, ys), values=list(vals.values()))
    value = f(utm_x, utm_y)
    if parameter == Parameter.PRECIPITATION_HEIGHT.name.lower():
        f_index = LinearNDInterpolator(points=(xs, ys), values=[float(v > 0) for v in list(vals.values())])
        value_index = f_index(utm_x, utm_y)
        value = value if value_index >= 0.5 else 0
    return dataset, parameter, value, distance_mean, station_group_ids
