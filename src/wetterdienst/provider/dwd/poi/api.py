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
from wetterdienst.model.quality_flags import Sentinel, join_quality_flags, null_sentinels
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

# The cloud cover is a percent on a grid of oktas (oktas x 12.5: 0, 12/13, 25, ... 100), and 20,804 reports of 960
# files (2026-10-12) hold 113 in 26 and 126 in 32 of the 8744 that have one. 113 is 9 oktas, the WMO N=9 "sky
# obscured"; 126 comes with fog (present_weather 5), a visibility below 1 km and no cloud base, and DWD describes
# neither. Neither is an amount of cloud.
_CLOUD_COVER_CODES = (Sentinel("113", "126", where=pl.col("parameter").eq("cloud_cover_total")),)

# The wind direction is mostly on a grid of 10 degrees (some stations write single degrees, where a 0 is no bearing
# either) with north as 360 and 0 for no direction: in 11,364 reports with a
# direction of 937 files (2026-10-12) 141 read 360, 141 read 10 and 155 read 350, but 747 read 0. 401 of those have a
# wind speed of 0 (of the 465 reports with a speed of 0), and 346, of 68 stations, a speed above 0 (4 km/h in 184, 7
# in 67, 5 in 32, 11 in 21, 2 in 19, and 23 from 8 to 22): a wind with no direction, a calm or a variable one, which
# the files do not tell apart and DWD does not describe. Neither is a bearing, so both are null.
_NO_WIND_DIRECTION = Sentinel(
    "0", where=pl.col("parameter").eq("mean_wind_direction_during_last_10 min_at_10_meters_above_ground")
)

_EMPTY_VALUES_SCHEMA = {
    "resolution": pl.String,
    "dataset": pl.String,
    "parameter": pl.String,
    "station_id": pl.String,
    "timestamp": pl.Datetime(time_unit="us", time_zone="UTC"),
    "value": pl.Float64,
}


def _station_file_url(station_id: str) -> str:
    """Build a station's file URL, padding the id the way DWD names the files."""
    return f"{_BASE_URL}{station_id.ljust(_STATION_ID_WIDTH, _PADDING)}{_FILE_SUFFIX}"


def _station_id_from_file_name(file_name: str) -> str:
    """Recover the catalogue station id from a file name, undoing DWD's underscore padding."""
    return file_name.removesuffix(_FILE_SUFFIX).rstrip(_PADDING)


def _read_poi_csv(content: bytes) -> pl.DataFrame:
    """Parse a station file, dropping the unit and description header lines.

    Read as latin-1: the German descriptions in the third line carry umlauts, which polars would
    otherwise reject as invalid utf-8.
    """
    df = pl.read_csv(content, separator=";", infer_schema_length=0, encoding="latin-1")
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
        # a 404 is a station whose file DWD has withdrawn since the catalogue was read, and is warned
        # about; any other failure is an outage, which swallowed would read as a station without
        # a report (GH-2461)
        if file.status != 404:
            file.raise_if_exception()
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
            .alias("timestamp"),
            *[pl.col(column) for column in columns],
        )
        df = df.unpivot(index=["timestamp"], variable_name="parameter", value_name="value")
        # "---" marks a missing value, and any other value DWD cannot express as a number is none either: both
        # become null and the text stays beside the value as `raw:` (GH-2759)
        value, raw = null_sentinels(
            pl.col("value").str.replace(",", "."), *_CLOUD_COVER_CODES, _NO_WIND_DIRECTION, non_numeric=True
        )
        return df.select(
            pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            pl.col("parameter"),
            pl.lit(station_id, dtype=pl.String).alias("station_id"),
            pl.col("timestamp"),
            value.alias("value"),
            join_quality_flags(None, raw=raw),
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
        "start_timestamp",
        "end_timestamp",
        "latitude",
        "longitude",
        "elevation",
        "name",
        "region",
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
            pl.lit(None, pl.Datetime(time_zone="UTC")).alias("start_timestamp"),
            pl.lit(None, pl.Datetime(time_zone="UTC")).alias("end_timestamp"),
            pl.lit(None, pl.String).alias("region"),
        )
        return df.select(self._base_columns).lazy()
