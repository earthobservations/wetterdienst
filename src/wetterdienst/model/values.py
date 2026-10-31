# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Core for sources of timeseries where data is related to a station."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Generic, Literal, cast

import polars as pl
from tqdm import tqdm
from typing_extensions import TypeVar

from wetterdienst.exceptions import ProviderContractError
from wetterdienst.metadata.resolution import count_readings, reading_interval
from wetterdienst.model.fetch_ahead import FetchAhead, FilesAhead
from wetterdienst.model.metadata import group_parameters_by_dataset
from wetterdienst.model.parameter_rows import ParameterRows
from wetterdienst.model.plausibility import applying, leave_out_suspect
from wetterdienst.model.quality_flags import QUALITY_FLAGS, RAW_TOKEN
from wetterdienst.model.request import require_window
from wetterdienst.model.result import StationsFilter, StationsResult, ValuesResult
from wetterdienst.model.schema import (
    LONG_SCHEMA,
    WIDE_FLAGS_DTYPE,
    WIDE_FLAGS_SUFFIX,
    WIDE_VALUE_DTYPE,
)
from wetterdienst.model.unit import UnitConverter
from wetterdienst.util.datetime import is_plausible_update, newest
from wetterdienst.util.logging import TqdmToLogger
from wetterdienst.util.response_warnings import (
    MISSING_VALUE_MARKER,
    MISSING_VALUE_MARKER_MESSAGE,
    count_response_warning,
    warn_response,
)
from wetterdienst.util.url import redact_password

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Callable, Iterable, Iterator, Sequence

    from wetterdienst.model.metadata import DatasetModel, ParameterModel

log = logging.getLogger(__name__)

# What a provider collects its values by: a provider that reads one dataset at a time takes a
# `DatasetModel` (and sets `grouped` on its datasets), one that reads one parameter at a time a
# `ParameterModel`, and one that does both leaves it unspecified. That is also what a bare
# `TimeseriesValues` in an annotation means (the default), so a result that holds one of any provider's
# does not ask for a type argument.
_UnitT = TypeVar("_UnitT", bound="ParameterModel | DatasetModel", default=Any)

# The columns of a provider's frame that the core cannot make up. A frame without one cannot be made to fit.
#: the column a provider whose source dates its files hands its rows over with, the date of the file of each row
UPDATED = "updated"
_REQUIRED_COLUMNS = ("parameter", "timestamp", "value")


def merge_duplicate_readings(df: pl.DataFrame, subset: Sequence[str]) -> pl.DataFrame:
    """Make one row of the rows that share a reading, each column taking its first non-null value (GH-3450).

    Rows are one reading when they agree on ``subset`` (for the long form: ``station_id``, ``resolution``, ``dataset``,
    ``parameter`` and ``timestamp``). Which row of them is kept is the first, in the order the frame has them, that has
    a ``value``: a row without one that comes first no longer takes the reading with it, as it did when the first row
    was kept whatever it held. Where every row is null the first row is kept, and where two rows have different values
    the first of them wins; one debug line says how many readings had such a conflict. A ``value`` that is still a
    text (a provider's frame before the core shapes it) has a value where the core reads a finite number from it, as
    `shape_provider_frame` does: ``""`` and ``"n/a"`` are none.

    The row is kept as it is, the other columns with it: ``quality_flags`` (and any other column) is the one of the row
    the value is of, so a value never carries the flag of another row. A reading whose rows are all null keeps the
    columns of its first row, ``raw:`` token and all. Nothing else changes: the rows keep the order of their first
    appearance, the columns and the dtypes stay, and a frame without a duplicate is handed back as it is.

    Args:
        df: a frame with the column ``value`` (and, by ``subset``, the columns that identify a reading).
        subset: the columns whose values identify a reading.

    Returns:
        The frame with one row per reading.

    """
    keys = list(subset)
    if df.height < 2:
        return df
    duplicated = df.select(keys).is_duplicated()
    if not duplicated.any():
        return df
    # only the readings that have several rows are grouped: the rest, nearly all of a large frame, pass untouched.
    # The helper columns are named so that no column of the frame has their name
    position = _unused_name("row", df.columns)
    conflicts = _unused_name("conflict", df.columns)
    indexed = df.with_row_index(position)
    others = [column for column in df.columns if column not in keys]
    number = pl.col("value")
    if df.schema["value"] == pl.String:
        read = pl.col("value").str.strip_chars().cast(pl.Float64, strict=False)
        number = pl.when(read.is_finite()).then(read)
    # the first row with a value, or the first row where none has one (`arg_max` of a boolean breaks a tie by no rule)
    first_with_value = pl.int_range(pl.len()).filter(number.is_not_null()).first().fill_null(0)
    merged = (
        indexed.filter(duplicated)
        .group_by(keys, maintain_order=True)
        .agg(
            pl.col(position).first(),
            pl.col(others).get(first_with_value),
            (number.drop_nulls().n_unique() > 1).alias(conflicts),
        )
    )
    log.debug(
        "%d rows share a reading with another and make %d readings, %d with different values (the first is kept)",
        int(duplicated.sum()),
        merged.height,
        int(merged.get_column(conflicts).sum()),
    )
    return pl.concat([indexed.filter(~duplicated), merged.select(indexed.columns)]).sort(position).select(df.columns)


def _unused_name(name: str, columns: Sequence[str]) -> str:
    """Give ``name``, with underscores in front until no column of ``columns`` has it."""
    while name in columns:
        name = f"_{name}"
    return name


def _can_be_cast(column: str, dtype: pl.DataType) -> bool:
    """Tell whether the core can make a column of this type the dtype the long form declares for it.

    The cast would do more than it should for some types (an integer is a count of microseconds to a datetime, a
    struct "casts" to a struct), so what is accepted is listed: a point in time for ``timestamp``, a number or a text
    for ``value``, a text, a category or a number for the names and flags.
    """
    base = dtype.base_type()
    if column == "timestamp":
        return base in {pl.Datetime, pl.Date}
    if column == "value":
        return dtype.is_numeric() or base in {pl.String, pl.Null}
    return base in {pl.String, pl.Categorical, pl.Enum, pl.Null} or dtype.is_integer()


def _check_provider_columns(df: pl.DataFrame, provider: str) -> None:
    """Raise `ProviderContractError` for a frame that lacks a required column or has one that cannot be cast."""
    missing = [column for column in _REQUIRED_COLUMNS if column not in df.columns]
    if missing:
        message = (
            f"{provider} returned a frame without the column(s) {', '.join(missing)}; its columns are {df.columns}"
        )
        raise ProviderContractError(message)
    for column in ("parameter", "timestamp", "value", "quality_flags"):
        if column in df.columns and not _can_be_cast(column, df.schema[column]):
            message = (
                f"{provider} returned `{column}` as {df.schema[column]}, which cannot be made {LONG_SCHEMA[column]}"
            )
            raise ProviderContractError(message)


