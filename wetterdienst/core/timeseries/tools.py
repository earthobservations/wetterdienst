from __future__ import annotations

import polars as pl


class _ParameterData:
    def __init__(self, values: pl.DataFrame, station_ids: list[str] | None = None, extra_station_counter: int = 0):
        self.station_ids = station_ids or []
        self.extra_station_counter = extra_station_counter
        self.values = values
        self.finished = False


def extract_station_values(
    param_data: _ParameterData,
    result_series_param: pl.Series,
    valid_station_groups_exists: bool,
) -> None:
    # Three rules:
    # 1. only add further stations if not a minimum of 4 stations is reached OR
    # 2. a gain of 10% of timestamps with at least 4 existing values over all stations is seen OR
    # 3. an additional stations_counter is below 3 (used if a station has really no or few values)
    cond1 = param_data.values.shape[1] < 4
    cond2 = not cond1 and gain_of_value_pairs(param_data.values, result_series_param) > 0.10
    if (
        not valid_station_groups_exists or cond1 or cond2 or param_data.extra_station_counter < 3
    ):  # timestamps + 4 stations
        if not (cond1 or cond2):
            param_data.extra_station_counter += 1
        # "S" is added to station id titles to prevent bug with pandas that somehow doesn't allow column name "02000"
        # under certain circumstances
        param_data.values = param_data.values.with_columns(
            pl.lit(result_series_param).alias(f"S{result_series_param.name}"),
        )
    else:
        param_data.finished = True


def gain_of_value_pairs(old_values: pl.DataFrame, new_values: pl.Series) -> float:
    old_score = (
        old_values.select(pl.fold(acc=0, function=lambda acc, s: acc + s.is_not_null(), exprs=pl.all()) >= 4)
        .sum()
        .item()
    )  # 5: dates plus 4 values
    old_values = old_values.with_columns(pl.lit(new_values).alias(f"S{new_values.name}"))
    new_score = (
        old_values.select(pl.fold(acc=0, function=lambda acc, s: acc + s.is_not_null(), exprs=pl.all()) >= 4)
        .sum()
        .item()
    )  # 5: dates plus 4 values
    if old_score == 0:
        if new_score == 0:
            return 0.0
        return 1.0
    return new_score / old_score - 1.0
