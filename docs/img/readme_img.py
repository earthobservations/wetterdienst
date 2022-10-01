# -*- coding: utf-8 -*-
# Copyright (c) 2018-2020 earthobservations
# Copyright (c) 2018-2020 Andreas Motl <andreas.motl@panodata.org>
# Copyright (c) 2018-2020 Benjamin Gutzmann <gutzemann@gmail.com>

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib import cm, colors
from matplotlib.collections import PatchCollection
from matplotlib.colors import ListedColormap
from matplotlib.patches import Rectangle

from wetterdienst.provider.dwd.observation import (
    DwdObservationDataset,
    DwdObservationParameter,
    DwdObservationPeriod,
    DwdObservationRequest,
    DwdObservationResolution,
    DwdObservationValues,
)

plt.style.use('ggplot')


def create_temperature_ts_plot():
    """ Create plot for README sketch """
    stations = DwdObservationRequest(
        "temperature_air_200",
        DwdObservationResolution.DAILY,
        DwdObservationPeriod.HISTORICAL
    ).filter_by_name("Hohenpeissenberg")

    df = stations.values.all().df

    df_annual = df.groupby(df.date.dt.year)["value"].mean().reset_index()
    df_annual["date"] = pd.to_datetime(df_annual["date"], format="%Y")

    temp_mean = df["value"].mean()

    fig, ax = plt.subplots(tight_layout=True)

    df.plot(
        "date", "value", ax=ax, color="blue", label="Tmean,daily", legend=False)
    df_annual.plot(
        "date", "value", ax=ax, color="orange", label="Tmean,annual", legend=False)
    ax.axhline(y=temp_mean, color="red", label="mean(Tmean,daily)")

    ax.text(
        0.2,
        0.05,
        "Source: Deutscher Wetterdienst",
        ha='center',
        va='center',
        transform=ax.transAxes
    )

    ax.set_xlabel("Date")

    title = f"Temperature (K) at Hohenpeissenberg, Germany"
    ax.set_title(title)
    ax.legend(facecolor="white")

    ax.margins(x=0)

    plt.savefig(f"temperature_ts.png")


def create_weather_stations_map():
    """ Create map of DWD weather stations_result in Germany """
    stations = DwdObservationRequest(
        DwdObservationDataset.CLIMATE_SUMMARY,
        DwdObservationResolution.DAILY,
        DwdObservationPeriod.HISTORICAL
    )

    stations_df = stations.all().df

    fig, ax = plt.subplots()

    # Rainbow colormap
    cmap = colors.LinearSegmentedColormap.from_list(
        "",
        [
            '#86007D',
            '#0000F9',
            '#008018',
            '#FFFF41',
            '#FFA52C',
            '#FF0018',
         ]
    )

    bounds = stations_df.height.quantile(
        [
            0,
            0.16666667,
            0.33333333,
            0.5,
            0.66666667,
            0.83333333,
            1
         ]).values

    norm = colors.BoundaryNorm(bounds, cmap.N)

    stations_df = stations_df.rename(columns={"height": "Height [m]"})

    stations_df.plot.scatter(x="longitude", y="latitude", c="Height [m]", cmap=cmap, norm=norm, ax=ax)

    ax.set_xlabel("Longitude [°]")
    ax.set_ylabel("Latitude [°]")
    ax.set_title("German weather stations_result")

    ax.text(
        0.3,
        0.05,
        "Source: Deutscher Wetterdienst",
        ha='center',
        va='center',
        transform=ax.transAxes
    )

    plt.savefig("german_weather_stations.png")

    return


def create_hohenpeissenberg_warming_stripes():
    """ Create warming stripes for Potsdam
    Source: https://matplotlib.org/matplotblog/posts/warming-stripes/
    """
    request = DwdObservationRequest(
        "temperature_air_200",
        DwdObservationResolution.ANNUAL,
        DwdObservationPeriod.HISTORICAL
    ).filter_by_name("Hohenpeissenberg")

    values_df = request.values.all().df

    # Definition of years
    first_year = 1781
    last_year = 2020

    first_ref = 1971
    last_ref = 2000

    lim = 0.7  # degrees

    anomaly = values_df.loc[:, 'value']

    reference = anomaly.loc[
        ((values_df.from_date.dt.year >= first_ref) &
        (values_df.from_date.dt.year <= last_ref))
    ].mean()

    fig, ax = plt.subplots()

    cmap = ListedColormap([
        '#08306b', '#08519c', '#2171b5', '#4292c6',
        '#6baed6', '#9ecae1', '#c6dbef', '#deebf7',
        '#fee0d2', '#fcbba1', '#fc9272', '#fb6a4a',
        '#ef3b2c', '#cb181d', '#a50f15', '#67000d',
    ])

    ax.set_axis_off()

    col = PatchCollection([
        Rectangle((y, 0), 1, 1)
        for y in range(first_year, last_year + 1)
    ])

    # set data, colormap and color limits
    col.set_array(anomaly)
    col.set_cmap(cmap)
    col.set_clim(reference - lim, reference + lim)
    ax.add_collection(col)

    ax.set_ylim(0, 1)
    ax.set_xlim(first_year, last_year + 1)

    ax.set_title("Warming stripes for Hohenpeissenberg, Germany\n"
                 "Reference period: 1971 - 2000")

    ax.text(
        0.05,
        -0.05,
        f"{first_year}",
        ha='center',
        va='center',
        transform=ax.transAxes
    )

    ax.text(
        0.95,
        -0.05,
        f"{last_year}",
        ha='center',
        va='center',
        transform=ax.transAxes
    )

    ax.text(
        0.5,
        -0.05,
        f"Source: Deutscher Wetterdienst",
        ha='center',
        va='center',
        transform=ax.transAxes
    )

    plt.savefig(f"hohenpeissenberg_warming_stripes.png")


def main():
    create_temperature_ts_plot()
    create_weather_stations_map()
    create_hohenpeissenberg_warming_stripes()


if __name__ == "__main__":
    main()