def shape_provider_frame(
    df: pl.DataFrame,
    *,
    station_id: str,
    dataset: DatasetModel,
    provider: str = "the provider",
) -> pl.DataFrame:
    """Make the frame a provider handed the core the long form: its columns, their order and their dtypes (GH-2627).

    Done once here so that a provider need not: the core writes ``station_id``, ``resolution`` and ``dataset``
    (whatever the provider put there is replaced), casts ``parameter`` to String, ``timestamp`` to
    ``Datetime("us", "UTC")`` and ``value`` to Float64, fills ``quality_flags`` with a String null where the
    provider left it out, writes a ``parameter`` in another casing than the metadata's as the metadata declares it
    (GH-3595), orders the columns as `LONG_SCHEMA` does and drops any other. A frame that is the long form already
    comes out unchanged, unless its ``parameter`` is in another casing than the metadata's.

    A frame without a row is no data and is the same answer whatever it holds: a station without data for the
    parameter may be handed over as a bare ``pl.DataFrame()``, as a frame with the columns and none of the rows, or
    with columns of ``Null`` dtype (what polars makes of an empty list). All of them come out as the empty frame of
    `LONG_SCHEMA`, so that nothing downstream has to ask which empty frame it got, and no columns are required of it.

    A ``value`` cell that is no number (a text such as ``"n/a"``) is no error: it becomes null, and one debug line per
    frame says how many did. A naive ``timestamp`` is read as UTC, a zoned one is converted to it.

    Args:
        df: the frame of one call of ``_collect_station_parameter_or_dataset``, with or without rows.
        station_id: the station the call was made for.
        dataset: the dataset the call was made for, which names ``resolution`` and ``dataset``.
        provider: the name to put in a message, the provider's class.

    Returns:
        The frame with exactly the columns of `LONG_SCHEMA`, in its order and with its dtypes; with no row, the empty
        frame of `LONG_SCHEMA`.

    Raises:
        ProviderContractError: ``parameter``, ``timestamp`` or ``value`` is missing, or has a type that cannot be made
            the declared one (a ``timestamp`` that is a string or an integer, a ``value`` that is a list). A frame
            without a row is never one.

    """
    if df.is_empty():
        return pl.DataFrame(schema=LONG_SCHEMA)
    _check_provider_columns(df, provider)
    value = _value_as_number(df, provider)
    surplus = [column for column in df.columns if column not in LONG_SCHEMA]
    if surplus:
        log.debug("%s: dropped the column(s) %s, which the long form does not have", provider, ", ".join(surplus))
    identity = {
        "station_id": station_id,
        "resolution": dataset.resolution.name,
        "dataset": dataset.name.lower(),
    }
    declared = _declared_parameter_names(df, dataset)
    columns = []
    for column, dtype in LONG_SCHEMA.items():
        if column in identity:
            columns.append(pl.lit(identity[column], dtype=dtype).alias(column))
        elif column == "value":
            columns.append(value.alias(column))
        elif column == "parameter" and declared:
            columns.append(pl.col(column).cast(dtype).replace(declared))
        elif column in df.columns:
            columns.append(pl.col(column).cast(dtype, strict=column != "value"))
        else:
            # a column the provider did not deliver is a typed null: an untyped one would not concatenate with the
            # String column of the providers that do deliver it
            columns.append(pl.lit(None, dtype=dtype).alias(column))
    return df.select(columns)


def _declared_parameter_names(df: pl.DataFrame, dataset: DatasetModel) -> dict[str, str]:
    """Give the names a provider wrote in its own casing, each with the name the metadata declares (GH-3595).

    The names are matched exactly where the frame is filtered to the parameters asked for (a grouped dataset), where
    the answer is humanized and where `_note_files_with_rows` keeps the rows that date it, and case-insensitively where
    the units are converted and the share of readings is measured, so a name in another casing than the metadata's
    would be dropped, or kept under the source's spelling. Written as declared before any of them, they see one name.

    A name that matches no parameter in any casing is left as the provider wrote it: a grouped dataset's filter drops
    it, and a non-grouped call's unit conversion refuses it (when units are converted). So is a name that two different
    declared names match alike (`Ab` and `aB` declared, `AB` emitted): only the lower-cased names that occur more than
    once are left out, the rest are mapped. A name declared twice is one name.
    """
    declared = {parameter.name_original for parameter in dataset}
    lowered = [name.lower() for name in declared]
    by_lower = {name.lower(): name for name in declared if lowered.count(name.lower()) == 1}
    emitted = df.get_column("parameter").cast(pl.String).unique().drop_nulls().to_list()
    return {name: by_lower[name.lower()] for name in emitted if name not in declared and name.lower() in by_lower}


def _value_as_number(df: pl.DataFrame, provider: str) -> pl.Expr:
    """Give the expression that reads the ``value`` of a provider's frame as a number, logging the cells that are none.

    A text is read as the number it writes, padding aside, and one that writes none is null, ``nan`` and ``inf`` too,
    which a cast would take for numbers (GH-3222): counted in one debug line, never named. A blank cell is no reading
    and is not counted.
    """
    dtype = df.schema["value"]
    if dtype == pl.String:
        cell = pl.col("value").str.strip_chars()
        number = cell.cast(pl.Float64, strict=False)
        value = pl.when(number.is_nan() | number.is_infinite()).then(None).otherwise(number)
        unreadable = df.select(((cell.str.len_chars() > 0) & value.is_null()).sum()).item()
    else:
        value = pl.col("value").cast(pl.Float64, strict=False)
        unreadable = 0 if dtype == pl.Float64 else df.select(value.null_count()).item() - df["value"].null_count()
    if unreadable:
        log.debug("%s: %d of %d value cells are no number and are null", provider, unreadable, df.height)
    return value


