# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""IMGW hydrology provider."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from io import BytesIO, StringIO
from typing import TYPE_CHECKING, ClassVar

import polars as pl
import portion
from dateutil.relativedelta import relativedelta

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.metadata import DatasetModel, build_metadata_model
from wetterdienst.model.quality_flags import Sentinel, join_quality_flags, null_sentinels
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.imgw.fileindex import keep_files_overlapping, list_files_for_interval
from wetterdienst.provider.imgw.metadata import _METADATA
from wetterdienst.util.archive import open_zip
from wetterdienst.util.geo import convert_dms_string_to_dd
from wetterdienst.util.network import File, download_file, download_files
from wetterdienst.util.polars_util import read_csv_without_header

if TYPE_CHECKING:
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

# what the files write for a reading they do not have, by column: 9999 (stage), 99999.999 (discharge), 99.9 and 9999
# (water temperature), e.g. `149180020;CHAŁUPKI;Odra (1);2023;01;01;88;14.200;99.9;11` in codz_2023.zip (live: 99.9 in
# the temperature of 265311 rows, 99999.999 in the discharge of 46895). A sentinel is matched by number, so each holds
# in its own column: a discharge of 99.900 m3/s is a reading and 99.9 is not one there. The reading keeps the text as
# `raw:` in `quality_flags` (GH-2759)
_MISSING = (
    Sentinel("9999", where=pl.col("parameter") == "stan wody"),
    Sentinel("99999.999", where=pl.col("parameter") == "przepływ"),
    Sentinel("99.9", "9999", where=pl.col("parameter") == "temperatura wody"),
)


_ImgwHydrologyMetadataSpec = {
    **_METADATA,
    "kind": "observation",
    "timezone": "Europe/Warsaw",
    "resolutions": [
        {
            "name": "daily",
            "name_original": "dobowe",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [
                {
                    "name": "hydrology",
                    "name_original": "hydrology",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "discharge",
                            "name_original": "przepływ",
                            "unit": "cubic_meter_per_second",
                        },
                        {
                            "name": "temperature_water",
                            "name_original": "temperatura wody",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "stage",
                            "name_original": "stan wody",
                            "unit": "centimeter",
                        },
                    ],
                },
            ],
        },
        {
            "name": "monthly",
            "name_original": "miesieczne",
            "periods": ["historical"],
            "date_required": True,
            "datasets": [
                {
                    "name": "hydrology",
                    "name_original": "hydrology",
                    "grouped": True,
                    "parameters": [
                        {
                            "name": "discharge_max",
                            "name_original": "maksymalna przepływ",
                            "unit": "cubic_meter_per_second",
                        },
                        {
                            "name": "discharge_mean",
                            "name_original": "średnia przepływ",
                            "unit": "cubic_meter_per_second",
                        },
                        {
                            "name": "discharge_min",
                            "name_original": "minimalna przepływ",
                            "unit": "cubic_meter_per_second",
                        },
                        {
                            "name": "temperature_water_max",
                            "name_original": "maksymalna temperatura wody",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_water_mean",
                            "name_original": "średnia temperatura wody",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "temperature_water_min",
                            "name_original": "minimalna temperatura wody",
                            "unit": "degree_celsius",
                        },
                        {
                            "name": "stage_max",
                            "name_original": "maksymalna stan wody",
                            "unit": "centimeter",
                        },
                        {
                            "name": "stage_mean",
                            "name_original": "średnia stan wody",
                            "unit": "centimeter",
                        },
                        {
                            "name": "stage_min",
                            "name_original": "minimalna stan wody",
                            "unit": "centimeter",
                        },
                    ],
                },
            ],
        },
    ],
}
ImgwHydrologyMetadata = build_metadata_model(_ImgwHydrologyMetadataSpec, "ImgwHydrologyMetadata")


