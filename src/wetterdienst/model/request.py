# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Core for timeseries information of a source."""

from __future__ import annotations

import datetime as dt
import logging
from abc import abstractmethod
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, ClassVar
from zoneinfo import ZoneInfo

import polars as pl
from measurement.measures import Distance
from measurement.utils import guess
from polars.exceptions import NoDataError
from rapidfuzz import fuzz, process
from rapidfuzz import utils as fuzz_utils

from wetterdienst.exceptions import (
    NoParametersFoundError,
    NoPeriodsFoundError,
    StartDateEndDateError,
    StationNotFoundError,
)
from wetterdienst.io.export import ExportMixin
from wetterdienst.metadata.parameter_table import INTERPOLATABLE_PARAMETERS
from wetterdienst.metadata.period import Period
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
from wetterdienst.model.util import create_station_id_from_string
from wetterdienst.settings import Settings
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.python import to_list

try:
    from backports.datetime_fromisoformat import MonkeyPatch
except ImportError:
    pass
else:
    MonkeyPatch.patch_fromisoformat()

if TYPE_CHECKING:
    from wetterdienst.model.history import TimeseriesHistory
    from wetterdienst.model.values import TimeseriesValues
log = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371

# types
# either of
# str: "daily/kl" or "daily/kl/temperature_air_mean_2m"  # noqa: ERA001
# tuple of strings: ("daily", "kl") or ("daily", "kl", "temperature_air_mean_2m")
# Parameter: DwdObservationMetadata.daily.kl.temperature_air_mean_2m or DwdObservationMetadata["daily"]["kl"]["temperature_air_mean_2m"]  # noqa: E501, ERA001
_PARAMETER_TYPE_SINGULAR = str | tuple[str, str] | tuple[str, str, str] | ParameterModel | DatasetModel
_PARAMETER_TYPE = _PARAMETER_TYPE_SINGULAR | Sequence[_PARAMETER_TYPE_SINGULAR]
_DATETIME_TYPE = str | dt.datetime | None
# either of
# str: "recent"  # noqa: ERA001
# Period: Period.RECENT  # noqa: ERA001
# an iterable of either: ["historical", "recent"] or {Period.HISTORICAL, Period.RECENT}
_PERIOD_TYPE_SINGULAR = str | Period
_PERIODS_TYPE = _PERIOD_TYPE_SINGULAR | Iterable[_PERIOD_TYPE_SINGULAR] | None


def _format_periods(periods: Iterable[Period]) -> str:
    """Name periods the way they are requested, oldest first."""
    return ", ".join(period.value for period in sorted(periods))


