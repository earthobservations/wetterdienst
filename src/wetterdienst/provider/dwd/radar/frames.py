# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The frames of DWD's RV composite, which the radar tool of the REST API serves (GH-3788).

A frame is the radar's precipitation of five minutes, drawn as an image (`rv.py`): the **analysis** of every run of the
last hours (lead time 0, one frame every 5 minutes) and the **forecast** of the newest run (lead times 5 to 120 minutes,
DWD's extrapolation of the recent movement of the rain, not a weather model).

The files are read for what a frame needs and no more:

- the analysis of a run is the first member of its `.tar`, so it is read by one range request of 400 KB (the file is
  about 320 KB; a second request follows for one that is longer) and not by the whole file (7.7 MB, holding the 24
  forecasts as well): a loop of two hours costs about 10 MB and not 190 MB;
- the forecasts of a run are in the one `.tar` that is read whole, once, and held while its frames are drawn. They are
  served for the newest `FORECAST_RUNS` runs only, and `MAX_TARS` (one more than that) are held (31 MB), so a run's tar
  is read once while its forecast is wanted, however the frames of the runs are asked for.

A drawn frame is held in this process by its run and lead time, so that one decode serves every reader, and the
oldest are dropped. A frame of a run never changes, so the cache needs no expiry: what changes is which run is the
newest, which the list of runs (held for a minute) says. At most two frames are drawn at once, and a frame two readers
ask for at the same time is drawn once.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
import tarfile
import threading
import time as clock
from collections import OrderedDict
from dataclasses import dataclass
from io import BytesIO
from typing import TYPE_CHECKING, cast

from wetterdienst.exceptions import DownloadError, NotFoundError, ProviderRateLimitError, RequestError
from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.provider.dwd.radar.rv import (
    FORECAST_MINUTES,
    STEP_MINUTES,
    ImageFrame,
    RadarFormatError,
    draw,
    image_frame,
    read_field,
)
from wetterdienst.util.network import (
    NetworkFilesystemManager,
    _failed_file,
    _worth_retrying,
    download_file,
    list_remote_files_fsspec,
)
from wetterdienst.util.response_warnings import warn_response

if TYPE_CHECKING:
    from wetterdienst.settings import Settings

log = logging.getLogger(__name__)

RV_URL = "https://opendata.dwd.de/weather/radar/composite/rv/"

#: the name of the file of a run, `composite_rv_20261119_2110.tar` (the `LATEST` alias has no time, and is no run)
_RUN_FILE = re.compile(r"composite_rv_(\d{8})_(\d{4})\.tar$")

#: how long the list of runs is held. DWD adds a run every 5 minutes, 3 to 5 minutes after its time
RUNS_TTL = 60.0
#: the frames held, which are about 35 KB each: all the runs of a loop and the forecast of the newest, a few times over
MAX_FRAMES = 400
#: the forecast is served for the newest runs of the listing only: a run holds its forecast in one tar of 7.7 MB,
#: which is read whole, so the runs of the two days DWD keeps are not each a download a request may ask for
FORECAST_RUNS = 3
#: the `.tar` files held whole (7.7 MB each): the runs whose forecast is served and the one that is next, so that
#: readers of the forecasts of all of them, frame by frame, never push out the tar of one that is read next
MAX_TARS = FORECAST_RUNS + 1
#: the most the first file of a tar may be: it is 300 to 330 KB
MAX_MEMBER_BYTES = 8 * 1024**2
#: the most a `.tar` of a run may be; it is 7.7 MB
MAX_TAR_BYTES = 64 * 1024**2
#: the frames drawn at the same time, which holds the memory of the decoding (about 40 MB each) to a bound
MAX_DECODES = 2
#: what is asked for first of a `.tar`: its first member's header (512 bytes) and the analysis, which is 300 to 330 KB
FIRST_READ_BYTES = 400_000
#: the age of the list of runs after which a time or a run later than its newest is looked for in a new one
NEWER_THAN_LISTED_AFTER = 10.0
#: a run whose newest is older than this is told to be stale: DWD publishes one every 5 minutes
STALE_AFTER = dt.timedelta(minutes=20)
#: the code of the warning that the newest run is old
RADAR_STALE = "radar-stale"

_TAR_BLOCK = 512

#: what wetterdienst did to the composite, which the `processing_note` of an answer says after the note every answer
#: has: the sums became rates and classes, and the grid was warped
RADAR_FRAMES_NOTE = (
    "Each frame is DWD's RV composite, the precipitation of 5 minutes, converted to a rate in mm/h and sorted into the "
    "classes of the legend, and warped from DWD's polar stereographic grid of 1 km cells to a Web Mercator image whose "
    "pixels are 1 km, each taking the cell it lies in: a pixel is a class and no reading, and the rain that falls "
    "under the first class and the places the composite has no data for are alike transparent. A frame after the "
    "newest run is DWD's forecast, an extrapolation of the recent movement of the rain and not an observation."
)
#: what the note says of the image of a frame
RADAR_IMAGE_NOTE = "The image is drawn from the composite's precipitation field."


class RadarFrameNotFoundError(NotFoundError):
    """Raised when DWD holds no frame at the time asked for: a run that is gone (it keeps about two days) or missing."""


@dataclass(frozen=True)
class RadarFrame:
    """A frame of the loop: the run it is read from, the time it is valid at and how far that is from the run."""

    run: dt.datetime
    time: dt.datetime
    lead_minutes: int

    @property
    def kind(self) -> str:
        """Tell the radar's analysis (`observation`) from DWD's `forecast`."""
        return "observation" if self.lead_minutes == 0 else "forecast"


@dataclass(frozen=True)
class RadarFrameList:
    """The frames there are: the newest run, the frames oldest first and where their image lies."""

    run: dt.datetime
    frames: tuple[RadarFrame, ...]
    image: ImageFrame


@dataclass(frozen=True)
class RadarImage:
    """A frame drawn."""

    png: bytes
    frame: RadarFrame
    image: ImageFrame


def format_instant(value: dt.datetime) -> str:
    """Write a time as the frames name it: UTC to the second with a `Z`, which a query takes without escaping."""
    return value.astimezone(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_instant(text: str, *, name: str = "time") -> dt.datetime:
    """Read the time of a request, ISO 8601 (UTC where it has no offset), as a time in UTC.

    Raises:
        RequestError: The text is no ISO 8601 time, or is out of what a time holds.

    """
    try:
        parsed = dt.datetime.fromisoformat(text.strip())
    except ValueError as e:
        msg = f"{name} {text!r} is not an ISO 8601 time: {e}"
        raise RequestError(msg) from e
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.UTC)
    try:
        return parsed.astimezone(dt.UTC)
    except OverflowError as e:
        msg = f"{name} {text!r} is out of range"
        raise RequestError(msg) from e


def run_url(run: dt.datetime) -> str:
    """Give the address of the `.tar` of a run."""
    return f"{RV_URL}composite_rv_{run:%Y%m%d_%H%M}.tar"


def member_name(run: dt.datetime, lead_minutes: int) -> str:
    """Give the name of the file of a lead time in the `.tar` of a run."""
    return f"composite_rv_{run:%Y%m%d_%H%M}_{lead_minutes:03d}-hd5"


class _Frames:
    """What the readers share: the list of runs, the frames drawn, the `.tar` files in hand and the locks."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.runs: tuple[float, list[dt.datetime]] | None = None
        #: when the list was last asked for again for a run that might be unlisted, whether that succeeded or not
        self.relisted_at: float | None = None
        self.frames: OrderedDict[tuple[dt.datetime, int], bytes] = OrderedDict()
        self.tars: OrderedDict[dt.datetime, bytes] = OrderedDict()
        # a lock for each of a few hundred keys is a lot of locks that nothing frees: sixteen of each kind, which a key
        # picks by its hash, and two keys that pick the same wait for each other, which costs no more than a decode. The
        # kinds are separate so that a thread holding one of a frame's takes one of a tar's without meeting itself: the
        # order is always list of runs (alone), then a frame, then a tar, and a lock is never taken inside its own kind
        self.frame_stripes = tuple(threading.Lock() for _ in range(16))
        self.tar_stripes = tuple(threading.Lock() for _ in range(16))
        self.runs_lock = threading.Lock()
        self.decodes = threading.BoundedSemaphore(MAX_DECODES)

    def frame_stripe(self, key: object) -> threading.Lock:
        return self.frame_stripes[hash(key) % len(self.frame_stripes)]

    def tar_stripe(self, key: object) -> threading.Lock:
        return self.tar_stripes[hash(key) % len(self.tar_stripes)]


_SHARED = _Frames()


def forget_everything() -> None:
    """Empty what the process holds of the frames: for tests, which each start from nothing."""
    with _SHARED.lock:
        _SHARED.runs = None
        _SHARED.relisted_at = None
        _SHARED.frames.clear()
        _SHARED.tars.clear()


class DwdRadarFrames:
    """Read the frames of the RV composite as images, the list of them and each one (see the module)."""

    def __init__(self, settings: Settings) -> None:
        """Keep the settings the network is reached by."""
        self.settings = settings

    # --- what there is -----------------------------------------------------------------------------------------

    def runs(self, max_age: float = RUNS_TTL) -> list[dt.datetime]:
        """Give the times of the runs DWD lists, the oldest first, from a list held for `max_age` seconds at most.

        Raises:
            DownloadError: The directory lists no run: DWD's directory is not the one of a composite that is running.

        """
        with _SHARED.lock:
            held = _SHARED.runs
        if held is not None and clock.monotonic() - held[0] < max_age:
            return list(held[1])
        with _SHARED.runs_lock:
            with _SHARED.lock:
                held = _SHARED.runs
            if held is not None and clock.monotonic() - held[0] < max_age:
                return list(held[1])
            started = clock.monotonic()
            files = list_remote_files_fsspec(RV_URL, settings=self.settings, cache_expiry=CacheExpiry.NO_CACHE)
            runs = sorted(
                dt.datetime.strptime(f"{m.group(1)}{m.group(2)}", "%Y%m%d%H%M").replace(tzinfo=dt.UTC)
                for name in files
                if (m := _RUN_FILE.search(name))
            )
            if not runs:
                # an empty directory is DWD's outage, not a sky with no radar: never an answer of no frames
                raise DownloadError(RV_URL, "the directory lists no run of the composite")
            with _SHARED.lock:
                _SHARED.runs = (started, runs)
            return list(runs)

    def frames(self, *, history_minutes: int = 120, forecast: bool = True) -> RadarFrameList:
        """List the frames: the analysis of every run of the last `history_minutes` before the newest, and the forecast.

        The forecast is that of the newest run, 5 to 120 minutes after it. A run that DWD did not publish is a frame
        that is not there, so the times of the analysis are those of the runs there are.
        """
        runs = self.runs()
        latest = runs[-1]
        since = latest - dt.timedelta(minutes=history_minutes)
        frames = [RadarFrame(run=run, time=run, lead_minutes=0) for run in runs if run >= since]
        if forecast:
            frames.extend(
                RadarFrame(run=latest, time=latest + dt.timedelta(minutes=lead), lead_minutes=lead)
                for lead in range(STEP_MINUTES, FORECAST_MINUTES + 1, STEP_MINUTES)
            )
        now = dt.datetime.now(dt.UTC)
        if now - latest > STALE_AFTER:
            minutes = round((now - latest).total_seconds() / 60)
            warn_response(
                log,
                RADAR_STALE,
                f"The newest run of DWD's RV composite is from {latest:%Y-%m-%dT%H:%MZ}, {minutes} minutes ago: DWD "
                f"publishes one every 5 minutes, so runs are missing and the last frame of the loop is not now. The "
                f"forecast starts from that run.",
            )
        return RadarFrameList(run=latest, frames=tuple(frames), image=image_frame())

    # --- one frame ---------------------------------------------------------------------------------------------

    def frame(self, time: dt.datetime, run: dt.datetime | None = None) -> RadarImage:
        """Give the frame valid at `time`, from `run` (by default the run that time is of), drawn.

        A time up to the newest run is the analysis of the run of that time; a later time is the forecast of the newest
        run. Both are the run, and the lead time between them, of a frame in `frames()`, which names them so that a
        frame's address is a frame that never changes.

        Raises:
            RequestError: The time is not a multiple of 5 minutes, or is not 0 to 120 minutes after the run.
            RadarFrameNotFoundError: DWD holds no such run, or the run no such lead time.

        """
        if time.minute % STEP_MINUTES or time.second or time.microsecond:
            msg = f"time {time:%Y-%m-%dT%H:%M:%SZ} is not a multiple of {STEP_MINUTES} minutes: frames are 5 apart"
            raise RequestError(msg)
        run, served = self._resolve(time, run)
        lead = int((time - run).total_seconds() // 60)
        frame = RadarFrame(run=run, time=time, lead_minutes=lead)
        key = (run, lead)
        with _SHARED.lock:
            held = _SHARED.frames.get(key)
            if held is not None:
                _SHARED.frames.move_to_end(key)
        if held is None and lead:
            # the download of a forecast's tar is made outside the lock of a frame, so that an analysis frame, which a
            # range request reads, does not wait for the 7.7 MB of another frame's tar
            self._tar(run)
        if held is None:
            with _SHARED.frame_stripe(key):
                with _SHARED.lock:
                    held = _SHARED.frames.get(key)
                if held is None:
                    held = self._draw(frame, served=served)
                    with _SHARED.lock:
                        _SHARED.frames[key] = held
                        while len(_SHARED.frames) > MAX_FRAMES:
                            _SHARED.frames.popitem(last=False)
        return RadarImage(png=held, frame=frame, image=image_frame())

    def _resolve(self, time: dt.datetime, run: dt.datetime | None) -> tuple[dt.datetime, bool]:
        """Give the run a frame is read from and whether the whole of its tar may be read; refuse what is not served.

        What DWD lists is what there is: no file is asked for of a run it does not list, and the list is read again (at
        most every `NEWER_THAN_LISTED_AFTER` seconds) for a time or a run that is later than the one held, so that a
        frame of the newest run is not the forecast of an older one.
        """
        if run is not None and (run.minute % STEP_MINUTES or run.second or run.microsecond):
            msg = f"run {run:%Y-%m-%dT%H:%M:%SZ} is not a multiple of {STEP_MINUTES} minutes: runs are 5 apart"
            raise RequestError(msg)
        if run is not None:
            self._check_lead(time, run)
        runs = self.runs()
        # a run later than the list, or a time that could be the analysis of one (a forecast frame is not a reason to
        # list again: its time is always later than the newest run)
        newest = runs[-1]
        could_be_unlisted = (
            newest < time <= newest + dt.timedelta(minutes=STEP_MINUTES) if run is None else run > newest
        )
        if could_be_unlisted:
            runs = self._runs_again(runs)
        if run is None:
            run = min(time, runs[-1])
            self._check_lead(time, run)
        if run not in runs:
            msg = f"DWD lists no run of its RV composite at {run:%Y-%m-%dT%H:%MZ}: it holds the last two days"
            raise RadarFrameNotFoundError(msg)
        if run != time and run not in runs[-FORECAST_RUNS:]:
            msg = (
                f"the forecast of the run {run:%Y-%m-%dT%H:%MZ} is not served: it is served for the newest "
                f"{FORECAST_RUNS} runs of DWD's RV composite"
            )
            raise RadarFrameNotFoundError(msg)
        return run, run in runs[-FORECAST_RUNS:]

    def _runs_again(self, held: list[dt.datetime]) -> list[dt.datetime]:
        """Give a new list of runs, asked for at most every `NEWER_THAN_LISTED_AFTER` seconds, or the held one.

        The attempt is timed whether it succeeds or not, so a listing of DWD that is down is asked once in the time and
        not by every request. A limit of the provider is raised: it is not let go.
        """
        with _SHARED.lock:
            last = _SHARED.relisted_at
            now = clock.monotonic()
            if last is not None and now - last < NEWER_THAN_LISTED_AFTER:
                return held
            _SHARED.relisted_at = now
        try:
            return self.runs(max_age=NEWER_THAN_LISTED_AFTER)
        except ProviderRateLimitError:
            raise
        except Exception:  # noqa: BLE001
            log.warning("The list of runs of DWD's RV composite could not be read again: the held list is used.")
            return held

    @staticmethod
    def _check_lead(time: dt.datetime, run: dt.datetime) -> None:
        """Refuse a time that is not 0 to 120 minutes after the run."""
        lead = int((time - run).total_seconds() // 60)
        if not 0 <= lead <= FORECAST_MINUTES:
            msg = (
                f"time {time:%Y-%m-%dT%H:%MZ} is {lead} minutes after the run {run:%Y-%m-%dT%H:%MZ}: a run holds "
                f"0 to {FORECAST_MINUTES} minutes"
            )
            raise RequestError(msg)

    def _draw(self, frame: RadarFrame, *, served: bool) -> bytes:
        """Read a frame's file and draw it, at most `MAX_DECODES` at a time; `served` is for the run's whole tar."""
        data = self._member(frame.run, frame.lead_minutes, served=served)
        with _SHARED.decodes:
            field = read_field(data)
            if field.end != frame.time:
                msg = f"the file of {frame.time:%Y-%m-%dT%H:%MZ} is of {field.end:%Y-%m-%dT%H:%MZ}"
                raise RadarFormatError(msg)
            return draw(field).png

    # --- the files ---------------------------------------------------------------------------------------------

    def _member(self, run: dt.datetime, lead: int, *, served: bool) -> bytes:
        """Give the HDF5 file of a lead time of a run."""
        if lead == 0:
            return self._first_member(run, served=served)
        return self._extract(run, lead)

    def _extract(self, run: dt.datetime, lead: int) -> bytes:
        """Give a file out of the whole `.tar` of a run."""
        return self._member_from(self._tar(run), run, lead)

    @staticmethod
    def _member_from(tar: bytes, run: dt.datetime, lead: int) -> bytes:
        """Give a file of a lead time out of the bytes of the `.tar` of a run."""
        name = member_name(run, lead)
        try:
            with tarfile.open(fileobj=BytesIO(tar), mode="r:") as archive:
                member = archive.extractfile(name)
                if member is None:
                    raise KeyError(name)  # noqa: TRY301
                return member.read()
        except KeyError as e:
            msg = f"the run {run:%Y-%m-%dT%H:%MZ} of DWD's RV composite holds no file for {lead} minutes"
            raise RadarFrameNotFoundError(msg) from e
        except tarfile.TarError as e:
            raise DownloadError(run_url(run), "the file is not a readable tar archive") from e

    def _tar(self, run: dt.datetime) -> bytes:
        """Give a run's whole `.tar`, which is read once and held while its frames are drawn."""
        with _SHARED.lock:
            held = _SHARED.tars.get(run)
            if held is not None:
                _SHARED.tars.move_to_end(run)
        if held is not None:
            return held
        with _SHARED.tar_stripe(run):
            with _SHARED.lock:
                held = _SHARED.tars.get(run)
            if held is not None:
                return held
            url = run_url(run)
            file = download_file(
                url,
                cache_dir=self.settings.cache_dir,
                ttl=CacheExpiry.NO_CACHE,
                client_kwargs=self.settings.fsspec_client_kwargs,
                cache_disable=True,
                use_certifi=self.settings.use_certifi,
                max_bytes=MAX_TAR_BYTES,
            )
            if file.status == 404:
                msg = f"DWD holds no run of its RV composite at {run:%Y-%m-%dT%H:%MZ}"
                raise RadarFrameNotFoundError(msg)
            file.raise_if_exception()
            # `raise_if_exception` raised the failure that is the content of a download that failed
            tar = cast("BytesIO", file.content).getvalue()
            self._hold_tar(run, tar)
            return tar

    @staticmethod
    def _check_tar(run: dt.datetime, tar: bytes) -> None:
        """Refuse a body that is no tar of the run: an outage page, an empty body, any other file."""
        url = run_url(run)
        if len(tar) > MAX_TAR_BYTES:
            raise DownloadError(url, "the file is larger than a run of the composite is")
        try:
            with tarfile.open(fileobj=BytesIO(tar), mode="r:") as archive:
                names = archive.getnames()
        except tarfile.TarError as e:
            raise DownloadError(url, "the file is not a readable tar archive") from e
        if member_name(run, 0) not in names:
            raise DownloadError(url, "the archive does not hold the analysis of its run")

    def _hold_tar(self, run: dt.datetime, tar: bytes) -> None:
        """Hold a run's whole `.tar` for the frames of its forecast, the `MAX_TARS` used last.

        Only a tar that is one (a 502 for any other, and the next request asks again).
        """
        self._check_tar(run, tar)
        with _SHARED.lock:
            _SHARED.tars[run] = tar
            while len(_SHARED.tars) > MAX_TARS:
                _SHARED.tars.popitem(last=False)

    def _first_member(self, run: dt.datetime, *, served: bool) -> bytes:
        """Read the first file of a run's `.tar`, the analysis, by range requests, and not the whole archive.

        A tar is a header of 512 bytes (the name, the size) and the file, padded to 512, one after the other: the first
        request takes the header and, as a rule, the whole file, and a second the rest where it was longer. A server
        that sends the whole body for a range, or a first member that is not the analysis, is read whole instead.
        """
        url = run_url(run)
        head = self._range(url, 0, FIRST_READ_BYTES)
        if len(head) > FIRST_READ_BYTES:
            # a server that ignores `Range` sent the whole file: the file is taken out of it, and it is kept where the
            # forecast of the run may be read from it
            self._check_tar(run, head)
            if served:
                self._hold_tar(run, head)
            return self._member_from(head, run, 0)
        try:
            info = tarfile.TarInfo.frombuf(head[:_TAR_BLOCK], "utf-8", "surrogateescape")
        except tarfile.TarError:
            info = None
        if info is None or not info.name.endswith("_000-hd5") or not info.isfile():
            # not the layout of DWD's tars: the whole file is read, for the runs whose forecast is served only
            if not served:
                raise DownloadError(url, "the first file of the archive is not the analysis")
            return self._extract(run, 0)
        if not 0 < info.size <= MAX_MEMBER_BYTES:
            raise DownloadError(url, "the first file of the archive is not the size of a frame")
        end = _TAR_BLOCK + info.size
        if len(head) < end:
            more = self._range(url, len(head), end)
            if len(more) != end - len(head):
                raise DownloadError(url, "the first file of the archive is cut short or is not what was asked for")
            head += more
        if len(head) < end:
            raise DownloadError(url, "the first file of the archive is cut short")
        return head[_TAR_BLOCK:end]

    def _range(self, url: str, start: int, end: int) -> bytes:
        """Read the bytes `start` to `end` (excluded) of a file, as the network module does a download: told by kind."""
        filesystem = NetworkFilesystemManager.get(
            cache_dir=self.settings.cache_dir,
            cache_expiry=CacheExpiry.NO_CACHE,
            client_kwargs=self.settings.fsspec_client_kwargs,
            cache_disable=True,
            use_certifi=self.settings.use_certifi,
        )
        failure: Exception | None = None
        for _ in range(2):
            try:
                return filesystem.cat_file(url, start=start, end=end)
            except FileNotFoundError:
                # the one status the filesystem raises as itself: a 404. Any other failure of the request is
                # raised as the client's own (a `ClientResponseError` of its status, a connection error, a timeout)
                msg = f"DWD holds no file {url.rsplit('/', 1)[-1]} of its RV composite"
                raise RadarFrameNotFoundError(msg) from None
            except Exception as e:  # noqa: BLE001
                failure = e
            if not _worth_retrying(failure):
                # a 429 is not asked again, nor is a 4xx or a certificate that does not verify
                break
        # raised outside the `except`, so that the error of the client, which holds a proxy's key, is no `__context__`
        failed = _failed_file(url, failure)
        if failed is None:
            raise failure
        failed.raise_if_exception()
        raise DownloadError(url, "the range could not be read")
