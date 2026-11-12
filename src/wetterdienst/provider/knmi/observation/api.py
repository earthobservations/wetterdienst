# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""KNMI (Netherlands) observation data provider.

The values are read from KNMI's EDR API (`edr`), which answers a range of several stations in one request. Until GH-3928
they were read from the Open Data API, which serves one NetCDF file for every timestamp and every station at once: a
station's time series was one file for each of its moments, a year of hourly values 8,760 requests of a quota of 1,000
an hour. The EDR API is a separate API with its own key, `WD_AUTH__KNMI_EDR`.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar, cast

import polars as pl

from wetterdienst.exceptions import CredentialMissingError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.metadata import DatasetModel, ParameterModel
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.knmi.observation import edr
from wetterdienst.provider.knmi.observation.grid import CALENDAR_RESOLUTIONS, floor
from wetterdienst.provider.knmi.observation.metadata import KnmiObservationMetadata
from wetterdienst.provider.knmi.observation.parser import knmi_readings, without_rows_before_the_variable
from wetterdienst.provider.knmi.observation.stations import read_stations
from wetterdienst.settings import Settings
from wetterdienst.util.network import download_file

if TYPE_CHECKING:
    from collections.abc import Iterator

    from wetterdienst.model.result import ValuesResult

log = logging.getLogger(__name__)

#: The types of station of the list (compared stripped and in lower case) that only the 10-minute dataset holds: the
#: four
#: fog stations (Assendelft 06233, Muiden 06236, Nieuw-Vennep 06237 and Nieuwkoop 06238) were in the 10-minute files of
#: 2014 to 2024 and in none of the hourly, daily, monthly and annual ones of 1901 to 2026 (read 2026-11-11).
#: "Fog station/Meteo site" (Voorschoten 06215) is in them all and is not this type.
_TEN_MINUTE_ONLY_TYPES = frozenset({"fog station"})

#: The WMO blocks of the stations a dataset does not hold although the list has them: block 78, the Caribbean
#: Netherlands (Saba 78871, Sint Eustatius 78873, Bonaire 78990), has daily and monthly values (2026) and no annual
#: ones: the annual collection answers 404 for them (read 2026-11-12).
_BLOCKS_NOT_IN_DATASET = {Resolution.ANNUAL: ("78",)}

#: How old the end of the interval a chunk covers must be for its content to be kept long. Before it a chunk is kept for
#: five minutes (GH-3927): the line was drawn at six hours, and it is no measured moment of settling. What was measured
#: (2026-11-11) is that the hourly files were made 5.5 to 78 hours after their hour, at a median of 25.
_SETTLED_AFTER = dt.timedelta(hours=6)

#: How long a check of the key is kept, which only an acceptance is: a key that is revoked stops reading valid within
#: the
#: minute
_PROBE_EXPIRY = CacheExpiry.ONE_MINUTE


def _now() -> dt.datetime:
    """Give the time the age of a chunk and the end of the data are taken against (a seam for a test, which pins it)."""
    return dt.datetime.now(dt.UTC)


def _chunk_expiry(end: dt.datetime | None) -> CacheExpiry:
    """Say how long the content of a chunk is kept, by the end of the interval it covers (GH-3927).

    A chunk whose end is younger than `_SETTLED_AFTER` is kept for `CacheExpiry.FIVE_MINUTES`: it is asked again for
    what KNMI has added since. An older one is kept for `CacheExpiry.TWELVE_HOURS`. That is no claim that it is final,
    for no age makes a chunk so (GH-4008, read 2026-11-11): KNMI validates the hourly and the daily values one to four
    weeks after their period and replaces them then, in batches, and corrects older ones now and then, a few at a time.
    So the twelve hours are no longer than a replaced value takes to be read again: the cap, not the age, limits how
    stale
    a copy is. A chunk whose end is not known counts as young.
    """
    if end is None:
        return CacheExpiry.FIVE_MINUTES
    if end.tzinfo is None:
        end = end.replace(tzinfo=dt.UTC)
    if _now() - end < _SETTLED_AFTER:
        return CacheExpiry.FIVE_MINUTES
    return CacheExpiry.TWELVE_HOURS


def _resolution_of(parameter_or_dataset: ParameterModel | DatasetModel) -> Resolution:
    """Return the Resolution enum for a parsed parameter or whole-dataset selection."""
    dataset = parameter_or_dataset.dataset if isinstance(parameter_or_dataset, ParameterModel) else parameter_or_dataset
    return dataset.resolution.value


def _probe_key(settings: Settings) -> bool | None:
    """Ask the API for its landing page (1 KB) with the key: True if it is accepted, False if it is refused, else None.

    A 401 or a 403 is answered by the gateway before the quota, so a refusal costs none; an acceptance costs one request
    and is kept for a minute. One attempt: it is a question about now. None for what says nothing of the key: no
    network, a 429, a 5xx.
    """
    if not settings.auth.knmi_edr:
        return False
    url = f"{edr.EDR_BASE_URL}/"
    kwargs = edr.client_kwargs(settings)
    file = download_file(
        url=url,
        cache_dir=settings.cache_dir,
        ttl=_PROBE_EXPIRY,
        client_kwargs=kwargs,
        cache_disable=settings.cache_disable,
        use_certifi=settings.use_certifi,
        attempts=1,
    )
    if not isinstance(file.content, Exception):
        return True
    if file.status in {401, 403}:
        return False
    log.warning("Could not check the KNMI EDR key (status %s)", file.status)
    return None


