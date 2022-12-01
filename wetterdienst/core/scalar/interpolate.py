# -*- coding: utf-8 -*-
# Copyright (c) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import logging
from datetime import datetime
from enum import Enum
from functools import lru_cache
from itertools import combinations
from queue import Queue
from typing import TYPE_CHECKING, List, Tuple

import numpy as np
import pandas as pd
import utm
from scipy import interpolate
from shapely.geometry import Point, Polygon

from wetterdienst.core.scalar.tools import _ParameterData, extract_station_values
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.parameter import Parameter

if TYPE_CHECKING:
    from wetterdienst.core.scalar.request import ScalarRequestCore
    from wetterdienst.core.scalar.result import StationsResult

log = logging.getLogger(__name__)


def get_interpolated_df(request: "ScalarRequestCore", latitude: float, longitude: float) -> pd.DataFrame:
    utm_x, utm_y, _, _ = utm.from_latlon(latitude, longitude)
    stations_dict, param_dict = request_stations(request, latitude, longitude, utm_x, utm_y)
    df = calculate_interpolation(utm_x, utm_y, stations_dict, param_dict, request.interp_use_nearby_station_until_km)
    df[Columns.DISTANCE_MEAN.value] = pd.Series(df[Columns.DISTANCE_MEAN.value].values, dtype=float)
    df[Columns.VALUE.value] = pd.Series(df[Columns.VALUE.value].values, dtype=float)
    df[Columns.DATE.value] = pd.to_datetime(df[Columns.DATE.value], infer_datetime_format=True)
    return df


def request_stations(
    request: "ScalarRequestCore", latitude: float, longitude: float, utm_x: float, utm_y: float
) -> Tuple[dict, dict]:
    param_dict = {}
    stations_dict = {}
    hard_distance_km_limit = 40
    stations_ranked = request.filter_by_rank(latlon=(latitude, longitude), rank=20)
    stations_ranked_df = stations_ranked.df.dropna()

    for (_, station), result in zip(stations_ranked_df.iterrows(), stations_ranked.values.query()):
        if station[Columns.DISTANCE.value] > hard_distance_km_limit:
            break

        valid_station_groups_exists = not get_valid_station_groups(stations_dict, utm_x, utm_y).empty()
        # check if all parameters found enough stations and the stations build a valid station group
        if len(param_dict) > 0 and all(param.finished for param in param_dict.values()) and valid_station_groups_exists:
            break

        if result.df.dropna().empty:
            continue

        # convert to utc
        result.df.date = result.df.date.dt.tz_convert("UTC")

        utm_x, utm_y = utm.from_latlon(station.latitude, station.longitude)[:2]
        stations_dict[station.station_id] = (utm_x, utm_y, station.distance)
        apply_station_values_per_parameter(result.df, stations_ranked, param_dict, station, valid_station_groups_exists)

    return stations_dict, param_dict


def apply_station_values_per_parameter(
    result_df: pd.DataFrame,
    stations_ranked: "StationsResult",
    param_dict: dict,
    station: pd.Series,
    valid_station_groups_exists: bool,
):
    km_limit = {
        Parameter.TEMPERATURE_AIR_MEAN_200.name: 40,
        Parameter.WIND_SPEED.name: 40,
        Parameter.PRECIPITATION_HEIGHT.name: 20,
    }

    for parameter, dataset in stations_ranked.stations.parameter:
        if parameter == dataset:
            log.info("only individual parameters can be interpolated")
            continue

        if parameter.name not in stations_ranked.stations.interpolatable_parameters:
            log.info(f"parameter {parameter.name} can not be interpolated")
            continue

        if station.distance > km_limit[parameter.name]:
            log.info(f"Station for parameter {parameter.name} is too far away")
            continue

        parameter_name = parameter.name.lower()
        if parameter_name in param_dict and param_dict[parameter_name].finished:
            continue

        # Filter only for exact parameter
        result_series_param = result_df.loc[result_df[Columns.PARAMETER.value] == parameter_name]
        if result_series_param.dropna().empty:
            continue

        result_series_param = result_series_param.loc[:, Columns.VALUE.value]
        result_series_param.name = station.station_id

        if parameter_name not in param_dict:
            param_dict[parameter_name] = _ParameterData(
                pd.DataFrame(
                    {
                        Columns.DATE.value: pd.date_range(
                            start=stations_ranked.stations.start_date,
                            end=stations_ranked.stations.end_date,
                            freq=stations_ranked.frequency.value,
                            tz="UTC",
                        )
                    }
                )
                .set_index(Columns.DATE.value)
                .astype("datetime64")
            )
        extract_station_values(param_dict[parameter_name], result_series_param, valid_station_groups_exists)


