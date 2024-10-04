# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import logging
import operator
from abc import ABCMeta, abstractmethod
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import polars as pl
from dateutil.relativedelta import relativedelta
from pint import Quantity
from tqdm import tqdm
from tzfpy import get_tz

from wetterdienst.core.timeseries.result import StationsResult, ValuesResult
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.resolution import DAILY_AT_MOST, Resolution
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.metadata.unit import REGISTRY, OriginUnit, SIUnit
from wetterdienst.util.logging import TqdmToLogger

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Iterator
    from enum import Enum

try:
    from backports.datetime_fromisoformat import MonkeyPatch
except ImportError:
    pass
else:
    MonkeyPatch.patch_fromisoformat()

log = logging.getLogger(__name__)


class TimeseriesValues(metaclass=ABCMeta):
    """Core for sources of point data where data is related to a station"""

    def __init__(self, stations_result: StationsResult) -> None:
        self.sr = stations_result
        self.stations_counter = 0
        self.stations_collected = []

    @classmethod
    def from_stations(cls, stations: StationsResult):
        return cls(stations)

    def __eq__(self, other):
        """Equal method of request object"""
        return self.sr.stations == other.sr.stations and self.sr.station_id == other.sr.station_id

    def __repr__(self):
        """Representation of values object"""
        station_ids_joined = ", ".join(self.sr.station_id.to_list())
        parameters_joined = ", ".join(
            [f"({parameter.value}/{dataset.value})" for parameter, dataset in self.sr.stations.parameter],
        )
        periods_joined = self.sr.stations.period and ", ".join([period.value for period in self.sr.stations.period])

        return (
            f"{self.sr.stations.__class__.__name__}Values("
            f"[{station_ids_joined}], "
            f"[{parameters_joined}], "
            f"[{periods_joined}], "
            f"{str(self.sr.start_date)},"
            f"{str(self.sr.end_date)})"
        )

    # Fields for type coercion, needed for separation from fields with actual data
    # that have to be parsed differently when having data in tabular form
    @property
    def _meta_fields(self) -> dict[str, str]:
        """
        Metadata fields that are independent of actual values and should be parsed
        differently

        :return: list of strings representing the metadata fields/columns
        """
        if not self.sr.tidy:
            return {
                Columns.STATION_ID.value: str,
                Columns.DATASET.value: str,
                Columns.DATE.value: pl.Datetime(time_zone="UTC"),
            }
        else:
            return {
                Columns.STATION_ID.value: str,
                Columns.DATASET.value: str,
                Columns.PARAMETER.value: str,
                Columns.DATE.value: pl.Datetime(time_zone="UTC"),
                Columns.VALUE.value: pl.Float64,
                Columns.QUALITY.value: pl.Float64,
            }

    # Fields for date coercion
    _date_fields = [Columns.DATE.value, Columns.START_DATE.value, Columns.END_DATE.value]

    # TODO: add data type (mosmix, observation, ...)

    @property
    def data_tz(self) -> str:
        """Timezone of the published data"""
        return self._data_tz.value

    @property
    @abstractmethod
    def _data_tz(self) -> Timezone:
        """Timezone enumeration of published data."""
        pass

    def _fetch_frequency(
        self,
        station_id,  # noqa: ARG002
        parameter: Enum,  # noqa: ARG002
        dataset: Enum,  # noqa: ARG002
    ) -> str:
        """
        Method used to fetch the dynamic frequency string from somewhere and then set it after download the
        corresponding dataset. The fetch may either be an arbitrary algorithm that parses the frequency from the
        downloaded data or simply get the frequency from elsewhere. This method has to be implemented only for
        services that have dynamic resolutions.
        :param station_id:
        :param parameter:
        :param dataset:
        :return:
        """
        if self.sr.resolution == Resolution.DYNAMIC:
            raise NotImplementedError("implement this method if the service has a dynamic resolution")

    def _adjust_start_end_date(
        self,
        start_date: dt.datetime,
        end_date: dt.datetime,
        tzinfo: ZoneInfo,
    ) -> tuple[dt.datetime, dt.datetime]:
        """Adjust start and end date to the resolution of the service. This is
        necessary for building a complete date range that matches the resolution.
        """
        # cut of everything smaller than day for daily or lower freq, same for monthly and annual
        if self.sr.resolution in DAILY_AT_MOST:
            start_date = start_date.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            end_date = end_date.replace(
                hour=23,
                minute=59,
                second=0,
                microsecond=0,
            )
        elif self.sr.resolution == Resolution.MONTHLY:
            start_date = start_date.replace(
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            end_date = end_date + relativedelta(months=1) - relativedelta(days=1)
        elif self.sr.resolution == Resolution.ANNUAL:
            start_date = start_date.replace(
                month=1,
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            end_date = end_date.replace(
                month=1,
                day=31,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )

        return start_date.replace(tzinfo=tzinfo), end_date.replace(tzinfo=tzinfo)

    def _get_complete_dates(self, start_date: dt.datetime, end_date: dt.datetime) -> pl.Series:
        """
        Complete datetime index for the requested start and end date, used for
        building a complementary pandas DataFrame with the date column on which
        other DataFrames can be joined on
        """
        date_range = pl.datetime_range(start_date, end_date, interval=self.sr.frequency.value, eager=True)
        if self.sr.resolution not in DAILY_AT_MOST:
            date_range = date_range.map_elements(lambda date: date.replace(day=1).isoformat(), return_dtype=pl.String)
            date_range = date_range.str.to_datetime()
        date_range = date_range.dt.cast_time_unit("us")
        return date_range.dt.convert_time_zone("UTC")

    def _get_timezone_from_station(self, station_id: str) -> str:
        """
        Get timezone information for explicit station that is used to set the
        correct timezone for the timestamps of the returned values

        :param station_id: station id string
        :return: timezone
        """
        stations = self.sr.df
        longitude, latitude = (
            stations.filter(pl.col(Columns.STATION_ID.value).eq(station_id))
            .select([pl.col(Columns.LONGITUDE.value), pl.col(Columns.LATITUDE.value)])
            .transpose()
            .to_series()
            .to_list()
        )
        return get_tz(longitude, latitude)

    def _get_base_df(self, start_date: dt.datetime, end_date: dt.datetime) -> pl.DataFrame:
        """
        Base dataframe which is used for creating empty dataframes if no data is
        found or for merging other dataframes on the full dates

        :return: pandas DataFrame with a date column with complete dates
        """
        return pl.DataFrame({Columns.DATE.value: self._get_complete_dates(start_date, end_date)})

    def _convert_values_to_si(self, df: pl.DataFrame, dataset) -> pl.DataFrame:
        """
        Function to convert values to metric units with help of conversion factors

        :param df: pandas DataFrame that should be converted to SI units
        :param dataset: dataset for which the conversion factors are created
        :return: pandas DataFrame with converted (SI) values
        """
        if df.is_empty():
            return df

        conversion_factors = self._create_conversion_factors(dataset)

        data = []
        for (dataset, parameter), group in df.group_by(
            [Columns.DATASET.value, Columns.PARAMETER.value],
            maintain_order=True,
        ):
            op, factor = conversion_factors.get(dataset).get(parameter, (None, None))
            if op:
                group = group.with_columns(pl.col(Columns.VALUE.value).map_batches(lambda s, o=op, f=factor: o(s, f)))
            data.append(group)

        return pl.concat(data)

    def _create_conversion_factors(
        self,
        datasets: list[str],
    ) -> dict[str, dict[str, tuple[operator.add | operator.mul, float]]]:
        """
        Function to create conversion factors based on a given dataset

        :param dataset: dataset for which conversion factors are created
        :return: dictionary with conversion factors for given parameter name
        """
        dataset_accessor = self.sr._dataset_accessor
        conversion_factors = {}
        for dataset in datasets:
            conversion_factors[dataset] = {}
            units = self.sr._unit_base[dataset_accessor][dataset.upper()]
            for parameter in units:
                parameter_name = self.sr._parameter_base[dataset_accessor][dataset.upper()][
                    parameter.name
                ].value.lower()
                conversion_factors[dataset][parameter_name] = self._get_conversion_factor(*parameter.value)
        return conversion_factors

    @staticmethod
    def _get_conversion_factor(
        origin_unit: Enum,
        si_unit: Enum,
    ) -> tuple[operator.mul | operator.add | None, float | None]:
        """
        Method to get the conversion factor (flaot) for a specific parameter
        :param origin_unit: origin unit enumeration of parameter
        :param si_unit: si unit enumeration of parameter
        :return: conversion factor as float
        """
        if si_unit == SIUnit.KILOGRAM_PER_SQUARE_METER.value:
            # Fixed conversion factors to kg / m², as it only applies
            # for water with density 1 g / cm³
            if origin_unit == OriginUnit.MILLIMETER.value:
                return operator.mul, 1
            elif origin_unit == si_unit:
                return operator.mul, 1
            else:
                raise ValueError("manually set conversion factor for precipitation unit")
        elif si_unit == SIUnit.DEGREE_KELVIN.value:
            # Apply offset addition to temperature measurements
            # Take 0 as this is appropriate for adding on other numbers
            # (just the difference)
            degree_offset = Quantity(0, origin_unit).to(si_unit).magnitude
            return operator.add, degree_offset
        elif si_unit == SIUnit.PERCENT.value:
            factor = REGISTRY(str(origin_unit)).to(str(si_unit)).magnitude
            try:
                factor = factor.item()
            except AttributeError:
                pass
            return operator.mul, factor
        elif si_unit == SIUnit.DIMENSIONLESS.value:
            return None, None
        else:
            # For multiplicative units we need to use 1 as quantity to apply the
            # appropriate factor
            factor = Quantity(1, origin_unit).to(si_unit).magnitude
            try:
                factor = factor.item()
            except AttributeError:
                pass
            return operator.mul, factor

    def _create_empty_station_parameter_df(self, station_id: str, dataset: Enum) -> pl.DataFrame:
        """
        Function to create an empty DataFrame
        :param station_id:
        :param parameter:
        :return:
        """
        # if parameter is a whole dataset, take every parameter from the dataset instead
        parameter = [*self.sr._parameter_base[self.sr.resolution.name][dataset.name]]

        if not self.sr.start_date:
            return pl.DataFrame(schema=self._meta_fields)

        if self._data_tz == Timezone.DYNAMIC:
            tzinfo = ZoneInfo(self._get_timezone_from_station(station_id))
        else:
            tzinfo = ZoneInfo(self.data_tz)
        start_date, end_date = self._adjust_start_end_date(self.sr.start_date, self.sr.end_date, tzinfo)

        base_df = self._get_base_df(start_date, end_date)

        data = []
        for par in pl.Series(parameter):
            if par.name.startswith("QUALITY"):
                continue
            par_df = base_df.with_columns(pl.lit(par.value).alias(Columns.PARAMETER.value))
            data.append(par_df)

        df = pl.concat(data)

        return df.with_columns(
            pl.lit(value=station_id, dtype=pl.String).alias(Columns.STATION_ID.value),
            pl.lit(value=None, dtype=pl.Float64).alias(Columns.VALUE.value),
            pl.lit(value=None, dtype=pl.Float64).alias(Columns.QUALITY.value),
        )

    def _build_complete_df(self, df: pl.DataFrame, station_id: str) -> pl.DataFrame:
        """Method to build a complete df with all dates from start to end date included. For cases where requests
        are not defined by start and end date but rather by periods, use the returned df without modifications
        We may put a standard date range here if no data is found

        :param df:
        :param station_id:
        :param parameter:
        :param dataset:
        :return:
        """
        if df.is_empty():
            return df
        if self._data_tz == Timezone.DYNAMIC:
            tzinfo = ZoneInfo(self._get_timezone_from_station(station_id))
        else:
            tzinfo = ZoneInfo(self.data_tz)
        start_date, end_date = self._adjust_start_end_date(self.sr.start_date, self.sr.end_date, tzinfo)
        base_df = self._get_base_df(start_date, end_date)
        data = []
        for (station_id, parameter), group in df.group_by(
            [Columns.STATION_ID.value, Columns.PARAMETER.value],
            maintain_order=True,
        ):
            par_df = base_df.join(
                other=group,
                on=[Columns.DATE.value],
                how="left",
            )
            par_df = par_df.with_columns(
                pl.lit(station_id).alias(Columns.STATION_ID.value),
                pl.lit(parameter).alias(Columns.PARAMETER.value),
            )
            data.append(par_df)
        return pl.concat(data)

    def _organize_df_columns(self, df: pl.DataFrame, station_id: str, dataset: Enum) -> pl.DataFrame:
        """
        Method to reorder index to always have the same order of columns

        :param df:
        :return:
        """
        columns = list(self._meta_fields.keys())
        columns.extend(set(df.columns).difference(columns))
        df = df.with_columns(
            pl.lit(station_id).alias(Columns.STATION_ID.value),
            pl.lit(dataset.name.lower()).alias(Columns.DATASET.value),
        )
        return df.select(pl.col(col) if col in df.columns else pl.lit(None).alias(col) for col in columns)

    def query(self) -> Iterator[ValuesResult]:
        """
        Core method for data collection, iterating of station ids and yielding a
        DataFrame for each station with all found parameters. Takes care of type
        coercion of data, date filtering and humanizing of parameters.

        :return:
        """
        # reset station stations_counter
        self.stations_counter = 0
        self.stations_collected = []

        # mapping of original to humanized parameter names is always the same
        if self.sr.humanize:
            hpm = self._create_humanized_parameters_mapping()
        datasets = [dataset.name.lower() for _, dataset in self.sr.parameter]

        for station_id in self.sr.station_id:
            if self.stations_counter == self.sr.rank:
                break

            # TODO: add method to return empty result with correct response string e.g.
            #  station id not available
            station_data = []

            for parameter, dataset in self.sr.parameter:
                parameter_df = self._collect_station_parameter(
                    station_id=station_id,
                    parameter=parameter,
                    dataset=dataset,
                )

                if parameter_df.is_empty():
                    parameter_df = self._create_empty_station_parameter_df(station_id=station_id, dataset=dataset)

                if parameter != dataset:
                    parameter_df = parameter_df.filter(pl.col(Columns.PARAMETER.value).eq(parameter.value.lower()))

                parameter_df = parameter_df.unique(
                    subset=[Columns.DATE.value, Columns.PARAMETER.value], maintain_order=True
                )

                # set dynamic resolution for services that have no fixed resolutions
                if self.sr.resolution == Resolution.DYNAMIC:
                    self.sr.stations.dynamic_frequency = self._fetch_frequency(station_id, parameter, dataset)

                if self.sr.start_date:
                    parameter_df = self._build_complete_df(parameter_df, station_id)

                parameter_df = self._organize_df_columns(parameter_df, station_id, dataset)

                station_data.append(parameter_df)

            try:
                station_df = pl.concat(station_data)
            except ValueError:
                station_df = pl.DataFrame()

            if self.sr.start_date:
                station_df = station_df.filter(
                    pl.col(Columns.DATE.value).is_between(
                        self.sr.start_date,
                        self.sr.end_date,
                        closed="both",
                    ),
                )

            if self.sr.skip_empty:
                percentage = self._get_actual_percentage(df=station_df)
                if percentage < self.sr.skip_threshold:
                    log.info(
                        f"station {station_id} is skipped as percentage of actual values ({percentage}) "
                        f"is below threshold ({self.sr.skip_threshold}).",
                    )
                    continue

            if self.sr.dropna:
                station_df = station_df.drop_nulls(subset="value")

            if not station_df.is_empty():
                if self.sr.si_units:
                    station_df = self._convert_values_to_si(station_df, datasets)

                if self.sr.humanize:
                    station_df = self._humanize(df=station_df, humanized_parameters_mapping=hpm)

                if not self.sr.tidy:
                    station_df = self._widen_df(df=station_df)

                if self.sr.tidy:
                    sort_columns = [Columns.DATASET.value, Columns.PARAMETER.value, Columns.DATE.value]
                else:
                    sort_columns = [Columns.DATASET.value, Columns.DATE.value]
                station_df = station_df.sort(sort_columns)

            self.stations_counter += 1
            self.stations_collected.append(station_id)

            yield ValuesResult(stations=self.sr, values=self, df=station_df)

    @abstractmethod
    def _collect_station_parameter(self, station_id: str, parameter: Enum, dataset: Enum) -> pl.DataFrame:
        """
        Implementation of data collection for a station id plus parameter from the
        specified weather service. Takes care of the gathering of the data and putting
        it in shape, either tabular with one parameter per column or tidied with a set
        of station id, date, parameter, value and quality in one row.

        :param station_id: station id for which the data is being collected
        :param parameter: parameter for which the data is collected
        :param dataset: dataset for which the data is collected
        :return: pandas.DataFrame with the data for given station id and parameter
        """
        pass

    @staticmethod
    def _widen_df(df: pl.DataFrame) -> pl.DataFrame:
        """
        Method to widen a dataframe with each row having one timestamp and
        all parameter values and corresponding quality levels.

        Example:

        date         parameter                  value   quality
        1971-01-01   precipitation_height       0       0
        1971-01-01   temperature_air_mean_2m   10      0

        becomes

        date         precipitation_height   qn_precipitation_height
        1971-01-01   0                      0
            temperature_air_mean_2m    ...
            10                          ...

        :param df: DataFrame with ts_shape data
        :returns DataFrame with widened data e.g. pairwise columns of values
        and quality flags
        """
        # if there is more than one dataset, we need to prefix parameter names with dataset names to avoid
        # column name conflicts
        if df.get_column(Columns.DATASET.value).unique().len() > 1:
            df = df.with_columns(
                pl.struct([pl.col(Columns.DATASET.value), pl.col(Columns.PARAMETER.value)])
                .map_elements(lambda x: f"""{x["dataset"]}_{x["parameter"]}""", return_dtype=pl.String)
                .alias(Columns.PARAMETER.value),
            )
        df_wide = df.select(
            [pl.col(Columns.STATION_ID.value), pl.col(Columns.DATASET.value), pl.col(Columns.DATE.value)],
        ).unique()

        for (parameter,), parameter_df in df.group_by([Columns.PARAMETER.value], maintain_order=True):
            # Build quality column name
            parameter_quality = f"{Columns.QUALITY_PREFIX.value}_{parameter}"
            parameter_df = parameter_df.select([Columns.DATE.value, Columns.VALUE.value, Columns.QUALITY.value]).rename(
                mapping={Columns.VALUE.value: parameter, Columns.QUALITY.value: parameter_quality},
            )
            df_wide = df_wide.join(parameter_df, on=[Columns.DATE.value])

        return df_wide

    def all(self) -> ValuesResult:  # noqa: A003
        """
        Collect all data from self.query

        :return:
        """
        data = []

        tqdm_out = TqdmToLogger(log, level=logging.INFO)

        for result in tqdm(self.query(), total=len(self.sr.station_id), file=tqdm_out):
            data.append(result.df)

        try:
            df = pl.concat(data)
        except ValueError:
            log.error("No data available for given constraints")
            return ValuesResult(stations=self.sr, values=self, df=pl.DataFrame())

        return ValuesResult(stations=self.sr, values=self, df=df)

    @staticmethod
    def _humanize(df: pl.DataFrame, humanized_parameters_mapping: dict[str, str]) -> pl.DataFrame:
        """
        Method for humanizing parameters.

        :param df: pandas.DataFrame with original column names
        :param humanized_parameters_mapping: mapping of original parameter names to humanized ones
        :return: pandas.DataFrame with renamed columns
        """
        return df.with_columns(pl.col(Columns.PARAMETER.value).replace(humanized_parameters_mapping))

    def _create_humanized_parameters_mapping(self) -> dict[str, str]:
        """
        Reduce the creation of parameter mapping of the massive amount of parameters
        by specifying the resolution.

        :return:
        """
        hpm = {}
        datasets = [
            dataset for dataset in self.sr._parameter_base[self.sr.resolution.name] if hasattr(dataset, "__name__")
        ]
        for dataset in datasets:
            for parameter in self.sr._parameter_base[self.sr.resolution.name][dataset.__name__]:
                try:
                    hpm[parameter.value.lower()] = parameter.name.lower()
                except AttributeError:
                    pass

        return hpm

    def _get_actual_percentage(self, df: pl.DataFrame) -> float:
        """
        Calculate percentage of actual values. The percentage is calculated
        per requested parameter and statistically aggregated to a float that
        can be compared with a threshold.
        :param df: pandas DataFrame with values
        :return: float of actual percentage of values
        """
        parameters = []
        for parameter, dataset in self.sr.parameter:
            if parameter != dataset:
                parameters.append(parameter.value)
            else:
                dataset_enum = self.sr.stations._parameter_base[self.sr.resolution.name][dataset.name]
                parameters.extend([par.value for par in dataset_enum if not par.name.lower().startswith("quality")])
        percentage = df.group_by(["parameter"]).agg(
            (pl.col("value").drop_nulls().len() / pl.col("value").len()).cast(pl.Float64).alias("perc"),
        )
        missing = pl.DataFrame(
            [{"parameter": par, "perc": 0.0} for par in parameters if par not in percentage.get_column("parameter")],
            schema={"parameter": pl.String, "perc": pl.Float64},
        )
        percentage = pl.concat([percentage, missing])
        if self.sr.settings.ts_skip_criteria == "min":
            return percentage.get_column("perc").min()
        elif self.sr.settings.ts_skip_criteria == "mean":
            return percentage.get_column("perc").mean()
        elif self.sr.settings.ts_skip_criteria == "max":
            return percentage.get_column("perc").max()
        else:
            raise KeyError("ts_skip_criteria must be one of min, mean, max")
