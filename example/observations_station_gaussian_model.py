# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
=====
About
=====
Acquire station information from DWD.

Requires:
  - pandas
  - matplotlib
  - lmfit

"""  # Noqa:D205,D400
import logging
import os
from typing import Tuple

import matplotlib.pyplot as plt
import polars as pl
from lmfit import Parameters
from lmfit.model import ModelResult

from wetterdienst import Settings
from wetterdienst.core.timeseries.result import StationsResult
from wetterdienst.provider.dwd.observation import (
    DwdObservationParameter,
    DwdObservationRequest,
    DwdObservationResolution,
)

log = logging.getLogger()

try:
    from lmfit.models import GaussianModel
except ImportError:
    log.error("observations_station_gaussian_model.py: please install lmfit ")
    exit(1)


def station_example(start_date="2018-12-25", end_date="2022-12-25", name="Frankfurt/Main"):
    """Retrieve stations_result of DWD that measure temperature."""

    stations = DwdObservationRequest(
        parameter=DwdObservationParameter.DAILY.TEMPERATURE_AIR_MEAN_200,
        resolution=DwdObservationResolution.DAILY,
        start_date=start_date,
        end_date=end_date,
        settings=Settings(ts_si_units=False),
    )
    return stations.filter_by_name(name=name)


class ModelYearlyGaussians:
    """

    Accepts station data and validates it for each year.

    Makes a composite model with a Gaussian curve per each year.

    Fits the model to the data and plots the result.

    """

    def __init__(self, station_data: StationsResult):
        self._station_data = station_data

        result_values = station_data.values.all().df.drop_nulls()

        valid_data = self.get_valid_data(result_values)

        valid_data = valid_data.with_row_count("rc")

        model, pars = self.make_composite_yearly_model(valid_data)

        x = valid_data.get_column("rc").to_numpy()
        y = valid_data.get_column("value").to_numpy()

        out = model.fit(y, pars, x=x)

        log.info(f"Fit Result message: {out.result.message}")

        self.plot_data_and_model(valid_data, out, savefig_to_file=True)

    def get_valid_data(self, result_values: pl.DataFrame) -> pl.DataFrame:
        valid_data_lst = []
        for _, group in result_values.groupby(pl.col("date").dt.year()):
            if self.validate_yearly_data(group):
                valid_data_lst.append(group)

        return pl.concat(valid_data_lst)

    @staticmethod
    def validate_yearly_data(df: pl.DataFrame) -> bool:
        year = df.get_column("date").dt.year().unique()[0]
        if df.is_empty() or not (df.get_column("date").min().month <= 2 and df.get_column("date").max().month > 10):
            log.info(f"skip year {year}")
            return False
        return True

    def make_composite_yearly_model(self, valid_data: pl.DataFrame) -> Tuple[GaussianModel, Parameters]:
        """makes a composite model
        https://lmfit.github.io/lmfit-py/model.html#composite-models-adding-or-multiplying-models"""
        number_of_years = valid_data.get_column("date").dt.year().n_unique()

        x = valid_data.get_column("rc").to_numpy()
        y = valid_data.get_column("value").to_numpy()

        index_per_year = x.max() / number_of_years

        pars, composite_model = None, None
        for year, group in valid_data.groupby(pl.col("date").dt.year(), maintain_order=True):
            gmod = GaussianModel(prefix=f"g{year}_")
            if pars is None:
                pars = gmod.make_params()
            else:
                pars.update(gmod.make_params())
            pars = self.model_pars_update(year, group, pars, index_per_year, y.max())
            if composite_model is None:
                composite_model = gmod
            else:
                composite_model = composite_model + gmod
        return composite_model, pars

    @staticmethod
    def model_pars_update(
        year: int, group: pl.DataFrame, pars: Parameters, index_per_year: float, y_max: float
    ) -> Parameters:
        """updates the initial values of the model parameters"""
        idx = group.get_column("rc").to_numpy()
        mean_index = idx.mean()

        pars[f"g{year}_center"].set(value=mean_index, min=0.75 * mean_index, max=1.25 * mean_index)
        pars[f"g{year}_sigma"].set(value=index_per_year / 4, min=3, max=100)
        pars[f"g{year}_amplitude"].set(value=5 * y_max, min=10)

        return pars

    def plot_data_and_model(self, valid_data: pl.DataFrame, out: ModelResult, savefig_to_file=True) -> None:
        """plots the data and the model"""
        if savefig_to_file:
            _ = plt.subplots(figsize=(12, 12))
        df = pl.DataFrame(
            {
                "year": valid_data.get_column("date"),
                "value": valid_data.get_column("value").to_numpy(),
                "model": out.best_fit,
            }
        )
        title = valid_data.get_column("parameter").unique()[0]
        df.to_pandas().plot(x="year", y=["value", "model"], title=title)
        if savefig_to_file:
            number_of_years = valid_data.get_column("date").dt.year().n_unique()
            filename = f"{self.__class__.__qualname__}_wetter_model_{number_of_years}"
            plt.savefig(filename, dpi=300, bbox_inches="tight")
            log.info("saved fig to file: " + filename)
            if "PYTEST_CURRENT_TEST" not in os.environ:
                plt.show()


def main():
    """Run example."""
    logging.basicConfig(level=logging.INFO)

    station_data_one_year = station_example(start_date="2020-12-25", end_date="2022-01-01")
    _ = ModelYearlyGaussians(station_data_one_year)

    station_data_many_years = station_example(start_date="1995-12-25", end_date="2022-12-31")
    _ = ModelYearlyGaussians(station_data_many_years)


if __name__ == "__main__":
    main()
