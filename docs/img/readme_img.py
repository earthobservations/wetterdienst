# -*- coding: utf-8 -*-
# Copyright (c) 2018-2020 earthobservations
# Copyright (c) 2018-2020 Andreas Motl <andreas.motl@panodata.org>
# Copyright (c) 2018-2020 Benjamin Gutzmann <gutzemann@gmail.com>

import matplotlib.pyplot as plt
import pandas as pd

from wetterdienst.dwd.observations import DWDObservationStations, DWDObservationData, DWDObservationParameter, DWDObservationParameterSet, DWDObservationResolution, DWDObservationPeriod

plt.style.use('ggplot')


def create_temperature_ts_plot():
    """ Create plot for README sketch """
    stations = DWDObservationStations(
        DWDObservationParameterSet.CLIMATE_SUMMARY,
        DWDObservationResolution.DAILY,
        DWDObservationPeriod.HISTORICAL
    )

    df = stations.all()

    station_id, _, _, height, lat, lon, station_name, state = df.sort_values("FROM_DATE").iloc[0].values
    station_name = station_name.replace(u"ß", "ss")

    data = DWDObservationData(
        [station_id],
        DWDObservationParameter.DAILY.TEMPERATURE_AIR_200,
        DWDObservationResolution.DAILY,
        periods=[DWDObservationPeriod.HISTORICAL]
    )

    df = data.all()

    df_annual = df.groupby(df.DATE.dt.year)["VALUE"].mean().reset_index()
    df_annual["DATE"] = pd.to_datetime(df_annual["DATE"], format="%Y")

    temp_mean = df["VALUE"].mean()

    fig, ax = plt.subplots(tight_layout=True)

    df.plot(
        "DATE", "VALUE", ax=ax, color="blue", label="Tmean,daily", legend=False)
    df_annual.plot(
        "DATE", "VALUE", ax=ax, color="orange", label="Tmean,annual", legend=False)
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

    title = f"temperature (°C) at {station_name} (GER)\n" \
            f"ID {station_id}\n" \
            f"{lat}N {lon}E {height}m"
    ax.set_title(title)
    ax.legend(facecolor="white")

    ax.margins(x=0)

    plt.savefig(f"temperature_ts.png")


def main():
    create_temperature_ts_plot()


if __name__ == "__main__":
    main()
