# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from abc import abstractmethod
from datetime import datetime
from enum import Enum
from logging import getLogger
from typing import Dict, Generator, List, Optional, Tuple, Union

import dateutil.parser
import numpy as np
import pandas as pd
import pytz
from pytz import timezone
from tqdm import tqdm

from wetterdienst.core.core import Core
from wetterdienst.dwd.metadata.column_names import DWDMetaColumns
from wetterdienst.exceptions import NoParametersFound, StartDateEndDateError
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.period import Period, PeriodType
from wetterdienst.metadata.resolution import Frequency, Resolution, ResolutionType
from wetterdienst.metadata.result import Result
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.geo import Coordinates, derive_nearest_neighbours

log = getLogger(__name__)


EARTH_RADIUS_KM = 6371

# TODO: move more attributes to __init__


class ScalarCore(Core):
    """Core for time series related classes """

    @property
    def resolution(self) -> Optional[Resolution]:
        """ Resolution accessor"""
        return self._resolution

    @resolution.setter
    def resolution(self, res) -> None:
        # TODO: add functionality to parse arbitrary resolutions for cases where
        #  resolution has to be determined based on returned data
        if self._resolution_type in (ResolutionType.FIXED, ResolutionType.UNDEFINED):
            self._resolution = res
        else:
            self._resolution = parse_enumeration_from_template(
                res, self._resolution_base, Resolution
            )

    @property
    @abstractmethod
    def _resolution_base(self) -> Optional[Resolution]:
        """ Optional enumeration for multiple resolutions """
        pass

    @property
    @abstractmethod
    def _resolution_type(self) -> ResolutionType:
        """ Resolution type, multi, fixed, ..."""
        pass

    # TODO: implement for source with dynamic resolution
    @staticmethod
    def _determine_resolution(dates: pd.Series) -> Resolution:
        """ Function to determine resolution from a pandas Series of dates """
        pass

    @property
    def frequency(self) -> Frequency:
        """Frequency for the given resolution, used to create a full date range for
        mering"""
        return Frequency[self.resolution.name]

    @property
    @abstractmethod
    def _period_type(self) -> PeriodType:
        """ Period type, fixed, multi, ..."""
        pass

    @property
    @abstractmethod
    def _period_base(self) -> Optional[Period]:
        """ Period base enumeration from which a period string can be parsed """
        pass

    @abstractmethod
    def _parse_period(self, period: List[Period]):
        """ Method for parsing period depending on if multiple are given """
        pass

    def __init__(
        self,
        resolution: Resolution,
        period: Union[Period, List[Period]],
        start_date: Optional[Union[str, datetime]],
        end_date: Optional[Union[str, datetime]],
    ) -> None:
        self.resolution = resolution
        self.period = self._parse_period(period)

        if start_date or end_date:
            # If only one date given, set the other one to equal
            if not start_date:
                start_date = end_date

            if not end_date:
                end_date = start_date

            start_date = dateutil.parser.isoparse(str(start_date))
            if not start_date.tzinfo:
                start_date = start_date.replace(tzinfo=pytz.UTC)

            end_date = dateutil.parser.isoparse(str(end_date))
            if not end_date.tzinfo:
                end_date = end_date.replace(tzinfo=pytz.UTC)

            # TODO: replace this with a response + logging
            if not start_date <= end_date:
                raise StartDateEndDateError(
                    "Error: 'start_date' must be smaller or equal to 'end_date'."
                )

        self.start_date = start_date
        self.end_date = end_date


