# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD derived data provider."""

from __future__ import annotations

import datetime as dt
import itertools
import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from functools import partial
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
    from collections.abc import Generator, Iterable

    from wetterdienst.model.metadata import DatasetModel, ParameterModel

log = logging.getLogger(__name__)


class CoolingDegreeHoursReferenceTemperature(Enum):
    """Enumeration for reference temperatures for cooling degree hours on dwd server."""

    CDH_13 = 13
    CDH_16 = 16
    CDH_18 = 18


def _get_data_from_file(
    downloaded_file: File,
    skip_rows: int = 3,
) -> pl.DataFrame:
    """Parse file content to DataFrame.

    :param downloaded_file: Downloaded file to parse
    :param skip_rows: How many rows to skip in the beginning of the file
    :return: Parsed DataFrame
    """
    df = pl.read_csv(
        downloaded_file.content,
        separator=";",
        skip_rows=skip_rows,
    )
    return df.select(pl.all().name.map(str.strip))


class DwdDerivedValues(TimeseriesValues):
    """Values class for dwd derived data."""

    _default_start_dates: ClassVar = {
        Resolution.MONTHLY: dt.datetime(2000, 1, 1, tzinfo=ZoneInfo("UTC")),
    }

    _DERIVED_BASE_URL = "https://opendata.dwd.de/climate_environment/CDC/derived_germany/techn/monthly"

    @staticmethod
    def _extract_datetime_from_file_url_single_date_format(
        file_url: str,
    ) -> datetime | None:
        """Extract a timestamp from a given file url.

        This assumes that the file url is for a CSV file in the format used
        by heating degreedays or cooling degreehours.
        Example: "example.org/file_202510.csv" will be parsed to 2025-10-01T00:00Z.

        :param file_url: URL to parse
        :return: Parsed result if a timestamp could be extracted, else None
        """
        match = re.search(r"_(\d{6})\.csv", file_url)
        if match is not None:
            return datetime.strptime(match.group(1), "%Y%m").replace(tzinfo=ZoneInfo("UTC"))
        # Other files like txt files.
        return None

    @staticmethod
    def _extract_datetime_from_file_url_multiple_dates_format(
        file_url: str,
    ) -> datetime | None:
        """Extract a timestamp from a given file url.

        This assumes that the file url is for a CSV file in the format used
        by climate correction factors.
        Example: "example.org/file_20251001_20261130.csv" will be parsed to 2025-10-01T00:00Z.

        :param file_url: URL to parse
        :return: Parsed result if a timestamp could be extracted, else None
        """
        match = re.search(r"_(\d{8})_\d{8}.csv", file_url)
        if match is not None:
            return datetime.strptime(match.group(1), "%Y%m%d").replace(tzinfo=ZoneInfo("UTC"))
        # Other files like txt files.
        return None

    _STRATEGIES_DATETIME_EXTRACTION_FROM_FILE_URL: ClassVar = {
        DwdDerivedMetadata.monthly.heating_degreedays.name: _extract_datetime_from_file_url_single_date_format,
        DwdDerivedMetadata.monthly.cooling_degreehours_13.name: _extract_datetime_from_file_url_single_date_format,
        DwdDerivedMetadata.monthly.cooling_degreehours_16.name: _extract_datetime_from_file_url_single_date_format,
        DwdDerivedMetadata.monthly.cooling_degreehours_18.name: _extract_datetime_from_file_url_single_date_format,
        DwdDerivedMetadata.monthly.climate_correction_factor.name: (
            _extract_datetime_from_file_url_multiple_dates_format
        ),
    }

    @staticmethod
    def _extract_datetime_from_file_url(
        dataset: DatasetModel,
        file_url: str,
    ) -> datetime | None:
        """Extract a timestamp from a given file url.

        :param dataset: Relevant dataset for which timestamp is parsed
        :param file_url: URL to parse
        :return: Parsed result if a timestamp could be extracted, else None
        """
        strategy = DwdDerivedValues._STRATEGIES_DATETIME_EXTRACTION_FROM_FILE_URL.get(dataset.name)
        if not strategy:
            error_msg = f"Unknown dataset: {dataset.name}"
            raise ValueError(error_msg)
        return strategy(file_url=file_url)

    def _filter_date_range_for_period(
        self,
        date_range: pl.Series,
        period: Period,
        dataset: DatasetModel,
    ) -> pl.Series:
        """Filter the given date range to only include dates where files exist for a period.

        :param date_range: Date range to filter
        :param period: Period for which is filtered
        :param dataset: Name of dataset whose files are searched for the period
        :return: Filtered date range, can be empty if no files exist for that period
        """
        file_url = self._get_base_file_url(
            dataset=dataset,
            period=period,
        )
        available_file_urls = list_remote_files_fsspec(
            url=file_url,
            settings=self.sr.settings,
        )
        available_dates = {
            self._extract_datetime_from_file_url(
                dataset=dataset,
                file_url=file_url,
            )
            for file_url in available_file_urls
        }

        # None values are artifacts from files that contain no dates, like
        # station TXT files or description PDFs.
        available_dates.discard(
            None,
        )

        if len(available_dates) == 0:
            return pl.Series()

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
        parameter: ParameterModel,
    ) -> list[datetime | None] | pl.Series:
        """Create a list of dates that are the first days of the months to fetch.

        If start and end dates were given, these determine the first and last month, respectively.
        Else, default values are used.

        :param parameter: Parameter name, determining default values for start dates
        :return: List of dates for which data should be fetched
        """
        if self.sr.start_date is None:
            start_date_of_range = self._default_start_dates[parameter.dataset.resolution.value].replace(day=1)
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
    def _get_base_file_url_heating_degreedays(
        period: Period,
    ) -> str:
        """Get base file url for heating degreedays.

        This base file url is the root directory of all files
        related to heating degreedays in the given period.

        :param period: Relevant period of data
        :return: Base file URL
        """
        return f"{DwdDerivedValues._DERIVED_BASE_URL}/heating_degreedays/hdd_3807/{period.value.lower()}"

    @staticmethod
    def _get_base_file_url_cooling_degreehours(
        period: Period,
        reference_temperature: CoolingDegreeHoursReferenceTemperature,
    ) -> str:
        """Get base file url for cooling degreehours.

        This base file url is the root directory of all files
        related to cooling degreehours days in the given period.

        :param period: Relevant period of data
        :param reference_temperature: Reference temperature for cooling degreehours
        :return: Base file URL
        """
        return (
            f"{DwdDerivedValues._DERIVED_BASE_URL}/cooling_degreehours/"
            f"cdh_{reference_temperature.value}/{period.value.lower()}"
        )

    @staticmethod
    def _get_base_file_url_climate_correction_factors(
        period: Period,
    ) -> str:
        """Get base file url for climate correction factors.

        This base file url is the root directory of all files
        related to climate factors in the given period.

        :param period: Relevant period of data
        :return: Base file URL
        """
        return f"{DwdDerivedValues._DERIVED_BASE_URL}/climate_correction_factor/{period.value.lower()}"

    @staticmethod
    def _get_values_url_heating_degreedays(
        period: Period,
        month_of_year: str,
    ) -> str:
        """Get specific file url for a month for heating degreedays.

        :param period: Relevant period of data
        :param month_of_year: String representing the month of a year (e.g. 202510)
        :return: File URL
        """
        base_file_url = DwdDerivedValues._get_base_file_url_heating_degreedays(
            period=period,
        )
        return f"{base_file_url}/gradtage_{month_of_year}.csv"

    @staticmethod
    def _get_values_url_cooling_degreehours(
        period: Period,
        month_of_year: str,
        reference_temperature: CoolingDegreeHoursReferenceTemperature,
    ) -> str:
        """Get specific file url for a month for cooling_degreehours.

        :param period: Relevant period of data
        :param month_of_year: String representing the month of a year (e.g. 202510)
        :param reference_temperature: Reference temperature for cooling degreehours
        :return: File URL
        """
        base_file_url = DwdDerivedValues._get_base_file_url_cooling_degreehours(
            period=period,
            reference_temperature=reference_temperature,
        )
        return f"{base_file_url}/kuehlgrade_{reference_temperature.value}_0_{month_of_year}.csv"

    @staticmethod
    def _get_values_url_climate_correction_factors(
        period: Period,
        month_of_year: str,
    ) -> str:
        """Get specific file url for a month for climate correction factors.

        The given month corresponds to the first month of the one-year range covered by the file.

        :param period: Relevant period of data
        :param month_of_year: String representing the month of a year (e.g. 202510),
        represents the start of the date range
        :return: File URL
        """
        base_file_url = DwdDerivedValues._get_base_file_url_climate_correction_factors(
            period=period,
        )

        start_date, end_date = DwdDerivedValues._get_date_range_for_year_starting_in_month(month_of_year=month_of_year)
        return f"{base_file_url}/KF_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.csv"

    @staticmethod
    def _get_date_range_for_year_starting_in_month(
        month_of_year: str,
    ) -> tuple[datetime, datetime]:
        """Get start and end date for a year that start at given month.

        The start date corresponds to the first day of the given month.
        The end date is the last day of the previous month one year later.
        E.g. for the input "202403", the returned start date is
        2024-03-01T00:00Z and the end date is 2025-02-28T00:00Z.

        :param month_of_year: Start month
        :return: Start and end date of year range
        """
        start_date = datetime.strptime(month_of_year, "%Y%m").replace(tzinfo=ZoneInfo("UTC"))
        # Do not need to worry about leap years since start_date is always the first of a month.
        end_date = start_date.replace(year=start_date.year + 1) - timedelta(days=1)
        return start_date, end_date

    _STRATEGIES_BASE_URL: ClassVar = {
        DwdDerivedMetadata.monthly.heating_degreedays.name: _get_base_file_url_heating_degreedays,
        DwdDerivedMetadata.monthly.cooling_degreehours_13.name: partial(
            _get_base_file_url_cooling_degreehours,
            reference_temperature=CoolingDegreeHoursReferenceTemperature.CDH_13,
        ),
        DwdDerivedMetadata.monthly.cooling_degreehours_16.name: partial(
            _get_base_file_url_cooling_degreehours,
            reference_temperature=CoolingDegreeHoursReferenceTemperature.CDH_16,
        ),
        DwdDerivedMetadata.monthly.cooling_degreehours_18.name: partial(
            _get_base_file_url_cooling_degreehours,
            reference_temperature=CoolingDegreeHoursReferenceTemperature.CDH_18,
        ),
        DwdDerivedMetadata.monthly.climate_correction_factor.name: _get_base_file_url_climate_correction_factors,
    }

    _STRATEGIES_VALUES_URL: ClassVar = {
        DwdDerivedMetadata.monthly.heating_degreedays.name: _get_values_url_heating_degreedays,
        DwdDerivedMetadata.monthly.cooling_degreehours_13.name: partial(
            _get_values_url_cooling_degreehours,
            reference_temperature=CoolingDegreeHoursReferenceTemperature.CDH_13,
        ),
        DwdDerivedMetadata.monthly.cooling_degreehours_16.name: partial(
            _get_values_url_cooling_degreehours,
            reference_temperature=CoolingDegreeHoursReferenceTemperature.CDH_16,
        ),
        DwdDerivedMetadata.monthly.cooling_degreehours_18.name: partial(
            _get_values_url_cooling_degreehours, reference_temperature=CoolingDegreeHoursReferenceTemperature.CDH_18
        ),
        DwdDerivedMetadata.monthly.climate_correction_factor.name: _get_values_url_climate_correction_factors,
    }

    _N_ROWS_TO_SKIP: ClassVar = {
        DwdDerivedMetadata.monthly.heating_degreedays.name: 3,
        DwdDerivedMetadata.monthly.cooling_degreehours_13.name: 2,
        DwdDerivedMetadata.monthly.cooling_degreehours_16.name: 2,
        DwdDerivedMetadata.monthly.cooling_degreehours_18.name: 2,
        DwdDerivedMetadata.monthly.climate_correction_factor.name: 0,
    }

    _STATION_ID_COLUMN_NAME: ClassVar = {
        DwdDerivedMetadata.monthly.heating_degreedays.name: "#ID",
        DwdDerivedMetadata.monthly.cooling_degreehours_13.name: "ID",
        DwdDerivedMetadata.monthly.cooling_degreehours_16.name: "ID",
        DwdDerivedMetadata.monthly.cooling_degreehours_18.name: "ID",
        DwdDerivedMetadata.monthly.climate_correction_factor.name: "PLZ",
    }

    _COOLING_DEGREE_HOURS_COLUMN_NAME_MAPPING: ClassVar = {
        "ID": "station_id",
        "Anzahl Stunden": "amount_hours",
        "Anzahl Kuehlstunden": "amount_cooling_hours",
        "Kuehlgradestunden": "cooling_degreehours",
        "Kuehltage": "cooling_days",
    }

    _HEATING_DEGREE_DAYS_COLUMN_NAME_MAPPING: ClassVar = {
        "#ID": "station_id",
        "Anzahl Tage": "amount_days_per_month",
        "Monatsgradtage": "heating_degreedays",
        "Anzahl Heiztage": "amount_heating_degreedays_per_month",
    }

    _CLIMATE_CORRECTION_FACTOR_COLUMN_NAME_MAPPING: ClassVar = {
        "PLZ": "station_id",
        "KF": "climate_correction_factor",
    }

    _COLUMN_NAME_MAPPING: ClassVar = {
        DwdDerivedMetadata.monthly.heating_degreedays.name: _HEATING_DEGREE_DAYS_COLUMN_NAME_MAPPING,
        DwdDerivedMetadata.monthly.cooling_degreehours_13.name: _COOLING_DEGREE_HOURS_COLUMN_NAME_MAPPING,
        DwdDerivedMetadata.monthly.cooling_degreehours_16.name: _COOLING_DEGREE_HOURS_COLUMN_NAME_MAPPING,
        DwdDerivedMetadata.monthly.cooling_degreehours_18.name: _COOLING_DEGREE_HOURS_COLUMN_NAME_MAPPING,
        DwdDerivedMetadata.monthly.climate_correction_factor.name: _CLIMATE_CORRECTION_FACTOR_COLUMN_NAME_MAPPING,
    }

    @staticmethod
    def _get_base_file_url(
        dataset: DatasetModel,
        period: Period,
    ) -> str:
        """Get base file url for a dataset.

        This base file url is the root directory of all files
        related to the dataset in the given period.

        :param dataset: Relevant dataset for which base file url is determined
        :param period: Relevant period of data
        :return: Base file URL
        """
        strategy = DwdDerivedValues._STRATEGIES_BASE_URL.get(dataset.name)
        if not strategy:
            error_msg = f"Unknown dataset: {dataset.name}"
            raise ValueError(error_msg)
        return strategy(period=period)

    @staticmethod
    def _get_values_url(
        dataset: DatasetModel,
        period: Period,
        month_of_year: str,
    ) -> str:
        """Get specific file url for a month for a dataset.

        :param dataset: Relevant dataset for which specific file url is determined
        :param period: Relevant period of data
        :param month_of_year: String representing the month of a year (e.g. 202510)
        :return: Specific file URL
        """
        strategy = DwdDerivedValues._STRATEGIES_VALUES_URL.get(dataset.name)
        if not strategy:
            error_msg = f"Unknown dataset: {dataset.name}"
            raise ValueError(error_msg)
        return strategy(period=period, month_of_year=month_of_year)

    @staticmethod
    def _process_dataframe_to_expected_format(
        df: pl.DataFrame,
        column_name_mapping: dict[str, str],
        date: datetime,
        parameter: ParameterModel,
    ) -> pl.DataFrame:
        """Process DataFrame to the expected format.

        :param df: Data to be processed
        :param column_name_mapping: Mapping of column names (key: old name, value: new name)
        :param date: Constant date that is stored in "date" column
        :param parameter: Parameter to which input data belongs
        :return: Processed DataFrame
        """
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
            pl.lit(None, dtype=pl.Float32).alias("quality"),
        )

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel,
    ) -> pl.DataFrame:
        """Fetch data for a station and a parameter.

        :param station_id: Station for which data is fetched
        :param parameter_or_dataset: Parameter for which data is fetched
        (name is for consistency with overridden method)
        :return: Fetched data
        """
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
                dataset=parameter_or_dataset.dataset,
            )
            for first_day_of_month_to_fetch in date_range_to_fetch_for_period:
                url = self._get_values_url(
                    dataset=parameter_or_dataset.dataset,
                    period=period,
                    month_of_year=first_day_of_month_to_fetch.strftime("%Y%m"),
                )
                downloaded_file = download_file(
                    url=url,
                    cache_dir=self.sr.stations.settings.cache_dir,
                    ttl=CacheExpiry.FIVE_MINUTES,
                    client_kwargs=self.sr.settings.fsspec_client_kwargs,
                    cache_disable=self.sr.settings.cache_disable,
                )

                if downloaded_file.status == 404:
                    log.info(
                        f"File {url.rsplit('/', 1)[1]} for station {station_id} not found on server {url}. Skipping."
                    )
                    continue
                downloaded_file.raise_if_exception()

                df = _get_data_from_file(
                    downloaded_file=downloaded_file,
                    skip_rows=DwdDerivedValues._N_ROWS_TO_SKIP.get(
                        parameter_or_dataset.dataset.name,
                        2,
                    ),
                )
                df = df.filter(
                    pl.col(DwdDerivedValues._STATION_ID_COLUMN_NAME[parameter_or_dataset.dataset.name]).eq(
                        int(station_id)
                    )
                )

                if df.is_empty():
                    log.info(f"No data found for ID {station_id} at {first_day_of_month_to_fetch.strftime('%m/%Y')}")
                    continue

                df = self._process_dataframe_to_expected_format(
                    df=df,
                    column_name_mapping=self._COLUMN_NAME_MAPPING.get(parameter_or_dataset.dataset.name),
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
        """Process station data to the expected format.

        :param stations_data: Data to be processed
        :param dataset: Dataset to which input data belongs
        :return: Processed DataFrame
        """
        stations_data = stations_data.sort(by=["station_id"])
        return stations_data.select(
            pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            "station_id",
            pl.col("start_date").str.to_datetime("%Y%m%d", time_zone="UTC"),
            pl.col("end_date").str.to_datetime("%Y%m%d", time_zone="UTC"),
            pl.col("height").cast(pl.Float32),
            pl.col("latitude").cast(pl.Float32),
            pl.col("longitude").str.strip_chars().cast(pl.Float32),
            "name",
            "state",
        )

    def __post_init__(self) -> None:
        """Post init method."""
        super().__post_init__()

        self.periods = self._parse_period(self.periods)
        if not self.periods:
            self.periods = self._available_periods

    def _parse_period(
        self,
        period: str | Period | Iterable[str | Period] | None,
    ) -> set[Period] | None:
        """Parse period from string or Period enumeration.

        :param period: Input value for the period
        :return: Parsed period
        """
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

    def _get_raw_station_data_from_url(self) -> pl.LazyFrame:
        """Download raw station data from DWD help directory.

        :return: Raw station data as lazy DataFrame
        """
        downloaded_file = download_file(
            url="https://opendata.dwd.de/climate_environment/CDC/help/KL_Monatswerte_Beschreibung_Stationen.txt",
            cache_dir=self.settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=self.settings.fsspec_client_kwargs,
            cache_disable=self.settings.cache_disable,
        )
        downloaded_file.raise_if_exception()
        return _read_meta_df(file=downloaded_file)

    @staticmethod
    def _generate_digit_combinations(number_of_digits: int = 5) -> Generator[str]:
        """Create a generator of all possible combinations of digits 0-9.

        This is mainly used to generate all possible postal codes (PLZ),
        when setting the number of digits to 5.

        :param number_of_digits: How many digits are included in the combination
        :return: Generator of strings containing the combinations
        """
        return (
            "".join(str(digit) for digit in combination_of_digits)
            for combination_of_digits in itertools.product(range(10), repeat=number_of_digits)
        )

    def _get_raw_station_data_from_plz_generator(self) -> pl.LazyFrame:
        """Get proxy station data containing all possible postals codes (PLZ) as station ID.

        The rest of the columns required by the library are filled with NULLs.

        :return: Proxy station data as lazy DataFrame
        """
        autogenerated_station_data = pl.DataFrame(
            {
                "station_id": DwdDerivedRequest._generate_digit_combinations(),
            },
            schema={"station_id": pl.String},
        ).lazy()
        return autogenerated_station_data.with_columns(
            pl.lit(None, dtype=pl.String).alias("name"),
            pl.lit(None, dtype=pl.String).alias("state"),
            pl.lit(None, dtype=pl.String).alias("latitude"),
            pl.lit(None, dtype=pl.String).alias("longitude"),
            pl.lit(None, dtype=pl.Float32).alias("height"),
            pl.lit(None, dtype=pl.String).alias("start_date"),
            pl.lit(None, dtype=pl.String).alias("end_date"),
        )

    _STRATEGIES_RAW_STATION_DATA: ClassVar = {
        DwdDerivedMetadata.monthly.heating_degreedays.name: _get_raw_station_data_from_url,
        DwdDerivedMetadata.monthly.cooling_degreehours_13.name: _get_raw_station_data_from_url,
        DwdDerivedMetadata.monthly.cooling_degreehours_16.name: _get_raw_station_data_from_url,
        DwdDerivedMetadata.monthly.cooling_degreehours_18.name: _get_raw_station_data_from_url,
        DwdDerivedMetadata.monthly.climate_correction_factor.name: _get_raw_station_data_from_plz_generator,
    }

    def _get_raw_station_data(
        self,
        dataset: DatasetModel,
    ) -> pl.LazyFrame:
        """Get raw station data for a given dataset.

        :param dataset: Dataset for which station data is returned
        :return: Raw station data as lazy DataFrame
        """
        strategy = DwdDerivedRequest._STRATEGIES_RAW_STATION_DATA.get(dataset.name)
        if not strategy:
            error_msg = f"Unknown dataset: {dataset.name}"
            raise ValueError(error_msg)
        return strategy(self)

    def _all(self) -> pl.LazyFrame:
        """Fetch station data for the given request.

        :return: Fetched station data.
        """
        data = []
        for dataset, _ in groupby(self.parameters, key=lambda x: x.dataset):
            raw_stations_data = self._get_raw_station_data(
                dataset=dataset,
            )

            processed_stations_data = self._process_dataframe_to_expected_format(
                stations_data=raw_stations_data,
                dataset=dataset,
            )
            data.append(processed_stations_data)
        return pl.concat(data)
