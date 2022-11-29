import pandas as pd

from wetterdienst import Parameter
from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationResolution

from datetime import datetime


def get_interpolated_df(start_date: datetime, end_date: datetime) -> pd.DataFrame:
    stations = DwdObservationRequest(
        parameter=Parameter.PRECIPITATION_HEIGHT.name,
        resolution=DwdObservationResolution.DAILY,
        start_date=start_date,
        end_date=end_date,
    )
    return stations.interpolate(latlon=(50.0, 8.9)).df


def get_regular_df(start_date: datetime, end_date: datetime, exclude_stations: list) -> pd.DataFrame:
    stations = DwdObservationRequest(
        parameter=Parameter.PRECIPITATION_HEIGHT.name,
        resolution=DwdObservationResolution.DAILY,
        start_date=start_date,
        end_date=end_date,
    )
    request = stations.filter_by_distance(latlon=(50.0, 8.9), distance=30)
    df = request.values.all().df.dropna()
    station_ids = df.station_id.tolist()
    first_station_id = set(station_ids).difference(set(exclude_stations)).pop()
    return df[df["station_id"] == first_station_id]


def calculate_percentage_difference(df: pd.DataFrame, text: str = "") -> float:
    total_amount = len(df["value"])
    zero_amount = len(df[df["value"] == 0.])
    percentage = zero_amount / total_amount
    print(f"{text}: {percentage*100:.2f}% = {zero_amount} of {total_amount} with zero value")
    return percentage


def main():
    start_date = datetime(2021, 1, 1)
    end_date = datetime(2022, 1, 1)
    interpolated_df = get_interpolated_df(start_date, end_date)
    print(interpolated_df)
    exclude_stations = interpolated_df.station_ids[0]
    regular_df = get_regular_df(start_date, end_date, exclude_stations)
    calculate_percentage_difference(regular_df, "regular")
    calculate_percentage_difference(interpolated_df, "interpolated")


if __name__ == "__main__":
    main()
