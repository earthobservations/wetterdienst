from dataclasses import dataclass, field
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
from scipy import interpolate

from wetterdienst import Parameter
from wetterdienst.provider.dwd.observation import (
    DwdObservationPeriod,
    DwdObservationRequest,
    DwdObservationResolution,
)

"""
example:

  station_id                 from_date                   to_date  height  latitude  longitude                    name   state   distance
0      04411 2002-01-24 00:00:00+00:00 2022-02-08 00:00:00+00:00   155.0   49.9195     8.9671  Schaafheim-Schlierbach  Hessen  11.653027
1      02480 2004-09-01 00:00:00+00:00 2022-02-08 00:00:00+00:00   108.0   50.0643     8.9930               Kahl/Main  Bayern  12.572154
2      07341 2005-07-16 00:00:00+00:00 2022-02-08 00:00:00+00:00   119.0   50.0899     8.7862    Offenbach-Wetterpark  Hessen  16.126121
3      00917 2004-09-01 00:00:00+00:00 2022-02-08 00:00:00+00:00   162.0   49.8809     8.6779               Darmstadt  Hessen  28.023156
4      01424 2008-08-01 00:00:00+00:00 2022-02-08 00:00:00+00:00   124.0   50.1269     8.6694  Frankfurt/Main-Westend  Hessen  29.267715

     station_id          dataset                 parameter                      date   value  quality
24        04411  temperature_air  temperature_air_mean_200 2022-01-02 00:00:00+00:00  277.15      1.0
481       02480  temperature_air  temperature_air_mean_200 2022-01-02 00:00:00+00:00  278.15      1.0
938       07341  temperature_air  temperature_air_mean_200 2022-01-02 00:00:00+00:00  278.35      1.0
1395      00917  temperature_air  temperature_air_mean_200 2022-01-02 00:00:00+00:00  276.25      1.0
1852      01424  temperature_air  temperature_air_mean_200 2022-01-02 00:00:00+00:00  281.05      1.0
"""


@dataclass
class Data:
    station_ids: field(default_factory=list)
    latitudes: field(default_factory=list)
    longitudes: field(default_factory=list)
    values: field(default_factory=list)
    colors: field(default_factory=list)


def request_weather_data(
    parameter: str, lat: float, lon: float, distance: float, start_date: datetime, end_date: datetime
):
    stations = DwdObservationRequest(
        parameter=parameter,
        resolution=DwdObservationResolution.HOURLY,
        period=DwdObservationPeriod.RECENT,
        start_date=start_date,
        end_date=end_date,
    )

    # request the nearest weather stations
    request = stations.filter_by_distance(latitude=lat, longitude=lon, distance=distance)
    station_ids = request.df["station_id"].values.tolist()
    latitudes = request.df["latitude"].values.tolist()
    longitudes = request.df["longitude"].values.tolist()

    # request parameter from weather stations
    df = request.values.all().df.dropna()
    # filters by one exact time and saves the given parameter per station at this time
    day_time = start_date + timedelta(days=1)
    filtered_df = df[df["date"].astype(str).str[:] == day_time.strftime("%Y-%m-%d %H:%M:%S+00:00")]
    values = filtered_df["value"].values.tolist()

    return Data(
        station_ids=station_ids,
        latitudes=latitudes,
        longitudes=longitudes,
        values=values,
        colors=["blue"] * len(station_ids),
    )


def interpolate_data(latitude: float, longitude: float, data: Data):
    # function for bilinear interpolation
    f = interpolate.interp2d(data.latitudes, data.longitudes, data.values, kind="linear")
    interpolated = f(latitude, longitude)
    print(f"{interpolated=}")

    # append interpolated value to the list to visualize the points later on
    data.latitudes.append(latitude)
    data.longitudes.append(longitude)
    data.values.append(interpolated[0])
    data.station_ids.append("interpolated")
    data.colors.append("red")


def visualize_points(data: Data):
    fig, ax = plt.subplots()
    ax.scatter(data.longitudes, data.latitudes, color=data.colors)

    for i, (station, value) in enumerate(zip(data.station_ids, data.values)):
        ax.annotate(
            f"id:{station}\nval:{value : .2f}\n",
            (data.longitudes[i], data.latitudes[i]),
            horizontalalignment="center",
            verticalalignment="bottom",
        )

    fig.show()


def main():
    parameter = Parameter.TEMPERATURE_AIR_MEAN_200.name
    latitude = 50.0
    longitude = 8.9
    distance = 30.0
    start_date = datetime(2022, 1, 1)
    end_date = datetime(2022, 1, 20)

    data = request_weather_data(parameter, latitude, longitude, distance, start_date, end_date)
    interpolate_data(latitude, longitude, data)
    visualize_points(data)


if __name__ == "__main__":
    main()
