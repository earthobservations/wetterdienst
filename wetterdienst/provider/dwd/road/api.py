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

from wetterdienst import Kind, Parameter, Provider, Settings
from wetterdienst.core.timeseries.request import TimeseriesRequest
from wetterdienst.core.timeseries.values import TimeseriesValues
from wetterdienst.metadata.columns import Columns
from wetterdienst.metadata.datarange import DataRange
from wetterdienst.metadata.metadata_model import DatasetModel, MetadataModel, ParameterModel
from wetterdienst.metadata.timezone import Timezone
from wetterdienst.metadata.unit import OriginUnit, SIUnit, UnitEnum
from wetterdienst.util.cache import CacheExpiry
from wetterdienst.util.eccodes import check_pdbufr
from wetterdienst.util.network import download_file, list_remote_files_fsspec
from wetterdienst.util.parameter import DatasetTreeCore

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Sequence
    from io import BytesIO

    from wetterdienst.core.timeseries.result import StationsResult

log = logging.getLogger(__name__)

DATE_REGEX = r"-(\d{10,})-"
TIME_COLUMNS = ("year", "month", "day", "hour", "minute")


class DwdRoadParameter(DatasetTreeCore):
    """
    enumeration for different parameter/variables
    measured by dwd road weather stations
    """

    class MINUTE_15(DatasetTreeCore):
        class ROAD_WEATHER(Enum):
            # class ROAD_WEATHER(Enum):
            HUMIDITY = "relativeHumidity"
            PRECIPITATION_FORM = "precipitationType"
            PRECIPITATION_HEIGHT = "totalPrecipitationOrTotalWaterEquivalent"
            PRECIPITATION_INTENSITY = "intensityOfPrecipitation"
            ROAD_SURFACE_CONDITION = "roadSurfaceCondition"
            TEMPERATURE_AIR_MEAN_2M = "airTemperature"
            TEMPERATURE_DEW_POINT_MEAN_2M = "dewpointTemperature"
            TEMPERATURE_SURFACE_MEAN = "roadSurfaceTemperature"
            VISIBILITY_RANGE = "horizontalVisibility"
            WATER_FILM_THICKNESS = "waterFilmThickness"
            WIND_DIRECTION = "windDirection"
            WIND_DIRECTION_GUST_MAX = "maximumWindGustDirection"
            WIND_GUST_MAX = "maximumWindGustSpeed"
            WIND_SPEED = "windSpeed"
            # INTENSITY_OF_PHENOMENA = "intensityOfPhenomena"  # noqa: ERA001

        HUMIDITY = ROAD_WEATHER.HUMIDITY
        PRECIPITATION_FORM = ROAD_WEATHER.PRECIPITATION_FORM
        PRECIPITATION_HEIGHT = ROAD_WEATHER.PRECIPITATION_HEIGHT
        PRECIPITATION_INTENSITY = ROAD_WEATHER.PRECIPITATION_INTENSITY
        ROAD_SURFACE_CONDITION = ROAD_WEATHER.ROAD_SURFACE_CONDITION
        TEMPERATURE_AIR_MEAN_2M = ROAD_WEATHER.TEMPERATURE_AIR_MEAN_2M
        TEMPERATURE_DEW_POINT_MEAN_2M = ROAD_WEATHER.TEMPERATURE_DEW_POINT_MEAN_2M
        TEMPERATURE_SURFACE_MEAN = ROAD_WEATHER.TEMPERATURE_SURFACE_MEAN
        VISIBILITY_RANGE = ROAD_WEATHER.VISIBILITY_RANGE
        WATER_FILM_THICKNESS = ROAD_WEATHER.WATER_FILM_THICKNESS
        WIND_DIRECTION = ROAD_WEATHER.WIND_DIRECTION
        WIND_DIRECTION_GUST_MAX = ROAD_WEATHER.WIND_DIRECTION_GUST_MAX
        WIND_GUST_MAX = ROAD_WEATHER.WIND_GUST_MAX
        WIND_SPEED = ROAD_WEATHER.WIND_SPEED
        # INTENSITY_OF_PHENOMENA = MINUTE_15.INTENSITY_OF_PHENOMENA  # noqa: ERA001


