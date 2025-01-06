# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import logging
from abc import ABCMeta, abstractmethod
from itertools import groupby
from textwrap import dedent
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import polars as pl
from dateutil.relativedelta import relativedelta
from tqdm import tqdm
from tzfpy import get_tz

from wetterdienst.core.timeseries.result import StationsResult, ValuesResult
from wetterdienst.core.timeseries.unit import UnitConverter
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.resolution import DAILY_AT_MOST, Frequency, Resolution
from wetterdienst.util.logging import TqdmToLogger

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Callable, Iterator

    from wetterdienst.core.timeseries.metadata import DatasetModel, ParameterModel

try:
    from backports.datetime_fromisoformat import MonkeyPatch
except ImportError:
    pass
else:
    MonkeyPatch.patch_fromisoformat()

log = logging.getLogger(__name__)


class TimeseriesValues(metaclass=ABCMeta):
    """Core for sources of point data where data is related to a station"""

    def __init__(self, stations_result: StationsResult) -> None:
        self.sr = stations_result
        self.stations_counter = 0
        self.stations_collected = []
        self.unit_converter = UnitConverter()
        self.unit_converter.update_targets(self.sr.settings.ts_unit_targets)

    @classmethod
    def from_stations(cls, stations: StationsResult):
        return cls(stations)

    def __eq__(self, other):
        """Equal method of request object"""
        return self.sr.stations == other.sr.stations and self.sr.station_id == other.sr.station

    def __repr__(self):
        """Representation of values object"""
        parameters_joined = ",".join(
            f"({parameter.dataset.resolution.name}/{parameter.dataset.name}/{parameter.name})"
            for parameter in self.sr.stations.parameters
        )
        station_ids_joined = ", ".join(self.sr.station_id.to_list())
        return dedent(
            f"""
            {self.sr.stations.__class__.__name__}Values(
                parameters=[{parameters_joined}],
                start_date={self.sr.start_date and self.sr.start_date.isoformat()},
                end_date={self.sr.end_date and self.sr.end_date.isoformat()},
                station_ids=[{station_ids_joined}],
            )
            """.strip()
        )

    # Fields for type coercion, needed for separation from fields with actual data
    # that have to be parsed differently when having data in tabular form
    @property
    def _meta_fields(self) -> dict[str, str]:
        """
        Metadata fields that are independent of actual values and should be parsed
        differently

        :return: list of strings representing the metadata fields/columns
        """
        if not self.sr.tidy:
            return {
                Columns.STATION_ID.value: str,
                Columns.DATASET.value: str,
                Columns.DATE.value: pl.Datetime(time_zone="UTC"),
            }
        else:
            return {
                Columns.STATION_ID.value: str,
                Columns.DATASET.value: str,
                Columns.PARAMETER.value: str,
                Columns.DATE.value: pl.Datetime(time_zone="UTC"),
                Columns.VALUE.value: pl.Float64,
                Columns.QUALITY.value: pl.Float64,
            }

    # Fields for date coercion
    _date_fields = [Columns.DATE.value, Columns.START_DATE.value, Columns.END_DATE.value]

    # TODO: add data type (mosmix, observation, ...)

    @property
    def timezone_data(self) -> str:
        """Timezone of the published data"""
        return self.sr.stations.metadata.timezone_data

    def _adjust_start_end_date(
        self,
        start_date: dt.datetime,
        end_date: dt.datetime,
        tzinfo: ZoneInfo,
        resolution: Resolution,
    ) -> tuple[dt.datetime, dt.datetime]:
        """Adjust start and end date to the resolution of the service. This is
        necessary for building a complete date range that matches the resolution.
        """
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
        """
        Complete datetime index for the requested start and end date, used for
        building a complementary pandas DataFrame with the date column on which
        other DataFrames can be joined on
        """
        date_range = pl.datetime_range(start_date, end_date, interval=Frequency[resolution.name].value, eager=True)
        if resolution not in DAILY_AT_MOST:
            date_range = date_range.map_elements(lambda date: date.replace(day=1).isoformat(), return_dtype=pl.String)
            date_range = date_range.str.to_datetime()
        date_range = date_range.dt.cast_time_unit("us")
        return date_range.dt.convert_time_zone("UTC")

    def _get_timezone_from_station(self, station_id: str) -> str:
        """
        Get timezone information for explicit station that is used to set the
        correct timezone for the timestamps of the returned values

        :param station_id: station id string
        :return: timezone
        """
        stations = self.sr.df
        longitude, latitude = (
            stations.filter(pl.col(Columns.STATION_ID.value).eq(station_id))
            .select([pl.col(Columns.LONGITUDE.value), pl.col(Columns.LATITUDE.value)])
            .transpose()
            .to_series()
            .to_list()
        )
        return get_tz(longitude, latitude)

    def _get_base_df(self, start_date: dt.datetime, end_date: dt.datetime, resolution: Resolution) -> pl.DataFrame:
        """
        Base dataframe which is used for creating empty dataframes if no data is
        found or for merging other dataframes on the full dates

        :return: pandas DataFrame with a date column with complete dates
        """
        return pl.DataFrame(
            {Columns.DATE.value: self._get_complete_dates(start_date, end_date, resolution)}, orient="col"
        )

    def _convert_units(self, df: pl.DataFrame, dataset: DatasetModel) -> pl.DataFrame:
        """
        Function to convert values to metric units with help of conversion factors

        :param df: pandas DataFrame that should be converted to SI units
        :param dataset: dataset for which the conversion factors are created
        :return: pandas DataFrame with converted (SI) values
        """
        if df.is_empty():
            return df

        # create lambdas here because not every parameter exists in DataFrame
        # and we can just use the name of the parameter to get the conversion factor
        # without going back to the dataset model
        conversion_factors = self._create_conversion_lambdas(dataset)

        data = []
        for (parameter,), group in df.group_by(
            [Columns.PARAMETER.value],
            maintain_order=True,
        ):
            lambda_ = conversion_factors[parameter.lower()]
            # round by 4 decimals to avoid long floats but keep precision
            group = group.with_columns(pl.col(Columns.VALUE.value).map_batches(lambda_).round(4))
            data.append(group)

        return pl.concat(data)

    def _create_conversion_lambdas(
        self,
        dataset: DatasetModel,
    ) -> dict[str, Callable[[Any], Any]]:
        """
        Function to create conversion factors based on a given dataset

        :param dataset: dataset for which conversion factors are created
        :return: dictionary with conversion factors for given parameter name
        """
        lambdas = {}
        for parameter in dataset:
            lambdas[parameter.name_original.lower()] = self.unit_converter.get_lambda(
                parameter.unit, parameter.unit_type
            )
        return lambdas

    def _create_empty_station_df(self, station_id: str, dataset: DatasetModel) -> pl.DataFrame:
        """
        Function to create an empty DataFrame for a station with all parameters
        """
        # if parameter is a whole dataset, take every parameter from the dataset instead
        if not self.sr.start_date:
            return pl.DataFrame(schema=self._meta_fields)

        if self.timezone_data == "dynamic":
            tzinfo = ZoneInfo(self._get_timezone_from_station(station_id))
        else:
            tzinfo = ZoneInfo(self.timezone_data)
        start_date, end_date = self._adjust_start_end_date(
            self.sr.start_date, self.sr.end_date, tzinfo, dataset.resolution.value
        )

        base_df = self._get_base_df(start_date, end_date, dataset.resolution.value)

        data = []
        for parameter in dataset.parameters:
            if parameter.name.startswith("quality"):
                continue
            par_df = base_df.with_columns(pl.lit(parameter.name_original).alias(Columns.PARAMETER.value))
            data.append(par_df)

        df = pl.concat(data)

        return df.with_columns(
            pl.lit(value=station_id, dtype=pl.String).alias(Columns.STATION_ID.value),
            pl.lit(value=None, dtype=pl.Float64).alias(Columns.VALUE.value),
            pl.lit(value=None, dtype=pl.Float64).alias(Columns.QUALITY.value),
        )

    def _build_complete_df(self, df: pl.DataFrame, station_id: str, resolution: Resolution) -> pl.DataFrame:
        """Method to build a complete df with all dates from start to end date included. For cases where requests
        are not defined by start and end date but rather by periods, use the returned df without modifications
        We may put a standard date range here if no data is found

        :param df:
        :param station_id:
        :param parameter:
        :param dataset:
        :return:
        """
        if df.is_empty():
            return df
        if self.timezone_data == "dynamic":
            tzinfo = ZoneInfo(self._get_timezone_from_station(station_id))
        else:
            tzinfo = ZoneInfo(self.timezone_data)
        start_date, end_date = self._adjust_start_end_date(self.sr.start_date, self.sr.end_date, tzinfo, resolution)
        base_df = self._get_base_df(start_date, end_date, resolution)
        data = []
        for (station_id, parameter), group in df.group_by(
            [Columns.STATION_ID.value, Columns.PARAMETER.value],
            maintain_order=True,
        ):
            par_df = base_df.join(
                other=group,
                on=[Columns.DATE.value],
                how="left",
            )
            par_df = par_df.with_columns(
                pl.lit(station_id).alias(Columns.STATION_ID.value),
                pl.lit(parameter).alias(Columns.PARAMETER.value),
            )
            data.append(par_df)
        return pl.concat(data)

    def _organize_df_columns(self, df: pl.DataFrame, station_id: str, dataset: DatasetModel) -> pl.DataFrame:
        """
        Method to reorder index to always have the same order of columns

        :param df:
        :return:
        """
        columns = list(self._meta_fields.keys())
        columns.extend(set(df.columns).difference(columns))
        df = df.with_columns(
            pl.lit(station_id).alias(Columns.STATION_ID.value),
            pl.lit(dataset.name.lower()).alias(Columns.DATASET.value),
        )
        return df.select(pl.col(col) if col in df.columns else pl.lit(None).alias(col) for col in columns)

    def query(self) -> Iterator[ValuesResult]:
        """
        Core method for data collection, iterating of station ids and yielding a
        DataFrame for each station with all found parameters. Takes care of type
        coercion of data, date filtering and humanizing of parameters.

        :return:
        """
        # reset station stations_counter
        self.stations_counter = 0
        self.stations_collected = []

        # mapping of original to humanized parameter names is always the same
        if self.sr.humanize:
            hpm = self._create_humanized_parameters_mapping()

        for station_id in self.sr.station_id:
            if self.stations_counter == self.sr.rank:
                break

            data = []

            for dataset, parameters in groupby(self.sr.stations.parameters, key=lambda x: x.dataset):
                if dataset.grouped:
                    df = self._collect_station_parameter_or_dataset(
                        station_id=station_id,
                        parameter_or_dataset=dataset,
                    )
                    if not df.is_empty():
                        parameter_names = {parameter.name_original for parameter in parameters}
                        df = df.filter(pl.col(Columns.PARAMETER.value).is_in(parameter_names))
                else:
                    dataset_data = []
                    for parameter in parameters:
                        df = self._collect_station_parameter_or_dataset(
                            station_id=station_id,
                            parameter_or_dataset=parameter,
                        )
                        dataset_data.append(df)
                    df = pl.concat(dataset_data)
                    del dataset_data

                if df.is_empty():
                    df = self._create_empty_station_df(station_id=station_id, dataset=dataset)

                if self.sr.convert_units:
                    df = self._convert_units(df, dataset)

                df = df.unique(subset=[Columns.DATE.value, Columns.PARAMETER.value], maintain_order=True)

                if self.sr.drop_nulls:
                    df = df.drop_nulls(subset=[Columns.VALUE.value])
                elif self.sr.complete and self.sr.start_date and dataset.resolution.value != Resolution.DYNAMIC:
                    df = self._build_complete_df(df, station_id, dataset.resolution.value)

                df = self._organize_df_columns(df, station_id, dataset)

                data.append(df)

            try:
                df = pl.concat(data)
            except ValueError:
                df = pl.DataFrame()

            if self.sr.start_date:
                df = df.filter(
                    pl.col(Columns.DATE.value).is_between(
                        self.sr.start_date,
                        self.sr.end_date,
                        closed="both",
                    ),
                )

            if self.sr.skip_empty:
                percentage = self._get_actual_percentage(df=df)
                if percentage < self.sr.skip_threshold:
                    log.info(
                        f"station {station_id} is skipped as percentage of actual values ({percentage}) "
                        f"is below threshold ({self.sr.skip_threshold}).",
                    )
                    continue

            # if not df.is_empty():
            if self.sr.humanize:
                df = self._humanize(df=df, humanized_parameters_mapping=hpm)

            if not self.sr.tidy:
                df = self._widen_df(df=df)

            if self.sr.tidy:
                sort_columns = [Columns.DATASET.value, Columns.PARAMETER.value, Columns.DATE.value]
            else:
                sort_columns = [Columns.DATASET.value, Columns.DATE.value]
            df = df.sort(sort_columns)

            self.stations_counter += 1
            self.stations_collected.append(station_id)

            yield ValuesResult(stations=self.sr, values=self, df=df)

    @abstractmethod
    def _collect_station_parameter_or_dataset(
        self, station_id: str, parameter_or_dataset: ParameterModel | DatasetModel
    ) -> pl.DataFrame:
        """
        Implementation of data collection for a station id plus parameter from the
        specified weather service. Takes care of the gathering of the data and putting
        it in shape, either tabular with one parameter per column or tidied with a set
        of station id, date, parameter, value and quality in one row.
        """
        pass

    def _widen_df(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        Method to widen a dataframe with each row having one timestamp and
        all parameter values and corresponding quality levels.

        Example:

        date         parameter                  value   quality
        1971-01-01   precipitation_height       0       0
        1971-01-01   temperature_air_mean_2m   10      0

        becomes

        date         precipitation_height   qn_precipitation_height
        1971-01-01   0                      0
            temperature_air_mean_2m    ...
            10                          ...

        :param df: DataFrame with ts_shape data
        :returns DataFrame with widened data e.g. pairwise columns of values
        and quality flags
        """
        # if there is more than one dataset, we need to prefix parameter names with dataset names to avoid
        # column name conflicts
        datasets = set(parameter.dataset.name for parameter in self.sr.parameters)
        if len(datasets) > 1:
            df = df.with_columns(
                pl.struct([pl.col(Columns.DATASET.value), pl.col(Columns.PARAMETER.value)])
                .map_elements(lambda x: f"""{x["dataset"]}_{x["parameter"]}""", return_dtype=pl.String)
                .alias(Columns.PARAMETER.value),
            )
        df_wide = df.select(
            [pl.col(Columns.STATION_ID.value), pl.col(Columns.DATASET.value), pl.col(Columns.DATE.value)],
        ).unique()

        if not df.is_empty():
            for (parameter,), parameter_df in df.group_by([Columns.PARAMETER.value], maintain_order=True):
                # Build quality column name
                parameter_quality = f"{Columns.QUALITY_PREFIX.value}_{parameter}"
                parameter_df = parameter_df.select(
                    [Columns.DATE.value, Columns.VALUE.value, Columns.QUALITY.value]
                ).rename(
                    mapping={Columns.VALUE.value: parameter, Columns.QUALITY.value: parameter_quality},
                )
                df_wide = df_wide.join(parameter_df, on=[Columns.DATE.value])
        else:
            for parameter in self.sr.parameters:
                parameter_name = parameter.name_original if not self.sr.humanize else parameter.name
                parameter_quality = f"{Columns.QUALITY_PREFIX.value}_{parameter_name}"
                df_wide = df_wide.with_columns(
                    pl.lit(None, pl.Float64).alias(parameter_name),
                    pl.lit(None, pl.Float64).alias(parameter_quality),
                )

        return df_wide

    def all(self) -> ValuesResult:  # noqa: A003
        """
        Collect all data from self.query

        :return:
        """
        data = []

        tqdm_out = TqdmToLogger(log, level=logging.INFO)

        for result in tqdm(self.query(), total=len(self.sr.station_id), file=tqdm_out):
            data.append(result.df)

        try:
            df = pl.concat(data)
        except ValueError:
            log.error("No data available for given constraints")
            return ValuesResult(stations=self.sr, values=self, df=pl.DataFrame())

        return ValuesResult(stations=self.sr, values=self, df=df)

    @staticmethod
    def _humanize(df: pl.DataFrame, humanized_parameters_mapping: dict[str, str]) -> pl.DataFrame:
        """
        Method for humanizing parameters.

        :param df: pandas.DataFrame with original column names
        :param humanized_parameters_mapping: mapping of original parameter names to humanized ones
        :return: pandas.DataFrame with renamed columns
        """
        return df.with_columns(pl.col(Columns.PARAMETER.value).replace(humanized_parameters_mapping))

    def _create_humanized_parameters_mapping(self) -> dict[str, str]:
        """
        Reduce the creation of parameter mapping of the massive amount of parameters
        by specifying the resolution.

        :return:
        """
        return {parameter.name_original: parameter.name for parameter in self.sr.stations.parameters}

    def _get_actual_percentage(self, df: pl.DataFrame) -> float:
        """
        Calculate percentage of actual values. The percentage is calculated
        per requested parameter and statistically aggregated to a float that
        can be compared with a threshold.
        :param df: pandas DataFrame with values
        :return: float of actual percentage of values
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
            return percentage.get_column("perc").min()
        elif self.sr.settings.ts_skip_criteria == "mean":
            return percentage.get_column("perc").mean()
        elif self.sr.settings.ts_skip_criteria == "max":
            return percentage.get_column("perc").max()
        else:
            raise KeyError("ts_skip_criteria must be one of min, mean, max")
