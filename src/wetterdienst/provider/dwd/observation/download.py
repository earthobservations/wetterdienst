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

from wetterdienst.exceptions import ProductFileNotFoundError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.dwd.observation.fileindex import forget_listing_of_missing_file
from wetterdienst.provider.dwd.observation.metadata import DwdObservationMetadata
from wetterdienst.provider.dwd.observation.mez_blocks import mez_block_spans
from wetterdienst.util.archive import open_zip
from wetterdienst.util.network import File, download_files
from wetterdienst.util.response_warnings import SkipCause, note_skipped_download

if TYPE_CHECKING:
    import polars as pl
    from fsspec.implementations.zip import ZipFileSystem

    from wetterdienst.model.metadata import DatasetModel
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

#: DWD's note on a period of a station in `Metadaten_Parameter_*.txt` (column `Zusatz-Info`) whose hourly stamps
#: are in true local solar time ("Wahre Ortszeit"), not UTC
WOZ_INFO = "Stundenwerte in WOZ"
#: the same note for the periods of the eMD archive (the Meteorologischer Dienst der DDR) whose hourly stamps are
#: MEZ, the fixed UTC+1 without daylight saving time (GH-2709). The plain `Stundenwerte in MEZ` is another note
MEZ_MD_INFO = "Stundenwerte in MEZ (MD)"
#: the plain note, which does not tell whether the values are MEZ: most of its stations are UTC in the values
MEZ_INFO = "Stundenwerte in MEZ"
#: the start of the `Datenquelle` of the hourly soil temperature periods that come from the eMD archive, whose
#: stamps are MEZ (GH-3029). Their `Zusatz-Info` is only `Stundenwerte`, the zone is in this text ("3,4 Terminwerte:
#: 01,07,13,19 MEZ und synoptische Haupttermine:01,04,07,10,13,16,19,22 MEZ")
MEZ_EMD_SOIL_SOURCE = "Daten der Erdbodentemperatur aus dem Archiv des eMD"


