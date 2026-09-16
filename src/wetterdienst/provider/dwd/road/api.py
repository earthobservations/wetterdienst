# Copyright (c) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD road weather data provider."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import Enum
from functools import reduce
from tempfile import NamedTemporaryFile
from typing import TYPE_CHECKING, ClassVar
from urllib.parse import urljoin

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import (
    DATASET_NAME_DEFAULT,
    DatasetModel,
    ParameterModel,
    build_metadata_model,
)
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.metadata import _METADATA
from wetterdienst.util.eccodes import require_bufr
from wetterdienst.util.network import File, download_file, download_files, list_remote_files_fsspec

if TYPE_CHECKING:
    import pandas as pd

    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

#: the stamp a road file carries, exactly as long as `%y%m%d%H%M` reads. Ten and not "ten or
#: more": a longer run anywhere else in the name would otherwise be captured instead of this
DATE_REGEX = r"-(\d{10})-"
TIME_COLUMNS = ("year", "month", "day", "hour", "minute")


DwdRoadMetadata = {
    **_METADATA,
    "kind": "observation",
    "timezone": "Europe/Berlin",
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
                            "unit": "percent",
                        },
                        {
                            "name": "precipitation_form",
                            "name_original": "precipitationType",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "precipitation_height",
                            "name_original": "totalPrecipitationOrTotalWaterEquivalent",
                            "unit": "millimeter",
                        },
                        {
                            "name": "precipitation_intensity",
                            "name_original": "intensityOfPrecipitation",
                            "unit": "millimeter_per_hour",
                        },
                        {
                            "name": "road_surface_condition",
                            "name_original": "roadSurfaceCondition",
                            "unit": "dimensionless",
                        },
                        {
                            "name": "temperature_air_mean_2m",
                            "name_original": "airTemperature",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "temperature_dew_point_mean_2m",
                            "name_original": "dewpointTemperature",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "temperature_surface_mean",
                            "name_original": "roadSurfaceTemperature",
                            "unit": "degree_kelvin",
                        },
                        {
                            "name": "visibility_range",
                            "name_original": "horizontalVisibility",
                            # BUFR 0 20 001 horizontalVisibility is metres, and nothing in this
                            # parser converts; the docs page already said m
                            "unit": "meter",
                        },
                        {
                            "name": "water_film_thickness",
                            "name_original": "waterFilmThickness",
                            "unit": "centimeter",
                        },
                        {
                            "name": "wind_direction",
                            "name_original": "windDirection",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_direction_gust_max",
                            "name_original": "maximumWindGustDirection",
                            "unit": "degree",
                        },
                        {
                            "name": "wind_gust_max",
                            "name_original": "maximumWindGustSpeed",
                            "unit": "meter_per_second",
                        },
                        {
                            "name": "wind_speed",
                            "name_original": "windSpeed",
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


#: what identifies one reading: a station and the minute it reported. Both column batches are read
#: against these and joined on them
_READING_KEYS = (*TIME_COLUMNS, "shortStationName")

#: the shape `__parse_dwd_road_weather_data` returns, named so that a file holding nothing can be
#: returned in it and still concatenate with the files that hold something
_PARSED_SCHEMA = {
    "station_id": pl.String,
    "date": pl.Datetime(time_zone="UTC"),
    "parameter": pl.String,
    "value": pl.Float64,
    "quality": pl.Float64,
}


def _read_batch(path: str, batch: list[str], source: str) -> pd.DataFrame:
    """Read one batch of columns, as one row per station and minute.

    `read_bufr` emits an observation only where every column asked for is present, which is its
    default and was ours. A road file holds one subset per station carrying the descriptors that
    station has, so asking for fourteen and keeping only the complete ones threw away every
    reading of anything not universally fitted: of one file of the DD group, the parse returned
    105 values where the file held 121, the whole of `roadSurfaceTemperature` among the missing.

    Required of the keys instead -- a station and a minute, which every subset carries -- each
    subset comes back as its own row, holding its own part of the station's reading. Those parts
    are one reading, so they are folded back together on the keys, `first` taking the value that
    is there over the ones that are not.

    Where two subsets both carry a value for the same descriptor, the earlier one wins and the
    later is dropped. They repeat each other constantly, and whether the repeats agree depends on
    the group -- over the last five files of each, DD had 261 repeated descriptors and no
    disagreement at all, where FN had 54 disagreements in 270 and HV 56 in 425. Nor are those
    rounding: `roadSurfaceTemperature` for station P129 came back as both 281.55 K and 304.65 K,
    which is 8 degrees and 31, and `roadSurfaceCondition` -- a code table, so a difference in kind
    rather than in degree -- as both 0 and 2.

    A station with two road sensors reports each of them, and this frame has nowhere to put the
    second: one row per station, minute and parameter, with no axis for which sensor spoke. So one
    is taken and the other is logged. That is where this stood before the reads were relaxed too
    -- the cross product of the old inner merge was collapsed just as arbitrarily one step later,
    by `unique` in `_process_dataset`. Telling them apart would take a discriminator, and no
    obvious one holds: `positionOfRoadSensors` reads 0 for both subsets of the stations measured,
    `subsetNumber` comes back as the whole file's numbering rather than the row's, and
    `road_sector` sits in the station index, one row per station, so it names where the station is
    and not which of its sensors spoke. Finding one is the first part of the problem rather than
    the easy part, and is tracked in GH-1908.
    """
    import pandas as pd  # noqa: PLC0415
    import pdbufr  # noqa: PLC0415

    columns = (*_READING_KEYS, *batch)
    df = pdbufr.read_bufr(path, columns=columns, required_columns=_READING_KEYS)
    if df.empty:
        # the file's messages decode to no subsets at all, which the size filter upstream tries to
        # catch by length and cannot do reliably. It comes back carrying its columns even so: the
        # merge then has keys to join on and the select has columns to name, so having nothing to
        # say is the same shape here as having something, and neither caller needs a branch for it
        log.info(f"{source} holds no reading for {batch}")
        # with the keys typed as they come back populated: merging them against a batch that did
        # find something is only otherwise allowed because pandas reads an all-empty object column
        # as dtype "empty" and lets it pass, which is a leniency rather than a promise
        empty = {key: pd.Series(dtype="int64") for key in TIME_COLUMNS}
        empty["shortStationName"] = pd.Series(dtype="object")
        empty.update({column: pd.Series(dtype="object") for column in batch})
        return pd.DataFrame(empty)
    keys = list(_READING_KEYS)
    grouped = df.groupby(keys)
    # of the batch, only what the read returned: a descriptor no subset carries is not a column
    # here at all, which is the same reason the parse fills them in further down
    present = [column for column in batch if column in df.columns]
    # a station reporting the same quantity twice and differently has two road sensors, and only
    # one of them fits in a frame with a row per station, minute and parameter. Which one is kept
    # is arbitrary; that the other existed is not, so it is said rather than swallowed. At debug,
    # because it is per file and routine -- HV disagrees in nearly every one, so a month of road
    # data is a few thousand of these and the CLI logs at info by default. What the fold does is
    # in the docstring above and in GH-1908, which is where someone would look; this line is for
    # the run where they want to know which stations, and when
    # asked only when it will be said: this is a groupby per file and per batch, about a tenth of
    # what the read itself costs, and it exists to write the line below and nothing else
    disagreeing = []
    if log.isEnabledFor(logging.DEBUG):
        counts = grouped[present].nunique(dropna=True)
        disagreeing = counts.columns[counts.gt(1).any()]
    if len(disagreeing):
        # the stations too, not only the descriptors: `first` is taken per column, so a row of a
        # station that reports twice may hold one sensor's air temperature beside the other's road
        # surface temperature -- a reading no sensor took. Naming them is what lets a caller find
        # the rows rather than only learn that some exist
        stations = counts.index[counts[disagreeing].gt(1).any(axis=1)].get_level_values(-1)
        log.debug(
            f"{source} reports {', '.join(sorted(disagreeing))} with more than one value for one "
            f"station and minute at "
            f"{', '.join(sorted(set(stations)))}; keeping the first of each (GH-1908)",
        )
    return grouped.first().reset_index()


class DwdRoadValues(TimeseriesValues):
    """Values class for DWD road weather data."""

    def __post_init__(self) -> None:
        """Post-initialization of the DwdRoadValues class."""
        super().__post_init__()
        # asked here so the answer comes back with the request rather than out of the middle of a
        # parse. It used to call `ensure_pdbufr()` and throw the answer away, which guarded nothing
        require_bufr("DWD road weather data")

    def _collect_station_parameter_or_dataset(  # ty: ignore[invalid-method-override]
        self,
        station_id: str,
        parameter_or_dataset: DatasetModel,
    ) -> pl.DataFrame:
        """Collect data from DWD Road Weather stations."""
        station_group = self.sr.df.filter(pl.col("station_id").eq(station_id)).get_column("station_group").item()
        station_group = DwdRoadStationGroup(station_group)
        parameters = list(parameter_or_dataset)
        df = self._collect_data_by_station_group(station_group, parameters)
        # nothing to answer with is a shape rather than a special case: the group published no file
        # for the window, or every file it published held nothing, and either way what comes back
        # is a frame of no readings rather than a frame of no columns. So the filter has a station
        # id to look for and the select has columns to name, and one row of this function answers
        # for the empty case and the populated one alike -- there being one less place to hand a
        # frame on before asking whether it holds anything, which is how this went wrong four
        # times over
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
        df = pl.DataFrame({"filename": files}, schema={"filename": pl.String}).with_columns(
            pl.col("filename")
            .str.split("/")
            .list.last()
            .str.extract(DATE_REGEX, 1)
            # not strict: ten digits are not necessarily a date, and `26091319ZZ` or `2699999999`
            # would raise here and take the request with it. A match that will not parse becomes a
            # null and is dropped below beside the entries that never matched -- one rule for what
            # counts as a file, rather than a crash for one kind of not-a-file and a drop for the
            # other
            .str.to_datetime("%y%m%d%H%M", time_zone="UTC", strict=False)
            .alias("date"),
        )
        # a listing of a group that exists and holds nothing is the group itself, which carries no
        # timestamp and is no file. Left in, it is downloaded and handed to the reader as though it
        # were one -- and it makes `files` non-empty, so the two lines below never say what is
        # actually the case
        listed = df.height
        df = df.drop_nulls("date")
        if df.is_empty():
            if listed > 1:
                # entries were there and not one of them was a file. Counted above one because a
                # quiet group can still list a single entry that is no file -- the group itself,
                # or the `LATEST` alias outliving the last timestamped file it pointed at -- and
                # that is the ordinary way to publish nothing, not a rename. Several of them is
                # not, and would mean the names have changed shape, which would otherwise empty
                # every group at once behind a line saying no files were found
                log.warning(
                    f"{listed} entries listed for {road_weather_station_group.value} and none of "
                    f"them carries a timestamp; the file names may have changed",
                )
            else:
                log.info(f"No files found for {road_weather_station_group.value}.")
            if road_weather_station_group in TEMPORARILY_UNAVAILABLE_STATION_GROUPS:
                log.info(f"Station group {road_weather_station_group.value} may be temporarily unavailable.")
        return df

    def _collect_data_by_station_group(
        self,
        road_weather_station_group: DwdRoadStationGroup,
        parameters: list[ParameterModel],
    ) -> pl.DataFrame:
        """Collect data from DWD Road Weather stations."""
        df_files = self._create_file_index_for_dwd_road_weather_station(road_weather_station_group)
        if self.sr.start_date:
            df_files = df_files.filter(
                pl.col("date").is_between(self.sr.start_date, self.sr.end_date),
            )
        remote_files = df_files.get_column("filename").to_list()
        files = download_files(
            urls=remote_files,
            cache_dir=self.sr.settings.cache_dir,
            ttl=CacheExpiry.TWELVE_HOURS,
            client_kwargs=self.sr.settings.fsspec_client_kwargs,
            cache_disable=self.sr.settings.cache_disable,
        )
        # files may be empty, see https://github.com/earthobservations/wetterdienst/issues/1526
        # -> those files had only 142 bytes
        # -> skip empty files with equal or less size
        files = [file for file in files if file.nbytes > 142]
        return self._parse_dwd_road_weather_data(files, parameters)

    def _parse_dwd_road_weather_data(
        self,
        files: list[File],
        parameters: list[ParameterModel],
    ) -> pl.DataFrame:
        """Parse the road weather station data from a given file and returns a DataFrame."""
        data = [self.__parse_dwd_road_weather_data(file, parameters) for file in files]
        if not data:
            return pl.DataFrame(schema=_PARSED_SCHEMA)
        return pl.concat(data)

    @staticmethod
    def __parse_dwd_road_weather_data(
        file: File,
        parameters: list[ParameterModel],
    ) -> pl.DataFrame:
        """Read the road weather station data from a given file and returns a DataFrame."""
        parameter_names = [parameter.name_original for parameter in parameters]
        first_batch = parameter_names[:10]
        second_batch = parameter_names[10:]
        with NamedTemporaryFile("w+b") as tf:
            if isinstance(file.content, Exception):
                raise file.content
            tf.write(file.content.read())
            tf.seek(0)
            df = _read_batch(tf.name, first_batch, file.url)
            if second_batch:
                # outer, so a station that answered one read and not the other keeps what it did
                # say, with nulls for the rest
                df2 = _read_batch(tf.name, second_batch, file.url)
                df = df.merge(df2, on=list(_READING_KEYS), how="outer")
        df = pl.from_pandas(df)
        # a descriptor no subset in the file carries is not a column at all, so the select below
        # would ask for one that is not there. Absent is null, the same as present and unreported
        df = df.with_columns(
            pl.lit(None, dtype=pl.Float64).alias(name) for name in parameter_names if name not in df.columns
        )
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


@dataclass
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

    def _all(self) -> pl.LazyFrame:
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.settings)
        file = download_file(
            url=self._endpoint,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            return pl.LazyFrame()
        df = pl.read_excel(source=file.content, sheet_name="Tabelle1", infer_schema_length=0)
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
