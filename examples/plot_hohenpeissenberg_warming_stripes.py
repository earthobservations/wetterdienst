# -*- coding: utf-8 -*-
# Copyright (c) 2018-2023 earthobservations
import os
from pathlib import Path

import polars as pl
from matplotlib import pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.colors import ListedColormap
from matplotlib.patches import Rectangle

from wetterdienst.provider.dwd.observation import DwdObservationRequest

HERE = Path(__file__).parent
ROOT = HERE.parent

SAVE_PLOT = False
SAVE_PLOT_HERE = True
PLOT_PATH = (
    HERE / "hohenpeissenberg_warming_stripes.png"
    if SAVE_PLOT_HERE
    else ROOT / "docs" / "img" / "hohenpeissenberg_warming_stripes.png"
)

plt.style.use("ggplot")


def plot_hohenpeissenberg_warming_stripes():
    """Create warming stripes for Potsdam
    Source: https://matplotlib.org/matplotblog/posts/warming-stripes/
    """
    request = DwdObservationRequest("temperature_air_mean_200", "annual", "historical").filter_by_name(
        "Hohenpeissenberg"
    )
    df_values = request.values.all().df
    # definition of years
    first_year = 1781
    last_year = 2020
    # definition of reference period
    first_ref = 1971
    last_ref = 2000
    # definition of limit for colorbar
    lim = 0.7  # degrees
    # calculate anomaly
    series_anomaly = df_values.get_column("value")
    reference_temperature = (
        df_values.filter(pl.col("date").dt.year().is_between(first_ref, last_ref)).get_column("value").mean()
    )
    fig, ax = plt.subplots()
    cmap = ListedColormap(
        [
            "#08306b",
            "#08519c",
            "#2171b5",
            "#4292c6",
            "#6baed6",
            "#9ecae1",
            "#c6dbef",
            "#deebf7",
            "#fee0d2",
            "#fcbba1",
            "#fc9272",
            "#fb6a4a",
            "#ef3b2c",
            "#cb181d",
            "#a50f15",
            "#67000d",
        ]
    )
    ax.set_axis_off()
    col = PatchCollection([Rectangle((y, 0), 1, 1) for y in range(first_year, last_year + 1)])
    # set data, colormap and color limits
    col.set_array(series_anomaly)
    col.set_cmap(cmap)
    col.set_clim(reference_temperature - lim, reference_temperature + lim)
    ax.add_collection(col)
    ax.set_ylim(0, 1)
    ax.set_xlim(first_year, last_year + 1)
    ax.set_title("Warming stripes for Hohenpeissenberg, Germany\n" "Reference period: 1971 - 2000")
    ax.text(0.05, -0.05, f"{first_year}", ha="center", va="center", transform=ax.transAxes)
    ax.text(0.95, -0.05, f"{last_year}", ha="center", va="center", transform=ax.transAxes)
    ax.text(0.5, -0.05, "Source: Deutscher Wetterdienst", ha="center", va="center", transform=ax.transAxes)
    if SAVE_PLOT:
        plt.savefig(PLOT_PATH)
    elif "PYTEST_CURRENT_TEST" not in os.environ:
        plt.show()


def main():
    plot_hohenpeissenberg_warming_stripes()


if __name__ == "__main__":
    main()
