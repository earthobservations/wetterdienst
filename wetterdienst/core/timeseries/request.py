# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import datetime as dt
import logging
from abc import abstractmethod
from enum import Enum
from hashlib import sha256
from typing import TYPE_CHECKING, Union
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl
from measurement.measures import Distance
from measurement.utils import guess
from polars.exceptions import NoDataError
from rapidfuzz import fuzz, process

from wetterdienst.core.core import Core
from wetterdienst.core.timeseries.result import (
    InterpolatedValuesResult,
    StationsFilter,
    StationsResult,
    SummarizedValuesResult,
)
from wetterdienst.exceptions import (
    InvalidEnumerationError,
    NoParametersFoundError,
    StartDateEndDateError,
    StationNotFoundError,
)
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.parameter import Parameter
from wetterdienst.metadata.period import Period, PeriodType
from wetterdienst.metadata.resolution import Frequency, Resolution, ResolutionType
from wetterdienst.settings import Settings
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.python import to_list

if TYPE_CHECKING:
    from collections.abc import Sequence

    from wetterdienst.metadata.datarange import DataRange
    from wetterdienst.metadata.kind import Kind
    from wetterdienst.metadata.provider import Provider

try:
    from backports.datetime_fromisoformat import MonkeyPatch
except ImportError:
    pass
else:
    MonkeyPatch.patch_fromisoformat()

log = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371

_PARAMETER_TYPE = Union[Union[str, Enum, Parameter], tuple[Union[str, Enum, Parameter], Union[str, Enum, Parameter]]]


