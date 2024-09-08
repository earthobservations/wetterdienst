# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import datetime as dt
import logging
from itertools import repeat
from typing import TYPE_CHECKING

import polars as pl
import portion as P
from polars.exceptions import ColumnNotFoundError
from portion import Interval

from wetterdienst.core.timeseries.request import TimeseriesRequest
from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.datarange import DataRange
from wetterdienst.metadata.kind import Kind
from wetterdienst.metadata.period import Period, PeriodType
from wetterdienst.metadata.provider import Provider
from wetterdienst.metadata.resolution import Resolution, ResolutionType
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.provider.dwd.observation.download import (
    download_climate_observations_data_parallel,
)
from wetterdienst.provider.dwd.observation.fileindex import (
    _create_file_index_for_dwd_server,
    create_file_index_for_climate_observations,
    create_file_list_for_climate_observations,
)
from wetterdienst.provider.dwd.observation.metadata.dataset import (
    DwdObservationDataset,
)
from wetterdienst.provider.dwd.observation.metadata.parameter import (
    DwdObservationParameter,
)
from wetterdienst.provider.dwd.observation.metadata.period import DwdObservationPeriod
from wetterdienst.provider.dwd.observation.metadata.resolution import (
    HIGH_RESOLUTIONS,
    RESOLUTION_TO_DATETIME_FORMAT_MAPPING,
    DwdObservationResolution,
)
from wetterdienst.provider.dwd.observation.metadata.unit import DwdObservationUnit
from wetterdienst.provider.dwd.observation.metaindex import (
    create_meta_index_for_climate_observations,
)
from wetterdienst.provider.dwd.observation.parser import parse_climate_observations_data
from wetterdienst.provider.dwd.observation.util.parameter import (
    check_dwd_observations_dataset,
)
from wetterdienst.settings import Settings
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.python import to_list

if TYPE_CHECKING:
    from collections.abc import Sequence

log = logging.getLogger(__name__)


