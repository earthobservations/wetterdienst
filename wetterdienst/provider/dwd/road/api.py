# Copyright (c) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from enum import Enum
from functools import reduce
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING
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
from wetterdienst.metadata.columns import Columns
from wetterdienst.provider.dwd.metadata import _METADATA
from wetterdienst.util.eccodes import check_pdbufr
from wetterdienst.util.network import download_file, list_remote_files_fsspec

if TYPE_CHECKING:
    from io import BytesIO

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
                }
            ],
        }
    ],
}
DwdRoadMetadata = build_metadata_model(DwdRoadMetadata, "DwdRoadMetadata")


class DwdRoadStationGroup(Enum):
    """
    enumeration for road weather subset groups
    """

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
    """
    The DwdRoadValues class represents a request for
    observation data from road weather stations as provided by the DWD service.
    """

    def __init__(self, stations_result: StationsResult) -> None:
        check_pdbufr()
        super().__init__(stations_result)

    def _collect_station_parameter_or_dataset(
        self, station_id: str, parameter_or_dataset: DatasetModel
    ) -> pl.DataFrame:
        """Takes station_name to download and parse RoadWeather Station data"""
        station_group = (
            self.sr.df.filter(pl.col(Columns.STATION_ID.value).eq(station_id))
            .get_column(Columns.STATION_GROUP.value)
            .item()
        )
        station_group = DwdRoadStationGroup(station_group)
        parameters = [parameter for parameter in parameter_or_dataset]
        try:
            df = self._collect_data_by_station_group(station_group, parameters)
        except ValueError:
            return pl.DataFrame()
        return df.filter(pl.col(Columns.STATION_ID.value).eq(station_id))

    def _create_file_index_for_dwd_road_weather_station(
        self,
        road_weather_station_group: DwdRoadStationGroup,
    ) -> pl.DataFrame:
        """
        Creates a file_index DataFrame from RoadWeather Station directory
        """
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
        df = pl.DataFrame({Columns.FILENAME.value: files}, schema={Columns.FILENAME.value: pl.String})
        return df.with_columns(
            pl.col(Columns.FILENAME.value)
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
        """
        Method to collect data for one specified parameter. Manages restoring,
        collection and storing of data, transformation and combination of different
        periods.

        Args:
            road_weather_station_group: subset id for which parameter is collected

        Returns:
            pandas.DataFrame for given parameter of station
        """
        remote_files = self._create_file_index_for_dwd_road_weather_station(road_weather_station_group)
        if self.sr.start_date:
            remote_files = remote_files.filter(
                pl.col(Columns.DATE.value).is_between(self.sr.start_date, self.sr.end_date),
            )
        remote_files = remote_files.get_column(Columns.FILENAME.value).to_list()
        filenames_and_files = self._download_road_weather_observations(remote_files, self.sr.settings)
        return self._parse_dwd_road_weather_data(filenames_and_files, parameters)

    @staticmethod
    def _download_road_weather_observations(remote_files: list[str], settings) -> list[tuple[str, BytesIO]]:
        """
        :param remote_files:    List of requested files
        :return:                List of downloaded files
        """
        log.info(f"Downloading {len(remote_files)} files from DWD Road Weather.")
        with ThreadPoolExecutor() as p:
            files_in_bytes = p.map(
                lambda file: download_file(url=file, settings=settings, ttl=CacheExpiry.TWELVE_HOURS),
                remote_files,
            )

        return list(zip(remote_files, files_in_bytes))

    def _parse_dwd_road_weather_data(
        self,
        filenames_and_files: list[tuple[str, BytesIO]],
        parameters: list[ParameterModel],
    ) -> pl.DataFrame:
        """
        This function is used to read the road weather station data from given bytes object.
        The filename is required to defined if and where an error happened.

        Args:
            filenames_and_files: list of tuples of a filename and its local stored file
            that should be read

        Returns:
            pandas.DataFrame with requested data, for different station ids the data is
            still put into one DataFrame
        """
        return pl.concat(
            [
                self.__parse_dwd_road_weather_data(filename_and_file, parameters)
                for filename_and_file in filenames_and_files
            ],
        )

    @staticmethod
    def __parse_dwd_road_weather_data(
        filename_and_file: tuple[str, BytesIO], parameters: list[ParameterModel]
    ) -> pl.DataFrame:
        """
        A wrapping function that only handles data for one station id. The files passed to
        it are thus related to this id. This is important for storing the data locally as
        the DataFrame that is stored should obviously only handle one station at a time.
        Args:
            filename_and_file: the files belonging to one station
            resolution: enumeration of time resolution used to correctly parse the
            date field
        Returns:
            pandas.DataFrame with data from that station, acn be empty if no data is
            provided or local file is not found or has no data in it
        """
        import pdbufr

        _, file = filename_and_file
        tf = NamedTemporaryFile("w+b")
        tf.write(file.read())
        tf.seek(0)
        parameter_names = [parameter.name_original for parameter in parameters]
        first_batch = parameter_names[:10]
        second_batch = parameter_names[10:]
        df = pdbufr.read_bufr(
            tf.name,
            columns=TIME_COLUMNS
            + (
                "shortStationName",
                *first_batch,
            ),
        )
        if second_batch:
            df2 = pdbufr.read_bufr(
                tf.name,
                columns=TIME_COLUMNS
                + (
                    "shortStationName",
                    *second_batch,
                ),
            )
            df = df.merge(df2, on=TIME_COLUMNS + ("shortStationName",))
        df = pl.from_pandas(df)
        df = df.select(
            pl.col("shortStationName").alias(Columns.STATION_ID.value),
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
            .alias(Columns.DATE.value),
            *parameter_names,
        )
        df = df.unpivot(
            index=[Columns.STATION_ID.value, Columns.DATE.value],
            variable_name=Columns.PARAMETER.value,
            value_name=Columns.VALUE.value,
        )
        return df.with_columns(
            pl.col("value").cast(pl.Float64),
            pl.lit(None, dtype=pl.Float64).alias(Columns.QUALITY.value),
        )


class DwdRoadRequest(TimeseriesRequest):
    metadata = DwdRoadMetadata
    _values = DwdRoadValues

    _base_columns = list(TimeseriesRequest._base_columns)
    _base_columns.extend(
        (
            Columns.STATION_GROUP.value,
            Columns.ROAD_NAME.value,
            Columns.ROAD_SECTOR.value,
            Columns.ROAD_TYPE.value,
            Columns.ROAD_SURFACE_TYPE.value,
            Columns.ROAD_SURROUNDINGS_TYPE.value,
        ),
    )
    _endpoint = (
        "https://www.dwd.de/DE/leistungen/opendata/help/stationen/sws_stations_xls.xlsx?__blob=publicationFile&v=11"
    )
    _column_mapping = {
        "Kennung": Columns.STATION_ID.value,
        "GMA-Name": Columns.NAME.value,
        "Bundesland  ": Columns.STATE.value,
        "Straße / Fahrtrichtung": Columns.ROAD_NAME.value,
        "Strecken-kilometer 100 m": Columns.ROAD_SECTOR.value,
        """Streckentyp (Register "Typen")""": Columns.ROAD_TYPE.value,
        """Streckenlage (Register "Typen")""": Columns.ROAD_SURROUNDINGS_TYPE.value,
        """Streckenbelag (Register "Typen")""": Columns.ROAD_SURFACE_TYPE.value,
        "Breite (Dezimalangabe)": Columns.LATITUDE.value,
        "Länge (Dezimalangabe)": Columns.LONGITUDE.value,
        "Höhe in m über NN": Columns.HEIGHT.value,
        "GDS-Verzeichnis": Columns.STATION_GROUP.value,
        "außer Betrieb (gemeldet)": Columns.HAS_FILE.value,
    }
    _dtypes = {
        Columns.STATION_ID.value: pl.String,
        Columns.NAME.value: pl.String,
        Columns.STATE.value: pl.String,
        Columns.ROAD_NAME.value: pl.String,
        Columns.ROAD_SECTOR.value: pl.Utf8,
        Columns.ROAD_TYPE.value: pl.Int64,
        Columns.ROAD_SURROUNDINGS_TYPE.value: pl.Int64,
        Columns.ROAD_SURFACE_TYPE.value: pl.Int64,
        Columns.LATITUDE.value: pl.Float64,
        Columns.LONGITUDE.value: pl.Float64,
        Columns.HEIGHT.value: pl.Float64,
        Columns.STATION_GROUP.value: pl.Utf8,
        Columns.HAS_FILE.value: pl.Utf8,
    }

    def __init__(
        self,
        parameters: _PARAMETER_TYPE,
        start_date: _DATETIME_TYPE = None,
        end_date: _DATETIME_TYPE = None,
        settings: _SETTINGS_TYPE = None,
    ):
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
            pl.col(Columns.HAS_FILE.value).ne("x")
            & pl.col(Columns.STATION_GROUP.value).ne("0")
            & pl.col(Columns.STATION_ID.value).is_not_null(),
        )
        df = df.with_columns(
            pl.col(Columns.LONGITUDE.value).str.replace(",", "."),
            pl.col(Columns.LATITUDE.value).str.replace(",", "."),
            pl.when(~pl.col(Columns.ROAD_TYPE.value).str.contains("x")).then(pl.col(Columns.ROAD_TYPE.value)),
            pl.when(~pl.col(Columns.ROAD_SURROUNDINGS_TYPE.value).str.contains("x")).then(
                pl.col(Columns.ROAD_SURROUNDINGS_TYPE.value),
            ),
            pl.when(~pl.col(Columns.ROAD_SURFACE_TYPE.value).str.contains("x")).then(
                pl.col(Columns.ROAD_SURFACE_TYPE.value),
            ),
        )
        df = df.with_columns(pl.col(col).cast(dtype) for col, dtype in self._dtypes.items())
        return df.lazy()
