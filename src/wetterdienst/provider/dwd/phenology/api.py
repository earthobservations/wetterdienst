# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""DWD phenology data provider.

The phenological network reports, per station and reference year, the day of the year on which a
plant reached a developmental phase. One file holds one plant for one reporter group and one
period, so a dataset is a plant and a parameter is a phase -- see the module docstring of
``metadata.py`` for the mapping.

Two things about the source shape this module. The files are *not* per station: one file carries
every station that observed the plant, so a request parses each file once and keeps only the
stations it asked for, rather than re-reading a 160 MB historical file per station. And DWD keeps
several historical releases of the same series side by side (``..._1925_2018_hist.txt``,
``..._1925_2019_hist.txt``, ``..._1925_2024_hist.txt``); only the one with the latest end year is
complete, so the file index picks that one.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING, cast
from zoneinfo import ZoneInfo

import polars as pl
import portion

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.period import Period
from wetterdienst.model.metadata import DatasetModel, ParameterModel
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.phenology.metadata import (
    DWD_PHENOLOGY_OBJECT_IDS,
    DWD_PHENOLOGY_PATHS,
    DwdPhenologyMetadata,
)
from wetterdienst.util.network import download_file, list_remote_files_fsspec

if TYPE_CHECKING:
    from portion import Interval

    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

_BASE_URL = "https://opendata.dwd.de/climate_environment/CDC/observations_germany/phenology"
# the station catalogues live beside the data rather than in it, one per reporter group
_STATIONS_URL = "https://opendata.dwd.de/climate_environment/CDC/help/PH_Beschreibung_Phaenologie_Stationen_{}.txt"
_STATIONS_FILE = {"annual_reporters": "Jahresmelder", "immediate_reporters": "Sofortmelder"}

# the recent files reach back three full years beyond the current one, and the historical files
# are re-released about once a year, so the two overlap by a couple of years. Both windows are
# drawn generously: pulling a period that turns out to add nothing costs a download, while missing
# one loses observations outright, and the overlap is deduplicated downstream anyway.
_RECENT_YEARS = 4

_EMPTY_VALUES_SCHEMA = {
    "station_id": pl.String,
    "parameter": pl.String,
    "date": pl.Datetime(time_unit="us", time_zone="UTC"),
    "value": pl.Float64,
    "quality": pl.Float64,
}

# The files head their columns inconsistently: most write ``Stations_id``, the two beet files
# shout ``STATIONS_ID`` and one of them writes ``REFERENZ_JAHR`` where every other file has
# ``REFERENZJAHR``. Names are upper-cased on read and the odd one out is aliased here.
_COLUMN_ALIASES = {"REFERENZ_JAHR": "REFERENZJAHR"}


def _first_content_line(content: bytes) -> int:
    """Give the offset of the first line that is not blank.

    The two beet files open with a blank line before the header, which `read_csv` would take for
    the header itself.
    """
    offset = 0
    while offset < len(content):
        end = content.find(b"\n", offset)
        line = content[offset:] if end == -1 else content[offset:end]
        if line.strip():
            return offset
        if end == -1:
            return len(content)
        offset = end + 1
    return offset


def _read_phenology_file(content: bytes) -> pl.DataFrame:
    """Read one phenology text file into a frame of stripped strings.

    Everything is read as a string and cast afterwards: the columns are blank-padded to a fixed
    width, which no numeric parser accepts, and a value that is empty rather than padded has to
    become null rather than fail the whole file.
    """
    # sliced as bytes and transcoded once: splitting a 160 MB file into lines and joining them
    # back together holds four copies of it at the peak, for the sake of the blank first line
    # that only the two beet files have
    # `_first_content_line` returns the length when every line is blank, so this is empty exactly
    # when there is nothing to read -- tested without `strip()`, which would copy the whole file
    content = content[_first_content_line(content) :]
    if not content:
        return pl.DataFrame()
    df = pl.read_csv(
        content.decode("latin-1").encode("utf-8"),
        separator=";",
        infer_schema_length=0,
        truncate_ragged_lines=True,
    )
    columns = {}
    for column in df.columns:
        normalized = column.strip().upper()
        columns[column] = _COLUMN_ALIASES.get(normalized, normalized)
    return df.rename(columns)


