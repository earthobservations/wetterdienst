# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Download climate observations data from DWD server."""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass
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


@dataclass
class ProductFile(File):
    """The product file of an archive, with what the archive says of the time its stamps are in."""

    woz_spans: tuple[tuple[dt.date, dt.date], ...] = ()
    """The periods (first and last day, both included) of the file whose stamps are in true solar time (GH-2816)."""


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