class TimeseriesRequest(Core):
    """Core for stations_result information of a source"""

    @property
    @abstractmethod
    def _provider(self) -> Provider:
        """Optional enumeration for multiple resolutions"""
        pass

    @property
    @abstractmethod
    def _kind(self) -> Kind:
        """Optional enumeration for multiple resolutions"""
        pass

    @property
    @abstractmethod
    def _resolution_base(self) -> Resolution | None:
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
    def dynamic_frequency(self) -> Frequency | None:
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
    def _period_base(self) -> Period | None:
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
    def _unit_base(self):
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
    def _dataset_base(self) -> Enum | None:
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
    def _parameter_to_dataset_mapping(self) -> dict:
        """Mapping to go from a (flat) parameter to dataset"""
        if not self._unique_dataset:
            raise NotImplementedError("for non unique datasets implement a mapping from parameter to dataset")
        return {}

    @property
    def datasets(self):
        datasets = self._dataset_tree[self._dataset_accessor].__dict__.keys()
        return [ds for ds in datasets if ds not in ("__module__", "__doc__")]

    @property
    @abstractmethod
    def _values(self):
        """Class to get the values for a request"""
        pass

    # Columns that should be contained within any stations_result information
    _base_columns = (
        Columns.STATION_ID.value,
        Columns.START_DATE.value,
        Columns.END_DATE.value,
        Columns.LATITUDE.value,
        Columns.LONGITUDE.value,
        Columns.HEIGHT.value,
        Columns.NAME.value,
        Columns.STATE.value,
    )

    #   - heterogeneous parameters such as precipitation_height
    #   - homogeneous parameters such as temperature_air_2m
    interpolatable_parameters = [
        Parameter.TEMPERATURE_AIR_MEAN_2M.name,
        Parameter.TEMPERATURE_AIR_MAX_2M.name,
        Parameter.TEMPERATURE_AIR_MIN_2M.name,
        Parameter.WIND_SPEED.name,
        Parameter.PRECIPITATION_HEIGHT.name,
    ]

    def _parse_period(self, period: Period) -> list[Period] | None:
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
            return sorted(
                [
                    parse_enumeration_from_template(p, intermediate=self._period_base, base=Period)
                    for p in to_list(period)
                ],
            )

    def _parse_parameter(self, parameter: list[str | Enum | None]) -> list[tuple[Enum, Enum]]:
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

        for par in to_list(parameter):
            # Each parameter can either be
            #  - a dataset : gets all data from the dataset
            #  - a parameter : gets prefixed parameter from a resolution e.g.
            #      precipitation height of daily values is taken from climate summary
            #  - a tuple of parameter -> dataset : to decide from which dataset
            #    the parameter is taken
            try:
                parameter, dataset = to_list(par)
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

    def _parse_dataset_and_parameter(self, parameter, dataset) -> tuple[Enum | None, Enum | None]:
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
        except InvalidEnumerationError:
            pass

        if dataset_:
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
                        parameter,
                        self._parameter_base[self._dataset_accessor][dataset_.name],
                    )
                except (InvalidEnumerationError, TypeError):
                    pass

        return parameter_, dataset_

    def _parse_parameter_and_dataset(self, parameter) -> tuple[Enum, Enum]:
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
    def _parse_station_id(series: pl.Series) -> pl.Series:
        """
        Dedicated method for parsing station ids, by default uses the same method as
        parse_strings but could be modified by the implementation class
        :param series:
        :return:
        """
        return series.cast(pl.String)

    def __init__(
        self,
        parameter: str | Parameter | Sequence[str | Parameter],
        resolution: str | Resolution,
        period: str | Period,
        start_date: str | dt.datetime | None = None,
        end_date: str | dt.datetime | None = None,
        settings: Settings | None = None,
    ) -> None:
        """

        :param parameter: requested parameter(s)
        :param resolution: requested resolution
        :param period: requested period(s)
        :param start_date: Start date for filtering stations_result for their available data
        :param end_date:   End date for filtering stations_result for their available data
        """
        settings = settings or Settings.default()
        self.settings = Settings.model_validate(settings)

        super().__init__()

        self.resolution = parse_enumeration_from_template(resolution, self._resolution_base, Resolution)
        self.period = self._parse_period(period)

        self.start_date, self.end_date = self.convert_timestamps(start_date, end_date)
        self.parameter = self._parse_parameter(parameter)

        if not self.parameter:
            raise NoParametersFoundError("no valid parameters could be parsed from given argument")

        self.humanize = settings.ts_humanize
        self.shape = settings.ts_shape
        self.tidy = 1 if self.shape == "long" else 0
        self.si_units = settings.ts_si_units

        # skip empty stations
        self.skip_empty = self.tidy and settings.ts_skip_empty
        self.skip_threshold = settings.ts_skip_threshold

        self.dropna = self.tidy and settings.ts_dropna
        self.interp_use_nearby_station_until_km = settings.ts_interpolation_use_nearby_station_distance

        if not self.tidy and settings.ts_skip_empty:
            log.info(
                "option 'ts_skip_empty' is only available with option 'ts_shape' "
                "and is thus ignored in this request.",
            )

        if not self.tidy and settings.ts_dropna:
            log.info(
                "option 'ts_dropna' is only available with option 'ts_shape' " "and is thus ignored in this request.",
            )

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
            f"format={self.shape}, "
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
        start_date: str | dt.datetime | None = None,
        end_date: str | dt.datetime | None = None,
    ) -> tuple[None, None] | tuple[dt.datetime, dt.datetime]:
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
                start_date = dt.datetime.fromisoformat(start_date)
            if not start_date.tzinfo:
                start_date = start_date.replace(tzinfo=ZoneInfo("UTC"))

        if end_date:
            if isinstance(end_date, str):
                end_date = dt.datetime.fromisoformat(end_date)
            if not end_date.tzinfo:
                end_date = end_date.replace(tzinfo=ZoneInfo("UTC"))

        # If only one date given, set the other one to equal.
        if not start_date:
            start_date = end_date

        if not end_date:
            end_date = start_date

        # TODO: replace this with a response + logging
        if not start_date <= end_date:
            raise StartDateEndDateError("Error: 'start_date' must be smaller or equal to 'end_date'.")

        return start_date, end_date

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
    def discover(cls, resolution=None, dataset=None, flatten: bool = True, with_units: bool = True) -> dict:
        """
        Function to print/discover available parameters

        :param resolution:
        :param dataset:
        :param flatten:
        :param with_units:
        :return:
        """
        resolutions = cls._setup_resolution_filter(resolution)

        if flatten:
            if dataset:
                log.info("dataset filter will be ignored due to 'flatten'")

            parameters = {}

            for resolution_item in resolutions:
                resolution_name = resolution_item.name
                parameters[resolution_name.lower()] = {}

                for parameter in cls._parameter_base[resolution_name]:
                    if not hasattr(parameter, "name"):
                        continue

                    origin_unit, si_unit = cls._unit_base[resolution_name][parameter.__class__.__name__][
                        parameter.name
                    ].value

                    if with_units:
                        slot = parameters[resolution_name.lower()][parameter.name.lower()] = {}
                        slot["origin"] = cls._format_unit(origin_unit)
                        slot["si"] = cls._format_unit(si_unit)

            return parameters

        has_datasets = cls._has_datasets

        if dataset:
            datasets_filter = [
                parse_enumeration_from_template(ds, intermediate=cls._dataset_base) for ds in to_list(dataset)
            ]
        elif has_datasets:
            datasets_filter = cls._dataset_base
        else:
            datasets_filter = cls._resolution_base

        datasets_filter = [ds.name for ds in datasets_filter]

        parameters = {}

        for resolution_item in resolutions:
            resolution_name = resolution_item.name
            parameters[resolution_name.lower()] = {}

            for dataset in cls._parameter_base[resolution_name]:
                if hasattr(dataset, "name"):
                    continue

                dataset_name = dataset.__name__.lower()
                if dataset_name.startswith("_") or dataset_name.upper() not in datasets_filter:
                    continue

                parameters[resolution_name.lower()][dataset_name] = {}

                for parameter in dataset:
                    origin_unit, si_unit = cls._unit_base[resolution_name][dataset_name.upper()][parameter.name].value

                    if with_units:
                        slot = parameters[resolution_name.lower()][dataset_name][parameter.name.lower()] = {}
                        slot["origin"] = cls._format_unit(origin_unit)
                        slot["si"] = cls._format_unit(si_unit)

        return parameters

    @classmethod
    def _setup_resolution_filter(cls, resolution) -> list:
        """
            Helper method to create resolution filter for discover method.

        :param resolution: resolution label, like "recent" or "historical"
        :return:
        """
        if not resolution:
            resolution = [*cls._resolution_base]

        return [
            parse_enumeration_from_template(r, intermediate=cls._resolution_base, base=Resolution)
            for r in to_list(resolution)
        ]

    @staticmethod
    def _coerce_meta_fields(df: pl.DataFrame) -> pl.DataFrame:
        """
        Method for metadata column coercion.

        :param df: DataFrame with columns as strings
        :return: DataFrame with columns coerced to date etc.
        """
        return df.with_columns(
            pl.col(Columns.STATION_ID.value).cast(pl.String),
            pl.col(Columns.HEIGHT.value).cast(pl.Float64),
            pl.col(Columns.LATITUDE.value).cast(pl.Float64),
            pl.col(Columns.LONGITUDE.value).cast(pl.Float64),
            pl.col(Columns.NAME.value).cast(pl.String),
            pl.col(Columns.STATE.value).cast(pl.String),
            pl.col(Columns.START_DATE.value).cast(pl.Datetime(time_zone="UTC")),
            pl.col(Columns.END_DATE.value).cast(pl.Datetime(time_zone="UTC")),
        )

    @abstractmethod
    def _all(self) -> pl.LazyFrame:
        """
        Abstract method for gathering of sites information for a given implementation.
        Information consist of a DataFrame with station ids, location, name, etc

        :return: pandas.DataFrame with the information of different available sites
        """
        pass

    def all(self) -> StationsResult:  # noqa: A003
        """
        Wraps the _all method and applies date filters.

        :return: pandas.DataFrame with the information of different available stations_result
        """
        df = self._all()

        df = df.collect()

        if not df.is_empty():
            df = df.select(pl.col(col) if col in df.columns else pl.lit(None).alias(col) for col in self._base_columns)
        else:
            df = pl.DataFrame(schema={col: pl.String for col in self._base_columns})

        df = self._coerce_meta_fields(df)

        return StationsResult(
            stations=self,
            df=df,
            df_all=df,
            stations_filter=StationsFilter.ALL,
        )

    def filter_by_station_id(self, station_id: str | tuple[str, ...] | list[str]) -> StationsResult:
        """
        Method to filter stations_result by station ids

        :param station_id: list of stations_result that are requested
        :return: df with filtered stations_result
        """
        df = self.all().df

        station_id = self._parse_station_id(pl.Series(name=Columns.STATION_ID.value, values=to_list(station_id)))

        log.info(f"Filtering for station_id={list(station_id)}")

        df_station_id = df.join(other=station_id.to_frame(), on=Columns.STATION_ID.value, how="inner")

        return StationsResult(
            stations=self,
            df=df_station_id,
            df_all=df,
            stations_filter=StationsFilter.BY_STATION_ID,
        )

    def filter_by_name(self, name: str, rank: int = 1, threshold: float = 0.9) -> StationsResult:
        """
        Method to filter stations_result for station name using string comparison.

        :param name: name of looked up station
        :param rank: number of stations requested
        :param threshold: threshold for string match 0.0...1.0
        :return: df with matched station
        """
        rank = int(rank)
        if rank <= 0:
            raise ValueError("'rank' has to be at least 1.")

        threshold = float(threshold)
        if threshold < 0 or threshold > 1:
            raise ValueError("threshold must be between 0.0 and 1.0")

        df = self.all().df

        station_match = process.extract(
            query=name,
            choices=df[Columns.NAME.value],
            scorer=fuzz.token_set_ratio,
            score_cutoff=threshold * 100,
        )

        if station_match:
            station_name = [station[0] for station in station_match]
            df = df.filter(pl.col(Columns.NAME.value).is_in(station_name))
        else:
            df = pl.DataFrame(schema=df.schema)

        if df.is_empty():
            log.info(f"No weather stations were found for name {name}")

        return StationsResult(
            stations=self,
            df=df,
            df_all=self.all().df,
            stations_filter=StationsFilter.BY_NAME,
            rank=rank,
        )

    def filter_by_rank(
        self,
        latlon: tuple[float, float],
        rank: int,
    ) -> StationsResult:
        """
        Wrapper for get_nearby_stations_by_number using the given parameter set. Returns
        the nearest stations_result defined by number.

        :param latlon: tuple of latitude and longitude for queried point
        :param rank: number of stations_result to be returned, greater 0
        :return: pandas.DataFrame with station information for the selected stations_result
        """
        from wetterdienst.util.geo import Coordinates, derive_nearest_neighbours

        rank = int(rank)

        if rank <= 0:
            raise ValueError("'rank' has to be at least 1.")

        lat, lon = latlon

        coords = Coordinates(np.array(lat), np.array(lon))

        df = self.all().df

        distances, indices_nearest_neighbours = derive_nearest_neighbours(
            latitudes=df.get_column(Columns.LATITUDE.value),
            longitudes=df.get_column(Columns.LONGITUDE.value),
            coordinates=coords,
            number_nearby=df.shape[0],
        )
        distances = distances.flatten() * EARTH_RADIUS_KM

        df = df[indices_nearest_neighbours.flatten(), :]
        df = df.with_columns(pl.lit(distances).alias(Columns.DISTANCE.value))

        return StationsResult(
            stations=self,
            df=df,
            df_all=self.all().df,
            stations_filter=StationsFilter.BY_RANK,
            rank=rank,
        )

    def filter_by_distance(self, latlon: tuple[float, float], distance: float, unit: str = "km") -> StationsResult:
        """
        Wrapper for get_nearby_stations_by_distance using the given parameter set.
        Returns the nearest stations_result defined by distance (km).

        :param latlon: tuple of latitude and longitude for queried point
        :param distance: distance (km) for which stations_result will be selected
        :param unit: unit string for conversion
        :return: pandas.DataFrame with station information for the selected stations_result
        """
        distance = float(distance)

        # Theoretically a distance of 0 km is possible
        if distance < 0:
            raise ValueError("'distance' has to be at least 0")

        unit = unit.strip()

        distance_in_km = guess(distance, unit, [Distance]).km

        all_nearby_stations = self.filter_by_rank(latlon, self.all().df.shape[0]).df

        df = all_nearby_stations.filter(pl.col(Columns.DISTANCE.value).le(distance_in_km))

        if df.is_empty():
            lat, lon = latlon
            log.info(
                f"No weather stations were found for coordinates {lat}/{lon} (lat/lon) "
                f"and distance {distance_in_km}km",
            )

        return StationsResult(
            stations=self,
            df=df,
            df_all=self.all().df,
            stations_filter=StationsFilter.BY_DISTANCE,
        )

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

        df = self.all().df

        df = df.filter(
            pl.col(Columns.LATITUDE.value).is_between(bottom, top, closed="both")
            & pl.col(Columns.LONGITUDE.value).is_between(left, right, closed="both"),
        )

        if df.is_empty():
            log.info(f"No weather stations were found for bbox {left}/{bottom}/{top}/{right}")

        return StationsResult(stations=self, df=df, df_all=self.all().df, stations_filter=StationsFilter.BY_BBOX)

    def filter_by_sql(self, sql: str) -> StationsResult:
        """

        :param sql:
        :return:
        """
        import duckdb

        df = self.all().df
        df = df.with_columns(
            pl.col(Columns.START_DATE.value).dt.replace_time_zone(None),
            pl.col(Columns.END_DATE.value).dt.replace_time_zone(None),
        )
        df = duckdb.query_df(df.to_pandas(), "data", sql).df()
        df = pl.from_pandas(df)
        df = df.with_columns(
            pl.col(Columns.START_DATE.value).dt.replace_time_zone(time_zone="UTC"),
            pl.col(Columns.END_DATE.value).dt.replace_time_zone(time_zone="UTC"),
        )
        if df.is_empty():
            log.info(f"No stations were found for sql {sql}")
        return StationsResult(stations=self, df=df, df_all=self.all().df, stations_filter=StationsFilter.BY_SQL)

    def interpolate(self, latlon: tuple[float, float]) -> InterpolatedValuesResult:
        """
        Method to interpolate values

        :param latlon: tuple of latitude and longitude for queried point
        :return: interpolated values
        """

        from wetterdienst.core.timeseries.interpolate import get_interpolated_df

        if not self.start_date:
            raise ValueError("start_date and end_date are required for interpolation")

        if self.resolution in (
            Resolution.MINUTE_1,
            Resolution.MINUTE_5,
            Resolution.MINUTE_10,
        ):
            log.warning("Interpolation might be slow for high resolutions due to mass of data")

        lat, lon = latlon
        lat, lon = float(lat), float(lon)
        df_interpolated = get_interpolated_df(self, lat, lon)
        station_id = self._create_station_id_from_string(f"interpolation({lat:.4f},{lon:.4f})")
        df_interpolated = df_interpolated.select(
            pl.lit(station_id).alias(Columns.STATION_ID.value),
            pl.col(Columns.PARAMETER.value),
            pl.col(Columns.DATE.value),
            pl.col(Columns.VALUE.value),
            pl.col(Columns.DISTANCE_MEAN.value),
            pl.col(Columns.TAKEN_STATION_IDS.value),
        )
        df_stations_all = self.all().df
        df_stations = df_stations_all.join(
            other=df_interpolated.select(pl.col(Columns.TAKEN_STATION_IDS.value).alias(Columns.STATION_ID.value))
            .explode(pl.col(Columns.STATION_ID.value))
            .unique(),
            on=Columns.STATION_ID.value,
        )
        stations_result = StationsResult(
            stations=self,
            df=df_stations,
            df_all=self.all().df,
            stations_filter=StationsFilter.BY_STATION_ID,
        )
        return InterpolatedValuesResult(df=df_interpolated, stations=stations_result, latlon=latlon)

    def interpolate_by_station_id(self, station_id: str) -> InterpolatedValuesResult:
        """
        Wrapper around .interpolate that uses station_id instead, for which latlon is determined by station list.
        :param station_id:
        :return:
        """
        latlon = self._get_latlon_by_station_id(station_id)
        return self.interpolate(latlon=latlon)

    def summarize(self, latlon: tuple[float, float]) -> SummarizedValuesResult:
        """
        Method to interpolate values

        :param latlon: tuple of latitude and longitude for queried point
        :return:
        """
        from wetterdienst.core.timeseries.summarize import get_summarized_df

        if not self.start_date:
            raise ValueError("start_date and end_date are required for summarization")

        if self.resolution in (
            Resolution.MINUTE_1,
            Resolution.MINUTE_5,
            Resolution.MINUTE_10,
        ):
            log.warning("Summary might be slow for high resolutions due to mass of data")

        lat, lon = latlon
        lat, lon = float(lat), float(lon)
        summarized_values = get_summarized_df(self, lat, lon)
        station_id = self._create_station_id_from_string(f"summary({lat:.4f},{lon:.4f})")
        summarized_values = summarized_values.select(
            pl.lit(station_id).alias(Columns.STATION_ID.value),
            pl.col(Columns.PARAMETER.value),
            pl.col(Columns.DATE.value),
            pl.col(Columns.VALUE.value),
            pl.col(Columns.DISTANCE.value),
            pl.col(Columns.TAKEN_STATION_ID.value),
        )
        df_stations_all = self.all().df
        df_stations = df_stations_all.join(
            other=summarized_values.select(pl.col(Columns.TAKEN_STATION_ID.value)).unique(),
            left_on=Columns.STATION_ID.value,
            right_on=Columns.TAKEN_STATION_ID.value,
        )
        stations_result = StationsResult(
            stations=self,
            df=df_stations,
            df_all=self.all().df,
            stations_filter=StationsFilter.BY_STATION_ID,
        )
        return SummarizedValuesResult(df=summarized_values, stations=stations_result, latlon=latlon)

    def summarize_by_station_id(self, station_id: str) -> SummarizedValuesResult:
        """
        Wrapper around .summarize that uses station_id instead, for which latlon is determined by station list.
        :param station_id: station id
        :return:
        """
        latlon = self._get_latlon_by_station_id(station_id)
        return self.summarize(latlon=latlon)

    def _get_latlon_by_station_id(self, station_id: str) -> tuple[float, float]:
        """
        Method to parse latlon for methods .summary/.interpolate. Typically, we expect a latlon tuple of floats, but
        we want users to be able to request for a station id as well.
        :param latlon: either tuple of two floats or station id
        :return: tuple of latlon
        """
        station_id = self._parse_station_id(pl.Series(values=to_list(station_id)))[0]
        stations = self.all().df
        try:
            lat, lon = (
                stations.filter(pl.col(Columns.STATION_ID.value).eq(station_id))
                .select(pl.col(Columns.LATITUDE.value), pl.col(Columns.LONGITUDE.value))
                .transpose()
                .to_series()
            )
        except NoDataError as e:
            raise StationNotFoundError(f"no station found for {station_id}") from e
        return lat, lon

    @staticmethod
    def _create_station_id_from_string(string: str) -> str:
        """
        Method to create station id from string, used for interpolation and summarization data
        :param string: string to create station id from
        :return: station id
        """
        return sha256(string.encode("utf-8")).hexdigest()[:8]
