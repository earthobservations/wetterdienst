# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import datetime as dt
import logging
from abc import abstractmethod
from collections.abc import Sequence
from hashlib import sha256
from zoneinfo import ZoneInfo

import numpy as np
import polars as pl
from measurement.measures import Distance
from measurement.utils import guess
from polars.exceptions import NoDataError
from rapidfuzz import fuzz, process

from wetterdienst.core.timeseries.metadata import (
    DatasetModel,
    MetadataModel,
    ParameterModel,
    ResolutionModel,
    parse_parameters,
)
from wetterdienst.core.timeseries.result import (
    InterpolatedValuesResult,
    StationsFilter,
    StationsResult,
    SummarizedValuesResult,
)
from wetterdienst.exceptions import (
    NoParametersFoundError,
    StartDateEndDateError,
    StationNotFoundError,
)
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.parameter import Parameter
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.settings import Settings
from wetterdienst.util.python import to_list

try:
    from backports.datetime_fromisoformat import MonkeyPatch
except ImportError:
    pass
else:
    MonkeyPatch.patch_fromisoformat()

log = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371

# types
# either of
# str: "daily/kl" or "daily/kl/temperature_air_mean_2m"  # noqa: ERA001
# tuple: ("daily", "kl") or ("daily", "kl", "temperature_air_mean_2m")  # noqa: ERA001
# Parameter: DwdObservationMetadata.daily.kl.temperature_air_mean_2m or DwdObservationMetadata["daily"]["kl"]["temperature_air_mean_2m"]  # noqa: E501, ERA001
_PARAMETER_TYPE_SINGULAR = str | tuple[str, str] | tuple[str, str, str] | ParameterModel | DatasetModel
_PARAMETER_TYPE = _PARAMETER_TYPE_SINGULAR | Sequence[_PARAMETER_TYPE_SINGULAR]
_DATETIME_TYPE = str | dt.datetime | None
_SETTINGS_TYPE = dict | Settings | None


class TimeseriesRequest:
    """Core for stations_result information of a source"""

    @property
    @abstractmethod
    def metadata(self) -> MetadataModel:
        """metadata model"""
        pass

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
        Parameter.TEMPERATURE_AIR_MEAN_2M.name.lower(),
        Parameter.TEMPERATURE_AIR_MAX_2M.name.lower(),
        Parameter.TEMPERATURE_AIR_MIN_2M.name.lower(),
        Parameter.WIND_SPEED.name.lower(),
        Parameter.PRECIPITATION_HEIGHT.name.lower(),
    ]

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
        parameters: _PARAMETER_TYPE,
        start_date: _DATETIME_TYPE = None,
        end_date: _DATETIME_TYPE = None,
        settings: _SETTINGS_TYPE = None,
    ) -> None:
        """

        :param parameters: requested parameter(s)
        :param resolution: requested resolution
        :param period: requested period(s)
        :param start_date: Start date for filtering stations_result for their available data
        :param end_date:   End date for filtering stations_result for their available data
        """
        settings = settings or Settings()
        self.settings = Settings.model_validate(settings)

        super().__init__()

        self.start_date, self.end_date = self.convert_timestamps(start_date, end_date)
        self.parameters = parse_parameters(parameters, self.metadata)

        if not self.parameters:
            raise NoParametersFoundError("no valid parameters could be parsed from given argument")

        self.humanize = settings.ts_humanize
        self.shape = settings.ts_shape
        self.tidy = 1 if self.shape == "long" else 0
        self.convert_units = settings.ts_convert_units

        self.drop_nulls = self.tidy and settings.ts_drop_nulls
        self.complete = not self.drop_nulls and settings.ts_complete
        # skip empty stations
        self.skip_empty = self.complete and settings.ts_skip_empty
        self.skip_threshold = settings.ts_skip_threshold

        self.interp_use_nearby_station_until_km = settings.ts_interpolation_use_nearby_station_distance

        if self.drop_nulls != settings.ts_drop_nulls:
            log.info(
                "option 'ts_drop_nulls' is only available with option 'ts_shape=long' and "
                "is thus ignored in this request.",
            )

        if self.complete != settings.ts_complete:
            log.info(
                "option 'ts_complete' is only available with option 'ts_drop_nulls=False' and "
                "is thus ignored in this request.",
            )

        if self.skip_empty != settings.ts_skip_empty:
            log.info(
                "option 'ts_skip_empty' is only available with options `ts_drop_nulls=False` and 'ts_complete=True' "
                "and is thus ignored in this request.",
            )

        log.info(f"Processing request {self.__repr__()}")

    def __eq__(self, other):
        if not isinstance(other, TimeseriesRequest):
            return False

        return (
            self.parameters == other.parameters
            and self.start_date == other.start_date
            and self.end_date == other.end_date
            and self.settings == other.settings
        )

    @staticmethod
    def convert_timestamps(
        start_date: _DATETIME_TYPE,
        end_date: _DATETIME_TYPE,
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

    @classmethod
    def discover(
        cls,
        resolutions: str | Resolution | ResolutionModel | Sequence[str | Resolution | ResolutionModel] = None,
        datasets: str | DatasetModel | Sequence[str | DatasetModel] = None,
    ) -> dict:
        """Function to print/discover available parameters"""
        if not resolutions:
            resolutions = []
        resolution_strings = []
        for resolution in to_list(resolutions):
            if isinstance(resolution, Resolution):
                resolution = resolution.value
            elif isinstance(resolution, ResolutionModel):
                resolution = resolution.name
            else:
                resolution = str(resolution)
            resolution_strings.append(resolution)
        if not datasets:
            datasets = []
        dataset_strings = []
        for dataset in to_list(datasets):
            if isinstance(dataset, DatasetModel):
                dataset = dataset.name
            else:
                dataset = str(dataset)
            dataset_strings.append(dataset)
        data = {}
        for resolution in cls.metadata:
            if (
                resolution_strings
                and resolution.name not in resolution_strings
                and resolution.name_original not in resolution_strings
            ):
                continue
            data[resolution.name] = {}
            for dataset in resolution:
                if (
                    dataset_strings
                    and dataset.name not in dataset_strings
                    and dataset.name_original not in dataset_strings
                ):
                    continue
                data[resolution.name][dataset.name] = []
                for parameter in dataset:
                    data[resolution.name][dataset.name].append(
                        {
                            "name": parameter.name,
                            "name_original": parameter.name_original,
                            "unit_type": parameter.unit_type,
                            "unit": parameter.unit,
                        }
                    )
            if not data[resolution.name]:
                del data[resolution.name]
        return data

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
            df = pl.DataFrame(schema={col: pl.String for col in self._base_columns}, orient="col")

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
        Method to filter stations by sql query
        :param sql: SQL WHERE clause for filtering e.g. "name = 'Berlin'"
        :return: df with stations filtered by sql
        """
        import duckdb

        df = self.all().df
        df = df.with_columns(
            pl.col(Columns.START_DATE.value).dt.replace_time_zone(None),
            pl.col(Columns.END_DATE.value).dt.replace_time_zone(None),
        )
        sql = f"FROM df WHERE {sql}"
        df = duckdb.sql(sql).pl()  # uses "df" from local scope
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

        resolutions = {parameter.dataset.resolution.value for parameter in self.parameters}

        if resolutions.intersection({Resolution.MINUTE_1, Resolution.MINUTE_5, Resolution.MINUTE_10}):
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

        resolutions = {parameter.dataset.resolution.value for parameter in self.parameters}

        if resolutions.intersection({Resolution.MINUTE_1, Resolution.MINUTE_5, Resolution.MINUTE_10}):
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
