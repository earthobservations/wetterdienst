# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import logging
from abc import abstractmethod
from datetime import datetime
from enum import Enum
from typing import List, Optional, Tuple, Union

import dateutil.parser
import numpy as np
import pandas as pd
import pytz

from wetterdienst.core.core import Core
from wetterdienst.core.scalar.result import StationsResult
from wetterdienst.exceptions import StartDateEndDateError
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.period import Period, PeriodType
from wetterdienst.metadata.resolution import Frequency, Resolution, ResolutionType
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.geo import Coordinates, derive_nearest_neighbours

EARTH_RADIUS_KM = 6371

log = logging.getLogger(__name__)


class ScalarRequestCore(Core):
    """ Core for stations information of a source """

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

    @property
    @abstractmethod
    def _parameter_base(self) -> Enum:
        """parameter base enumeration from which parameters can be parsed e.g.
        DWDObservationParameter"""
        pass

    @property
    @abstractmethod
    def _values(self):
        pass

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

    def _parse_period(self, period: Period) -> Optional[List[Period]]:
        if not period:
            return None
        elif self._period_type == PeriodType.FIXED:
            return [period]
        else:
            return (
                pd.Series(period)
                .apply(
                    parse_enumeration_from_template, args=(self._period_base, Period)
                )
                .sort_values()
                .tolist()
            )

    def _parse_parameter(self, parameter: List[Union[str, Enum]]) -> List[Enum]:
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

    @staticmethod
    def _parse_station_id(series: pd.Series) -> pd.Series:
        """Dedicated method for parsing station ids, by default uses the same method as
        parse_strings but could be modified by the implementation class"""
        return series.astype(pd.StringDtype())

    def __eq__(self, other) -> bool:
        """ Equal method of request object """
        return (
            self.parameter == other.parameter
            and self.resolution == other.resolution
            and self.period == other.period
            and self.start_date == other.start_date
            and self.end_date == other.end_date
            and self.humanize_parameters == other.humanize_parameters
            and self.tidy_data == other.tidy_data
        )

    def __init__(
        self,
        parameter: Tuple[Union[str, Enum]],
        resolution: Resolution,
        period: Period,
        start_date: Optional[Union[str, datetime]] = None,
        end_date: Optional[Union[str, datetime]] = None,
        humanize_parameters: bool = True,
        tidy_data: bool = True,
    ) -> None:
        """

        :param start_date: start date for filtering stations for their available data
        :param end_date: end date for filtering stations for their available data
        """
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
        self.parameter = self._parse_parameter(parameter)
        self.humanize_parameters = humanize_parameters
        self.tidy_data = tidy_data

    def all(self) -> "StationsResult":
        """
        Wraps the _all method and applies date filters.

        :return: pandas.DataFrame with the information of different available stations
        """
        df = self._all()

        df = df.reindex(columns=self._base_columns)

        df = self._coerce_meta_fields(df)

        # TODO: exchange with more foreceful filtering if user wants
        # if self.start_date:
        #     df = df[
        #         df[Columns.FROM_DATE.value] <= self.start_date
        #     ]
        #
        # if self.end_date:
        #     df = df[
        #         df[Columns.TO_DATE.value] >= self.end_date
        #     ]

        # TODO: use StationsResult here
        # TODO: ._filter should stay empty as _all_ stations are returned

        result = StationsResult(self, df.copy().reset_index(drop=True))

        return result

    def filter(self, station_id: Tuple[str, ...]) -> "StationsResult":
        # TODO: add queries for the given possible parameters
        # TODO: eventually add other parameters from nearby_... and use DataFrame of
        #  them instead
        df = self.all().df

        station_id = self._parse_station_id(pd.Series(station_id))

        df = df[df[Columns.STATION_ID.value].isin(station_id)]

        result = StationsResult(self, df)

        return result

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
    ) -> "StationsResult":
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

        metadata = self.all().df

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

        metadata_location[Columns.DISTANCE_TO_LOCATION.value] = distances_km

        if metadata_location.empty:
            log.warning(
                f"No weather stations were found for coordinate "
                f"{latitude}°N and {longitude}°E "
            )

        # TODO: use StationsResult here
        # TODO: add filter for number filtering

        result = StationsResult(self, metadata_location.reset_index(drop=True))

        return result

    def nearby_radius(
        self,
        latitude: float,
        longitude: float,
        max_distance_in_km: int,
    ) -> "StationsResult":
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

        metadata = self.all().df

        all_nearby_stations = self.nearby_number(
            latitude, longitude, metadata.shape[0]
        ).df

        nearby_stations_in_distance = all_nearby_stations[
            all_nearby_stations[Columns.DISTANCE_TO_LOCATION.value]
            <= max_distance_in_km
        ]

        # TODO: use StationsResult here
        # TODO: add filter for radius filtering

        result = StationsResult(
            self, nearby_stations_in_distance.reset_index(drop=True)
        )

        return result
