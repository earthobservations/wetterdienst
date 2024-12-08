# Copyright (C) 2018-2023, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from datetime import datetime

import polars as pl

from wetterdienst import Parameter
from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
    DwdObservationResolution,
)

LATLON = (52.52, 13.40)


def get_interpolated_df(start_date: datetime, end_date: datetime) -> pl.DataFrame:
    stations = DwdObservationRequest(
        parameters=Parameter.PRECIPITATION_HEIGHT,
        resolution=DwdObservationResolution.DAILY,
        start_date=start_date,
        end_date=end_date,
    )
    return stations.interpolate(latlon=LATLON).df


def get_regular_df(start_date: datetime, end_date: datetime, exclude_stations: list) -> pl.DataFrame:
    stations = DwdObservationRequest(
        parameters=Parameter.PRECIPITATION_HEIGHT.name,
        resolution=DwdObservationResolution.DAILY,
        start_date=start_date,
        end_date=end_date,
    )
    request = stations.filter_by_distance(latlon=LATLON, distance=30)
    df = request.values.all().df.drop_nulls(subset=["value"])
    station_ids = df.get_column("station_id")
    first_station_id = set(station_ids).difference(set(exclude_stations)).pop()
    return df.filter(pl.col("station_id").eq(first_station_id))


def calculate_percentage_difference(df: pl.DataFrame, text: str = "") -> float:
    total_amount = df.get_column("value").len()
    zero_amount = df.filter(pl.col("value").eq(0.0)).height
    percentage = zero_amount / total_amount
    print(f"{text}: {percentage*100:.2f}% = {zero_amount} of {total_amount} with zero value")
    return percentage


def main():
    start_date = datetime(2021, 1, 1)
    end_date = datetime(2022, 1, 1)
    interpolated_df = get_interpolated_df(start_date, end_date)
    print(interpolated_df)
    exclude_stations = interpolated_df.get_column("taken_station_ids")[0]
    regular_df = get_regular_df(start_date, end_date, exclude_stations)
    calculate_percentage_difference(regular_df, "regular")
    calculate_percentage_difference(interpolated_df, "interpolated")


if __name__ == "__main__":
    main()
