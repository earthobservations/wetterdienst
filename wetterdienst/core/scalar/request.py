# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import json
import logging
from abc import abstractmethod
from datetime import datetime
from enum import Enum
from typing import List, Optional, Tuple, Union

import dateutil.parser
import numpy as np
import pandas as pd
import pytz
from measurement.measures import Distance
from measurement.utils import guess
from rapidfuzz import fuzz, process

from wetterdienst.core.core import Core
from wetterdienst.core.scalar.result import StationsResult
from wetterdienst.exceptions import InvalidEnumeration, StartDateEndDateError
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.period import Period, PeriodType
from wetterdienst.metadata.resolution import Frequency, Resolution, ResolutionType
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.geo import Coordinates, derive_nearest_neighbours

log = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371


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
    def _has_datasets(self) -> bool:
        """Boolean if weather service has datasets (when multiple parameters are stored
        in one table/file"""
        pass

    @property
    def _dataset_base(self) -> Optional[Enum]:
        """ Dataset base that is used to differ between different datasets """
        if self._has_datasets:
            raise NotImplementedError(
                "implement _dataset_base Enumeration that contains available datasets"
            )
        return

    @property
    def _dataset_tree(self) -> Optional[object]:
        """ Detailed dataset tree with all parameters per dataset """
        if self._has_datasets:
            raise NotImplementedError(
                "implement _dataset_tree class that contains available datasets "
                "and their parameters"
            )
        return None

    @property
    def _unique_dataset(self) -> bool:
        """If ALL parameters are stored in one dataset e.g. all daily data is stored in
        one file"""
        if self._has_datasets:
            raise NotImplementedError("define if only one big dataset is available")
        return False

    @property
    def _dataset_accessor(self) -> str:
        """Accessor for dataset, by default the resolution is used as we expect
        datasets to be divided in resolutions"""
        return self.resolution.name

    @property
    def _parameter_to_dataset_mapping(self) -> dict:
        """ Mapping to go from a (flat) parameter to dataset """
        if not self._unique_dataset:
            raise NotImplementedError(
                "for non unique datasets implement a mapping from parameter to dataset"
            )
        return dict()

    @property
    @abstractmethod
    def _values(self):
        """ Class to get the values for a request """
        pass

    # Columns that should be contained within any stations information
    _base_columns = (
        Columns.STATION_ID.value,
        Columns.FROM_DATE.value,
        Columns.TO_DATE.value,
        Columns.HEIGHT.value,
        Columns.LATITUDE.value,
        Columns.LONGITUDE.value,
        Columns.NAME.value,
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
        Columns.NAME.value: str,
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
        # TODO: refactor this!
        # for logging
        enums = []
        if self._dataset_base:
            enums.append(self._dataset_base)

        enums.append(self._parameter_base)

        parameters = []

        for parameter in pd.Series(parameter):
            parameter_ = None

            if self._dataset_base:
                try:
                    parameter_ = parse_enumeration_from_template(
                        parameter, self._dataset_base
                    )
                except InvalidEnumeration:
                    pass
                else:
                    parameters.append((parameter_, parameter_))
                    continue

                try:
                    parameter_ = parse_enumeration_from_template(
                        parameter, self._parameter_base[self._dataset_accessor]
                    )
                    if self._unique_dataset:
                        dataset = self._dataset_base[self._dataset_accessor]
                    else:
                        dataset = self._parameter_to_dataset_mapping[self.resolution][
                            parameter_
                        ]
                        parameter_ = self._dataset_tree[self._dataset_accessor][
                            dataset.name
                        ][parameter_.name]
                except InvalidEnumeration:
                    pass
                else:
                    parameters.append((parameter_, dataset))
                    continue

            try:
                parameter_ = parse_enumeration_from_template(
                    parameter, self._parameter_base[self._dataset_accessor]
                )
                parameters.append(parameter_)
            except InvalidEnumeration:
                pass

            if not parameter_:
                log.info(f"parameter {parameter} could not be parsed from ({enums})")

        return parameters

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
            and self.humanize == other.humanize
            and self.tidy == other.tidy
        )

    def __init__(
        self,
        parameter: Tuple[Union[str, Enum]],
        resolution: Resolution,
        period: Period,
        start_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
        end_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
        humanize: bool = True,
        tidy: bool = True,
    ) -> None:
        """
        :param start_date: Start date for filtering stations for their available data
        :param end_date:   End date for filtering stations for their available data
        """

        super().__init__()

        self.resolution = resolution
        self.period = self._parse_period(period)

        self.start_date, self.end_date = self.convert_timestamps(start_date, end_date)
        self.parameter = self._parse_parameter(parameter)
        self.humanize = humanize

        tidy = tidy
        if self._has_datasets:
            tidy = tidy or any(
                [
                    parameter not in self._dataset_base
                    for parameter, dataset in self.parameter
                ]
            )

        self.tidy = tidy

        log.info(
            f"Processing request for "
            f"provider={self.provider}, "
            f"parameter={self.parameter}, "
            f"resolution={self.resolution}, "
            f"period={self.period}, "
            f"start_date={self.start_date}, "
            f"end_date={self.end_date}, "
            f"humanize={self.humanize}, "
            f"tidy={self.tidy}"
        )

    @staticmethod
    def convert_timestamps(
        start_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
        end_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
    ) -> Union[Tuple[None, None], Tuple[pd.Timestamp, pd.Timestamp]]:
        """
        Sort out start_date vs. end_date, parse strings to datetime
        objects and finally convert both to pd.Timestamp types.

        :param start_date: Start date for filtering stations for their available data
        :param end_date:   End date for filtering stations for their available data
        :return:           pd.Timestamp objects tuple of (start_date, end_date)
        """

        if start_date is None and end_date is None:
            return None, None

        if start_date:
            if isinstance(start_date, str):
                start_date = dateutil.parser.isoparse(start_date)
            if not start_date.tzinfo:
                start_date = start_date.replace(tzinfo=pytz.UTC)

        if end_date:
            if isinstance(end_date, str):
                end_date = dateutil.parser.isoparse(end_date)
            if not end_date.tzinfo:
                end_date = end_date.replace(tzinfo=pytz.UTC)

        # If only one date given, set the other one to equal.
        if not start_date:
            start_date = end_date

        if not end_date:
            end_date = start_date

        # TODO: replace this with a response + logging
        if not start_date <= end_date:
            raise StartDateEndDateError(
                "Error: 'start_date' must be smaller or equal to 'end_date'."
            )

        return pd.Timestamp(start_date), pd.Timestamp(end_date)

    @classmethod
    def discover(cls, filter_=None, dataset=None, flatten: bool = True) -> str:
        """ Function to print/discover available parameters """
        # TODO: Refactor this!
        flatten = cls._unique_dataset or flatten

        filter_ = cls._setup_discover_filter(filter_)

        filter_ = [f.name for f in filter_]

        if flatten:
            if dataset:
                log.warning("dataset filter will be ignored due to 'flatten'")

            parameters = {}

            for f in filter_:
                parameters[f.lower()] = []
                for parameter in cls._parameter_base[f]:
                    parameters[f.lower()].append(parameter.name.lower())

            return json.dumps(parameters, indent=4)

        datasets_filter = (
            pd.Series(dataset)
            .apply(parse_enumeration_from_template, args=(cls._dataset_base,))
            .tolist()
            or cls._dataset_base
        )

        datasets_filter = [ds.name for ds in datasets_filter]

        parameters = {}

        for f in filter_:
            parameters[f.lower()] = {}

            for dataset in cls._dataset_tree[f].__dict__:
                if dataset.startswith("_") or dataset not in datasets_filter:
                    continue

                parameters[f.lower()][dataset.lower()] = []

                for parameter in cls._dataset_tree[f][dataset]:
                    parameters[f.lower()][dataset.lower()].append(
                        parameter.name.lower()
                    )

        return json.dumps(parameters, indent=4)

    @classmethod
    def _setup_discover_filter(cls, filter_):
        if cls._resolution_type == ResolutionType.FIXED:
            log.warning("resolution filter will be ignored due to fixed resolution")

            filter_ = [cls.resolution]

        filter_ = pd.Series(filter_).apply(
            parse_enumeration_from_template, args=(cls._resolution_base,)
        ).tolist() or [*cls._resolution_base]

        return filter_

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

    def all(self) -> StationsResult:
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

        result = StationsResult(self, df.copy().reset_index(drop=True))

        return result

    def filter_by_station_id(self, station_id: Tuple[str, ...]) -> StationsResult:
        """
        Method to filter stations by station ids

        :param station_id: list of stations that are requested
        :return: df with filtered stations
        """
        df = self.all().df

        station_id = self._parse_station_id(pd.Series(station_id))

        log.info(f"Filtering for station_id={list(station_id)}")

        df = df[df[Columns.STATION_ID.value].isin(station_id)]

        result = StationsResult(self, df)

        return result

    def filter_by_name(
        self, name: str, first: bool = True, threshold: int = 90
    ) -> StationsResult:
        """
        Method to filter stations for station name using string comparison.

        :param name: name of looked up station
        :param first: boolean if only first station is returned
        :param threshold: threshold for string match 0...100
        :return: df with matched station
        """
        if first:
            extract_fun = process.extractOne
        else:
            extract_fun = process.extract

        threshold = int(threshold)

        if threshold < 0:
            raise ValueError("threshold must be ge 0")

        df = self.all().df

        station_match = extract_fun(
            query=name,
            choices=df[Columns.NAME.value],
            scorer=fuzz.token_set_ratio,
            score_cutoff=threshold,
        )

        if station_match:
            if first:
                station_match = [station_match]
            station_name = pd.Series(station_match).apply(lambda x: x[0])

            df = df[df[Columns.NAME.value].isin(station_name)]

            df = df.reset_index(drop=True)
        else:
            df = pd.DataFrame().reindex(columns=df.columns)

        result = StationsResult(stations=self, df=df)

        return result

    def filter_by_rank(
        self,
        latitude: float,
        longitude: float,
        rank: int,
    ) -> StationsResult:
        """
        Wrapper for get_nearby_stations_by_number using the given parameter set. Returns
        nearest stations defined by number.

        :param latitude: latitude in degrees
        :param longitude: longitude in degrees
        :param rank: number of stations to be returned, greater 0
        :return: pandas.DataFrame with station information for the selected stations
        """
        rank = int(rank)

        if rank <= 0:
            raise ValueError("'num_stations_nearby' has to be at least 1.")

        coords = Coordinates(np.array(latitude), np.array(longitude))

        df = self.all().df.reset_index(drop=True)

        distances, indices_nearest_neighbours = derive_nearest_neighbours(
            df[Columns.LATITUDE.value].values,
            df[Columns.LONGITUDE.value].values,
            coords,
            rank,
        )

        distances = pd.Series(distances)
        indices_nearest_neighbours = pd.Series(indices_nearest_neighbours)

        # If num_stations_nearby is higher then the actual amount of stations
        # further indices and distances are added which have to be filtered out
        distances = distances[: min(df.shape[0], rank)]
        indices_nearest_neighbours = indices_nearest_neighbours[
            : min(df.shape[0], rank)
        ]

        distances_km = np.array(distances * EARTH_RADIUS_KM)

        df = df.iloc[indices_nearest_neighbours, :].reset_index(drop=True)

        df[Columns.DISTANCE.value] = distances_km

        if df.empty:
            log.warning(
                f"No weather stations were found for coordinate "
                f"{latitude}°N and {longitude}°E and number {rank}"
            )

        result = StationsResult(self, df.reset_index(drop=True))

        return result

    def filter_by_distance(
        self, latitude: float, longitude: float, distance: float, unit: str = "km"
    ) -> StationsResult:
        """
        Wrapper for get_nearby_stations_by_distance using the given parameter set.
        Returns nearest stations defined by distance (km).

        :param latitude: latitude in degrees
        :param longitude: longitude in degrees
        :param distance: distance (km) for which stations will be selected
        :param unit: unit string for conversion
        :return: pandas.DataFrame with station information for the selected stations
        """
        distance = float(distance)

        # Theoretically a distance of 0 km is possible
        if distance < 0:
            raise ValueError("'distance' has to be at least 0.0")

        unit = unit.strip()

        distance_in_km = guess(distance, unit, [Distance]).km

        # TODO: replace the repeating call to self.all()
        all_nearby_stations = self.filter_by_rank(
            latitude, longitude, self.all().df.shape[0]
        ).df

        df = all_nearby_stations[
            all_nearby_stations[Columns.DISTANCE.value] <= distance_in_km
        ]

        if df.empty:
            log.warning(
                f"No weather stations were found for coordinate "
                f"{latitude}°N and {longitude}°E and distance {distance_in_km}km"
            )

        result = StationsResult(stations=self, df=df.reset_index(drop=True))

        return result

    def filter_by_bbox(
        self, left: float, bottom: float, right: float, top: float
    ) -> StationsResult:
        """
        Method to filter stations by bounding box.

        :param bottom: bottom latitude as float
        :param left: left longitude as float
        :param top: top latitude as float
        :param right: right longitude as float
        :return: df with stations in bounding box
        """
        left, bottom, right, top = float(left), float(bottom), float(right), float(top)

        if left >= right:
            raise ValueError("bbox left border should be smaller then right")

        if bottom >= top:
            raise ValueError("bbox bottom border should be smaller then top")

        lat_interval = pd.Interval(bottom, top, closed="both")
        lon_interval = pd.Interval(left, right, closed="both")

        df = self.all().df

        df = df[
            df[Columns.LATITUDE.value].apply(lambda x: x in lat_interval)
            & df[Columns.LONGITUDE.value].apply(lambda x: x in lon_interval)
        ]

        result = StationsResult(stations=self, df=df.reset_index(drop=True))

        return result
