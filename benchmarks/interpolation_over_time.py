# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Benchmark interpolation over time."""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import polars as pl
from sklearn.feature_selection import r_regression
from sklearn.metrics import root_mean_squared_error

from wetterdienst.io.charts import DEFAULT_HEIGHT, DEFAULT_WIDTH, FONT, altair
from wetterdienst.io.export import render_image
from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
)

if TYPE_CHECKING:
    import altair as alt

#: where the picture is written: the folder of the benchmarks that git ignores
CACHE_DIR = Path(__file__).parent / ".cache"


def get_interpolated_df(
    parameters: tuple[str, str, str],
    start_date: dt.datetime,
    end_date: dt.datetime,
) -> pl.DataFrame:
    """Get interpolated data for a location."""
    stations = DwdObservationRequest(
        parameters=parameters,
        start=start_date,
        end=end_date,
    )
    return stations.interpolate(latlon=(50.0, 8.9)).df


def get_regular_df(
    parameters: tuple[str, str, str],
    start_date: dt.datetime,
    end_date: dt.datetime,
    exclude_stations: list,
) -> pl.DataFrame:
    """Get regular data for a station."""
    stations = DwdObservationRequest(
        parameters=parameters,
        start=start_date,
        end=end_date,
    )
    request = stations.filter_by_distance(latlon=(50.0, 8.9), distance=30)
    df = request.values().all().df.drop_nulls()
    station_ids = df.get_column("station_id")
    first_station_id = set(station_ids).difference(set(exclude_stations)).pop()
    return df.filter(pl.col("station_id").eq(first_station_id))


def get_rmse(regular_values: pl.Series, interpolated_values: pl.Series) -> float:
    """Calculate root mean squared error between regular and interpolated values."""
    return root_mean_squared_error(
        regular_values.reshape((-1, 1)).to_list(),
        interpolated_values.reshape((-1, 1)).to_list(),
    )


def get_corr(regular_values: pl.Series, interpolated_values: pl.Series) -> float:
    """Calculate correlation between regular and interpolated values."""
    return r_regression(
        regular_values.reshape((-1, 1)).to_list(),
        interpolated_values.reshape((-1, 1)).to_list(),
    ).item()


def draw(
    parameter: tuple[str, str, str],
    unit: str,
    regular_df: pl.DataFrame,
    interpolated_df: pl.DataFrame,
) -> alt.Chart:
    """Draw the regular and the interpolated values as lines, titled with their rmse and correlation."""
    alt = altair()
    rmse = get_rmse(regular_df.get_column("value"), interpolated_df.get_column("value"))
    corr = get_corr(regular_df.get_column("value"), interpolated_df.get_column("value"))
    df = pl.concat(
        [
            regular_df.select("timestamp", "value").with_columns(pl.lit("regular").alias("series")),
            interpolated_df.select("timestamp", "value").with_columns(pl.lit("interpolated").alias("series")),
        ],
    )
    title = alt.TitleParams(
        text=[
            f"rmse: {round(rmse, 2)}, corr: {round(corr, 2)}",
            f"station_ids: {interpolated_df.get_column('taken_station_ids').to_list()[0]}",
        ],
        anchor="start",
        fontSize=14,
    )
    chart = (
        alt.Chart(df)
        .mark_line()
        .encode(
            x=alt.X(
                "timestamp:T", title="Date", scale=alt.Scale(type="utc"), axis=alt.Axis(format="%d %b", tickCount=10)
            ),
            y=alt.Y("value:Q", title=f"{parameter[-1].lower()} [{unit}]", scale=alt.Scale(zero=False)),
            color=alt.Color(
                "series:N",
                title=None,
                scale=alt.Scale(domain=["regular", "interpolated"], range=["red", "black"]),
                legend=alt.Legend(orient="top-left", fillColor="white", padding=4),
            ),
        )
        .properties(title=title)
    )
    return chart.configure(font=FONT, background="white").configure_view(stroke="#888")


def visualize(
    parameter: tuple[str, str, str],
    unit: str,
    regular_df: pl.DataFrame,
    interpolated_df: pl.DataFrame,
) -> Path:
    """Draw the regular and the interpolated data and write the picture."""
    chart = draw(parameter, unit, regular_df, interpolated_df)
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / "interpolation_over_time.png"
    path.write_bytes(render_image(chart, "png", width=DEFAULT_WIDTH, height=DEFAULT_HEIGHT))
    print(f"picture: {path}")
    return path


def main() -> None:
    """Run example."""
    parameter = ("hourly", "air_temperature", "temperature_air_2m")
    unit = "°C"
    start_date = dt.datetime(2022, 3, 1, tzinfo=ZoneInfo("UTC"))
    end_date = dt.datetime(2022, 3, 31, tzinfo=ZoneInfo("UTC"))
    interpolated_df = get_interpolated_df(parameter, start_date, end_date)
    exclude_stations = interpolated_df.get_column("taken_station_ids")[0]
    regular_df = get_regular_df(parameter, start_date, end_date, exclude_stations)
    visualize(parameter, unit, regular_df, interpolated_df)


if __name__ == "__main__":
    main()
