# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Core for timeseries information of a source."""

from __future__ import annotations

import copy
import datetime as dt
import logging
from abc import abstractmethod
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, Literal, Self, cast
from zoneinfo import ZoneInfo

import polars as pl
from measurement.measures import Distance
from measurement.utils import guess
from rapidfuzz import fuzz, process
from rapidfuzz import utils as fuzz_utils

from wetterdienst.exceptions import (
    InvalidBoundingBoxError,
    InvalidParameterError,
    InvalidTimeIntervalError,
    LocationOutOfRangeError,
    MetadataNotFoundError,
    MissingTimeIntervalError,
    NoParametersFoundError,
    NoPeriodsFoundError,
    ReversedTimeIntervalError,
    StationNotFoundError,
)
from wetterdienst.io.export import ExportMixin
from wetterdienst.metadata.parameter_table import INTERPOLATABLE_PARAMETERS
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.renamed import refuse_renamed_arguments
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.metadata import (
    CoverageDataset,
    CoverageResolution,
    DatasetModel,
    MetadataModel,
    ParameterModel,
    ResolutionModel,
    check_on_unknown,
    parse_parameters,
)
from wetterdienst.model.result import (
    InterpolatedValuesResult,
    StationsFilter,
    StationsResult,
    SummarizedValuesResult,
)
from wetterdienst.model.schema import INTERPOLATED_SCHEMA, STATIONS_SCHEMA, SUMMARIZED_SCHEMA, coerce
from wetterdienst.model.util import create_station_id_from_string
from wetterdienst.options import resolve_options
from wetterdienst.settings import Settings
from wetterdienst.util.datetime import parse_date_window
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.extras import import_optional
from wetterdienst.util.python import to_list
from wetterdienst.util.response_warnings import warn_response

if TYPE_CHECKING:
    from wetterdienst.model.history import TimeseriesHistory
    from wetterdienst.model.values import TimeseriesValues
    from wetterdienst.options import Options
log = logging.getLogger(__name__)

EARTH_RADIUS_KM = 6371

# How many stations a name selects when no rank is given, which every surface takes from here so that the
# same name gives the same stations (GH-2635). A name is fuzzy -- "Kiel" is several stations, and "Berlin-
# Tempelhof" also matches "Hof" -- so what is fetched for it is the one best match: `filter_by_name`, and
# the `values` request of the command line, the REST API and MCP. A listing (`stations`) offers the best
# few to choose from instead. Pass `rank` for another number.
DEFAULT_NAME_RANK = 1
DEFAULT_NAME_RANK_LISTING = 5

