# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""ECCC observation data provider."""

from __future__ import annotations

import datetime as dt
import gzip
import logging
from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from typing import TYPE_CHECKING, ClassVar
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.core.timeseries.request import _DATETIME_TYPE, _PARAMETER_TYPE, _SETTINGS_TYPE, TimeseriesRequest
from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.eccc.observation.metadata import EcccObservationMetadata
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from collections.abc import Iterator

    from wetterdienst.core.timeseries.metadata import DatasetModel

log = logging.getLogger(__name__)


class EcccObservationValues(TimeseriesValues):
    """Values class for Environment and Climate Change Canada (ECCC) observation data."""

    _base_url = (
        "https://climate.weather.gc.ca/climate_data/bulk_data_e.html?"
        "format=csv&stationID={0}&timeframe={1}"
        "&submit= Download+Data"
    )

    _timeframe_mapping: ClassVar = {
        Resolution.HOURLY: "1",
        Resolution.DAILY: "2",
        Resolution.MONTHLY: "3",
        Resolution.ANNUAL: "4",
    }

    @staticmethod
    def _tidy_up_df(df: pl.DataFrame) -> pl.DataFrame:
        """Tidy up dataframe pairwise by column 'DATE', 'Temp (°C)', 'Temp Flag', ..."""
        data = []
        columns = df.columns
        for parameter_column, quality_column in zip(columns[1::2], columns[2::2], strict=False):
            df_parameter = df.select(
                pl.col("date"),
                pl.lit(parameter_column).alias("parameter"),
                pl.col(parameter_column).replace("", None).alias("value"),
                pl.col(quality_column).replace("", None).alias("quality"),
            )
            data.append(df_parameter)
        try:
            return pl.concat(data)
        except ValueError:
            return pl.DataFrame()

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: DatasetModel,
    ) -> pl.DataFrame:
        """Collect station dataset."""
        meta = self.sr.df.filter(pl.col("station_id").eq(station_id))
        start_year, end_year = (
            meta.select(
                [
                    pl.col("start_date").dt.year(),
                    pl.col("end_date").dt.year(),
                ],
            )
            .transpose()
            .to_series()
            .to_list()
        )
        # start_date and end_date from request
        start_date = self.sr.stations.start_date
        end_date = self.sr.stations.end_date
        start_year = start_year and max(start_year, (start_date and start_date.year) or start_year)
        end_year = end_year and min(end_year, (end_date and end_date.year) or end_year)
        # Following lines may partially be based on @Zeitsperre's canada-climate-python
        # code at https://github.com/Zeitsperre/canada-climate-python/blob/
        # master/ECCC_stations_fulldownload.py
        # check that station has a first and last year value
        if not (start_year and end_year):
            return pl.DataFrame()
        remote_files = list(
            self._create_file_urls(station_id, parameter_or_dataset.resolution.value, start_year, end_year),
        )
        if len(remote_files) > 1:
            with ThreadPoolExecutor() as p:
                files_in_bytes = p.map(
                    lambda remote_file: download_file(
                        url=remote_file,
                        settings=self.sr.stations.settings,
                        ttl=CacheExpiry.FIVE_MINUTES,
                    ),
                    remote_files,
                )
        else:
            files_in_bytes = [
                download_file(url=remote_files[0], settings=self.sr.stations.settings, ttl=CacheExpiry.FIVE_MINUTES),
            ]
        data = []
        for file_in_bytes in files_in_bytes:
            df = pl.read_csv(file_in_bytes, infer_schema_length=0)
            data.append(df)
        try:
            df = pl.concat(data)
        except ValueError:
            return pl.DataFrame()
        df = df.rename(str.lower)
        droppable_columns = [
            "longitude (x)",
            "latitude (y)",
            "station name",
            "climate id",
            "year",
            "month",
            "day",
            "time (lst)",
            "data quality",
        ]
        df = df.drop(*droppable_columns, strict=False)
        mapping = {"date/time (lst)": "date", "date/time": "date"}
        df = df.rename(
            mapping=lambda col: mapping.get(col, col),
        )
        df = self._tidy_up_df(df)
        return df.select(
            pl.lit(parameter_or_dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(parameter_or_dataset.name, dtype=pl.String).alias("dataset"),
            "parameter",
            pl.lit(station_id, dtype=pl.String).alias("station_id"),
            pl.col("date").str.to_datetime("%Y-%m-%d", time_zone="UTC"),
            pl.when(pl.col("value").str.starts_with("<"))
            .then(pl.col("value").str.slice(1))
            .otherwise(pl.col("value"))
            .alias("value")
            .cast(pl.Float64),
            pl.lit(None, dtype=pl.Float64).alias("quality"),
        )

    def _create_file_urls(
        self,
        station_id: str,
        resolution: Resolution,
        start_year: int,
        end_year: int,
    ) -> Iterator[str]:
        """Create URLs for downloading data files.

        The URLs are created based on the station ID, resolution, and the years
        for which data is requested.
        """
        freq = "1y"
        if resolution == Resolution.HOURLY:
            freq = "1mo"
        # For hourly data request only necessary data to reduce amount of data being
        # downloaded and parsed
        for date in pl.datetime_range(
            dt.datetime(start_year, 1, 1, tzinfo=ZoneInfo("UTC")),
            dt.datetime(end_year + 1, 1, 1, tzinfo=ZoneInfo("UTC")),
            interval=freq,
            eager=True,
        ):
            url = self._base_url.format(int(station_id), self._timeframe_mapping[resolution])
            url += f"&Year={date.year}"
            if resolution == Resolution.HOURLY:
                url += f"&Month={date.month}"
            yield url


class EcccObservationRequest(TimeseriesRequest):
    """Download weather data from Environment and Climate Change Canada (ECCC).

    - https://www.canada.ca/en/environment-climate-change.html
    - https://www.canada.ca/en/services/environment/weather.html

    Original code by Trevor James Smith. Thanks!
    - https://github.com/Zeitsperre/canada-climate-python

    """

    metadata = EcccObservationMetadata
    _values = EcccObservationValues

    _columns_mapping: ClassVar[dict] = {
        "station id": "station_id",
        "name": "name",
        "province": "state",
        "latitude (decimal degrees)": "latitude",
        "longitude (decimal degrees)": "longitude",
        "elevation (m)": "height",
        "first year": "start_date",
        "last year": "end_date",
    }

    def __init__(
        self,
        parameters: _PARAMETER_TYPE,
        start_date: _DATETIME_TYPE = None,
        end_date: _DATETIME_TYPE = None,
        settings: _SETTINGS_TYPE = None,
    ) -> None:
        """Initialize the EcccObservationRequest class.

        Args:
            parameters: requested parameters
            start_date: start date of the requested data
            end_date: end date of the requested data
            settings: settings for the request

        """
        super().__init__(
            parameters=parameters,
            start_date=start_date,
            end_date=end_date,
            settings=settings,
        )

    def _all(self) -> pl.LazyFrame:
        # Acquire raw CSV payload.
        csv_payload, source = self._download_stations()
        header = 2 if source else 3
        # Read into Pandas data frame.
        df_raw = pl.read_csv(csv_payload, has_header=True, skip_rows=header, infer_schema_length=0).lazy()
        df_raw = df_raw.rename(str.lower)
        df_raw = df_raw.drop("latitude", "longitude")
        df_raw = df_raw.rename(self._columns_mapping)
        df_raw = df_raw.with_columns(
            pl.when(pl.col("start_date").ne("")).then(pl.col("start_date")),
            pl.when(pl.col("end_date").ne("")).then(pl.col("end_date")),
            pl.when(pl.col("height").ne("")).then(pl.col("height")),
        )
        df_raw = df_raw.with_columns(
            pl.col("start_date").fill_null(pl.col("start_date").cast(int).min()),
            pl.col("end_date").fill_null(pl.col("end_date").cast(int).max()),
        )
        df_raw = df_raw.with_columns(
            pl.col("start_date").str.to_datetime("%Y", time_zone="UTC"),
            pl.col("end_date")
            .cast(pl.Int64)
            .add(1)
            .cast(pl.String)
            .str.to_datetime("%Y", time_zone="UTC")
            .dt.offset_by("-1d"),
        )
        # combinations of resolution and dataset
        resolutions_and_datasets = {
            (parameter.dataset.resolution.name, parameter.dataset.name) for parameter in self.parameters
        }
        data = []
        # for each combination of resolution and dataset create a new DataFrame with the columns
        for resolution, dataset in resolutions_and_datasets:
            data.append(
                df_raw.with_columns(
                    pl.lit(resolution, pl.String).alias("resolution"),
                    pl.lit(dataset, pl.String).alias("dataset"),
                ),
            )
        df = pl.concat(data)
        return df.filter(pl.col("latitude").ne("") & pl.col("longitude").ne(""))

    def _download_stations(self) -> tuple[BytesIO, int]:
        """Download station list from ECCC FTP server.

        :return: CSV payload, source identifier
        """
        gdrive_url = "https://drive.google.com/uc?id=1HDRnj41YBWpMioLPwAFiLlK4SK8NV72C"
        http_url = (
            "https://github.com/earthobservations/testdata/raw/main/ftp.tor.ec.gc.ca/Pub/"
            "Get_More_Data_Plus_de_donnees/Station%20Inventory%20EN.csv.gz"
        )

        payload = None
        source = None
        try:
            log.info(f"Downloading file {gdrive_url}.")
            payload = download_file(gdrive_url, self.settings, CacheExpiry.METAINDEX)
            source = 0
        except Exception:
            log.exception(f"Unable to access Google drive server at {gdrive_url}")
            # Fall back to different source.
            try:
                log.info(f"Downloading file {http_url}.")
                response = download_file(http_url, self.settings, CacheExpiry.METAINDEX)
                with gzip.open(response, mode="rb") as f:
                    payload = BytesIO(f.read())
                source = 1
            except Exception:
                log.exception(f"Unable to access HTTP server at {http_url}")
        if not payload:
            msg = "Unable to acquire ECCC stations list"
            raise FileNotFoundError(msg)
        return payload, source
