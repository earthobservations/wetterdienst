# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from abc import abstractmethod
from enum import Enum
from typing import Dict, Generator, Tuple, Union

import pandas as pd
from pytz import timezone
from tqdm import tqdm

from wetterdienst.core.scalar.result import StationsResult, ValuesResult
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.resolution import Resolution, ResolutionType
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.util.enumeration import parse_enumeration_from_template


class ScalarValuesCore:
    """ Core for sources of point data where data is related to a station """

    # Fields for type coercion, needed for separation from fields with actual data
    # that have to be parsed differently when having data in tabular form
    _meta_fields = [
        Columns.STATION_ID.value,
        Columns.DATE.value,
        Columns.PARAMETER.value,
        Columns.QUALITY.value,
    ]

    # Fields for date coercion
    _date_fields = [Columns.DATE.value, Columns.FROM_DATE.value, Columns.TO_DATE.value]

    # TODO: add data type (forecast, observation, ...)
    @property
    @abstractmethod
    def _has_quality(self) -> bool:
        """Attribute that tells if a weather service has quality, which otherwise will
        have to be set to NaN"""
        pass

    @property
    def data_tz(self) -> timezone:
        """ Timezone of the published data """
        return timezone(self._data_tz.value)

    @property
    @abstractmethod
    def _data_tz(self) -> Timezone:
        """ Timezone enumeration of published data. """
        pass

    @property
    @abstractmethod
    def _irregular_parameters(self) -> Tuple[str]:
        """Declaration of irregular parameters which will have to be parsed differently
        then others e.g. when a parameter is a date."""
        pass

    @property
    @abstractmethod
    def _integer_parameters(self) -> Tuple[str]:
        """ Integer parameters that will be parsed to integers. """
        pass

    @property
    @abstractmethod
    def _string_parameters(self) -> Tuple[str]:
        """ String parameters that will be parsed to integers. """
        pass

    @property
    def _complete_dates(self) -> pd.DatetimeIndex:
        start_date, end_date = self.stations.start_date, self.stations.end_date

        if self.stations.stations.resolution == Resolution.MONTHLY:
            end_date += pd.Timedelta(days=31)
        elif self.stations.stations.resolution == Resolution.ANNUAL:
            end_date += pd.Timedelta(year=366)

        date_range = pd.date_range(
            start_date,
            end_date,
            freq=self.stations.frequency.value,
            tz=self.data_tz,
        )

        return date_range

    @property
    def _base_df(self) -> pd.DataFrame:
        """Base dataframe which is used for creating empty dataframes if no data is
        found or for merging other dataframes on the full dates"""
        return pd.DataFrame({Columns.DATE.value: self._complete_dates})

    @staticmethod
    def _determine_resolution(series: pd.Series) -> Resolution:
        pass

    def __init__(self, stations: StationsResult) -> None:
        self.stations = stations

    @classmethod
    def from_stations(cls, stations: StationsResult):
        return cls(stations)

    def __eq__(self, other):
        """ Equal method of request object """
        return (
            self.stations.station_id == other.stations.station_id
            and self.stations.parameter == other.stations.parameter
            and self.stations.start_date == other.stations.start_date
            and self.stations.end_date == other.stations.end_date
        )
        pass

    def __str__(self):
        """ Str representation of request object """
        # TODO: include source
        # TODO: include data type
        station_ids_joined = "& ".join(
            [str(station_id) for station_id in self.stations.station_id]
        )

        parameters_joined = "& ".join(
            [
                parameter.value
                for parameter, parameter_set in self.stations.stations.parameter
            ]
        )

        return ", ".join(
            [
                f"station_ids {station_ids_joined}",
                f"parameters {parameters_joined}",
                str(self.stations.start_date),
                str(self.stations.end_date),
            ]
        )
        pass

    def _get_empty_station_parameter_df(
        self, station_id: str, parameter: Union[Enum, Tuple[Enum, Enum]]
    ) -> pd.DataFrame:
        dataset_tree = self.stations.stations._dataset_tree
        resolution = self.stations.stations.resolution

        dataset = None
        # Split parameter into parameter and dataset if parameters are stored in dataset
        if self.stations.stations._has_datasets:
            parameter, dataset = parameter

        # if parameter is a whole dataset, take every parameter from the dataset instead
        if parameter == dataset:
            if self.stations.stations._unique_dataset:
                parameter = [*dataset_tree[resolution.name]]
            else:
                parameter = [*dataset_tree[resolution.name][dataset.name]]

        if self.stations.stations.tidy:
            data = []
            for par in pd.Series(parameter):
                if par.name.startswith("QUALITY"):
                    continue

                par_df = self._base_df
                par_df[Columns.PARAMETER.value] = par.value

                data.append(par_df)

            df = pd.concat(data)

            df[Columns.STATION_ID.value] = station_id
            df[Columns.DATASET.value] = dataset.name
            df[Columns.VALUE.value] = pd.NA
            df[Columns.QUALITY.value] = pd.NA

            return df
        else:
            df = self._base_df
            parameter = pd.Series(parameter).map(lambda x: x.value).tolist()

            # Base columns
            columns = [Columns.STATION_ID.value, Columns.DATE.value, *parameter]

            df = df.reindex(columns=columns)

            df[Columns.STATION_ID.value] = station_id

            return df

    def _build_complete_df(
        self, df: pd.DataFrame, station_id: str, parameter: Enum
    ) -> pd.DataFrame:
        # For cases where requests are not defined by start and end date but rather by
        # periods, use the returned df without modifications
        # We may put a standard date range here if no data is found
        if not self.stations.start_date:
            return df

        dataset = None
        if self.stations.stations._has_datasets:
            parameter, dataset = parameter

        if parameter != dataset or not self.stations.stations.tidy:
            df = pd.merge(
                left=self._base_df,
                right=df,
                left_on=Columns.DATE.value,
                right_on=Columns.DATE.value,
                how="left",
            )

            df[Columns.STATION_ID.value] = station_id

            if self.stations.tidy:
                df[Columns.PARAMETER.value] = parameter.value
                df[Columns.PARAMETER.value] = pd.Categorical(
                    df[Columns.PARAMETER.value]
                )

                if dataset:
                    df[Columns.DATASET.value] = dataset.name.lower()
                    df[Columns.DATASET.value] = pd.Categorical(
                        df[Columns.DATASET.value]
                    )

            return df
        else:
            data = []
            for parameter, group in df.groupby(Columns.PARAMETER.value, sort=False):
                if self.stations.stations._unique_dataset:
                    parameter_ = parse_enumeration_from_template(
                        parameter,
                        self.stations.stations._parameter_base[
                            self.stations.resolution.name
                        ],
                    )
                else:
                    parameter_ = parse_enumeration_from_template(
                        parameter,
                        self.stations.stations._dataset_tree[
                            self.stations.resolution.name
                        ][dataset.name],
                    )

                df = pd.merge(
                    left=self._base_df,
                    right=group,
                    left_on=Columns.DATE.value,
                    right_on=Columns.DATE.value,
                    how="left",
                )

                df[Columns.STATION_ID.value] = station_id

                df[Columns.PARAMETER.value] = parameter_.value

                df[Columns.DATASET.value] = dataset.name.lower()
                df[Columns.DATASET.value] = pd.Categorical(df[Columns.DATASET.value])

                data.append(df)

            return pd.concat(data)

    def query(self) -> Generator[ValuesResult, None, None]:
        """Core method for data collection, iterating of station ids and yielding a
        DataFrame for each station with all found parameters. Takes care of type
        coercion of data, date filtering and humanizing of parameters."""
        for station_id in self.stations.station_id:
            # TODO: add method to return empty result with correct response string e.g.
            #  station id not available
            station_data = []

            for parameter in self.stations.parameter:
                parameter_df = self._collect_station_parameter(station_id, parameter)

                # TODO: solve exceptional case where empty df and dynamic resolution
                if self.stations._resolution_type == ResolutionType.DYNAMIC:
                    self.stations.resolution = self._determine_resolution(
                        parameter_df[Columns.DATE.value]
                    )

                # TODO: move tidying of data outside collect method to apply it here
                #  after collecting data/ if data is empty "tidy" the created base_df
                #  instead
                if parameter_df.empty:
                    parameter_df = self._get_empty_station_parameter_df(
                        station_id, parameter
                    )
                else:
                    # Merge on full date range if values are found to ensure result
                    # even if no actual values exist
                    self._coerce_date_fields(parameter_df)

                    parameter_df = self._build_complete_df(
                        parameter_df, station_id, parameter
                    )

                station_data.append(parameter_df)

            station_df = pd.concat(station_data, ignore_index=True)

            station_df = self._coerce_meta_fields(station_df)
            station_df = self._coerce_parameter_types(station_df)

            # Filter for dates range if start_date and end_date are defined
            if self.stations.start_date:
                # df_station may be empty depending on if station has data for given
                # constraints
                try:
                    station_df = station_df[
                        (station_df[Columns.DATE.value] >= self.stations.start_date)
                        & (station_df[Columns.DATE.value] <= self.stations.end_date)
                    ]
                except KeyError:
                    pass

            # Assign meaningful parameter names (humanized).
            if self.stations.humanize:
                station_df = self._humanize(station_df)

            # Empty dataframe should be skipped
            if station_df.empty:
                continue

            # TODO: add meaningful metadata here
            yield ValuesResult(stations=self.stations, df=station_df)

    @abstractmethod
    def _collect_station_parameter(self, station_id: str, parameter) -> pd.DataFrame:
        """
        Implementation of data collection for a station id plus parameter from the
        specified weather service. Takes care of the gathering of the data and putting
        it in shape, either tabular with one parameter per column or tidied with a set
        of station id, date, parameter, value and quality in one row.

        :param station_id: station id for which the data is being collected
        :param parameter: parameter for which the data is collected, parameter could
        also be a tuple or a more complex object depending on the self._parse_parameters
        function
        :return: pandas.DataFrame with the data for given station id and parameter
        """
        pass

    def _coerce_date_fields(self, df: pd.DataFrame) -> pd.DataFrame:
        """ Function for coercion of possible date fields """
        for column in (
            Columns.DATE.value,
            Columns.FROM_DATE.value,
            Columns.TO_DATE.value,
        ):
            try:
                df[column] = self._coerce_dates(df[column])
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
        df[Columns.STATION_ID.value] = self._parse_station_id(
            df[Columns.STATION_ID.value]
        ).astype("category")

        if self.stations.tidy:
            df[Columns.PARAMETER.value] = self._coerce_strings(
                df[Columns.PARAMETER.value]
            ).astype("category")

            if self._has_quality:
                df[Columns.QUALITY.value] = self._coerce_integers(
                    df[Columns.QUALITY.value]
                ).astype("category")

        return df

    def _parse_station_id(self, series: pd.Series) -> pd.Series:
        """Dedicated method for parsing station ids, by default uses the same method as
        parse_strings but could be modified by the implementation class"""
        return self.stations.stations._parse_station_id(series)

    def _coerce_dates(self, series: pd.Series) -> pd.Series:
        """Method to parse dates in the pandas.DataFrame. Leverages the data timezone
        attribute to ensure correct comparison of dates."""
        return pd.to_datetime(series, infer_datetime_format=True).dt.tz_localize(
            self.data_tz
        )

    @staticmethod
    def _coerce_integers(series: pd.Series) -> pd.Series:
        """Method to parse integers for type coercion. Uses pandas.Int64Dtype() to
        allow missing values."""
        return pd.to_numeric(series, errors="coerce").astype(pd.Int64Dtype())

    @staticmethod
    def _coerce_strings(series: pd.Series) -> pd.Series:
        """ Method to parse strings for type coercion. """
        return series.astype(pd.StringDtype())

    @staticmethod
    def _coerce_floats(series: pd.Series) -> pd.Series:
        """ Method to parse floats for type coercion. """
        return pd.to_numeric(series, errors="coerce")

    def _coerce_irregular_parameter(self, series: pd.Series) -> pd.Series:
        """Method to parse irregular parameters. This will raise an error if an
        implementation has defined irregular parameters but has not implemented its own
        method of parsing irregular parameters."""
        if self._irregular_parameters:
            raise NotImplementedError(
                "implement _parse_irregular_parameter "
                "method to parse irregular parameters"
            )

        return pd.Series(series)

    def _coerce_parameter_types(self, df: pd.DataFrame) -> pd.DataFrame:
        """ Method for parameter type coercion. Depending on the shape of the data. """
        if not self.stations.tidy:
            for column in df.columns:
                if column in self._meta_fields or column in self._date_fields:
                    continue
                if column in self._irregular_parameters:
                    df[column] = self._coerce_irregular_parameter(df[column])
                elif column in self._integer_parameters or column.startswith(
                    Columns.QUALITY_PREFIX.value
                ):
                    df[column] = self._coerce_integers(df[column])
                elif column in self._string_parameters:
                    df[column] = self._coerce_strings(df[column])
                else:
                    df[column] = self._coerce_floats(df[column])

            return df

        data = []
        for parameter, group in df.groupby(Columns.PARAMETER.value, sort=False):
            if parameter in self._irregular_parameters:
                group[Columns.VALUE.value] = self._coerce_irregular_parameter(
                    group[Columns.VALUE.value]
                )
            elif parameter in self._integer_parameters:
                group[Columns.VALUE.value] = self._coerce_integers(
                    group[Columns.VALUE.value]
                )
            elif parameter in self._string_parameters:
                group[Columns.VALUE.value] = self._coerce_strings(
                    group[Columns.VALUE.value]
                )
            else:
                group[Columns.VALUE.value] = self._coerce_floats(
                    group[Columns.VALUE.value]
                )

            data.append(group)

        df = pd.concat(data)

        return df

    def all(self) -> ValuesResult:
        """ Collect all data from self.collect_data """
        data = []

        for result in tqdm(self.query(), total=len(self.stations.station_id)):
            data.append(result.df)

        if not data:
            raise ValueError("No data available for given constraints")

        df = pd.concat(data, ignore_index=True)

        # Have to reapply category dtype after concatenation
        for column in (
            Columns.STATION_ID.value,
            Columns.PARAMETER.value,
            Columns.QUALITY.value,
        ):
            try:
                df[column] = df[column].astype("category")
            except KeyError:
                pass

        df.attrs["tidy"] = self.stations.tidy

        return ValuesResult(stations=self.stations, df=df)

    def _humanize(self, df: pd.DataFrame) -> pd.DataFrame:
        """ Method for humanizing parameters. """
        hcnm = self._create_humanized_parameters_mapping()

        if not self.stations.tidy:
            df = df.rename(columns=hcnm)
        else:
            df[Columns.PARAMETER.value] = df[
                Columns.PARAMETER.value
            ].cat.rename_categories(hcnm)

        return df

    def _create_humanized_parameters_mapping(self) -> Dict[str, str]:
        """Method for creation of parameter name mappings based on
        self._parameter_base"""
        hcnm = {
            parameter.value: parameter.name
            for parameter in self.stations.stations._parameter_base
        }

        return hcnm
