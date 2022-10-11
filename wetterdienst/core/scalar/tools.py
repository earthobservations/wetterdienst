import pandas as pd


class _ParameterData:
    def __init__(self, values: pd.DataFrame, station_ids: list = None, extra_station_counter=0):
        self.station_ids = station_ids or []
        self.extra_station_counter = extra_station_counter
        self.values = values
        self.finished = False


def extract_station_values(
    param_data: _ParameterData, result_series_param: pd.Series, valid_station_groups_exists: bool
):
    # Three rules:
    # 1. only add further stations if not a minimum of 4 stations is reached OR
    # 2. a gain of 10% of timestamps with at least 4 existing values over all stations is seen OR
    # 3. an additional counter is below 3 (used if a station has really no or few values)

    cond1 = param_data.values.shape[1] < 4
    cond2 = not cond1 and gain_of_value_pairs(param_data.values, result_series_param) > 0.10
    if (
        not valid_station_groups_exists or cond1 or cond2 or param_data.extra_station_counter < 3
    ):  # timestamps + 4 stations
        if not (cond1 or cond2):
            param_data.extra_station_counter += 1

        param_data.values[result_series_param.name] = result_series_param.values
    else:
        param_data.finished = True


def gain_of_value_pairs(old_values: pd.DataFrame, new_values: pd.Series) -> float:
    old_score = old_values.apply(lambda row: row.dropna().size >= 4).sum()  # 5: dates plus 4 values
    old_values[new_values.name] = new_values.values  # Add new column
    new_score = old_values.apply(lambda row: row.dropna().size >= 4).sum()  # 5: dates plus 4 values
    return new_score / old_score - 1