@dataclass
class TimeseriesValues(ABC, Generic[_UnitT]):
    """Core for sources of timeseries where data is related to a station.

    Subscript it with the model the provider collects by -- `TimeseriesValues[DatasetModel]` -- so that
    `_collect_station_parameter_or_dataset` is declared as the narrow signature the provider implements.
    """

    sr: StationsResult
    unit_converter: UnitConverter = field(default_factory=UnitConverter)
    #: the dates a provider noted while it collected the station in hand (`_note_data_updated`)
    _data_updated: list[dt.datetime] = field(default_factory=list, init=False, repr=False, compare=False)
    #: whether `query` may have the files of the next stations fetched while one is read (GH-3454); a caller that stops
    #: the walk where the data says, not at a number it knows (interpolation, summary), sets it False
    _fetch_ahead_allowed: bool = field(default=True, init=False, repr=False, compare=False)
    #: whether the `missing-value-marker` warning counts the readings of the stations this reads (GH-3554); a caller
    #: whose answer is an estimate of them (interpolation, summary) and not their readings sets it False
    _count_missing_value_markers: bool = field(default=True, init=False, repr=False, compare=False)
    #: the readings of the window that the source marked as missing, in the station in hand: counted by
    #: `_process_dataset`, told by `_query_stations` once the station is not left out (GH-3554)
    _markers_in_window: int = field(default=0, init=False, repr=False, compare=False)
    #: under `skip_empty` with the nulls dropped, the `resolution, dataset, parameter` of the readings in the window
    #: before `drop_nulls` took the nulls out (null or not), in the station in hand: the rows the station has with the
    #: nulls kept, which tell `station-skipped` of a station they empty just the same (GH-3567)
    _window_parameters: list[pl.DataFrame] = field(default_factory=list, init=False, repr=False, compare=False)
    #: under `skip_empty`, the span of the readings in the window per `resolution, dataset` (`first`, `last`) before
    #: `drop_nulls` took the nulls out, in the station in hand: the series `_get_actual_percentage` measures a request
    #: without a window against, which is the same with the nulls dropped as with them kept (GH-3578)
    _window_spans: list[pl.DataFrame] = field(default_factory=list, init=False, repr=False, compare=False)
    #: under `skip_empty`, the number of readings in the window per `resolution, dataset, parameter` (`rows`) before
    #: `drop_nulls` took the nulls out, in the station in hand: what `_get_actual_percentage` divides by where the
    #: resolution has no grid to count against, the same with the nulls dropped as with them kept (GH-3578)
    _window_rows: list[pl.DataFrame] = field(default_factory=list, init=False, repr=False, compare=False)
    #: whether `query` tells, at the end of the walk, the parameters of the request that no station had a row of
    #: (`parameter-without-rows`, GH-3539); a caller that reads stations only to estimate between them (interpolation,
    #: summary) sets it False, as a station without a parameter is what it expects there; the stations whose file the
    #: provider let go (`file-skipped`, GH-3552) are told by the same walk and so are left out there too
    _warn_without_rows: bool = field(default=True, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Post-initialization of the TimeseriesValues object."""
        self.unit_converter.update_targets(self.sr.options.unit_targets)
        # before the first station is read: a window-less request for such a dataset used to answer an empty frame
        require_window(self.sr.parameters, self.sr.start, self.sr.end)

    @classmethod
    def from_stations(cls, stations: StationsResult) -> TimeseriesValues:
        """Create a new instance of the class from a StationsResult object."""
        return cls(stations)

    def _note_data_updated(self, updated: dt.datetime | None) -> None:
        """Note the date the source states for data this station's frame is made from (GH-2567).

        For a provider whose source says when what it serves was last updated, called with each such date it reads:
        the result of the station carries the newest one, as `data_updated_at`. A date the source does not state is
        not made up, and not noting any leaves the result's null, so a provider that has none does nothing. A date that
        is no plausible one (`is_plausible_update`: before 1990, or later than a day from now) is not noted, whatever
        the source of it is: the answer is not dated by a mistake.
        """
        if updated is not None and is_plausible_update(updated):
            self._data_updated.append(updated)

    def _convert_units(self, df: pl.DataFrame, dataset: DatasetModel) -> pl.DataFrame:
        """Convert values to metric units with help of conversion factors."""
        if df.is_empty():
            return df

        # create lambdas here because not every parameter exists in DataFrame
        # and we can just use the name of the parameter to get the conversion factor
        # without going back to the dataset model
        conversions = self._create_conversions(dataset)

        data = []
        for (parameter,), df_group in df.group_by(
            ["parameter"],
            maintain_order=True,
        ):
            if parameter.lower() not in conversions:
                message = (
                    f"{type(self).__name__} returned the parameter {parameter!r}, which the dataset "
                    f"{dataset.resolution.name}/{dataset.name} does not declare in any casing"
                )
                raise ProviderContractError(message)
            lambda_, decimals = conversions[parameter.lower()]
            # rounded to avoid long floats, by as many decimals as the target unit needs to keep the
            # reading's precision -- see `UnitConverter.decimals`. The conversions are plain arithmetic, so
            # the column goes through them as an expression, as the Float64 the long form declares; named
            # again because `9 / 5 * x` is named after its leftmost operand, the literal
            df_group = df_group.with_columns(
                lambda_(pl.col("value").cast(pl.Float64)).round(decimals).alias("value"),
            )
            data.append(df_group)

        return pl.concat(data)

    def _create_conversions(
        self,
        dataset: DatasetModel,
    ) -> dict[str, tuple[Callable[[Any], Any], int]]:
        """Create each parameter's conversion of a given dataset, and the decimals to round it to."""
        conversions = {}
        for parameter in dataset:
            lambda_ = self.unit_converter.get_lambda(parameter.unit, parameter.unit_type)
            target = self.unit_converter.targets[parameter.unit_type].name
            conversions[parameter.name_original.lower()] = (
                lambda_,
                self.unit_converter.decimals(parameter.unit, target),
            )
        return conversions

    def query(self) -> Iterator[ValuesResult]:
        """Query data for all stations and parameters and return a DataFrame for each station.

        For a provider that names the files of a station beforehand (`_files_ahead`) the files of the next stations
        are fetched while one is read, as many as `Settings.fetch_ahead` says (GH-3454). Nothing about the answer
        depends on it: the stations come in the same order with the same rows, and a failure is the failure of the
        station it was met at.
        """
        groups = list(self.sr.df.group_by(["station_id"], maintain_order=True))
        ahead = self._fetch_ahead(groups)
        try:
            yield from self._query_stations(groups, ahead)
        finally:
            # a consumer that stops (a closed generator, an error, a streamed answer whose client has gone) starts
            # nothing more: what is begun ends with its download, and a download never leaves a part of a file in
            # the cache
            if ahead is not None:
                ahead.close()

    def _query_stations(
        self, groups: list[tuple[Any, pl.DataFrame]], ahead: FetchAhead | None
    ) -> Iterator[ValuesResult]:
        """Walk the stations in order, each one collected, cut to the window and shaped, as `query` yields them."""
        # the stations that returned values, which `filter_by_rank` counts its slots in
        stations_collected = 0
        rows = ParameterRows(self.sr.request, self.sr.start, self.sr.end, enabled=self._warn_without_rows)
        # mapping of original to humanized parameter names is always the same
        hpm = self._create_humanized_parameters_mapping() if self.sr.options.humanize else None
        for position, ((station_id,), df_station_meta) in enumerate(groups):
            if stations_collected == self.sr._rank:  # noqa: SLF001
                break
            station_id = cast("str", station_id)
            if self._begins_after_window(df_station_meta):
                continue
            available_datasets = self._get_available_datasets(df_station_meta)
            rows.examine(station_id, available_datasets)
            self._data_updated.clear()
            self._markers_in_window = 0
            self._window_parameters.clear()
            self._window_spans.clear()
            self._window_rows.clear()
            self._advance_fetch_ahead(ahead, position, stations_collected)
            # Collect data for this station
            with rows.collecting(station_id):
                df = self._filter_by_window(self._collect_station_data(station_id, available_datasets))
            rows.note(df)
            # judged after the window has been cut, not before it: a station whose record lies
            # entirely outside the requested window returned data, but none that was asked for.
            # Counting it as collected spent one of `filter_by_rank`'s slots on an empty frame, so
            # the ranked walk stopped short of the stations that do cover the window and the
            # request came back with nothing
            if df.is_empty():
                self._leave_out_emptied(station_id, rows)
                self._pass_over(rows, station_id)
                continue
            if self.sr.options.skip_empty:
                percentage = self._get_actual_percentage(df=df, spans=self._station_spans(), rows=self._station_rows())
                if percentage < self.sr.options.skip_threshold:
                    # a parameter that holds nothing but nulls is a row the station has, with the nulls kept
                    self._note_nulls_dropped(rows)
                    self._warn_station_skipped(station_id, percentage)
                    self._pass_over(rows, station_id)
                    continue
            self._tell_missing_value_markers()
            if hpm is not None:
                df = self._humanize(df=df, humanized_parameters_mapping=hpm)
            if not self.sr.options.tidy:
                df = self._widen_df(df=df)
            # sorted by resolution first in either shape: two resolutions are two series, and
            # sorting by the dataset alone interleaves them when they share one -- an hourly and a
            # 10-minute precipitation series came out shuffled into each other. `unique()` in
            # `_widen_df` leaves the wide rows in no particular order to begin with.
            sort_columns = (
                ["resolution", "dataset", "parameter", "timestamp"]
                if self.sr.options.tidy
                else ["resolution", "dataset", "timestamp"]
            )
            df = df.sort(sort_columns)
            stations_collected += 1
            yield ValuesResult(stations=self.sr, df=df, data_updated_at=newest(self._data_updated))
        # only a walk read to its end says what it found: a failure raised before it, and one that is stopped is silent
        rows.warn(rank_filled=stations_collected == self.sr._rank)  # noqa: SLF001

    def _pass_over(self, rows: ParameterRows, station_id: str) -> None:
        """Note that a rank walk passed a candidate over (an empty frame, or one below `skip_threshold`) for the next.

        Only a rank walk replaces a station: a pick by ids, distance or name that drops one leaves the answer short of
        it, which `file-skipped` tells if its file was let go (GH-3552). Whether the replacement filled the rank is
        known at the end of the walk (`ParameterRows.warn`).
        """
        if self.sr._stations_filter == StationsFilter.BY_RANK:  # noqa: SLF001
            rows.passed_over(station_id)

    def _warn_station_skipped(self, station_id: str, percentage: float) -> None:
        """Tell that `skip_empty` leaves the station out, for a share of actual values below the threshold."""
        warn_response(
            log,
            "station-skipped",
            f"station {station_id} is skipped as percentage of actual values ({percentage}) "
            f"is below threshold ({self.sr.options.skip_threshold}).",
            level=logging.INFO,
        )

    def _leave_out_emptied(self, station_id: str, rows: ParameterRows) -> None:
        """Tell of a station with nothing left in the window: `station-skipped` if it held readings, all nulls."""
        if self._note_nulls_dropped(rows):
            # `skip_empty` leaves it out, as it does with the nulls kept
            self._warn_station_skipped(station_id, 0.0)
        self._tell_missing_value_markers(emptied=True)

    def _station_spans(self) -> pl.DataFrame | None:
        """Give the span of the station's readings in the window per dataset, before `drop_nulls`, or None for none."""
        if not self._window_spans:
            return None
        return (
            pl.concat(self._window_spans)
            .group_by("resolution", "dataset")
            .agg(pl.col("first").min(), pl.col("last").max())
        )

    def _station_rows(self) -> pl.DataFrame | None:
        """Give the readings of the station in the window per parameter, before `drop_nulls`, or None for none."""
        if not self._window_rows:
            return None
        return (
            pl.concat(self._window_rows)
            .with_columns(pl.col("parameter").str.to_lowercase())
            .group_by("resolution", "dataset", "parameter")
            .agg(pl.col("rows").sum())
        )

    def _note_nulls_dropped(self, rows: ParameterRows) -> bool:
        """Note the parameters the station has in the window before `drop_nulls`, of a station `skip_empty` leaves out.

        With the nulls kept such a station has frames of nulls, which `skip_empty` leaves out and tells so; with them
        dropped (the long shape's default) the same station has the same rows, and `parameter-without-rows` says
        nothing of their parameters, as it says nothing of them with the nulls kept (GH-3567). `_window_parameters`
        holds the parameters of every reading in the window, null or not, and is filled under `skip_empty` only. Gives
        whether the station had any reading in the window: one with none is left out unsaid, as it is with the nulls
        kept.
        """
        if not self._window_parameters:
            return False
        parameters = pl.concat(self._window_parameters)
        rows.note(parameters)
        return not parameters.is_empty()

    def _tell_missing_value_markers(self, *, emptied: bool = False) -> None:
        """Add the markers of the station in hand to the warning of the request, unless the station is left out.

        Counted by `_process_dataset` for the station and told here, once the walk has not skipped it (`skip_empty`):
        the count is of the readings of the answer, and a station that is not in it, or one that an estimate reads
        (`_count_missing_value_markers`), has none to tell (GH-3554). One sum for the request, which
        `count_response_warning` keeps.

        A station `emptied` of its frame because the nulls were dropped is told when the request names it: the markers
        are what the nulls were. Not where it would be left out all the same -- `skip_empty` skips a frame without a
        reading, as it does with the nulls kept, and a rank walk (`filter_by_rank`) walks past it. A pick by name
        takes the stations the name matches, and none takes the place of an emptied one.
        """
        if emptied and (self.sr.options.skip_empty or self.sr._stations_filter == StationsFilter.BY_RANK):  # noqa: SLF001
            return
        if self._count_missing_value_markers:
            count_response_warning(MISSING_VALUE_MARKER, self._markers_in_window, MISSING_VALUE_MARKER_MESSAGE)

    def _advance_fetch_ahead(self, ahead: FetchAhead | None, position: int, stations_collected: int) -> None:
        """Have the files of the stations after ``position`` fetched, and wait for those of ``position``."""
        if ahead is None:
            return
        rank = self.sr._rank  # noqa: SLF001
        ahead.advance(position, None if rank is None else rank - stations_collected)

    def _files_ahead(
        self,
        station_id: str,  # noqa: ARG002
        datasets: Sequence[DatasetModel],  # noqa: ARG002
    ) -> FilesAhead | None:
        """Name the files this station's collection will download, for a provider whose files are one set per station.

        Implemented by a provider to have the files of the next stations of a read fetched while one is parsed
        (GH-3454): `query` calls it for the station in hand and for those a few ahead of it, in the thread that
        consumes it, and the files are downloaded into the cache of the expiry named (`FilesAhead`) by a few threads.
        Not implemented, which is what a provider that does not have it does, the files are downloaded when the
        station is collected, one station after the other, as they always were.

        What the provider's own collection downloads afterwards does not change: it asks for the same URLs, with
        the same arguments, through `download_file` or `download_files`, and finds the files in the cache. So the
        URLs must be those it will ask for, with the same ``ttl``: a URL it does not ask for is fetched for
        nothing, and one it does ask for and this does not name is downloaded when its station is reached.

        Raising is fine: it is not heard of, and the station's own collection meets the cause at its turn. Keep it
        cheap, it is called a few times ahead of the walk in the thread of the consumer, and do not download from it
        beyond what the provider's own collection downloads anyway (a listing, which is cached): the files it names
        are fetched by the threads, and a file named by two stations is fetched once.

        Args:
            station_id: the station.
            datasets: the datasets collected for it, as `_collect_station_data` collects them.

        Returns:
            The files and the expiry they are downloaded with, or None for a station that has none.

        """
        return None

    def _fetch_ahead(self, groups: list[tuple[Any, pl.DataFrame]]) -> FetchAhead | None:
        """Make the fetch-ahead of the walk over ``groups``, None where it has nothing to do or is not allowed to."""
        if type(self)._files_ahead is TimeseriesValues._files_ahead or len(groups) < 2:  # noqa: SLF001
            return None
        settings = self.sr.settings
        # where nothing is cached nothing that is fetched ahead is found again by the provider's own download
        if not settings.fetch_ahead or settings.cache_disable or not self._fetch_ahead_allowed:
            return None

        def station(position: int) -> tuple[str, list[DatasetModel]] | None:
            (station_id,), df_station_meta = groups[position]
            if self._begins_after_window(df_station_meta):
                return None
            return cast("str", station_id), self._requested_datasets(self._get_available_datasets(df_station_meta))

        return FetchAhead(
            settings=settings,
            depth=settings.fetch_ahead,
            stations=station,
            count=len(groups),
            files_of=self._files_ahead,
        )

    def _requested_datasets(self, available_datasets: list[DatasetModel]) -> list[DatasetModel]:
        """Give the datasets `_collect_station_data` collects for a station that has these, in its order."""
        return [
            dataset
            for dataset, _ in group_parameters_by_dataset(cast("Iterable[ParameterModel]", self.sr.request.parameters))
            if dataset in available_datasets
        ]

    def _begins_after_window(self, df_station_meta: pl.DataFrame) -> bool:
        """Whether the station index already says this station started after the window ended.

        Asked of the index rather than of the data, because nothing else bounds the walk once a
        station that returns nothing inside the window no longer counts towards ``rank``: a ranked
        request for a window that predates the whole network used to stop after ``rank`` stations
        and would otherwise download every station there is to reach the same answer.

        Only this one direction is read. A ``start_timestamp`` is a historical fact and does not move,
        while an ``end_timestamp`` lags on a station that is still reporting -- the index is written
        before the day it describes is over -- so ruling a station out for having stopped too
        early would drop live stations from a request for recent data. A bound the provider did
        not publish, as the forecast networks do not, states nothing either way. That holds for
        each row: a station asked for several datasets has a row per dataset, and one that leaves
        its ``start_timestamp`` out says nothing about that dataset's data, so the station is kept even
        if another dataset begins after the window. ``min()`` skips nulls, so asking it alone let
        the published bound speak for the unpublished one.
        """
        if not self.sr.end or "start_timestamp" not in df_station_meta.columns:
            return False
        start_timestamps = df_station_meta.get_column("start_timestamp")
        if start_timestamps.null_count():
            return False
        # null-free and never empty, as `group_by` yields no empty group, so `min()` has a value
        return cast("dt.datetime", start_timestamps.min()) > self.sr.end

    def _filter_by_window(self, df: pl.DataFrame) -> pl.DataFrame:
        """Cut a station's frame down to the window the request asked for, if it named one.

        A frame with nothing in it is handed back untouched: a station that delivered no data at
        all comes back as a bare frame with no ``timestamp`` column to filter on.
        """
        if not self.sr.start or df.is_empty():
            return df
        return df.filter(
            pl.col("timestamp").is_between(
                self.sr.start,
                self.sr.end,
                closed="both",
            ),
        )

    def _window_stamp(self, df: pl.DataFrame, column: str = "timestamp") -> pl.Expr | None:
        """Give the stamps of a provider's frame as the UTC datetimes the core cuts the window on, null where it cannot.

        The stamp may be a date or a datetime, with or without a zone (none is UTC, as everywhere else); a column that
        is neither (a text) cannot be told.
        """
        if column not in df.columns:
            return None
        dtype = df.schema[column]
        if dtype != pl.Date and not isinstance(dtype, pl.Datetime):
            return None
        stamp = pl.col(column).cast(pl.Datetime("us")) if dtype == pl.Date else pl.col(column)
        if dtype == pl.Date or getattr(dtype, "time_zone", None) is None:
            stamp = stamp.dt.replace_time_zone("UTC")
        return stamp

    def _has_rows_in_window(
        self,
        df: pl.DataFrame,
        column: str = "timestamp",
        *,
        value: str | None = None,
        columns: Iterable[str] | None = None,
    ) -> bool:
        """Tell whether a provider's frame has a row inside the window of the request, as `_filter_by_window` cuts it.

        For a provider that dates its answer by the files it read (`_note_data_updated`) and cannot carry the date of a
        file with its rows (`_note_files_with_rows` does): a file counts only if rows of it are in the answer, and one
        read because its period was selected, whose rows all lie outside the window, is not. A frame with no row is
        none. Without a window every row is in, and a column that cannot be told counts every row. Where the nulls are
        dropped and the frame is long (a column `value` names), only a row with a value counts, and where it is wide
        (the `columns` that are requested), only a row with a value in one of them.
        """
        if self.sr.options.drop_nulls_effective:
            if value is not None and value in df.columns:
                df = df.filter(pl.col(value).is_not_null())
            elif columns is not None:
                present = [name for name in columns if name in df.columns]
                df = df.filter(pl.any_horizontal(pl.col(name).is_not_null() for name in present)) if present else df
        if df.is_empty():
            return False
        stamp = self._window_stamp(df, column)
        if not self.sr.start or stamp is None:
            return True
        return not df.filter(stamp.is_between(self.sr.start, self.sr.end, closed="both")).is_empty()

    def _note_written_of_periods_with_rows(
        self,
        df: pl.DataFrame,
        written: dict[int, list[dt.datetime | None]],
        dataset: DatasetModel,
        rank: str,
    ) -> None:
        """Note when the source wrote the files of each period that has a row in the answer (GH-2567).

        For a provider that reads the periods of a dataset (the recent and the historical archive) into one wide frame
        and has settled the stamps they share: `written` has the dates of the files of each period by its rank, and the
        column `rank` of `df` has the rank of the period of each row. A period dates the answer where a row of it is
        inside the window and, where the nulls are dropped, has a value in a requested parameter of the dataset. A
        value the core reads as null although the file wrote a text for it is out of sight.
        """
        requested = [
            parameter.name_original
            for parameter in self.sr.parameters
            if parameter.dataset.resolution.name == dataset.resolution.name and parameter.dataset.name == dataset.name
        ]
        for period, dates in written.items():
            if self._has_rows_in_window(df.filter(pl.col(rank) == period), columns=requested):
                for updated in dates:
                    self._note_data_updated(updated)

    def _note_files_with_rows(self, df: pl.DataFrame, dataset: DatasetModel) -> pl.DataFrame:
        """Note the date of each file that holds rows the answer keeps, and give the frame without the dates (GH-2567).

        For a provider whose source dates its files: the frame it hands over has, beside each row, the date of the file
        the row is of in the column `UPDATED` (null for a file that has none). The date of a file is the answer's "date
        of the most recent update" only for a file that has rows in the answer, or the answer would be dated by data it
        has not got. A row is kept as the core keeps it: of a requested parameter, inside the window, and, where the
        shape drops the rows without a value, with a value; of the rows of one reading the first that has a value is
        kept (the first where none has one), in the order the provider hands them over, and the other columns, the
        date of the file among them, are the ones of that row. The core cuts the frame after this one, so what it cuts
        here it would cut there. A frame whose stamp is a text cannot be cut by the window, and every row of it
        counts. A `value` that is still a text has a value where a finite number can be read from it, here as in the
        core: `""` and `"n/a"` are none, though the rows without a value that are dropped after this are judged by
        `is_not_null`, so a file whose only rows hold such a text still counts.
        """
        requested = {
            parameter.name_original
            for parameter in self.sr.parameters
            if parameter.dataset.resolution.name == dataset.resolution.name and parameter.dataset.name == dataset.name
        }
        # the core makes one row of the rows of one reading (a period overlap, a file that is read twice), the first one
        # with a value, and then drops the rows without a value: the files whose rows are the ones it keeps are the ones
        # that date the answer, so it is done here in the same order, on the same key and before the rows without a
        # value go
        # the name is written as declared first, as `shape_provider_frame` does after this, so that the rows the core
        # keeps are the rows counted here
        declared = _declared_parameter_names(df, dataset)
        if declared:
            df = df.with_columns(pl.col("parameter").cast(pl.String).replace(declared))
        df = merge_duplicate_readings(df, ["parameter", "timestamp"])
        kept = pl.col("parameter").is_in(requested)
        stamp = self._window_stamp(df)
        if self.sr.start and stamp is not None:
            kept &= stamp.is_between(self.sr.start, self.sr.end, closed="both")
        if self.sr.options.drop_nulls_effective:
            kept &= pl.col("value").is_not_null()
        for updated in df.filter(kept).get_column(UPDATED).drop_nulls().unique():
            self._note_data_updated(updated)
        # the core drops any column of its own accord (`shape_provider_frame`); this is so that it need not
        return df.drop(UPDATED)

    def _empty_values_df(self) -> pl.DataFrame:
        """Build the frame a request that collected nothing returns, carrying its schema.

        Shaped like a collected one would have been, so that the empty case differs from the
        populated case only in having no rows: wide for ``shape="wide"``, where ``_widen_df``
        names the parameter columns from the request rather than from data it does not have.

        Built in the long form and then reshaped, exactly as a collected frame is, rather than in
        the shape asked for: `_widen_df` reads the `parameter` column that the wide form no longer
        has, and a wide request spanning two datasets raised `ColumnNotFoundError` from inside it.

        Built from `LONG_SCHEMA`, so its columns are the ones a populated frame has, down to the dtypes.
        """
        df = pl.DataFrame(schema=LONG_SCHEMA)
        if not self.sr.options.tidy:
            df = self._widen_df(df=df)
        return df

    def _station_elevation(self, station_id: str, dataset: DatasetModel | None = None) -> float | None:
        """Give the elevation in m that the station list holds for a station, or ``None`` where it holds none.

        A list that has a row per resolution and dataset (as the DWD and Météo-France ones do) may hold another
        elevation for each; with ``dataset`` the row of that resolution and dataset is the one read.
        """
        columns = self.sr.df.columns
        if "elevation" not in columns:
            return None
        rows = self.sr.df.filter(pl.col("station_id").eq(station_id))
        if dataset is not None and "resolution" in columns and "dataset" in columns:
            rows = rows.filter(pl.col("resolution").eq(dataset.resolution.name) & pl.col("dataset").eq(dataset.name))
        elevations = rows.get_column("elevation").cast(pl.Float64, strict=False).drop_nulls().drop_nans()
        return None if elevations.is_empty() else float(elevations[0])

    def _get_available_datasets(self, df: pl.DataFrame) -> list[DatasetModel]:
        """Extract available datasets for the station."""
        resolution_dataset_pairs = (
            df.select(["resolution", "dataset"]).unique().sort(["resolution", "dataset"]).rows(named=True)
        )
        return [self.sr.request.metadata[pair["resolution"]][pair["dataset"]] for pair in resolution_dataset_pairs]

    def _collect_station_data(self, station_id: str, available_datasets: list[DatasetModel]) -> pl.DataFrame:
        """Collect and process data for a single station."""
        if not available_datasets:
            return pl.DataFrame(schema=LONG_SCHEMA)
        data = []
        # self.sr.request.parameters is parsed at runtime to a list[ParameterModel],
        # but the static type of the attribute is a union of input forms. Cast here so
        # the typechecker understands we iterate ParameterModel instances.
        for dataset, parameters in group_parameters_by_dataset(
            cast("Iterable[ParameterModel]", self.sr.request.parameters),
        ):
            if dataset not in available_datasets:
                continue
            df = self._process_dataset(station_id, dataset, parameters)
            if not df.is_empty():
                data.append(df)
        return pl.concat(data) if data else pl.DataFrame(schema=LONG_SCHEMA)

    def _process_dataset(
        self, station_id: str, dataset: DatasetModel, parameters: Sequence[ParameterModel]
    ) -> pl.DataFrame:
        """Process data for a specific dataset."""
        # the readers judge the numbers they parse with the modes of the request's `plausibility` (GH-3676)
        with applying(self.sr.options.plausibility):
            return self._process_dataset_in_effect(station_id, dataset, parameters)

    def _process_dataset_in_effect(
        self, station_id: str, dataset: DatasetModel, parameters: Sequence[ParameterModel]
    ) -> pl.DataFrame:
        """Process data for a specific dataset, as `_process_dataset` does inside the modes of the request."""
        if dataset.grouped:
            df = self._collect_station_parameter_or_dataset(
                station_id=station_id,
                # a dataset marked `grouped` is collected as a whole: the provider asked for it by
                # saying so, and the type parameter is what it said it would be handed
                parameter_or_dataset=cast("_UnitT", dataset),
            )
            df = self._shape(df, station_id, dataset)
            parameter_names = {parameter.name_original for parameter in parameters}
            df = df.filter(pl.col("parameter").is_in(parameter_names))
        else:
            data = []
            for parameter in parameters:
                df = self._collect_station_parameter_or_dataset(
                    station_id=station_id,
                    parameter_or_dataset=cast("_UnitT", parameter),
                )
                # shaped per call, so that the frames of the parameters have one schema to concatenate by: a parameter
                # with no data for this station is the empty frame of that schema, whatever the provider handed over
                # (a bare frame with no columns would raise "unable to append to a DataFrame of width 6 with a
                # DataFrame of width 0"), and it contributes no rows
                data.append(self._shape(df, station_id, dataset))
            df = pl.concat(data) if data else pl.DataFrame(schema=LONG_SCHEMA)
        if df.is_empty():
            # the empty frame of `LONG_SCHEMA`, as `shape_provider_frame` makes it of any provider frame without rows
            return df
        if self.sr.options.convert_units:
            df = self._convert_units(df, dataset)
        df = merge_duplicate_readings(df, ["station_id", "resolution", "dataset", "parameter", "timestamp"])
        in_window = self._filter_by_window(df)
        if QUALITY_FLAGS in df.columns:
            # the readings the source marked as missing may leave with the nulls; the answer still tells how many,
            # of the window it is cut to (`_filter_by_window`, later) and not of the whole file, and of the stations
            # it keeps: counted here, told by `_query_stations` (`_tell_missing_value_markers`)
            self._markers_in_window += in_window.filter(
                pl.col("value").is_null() & pl.col(QUALITY_FLAGS).str.contains(RAW_TOKEN)
            ).height
        if self.sr.options.skip_empty:
            # the span the nulls make with them kept, and the readings they are, which the coverage is measured
            # against where there is no window or no grid to count readings by, whether the nulls are dropped or not
            # (`_get_actual_percentage`)
            self._window_spans.append(
                in_window.group_by("resolution", "dataset").agg(
                    pl.col("timestamp").min().alias("first"), pl.col("timestamp").max().alias("last")
                )
            )
            self._window_rows.append(
                in_window.group_by("resolution", "dataset", "parameter").agg(pl.len().alias("rows"))
            )
        if self.sr.options.drop_nulls_effective:
            if self.sr.options.skip_empty:
                # what the station has with the nulls kept, were `skip_empty` to leave it out (`_query_stations`)
                self._window_parameters.append(in_window.select("resolution", "dataset", "parameter").unique())
            df = df.drop_nulls(subset=["value"])
        return df

    def _shape(self, df: pl.DataFrame, station_id: str, dataset: DatasetModel) -> pl.DataFrame:
        """Make the frame of one provider call the long form, by `shape_provider_frame`."""
        return shape_provider_frame(df, station_id=station_id, dataset=dataset, provider=type(self).__name__)

    @abstractmethod
    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: _UnitT,
    ) -> pl.DataFrame:
        """Collect data for a station and a single parameter or dataset.

        This is what a provider hands to the core, and `shape_provider_frame` is what the core makes of it (GH-2627):
        it writes the identity columns, casts to the long form's dtypes, fills what is missing, orders the columns and
        drops the others, so what is listed as required is all a provider has to get right. A provider that shapes its
        frame already (many still do, and are to stop) comes out unchanged.

        Called once per parameter, with a `ParameterModel`, or, for a dataset declared `grouped`, once per dataset,
        with the `DatasetModel`: the frame may then hold every parameter of the dataset, and the core keeps the
        requested ones.

        Returns:
            One long-form frame of the readings of the station for that parameter or dataset, with the columns

            - ``parameter`` (String): the source's own name of the parameter, `name_original`; a name in another
              casing than the metadata's is written as the metadata declares it (`shape_provider_frame`). Required. A
              non-grouped call returns the one parameter it was asked for: nothing filters the others out.
            - ``timestamp`` (Datetime): the instant of the reading, and not null on a row that has a value. The core
              casts it to ``Datetime("us", "UTC")``: a naive stamp is read as UTC, a zoned one is converted, so a
              source that stamps in local time is converted by the provider, which knows the zone. A date is
              midnight UTC. A text or a number is no timestamp and is a `ProviderContractError`. Required.
            - ``value`` (Float64): the reading in the unit the metadata declares for the parameter, which the core
              converts unless `convert_units` is off, or null where the source has none: the core drops the null
              rows unless the caller asked for them. A sentinel is mapped to null here, before any unit conversion,
              with `null_sentinels`, and a NaN is the provider's to turn into null. The core casts a number to
              Float64, and a text to the number it writes: a cell that is none becomes null, and the core logs one
              debug line per frame with how many did, never one per cell. Required.
            - ``quality_flags`` (String): the flags of the source for the reading, built with `join_quality_flags`.
              Optional: the core adds a typed null column to a frame without it.
            - ``station_id``, ``resolution`` and ``dataset`` are the core's: it writes the id the call was made for,
              the name of the dataset's resolution and the lower-cased name of the dataset, over whatever the frame
              holds, before the duplicates are removed. A provider may leave them out.

            Any other column is dropped.

            For no data (a station without readings for the parameter) return a frame without a row, whatever its
            columns: a bare `pl.DataFrame()` is right, and so is the frame with the columns and none of the rows. The
            core makes of it the empty frame of `LONG_SCHEMA` and contributes no rows; a provider need not build an
            empty schema of its own, and none is read.

            The rows may come in any order, more than once, and outside the requested window (the core cuts it
            after, so a provider is free to narrow what it downloads by it, not obliged to). The core makes one row of
            the rows that share `resolution`, `dataset`, `parameter` and `timestamp`: the first that has a `value`,
            with its `quality_flags`, or the first row where none has one.

        Raises:
            NoInternetError: a connection that cannot be made, which is never answered by an empty frame.
            ProviderContractError: raised by the core, not by the provider, for a frame that cannot be made to fit.

        """

    def _widen_df(self, df: pl.DataFrame) -> pl.DataFrame:
        """Widen a dataframe with each row having one timestamp, parameter, value and quality flags.

        Example:
        timestamp    parameter                  value   quality_flags
        1971-01-01   precipitation_amount       0       3
        1971-01-01   temperature_air_mean_2m   10      null

        becomes

        timestamp    precipitation_amount   precipitation_amount_quality_flags
        1971-01-01   0                      3
            temperature_air_mean_2m    temperature_air_mean_2m_quality_flags
            10                          null

        Each flags column is named after its parameter with a `_quality_flags` suffix rather than a
        `quality_` prefix, which is how the table names a source's own quality flags
        (`quality_wind` and others like it); those never become value columns,
        but a column named like one would read as one.

        Args:
            df: DataFrame with columns timestamp, parameter, value and quality_flags.

        Returns:
            DataFrame with one value and one quality flags column per parameter.

        """
        # if there is more than one dataset, we need to prefix parameter names with dataset names to avoid
        # column name conflicts
        datasets_by_resolution: dict[str, set[str]] = defaultdict(set)
        for parameter in self.sr.parameters:
            datasets_by_resolution[parameter.dataset.resolution.name].add(parameter.dataset.name.lower())
        datasets = {name for names in datasets_by_resolution.values() for name in names}
        if len(datasets) > 1:
            df = df.with_columns(
                pl.concat_str(
                    [
                        pl.col("dataset"),
                        pl.lit("_"),
                        pl.col("parameter"),
                    ]
                ).alias("parameter"),
            )
        # A wide row is one timestamp of one resolution. Resolution is what defines the time axis,
        # so two resolutions cannot share a row -- a 15-minute series and an hourly one do not have
        # the same timestamps to begin with. Two datasets recorded at the same resolution do share
        # their timestamps and so do share a row, which is the whole point of the dataset-name
        # prefix above: it exists to let their columns sit side by side.
        #
        # Keying the row on the dataset as well used to put each timestamp in the frame once per
        # dataset, and since the join below matched on the date alone every one of those rows was
        # then filled with every dataset's values -- so a `precipitation_more` row reported a
        # `climate_summary` value, and the two rows were identical but for the label.
        #
        # No single name describes a row that spans several datasets, so it carries none and the
        # column prefix names them instead. A resolution that holds one dataset keeps its name --
        # resolutions are not merged into one another, so no row of theirs is missing a name.
        #
        # Which resolutions those are is read from the request rather than from what the station
        # returned, exactly as the column prefix above is: a station that happens to deliver only
        # one of the two datasets asked for still gets the prefixed columns, and labelling its rows
        # with the one dataset that answered would make the column mean something different from
        # station to station in the frame they are concatenated into.
        merged_resolutions = [resolution for resolution, names in datasets_by_resolution.items() if len(names) > 1]
        dataset = (
            pl.when(pl.col("resolution").is_in(merged_resolutions))
            .then(pl.lit(None, dtype=df.schema["dataset"]))
            .otherwise(pl.col("dataset"))
            .alias("dataset")
            if merged_resolutions
            else pl.col("dataset")
        )
        df_wide = df.select(pl.col("station_id"), pl.col("resolution"), dataset, pl.col("timestamp")).unique()

        # the columns of the parameters in the order the request names them, as the empty frame has them,
        # and not in the order the source happened to deliver its rows in
        requested = []
        for parameter in self.sr.parameters:
            name = parameter.name_original if not self.sr.options.humanize else parameter.name
            requested.append(f"{parameter.dataset.name.lower()}_{name}" if len(datasets) > 1 else name)
        # once: the same parameter of a dataset of one name at two resolutions is one column
        requested = list(dict.fromkeys(requested))

        if not df.is_empty():
            delivered = {
                key[0]: df_parameter
                for key, df_parameter in df.partition_by(["parameter"], as_dict=True, maintain_order=True).items()
            }
            # a name the request does not account for, which the humanize mapping did not cover, follows
            ordered = [name for name in requested if name in delivered]
            ordered += [name for name in delivered if name not in ordered]
            for parameter in ordered:
                df_parameter = delivered[parameter]
                df_parameter = df_parameter.select(["resolution", "timestamp", "value", "quality_flags"])
                df_parameter = df_parameter.rename(
                    mapping={
                        "value": parameter,
                        "quality_flags": f"{parameter}{WIDE_FLAGS_SUFFIX}",
                    },
                )
                # left, not inner: a parameter that has no reading at a timestamp another parameter
                # does have one at must leave a null behind rather than take the whole timestamp
                # out of the frame. Chained inner joins reduced the frame to the timestamps every
                # requested parameter shared, which silently dropped readings that were asked for
                # -- three quarters of a 15-minute series joined against an hourly one
                df_wide = df_wide.join(df_parameter, on=["resolution", "timestamp"], how="left")
        else:
            # named as the populated branch above names them, so that an empty frame carries the column
            # names a populated one would have rather than the unprefixed names it used to, which named
            # no column the request could produce
            for parameter_name in requested:
                df_wide = df_wide.with_columns(
                    pl.lit(None, WIDE_VALUE_DTYPE).alias(parameter_name),
                    pl.lit(None, WIDE_FLAGS_DTYPE).alias(f"{parameter_name}{WIDE_FLAGS_SUFFIX}"),
                )

        return df_wide

    def all(self) -> ValuesResult:
        """Collect all data for all stations and parameters and return a single DataFrame."""
        data = []
        updated = []

        tqdm_out = TqdmToLogger(log, level=logging.INFO)

        for result in tqdm(self.query(), total=len(self.sr.station_id), file=tqdm_out):
            data.append(result.df)
            if result.data_updated_at is not None:
                updated.append(result.data_updated_at)

        if not data:
            # an ordinary outcome -- no station covered the requested window -- rather than an
            # error, so it is logged as one and does not print a traceback. The frame still carries
            # its schema: a caller writes it out as a header row, asks it for a column or
            # concatenates it against a populated frame, and none of that survives a frame with no
            # columns at all
            log.info("No data available for given constraints")
            return ValuesResult(stations=self.sr, df=self._empty_values_df())

        df = pl.concat(data, how="diagonal")

        return ValuesResult(stations=self.sr, df=df, data_updated_at=newest(updated))

    def to_target(self, target: str, if_exists: Literal["replace", "append", "fail", "skip"] = "fail") -> None:
        """Wrap to_target of all queried results.

        `if_exists` is for the first station and defaults to 'fail', where a result's `to_target` defaults to
        'replace': this is one table being filled station by station rather than one frame being written, so the
        first station must not overwrite a table that already holds data. Every station after it is appended.
        """
        tqdm_out = TqdmToLogger(log, level=logging.INFO)
        redacted = redact_password(target)
        for i, result in tqdm(enumerate(self.query()), total=len(self.sr.station_id), file=tqdm_out):
            result.to_target(target, if_exists=if_exists if i == 0 else "append")
            log.info(f"Exported data for station {result.df.get_column('station_id').unique()[0]} to {redacted}.")

    @staticmethod
    def _humanize(df: pl.DataFrame, humanized_parameters_mapping: pl.DataFrame) -> pl.DataFrame:
        """Humanize parameter names in a DataFrame.

        The name the source gives a parameter is only unique within a dataset of a resolution: chmi's `T` is
        `temperature_air_2m` at 10 minutes and `temperature_air_mean_2m` daily. So the mapping is looked up on the
        resolution and the dataset of the row as well (GH-3605). A name the mapping does not hold stays as it is.
        """
        keys = ["resolution", "dataset", "parameter"]
        return (
            df.join(humanized_parameters_mapping, on=keys, how="left", maintain_order="left")
            .with_columns(pl.coalesce("humanized", "parameter").alias("parameter"))
            .drop("humanized")
        )

    def _create_humanized_parameters_mapping(self) -> pl.DataFrame:
        """Create the mapping of original to humanized parameter names, per resolution and dataset.

        The columns are the identity columns a frame carries when it is humanized (`resolution` by name, `dataset`
        by lowercased name, as `_long_form` writes them), `parameter` as the source names it, and `humanized`.
        """
        parameters = cast("Iterable[ParameterModel]", self.sr.parameters)
        return pl.DataFrame(
            {
                "resolution": [parameter.dataset.resolution.name for parameter in parameters],
                "dataset": [parameter.dataset.name.lower() for parameter in parameters],
                "parameter": [parameter.name_original for parameter in parameters],
                "humanized": [parameter.name for parameter in parameters],
            },
            schema={"resolution": pl.String, "dataset": pl.String, "parameter": pl.String, "humanized": pl.String},
        ).unique(subset=["resolution", "dataset", "parameter"], keep="first", maintain_order=True)

    @staticmethod
    def _series_span(
        df_dataset: pl.DataFrame, spans: pl.DataFrame | None, resolution: str, dataset: str
    ) -> tuple[dt.datetime | None, dt.datetime | None]:
        """Give the first and last stamp of a dataset's readings: ``spans`` where it has them, else ``df_dataset``."""
        if spans is not None:
            row = spans.filter(pl.col("resolution").eq(resolution), pl.col("dataset").eq(dataset.lower()))
            if not row.is_empty():
                return cast("dt.datetime | None", row.item(0, "first")), cast("dt.datetime | None", row.item(0, "last"))
        if df_dataset.is_empty():
            return None, None
        dates = df_dataset.get_column("timestamp")
        return cast("dt.datetime", dates.min()), cast("dt.datetime", dates.max())

    @staticmethod
    def _rows_held(
        df_parameter: pl.DataFrame, rows: pl.DataFrame | None, resolution: str, parameter: ParameterModel
    ) -> int:
        """Give how many readings the station has of a parameter in the window: ``rows`` if given, else the frame's."""
        if rows is not None:
            row = rows.filter(
                pl.col("resolution").eq(resolution),
                pl.col("dataset").eq(parameter.dataset.name.lower()),
                pl.col("parameter").eq(parameter.name_original.lower()),
            )
            if not row.is_empty():
                return cast("int", row.item(0, "rows"))
        return df_parameter.height

    def _get_actual_percentage(
        self, df: pl.DataFrame, spans: pl.DataFrame | None = None, rows: pl.DataFrame | None = None
    ) -> float:
        """Share of the readings a request asked for that the station actually delivered.

        The denominator is how many readings the requested window can hold at the parameter's own
        resolution, counted from the window and the resolution rather than read off a frame that
        has first been reindexed onto a grid. So a station is measured against what was asked for
        and not against whatever the provider happened to send back, and asking the question no
        longer costs a materialized timestamp per reading of the window.

        A request that names no window is measured against the span of the station's own series
        for the dataset in question, since that is the only window there is; and where even that
        says nothing -- a resolution that names no interval, or a window too short to hold a
        single reading -- what is left is the share of the returned rows that carry a value.

        That span is read off the readings with the nulls kept, null or not: ``spans`` (``resolution``, ``dataset``,
        ``first``, ``last``) is what the frame held before ``drop_nulls`` took the nulls out, and without it the span is
        read off ``df``. So a station whose readings end in a stretch of nulls is judged the same with the nulls
        dropped as with them kept, and not against the shorter series of its non-null readings (GH-3578).

        Where there is no grid to count against, the share is of the readings the station has with the nulls kept:
        ``rows`` (``resolution``, ``dataset``, ``parameter``, ``rows``) is how many the window held before
        ``drop_nulls``, and without it the rows of ``df`` are counted.

        A parameter that was asked for and came back with nothing counts as zero rather than
        going unmeasured: a request for two parameters where one is missing is not fully covered. So does one whose
        values are all flagged ``suspect:`` by a soft plausibility check: the coverage counts the unflagged values
        alone, as an interpolation and the climate stripes do.
        """
        # a station that returned nothing inside the window covers none of it, and there is no
        # frame under the question to read a span or a dtype off
        if df.is_empty():
            return 0.0
        # a value a soft plausibility check flagged suspect is no coverage: a station with only such values is skipped
        # as it was when the check nulled them, whatever the mode (GH-3676)
        df = leave_out_suspect(df)
        percentages = []
        for parameter in cast("Iterable[ParameterModel]", self.sr.parameters):
            resolution = parameter.dataset.resolution
            # the dataset frame carries the fallback window below. Read per dataset rather than
            # over the whole frame, which spans every resolution asked for: a request pairing a
            # daily series reaching back to 1934 with an hourly one that starts decades later
            # would measure the hourly parameters against ninety years and drop a station whose
            # hourly record is complete for the whole of its life
            df_dataset = df.filter(
                pl.col("resolution").eq(resolution.name),
                pl.col("dataset").eq(parameter.dataset.name.lower()),
            )
            df_parameter = df_dataset.filter(
                # matched case-insensitively, as the unit conversion looks the name up: an exact match
                # would count a parameter that is present as missing and skip the station over it
                # (`shape_provider_frame` writes the declared name already, so this is the same name)
                pl.col("parameter").str.to_lowercase().eq(parameter.name_original.lower()),
            )
            start_date, end_date = self.sr.start, self.sr.end
            if start_date is None or end_date is None:
                start_date, end_date = self._series_span(df_dataset, spans, resolution.name, parameter.dataset.name)
            expected = (
                count_readings(resolution.value, start_date, end_date)
                if start_date is not None and end_date is not None
                else None
            )
            interval = reading_interval(resolution.value)
            if not expected or interval is None:
                held = self._rows_held(df_parameter, rows, resolution.name, parameter)
                percentages.append(df_parameter.get_column("value").drop_nulls().len() / held if held else 0.0)
                continue
            # counted as readings landing in distinct slots of the resolution's grid rather than
            # as readings. A station is free to report more often than the resolution it is listed
            # under, and its extra readings say nothing about the stretches of the window it was
            # silent for -- counted one by one, a station reporting every ten minutes through half
            # of an hourly window would cover it twice over and read as complete
            covered = df_parameter.drop_nulls("value").get_column("timestamp").dt.truncate(interval).n_unique()
            percentages.append(min(covered / expected, 1.0))
        if not percentages:
            return 0.0
        if self.sr.options.skip_criteria == "min":
            return min(percentages)
        if self.sr.options.skip_criteria == "mean":
            return sum(percentages) / len(percentages)
        if self.sr.options.skip_criteria == "max":
            return max(percentages)
        msg = "skip_criteria must be one of min, mean, max"
        raise KeyError(msg)
