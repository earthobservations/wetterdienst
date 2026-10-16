# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Download climate observations data from DWD server."""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field
from io import BytesIO
from typing import TYPE_CHECKING
from zipfile import BadZipFile

from fsspec.implementations.zip import ZipFileSystem

from wetterdienst.exceptions import ProductFileNotFoundError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.dwd.observation.metadata import DwdObservationMetadata
from wetterdienst.util.network import File, download_files

if TYPE_CHECKING:
    import polars as pl

    from wetterdienst.model.metadata import DatasetModel
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

#: DWD's note on a period of a station in `Metadaten_Parameter_*.txt` (column `Zusatz-Info`) whose hourly stamps
#: are in true local solar time ("Wahre Ortszeit"), not UTC
WOZ_INFO = "Stundenwerte in WOZ"
#: the same note for the periods of the eMD archive (the Meteorologischer Dienst der DDR) whose hourly stamps are
#: MEZ, the fixed UTC+1 without daylight saving time (GH-2709). The plain `Stundenwerte in MEZ` is another note
MEZ_MD_INFO = "Stundenwerte in MEZ (MD)"


@dataclass
class ProductFile(File):
    """The product file of an archive, with what the archive says of the time its stamps are in."""

    woz_spans: tuple[tuple[dt.date, dt.date], ...] = ()
    """The periods (first and last day, both included) of the file whose stamps are in true solar time (GH-2816)."""
    mez_md_spans: dict[str, tuple[tuple[dt.datetime, dt.datetime], ...]] = field(default_factory=dict)
    """Per parameter (`tt_tu`, `rf_tu`), the stamps (first and last, both included, UTC) the archive calls MEZ (MD)."""


def download_climate_observations_data(
    remote_files: pl.Series,
    settings: Settings,
    dataset: DatasetModel | None = None,
) -> list[File]:
    """Download climate observations data from DWD server."""
    files = download_files(
        urls=remote_files.to_list(),
        cache_dir=settings.cache_dir,
        ttl=CacheExpiry.FIVE_MINUTES,
        client_kwargs=settings.fsspec_client_kwargs,
        cache_disable=settings.cache_disable,
        use_certifi=settings.use_certifi,
    )
    # a 404 is a file that is not there, and is dropped; any other failure -- a timeout, a 5xx after
    # the retries -- is an outage, which dropped would read as a station without data (GH-2430)
    for file in files:
        if file.status != 404:
            file.raise_if_exception()
    files = [file for file in files if isinstance(file.content, BytesIO)]
    # unpack the files
    return [_unpack_climate_observations_data(file, dataset) for file in files]


def _unpack_climate_observations_data(file: File, dataset: DatasetModel | None = None) -> File:
    try:
        zfs = ZipFileSystem(file.content)
    except BadZipFile as e:
        msg = f"The archive of {file.filename} seems to be corrupted."
        raise BadZipFile(msg) from e
    product_file = zfs.glob("produkt*")
    if len(product_file) != 1:
        msg = f"The archive of {file.filename} does not hold a 'produkt' file."
        raise ProductFileNotFoundError(msg)
    product_bytes = zfs.open(product_file[0]).read()
    # let's put this again in another file object
    return ProductFile(
        url=file.url,
        content=BytesIO(product_bytes),
        status=file.status,
        # carried, not dropped: unpacking does not change where the bytes came from, and a caller
        # that finds the member corrupt is exactly who the flag is for
        from_cache=file.from_cache,
        woz_spans=_read_woz_spans(zfs) if dataset == DwdObservationMetadata.hourly.sun else (),
        mez_md_spans=_read_mez_md_spans(zfs) if dataset == DwdObservationMetadata.hourly.temperature_air else {},
    )


def _read_woz_spans(zfs: ZipFileSystem) -> tuple[tuple[dt.date, dt.date], ...]:
    """Read the periods of a station whose hourly stamps are in true solar time from the archive's metadata.

    `Metadaten_Parameter_*.txt` lists the periods of the series with the source of their data and, in `Zusatz-Info`,
    `Stundenwerte in WOZ` or `Stundenwerte in UTC`. They do not end at one date: 528 of the 636 stations of
    `hourly/sun` have WOZ periods, the last of 140 of them ends on 2001-03-31 but those of 172 run to 2006, and some
    stations change back and forth by the month. A file without the metadata, or a line that does not read, is no WOZ.
    """
    files = zfs.glob("**/Metadaten_Parameter_*.txt")
    if not files:
        return ()
    text = zfs.open(files[0]).read().decode("latin-1")
    spans = []
    for line in text.splitlines()[1:]:
        parts = [part.strip() for part in line.split(";")]
        if len(parts) < 9 or not parts[0].isdigit() or parts[8] != WOZ_INFO:
            continue
        try:
            first = dt.date.fromisoformat(parts[1])
            # an open end is still running
            last = dt.date.fromisoformat(parts[2]) if parts[2] else dt.date.max
        except ValueError:
            log.warning(f"The period {line!r} of the metadata of {files[0]} does not read and is taken as UTC.")
            continue
        spans.append((first, last))
    return tuple(spans)


