# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import datetime
import logging
import operator
from abc import ABCMeta, abstractmethod
from enum import Enum
from typing import Dict, Generator, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
import pytz
from pandas.api.types import is_datetime64_any_dtype as is_datetime
from pint import Quantity
from pytz import timezone
from timezonefinder import timezonefinder
from tqdm import tqdm

from wetterdienst.core.scalar.result import StationsResult, ValuesResult
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.metadata.unit import REGISTRY, OriginUnit, SIUnit
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.logging import TqdmToLogger

log = logging.getLogger(__name__)


class ScalarValuesCore(metaclass=ABCMeta):
    """Core for sources of point data where data is related to a station"""

    _tf = timezonefinder.TimezoneFinder()

    def __init__(self, stations_result: StationsResult) -> None:
        self.sr = stations_result

    @classmethod
    def from_stations(cls, stations: StationsResult):
        return cls(stations)

    def __eq__(self, other):
        """Equal method of request object"""
        return self.sr.stations == other.sr.stations and self.sr.station_id == other.sr.station_id

    def __repr__(self):
        """Representation of values object"""
        station_ids_joined = ", ".join(self.sr.station_id.tolist())
        parameters_joined = ", ".join(
            [f"({parameter.value}/{dataset.value})" for parameter, dataset in self.sr.stations.parameter]
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
    def _meta_fields(self) -> List[str]:
        """
        Metadata fields that are independent of actual values and should be parsed
        differently

        :return: list of strings representing the metadata fields/columns
        """
        if not self.sr.tidy:
            return [
                Columns.STATION_ID.value,
                Columns.DATASET.value,
                Columns.DATE.value,
            ]
        else:
            return [
                Columns.STATION_ID.value,
                Columns.DATASET.value,
                Columns.PARAMETER.value,
                Columns.DATE.value,
                Columns.VALUE.value,
                Columns.QUALITY.value,
            ]

    # Fields for date coercion
    _date_fields = [Columns.DATE.value, Columns.FROM_DATE.value, Columns.TO_DATE.value]

    # TODO: add data type (mosmix, observation, ...)

    @property
    def data_tz(self) -> timezone:
        """Timezone of the published data"""
        return timezone(self._data_tz.value)

    @property
    @abstractmethod
    def _data_tz(self) -> Timezone:
        """Timezone enumeration of published data."""
        pass

    @property
    @abstractmethod
    def _date_parameters(self) -> Tuple[str]:
        """Declaration of irregular parameters which will have to be parsed differently
        then others e.g. when a parameter is a date."""
        pass

    @property
    @abstractmethod
    def _irregular_parameters(self) -> Tuple[str]:
        """Declaration of irregular parameters which will have to be parsed differently
        then others e.g. when a parameter is a date."""
        pass

    @property
    @abstractmethod
    def _string_parameters(self) -> Tuple[str]:
        """String parameters that will be parsed to integers."""
        pass

    def fetch_dynamic_frequency(self, station_id, parameter: Enum, dataset: Enum) -> str:
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

    def _get_complete_dates(self, station_id) -> pd.DatetimeIndex:
        """
        Complete datetime index for the requested start and end date, used for
        building a complementary pandas DataFrame with the date column on which
        other DataFrames can be joined on

        :return: pandas.DatetimeIndex
        """
        start_date, end_date = self.sr.start_date, self.sr.end_date

        if self.sr.resolution == Resolution.MONTHLY:
            end_date += pd.Timedelta(days=31)
        elif self.sr.resolution == Resolution.ANNUAL:
            end_date += pd.Timedelta(days=366)

        if self._data_tz == Timezone.DYNAMIC:
            timezone_ = self._get_timezone_from_station(station_id)
        else:
            timezone_ = self.data_tz

        tz_delta = self._get_timedelta_from_timezones(timezone_, pytz.UTC)

        return pd.date_range(
            start_date + datetime.timedelta(hours=tz_delta),
            end_date + datetime.timedelta(hours=tz_delta),
            freq=self.sr.frequency.value,
            tz=pytz.UTC,
        )

    def _get_timezone_from_station(self, station_id: str) -> timezone:
        """
        Get timezone information for explicit station that is used to set the
        correct timezone for the timestamps of the returned values

        :param station_id: station id string
        :return: timezone
        """

        stations = self.sr.df

        station = stations[stations[Columns.STATION_ID.value] == station_id]

        longitude, latitude = station.loc[:, [Columns.LONGITUDE.value, Columns.LATITUDE.value]].T.values

        tz_string = self._tf.timezone_at(lng=longitude, lat=latitude)

        return timezone(tz_string)

    @staticmethod
    def _get_timedelta_from_timezones(tz1: timezone, tz2: timezone) -> float:
        """Method to get timedelta in hours (float) from two timezones

        :param tz1:
        :param tz2:
        :return:
        """
        dt_1970 = datetime.datetime(1970, 1, 1)

        dt_1970_tz1 = tz1.localize(dt_1970)
        dt_1970_tz2 = tz2.localize(dt_1970).astimezone(tz1)

        dt_diff = dt_1970_tz1 - dt_1970_tz2

        return dt_diff.days * 24 + dt_diff.seconds / 3600

    def _get_base_df(self, station_id: str) -> pd.DataFrame:
        """
        Base dataframe which is used for creating empty dataframes if no data is
        found or for merging other dataframes on the full dates

        :return: pandas DataFrame with a date column with complete dates
        """
        return pd.DataFrame({Columns.DATE.value: self._get_complete_dates(station_id)})

    def convert_values_to_si(self, df: pd.DataFrame, dataset) -> pd.DataFrame:
        """
        Function to convert values to metric units with help of conversion factors

        :param df: pandas DataFrame that should be converted to SI units
        :param dataset: dataset for which the conversion factors are created
        :return: pandas DataFrame with converted (SI) values
        """
        # TODO: THIS DOESNT CURRENTLY WORK WITH PREFIXED TIDY DATA
        def _convert_values_to_si(
            series,
            conv_factors: Dict[str, Tuple[Union[operator.add, operator.mul], float]],
            parameter: Optional[str] = None,
        ) -> pd.Series:
            """
            Helper function to apply conversion factors column wise to a pandas DataFrame

            :param series: pandas Series that should be converted
            :param parameter: optional parameter string used for tidy data
            :param conv_factors: dictionary of prepared conversion factors and operators
            :return: converted pandas Series
            """
            if not parameter:
                parameter = series.name

            op, factor = conv_factors.get(parameter, (None, None))

            if not op or not factor:
                return series

            return op(series, factor)

        conversion_factors = self._create_conversion_factors(dataset)

        if self.sr.tidy:
            data = []
            for par, group in df.groupby(Columns.PARAMETER.value, sort=False):
                group[Columns.VALUE.value] = group[Columns.VALUE.value].apply(
                    _convert_values_to_si, conv_factors=conversion_factors, parameter=par
                )
                data.append(group)
            try:
                return pd.concat(data, axis=0)
            except ValueError:
                return df

        return df.apply(_convert_values_to_si, axis=0, conv_factors=conversion_factors)

    def _create_conversion_factors(self, dataset) -> Dict[str, Tuple[Union[operator.add, operator.mul], float]]:
        """
        Function to create conversion factors based on a given dataset

        :param dataset: dataset for which conversion factors are created
        :return: dictionary with conversion factors for given parameter name
        """
        dataset = dataset.name

        dataset_accessor = self.sr._dataset_accessor

        if self.sr._unique_dataset or not self.sr._has_datasets:
            units = self.sr._unit_tree[dataset_accessor]
        else:
            units = self.sr._unit_tree[dataset_accessor][dataset]

        conversion_factors = {}

        for parameter in units:
            if self.sr._unique_dataset or not self.sr._has_datasets:
                parameter_name = self.sr._parameter_base[dataset_accessor][parameter.name].value.lower()
            else:
                parameter_name = self.sr._parameter_base[dataset_accessor][dataset][parameter.name].value.lower()

            conversion_factors[parameter_name] = self._get_conversion_factor(*parameter.value)

        return conversion_factors

    @staticmethod
    def _get_conversion_factor(origin_unit: Enum, si_unit: Enum) -> Tuple[Union[operator.mul, operator.add], float]:
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
            return operator.mul, factor
        else:
            # For multiplicative units we need to use 1 as quantity to apply the
            # appropriate factor
            factor = Quantity(1, origin_unit).to(si_unit).magnitude
            return operator.mul, factor

    def _create_empty_station_parameter_df(self, station_id: str, parameter: Enum, dataset: Enum) -> pd.DataFrame:
        """
        Function to create an empty DataFrame
        :param station_id:
        :param parameter:
        :return:
        """
        parameter_base = self.sr._parameter_base
        resolution = self.sr.resolution

        # if parameter is a whole dataset, take every parameter from the dataset instead
        if self.sr._unique_dataset or not self.sr._has_datasets:
            parameter = [*parameter_base[resolution.name]]
        else:
            parameter = [*parameter_base[resolution.name][dataset.name]]

        if self.sr._has_tidy_data:
            if not self.sr.start_date:
                return pd.DataFrame(columns=self._meta_fields)

            data = []
            default_df = self._get_base_df(station_id)
            for par in pd.Series(parameter):
                if par.name.startswith("QUALITY"):
                    continue
                par_df = default_df.copy()
                par_df[Columns.PARAMETER.value] = par.value

                data.append(par_df)

            df = pd.concat(data)

            df[Columns.VALUE.value] = pd.NA
            df[Columns.QUALITY.value] = pd.NA

            return df
        else:
            parameter = pd.Series(parameter).map(lambda x: x.value).tolist()
            # Base columns
            columns = [Columns.STATION_ID.value, Columns.DATE.value, *parameter]

            if not self.sr.start_date:
                return pd.DataFrame(columns=columns)

            df = self._get_base_df(station_id)

            return df.reindex(columns=columns)

    def _build_complete_df(self, df: pd.DataFrame, station_id: str, parameter: Enum, dataset: Enum) -> pd.DataFrame:
        """Method to build a complete df with all dates from start to end date included.

        :param df:
        :param station_id:
        :param parameter:
        :param dataset:
        :return:
        """
        if parameter != dataset or not self.sr.tidy:
            base_df = self._get_base_df(station_id)

            df = pd.merge(
                left=base_df,
                right=df,
                left_on=Columns.DATE.value,
                right_on=Columns.DATE.value,
                how="left",
            )

            if self.sr.tidy:
                df[Columns.PARAMETER.value] = parameter.value
                df[Columns.PARAMETER.value] = pd.Categorical(df.loc[:, Columns.PARAMETER.value])

            return df
        else:
            data = []
            for parameter, group in df.groupby(Columns.PARAMETER.value, sort=False):
                if self.sr._unique_dataset:
                    parameter_ = parse_enumeration_from_template(
                        parameter,
                        self.sr._parameter_base[self.sr.resolution.name],
                    )
                else:
                    parameter_ = parse_enumeration_from_template(
                        parameter,
                        self.sr._parameter_base[self.sr._dataset_accessor][dataset.name],
                    )

                df = pd.merge(
                    left=self._get_base_df(station_id),
                    right=group,
                    left_on=Columns.DATE.value,
                    right_on=Columns.DATE.value,
                    how="left",
                )

                df[Columns.PARAMETER.value] = parameter_.value.lower()

                data.append(df)

            return pd.concat(data)

    def _organize_df_columns(self, df: pd.DataFrame, station_id: str, dataset: Enum) -> pd.DataFrame:
        """
        Method to reorder index to always have the same order of columns

        :param df:
        :return:
        """
        columns = self._meta_fields.copy()
        columns.extend(df.columns.difference(columns, sort=False))
        df[Columns.STATION_ID.value] = station_id
        df[Columns.DATASET.value] = dataset.name.lower()
        return df.reindex(columns=columns)

    def query(self) -> Generator[ValuesResult, None, None]:
        """
        Core method for data collection, iterating of station ids and yielding a
        DataFrame for each station with all found parameters. Takes care of type
        coercion of data, date filtering and humanizing of parameters.

        :return:
        """
        # mapping of original to humanized parameter names is always the same
        if self.sr.humanize:
            hpm = self._create_humanized_parameters_mapping()

        for station_id in self.sr.station_id:
            # TODO: add method to return empty result with correct response string e.g.
            #  station id not available
            station_data = []

            for parameter, dataset in self.sr.parameter:
                single_tidy_date_parameters = self.sr.tidy and parameter.value in self._date_parameters
                if single_tidy_date_parameters:
                    log.warning(
                        f"parameter {parameter.value} is skipped in tidy format "
                        f"as the date parameter is currently not converted to float"
                    )
                    continue

                parameter_df = self._collect_station_parameter(station_id, parameter, dataset)

                if parameter_df.empty:
                    parameter_df = self._create_empty_station_parameter_df(station_id, parameter, dataset)

                # set dynamic resolution for services that have no fixed resolutions
                if self.sr.resolution == Resolution.DYNAMIC:
                    self.sr.stations.dynamic_frequency = self.fetch_dynamic_frequency(station_id, parameter, dataset)

                # TODO: we are coercing values here for conversion of units
                #  however we later again coerce when concatenating DataFrames
                parameter_df = self._coerce_parameter_types(parameter_df)

                if self.sr.tidy:
                    if not self.sr._has_tidy_data:
                        parameter_df = self.tidy_up_df(parameter_df, dataset)

                    if Columns.PARAMETER.value not in parameter_df:
                        parameter_df[Columns.PARAMETER.value] = parameter.value.lower()

                    if parameter != dataset:
                        parameter_df = parameter_df.loc[
                            parameter_df[Columns.PARAMETER.value] == parameter.value.lower(), :
                        ]
                elif self.sr._has_tidy_data:
                    parameter_df = self.tabulate_df(parameter_df)

                if not parameter_df.empty and self.sr.si_units:
                    parameter_df = self.convert_values_to_si(parameter_df, dataset)

                # Skip date fields in tidy format, no further check required as still
                # "normal" parameters should be available
                if self.sr.tidy and self._date_parameters:
                    parameter_df = parameter_df.loc[
                        ~parameter_df.loc[:, Columns.PARAMETER.value].isin(self._date_parameters), :
                    ]
                    if parameter_df.empty:
                        continue

                # ensure meta columns content
                parameter_df[Columns.STATION_ID.value] = station_id
                parameter_df[Columns.DATASET.value] = dataset.name.lower()

                parameter_df = self._coerce_date_fields(parameter_df, station_id)

                # Merge on full date range if values are found to ensure result
                # even if no actual values exist
                # For cases where requests are not defined by start and end date but rather by
                # periods, use the returned df without modifications
                # We may put a standard date range here if no data is found
                if self.sr.start_date:
                    parameter_df = self._build_complete_df(parameter_df, station_id, parameter, dataset)

                parameter_df = self._organize_df_columns(parameter_df, station_id, dataset)

                station_data.append(parameter_df)

            try:
                station_df = pd.concat(station_data, ignore_index=True)
            except ValueError:
                station_df = pd.DataFrame()

            if self.sr.skip_empty:
                ap = self._get_actual_percentage(station_df)

                if ap < self.sr.skip_threshold:
                    log.info(
                        f"station {station_id} is skipped as percentage of actual values ({ap}) "
                        f"is below threshold ({self.sr.skip_threshold})."
                    )
                    continue

            if self.sr.dropna:
                station_df = station_df.loc[station_df.value.notna(), :].reset_index(drop=True)

            station_df = self._coerce_meta_fields(station_df)

            # Filter for dates range if start_date and end_date are defined
            if not station_df.empty and self.sr.start_date:
                station_df = station_df.loc[
                    (station_df[Columns.DATE.value] >= self.sr.start_date)
                    & (station_df[Columns.DATE.value] <= self.sr.end_date),
                    :,
                ]

            station_df = self._coerce_parameter_types(station_df)

            # Assign meaningful parameter names (humanized).
            if self.sr.humanize:
                station_df = self._humanize(station_df, hpm)

            yield ValuesResult(stations=self.sr, df=station_df)

    @abstractmethod
    def _collect_station_parameter(self, station_id: str, parameter: Enum, dataset: Enum) -> pd.DataFrame:
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

    def tidy_up_df(self, df: pd.DataFrame, dataset: Enum) -> pd.DataFrame:
        """
        Function to tidy a DataFrame

        :param df:
        :param dataset:
        :return:
        """
        df = self._tidy_up_df(df, dataset)

        df[Columns.VALUE.value] = pd.to_numeric(df[Columns.VALUE.value]).astype(float)

        if Columns.QUALITY.value not in df:
            df[Columns.QUALITY.value] = np.nan

        df[Columns.QUALITY.value] = pd.to_numeric(df[Columns.QUALITY.value]).astype(float)

        # Set quality of NaN values to NaN as well
        df.loc[df[Columns.VALUE.value].isna(), Columns.QUALITY.value] = np.nan

        return df

    def _tidy_up_df(self, df: pd.DataFrame, dataset) -> pd.DataFrame:
        """
        Abstract method to be implemented by services to tidy a DataFrame if
        tidy is not provided tidy by default

        :param df:
        :return:
        """
        if not self.sr._has_tidy_data:
            raise NotImplementedError("implement _tidy_up_df method to tidy data")

    @staticmethod
    def tabulate_df(df: pd.DataFrame) -> pd.DataFrame:
        """
        Method to tabulate a dataframe with each row having one timestamp and
        all parameter values and corresponding quality levels.

        Example:

        date         parameter                  value   quality
        1971-01-01   precipitation_height       0       0
        1971-01-01   temperature_air_mean_200   10      0

        becomes

        date         precipitation_height   qn_precipitation_height
        1971-01-01   0                      0
            temperature_air_mean_200    ...
            10                          ...

        :param df: pandas.DataFrame with tidy data
        :returns pandas.DataFrame with tabulated data e.g. pairwise columns of values
        and quality flags
        """
        df_tabulated = df.loc[:, [Columns.DATE.value]].copy()

        for parameter, parameter_df in df.groupby(by=[df[Columns.PARAMETER.value]]):
            # Build quality column name
            parameter_quality = f"{Columns.QUALITY_PREFIX.value}_{parameter}"
            df_tabulated.loc[:, parameter] = parameter_df[Columns.VALUE.value]
            df_tabulated.loc[:, parameter_quality] = parameter_df[Columns.QUALITY.value]

        return df_tabulated

    def _coerce_date_fields(self, df: pd.DataFrame, station_id: str) -> pd.DataFrame:
        """
        Function for coercion of possible date fields

        :param df:
        :return:
        """
        if self._data_tz == Timezone.DYNAMIC:
            timezone_ = self._get_timezone_from_station(station_id)
        else:
            timezone_ = self.data_tz

        for column in (
            Columns.DATE.value,
            Columns.FROM_DATE.value,
            Columns.TO_DATE.value,
        ):
            try:
                df[column] = self._coerce_dates(df[column], timezone_)
            except KeyError:
                pass

        return df

    def _coerce_meta_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Method that coerces meta fields. Those fields are expected to be found in the
        DataFrame in a columnar shape. Thore are basically the station id and the date
        fields. Furthermore if the data is tidied parameter can be found as well as
        quality. For station id, parameter and quality those columns are additionally
        coerced to categories to reduce consumption of the DataFrame.

        :param df: pandas.DataFrame with the "fresh" data
        :return: pandas.DataFrame with meta fields being coerced
        """
        df[Columns.STATION_ID.value] = self._parse_station_id(df[Columns.STATION_ID.value]).astype("category")
        df[Columns.DATASET.value] = self._coerce_strings(df[Columns.DATASET.value]).astype("category")

        if self.sr.stations.tidy:
            df[Columns.PARAMETER.value] = self._coerce_strings(df[Columns.PARAMETER.value]).astype("category")
            df[Columns.VALUE.value] = df[Columns.VALUE.value].astype(pd.Float64Dtype()).astype(float)
            df[Columns.QUALITY.value] = df[Columns.QUALITY.value].astype(pd.Float64Dtype()).astype(float)

        return df

    def _parse_station_id(self, series: pd.Series) -> pd.Series:
        """
        Dedicated method for parsing station ids, by default uses the same method as
        parse_strings but could be modified by the implementation class

        :param series:
        :return:
        """
        return self.sr.stations._parse_station_id(series)

    def _coerce_dates(self, series: pd.Series, timezone_: timezone) -> pd.Series:
        """
        Method to parse dates in the pandas.DataFrame. Leverages the data timezone
        attribute to ensure correct comparison of dates.

        :param series:
        :return:
        """
        if not is_datetime(series):
            series = pd.Series(series.map(lambda x: pd.Timestamp(x)))
        if not series.dt.tz:
            series = series.dt.tz_localize(timezone_)
        return series.dt.tz_convert(pytz.UTC)

    @staticmethod
    def _coerce_strings(series: pd.Series) -> pd.Series:
        """
        Method to parse strings for type coercion.

        :param series:
        :return:
        """
        return series.astype(pd.StringDtype())

    @staticmethod
    def _coerce_floats(series: pd.Series) -> pd.Series:
        """
        Method to parse floats for type coercion.

        :param series:
        :return:
        """
        return pd.to_numeric(series, errors="coerce").astype(float)

    def _coerce_irregular_parameter(self, series: pd.Series) -> pd.Series:
        """
        Method to parse irregular parameters. This will raise an error if an
        implementation has defined irregular parameters but has not implemented its own
        method of parsing irregular parameters.

        :param series:
        :return:
        """
        if self._irregular_parameters:
            raise NotImplementedError("implement _parse_irregular_parameter " "method to parse irregular parameters")

        return pd.Series(series)

    def _coerce_parameter_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Method for parameter type coercion. Depending on the shape of the data.

        :param df:
        :return:
        """
        for column in df.columns:
            if column in self._meta_fields or column in self._date_fields:
                continue
            if column in self._irregular_parameters:
                df[column] = self._coerce_irregular_parameter(df[column])
            elif column in self._string_parameters:
                df[column] = self._coerce_strings(df[column])
            else:
                df[column] = self._coerce_floats(df[column])

        return df

    def all(self) -> ValuesResult:
        """
        Collect all data from self.query

        :return:
        """
        data = []

        tqdm_out = TqdmToLogger(log, level=logging.INFO)

        for result in tqdm(self.query(), total=len(self.sr.station_id), file=tqdm_out):
            data.append(result.df)

        try:
            df = pd.concat(data, ignore_index=True)
        except ValueError:
            log.error("No data available for given constraints")
            return ValuesResult(stations=self.sr, df=pd.DataFrame())

        # Have to reapply category dtype after concatenation
        df = self._coerce_meta_fields(df)

        return ValuesResult(stations=self.sr, df=df)

    def _humanize(self, df: pd.DataFrame, humanized_parameters_mapping: Dict[str, str]) -> pd.DataFrame:
        """
        Method for humanizing parameters.

        :param df: pandas.DataFrame with original column names
        :param humanized_parameters_mapping: mapping of original parameter names to humanized ones
        :return: pandas.DataFrame with renamed columns
        """
        if not self.sr.tidy:
            df = df.rename(columns=humanized_parameters_mapping)
        else:
            df[Columns.PARAMETER.value] = (
                df.loc[:, Columns.PARAMETER.value].map(humanized_parameters_mapping).astype("category")
            )

        return df

    def _create_humanized_parameters_mapping(self) -> Dict[str, str]:
        """
        Reduce the creation of parameter mapping of the massive amount of parameters
        by specifying the resolution.

        :return:
        """
        hpm = {}
        if self.sr._unique_dataset or not self.sr._has_datasets:
            for parameter in self.sr._parameter_base[self.sr.resolution.name]:
                try:
                    hpm[parameter.value.lower()] = parameter.name.lower()
                except AttributeError:
                    pass
        else:
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

    @staticmethod
    def _get_actual_percentage(df: pd.DataFrame) -> float:
        """Calculate percentage of actual values"""
        return df.groupby("parameter").apply(lambda x: x.value.dropna().size / x.value.size).min()
