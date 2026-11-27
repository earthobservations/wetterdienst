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
from typing_extensions import TypeVar, Unpack

from wetterdienst.exceptions import ProviderContractError
from wetterdienst.metadata.resolution import count_readings, reading_interval
from wetterdienst.model.fetch_ahead import FetchAhead, FilesAhead
from wetterdienst.model.group_statistics import StatisticsResult, StatisticsRun, parse_statistics
from wetterdienst.model.judge import SOURCE as SOURCE_COLUMN
from wetterdienst.model.judge import (
    SOURCE_TEXT,
    Plan,
    Rule,
    judge,
    limits_in_canonical,
    plan_for,
    to_canonical,
    to_requested,
)
from wetterdienst.model.metadata import group_parameters_by_dataset
from wetterdienst.model.parameter_rows import EstimateLeftOut, ParameterRows
from wetterdienst.model.plausibility import REJECTED_TOKEN, leave_out_suspect
from wetterdienst.model.quality_flags import CALM_TOKEN, QUALITY_FLAGS, RAW_TOKEN
from wetterdienst.model.request import require_window
from wetterdienst.model.result import StationsFilter, StationsResult, ValuesResult
from wetterdienst.model.row_selection import (
    ParameterNames,
    RowSelection,
    RowSelectionRefusedError,
    RowsOverLimitError,
    Searched,
    parse_row_selection,
    searched_of,
    station_names,
    wide_value_columns,
)
from wetterdienst.model.schema import (
    LONG_SCHEMA,
    WIDE_FLAGS_DTYPE,
    WIDE_FLAGS_SUFFIX,
    WIDE_VALUE_DTYPE,
    wide_schema,
)
from wetterdienst.model.station_window import NAMED_BY_ID, station_ids_read
from wetterdienst.model.unit import UnitConverter
from wetterdienst.util.cancellation import check as check_cancelled
from wetterdienst.util.datetime import is_plausible_update, newest
from wetterdienst.util.logging import TqdmToLogger
from wetterdienst.util.response_warnings import (
    CALM_WIND_DIRECTION,
    CALM_WIND_DIRECTION_MESSAGE,
    MISSING_VALUE_MARKER,
    MISSING_VALUE_MARKER_MESSAGE,
    REJECTED_BY_PLAUSIBILITY,
    REJECTED_BY_PLAUSIBILITY_MESSAGE,
    count_response_warning,
    warn_response,
)
from wetterdienst.util.url import redact_password

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Iterable, Iterator, Mapping, Sequence

    from wetterdienst.model.metadata import DatasetModel, ParameterModel
    from wetterdienst.model.row_selection import RowOptions

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


def _cells(frame: pl.DataFrame) -> int:
    """Count what a frame of values holds in cells: a long row is one, a wide row one for each parameter it has."""
    if "parameter" in frame.columns:
        return frame.height
    return frame.height * max(1, len(wide_value_columns(frame)))


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


