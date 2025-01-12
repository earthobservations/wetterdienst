# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Iterable
from itertools import repeat
from typing import TYPE_CHECKING, Literal
from zoneinfo import ZoneInfo

import polars as pl
import portion as P
from polars.exceptions import ColumnNotFoundError
from portion import Interval

from wetterdienst.core.timeseries.metadata import DatasetModel, ParameterSearch
from wetterdienst.core.timeseries.request import _DATETIME_TYPE, _PARAMETER_TYPE, _SETTINGS_TYPE, TimeseriesRequest
from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.dwd.observation.download import (
    download_climate_observations_data,
)
from wetterdienst.provider.dwd.observation.fileindex import (
    _create_file_index_for_dwd_server,
    create_file_index_for_climate_observations,
    create_file_list_for_climate_observations,
)
from wetterdienst.provider.dwd.observation.metadata import (
    HIGH_RESOLUTIONS,
    DwdObservationMetadata,
)
from wetterdienst.provider.dwd.observation.metaindex import (
    create_meta_index_for_climate_observations,
)
from wetterdienst.provider.dwd.observation.parser import parse_climate_observations_data
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

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: DatasetModel,
    ) -> pl.DataFrame:
        """
        Method to collect data for one specified parameter. Manages restoring,
        collection and storing of data, transformation and combination of different
        periods.

        :param station_id: station id for which parameter is collected
        :param parameter_or_dataset: parameter or dataset model

        :return: polars.DataFrame for given parameter of station
        """
        periods_and_date_ranges = []

        for period in self.sr.stations.periods:
            if parameter_or_dataset.resolution.value in HIGH_RESOLUTIONS and period == Period.HISTORICAL:
                date_ranges = self._get_historical_date_ranges(
                    station_id, parameter_or_dataset, self.sr.stations.settings
                )
                periods_and_date_ranges.append((period, date_ranges))
            else:
                periods_and_date_ranges.append((period, None))

        parameter_data = []

        for period, date_ranges in periods_and_date_ranges:
            if period not in parameter_or_dataset.periods:
                log.info(f"Skipping period {period} for {parameter_or_dataset.name}.")
                continue
            dataset_identifier = (
                f"{parameter_or_dataset.resolution.value.name}/{parameter_or_dataset.name}/{station_id}/{period.value}"  # noqa: E501
            )
            log.info(f"Acquiring observation data for {dataset_identifier}.")
            remote_files = create_file_list_for_climate_observations(
                station_id,
                parameter_or_dataset,
                period,
                self.sr.stations.settings,
                date_ranges,
            )
            if remote_files.is_empty():
                log.info(f"No files found for {dataset_identifier}. Station will be skipped.")
                continue
            filenames_and_files = download_climate_observations_data(remote_files, self.sr.stations.settings)
            period_df = parse_climate_observations_data(filenames_and_files, parameter_or_dataset, period)
            parameter_data.append(period_df)

        try:
            parameter_df = pl.concat(parameter_data, how="align")
        except ValueError:
            return pl.DataFrame()

        # Filter out values which already are in the DataFrame
        parameter_df = parameter_df.unique(subset=Columns.DATE.value)

        parameter_df = parameter_df.collect()

        if parameter_or_dataset.resolution.value in (Resolution.MINUTE_1, Resolution.MINUTE_5, Resolution.MINUTE_10):
            parameter_df = self._fix_timestamps(parameter_df)

        df = self._tidy_up_df(parameter_df, parameter_or_dataset)

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

    @staticmethod
    def _tidy_up_df(df: pl.DataFrame, dataset: DatasetModel) -> pl.DataFrame:
        """
        Implementation of _tidy_up_df for DWD Observations

        :param df: untidy DataFrame
        :param dataset: dataset enumeration
        :return: tidied DataFrame
        """
        droppable_columns = [
            # Hourly
            # Cloud type
            DwdObservationMetadata.hourly.cloud_type.cloud_type_layer1_abbreviation.name_original,
            DwdObservationMetadata.hourly.cloud_type.cloud_type_layer2_abbreviation.name_original,
            DwdObservationMetadata.hourly.cloud_type.cloud_type_layer3_abbreviation.name_original,
            DwdObservationMetadata.hourly.cloud_type.cloud_type_layer4_abbreviation.name_original,
            # Cloudiness
            DwdObservationMetadata.hourly.cloudiness.cloud_cover_total_index.name_original,
            # Solar
            DwdObservationMetadata.hourly.solar.end_of_interval.name_original,
            DwdObservationMetadata.hourly.solar.true_local_time.name_original,
            # Visibility
            DwdObservationMetadata.hourly.visibility.visibility_range_index.name_original,
            # Weather
            DwdObservationMetadata.hourly.weather_phenomena.weather_text.name_original,
        ]

        # Drop string columns, can't be coerced to float
        df = df.drop(*droppable_columns, strict=False)

        df = df.select(
            pl.col(Columns.STATION_ID.value),
            pl.col(Columns.DATE.value),
            pl.all().exclude([Columns.STATION_ID.value, Columns.DATE.value]),
        )

        if dataset == DwdObservationMetadata.daily.climate_summary:
            quality_wind = df.get_column(dataset.quality_wind.name_original)
            quality_general = df.get_column(dataset.quality_general.name_original)
            quality = pl.concat(
                [
                    pl.Series(repeat(quality_wind, times=2)).list.explode(),
                    pl.Series(repeat(quality_general, times=12)).list.explode(),
                ],
            )
            df = df.drop(
                dataset.quality_wind.name_original,
                dataset.quality_general.name_original,
            )
        elif dataset in (DwdObservationMetadata.monthly.climate_summary, DwdObservationMetadata.annual.climate_summary):
            quality_general = df.get_column(dataset.quality_general.name_original)
            quality_precipitation = df.get_column(
                dataset.quality_precipitation.name_original,
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
                dataset.quality_general.name_original,
                dataset.quality_precipitation.name_original,
            )
        elif dataset == DwdObservationMetadata.subdaily.wind_extreme:
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
        dataset: DatasetModel,
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

    metadata = DwdObservationMetadata
    _values = DwdObservationValues
    _available_periods = {Period.HISTORICAL, Period.RECENT, Period.NOW}

    @property
    def _interval(self) -> Interval | None:
        """
        Interval of the request if date given

        :return:
        """
        if self.start_date:
            # cut of hours, seconds,...
            return P.closed(
                self.start_date.astimezone(ZoneInfo(self.metadata.timezone)),
                self.end_date.astimezone(ZoneInfo(self.metadata.timezone)),
            )

        return None

    @property
    def _historical_interval(self) -> Interval:
        """
        Interval of historical data release schedule. Historical data is typically
        release once in a year somewhere in the first few months with updated quality

        :return:
        """
        now_local = dt.datetime.now(ZoneInfo(self.metadata.timezone))
        historical_end = now_local.replace(month=1, day=1)
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
        now_local = dt.datetime.now(ZoneInfo(self.metadata.timezone))
        recent_end = now_local.replace(hour=0, minute=0, second=0)
        recent_begin = recent_end - dt.timedelta(days=500)
        return P.closed(recent_begin, recent_end)

    @property
    def _now_interval(self) -> Interval:
        """
        Interval of now data release schedule. Now data is released every hour (near
        real time) reaching back to beginning of the previous day.

        :return:
        """
        now_end = dt.datetime.now(ZoneInfo(self.metadata.timezone))
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

    def _parse_period(self, period: Period) -> set[Period] | None:
        """
        Method to parse period(s)

        :param period:
        :return:
        """
        if not period:
            return None
        periods_parsed = set()
        for p in to_list(period):
            periods_parsed.add(parse_enumeration_from_template(p, Period))
        return periods_parsed & self._available_periods or None

    def __init__(
        self,
        parameters: _PARAMETER_TYPE,
        periods: str | Period | Sequence[str | Period] = None,
        start_date: _DATETIME_TYPE = None,
        end_date: _DATETIME_TYPE = None,
        settings: _SETTINGS_TYPE = None,
    ):
        """

        :param parameters: parameter set str/enumeration
        :param resolution: resolution str/enumeration
        :param period: period str/enumeration
        :param start_date: start date to limit the stations_result
        :param end_date: end date to limit the stations_result
        """
        super().__init__(
            parameters=parameters,
            start_date=start_date,
            end_date=end_date,
            settings=settings,
        )

        self.periods = self._parse_period(periods)

        # Has to follow the super call as start date and end date are required for getting
        # automated periods from overlapping intervals
        if not self.periods:
            if self.start_date:
                self.periods = self._get_periods()
            else:
                self.periods = self._available_periods

    def __eq__(self, other):
        return super().__eq__(other) and self.periods == other.periods

    def filter_by_station_id(self, station_id: str | int | tuple[str, ...] | tuple[int, ...] | list[str] | list[int]):
        return super().filter_by_station_id(
            pl.Series(name=Columns.STATION_ID.value, values=to_list(station_id)).cast(str).str.pad_start(5, "0"),
        )

    @classmethod
    def describe_fields(
        cls,
        dataset: str | Sequence[str] | ParameterSearch | DatasetModel,
        period: str | Period,
        language: Literal["en", "de"] = "en",
    ) -> dict:
        from wetterdienst.provider.dwd.observation.fields import read_description

        if isinstance(dataset, str) or isinstance(dataset, Iterable):
            parameter_template = ParameterSearch.parse(dataset)
        elif isinstance(dataset, DatasetModel):
            parameter_template = ParameterSearch(
                resolution=dataset.resolution.value.value, dataset=dataset.name_original
            )
        elif isinstance(dataset, ParameterSearch):
            parameter_template = dataset
        else:
            raise KeyError("dataset must be a string, ParameterTemplate or DatasetModel")

        dataset = DwdObservationMetadata.search_parameter(parameter_template)[0].dataset
        period = parse_enumeration_from_template(period, Period)
        if period not in dataset.periods or period not in cls._available_periods:
            raise ValueError(f"Period {period} not available for dataset {dataset}")

        file_index = _create_file_index_for_dwd_server(
            dataset=dataset,
            period=period,
            cdc_base="observations_germany/climate",
            settings=Settings(),
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
        for parameter in self.parameters:
            if parameter.dataset not in datasets:
                datasets.append(parameter.dataset)

        stations = []

        for dataset in datasets:
            periods = set(dataset.periods) & set(self.periods) if self.periods else dataset.periods
            for period in reversed(list(periods)):
                df = create_meta_index_for_climate_observations(dataset, period, self.settings)
                file_index = create_file_index_for_climate_observations(dataset, period, self.settings)
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
