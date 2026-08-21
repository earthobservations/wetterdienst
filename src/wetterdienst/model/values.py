# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Core for sources of timeseries where data is related to a station."""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from itertools import groupby
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast

import polars as pl
from tqdm import tqdm
from tzfpy import get_tz

from wetterdienst.metadata.resolution import count_readings, reading_interval
from wetterdienst.model.result import StationsResult, ValuesResult
from wetterdienst.model.unit import UnitConverter
from wetterdienst.util.logging import TqdmToLogger

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Callable, Iterable, Iterator

    from wetterdienst.model.metadata import DatasetModel, ParameterModel

try:
    from backports.datetime_fromisoformat import MonkeyPatch
except ImportError:
    pass
else:
    MonkeyPatch.patch_fromisoformat()

log = logging.getLogger(__name__)


@dataclass
class TimeseriesValues(ABC):
    """Core for sources of timeseries where data is related to a station."""

    sr: StationsResult
    stations_counter: int = 0
    stations_collected: list[str] = field(default_factory=list)
    unit_converter: UnitConverter = field(default_factory=UnitConverter)

    # Fields for date coercion
    _date_fields: ClassVar = ["date", "start_date", "end_date"]

    def __post_init__(self) -> None:
        """Post-initialization of the TimeseriesValues object."""
        self.unit_converter.update_targets(self.sr.settings.ts_unit_targets)

    @classmethod
    def from_stations(cls, stations: StationsResult) -> TimeseriesValues:
        """Create a new instance of the class from a StationsResult object."""
        return cls(stations)

    # Fields for type coercion, needed for separation from fields with actual data
    # that have to be parsed differently when having data in tabular form
    @property
    def _meta_fields(self) -> dict[str, Any]:
        """Get metadata fields for the DataFrame."""
        if not self.sr.settings.ts_tidy:
            return {
                "station_id": pl.String,
                "resolution": pl.String,
                "dataset": pl.String,
                "date": pl.Datetime(time_zone="UTC"),
            }
        return {
            "station_id": pl.String,
            "resolution": pl.String,
            "dataset": pl.String,
            "parameter": pl.String,
            "date": pl.Datetime(time_zone="UTC"),
            "value": pl.Float64,
            "quality": pl.Float64,
        }

    def _get_timezone_from_station(self, station_id: str) -> str:
        """Get timezone information for explicit station.

        This is used to set the correct timezone for the timestamps of the returned values.

        """
        stations = self.sr.df
        longitude, latitude = (
            stations.filter(pl.col("station_id").eq(station_id))
            .select([pl.col("longitude"), pl.col("latitude")])
            .transpose()
            .to_series()
            .to_list()
        )
        return get_tz(longitude, latitude)

    def _convert_units(self, df: pl.DataFrame, dataset: DatasetModel) -> pl.DataFrame:
        """Convert values to metric units with help of conversion factors."""
        if df.is_empty():
            return df

        # create lambdas here because not every parameter exists in DataFrame
        # and we can just use the name of the parameter to get the conversion factor
        # without going back to the dataset model
        conversion_factors = self._create_conversion_lambdas(dataset)

        data = []
        for (parameter,), df_group in df.group_by(
            ["parameter"],
            maintain_order=True,
        ):
            lambda_ = conversion_factors[parameter.lower()]
            # round by 4 decimals to avoid long floats but keep precision
            df_group = df_group.with_columns(pl.col("value").map_batches(lambda_, return_dtype=pl.Float64).round(4))
            data.append(df_group)

        return pl.concat(data)

    def _create_conversion_lambdas(
        self,
        dataset: DatasetModel,
    ) -> dict[str, Callable[[Any], Any]]:
        """Create conversion factors based on a given dataset."""
        lambdas = {}
        for parameter in dataset:
            lambdas[parameter.name_original.lower()] = self.unit_converter.get_lambda(
                parameter.unit,
                parameter.unit_type,
            )
        return lambdas

    def _organize_df_columns(self, df: pl.DataFrame, station_id: str, dataset: DatasetModel) -> pl.DataFrame:
        """Reorder columns in DataFrame to match the expected order of columns."""
        columns = list(self._meta_fields.keys())
        columns.extend(set(df.columns).difference(columns))
        df = df.with_columns(
            pl.lit(station_id).alias("station_id"),
            pl.lit(dataset.resolution.name).alias("resolution"),
            pl.lit(dataset.name.lower()).alias("dataset"),
        )
        return df.select(pl.col(col) if col in df.columns else pl.lit(None).alias(col) for col in columns)

    # low-cardinality metadata columns that are stored as Enum instead of String to save memory
    _meta_enum_columns: ClassVar = ("station_id", "resolution", "dataset", "parameter")

    @classmethod
    def _cast_metadata_to_enum(cls, df: pl.DataFrame) -> pl.DataFrame:
        """Cast the low-cardinality metadata columns to ``Enum`` to reduce the memory footprint.

        The categories are taken from the values actually present in the frame (not from the
        request metadata), so the cast never fails on provider-specific casing or humanization
        quirks (e.g. WSV emitting ``w`` while the metadata declares ``W``). These columns repeat
        every row, so integer-backed ``Enum`` codes roughly halve the size of tidy value frames.
        """
        return df.with_columns(
            # nulls are dropped from the categories rather than carried into them: `Enum` rejects a
            # null category outright, and a null here is a column that does not describe the row --
            # a wide frame spanning several datasets has no one dataset name to put in the column
            pl.col(column).cast(pl.Enum(df.get_column(column).drop_nulls().unique().sort()))
            for column in cls._meta_enum_columns
            if column in df.columns
        )

    def query(self) -> Iterator[ValuesResult]:
        """Query data for all stations and parameters and return a DataFrame for each station."""
        # reset station stations_counter
        self.stations_counter = 0
        self.stations_collected = []
        # mapping of original to humanized parameter names is always the same
        hpm: dict[str, str] = {}
        if self.sr.settings.ts_humanize:
            hpm = self._create_humanized_parameters_mapping()
        for (station_id,), df_station_meta in self.sr.df.group_by(["station_id"], maintain_order=True):
            if self.stations_counter == self.sr.rank:
                break
            station_id = cast("str", station_id)
            available_datasets = self._get_available_datasets(df_station_meta)
            # Collect data for this station
            df = self._collect_station_data(station_id, available_datasets)
            # Skip if no data found
            if df.is_empty():
                continue
            if self.sr.start_date:
                df = df.filter(
                    pl.col("date").is_between(
                        self.sr.start_date,
                        self.sr.end_date,
                        closed="both",
                    ),
                )
            if self.sr.settings.ts_skip_empty:
                percentage = self._get_actual_percentage(df=df)
                if percentage < self.sr.settings.ts_skip_threshold:
                    log.info(
                        f"station {station_id} is skipped as percentage of actual values ({percentage}) "
                        f"is below threshold ({self.sr.settings.ts_skip_threshold}).",
                    )
                    continue
            if self.sr.settings.ts_humanize:
                df = self._humanize(df=df, humanized_parameters_mapping=hpm)
            if not self.sr.settings.ts_tidy:
                df = self._widen_df(df=df)
            # sorted by resolution first in either shape: two resolutions are two series, and
            # sorting by the dataset alone interleaves them when they share one -- an hourly and a
            # 10-minute precipitation series came out shuffled into each other. `unique()` in
            # `_widen_df` leaves the wide rows in no particular order to begin with.
            sort_columns = (
                ["resolution", "dataset", "parameter", "date"]
                if self.sr.settings.ts_tidy
                else ["resolution", "dataset", "date"]
            )
            df = df.sort(sort_columns)
            self.stations_counter += 1
            self.stations_collected.append(station_id)
            yield ValuesResult(stations=self.sr, values=self, df=df)

    def _get_available_datasets(self, df: pl.DataFrame) -> list[DatasetModel]:
        """Extract available datasets for the station."""
        resolution_dataset_pairs = (
            df.select(["resolution", "dataset"]).unique().sort(["resolution", "dataset"]).rows(named=True)
        )
        return [self.sr.stations.metadata[pair["resolution"]][pair["dataset"]] for pair in resolution_dataset_pairs]

    def _collect_station_data(self, station_id: str, available_datasets: list[DatasetModel]) -> pl.DataFrame:
        """Collect and process data for a single station."""
        if not available_datasets:
            return pl.DataFrame()
        data = []
        # self.sr.stations.parameters is parsed at runtime to a list[ParameterModel],
        # but the static type of the attribute is a union of input forms. Cast here so
        # the typechecker understands we iterate ParameterModel instances.
        for dataset, parameters in groupby(
            cast("Iterable[ParameterModel]", self.sr.stations.parameters), key=lambda x: x.dataset
        ):
            if dataset not in available_datasets:
                continue
            df = self._process_dataset(station_id, dataset, parameters)
            if not df.is_empty():
                data.append(df)
        return pl.concat(data) if data else pl.DataFrame()

    def _process_dataset(
        self, station_id: str, dataset: DatasetModel, parameters: Iterator[ParameterModel]
    ) -> pl.DataFrame:
        """Process data for a specific dataset."""
        if dataset.grouped:
            df = self._collect_station_parameter_or_dataset(
                station_id=station_id,
                parameter_or_dataset=dataset,
            )
            if not df.is_empty():
                parameter_names = {parameter.name_original for parameter in parameters}
                df = df.filter(pl.col("parameter").is_in(parameter_names))
        else:
            data = []
            for parameter in parameters:
                df = self._collect_station_parameter_or_dataset(
                    station_id=station_id,
                    parameter_or_dataset=parameter,
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
        if self.sr.settings.ts_convert_units:
            df = self._convert_units(df, dataset)
        df = df.unique(subset=["resolution", "dataset", "parameter", "date"], maintain_order=True)
        if self.sr.settings.ts_drop_nulls:
            df = df.drop_nulls(subset=["value"])
        return self._organize_df_columns(df, station_id, dataset)

    @abstractmethod
    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel | DatasetModel,
    ) -> pl.DataFrame:
        """Collect data for a station and a single parameter or dataset."""

    def _widen_df(self, df: pl.DataFrame) -> pl.DataFrame:
        """Widen a dataframe with each row having one timestamp, parameter, value and quality.

        Example:
        date         parameter                  value   quality
        1971-01-01   precipitation_height       0       0
        1971-01-01   temperature_air_mean_2m   10      0

        becomes

        date         precipitation_height   qn_precipitation_height
        1971-01-01   0                      0
            temperature_air_mean_2m    ...
            10                          ...

        Args:
            df: DataFrame with columns date, parameter, value and quality.

        Returns:
            DataFrame with columns date, parameter, value and quality as columns.

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
        df_wide = df.select(pl.col("station_id"), pl.col("resolution"), dataset, pl.col("date")).unique()

        if not df.is_empty():
            for (parameter,), df_parameter in df.group_by(["parameter"], maintain_order=True):
                # Build quality column name
                parameter_quality = f"qn_{parameter}"
                df_parameter = df_parameter.select(["resolution", "date", "value", "quality"])
                df_parameter = df_parameter.rename(
                    mapping={"value": parameter, "quality": parameter_quality},
                )
                # left, not inner: a parameter that has no reading at a timestamp another parameter
                # does have one at must leave a null behind rather than take the whole timestamp
                # out of the frame. Chained inner joins reduced the frame to the timestamps every
                # requested parameter shared, which silently dropped readings that were asked for
                # -- three quarters of a 15-minute series joined against an hourly one
                df_wide = df_wide.join(df_parameter, on=["resolution", "date"], how="left")
        else:
            for parameter in self.sr.parameters:
                parameter_name = parameter.name_original if not self.sr.settings.ts_humanize else parameter.name
                parameter_quality = f"qn_{parameter_name}"
                df_wide = df_wide.with_columns(
                    pl.lit(None, pl.Float64).alias(parameter_name),
                    pl.lit(None, pl.Float64).alias(parameter_quality),
                )

        return df_wide

    def all(self) -> ValuesResult:
        """Collect all data for all stations and parameters and return a single DataFrame."""
        data = []

        tqdm_out = TqdmToLogger(log, level=logging.INFO)

        for result in tqdm(self.query(), total=len(self.sr.station_id), file=tqdm_out):
            data.append(result.df)

        try:
            df = pl.concat(data, how="diagonal")
        except ValueError:
            log.exception("No data available for given constraints")
            return ValuesResult(stations=self.sr, values=self, df=pl.DataFrame())

        # store the low-cardinality metadata columns as Enum to reduce the memory footprint of the
        # aggregated result; done once here on the full frame, with categories from the actual data
        df = self._cast_metadata_to_enum(df)

        return ValuesResult(stations=self.sr, values=self, df=df)

    def to_target(self, target: str, if_exists: Literal["replace", "append", "fail", "skip"] = "fail") -> None:
        """Wrap to_target of all queried results."""
        tqdm_out = TqdmToLogger(log, level=logging.INFO)
        for i, result in tqdm(enumerate(self.query()), total=len(self.sr.station_id), file=tqdm_out):
            result.to_target(target, if_exists=if_exists if i == 0 else "append")
            log.info(f"Exported data for station {result.df.get_column('station_id').unique()[0]} to {target}.")

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
            start_date, end_date = self.sr.start_date, self.sr.end_date
            if (start_date is None or end_date is None) and not df_dataset.is_empty():
                dates = df_dataset.get_column("date")
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
            covered = df_parameter.drop_nulls("value").get_column("date").dt.truncate(interval).n_unique()
            percentages.append(min(covered / expected, 1.0))
        if not percentages:
            return 0.0
        if self.sr.settings.ts_skip_criteria == "min":
            return min(percentages)
        if self.sr.settings.ts_skip_criteria == "mean":
            return sum(percentages) / len(percentages)
        if self.sr.settings.ts_skip_criteria == "max":
            return max(percentages)
        msg = "ts_skip_criteria must be one of min, mean, max"
        raise KeyError(msg)
