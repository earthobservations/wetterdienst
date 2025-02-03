# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import datetime as dt
import gzip
import logging
from io import BytesIO
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.core.timeseries.request import _DATETIME_TYPE, _PARAMETER_TYPE, _SETTINGS_TYPE, TimeseriesRequest
from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider.eccc.observation.metadata import EcccObservationMetadata
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from collections.abc import Iterator

    from wetterdienst.core.timeseries.metadata import DatasetModel

log = logging.getLogger(__name__)


class EcccObservationValues(TimeseriesValues):
    _base_url = (
        "https://climate.weather.gc.ca/climate_data/bulk_data_e.html?"
        "format=csv&stationID={0}&timeframe={1}"
        "&submit= Download+Data"
    )

    _timeframe_mapping = {
        Resolution.HOURLY: "1",
        Resolution.DAILY: "2",
        Resolution.MONTHLY: "3",
        Resolution.ANNUAL: "4",
    }

    @staticmethod
    def _tidy_up_df(df: pl.LazyFrame) -> pl.LazyFrame:
        """
        Tidy up dataframe pairwise by column 'DATE', 'Temp (°C)', 'Temp Flag', ...

        :param df: DataFrame with loaded data
        :return: tidied DataFrame
        """
        data = []

        columns = df.columns
        for parameter_column, quality_column in zip(columns[1::2], columns[2::2]):
            df_parameter = df.select(
                pl.col(Columns.DATE.value),
                pl.lit(parameter_column).alias(Columns.PARAMETER.value),
                pl.col(parameter_column).replace("", None).alias(Columns.VALUE.value),
                pl.col(quality_column).replace("", None).alias(Columns.QUALITY.value),
            )
            data.append(df_parameter)

        try:
            return pl.concat(data)
        except ValueError:
            return pl.LazyFrame()

    def _collect_station_parameter_or_dataset(
        self, station_id: str, parameter_or_dataset: DatasetModel
    ) -> pl.DataFrame:
        """

        :param station_id: station id being queried
        :param parameter: parameter being queried
        :param dataset: dataset of query, can be skipped as ECCC has unique dataset
        :return: pandas.DataFrame with data
        """
        meta = self.sr.df.filter(pl.col(Columns.STATION_ID.value).eq(station_id))

        start_year, end_year = (
            meta.select(
                [
                    pl.col(Columns.START_DATE.value).dt.year(),
                    pl.col(Columns.END_DATE.value).dt.year(),
                ],
            )
            .transpose()
            .to_series()
            .to_list()
        )

        # start_date and end_date from request
        start_date = self.sr.stations.start_date
        end_date = self.sr.stations.end_date

        start_year = start_year and max(start_year, start_date and start_date.year or start_year)
        end_year = end_year and min(end_year, end_date and end_date.year or end_year)

        # Following lines may partially be based on @Zeitsperre's canada-climate-python
        # code at https://github.com/Zeitsperre/canada-climate-python/blob/
        # master/ECCC_stations_fulldownload.py
        data = []

        # check that station has a first and last year value
        if start_year and end_year:
            for url in self._create_file_urls(station_id, parameter_or_dataset.resolution.value, start_year, end_year):
                log.info(f"Acquiring file from {url}")
                payload = download_file(url, self.sr.stations.settings, CacheExpiry.NO_CACHE)
                df = pl.read_csv(payload, infer_schema_length=0).lazy()
                df = df.rename(mapping=lambda col: col.lower())
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
                data.append(df)

        try:
            df = pl.concat(data)
        except ValueError:
            df = pl.LazyFrame()
        mapping = {"date/time (lst)": Columns.DATE.value, "date/time": Columns.DATE.value}
        df = df.rename(
            mapping=lambda col: mapping.get(col, col),
        )

        df = self._tidy_up_df(df)

        return df.with_columns(
            pl.col(Columns.DATE.value).str.to_datetime("%Y-%m-%d", time_zone="UTC"),
            pl.lit(station_id).alias(Columns.STATION_ID.value),
            pl.when(pl.col(Columns.VALUE.value).str.starts_with("<"))
            .then(pl.col(Columns.VALUE.value).str.slice(1))
            .otherwise(pl.col(Columns.VALUE.value))
            .alias(Columns.VALUE.value)
            .cast(pl.Float64),
            pl.lit(value=None, dtype=pl.Float64).alias(Columns.QUALITY.value),
        ).collect()

    def _create_file_urls(
        self, station_id: str, resolution: Resolution, start_year: int, end_year: int
    ) -> Iterator[str]:
        """

        :param station_id:
        :param start_year:
        :param end_year:
        :return:
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
    """
    Download weather data from Environment and Climate Change Canada (ECCC).
    - https://www.canada.ca/en/environment-climate-change.html
    - https://www.canada.ca/en/services/environment/weather.html

    Original code by Trevor James Smith. Thanks!
    - https://github.com/Zeitsperre/canada-climate-python

    """

    metadata = EcccObservationMetadata
    _values = EcccObservationValues

    _columns_mapping: dict = {
        "station id": Columns.STATION_ID.value,
        "name": Columns.NAME.value,
        "province": Columns.STATE.value,
        "latitude (decimal degrees)": Columns.LATITUDE.value,
        "longitude (decimal degrees)": Columns.LONGITUDE.value,
        "elevation (m)": Columns.HEIGHT.value,
        "first year": Columns.START_DATE.value,
        "last year": Columns.END_DATE.value,
    }

    def __init__(
        self,
        parameters: _PARAMETER_TYPE,
        start_date: _DATETIME_TYPE = None,
        end_date: _DATETIME_TYPE = None,
        settings: _SETTINGS_TYPE = None,
    ) -> None:
        """

        :param parameters: parameter or list of parameters that are being queried
        :param start_date: start date for values filtering
        :param end_date: end date for values filtering
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
        df = pl.read_csv(csv_payload, has_header=True, skip_rows=header, infer_schema_length=0).lazy()

        df = df.rename(mapping=lambda col: col.lower())

        df = df.drop("latitude", "longitude")

        df = df.rename(mapping=self._columns_mapping)

        df = df.with_columns(
            pl.when(pl.col(Columns.START_DATE.value).ne("")).then(pl.col(Columns.START_DATE.value)),
            pl.when(pl.col(Columns.END_DATE.value).ne("")).then(pl.col(Columns.END_DATE.value)),
            pl.when(pl.col(Columns.HEIGHT.value).ne("")).then(pl.col(Columns.HEIGHT.value)),
        )

        df = df.with_columns(
            pl.col(Columns.START_DATE.value).fill_null(pl.col(Columns.START_DATE.value).cast(int).min()),
            pl.col(Columns.END_DATE.value).fill_null(pl.col(Columns.END_DATE.value).cast(int).max()),
        )

        df = df.with_columns(
            pl.col(Columns.START_DATE.value).str.to_datetime("%Y", time_zone="UTC"),
            pl.col(Columns.END_DATE.value)
            .cast(int)
            .add(1)
            .map_elements(
                lambda v: dt.datetime(v, 1, 1, tzinfo=ZoneInfo("UTC")) - dt.timedelta(days=1), return_dtype=pl.Datetime
            ),
        )

        return df.filter(pl.col(Columns.LATITUDE.value).ne("") & pl.col(Columns.LONGITUDE.value).ne(""))

    def _download_stations(self) -> tuple[BytesIO, int]:
        """
        Download station list from ECCC FTP server.

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
        except Exception as e:
            log.exception(e)
            log.exception(f"Unable to access Google drive server at {gdrive_url}")

            # Fall back to different source.
            try:
                log.info(f"Downloading file {http_url}.")
                response = download_file(http_url, self.settings, CacheExpiry.METAINDEX)
                with gzip.open(response, mode="rb") as f:
                    payload = BytesIO(f.read())
                source = 1
            except Exception as e:
                log.exception(e)
                log.exception(f"Unable to access HTTP server at {http_url}")

        if not payload:
            raise FileNotFoundError("Unable to acquire ECCC stations list")

        return payload, source