def _read_mez_md_spans(zfs: ZipFileSystem) -> dict[str, tuple[tuple[dt.datetime, dt.datetime], ...]]:
    """Read, per parameter, the stamps of a station's hourly air temperature that are MEZ (MD) from the metadata.

    `Metadaten_Parameter_*.txt` has a table of periods per parameter, and the tables of `TT_TU` and `RF_TU` differ in
    42 of the 637 stations (Aue 00222: `TT_TU` is MEZ (MD) from 1982-01-01, `RF_TU` from 1991-01-01), so the periods
    are read per parameter. A period is `Stundenwerte in MEZ (MD)`, the plain `Stundenwerte in MEZ` or `Stundenwerte in
    UTC`; only the first is returned (GH-2709). A file without the metadata, or a line that does not read, is no MEZ
    (MD).

    The periods are dates, and where an MD period meets another on one day (`Bis_Datum` of the one is `Von_Datum` of
    the other: 38 periods at 37 stations where it ends, 36 of them on 1991-11-01, and 3 where it begins) the clock
    changes inside that day, at no hour the metadata names (read 2026-10-16 in all 637 archives). Against NOAA ISD
    the change is after the stamp 00 of that day: at the stations with a reading on it the stamp 00 is MEZ in 18 of
    18 cases (it is the 23 UTC report of the day before), the stamps 01 to 03 are UTC in 11 of 11 readings at 10
    stations (Fichtelberg 01358 on 1991-05-02, Chemnitz, Leinefelde, Oschatz on 1991-11-01 among them), and 75 of
    the 88 later stamps of the day agree with UTC (Ummendorf 05158 is the one that agrees with MEZ). Treating the
    whole day as MEZ mislabels 21 to 23 stamps, treating it as UTC one. So the stamp 00 of a shared day belongs to
    the period that ends on it and the stamps 01 to 23 to the period that begins on it: an MD period that begins on
    a shared day starts at its 01 stamp, one that ends on it ends at its 00 stamp. Any other MD period runs from the
    first stamp of its first day to the last stamp of its last day.
    """
    files = zfs.glob("**/Metadaten_Parameter_*.txt")
    if not files:
        return {}
    rows: dict[str, list[tuple[dt.date, dt.date, bool]]] = {}
    for line in zfs.open(files[0]).read().decode("latin-1").splitlines()[1:]:
        parts = [part.strip() for part in line.split(";")]
        if len(parts) < 9 or not parts[0].isdigit():
            continue
        try:
            first = dt.date.fromisoformat(parts[1])
            # an open end is still running
            last = dt.date.fromisoformat(parts[2]) if parts[2] else dt.date.max
        except ValueError:
            log.warning(f"The period {line!r} of the metadata of {files[0]} does not read and is taken as UTC.")
            continue
        rows.setdefault(parts[4].lower(), []).append((first, last, parts[8] == MEZ_MD_INFO))
    spans = {parameter: _mez_md_stamps(periods) for parameter, periods in rows.items()}
    return {parameter: stamps for parameter, stamps in spans.items() if stamps}


def _mez_md_stamps(periods: list[tuple[dt.date, dt.date, bool]]) -> tuple[tuple[dt.datetime, dt.datetime], ...]:
    """Turn the periods (first day, last day, is MEZ (MD)) of one parameter into the first and last MEZ (MD) stamp."""
    stamps = []
    for first, last, is_md in periods:
        if not is_md:
            continue
        start = dt.datetime.combine(first, dt.time(0), tzinfo=dt.UTC)
        end = dt.datetime.combine(last, dt.time(23), tzinfo=dt.UTC)
        if any(not other_md and other_last == first for _, other_last, other_md in periods):
            start += dt.timedelta(hours=1)
        if any(not other_md and other_first == last for other_first, _, other_md in periods):
            end = dt.datetime.combine(last, dt.time(0), tzinfo=dt.UTC)
        if start <= end:
            stamps.append((start, end))
    return tuple(stamps)