def _hydrology_daily_file_period() -> tuple[pl.Expr, pl.Expr]:
    """Give the first and last instant a hydrology daily zip file covers, from the ``year`` and ``month`` of its name.

    Daily files are either per-month (``codz_YYYY_MM.zip``, historical) or a single
    consolidated file per year (``codz_YYYY.zip``, used from 2023 onwards). ``month`` is
    null for the latter, in which case the whole hydrological year is covered.
    """
    year, month = pl.col("year"), pl.col("month")
    hydrological_year = pl.datetime(year, 1, 1, time_zone="UTC")
    # shift hydrological year/month to calendar year/month, mirroring __parse_file below
    month_start = pl.datetime(
        year - (month <= 2).cast(pl.Int64),
        pl.when(month > 2).then(month - 2).otherwise(month + 10),
        1,
        time_zone="UTC",
    )
    start = pl.when(month.is_null()).then(hydrological_year.dt.offset_by("-2mo")).otherwise(month_start)
    end = (
        pl.when(month.is_null())
        .then(hydrological_year.dt.offset_by("11mo"))
        .otherwise(month_start.dt.offset_by("1mo"))
        .dt.offset_by("-1d")
    )
    return start, end


def _normalize_hydrology_csv(data: bytes) -> tuple[bytes, str]:
    """Detect and normalize the CSV export quirks IMGW has used for hydrology zip files.

    IMGW's per-row export format has changed multiple times:
      - historically (through ~2022): comma-separated, individually quoted fields
      - 2023: semicolon-separated, unquoted fields (sometimes with a UTF-8 BOM)
      - 2024: comma-separated, but each row wrapped in one extra pair of quotes with
        doubly-escaped inner quotes, e.g. ``"id,name,river,""2024"",""01"",...``

    Returns the (possibly rewritten) bytes together with the separator to parse them with.
    """
    body = data.replace(b"\xef\xbb\xbf", b"")
    first_line = body.split(b"\n", 1)[0].rstrip(b"\r")
    if first_line.startswith(b'"') and b',""' in first_line:
        unwrapped = []
        for raw_line in body.split(b"\n"):
            line = raw_line.rstrip(b"\r")
            if not line:
                continue
            if line.startswith(b'"') and line.endswith(b'"'):
                line = line[1:-1]
            unwrapped.append(line.replace(b'""', b'"'))
        return b"\r\n".join(unwrapped), ","
    if b";" in first_line and b"," not in first_line:
        return body, ";"
    return body, ","


