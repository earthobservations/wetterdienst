# Copyright (C) 2018-2023, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import os
from datetime import datetime

import matplotlib.pyplot as plt
import polars as pl

from wetterdienst import Parameter
from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
    DwdObservationResolution,
)


def get_summarized_df(start_date: datetime, end_date: datetime, lat, lon) -> pl.DataFrame:
    stations = DwdObservationRequest(
        parameters=Parameter.TEMPERATURE_AIR_MEAN_2M,
        resolution=DwdObservationResolution.DAILY,
        start_date=start_date,
        end_date=end_date,
    )
    return stations.summarize(latlon=(lat, lon)).df


def get_regular_df(start_date: datetime, end_date: datetime, station_id) -> pl.DataFrame:
    stations = DwdObservationRequest(
        parameters=Parameter.TEMPERATURE_AIR_MEAN_2M,
        resolution=DwdObservationResolution.DAILY,
        start_date=start_date,
        end_date=end_date,
    )
    request = stations.filter_by_station_id(station_id)
    return request.values.all().df


def main():
    start_date = datetime(1934, 1, 1)
    end_date = datetime(1980, 12, 31)
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

    fig, ax = plt.subplots(nrows=5, tight_layout=True, sharex=True, sharey=True)

    summarized_df.to_pandas().plot("date", "value", c="color", label="summarized", kind="scatter", ax=ax[0], s=5)
    regular_df_01050.to_pandas().plot("date", "value", color="yellow", label="01050", ax=ax[1])
    regular_df_01051.to_pandas().plot("date", "value", color="blue", label="01051", ax=ax[2])
    regular_df_01048.to_pandas().plot("date", "value", color="green", label="01048", ax=ax[3])
    regular_df_05282.to_pandas().plot("date", "value", color="pink", label="05282", ax=ax[4])

    ax[0].set_ylabel(None)

    title = "Comparison of summarized values and single stations for\ntemperature_air_mean_2m"
    plt.suptitle(title)
    plt.legend()
    plt.tight_layout()
    if "PYTEST_CURRENT_TEST" not in os.environ:
        plt.show()


if __name__ == "__main__":
    main()