def _parse_values(content: bytes, object_id: int) -> pl.DataFrame:
    """Parse one phenology file into tidy rows.

    ``Jultag`` is the value -- the day of the year the phase was reached -- and the row is dated to
    the 1st of January of ``Referenzjahr``, which is the timestamp the ``annual`` resolution uses.
    The entry date itself is not carried separately: it is that January the 1st plus ``Jultag``.
    """
    df = _read_phenology_file(content)
    if df.is_empty():
        return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
    df = df.select(
        # station ids are written unpadded here and zero-padded to five in the catalogue
        pl.col("STATIONS_ID").str.strip_chars().cast(pl.Int64, strict=False).alias("station_id"),
        pl.col("REFERENZJAHR").str.strip_chars().cast(pl.Int32, strict=False).alias("year"),
        pl.col("OBJEKT_ID").str.strip_chars().cast(pl.Int32, strict=False).alias("object_id"),
        pl.col("PHASE_ID").str.strip_chars().cast(pl.Int32, strict=False).alias("phase_id"),
        pl.col("JULTAG").str.strip_chars().cast(pl.Float64, strict=False).alias("value"),
        pl.col("QUALITAETSNIVEAU").str.strip_chars().cast(pl.Float64, strict=False).alias("quality"),
    )
    df = df.filter(
        pl.col("object_id").eq(object_id),
        pl.col("station_id").is_not_null(),
        pl.col("year").is_not_null(),
        pl.col("phase_id").is_not_null(),
    )
    return df.select(
        pl.col("station_id").cast(pl.String).str.pad_start(5, "0"),
        pl.col("phase_id").cast(pl.String).alias("parameter"),
        pl.datetime(pl.col("year"), 1, 1, time_zone="UTC").alias("date"),
        pl.col("value"),
        pl.col("quality"),
    )


def _file_url(dataset: DatasetModel, period: Period, settings: Settings) -> str | None:
    """Give the URL of the file holding one dataset for one period, if there is one.

    ``recent`` is one file at a fixed name. ``historical`` is not: DWD leaves the previous releases
    of a series in place beside the current one, distinguished only by the end year in the file
    name, and the earlier releases are truncated -- the 2018 release of the mugwort series is
    150 kB against 6.5 MB for the 2024 one. The latest end year is therefore the only one to read.
    A handful of series carry no year range at all, which sorts below any that does.
    """
    reporter, group, stem = DWD_PHENOLOGY_PATHS[dataset.name]
    if period == Period.RECENT:
        return f"{_BASE_URL}/{reporter}/{group}/recent/{stem}_akt.txt"
    url = f"{_BASE_URL}/{reporter}/{group}/historical/"
    # anchored on the suffix so that a stem is not matched by a longer one that starts with it --
    # ``..._Obst_Apfel`` would otherwise pick up ``..._Obst_Apfel_spaete_Reife_1925_2024_hist.txt``
    pattern = re.compile(rf"/{re.escape(stem)}(?:_(\d{{4}})_(\d{{4}}))?_hist\.txt$")
    candidates = []
    for candidate in list_remote_files_fsspec(url, settings=settings, cache_expiry=CacheExpiry.METAINDEX):
        match = pattern.search(candidate)
        if match:
            candidates.append((int(match.group(2)) if match.group(2) else -1, candidate))
    if not candidates:
        log.info(f"No historical file for dataset {dataset.name} below {url}")
        return None
    return max(candidates)[1]


def _periods_for(requested: set[Period] | None, dataset: DatasetModel) -> set[Period]:
    """Choose the periods to read for one dataset.

    A dataset published in only one period has nothing to choose between, so it is read whatever
    the request asked for. Periods derived from a date range assume `recent` holds the last few
    years, which does not hold for the two datasets with no historical release at all: their whole
    record lives in the recent file, back to 2018 for `annual_currant_all_varieties` and 2021 for
    `annual_beet`. Intersecting would have left those years unreachable by any date range -- the
    request returned nothing at all rather than the rows it asked for.

    The exception is a request that resolved to no period at all: that says its interval reaches
    no release, so there is nothing to read and nothing to widen to.
    """
    published = set(dataset.periods)
    if requested is not None and not requested:
        # the interval reaches no release at all -- see `TimeseriesRequest._get_periods`. Reading
        # the files anyway would download a whole network's records to filter them all away
        return set()
    return (requested or published) & published or published