class DwdObservationValues(TimeseriesValues):
    """
    The DWDObservationData class represents a request for
    observation data as provided by the DWD service.
    """

    _tz = Timezone.GERMANY
    _data_tz = Timezone.UTC
    _resolution_type = ResolutionType.MULTI
    _resolution_base = DwdObservationResolution
    _period_type = PeriodType.MULTI
    _period_base = DwdObservationPeriod

    @property
    def _datetime_format(self):
        """

        :return:
        """
        return RESOLUTION_TO_DATETIME_FORMAT_MAPPING.get(self.sr.stations.resolution)

    def __eq__(self, other):
        """

        :param other:
        :return:
        """
        return super().__eq__(other) and (
            self.sr.resolution == other.sr.resolution and self.sr.period == other.sr.period
        )

    def __str__(self):
        """

        :return:
        """
        periods_joined = "& ".join([period_type.value for period_type in self.sr.period])

        return ", ".join(
            [
                super().__str__(),
                f"resolution {self.sr.resolution.value}",
                f"periods {periods_joined}",
            ],
        )

    def _collect_station_parameter(
        self,
        station_id: str,
        parameter: DwdObservationParameter | DwdObservationDataset,  # noqa: ARG002
        dataset: DwdObservationDataset,
    ) -> pl.DataFrame:
        """
        Method to collect data for one specified parameter. Manages restoring,
        collection and storing of data, transformation and combination of different
        periods.

        :param station_id: station id for which parameter is collected
        :param parameter: chosen parameter-dataset combination that is collected

        :return: pandas.DataFrame for given parameter of station
        """
        periods_and_date_ranges = []

        for period in self.sr.period:
            if self.sr.resolution in HIGH_RESOLUTIONS and period == Period.HISTORICAL:
                date_ranges = self._get_historical_date_ranges(station_id, dataset, self.sr.stations.settings)

                for date_range in date_ranges:
                    periods_and_date_ranges.append((period, date_range))
            else:
                periods_and_date_ranges.append((period, None))

        parameter_data = []

        for period, date_range in periods_and_date_ranges:
            if not check_dwd_observations_dataset(dataset, self.sr.resolution, period):
                log.info(f"Invalid combination {dataset.value}/{self.sr.resolution.value}/{period} is skipped.")
                continue

            dataset_identifier = f"{dataset.value}/{self.sr.resolution.value}/{period.value}/{station_id}/{date_range}"

            log.info(f"Acquiring observation data for {dataset_identifier}.")

            remote_files = create_file_list_for_climate_observations(
                station_id,
                dataset,
                self.sr.resolution,
                period,
                self.sr.stations.settings,
                date_range,
            )

            if remote_files.is_empty():
                log.info(f"No files found for {dataset_identifier}. Station will be skipped.")
                continue

            filenames_and_files = download_climate_observations_data_parallel(remote_files, self.sr.stations.settings)

            period_df = parse_climate_observations_data(filenames_and_files, dataset, self.sr.resolution, period)

            parameter_data.append(period_df)

        try:
            parameter_df = pl.concat(parameter_data, how="align")
        except ValueError:
            return pl.DataFrame()

        # Filter out values which already are in the DataFrame
        parameter_df = parameter_df.unique(subset=Columns.DATE.value)

        parameter_df = parameter_df.collect()

        if self.sr.resolution in (Resolution.MINUTE_1, Resolution.MINUTE_5, Resolution.MINUTE_10):
            parameter_df = self._fix_timestamps(parameter_df)

        df = self._tidy_up_df(parameter_df, dataset)

        return df.with_columns(
            pl.col(Columns.DATE.value).dt.replace_time_zone("UTC"),
            pl.col(Columns.STATION_ID.value).str.pad_start(5, "0"),
            pl.col(Columns.VALUE.value).cast(pl.Float64),
            pl.col(Columns.QUALITY.value).cast(pl.Float64),
        )

    @staticmethod
    def _fix_timestamps(df: pl.DataFrame) -> pl.DataFrame:
        """
        This method is used to fix timestamps for 10 minute resolution data provided
        by DWD. The original document states
        " The time stamp before the year 2000 is given in MEZ, the time stamp after
        the year 2000 is given in UTC. "
        :param df: pandas DataFrame with original timestamps
        :return: pandas DataFrame with fixed timestamps
        """
        return df.with_columns(
            pl.when(pl.col(Columns.DATE.value).dt.year() < 2000)
            .then(pl.col(Columns.DATE.value) - pl.duration(hours=1))
            .otherwise(pl.col(Columns.DATE.value))
            .alias(Columns.DATE.value),
        )

    def _tidy_up_df(self, df: pl.DataFrame, dataset) -> pl.DataFrame:
        """
        Implementation of _tidy_up_df for DWD Observations

        :param df: untidy DataFrame
        :param dataset: dataset enumeration
        :return: tidied DataFrame
        """
        droppable_columns = [
            # Hourly
            # Cloud type
            DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER1_ABBREVIATION.value,
            DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER2_ABBREVIATION.value,
            DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER3_ABBREVIATION.value,
            DwdObservationParameter.HOURLY.CLOUD_TYPE.CLOUD_TYPE_LAYER4_ABBREVIATION.value,
            # Cloudiness
            DwdObservationParameter.HOURLY.CLOUDINESS.CLOUD_COVER_TOTAL_INDEX.value,
            # Solar
            DwdObservationParameter.HOURLY.SOLAR.END_OF_INTERVAL.value,
            DwdObservationParameter.HOURLY.SOLAR.TRUE_LOCAL_TIME.value,
            # Visibility
            DwdObservationParameter.HOURLY.VISIBILITY.VISIBILITY_RANGE_INDEX.value,
            # Weather
            DwdObservationParameter.HOURLY.WEATHER_PHENOMENA.WEATHER_TEXT.value,
        ]

        # Drop string columns, can't be coerced to float
        df = df.drop(*droppable_columns, strict=False)

        df = df.select(
            pl.col(Columns.STATION_ID.value),
            pl.col(Columns.DATE.value),
            pl.all().exclude([Columns.STATION_ID.value, Columns.DATE.value]),
        )

        resolution = self.sr.stations.resolution

        if dataset == DwdObservationDataset.CLIMATE_SUMMARY:
            if resolution == Resolution.DAILY:
                quality_wind = df.get_column(DwdObservationParameter.DAILY.CLIMATE_SUMMARY.QUALITY_WIND.value)
                quality_general = df.get_column(DwdObservationParameter.DAILY.CLIMATE_SUMMARY.QUALITY_GENERAL.value)
                quality = pl.concat(
                    [
                        pl.Series(repeat(quality_wind, times=2)).list.explode(),
                        pl.Series(repeat(quality_general, times=12)).list.explode(),
                    ],
                )
                df = df.drop(
                    DwdObservationParameter.DAILY.CLIMATE_SUMMARY.QUALITY_WIND.value,
                    DwdObservationParameter.DAILY.CLIMATE_SUMMARY.QUALITY_GENERAL.value,
                )
            elif resolution in (Resolution.MONTHLY, Resolution.ANNUAL):
                quality_general = df.get_column(DwdObservationParameter.MONTHLY.CLIMATE_SUMMARY.QUALITY_GENERAL.value)
                quality_precipitation = df.get_column(
                    DwdObservationParameter.MONTHLY.CLIMATE_SUMMARY.QUALITY_PRECIPITATION.value,
                )

                quality = pl.concat(
                    [
                        pl.Series(
                            repeat(
                                quality_general,
                                times=9,
                            ),
                        ).list.explode(),
                        pl.Series(
                            repeat(
                                quality_precipitation,
                                times=2,
                            ),
                        ).list.explode(),
                    ],
                )
                df = df.drop(
                    DwdObservationParameter.MONTHLY.CLIMATE_SUMMARY.QUALITY_GENERAL.value,
                    DwdObservationParameter.MONTHLY.CLIMATE_SUMMARY.QUALITY_PRECIPITATION.value,
                )
        elif resolution == Resolution.SUBDAILY and dataset == DwdObservationDataset.WIND_EXTREME:
            quality = []
            for column in ("qn_8_3", "qn_8_6"):
                try:
                    quality.append(df.get_column(column))
                except ColumnNotFoundError:
                    pass
                else:
                    df = df.select(pl.all().exclude(column))
            quality = pl.concat(quality)
        else:
            n = len(df.columns) - 3
            quality = pl.Series(values=repeat(df.get_column(df.columns[2]), times=n)).list.explode()
            df = df.drop(df.columns[2])

        possible_index_variables = (
            Columns.STATION_ID.value,
            Columns.DATE.value,
            Columns.START_DATE.value,
            Columns.END_DATE.value,
        )

        index = list(set(df.columns).intersection(possible_index_variables))

        df = df.unpivot(
            index=index,
            variable_name=Columns.PARAMETER.value,
            value_name=Columns.VALUE.value,
        )

        df = df.with_columns(quality.alias(Columns.QUALITY.value))

        return df.with_columns(pl.when(pl.col(Columns.VALUE.value).is_not_null()).then(pl.col(Columns.QUALITY.value)))

    def _get_historical_date_ranges(
        self,
        station_id: str,
        dataset: DwdObservationDataset,
        settings: Settings,
    ) -> list[str]:
        """
        Get particular files for historical data which for high resolution is
        released in data chunks e.g. decades or monthly chunks

        :param station_id:
        :param dataset:
        :return:
        """
        file_index = create_file_index_for_climate_observations(
            dataset,
            self.sr.resolution,
            Period.HISTORICAL,
            settings,
        )

        file_index = file_index.filter(pl.col(Columns.STATION_ID.value).eq(station_id))

        # The request interval may be None, if no start and end date
        # is given but rather the entire available data is queried.
        # In this case the interval should overlap with all files
        interval = self.sr.stations._interval
        start_date_min, end_date_max = interval and (interval.lower, interval.upper) or (None, None)
        if start_date_min:
            file_index = file_index.filter(
                pl.col(Columns.STATION_ID.value).eq(station_id)
                & pl.col(Columns.START_DATE.value).ge(end_date_max).not_()
                & pl.col(Columns.END_DATE.value).le(start_date_min).not_(),
            )

        return file_index.collect().get_column(Columns.DATE_RANGE.value).to_list()


