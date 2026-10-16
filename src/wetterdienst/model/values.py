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

from wetterdienst.metadata.resolution import count_readings, reading_interval
from wetterdienst.model.metadata import group_parameters_by_dataset
from wetterdienst.model.quality_flags import QUALITY_FLAGS, RAW_TOKEN
from wetterdienst.model.result import StationsResult, ValuesResult
from wetterdienst.model.schema import (
    LONG_SCHEMA,
    WIDE_FLAGS_DTYPE,
    WIDE_FLAGS_SUFFIX,
    WIDE_SCHEMA,
    WIDE_VALUE_DTYPE,
)
from wetterdienst.model.unit import UnitConverter
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


@dataclass
class TimeseriesValues(ABC, Generic[_UnitT]):
    """Core for sources of timeseries where data is related to a station.

    Subscript it with the model the provider collects by -- `TimeseriesValues[DatasetModel]` -- so that
    `_collect_station_parameter_or_dataset` is declared as the narrow signature the provider implements.
    """

    sr: StationsResult
    stations_counter: int = 0
    stations_collected: list[str] = field(default_factory=list)
    unit_converter: UnitConverter = field(default_factory=UnitConverter)

    def __post_init__(self) -> None:
        """Post-initialization of the TimeseriesValues object."""
        self.unit_converter.update_targets(self.sr.options.unit_targets)

    @classmethod
    def from_stations(cls, stations: StationsResult) -> TimeseriesValues:
        """Create a new instance of the class from a StationsResult object."""
        return cls(stations)

    @property
    def _meta_fields(self) -> pl.Schema:
        """Get the schema of the columns that describe a row: all of the long form, or the wide form's own."""
        return LONG_SCHEMA if self.sr.options.tidy else WIDE_SCHEMA

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

    def _organize_df_columns(self, df: pl.DataFrame, station_id: str, dataset: DatasetModel) -> pl.DataFrame:
        """Reorder columns in DataFrame to match the expected order of columns."""
        columns = list(self._meta_fields)
        columns.extend(set(df.columns).difference(columns))
        # the wide form lists no value columns among the meta fields, so the flags are asked for by name
        if "quality_flags" not in columns:
            columns.append("quality_flags")
        df = df.with_columns(
            pl.lit(station_id).alias("station_id"),
            pl.lit(dataset.resolution.name).alias("resolution"),
            pl.lit(dataset.name.lower()).alias("dataset"),
        )
        # a column the provider did not deliver is a typed null where the long form declares it: the
        # providers that publish no flag leave `quality_flags` out, and an untyped null would not
        # concatenate with the String column of those that do
        return df.select(
            pl.col(col) if col in df.columns else pl.lit(None, dtype=LONG_SCHEMA.get(col)).alias(col) for col in columns
        )

    def query(self) -> Iterator[ValuesResult]:
        """Query data for all stations and parameters and return a DataFrame for each station."""
        # reset station stations_counter
        self.stations_counter = 0
        self.stations_collected = []
        # mapping of original to humanized parameter names is always the same
        hpm: dict[str, str] = {}
        if self.sr.options.humanize:
            hpm = self._create_humanized_parameters_mapping()
        for (station_id,), df_station_meta in self.sr.df.group_by(["station_id"], maintain_order=True):
            if self.stations_counter == self.sr.rank:
                break
            station_id = cast("str", station_id)
            if self._begins_after_window(df_station_meta):
                continue
            available_datasets = self._get_available_datasets(df_station_meta)
            # Collect data for this station
            df = self._filter_by_window(self._collect_station_data(station_id, available_datasets))
            # judged after the window has been cut, not before it: a station whose record lies
            # entirely outside the requested window returned data, but none that was asked for.
            # Counting it as collected spent one of `filter_by_rank`'s slots on an empty frame, so
            # the ranked walk stopped short of the stations that do cover the window and the
            # request came back with nothing
            if df.is_empty():
                continue
            if self.sr.options.skip_empty:
                percentage = self._get_actual_percentage(df=df)
                if percentage < self.sr.options.skip_threshold:
                    warn_response(
                        log,
                        "station-skipped",
                        f"station {station_id} is skipped as percentage of actual values ({percentage}) "
                        f"is below threshold ({self.sr.options.skip_threshold}).",
                        level=logging.INFO,
                    )
                    continue
            if self.sr.options.humanize:
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
            self.stations_counter += 1
            self.stations_collected.append(station_id)
            yield ValuesResult(stations=self.sr, df=df)

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

    def _get_available_datasets(self, df: pl.DataFrame) -> list[DatasetModel]:
        """Extract available datasets for the station."""
        resolution_dataset_pairs = (
            df.select(["resolution", "dataset"]).unique().sort(["resolution", "dataset"]).rows(named=True)
        )
        return [self.sr.request.metadata[pair["resolution"]][pair["dataset"]] for pair in resolution_dataset_pairs]

    def _collect_station_data(self, station_id: str, available_datasets: list[DatasetModel]) -> pl.DataFrame:
        """Collect and process data for a single station."""
        if not available_datasets:
            return pl.DataFrame()
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
        return pl.concat(data) if data else pl.DataFrame()

    def _process_dataset(
        self, station_id: str, dataset: DatasetModel, parameters: Sequence[ParameterModel]
    ) -> pl.DataFrame:
        """Process data for a specific dataset."""
        if dataset.grouped:
            df = self._collect_station_parameter_or_dataset(
                station_id=station_id,
                # a dataset marked `grouped` is collected as a whole: the provider asked for it by
                # saying so, and the type parameter is what it said it would be handed
                parameter_or_dataset=cast("_UnitT", dataset),
            )
            if not df.is_empty():
                parameter_names = {parameter.name_original for parameter in parameters}
                df = df.filter(pl.col("parameter").is_in(parameter_names))
        else:
            data = []
            for parameter in parameters:
                df = self._collect_station_parameter_or_dataset(
                    station_id=station_id,
                    parameter_or_dataset=cast("_UnitT", parameter),
                )
                # a parameter with no data for this station yields a bare frame with no columns,
                # which cannot be concatenated with the populated ones -- polars raises
                # "unable to append to a DataFrame of width 6 with a DataFrame of width 0". It
                # contributes no rows either way, so drop it rather than let one absent parameter
                # fail the whole request.
                if not df.is_empty():
                    data.append(df)
            df = pl.concat(data) if data else pl.DataFrame()
        if df.is_empty():
            return df
        if self.sr.options.convert_units:
            df = self._convert_units(df, dataset)
        df = df.unique(subset=["resolution", "dataset", "parameter", "timestamp"], maintain_order=True)
        if QUALITY_FLAGS in df.columns:
            # the readings the source marked as missing may leave with the nulls; the answer still tells how many
            count_response_warning(
                MISSING_VALUE_MARKER,
                df.filter(pl.col("value").is_null() & pl.col(QUALITY_FLAGS).str.contains(RAW_TOKEN)).height,
                MISSING_VALUE_MARKER_MESSAGE,
            )
        if self.sr.options.drop_nulls_effective:
            df = df.drop_nulls(subset=["value"])
        return self._organize_df_columns(df, station_id, dataset)

    @abstractmethod
    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: _UnitT,
    ) -> pl.DataFrame:
        """Collect data for a station and a single parameter or dataset."""

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
        (`quality_temperature_air_max_2m` and ten more like it); those never become value columns,
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
            datasets_by_resolution[parameter.dataset.resolution.name].add(parameter.dataset.name)
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
            requested.append(f"{parameter.dataset.name}_{name}" if len(datasets) > 1 else name)
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

        tqdm_out = TqdmToLogger(log, level=logging.INFO)

        for result in tqdm(self.query(), total=len(self.sr.station_id), file=tqdm_out):
            data.append(result.df)

        if not data:
            # an ordinary outcome -- no station covered the requested window -- rather than an
            # error, so it is logged as one and does not print a traceback. The frame still carries
            # its schema: a caller writes it out as a header row, asks it for a column or
            # concatenates it against a populated frame, and none of that survives a frame with no
            # columns at all
            log.info("No data available for given constraints")
            return ValuesResult(stations=self.sr, df=self._empty_values_df())

        df = pl.concat(data, how="diagonal")

        return ValuesResult(stations=self.sr, df=df)

    def to_target(self, target: str, if_exists: Literal["replace", "append", "fail", "skip"] = "fail") -> None:
        """Wrap to_target of all queried results."""
        tqdm_out = TqdmToLogger(log, level=logging.INFO)
        redacted = redact_password(target)
        for i, result in tqdm(enumerate(self.query()), total=len(self.sr.station_id), file=tqdm_out):
            result.to_target(target, if_exists=if_exists if i == 0 else "append")
            log.info(f"Exported data for station {result.df.get_column('station_id').unique()[0]} to {redacted}.")

    @staticmethod
    def _humanize(df: pl.DataFrame, humanized_parameters_mapping: dict[str, str]) -> pl.DataFrame:
        """Humanize parameter names in a DataFrame."""
        return df.with_columns(pl.col("parameter").replace(humanized_parameters_mapping))

    def _create_humanized_parameters_mapping(self) -> dict[str, str]:
        """Create mapping of original to humanized parameter names."""
        return {parameter.name_original: parameter.name for parameter in self.sr.parameters}

    def _get_actual_percentage(self, df: pl.DataFrame) -> float:
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

        A parameter that was asked for and came back with nothing counts as zero rather than
        going unmeasured: a request for two parameters where one is missing is not fully covered.
        """
        # a station that returned nothing inside the window covers none of it, and there is no
        # frame under the question to read a span or a dtype off
        if df.is_empty():
            return 0.0
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
                # matched case-insensitively: a provider is free to emit a name in its own casing
                # (WSV reports `w` where its metadata declares `W`), and an exact match there
                # counts a parameter that is present as missing and skips the station over it
                pl.col("parameter").str.to_lowercase().eq(parameter.name_original.lower()),
            )
            start_date, end_date = self.sr.start, self.sr.end
            if (start_date is None or end_date is None) and not df_dataset.is_empty():
                dates = df_dataset.get_column("timestamp")
                start_date, end_date = cast("dt.datetime", dates.min()), cast("dt.datetime", dates.max())
            expected = (
                count_readings(resolution.value, start_date, end_date)
                if start_date is not None and end_date is not None
                else None
            )
            interval = reading_interval(resolution.value)
            if not expected or interval is None:
                percentages.append(
                    df_parameter.get_column("value").drop_nulls().len() / df_parameter.height
                    if df_parameter.height
                    else 0.0,
                )
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
