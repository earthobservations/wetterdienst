# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD POI (Point Of Interest) current weather report provider.

DWD publishes one CSV file per station under
https://opendata.dwd.de/weather/weather_reports/poi/, holding that station's hourly weather
reports for roughly the last day, newest row first. This is the observed counterpart to MOSMIX and
covers the same stations, so the station list is the MOSMIX catalogue narrowed to the stations that
have a file -- currently about 970 of the catalogue's 5600, in Germany and abroad.

The file name is the station id padded to five characters with underscores (``A191`` becomes
``A191_-BEOB.csv``), while the station id reported here stays the catalogue's, so a station keeps
one id across ``dwd/mosmix`` and ``dwd/poi``.

Each file starts with three header lines -- DWD's English parameter names, their units, then German
descriptions -- followed by ``DD.MM.YY;HH:MM;<values...>`` rows. Timestamps are UTC (the second
header line says so), values use ``,`` as the decimal separator and ``---`` for a missing value,
and the whole file is latin-1 encoded.

Only the most recent day is served, so a request for anything older comes back empty. Values older
than the file's oldest row are in ``dwd/observation`` instead, once DWD has quality-checked them.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, cast

import polars as pl

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import DatasetModel, ParameterModel
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.catalogue import read_mosmix_station_catalogue
from wetterdienst.provider.dwd.poi.metadata import DwdPoiMetadata
from wetterdienst.util.network import download_file, list_remote_files_fsspec

if TYPE_CHECKING:
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

_BASE_URL = "https://opendata.dwd.de/weather/weather_reports/poi/"
_FILE_SUFFIX = "-BEOB.csv"
# DWD pads the station id out to five characters with underscores in the file name
_STATION_ID_WIDTH = 5
_PADDING = "_"
# the two columns before the parameters, named "surface observations" and "Parameter description"
# in the first header line
_DATE_COLUMN_INDEX = 0
_TIME_COLUMN_INDEX = 1
# line 1 is the header polars reads; lines 2 and 3 are the units and the German descriptions
_HEADER_ROWS = 2
_MISSING_VALUE = "---"

_EMPTY_VALUES_SCHEMA = {
    "resolution": pl.String,
    "dataset": pl.String,
    "parameter": pl.String,
    "station_id": pl.String,
    "date": pl.Datetime(time_unit="us", time_zone="UTC"),
    "value": pl.Float64,
    "quality": pl.Float64,
}


def _station_file_url(station_id: str) -> str:
    """Build a station's file URL, padding the id the way DWD names the files."""
    return f"{_BASE_URL}{station_id.ljust(_STATION_ID_WIDTH, _PADDING)}{_FILE_SUFFIX}"


def _station_id_from_file_name(file_name: str) -> str:
    """Recover the catalogue station id from a file name, undoing DWD's underscore padding."""
    return file_name.removesuffix(_FILE_SUFFIX).rstrip(_PADDING)


def _read_poi_csv(content: bytes) -> pl.DataFrame:
    """Parse a station file, dropping the unit and description header lines."""
    # decoded here rather than left to polars: the German descriptions in the third line carry
    # umlauts and are latin-1, which polars would reject as invalid utf-8
    csv = content.decode("latin-1").encode("utf-8")
    df = pl.read_csv(csv, separator=";", infer_schema_length=0)
    return df.slice(_HEADER_ROWS)


class DwdPoiValues(TimeseriesValues):
    """Values class for DWD POI weather reports."""

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel | DatasetModel,
    ) -> pl.DataFrame:
        if isinstance(parameter_or_dataset, ParameterModel):
            dataset = parameter_or_dataset.dataset
        elif isinstance(parameter_or_dataset, DatasetModel):
            dataset = parameter_or_dataset
        else:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
        settings = cast("Settings", self.sr.stations.settings)
        file = download_file(
            url=_station_file_url(station_id),
            cache_dir=settings.cache_dir,
            # the files are rewritten every hour, and the point of the network is the newest row
            ttl=CacheExpiry.FIVE_MINUTES,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        if isinstance(file.content, Exception):
            if not file.is_no_internet_error:
                log.warning(f"Failed to fetch POI report for station {station_id}: {file.content}")
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
        # DWD rewrites all ~970 files every hour, and a rewrite in progress can be served as an
        # empty 200. polars raises NoDataError on those bytes, which would abort a whole
        # multi-station query over one file
        if file.is_empty:
            log.warning(f"POI report for station {station_id} is empty")
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
        df = _read_poi_csv(file.content.read())
        if df.is_empty():
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
        columns = [parameter.name_original for parameter in dataset.parameters if parameter.name_original in df.columns]
        if not columns:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
        df = df.select(
            pl.concat_str(
                [
                    pl.nth(_DATE_COLUMN_INDEX),
                    pl.nth(_TIME_COLUMN_INDEX),
                ],
                separator=" ",
            )
            .str.to_datetime("%d.%m.%y %H:%M", time_unit="us")
            .dt.replace_time_zone("UTC")
            .alias("date"),
            *[pl.col(column) for column in columns],
        )
        df = df.unpivot(index=["date"], variable_name="parameter", value_name="value")
        return df.select(
            pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            pl.col("parameter"),
            pl.lit(station_id, dtype=pl.String).alias("station_id"),
            pl.col("date"),
            # "---" marks a missing value and is cast away non-strictly, as is any other value DWD
            # cannot express as a number
            pl.col("value").str.replace(",", ".").cast(pl.Float64, strict=False),
            pl.lit(None, dtype=pl.Float64).alias("quality"),
        )


@dataclass
class DwdPoiRequest(TimeseriesRequest):
    """Request class for DWD POI weather reports."""

    metadata = DwdPoiMetadata
    _values = DwdPoiValues

    _base_columns: ClassVar = (
        "resolution",
        "dataset",
        "station_id",
        "icao_id",
        "start_date",
        "end_date",
        "latitude",
        "longitude",
        "height",
        "name",
        "state",
    )

    def _all(self) -> pl.LazyFrame:
        """Return the MOSMIX catalogue stations that currently have a POI file."""
        settings = cast("Settings", self.settings)
        files = list_remote_files_fsspec(_BASE_URL, settings, CacheExpiry.TWELVE_HOURS)
        station_ids = [
            _station_id_from_file_name(file.rsplit("/", 1)[-1]) for file in files if file.endswith(_FILE_SUFFIX)
        ]
        if not station_ids:
            log.warning("No POI station files found")
            return pl.LazyFrame()
        df = read_mosmix_station_catalogue(settings)
        if df.is_empty():
            return pl.LazyFrame()
        df = df.filter(pl.col("station_id").is_in(station_ids))
        resolution = self.metadata[0]
        df = df.with_columns(
            pl.lit(resolution.name, pl.String).alias("resolution"),
            pl.lit(resolution.datasets[0].name, pl.String).alias("dataset"),
            pl.lit(None, pl.Datetime(time_zone="UTC")).alias("start_date"),
            pl.lit(None, pl.Datetime(time_zone="UTC")).alias("end_date"),
            pl.lit(None, pl.String).alias("state"),
        )
        return df.select(self._base_columns).lazy()
