# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Read DWD XML Weather Forecast File of Type KML."""

# Source:
# https://github.com/jlewis91/dwdbulk/blob/master/dwdbulk/api/forecasts.py
from __future__ import annotations

import datetime as dt
import logging
import os
import time
from collections import OrderedDict
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Any
from zipfile import BadZipFile

import polars as pl
from aiohttp import ClientConnectorError
from fsspec.implementations.cached import WholeFileCacheFileSystem
from tqdm import tqdm

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.model.quality_flags import raw_column
from wetterdienst.util import network
from wetterdienst.util.archive import open_zip
from wetterdienst.util.io import read_in_chunks
from wetterdienst.util.logging import TqdmToLogger
from wetterdienst.util.network import DownloadRefusedError, File, NetworkFilesystemManager, _failed_file
from wetterdienst.util.xml import iterparse_xml

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator
    from typing import BinaryIO
    from xml.etree.ElementTree import Element

    from wetterdienst.settings import Settings
    from wetterdienst.util.network import HTTPFileSystem

log = logging.getLogger(__name__)

# how the file writes a value it does not have, in the list of values of an element
MISSING_VALUE = "-"

#: The most a run may unpack to. The KML of MOSMIX-L is 1.8 GB (an hour's run of MOSMIX-S 0.6 GB) and is
#: parsed from a stream, so this is about twice the largest and only bounds what a file may claim.
MAX_KML_BYTES = 4 * 1024**3


def _local_size(response: BinaryIO) -> int | None:
    """Give the size of a file held on disk, else None.

    What the caching filesystem opens is the cached copy, fetched whole by then: its size is on the disk and
    asking the server for it (an HTTP HEAD, even for a run the cache holds) kept a cached run from being
    served offline (GH-3003). A stream of an uncached filesystem has no file descriptor.
    """
    try:
        return os.fstat(response.fileno()).st_size
    except (AttributeError, OSError, ValueError):
        # `io.UnsupportedOperation` is an `OSError` and a `ValueError` both
        return None


def _failure_under_fsspec(error: Exception) -> Exception:
    """Give the failure of the request under an fsspec filesystem that raised ``error`` for it.

    The plain HTTP filesystem asks for the size of a file before it opens it and answers a request that failed, of
    whatever kind -- a refused connection, a reset, a timeout, a 5xx -- with a `FileNotFoundError` naming the URL,
    the failure as its ``__cause__``. So a missing file is the one without a cause, and for any other the cause is
    what happened.
    """
    if isinstance(error, FileNotFoundError) and isinstance(error.__cause__, Exception):
        return error.__cause__
    return error


@dataclass
class _ParsedRun:
    """What one parsed file holds for the stations asked: the head of the run, its steps and the elements by station."""

    metadata: dict[str, Any]
    timesteps: list[str]
    data: dict[str, dict[str, list[float | None]]]
    #: the steps at which some station of the file has a value, per element (lower case); None where the reader was not
    #: asked to collect them (`read(steps_of=...)`)
    given: dict[str, list[str]] | None = None