class DwdObservationRequest(TimeseriesRequest):
    """
    The DWDObservationStations class represents a request for
    a station list as provided by the DWD service.
    """

    _provider = Provider.DWD
    _kind = Kind.OBSERVATION
    _tz = Timezone.GERMANY
    _dataset_base = DwdObservationDataset
    _parameter_base = DwdObservationParameter
    _unit_base = DwdObservationUnit
    _resolution_type = ResolutionType.MULTI
    _resolution_base = DwdObservationResolution
    _period_type = PeriodType.MULTI
    _period_base = DwdObservationPeriod
    _has_datasets = True
    _unique_dataset = False
    _data_range = DataRange.FIXED
    _values = DwdObservationValues

    @property
    def _interval(self) -> Interval | None:
        """
        Interval of the request if date given

        :return:
        """
        if self.start_date:
            # cut of hours, seconds,...
            return P.closed(self.start_date.astimezone(self.tz), self.end_date.astimezone(self.tz))

        return None

    @property
    def _historical_interval(self) -> Interval:
        """
        Interval of historical data release schedule. Historical data is typically
        release once in a year somewhere in the first few months with updated quality

        :return:
        """
        historical_end = self._now_local.replace(month=1, day=1)
        # a year that is way before any data is collected
        historical_begin = dt.datetime(year=1678, month=1, day=1, tzinfo=historical_end.tzinfo)
        return P.closed(historical_begin, historical_end)

    @property
    def _recent_interval(self) -> Interval:
        """
        Interval of recent data release schedule. Recent data is released every day
        somewhere after midnight with data reaching back 500 days.

        :return:
        """
        recent_end = self._now_local.replace(hour=0, minute=0, second=0)
        recent_begin = recent_end - dt.timedelta(days=500)
        return P.closed(recent_begin, recent_end)

    @property
    def _now_interval(self) -> Interval:
        """
        Interval of now data release schedule. Now data is released every hour (near
        real time) reaching back to beginning of the previous day.

        :return:
        """
        now_end = self._now_local
        now_begin = now_end.replace(hour=0, minute=0, second=0) - dt.timedelta(days=1)
        return P.closed(now_begin, now_end)

    def _get_periods(self) -> list[Period]:
        """
        Set periods automatically depending on the given start date and end date.
        Overlapping of historical and recent interval will cause both periods to appear
        if values from last year are queried within the 500 day range of recent. This is
        okay as we'd prefer historical values with quality checks, but may encounter
        that in the beginning of a new year historical data is not yet updated and only
        recent periods cover this data.

        :return:
        """
        periods = []
        interval = self._interval
        if interval.overlaps(self._historical_interval):
            periods.append(Period.HISTORICAL)
        if interval.overlaps(self._recent_interval):
            periods.append(Period.RECENT)
        if interval.overlaps(self._now_interval):
            periods.append(Period.NOW)
        return periods

    @staticmethod
    def _parse_station_id(series: pl.Series) -> pl.Series:
        return series.cast(pl.String).str.pad_start(5, "0")

    def __init__(
        self,
        parameter: str
        | DwdObservationDataset
        | DwdObservationParameter
        | Sequence[
            str
            | DwdObservationDataset
            | DwdObservationParameter
            | tuple[str | DwdObservationParameter, str | DwdObservationDataset]
        ],
        resolution: str | DwdObservationResolution | Resolution,
        period: str | DwdObservationPeriod | Period | Sequence[str | DwdObservationPeriod | Period] = None,
        start_date: str | dt.datetime | None = None,
        end_date: str | dt.datetime | None = None,
        settings: Settings | None = None,
    ):
        """

        :param parameter: parameter set str/enumeration
        :param resolution: resolution str/enumeration
        :param period: period str/enumeration
        :param start_date: start date to limit the stations_result
        :param end_date: end date to limit the stations_result
        """
        super().__init__(
            parameter=parameter,
            resolution=resolution,
            period=period,
            start_date=start_date,
            end_date=end_date,
            settings=settings,
        )

        if self.start_date and self.period:
            log.warning(f"start_date and end_date filtering limited to defined " f"periods {self.period}")

        # Has to follow the super call as start date and end date are required for getting
        # automated periods from overlapping intervals
        if not self.period:
            if self.start_date:
                self.period = self._get_periods()
            else:
                self.period = self._parse_period([*self._period_base])

    def filter_by_station_id(self, station_id: str | int | tuple[str, ...] | tuple[int, ...] | list[str] | list[int]):
        return super().filter_by_station_id(
            pl.Series(name=Columns.STATION_ID.value, values=to_list(station_id)).cast(str).str.pad_start(5, "0"),
        )

    @classmethod
    def describe_fields(cls, dataset, resolution, period, language: str = "en") -> dict:
        """

        :param dataset:
        :param resolution:
        :param period:
        :param language:
        :return:
        """
        from wetterdienst.provider.dwd.observation.fields import read_description

        dataset = parse_enumeration_from_template(dataset, DwdObservationDataset)
        resolution = parse_enumeration_from_template(resolution, cls._resolution_base, Resolution)
        period = parse_enumeration_from_template(period, cls._period_base, Period)

        file_index = _create_file_index_for_dwd_server(
            dataset=dataset,
            resolution=resolution,
            period=period,
            cdc_base="observations_germany/climate",
            settings=Settings.default(),
        ).collect()

        if language == "en":
            file_prefix = "DESCRIPTION_"
        elif language == "de":
            file_prefix = "BESCHREIBUNG_"
        else:
            raise ValueError("Only language 'en' or 'de' supported")

        file_index = file_index.filter(pl.col("filename").str.contains(file_prefix))
        description_file_url = str(file_index.get_column("filename").item())
        log.info(f"Acquiring field information from {description_file_url}")

        return read_description(description_file_url, language=language)

    def _all(self) -> pl.LazyFrame:
        """

        :return:
        """
        datasets = []
        for _, dataset in self.parameter:
            if dataset not in datasets:
                datasets.append(dataset)

        stations = []

        for dataset in datasets:
            # First "now" period as it has more updated end date up to the last "now"
            # values
            for period in reversed(self.period):
                if not check_dwd_observations_dataset(dataset, self.resolution, period):
                    log.warning(
                        f"The combination of {dataset.value}, " f"{self.resolution.value}, {period.value} is invalid.",
                    )

                    continue
                df = create_meta_index_for_climate_observations(dataset, self.resolution, period, self.settings)
                file_index = create_file_index_for_climate_observations(dataset, self.resolution, period, self.settings)
                df = df.join(
                    other=file_index.select(pl.col(Columns.STATION_ID.value)),
                    on=[pl.col(Columns.STATION_ID.value)],
                    how="inner",
                )
                stations.append(df)

        try:
            stations_df = pl.concat(stations)
        except ValueError:
            return pl.LazyFrame()

        stations_df = stations_df.unique(subset=[Columns.STATION_ID.value], keep="first")

        return stations_df.sort(by=[pl.col(Columns.STATION_ID.value).cast(int)])