#: The stamps of the hourly air temperature that are MEZ though no label says it, by station and parameter (GH-3029):
#: the stamps (first and last, both included, as written) that equal the report of the hour before in NOAA ISD and
#: correlate best at one hour before with the mean of the neighbouring stations that are UTC. The label of the stations
#: with a plain `Stundenwerte in MEZ` period does not tell: at most of them the values are UTC (the scan of all of them
#: is in docs/data/time_reference.md). Only spans whose bounds were read hour by hour (the end of Nürnberg's by the
#: pattern of the others) and that are as good as the first are here (Bremen, at 88.2 %, by the maintainer's
#: decision); the others, which change the clock inside the period or are only partly identical to ISD
#: (Regensburg-Oberhub 04104, Stötten 04887, Lübeck-Blankensee 03086, ...), are returned as written.
#:
#: Where the shift moves the first stamp of a block onto a stamp the file has (the stamp 00 of its day; for Diepholz
#: 1995-01-31 23), the moved row is kept: Nürnberg 1986-01-01 01 is -6.6 against -7.0 at the stamp 00, which equals no
#: report of ISD; elsewhere the row that was not moved is kept (`DwdObservationValues._tidy_up_df`).
#:
#: Diepholz 00963, label MEZ from 1994-04-01 to 1996-06-01: UTC up to the stamp 1995-01-31 23 (24 of 24 hours equal to
#: ISD at lag 0 on 1995-01-31), MEZ from the stamp 1995-02-01 00 (24 of 24 at lag -1) to the stamp 1996-05-31 23 (24 of
#: 24), UTC again from 1996-06-01 00 (22 of 23 at lag 0); 11,374 of 11,397 hours of the MEZ span equal ISD at lag -1
#: against 1,075 at lag 0, 729 of 735 hours before it at lag 0 against 68 at lag -1. Relative humidity has the same
#: span: against the neighbours lag -1 beats lag 0 in 14 of the 16 months, and lag 0 beats it before and after.
#:
#: Four more, each a block of whole UTC days of the SYNOP reports stamped 01 to 24 (the 24 written as 00 of the next
#: day), the stamps next to it at lag 0 or equal to no ISD report:
#:
#: - Nürnberg 03668, label MEZ 1951-01-01 to 1995-08-31: from the stamp 1986-01-01 01 to the stamp 1988-11-01 00,
#:   24,212 of 24,435 hours equal ISD 107630 at lag -1 (99.1 %), 1,892 of 24,434 at lag 0 (7.7 %); lag 0 from the
#:   stamp 1988-11-01 01 (every one of the 120 days to 1989-02-28 told apart); ISD has no report of 23 UTC on
#:   1988-10-31, so the last stamp is the 24 of the day by the pattern of the other blocks. The months before 1986
#:   are not identical to ISD at any lag (analog values) and are returned as written. Relative humidity is within 3 %
#:   of ISD's at lag -1 in 98.9 % of the hours (lag 0: 56.9 %).
#: - Bremen 00691, label MEZ 1949-01-01 to 1991-10-31: from the stamp 1990-11-01 01 to the stamp 1991-03-01 00,
#:   2,491 of 2,825 hours equal ISD 102240 at lag -1 (88.2 %), 296 at lag 0 (10.5 %); mean absolute difference
#:   0.028 K against 0.447 K, 93.5 % within 0.15 K; lag 0 in 1985-06 to 1990-10 and from the stamp 1991-03-01 01.
#:   Relative humidity within 3 % of ISD's at lag -1 in 98.7 % (lag 0: 71.9 %).
#: - Frankfurt/Main 01420, label MEZ 1981-01-01 to 1993-10-31: from the stamp 1990-05-01 01 to the stamp 1990-06-01 00,
#:   734 of 743 hours equal ISD 106370 at lag -1 (98.8 %), 21 at lag 0 (2.8 %); lag 0 in 1990-02 to 04 and 06 to 08.
#: - Trier-Petrisberg 05100, label MEZ 1941-01-01 to 1999-12-31: from the stamp 1989-08-01 01 to the stamp 1989-09-01
#:   00, 715 of 722 hours equal ISD 106090 at lag -1 (99.0 %), 25 at lag 0 (3.5 %); lag 0 in 1989-05 to 07 and 09 to 10.
#:
#: Against the mean of the nearest stations that are UTC the days vote for lag -1 in the span and for lag 0 around it
#: (Nürnberg 1986 and 1987: 529 of 730 days at lag -1; Frankfurt 1990-05: 21 of 31 against 10 at lag 0, where 57 of 89
#: days before it are at lag 0; Trier 1989-08: 28 of 31; Bremen 1990-11 to 1991-02: 77 of 120 days against 30, where
#: 180 of 304 days of 1990-01 to 10 are at lag 0). Relative humidity has the same span (Frankfurt 98.4 %, Trier
#: 96.3 % within 3 % of ISD's at lag -1).
#:
#: Where the values are analog and equal no report of ISD at any lag, a second method decides next to the fit of the
#: offset to ISD's reports (GH-3776): the blocks of `mez_blocks.csv`, the months that both methods find in MEZ under
#: every variant of the constants of the scan, are shifted like these. A block is whole UTC days, from the stamp 01 of
#: its first day to the stamp 00 after its last (`mez_blocks.py` has the method and the columns of the table). They
#: are flagged `zone:mez`, and those of the 1973-01 to 1975-12 batch `zone:mez-1973-75`: shifted by the 1 h of the
#: clock, with the lag of the analog recorder (about 0.4 h at 8 of its 13 stations) left in the values. The same rule
#: settles a stamp the shift moves onto one that is there: the row that was moved is kept. The blocks of the table lie
#: outside the five above (a test holds it to that).
_MEZ_COMPARED_WITH_ISD: dict[str, tuple[dt.datetime, dt.datetime]] = {
    "00963": (dt.datetime(1995, 2, 1, 0, tzinfo=dt.UTC), dt.datetime(1996, 5, 31, 23, tzinfo=dt.UTC)),
    "03668": (dt.datetime(1986, 1, 1, 1, tzinfo=dt.UTC), dt.datetime(1988, 11, 1, 0, tzinfo=dt.UTC)),
    "01420": (dt.datetime(1990, 5, 1, 1, tzinfo=dt.UTC), dt.datetime(1990, 6, 1, 0, tzinfo=dt.UTC)),
    "05100": (dt.datetime(1989, 8, 1, 1, tzinfo=dt.UTC), dt.datetime(1989, 9, 1, 0, tzinfo=dt.UTC)),
    "00691": (dt.datetime(1990, 11, 1, 1, tzinfo=dt.UTC), dt.datetime(1991, 3, 1, 0, tzinfo=dt.UTC)),
}


def _by_comparison() -> dict[str, dict[str, tuple[tuple[dt.datetime, dt.datetime], ...]]]:
    spans: dict[str, tuple[tuple[dt.datetime, dt.datetime], ...]] = {
        station: (span,) for station, span in _MEZ_COMPARED_WITH_ISD.items()
    }
    for station, blocks in mez_block_spans().items():
        spans[station] = (*spans.get(station, ()), *blocks)
    return {station: dict.fromkeys(("tt_tu", "rf_tu"), stamps) for station, stamps in spans.items()}


MEZ_BY_COMPARISON: dict[str, dict[str, tuple[tuple[dt.datetime, dt.datetime], ...]]] = _by_comparison()

#: the stamps of the 1973-01 to 1975-12 batch, by station: the rows of these are flagged `zone:mez-1973-75` (GH-3776)
MEZ_BATCH_SPANS: dict[str, tuple[tuple[dt.datetime, dt.datetime], ...]] = mez_block_spans(batch=True)

#: the datasets whose stamps are MEZ in some periods: hourly air temperature (GH-2709), hourly soil temperature
#: (GH-3029)
MEZ_DATASETS = (DwdObservationMetadata.hourly.temperature_air, DwdObservationMetadata.hourly.temperature_soil)