class DwdRoadUnit(DatasetTreeCore):
    """
    enumeration for different parameter/variables
    measured by dwd road weather stations
    """

    class MINUTE_15(DatasetTreeCore):
        class ROAD_WEATHER(UnitEnum):
            HUMIDITY = OriginUnit.PERCENT.value, SIUnit.PERCENT.value
            PRECIPITATION_FORM = OriginUnit.DIMENSIONLESS.value, OriginUnit.DIMENSIONLESS.value
            PRECIPITATION_HEIGHT = OriginUnit.MILLIMETER.value, SIUnit.KILOGRAM_PER_SQUARE_METER.value
            PRECIPITATION_INTENSITY = OriginUnit.MILLIMETER_PER_HOUR.value, SIUnit.MILLIMETER_PER_HOUR.value
            ROAD_SURFACE_CONDITION = OriginUnit.DIMENSIONLESS.value, OriginUnit.DIMENSIONLESS.value
            TEMPERATURE_AIR_MEAN_2M = OriginUnit.DEGREE_KELVIN.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_DEW_POINT_MEAN_2M = OriginUnit.DEGREE_KELVIN.value, SIUnit.DEGREE_KELVIN.value
            TEMPERATURE_SURFACE_MEAN = OriginUnit.DEGREE_KELVIN.value, SIUnit.DEGREE_KELVIN.value
            VISIBILITY_RANGE = OriginUnit.KILOMETER.value, SIUnit.METER.value
            WATER_FILM_THICKNESS = OriginUnit.CENTIMETER.value, SIUnit.METER.value
            WIND_DIRECTION = OriginUnit.DEGREE.value, SIUnit.DEGREE.value
            WIND_DIRECTION_GUST_MAX = OriginUnit.DEGREE.value, SIUnit.DEGREE.value
            WIND_GUST_MAX = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value
            WIND_SPEED = OriginUnit.METER_PER_SECOND.value, SIUnit.METER_PER_SECOND.value
            # INTENSITY_OF_PHENOMENA = OriginUnit.DIMENSIONLESS.value, OriginUnit.DIMENSIONLESS.value  # noqa: ERA001


DwdRoadMetadata = {
    "resolutions": [
        {
            "name": "15_minutes",
            "name_original": "15_minutes",
            "datasets": [
                {
                    "name": "road_weather",
                    "name_original": "road_weather",
                    "grouped": True,
                    "periods": ["historical"],
                    "parameters": [
                        {
                            "name": "humidity",
                            "name_original": "relativeHumidity",
                            "unit": "percent",
                            "unit_original": "percent",
                        },
                        {
                            "name": "precipitation_form",
                            "name_original": "precipitationType",
                            "unit": "dimensionless",
                            "unit_original": "dimensionless",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "totalPrecipitationOrTotalWaterEquivalent",
                            "unit": "kilogram_per_square_meter",
                            "unit_original": "millimeter",
                        },
                        {
                            "name": "precipitation_intensity",
                            "name_original": "intensityOfPrecipitation",
                            "unit": "millimeter_per_hour",
                            "unit_original": "millimeter_per_hour",
                        },
                        {
                            "name": "road_surface_condition",
                            "name_original": "roadSurfaceCondition",
                            "unit": "dimensionless",
                            "unit_original": "dimensionless",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "airTemperature",
                            "unit": "degree_kelvin",
                            "unit_original": "degree_kelvin",
                        },
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "dewpointTemperature",
                            "unit": "degree_kelvin",
                            "unit_original": "degree_kelvin",
                        },
                        {
                            "name": "temperature_surface_mean",
                            "name_original": "roadSurfaceTemperature",
                            "unit": "degree_kelvin",
                            "unit_original": "degree_kelvin",
                        },
                        {
                            "name": "visibility_range",
                            "name_original": "horizontalVisibility",
                            "unit": "meter",
                            "unit_original": "kilometer",
                        },
                        {
                            "name": "water_film_thickness",
                            "name_original": "waterFilmThickness",
                            "unit": "meter",
                            "unit_original": "centimeter",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "windDirection",
                            "unit": "degree",
                            "unit_original": "degree",
                        },
                        {
                            "name": "wind_direction_gust_max",
                            "name_original": "maximumWindGustDirection",
                            "unit": "degree",
                            "unit_original": "degree",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "maximumWindGustSpeed",
                            "unit": "meter_per_second",
                            "unit_original": "meter_per_second",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "windSpeed",
                            "unit": "meter_per_second",
                            "unit_original": "meter_per_second",
                        },
                    ],
                }
            ],
        }
    ]
}
DwdRoadMetadata = MetadataModel.model_validate(DwdRoadMetadata)


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

    _data_tz = Timezone.UTC

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
        df = df.rename(mapping={"timestamp": Columns.DATE.value, "shortstationname": Columns.STATION_ID.value})
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
            pl.col("shortStationName"),
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
            .alias("timestamp"),
            *parameters,
        )
        df = df.rename(mapping=lambda col: col.lower())
        df = df.unpivot(
            index=["shortstationname", "timestamp"],
            variable_name=Columns.PARAMETER.value,
            value_name=Columns.VALUE.value,
        )
        return df.with_columns(
            pl.col("value").cast(pl.Float64),
            pl.lit(None, dtype=pl.Float64).alias(Columns.QUALITY.value),
        )


class DwdRoadRequest(TimeseriesRequest):
    _provider = Provider.DWD
    _kind = Kind.OBSERVATION
    _tz = Timezone.GERMANY
    metadata = DwdRoadMetadata
    _values = DwdRoadValues
    _data_range = DataRange.FIXED

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
        parameter: str | DwdRoadParameter | Parameter | Sequence[str | DwdRoadParameter | Parameter],
        start_date: str | dt.datetime | None = None,
        end_date: str | dt.datetime | None = None,
        settings: Settings | None = None,
    ):
        super().__init__(
            parameter=parameter,
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
