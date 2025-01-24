# Copyright (C) 2018-2023, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt
import os

import polars as pl

from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
)


def get_summarized_df(start_date: dt.datetime, end_date: dt.datetime, lat, lon) -> pl.DataFrame:
    stations = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start_date=start_date,
        end_date=end_date,
    )
    return stations.summarize(latlon=(lat, lon)).df


def get_regular_df(start_date: dt.datetime, end_date: dt.datetime, station_id) -> pl.DataFrame:
    stations = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "temperature_air_mean_2m")],
        start_date=start_date,
        end_date=end_date,
    )
    request = stations.filter_by_station_id(station_id)
    return request.values.all().df


def main():
    start_date = dt.datetime(1934, 1, 1)
    end_date = dt.datetime(1980, 12, 31)
    lat = 51.0221
    lon = 13.8470

    summarized_df = get_summarized_df(start_date, end_date, lat, lon)
    print(summarized_df)
    summarized_df = summarized_df.with_columns(
        pl.col("taken_station_id")
        .replace({"01050": "yellow", "01048": "green", "01051": "blue", "05282": "violet"})
        .alias("color"),
    )

    regular_df_01050 = get_regular_df(start_date, end_date, "01050")
    regular_df_01048 = get_regular_df(start_date, end_date, "01048")
    regular_df_01051 = get_regular_df(start_date, end_date, "01051")
    regular_df_05282 = get_regular_df(start_date, end_date, "05282")

    try:
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
    except ImportError as e:
        raise ImportError("Please install extra `plotting` with wetterdienst[plotting]") from e

    fig = make_subplots(rows=5, shared_xaxes=True, subplot_titles=("Summarized", "01050", "01051", "01048", "05282"))

    fig.add_trace(
        go.Scatter(
            x=summarized_df.get_column("date"),
            y=summarized_df.get_column("value"),
            mode="markers",
            marker=dict(color=summarized_df.get_column("color")),
            name="summarized",
        ),
        row=1,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=regular_df_01050.get_column("date"),
            y=regular_df_01050.get_column("value"),
            mode="lines",
            line=dict(color="yellow"),
            name="01050",
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=regular_df_01051.get_column("date"),
            y=regular_df_01051.get_column("value"),
            mode="lines",
            line=dict(color="blue"),
            name="01051",
        ),
        row=3,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=regular_df_01048.get_column("date"),
            y=regular_df_01048.get_column("value"),
            mode="lines",
            line=dict(color="green"),
            name="01048",
        ),
        row=4,
        col=1,
    )

    fig.add_trace(
        go.Scatter(
            x=regular_df_05282.get_column("date"),
            y=regular_df_05282.get_column("value"),
            mode="lines",
            line=dict(color="pink"),
            name="05282",
        ),
        row=5,
        col=1,
    )

    fig.update_layout(
        title="Comparison of summarized values and single stations for temperature_air_mean_2m",
        legend_title="Stations",
        showlegend=True,
    )

    if "PYTEST_CURRENT_TEST" not in os.environ:
        fig.show()


if __name__ == "__main__":
    main()