# types
# either of
# str: "daily/kl" or "daily/kl/temperature_air_mean_2m"  # noqa: ERA001
# tuple of strings: ("daily", "kl") or ("daily", "kl", "temperature_air_mean_2m"), the resolution
# also as its member, Resolution.DAILY
# Parameter: DwdObservationMetadata.daily.kl.temperature_air_mean_2m or DwdObservationMetadata["daily"]["kl"]["temperature_air_mean_2m"]  # noqa: E501, ERA001
_PARAMETER_TYPE_SINGULAR = (
    str | tuple[str | Resolution, str] | tuple[str | Resolution, str, str] | ParameterModel | DatasetModel
)
_PARAMETER_TYPE = _PARAMETER_TYPE_SINGULAR | Sequence[_PARAMETER_TYPE_SINGULAR]
_DATETIME_TYPE = str | dt.date | dt.datetime | None
# what `start` and `end` accept, for the error that refuses one
_BOUND_FORMS = (
    'a day ("2020-05-01" or a datetime.date), a month ("2020-05") or a year ("2020") is the whole span, '
    'a time ("2020-05-01T12:00", with an offset or without) or a datetime.datetime is that instant'
)
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

    # implementations of subclasses: each provider sets these as class attributes, `_values` and
    # `_history` being the classes that read the values and the station history, not instances
    metadata: ClassVar[MetadataModel]
    _values: ClassVar[type[TimeseriesValues]]
    _history: ClassVar[type[TimeseriesHistory] | None] = None
    # actual parameters
    parameters: _PARAMETER_TYPE
    start: _DATETIME_TYPE = None
    end: _DATETIME_TYPE = None
    settings: Settings | dict[str, Any] = field(default_factory=Settings)
    # The periods to read. Every provider publishes its datasets under one or more of them, so this
    # is accepted everywhere and resolved in __post_init__ to the set actually served -- see
    # `_resolve_periods`. A dataset published under a single period has nothing to choose between;
    # asking for another one is an error rather than a silently widened request.
    periods: _PERIODS_TYPE = None
    # How the values come back and how the stations are chosen, as opposed to `settings`, which is
    # the host's. None takes the options of the environment; a dict is taken as the options it names.
    # Resolved in __post_init__ to an `Options`, which is read from there on.
    # Keyword-only, so that it moves none of the arguments a subclass adds after `periods` (`issue` of
    # the forecasts)
    options: Options | dict[str, Any] | None = field(default=None, kw_only=True)
    # What to do with a parameter the provider does not have or that is not shaped like one:
    # "raise" refuses the request with an `InvalidParameterError` naming each, "warn" logs them
    # and goes on with the parameters that did resolve. On the request rather than in `Options`,
    # which is about how values come back and not about how the request is read, and keyword-only
    # like it.
    on_unknown: Literal["raise", "warn"] = field(default="raise", kw_only=True)

    def __new__(cls, *args: object, **kwargs: object) -> Self:  # noqa: ARG004
        """Refuse a renamed argument before the dataclass __init__ rejects it without naming the new one.

        Here rather than in __post_init__, which an unknown keyword never reaches, and rather than
        in every provider's __init__, which the dataclass decorator generates.
        """
        refuse_renamed_arguments(cls.__name__, kwargs)
        return super().__new__(cls)

    def __post_init__(self) -> None:
        """Post init method to validate the settings and convert the timestamps."""
        if not getattr(self, "metadata", None):
            msg = f"{self.__class__.__name__}.metadata not implemented"
            raise NotImplementedError(msg)
        if not getattr(self, "_values", None):
            msg = f"{self.__class__.__name__}._values not implemented"
            raise NotImplementedError(msg)
        # Convert settings given as a dict to a validated model. A `Settings` object is used as it is:
        # one built the usual way was validated at construction and on every assignment since, and
        # validating it again would only re-run its after-validators (it once logged the cache line a
        # second time, GH-2476, GH-2504)
        if not isinstance(self.settings, Settings):
            self.settings = Settings.model_validate(self.settings)
        self.options = resolve_options(self.options)
        # Convert timestamps
        self.start, self.end = self.convert_timestamps(self.start, self.end)
        # Parse parameters
        requested = self.parameters
        if isinstance(requested, Iterator):
            # parse_parameters consumes an iterator, so keep the values for the message below,
            # which would otherwise render the exhausted iterator rather than what was asked for
            requested = cast("_PARAMETER_TYPE", list(requested))
        check_on_unknown(self.on_unknown)
        if requested:
            try:
                self.parameters = parse_parameters(requested, self.metadata, self.on_unknown)  # type: list[ParameterModel]
            except InvalidParameterError as e:
                if not e.resolved:
                    raise
                msg = f"{str(e).rstrip('.')}. Pass on_unknown='warn' to skip these and read the others."
                error = InvalidParameterError(msg)
                error.resolved = True
                raise error from None
        if not self.parameters:
            # with on_unknown="warn" the warnings parse_parameters logged say per parameter what was
            # wrong with it, but they are only visible to whoever configured logging, so name the
            # request here too
            msg = f"No valid parameters could be parsed from {requested!r} for {type(self).__name__}"
            raise NoParametersFoundError(msg)
        # Has to follow the parameters, which say which datasets -- and so which periods -- were
        # asked for, and the timestamps, which a provider may derive the periods from
        self.periods = self._resolve_periods(self.periods)

    # Columns that should be contained within any stations information
    _base_columns: ClassVar = tuple(STATIONS_SCHEMA)

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
                warn_response(
                    log,
                    "period-not-published",
                    f"Periods {_format_periods(dropped)} are not published for the datasets requested from "
                    f"{type(self).__name__} and are skipped. Available periods: {_format_periods(published)}",
                )
            if served != published and not self._selects_by_period:
                warn_response(
                    log,
                    "period-not-narrowing",
                    f"{type(self).__name__} does not read its data per period, so asking for "
                    f"{_format_periods(served)} does not narrow what is returned: every period the requested "
                    f"datasets publish ({_format_periods(published)}) is read.",
                )
            return served
        if self.start is not None:
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
    def _bound_to_window(name: str, bound: _DATETIME_TYPE) -> tuple[dt.datetime, dt.datetime] | None:
        """Read one bound as the first and the last instant it names, in UTC, or None where none was given.

        A bound that names an instant -- a `datetime`, or a string carrying a time -- names that instant
        alone, so its first and last are one. A bound that names a span and nothing finer -- a `date`, or
        a string such as ``"2026-01-31"``, ``"2026-01"`` or ``"2026"`` -- names the whole day, month or
        year, as it does as the ``timestamp`` of the REST API, the command line and MCP, through the same
        `parse_date_window` (GH-3133).
        """
        if bound is not None and not isinstance(bound, str | dt.date):
            msg = f"{name} must be a str, a date or a datetime, got {type(bound).__name__} {bound!r}; {_BOUND_FORMS}"
            raise TypeError(msg)
        if not bound:
            return None
        if isinstance(bound, dt.datetime):
            window = (bound, bound)
        elif isinstance(bound, dt.date):
            window = parse_date_window(bound.isoformat())
        else:
            try:
                window = parse_date_window(bound)
            except InvalidTimeIntervalError as e:
                msg = f"{name}={bound!r} is refused: {e}; {_BOUND_FORMS}"
                raise InvalidTimeIntervalError(msg) from e
        first, last = (
            instant.replace(tzinfo=ZoneInfo("UTC")) if not instant.tzinfo else instant.astimezone(ZoneInfo("UTC"))
            for instant in window
        )
        return first, last

    @staticmethod
    def convert_timestamps(
        start: _DATETIME_TYPE,
        end: _DATETIME_TYPE,
    ) -> tuple[None, None] | tuple[dt.datetime, dt.datetime]:
        """Convert timestamps to datetime objects in UTC.

        A naive bound is read as UTC and an aware one is converted to it, whatever its zone: a named
        zone (``ZoneInfo("Europe/Vilnius")``) or a fixed offset keeps its instant and loses its zone.
        The values are UTC, so a bound in any other zone could not be compared with them, and a
        provider that formats or floors a bound -- by its year, its date -- would do so in the
        caller's zone rather than the one the values are in.

        A bound that names a span and nothing finer is the whole span, as the ``timestamp`` of the REST API,
        the command line and MCP reads it (`parse_date_window`, GH-3133): a `datetime.date` or a string such
        as ``"2026-01-31"`` is the day, ``"2026-01"`` the month and ``"2026"`` the year. ``start`` is the
        first instant of the span and ``end`` the last, ``23:59:59.999999`` UTC, so ``end="2026-01-31"``
        includes the readings of the 31st and ``end="2026-01"`` those of the whole of January. A `datetime`,
        or a string with a time (``"2026-01-31T00:00"``), is that instant and no more.

        A bound given alone is the whole window, ``start`` as much as ``end``: an instant is a window of
        one instant (``start == end``) and a date, month or year is the whole span. It is not an open end.

        Args:
            start: Start of the request, an ISO 8601 string, a date or a datetime.
            end: End of the request, an ISO 8601 string, a date or a datetime.

        Returns:
            tuple[None, None] | tuple[dt.datetime, dt.datetime]: Start and end of the request.

        Raises:
            TypeError: a bound is neither a string, a date nor a datetime, an int such as ``2020`` among them.
            InvalidTimeIntervalError: a string is no day, month, year or time (a `ValueError`).

        """
        start_window = TimeseriesRequest._bound_to_window("start", start)
        end_window = TimeseriesRequest._bound_to_window("end", end)
        if start_window is None and end_window is None:
            return None, None

        # If only one bound is given, the window is the one it names.
        first, _ = start_window or cast("tuple[dt.datetime, dt.datetime]", end_window)
        _, last = end_window or cast("tuple[dt.datetime, dt.datetime]", start_window)

        if not first <= last:
            msg = "'start' must be smaller or equal to 'end'."
            raise ReversedTimeIntervalError(msg)

        return first, last

    @classmethod
    def is_configured(cls) -> bool:
        """Return True if this provider's required credentials are present (env var / settings).

        This is a cheap, offline check. Override in subclasses that require authentication.
        """
        return True

    @classmethod
    def is_valid(cls, settings: Settings | None = None) -> bool | None:  # noqa: ARG003
        """Tell whether the provider accepts its credentials.

        Returns True if the provider accepted them, False if it rejected them, and None if the
        probe could not tell (no network, a timeout, a rate limit, an outage): only an answer
        that says the credentials are refused makes them invalid.

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
    ) -> dict[str, CoverageResolution]:
        """Discover metadata for the given resolutions and datasets.

        Each level carries its own description, so the shape has a place for one::

            {resolution: {"description": ..., "datasets": {dataset: {"description": ...,
             "parameters": [{"name": ..., "name_original": ..., "unit_type": ..., "unit": ...,
             "description": ...}]}}}}

        `unit` is the unit the source publishes in, which is not always the unit a request answers
        with: a value is converted to its type's target unless the option `convert_units` is off, so
        `dwd/road` reports `degree_kelvin` here and answers in °C, and `millimeter_per_second` here
        and answers in mm/h. `UnitConverter.targets`, which the option `unit_targets` overrides, is the other
        side.

        Names are matched by either name of a resolution or dataset, in any case.

        Args:
            resolutions: Resolutions to discover metadata for.
            datasets: Datasets to discover metadata for.

        Returns:
            dict: Metadata for the given resolutions and datasets.

        Raises:
            MetadataNotFoundError: a resolution or dataset the network does not have, a dataset being
                looked for in the resolutions asked for.

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
            resolution_strings.append(resolution.strip())
        if not datasets:
            datasets = []
        dataset_strings = []
        for dataset in to_list(datasets):
            dataset = dataset.name if isinstance(dataset, DatasetModel) else str(dataset)
            dataset_strings.append(dataset.strip())

        def named(model: ResolutionModel | DatasetModel, names: list[str]) -> bool:
            return bool({model.name.lower(), model.name_original.lower()} & {name.lower() for name in names})

        selected = [
            resolution for resolution in cls.metadata if not resolution_strings or named(resolution, resolution_strings)
        ]
        # an empty answer would read as "nothing published" where the name is only wrong
        for name in resolution_strings:
            if not any(named(resolution, [name]) for resolution in selected):
                available = ", ".join(resolution.name for resolution in cls.metadata)
                msg = f"Resolution '{name}' not found in {cls.metadata.name}. Available resolutions: {available}"
                raise MetadataNotFoundError(msg)
        for name in dataset_strings:
            if not any(named(dataset, [name]) for resolution in selected for dataset in resolution):
                available = ", ".join(sorted({dataset.name for resolution in selected for dataset in resolution}))
                where = (
                    f"{cls.metadata.name} for resolutions {', '.join(resolution_strings)}"
                    if resolution_strings
                    else cls.metadata.name
                )
                msg = f"Dataset '{name}' not found in {where}. Available datasets: {available}"
                raise MetadataNotFoundError(msg)
        data: dict[str, CoverageResolution] = {}
        for resolution in selected:
            described_datasets: dict[str, CoverageDataset] = {}
            for dataset in resolution:
                if dataset_strings and not named(dataset, dataset_strings):
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

    @classmethod
    def _coerce_meta_fields(cls, df: pl.DataFrame) -> pl.DataFrame:
        """Coerce the station columns to the dtypes of `STATIONS_SCHEMA`."""
        return coerce(df, STATIONS_SCHEMA)

    @abstractmethod
    def _all(self) -> pl.LazyFrame:
        """Implement this method to get all stations.

        This is what a provider hands to the core for the stations, and `all()` is what the core makes of it
        (GH-2627). A row is a station of a dataset: a station that has two of the requested datasets has two rows.

        Returns:
            pl.LazyFrame: All stations, with the columns of `STATIONS_SCHEMA` (`wetterdienst.model.schema`):

            - ``resolution``, ``dataset`` (String) and ``station_id`` (String, the id the values are collected
              by): required. The values step finds a station's datasets by the first two and collects them by the
              third, and the station filters key on `station_id`.
            - ``latitude``, ``longitude``, ``elevation`` (Float64), ``name``, ``region`` (String),
              ``start_timestamp`` and ``end_timestamp`` (Datetime("us", "UTC")): may be left out, and `all()` then
              fills the column with null. A station with no position is listed, but no distance filter can reach it;
              a ``start_timestamp`` left out says nothing about when the station began, which the values step reads
              as "may have data in the window".
            - any column of the request's own `_base_columns` (the provider adds them there, as WSV does its river
              kilometre): kept. A column that `_base_columns` does not list is dropped without a message, and the
              provider tests fail for it (GH-2019).

            The core casts the columns of `STATIONS_SCHEMA` to their dtypes (strictly, so a value that cannot be
            cast raises), reading a naive datetime as UTC, and orders the columns as `_base_columns` does. A
            frame without a row, whatever its columns, is the empty stations frame.

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
            # a column of the schema has its dtype, any other the provider declared is a String as before
            df = pl.DataFrame(
                schema={column: STATIONS_SCHEMA.get(column, pl.String) for column in self._base_columns}, orient="col"
            )

        df = self._coerce_meta_fields(df)

        return StationsResult(
            request=self,
            df=df,
            _df_all=df,
            _stations_filter=StationsFilter.ALL,
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

        # an id the request has no station for leaves it out of the result, which would otherwise be
        # an empty or a shorter one with no word on why (GH-2635)
        found = set(df_station_id.get_column("station_id"))
        if unknown := [station for station in dict.fromkeys(station_id_series) if station not in found]:
            warn_response(
                log,
                "unknown-station",
                f"No station with station_id {', '.join(map(str, unknown))} for the requested parameters and "
                f"periods of {type(self).__name__}.",
            )

        return StationsResult(
            request=self,
            df=df_station_id,
            _df_all=df,
            _stations_filter=StationsFilter.BY_STATION_ID,
        )

    def filter_by_name(
        self,
        name: str,
        rank: int = DEFAULT_NAME_RANK,
        threshold: float = 0.8,
        *,
        df_all: pl.DataFrame | None = None,
    ) -> StationsResult:
        """Filter stations by name.

        Args:
            name: Name of the station.
            rank: Maximum number of stations to return (default `DEFAULT_NAME_RANK`, the best match).
                The `stations` listing of the command line and the REST API takes the best
                `DEFAULT_NAME_RANK_LISTING` (5) instead: pass `rank=5` for the same. A station is one
                match however many datasets (rows) it has, and two stations that share a name are two.
                The rows come back best match first, equal scores ordered by `station_id`.
            threshold: Threshold for the fuzzy search.
            df_all: The stations to match the name against, where not every station of the request: a
                listing that has left out those without a record in its window, so that the best
                matches are taken among the stations that remain (GH-2635). Default: all of them. The
                window of the request is not applied by this method: the command line, the REST API and
                MCP apply it to `df_all` themselves (`ui.core.limit_stations_to_window`).

        Returns:
            StationsResult: Filtered stations.

        """
        # checked before `all()` below, so a wrong type is answered without downloading the whole
        # station index first -- rapidfuzz would raise the same TypeError, one station list later
        if not isinstance(name, str):
            msg = "'name' has to be a string."
            raise TypeError(msg)

        rank = int(rank)
        if rank <= 0:
            msg = "'rank' has to be at least 1."
            raise ValueError(msg)

        threshold = float(threshold)
        if threshold < 0 or threshold > 1:
            msg = "threshold must be between 0.0 and 1.0"
            raise ValueError(msg)

        if df_all is None:
            df_all = self.all().df

        # WRatio (rapidfuzz's weighted composite of ratio/partial/token-sort/token-set with
        # length-ratio guards) so a short place query matches longer station names: "Kiel" ->
        # "Kiel-Holtenau"/"Kiel-Kronshagen". The previous token_sort_ratio scored by full-string
        # similarity and thus penalised the length gap ("Kiel" vs "Kiel-Holtenau" ~47%), so a bare
        # city name fell below the threshold and returned nothing.
        #
        # The unit of `rank` is the station, not the row: a station has a row for every dataset asked
        # for, and several stations may share a name. So the names are scored per station (once for
        # each name a station goes by), the best `rank` stations are taken, and their rows come back
        # best match first. Equal scores -- common, as WRatio tops out at 100 for any name that holds
        # the query -- are ordered by station_id, which does not depend on how the provider sorts its
        # list. (GH-3025)
        candidates = (
            df_all.select("station_id", "name").unique(maintain_order=True).sort("station_id", maintain_order=True)
        )
        matches = process.extract(
            query=name,
            choices=candidates.get_column("name"),
            scorer=fuzz.WRatio,
            score_cutoff=threshold * 100,
            processor=fuzz_utils.default_process,
            limit=None,
        )
        station_ids = candidates.get_column("station_id")
        selected = list(
            dict.fromkeys(
                station_ids[index] for _, _, index in sorted(matches, key=lambda match: (-match[1], match[2]))
            )
        )[:rank]

        if selected:
            position = pl.DataFrame({"station_id": selected, "_match": range(len(selected))})
            df = (
                df_all.join(position, on="station_id", how="inner", maintain_order="left")
                .sort("_match", maintain_order=True)
                .drop("_match")
            )
        else:
            df = pl.DataFrame(schema=df_all.schema)

        if df.is_empty():
            log.info(f"No weather stations were found for name {name}")

        return StationsResult(
            request=self,
            df=df,
            _df_all=df_all,
            _stations_filter=StationsFilter.BY_NAME,
            _rank=rank,
        )

    def filter_by_rank(
        self,
        latlon: tuple[float, float],
        rank: int,
        *,
        df_all: pl.DataFrame | None = None,
    ) -> StationsResult:
        """Filter stations by rank.

        Rank is defined by distance to the requested point. The resulting
        ``StationsResult.df`` holds **all** stations with a position sorted by
        distance, not just ``rank`` rows; a station without a latitude or longitude
        has no distance and is left out. Because we cannot know upfront which
        stations actually carry data for the request, the ``rank`` limit is applied
        lazily while collecting values. Value collection walks the distance-sorted
        stations and stops once ``rank`` stations that returned anything have been
        consumed. The stations that ended up contributing values are then exposed via
        ``ValuesResult.df_stations``.

        In other words, use ``stations.values().all().df_stations`` (not
        ``stations.df``) to see the ``rank`` closest stations that actually returned
        data. Enable the option ``skip_empty`` to walk past a station that returned data but
        too little of it, as ``skip_threshold`` and ``skip_criteria`` define.

        Args:
            latlon: Latitude and longitude for the requested point.
            rank: Number of stations requested.
            df_all: This request's own ``all().df``, for a caller that has it already; built here
                where left out.

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
        if df_all is None:
            df_all = self.all().df
        latitudes = df_all.get_column("latitude").to_arrow()
        longitudes = df_all.get_column("longitude").to_arrow()
        distances = derive_nearest_neighbours(
            latitudes=latitudes,
            longitudes=longitudes,
            q_lat=q_lat,
            q_lon=q_lon,
        )
        # add distances and sort by distance. A station without a position has none, and a null
        # sorts first, ahead of the nearest station: it is left out, as `filter_by_distance` and
        # `filter_by_bbox` leave it out (GH-2380)
        df = df_all.with_columns(pl.lit(pl.Series(distances, dtype=pl.Float64)).alias("distance"))
        located = df.filter(pl.col("distance").is_not_null()).sort(by=["distance", "station_id"])
        if located.is_empty() and not df.is_empty():
            log.info("None of the stations has a position to be ranked by")
        df = located
        return StationsResult(
            request=self,
            df=df,
            _df_all=df_all,
            _stations_filter=StationsFilter.BY_RANK,
            _rank=rank,
        )

    def filter_by_distance(
        self,
        latlon: tuple[float, float],
        distance: float,
        unit: str = "km",
        *,
        df_all: pl.DataFrame | None = None,
    ) -> StationsResult:
        """Filter stations by distance.

        Args:
            latlon: Latitude and longitude for the requested point.
            distance: Maximum distance to the requested point.
            unit: Unit of the distance.
            df_all: This request's own ``all().df``, for a caller that has it already; built here
                where left out.

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

        # the rank only limits value collection later on: `df` holds every located station whatever
        # it is, so asking for one spares building the station index again just to count it
        ranked = self.filter_by_rank(latlon, rank=1, df_all=df_all)

        df = ranked.df.filter(pl.col("distance").le(distance_in_km))

        if df.is_empty():
            log.info("No weather stations were found for the provided coordinates")

        return StationsResult(
            request=self,
            df=df,
            _df_all=ranked._df_all,  # noqa: SLF001
            _stations_filter=StationsFilter.BY_DISTANCE,
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
            raise InvalidBoundingBoxError(msg)

        if bottom >= top:
            msg = "bbox bottom border should be smaller then top"
            raise InvalidBoundingBoxError(msg)

        df_all = self.all().df

        df = df_all.filter(
            pl.col("latitude").is_between(bottom, top, closed="both")
            & pl.col("longitude").is_between(left, right, closed="both"),
        )

        if df.is_empty():
            log.info(f"No weather stations were found for bbox {left}/{bottom}/{top}/{right}")

        return StationsResult(request=self, df=df, _df_all=df_all, _stations_filter=StationsFilter.BY_BBOX)

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
        return StationsResult(request=self, df=df, _df_all=df_all, _stations_filter=StationsFilter.BY_SQL)

    def interpolate(self, latlon: tuple[float, float], elevation: float | None = None) -> InterpolatedValuesResult:
        """Interpolate values across multiple stations.

        Interpolation means we interpolate the values of the closest available stations to the requested point.

        Args:
            latlon: Latitude and longitude for the requested point.
            elevation: Elevation of the requested point in metres above sea level. Given, the quantities that fall with
                elevation -- air temperature, dew point -- are brought from each station's altitude to
                this one before being interpolated, which is what tells a valley reading from a
                summit one. Left out, the readings are interpolated as they come.

        Returns:
            InterpolatedValuesResult: Interpolated values.

        Raises:
            NoStationsWithElevationError: Where an elevation is asked about and leaving out the
                stations whose elevation the provider does not report leaves nothing that can answer
                it. A few providers report no elevation for any station.

        """
        return self._interpolate(latlon, elevation)

    def _interpolate(
        self,
        latlon: tuple[float, float],
        elevation: float | None,
        *,
        df_all: pl.DataFrame | None = None,
    ) -> InterpolatedValuesResult:
        """Do `interpolate` with the station list `all()` gave, where the caller has it already.

        The core ranks the stations near the point and the result names the stations taken, both off
        this one frame, so that the provider builds its station list once.
        """
        # scipy, shapely and utm are imported by the module, so a missing one surfaces from this
        interpolate = import_optional("wetterdienst.core.interpolate", "Interpolation", extra="interpolation")
        get_interpolated_df, place_in_utm = interpolate.get_interpolated_df, interpolate.place_in_utm

        if not self.start:
            msg = "start and end are required for interpolation"
            raise MissingTimeIntervalError(msg)

        resolutions = {
            parameter.dataset.resolution.value for parameter in self.parameters if isinstance(parameter, ParameterModel)
        }

        if resolutions.intersection(
            {Resolution.MINUTE_1, Resolution.MINUTE_5, Resolution.MINUTE_6, Resolution.MINUTE_10}
        ):
            log.warning("Interpolation might be slow for high resolutions due to mass of data")

        lat, lon = latlon
        lat, lon = float(lat), float(lon)
        # a point UTM cannot place is refused before the station list is built, as the core does
        place_in_utm(lat, lon)
        if df_all is None:
            df_all = self.all().df
        df_interpolated = self._as_asked(
            get_interpolated_df(self._for_estimating(), lat, lon, elevation, df_all=df_all)
        )
        # the elevation belongs in the name: two elevations at one point are two different
        # answers, and sharing an id would merge them wherever the id is what identifies a series
        point = (
            f"interpolation({lat:.4f},{lon:.4f})"
            if elevation is None
            else f"interpolation({lat:.4f},{lon:.4f},{elevation:.1f}m)"
        )
        station_id = create_station_id_from_string(point)
        df_interpolated = coerce(
            df_interpolated.select(
                pl.lit(station_id).alias("station_id"),
                *(pl.col(column) for column in INTERPOLATED_SCHEMA if column != "station_id"),
            ),
            INTERPOLATED_SCHEMA,
        )
        df_stations = df_all.join(
            other=df_interpolated.select(pl.col("taken_station_ids").alias("station_id"))
            .explode("station_id", empty_as_null=True)
            .unique(),
            on="station_id",
        )
        stations_result = StationsResult(
            request=self,
            df=df_stations,
            _df_all=df_all,
            _stations_filter=StationsFilter.BY_STATION_ID,
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
        names its elevation as well, and it is the one case where an interpolation knows the elevation
        of its target without being told. For the reading uncorrected, pass the station's
        coordinates to `interpolate` instead.

        Raises:
            NoStationsWithElevationError: Where leaving out the stations of unknown elevation leaves
                nothing that can answer at this station's altitude. There is no elevation to omit
                here, so the reading as it came is asked for by coordinates: pass the station's
                own to `interpolate`.
            LocationOutOfRangeError: Where the station has no position, such as a NOAA GHCN hourly
                station listed at 0.0, 0.0 or named BOGUS.

        """
        df_all = self.all().df
        latitude, longitude, station_elevation = self._get_position_by_station_id(station_id, df_all=df_all)
        return self._interpolate(
            (latitude, longitude),
            elevation if elevation is not None else station_elevation,
            df_all=df_all,
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

        Raises:
            NoStationsWithElevationError: Where an elevation is asked about and leaving out the
                stations whose elevation the provider does not report leaves nothing that can answer
                it. A few providers report no elevation for any station.

        """
        return self._summarize(latlon, elevation)

    def _summarize(
        self,
        latlon: tuple[float, float],
        elevation: float | None,
        *,
        df_all: pl.DataFrame | None = None,
    ) -> SummarizedValuesResult:
        """Do `summarize` with the station list `all()` gave, where the caller has it already.

        The core ranks the stations near the point and the result names the stations taken, both off
        this one frame, so that the provider builds its station list once.
        """
        from wetterdienst.core.summarize import get_summarized_df  # noqa: PLC0415

        if not self.start:
            msg = "start and end are required for summarization"
            raise MissingTimeIntervalError(msg)

        resolutions = {
            parameter.dataset.resolution.value for parameter in self.parameters if isinstance(parameter, ParameterModel)
        }

        if resolutions.intersection(
            {Resolution.MINUTE_1, Resolution.MINUTE_5, Resolution.MINUTE_6, Resolution.MINUTE_10}
        ):
            log.warning("Summary might be slow for high resolutions due to mass of data")

        lat, lon = latlon
        lat, lon = float(lat), float(lon)
        if df_all is None:
            df_all = self.all().df
        summarized_values = self._as_asked(
            get_summarized_df(self._for_estimating(), lat, lon, elevation, df_all=df_all)
        )
        # the elevation belongs in the name: two elevations at one point are two different
        # answers, and sharing an id would merge them wherever the id is what identifies a series
        point = (
            f"summary({lat:.4f},{lon:.4f})" if elevation is None else f"summary({lat:.4f},{lon:.4f},{elevation:.1f}m)"
        )
        station_id = create_station_id_from_string(point)
        summarized_values = coerce(
            summarized_values.select(
                pl.lit(station_id).alias("station_id"),
                *(pl.col(column) for column in SUMMARIZED_SCHEMA if column != "station_id"),
            ),
            SUMMARIZED_SCHEMA,
        )
        df_stations = df_all.join(
            other=summarized_values.select(pl.col("taken_station_id")).unique(),
            left_on="station_id",
            right_on="taken_station_id",
        )
        stations_result = StationsResult(
            request=self,
            df=df_stations,
            _df_all=df_all,
            _stations_filter=StationsFilter.BY_STATION_ID,
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

        Raises:
            NoStationsWithElevationError: Where leaving out the stations of unknown elevation leaves
                nothing that can answer at this station's altitude. There is no elevation to omit
                here, so the reading as it came is asked for by coordinates: pass the station's
                own to `summarize`.
            LocationOutOfRangeError: Where the station has no position, as `interpolate_by_station_id`
                says.

        """
        df_all = self.all().df
        latitude, longitude, station_elevation = self._get_position_by_station_id(station_id, df_all=df_all)
        return self._summarize(
            (latitude, longitude),
            elevation if elevation is not None else station_elevation,
            df_all=df_all,
        )

    def _for_estimating(self) -> TimeseriesRequest:
        """Give the request `interpolate` and `summarize` read the stations' values through.

        Both read a long frame named by canonical parameter: they pick a parameter's rows by its
        canonical name and take the `value` column. A caller's `humanize=False` left them
        matching no row at all, and `shape="wide"` has no `value` column (GH-2331). So the
        values are read as long and humanized whatever the caller's options say, on a copy, so
        that the caller's own request keeps them. `_as_asked` names the result the caller's way.
        The copy drops nulls as the caller's options do, which a wide shape does not.
        """
        options = cast("Options", self.options)
        if options.shape == "long" and options.humanize:
            return self
        request = copy.copy(self)
        request.options = options.replace(shape="long", humanize=True, drop_nulls=options.drop_nulls_effective)
        return request

    def _as_asked(self, df: pl.DataFrame) -> pl.DataFrame:
        """Name an interpolated or summarized frame's parameters as the caller's `humanize` does.

        The frame comes back long whatever `shape` says: one estimate per row, with the distance
        and the stations it was drawn from beside it, has no wide form.
        """
        if cast("Options", self.options).humanize:
            return df
        name = pl.col("parameter")
        for parameter in self.parameters:
            if not isinstance(parameter, ParameterModel):
                continue
            name = (
                pl.when(
                    pl.col("resolution").eq(parameter.dataset.resolution.name),
                    pl.col("dataset").eq(parameter.dataset.name),
                    pl.col("parameter").eq(parameter.name),
                )
                .then(pl.lit(parameter.name_original))
                .otherwise(name)
            )
        # sorted again, as the cores sorted by the canonical names: `tmk` is `values`' first under
        # `humanize=False` and came last here, behind `txk` (`temperature_air_max_2m`)
        return df.with_columns(name.alias("parameter")).sort(["resolution", "dataset", "parameter", "timestamp"])

    def _get_latlon_by_station_id(self, station_id: str) -> tuple[float, float]:
        """Get latlon for a station_id.

        Used for .summary/.interpolate. Typically, we expect a latlon tuple of floats, but
        we want users to be able to request for a station id as well.
        """
        latitude, longitude, _ = self._get_position_by_station_id(station_id)
        return latitude, longitude

    def _get_position_by_station_id(
        self,
        station_id: str,
        *,
        df_all: pl.DataFrame | None = None,
    ) -> tuple[float, float, float | None]:
        """Get the coordinates and the elevation of a station.

        The elevation comes along because naming a point by a station names its altitude too, which
        is otherwise the one thing an interpolation cannot know about its target. It is null for
        the providers that do not report one.

        A station requested at several resolutions has a row in each one's station list, and the
        lists can disagree: NOAA GHCN's hourly list gives no elevation for hundreds of the stations
        its daily list does. The coordinates are the first row's that has both, and the elevation
        the first one known across those rows, so whether either is known does not depend on which
        resolution the parameters named first.

        Raises:
            StationNotFoundError: Where the station is not listed.
            LocationOutOfRangeError: Where no row of the station gives both a latitude and a longitude.

        """
        station_id = self._parse_station_id(pl.Series(values=to_list(station_id)))[0]
        if df_all is None:
            df_all = self.all().df
        stations = df_all.filter(pl.col("station_id").eq(station_id))
        if stations.is_empty():
            msg = f"no station found for {station_id}"
            raise StationNotFoundError(msg)
        located = pl.col("latitude").is_not_null() & pl.col("longitude").is_not_null()
        lat, lon, elevation = stations.select(
            pl.col("latitude").filter(located).first(),
            pl.col("longitude").filter(located).first(),
            pl.col("elevation").drop_nulls().first(),
        ).row(0)
        if lat is None or lon is None:
            # a postcode of DWD derived's climate_correction_factor, or a NOAA GHCN hourly station
            # listed at 0.0, 0.0 or named BOGUS (GH-2380): there is no point to estimate at
            msg = f"station {station_id} has no position to interpolate or summarize at"
            raise LocationOutOfRangeError(msg)
        return lat, lon, elevation


# inspect, and with it help() and IPython, read a class's arguments off its __new__ where the class
# defines one beside its __init__, and the variadic refusal above names none: point it at the
# arguments __init__ takes, which a direct subclass that is no dataclass of its own inherits as they
# are
# (`__wrapped__` is no attribute a function is declared to have, which is how `inspect` looks it up)
TimeseriesRequest.__new__.__wrapped__ = TimeseriesRequest.__init__  # ty: ignore[unresolved-attribute]
