# Copyright (C) 2018-2023, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime as dt
import os
from dataclasses import dataclass, field
from zoneinfo import ZoneInfo

import matplotlib.pyplot as plt
import polars as pl
import utm
from scipy import interpolate

from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
)

pl.Config.set_tbl_width_chars(400)

"""
example:

  station_id                 start_date                   end_date  height  latitude  longitude                    name   state   distance
0      02480 2004-09-01 00:00:00+00:00 2022-02-11 00:00:00+00:00   108.0   50.0643     8.9930               Kahl/Main  Bayern   9.759385
1      04411 2002-01-24 00:00:00+00:00 2022-02-11 00:00:00+00:00   155.0   49.9195     8.9671  Schaafheim-Schlierbach  Hessen  10.156943
2      07341 2005-07-16 00:00:00+00:00 2022-02-11 00:00:00+00:00   119.0   50.0899     8.7862    Offenbach-Wetterpark  Hessen  12.882694
3      00917 2004-09-01 00:00:00+00:00 2022-02-11 00:00:00+00:00   162.0   49.8809     8.6779               Darmstadt  Hessen  20.688403
4      01424 2008-08-01 00:00:00+00:00 2022-02-11 00:00:00+00:00   124.0   50.1269     8.6694  Frankfurt/Main-Westend  Hessen  21.680660
5      01420 1981-01-01 00:00:00+00:00 2022-02-11 00:00:00+00:00   100.0   50.0259     8.5213          Frankfurt/Main  Hessen  27.212977

     station_id          dataset                 parameter                      date   value  quality
24        02480  temperature_air  temperature_air_mean_2m 2022-01-02 00:00:00+00:00  278.15      1.0
481       04411  temperature_air  temperature_air_mean_2m 2022-01-02 00:00:00+00:00  277.15      1.0
938       07341  temperature_air  temperature_air_mean_2m 2022-01-02 00:00:00+00:00  278.35      1.0
1395      00917  temperature_air  temperature_air_mean_2m 2022-01-02 00:00:00+00:00  276.25      1.0
1852      01424  temperature_air  temperature_air_mean_2m 2022-01-02 00:00:00+00:00  281.05      1.0
2309      01420  temperature_air  temperature_air_mean_2m 2022-01-02 00:00:00+00:00  277.05      1.0
"""  # noqa: E501


@dataclass
class Data:
    station_ids: field(default_factory=list)
    utm_x: field(default_factory=list)
    utm_y: field(default_factory=list)
    values: field(default_factory=list)
    colors: field(default_factory=list)


def request_weather_data(
    parameter: str,
    lat: float,
    lon: float,
    distance: float,
    start_date: dt.datetime,
    end_date: dt.datetime,
):
    stations = DwdObservationRequest(
        parameters=parameter,
        resolution="hourly",
        start_date=start_date,
        end_date=end_date,
    )

    # request the nearest weather stations
    request = stations.filter_by_distance(latlon=(lat, lon), distance=distance)
    print(request.df)
    station_ids = request.df.get_column("station_id")
    latitudes = request.df.get_column("latitude")
    longitudes = request.df.get_column("longitude")

    utm_x = []
    utm_y = []
    for latitude, longitude in zip(latitudes, longitudes):
        x, y, _, _ = utm.from_latlon(latitude, longitude)
        utm_x.append(x)
        utm_y.append(y)

    # request parameter from weather stations
    df = request.values.all().df.drop_nulls(subset=["value"])
    print(df)
    # filters by one exact time and saves the given parameter per station at this time
    day_time = start_date + dt.timedelta(days=1)
    filtered_df = df.filter(pl.col("date").eq(day_time))
    print(filtered_df)
    values = filtered_df.get_column("value").to_list()

    return Data(
        station_ids=station_ids.to_list(),
        utm_x=utm_x,
        utm_y=utm_y,
        values=values,
        colors=["blue"] * len(station_ids),
    )


def interpolate_data(latitude: float, longitude: float, data: Data):
    # function for bilinear interpolation
    f = interpolate.LinearNDInterpolator(points=list(zip(data.utm_x, data.utm_y)), values=data.values)
    x, y, _, _ = utm.from_latlon(latitude, longitude)
    interpolated = f(x, y)
    print(f"{interpolated=}")

    # append interpolated value to the list to visualize the points later on
    data.utm_x.append(x)
    data.utm_y.append(y)
    data.values.append(interpolated)
    data.station_ids.append("interpolated")
    data.colors.append("red")


def visualize_points(data: Data):
    fig, ax = plt.subplots()
    ax.scatter(data.utm_y, data.utm_x, color=data.colors)

    for i, (station, value) in enumerate(zip(data.station_ids, data.values)):
        ax.annotate(
            f"id:{station}\nval:{value : .2f}\n",
            (data.utm_y[i], data.utm_x[i]),
            horizontalalignment="center",
            verticalalignment="bottom",
        )
    if "PYTEST_CURRENT_TEST" not in os.environ:
        plt.show()


def main():
    parameter = [("temperature_air_mean_2m", "temperature_air")]
    latitude = 50.0
    longitude = 8.9
    distance = 21.0
    start_date = dt.datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC"))
    end_date = dt.datetime(2022, 1, 20, tzinfo=ZoneInfo("UTC"))

    data = request_weather_data(parameter, latitude, longitude, distance, start_date, end_date)
    interpolate_data(latitude, longitude, data)
    visualize_points(data)


if __name__ == "__main__":
    main()
