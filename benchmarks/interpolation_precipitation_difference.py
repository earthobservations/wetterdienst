# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Compare regular and interpolated data for a location."""

import datetime as dt
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
)

LATLON = (52.52, 13.40)


def get_interpolated_df(start_date: dt.datetime, end_date: dt.datetime) -> pl.DataFrame:
    """Get interpolated data for a location."""
    stations = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "precipitation_height")],
        start_date=start_date,
        end_date=end_date,
    )
    return stations.interpolate(latlon=LATLON).df


def get_regular_df(start_date: dt.datetime, end_date: dt.datetime, exclude_stations: list) -> pl.DataFrame:
    """Get regular data for a station."""
    stations = DwdObservationRequest(
        parameters=[("daily", "climate_summary", "precipitation_height")],
        start_date=start_date,
        end_date=end_date,
    )
    request = stations.filter_by_distance(latlon=LATLON, distance=30)
    df = request.values.all().df.drop_nulls(subset=["value"])
    station_ids = df.get_column("station_id")
    first_station_id = set(station_ids).difference(set(exclude_stations)).pop()
    return df.filter(pl.col("station_id").eq(first_station_id))


def calculate_percentage_difference(df: pl.DataFrame, text: str = "") -> float:
    """Calculate percentage of zero values in a DataFrame."""
    total_amount = df.get_column("value").len()
    zero_amount = df.filter(pl.col("value").eq(0.0)).height
    percentage = zero_amount / total_amount
    print(f"{text}: {percentage * 100:.2f}% = {zero_amount} of {total_amount} with zero value")
    return percentage


def main() -> None:
    """Run example."""
    start_date = dt.datetime(2021, 1, 1, tzinfo=ZoneInfo("UTC"))
    end_date = dt.datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC"))
    interpolated_df = get_interpolated_df(start_date, end_date)
    print(interpolated_df)
    exclude_stations = interpolated_df.get_column("taken_station_ids")[0]
    regular_df = get_regular_df(start_date, end_date, exclude_stations)
    calculate_percentage_difference(regular_df, "regular")
    calculate_percentage_difference(interpolated_df, "interpolated")


if __name__ == "__main__":
    main()
