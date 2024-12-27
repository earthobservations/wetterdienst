# Copyright (c) 2018-2023 earthobservations
import os
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from matplotlib import colors
from matplotlib.colors import ListedColormap

from wetterdienst.provider.dwd.observation import (
    DwdObservationRequest,
)

HERE = Path(__file__).parent
ROOT = HERE.parent

SAVE_PLOT = False
SAVE_PLOT_HERE = True
PLOT_PATH = (
    HERE / "german_weather_stations.png" if SAVE_PLOT_HERE else ROOT / "docs" / "img" / "german_weather_stations.png"
)

plt.style.use("ggplot")


def plot_german_weather_stations():
    """Create map of DWD weather stations in Germany"""
    stations = DwdObservationRequest(parameters=("daily", "climate_summary"), periods="historical")
    stations_df = stations.all().df
    fig, ax = plt.subplots()
    quantiles = [0.0, 0.16666667, 0.33333333, 0.5, 0.66666667, 0.83333333, 1.0]
    bounds = [stations_df["height"].quantile(q) for q in quantiles]
    inferno = plt.get_cmap("inferno")
    cmap = ListedColormap([inferno(q) for q in quantiles])
    norm = colors.BoundaryNorm(bounds, cmap.N)
    plot = ax.scatter(data=stations_df, x="longitude", y="latitude", c="height", s=10, cmap=cmap, norm=norm)
    fig.colorbar(plot, ax=ax, label="Height / m")
    ax.set_xlabel("Longitude / deg")
    ax.set_ylabel("Latitude / deg")
    ax.set_title("German weather stations")
    # make Germany look like Germany by using the proper scaling between y-axis and x-axis
    # 51 is approximately the mean latitude of Germany
    ax.set_aspect(1 / np.cos(np.deg2rad(51)))
    ax.text(0.5, 0.01, "Source: Deutscher Wetterdienst", ha="center", va="bottom", transform=ax.transAxes)
    fig.tight_layout()
    if SAVE_PLOT:
        fig.savefig(PLOT_PATH)
    elif "PYTEST_CURRENT_TEST" not in os.environ:
        plt.show()


def main():
    plot_german_weather_stations()


if __name__ == "__main__":
    main()
