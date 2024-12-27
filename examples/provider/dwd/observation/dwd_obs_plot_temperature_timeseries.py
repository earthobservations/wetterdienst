# Copyright (c) 2018-2023 earthobservations
import os
from pathlib import Path

import polars as pl
from matplotlib import pyplot as plt

from wetterdienst.provider.dwd.observation import DwdObservationRequest

HERE = Path(__file__).parent
ROOT = HERE.parent

SAVE_PLOT = False
SAVE_PLOT_HERE = True
PLOT_PATH = HERE / "temperature_ts.png" if SAVE_PLOT_HERE else ROOT / "docs" / "img" / "temperature_ts.png"

plt.style.use("ggplot")


def plot_temperature_timeseries():
    """Create plot for README sketch"""
    stations = DwdObservationRequest(
        parameters=("daily", "climate_summary", "temperature_air_mean_2m"),
        periods="historical",
    ).filter_by_name("Hohenpeissenberg")
    df = stations.values.all().df
    df_annual = df.group_by([pl.col("date").dt.year()], maintain_order=True).agg(pl.col("value").mean().alias("value"))
    df_annual = df_annual.with_columns(
        pl.col("date").cast(str).str.to_datetime("%Y"),
        pl.col("value").mean().alias("mean"),
    )
    fig, ax = plt.subplots(tight_layout=True)
    df.to_pandas().plot("date", "value", ax=ax, color="blue", label="Tmean,daily", legend=False)
    df_annual.to_pandas().plot("date", "value", ax=ax, color="orange", label="Tmean,annual", legend=False)
    df_annual.to_pandas().plot("date", "mean", ax=ax, color="red", label="mean(Tmean,daily)", legend=False)
    ax.text(0.2, 0.05, "Source: Deutscher Wetterdienst", ha="center", va="center", transform=ax.transAxes)
    ax.set_xlabel("Date")
    title = "Temperature (K) at Hohenpeissenberg, Germany"
    ax.set_title(title)
    ax.legend(facecolor="white")
    ax.margins(x=0)
    if SAVE_PLOT:
        fig.savefig(PLOT_PATH)
    elif "PYTEST_CURRENT_TEST" not in os.environ:
        plt.show()


def main():
    plot_temperature_timeseries()


if __name__ == "__main__":
    main()
