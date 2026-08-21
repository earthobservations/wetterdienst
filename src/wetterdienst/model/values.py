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
from zoneinfo import ZoneInfo

import polars as pl
from dateutil.relativedelta import relativedelta
from tqdm import tqdm
from tzfpy import get_tz

from wetterdienst.metadata.resolution import DAILY_AT_MOST, Frequency, Resolution
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

    @property
    def timezone_data(self) -> str:
        """Get timezone data for the station."""
        return self.sr.stations.metadata.timezone_data

    def _adjust_start_end_date(
        self,
        start_date: dt.datetime,
        end_date: dt.datetime,
        tzinfo: ZoneInfo,
        resolution: Resolution,
    ) -> tuple[dt.datetime, dt.datetime]:
        """Adjust start and end date for a given resolution."""
        # cut of everything smaller than day for daily or lower freq, same for monthly and annual
        if resolution in DAILY_AT_MOST:
            start_date = start_date.replace(
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            end_date = end_date.replace(
                hour=23,
                minute=59,
                second=0,
                microsecond=0,
            )
        elif resolution == Resolution.MONTHLY:
            start_date = start_date.replace(
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            end_date = end_date + relativedelta(months=1) - relativedelta(days=1)
        elif resolution == Resolution.ANNUAL:
            start_date = start_date.replace(
                month=1,
                day=1,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )
            end_date = end_date.replace(
                month=1,
                day=31,
                hour=0,
                minute=0,
                second=0,
                microsecond=0,
            )

        return start_date.replace(tzinfo=tzinfo), end_date.replace(tzinfo=tzinfo)

    def _get_complete_dates(self, start_date: dt.datetime, end_date: dt.datetime, resolution: Resolution) -> pl.Series:
        """Get a complete date range for a given start and end date and resolution."""
        date_range = pl.datetime_range(start_date, end_date, interval=Frequency[resolution.name].value, eager=True)
        if resolution not in DAILY_AT_MOST:
            date_range = date_range.dt.replace(day=1)
        date_range = date_range.dt.cast_time_unit("us")
        return date_range.dt.convert_time_zone("UTC")

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

    def _get_base_df(self, start_date: dt.datetime, end_date: dt.datetime, resolution: Resolution) -> pl.DataFrame:
        """Create a base DataFrame with all dates for a given station."""
        return pl.DataFrame(
            {"date": self._get_complete_dates(start_date, end_date, resolution)},
            orient="col",
        )

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

    def _build_complete_df(self, df: pl.DataFrame, station_id: str, resolution: Resolution) -> pl.DataFrame:
        """Build a complete DataFrame with all dates for a given station."""
        if df.is_empty():
            return df
        if self.timezone_data == "dynamic":
            tzinfo = ZoneInfo(self._get_timezone_from_station(station_id))
        else:
            tzinfo = ZoneInfo(self.timezone_data)
        if self.sr.start_date is None or self.sr.end_date is None:
            msg = "start_date and end_date must be set for building complete DataFrame"
            raise ValueError(msg)
        start_date, end_date = self._adjust_start_end_date(self.sr.start_date, self.sr.end_date, tzinfo, resolution)
        base_df = self._get_base_df(start_date, end_date, resolution)
        data = []
        for (parameter,), df_group in df.group_by(
            ["parameter"],
            maintain_order=True,
        ):
            df_group = base_df.join(
                other=df_group,
                on=["date"],
                how="left",
            )
            df_group = df_group.with_columns(
                pl.lit(station_id).alias("station_id"),
                pl.lit(parameter).alias("parameter"),
            )
            data.append(df_group)
        return pl.concat(data)

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
        elif self.sr.settings.ts_complete and self.sr.start_date and dataset.resolution.value != Resolution.DYNAMIC:
            df = self._build_complete_df(df, station_id, dataset.resolution.value)
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
        """Get the percentage of actual values in the DataFrame.

        This is used to skip stations with too many missing values.
        """
        percentage = df.group_by(["parameter"]).agg(
            (pl.col("value").drop_nulls().len() / pl.col("value").len()).cast(pl.Float64).alias("perc"),
        )
        missing = pl.DataFrame(
            [
                {"parameter": parameter.name_original, "perc": 0.0}
                for parameter in self.sr.parameters
                if parameter.name_original not in percentage.get_column("parameter")
            ],
            schema={"parameter": pl.String, "perc": pl.Float64},
        )
        percentage = pl.concat([percentage, missing])
        if self.sr.settings.ts_skip_criteria == "min":
            return cast("float", percentage.get_column("perc").min() or 0.0)
        if self.sr.settings.ts_skip_criteria == "mean":
            return cast("float", percentage.get_column("perc").mean() or 0.0)
        if self.sr.settings.ts_skip_criteria == "max":
            return cast("float", percentage.get_column("perc").max() or 0.0)
        msg = "ts_skip_criteria must be one of min, mean, max"
        raise KeyError(msg)