def shape_provider_frame(  # noqa: C901
    df: pl.DataFrame,
    *,
    station_id: str,
    dataset: DatasetModel,
    provider: str = "the provider",
    keep_source_text: bool = False,
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
        keep_source_text: also give the column `SOURCE_TEXT`, the text the source wrote for the value, for the checks of
            the core to write in the `raw:` token of a value they reject (`model/judge.py`). It is the column
            `source_text` of the provider's frame where it has one, else its `value` where that is a text, else null,
            and the core then writes the number as short as it goes.

    Returns:
        The frame with exactly the columns of `LONG_SCHEMA`, in its order and with its dtypes (and `SOURCE_TEXT` last,
        where asked for); with no row, the empty frame of `LONG_SCHEMA`.

    Raises:
        ProviderContractError: ``parameter``, ``timestamp`` or ``value`` is missing, or has a type that cannot be made
            the declared one (a ``timestamp`` that is a string or an integer, a ``value`` that is a list). A frame
            without a row is never one.

    """
    extra = pl.Schema({SOURCE_TEXT: pl.String}) if keep_source_text else pl.Schema()
    if df.is_empty():
        return pl.DataFrame(schema=pl.Schema({**LONG_SCHEMA, **extra}))
    _check_provider_columns(df, provider)
    value = _value_as_number(df, provider)
    surplus = [column for column in df.columns if column not in LONG_SCHEMA and column != SOURCE_TEXT]
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
    if keep_source_text:
        # the text is not read or stripped here: it is written for the few rows a check rejects
        if SOURCE_TEXT in df.columns:
            columns.append(pl.col(SOURCE_TEXT).cast(pl.String))
        elif df.schema["value"] == pl.String:
            columns.append(pl.col("value").alias(SOURCE_TEXT))
        else:
            columns.append(pl.lit(None, dtype=pl.String).alias(SOURCE_TEXT))
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


def _requested_wide_columns(parameters: Iterable[ParameterModel], *, humanize: bool) -> list[str]:
    """Give the value columns of the requested parameters of a wide frame, in request order, once each.

    Named after humanising if that is on, else as the source names them, with the dataset as a prefix when the
    parameters span several datasets: what `TimeseriesValues._widen_df` names them, and the header of a streamed CSV.
    """
    parameters = list(parameters)
    datasets = {parameter.dataset.name.lower() for parameter in parameters}
    requested = []
    for parameter in parameters:
        name = parameter.name if humanize else parameter.name_original
        requested.append(f"{parameter.dataset.name.lower()}_{name}" if len(datasets) > 1 else name)
    # once: the same parameter of a dataset of one name at two resolutions is one column
    return list(dict.fromkeys(requested))


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
    #: whether the walk leaves out the stations the window cannot have data in (`model.station_window`, GH-4426); a
    #: caller whose walk stops where the data says and is held to a limit of its own (interpolation, summary) sets it
    #: False, and skips the stations whose list begins after the window alone, as it did
    _window_rule_allowed: bool = field(default=True, init=False, repr=False, compare=False)
    #: whether the `missing-value-marker` warning counts the readings of the stations this reads (GH-3554); a caller
    #: whose answer is an estimate of them (interpolation, summary) and not their readings sets it False
    _count_missing_value_markers: bool = field(default=True, init=False, repr=False, compare=False)
    #: the readings of the window that the source marked as missing, in the station in hand: counted by
    #: `_process_dataset`, told by `_query_stations` once the station is not left out (GH-3554)
    _markers_in_window: int = field(default=0, init=False, repr=False, compare=False)
    #: the same for the wind directions the source wrote as a calm (`raw:0`): a state of the wind and not a missing
    #: reading, so `missing-value-marker` leaves them out and `calm-wind-direction` counts them (GH-3696)
    _calm_in_window: int = field(default=0, init=False, repr=False, compare=False)
    #: the same for the nulls a hard plausibility check made (`rejected:<check>`), by check: the source wrote a number
    #: there and not a marker, so `missing-value-marker` leaves them out and `rejected-by-plausibility` counts them
    #: (GH-3682)
    _rejected_in_window: int = field(default=0, init=False, repr=False, compare=False)
    _rejected_by_check: dict[str, int] = field(default_factory=dict, init=False, repr=False, compare=False)
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
    #: provider let go (`file-skipped`, GH-3552) and the dates left out for another series (`other-window-left-out`) are
    #: told by the same walk and so are left out there too; the estimate tells them once (`_left_out_of_estimate`)
    _warn_without_rows: bool = field(default=True, init=False, repr=False, compare=False)
    #: where an estimate (interpolation, summary) has the walk tell what it left out at each station it reads: the
    #: stations whose file the provider let go, those whose dates of another series were left out and those whose values
    #: of a window that had not closed were left out, which the estimate tells once as `source-data-left-out` when its
    #: walk is over (`EstimateLeftOut`, GH-3848, GH-3883). It also says that the values are read for an estimate:
    #: `metno/frost` leaves the monthly and annual value of an open window out of one, as it does a daily value,
    #: and `dmi/observation` the day, the month and the year still running (`model/open_window.py`)
    _left_out_of_estimate: EstimateLeftOut | None = field(default=None, init=False, repr=False, compare=False)
    #: whether `all` is the caller of `query`, which finishes what the walk reduces station by station: a grouping that
    #: spans stations (`by=year`) and the order of `sort` are the whole answer's, and `query` alone cannot give them
    _finishing_rows: bool = field(default=False, init=False, repr=False, compare=False)
    #: the most rows `all` holds of the rows chosen, which a caller that answers within a limit (the REST API)
    #: sets; None for no limit. A walk whose choice stays in a station (a `filter`, a `sort`, a `first` by station) is
    #: stopped with `RowsOverLimitError` when it has held more
    _held_rows_limit: int | None = field(default=None, init=False, repr=False, compare=False)
    #: the stations the walk in hand read, those without a value included (`Searched.stations_read`)
    _stations_read: int = field(default=0, init=False, repr=False, compare=False)
    #: the ids of the stations the walk in hand reads where the window cuts its selection, None where it cuts none
    #: (`wetterdienst.model.station_window`, GH-4426): the stations the size limit counted
    _read_ids: frozenset[str] | None = field(default=None, init=False, repr=False, compare=False)
    #: the cells `all` held when it last made the choice again over groups that span stations (`_hold`)
    _compacted_cells: int = field(default=0, init=False, repr=False, compare=False)
    #: the names of the stations of the walk in hand by id, read once for the report (`_searched_of`)
    _names: dict[str, str | None] | None = field(default=None, init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Post-initialization of the TimeseriesValues object."""
        self.unit_converter.update_targets(self.sr.options.unit_targets)
        # before the first station is read: a window-less request for such a dataset used to answer an empty frame
        require_window(self.sr.parameters, self.sr.start, self.sr.end)
        self._check_limits()

    def _check_limits(self) -> None:
        """Refuse a bound the caller set that is no value of the unit the answer comes in, before anything is read.

        Converted for every dataset the request reads, as it is for each station later (`limits_in_canonical`): a bound
        outside the domain of a unit (a negative Beaufort number as m/s) is the request's error, a 400 for REST.
        """
        if not self.sr.options.limits:
            return
        for dataset, _ in group_parameters_by_dataset(cast("Iterable[ParameterModel]", self.sr.request.parameters)):
            limits_in_canonical(
                plan_for(self._network(), dataset),
                dataset,
                self.sr.options.limits,
                self.unit_converter,
                convert_units=self.sr.options.convert_units,
            )

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

    def _plausibility_rules(self, station_id: str, dataset: DatasetModel) -> Sequence[Rule]:  # noqa: ARG002
        """Give the rules only this provider knows for the station in hand, to be judged beside the core's own.

        The stations without frost, the periods in which one sensor of one station did not work, the relation of a
        road surface to the air of its minute at night (`Bound`, `StuckPeriod`, `Beside` of `model/judge.py`); a
        provider with none keeps this.
        """
        return ()

    def _network(self) -> str:
        """Name the network this values object reads as `provider/network`, as the registry of `Wetterdienst` has it."""
        from wetterdienst.api import Wetterdienst  # noqa: PLC0415

        return Wetterdienst._network_of(type(getattr(self.sr, "request", None)))  # noqa: SLF001

    def _judge_in_canonical_units(
        self,
        df: pl.DataFrame,
        station_id: str,
        dataset: DatasetModel,
        plan: Plan,
        rules: Sequence[Rule],
        limits: Mapping[str, tuple[float, float]],
    ) -> pl.DataFrame:
        """Convert every parameter of a collected frame to its canonical unit and judge it there (`model/judge.py`).

        The number the source wrote stays in `SOURCE_COLUMN`, for a caller that does not convert units, and its text in
        `SOURCE_TEXT` for the `raw:` token of a rejected value, which is dropped here.
        """
        df = df.with_columns(pl.col("value").alias(SOURCE_COLUMN))
        canonical = to_canonical(plan)
        if canonical is not None:
            df = df.with_columns(canonical.alias("value"))
        needs_elevation = plan.pressure or plan.daylight
        elevation = self._station_elevation(station_id, dataset) if needs_elevation and hasattr(self.sr, "df") else None
        position = self._station_position(station_id, dataset) if plan.daylight and hasattr(self.sr, "df") else None
        return judge(df, plan, self.sr.options.plausibility, rules, elevation, limits, position).drop(
            SOURCE_TEXT, strict=False
        )

    def _to_requested_units(
        self, df: pl.DataFrame, dataset: DatasetModel, plan: Plan, *, canonical: bool
    ) -> pl.DataFrame:
        """Convert the values of the parameters asked for to the unit asked for, in one expression, rounding once.

        From the canonical unit where the frame was judged (and `SOURCE_COLUMN` dropped), from the unit of the source
        where it was not. Nothing is converted where the options say so, and the numbers the source wrote are handed
        back (but for what a hard check mapped).
        """
        if canonical and not self.sr.options.convert_units:
            return df.with_columns(pl.col(SOURCE_COLUMN).alias("value")).drop(SOURCE_COLUMN)
        if not self.sr.options.convert_units:
            return df
        # a name is matched to the parameter that declares it in any casing, as it always was
        by_lower = {name.lower(): name for name in plan.parameters}
        present: dict[str, str] = {}
        for name in df.get_column("parameter").unique(maintain_order=True).to_list():
            if name.lower() not in by_lower:
                message = (
                    f"{type(self).__name__} returned the parameter {name!r}, which the dataset "
                    f"{dataset.resolution.name}/{dataset.name} does not declare in any casing"
                )
                raise ProviderContractError(message)
            present[name] = by_lower[name.lower()]
        # rounded to avoid long floats, by as many decimals as the target unit needs to keep the reading's precision
        # (`UnitConverter.decimals`)
        convert = to_requested(plan, present, self.unit_converter, canonical=canonical)
        df = df.with_columns(convert)
        return df.drop(SOURCE_COLUMN) if canonical else df

    def _unit_symbol(self, parameter: ParameterModel) -> str:
        """Give the symbol of the unit the values of a parameter come back in."""
        if self.sr.options.convert_units:
            return self.unit_converter.targets[parameter.unit_type].symbol
        return self.unit_converter.get_unit(parameter.unit, parameter.unit_type).symbol

    def _row_names(self) -> ParameterNames:
        """Give the names of the parameters of the request that a `filter` or a `sort` may write, as answered."""
        return ParameterNames.of(self.sr.parameters, humanize=self.sr.options.humanize)

    def _row_selection(self, rows: RowOptions, *, whole: bool) -> RowSelection | None:
        """Read the options that choose the rows and check them against this request, None where none is given.

        Raised before a station is read: a text that cannot be read (`RowSelectionError`), `value` over parameters in
        different units or in the wide shape, and a grouping across stations asked of `query`, which yields the
        stations one by one and cannot give it (`RowSelectionRefusedError`). `whole` is `all`, which can.
        """
        selection = parse_row_selection(**rows, parameters=self._row_names())
        if selection is None:
            return None
        if not self.sr.options.tidy:
            selection.refuse_wide()
        selection.refuse_for(self.sr.parameters, self._unit_symbol)
        if not whole and not selection.per_station:
            msg = (
                f"`by` without station_id groups across stations ({selection.echo()['by']}), which the stations of "
                "`query` cannot give one by one: use `all`, or add station_id to `by`."
            )
            raise RowSelectionRefusedError(msg)
        return selection

    def query(self, **rows: Unpack[RowOptions]) -> Iterator[ValuesResult]:
        """Query data for all stations and parameters and return a DataFrame for each station.

        For a provider that names the files of a station beforehand (`_files_ahead`) the files of the next stations
        are fetched while one is read, as many as `Settings.fetch_ahead` says (GH-3454). Nothing about the answer
        depends on it: the stations come in the same order with the same rows, and a failure is the failure of the
        station it was met at.

        `filter`, `sort`, `first` and `by` choose the rows of each station (`RowSelection`): the readings that meet the
        conditions, the first of each group in the order of `sort`. They are applied to a station after it is counted
        for a `rank` and for `skip_empty`, so that they change which rows come back and never which stations are read.
        Each result carries what was searched of its station (`ValuesResult.search`). A `by` that spans stations needs
        the whole answer, and is refused here: use `all`. `max_rows` caps the answer, which `query` has station by
        station: each station's rows are cut to it, and the cap of the whole is the caller's (`all` does it).

        Raises:
            RowSelectionError: an option whose text cannot be read, when the walk begins and before any station is.
            RowSelectionRefusedError: a selection that cannot be applied to this request, at the same point.

        """
        return self._walk(self._row_selection(rows, whole=self._finishing_rows))

    def _walk(self, selection: RowSelection | None, statistics: StatisticsRun | None = None) -> Iterator[ValuesResult]:
        """Walk the stations of the request, each reduced by `selection` or fed to `statistics` where there is one."""
        self._stations_read = 0
        self._names = None
        ids = station_ids_read(self.sr) if self._window_rule_allowed else None
        self._read_ids = None if ids is None else frozenset(ids)
        groups = list(self.sr.df.group_by(["station_id"], maintain_order=True))
        ahead = self._fetch_ahead(groups)
        try:
            yield from self._query_stations(groups, ahead, selection, statistics)
        finally:
            # a consumer that stops (a closed generator, an error, a streamed answer whose client has gone) starts
            # nothing more: what is begun ends with its download, and a download never leaves a part of a file in
            # the cache
            if ahead is not None:
                ahead.close()

    def _query_stations(
        self,
        groups: list[tuple[Any, pl.DataFrame]],
        ahead: FetchAhead | None,
        selection: RowSelection | None = None,
        statistics: StatisticsRun | None = None,
    ) -> Iterator[ValuesResult]:
        """Walk the stations in order, each one collected, cut to the window and shaped, as `query` yields them.

        With `statistics` each station's rows are handed to it as they are read and let go: the result a station yields
        has no rows then, and the groups are the run's.
        """
        # the stations that returned values, which `filter_by_rank` counts its slots in
        stations_collected = 0
        # an explicit list of ids, `station_id`s or the WMO, WIGOS or ICAO ids of stations, is the one kind of selection
        # whose empty stations are told (`station-without-rows`, GH-3828, GH-4070)
        asked = (
            [cast("str", station_id) for (station_id,), _ in groups]
            if self.sr._stations_filter in NAMED_BY_ID  # noqa: SLF001
            else None
        )
        rows = ParameterRows(
            self.sr.request,
            self.sr.start,
            self.sr.end,
            enabled=self._warn_without_rows,
            asked=asked,
            # `skip_empty` tells a station with a reading, all null, by `station-skipped` (`_leave_out_emptied`)
            nulls_dropped=self.sr.options.drop_nulls_effective and not self.sr.options.skip_empty,
            left_out=self._left_out_of_estimate,
        )
        # mapping of original to humanized parameter names is always the same
        hpm = self._create_humanized_parameters_mapping() if self.sr.options.humanize else None
        for position, ((station_id,), df_station_meta) in enumerate(groups):
            if stations_collected == self.sr._rank:  # noqa: SLF001
                break
            # the request this walk is for may have had its answer given up (a timeout, a client that left): the work
            # ends here, between two stations, and not at the last of them (GH-4429)
            check_cancelled()
            station_id = cast("str", station_id)
            if self._skips_station(station_id, df_station_meta):
                continue
            self._stations_read += 1
            available_datasets = self._get_available_datasets(df_station_meta)
            rows.examine(station_id, available_datasets)
            self._data_updated.clear()
            self._markers_in_window = 0
            self._calm_in_window = 0
            self._rejected_in_window = 0
            self._rejected_by_check.clear()
            self._window_parameters.clear()
            self._window_spans.clear()
            self._window_rows.clear()
            self._advance_fetch_ahead(ahead, position, stations_collected)
            # Collect data for this station
            with rows.collecting(station_id):
                df = self._filter_by_window(self._collect_station_data(station_id, available_datasets))
            # the values a hard check made null at this station, for an estimate to tell (`EstimateLeftOut`)
            rows.rejected(station_id, self._rejected_in_window, self._rejected_by_check)
            rows.note(df)
            # judged after the window has been cut, not before it: a station whose record lies
            # entirely outside the requested window returned data, but none that was asked for.
            # Counting it as collected spent one of `filter_by_rank`'s slots on an empty frame, so
            # the ranked walk stopped short of the stations that do cover the window and the
            # request came back with nothing
            if df.is_empty():
                self._leave_out_emptied(station_id, rows, df_station_meta)
                self._pass_over(rows, station_id)
                continue
            if self.sr.options.skip_empty:
                percentage = self._get_actual_percentage(df=df, spans=self._station_spans(), rows=self._station_rows())
                if percentage < self.sr.options.skip_threshold:
                    # a parameter that holds nothing but nulls is a row the station has, with the nulls kept
                    self._note_nulls_dropped(rows)
                    self._warn_station_skipped(station_id, percentage, rows)
                    self._pass_over(rows, station_id)
                    continue
            self._tell_missing_value_markers(station_id, df_station_meta)
            if hpm is not None:
                df = self._humanize(df=df, humanized_parameters_mapping=hpm)
            # what the selection searches, as the answer names it, counted before it chooses
            searched = (
                self._searched_of(df, stamped_on_the_day=statistics is not None)
                if selection is not None or statistics is not None
                else None
            )
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
            rows.returned(station_id)
            if statistics is not None and searched is not None:
                statistics.add_station(df, searched)
                df, search = df.head(0), None
            else:
                df, search = self._choose_rows(selection, searched, df)
            yield ValuesResult(stations=self.sr, df=df, data_updated_at=newest(self._data_updated), search=search)
        # the answer of the request may have been given up while the last station was read: what is made of the stations
        # (the rows, the picture) is not made for nobody (GH-4429)
        check_cancelled()
        # only a walk read to its end says what it found: a failure raised before it, and one that is stopped is silent
        rows.warn(rank_filled=stations_collected == self.sr._rank)  # noqa: SLF001

    def _searched_of(self, df: pl.DataFrame, *, stamped_on_the_day: bool = False) -> pl.DataFrame:
        """Count what the rows of a station hold for the report, with the window, the station's name and the kind."""
        if self._names is None:
            self._names = station_names(self.sr.df)
        return searched_of(
            df,
            (self.sr.start, self.sr.end),
            names=self._names,
            forecast=self.sr.request.metadata.kind == "forecast",
            stamped_on_the_day=stamped_on_the_day,
        )

    def _choose_rows(
        self, selection: RowSelection | None, searched: pl.DataFrame | None, df: pl.DataFrame
    ) -> tuple[pl.DataFrame, Searched | None]:
        """Apply the selection to the rows of a station that is counted, and say what it searched there.

        After the station is counted for a rank and for `skip_empty`: the rows chosen are the answer's, the station
        read is what the options of the request decided.
        """
        if selection is None or searched is None:
            return df, None
        df = selection.reduce_station(df)
        search = Searched(series=searched, selection=selection, window=(self.sr.start, self.sr.end)).with_matched(df)
        if selection.per_station:
            # a station holds no more than the answer can: the count of what matched is taken before
            df = selection.cap_station(df, held=self._finishing_rows)
            search = search.with_returned(df)
        return df, search

    def _pass_over(self, rows: ParameterRows, station_id: str) -> None:
        """Note that a rank walk passed a candidate over (an empty frame, or one below `skip_threshold`) for the next.

        Only a rank walk replaces a station: a pick by ids, distance or name that drops one leaves the answer short of
        it, which `file-skipped` tells if its file was let go (GH-3552). Whether the replacement filled the rank is
        known at the end of the walk (`ParameterRows.warn`).
        """
        if self.sr._stations_filter == StationsFilter.BY_RANK:  # noqa: SLF001
            rows.passed_over(station_id)

    def _warn_station_skipped(self, station_id: str, percentage: float, rows: ParameterRows) -> None:
        """Tell that `skip_empty` leaves the station out, for a share of actual values below the threshold."""
        rows.explained(station_id)
        warn_response(
            log,
            "station-skipped",
            f"station {station_id} is skipped as percentage of actual values ({percentage}) "
            f"is below threshold ({self.sr.options.skip_threshold}).",
            level=logging.INFO,
        )

    def _leave_out_emptied(self, station_id: str, rows: ParameterRows, df_station_meta: pl.DataFrame) -> None:
        """Tell of a station with nothing left in the window: `station-skipped` if it held readings, all nulls."""
        if self._note_nulls_dropped(rows):
            # `skip_empty` leaves it out, as it does with the nulls kept
            self._warn_station_skipped(station_id, 0.0, rows)
        self._tell_missing_value_markers(station_id, df_station_meta, emptied=True)

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

    def _count_rejected(self, rejected: pl.DataFrame) -> None:
        """Count the nulls of the window that a hard check made, in all and by the check that rejected them."""
        if rejected.is_empty():
            return
        self._rejected_in_window += rejected.height
        checks = (
            rejected.get_column(QUALITY_FLAGS)
            .str.extract(rf"{REJECTED_TOKEN}([a-z+]+)", 2)
            .str.split("+")
            .explode()
            .drop_nulls()
            .value_counts()
        )
        for check, number in checks.iter_rows():
            self._rejected_by_check[check] = self._rejected_by_check.get(check, 0) + number

    def _tell_missing_value_markers(
        self, station_id: str, df_station_meta: pl.DataFrame, *, emptied: bool = False
    ) -> None:
        """Add the markers of the station in hand to the warning of the request, unless the station is left out.

        Counted by `_process_dataset` for the station and told here, once the walk has not skipped it (`skip_empty`):
        the count is of the readings of the answer, and a station that is not in it, or one that an estimate reads
        (`_count_missing_value_markers`), has none to tell (GH-3554). One sum for the request, which
        `count_response_warning` keeps, with the count at each station (and its name), which the message tells for the
        first few (GH-4424).

        A station `emptied` of its frame because the nulls were dropped is told when the request names it: the markers
        are what the nulls were. Not where it would be left out all the same -- `skip_empty` skips a frame without a
        reading, as it does with the nulls kept, and a rank walk (`filter_by_rank`) walks past it. A pick by name
        takes the stations the name matches, and none takes the place of an emptied one.
        """
        if emptied and (self.sr.options.skip_empty or self.sr._stations_filter == StationsFilter.BY_RANK):  # noqa: SLF001
            return
        if self._count_missing_value_markers:
            name = self._name_of(df_station_meta)
            count_response_warning(
                MISSING_VALUE_MARKER,
                self._markers_in_window,
                MISSING_VALUE_MARKER_MESSAGE,
                station=station_id,
                station_name=name,
            )
            count_response_warning(
                CALM_WIND_DIRECTION,
                self._calm_in_window,
                CALM_WIND_DIRECTION_MESSAGE,
                station=station_id,
                station_name=name,
            )
            count_response_warning(
                REJECTED_BY_PLAUSIBILITY,
                self._rejected_in_window,
                REJECTED_BY_PLAUSIBILITY_MESSAGE,
                details=self._rejected_by_check,
                station=station_id,
                station_name=name,
            )

    @staticmethod
    def _name_of(df_station_meta: pl.DataFrame) -> str | None:
        """Give the name the station list has for the station, or None where it has none (its rows are at hand)."""
        if "name" not in df_station_meta.columns or df_station_meta.is_empty():
            return None
        name = df_station_meta.get_column("name")[0]
        return name.strip() if isinstance(name, str) and name.strip() else None

    @staticmethod
    def _rows_of(*parameters: ParameterModel) -> pl.Expr:
        """Select the rows of a long frame that hold one of the parameters, by `resolution`, `dataset` and `parameter`.

        The `parameter` column holds the source's own name (`name_original`) until the answer is humanized.
        """
        return pl.any_horizontal(
            pl.col("resolution").eq(parameter.dataset.resolution.name)
            & pl.col("dataset").eq(parameter.dataset.name)
            & pl.col("parameter").eq(parameter.name_original)
            for parameter in parameters
        )

    def _zero_direction_is_no_bearing(self) -> pl.Expr:
        """Select the rows whose wind direction of `raw:0` is a code of no bearing, and no calm (GH-3696).

        `calm-wind-direction` counts the nulls of a wind direction whose `raw` token is the 0 of a calm. A provider
        whose 0 is something else overrides this with an expression of the `resolution`, `dataset` and `parameter`
        columns that is true for them, and those stay with `missing-value-marker`: a code of the source for a variable
        wind or for a direction it does not report, which is missing and not a state of the wind.
        """
        return pl.lit(value=False)

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
            if self._skips_station(cast("str", station_id), df_station_meta):
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

    def _skips_station(self, station_id: str, df_station_meta: pl.DataFrame) -> bool:
        """Whether the walk leaves this station out for the window: the one rule of the stations a window reads.

        A station named by id is never left out (`NAMED_BY_ID`). Where the window cuts the selection, the station is
        read if the stations the limit counted include it (`_read_ids`, from `station_ids_read`, the one rule of
        `wetterdienst.model.station_window`), and a provider's own `_begins_after_window` may leave out one more. For
        the selections the rule does not cut (a rank, a name) and a network that opted out of it (ECCC) it is
        `_begins_after_window` alone, as it was.
        """
        if self.sr._stations_filter in NAMED_BY_ID:  # noqa: SLF001
            return False
        if self._read_ids is not None and station_id not in self._read_ids:
            return True
        return self._begins_after_window(df_station_meta)

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

    def _station_position(self, station_id: str, dataset: DatasetModel | None = None) -> tuple[float, float] | None:
        """Give the latitude and longitude in degrees the station list holds for a station, or ``None`` if it has none.

        The row of the resolution and dataset is the one read, where the list has a row for each, as for the elevation
        (`_station_elevation`).
        """
        columns = self.sr.df.columns
        if "latitude" not in columns or "longitude" not in columns:
            return None
        rows = self.sr.df.filter(pl.col("station_id").eq(station_id))
        if dataset is not None and "resolution" in columns and "dataset" in columns:
            rows = rows.filter(pl.col("resolution").eq(dataset.resolution.name) & pl.col("dataset").eq(dataset.name))
        rows = rows.select(
            pl.col("latitude").cast(pl.Float64, strict=False), pl.col("longitude").cast(pl.Float64, strict=False)
        ).drop_nulls()
        return None if rows.is_empty() else (float(rows["latitude"][0]), float(rows["longitude"][0]))

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

    def _process_dataset(  # noqa: C901
        self, station_id: str, dataset: DatasetModel, parameters: Sequence[ParameterModel]
    ) -> pl.DataFrame:
        """Process data for a specific dataset."""
        parameter_names = {parameter.name_original for parameter in parameters}
        # every check runs here, in canonical units, once the duplicates of the periods are merged and before the
        # parameters are cut to those asked for (`model/judge.py`); a dataset no check applies to is cut and converted
        # straight to the unit asked for
        plan = plan_for(self._network(), dataset)
        rules = self._plausibility_rules(station_id, dataset)
        # the bounds the caller set for the parameters of this dataset, in canonical units (`Options.limits`)
        limits = limits_in_canonical(
            plan,
            dataset,
            self.sr.options.limits,
            self.unit_converter,
            convert_units=self.sr.options.convert_units,
        )
        judged = plan.judges or bool(rules) or bool(limits)
        if dataset.grouped:
            df = self._collect_station_parameter_or_dataset(
                station_id=station_id,
                # a dataset marked `grouped` is collected as a whole: the provider asked for it by
                # saying so, and the type parameter is what it said it would be handed
                parameter_or_dataset=cast("_UnitT", dataset),
            )
            df = self._shape(df, station_id, dataset, keep_source_text=judged)
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
                data.append(self._shape(df, station_id, dataset, keep_source_text=judged))
            df = pl.concat(data) if data else pl.DataFrame(schema=LONG_SCHEMA)
        if df.is_empty():
            # the empty frame of `LONG_SCHEMA`, as `shape_provider_frame` makes it of any provider frame without rows
            return df.drop(SOURCE_TEXT, strict=False)
        # the station, the resolution and the dataset are the same on every row, so the reading is the parameter and the
        # stamp. The rows of the periods a provider read are one series here, the first that has a value first (for DWD
        # the historical archive before the recent one), before any check looks at it
        if judged:
            if dataset.grouped:
                # a verdict on a parameter that is cut afterwards is never seen: only what is asked for and what a rule
                # reads beside it is merged, converted and judged, which is the same answer for a fraction of the work
                df = df.filter(pl.col("parameter").is_in(parameter_names | plan.read_beside(rules, parameter_names)))
            df = self._judge_in_canonical_units(
                merge_duplicate_readings(df, ["parameter", "timestamp"]), station_id, dataset, plan, rules, limits
            )
        if dataset.grouped:
            df = df.filter(pl.col("parameter").is_in(parameter_names))
        if df.is_empty():
            return df.drop(SOURCE_COLUMN, strict=False)
        if not judged:
            df = merge_duplicate_readings(df, ["parameter", "timestamp"])
        df = self._to_requested_units(df, dataset, plan, canonical=judged)
        in_window = self._filter_by_window(df)
        if QUALITY_FLAGS in df.columns:
            # the readings the source marked as missing may leave with the nulls; the answer still tells how many,
            # of the window it is cut to (`_filter_by_window`, later) and not of the whole file, and of the stations
            # it keeps: counted here, told by `_query_stations` (`_tell_missing_value_markers`)
            # a null a hard check made carries the number the source wrote, not a marker: counted apart (GH-3682)
            nulled = in_window.filter(pl.col("value").is_null() & pl.col(QUALITY_FLAGS).str.contains(RAW_TOKEN))
            rejected = pl.col(QUALITY_FLAGS).str.contains(REJECTED_TOKEN)
            # a calm has no direction: the source wrote 0 for it, and the wind is not missing (GH-3696)
            # (`parameter` is the source's own name here, so the directions are told by the metadata)
            directions = [
                parameter.name_original for parameter in dataset if parameter.name.startswith("wind_direction")
            ]
            calm = (
                pl.col("parameter").is_in(directions)
                & pl.col(QUALITY_FLAGS).str.contains(CALM_TOKEN)
                & ~self._zero_direction_is_no_bearing()
            )
            written = nulled.filter(~rejected)
            calms = written.filter(calm).height
            self._calm_in_window += calms
            self._markers_in_window += written.height - calms
            self._count_rejected(nulled.filter(rejected))
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

    def _shape(
        self, df: pl.DataFrame, station_id: str, dataset: DatasetModel, *, keep_source_text: bool = False
    ) -> pl.DataFrame:
        """Make the frame of one provider call the long form, by `shape_provider_frame`."""
        return shape_provider_frame(
            df, station_id=station_id, dataset=dataset, provider=type(self).__name__, keep_source_text=keep_source_text
        )

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

    def _wide_schema(self) -> pl.Schema:
        """Give the columns a wide frame of this request can have, in the order it writes them, with their dtypes.

        The columns of `WIDE_SCHEMA`, then the value column of every requested parameter, each followed by its flags
        column, named as `_widen_df` names them: after humanising if that is on, with the dataset as a prefix when
        the request spans several. A station's frame has the columns of the parameters it delivers only, so a stream
        that writes its header with the first station asks this for the header of all (GH-4432).
        """
        return wide_schema(_requested_wide_columns(self.sr.parameters, humanize=self.sr.options.humanize))

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
        requested = _requested_wide_columns(self.sr.parameters, humanize=self.sr.options.humanize)

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

    def all(self, **rows: Unpack[RowOptions]) -> ValuesResult:
        """Collect all data for all stations and parameters and return a single DataFrame.

        `filter`, `sort`, `first` and `by` choose the rows (`RowSelection`; see `query`). Each station is reduced as it
        is read, so that only the rows chosen are held, and the whole is finished once: the groups of `by` that span
        stations, and the order of `sort` (by series, the sort keys, then station and timestamp). The result says
        what was searched, per station and series, in `search`.

        Raises:
            RowSelectionError: an option whose text cannot be read, before any station is.
            RowSelectionRefusedError: a selection that cannot be applied to this request.

        """
        selection = self._row_selection(rows, whole=True)
        data = []
        updated = []
        parts: list[pl.DataFrame] = []
        matched_rows = 0
        # `max_rows` over a choice that stays in a station: what is held is no more than the answer, and the walk
        # goes on counting what matched at the stations after it
        keep = selection.max_rows if selection is not None and selection.per_station and not selection.sort else None

        tqdm_out = TqdmToLogger(log, level=logging.INFO)

        self._finishing_rows = selection is not None
        self._compacted_cells = 0
        held_rows = held_cells = 0
        try:
            walk = self.query(**rows) if selection is not None else self.query()
            for result in tqdm(walk, total=len(self.sr.station_id), file=tqdm_out):
                frame = result.df if keep is None else result.df.head(max(keep - held_rows, 0))
                data.append(frame)
                held_rows += frame.height
                held_cells += _cells(frame)
                if selection is not None:
                    held_rows, held_cells, data = self._hold(selection, held_rows, held_cells, data)
                if result.data_updated_at is not None:
                    updated.append(result.data_updated_at)
                if result.search is not None:
                    parts.append(result.search.series)
                    matched_rows += result.search.matched_rows or 0
        finally:
            self._finishing_rows = False

        window = (self.sr.start, self.sr.end)
        if not data:
            # an ordinary outcome -- no station covered the requested window -- rather than an
            # error, so it is logged as one and does not print a traceback. The frame still carries
            # its schema: a caller writes it out as a header row, asks it for a column or
            # concatenates it against a populated frame, and none of that survives a frame with no
            # columns at all
            log.info("No data available for given constraints")
            empty = self._empty_values_df()
            search = None
            if selection is not None:
                search = Searched.nothing(selection, window, self._stations_read)
            return ValuesResult(stations=self.sr, df=empty, search=search)

        if selection is None:
            df = pl.concat(data, how="diagonal")
            return ValuesResult(stations=self.sr, df=df, data_updated_at=newest(updated))
        matching = selection.finish(data)
        search = Searched(
            series=pl.concat(parts),
            selection=selection,
            window=window,
            matched_rows=matched_rows,
            stations_read=self._stations_read,
        )
        if not (selection.max_rows is not None and selection.per_station):
            # the rows of the walk are what matched: counted again over the whole, which a group that spans stations
            # settles. Where the stations were cut to `max_rows`, the counts of the walk are the ones that count
            search = search.with_matched(matching)
        df = selection.cap(matching)
        search = search.with_returned(df)
        search.warn_if_capped()
        return ValuesResult(stations=self.sr, df=df, data_updated_at=newest(updated), search=search)

    def statistics(
        self,
        aggregate: str | Sequence[str],
        *,
        by: str | Sequence[str] | None = None,
        filter: str | None = None,  # noqa: A002
        year_start: int | str | None = None,
        max_missing: int | str | None = None,
        having: str | None = None,
        sort: str | None = None,
        first: int | str | None = None,
        per: str | None = None,
        max_rows: int | str | None = None,
    ) -> StatisticsResult:
        """Count, average, add up or take the extremes of each station's values per year, month, day or hour.

        `aggregate` is one to five of `count mean sum min max earliest latest`; `by` the groups besides the series (any
        of `year month day hour`); `filter` the conditions (`year month day hour` say which values are looked at,
        `value` which of them count); `year_start` the month a `year` begins; `max_missing` how many missing values a
        group may have and still get a `mean` and a `sum` (keep it 0 to rank: `gaps-allowed` counts the groups it
        lets in); `having` and `sort` choose and order the groups by what was calculated, `first` keeps the first N of
        them (exactly N: `ties-not-shown` says how many more tie) per series or, with `per="none"`, over the stations
        of a parameter; `max_rows` cuts the answer. See `group_statistics`.

        Each station is reduced to its groups as it is read and its rows let go, so that what is held is the groups
        and not the readings. A group that is not over yet is incomplete: its `mean` and `sum` are null unless
        `max_missing` allows it, and `searched` and `expected` say how many values it has and should have. Series are
        never merged.

        Raises:
            RowSelectionError: an option whose text cannot be read, before any station is.
            RowSelectionRefusedError: an option that cannot be applied to this request or to one of its series (a sum
                of a pressure, `by=hour` of daily values, the wide shape).
            GroupsOverLimitError: the groups held are more than `_held_rows_limit` allows.

        """
        plan = parse_statistics(
            aggregate,
            by=by,
            filter=filter,
            year_start=year_start,
            max_missing=max_missing,
            having=having,
            sort=sort,
            first=first,
            per=per,
            max_rows=max_rows,
        )
        run = StatisticsRun.for_stations(
            self.sr, plan, unit_symbol=self._unit_symbol, held_groups_limit=self._held_rows_limit
        )
        updated: list[dt.datetime] = []
        tqdm_out = TqdmToLogger(log, level=logging.INFO)
        for result in tqdm(self._walk(None, run), total=len(self.sr.station_id), file=tqdm_out):
            if result.data_updated_at is not None:
                updated.append(result.data_updated_at)
        return run.finish(self.sr, stations_read=self._stations_read, data_updated_at=newest(updated))

    #: the cells of the rows chosen that `all` lets pile up before it makes the first rows of the groups that span
    #: stations of them, or fewer where the limit it was given is lower
    _COMPACT_CELLS = 1_000_000

    def _hold(
        self, selection: RowSelection, rows: int, cells: int, data: list[pl.DataFrame]
    ) -> tuple[int, int, list[pl.DataFrame]]:
        """Keep what `all` holds of the rows chosen bounded, and stop a walk that has chosen more than it may hold.

        The rows are what the limit and `max_rows` count, one unit throughout: a row of the frame. The cells (a long row
        is one, a wide row one for each parameter it holds) are what the memory is, and set when the rows chosen are
        chosen again. Three cases, by where the rows that will be in the answer can come from:

        - a choice that stays in a station (a `filter` alone, a `sort`, or `first` with `station_id` in `by`) is the
          answer as it is read: a station's rows that match are held as they arrive and the rest let go, and more rows
          than the limit are an answer that is refused, now and not after the last station (`RowsOverLimitError`);
        - the same with `max_rows` and a `sort`: every station holds up to `max_rows` rows and a hundred stations
          hold a hundred times that, of which only the first `max_rows` in the answer's order can matter, so what is
          held is cut to them once it is twice as many rows;
        - groups that span stations: the first rows of a group are among those of its parts, so the choice is made
          again over what was chosen, which gives the same rows. It is done when the held cells double what the last
          time left (never before a million, or the limit where that is lower), so that the work is of the order of
          the rows read and not of their square. Rows that remain above the limit after it are refused, as a group that
          ties over many stations (every dry day at 0.0 mm) has no bound but its rows: add a column to `sort`.

        Gives the rows and cells held and the frames, which are the same ones unless the choice was made again.
        """
        limit = self._held_rows_limit
        if selection.per_station:
            if selection.max_rows is not None:
                if selection.sort and rows > 2 * selection.max_rows:
                    compact = selection.cap_held(selection.finish(data))
                    return compact.height, _cells(compact), [compact]
                return rows, cells, data
            if limit and rows > limit:
                raise RowsOverLimitError(rows, limit)
            return rows, cells, data
        base = min(self._COMPACT_CELLS, limit) if limit else self._COMPACT_CELLS
        if cells >= max(base, 2 * self._compacted_cells):
            compact = selection.finish(data)
            held = _cells(compact)
            self._compacted_cells = held
            if limit and compact.height > limit:
                raise RowsOverLimitError(compact.height, limit)
            return compact.height, held, [compact]
        return rows, cells, data

    def to_target(self, target: str, if_exists: Literal["replace", "append", "fail", "skip"] = "fail") -> None:
        """Wrap to_target of all queried results.

        `if_exists` is for the first station and defaults to 'fail', where a result's `to_target` defaults to
        'replace': this is one table being filled station by station rather than one frame being written, so the
        first station must not overwrite a table that already holds data. Every station after it is appended.

        Raises:
            ExportRefusedError: `if_exists` is none of the four words, told before any station is downloaded.

        """
        # the sinks import the results, which import this module
        from wetterdienst.io.sinks import refuse_unknown_if_exists  # noqa: PLC0415

        refuse_unknown_if_exists(if_exists)
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

    def _given_timestamps(self, parameter: ParameterModel) -> pl.Series | None:  # noqa: ARG002
        """Name the steps at which the source gives a parameter at the station in hand, for `skip_empty`, or None.

        Implemented by a provider whose product gives an element at some steps of its resolution only, which a share
        measured against every step of the grid (`_get_actual_percentage`) would read as a station that lacks values
        (MOSMIX-L's `TX` every 12th hour, MOSMIX-SNOW's `SnCv` every 3rd, GH-4093). Called once per parameter of the
        request after the station was collected, for the station in hand; it must not download. The steps are
        timestamps (a UTC datetime series, or None for no say) of the readings the file the station was read from
        gives, whether this station has a value there or not, in the timezone of the frames the provider returns; the
        share is then the distinct slots of the resolution among them that the station has a value at, of those that
        lie in the window (or the span of the station's series). An empty series is a parameter given at no step at all,
        which counts as zero, as a parameter that came back with nothing does. A parameter given at steps, none of them
        in the window, is not measured: there is nothing to share, so it is left out of `skip_criteria`'s min, mean and
        max beside the parameters that are measured (a source that gives an element at 06 and 18 UTC has no say about a
        window of 07 to 17). A station whose every parameter is left out has nothing in the window and is skipped, as
        it is whatever `drop_nulls` and the shape are.

        The steps are the file's own, so an element that ends before the run does cannot be told from one that is given
        so: its last step is whichever the file last gives, and a station that has them all is complete. No real file
        has such an element (MOSMIX-L and MOSMIX-S, 2026-11-17: every element reaches the last step of its cadence),
        and `docs/data/provider/dwd/mosmix/elements/index.md` lists them. An element the file gives at no step for the
        station (`DRR1` at 10961, the Zugspitze) is an empty series: zero coverage, and `skip_empty` (with
        `skip_criteria` "min") skips the station.

        Not implemented, which is what a provider that does not name its steps does, the steps are every slot of the
        resolution's grid over the window, as they always were.
        """
        return None

    @staticmethod
    def _share_of_given_steps(
        df_parameter: pl.DataFrame,
        given: pl.Series,
        interval: str,
        window: tuple[dt.datetime | None, dt.datetime | None],
    ) -> float | None:
        """Give the share of the slots the source gives a parameter at, in the window, the station has a value at.

        None where the source gives the parameter at steps and none of them lies in the window: nothing to measure.
        """
        if given.is_empty():
            return 0.0
        slots = given.cast(df_parameter.schema["timestamp"]).to_frame("timestamp")
        start_date, end_date = window
        if start_date is not None and end_date is not None:
            slots = slots.filter(pl.col("timestamp").is_between(start_date, end_date, closed="both"))
        expected = slots.select(pl.col("timestamp").dt.truncate(interval).unique()).get_column("timestamp")
        if expected.is_empty():
            return None
        covered = df_parameter.drop_nulls("value").get_column("timestamp").dt.truncate(interval)
        return min(covered.filter(covered.is_in(expected.implode())).n_unique() / expected.len(), 1.0)

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
        alone, as an interpolation does.
        """
        # a station that returned nothing inside the window covers none of it, and there is no
        # frame under the question to read a span or a dtype off
        if df.is_empty():
            return 0.0
        # a value a soft plausibility check flagged suspect is no coverage: a station with only such values is skipped,
        # whatever the mode (GH-3676). As it was where the check used to null the value; a road sensor that stopped,
        # which kept its value and counted, no longer counts
        df = leave_out_suspect(df)
        # None for a parameter that is not measured (`_share_of_given_steps`)
        percentages: list[float | None] = []
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
            interval = reading_interval(resolution.value)
            # a source that names the steps it gives the parameter at is measured against those, not against every
            # slot of the grid (`_given_timestamps`)
            given = self._given_timestamps(parameter) if interval is not None else None
            if given is not None and interval is not None:
                percentages.append(self._share_of_given_steps(df_parameter, given, interval, (start_date, end_date)))
                continue
            expected = (
                count_readings(resolution.value, start_date, end_date)
                if start_date is not None and end_date is not None
                else None
            )
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
        measured = [percentage for percentage in percentages if percentage is not None]
        if not measured:
            # every parameter was left unmeasured (`_given_timestamps` names none in the window), or there is none: the
            # station has nothing in the window and is skipped, as it is with the nulls dropped (an empty frame) and
            # as it was before the steps were named. Not measured only means a parameter has no say beside the others
            return 0.0
        if self.sr.options.skip_criteria == "min":
            return min(measured)
        if self.sr.options.skip_criteria == "mean":
            return sum(measured) / len(measured)
        if self.sr.options.skip_criteria == "max":
            return max(measured)
        msg = "skip_criteria must be one of min, mean, max"
        raise KeyError(msg)
