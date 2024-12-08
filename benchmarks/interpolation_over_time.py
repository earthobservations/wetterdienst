# Copyright (C) 2018-2023, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import os
from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import polars as pl
from sklearn.feature_selection import r_regression
from sklearn.metrics import root_mean_squared_error

from wetterdienst import Parameter
from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
    DwdObservationResolution,
)

plt.style.use("ggplot")


def get_interpolated_df(parameter: str, start_date: datetime, end_date: datetime) -> pl.DataFrame:
    stations = DwdObservationRequest(
        parameters=parameter,
        resolution=DwdObservationResolution.HOURLY,
        start_date=start_date,
        end_date=end_date,
    )
    return stations.interpolate(latlon=(50.0, 8.9)).df


def get_regular_df(parameter: str, start_date: datetime, end_date: datetime, exclude_stations: list) -> pl.DataFrame:
    stations = DwdObservationRequest(
        parameters=parameter,
        resolution=DwdObservationResolution.HOURLY,
        start_date=start_date,
        end_date=end_date,
    )
    request = stations.filter_by_distance(latlon=(50.0, 8.9), distance=30)
    df = request.values.all().df.drop_nulls()
    station_ids = df.get_column("station_id")
    first_station_id = set(station_ids).difference(set(exclude_stations)).pop()
    return df.filter(pl.col("station_id").eq(first_station_id))


def get_rmse(regular_values: pl.Series, interpolated_values: pl.Series) -> float:
    return root_mean_squared_error(
        regular_values.reshape((-1, 1)).to_list(),
        interpolated_values.reshape((-1, 1)).to_list(),
    )


def get_corr(regular_values: pl.Series, interpolated_values: pl.Series) -> float:
    return r_regression(
        regular_values.reshape((-1, 1)).to_list(),
        interpolated_values.reshape((-1, 1)).to_list(),
    ).item()


def visualize(parameter: str, unit: str, regular_df: pl.DataFrame, interpolated_df: pl.DataFrame):
    rmse = get_rmse(regular_df.get_column("value"), interpolated_df.get_column("value"))
    corr = get_corr(regular_df.get_column("value"), interpolated_df.get_column("value"))
    factor = 0.5
    plt.figure(figsize=(factor * 19.2, factor * 10.8))
    plt.plot(regular_df.get_column("date"), regular_df.get_column("value"), color="red", label="regular")
    plt.plot(
        interpolated_df.get_column("date"),
        interpolated_df.get_column("value"),
        color="black",
        label="interpolated",
    )
    ylabel = f"{parameter.lower()} [{unit}]"
    plt.ylabel(ylabel)
    title = (
        f"rmse: {np.round(rmse, 2)}, corr: {np.round(corr, 2)}\n"
        f"station_ids: {interpolated_df.get_column('taken_station_ids').to_list()[0]}"
    )
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    if "PYTEST_CURRENT_TEST" not in os.environ:
        plt.show()


def main():
    parameter = Parameter.TEMPERATURE_AIR_MEAN_2M.name
    unit = "K"
    start_date = datetime(2022, 3, 1)
    end_date = datetime(2022, 3, 31)
    interpolated_df = get_interpolated_df(parameter, start_date, end_date)
    exclude_stations = interpolated_df.get_column("taken_station_ids")[0]
    regular_df = get_regular_df(parameter, start_date, end_date, exclude_stations)
    visualize(parameter, unit, regular_df, interpolated_df)


if __name__ == "__main__":
    main()