@dataclass
class TimeseriesRequest:
    """Core class for timeseries information of a source."""

    # implementations of subclasses
    metadata: MetadataModel = field(  # ty: ignore[invalid-assignment]
        init=False,
        repr=False,
        default=None,
    )
    _values: TimeseriesValues = field(init=False, repr=False, default=None)  # ty: ignore[invalid-assignment]
    _history: TimeseriesHistory = field(init=False, repr=False, default=None)  # ty: ignore[invalid-assignment]
    # actual parameters
    parameters: _PARAMETER_TYPE  # ty: ignore[dataclass-field-order]
    start_date: _DATETIME_TYPE = None
    end_date: _DATETIME_TYPE = None
    settings: Settings | dict = field(default_factory=Settings)
    # The periods to read. Every provider publishes its datasets under one or more of them, so this
    # is accepted everywhere and resolved in __post_init__ to the set actually served -- see
    # `_resolve_periods`. A dataset published under a single period has nothing to choose between;
    # asking for another one is an error rather than a silently widened request.
    periods: _PERIODS_TYPE = None

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
        requested = self.parameters
        if isinstance(requested, Iterator):
            # parse_parameters consumes an iterator, so keep the values for the message below,
            # which would otherwise render the exhausted iterator rather than what was asked for
            requested = list(requested)
        if requested:
            self.parameters = parse_parameters(requested, self.metadata)  # type: list[ParameterModel]
        if not self.parameters:
            # the warnings parse_parameters logged say per parameter what was wrong with it, but
            # they are only visible to whoever configured logging, so name the request here too
            msg = f"No valid parameters could be parsed from {requested!r} for {type(self).__name__}"
            raise NoParametersFoundError(msg)
        # Has to follow the parameters, which say which datasets -- and so which periods -- were
        # asked for, and the timestamps, which a provider may derive the periods from
        self.periods = self._resolve_periods(self.periods)

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

    # The parameters that may be interpolated or summarized, which is a property of the measured
    # quantity rather than of a request -- see `CanonicalParameter.interpolation`. Kept here as a
    # class attribute because that is where callers look for it.
    interpolatable_parameters: ClassVar = INTERPOLATABLE_PARAMETERS

    # Whether the values implementation reads `self.periods` to decide which source to fetch. Only
    # a diagnostic: a provider that leaves it False still validates periods, it just cannot narrow
    # what it reads by them, and says so instead of accepting the argument and ignoring it. Getting
    # it wrong costs a spurious warning, never a dropped argument -- which is what the per-provider
    # `periods` field it replaces used to cost.
    _selects_by_period: ClassVar[bool] = False

    @classmethod
    def available_periods(cls) -> set[Period]:
        """Periods the provider publishes, across all of its datasets."""
        return {period for resolution in cls.metadata for dataset in resolution for period in dataset.periods}

    @property
    def published_periods(self) -> set[Period]:
        """Periods published for the datasets this request resolved to."""
        return {
            period
            for parameter in self.parameters
            if isinstance(parameter, ParameterModel)
            for period in parameter.dataset.periods
        }

    def _get_periods(self) -> set[Period] | None:
        """Derive the periods from the requested interval.

        ``None`` -- the default -- means the provider has no release schedule to derive them from,
        so the request falls back to every period its datasets publish. A provider that does know
        one returns the periods the interval reaches, which may legitimately be empty for an
        interval no period covers; see ``DwdObservationRequest._get_periods``.
        """
        return None

    def _resolve_periods(self, periods: _PERIODS_TYPE) -> set[Period]:
        """Resolve the requested periods against the ones the requested datasets publish.

        A period that is not published is dropped with a warning naming it, and if that leaves
        nothing the request fails -- it used to fall back to *every* period, so asking for one that
        does not exist quietly returned more data than asking for a valid one.
        """
        published = self.published_periods
        if periods:
            requested = {parse_enumeration_from_template(period, Period) for period in to_list(periods)}
            served = requested & published
            if not served:
                msg = (
                    f"None of the periods {_format_periods(requested)} is published for the datasets requested "
                    f"from {type(self).__name__}. Available periods: {_format_periods(published)}"
                )
                raise NoPeriodsFoundError(msg)
            if dropped := requested - served:
                log.warning(
                    f"Periods {_format_periods(dropped)} are not published for the datasets requested from "
                    f"{type(self).__name__} and are skipped. Available periods: {_format_periods(published)}",
                )
            if served != published and not self._selects_by_period:
                log.warning(
                    f"{type(self).__name__} does not read its data per period, so asking for "
                    f"{_format_periods(served)} does not narrow what is returned: every period the requested "
                    f"datasets publish ({_format_periods(published)}) is read.",
                )
            return served
        if self.start_date is not None:
            derived = self._get_periods()
            if derived is not None:
                if not derived:
                    # The interval reaches no release at all -- a window in the future. There is
                    # nothing to read and nothing to fall back to, so the request stays empty
                    # rather than downloading a period that cannot hold it
                    return derived
                # The derived periods have to pass the same check as the requested ones, or a
                # request lands on a period its datasets do not publish: an interval reaching into
                # today derives `now`, which `daily/kl` has no release for, and the request then
                # read no station index at all and reported no stations rather than no data. Where
                # the interval reaches past the newest release a dataset has, that release is what
                # holds whatever it can answer with, so fall back to it rather than to every period
                # -- which would pull the whole historical archive for a query about today.
                return derived & published or {max(published)}
        return published

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
        if not isinstance(start_date, dt.datetime) or not isinstance(end_date, dt.datetime):
            msg = "start_date and end_date must be datetime objects at this point"
            raise TypeError(msg)
        if not start_date <= end_date:
            msg = "Error: 'start_date' must be smaller or equal to 'end_date'."
            raise StartDateEndDateError(msg)

        return start_date, end_date

    @classmethod
    def is_configured(cls) -> bool:
        """Return True if this provider's required credentials are present (env var / settings).

        This is a cheap, offline check. Override in subclasses that require authentication.
        """
        return True

    @classmethod
    def is_valid(cls, settings: Settings | None = None) -> bool:  # noqa: ARG003
        """Return True if the provider's credentials are valid (authenticated successfully).

        This may perform a lightweight network probe and should cache the result.
        Only called when is_configured() is True. Override in auth-requiring subclasses.
        The optional `settings` argument lets callers pass a custom Settings instance;
        implementations that ignore it fall back to Settings() internally.
        """
        return True

    @classmethod
    def discover(  # noqa: C901
        cls,
        resolutions: str | Resolution | ResolutionModel | Sequence[str | Resolution | ResolutionModel] | None = None,
        datasets: str | DatasetModel | Sequence[str | DatasetModel] | None = None,
    ) -> dict:
        """Discover metadata for the given resolutions and datasets.

        Each level carries its own description, so the shape has a place for one::

            {resolution: {"description": ..., "datasets": {dataset: {"description": ...,
             "parameters": [{"name": ..., "name_original": ..., "unit_type": ..., "unit": ...,
             "description": ...}]}}}}

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
            described_datasets = {}
            for dataset in resolution:
                if (
                    dataset_strings
                    and dataset.name not in dataset_strings
                    and dataset.name_original not in dataset_strings
                ):
                    continue
                described_datasets[dataset.name] = {
                    "description": dataset.description,
                    "parameters": [
                        {
                            "name": parameter.name,
                            "name_original": parameter.name_original,
                            "unit_type": parameter.unit_type,
                            "unit": parameter.unit,
                            # the source's own words for its own field, where we have them; the
                            # canonical, provider-independent sentence lives in the glossary
                            "description": parameter.description,
                        }
                        for parameter in dataset
                    ],
                }
            if not described_datasets:
                continue
            data[resolution.name] = {
                "description": resolution.description,
                "datasets": described_datasets,
            }
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

        result = df.collect(background=False)
        if not isinstance(result, pl.DataFrame):
            msg = "collect() did not return a DataFrame"
            raise TypeError(msg)
        df = result

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

        station_id_series = self._parse_station_id(pl.Series(name="station_id", values=to_list(station_id)))

        log.info(f"Filtering for station_id={list(station_id_series)}")

        df_station_id = df.join(other=station_id_series.to_frame(), on="station_id", how="inner")

        return StationsResult(
            stations=self,
            df=df_station_id,
            df_all=df,
            stations_filter=StationsFilter.BY_STATION_ID,
        )

    def filter_by_name(self, name: str, rank: int = 1, threshold: float = 0.8) -> StationsResult:
        """Filter stations by name.

        Args:
            name: Name of the station.
            rank: Maximum number of matches to return, best score first (default 1).
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

        # WRatio (rapidfuzz's weighted composite of ratio/partial/token-sort/token-set with
        # length-ratio guards) so a short place query matches longer station names: "Kiel" ->
        # "Kiel-Holtenau"/"Kiel-Kronshagen". The previous token_sort_ratio scored by full-string
        # similarity and thus penalised the length gap ("Kiel" vs "Kiel-Holtenau" ~47%), so a bare
        # city name fell below the threshold and returned nothing.
        # limit=rank so the caller actually gets the requested number of matches; process.extract
        # otherwise defaults to its own limit (5) and the rank argument would be silently ignored.
        station_match = process.extract(
            query=name,
            choices=df.get_column("name"),
            scorer=fuzz.WRatio,
            score_cutoff=threshold * 100,
            processor=fuzz_utils.default_process,
            limit=rank,
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

        Rank is defined by distance to the requested point. The resulting
        ``StationsResult.df`` holds **all** stations sorted by distance, not just
        ``rank`` rows: because we cannot know upfront which stations actually carry
        data for the request, the ``rank`` limit is applied lazily while collecting
        values. Value collection walks the distance-sorted stations and stops once
        ``rank`` stations that returned anything have been consumed. The stations
        that ended up contributing values are then exposed via
        ``ValuesResult.df_stations``.

        In other words, use ``stations.values.all().df_stations`` (not
        ``stations.df``) to see the ``rank`` closest stations that actually returned
        data. Enable ``ts_skip_empty`` to walk past a station that returned data but
        too little of it, as ``ts_skip_threshold`` and ``ts_skip_criteria`` define.

        Args:
            latlon: Latitude and longitude for the requested point.
            rank: Number of stations requested.

        Returns:
            StationsResult: Stations sorted by distance (see note above on ``rank``).

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
        df = df.sort(by=["distance", "station_id"])
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
        df_all = self.all().df
        # the same filter a result runs, rather than a second copy of it naming the two timestamp
        # columns a stations frame happens to have and calling whatever comes back UTC
        df = ExportMixin._filter_by_sql(df_all, sql)  # noqa: SLF001
        if df.is_empty():
            log.info(f"No stations were found for sql {sql}")
        return StationsResult(stations=self, df=df, df_all=df_all, stations_filter=StationsFilter.BY_SQL)

    def interpolate(self, latlon: tuple[float, float], elevation: float | None = None) -> InterpolatedValuesResult:
        """Interpolate values across multiple stations.

        Interpolation means we interpolate the values of the closest available stations to the requested point.

        Args:
            latlon: Latitude and longitude for the requested point.
            elevation: Elevation of the requested point in metres above sea level. Given, the quantities that fall with
                height -- air temperature, dew point -- are brought from each station's altitude to
                this one before being interpolated, which is what tells a valley reading from a
                summit one. Left out, the readings are interpolated as they come.

        Returns:
            InterpolatedValuesResult: Interpolated values.

        """
        from wetterdienst.core.interpolate import get_interpolated_df  # noqa: PLC0415

        if not self.start_date:
            msg = "start_date and end_date are required for interpolation"
            raise ValueError(msg)

        resolutions = {
            parameter.dataset.resolution.value for parameter in self.parameters if isinstance(parameter, ParameterModel)
        }

        if resolutions.intersection(
            {Resolution.MINUTE_1, Resolution.MINUTE_5, Resolution.MINUTE_6, Resolution.MINUTE_10}
        ):
            log.warning("Interpolation might be slow for high resolutions due to mass of data")

        lat, lon = latlon
        lat, lon = float(lat), float(lon)
        df_interpolated = get_interpolated_df(self, lat, lon, elevation)
        # the elevation belongs in the name: two elevations at one point are two different
        # answers, and sharing an id would merge them wherever the id is what identifies a series
        point = (
            f"interpolation({lat:.4f},{lon:.4f})"
            if elevation is None
            else f"interpolation({lat:.4f},{lon:.4f},{elevation:.1f}m)"
        )
        station_id = create_station_id_from_string(point)
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
            .explode("station_id", empty_as_null=True)
            .unique(),
            on="station_id",
        )
        stations_result = StationsResult(
            stations=self,
            df=df_stations,
            df_all=self.all().df,
            stations_filter=StationsFilter.BY_STATION_ID,
        )
        return InterpolatedValuesResult(
            df=df_interpolated,
            stations=stations_result,
            latlon=latlon,
            elevation=elevation,
        )

    def interpolate_by_station_id(self, station_id: str, elevation: float | None = None) -> InterpolatedValuesResult:
        """Use .interpolate with station_id instead of latlon.

        Answers at the station's own altitude unless told another: naming a point by a station
        names its height as well, and it is the one case where an interpolation knows the elevation
        of its target without being told. For the reading uncorrected, pass the station's
        coordinates to `interpolate` instead.
        """
        latitude, longitude, station_height = self._get_position_by_station_id(station_id)
        return self.interpolate(
            latlon=(latitude, longitude),
            elevation=elevation if elevation is not None else station_height,
        )

    def summarize(self, latlon: tuple[float, float], elevation: float | None = None) -> SummarizedValuesResult:
        """Summarize values across multiple stations.

        Summarize means we take any available data of the closest station as representative for the timestamp.

        Args:
            latlon: Latitude and longitude for the requested point.
            elevation: Elevation of the requested point in metres above sea level. Given, a reading of a quantity that
                falls with height is brought from the station's altitude to this one -- which
                matters more here than in an interpolation, one station's reading standing for the
                point with nothing to soften the difference.

        Returns:
            SummarizedValuesResult: Summarized values.

        """
        from wetterdienst.core.summarize import get_summarized_df  # noqa: PLC0415

        if not self.start_date:
            msg = "start_date and end_date are required for summarization"
            raise ValueError(msg)

        resolutions = {
            parameter.dataset.resolution.value for parameter in self.parameters if isinstance(parameter, ParameterModel)
        }

        if resolutions.intersection(
            {Resolution.MINUTE_1, Resolution.MINUTE_5, Resolution.MINUTE_6, Resolution.MINUTE_10}
        ):
            log.warning("Summary might be slow for high resolutions due to mass of data")

        lat, lon = latlon
        lat, lon = float(lat), float(lon)
        summarized_values = get_summarized_df(self, lat, lon, elevation)
        # the elevation belongs in the name: two elevations at one point are two different
        # answers, and sharing an id would merge them wherever the id is what identifies a series
        point = (
            f"summary({lat:.4f},{lon:.4f})" if elevation is None else f"summary({lat:.4f},{lon:.4f},{elevation:.1f}m)"
        )
        station_id = create_station_id_from_string(point)
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
        return SummarizedValuesResult(
            df=summarized_values,
            stations=stations_result,
            latlon=latlon,
            elevation=elevation,
        )

    def summarize_by_station_id(self, station_id: str, elevation: float | None = None) -> SummarizedValuesResult:
        """Use .summarize with station_id instead of latlon.

        Answers at the station's own altitude unless told another, as `interpolate_by_station_id`
        does.
        """
        latitude, longitude, station_height = self._get_position_by_station_id(station_id)
        return self.summarize(
            latlon=(latitude, longitude),
            elevation=elevation if elevation is not None else station_height,
        )

    def _get_latlon_by_station_id(self, station_id: str) -> tuple[float, float]:
        """Get latlon for a station_id.

        Used for .summary/.interpolate. Typically, we expect a latlon tuple of floats, but
        we want users to be able to request for a station id as well.
        """
        latitude, longitude, _ = self._get_position_by_station_id(station_id)
        return latitude, longitude

    def _get_position_by_station_id(self, station_id: str) -> tuple[float, float, float | None]:
        """Get the coordinates and the height of a station.

        The height comes along because naming a point by a station names its altitude too, which
        is otherwise the one thing an interpolation cannot know about its target. It is null for
        the providers that do not report one.
        """
        station_id = self._parse_station_id(pl.Series(values=to_list(station_id)))[0]
        stations = self.all().df
        try:
            lat, lon, height = (
                stations.filter(pl.col("station_id").eq(station_id))
                .select(pl.col("latitude"), pl.col("longitude"), pl.col("height"))
                .transpose()
                .to_series()
            )
        except NoDataError as e:
            msg = f"no station found for {station_id}"
            raise StationNotFoundError(msg) from e
        return lat, lon, height
