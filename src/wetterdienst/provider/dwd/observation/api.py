# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD observation data provider."""

from __future__ import annotations

import datetime as dt
import logging
from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, Literal
from zoneinfo import ZoneInfo

import polars as pl
import portion
from fsspec.implementations.zip import ZipFileSystem
from portion import Interval

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.history import (
    History,
    TimeseriesHistory,
    _DeviceHistory,
    _GeographyHistory,
    _MissingDataHistory,
    _NameHistory,
    _ParameterHistory,
)
from wetterdienst.model.metadata import DatasetModel, ParameterSearch
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.observation.download import (
    download_climate_observations_data,
)
from wetterdienst.provider.dwd.observation.fileindex import (
    _build_url_from_dataset_and_period,
    _create_file_index_for_1minute_or_5minute_historical_precipitation_metadata,
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
from wetterdienst.util.network import File, download_file
from wetterdienst.util.python import to_list

if TYPE_CHECKING:
    from collections.abc import Sequence

    from wetterdienst.model.result import StationsResult
log = logging.getLogger(__name__)

# columns that can't be coerced to float are dropped
DROPPABLE_COLUMNS = [
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


class DwdObservationValues(TimeseriesValues):
    """Values class for DWD observation data."""

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: DatasetModel,
    ) -> pl.DataFrame:
        """Collect station data for a given dataset."""
        periods_and_date_ranges = []
        for period in self.sr.stations.periods:
            if parameter_or_dataset.resolution.value in HIGH_RESOLUTIONS and period == Period.HISTORICAL:
                date_ranges = self._get_historical_date_ranges(
                    station_id,
                    parameter_or_dataset,
                    self.sr.stations.settings,
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
                f"{parameter_or_dataset.resolution.value.name}/{parameter_or_dataset.name}/{station_id}/{period.value}"
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
        parameter_df = parameter_df.unique(subset=["date"])
        parameter_df = parameter_df.collect()
        parameter_df = parameter_df.drop(*DROPPABLE_COLUMNS, strict=False)
        if parameter_or_dataset.resolution.value in (Resolution.MINUTE_1, Resolution.MINUTE_5, Resolution.MINUTE_10):
            parameter_df = self._fix_timestamps(parameter_df)
        df = self._tidy_up_df(parameter_df)
        return df.select(
            pl.lit(parameter_or_dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(parameter_or_dataset.name, dtype=pl.String).alias("dataset"),
            "parameter",
            pl.col("station_id").str.pad_start(5, "0"),
            pl.col("date").dt.replace_time_zone("UTC"),
            pl.col("value").cast(pl.Float32),
            pl.col("quality").cast(pl.Float32),
        )

    @staticmethod
    def _fix_timestamps(df: pl.DataFrame) -> pl.DataFrame:
        """Fix timestamps for minute data."""
        return df.with_columns(
            pl.when(pl.col("date").dt.year() < 2000)
            .then(pl.col("date") - pl.duration(hours=1))
            .otherwise(pl.col("date"))
            .alias("date"),
        )

    @staticmethod
    def _tidy_up_df(df: pl.DataFrame) -> pl.DataFrame:
        """Tidy up the DataFrame by dropping unnecessary columns and renaming columns."""
        data = []
        series_quality = pl.Series()
        for column in df.columns[2:]:
            if column.startswith(("qn", "qualitaet")):
                series_quality = df.get_column(column)
            else:
                df_parameter = df.select(
                    "station_id",
                    "date",
                    pl.lit(column, dtype=pl.String).alias("parameter"),
                    pl.col(column).alias("value"),
                    series_quality.alias("quality"),
                )
                data.append(df_parameter)
        df = pl.concat(data)
        return df.with_columns(pl.when(pl.col("value").is_not_null()).then(pl.col("quality")))

    def _get_historical_date_ranges(
        self,
        station_id: str,
        dataset: DatasetModel,
        settings: Settings,
    ) -> list[str]:
        """Get historical date ranges for a given station id and dataset."""
        file_index = create_file_index_for_climate_observations(
            dataset,
            Period.HISTORICAL,
            settings,
        )
        file_index = file_index.filter(pl.col("station_id").eq(station_id))
        # The request interval may be None, if no start and end date
        # is given but rather the entire available data is queried.
        # In this case the interval should overlap with all files
        interval = self.sr.stations.interval
        start_date_min, end_date_max = (interval and (interval.lower, interval.upper)) or (None, None)
        if start_date_min:
            file_index = file_index.filter(
                pl.col("station_id").eq(station_id)
                & pl.col("start_date").ge(end_date_max).not_()
                & pl.col("end_date").le(start_date_min).not_(),
            )
        return file_index.collect().get_column("date_range").to_list()


class DwdObservationHistory(TimeseriesHistory):
    """History class for DWD observation data."""

    def _collect_station_history(self, station_id: str, available_datasets: list[DatasetModel]) -> Iterator[History]:
        for dataset in available_datasets:
            dataset_identifier = f"{dataset.resolution.value.name}/{dataset.name}/{station_id}"
            log.info(f"Acquiring station history for {dataset_identifier}.")
            try:
                if dataset.resolution.value in HIGH_RESOLUTIONS:
                    file_index = _create_file_index_for_1minute_or_5minute_historical_precipitation_metadata(
                        resolution=dataset.resolution.value.value,
                        dataset=dataset.name_original,
                        settings=self.sr.stations.settings,
                    )
                else:
                    file_index = create_file_index_for_climate_observations(
                        dataset=dataset,
                        period=Period.HISTORICAL,
                        settings=self.sr.stations.settings,
                    )
            except FileNotFoundError:
                log.info(
                    f"No files found for {dataset_identifier} and period {Period.HISTORICAL}. Station will be skipped."
                )
                continue
            file_index = file_index.filter(pl.col("station_id").eq(station_id)).collect()
            if file_index.is_empty():
                log.info(f"No files found for {dataset_identifier}. Station will be skipped.")
                continue
            if dataset.resolution.value in (Resolution.SUBDAILY, Resolution.DAILY) and dataset.name == "wind_extreme":
                # subdaily extreme wind dataset has one file for FX3 and one for FX6
                name_histories = []
                parameter_histories = []
                device_histories = []
                geography_histories = []
                missing_data_histories = []

                for file in file_index.get_column("url"):
                    file: File = download_file(
                        url=file,
                        cache_dir=self.sr.stations.settings.cache_dir,
                        ttl=CacheExpiry.METAINDEX,
                        client_kwargs=self.sr.stations.settings.fsspec_client_kwargs,
                        cache_disable=self.sr.stations.settings.cache_disable,
                        use_certifi=self.sr.stations.settings.use_certifi,
                    )
                    name_history = self.read_name_history(file)
                    name_histories.append(name_history)
                    parameter_history_list = self.read_parameter_history(file)
                    parameter_histories.append(parameter_history_list)
                    device_history_list = self.read_device_history(file)
                    device_histories.append(device_history_list)
                    geography_history_list = self.read_geography_history(file)
                    geography_histories.append(geography_history_list)
                    missing_data_history = self.read_missing_data_history(file, dataset.resolution.value)
                    missing_data_histories.append(missing_data_history)
                yield History(
                    name=_NameHistory(
                        station=[station for nh in name_histories for station in nh.station],
                        operator=[operator for nh in name_histories for operator in nh.operator],
                    ),
                    parameter=[ph for sublist in parameter_histories for ph in sublist],
                    device=[dh for sublist in device_histories for dh in sublist],
                    geography=[gh for sublist in geography_histories for gh in sublist],
                    missing_data=_MissingDataHistory(
                        summary=[summary for mdh in missing_data_histories for summary in mdh.summary],
                        periods=[periods for mdh in missing_data_histories for periods in mdh.periods],
                    ),
                )
            file: File = download_file(
                url=file_index.get_column("url").item(),
                cache_dir=self.sr.stations.settings.cache_dir,
                ttl=CacheExpiry.METAINDEX,
                client_kwargs=self.sr.stations.settings.fsspec_client_kwargs,
                cache_disable=self.sr.stations.settings.cache_disable,
                use_certifi=self.sr.stations.settings.use_certifi,
            )
            name_history = self.read_name_history(file)
            parameter_history_list = self.read_parameter_history(file)
            device_history_list = self.read_device_history(file)
            geography_history_list = self.read_geography_history(file)
            missing_data_history = self.read_missing_data_history(file, dataset.resolution.value)
            yield History(
                name=name_history,
                parameter=parameter_history_list,
                device=device_history_list,
                geography=geography_history_list,
                missing_data=missing_data_history,
            )

    @staticmethod
    def read_name_history(file: File) -> _NameHistory:
        """Read station name and operator name history from a zip file."""
        zfs = ZipFileSystem(file.content)
        # find file
        name_file = zfs.glob("Metadaten_Stationsname_Betreibername_*.txt")
        if not name_file:
            return _NameHistory()
        name_file = name_file[0]
        with zfs.open(name_file, "r") as f:
            lines = f.readlines()
        # split by empty line into station name and operator name
        split_index = lines.index("\n")
        # determine which part is station name and which is operator name
        if "Stationsname" in lines[0]:
            station_name_lines = lines[1:split_index]
            operator_name_lines = lines[split_index + 2 : -1]
            if operator_name_lines[-1].startswith("generiert:"):
                operator_name_lines = operator_name_lines[:-1]
        else:
            operator_name_lines = lines[1:split_index]
            station_name_lines = lines[split_index + 2 : -1]
            if station_name_lines[-1].startswith("generiert:"):
                station_name_lines = station_name_lines[:-1]

        station_name_data = []
        for line in station_name_lines:
            parts = line.strip().split(";")
            station_name_data.append(
                {
                    "station_id": parts[0].strip().zfill(5),
                    "station_name": parts[1].strip(),
                    "start_date": dt.datetime.strptime(parts[2].strip(), "%Y%m%d").replace(tzinfo=ZoneInfo("UTC")),
                    "end_date": (
                        dt.datetime.strptime(parts[3].strip(), "%Y%m%d").replace(tzinfo=ZoneInfo("UTC"))
                        if parts[3].strip()
                        else None
                    ),
                }
            )
        operator_name_data = []
        for line in operator_name_lines:
            parts = line.strip().split(";")
            operator_name_data.append(
                {
                    "station_id": parts[0].strip().zfill(5),
                    "operator_name": parts[1].strip(),
                    "start_date": dt.datetime.strptime(parts[2].strip(), "%Y%m%d").replace(tzinfo=ZoneInfo("UTC")),
                    "end_date": (
                        dt.datetime.strptime(parts[3].strip(), "%Y%m%d").replace(tzinfo=ZoneInfo("UTC"))
                        if parts[3].strip()
                        else None
                    ),
                }
            )
        return _NameHistory(station=station_name_data, operator=operator_name_data)

    @staticmethod
    def read_parameter_history(file: File) -> list[_ParameterHistory]:
        """Read parameter history from file."""
        zfs = ZipFileSystem(file.content)
        # find file Metadaten_Parameter_klima_tag_01048.txt, but use glob to be independent of station
        parameter_file = zfs.glob("**/Metadaten_Parameter_*.txt")
        if not parameter_file:
            return []
        parameter_file = parameter_file[0]
        parameter_text = zfs.open(parameter_file).read()
        lines = parameter_text.strip().decode(encoding="latin1").splitlines()
        records = []
        for line in lines[1:]:
            if line.startswith(("Legende:", "generiert:")):
                continue
            parts = line.split(";")
            if len(parts) < 8:
                continue
            record = {
                "station_id": parts[0].strip(),
                "start_date": dt.datetime.strptime(parts[1].strip(), "%Y%m%d").replace(tzinfo=ZoneInfo("UTC")),
                "end_date": dt.datetime.strptime(parts[2].strip(), "%Y%m%d").replace(tzinfo=ZoneInfo("UTC")),
                "station_name": parts[3].strip(),
                "parameter": parts[4].strip(),
                "description": parts[5].strip(),
                "unit": parts[6].strip(),
                "data_source": parts[7].strip(),
                "extra_info": parts[8].strip(),
                "special": parts[9].strip(),
                "literature": parts[10].strip(),
            }
            records.append(record)
        return [_ParameterHistory.model_validate(record) for record in records]

    @staticmethod
    def read_device_history(file: File) -> list[_DeviceHistory]:
        """Read device history from file."""
        zfs = ZipFileSystem(file.content)
        # find all Metadaten_Geraete_*.txt files, but use glob to be independent of station
        device_files = zfs.glob("**/Metadaten_Geraete_*.txt")
        records = []
        for device_file in device_files:
            device_text = zfs.open(device_file).read()
            lines = device_text.strip().decode(encoding="latin1").splitlines()
            for line in lines[1:]:
                if line.startswith("generiert:"):
                    continue
                parts = line.split(";")
                if len(parts) < 10:
                    continue
                record = {
                    "station_id": parts[0].strip(),
                    "station_name": parts[1].strip(),
                    "longitude": parts[2].strip() or None,
                    "latitude": parts[3].strip() or None,
                    "station_height": parts[4].strip() or None,
                    "device_height": parts[5].strip() or None,
                    "start_date": dt.datetime.strptime(parts[6].strip(), "%Y%m%d").replace(tzinfo=ZoneInfo("UTC")),
                    "end_date": dt.datetime.strptime(parts[7].strip(), "%Y%m%d").replace(tzinfo=ZoneInfo("UTC")),
                    "device_type": parts[8].strip(),
                    "method": parts[9].strip(),
                }
                records.append(record)
        return [_DeviceHistory.model_validate(record) for record in records]

    @staticmethod
    def read_geography_history(file: File) -> list[_GeographyHistory]:
        """Read geography history from file."""
        zfs = ZipFileSystem(file.content)
        # find all Metadaten_Geographie_*.txt files, but use glob to be independent of station
        geography_files = zfs.glob("**/Metadaten_Geographie_*.txt")
        records = []
        for geography_file in geography_files:
            geography_text = zfs.open(geography_file).read()
            lines = geography_text.strip().decode(encoding="latin1").splitlines()
            for line in lines[1:]:
                parts = line.split(";")
                if len(parts) < 7:
                    continue
                record = {
                    "station_id": parts[0].strip(),
                    "station_height": float(parts[1].strip()),
                    "latitude": float(parts[2].strip()),
                    "longitude": float(parts[3].strip()),
                    "start_date": dt.datetime.strptime(parts[4].strip(), "%Y%m%d").replace(tzinfo=ZoneInfo("UTC")),
                    "end_date": dt.datetime.strptime(parts[5].strip(), "%Y%m%d").replace(tzinfo=ZoneInfo("UTC"))
                    if parts[5].strip()
                    else dt.datetime.now(tz=ZoneInfo("UTC")),
                    "station_name": parts[6].strip(),
                }
                records.append(record)
        return [_GeographyHistory.model_validate(record) for record in records]

    @staticmethod
    def read_missing_data_history(file: File, resolution: Resolution) -> _MissingDataHistory:
        """Read missing data history from file."""
        # we need to adjust date format based on resolution for period records
        resolution_to_date_format = defaultdict(
            lambda: "%d.%m.%Y", {Resolution.HOURLY: "%d.%m.%Y-%H:%M", Resolution.SUBDAILY: "%d.%m.%Y-%H:%M"}
        )
        date_format = resolution_to_date_format[resolution]
        zfs = ZipFileSystem(file.content)
        # find all Metadaten_Fehlzeiten_*.txt files, but use glob to be independent of station
        missing_data_file = zfs.glob("**/Metadaten_Fehldaten_*.txt")
        if not missing_data_file:
            return _MissingDataHistory()
        missing_data_file = missing_data_file[0]
        missing_data_text = zfs.open(missing_data_file).read()
        lines = missing_data_text.decode("utf-8").strip().splitlines()
        # find line that separates summary from period
        split_line = 0
        count_starts_with = 0
        for i, line in enumerate(lines):
            if line.strip().startswith("Stations_ID"):
                count_starts_with += 1
                if count_starts_with == 2:
                    split_line = i
                    break
        summary_lines = lines[1:split_line]
        period_lines = lines[split_line + 1 : -1]
        summary_records = []
        for line in summary_lines:
            parts = line.split(";")
            record = {
                "station_id": parts[0].zfill(5),
                "station_name": parts[1],
                "parameter": parts[2],
                "start_date": dt.datetime.strptime(parts[3], "%d.%m.%Y").replace(tzinfo=ZoneInfo("UTC")),
                "end_date": dt.datetime.strptime(parts[4], "%d.%m.%Y").replace(tzinfo=ZoneInfo("UTC")),
                "missing_count": int(parts[5]) if parts[5] else None,
                "description": parts[6],
            }
            summary_records.append(record)
        # period records use date format depending on resolution
        period_records = []
        for line in period_lines:
            parts = line.split(";")
            record = {
                "station_id": parts[0].zfill(5),
                "station_name": parts[1],
                "parameter": parts[2],
                "start_date": dt.datetime.strptime(parts[3], date_format).replace(tzinfo=ZoneInfo("UTC")),
                "end_date": dt.datetime.strptime(parts[4], date_format).replace(tzinfo=ZoneInfo("UTC")),
                "missing_count": int(parts[5]) if parts[5] else None,
                "description": parts[6],
            }
            period_records.append(record)
        return _MissingDataHistory(summary=summary_records, periods=period_records)


@dataclass
class DwdObservationRequest(TimeseriesRequest):
    """Request class for DWD observation data."""

    metadata = DwdObservationMetadata
    _values = DwdObservationValues
    _history = DwdObservationHistory
    _available_periods: ClassVar = {Period.HISTORICAL, Period.RECENT, Period.NOW}
    periods: str | Period | set[str | Period] = None

    @property
    def interval(self) -> Interval | None:
        """Interval of the request."""
        if self.start_date:
            # cut of hours, seconds,...
            return portion.closed(
                self.start_date.astimezone(ZoneInfo(self.metadata.timezone)),
                self.end_date.astimezone(ZoneInfo(self.metadata.timezone)),
            )
        return None

    @property
    def _historical_interval(self) -> Interval:
        """Interval of historical data release schedule.

        Historical data is typically release once in a year somewhere in the first few months with updated quality
        """
        now_local = dt.datetime.now(ZoneInfo(self.metadata.timezone))
        historical_end = now_local.replace(month=1, day=1)
        # a year that is way before any data is collected
        historical_begin = dt.datetime(year=1678, month=1, day=1, tzinfo=historical_end.tzinfo)
        return portion.closed(historical_begin, historical_end)

    @property
    def _recent_interval(self) -> Interval:
        """Interval of recent data release schedule.

        Recent data is released every day somewhere after midnight with data reaching back 500 days.
        """
        now_local = dt.datetime.now(ZoneInfo(self.metadata.timezone))
        recent_end = now_local.replace(hour=0, minute=0, second=0)
        recent_begin = recent_end - dt.timedelta(days=500)
        return portion.closed(recent_begin, recent_end)

    @property
    def _now_interval(self) -> Interval:
        """Interval of now data release schedule.

        Now data is released every hour (near real time) reaching back to beginning of the previous day.
        """
        now_end = dt.datetime.now(ZoneInfo(self.metadata.timezone))
        now_begin = now_end.replace(hour=0, minute=0, second=0) - dt.timedelta(days=1)
        return portion.closed(now_begin, now_end)

    def _get_periods(self) -> set[Period]:
        """Get periods based on the interval of the request."""
        periods = set()
        interval = self.interval
        if interval.overlaps(self._historical_interval):
            periods.add(Period.HISTORICAL)
        if interval.overlaps(self._recent_interval):
            periods.add(Period.RECENT)
        if interval.overlaps(self._now_interval):
            periods.add(Period.NOW)
        return periods

    @staticmethod
    def _parse_station_id(series: pl.Series) -> pl.Series:
        return series.cast(pl.String).str.pad_start(5, "0")

    def _parse_period(self, period: Period) -> set[Period] | None:
        """Parse period from string or Period enumeration."""
        if not period:
            return None
        periods_parsed = set()
        periods_parsed.update(parse_enumeration_from_template(p, Period) for p in to_list(period))
        return periods_parsed & self._available_periods or None

    def __post_init__(self) -> None:
        """Post init method."""
        super().__post_init__()

        self.periods = self._parse_period(self.periods)
        # Has to follow the super call as start date and end date are required for getting
        # automated periods from overlapping intervals
        if not self.periods:
            if self.start_date:
                self.periods = self._get_periods()
            else:
                self.periods = self._available_periods

    def filter_by_station_id(
        self,
        station_id: str | int | tuple[str, ...] | tuple[int, ...] | list[str] | list[int],
    ) -> StationsResult:
        """Filter by station id."""
        # ensure station_id is a list of strings with padded zeros to length 5
        station_id = [str(station_id).zfill(5) for station_id in to_list(station_id)]
        return super().filter_by_station_id(station_id)

    @classmethod
    def describe_fields(
        cls,
        dataset: str | Sequence[str] | ParameterSearch | DatasetModel,
        period: str | Period,
        language: Literal["en", "de"] = "en",
    ) -> dict:
        """Describe fields of a dataset."""
        from wetterdienst.provider.dwd.observation.fields import read_description  # noqa: PLC0415

        if isinstance(dataset, str | Iterable):
            parameter_template = ParameterSearch.parse(dataset)
        elif isinstance(dataset, DatasetModel):
            parameter_template = ParameterSearch(
                resolution=dataset.resolution.value.value,
                dataset=dataset.name_original,
            )
        elif isinstance(dataset, ParameterSearch):
            parameter_template = dataset
        else:
            msg = "dataset must be a string, ParameterTemplate or DatasetModel"
            raise KeyError(msg)
        dataset = DwdObservationMetadata.search_parameter(parameter_template)[0].dataset
        period = parse_enumeration_from_template(period, Period)
        if period not in dataset.periods or period not in cls._available_periods:
            msg = f"Period {period} not available for dataset {dataset}"
            raise ValueError(msg)
        url = _build_url_from_dataset_and_period(dataset, period)
        file_index = _create_file_index_for_dwd_server(
            url=url,
            settings=Settings(),
            ttl=CacheExpiry.METAINDEX,
        ).collect()
        if language == "en":
            file_prefix = "DESCRIPTION_"
        elif language == "de":
            file_prefix = "BESCHREIBUNG_"
        else:
            msg = "Only language 'en' or 'de' supported"
            raise ValueError(msg)
        file_index = file_index.filter(pl.col("filename").str.contains(file_prefix))
        description_file_url = str(file_index.get_column("filename").item())
        log.info(f"Acquiring field information from {description_file_url}")
        return read_description(description_file_url, language=language)

    def _all(self) -> pl.LazyFrame:
        """:return:"""
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
                    other=file_index.select(pl.col("station_id")),
                    on=["station_id"],
                    how="inner",
                )
                stations.append(df)
        try:
            stations_df = pl.concat(stations)
        except ValueError:
            return pl.LazyFrame()
        stations_df = stations_df.unique(subset=["resolution", "dataset", "station_id"], keep="first")
        return stations_df.sort(by=[pl.col("station_id").cast(int)])
