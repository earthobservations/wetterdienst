# Copyright (c) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD road weather data provider."""

from __future__ import annotations

import logging
import re
import warnings
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
    from collections.abc import Collection, Iterable

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


#: `pdbufr`'s flat read names every value by its rank in the message -- `#1#airTemperature`, and
#: for a station carrying two road sensors `#1#roadSurfaceTemperature` beside
#: `#2#roadSurfaceTemperature`. The rank is what names the sensor
_RANKED_KEY = re.compile(r"^#(\d+)#(.+)$")

#: the shape `__parse_dwd_road_weather_data` returns, named so that a file holding nothing can be
#: returned in it and still concatenate with the files that hold something
_PARSED_SCHEMA = {
    "station_id": pl.String,
    "date": pl.Datetime(time_zone="UTC"),
    "parameter": pl.String,
    "value": pl.Float64,
    "quality": pl.Float64,
}


def _columns_by_rank(columns: Iterable[str], wanted: Collection[str]) -> dict[str, dict[int, str]]:
    """Group a flat read's columns by the descriptor they carry, keyed by rank.

    `#1#roadSurfaceTemperature` and `#2#roadSurfaceTemperature` become one entry holding both, so
    that what replicates can be told from what does not by asking how many ranks it has.
    """
    by_name: dict[str, dict[int, str]] = {}
    for column in columns:
        match = _RANKED_KEY.match(column)
        if not match:
            continue
        rank, name = int(match.group(1)), match.group(2)
        if name in wanted:
            by_name.setdefault(name, {})[rank] = column
    return by_name


def _contested(columns: dict[int, str]) -> pl.Expr:
    """Whether more than one road sensor reported this descriptor for the row.

    Contested is the only case that needs deciding. Two sensors reporting different quantities --
    the whole of the DD group, where one carries the surface temperature and the other the surface
    condition -- leave nothing to choose between, and taking both composes a row the same way every
    row in this library is composed, out of the several instruments a station is fitted with.
    """
    return pl.sum_horizontal([pl.col(column).is_not_null().cast(pl.Int32) for column in columns.values()]).gt(1)


def _sensor_choice(replicated: dict[str, dict[int, str]], ranks: list[int]) -> pl.Expr:
    """Name the sensor a row's contested readings come from: whichever reported most of them.

    Counted over the descriptors this row actually has twice, not over the file's columns or over
    everything the sensor reported: a sensor that carries nothing contested cannot be the answer to
    a contest, and counting what it does carry would let it win one.

    The first sensor on a tie, which is the ordinary case -- two sensors fitted alike report the
    same three quantities, so the count cannot separate them and the order DWD encodes them in is
    the only thing left. Arbitrary between the two, but fixed: the same file parses the same way
    twice, and the reading that is dropped is named in the log rather than lost quietly.
    """
    contested = {name: _contested(columns) for name, columns in replicated.items()}
    chosen = pl.lit(None, dtype=pl.Int32)
    most = pl.lit(0, dtype=pl.Int32)
    for rank in ranks:
        reported = pl.sum_horizontal(
            [
                pl.when(contested[name] & pl.col(columns[rank]).is_not_null()).then(1).otherwise(0)
                for name, columns in replicated.items()
                if rank in columns
            ]
            or [pl.lit(0, dtype=pl.Int32)],
        )
        beats = reported.gt(most)
        chosen = pl.when(beats).then(pl.lit(rank, dtype=pl.Int32)).otherwise(chosen)
        most = pl.when(beats).then(reported).otherwise(most)
    return chosen


def _reading(name: str, columns: dict[int, str], chosen: pl.Expr) -> pl.Expr:
    """One descriptor's value for a row.

    From the chosen sensor where the row has it twice, so that everything contested comes from one
    sensor and the row does not pair one sensor's surface temperature with another's surface
    condition. Otherwise as it came, there being one reading and nothing to decide.
    """
    if not columns:
        return pl.lit(None, dtype=pl.Float64).alias(name)
    if len(columns) == 1:
        return pl.col(next(iter(columns.values()))).cast(pl.Float64).alias(name)
    order = sorted(columns.items())
    return (
        pl.when(_contested(columns))
        .then(pl.coalesce([pl.when(chosen.eq(rank)).then(pl.col(column).cast(pl.Float64)) for rank, column in order]))
        .otherwise(pl.coalesce([pl.col(column).cast(pl.Float64) for _, column in order]))
        .alias(name)
    )


