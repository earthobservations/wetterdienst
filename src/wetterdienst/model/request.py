# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Core for timeseries information of a source."""

from __future__ import annotations

import datetime as dt
import logging
from abc import abstractmethod
from collections.abc import Sequence
from dataclasses import dataclass, field
from hashlib import sha256
from typing import TYPE_CHECKING, ClassVar
from zoneinfo import ZoneInfo

import polars as pl
from measurement.measures import Distance
from measurement.utils import guess
from polars.exceptions import NoDataError
from rapidfuzz import fuzz, process

from wetterdienst.exceptions import (
    NoParametersFoundError,
    StartDateEndDateError,
    StationNotFoundError,
)
from wetterdienst.metadata.parameter import Parameter
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.metadata import (
    DatasetModel,
    MetadataModel,
    ParameterModel,
    ResolutionModel,
    parse_parameters,
)
from wetterdienst.model.result import (
    InterpolatedValuesResult,
    StationsFilter,
    StationsResult,
    SummarizedValuesResult,
)
from wetterdienst.settings import Settings
from wetterdienst.util.python import to_list

try:
    from backports.datetime_fromisoformat import MonkeyPatch
except ImportError:
    pass
else:
    MonkeyPatch.patch_fromisoformat()

if TYPE_CHECKING:
    from wetterdienst.model.values import TimeseriesValues
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


