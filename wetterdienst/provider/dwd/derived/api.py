# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD derived data provider."""

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass
from datetime import datetime
from itertools import groupby
from typing import TYPE_CHECKING, ClassVar
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst import Period
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.derived.metadata import DwdDerivedMetadata
from wetterdienst.provider.dwd.observation.metaindex import _read_meta_df
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.network import File, download_file, list_remote_files_fsspec
from wetterdienst.util.python import to_list

if TYPE_CHECKING:
    from wetterdienst.model.metadata import DatasetModel, ParameterModel

log = logging.getLogger(__name__)

_ENDPOINT_PREFIX = {
    "heating_degreedays": {
        Period.RECENT: "https://opendata.dwd.de/climate_environment/CDC/derived_germany/"
        "techn/monthly/heating_degreedays/hdd_3807/recent/",
        Period.HISTORICAL: "https://opendata.dwd.de/climate_environment/CDC/derived_germany/"
        "techn/monthly/heating_degreedays/hdd_3807/historical/",
    },
    "stations_list": "https://opendata.dwd.de/climate_environment/CDC/help/KL_Monatswerte_Beschreibung_Stationen.txt",
}

_ENDPOINT_SUFFIX = {
    "heating_degreedays": "gradtage_{date}.csv",
}


def _get_data_from_file(file: File) -> pl.DataFrame:
    df = pl.read_csv(
        file.content,
        separator=";",
        skip_rows=3,
    )
    return df.select(pl.all().name.map(str.strip))


class DwdDerivedValues(TimeseriesValues):
    """Values class for dwd derived data."""

    _default_start_dates: ClassVar = {
        Resolution.MONTHLY: dt.datetime(2000, 1, 1, tzinfo=ZoneInfo("UTC")),
    }

    _column_name_mapping: ClassVar = {
        "#ID": "station_id",
        "Anzahl Tage": "amount_days_per_month",
        "Monatsgradtage": "heating_degreedays",
        "Anzahl Heiztage": "amount_heating_degreedays_per_month",
    }

    @staticmethod
    def _extract_datetime_from_file_url(file_url: str) -> datetime | None:
        match = re.search(r"_(\d{6})\.csv", file_url)
        if match is None:
            # Other files like txt files.
            return None
        date_str = match.group(1)
        return datetime.strptime(date_str, "%Y%m").replace(tzinfo=ZoneInfo("UTC"))

    def _filter_date_range_for_period(
        self,
        date_range: pl.Series,
        period: Period,
        parameter: ParameterModel,
    ) -> pl.Series:
        file_url = _ENDPOINT_PREFIX.get(parameter.dataset.name).get(period)

        available_file_urls = list_remote_files_fsspec(
            url=file_url,
            settings=self.sr.settings,
        )
        available_dates = {self._extract_datetime_from_file_url(file_url=file_url) for file_url in available_file_urls}
        available_dates.discard(
            None,
        )
        earliest_date_with_available_file = min(available_dates)
        latest_date_with_available_file = max(available_dates)

        # Proper expression filtering only possible with DataFrame.
        return (
            date_range.to_frame("date")
            .filter(pl.col("date").is_between(earliest_date_with_available_file, latest_date_with_available_file))
            .to_series()
        )

    def _get_first_day_of_months_to_fetch(
        self,
        parameter_or_dataset: ParameterModel,
    ) -> list[datetime | None] | pl.Series:
        """Create a list of dates that are the first days of the months to fetch.

        If start and end dates were given, these determine the first and last month, respectively.
        Else, default values are used.
        """
        if self.sr.start_date is None:
            start_date_of_range = self._default_start_dates[parameter_or_dataset.dataset.resolution.value].replace(
                day=1
            )
        else:
            start_date_of_range = self.sr.start_date.replace(day=1)

        if self.sr.end_date is None:
            end_date_of_range = datetime.now(ZoneInfo("UTC")).replace(day=1)
        else:
            end_date_of_range = self.sr.end_date.replace(day=1)

        return pl.datetime_range(
            start_date_of_range,
            end_date_of_range,
            "1mo",
            eager=True,
            closed="both",
            time_zone="UTC",
        )

    @staticmethod
    def _get_values_url(product_name: str, period: Period, start_date: str) -> str:
        endpoint_prefix = _ENDPOINT_PREFIX.get(product_name).get(period)
        endpoint = endpoint_prefix + _ENDPOINT_SUFFIX.get(product_name, "")
        return endpoint.format(
            date=start_date,
        )

    @staticmethod
    def _process_dataframe_to_expected_format(
        df: pl.DataFrame,
        column_name_mapping: dict[str, str],
        date: datetime,
        parameter: ParameterModel,
    ) -> pl.DataFrame:
        """Process DataFrame to the expected format."""
        df = df.rename(mapping=column_name_mapping)
        # Need to manually cast value since leading whitespaces cause issues
        # when using polars casting function.
        value = float(df.select(parameter.name).item())
        return df.select(
            pl.lit(parameter.dataset.resolution.name).alias("resolution"),
            pl.lit(parameter.dataset.name).alias("dataset"),
            pl.lit(parameter.name_original).alias("parameter"),
            pl.lit(date).alias("date"),
            pl.lit(value).alias("value"),
            pl.lit(None, dtype=pl.Float64).alias("quality"),
        )

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel,
    ) -> pl.DataFrame:
        data = []

        full_date_range_to_fetch = self._get_first_day_of_months_to_fetch(
            parameter_or_dataset,
        )

        for period in self.sr.stations.periods:
            if period not in parameter_or_dataset.dataset.periods:
                log.info(f"Skipping period {period} for {parameter_or_dataset.name}.")
                continue
            date_range_to_fetch_for_period = self._filter_date_range_for_period(
                date_range=full_date_range_to_fetch,
                period=period,
                parameter=parameter_or_dataset,
            )
            for first_day_of_month_to_fetch in date_range_to_fetch_for_period:
                for dataset, _ in groupby(self.sr.stations.parameters, key=lambda x: x.dataset):
                    url = self._get_values_url(
                        product_name=dataset.name,
                        period=period,
                        start_date=first_day_of_month_to_fetch.strftime("%Y%m"),
                    )
                    file = download_file(
                        url=url,
                        cache_dir=self.sr.stations.settings.cache_dir,
                        ttl=CacheExpiry.FIVE_MINUTES,
                        client_kwargs=self.sr.settings.fsspec_client_kwargs,
                        cache_disable=self.sr.settings.cache_disable,
                    )

                    if file.status == 404:
                        log.warning(
                            f"File {url.rsplit('/', 1)[1]} for "
                            f"station {station_id} not found on server {url}. Skipping."
                        )
                        continue
                    file.raise_if_exception()

                    df = _get_data_from_file(file)
                    df = df.filter(pl.col("#ID").eq(int(station_id)))

                    if df.is_empty():
                        log.warning(
                            f"No data found for ID {station_id} at {first_day_of_month_to_fetch.strftime('%m/%Y')}"
                        )
                        continue

                    df = self._process_dataframe_to_expected_format(
                        df=df,
                        column_name_mapping=self._column_name_mapping,
                        date=first_day_of_month_to_fetch,
                        parameter=parameter_or_dataset,
                    )
                    data.append(df)

        if len(data) == 0:
            return pl.DataFrame()
        return pl.concat(data)