class ImgwHydrologyValues(TimeseriesValues[DatasetModel]):
    """Values class for hydrological data from IMGW."""

    _endpoint = "https://danepubliczne.imgw.pl/data/dane_pomiarowo_obserwacyjne/dane_hydrologiczne/{resolution}/"
    _file_schema: ClassVar = {
        Resolution.DAILY: {
            "hydrology": {
                "codz.*.csv": {
                    "column_1": "station_id",
                    "column_4": "year",
                    "column_5": "month",
                    "column_6": "day",
                    "column_7": "stan wody",
                    "column_8": "przepływ",
                    "column_9": "temperatura wody",
                },
            },
        },
        Resolution.MONTHLY: {
            "hydrology": {
                "mies.*.csv": {
                    "column_1": "station_id",
                    "column_4": "year",
                    "column_5": "month",
                    "column_6": "extremity",
                    "column_7": "stan wody",
                    "column_8": "przepływ",
                    "column_9": "temperatura wody",
                },
            },
        },
    }

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: DatasetModel,
    ) -> pl.DataFrame:
        """Collect hydrological data for a single station and dataset."""
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.sr.request.settings)
        urls = self._get_urls(parameter_or_dataset)
        files = download_files(
            urls=urls,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.FIVE_MINUTES,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        # a 404 is a file that is not there, and is dropped; any other failure -- a timeout, a 5xx
        # after the retries -- is an outage, which dropped would read as a station without data
        for file in files:
            if file.status != 404:
                file.raise_if_exception()
        files = [file for file in files if isinstance(file.content, BytesIO)]
        data = []
        file_schema = self._file_schema[parameter_or_dataset.resolution.value][parameter_or_dataset.name]
        for file in files:
            df = self._parse_file(
                file=file,
                station_id=station_id,
                dataset=parameter_or_dataset,
                file_schema=file_schema,
            )
            if not df.is_empty():
                data.append(df)
                # the archive gave this station readings: when IMGW wrote it is the date of what is read (GH-2567)
                self._note_data_updated(file.last_modified)
        try:
            df = pl.concat(data)
        except ValueError:
            return pl.DataFrame()
        if df.is_empty():
            return pl.DataFrame()
        # the dates are IMGW's own, read as UTC by the core
        return df

    def _parse_file(
        self,
        file: File,
        station_id: str,
        dataset: DatasetModel,
        file_schema: dict,
    ) -> pl.DataFrame:
        """Parse hydrological data from a single file."""
        zfs = open_zip(file)
        data = []
        files = zfs.glob("*")
        for file_pattern, schema in file_schema.items():
            matched_path: str | None = None
            for f in files:
                if re.match(file_pattern, f):
                    matched_path = f
                    break
            df = self.__parse_file(
                file=zfs.read_bytes(matched_path),
                station_id=station_id,
                dataset=dataset,
                schema=schema,
            )
            if not df.is_empty():
                data.append(df)
        try:
            df = pl.concat(data)
        except ValueError:
            return pl.DataFrame()
        if df.is_empty():
            return pl.DataFrame()
        return df.unique(subset=["parameter", "timestamp"], keep="first")

    def __parse_file(self, file: bytes, station_id: str, dataset: DatasetModel, schema: dict) -> pl.DataFrame:
        """Parse hydrological data from a single file."""
        normalized, separator = _normalize_hydrology_csv(file)
        df = read_csv_without_header(
            normalized,
            encoding="latin-1",
            separator=separator,
            infer_schema_length=0,
        )
        df = df.select(list(schema.keys())).rename(schema)
        df = df.with_columns(pl.col("station_id").str.strip_chars())
        df = df.filter(pl.col("station_id").eq(station_id))
        if df.is_empty():
            return df
        df = df.with_columns(pl.col("year").cast(pl.Int64), pl.col("month").cast(pl.Int64))
        # shift hydrological year to regular year
        df = df.with_columns(
            pl.when(pl.col("month") <= 2).then(pl.col("year") - 1).otherwise(pl.col("year")).alias("year"),
            pl.when(pl.col("month").add(10).gt(12)).then(pl.col("month").sub(2)).otherwise(pl.col("month").add(10)),
        )
        if dataset.resolution.value == Resolution.DAILY:
            df = df.with_columns(pl.col("day").cast(pl.Int64))
            exp1 = pl.all().exclude(["year", "month", "day"])
            exp2 = pl.datetime("year", "month", "day").alias("timestamp")
        else:
            exp1 = pl.all().exclude(["year", "month"])
            exp2 = pl.datetime("year", "month", 1).alias("timestamp")
        df = df.select(exp1, exp2)
        if dataset.resolution.value == Resolution.DAILY:
            index = ["station_id", "timestamp"]
        else:
            # monthly data includes extrimity column (1: min, 2: mean, 3: max)
            index = ["station_id", "timestamp", "extremity"]
        df = df.unpivot(index=index, variable_name="parameter", value_name="value")
        # the values the files write for a reading they do not have, nulled with their text kept as `raw:` (GH-2759)
        value, raw = null_sentinels(pl.col("value"), *_MISSING)
        df = df.with_columns(value.alias("value"), join_quality_flags(None, raw=raw))
        if dataset.resolution.value == Resolution.MONTHLY:
            df = df.select(
                pl.col("station_id"),
                pl.col("timestamp"),
                pl.concat_str(
                    exprs=[
                        pl.col("extremity").replace({"1": "minimalna", "2": "średnia", "3": "maksymalna"}),
                        pl.col("parameter"),
                    ],
                    separator=" ",
                ).alias("parameter"),
                pl.col("value"),
                pl.col("quality_flags"),
            )
        return df

    def _get_urls(self, dataset: DatasetModel) -> list[str]:
        """Get all urls for the given dataset."""
        url = self._endpoint.format(resolution=dataset.resolution.name_original, dataset=dataset.name_original)
        interval = None
        folder_interval = None
        if self.sr.start:
            interval = portion.closed(self.sr.start, self.sr.end)
            # widen by 2 months on each side when pruning folders: IMGW files use "hydrological years"
            # (shifted by 2 months, see __parse_file below) internally, so e.g. a file living in the "2023"
            # folder can contain data as early as 2022-11. The exact per-file filtering below is unaffected.
            folder_interval = portion.closed(
                self.sr.start - relativedelta(months=2),
                self.sr.end + relativedelta(months=2),
            )
        files = list_files_for_interval(url, self.sr.settings, folder_interval)
        df_files = pl.DataFrame({"url": files})
        df_files = df_files.with_columns(pl.col("url").str.split("/").list.last().alias("file"))
        df_files = df_files.filter(pl.col("file").str.ends_with(".zip") & ~pl.col("file").str.starts_with("zjaw"))
        if interval is not None:
            if dataset.resolution.value == Resolution.DAILY:
                # daily files are either per-month ("codz_YYYY_MM.zip", historical) or a single
                # consolidated file per year ("codz_YYYY.zip", used from 2023 onwards); month is
                # null for the latter and _hydrology_daily_file_period() covers the whole year
                df_files = df_files.with_columns(
                    pl.col("file").str.strip_chars_end(".zip").str.split("_").list.slice(1).alias("year_month"),
                )
                df_files = df_files.with_columns(
                    pl.col("year_month").list.first().cast(pl.Int64).alias("year"),
                    pl.col("year_month").list.get(1, null_on_oob=True).cast(pl.Int64).alias("month"),
                )
                start, end = _hydrology_daily_file_period()
            else:
                # the hydrological year of the file's year starts two months before it, in November; it is kept
                # until the end of the November after, a month past its end, as it always was
                year = (
                    pl.col("file")
                    .str.strip_chars_end(".zip")
                    .str.split("_")
                    .list.last()
                    .str.to_datetime("%Y", time_zone="UTC", strict=False)
                )
                start = year.dt.offset_by("-2mo")
                end = year.dt.offset_by("11mo").dt.offset_by("-1d")
            df_files = keep_files_overlapping(df_files, start, end, interval)
        return df_files.get_column("url").to_list()


@dataclass
class ImgwHydrologyRequest(TimeseriesRequest):
    """Request class for hydrological data from IMGW."""

    metadata = ImgwHydrologyMetadata
    _values = ImgwHydrologyValues
    _endpoint = "https://dane.imgw.pl/datastore/getfiledown/Arch/Telemetria/Hydro/kody_stacji.csv"

    def _all(self) -> pl.LazyFrame:
        """:return:"""
        from typing import cast  # noqa: PLC0415

        settings = cast("Settings", self.settings)
        payload = download_file(
            url=self._endpoint,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        payload.raise_if_exception()
        if isinstance(payload.content, Exception):
            return pl.LazyFrame()
        # skip empty lines in the csv file
        lines = payload.content.read().decode("utf-8").replace("\r", "").split("\n")
        lines = [line for line in lines if line]
        payload = StringIO("\n".join(lines))
        df = pl.read_csv(
            payload,
            encoding="utf8",
            has_header=False,
            separator=";",
            skip_rows=1,
            infer_schema_length=0,
            truncate_ragged_lines=True,
        )
        # columns (0-indexed): LP, Kod (station_id), Nazwa (name), Rzeka, Rok założenia, Szerokość (latitude),
        # Długość (longitude), Rzędna zera wodowskazu, Kilometr biegu rzeki
        df = df[:, [1, 2, 5, 6]]
        df.columns = [
            "station_id",
            "name",
            "latitude",
            "longitude",
        ]
        df = df.with_columns(
            # the list pads some names with a trailing blank (`LUDŹMIERZ `),
            # which an exact comparison of the name then misses
            pl.col("name").str.strip_chars(),
            convert_dms_string_to_dd(pl.col("latitude")),
            convert_dms_string_to_dd(pl.col("longitude")),
        )
        # the station list is shared across all datasets: the core tags each row once per requested resolution/dataset
        return df.lazy()
