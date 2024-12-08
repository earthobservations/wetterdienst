# Copyright (C) 2018-2023, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
=====
About
=====
Example for DWD Road Weather acquisition and comparison with nearest weather station.

This program will request latest DWD air temperature for
- road weather station Boeglum (A006)
- interpolated weather station data (54.8892, 8.9087)
and compare them in a plot.

"""  # Noqa:D205,D400

import datetime as dt
import os
from zoneinfo import ZoneInfo

import matplotlib.pyplot as plt

from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.road import DwdRoadRequest
from wetterdienst.util.cli import setup_logging


def dwd_road_weather_example():
    end_date = dt.datetime.now(ZoneInfo("UTC")).replace(tzinfo=None)
    start_date = end_date - dt.timedelta(days=1)
    drw_request = DwdRoadRequest(
        parameters=[("15_minutes", "data", "airTemperature")],
        start_date=start_date,
        end_date=end_date,
    ).filter_by_station_id("A006")
    print(drw_request.df)
    df_drw = drw_request.values.all().df.drop_nulls(subset="value")
    print(df_drw)

    dobs_request = DwdObservationRequest(
        parameters=[("10_minutes", "temperature_air", "temperature_air_mean_2m")],
        start_date=start_date,
        end_date=end_date,
    ).summarize(latlon=(54.8892, 8.9087))
    print(dobs_request.stations)
    df_dobs = dobs_request.df.drop_nulls(subset="value")
    print(df_dobs)

    fig, ax = plt.subplots(tight_layout=True)

    df_drw.drop_nulls(subset="value").to_pandas().plot(x="date", y="value", label="DRW", ax=ax)
    df_dobs.drop_nulls(subset="value").to_pandas().plot(x="date", y="value", label="DOBS", ax=ax)

    if "PYTEST_CURRENT_TEST" not in os.environ:
        plt.show()


def main():
    """Run example."""
    setup_logging()
    dwd_road_weather_example()


if __name__ == "__main__":
    main()
