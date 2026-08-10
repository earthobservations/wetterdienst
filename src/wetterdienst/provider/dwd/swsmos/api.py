# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD SWSMOS (Straßenwetter-MOS) road weather forecast provider.

DWD publishes one CSV file per model run under
https://opendata.dwd.de/weather/local_forecasts/swsmos/ (``swsmos_<YYYYMMDDHH0000>_opendata.csv.bz2``),
each holding an hourly forecast to +167 h for every road weather station. The station catalogue is
``swsKatalog.csv.bz2``. See ``metadata.py`` for the field/unit mapping.

Each run file is a small deviation from a plain CSV: line 1 is the header, line 2 is the run
timestamp, and the remaining lines are ``ID;Lat;Lon;YYYYMMDDHHmm;<values...>`` rows (one per station
per forecast hour). Values use ``.`` decimals; the catalogue uses ``,`` decimals.
"""

from __future__ import annotations

import bz2
import contextlib
import datetime as dt
import logging
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, cast
from zoneinfo import ZoneInfo

import polars as pl

from wetterdienst.exceptions import InvalidEnumerationError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.metadata import DatasetModel, ParameterModel
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.swsmos.metadata import DwdSwsmosMetadata
from wetterdienst.util.enumeration import parse_enumeration_from_template
from wetterdienst.util.network import download_file, list_remote_files_fsspec

if TYPE_CHECKING:
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

_UTC = ZoneInfo("UTC")
_BASE_URL = "https://opendata.dwd.de/weather/local_forecasts/swsmos"
_CATALOG_URL = f"{_BASE_URL}/swsKatalog.csv.bz2"
_LATEST_FILE = "swsmos_LATEST_opendata.csv.bz2"

_EMPTY_VALUES_SCHEMA = {
    "resolution": pl.String,
    "dataset": pl.String,
    "parameter": pl.String,
    "station_id": pl.String,
    "date": pl.Datetime(time_unit="us", time_zone="UTC"),
    "value": pl.Float64,
    "quality": pl.Float64,
}


class DwdForecastDate(Enum):
    """Sentinel selecting the latest available model run."""

    LATEST = "latest"


def _run_url(issue: dt.datetime) -> str:
    return f"{_BASE_URL}/swsmos_{issue:%Y%m%d%H}0000_opendata.csv.bz2"


def _read_run_csv(content: bytes) -> pl.DataFrame:
    """Decompress and parse a run file, dropping the run-timestamp line between header and data."""
    lines = bz2.decompress(content).decode("latin-1").splitlines()
    if len(lines) < 3:
        return pl.DataFrame()
    csv = ("\n".join([lines[0], *lines[2:]])).encode()
    return pl.read_csv(csv, separator=";", infer_schema_length=0)


class DwdSwsmosValues(TimeseriesValues):
    """Values class for DWD SWSMOS road weather forecast data."""

    def _run_content(self, settings: Settings) -> bytes | None:
        issue = cast("DwdSwsmosRequest", self.sr.stations).issue
        if issue is DwdForecastDate.LATEST:
            files = list_remote_files_fsspec(f"{_BASE_URL}/", settings, CacheExpiry.NO_CACHE)
            names = {f.rsplit("/", 1)[-1]: f for f in files}
            # DWD maintains a ``swsmos_LATEST_opendata.csv.bz2`` alias pointing at the newest run;
            # fall back to the newest timestamped file if the alias is ever missing
            if _LATEST_FILE in names:
                url = names[_LATEST_FILE]
            else:
                timestamped = sorted(n for n in names if n.startswith("swsmos_") and n != _LATEST_FILE)
                if not timestamped:
                    return None
                url = names[timestamped[-1]]
        else:
            url = _run_url(cast("dt.datetime", issue))
        file = download_file(
            url=url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.TWELVE_HOURS,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        # a run that has not been published yet has no file, which is a 404 and routine; a
        # timeout or a 5xx is not, and must not be reported as "no forecast for this run"
        file.raise_unless_absent()
        if isinstance(file.content, Exception):
            if not file.is_no_internet_error:
                log.debug(f"No SWSMOS run {url}: {file.content}")
            return None
        return file.content.read()

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
        content = self._run_content(settings)
        if content is None:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
        df = _read_run_csv(content)
        if df.is_empty() or "ID" not in df.columns:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
        df = df.filter(pl.col("ID") == station_id)
        if df.is_empty():
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
        columns = [p.name_original for p in dataset.parameters if p.name_original in df.columns]
        df = df.select(
            pl.col("YYYYMMDDHHmm")
            .str.to_datetime("%Y%m%d%H%M", time_unit="us")
            .dt.replace_time_zone("UTC")
            .alias("date"),
            *[pl.col(c).cast(pl.Float64, strict=False) for c in columns],
        )
        df = df.unpivot(index=["date"], variable_name="parameter", value_name="value")
        return df.select(
            pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            pl.col("parameter"),
            pl.lit(station_id, dtype=pl.String).alias("station_id"),
            pl.col("date"),
            pl.col("value"),
            pl.lit(None, dtype=pl.Float64).alias("quality"),
        )


@dataclass
class DwdSwsmosRequest(TimeseriesRequest):
    """Request class for DWD SWSMOS road weather forecast data."""

    metadata = DwdSwsmosMetadata
    _values = DwdSwsmosValues

    issue: str | dt.datetime | DwdForecastDate = DwdForecastDate.LATEST

    def __post_init__(self) -> None:
        """Resolve the ``issue`` (model run) to LATEST or a UTC hour."""
        super().__post_init__()
        issue: str | dt.datetime | DwdForecastDate = self.issue
        with contextlib.suppress(InvalidEnumerationError):
            issue = parse_enumeration_from_template(issue, DwdForecastDate)  # ty: ignore[no-matching-overload]
        if issue is not DwdForecastDate.LATEST:
            if isinstance(issue, str):
                issue = dt.datetime.fromisoformat(issue)
            issue = dt.datetime(issue.year, issue.month, issue.day, issue.hour, tzinfo=_UTC)
        self.issue = issue

    def _all(self) -> pl.LazyFrame:
        settings = cast("Settings", self.settings)
        file = download_file(
            url=_CATALOG_URL,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        # a catalogue that failed to download is not an empty catalogue -- only a missing
        # connection stays soft
        file.raise_if_exception()
        if isinstance(file.content, Exception):
            log.warning("No internet connection while fetching the SWSMOS station catalogue")
            return pl.LazyFrame()
        # the catalogue is latin-1 encoded (German station names carry umlauts)
        catalogue = bz2.decompress(file.content.read()).decode("latin-1").encode("utf-8")
        df = pl.read_csv(catalogue, separator=";", infer_schema_length=0)
        if df.is_empty():
            return pl.LazyFrame()
        resolution = self.metadata[0]
        # catalogue columns: Kennung;Name;Streckentyp;Streckenbelag;Breite;Laenge;Hoehe;Flughafen;Inaktiv
        # (Breite/Laenge/Hoehe use a comma decimal separator, unlike the run files)
        # drop stations flagged inactive (the ``Inaktiv`` column is empty for active stations)
        if "Inaktiv" in df.columns:
            df = df.filter(pl.col("Inaktiv").is_null() | (pl.col("Inaktiv").str.strip_chars() == ""))
        return df.select(
            pl.col("Kennung").alias("station_id"),
            pl.col("Name").alias("name"),
            pl.col("Breite").str.replace(",", ".").cast(pl.Float64, strict=False).alias("latitude"),
            pl.col("Laenge").str.replace(",", ".").cast(pl.Float64, strict=False).alias("longitude"),
            pl.col("Hoehe").str.replace(",", ".").cast(pl.Float64, strict=False).alias("height"),
            pl.lit(resolution.name, pl.String).alias("resolution"),
            pl.lit(resolution.datasets[0].name, pl.String).alias("dataset"),
        ).lazy()