@dataclass
class TimeseriesRequest:
    """Core class for timeseries information of a source."""

    # implementations of subclasses
    metadata: MetadataModel = field(
        init=False,
        repr=False,
        default=None,
    )
    _values: TimeseriesValues = field(init=False, repr=False, default=None)

    # actual parameters
    parameters: _PARAMETER_TYPE
    start_date: _DATETIME_TYPE = None
    end_date: _DATETIME_TYPE = None
    settings: Settings | dict = field(default_factory=lambda: Settings())

    def __post_init__(self) -> None:
        """Post init method to validate the settings and convert the timestamps."""
        if not self.metadata:
            msg = f"{self.__class__.__name__}.metadata not implemented"
            raise NotImplementedError(msg)
        if not self._values:
            msg = f"{self.__class__.__name__}._values not implemented"
            raise NotImplementedError(msg)
        # Convert settings to a validated model
        self.settings = Settings.model_validate(self.settings)
        # Convert timestamps
        self.start_date, self.end_date = self.convert_timestamps(self.start_date, self.end_date)
        # Parse parameters
        if self.parameters:
            self.parameters = parse_parameters(self.parameters, self.metadata)  # type: list[ParameterModel]
        if not self.parameters:
            msg = "No valid parameters could be parsed from given argument"
            raise NoParametersFoundError(msg)

    # Columns that should be contained within any stations information
    _base_columns: ClassVar = (
        "resolution",
        "dataset",
        "station_id",
        "start_date",
        "end_date",
        "latitude",
        "longitude",
        "height",
        "name",
        "state",
    )

    #   - heterogeneous parameters such as precipitation_height
    #   - homogeneous parameters such as temperature_air_2m
    interpolatable_parameters: ClassVar = [
        Parameter.TEMPERATURE_AIR_MEAN_2M.name.lower(),
        Parameter.TEMPERATURE_AIR_MAX_2M.name.lower(),
        Parameter.TEMPERATURE_AIR_MIN_2M.name.lower(),
        Parameter.HUMIDITY.name.lower(),
        Parameter.WIND_SPEED.name.lower(),
        Parameter.PRECIPITATION_HEIGHT.name.lower(),
    ]

    @staticmethod
    def _parse_station_id(series: pl.Series) -> pl.Series:
        """Parse station_id column to string.

        Args:
            series: Series containing station ids.

        Returns:
            pl.Series: Series with station ids as strings.

        """
        return series.cast(pl.String)

    @staticmethod
    def convert_timestamps(  # noqa: C901
        start_date: _DATETIME_TYPE,
        end_date: _DATETIME_TYPE,
    ) -> tuple[None, None] | tuple[dt.datetime, dt.datetime]:
        """Convert timestamps to datetime objects.

        Args:
            start_date: Start date of the request.
            end_date: End date of the request.

        Returns:
            tuple[None, None] | tuple[dt.datetime, dt.datetime]: Start and end date of the request.

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
            msg = "Error: 'start_date' must be smaller or equal to 'end_date'."
            raise StartDateEndDateError(msg)

        return start_date, end_date

    @classmethod
    def discover(  # noqa: C901
        cls,
        resolutions: str | Resolution | ResolutionModel | Sequence[str | Resolution | ResolutionModel] = None,
        datasets: str | DatasetModel | Sequence[str | DatasetModel] = None,
    ) -> dict:
        """Discover metadata for the given resolutions and datasets.

        Args:
            resolutions: Resolutions to discover metadata for.
            datasets: Datasets to discover metadata for.

        Returns:
            dict: Metadata for the given resolutions and datasets.

        """
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
            dataset = dataset.name if isinstance(dataset, DatasetModel) else str(dataset)
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
                        },
                    )
            if not data[resolution.name]:
                del data[resolution.name]
        return data

    @staticmethod
    def _coerce_meta_fields(df: pl.DataFrame) -> pl.DataFrame:
        """Coerce metadata fields to the correct types."""
        return df.with_columns(
            pl.col("station_id").cast(pl.String),
            pl.col("height").cast(pl.Float64),
            pl.col("latitude").cast(pl.Float64),
            pl.col("longitude").cast(pl.Float64),
            pl.col("name").cast(pl.String),
            pl.col("state").cast(pl.String),
            pl.col("start_date").cast(pl.Datetime(time_zone="UTC")),
            pl.col("end_date").cast(pl.Datetime(time_zone="UTC")),
        )

    @abstractmethod
    def _all(self) -> pl.LazyFrame:
        """Implement this method to get all stations.

        Returns:
            pl.LazyFrame: All stations.

        """

    def all(self) -> StationsResult:
        """Get all stations.

        Returns:
            StationsResult: All stations.

        """
        df = self._all()

        df = df.collect()

        if not df.is_empty():
            df = df.select(pl.col(col) if col in df.columns else pl.lit(None).alias(col) for col in self._base_columns)
        else:
            df = pl.DataFrame(schema=dict.fromkeys(self._base_columns, pl.String), orient="col")

        df = self._coerce_meta_fields(df)

        return StationsResult(
            stations=self,
            df=df,
            df_all=df,
            stations_filter=StationsFilter.ALL,
        )

    def filter_by_station_id(self, station_id: str | tuple[str, ...] | list[str]) -> StationsResult:
        """Filter stations by station_id.

        Args:
            station_id: Station id or list of station ids.

        Returns:
            StationsResult: Filtered stations.

        """
        df = self.all().df

        station_id = self._parse_station_id(pl.Series(name="station_id", values=to_list(station_id)))

        log.info(f"Filtering for station_id={list(station_id)}")

        df_station_id = df.join(other=station_id.to_frame(), on="station_id", how="inner")

        return StationsResult(
            stations=self,
            df=df_station_id,
            df_all=df,
            stations_filter=StationsFilter.BY_STATION_ID,
        )

    def filter_by_name(self, name: str, rank: int = 1, threshold: float = 0.9) -> StationsResult:
        """Filter stations by name.

        Args:
            name: Name of the station.
            rank: Number of stations requested.
            threshold: Threshold for the fuzzy search.

        Returns:
            StationsResult: Filtered stations.

        """
        rank = int(rank)
        if rank <= 0:
            msg = "'rank' has to be at least 1."
            raise ValueError(msg)

        threshold = float(threshold)
        if threshold < 0 or threshold > 1:
            msg = "threshold must be between 0.0 and 1.0"
            raise ValueError(msg)

        df = self.all().df

        station_match = process.extract(
            query=name,
            choices=df.get_column("name"),
            scorer=fuzz.token_set_ratio,
            score_cutoff=threshold * 100,
        )

        if station_match:
            station_name = [station[0] for station in station_match]
            df = df.filter(pl.col("name").is_in(station_name))
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
        """Filter stations by rank.

        Rank is defined by distance to the requested point.

        Args:
            latlon: Latitude and longitude for the requested point.
            rank: Number of stations requested.

        Returns:
            StationsResult: Filtered stations.

        """
        from wetterdienst.util.geo import derive_nearest_neighbours  # noqa: PLC0415

        rank = int(rank)
        if rank <= 0:
            msg = "'rank' has to be at least 1."
            raise ValueError(msg)
        # setup spatial parameters
        q_lat, q_lon = latlon
        df = self.all().df
        latitudes = df.get_column("latitude").to_arrow()
        longitudes = df.get_column("longitude").to_arrow()
        distances = derive_nearest_neighbours(
            latitudes=latitudes,
            longitudes=longitudes,
            q_lat=q_lat,
            q_lon=q_lon,
        )
        # add distances and sort by distance
        df = df.with_columns(pl.lit(pl.Series(distances, dtype=pl.Float64)).alias("distance"))
        df = df.sort(by=["distance"])
        return StationsResult(
            stations=self,
            df=df,
            df_all=self.all().df,
            stations_filter=StationsFilter.BY_RANK,
            rank=rank,
        )

    def filter_by_distance(self, latlon: tuple[float, float], distance: float, unit: str = "km") -> StationsResult:
        """Filter stations by distance.

        Args:
            latlon: Latitude and longitude for the requested point.
            distance: Maximum distance to the requested point.
            unit: Unit of the distance.

        Returns:
            StationsResult: Filtered stations.

        """
        distance = float(distance)

        # Theoretically a distance of 0 km is possible
        if distance < 0:
            msg = "'distance' has to be at least 0"
            raise ValueError(msg)

        unit = unit.strip()

        distance_in_km = guess(distance, unit, [Distance]).km

        all_nearby_stations = self.filter_by_rank(latlon, self.all().df.shape[0]).df

        df = all_nearby_stations.filter(pl.col("distance").le(distance_in_km))

        if df.is_empty():
            log.info("No weather stations were found for the provided coordinates")

        return StationsResult(
            stations=self,
            df=df,
            df_all=self.all().df,
            stations_filter=StationsFilter.BY_DISTANCE,
        )

    def filter_by_bbox(self, left: float, bottom: float, right: float, top: float) -> StationsResult:
        """Filter stations by bounding box.

        Args:
            left: Left border of the bounding box.
            bottom: Bottom border of the bounding box.
            right: Right border of the bounding box.
            top: Top border of the bounding box.

        Returns:
            StationsResult: Filtered stations.

        """
        left, bottom, right, top = float(left), float(bottom), float(right), float(top)

        if left >= right:
            msg = "bbox left border should be smaller then right"
            raise ValueError(msg)

        if bottom >= top:
            msg = "bbox bottom border should be smaller then top"
            raise ValueError(msg)

        df = self.all().df

        df = df.filter(
            pl.col("latitude").is_between(bottom, top, closed="both")
            & pl.col("longitude").is_between(left, right, closed="both"),
        )

        if df.is_empty():
            log.info(f"No weather stations were found for bbox {left}/{bottom}/{top}/{right}")

        return StationsResult(stations=self, df=df, df_all=self.all().df, stations_filter=StationsFilter.BY_BBOX)

    def filter_by_sql(self, sql: str) -> StationsResult:
        """Filter stations by SQL query.

        Args:
            sql: SQL query to filter stations by.

        Returns:
            StationsResult: Filtered stations.

        """
        import duckdb  # noqa: PLC0415

        df = self.all().df
        df = df.with_columns(
            pl.col("start_date").dt.replace_time_zone(None),
            pl.col("end_date").dt.replace_time_zone(None),
        )
        sql = f"FROM df WHERE {sql}"
        df = duckdb.sql(sql).pl()  # uses "df" from local scope
        df = df.with_columns(
            pl.col("start_date").dt.replace_time_zone(time_zone="UTC"),
            pl.col("end_date").dt.replace_time_zone(time_zone="UTC"),
        )
        if df.is_empty():
            log.info(f"No stations were found for sql {sql}")
        return StationsResult(stations=self, df=df, df_all=self.all().df, stations_filter=StationsFilter.BY_SQL)

    def interpolate(self, latlon: tuple[float, float]) -> InterpolatedValuesResult:
        """Interpolate values across multiple stations.

        Interpolation means we interpolate the values of the closest available stations to the requested point.

        Args:
            latlon: Latitude and longitude for the requested point.

        Returns:
            InterpolatedValuesResult: Interpolated values.

        """
        from wetterdienst.core.interpolate import get_interpolated_df  # noqa: PLC0415

        if not self.start_date:
            msg = "start_date and end_date are required for interpolation"
            raise ValueError(msg)

        resolutions = {parameter.dataset.resolution.value for parameter in self.parameters}

        if resolutions.intersection({Resolution.MINUTE_1, Resolution.MINUTE_5, Resolution.MINUTE_10}):
            log.warning("Interpolation might be slow for high resolutions due to mass of data")

        lat, lon = latlon
        lat, lon = float(lat), float(lon)
        df_interpolated = get_interpolated_df(self, lat, lon)
        station_id = self._create_station_id_from_string(f"interpolation({lat:.4f},{lon:.4f})")
        df_interpolated = df_interpolated.select(
            pl.lit(station_id).alias("station_id"),
            pl.col("resolution"),
            pl.col("dataset"),
            pl.col("parameter"),
            pl.col("date"),
            pl.col("value"),
            pl.col("distance_mean"),
            pl.col("taken_station_ids"),
        )
        df_stations_all = self.all().df
        df_stations = df_stations_all.join(
            other=df_interpolated.select(pl.col("taken_station_ids").alias("station_id"))
            .explode(pl.col("station_id"))
            .unique(),
            on="station_id",
        )
        stations_result = StationsResult(
            stations=self,
            df=df_stations,
            df_all=self.all().df,
            stations_filter=StationsFilter.BY_STATION_ID,
        )
        return InterpolatedValuesResult(df=df_interpolated, stations=stations_result, latlon=latlon)

    def interpolate_by_station_id(self, station_id: str) -> InterpolatedValuesResult:
        """Use .interpolate with station_id instead of latlon."""
        latlon = self._get_latlon_by_station_id(station_id)
        return self.interpolate(latlon=latlon)

    def summarize(self, latlon: tuple[float, float]) -> SummarizedValuesResult:
        """Summarize values across multiple stations.

        Summarize means we take any available data of the closest station as representative for the timestamp.
        """
        from wetterdienst.core.summarize import get_summarized_df  # noqa: PLC0415

        if not self.start_date:
            msg = "start_date and end_date are required for summarization"
            raise ValueError(msg)

        resolutions = {parameter.dataset.resolution.value for parameter in self.parameters}

        if resolutions.intersection({Resolution.MINUTE_1, Resolution.MINUTE_5, Resolution.MINUTE_10}):
            log.warning("Summary might be slow for high resolutions due to mass of data")

        lat, lon = latlon
        lat, lon = float(lat), float(lon)
        summarized_values = get_summarized_df(self, lat, lon)
        station_id = self._create_station_id_from_string(f"summary({lat:.4f},{lon:.4f})")
        summarized_values = summarized_values.select(
            pl.lit(station_id).alias("station_id"),
            pl.col("resolution"),
            pl.col("dataset"),
            pl.col("parameter"),
            pl.col("date"),
            pl.col("value"),
            pl.col("distance"),
            pl.col("taken_station_id"),
        )
        df_stations_all = self.all().df
        df_stations = df_stations_all.join(
            other=summarized_values.select(pl.col("taken_station_id")).unique(),
            left_on="station_id",
            right_on="taken_station_id",
        )
        stations_result = StationsResult(
            stations=self,
            df=df_stations,
            df_all=self.all().df,
            stations_filter=StationsFilter.BY_STATION_ID,
        )
        return SummarizedValuesResult(df=summarized_values, stations=stations_result, latlon=latlon)

    def summarize_by_station_id(self, station_id: str) -> SummarizedValuesResult:
        """Use .summarize with station_id instead of latlon."""
        latlon = self._get_latlon_by_station_id(station_id)
        return self.summarize(latlon=latlon)

    def _get_latlon_by_station_id(self, station_id: str) -> tuple[float, float]:
        """Get latlon for a station_id.

        Used for .summary/.interpolate. Typically, we expect a latlon tuple of floats, but
        we want users to be able to request for a station id as well.
        """
        station_id = self._parse_station_id(pl.Series(values=to_list(station_id)))[0]
        stations = self.all().df
        try:
            lat, lon = (
                stations.filter(pl.col("station_id").eq(station_id))
                .select(pl.col("latitude"), pl.col("longitude"))
                .transpose()
                .to_series()
            )
        except NoDataError as e:
            msg = f"no station found for {station_id}"
            raise StationNotFoundError(msg) from e
        return lat, lon

    @staticmethod
    def _create_station_id_from_string(string: str) -> str:
        """Create station id from string.

        Used for interpolation and summarization data
        """
        return sha256(string.encode("utf-8")).hexdigest()[:8]
