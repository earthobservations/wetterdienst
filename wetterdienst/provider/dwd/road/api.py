# Copyright (c) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD road weather data provider."""

from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from functools import reduce
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, ClassVar
from urllib.parse import urljoin

import polars as pl

from wetterdienst.core.timeseries.metadata import (
    DATASET_NAME_DEFAULT,
    DatasetModel,
    ParameterModel,
    build_metadata_model,
)
from wetterdienst.core.timeseries.request import _DATETIME_TYPE, _PARAMETER_TYPE, _SETTINGS_TYPE, TimeseriesRequest
from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.dwd.metadata import _METADATA
from wetterdienst.util.eccodes import check_pdbufr
from wetterdienst.util.network import download_file, list_remote_files_fsspec

if TYPE_CHECKING:
    from io import BytesIO

    from wetterdienst import Settings
    from wetterdienst.core.timeseries.result import StationsResult

log = logging.getLogger(__name__)

DATE_REGEX = r"-(\d{10,})-"
TIME_COLUMNS = ("year", "month", "day", "hour", "minute")


DwdRoadMetadata = {
    **_METADATA,
    "kind": "observation",
    "timezone": "Europe/Berlin",
    "timezone_data": "UTC",
    "resolutions": [
        {
            "name": "15_minutes",
            "name_original": "15_minutes",
            "date_required": True,
            "datasets": [
                {
                    "name": DATASET_NAME_DEFAULT,
                    "name_original": DATASET_NAME_DEFAULT,
                    "grouped": True,
                    "periods": ["historical"],
                    "parameters": [
                        {
                            "name": "humidity",
                            "name_original": "relativeHumidity",
                            "unit_type": "fraction",
                            "unit": "percent",
                        },
                        {
                            "name": "precipitation_form",
                            "name_original": "precipitationType",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "totalPrecipitationOrTotalWaterEquivalent",
                            "unit_type": "precipitation",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_intensity",
                            "name_original": "intensityOfPrecipitation",
                            "unit_type": "precipitation_intensity",
                            "unit": "millimeter_per_hour",
                        },
                        {
                            "name": "road_surface_condition",
                            "name_original": "roadSurfaceCondition",
                            "unit_type": "dimensionless",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "airTemperature",
                            "unit_type": "temperature",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "dewpointTemperature",
                            "unit_type": "temperature",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "temperature_surface_mean",
                            "name_original": "roadSurfaceTemperature",
                            "unit_type": "temperature",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "visibility_range",
                            "name_original": "horizontalVisibility",
                            "unit_type": "length_medium",
                            "unit": "kilometer",
                        },
                        {
                            "name": "water_film_thickness",
                            "name_original": "waterFilmThickness",
                            "unit_type": "length_short",
                            "unit": "centimeter",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "windDirection",
                            "unit_type": "angle",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_direction_gust_max",
                            "name_original": "maximumWindGustDirection",
                            "unit_type": "angle",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "maximumWindGustSpeed",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "windSpeed",
                            "unit_type": "speed",
                            "unit": "meter_per_second",
                        },
                    ],
                },
            ],
        },
    ],
}
DwdRoadMetadata = build_metadata_model(DwdRoadMetadata, "DwdRoadMetadata")


class DwdRoadStationGroup(Enum):
    """Enumeration of DWD road weather station groups."""

    DD = "DD"
    DF = "DF"
    ER = "ER"
    FN = "FN"
    HJ = "HJ"
    HL = "HL"
    HS = "HS"
    HV = "HV"
    JA = "JA"
    JH = "JH"
    JS = "JS"
    KK = "KK"
    KM = "KM"
    KO = "KO"
    LF = "LF"
    LH = "LH"
    LW = "LW"
    MC = "MC"
    NC = "NC"
    ND = "ND"
    RB = "RB"
    RH = "RH"
    SF = "SF"
    SP = "SP"
    WW = "WW"
    XX = "XX"


# TODO: it seems that the following station groups are temporarily unavailable
TEMPORARILY_UNAVAILABLE_STATION_GROUPS = [
    DwdRoadStationGroup.DF,
    DwdRoadStationGroup.LF,
    DwdRoadStationGroup.SF,
    DwdRoadStationGroup.XX,
]


