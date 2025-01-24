# Copyright (C) 2018-2023, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt
import os

import numpy as np
import polars as pl
from sklearn.feature_selection import r_regression
from sklearn.metrics import root_mean_squared_error

from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
)


def get_interpolated_df(
    parameters: tuple[str, str, str], start_date: dt.datetime, end_date: dt.datetime
) -> pl.DataFrame:
    stations = DwdObservationRequest(
        parameters=parameters,
        start_date=start_date,
        end_date=end_date,
    )
    return stations.interpolate(latlon=(50.0, 8.9)).df


def get_regular_df(
    parameters: tuple[str, str, str], start_date: dt.datetime, end_date: dt.datetime, exclude_stations: list
) -> pl.DataFrame:
    stations = DwdObservationRequest(
        parameters=parameters,
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


def visualize(parameter: tuple[str, str, str], unit: str, regular_df: pl.DataFrame, interpolated_df: pl.DataFrame):
    try:
        import plotly.graph_objects as go
    except ImportError as e:
        raise ImportError("Please install extra `plotting` with wetterdienst[plotting]") from e

    rmse = get_rmse(regular_df.get_column("value"), interpolated_df.get_column("value"))
    corr = get_corr(regular_df.get_column("value"), interpolated_df.get_column("value"))
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=regular_df.get_column("date"),
            y=regular_df.get_column("value"),
            mode="lines",
            name="regular",
            line=dict(color="red"),
        )
    )
    fig.add_trace(
        go.Scatter(
            x=interpolated_df.get_column("date"),
            y=interpolated_df.get_column("value"),
            mode="lines",
            name="interpolated",
            line=dict(color="black"),
        )
    )

    ylabel = f"{parameter[-1].lower()} [{unit}]"
    title = (
        f"rmse: {np.round(rmse, 2)}, corr: {np.round(corr, 2)}\n"
        f"station_ids: {interpolated_df.get_column('taken_station_ids').to_list()[0]}"
    )

    fig.update_layout(
        title=title, xaxis_title="Date", yaxis_title=ylabel, legend=dict(x=0, y=1), margin=dict(l=40, r=40, t=40, b=40)
    )

    if "PYTEST_CURRENT_TEST" not in os.environ:
        fig.show()


def main():
    parameter = ("hourly", "air_temperature", "temperature_air_mean_2m")
    unit = "K"
    start_date = dt.datetime(2022, 3, 1)
    end_date = dt.datetime(2022, 3, 31)
    interpolated_df = get_interpolated_df(parameter, start_date, end_date)
    exclude_stations = interpolated_df.get_column("taken_station_ids")[0]
    regular_df = get_regular_df(parameter, start_date, end_date, exclude_stations)
    visualize(parameter, unit, regular_df, interpolated_df)


if __name__ == "__main__":
    main()