def _log_dropped_sensors(
    df: pl.DataFrame,
    ranked: dict[str, dict[int, str]],
    replicated: dict[str, dict[int, str]],
    ranks: list[int],
    chosen: pl.Expr,
    source: str,
) -> None:
    """Say which stations reported one quantity from two road sensors, and how much went.

    At debug, because it is per file and routine -- a tenth of the stations of a populated group
    carry a second sensor, so a month of road data is thousands of these and the CLI logs at info.
    What the choice is and why is in `__parse_dwd_road_weather_data` and in GH-1908, which is where
    someone would look; this is for the run where they want to know which stations, and when.
    """
    contested = {name: _contested(columns) for name, columns in replicated.items()}
    lost = pl.sum_horizontal(
        [
            pl.when(contested[name] & pl.col(columns[rank]).is_not_null() & chosen.ne(rank)).then(1).otherwise(0)
            for name, columns in replicated.items()
            for rank in ranks
            if rank in columns
        ],
    )
    dropped = df.select(
        pl.col(ranked["shortStationName"][1]).alias("station"),
        lost.alias("lost"),
    ).filter(pl.col("lost").gt(0))
    if dropped.is_empty():
        return
    stations = sorted(dropped.get_column("station").to_list())
    log.debug(
        f"{source}: {len(stations)} stations reported the same quantity from more than one road "
        f"sensor ({', '.join(stations[:5])}{', ...' if len(stations) > 5 else ''}); answered from "
        f"the one carrying most of {', '.join(sorted(replicated))}, dropping "
        f"{dropped.get_column('lost').sum()} readings from the others (GH-1908)",
    )


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
        df = (
            pl.DataFrame({"filename": files}, schema={"filename": pl.String})
            .with_columns(
                pl.col("filename").str.split("/").list.last().alias("name"),
            )
            .with_columns(
                pl.col("name")
                .str.extract(DATE_REGEX, 1)
                # not strict: ten digits are not necessarily a date, and `26091319ZZ` or `2699999999`
                # would raise here and take the request with it. A match that will not parse becomes a
                # null and is dropped below beside the entries that never matched -- one rule for what
                # counts as a file, rather than a crash for one kind of not-a-file and a drop for the
                # other
                .str.to_datetime("%y%m%d%H%M", time_zone="UTC", strict=False)
                .alias("date"),
            )
        )
        # what is dropped below and expected to be: the listing of a group that exists and holds
        # nothing is the group itself, which comes back named for the group or not named at all
        # depending on whether the URL it was asked for ended in a slash, and each family a group
        # publishes under keeps a `LATEST` alias duplicating its newest file -- FN publishes two,
        # under `DWFN` and `DWNB`. Left in, either is downloaded and handed to the reader as
        # though it were a file
        expected = pl.col("name").is_in(["", road_weather_station_group.value]) | pl.col("name").str.contains("LATEST")
        unreadable = df.filter(pl.col("date").is_null() & ~expected).get_column("name").to_list()
        if unreadable:
            # a name the index cannot read, which is asked of every listing rather than only of one
            # that came back empty: a group publishing under two families loses half its readings
            # when one of them is renamed, and the drop is as quiet as the alias's -- so the
            # request would simply return less, with nothing said anywhere
            log.warning(
                f"{len(unreadable)} of {df.height} entries listed for "
                f"{road_weather_station_group.value} carry no timestamp the file index reads "
                f"({', '.join(sorted(unreadable)[:3])}); the file names may have changed",
            )
        df = df.drop_nulls("date")
        if df.is_empty():
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
        """Read one road file as one row per station, minute and parameter.

        A road file holds one subset per station -- 1199 subsets across fifteen groups, and no
        station appeared in two of them -- and the road sensors sit inside that subset as a delayed
        replication: `1 09 000` and `0 31 001` wrapping `positionOfRoadSensors`,
        `roadSurfaceTemperature`, the sub-surface temperatures at their depths, `waterFilmThickness`
        and `roadSurfaceCondition`. A station with two sensors carries that group twice, and one
        with four carries it four times.

        Read flat, the replication comes back as the rank on the key -- `#1#roadSurfaceTemperature`
        beside `#2#roadSurfaceTemperature` -- and the rank is what names the sensor. Nothing else
        does: `positionOfRoadSensors` reads 0 or missing in all 1199 subsets, and `road_sector` is
        in the station index, one row per station, so it says where the station is rather than
        which of its sensors spoke.

        So only what is inside that replication can arrive twice. Of the fourteen descriptors this
        dataset maps, three do -- the surface temperature, the surface condition and the water film
        -- and the other eleven, air temperature and dew point and humidity and visibility and the
        wind and the precipitation among them, are outside it and come once per station. A row can
        therefore never hold one sensor's air temperature beside another's road surface temperature,
        there being only ever one air temperature to hold.

        Two sensors are two things, and which of the two a station is doing can be read off what
        they reported. Where they carry the same quantity they are measuring one road twice, from
        different points of it. They mostly agree closely -- of 75 stations whose sensors both
        reported a surface temperature, the median disagreement was 0.3 K and 97 in 100 were inside
        3 K -- so which one answers rarely changes the reading. Two of the 75 were nothing like
        that, at 22 K and 18 K, and both were a broken sensor rather than a property of the road:
        one stuck at 273.14 K for a whole day of readings, the other running some 22 K hot while
        keeping a normal daily swing. The network carries such readings at about one station in
        forty, on stations with one sensor as much as two, and none of that is decided here: a
        sensor has to be chosen, everything contested is then taken from that one so the row is a
        road rather than an average of two, and where the two disagree wildly the choice is the
        rank order and nothing better. This library does not judge whether a reading is plausible,
        here or anywhere else.

        Where they carry different quantities they are two instruments of one installation -- the
        whole of the DD group, where the first sensor holds the surface temperature and the second
        the surface condition, for 24 of its 25 stations. Nothing is contested there, so both are
        kept: composing that row is what this library does with every station, whose air temperature
        and wind and humidity are three instruments already.

        What is dropped is only ever a reading that a station reported twice and differently, which
        is 36 of a populated group's file, and it is named in the log. Keeping those would want an
        axis this frame has not got, which is GH-1908.
        """
        import pdbufr  # noqa: PLC0415

        parameter_names = [parameter.name_original for parameter in parameters]
        with NamedTemporaryFile("w+b") as tf:
            if isinstance(file.content, Exception):
                raise file.content
            tf.write(file.content.read())
            tf.seek(0)
            with warnings.catch_warnings():
                # the flat read unions the keys of subsets that do not carry the same ones and
                # says so, which for this network is every file: road stations are fitted
                # differently, so one carries a second sensor where the next does not. What it
                # warns of is the column order it returns them in, and nothing below reads a
                # column by position
                warnings.filterwarnings(
                    "ignore",
                    message="not all BUFR messages/subsets have the same structure",
                    category=UserWarning,
                )
                # every key, rather than the fourteen asked for: flat, a read that names its
                # columns returns the first rank of each and drops the rest, which is the sensor
                # thrown away before anything can choose between them
                df = pdbufr.read_bufr(tf.name, flat=True)
        ranked = _columns_by_rank(df.columns, {*TIME_COLUMNS, "shortStationName", *parameter_names})
        # a file whose messages decode to no subsets comes back with no columns at all, and one
        # that decodes to subsets carrying no station is as unreadable. Either is nothing to
        # answer with rather than something to fail on -- the group published, and what it
        # published held no readings
        if df.empty or "shortStationName" not in ranked:
            log.info(f"{file.url} holds no readings")
            return pl.DataFrame(schema=_PARSED_SCHEMA)
        df = pl.from_pandas(df)
        replicated = {name: columns for name, columns in ranked.items() if name in parameter_names and len(columns) > 1}
        ranks = sorted({rank for columns in replicated.values() for rank in columns})
        chosen = _sensor_choice(replicated, ranks)
        if replicated and log.isEnabledFor(logging.DEBUG):
            _log_dropped_sensors(df, ranked, replicated, ranks, chosen, file.url)
        return (
            df.select(
                pl.col(ranked["shortStationName"][1]).cast(pl.String).alias("station_id"),
                pl.concat_str(
                    exprs=[
                        pl.col(ranked[name][1]).cast(pl.String).str.pad_start(2 if name != "year" else 4, "0")
                        for name in TIME_COLUMNS
                    ],
                )
                .str.to_datetime("%Y%m%d%H%M", time_zone="UTC")
                .alias("date"),
                # a descriptor no subset in the file carries is not a column of the read at all,
                # and is null here for the same reason a station that did not report it is: absent
                # and unreported are the same thing to a caller
                *(_reading(name, ranked.get(name, {}), chosen) for name in parameter_names),
            )
            .unpivot(
                index=["station_id", "date"],
                variable_name="parameter",
                value_name="value",
            )
            .with_columns(pl.lit(None, dtype=pl.Float64).alias("quality"))
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