class DwdRoadValues(TimeseriesValues):
    """Values class for DWD road weather data."""

    def __init__(self, stations_result: StationsResult) -> None:
        """Initialize the DwdRoadValues class.

        First, check if the pdbufr library is available. If not, raise an ImportError.
        """
        check_pdbufr()
        super().__init__(stations_result)

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: DatasetModel,
    ) -> pl.DataFrame:
        """Collect data from DWD Road Weather stations."""
        station_group = self.sr.df.filter(pl.col("station_id").eq(station_id)).get_column("station_group").item()
        station_group = DwdRoadStationGroup(station_group)
        parameters = list(parameter_or_dataset)
        try:
            df = self._collect_data_by_station_group(station_group, parameters)
        except ValueError:
            return pl.DataFrame()
        df = df.filter(pl.col("station_id").eq(station_id))
        return df.select(
            pl.lit(parameter_or_dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(parameter_or_dataset.name, dtype=pl.String).alias("dataset"),
            "parameter",
            "station_id",
            "date",
            "value",
            "quality",
        )

    def _create_file_index_for_dwd_road_weather_station(
        self,
        road_weather_station_group: DwdRoadStationGroup,
    ) -> pl.DataFrame:
        """Create a file index for DWD Road Weather stations."""
        files = list_remote_files_fsspec(
            reduce(
                urljoin,
                [
                    "https://opendata.dwd.de/weather/weather_reports/road_weather_stations/",
                    road_weather_station_group.value,
                ],
            ),
            settings=self.sr.settings,
        )
        if not files:
            log.info(f"No files found for {road_weather_station_group.value}.")
            if road_weather_station_group in TEMPORARILY_UNAVAILABLE_STATION_GROUPS:
                log.info(f"Station group {road_weather_station_group.value} may be temporarily unavailable.")
        df = pl.DataFrame({"filename": files}, schema={"filename": pl.String})
        return df.with_columns(
            pl.col("filename")
            .str.split("/")
            .list.last()
            .str.extract(DATE_REGEX, 1)
            .str.to_datetime("%y%m%d%H%M", time_zone="UTC")
            .alias("date"),
        )

    def _collect_data_by_station_group(
        self,
        road_weather_station_group: DwdRoadStationGroup,
        parameters: list[ParameterModel],
    ) -> pl.DataFrame:
        """Collect data from DWD Road Weather stations."""
        remote_files = self._create_file_index_for_dwd_road_weather_station(road_weather_station_group)
        if self.sr.start_date:
            remote_files = remote_files.filter(
                pl.col("date").is_between(self.sr.start_date, self.sr.end_date),
            )
        remote_files = remote_files.get_column("filename").to_list()
        filenames_and_files = self._download_road_weather_observations(remote_files, self.sr.settings)
        return self._parse_dwd_road_weather_data(filenames_and_files, parameters)

    @staticmethod
    def _download_road_weather_observations(remote_files: list[str], settings: Settings) -> list[tuple[str, BytesIO]]:
        """Download the road weather station data from a given file and returns a DataFrame."""
        log.info(f"Downloading {len(remote_files)} files from DWD Road Weather.")
        with ThreadPoolExecutor() as p:
            files_in_bytes = p.map(
                lambda file: download_file(url=file, settings=settings, ttl=CacheExpiry.TWELVE_HOURS),
                remote_files,
            )
        return list(zip(remote_files, files_in_bytes, strict=False))

    def _parse_dwd_road_weather_data(
        self,
        filenames_and_files: list[tuple[str, BytesIO]],
        parameters: list[ParameterModel],
    ) -> pl.DataFrame:
        """Parse the road weather station data from a given file and returns a DataFrame."""
        return pl.concat(
            [
                self.__parse_dwd_road_weather_data(filename_and_file, parameters)
                for filename_and_file in filenames_and_files
            ],
        )

    @staticmethod
    def __parse_dwd_road_weather_data(
        filename_and_file: tuple[str, BytesIO],
        parameters: list[ParameterModel],
    ) -> pl.DataFrame:
        """Read the road weather station data from a given file and returns a DataFrame."""
        import pdbufr

        _, file = filename_and_file
        parameter_names = [parameter.name_original for parameter in parameters]
        first_batch = parameter_names[:10]
        second_batch = parameter_names[10:]
        with NamedTemporaryFile("w+b") as tf:
            tf.write(file.read())
            tf.seek(0)
            df = pdbufr.read_bufr(
                tf.name,
                columns=(
                    *TIME_COLUMNS,
                    "shortStationName",
                    *first_batch,
                ),
            )
            if second_batch:
                df2 = pdbufr.read_bufr(
                    tf.name,
                    columns=(
                        *TIME_COLUMNS,
                        "shortStationName",
                        *second_batch,
                    ),
                )
                df = df.merge(df2, on=(*TIME_COLUMNS, "shortStationName"))
        df = pl.from_pandas(df)
        df = df.select(
            pl.col("shortStationName").alias("station_id"),
            pl.concat_str(
                exprs=[
                    pl.col("year").cast(pl.String),
                    pl.col("month").cast(pl.String).str.pad_start(2, "0"),
                    pl.col("day").cast(pl.String).str.pad_start(2, "0"),
                    pl.col("hour").cast(pl.String).str.pad_start(2, "0"),
                    pl.col("minute").cast(pl.String).str.pad_start(2, "0"),
                ],
            )
            .str.to_datetime("%Y%m%d%H%M", time_zone="UTC")
            .alias("date"),
            *parameter_names,
        )
        df = df.unpivot(
            index=["station_id", "date"],
            variable_name="parameter",
            value_name="value",
        )
        return df.with_columns(
            pl.col("value").cast(pl.Float64),
            pl.lit(None, dtype=pl.Float64).alias("quality"),
        )


class DwdRoadRequest(TimeseriesRequest):
    """Request class for DWD road weather data."""

    metadata = DwdRoadMetadata
    _values = DwdRoadValues

    _base_columns: ClassVar = (
        "resolution",
        "dataset",
        "station_id",
        "start_date",
        "end_date",
        "latitude",
        "longitude",
        "height",
        "name",
        "state",
        "station_group",
        "road_name",
        "road_sector",
        "road_type",
        "road_surface_type",
        "road_surroundings_type",
    )
    _endpoint = (
        "https://www.dwd.de/DE/leistungen/opendata/help/stationen/sws_stations_xls.xlsx?__blob=publicationFile&v=11"
    )
    _column_mapping: ClassVar = {
        "Kennung": "station_id",
        "GMA-Name": "name",
        "Bundesland  ": "state",
        "Straße / Fahrtrichtung": "road_name",
        "Strecken-kilometer 100 m": "road_sector",
        """Streckentyp (Register "Typen")""": "road_type",
        """Streckenlage (Register "Typen")""": "road_surroundings_type",
        """Streckenbelag (Register "Typen")""": "road_surface_type",
        "Breite (Dezimalangabe)": "latitude",
        "Länge (Dezimalangabe)": "longitude",
        "Höhe in m über NN": "height",
        "GDS-Verzeichnis": "station_group",
        "außer Betrieb (gemeldet)": "has_file",
    }
    _dtypes: ClassVar = {
        "station_id": pl.String,
        "name": pl.String,
        "state": pl.String,
        "road_name": pl.String,
        "road_sector": pl.Utf8,
        "road_type": pl.Int64,
        "road_surroundings_type": pl.Int64,
        "road_surface_type": pl.Int64,
        "latitude": pl.Float64,
        "longitude": pl.Float64,
        "height": pl.Float64,
        "station_group": pl.Utf8,
        "has_file": pl.Utf8,
    }

    def __init__(
        self,
        parameters: _PARAMETER_TYPE,
        start_date: _DATETIME_TYPE = None,
        end_date: _DATETIME_TYPE = None,
        settings: _SETTINGS_TYPE = None,
    ) -> None:
        """Initialize the DwdRoadRequest class.

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
        log.info(f"Downloading file {self._endpoint}.")
        payload = download_file(self._endpoint, self.settings, CacheExpiry.METAINDEX)
        df = pl.read_excel(source=payload, sheet_name="Tabelle1", infer_schema_length=0)
        df = df.rename(mapping=self._column_mapping)
        df = df.select(pl.col(col) for col in self._column_mapping.values())
        df = df.filter(
            pl.col("has_file").ne("x") & pl.col("station_group").ne("0") & pl.col("station_id").is_not_null(),
        )
        df = df.with_columns(
            pl.lit(self.metadata[0].name, dtype=pl.String).alias("resolution"),
            pl.lit(self.metadata[0].datasets[0].name, dtype=pl.String).alias("dataset"),
            pl.col("longitude").str.replace(",", "."),
            pl.col("latitude").str.replace(",", "."),
            pl.when(~pl.col("road_type").str.contains("x")).then(pl.col("road_type")),
            pl.when(~pl.col("road_surroundings_type").str.contains("x")).then(
                pl.col("road_surroundings_type"),
            ),
            pl.when(~pl.col("road_surface_type").str.contains("x")).then(
                pl.col("road_surface_type"),
            ),
        )
        df = df.with_columns(pl.col(col).cast(dtype) for col, dtype in self._dtypes.items())
        return df.lazy()