@dataclass(frozen=True)
class _EdrRead:
    """What the EDR API gave of a station: the readings of it, as `knmi_readings` makes them, None if it gave none."""

    frame: pl.DataFrame | None


class KnmiObservationValues(TimeseriesValues):
    """Values class for KNMI observation data."""

    def __post_init__(self) -> None:
        """Post-initialization of the KnmiObservationValues class."""
        super().__post_init__()
        # the reader of the API of the query in hand, and what it has read for the stations that follow the one in hand
        # (`_edr_read`): both belong to one walk (`query`)
        self._edr: edr.EdrReader | None = None
        self._edr_reads: dict[tuple[str, str], dict[str, edr.Reading]] = {}

    def query(self) -> Iterator[ValuesResult]:
        """Answer each station of the request; what the EDR API gave is kept for the walk and no longer."""
        self._edr = None
        self._edr_reads.clear()
        try:
            yield from super().query()
        finally:
            # a result keeps the values object, and so what is held here, for as long as its caller keeps it
            self._edr = None
            self._edr_reads.clear()

    def _collect_station_parameter_or_dataset(
        self,
        station_id: str,
        parameter_or_dataset: ParameterModel | DatasetModel,
    ) -> pl.DataFrame:
        if isinstance(parameter_or_dataset, DatasetModel):
            dataset = parameter_or_dataset
        elif isinstance(parameter_or_dataset, ParameterModel):
            dataset = parameter_or_dataset.dataset
        else:
            return pl.DataFrame()
        settings = cast("Settings", self.sr.request.settings)
        start_date = self.sr.start
        end_date = self.sr.end
        if not start_date or not end_date or not settings.auth.knmi_edr:
            return pl.DataFrame()
        # the parameters asked of the API are all of the dataset, whichever were requested: the core judges a parameter
        # against its neighbours in the dataset (the maximum of a day against its mean and its minimum), so the frame
        # must hold them, and the same request is the same cached chunk for every parameter
        parameter_names = [parameter.name_original for parameter in dataset.parameters]
        read = self._edr_read(station_id, dataset, parameter_names, start_date, end_date, settings)
        return pl.DataFrame() if read.frame is None else read.frame

    def _edr_read(
        self,
        station_id: str,
        dataset: DatasetModel,
        parameter_names: list[str],
        start_date: dt.datetime,
        end_date: dt.datetime,
        settings: Settings,
    ) -> _EdrRead:
        """Read a station's range from the EDR API.

        The stations of the result that follow the one in hand are read with it (`_edr_batch`), their readings kept for
        when the walk comes to them. The requests are planned for them together (`edr.plan_requests`).
        """
        resolution = dataset.resolution.value
        bounds = edr.stamp_bounds(start_date, end_date, resolution, _now())
        if bounds is None:
            return _EdrRead(None)
        first, last = bounds
        reader = self._edr
        if reader is None:
            reader = self._edr = edr.EdrReader(settings, _chunk_expiry)
        reads = self._edr_reads.setdefault((dataset.resolution.name, dataset.name), {})
        if station_id not in reads:
            batch = self._edr_batch(
                station_id, dataset, reads, edr.count_stamps(first, last, resolution), len(parameter_names)
            )
            if not batch:
                return _EdrRead(None)
            plan = edr.plan_requests(len(batch), first, last, resolution, _now(), len(parameter_names))
            reads.update(reader.read(batch, resolution, parameter_names, plan))
        reading = reads.pop(station_id, None)
        if reading is None or not reading.frames:
            return _EdrRead(None)
        # the chunks are whole blocks of the calendar: cut to the stamps of the range
        raw = pl.concat(reading.frames).filter(pl.col("timestamp").is_between(first, last))
        raw = without_rows_before_the_variable(raw, resolution)
        if raw.is_empty():
            return _EdrRead(None)
        return _EdrRead(knmi_readings(raw, trace_codes=resolution not in CALENDAR_RESOLUTIONS))

    def _edr_batch(
        self, station_id: str, dataset: DatasetModel, reads: dict[str, edr.Reading], stamps: int, parameters: int
    ) -> list[tuple[str, str]]:
        """Give the station in hand and those after it in the result for the requests of the EDR API, as (id, WSI).

        Empty if the station in hand has no WIGOS identifier to ask by. As many as fit the memory that is held before
        the first is handed over (`edr.MEMORY_POINTS`: a long range is a station at a time, a day is all of them), and
        no more than `edr.STATIONS_AT_MOST`; only the station in hand where the walk stops where the data says
        (interpolation, summary), and no more than the rank asked for.
        """
        if "wigos_id" not in self.sr.df.columns:
            return []
        df = self.sr.df.filter((pl.col("resolution") == dataset.resolution.name) & (pl.col("dataset") == dataset.name))
        rows = df.select("station_id", "wigos_id").unique(subset="station_id", maintain_order=True).rows()
        position = next((index for index, (identifier, _) in enumerate(rows) if identifier == station_id), None)
        if position is None or not edr.is_wsi(rows[position][1]):
            return []
        room = min(edr.STATIONS_AT_MOST, max(1, edr.MEMORY_POINTS // (stamps * max(parameters, 1))))
        if not self._fetch_ahead_allowed:
            room = 1
        if self.sr._rank:  # noqa: SLF001
            room = min(room, self.sr._rank)  # noqa: SLF001
        batch = [rows[position]]
        for identifier, wsi in rows[position + 1 :]:
            if len(batch) >= room:
                break
            if (
                identifier not in reads
                and identifier not in (self._edr.skipped if self._edr else ())
                and edr.is_wsi(wsi)
            ):
                batch.append((identifier, wsi))
        return batch


def _stations_of(df: pl.DataFrame, resolution: Resolution) -> pl.DataFrame:
    """Give the stations of the list that have data at a resolution: without those that cannot."""
    first = edr.FIRST_STAMP[resolution]
    df = df.filter(pl.col("end_timestamp").is_null() | (pl.col("end_timestamp") >= first))
    if resolution != Resolution.MINUTE_10:
        kind = pl.col("type").str.strip_chars().str.to_lowercase()
        df = df.filter(~kind.is_in(_TEN_MINUTE_ONLY_TYPES))
    for block in _BLOCKS_NOT_IN_DATASET.get(resolution, ()):
        df = df.filter(~pl.col("station_id").str.starts_with(block))
    return df.drop("type")


@dataclass
class KnmiObservationRequest(TimeseriesRequest):
    """Request class for KNMI observation data."""

    metadata = KnmiObservationMetadata
    _values = KnmiObservationValues

    # extend base columns of core class with the station's full WIGOS station identifier, of which
    # `station_id` is the trailing WMO number
    _base_columns: ClassVar = (
        *TimeseriesRequest._base_columns,  # noqa: SLF001
        "wigos_id",
    )

    @classmethod
    def is_configured(cls) -> bool:  # noqa: D102
        return bool(Settings().auth.knmi_edr)

    @classmethod
    def is_valid(cls, settings: Settings | None = None) -> bool | None:  # noqa: D102
        return _probe_key(settings or Settings())

    def __post_init__(self) -> None:  # noqa: D105
        super().__post_init__()
        settings = cast("Settings", self.settings)
        if not settings.auth.knmi_edr:
            msg = (
                "KNMI Data Platform reads from its EDR API, which requires a key of that API. "
                f"Request one in the API Catalog at {edr.EDR_KEY_URL} "
                "(a key of the Open Data API, as WD_AUTH__KNMI held until now, does not work) "
                "and set WD_AUTH__KNMI_EDR=<api_key> (env var) "
                "or Settings(auth={'knmi_edr': '<api_key>'}) (Python)."
            )
            raise CredentialMissingError(msg)
        # When the whole request targets the daily resolution, snap start down to the day: a daily value is stamped
        # with its date, so a query beginning mid-day should include that day, and flooring start here (the one
        # filter the framework shares across resolutions) keeps the stamp on the date AND the day in range. The
        # 10-minute and the hourly values are stamped with the END of their interval, so an unaligned start
        # correctly excludes the interval that ends before it (the framework's [start, end] filter does
        # that). A mixed-resolution request has no single boundary and is left as-is.
        resolutions = {
            _resolution_of(parameter_or_dataset)
            for parameter_or_dataset in self.parameters
            if isinstance(parameter_or_dataset, (ParameterModel, DatasetModel))
        }
        # the same for a month and a year, which are stamped with their first day
        for resolution in (Resolution.DAILY, *CALENDAR_RESOLUTIONS):
            if self.start and resolutions == {resolution}:
                self.start = floor(cast("dt.datetime", self.start), resolution)

    def _all(self) -> pl.LazyFrame:
        """Enumerate stations per requested resolution, from the list of the stations of KNMI's EDR API.

        The list is one for every resolution (`stations.read_stations`), of which a resolution lists the stations that
        have data in its dataset (`_stations_of`): the 10-minute network holds the fog stations that the other four do
        not, and no station of the 10-minute data closed before it.
        """
        settings = cast("Settings", self.settings)
        # in the order the request names them (a set would give the stations in the order of the hash seed of the
        # process, GH-3551)
        requested = dict.fromkeys(
            (parameter.dataset.resolution.value, parameter.dataset.resolution.name, parameter.dataset.name)
            for parameter in self.parameters
            if isinstance(parameter, ParameterModel)
        )
        if not requested:
            return pl.LazyFrame()
        stations = read_stations(settings, _now())
        if stations.is_empty():
            return pl.LazyFrame()
        data = [
            _stations_of(stations, resolution).with_columns(
                pl.lit(resolution_name, dtype=pl.String).alias("resolution"),
                pl.lit(dataset, dtype=pl.String).alias("dataset"),
            )
            for resolution, resolution_name, dataset in requested
        ]
        return pl.concat(data, how="diagonal").lazy()
