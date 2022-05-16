import pandas as pd

from wetterdienst import Parameter
from wetterdienst.provider.dwd.observation import DwdObservationRequest, DwdObservationResolution

import matplotlib.pyplot as plt
from datetime import datetime

plt.style.use('seaborn')


def get_interpolated_df(start_date: datetime, end_date: datetime) -> pd.DataFrame:
    stations = DwdObservationRequest(
        parameter=Parameter.TEMPERATURE_AIR_MEAN_200.name,
        resolution=DwdObservationResolution.HOURLY,
        start_date=start_date,
        end_date=end_date,
    )
    return stations.interpolate(latitude=50.0, longitude=8.9).df


def get_regular_df(start_date: datetime, end_date: datetime, exclude_stations: list) -> pd.DataFrame:
    stations = DwdObservationRequest(
        parameter=Parameter.TEMPERATURE_AIR_MEAN_200.name,
        resolution=DwdObservationResolution.HOURLY,
        start_date=start_date,
        end_date=end_date,
    )
    request = stations.filter_by_distance(latitude=50.0, longitude=8.9, distance=30)
    df = request.values.all().df.dropna()
    station_ids = df.station_id.tolist()
    first_station_id = set(station_ids).difference(set(exclude_stations)).pop()
    return df[df["station_id"] == first_station_id]


def visualize(regular_df: pd.DataFrame, interpolated_df: pd.DataFrame):
    plt.plot_date(regular_df["date"], regular_df["value"], fmt='red')
    plt.plot_date(interpolated_df["date"], interpolated_df["value"], fmt='black')
    plt.tight_layout()
    plt.show()


def main():
    start_date = datetime(2022, 1, 1)
    end_date = datetime(2022, 2, 24)
    interpolated_df = get_interpolated_df(start_date, end_date)
    exclude_stations = interpolated_df.station_ids[0]
    regular_df = get_regular_df(start_date, end_date, exclude_stations)
    visualize(regular_df, interpolated_df)


if __name__ == "__main__":
    main()