class DwdPhenologyValues(TimeseriesValues):
    """Values class for DWD phenology data."""

    def __post_init__(self) -> None:
        """Post-initialize, adding the per-file cache."""
        super().__post_init__()
        # one file holds every station, so it is parsed once per (dataset, period) and cut down to
        # the stations of the request straight away. Without this a 20-station request would parse
        # the same 160 MB file twenty times over.
        self._files: dict[tuple[str, Period], pl.DataFrame] = {}
        self._station_ids: set[str] | None = None

    def _requested_station_ids(self) -> set[str]:
        """Give the stations of the request -- the only rows worth keeping out of a network-wide file."""
        if self._station_ids is None:
            self._station_ids = set(self.sr.df.get_column("station_id").unique().to_list())
        return self._station_ids

    def _load(self, dataset: DatasetModel, period: Period) -> pl.DataFrame:
        """Read one dataset for one period, reduced to the stations of the request."""
        key = (dataset.name, period)
        if key in self._files:
            return self._files[key]
        settings = cast("Settings", self.sr.stations.settings)
        url = _file_url(dataset, period, settings)
        df = pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
        if url:
            file = download_file(
                url=url,
                cache_dir=settings.cache_dir,
                # the longest bounded expiry `CacheExpiry` offers. The historical files are
                # re-released about once a year and run to 160 MB, so they would earn a far longer
                # one, but the only thing above twelve hours is `INFINITE`, and a release corrected
                # in place under the same name would then never be picked up again
                ttl=CacheExpiry.TWELVE_HOURS,
                client_kwargs=settings.fsspec_client_kwargs,
                cache_disable=settings.cache_disable,
                use_certifi=settings.use_certifi,
            )
            if isinstance(file.content, Exception):
                if not file.is_no_internet_error:
                    log.warning(f"Failed to download {url}: {file.content}")
            else:
                df = _parse_values(file.content.read(), DWD_PHENOLOGY_OBJECT_IDS[dataset.name])
                df = df.filter(pl.col("station_id").is_in(self._requested_station_ids()))
        self._files[key] = df
        return df

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel | DatasetModel,
    ) -> pl.DataFrame:
        dataset = (
            parameter_or_dataset
            if isinstance(parameter_or_dataset, DatasetModel)
            else parameter_or_dataset.dataset  # every phenology dataset is grouped
        )
        stations = cast("DwdPhenologyRequest", self.sr.stations)
        periods = _periods_for(cast("set[Period] | None", stations.periods), dataset)
        # oldest period first: where the periods overlap -- and recent reaches back into the years
        # the last historical release already covers -- `_process_dataset` keeps the first row for a
        # (parameter, date), and the historical file is the one carrying the final quality marks
        frames = [
            df
            for period in sorted(periods)
            if not (df := self._load(dataset, period).filter(pl.col("station_id").eq(station_id))).is_empty()
        ]
        if not frames:
            return pl.DataFrame(schema=_EMPTY_VALUES_SCHEMA)
        df = pl.concat(frames)
        return df.select(
            pl.lit(dataset.resolution.name, dtype=pl.String).alias("resolution"),
            pl.lit(dataset.name, dtype=pl.String).alias("dataset"),
            pl.col("parameter"),
            pl.col("station_id"),
            pl.col("date"),
            pl.col("value"),
            pl.col("quality"),
        )