@dataclass
class ProductFile(File):
    """The product file of an archive, with what the archive says of the time its stamps are in."""

    woz_spans: tuple[tuple[dt.date, dt.date], ...] = ()
    """The periods (first and last day, both included) of the file whose stamps are in true solar time (GH-2816)."""
    mez_md_spans: dict[str, tuple[tuple[dt.datetime, dt.datetime], ...]] = field(default_factory=dict)
    """Per parameter (`tt_tu`, `rf_tu`, `v_te005`), the stamps (first and last, both included, as written) that are MEZ.

    The periods the archive calls MEZ (MD) (air temperature, GH-2709) or takes from the eMD archive (soil temperature,
    GH-3029), and the stamps of `MEZ_BY_COMPARISON`.
    """


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
    # the retries -- is an outage, which dropped would read as a station without data (GH-2430). The files are the
    # ones the file index listed, so a 404 is one withdrawn (or renamed) since, which leaves the station's values
    # missing: the provider lets it go, and says so
    for file in files:
        if file.status != 404:
            file.raise_if_exception()
        else:
            note_skipped_download(SkipCause.WITHDRAWN)
            # the listing is what named the file: drop it, so that the next request lists the directory again and
            # finds the file where it is now, instead of this one until the listing expires (GH-3892)
            forget_listing_of_missing_file(file.url, settings, CacheExpiry.TWELVE_HOURS)
            log.warning(
                f"The file {file.url} that the file index lists is not on the server (404): its values are missing"
            )
    files = [file for file in files if isinstance(file.content, BytesIO)]
    # unpack the files
    return [_unpack_climate_observations_data(file, dataset) for file in files]


def _unpack_climate_observations_data(file: File, dataset: DatasetModel | None = None) -> File:
    try:
        zfs = open_zip(file)
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
        last_modified=file.last_modified,
        woz_spans=_read_woz_spans(zfs) if dataset == DwdObservationMetadata.hourly.sun else (),
        mez_md_spans=_read_mez_md_spans(zfs, dataset) if dataset in MEZ_DATASETS else {},
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


def _read_mez_md_spans(
    zfs: ZipFileSystem, dataset: DatasetModel | None
) -> dict[str, tuple[tuple[dt.datetime, dt.datetime], ...]]:
    """Read, per parameter, the stamps of a station's hourly air or soil temperature that are MEZ from the metadata.

    `Metadaten_Parameter_*.txt` has a table of periods per parameter, and the tables of `TT_TU` and `RF_TU` differ in
    42 of the 637 stations (Aue 00222: `TT_TU` is MEZ (MD) from 1982-01-01, `RF_TU` from 1991-01-01), so the periods
    are read per parameter. For the air temperature a period is `Stundenwerte in MEZ (MD)`, the plain `Stundenwerte in
    MEZ` or `Stundenwerte in UTC`; only the first is MEZ (GH-2709), and the stamps `MEZ_BY_COMPARISON` names inside a
    plain MEZ period (GH-3029). For the soil temperature a period is MEZ where its source is the archive of the eMD
    (74 stations, 1951 to 1991: stamps 01, 04, ..., 22 only, GH-3029). A file without the metadata, or a line that
    does not read, is no MEZ.

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
    plain_mez: dict[str, list[tuple[dt.date, dt.date]]] = {}
    stations: set[str] = set()
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
        parameter = parts[4].lower()
        stations.add(f"{int(parts[0]):05d}")
        if dataset == DwdObservationMetadata.hourly.temperature_soil:
            is_mez = parts[7].startswith(MEZ_EMD_SOIL_SOURCE)
        else:
            is_mez = parts[8] == MEZ_MD_INFO
            if parts[8] == MEZ_INFO:
                plain_mez.setdefault(parameter, []).append((first, last))
        rows.setdefault(parameter, []).append((first, last, is_mez))
    spans = {parameter: _mez_md_stamps(periods) for parameter, periods in rows.items()}
    if dataset == DwdObservationMetadata.hourly.temperature_air:
        for station in stations:
            for parameter, compared in MEZ_BY_COMPARISON.get(station, {}).items():
                spans[parameter] = (
                    *spans.get(parameter, ()),
                    *_inside_plain_mez(compared, plain_mez.get(parameter, [])),
                )
    return {parameter: stamps for parameter, stamps in spans.items() if stamps}


def _inside_plain_mez(
    stamps: tuple[tuple[dt.datetime, dt.datetime], ...], periods: list[tuple[dt.date, dt.date]]
) -> list[tuple[dt.datetime, dt.datetime]]:
    """Cut the stamps that were compared to the periods the metadata still calls plain `Stundenwerte in MEZ`.

    A comparison was made on the archive as it is. If DWD turns a period into UTC, with the stamps or with the label,
    the label is no longer the one the comparison was made under and the stamps are returned as written.
    """
    inside = []
    for first, last in stamps:
        for period_first, period_last in periods:
            start = max(first, dt.datetime.combine(period_first, dt.time(0), tzinfo=dt.UTC))
            end = min(last, dt.datetime.combine(period_last, dt.time(23), tzinfo=dt.UTC))
            if start <= end:
                inside.append((start, end))
    return inside


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
