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
    from collections.abc import Iterator

    from wetterdienst.model.result import ValuesResult
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

    def __post_init__(self) -> None:
        """Post-initialization of the DwdSwsmosValues class."""
        super().__post_init__()
        # the run this request answers for, resolved and parsed once. `None` is "not looked up
        # yet"; an empty frame is "looked up, and there is nothing there". See `_run_frame`
        self._run_frame_cache: pl.DataFrame | None = None

    def _run_content(self, settings: Settings) -> bytes | None:
        issue = cast("DwdSwsmosRequest", self.sr.stations).issue
        # how long a run may be answered from the cache is a property of the URL, not of the
        # request. A timestamped run is that run for good, while the ``LATEST`` alias is a name
        # whose content DWD replaces every hour -- so caching the alias by URL for twelve hours,
        # as this did, answered "the latest run" with one up to twelve hours old, whose first
        # twelve forecast hours have already happened. Measured: at 22:57 UTC the alias was
        # answered from the 21:00 run while the server was serving 22:00. Five minutes is what
        # ``dwd/mosmix`` holds its KML for, and against an hourly cadence it is a bounded lag
        ttl = CacheExpiry.TWELVE_HOURS
        if issue is DwdForecastDate.LATEST:
            files = list_remote_files_fsspec(f"{_BASE_URL}/", settings, CacheExpiry.NO_CACHE)
            names = {f.rsplit("/", 1)[-1]: f for f in files}
            # DWD maintains a ``swsmos_LATEST_opendata.csv.bz2`` alias pointing at the newest run;
            # fall back to the newest timestamped file if the alias is ever missing
            if _LATEST_FILE in names:
                url = names[_LATEST_FILE]
                ttl = CacheExpiry.FIVE_MINUTES
            else:
                timestamped = sorted(n for n in names if n.startswith("swsmos_") and n != _LATEST_FILE)
                if not timestamped:
                    return None
                # the fallback names a run rather than the alias, so it keeps the long TTL
                url = names[timestamped[-1]]
        else:
            url = _run_url(cast("dt.datetime", issue))
        file = download_file(
            url=url,
            cache_dir=settings.cache_dir,
            ttl=ttl,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        if isinstance(file.content, Exception):
            if not file.is_no_internet_error:
                log.warning(f"Failed to fetch SWSMOS run {url}: {file.content}")
            return None
        return file.content.read()

    def _run_frame(self, settings: Settings) -> pl.DataFrame:
        """Resolve and parse the run once, for every station it answers for.

        One run file holds every road station's whole forecast, where the collection above this
        asks for one station at a time -- so the run was listed, fetched and parsed once per
        station, and all but one station's rows thrown away each time. Five stations decompressed
        and parsed the same 306,612 rows five times -- 2.5 s of a 2.7 s request -- and twenty-five
        took 14.1 s, where the whole network of 1,836 stations would have spent a quarter of an
        hour on 1,836 parses of one file. They now take 0.7 s and 0.8 s: one parse either way, the
        cost flat in the number of stations asked for. The file itself comes from the cache; what
        was repeated is the bz2 decompress and the CSV parse (~0.5 s), and -- for a `LATEST`
        request -- the uncached directory listing that resolves the alias, which is a remote round
        trip rather than local work.

        The whole run is kept, where road keeps only its last station group: a run is one file of
        some 20 MB no matter how wide the request or how long the window, so there is nothing here
        to bound. Nor is there a key. A group varies from station to station, while the run is a
        property of the request -- `issue` is resolved when the request is built and cannot change
        while it is answered -- so the frame parsed for one station is by construction the frame
        every other station wants.

        For `DwdForecastDate.LATEST` that also makes the answer consistent rather than merely
        quicker: resolving the alias once pins every station to one model run. Resolved per
        station, a walk that outlived the alias's cache entry -- or one made with caching disabled,
        or falling back to the timestamped listing, which is never cached -- re-fetched the alias
        part way through, so the stations after that point were answered from whatever run DWD had
        published by then, and the frame quietly mixed two runs.
        """
        if self._run_frame_cache is None:
            content = self._run_content(settings)
            self._run_frame_cache = _read_run_csv(content) if content is not None else pl.DataFrame()
        return self._run_frame_cache

    def query(self) -> Iterator[ValuesResult]:
        """Answer each station of the request, from one run resolved for this query.

        The run is pinned for the length of a query and no longer. `StationsResult.values` builds a
        values object per access, so most callers get a fresh run either way -- but one that keeps
        the object and queries it again on a timer is asking for the latest run a second time, and
        would otherwise be answered from the one resolved on its first call for as long as it lived.
        """
        self._run_frame_cache = None
        yield from super().query()

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
        df = self._run_frame(settings)
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
        if isinstance(file.content, Exception):
            log.warning(f"Failed to fetch SWSMOS station catalogue: {file.content}")
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
