# -*- coding: utf-8 -*-
from abc import abstractmethod
from datetime import datetime
from enum import Enum
from typing import Tuple, Union, Optional, List, Generator, Dict
from logging import getLogger

import dateparser
import pandas as pd
import pytz
from pytz import timezone
from pandas._libs.tslibs.timestamps import Timestamp

from wetterdienst.core.core import Core
from wetterdienst.exceptions import NoParametersFound, StartDateEndDateError
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.result import Result
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.util.enumeration import parse_enumeration_from_template


log = getLogger(__name__)


class PointDataCore(Core):
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

    # TODO: add frequency property that defines the expected time steps of the returned
    #  data. This will help us return equal results whether or not there actually is
    #  data

    # TODO: add data type (forecast, observation, ...)

    # TODO: think about adding untidy/tidy tabular/row-based attribute as we already
    #  have two sources of data with both schemes

    @property
    @abstractmethod
    def _tidy(self) -> bool:
        """Attribute that tells if data is tidy or has a tidy argument meaning that it
        may have two different shapes (column-based/tabular vs row-based)"""
        pass

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
    @abstractmethod
    def _parameter_base(self) -> Enum:
        """parameter base enumeration from which parameters can be parsed e.g.
        DWDObservationParameter"""
        pass

    def __init__(
        self,
        station_ids: Tuple[str],
        parameters: Tuple[Union[str, Enum]],
        start_date: Optional[Union[str, Timestamp, datetime]] = None,
        end_date: Optional[Union[str, Timestamp, datetime]] = None,
        humanize_parameters: bool = False,
    ) -> None:
        """

        :param station_ids: station ids for which data is requested
        :param parameters: parameters either as strings or enumerations for which data
        is requested
        :param start_date: start date of the resulting data,
        if not start_date: start_date = end_date
        :param end_date: end date of the resulting data
        if not end_date: end_date = start_date
        :param humanize_parameters: bool if parameters should be renamed to meaningful
        names
        """
        # Make sure we receive a list of ids
        self.station_ids = pd.Series(station_ids).astype(str).tolist()
        self.parameters = self._parse_parameters(parameters)

        # TODO: replace this with a response + logging
        # TODO: move this to self.collect_data
        if not self.parameters:
            raise NoParametersFound(f"No parameters could be parsed from {parameters}")

        if start_date or end_date:
            # If only one date given, set the other one to equal
            if not start_date:
                start_date = end_date

            if not end_date:
                end_date = start_date

            # TODO: use dynamic parsing that accepts entered timestamps with given
            #  timezone
            start_date = Timestamp(dateparser.parse(str(start_date)), tz=pytz.UTC)
            end_date = Timestamp(dateparser.parse(str(end_date)), tz=pytz.UTC)

            # TODO: replace this with a response + logging
            if not start_date <= end_date:
                raise StartDateEndDateError(
                    "Error: 'start_date' must be smaller or equal to 'end_date'."
                )

        self.start_date = start_date
        self.end_date = end_date
        self.humanize_parameters = humanize_parameters

    def __eq__(self, other):
        """ Equal method of request object """
        return (
            self.station_ids == other.station_ids
            and self.parameters == other.parameters
            and self.start_date == other.start_date
            and self.end_date == other.end_date
        )

    def __str__(self):
        """ Str representation of request object """
        # TODO: include source
        # TODO: include data type
        station_ids_joined = "& ".join(
            [str(station_id) for station_id in self.station_ids]
        )

        parameters_joined = "& ".join(
            [parameter.value for parameter, parameter_set in self.parameters]
        )

        return ", ".join(
            [
                f"station_ids {station_ids_joined}",
                f"parameters {parameters_joined}",
                self.start_date.value,
                self.end_date.value,
            ]
        )

    def _parse_parameters(self, parameters: List[Union[str, Enum]]) -> List[Enum]:
        """
        Method to parse parameters, either from string or enum. Case independent for
        strings.

        :param parameters: parameters as strings or enumerations
        :return: list of parameter enumerations of type self._parameter_base
        """
        return (
            pd.Series(parameters)
            .apply(parse_enumeration_from_template, args=(self._parameter_base,))
            .tolist()
        )

    def query(self) -> Generator[Result, None, None]:
        """Core method for data collection, iterating of station ids and yielding a
        DataFrame for each station with all found parameters. Takes care of type
        coercion of data, date filtering and humanizing of parameters."""
        for station_id in self.station_ids:
            station_data = []

            for parameter in self.parameters:
                parameter_df = self._collect_station_parameter(station_id, parameter)

                station_data.append(parameter_df)

            station_df = pd.concat(station_data)

            station_df = self._coerce_meta_fields(station_df)
            station_df = self._coerce_parameter_types(station_df)

            # Filter for dates range if start_date and end_date are defined
            if self.start_date:
                # df_station may be empty depending on if station has data for given
                # constraints
                try:
                    station_df = station_df[
                        (station_df[Columns.DATE.value] >= self.start_date)
                        & (station_df[Columns.DATE.value] <= self.end_date)
                    ]
                except KeyError:
                    pass

            # Assign meaningful parameter names (humanized).
            if self.humanize_parameters:
                station_df = self._humanize(station_df)

            # Empty dataframe should be skipped
            if station_df.empty:
                continue

            # TODO: add meaningful metadata here
            yield Result(pd.DataFrame(), station_df)

    def collect_data(self):
        # TODO: remove method at some point
        log.warning("method self.collect_data() will deprecate. change to self.query()")

        yield from self.all()

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
        df[Columns.STATION_ID.value] = self._parse_strings(
            df[Columns.STATION_ID.value]
        ).astype("category")

        for column in (
            Columns.DATE.value,
            Columns.FROM_DATE.value,
            Columns.TO_DATE.value,
        ):
            try:
                df[column] = self._parse_datetimes(df[column])
            except KeyError:
                pass

        if self._tidy:
            df[Columns.PARAMETER.value] = self._parse_strings(
                df[Columns.PARAMETER.value]
            ).astype("category")

            if self._has_quality:
                df[Columns.QUALITY.value] = self._parse_integers(
                    df[Columns.QUALITY.value]
                ).astype("category")

        return df

    def _parse_datetimes(self, series: pd.Series) -> pd.Series:
        """Method to parse dates in the pandas.DataFrame. Leverages the data timezone
        attribute to ensure correct comparison of dates."""
        series = pd.to_datetime(series, infer_datetime_format=True)
        try:
            series = series.dt.tz_localize(self.data_tz)
        except TypeError:
            pass

        return series

    @staticmethod
    def _parse_integers(series: pd.Series) -> pd.Series:
        """Method to parse integers for type coercion. Uses pandas.Int64Dtype() to
        allow missing values."""
        return pd.to_numeric(series, errors="coerce").astype(pd.Int64Dtype())

    @staticmethod
    def _parse_strings(series: pd.Series) -> pd.Series:
        """ Method to parse strings for type coercion. """
        return series.astype(pd.StringDtype())

    @staticmethod
    def _parse_floats(series: pd.Series) -> pd.Series:
        """ Method to parse floats for type coercion. """
        return pd.to_numeric(series, errors="coerce")

    def _parse_irregular_parameter(self, series: pd.Series) -> pd.Series:
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
        if not self._tidy:
            for column in df.columns:
                if column in self._meta_fields:
                    continue
                if column in self._irregular_parameters:
                    df[column] = self._parse_irregular_parameter(df[column])
                elif column in self._integer_parameters or column.startswith("QN"):
                    df[column] = self._parse_integers(df[column])
                elif column in self._string_parameters:
                    df[column] = self._parse_strings(df[column])
                else:
                    df[column] = self._parse_floats(df[column])

            return df

        data = []
        for parameter, group in df.groupby(Columns.PARAMETER.value):
            if parameter in self._irregular_parameters:
                group[Columns.VALUE.value] = self._parse_irregular_parameter(
                    group[Columns.VALUE.value]
                )
            elif parameter in self._integer_parameters:
                group[Columns.VALUE.value] = self._parse_integers(
                    group[Columns.VALUE.value]
                )
            elif parameter in self._string_parameters:
                group[Columns.VALUE.value] = self._parse_strings(
                    group[Columns.VALUE.value]
                )
            else:
                group[Columns.VALUE.value] = self._parse_floats(
                    group[Columns.VALUE.value]
                )

            data.append(group)

        df = pd.concat(data)

        return df

    def all(self) -> pd.DataFrame:
        """ Collect all data from self.collect_data """
        data = list(map(lambda x: x.data, self.query()))

        if not data:
            raise ValueError("No data available for given constraints")

        df = pd.concat(data)

        # Have to reapply category dtype after concatenation
        for column in (
            Columns.STATION_ID.value,
            Columns.ELEMENT.value,
            Columns.QUALITY.value,
        ):
            try:
                df[column] = df[column].astype("category")
            except KeyError:
                pass

        df.attrs["tidy"] = self._tidy

        return df

    def collect_safe(self):
        # TODO: remove method at some point
        log.warning("method self.collect_safe() will deprecate. change to self.all()")

        return self.all()

    def _humanize(self, df: pd.DataFrame) -> pd.DataFrame:
        """ Method for humanizing parameters. """
        hcnm = self._create_humanized_parameters_mapping()

        if not self._tidy:
            df = df.rename(columns=hcnm)
        else:
            df[Columns.PARAMETER.value] = df[
                Columns.PARAMETER.value
            ].cat.rename_categories(hcnm)

        return df

    def _create_humanized_parameters_mapping(self) -> Dict[str, str]:
        """Method for creation of parameter name mappings based on
        self._parameter_base"""
        hcnm = {parameter.value: parameter.name for parameter in self._parameter_base}

        return hcnm