class KMLReader:
    """Read DWD XML Weather Forecast File of Type KML."""

    def __init__(self, station_ids: list[str], settings: Settings, *, keep_parsed: int = 1) -> None:
        """Initialize KMLReader.

        Args:
            station_ids: List of station IDs to read.
            settings: Settings object.
            keep_parsed: How many parsed files the reader holds at once, the files of one request: a request for
                several datasets reads one file per dataset at every station, and a reader that holds one parsed
                file parses the other's again at the next station (MOSMIX-S is 36 MB). The one held longest ago is
                dropped for a new one, so the memory is that of `keep_parsed` files' stations and never grows with
                the request.

        """
        self.station_ids = station_ids
        self.metadata = {}
        self.data = {}
        self.given: dict[str, list[str]] | None = None
        self.timesteps = []
        self.nsmap = None
        self.iter_elems = None
        # `metadata`, `timesteps` and `data` are those of the file `read` was last asked for; every file parsed
        # is kept by its URL, up to `keep_parsed` of them, least recently read dropped first
        self._keep_parsed = max(keep_parsed, 1)
        self._parsed: OrderedDict[str, _ParsedRun] = OrderedDict()
        # keep the zip buffer/handle alive while lxml streams from it.
        self._zip_refs = None

        # how long a forecast may be held is a property of the URL, not of the reader. A run named
        # by its timestamp is that run for good and may be kept; a `LATEST` alias is a name whose
        # content DWD replaces, so it may only be held briefly. Holding everything briefly is what
        # this did, and for `MOSMIX_S` -- 36 MB, published hourly -- that meant re-downloading it
        # up to twelve times an hour for a file that had not changed (GH-1945).
        #
        # What it costs instead: a distinct URL per run, so the cache gains a blob an hour where it
        # reused one -- 36 MB an hour, 871 MB a day for MOSMIX-S, against 10.4 GB a day over the
        # wire before. Nothing evicts a blob once its expiry has passed, which is GH-1955 and is
        # true of every provider here: the observation zips, the radar files and the rest all
        # accumulate per URL already. Reusing one blob was mosmix's anomaly, and it came from
        # resolving to a name whose content changed under it.
        #
        # `dwd/dmo` reads through this class too, so its downloads move with mosmix's. Its names
        # carry the same kind of immutable run stamp (`ptp_gdmog_01001_078_1_230000.kmz`) and none
        # of them says `LATEST`, so every DMO file takes the long hold -- correct, and worth saying
        # because DMO keeps only a handful of runs, so a blob can outlive the file upstream
        self._filesystems = {
            ttl: NetworkFilesystemManager.get(
                cache_dir=settings.cache_dir,
                cache_expiry=ttl,
                client_kwargs=settings.fsspec_client_kwargs,
                cache_disable=settings.cache_disable,
                use_certifi=settings.use_certifi,
            )
            for ttl in (CacheExpiry.FIVE_MINUTES, CacheExpiry.TWELVE_HOURS)
        }
        # no `self.dwdfs`: which filesystem answers is per-URL now, and an attribute pinned to one
        # of them is a trap for whatever reaches for it next

    def _filesystem_for(self, url: str) -> HTTPFileSystem | WholeFileCacheFileSystem:
        """Pick how long this URL may be held: briefly for a mutable alias, long for a named run."""
        mutable = "LATEST" in url.rsplit("/", 1)[-1].upper()
        return self._filesystems[CacheExpiry.FIVE_MINUTES if mutable else CacheExpiry.TWELVE_HOURS]

    def download(self, url: str) -> BytesIO:
        """Download kml file as bytes.

        https://stackoverflow.com/questions/37573483/progress-bar-while-download-file-over-http-with-requests

        Raises:
            NoInternetError: If no connection could be made, naming the URL (GH-2640).
            DownloadError: If the server answered badly: a TLS check that fails, a connection reset, a timeout, a
                body cut short or an HTTP error status, a missing run among them, naming the URL with the failure
                as its ``__cause__``, as `File.raise_if_exception` raises it for a download (GH-3120).

        """
        dwdfs = self._filesystem_for(url)
        failed: File | None = None
        buffer = BytesIO()
        try:
            buffer = self._read(dwdfs, url)
        except Exception as e:
            # the place this reader meets the network, through fsspec and not `download_file`: told by the same
            # function, so that a failure is the same error whichever of them met it (GH-2640, GH-3120)
            failed = _failed_file(url, _failure_under_fsspec(e))
            if failed is None:
                raise
        # raised outside the `except`, so that the aiohttp error, which holds a proxy's key, is no `__context__`
        if failed is not None:
            failed.raise_if_exception()
        return buffer

    @staticmethod
    def _read(dwdfs: HTTPFileSystem | WholeFileCacheFileSystem, url: str) -> BytesIO:
        """Open a run and read it whole, showing how far it is."""
        response = dwdfs.open(url, block_size=0)
        # the size only sizes the progress bar
        total = _local_size(response)
        if total is None:
            # a stream that is not held on disk (the cache is disabled) knows its size from a HEAD only
            try:
                total = dwdfs.size(url)
            except ClientConnectorError:
                total = None

        buffer = BytesIO()
        # the cache fetches under the ceilings of the network module, a stream that is not held on disk does not
        deadline = time.monotonic() + network.MAX_DOWNLOAD_SECONDS

        tqdm_out = TqdmToLogger(log, level=logging.INFO)

        with tqdm(
            desc=url,
            total=total,
            unit="iB",
            unit_scale=True,
            unit_divisor=1024,
            file=tqdm_out,
        ) as bar:
            for data in read_in_chunks(response, chunk_size=1024):
                size = buffer.write(data)
                bar.update(size)
                if buffer.tell() > network.MAX_DOWNLOAD_BYTES:
                    msg = "the file is larger than a download is held to"
                    raise DownloadRefusedError(msg)
                if time.monotonic() > deadline:
                    msg = "the file took longer than a download is held to"
                    raise DownloadRefusedError(msg)

        return buffer

    def fetch(self, url: str) -> BinaryIO:
        """Open the zipped mosmix KML as a streaming handle (decompressed lazily, not all at once)."""
        try:
            return self._fetch(url)
        except BadZipFile:
            # a run held under an immutable URL for twelve hours, and the body is not a zip. fsspec
            # writes its cache metadata before the copy finishes -- `_make_local_details` records
            # the entry, `get_file` fills it afterwards -- so a download interrupted mid-copy
            # leaves a truncated blob that `_check_file` then accepts for the life of the entry.
            # `_LockedWholeFileCacheFileSystem._open` now records the entry after the copy
            # (GH-2467), but a blob an earlier version cached that way is still read back, and a
            # body cut short with no `Content-Length` to tell is recorded as if whole.
            # Held five minutes that righted itself; held twelve hours, and with `LATEST` now
            # resolving to the same immutable URL rather than to an alias, it would not.
            #
            # So the entry is dropped and the run asked for once more. A body that is still not a
            # zip after that is upstream's, and raises
            filesystem = self._filesystem_for(url)
            if not isinstance(filesystem, WholeFileCacheFileSystem):
                # nothing held, so nothing to drop and nothing a second request would answer
                # differently -- and for MOSMIX-S that second request is another 36 MB
                raise
            log.warning(f"Cached MOSMIX run {url} is not a zip; dropping it from the cache and asking again")
            filesystem.pop_from_cache(url)
            return self._fetch(url)

    def _fetch(self, url: str) -> BinaryIO:
        """Download and open one run, whatever the cache currently holds for it."""
        buffer = self.download(url)
        zfs = open_zip(File(url=url, content=buffer, status=200), limit=MAX_KML_BYTES)
        handle = zfs.open(zfs.glob("*")[0])
        # keep the compressed buffer and zip filesystem alive so the handle stays readable while
        # lxml pulls from it incrementally
        self._zip_refs = (buffer, zfs, handle)
        return handle

    def read(self, url: str, steps_of: Iterable[str] | None = None) -> None:
        """Download and read DWD XML Weather Forecast File of Type KML.

        Args:
            url: The file.
            steps_of: The elements (any casing) to note the steps of at which some station of the file has a value
                (`given_timesteps`), of every station of the file and not only of the ones asked for. The file writes
                `-` for a step a product does not give just as for a value that is missing, and a step that no station
                has a value at is the former. None, which `dwd/dmo` shares this class with, notes none. Only these
                elements are looked at for a station not asked for, and not at all once every step of every one of
                them has been seen (an element the file does not have is never complete).

        """
        # Skip if this URL's forecasts are already parsed: made the current ones again, and the newest of those held
        run = self._parsed.get(url)
        if run is not None:
            self._parsed.move_to_end(url)
            self.metadata, self.timesteps, self.data, self.given = run.metadata, run.timesteps, run.data, run.given
            return

        log.info(f"Downloading KMZ file {Path(url).name}")
        handle = self.fetch(url)
        log.info("Parsing KML data")

        # Stream straight from the (incrementally decompressed) zip handle. Using end-only events
        # plus sibling pruning in iter_items keeps peak memory bounded by the compressed file size
        # rather than the ~600MB of decompressed KML.
        self.iter_elems = iterparse_xml(handle)
        prod_items = {
            "issuer": "Issuer",
            "product_id": "ProductID",
            "generating_process": "GeneratingProcess",
            "issue_time": "IssueTime",
        }
        nsmap = None
        # Get Basic Metadata
        prod_definition = None
        prod_definition_tag = None
        for _, element in self.iter_elems:
            # namespaces are declared on the root and inherited, so any element carries the full map
            if nsmap is None:
                nsmap = element.nsmap
                prod_definition_tag = f"{{{nsmap['dwd']}}}ProductDefinition"
            if element.tag == prod_definition_tag:
                prod_definition = element
                # stop processing after head; leave forecast placemarks for iteration
                break
        if prod_definition is None or nsmap is None:
            msg = "Could not find ProductDefinition in KML file"
            raise ValueError(msg)
        self.metadata = {k: prod_definition.find(f"{{{nsmap['dwd']}}}{v}").text for k, v in prod_items.items()}
        self.metadata["issue_time"] = dt.datetime.fromisoformat(self.metadata["issue_time"])
        # Get time steps.
        timesteps = prod_definition.findall(
            "dwd:ForecastTimeSteps",
            nsmap,
        )[0]
        self.timesteps = [i.text for i in list(timesteps)]
        # save namespace map for later iteration
        self.nsmap = nsmap
        # release the head subtree before iterating placemarks
        prod_definition.clear()
        self._store_station_forecasts(None if steps_of is None else frozenset(e.lower() for e in steps_of))
        self._parsed[url] = _ParsedRun(self.metadata, self.timesteps, self.data, self.given)
        while len(self._parsed) > self._keep_parsed:
            self._parsed.popitem(last=False)

    def iter_items(self) -> Iterator[Element]:
        """Iterate over station forecasts, pruning parsed elements to bound memory."""
        if self.iter_elems is None or self.nsmap is None:
            return
        placemark_tag = f"{{{self.nsmap['kml']}}}Placemark"
        for _, element in self.iter_elems:
            if element.tag != placemark_tag:
                continue
            yield element
            # release the finished placemark and every preceding sibling still held under the root,
            # so the tree never accumulates more than one placemark at a time
            element.clear()
            while element.getprevious() is not None:
                del element.getparent()[0]

    def get_metadata(self) -> pl.DataFrame:
        """Get metadata as DataFrame."""
        return pl.DataFrame([self.metadata], orient="row")

    def _store_station_forecasts(self, steps_of: frozenset[str] | None = None) -> None:
        """Store station forecasts in self.data.

        For mosmix we want the reader to only go once through the file and store
        all data (meaning all queried stations) in memory. This is to avoid
        multiple downloads/parses of the same file when users want to access
        data of multiple stations.

        Returns:
            None

        """
        self.data = {}
        self.given = None
        nsmap = self.nsmap
        if nsmap is None:
            return
        # per element asked for, the steps no station has had a value at so far: an element given at every step is done
        # at the first station that has it, and one given at some steps only (MOSMIX-L's `TX`, MOSMIX-SNOW's `SnCv`)
        # has its stations' strings split until the file ends
        unseen = None if steps_of is None else {element: set(range(len(self.timesteps))) for element in steps_of}
        for station_forecast in self.iter_items():
            station_id = station_forecast.find("kml:name", nsmap)
            if station_id is None:
                continue
            station_id = station_id.text
            requested = station_id in self.station_ids
            if not requested and not (unseen and any(unseen.values())):
                continue
            if requested:
                self.data[station_id] = {}
            for element, measurement_string in self._elements_of(station_forecast, nsmap):
                tokens = self._note_steps(unseen, element, measurement_string) if unseen else None
                if requested:
                    # str.split() already collapses the whitespace-separated value list
                    tokens = tokens if tokens is not None else measurement_string.split()
                    self.data[station_id][element] = [None if i == MISSING_VALUE else float(i) for i in tokens]
            station_forecast.clear()
        if unseen is not None:
            self.given = {
                element: [step for i, step in enumerate(self.timesteps) if i not in pending]
                for element, pending in unseen.items()
            }

    def _note_steps(self, unseen: dict[str, set[int]], element: str, measurement_string: str) -> list[str] | None:
        """Strike the steps a station has a value of off those of the element that no station has had one at yet.

        Gives the split values where they were read, None where every step of the element was seen already.
        """
        pending = unseen.get(element)
        if not pending:
            return None
        tokens = measurement_string.split()
        pending.difference_update(i for i in tuple(pending) if i < len(tokens) and tokens[i] != MISSING_VALUE)
        return tokens

    @staticmethod
    def _elements_of(station_forecast: Element, nsmap: dict[str, str]) -> Iterator[tuple[str, str]]:
        """Give the elements a station's placemark holds, by lower-case name, with the string of its values."""
        for measurement_item in station_forecast.findall("kml:ExtendedData/dwd:Forecast", nsmap):
            measurement_parameter = measurement_item.get(f"{{{nsmap['dwd']}}}elementName")
            if measurement_parameter is None:
                continue
            measurement_string = next(iter(measurement_item)).text
            if measurement_string is None:
                continue
            yield measurement_parameter.lower(), measurement_string

    def given_timesteps(self, url: str, element: str) -> list[str] | None:
        """Give the steps of a parsed file at which some station of it has a value of the element.

        An element no station has a value of is given at no step (an empty list). None where the file is not held
        (never read, or dropped for a newer one) or the reader was not asked to collect the steps.
        """
        run = self._parsed.get(url)
        if run is None or run.given is None:
            return None
        return run.given.get(element.lower(), [])

    def get_station_forecast(self, station_id: str) -> pl.DataFrame:
        """Get forecasts as DataFrame."""
        station_forecast_values = self.data.get(station_id)
        if not station_forecast_values:
            return pl.DataFrame()
        data = {"timestamp": self.timesteps} | station_forecast_values
        df = pl.DataFrame(data)
        # a value the file writes as "-" was stored as None, so the text beside each None is that "-". It is kept
        # beside its column for `quality_flags` (GH-2759); the stored lists stay floats, as MOSMIX-S holds
        # tens of millions of them for all stations
        return df.with_columns(
            pl.when(pl.col(parameter).is_null()).then(pl.lit(MISSING_VALUE)).alias(raw_column(parameter))
            for parameter in station_forecast_values
        )