def calculate_interpolation(
    utm_x: float,
    utm_y: float,
    stations_dict: dict,
    param_dict: dict,
    use_nearby_station_until_km: float,
) -> pd.DataFrame:
    columns = [
        Columns.DATE.value,
        Columns.PARAMETER.value,
        Columns.VALUE.value,
        Columns.DISTANCE_MEAN.value,
        Columns.STATION_IDS.value,
    ]
    param_df_list = [pd.DataFrame(columns=columns)]
    valid_station_groups = get_valid_station_groups(stations_dict, utm_x, utm_y)

    nearby_stations = [
        "S" + station_id
        for station_id, (_, _, distance) in stations_dict.items()
        if distance < use_nearby_station_until_km
    ]

    for parameter, param_data in param_dict.items():
        param_df = pd.DataFrame(columns=columns)
        param_df[columns[1:]] = param_data.values.apply(
            lambda row, param=parameter: apply_interpolation(
                row, stations_dict, valid_station_groups, param, utm_x, utm_y, nearby_stations
            ),
            axis=1,
            result_type="expand",
        )
        param_df[Columns.DATE.value] = param_data.values.index
        param_df_list.append(param_df)

    return pd.concat(param_df_list).sort_values(by=[Columns.DATE.value, Columns.PARAMETER.value]).reset_index(drop=True)


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
    row,
    stations_dict: dict,
    valid_station_groups: Queue,
    parameter: Enum,
    utm_x: float,
    utm_y: float,
    nearby_stations: List[str],
) -> Tuple[Enum, float, float, List[str]]:
    """
    Interpolation function that is being applied over each row of the accumulated data of different stations.
    :param row: row with values of each station
    :param stations_dict: station dictionary with latlon pairs
    :param valid_station_groups: list of valid station groups
    :param parameter: parameter that is interpolated
    :param utm_x: utm x of interpolated location
    :param utm_y: utm y of interpolated location
    :param use_nearby_station: bool if the nearest station should be used. depends on distance
    :return:
    """
    if nearby_stations:
        valid_values = row[nearby_stations].dropna()
        if not valid_values.empty:
            first_station = valid_values.index[0]
            return parameter, valid_values[first_station], stations_dict[first_station[1:]][2], [first_station[1:]]
    vals_state = ~pd.isna(row.values)
    vals = row[vals_state].astype(float)
    station_group_ids = get_station_group_ids(valid_station_groups, frozenset([s[1:] for s in vals.index]))

    if station_group_ids:
        station_group_ids_with_s = ["S" + s for s in station_group_ids]
        vals = vals[station_group_ids_with_s]
    else:
        vals = None

    value = np.nan
    distance_mean = np.nan

    if vals is None or vals.size < 4:
        return parameter, value, distance_mean, station_group_ids

    xs, ys, distances = map(list, zip(*[stations_dict[station_id] for station_id in station_group_ids]))
    distance_mean = sum(distances) / len(distances)

    f = interpolate.interp2d(xs, ys, vals, kind="linear")
    value = f(utm_x, utm_y)[0]  # there is only one interpolation result

    if parameter == Parameter.PRECIPITATION_HEIGHT.name.lower():
        f_index = interpolate.interp2d(ys, xs, vals > 0, kind="linear")
        value_index = f_index(utm_x, utm_y)[0]  # there is only one interpolation result
        value_index = 1 if value_index >= 0.5 else 0
        value *= value_index

    return parameter, value, distance_mean, station_group_ids


if __name__ == "__main__":
    from wetterdienst.provider.dwd.observation import DwdObservationRequest

    lat = 50.0
    lon = 8.9
    distance = 30.0
    start_date = datetime(2003, 1, 1)
    end_date = datetime(2004, 12, 31)

    stations = DwdObservationRequest(
        parameter="temperature_air_mean_200",
        resolution="hourly",
        start_date=start_date,
        end_date=end_date,
    )

    df = stations.interpolate((lat, lon))

    log.info(df.df.dropna())
