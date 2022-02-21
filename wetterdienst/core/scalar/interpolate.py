# -*- coding: utf-8 -*-
# Copyright (c) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import logging

import numpy as np
import pandas as pd
import utm
from scipy import interpolate

from wetterdienst.metadata.columns import Columns

log = logging.getLogger(__name__)


class _ParameterData:
    def __init__(self, values: pd.DataFrame, station_ids: list = None, extra_station_counter=0):
        self.station_ids = station_ids if station_ids else []
        self.extra_station_counter = extra_station_counter
        self.values = values
        self.finished = False


def get_interpolated_df(
    stations_ranked, requested_x, requested_y, parameters, interpolatable_parameters
) -> pd.DataFrame:
    stations_dict, param_dict = request_stations(stations_ranked, interpolatable_parameters, parameters)
    return calculate_interpolation(requested_x, requested_y, stations_dict, param_dict)


def request_stations(stations_ranked, interpolatable_parameters, parameters) -> (dict, dict):
    param_dict = {}
    stations_dict = {}
    # TODO: add soft limit (soft_distance_km_limit = 20)
    hard_distance_km_limit = 40
    stations_ranked_df = stations_ranked.df.dropna()

    for (_, station), result in zip(stations_ranked_df.iterrows(), stations_ranked.values.query()):
        if station[Columns.DISTANCE.value] > hard_distance_km_limit:
            break

        # check if all parameters found enough stations
        if len(param_dict) > 0 and all(param.finished for param in param_dict.values()):
            break

        if result.df.dropna().empty:
            continue

        utm_x, utm_y = utm.from_latlon(station.latitude, station.longitude)[:2]
        stations_dict[station.station_id] = (utm_x, utm_y, station.distance)
        apply_station_values_per_parameter(
            result, stations_ranked, parameters, interpolatable_parameters, param_dict, station.station_id
        )

    return stations_dict, param_dict


def apply_station_values_per_parameter(
    result, stations_ranked, parameters, interpolatable_parameters, param_dict, station_id
):
    for parameter, dataset in parameters:
        if parameter == dataset:
            log.info("only individual parameters can be interpolated")
            continue

        if parameter.name not in interpolatable_parameters:
            log.info(f"parameter {parameter.name} can not be interpolated")
            continue

        parameter_name = parameter.name.lower()
        if parameter_name in param_dict and param_dict[parameter_name].finished:
            continue

        # Filter only for exact parameter
        result_df_param = result.df.loc[result.df[Columns.PARAMETER.value] == parameter_name]
        if result_df_param.dropna().empty:
            continue

        result_df_param = result_df_param.loc[:, Columns.VALUE.value]
        result_df_param.name = station_id

        if parameter_name not in param_dict:
            # TODO: this currently only works for a fixed timezone
            param_dict[parameter_name] = _ParameterData(
                stations_ranked.values._get_base_df("").set_index(Columns.DATE.value)
            )

        extract_station_values(param_dict[parameter_name], result_df_param, station_id)


def extract_station_values(param_data, result_df_param, station_id):
    # Three rules:
    # 1. only add further stations if not a minimum of 4 stations is reached OR
    # 2. a gain of 10% of timestamps with at least 4 existing values over all stations is seen OR
    # 3. an additional counter is below 3 (used if a station has really no or few values)

    cond1 = param_data.values.shape[1] < 4
    cond2 = not cond1 and gain_of_value_pairs(param_data.values, result_df_param) > 0.10
    if cond1 or cond2 or param_data.extra_station_counter < 3:  # timestamps + 4 stations
        if not (cond1 or cond2):
            param_data.extra_station_counter += 1

        param_data.values[result_df_param.name] = result_df_param.values
        param_data.station_ids.append(station_id)
    else:
        param_data.finished = True


def gain_of_value_pairs(old_values: pd.DataFrame, new_values: pd.Series) -> float:
    old_score = old_values.apply(lambda row: row.dropna().size >= 4).sum()  # 5: dates plus 4 values
    old_values[new_values.name] = new_values.values  # Add new column
    new_score = old_values.apply(lambda row: row.dropna().size >= 4).sum()  # 5: dates plus 4 values
    return new_score / old_score - 1


def calculate_interpolation(requested_x, requested_y, stations_dict, param_dict) -> pd.DataFrame:
    columns = [
        Columns.DATE.value,
        Columns.PARAMETER.value,
        Columns.VALUE.value,
        Columns.DISTANCE_MEAN.value,
        Columns.STATION_IDS.value,
    ]
    param_df_list = [pd.DataFrame(columns=columns)]

    for parameter, param_data in param_dict.items():
        param_df = pd.DataFrame(columns=columns)
        param_df[columns[1:]] = param_data.values.apply(
            lambda row: apply_interpolation(
                row, param_data.station_ids, stations_dict, parameter, requested_x, requested_y
            ),
            axis=1,
            result_type="expand",
        )
        param_df[Columns.DATE.value] = param_data.values.index
        param_df_list.append(param_df)

    return pd.concat(param_df_list).sort_values(by=[Columns.DATE.value, Columns.PARAMETER.value]).reset_index(drop=True)


def apply_interpolation(row, all_station_ids, stations_dict, parameter, requested_x, requested_y):
    vals = row.values[~np.isnan(row.values)][:4]
    value = pd.NA
    distance_mean = pd.NA
    station_ids = pd.NA

    if vals.size < 4:
        return parameter, value, distance_mean, station_ids

    station_idx = np.arange(row.values.size)[~np.isnan(row.values)][:4]
    station_ids = np.array(all_station_ids)[station_idx]

    xs, ys, distances = map(np.float64, zip(*[stations_dict[station_id] for station_id in station_ids]))
    distance_mean = distances.mean()

    f = interpolate.interp2d(ys, xs, vals, kind="linear")
    value = np.float64(f(requested_y, requested_x)[0])  # there is only one interpolation result

    return parameter, value, distance_mean, station_ids
