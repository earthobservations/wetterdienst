# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import logging
from abc import abstractmethod
from copy import copy
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
from wetterdienst.core.scalar.result import (
    InterpolatedValuesResult,
    StationsResult,
    SummarizedValuesResult,
)
from wetterdienst.exceptions import (
    InvalidEnumeration,
    NoParametersFound,
    StartDateEndDateError,
    StationNotFoundError,
)
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.datarange import DataRange
from wetterdienst.metadata.kind import Kind
from wetterdienst.metadata.parameter import Parameter
from wetterdienst.metadata.period import Period, PeriodType
from wetterdienst.metadata.provider import Provider
from wetterdienst.metadata.resolution import Frequency, Resolution, ResolutionType
from wetterdienst.settings import Settings
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.geo import Coordinates, derive_nearest_neighbours

log = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371


class ScalarRequestCore(Core):
    """Core for stations_result information of a source"""

    @property
    @abstractmethod
    def provider(self) -> Provider:
        """Optional enumeration for multiple resolutions"""
        pass

    @property
    @abstractmethod
    def kind(self) -> Kind:
        """Optional enumeration for multiple resolutions"""
        pass

    @property
    @abstractmethod
    def _resolution_base(self) -> Optional[Resolution]:
        """Optional enumeration for multiple resolutions"""
        pass

    @property
    @abstractmethod
    def _resolution_type(self) -> ResolutionType:
        """Resolution type, multi, fixed, ..."""
        pass

    @property
    def frequency(self) -> Frequency:
        """Frequency for the given resolution, used to create a full date range for
        mering"""
        if self.resolution == Resolution.DYNAMIC:
            return self._dynamic_frequency
        return Frequency[self.resolution.name]

    @property
    def dynamic_frequency(self) -> Optional[Frequency]:
        return self._dynamic_frequency

    @dynamic_frequency.setter
    def dynamic_frequency(self, df) -> None:
        if df:
            self._dynamic_frequency = parse_enumeration_from_template(df, Frequency)

    @property
    @abstractmethod
    def _period_type(self) -> PeriodType:
        """Period type, fixed, multi, ..."""
        pass

    @property
    @abstractmethod
    def _period_base(self) -> Optional[Period]:
        """Period base enumeration from which a period string can be parsed"""
        pass

    @property
    @abstractmethod
    def _parameter_base(self) -> Enum:
        """parameter base enumeration from which parameters can be parsed e.g.
        DWDObservationParameter"""
        pass

    @property
    @abstractmethod
    def _data_range(self) -> DataRange:
        """State whether data from this provider is given in fixed data chunks
        or has to be defined over start and end date"""
        pass

    @property
    @abstractmethod
    def _has_datasets(self) -> bool:
        """Boolean if weather service has datasets (when multiple parameters are stored
        in one table/file)"""
        pass

    @property
    def _dataset_base(self) -> Optional[Enum]:
        """Dataset base that is used to differ between different datasets"""
        if self._has_datasets:
            raise NotImplementedError("implement _dataset_base enumeration that contains available datasets")

        return self._resolution_base

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
        datasets to be divided in resolutions but for some e.g. DWD Mosmix
        datasets are divided in another way (SMALL/LARGE in this case)"""
        return self.resolution.name

    @property
    @abstractmethod
    def _has_tidy_data(self) -> bool:
        """If data is generally provided tidy -> then data should not be tidied but
        rather tabulated if data is requested to not being tidy"""
        pass

    @property
    def _parameter_to_dataset_mapping(self) -> dict:
        """Mapping to go from a (flat) parameter to dataset"""
        if not self._unique_dataset:
            raise NotImplementedError("for non unique datasets implement a mapping from parameter to dataset")
        return {}

    @property
    @abstractmethod
    def _unit_tree(self):
        pass

    @property
    def datasets(self):
        datasets = self._dataset_tree[self._dataset_accessor].__dict__.keys()

        return list(filter(lambda x: x not in ("__module__", "__doc__"), datasets))

    @property
    @abstractmethod
    def _values(self):
        """Class to get the values for a request"""
        pass

    # Columns that should be contained within any stations_result information
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

    #   - heterogeneous parameters such as precipitation_height
    #   - homogeneous parameters such as temperature_air_200
    interpolatable_parameters = [
        Parameter.TEMPERATURE_AIR_MEAN_200.name,
        Parameter.WIND_SPEED.name,
        Parameter.PRECIPITATION_HEIGHT.name,
    ]

    def _parse_period(self, period: Period) -> Optional[List[Period]]:
        """
        Method to parse period(s)

        :param period:
        :return:
        """
        if not period:
            return None
        elif self._period_type == PeriodType.FIXED:
            return [period]
        else:
            return (
                pd.Series(period)
                .apply(parse_enumeration_from_template, args=(self._period_base, Period))
                .sort_values()
                .tolist()
            )

    def _parse_parameter(self, parameter: List[Union[str, Enum]]) -> List[Tuple[Enum, Enum]]:
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

        for par in pd.Series(parameter):

            # Each parameter can either be
            #  - a dataset : gets all data from the dataset
            #  - a parameter : gets prefixed parameter from a resolution e.g.
            #      precipitation height of daily values is taken from climate summary
            #  - a tuple of parameter -> dataset : to decide from which dataset
            #    the parameter is taken
            try:
                parameter, dataset = pd.Series(par)
            except (ValueError, TypeError):
                parameter, dataset = par, par

            try:
                parameter = parameter.name
            except AttributeError:
                pass

            try:
                dataset = dataset.name
            except AttributeError:
                pass

            # Prefix return values
            parameter_, dataset_ = self._parse_dataset_and_parameter(parameter, dataset)

            if not (parameter_ and dataset_):
                parameter_, dataset_ = self._parse_parameter_and_dataset(parameter)

            if parameter_ and dataset_:
                parameters.append((parameter_, dataset_))
            else:
                log.info(f"parameter {parameter} could not be parsed from ({enums})")

        return parameters

    def _parse_dataset_and_parameter(self, parameter, dataset) -> Tuple[Optional[Enum], Optional[Enum]]:
        """
        Parse parameters for cases like
            - parameter=("climate_summary", ) or
            - parameter=(("precipitation_height", "climate_summary"))
        :param self:
        :param parameter:
        :param dataset:
        :return:
        """
        parameter_, dataset_ = None, None

        try:
            dataset_ = parse_enumeration_from_template(dataset, self._dataset_base)
        except InvalidEnumeration:
            pass

        if dataset_ and self._has_datasets and not self._unique_dataset:
            try:
                self._parameter_base[self._dataset_accessor][dataset_.name]
            except (KeyError, AttributeError):
                log.warning(f"dataset {dataset_.name} is not a valid dataset for resolution {self._dataset_accessor}")
                return None, None

        if dataset_:
            if parameter == dataset:
                # Case 1: entire dataset e.g. parameter="climate_summary"
                parameter_, dataset_ = dataset_, dataset_
            else:
                # Case 2: dataset and parameter e.g. (precipitation_height, climate_summary)
                try:
                    parameter_ = parse_enumeration_from_template(
                        parameter, self._parameter_base[self._dataset_accessor][dataset_.name]
                    )
                except (InvalidEnumeration, TypeError):
                    pass

        return parameter_, dataset_

    def _parse_parameter_and_dataset(self, parameter) -> Tuple[Enum, Enum]:
        """Try to parse dataset first e.g. when "climate_summary" or
        "precipitation_height", "climate_summary" is requested

        :param parameter:
        :return:
        """

        parameter_, dataset_ = None, None

        flat_parameters = {par for par in self._parameter_base[self._dataset_accessor] if hasattr(par, "name")}

        for par in flat_parameters:
            if par.name.lower() == parameter.lower() or par.value.lower() == parameter.lower():
                parameter_ = par
                break

        if parameter_:
            dataset_name = parameter_.__class__.__name__

            dataset_ = parse_enumeration_from_template(dataset_name, self._dataset_base)

        return parameter_, dataset_

    @staticmethod
    def _parse_station_id(series: pd.Series) -> pd.Series:
        """
        Dedicated method for parsing station ids, by default uses the same method as
        parse_strings but could be modified by the implementation class

        :param series:
        :return:
        """
        return series.astype(str)

    def __init__(
        self,
        parameter: Tuple[Union[str, Enum]],
        resolution: Resolution,
        period: Period,
        start_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
        end_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
    ) -> None:
        """

        :param parameter: requested parameter(s)
        :param resolution: requested resolution
        :param period: requested period(s)
        :param start_date: Start date for filtering stations_result for their available data
        :param end_date:   End date for filtering stations_result for their available data
        """
        settings = copy(Settings)
        super().__init__()

        self.resolution = parse_enumeration_from_template(resolution, self._resolution_base, Resolution)
        self.period = self._parse_period(period)

        self.start_date, self.end_date = self.convert_timestamps(start_date, end_date)
        self.parameter = self._parse_parameter(parameter)

        if not self.parameter:
            raise NoParametersFound("no valid parameters could be parsed from given argument")

        self.humanize = settings.humanize

        tidy = settings.tidy
        if self._has_datasets:
            tidy = tidy or any([parameter not in self._dataset_base for parameter, dataset in self.parameter])
        self.tidy = tidy

        self.si_units = settings.si_units

        # skip empty stations
        self.skip_empty = self.tidy and settings.skip_empty
        self.skip_threshold = settings.skip_threshold
        self.dropna = self.tidy and settings.dropna
        self.interp_use_nearby_station_until_km = settings.interp_use_nearby_station_until_km

        if not tidy and settings.skip_empty:
            log.warning("option 'skip_empty' is only available with option 'tidy' and is thus ignored in this request.")

        if not tidy and settings.dropna:
            log.warning("option 'dropna' is only available with option 'tidy' and is thus ignored in this request.")

        # optional attribute for dynamic resolutions
        if self.resolution == Resolution.DYNAMIC:
            self._dynamic_frequency = None

        log.info(f"Processing request {self.__repr__()}")

    def __repr__(self):
        """Representation of request object"""
        parameters_joined = ", ".join([f"({parameter.value}/{dataset.value})" for parameter, dataset in self.parameter])
        periods_joined = self.period and ", ".join([period.value for period in self.period])

        return (
            f"{self.__class__.__name__}("
            f"parameter=[{parameters_joined}], "
            f"resolution={self.resolution.value}, "
            f"period=[{periods_joined}], "
            f"start_date={str(self.start_date)}, "
            f"end_date={str(self.end_date)}, "
            f"humanize={self.humanize}, "
            f"tidy={self.tidy}, "
            f"si_units={self.si_units})"
        )

    def __eq__(self, other) -> bool:
        """Equal method of request object"""
        return (
            self.parameter == other.parameter
            and self.resolution == other.resolution
            and self.period == other.period
            and self.start_date == other.start_date
            and self.end_date == other.end_date
        )

    @staticmethod
    def convert_timestamps(
        start_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
        end_date: Optional[Union[str, datetime, pd.Timestamp]] = None,
    ) -> Union[Tuple[None, None], Tuple[pd.Timestamp, pd.Timestamp]]:
        """
        Sort out start_date vs. end_date, parse strings to datetime
        objects and finally convert both to pd.Timestamp types.

        :param start_date: Start date for filtering stations_result for their available data
        :param end_date:   End date for filtering stations_result for their available data
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
            raise StartDateEndDateError("Error: 'start_date' must be smaller or equal to 'end_date'.")

        return pd.Timestamp(start_date), pd.Timestamp(end_date)

    @staticmethod
    def _format_unit(unit) -> str:
        """
        Method to format unit and create a string
        :param unit: pint Unit
        :return: unit as string
        """
        try:
            unit = unit.units
        except AttributeError:
            pass

        unit_string = format(unit, "~")

        if unit_string == "":
            return "-"

        return unit_string

    @classmethod
    def discover(cls, filter_=None, dataset=None, flatten: bool = True) -> dict:
        """
        Function to print/discover available parameters

        :param filter_:
        :param dataset:
        :param flatten:
        :return:
        """
        # TODO: Refactor this!!!
        flatten = cls._unique_dataset or flatten

        filter_ = cls._setup_discover_filter(filter_)

        if flatten:
            if dataset:
                log.warning("dataset filter will be ignored due to 'flatten'")

            parameters = {}

            for f in filter_:
                parameters[f.name.lower()] = {}

                for parameter in cls._parameter_base[f.name]:
                    if not hasattr(parameter, "name"):
                        continue

                    parameters[f.name.lower()][parameter.name.lower()] = {}

                    if cls._unique_dataset:
                        origin_unit, si_unit = cls._unit_tree[f.name][parameter.name].value
                    else:
                        origin_unit, si_unit = cls._unit_tree[f.name][parameter.__class__.__name__][
                            parameter.name
                        ].value

                    parameters[f.name.lower()][parameter.name.lower()]["origin"] = cls._format_unit(origin_unit)

                    parameters[f.name.lower()][parameter.name.lower()]["si"] = cls._format_unit(si_unit)

            return parameters

        datasets_filter = (
            pd.Series(dataset, dtype=str).apply(parse_enumeration_from_template, args=(cls._dataset_base,)).tolist()
            or cls._dataset_base
        )

        datasets_filter = [ds.name for ds in datasets_filter]

        parameters = {}

        for f in filter_:
            parameters[f.name.lower()] = {}

            for dataset in cls._parameter_base[f.name]:
                if hasattr(dataset, "name"):
                    continue

                dataset_name = dataset.__name__.lower()
                if dataset_name.startswith("_") or dataset_name.upper() not in datasets_filter:
                    continue

                parameters[f.name.lower()][dataset_name] = {}

                for parameter in dataset:
                    parameters[f.name.lower()][dataset_name][parameter.name.lower()] = {}

                    origin_unit, si_unit = cls._unit_tree[f.name][dataset_name.upper()][parameter.name].value

                    parameters[f.name.lower()][dataset_name][parameter.name.lower()]["origin"] = cls._format_unit(
                        origin_unit
                    )

                    parameters[f.name.lower()][dataset_name][parameter.name.lower()]["si"] = cls._format_unit(si_unit)

        return parameters

    @classmethod
    def _setup_discover_filter(cls, filter_) -> list:
        """
            Helper method to create filter for discover method, can be overwritten by
            subclasses to use other then the resolution for filtering

        :param filter_: typically resolution, if used in subclass can be directed
            towards something else
        :return:
        """
        if not filter_:
            filter_ = [*cls._resolution_base]

        return (
            pd.Series(filter_).apply(parse_enumeration_from_template, args=(cls._resolution_base, Resolution)).tolist()
        )

    @staticmethod
    def _coerce_meta_fields(df) -> pd.DataFrame:
        """
        Method for metadata column coercion.

        :param df: DataFrame with columns as strings
        :return: DataFrame with columns coerced to date etc.
        """
        df[Columns.STATION_ID.value] = pd.Series(df[Columns.STATION_ID.value].values, dtype=str)
        df[Columns.HEIGHT.value] = pd.Series(df[Columns.HEIGHT.value], dtype=float)
        df[Columns.LATITUDE.value] = df[Columns.LATITUDE.value].astype(float)
        df[Columns.LONGITUDE.value] = df[Columns.LONGITUDE.value].astype(float)
        df[Columns.NAME.value] = pd.Series(df[Columns.NAME.value].values, dtype=str)
        df[Columns.STATE.value] = pd.Series(df[Columns.STATE.value].values, dtype=str)

        df[Columns.FROM_DATE.value] = pd.to_datetime(df[Columns.FROM_DATE.value], infer_datetime_format=True)

        if not df[Columns.FROM_DATE.value].dt.tz:
            df[Columns.FROM_DATE.value] = df[Columns.FROM_DATE.value].dt.tz_localize(pytz.UTC)
        df[Columns.TO_DATE.value] = pd.to_datetime(df[Columns.TO_DATE.value], infer_datetime_format=True)
        if not df[Columns.TO_DATE.value].dt.tz:
            df[Columns.TO_DATE.value] = df[Columns.TO_DATE.value].dt.tz_localize(pytz.UTC)

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

        :return: pandas.DataFrame with the information of different available stations_result
        """
        df = self._all().copy().reset_index(drop=True)

        df = df.reindex(columns=self._base_columns)

        df = self._coerce_meta_fields(df)

        return StationsResult(self, df.reset_index(drop=True))

    def filter_by_station_id(self, station_id: Tuple[str, ...]) -> StationsResult:
        """
        Method to filter stations_result by station ids

        :param station_id: list of stations_result that are requested
        :return: df with filtered stations_result
        """
        df = self.all().df

        station_id = self._parse_station_id(pd.Series(station_id))

        log.info(f"Filtering for station_id={list(station_id)}")

        df = df[df[Columns.STATION_ID.value].isin(station_id)]

        return StationsResult(self, df)

    def filter_by_name(self, name: str, first: bool = True, threshold: int = 90) -> StationsResult:
        """
        Method to filter stations_result for station name using string comparison.

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

        return StationsResult(stations=self, df=df)

    def filter_by_rank(
        self,
        latlon: Tuple[float, float],
        rank: int,
    ) -> StationsResult:
        """
        Wrapper for get_nearby_stations_by_number using the given parameter set. Returns
        nearest stations_result defined by number.

        :param latlon: tuple of latitude and longitude for queried point
        :param rank: number of stations_result to be returned, greater 0
        :return: pandas.DataFrame with station information for the selected stations_result
        """
        rank = int(rank)

        if rank <= 0:
            raise ValueError("'num_stations_nearby' has to be at least 1.")

        lat, lon = latlon

        coords = Coordinates(np.array(lat), np.array(lon))

        df = self.all().df.reset_index(drop=True)

        distances, indices_nearest_neighbours = derive_nearest_neighbours(
            df[Columns.LATITUDE.value].values,
            df[Columns.LONGITUDE.value].values,
            coords,
            min(rank, df.shape[0]),
        )

        df = df.iloc[indices_nearest_neighbours.flatten(), :].reset_index(drop=True)

        df[Columns.DISTANCE.value] = pd.Series(distances.flatten() * EARTH_RADIUS_KM, dtype=float)

        if df.empty:
            log.warning(
                f"No weather stations_result were found for coordinate " f"{lat}°N and {lon}°E and number {rank}"
            )

        return StationsResult(self, df.reset_index(drop=True))

    def filter_by_distance(self, latlon: Tuple[float, float], distance: float, unit: str = "km") -> StationsResult:
        """
        Wrapper for get_nearby_stations_by_distance using the given parameter set.
        Returns nearest stations_result defined by distance (km).

        :param latlon: tuple of latitude and longitude for queried point
        :param distance: distance (km) for which stations_result will be selected
        :param unit: unit string for conversion
        :return: pandas.DataFrame with station information for the selected stations_result
        """
        distance = float(distance)

        # Theoretically a distance of 0 km is possible
        if distance < 0:
            raise ValueError("'distance' has to be at least 0.0")

        unit = unit.strip()

        distance_in_km = guess(distance, unit, [Distance]).km

        all_nearby_stations = self.filter_by_rank(latlon, self.all().df.shape[0]).df

        df = all_nearby_stations[all_nearby_stations[Columns.DISTANCE.value] <= distance_in_km]

        if df.empty:
            lat, lon = latlon
            log.warning(
                f"No weather stations_result were found for coordinate "
                f"{lat}°N and {lon}°E and distance {distance_in_km}km"
            )

        return StationsResult(stations=self, df=df.reset_index(drop=True))

    def filter_by_bbox(self, left: float, bottom: float, right: float, top: float) -> StationsResult:
        """
        Method to filter stations_result by bounding box.

        :param bottom: bottom latitude as float
        :param left: left longitude as float
        :param top: top latitude as float
        :param right: right longitude as float
        :return: df with stations_result in bounding box
        """
        left, bottom, right, top = float(left), float(bottom), float(right), float(top)

        if left >= right:
            raise ValueError("bbox left border should be smaller then right")

        if bottom >= top:
            raise ValueError("bbox bottom border should be smaller then top")

        lat_interval = pd.Interval(bottom, top, closed="both")
        lon_interval = pd.Interval(left, right, closed="both")

        df = self.all().df

        df = df.loc[
            df[Columns.LATITUDE.value].apply(lambda x: x in lat_interval)
            & df[Columns.LONGITUDE.value].apply(lambda x: x in lon_interval),
            :,
        ]

        return StationsResult(stations=self, df=df.reset_index(drop=True))

    def filter_by_sql(self, sql: str) -> StationsResult:
        """

        :param sql:
        :return:
        """
        import duckdb

        df = self.all().df

        df: pd.DataFrame = duckdb.query_df(df, "data", sql).df()

        df[Columns.FROM_DATE.value] = df.loc[:, Columns.FROM_DATE.value].dt.tz_convert(self.tz)
        df[Columns.TO_DATE.value] = df.loc[:, Columns.TO_DATE.value].dt.tz_convert(self.tz)

        return StationsResult(stations=self, df=df.reset_index(drop=True))

    def interpolate(self, latlon: Tuple[float, float]) -> InterpolatedValuesResult:
        """
        Method to interpolate values

        :param latlon: tuple of latitude and longitude for queried point
        :return: interpolated values
        """

        from wetterdienst.core.scalar.interpolate import get_interpolated_df
        from wetterdienst.provider.dwd.observation import DwdObservationRequest

        if self.resolution in (
            Resolution.MINUTE_1,
            Resolution.MINUTE_5,
            Resolution.MINUTE_10,
        ):
            log.warning("Interpolation might be slow for high resolutions due to mass of data")

        if not isinstance(self, DwdObservationRequest):
            log.error("Interpolation currently only works for DwdObservationRequest")
            return InterpolatedValuesResult(df=pd.DataFrame(), stations=self)
        lat, lon = latlon
        lat, lon = float(lat), float(lon)
        interpolated_values = get_interpolated_df(self, lat, lon)
        return InterpolatedValuesResult(df=interpolated_values, stations=self)

    def interpolate_by_station_id(self, station_id: str) -> InterpolatedValuesResult:
        """
        Wrapper around .interpolate that uses station_id instead, for which latlon is determined by station list.
        :param station_id:
        :return:
        """
        latlon = self._get_latlon_by_station_id(station_id)
        return self.interpolate(latlon=latlon)

    def summarize(self, latlon: Tuple[float, float]) -> SummarizedValuesResult:
        """
        Method to interpolate values

        :param latlon: tuple of latitude and longitude for queried point
        :return:
        """
        from wetterdienst.core.scalar.summarize import get_summarized_df
        from wetterdienst.provider.dwd.observation import DwdObservationRequest

        if self.resolution in (
            Resolution.MINUTE_1,
            Resolution.MINUTE_5,
            Resolution.MINUTE_10,
        ):
            log.warning("Summary might be slow for high resolutions due to mass of data")

        if not isinstance(self, DwdObservationRequest):
            log.error("Interpolation currently only works for DwdObservationRequest")
            return SummarizedValuesResult(df=pd.DataFrame(), stations=self)
        lat, lon = latlon
        lat, lon = float(lat), float(lon)
        summarized_values = get_summarized_df(self, lat, lon)
        return SummarizedValuesResult(df=summarized_values, stations=self)

    def summarize_by_station_id(self, station_id: str) -> SummarizedValuesResult:
        """
        Wrapper around .summarize that uses station_id instead, for which latlon is determined by station list.
        :param station_id: station id
        :return:
        """
        latlon = self._get_latlon_by_station_id(station_id)
        return self.summarize(latlon=latlon)

    def _get_latlon_by_station_id(self, station_id: str) -> Tuple[float, float]:
        """
        Method to parse latlon for methods .summary/.interpolate. Typically, we expect a latlon tuple of floats, but
        we want users to be able to request for a station id as well.
        :param latlon: either tuple of two floats or station id
        :return: tuple of latlon
        """
        station_id = self._parse_station_id(pd.Series(station_id)).iloc[0]
        stations = self.all().df
        try:
            lat, lon = stations.loc[
                stations[Columns.STATION_ID.value] == station_id, [Columns.LATITUDE.value, Columns.LONGITUDE.value]
            ].values.flatten()
        except ValueError:
            raise StationNotFoundError(f"no station found for {station_id}")

        return lat, lon