@dataclass
class DwdDerivedRequest(TimeseriesRequest):
    """Request class for dwd derived data.

    The months that are fetched are the ones whose first day is between the start and the end date.
    """

    metadata = DwdDerivedMetadata
    _values = DwdDerivedValues
    _available_periods: ClassVar = {Period.HISTORICAL, Period.RECENT}
    periods: str | Period | set[str | Period] = None

    @staticmethod
    def _process_dataframe_to_expected_format(
        stations_data: pl.LazyFrame,
        dataset: DatasetModel,
    ) -> pl.LazyFrame:
        stations_data = stations_data.sort(by=["station_id"])
        return stations_data.select(
            pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            "station_id",
            pl.col("start_date").str.to_datetime("%Y%m%d", time_zone="UTC"),
            pl.col("end_date").str.to_datetime("%Y%m%d", time_zone="UTC"),
            pl.col("height").cast(pl.Float64),
            pl.col("latitude").cast(pl.Float64),
            pl.col("longitude").str.strip_chars().cast(pl.Float64),
            "name",
            "state",
        )

    @staticmethod
    def _get_station_url(
        product_name: str,
    ) -> str:
        return _ENDPOINT_PREFIX.get(product_name)

    def __post_init__(self) -> None:
        """Post init method."""
        super().__post_init__()

        self.periods = self._parse_period(self.periods)
        if not self.periods:
            self.periods = self._available_periods

    def _parse_period(self, period: str | Period | None) -> set[Period] | None:
        """Parse period from string or Period enumeration."""
        if not period:
            return None
        periods_parsed = {
            parse_enumeration_from_template(
                enum_=p,
                intermediate=Period,
            )
            for p in to_list(period)
        }
        return periods_parsed & self._available_periods or None

    def _all(self) -> pl.LazyFrame:
        data = []
        for dataset, _ in groupby(self.parameters, key=lambda x: x.dataset):
            url = self._get_station_url(product_name="stations_list")
            file = download_file(
                url=url,
                cache_dir=self.settings.cache_dir,
                ttl=CacheExpiry.METAINDEX,
                client_kwargs=self.settings.fsspec_client_kwargs,
                cache_disable=self.settings.cache_disable,
            )
            file.raise_if_exception()
            raw_stations_data = _read_meta_df(file=file)
            processed_stations_data = self._process_dataframe_to_expected_format(
                stations_data=raw_stations_data,
                dataset=dataset,
            )
            data.append(processed_stations_data)
        return pl.concat(data)
