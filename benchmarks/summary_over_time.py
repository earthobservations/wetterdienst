from datetime import datetime

import matplotlib.pyplot as plt
import polars as pl

from wetterdienst import Parameter
from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
    DwdObservationResolution,
)

plt.style.use("seaborn")


def get_summarized_df(start_date: datetime, end_date: datetime, lat, lon) -> pl.DataFrame:
    stations = DwdObservationRequest(
        parameter=Parameter.TEMPERATURE_AIR_MEAN_200,
        resolution=DwdObservationResolution.DAILY,
        start_date=start_date,
        end_date=end_date,
    )
    return stations.summarize(latlon=(lat, lon)).df


def get_regular_df(start_date: datetime, end_date: datetime, station_id) -> pl.DataFrame:
    stations = DwdObservationRequest(
        parameter=Parameter.TEMPERATURE_AIR_MEAN_200,
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
    summarized_df["color"] = summarized_df.station_id.map(
        lambda x: {"01050": "yellow", "01048": "green", "01051": "blue", "05282": "violet"}.get(x)
    )

    regular_df_01050 = get_regular_df(start_date, end_date, "01050")
    regular_df_01048 = get_regular_df(start_date, end_date, "01048")
    regular_df_01051 = get_regular_df(start_date, end_date, "01051")
    regular_df_05282 = get_regular_df(start_date, end_date, "05282")

    fig, ax = plt.subplots(nrows=5, tight_layout=True, sharex=True)

    summarized_df.plot("date", "value", c="color", label="summarized", kind="scatter", ax=ax[0], s=5)
    regular_df_01050.plot("date", "value", color="yellow", label="01050", ax=ax[1])
    regular_df_01051.plot("date", "value", color="blue", label="01051", ax=ax[2])
    regular_df_01048.plot("date", "value", color="green", label="01048", ax=ax[3])
    regular_df_05282.plot("date", "value", color="pink", label="05282", ax=ax[4])

    ax[0].set_ylabel(None)

    title = "Comparison of summarized values and single stations"
    plt.suptitle(title)
    plt.legend()
    plt.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