class ScalarValuesCore(ScalarCore):
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

    @property
    def _complete_dates(self) -> pd.DatetimeIndex:
        return pd.date_range(
            self.start_date, self.end_date, freq=self.frequency.value, tz=self.data_tz
        )

    @property
    def _base_df(self) -> pd.DataFrame:
        """Base dataframe which is used for creating empty dataframes if no data is
        found or for merging other dataframes on the full dates"""
        return pd.DataFrame({Columns.DATE.value: self._complete_dates})

    def _parse_period(self, period: List[Period]):
        """ Parsing method for period, depending on the type of period"""
        if not period:
            return None
        elif self._period_type == PeriodType.FIXED:
            return period
        else:
            return (
                pd.Series(period)
                .apply(
                    parse_enumeration_from_template, args=(self._period_base, Period)
                )
                .sort_values()
                .tolist()
            )

    def __init__(
        self,
        station_id: Tuple[str],
        parameter: Tuple[Union[str, Enum]],
        resolution: Resolution,
        period: Period,
        start_date: Optional[Union[str, datetime]],
        end_date: Optional[Union[str, datetime]],
        humanize_parameters: bool,
        tidy_data: bool,
    ) -> None:
        """

        :param station_id: station ids for which data is requested
        :param parameter: parameters either as strings or enumerations for which data
            is requested
        :param start_date: start date of the resulting data,
            if not start_date: start_date = end_date
        :param end_date: end date of the resulting data
            if not end_date: end_date = start_date
        :param humanize_parameters: bool if parameters should be renamed to meaningful
            names

        """
        super(ScalarValuesCore, self).__init__(
            resolution=resolution,
            period=period,
            start_date=start_date,
            end_date=end_date,
        )

        # Make sure we receive a list of ids
        self.station_ids = pd.Series(station_id).astype(str).tolist()
        self.parameters = self._parse_parameters(parameter)

        # TODO: replace this with a response + logging
        # TODO: move this to self.collect_data
        if not self.parameters:
            raise NoParametersFound(f"No parameters could be parsed from {parameter}")

        self.humanize_parameters = humanize_parameters
        self.tidy_data = tidy_data

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
                str(self.start_date),
                str(self.end_date),
            ]
        )

    def _parse_parameters(self, parameter: List[Union[str, Enum]]) -> List[Enum]:
        """
        Method to parse parameters, either from string or enum. Case independent for
        strings.

        :param parameter: parameters as strings or enumerations
        :return: list of parameter enumerations of type self._parameter_base
        """
        return (
            pd.Series(parameter)
            .apply(parse_enumeration_from_template, args=(self._parameter_base,))
            .tolist()
        )

    def _get_empty_station_parameter_df(
        self, station_id: str, parameter: Union[Enum, List[Enum]]
    ) -> pd.DataFrame:
        parameter = pd.Series(parameter).map(lambda x: x.value).tolist()
        df = self._base_df

        # Base columns
        columns = [Columns.STATION_ID.value, Columns.DATE.value]

        if self.tidy_data:
            columns.extend(
                [Columns.PARAMETER.value, Columns.VALUE.value, Columns.QUALITY.value]
            )
        else:
            columns.extend(parameter)

        df = df.reindex(columns=columns)

        df[Columns.STATION_ID.value] = station_id

        if self.tidy_data:
            if len(parameter) == 1:
                parameter = parameter[0]
            df[Columns.PARAMETER.value] = parameter

        return df

    def _build_complete_df(
        self, df: pd.DataFrame, station_id: str, parameter: Enum
    ) -> pd.DataFrame:
        # For cases where requests are not defined by start and end date but rather by
        # periods, use the returned df without modifications
        # We may put a standard date range here if no data is found
        if not self.start_date:
            return df

        df = pd.merge(
            left=self._base_df,
            right=df,
            left_on=Columns.DATE.value,
            right_on=Columns.DATE.value,
            how="left",
        )

        df[Columns.STATION_ID.value] = station_id

        if self.tidy_data:
            df[Columns.PARAMETER.value] = parameter.value

        return df

    def query(self) -> Generator[Result, None, None]:
        """Core method for data collection, iterating of station ids and yielding a
        DataFrame for each station with all found parameters. Takes care of type
        coercion of data, date filtering and humanizing of parameters."""
        for station_id in self.station_ids:

            # TODO: add method to return empty result with correct response string e.g.
            #  station id not available
            station_data = []

            for parameter in self.parameters:
                parameter_df = self._collect_station_parameter(station_id, parameter)

                # TODO: solve exceptional case where empty df and dynamic resolution
                if self._resolution_type == ResolutionType.DYNAMIC:
                    self.resolution = self._determine_resolution(
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
                    self._coerce_dates(parameter_df)

                    parameter_df = self._build_complete_df(
                        parameter_df, station_id, parameter
                    )

                station_data.append(parameter_df)

            station_df = pd.concat(station_data, ignore_index=True)

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

    def _coerce_dates(self, df: pd.DataFrame) -> pd.DataFrame:
        for column in (
            Columns.DATE.value,
            Columns.FROM_DATE.value,
            Columns.TO_DATE.value,
        ):
            try:
                df[column] = self._parse_dates(df[column])
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
        df[Columns.STATION_ID.value] = self._parse_station_ids(
            df[Columns.STATION_ID.value]
        ).astype("category")

        if self.tidy_data:
            df[Columns.PARAMETER.value] = self._parse_strings(
                df[Columns.PARAMETER.value]
            ).astype("category")

            if self._has_quality:
                df[Columns.QUALITY.value] = self._parse_integers(
                    df[Columns.QUALITY.value]
                ).astype("category")

        return df

    def _parse_station_ids(self, series: pd.Series) -> pd.Series:
        """Dedicated method for parsing station ids, by default uses the same method as
        parse_strings but could be modified by the implementation class"""
        return self._parse_strings(series)

    def _parse_dates(self, series: pd.Series) -> pd.Series:
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
        if not self.tidy_data:
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
        for parameter, group in df.groupby(Columns.PARAMETER.value, sort=False):
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
        data = []

        for result in tqdm(self.query(), total=len(self.station_ids)):
            data.append(result.data)

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

        df.attrs["tidy"] = self.tidy_data

        return df

    def _humanize(self, df: pd.DataFrame) -> pd.DataFrame:
        """ Method for humanizing parameters. """
        hcnm = self._create_humanized_parameters_mapping()

        if not self.tidy_data:
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


class ScalarStationsCore(ScalarCore):
    """ Core for stations information of a source """

    # Columns that should be contained within any stations information
    _base_columns = (
        Columns.STATION_ID.value,
        Columns.FROM_DATE.value,
        Columns.TO_DATE.value,
        Columns.HEIGHT.value,
        Columns.LATITUDE.value,
        Columns.LONGITUDE.value,
        Columns.STATION_NAME.value,
        Columns.STATE.value,
    )
    # TODO: eventually this can be matched with the type coercion of station data to get
    #  similar types of floats and strings
    # Dtype mapping for stations
    _dtype_mapping = {
        Columns.STATION_ID.value: str,
        Columns.HEIGHT.value: float,
        Columns.LATITUDE.value: float,
        Columns.LONGITUDE.value: float,
        Columns.STATION_NAME.value: str,
        Columns.STATE.value: str,
    }

    def _parse_period(self, period: Period):
        if not period:
            return None
        elif self._period_type == PeriodType.FIXED:
            return period
        else:
            return parse_enumeration_from_template(period, self._period_base, Period)

    def __init__(
        self,
        resolution: Resolution,
        period: Period,
        start_date: Union[None, str, datetime] = None,
        end_date: Union[None, str, datetime] = None,
    ) -> None:
        """

        :param start_date: start date for filtering stations for their available data
        :param end_date: end date for filtering stations for their available data
        """
        super(ScalarStationsCore, self).__init__(
            resolution=resolution,
            period=period,
            start_date=start_date,
            end_date=end_date,
        )

    def all(self) -> pd.DataFrame:
        """
        Wraps the _all method and applies date filters.

        :return: pandas.DataFrame with the information of different available stations
        """
        metadata_df = self._all().copy()

        metadata_df = metadata_df.reindex(columns=self._base_columns)

        metadata_df = self._coerce_meta_fields(metadata_df)

        if self.start_date:
            metadata_df = metadata_df[
                metadata_df[DWDMetaColumns.FROM_DATE.value] <= self.start_date
            ]

        if self.end_date:
            metadata_df = metadata_df[
                metadata_df[DWDMetaColumns.TO_DATE.value] >= self.end_date
            ]

        return metadata_df

    def _coerce_meta_fields(self, df) -> pd.DataFrame:
        """ Method for filed coercion. """
        df = df.astype(self._dtype_mapping)

        df[Columns.FROM_DATE.value] = pd.to_datetime(
            df[Columns.FROM_DATE.value], infer_datetime_format=True
        ).dt.tz_localize(pytz.UTC)
        df[Columns.TO_DATE.value] = pd.to_datetime(
            df[Columns.TO_DATE.value], infer_datetime_format=True
        ).dt.tz_localize(pytz.UTC)

        return df

    @abstractmethod
    def _all(self) -> pd.DataFrame:
        """
        Abstract method for gathering of sites information for a given implementation.
        Information consist of a DataFrame with station ids, location, name, etc

        :return: pandas.DataFrame with the information of different available sites
        """
        pass

    def nearby_number(
        self,
        latitude: float,
        longitude: float,
        number: int,
    ) -> pd.DataFrame:
        """
        Wrapper for get_nearby_stations_by_number using the given parameter set. Returns
        nearest stations defined by number.

        :param latitude: latitude in degrees
        :param longitude: longitude in degrees
        :param number: number of stations to be returned, greater 0
        :return: pandas.DataFrame with station information for the selected stations
        """
        if number <= 0:
            raise ValueError("'num_stations_nearby' has to be at least 1.")

        coords = Coordinates(np.array(latitude), np.array(longitude))

        metadata = self.all()

        metadata = metadata.reset_index(drop=True)

        distances, indices_nearest_neighbours = derive_nearest_neighbours(
            metadata[Columns.LATITUDE.value].values,
            metadata[Columns.LONGITUDE.value].values,
            coords,
            number,
        )

        distances = pd.Series(distances)
        indices_nearest_neighbours = pd.Series(indices_nearest_neighbours)

        # If num_stations_nearby is higher then the actual amount of stations
        # further indices and distances are added which have to be filtered out
        distances = distances[: min(metadata.shape[0], number)]
        indices_nearest_neighbours = indices_nearest_neighbours[
            : min(metadata.shape[0], number)
        ]

        distances_km = np.array(distances * EARTH_RADIUS_KM)

        metadata_location = metadata.iloc[indices_nearest_neighbours, :].reset_index(
            drop=True
        )

        metadata_location[DWDMetaColumns.DISTANCE_TO_LOCATION.value] = distances_km

        if metadata_location.empty:
            log.warning(
                f"No weather stations were found for coordinate "
                f"{latitude}°N and {longitude}°E "
            )

        return metadata_location

    def nearby_radius(
        self,
        latitude: float,
        longitude: float,
        max_distance_in_km: int,
    ) -> pd.DataFrame:
        """
        Wrapper for get_nearby_stations_by_distance using the given parameter set.
        Returns nearest stations defined by distance (km).

        :param latitude: latitude in degrees
        :param longitude: longitude in degrees
        :param max_distance_in_km: distance (km) for which stations will be selected
        :return: pandas.DataFrame with station information for the selected stations
        """
        # Theoretically a distance of 0 km is possible
        if max_distance_in_km < 0:
            raise ValueError("'max_distance_in_km' has to be at least 0.0.")

        metadata = self.all()

        all_nearby_stations = self.nearby_number(latitude, longitude, metadata.shape[0])

        nearby_stations_in_distance = all_nearby_stations[
            all_nearby_stations[DWDMetaColumns.DISTANCE_TO_LOCATION.value]
            <= max_distance_in_km
        ]

        return nearby_stations_in_distance.reset_index(drop=True)
