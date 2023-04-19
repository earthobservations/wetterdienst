from datetime import datetime

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from wetterdienst import Parameter
from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
    DwdObservationResolution,
)

plt.style.use("seaborn")


def get_interpolated_df(parameter: str, start_date: datetime, end_date: datetime) -> pd.DataFrame:
    stations = DwdObservationRequest(
        parameter=parameter,
        resolution=DwdObservationResolution.HOURLY,
        start_date=start_date,
        end_date=end_date,
    )
    return stations.interpolate(latlon=(50.0, 8.9)).df


def get_regular_df(parameter: str, start_date: datetime, end_date: datetime, exclude_stations: list) -> pd.DataFrame:
    stations = DwdObservationRequest(
        parameter=parameter,
        resolution=DwdObservationResolution.HOURLY,
        start_date=start_date,
        end_date=end_date,
    )
    request = stations.filter_by_distance(latlon=(50.0, 8.9), distance=30)
    df = request.values.all().df.dropna()
    station_ids = df.station_id.tolist()
    first_station_id = set(station_ids).difference(set(exclude_stations)).pop()
    return df[df["station_id"] == first_station_id]


def get_rmse(regular_values, interpolated_values):
    n = regular_values.size
    return (((regular_values - interpolated_values).dropna() ** 2).sum() / n) ** 0.5


def visualize(regular_df: pd.DataFrame, interpolated_df: pd.DataFrame):
    rmse = get_rmse(regular_df.value.reset_index(drop=True), interpolated_df.value.reset_index(drop=True))
    plt.plot_date(regular_df["date"], regular_df["value"], fmt="red", label="regular")
    plt.plot_date(interpolated_df["date"], interpolated_df["value"], fmt="black", label="interpolated")
    title = f"RMSE: {np.round(rmse, 2)}"
    plt.title(title)
    plt.legend()
    plt.tight_layout()
    plt.show()


def main():
    parameter = Parameter.TEMPERATURE_AIR_MEAN_200.name
    start_date = datetime(2022, 1, 1)
    end_date = datetime(2022, 2, 24)
    interpolated_df = get_interpolated_df(parameter, start_date, end_date)
    exclude_stations = interpolated_df.station_ids[0]
    regular_df = get_regular_df(parameter, start_date, end_date, exclude_stations)
    visualize(regular_df, interpolated_df)


if __name__ == "__main__":
    main()