@dataclass
class DwdPhenologyRequest(TimeseriesRequest):
    """Request class for DWD phenology data."""

    metadata = DwdPhenologyMetadata
    _values = cast("TimeseriesValues", DwdPhenologyValues)
    _selects_by_period = True

    @staticmethod
    def _parse_station_id(series: pl.Series) -> pl.Series:
        return series.cast(pl.String).str.pad_start(5, "0")

    @property
    def interval(self) -> Interval | None:
        """Interval of the request, in the timezone of the provider."""
        if not self.start_date:
            return None
        timezone = ZoneInfo(self.metadata.timezone)
        return portion.closed(
            cast("dt.datetime", self.start_date).astimezone(timezone),
            cast("dt.datetime", self.end_date).astimezone(timezone),
        )

    def _get_periods(self) -> set[Period] | None:
        """Choose the periods that can hold the requested interval."""
        interval = self.interval
        if interval is None:
            return None
        now_local = dt.datetime.now(ZoneInfo(self.metadata.timezone))
        year_start = now_local.replace(month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
        historical = portion.closed(dt.datetime(1678, 1, 1, tzinfo=year_start.tzinfo), year_start)
        recent = portion.closed(year_start.replace(year=year_start.year - _RECENT_YEARS), now_local)
        periods = set()
        if interval.overlaps(historical):
            periods.add(Period.HISTORICAL)
        if interval.overlaps(recent):
            periods.add(Period.RECENT)
        return periods

    def _stations(self, reporter: str) -> pl.DataFrame:
        """Read the station catalogue of one reporter group."""
        settings = cast("Settings", self.settings)
        url = _STATIONS_URL.format(_STATIONS_FILE[reporter])
        file = download_file(
            url=url,
            cache_dir=settings.cache_dir,
            ttl=CacheExpiry.METAINDEX,
            client_kwargs=settings.fsspec_client_kwargs,
            cache_disable=settings.cache_disable,
            use_certifi=settings.use_certifi,
        )
        if isinstance(file.content, Exception):
            log.warning(f"Failed to fetch DWD phenology station catalogue {url}: {file.content}")
            return pl.DataFrame()
        # read positionally: the header carries a stray tab inside the "Naturraumgruppe" cell and
        # names the columns in German, so the position is the more reliable handle
        df = pl.read_csv(
            file.content.read().decode("latin-1").encode("utf-8"),
            separator=";",
            has_header=False,
            skip_rows=1,
            infer_schema_length=0,
            truncate_ragged_lines=True,
        )
        if df.is_empty():
            return pl.DataFrame()
        df = df.select(
            pl.nth(0).str.strip_chars().alias("station_id"),
            pl.nth(1).str.strip_chars().alias("name"),
            pl.nth(2).str.strip_chars().cast(pl.Float64, strict=False).alias("latitude"),
            pl.nth(3).str.strip_chars().cast(pl.Float64, strict=False).alias("longitude"),
            pl.nth(4).str.strip_chars().cast(pl.Float64, strict=False).alias("height"),
            # "Datum Stationsaufloesung", the day the station was dissolved; empty while it runs
            pl.nth(9).str.strip_chars().str.to_datetime("%d.%m.%Y", time_zone="UTC", strict=False).alias("end_date"),
            pl.nth(10).str.strip_chars().alias("state"),
        )
        return df.filter(pl.col("station_id").str.len_chars().gt(0)).unique(subset=["station_id"], maintain_order=True)

    def _all(self) -> pl.LazyFrame:
        datasets = {
            (parameter.dataset.resolution.name, parameter.dataset.name)
            for parameter in cast("list[ParameterModel]", self.parameters)
        }
        if not datasets:
            return pl.LazyFrame()
        catalogues: dict[str, pl.DataFrame] = {}
        data = []
        for resolution, dataset in sorted(datasets):
            reporter = DWD_PHENOLOGY_PATHS[dataset][0]
            if reporter not in catalogues:
                catalogues[reporter] = self._stations(reporter)
            stations = catalogues[reporter]
            if stations.is_empty():
                continue
            # the catalogue is per reporter group rather than per plant, so it is replicated over
            # the requested datasets -- a station that never observed the plant simply has no values
            data.append(
                stations.with_columns(
                    pl.lit(resolution, pl.String).alias("resolution"),
                    pl.lit(dataset, pl.String).alias("dataset"),
                ),
            )
        if not data:
            return pl.LazyFrame()
        return pl.concat(data).lazy()
