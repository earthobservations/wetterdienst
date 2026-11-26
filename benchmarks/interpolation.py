# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Interpolate weather data from DWD weather stations."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import polars as pl
import utm
from scipy import interpolate

from wetterdienst.io.charts import FONT, altair
from wetterdienst.io.export import render_image
from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
)

if TYPE_CHECKING:
    import altair as alt

#: where the picture is written: the folder of the benchmarks that git ignores
CACHE_DIR = Path(__file__).parent / ".cache"

pl.Config.set_tbl_width_chars(400)

"""
example:

  station_id            start_timestamp              end_timestamp  elevation  latitude  longitude                    name  region   distance
0      02480 2004-09-01 00:00:00+00:00 2022-02-11 00:00:00+00:00      108.0   50.0643     8.9930               Kahl/Main  Bayern   9.759385
1      04411 2002-01-24 00:00:00+00:00 2022-02-11 00:00:00+00:00      155.0   49.9195     8.9671  Schaafheim-Schlierbach  Hessen  10.156943
2      07341 2005-07-16 00:00:00+00:00 2022-02-11 00:00:00+00:00      119.0   50.0899     8.7862    Offenbach-Wetterpark  Hessen  12.882694
3      00917 2004-09-01 00:00:00+00:00 2022-02-11 00:00:00+00:00      162.0   49.8809     8.6779               Darmstadt  Hessen  20.688403
4      01424 2008-08-01 00:00:00+00:00 2022-02-11 00:00:00+00:00      124.0   50.1269     8.6694  Frankfurt/Main-Westend  Hessen  21.680660
5      01420 1981-01-01 00:00:00+00:00 2022-02-11 00:00:00+00:00      100.0   50.0259     8.5213          Frankfurt/Main  Hessen  27.212977

     station_id          dataset                 parameter                 timestamp   value quality_flags
24        02480  temperature_air  temperature_air_2m 2022-01-02 00:00:00+00:00  278.15             1
481       04411  temperature_air  temperature_air_2m 2022-01-02 00:00:00+00:00  277.15             1
938       07341  temperature_air  temperature_air_2m 2022-01-02 00:00:00+00:00  278.35             1
1395      00917  temperature_air  temperature_air_2m 2022-01-02 00:00:00+00:00  276.25             1
1852      01424  temperature_air  temperature_air_2m 2022-01-02 00:00:00+00:00  281.05             1
2309      01420  temperature_air  temperature_air_2m 2022-01-02 00:00:00+00:00  277.05             1
"""  # noqa: E501


@dataclass
class Data:
    """Data class for weather data."""

    station_ids: field(default_factory=list)
    utm_x: field(default_factory=list)
    utm_y: field(default_factory=list)
    values: field(default_factory=list)
    colors: field(default_factory=list)


def request_weather_data(
    parameters: list[tuple[str, str, str]],
    lat: float,
    lon: float,
    distance: float,
    start_date: dt.datetime,
    end_date: dt.datetime,
) -> Data:
    """Request weather data for a location."""
    stations = DwdObservationRequest(
        parameters=parameters,
        start=start_date,
        end=end_date,
    )

    # request the nearest weather stations
    request = stations.filter_by_distance(latlon=(lat, lon), distance=distance)
    print(request.df)
    station_ids = request.df.get_column("station_id")
    latitudes = request.df.get_column("latitude")
    longitudes = request.df.get_column("longitude")

    utm_x = []
    utm_y = []
    for latitude, longitude in zip(latitudes, longitudes, strict=False):
        x, y, _, _ = utm.from_latlon(latitude, longitude)
        utm_x.append(x)
        utm_y.append(y)

    # request parameter from weather stations
    df = request.values().all().df.drop_nulls(subset=["value"])
    print(df)
    # filters by one exact time and saves the given parameter per station at this time
    day_time = start_date + dt.timedelta(days=1)
    filtered_df = df.filter(pl.col("timestamp").eq(day_time))
    print(filtered_df)
    values = filtered_df.get_column("value").to_list()

    return Data(
        station_ids=station_ids.to_list(),
        utm_x=utm_x,
        utm_y=utm_y,
        values=values,
        colors=["blue"] * len(station_ids),
    )


def interpolate_data(latitude: float, longitude: float, data: Data) -> None:
    """Interpolate the weather data for a given location."""
    # function for bilinear interpolation
    f = interpolate.LinearNDInterpolator(points=list(zip(data.utm_x, data.utm_y, strict=False)), values=data.values)
    x, y, _, _ = utm.from_latlon(latitude, longitude)
    interpolated = f(x, y)
    print(f"{interpolated=}")

    # append interpolated value to the list to visualize the points later on
    data.utm_x.append(x)
    data.utm_y.append(y)
    data.values.append(interpolated)
    data.station_ids.append("interpolated")
    data.colors.append("red")


def draw_points(data: Data) -> alt.LayerChart:
    """Draw the weather stations and the interpolated point: easting across, northing up, each with its value."""
    alt = altair()
    values = [float(value) for value in data.values]
    df = pl.DataFrame(
        {
            "easting": data.utm_x,
            "northing": data.utm_y,
            "color": data.colors,
            "id_label": [f"id:{station}" for station in data.station_ids],
            "value_label": [f"val: {value:.2f}" for value in values],
        },
    )
    # the labels reach 40 pixels above a point, so the northern one needs more room than the others
    x_scale, y_scale = alt.Scale(zero=False, padding=30), alt.Scale(zero=False, padding=50)
    axis = alt.Axis(format=",.0f", tickCount=6, grid=False)
    base = alt.Chart(df).encode(
        x=alt.X("easting:Q", title="easting [m]", scale=x_scale, axis=axis),
        y=alt.Y("northing:Q", title="northing [m]", scale=y_scale, axis=axis),
    )
    points = base.mark_circle(size=70, opacity=1).encode(color=alt.Color("color:N", scale=None))
    # the id above the value, each a line of its own above the point
    ids = base.mark_text(dy=-26, baseline="bottom", fontSize=12).encode(text="id_label:N")
    labels = base.mark_text(dy=-10, baseline="bottom", fontSize=12).encode(text="value_label:N")
    return alt.layer(points, ids, labels).configure(font=FONT, background="white").configure_view(stroke="#888")


def visualize_points(data: Data) -> Path:
    """Draw the weather stations and the interpolated point and write the picture."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = CACHE_DIR / "interpolation.png"
    path.write_bytes(render_image(draw_points(data), "png", width=640, height=480))
    print(f"picture: {path}")
    return path


def main() -> None:
    """Run example."""
    parameters = [("hourly", "temperature_air", "temperature_air_2m")]
    latitude = 50.0
    longitude = 8.9
    distance = 21.0
    start_date = dt.datetime(2022, 1, 1, tzinfo=ZoneInfo("UTC"))
    end_date = dt.datetime(2022, 1, 20, tzinfo=ZoneInfo("UTC"))

    data = request_weather_data(parameters, latitude, longitude, distance, start_date, end_date)
    interpolate_data(latitude, longitude, data)
    visualize_points(data)


if __name__ == "__main__":
    main()
