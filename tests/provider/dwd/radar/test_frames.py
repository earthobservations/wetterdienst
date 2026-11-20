# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The frames of DWD's RV composite, listed and read from a stand-in for its directory (GH-3788)."""

# ruff: noqa: SLF001  (the process-wide state of the frames and the one reader of a range are what this holds to)

from __future__ import annotations

import datetime as dt
import threading
from typing import TYPE_CHECKING
from unittest.mock import MagicMock

import freezegun
import pytest
from aiohttp import ClientConnectorError, ClientResponseError, ServerDisconnectedError

from tests.provider.dwd.radar.rv_stub import FIXTURE_TIME, Dwd, rv_tar
from wetterdienst import Settings
from wetterdienst.exceptions import DownloadError, NoInternetError, NotFoundError, ProviderRateLimitError, RequestError
from wetterdienst.provider.dwd.radar import frames as frames_module
from wetterdienst.provider.dwd.radar import rv
from wetterdienst.provider.dwd.radar.frames import (
    FIRST_READ_BYTES,
    DwdRadarFrames,
    RadarFrameNotFoundError,
    format_instant,
    parse_instant,
)
from wetterdienst.util.network import File
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

if TYPE_CHECKING:
    from pathlib import Path

UTC = dt.UTC
NEWEST = FIXTURE_TIME + dt.timedelta(minutes=30)
#: a run of the stand-in is 25 files of 318 KB: the tars are made once for the module
_RUNS = [FIXTURE_TIME + dt.timedelta(minutes=5 * i) for i in range(7)]


@pytest.fixture(scope="module")
def tars(tmp_path_factory: pytest.TempPathFactory) -> dict[dt.datetime, bytes]:
    """Make the `.tar` of seven runs, 21:10 to 21:40; only the newest holds a forecast, as it is the one read."""
    directory = tmp_path_factory.mktemp("rv")
    return {run: rv_tar(run, directory, range(0, 121, 5) if run == NEWEST else range(0, 11, 5)) for run in _RUNS}


@pytest.fixture
def dwd(monkeypatch: pytest.MonkeyPatch, tars: dict[dt.datetime, bytes]) -> Dwd:
    """Serve the seven runs."""
    return Dwd(dict(tars)).install(monkeypatch)


@pytest.fixture
def service(dwd: Dwd) -> DwdRadarFrames:  # noqa: ARG001
    """Give the service, whose network is the stand-in's `dwd`."""
    begin_response()
    return DwdRadarFrames(Settings())


def _now(minutes: int) -> freezegun.api.FrozenDateTimeFactory | object:
    return freezegun.freeze_time(NEWEST + dt.timedelta(minutes=minutes))


# --- what there is --------------------------------------------------------------------------------------------------


def test_the_runs_are_the_files_of_the_directory_in_time_order_and_the_alias_is_none(
    dwd: Dwd, service: DwdRadarFrames
) -> None:
    """`composite_rv_LATEST.tar` is the newest run under another name, and is not listed as a second one."""
    dwd.tars = dict(reversed(list(dwd.tars.items())))

    assert service.runs() == _RUNS


def test_an_empty_directory_is_a_failure_of_dwd_and_not_a_sky_with_no_radar(
    monkeypatch: pytest.MonkeyPatch, service: DwdRadarFrames
) -> None:
    """A listing with no run is DWD's outage: a 502 for the caller to retry, never an answer of no frames."""
    Dwd({}).install(monkeypatch)

    with pytest.raises(DownloadError, match="lists no run"):
        service.runs()


def test_the_list_of_runs_is_held_for_a_minute(dwd: Dwd, service: DwdRadarFrames) -> None:
    """Many readers are one listing a minute, and a new run is seen within it."""
    service.runs()
    service.runs()
    assert dwd.listings == 1

    frames_module._SHARED.runs = (frames_module._SHARED.runs[0] - frames_module.RUNS_TTL - 1, _RUNS)  # ty: ignore[not-subscriptable]
    service.runs()
    assert dwd.listings == 2


def test_the_loop_is_the_analysis_of_every_run_of_the_past_and_the_forecast_of_the_newest(
    service: DwdRadarFrames,
) -> None:
    """Seven runs of 5 minutes, then the 24 steps of the forecast to two hours after the newest."""
    with _now(2):
        listing = service.frames(history_minutes=120, forecast=True)

    assert listing.run == NEWEST
    observed = [f for f in listing.frames if f.kind == "observation"]
    forecast = [f for f in listing.frames if f.kind == "forecast"]
    assert [f.time for f in observed] == _RUNS
    assert all(f.run == f.time and f.lead_minutes == 0 for f in observed)
    assert len(forecast) == 24
    assert {f.run for f in forecast} == {NEWEST}
    assert [f.lead_minutes for f in forecast] == list(range(5, 121, 5))
    assert [f.time for f in forecast] == [NEWEST + dt.timedelta(minutes=m) for m in range(5, 121, 5)]
    assert [f.time for f in listing.frames] == sorted(f.time for f in listing.frames)
    assert recorded_warnings() == []


def test_the_past_is_as_far_back_as_asked_and_the_forecast_is_left_out_on_request(
    service: DwdRadarFrames,
) -> None:
    """`past` minutes before the newest run, the run of that time included; `forecast=false` is the analysis alone."""
    with _now(2):
        listing = service.frames(history_minutes=10, forecast=False)
        nothing_past = service.frames(history_minutes=0, forecast=False)

    assert [f.time for f in listing.frames] == _RUNS[-3:]
    assert [f.time for f in nothing_past.frames] == [NEWEST]


def test_a_run_that_dwd_did_not_publish_is_a_frame_that_is_not_there(dwd: Dwd, service: DwdRadarFrames) -> None:
    """The loop has the times DWD has, so a gap is a gap and the page is not given a frame that would be a 404."""
    del dwd.tars[_RUNS[3]]
    with _now(2):
        listing = service.frames(history_minutes=120, forecast=False)

    assert _RUNS[3] not in [f.time for f in listing.frames]
    assert len(listing.frames) == 6


def test_the_image_lies_where_the_decoder_says_for_every_frame(dwd: Dwd, service: DwdRadarFrames) -> None:
    """The bounds are announced with the list, from no file: they are those of the DE1200 grid."""
    with _now(2):
        listing = service.frames()

    assert listing.image == rv.image_frame()
    assert dwd.ranged == dwd.whole == []


def test_an_old_newest_run_is_told_as_a_warning_and_still_listed(service: DwdRadarFrames) -> None:
    """DWD's run that stopped is no all-clear: the loop ends at the old run and the answer says it is old."""
    with _now(45):
        listing = service.frames()

    assert listing.run == NEWEST
    (warning,) = recorded_warnings()
    assert warning["code"] == "radar-stale"
    assert "45 minutes" in warning["message"] or "47 minutes" in warning["message"]


def test_a_fresh_run_is_no_warning(service: DwdRadarFrames) -> None:
    """The newest run is up to 8 minutes old when it appears and 5 more before the next, so 13 are none."""
    with _now(13):
        service.frames()

    assert recorded_warnings() == []


# --- one frame ------------------------------------------------------------------------------------------------------


def test_the_analysis_is_read_by_two_ranges_and_never_by_the_whole_tar(dwd: Dwd, service: DwdRadarFrames) -> None:
    """The analysis is the first file of the tar: its 512 bytes of header and 318 KB, not the 7.7 MB of 25 files."""
    image = service.frame(_RUNS[2], _RUNS[2])

    assert dwd.whole == []
    assert dwd.ranged == [(_RUNS[2], 0, FIRST_READ_BYTES)]
    assert image.frame.kind == "observation"
    assert image.frame.time == image.frame.run == _RUNS[2]
    assert image.png.startswith(b"\x89PNG")
    assert image.image == rv.image_frame()


def test_a_first_file_larger_than_the_first_read_takes_a_second_range(
    dwd: Dwd, service: DwdRadarFrames, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The rest of the file is asked for from where the first read ended."""
    monkeypatch.setattr(frames_module, "FIRST_READ_BYTES", 100_000)

    service.frame(_RUNS[1], _RUNS[1])

    (first, second) = dwd.ranged
    assert first == (_RUNS[1], 0, 100_000)
    assert second[:2] == (_RUNS[1], 100_000)
    assert second[2] > 300_000


def test_a_server_that_sends_the_whole_file_for_a_range_is_read_whole_and_the_frame_is_the_same(
    dwd: Dwd, service: DwdRadarFrames
) -> None:
    """A mirror that ignores `Range` answers the 7.7 MB: the analysis is taken out of it, not read as a header."""
    expected = service.frame(_RUNS[5], _RUNS[5]).png
    frames_module.forget_everything()
    dwd.ranges = False
    dwd.ranged.clear()

    assert service.frame(_RUNS[5], _RUNS[5]).png == expected
    # the body that came for the range is the tar: it is not asked for again, and is held for the forecast
    assert dwd.whole == []
    assert len(dwd.ranged) == 1
    assert list(frames_module._SHARED.tars) == [_RUNS[5]]


def test_a_forecast_frame_is_read_from_the_tar_which_is_downloaded_once_for_all_of_them(
    dwd: Dwd, service: DwdRadarFrames
) -> None:
    """The 24 forecast frames of a run are one download, the one the first of them makes."""
    leads = range(5, 121, 5)
    images = [service.frame(NEWEST + dt.timedelta(minutes=m), NEWEST) for m in leads]

    assert dwd.whole == [NEWEST]
    assert dwd.ranged == []
    assert [i.frame.lead_minutes for i in images] == list(leads)
    assert {i.frame.kind for i in images} == {"forecast"}


def test_a_frame_is_drawn_once_for_every_reader(
    dwd: Dwd, service: DwdRadarFrames, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The second ask is the one decode's: no request, no decode, the very bytes."""
    drawn = []
    original = frames_module.draw
    monkeypatch.setattr(frames_module, "draw", lambda *a, **k: drawn.append(1) or original(*a, **k))

    first = service.frame(_RUNS[0], _RUNS[0])
    ranged = len(dwd.ranged)
    second = DwdRadarFrames(Settings()).frame(_RUNS[0], _RUNS[0])

    assert second.png is first.png
    assert len(drawn) == 1
    assert len(dwd.ranged) == ranged


def test_frames_asked_for_at_the_same_time_are_one_decode(
    dwd: Dwd,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A page asks for its 49 frames at once, and another reader does too: a frame is read and drawn one time."""
    drawn = []
    original = frames_module.draw
    release = threading.Event()

    def slow_draw(*args: object, **kwargs: object) -> object:
        drawn.append(1)
        release.wait(5)
        return original(*args, **kwargs)  # ty: ignore[invalid-argument-type]

    monkeypatch.setattr(frames_module, "draw", slow_draw)
    results: list[bytes] = []

    def ask() -> None:
        results.append(DwdRadarFrames(Settings()).frame(_RUNS[4], _RUNS[4]).png)

    threads = [threading.Thread(target=ask) for _ in range(6)]
    for thread in threads:
        thread.start()
    release.set()
    for thread in threads:
        thread.join(10)

    assert len(drawn) == 1
    assert len(results) == 6
    assert len({id(png) for png in results}) == 1
    assert len(dwd.ranged) == 1


def test_no_more_frames_than_the_cap_are_held_and_the_oldest_asked_for_goes_first(
    service: DwdRadarFrames,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The memory of the cache is bounded; a frame that was asked for again is the one that stays."""
    monkeypatch.setattr(frames_module, "MAX_FRAMES", 3)
    for run in _RUNS[:3]:
        service.frame(run, run)
    service.frame(_RUNS[0], _RUNS[0])  # asked for again: now the newest of the three
    service.frame(_RUNS[3], _RUNS[3])  # pushes out the oldest, which is no longer the first

    assert set(frames_module._SHARED.frames) == {(_RUNS[0], 0), (_RUNS[2], 0), (_RUNS[3], 0)}


def test_the_tars_held_whole_are_the_ones_used_last(service: DwdRadarFrames, monkeypatch: pytest.MonkeyPatch) -> None:
    """The first run's tar is let go where more are read than are held: not kept for every run."""
    monkeypatch.setattr(frames_module, "MAX_TARS", 2)
    for run in (NEWEST, _RUNS[5], _RUNS[4]):
        service.frame(run + dt.timedelta(minutes=5), run)

    assert list(frames_module._SHARED.tars) == [_RUNS[5], _RUNS[4]]


def test_a_time_without_a_run_is_the_analysis_up_to_the_newest_run_and_its_forecast_after(
    service: DwdRadarFrames,
) -> None:
    """A caller that names no run asks for what is shown now: a past time is the analysis, a future one DWD's."""
    past = service.frame(_RUNS[1])
    future = service.frame(NEWEST + dt.timedelta(minutes=45))

    assert (past.frame.run, past.frame.lead_minutes) == (_RUNS[1], 0)
    assert (future.frame.run, future.frame.lead_minutes) == (NEWEST, 45)


@pytest.mark.parametrize(
    ("time", "run", "message"),
    [
        (_RUNS[0] + dt.timedelta(minutes=1), None, "multiple of 5 minutes"),
        (_RUNS[0] + dt.timedelta(seconds=30), None, "multiple of 5 minutes"),
        (_RUNS[0], _RUNS[0] + dt.timedelta(minutes=3), "run .* is not a multiple of 5"),
        (_RUNS[0] - dt.timedelta(minutes=5), _RUNS[0], "-5 minutes after the run"),
        (_RUNS[0] + dt.timedelta(minutes=125), _RUNS[0], "125 minutes after the run"),
    ],
)
def test_a_time_that_is_no_frame_is_a_refusal_that_says_why(
    dwd: Dwd, service: DwdRadarFrames, time: dt.datetime, run: dt.datetime | None, message: str
) -> None:
    """A request that cannot be a frame is the caller's (a 400), before any file is asked for."""
    with pytest.raises(RequestError, match=message):
        service.frame(time, run)

    assert dwd.ranged == dwd.whole == []


def test_a_run_dwd_does_not_hold_is_not_found(dwd: Dwd, service: DwdRadarFrames) -> None:
    """DWD keeps about two days: a run older is a 404 with the file's name, and nothing is kept of it."""
    gone = FIXTURE_TIME - dt.timedelta(days=3)

    with pytest.raises(RadarFrameNotFoundError, match=r"lists no run .* 2026-11-16T21:10Z") as excinfo:
        service.frame(gone, gone)
    assert isinstance(excinfo.value, NotFoundError)
    with pytest.raises(RadarFrameNotFoundError, match="lists no run"):
        service.frame(gone + dt.timedelta(minutes=5), gone)
    with pytest.raises(RadarFrameNotFoundError, match="lists no run"):
        service.frame(gone)
    assert frames_module._SHARED.frames == {}
    # told from the listing: no file of DWD was asked for
    assert dwd.ranged == dwd.whole == []


def test_a_run_that_is_listed_and_gone_when_it_is_read_is_not_found(dwd: Dwd, service: DwdRadarFrames) -> None:
    """DWD removes a run between the listing and the read: the 404 of the file is the same answer."""
    service.runs()
    del dwd.tars[_RUNS[2]]

    with pytest.raises(RadarFrameNotFoundError, match=r"composite_rv_20261119_2120\.tar"):
        service.frame(_RUNS[2], _RUNS[2])


def test_the_forecast_is_served_for_the_newest_runs_only_and_asks_nothing_of_dwd_for_the_others(
    dwd: Dwd, service: DwdRadarFrames
) -> None:
    """Each run's forecast is a tar of 7.7 MB: a request may not make the server read the one of any run of two days."""
    assert frames_module.FORECAST_RUNS == 3
    with pytest.raises(RadarFrameNotFoundError, match="not served"):
        service.frame(_RUNS[3] + dt.timedelta(minutes=5), _RUNS[3])

    assert dwd.ranged == dwd.whole == []
    service.frame(_RUNS[4] + dt.timedelta(minutes=5), _RUNS[4])
    assert dwd.whole == [_RUNS[4]]


def test_a_time_or_a_run_later_than_the_list_is_looked_for_in_a_new_list_at_most_every_ten_seconds(
    dwd: Dwd, service: DwdRadarFrames
) -> None:
    """A run that has just appeared is the analysis of its time and not a forecast of the run before it."""
    service.runs()
    newer = NEWEST + dt.timedelta(minutes=5)
    dwd.tars[newer] = dwd.tars[NEWEST]
    # the stand-in has no file of 21:45: only the choice of run counts
    listed = dwd.listings

    with pytest.raises(RadarFrameNotFoundError, match="lists no run"):
        service.frame(newer, newer)
    assert dwd.listings == listed  # the list was read a moment ago

    frames_module._SHARED.runs = (frames_module._SHARED.runs[0] - 11, _RUNS)  # ty: ignore[not-subscriptable]
    run = service.runs(max_age=frames_module.NEWER_THAN_LISTED_AFTER)
    assert run[-1] == newer
    assert dwd.listings == listed + 1


@pytest.mark.parametrize(
    "body", [b"<html>nginx maintenance</html>" * 100, b"", b"x" * 100_000], ids=["html", "empty", "binary"]
)
@pytest.mark.parametrize("lead", [0, 5])
def test_a_body_that_is_no_tar_is_a_failure_and_is_held_for_no_frame_and_the_next_request_mends_it(
    dwd: Dwd, service: DwdRadarFrames, body: bytes, lead: int
) -> None:
    """An outage page, an empty body or any other file is a 502 for the frame, whichever lead time, and is not kept."""
    good = dwd.tars[NEWEST]
    dwd.tars[NEWEST] = body
    time = NEWEST + dt.timedelta(minutes=lead)

    with pytest.raises(DownloadError):
        service.frame(time, NEWEST)

    assert frames_module._SHARED.tars == {}
    assert frames_module._SHARED.frames == {}
    dwd.tars[NEWEST] = good
    assert service.frame(time, NEWEST).png.startswith(b"\x89PNG")


def test_a_tar_that_lacks_the_analysis_of_its_run_is_no_tar_of_it(
    dwd: Dwd, service: DwdRadarFrames, tmp_path: Path
) -> None:
    """A tar of other files, as DWD's server answers a name it does not know, is not held as the run's."""
    other = rv_tar(NEWEST + dt.timedelta(minutes=5), tmp_path, range(0, 11, 5))
    dwd.tars[NEWEST] = other

    with pytest.raises(DownloadError, match="does not hold the analysis"):
        service.frame(NEWEST + dt.timedelta(minutes=5), NEWEST)
    assert frames_module._SHARED.tars == {}


def test_a_first_file_that_is_not_the_size_of_a_frame_is_refused_and_a_second_range_must_be_whole(
    service: DwdRadarFrames, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The size in the header of the tar is DWD's to state and the server's to bound: no allocation follows it."""
    monkeypatch.setattr(frames_module, "MAX_MEMBER_BYTES", 1000)
    with pytest.raises(DownloadError, match="not the size of a frame"):
        service.frame(_RUNS[1], _RUNS[1])
    monkeypatch.setattr(frames_module, "MAX_MEMBER_BYTES", 8 * 1024**2)
    monkeypatch.setattr(frames_module, "FIRST_READ_BYTES", 100_000)
    original = frames_module.DwdRadarFrames._range

    def short(self: DwdRadarFrames, url: str, start: int, end: int) -> bytes:
        return original(self, url, start, end)[:-1] if start else original(self, url, start, end)

    monkeypatch.setattr(frames_module.DwdRadarFrames, "_range", short)
    with pytest.raises(DownloadError, match="cut short"):
        service.frame(_RUNS[1], _RUNS[1])


def test_a_lead_time_the_run_does_not_hold_is_not_found(service: DwdRadarFrames) -> None:
    """The runs of the stand-in but the newest hold two forecast steps: the third is not in the tar."""
    with pytest.raises(RadarFrameNotFoundError, match="holds no file for 15 minutes"):
        service.frame(_RUNS[5] + dt.timedelta(minutes=15), _RUNS[5])


def test_a_file_of_another_time_than_its_name_is_not_drawn(dwd: Dwd, service: DwdRadarFrames, tmp_path: Path) -> None:
    """A mislabelled frame would be a loop in the wrong order: it is a format error, and nothing is kept."""
    import io  # noqa: PLC0415
    import tarfile  # noqa: PLC0415

    from tests.provider.dwd.radar.rv_stub import member_file  # noqa: PLC0415

    data = member_file(_RUNS[1], tmp_path)  # the file of 21:15, named as the analysis of 21:10
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        info = tarfile.TarInfo(frames_module.member_name(_RUNS[0], 0))
        info.size = len(data)
        archive.addfile(info, io.BytesIO(data))
    dwd.tars[_RUNS[0]] = buffer.getvalue()

    with pytest.raises(rv.RadarFormatError, match="is of 2026-11-19T21:15Z"):
        service.frame(_RUNS[0], _RUNS[0])
    assert frames_module._SHARED.frames == {}


def test_a_first_file_cut_short_is_a_failure_of_dwd_and_is_not_kept(dwd: Dwd, service: DwdRadarFrames) -> None:
    """A tar that is still being written, or cut: the 502 of a download that failed, which the next request may mend."""
    dwd.tars[_RUNS[0]] = dwd.tars[_RUNS[0]][:200_000]

    with pytest.raises(DownloadError, match="cut short"):
        service.frame(_RUNS[0], _RUNS[0])
    assert frames_module._SHARED.frames == {}


def test_a_first_member_that_is_not_the_analysis_is_taken_from_the_whole_tar(dwd: Dwd, service: DwdRadarFrames) -> None:
    """The order of a tar is DWD's: a layout that does not begin with lead 0 is read by name, not by position."""
    import io  # noqa: PLC0415
    import tarfile  # noqa: PLC0415

    buffer = io.BytesIO()
    with (
        tarfile.open(fileobj=io.BytesIO(dwd.tars[_RUNS[5]])) as source,
        tarfile.open(fileobj=buffer, mode="w") as target,
    ):
        for member in reversed(source.getmembers()):
            target.addfile(member, source.extractfile(member))
    dwd.tars[_RUNS[5]] = buffer.getvalue()

    assert service.frame(_RUNS[5], _RUNS[5]).png.startswith(b"\x89PNG")
    assert dwd.whole == [_RUNS[5]]


def test_a_tar_that_is_none_is_a_failure_of_dwd(dwd: Dwd, service: DwdRadarFrames) -> None:
    """HTML where an archive was expected, which a forecast frame opens: told as the download that failed it is."""
    dwd.tars[NEWEST] = b"<html>nginx maintenance</html>" * 100

    with pytest.raises(DownloadError, match="not a readable tar"):
        service.frame(NEWEST + dt.timedelta(minutes=5), NEWEST)
    assert frames_module._SHARED.tars == {}


# --- the network ----------------------------------------------------------------------------------------------------


class _Filesystem:
    """What `NetworkFilesystemManager.get` is made to give: it answers a range with bytes, or raises what it is told."""

    def __init__(self, *outcomes: object) -> None:
        self.outcomes = list(outcomes)
        self.asked: list[tuple[str, int, int]] = []

    def cat_file(self, url: str, start: int, end: int) -> bytes:
        self.asked.append((url, start, end))
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome  # ty: ignore[invalid-return-type]


def _serve(monkeypatch: pytest.MonkeyPatch, filesystem: _Filesystem) -> None:
    monkeypatch.setattr(frames_module.NetworkFilesystemManager, "get", lambda **_: filesystem)


URL = "https://opendata.dwd.de/weather/radar/composite/rv/composite_rv_20261119_2110.tar"


def test_a_range_is_read_through_the_network_module_without_a_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    """The bytes are the range's, from a filesystem that keeps no copy: a frame is held decoded, not as 300 KB too."""
    filesystem = _Filesystem(b"abc")
    _serve(monkeypatch, filesystem)

    assert DwdRadarFrames(Settings())._range(URL, 5, 8) == b"abc"
    assert filesystem.asked == [(URL, 5, 8)]


def test_a_range_that_fails_once_is_asked_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """A reset of a connection that DWD's server closes is the next request's to mend, as downloads are."""
    filesystem = _Filesystem(ServerDisconnectedError("reset"), b"abc")
    _serve(monkeypatch, filesystem)

    assert DwdRadarFrames(Settings())._range(URL, 0, 3) == b"abc"
    assert len(filesystem.asked) == 2


def test_a_range_that_fails_twice_is_the_failure_of_a_download(monkeypatch: pytest.MonkeyPatch) -> None:
    """Told by the network module's own rule, the URL in it and the failure as its cause: a 502."""
    _serve(monkeypatch, _Filesystem(ServerDisconnectedError("reset"), ServerDisconnectedError("reset")))

    with pytest.raises(DownloadError, match="composite_rv_20261119_2110") as excinfo:
        DwdRadarFrames(Settings())._range(URL, 0, 3)
    assert isinstance(excinfo.value.__cause__, ServerDisconnectedError)


def test_a_range_of_a_file_that_is_not_there_is_a_run_that_is_gone(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 404 is not asked again and is not a failure of DWD: the run is older than what it keeps."""
    filesystem = _Filesystem(FileNotFoundError(URL))
    _serve(monkeypatch, filesystem)

    with pytest.raises(RadarFrameNotFoundError, match=r"composite_rv_20261119_2110\.tar"):
        DwdRadarFrames(Settings())._range(URL, 0, 3)
    assert len(filesystem.asked) == 1


def test_no_connection_is_the_error_of_no_connection(monkeypatch: pytest.MonkeyPatch) -> None:
    """A server that cannot be reached is a 503 and not a 502, as it is for every download (GH-2640)."""
    unreachable = ClientConnectorError(MagicMock(ssl=None, host="opendata.dwd.de", port=443), OSError("unreachable"))
    _serve(monkeypatch, _Filesystem(unreachable, unreachable))

    with pytest.raises(NoInternetError):
        DwdRadarFrames(Settings())._range(URL, 0, 3)


def _response_error(status: int) -> ClientResponseError:
    return ClientResponseError(request_info=MagicMock(), history=(), status=status, message="no")


def test_a_limit_of_the_provider_on_a_range_is_not_asked_again_and_is_the_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A 429 is how DWD's server says to slow down: asking again is how that gets worse. It is the 503 with a wait."""
    filesystem = _Filesystem(_response_error(429), b"never asked")
    _serve(monkeypatch, filesystem)

    with pytest.raises(ProviderRateLimitError):
        DwdRadarFrames(Settings())._range(URL, 0, 3)
    assert len(filesystem.asked) == 1


def test_a_refusal_of_a_range_is_not_asked_again(monkeypatch: pytest.MonkeyPatch) -> None:
    """A 403 will not be a 206 on the second try; a 503 might be, which `test_a_range_that_fails_once` holds."""
    filesystem = _Filesystem(_response_error(403), b"never asked")
    _serve(monkeypatch, filesystem)

    with pytest.raises(DownloadError):
        DwdRadarFrames(Settings())._range(URL, 0, 3)
    assert len(filesystem.asked) == 1


@pytest.mark.usefixtures("dwd")
def test_a_limit_of_the_provider_on_the_tar_is_the_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole file is downloaded as every download is: its 429 is the same limit, with the wait DWD sent."""

    def download(url: str, **_kwargs: object) -> File:
        return File(url=url, content=_response_error(429), status=429)

    monkeypatch.setattr(frames_module, "download_file", download)

    with pytest.raises(ProviderRateLimitError):
        DwdRadarFrames(Settings()).frame(NEWEST + dt.timedelta(minutes=5), NEWEST)
    assert frames_module._SHARED.tars == {}


# --- the times ------------------------------------------------------------------------------------------------------


def test_times_are_written_with_a_z_and_read_with_or_without_an_offset() -> None:
    """The frames name times a query takes as they are, and read ones with an offset or none (UTC)."""
    assert format_instant(FIXTURE_TIME) == "2026-11-19T21:10:00Z"
    assert format_instant(FIXTURE_TIME.astimezone(dt.timezone(dt.timedelta(hours=1)))) == "2026-11-19T21:10:00Z"
    assert parse_instant("2026-11-19T21:10:00Z") == FIXTURE_TIME
    assert parse_instant("2026-11-19T22:10:00+01:00") == FIXTURE_TIME
    assert parse_instant("2026-11-19T21:10") == FIXTURE_TIME
    assert parse_instant(" 2026-11-19T21:10:00.000000+00:00 ") == FIXTURE_TIME


@pytest.mark.parametrize("text", ["", "now", "2026-13-01T00:00:00Z", "9999-12-31T23:00:00-05:00"])
def test_a_time_that_is_none_is_a_refusal(text: str) -> None:
    """Text that is no time, or one the offset carries out of what a datetime holds, is the request's (a 400)."""
    with pytest.raises(RequestError):
        parse_instant(text)


@pytest.mark.usefixtures("dwd")
def test_the_tars_are_kept_out_of_the_cache_directory(tmp_path: Path) -> None:
    """Nothing is written to the cache directory for a frame: it is held decoded in memory, and the tar for a moment."""
    from wetterdienst import Settings as _Settings  # noqa: PLC0415

    DwdRadarFrames(_Settings(cache_dir=tmp_path / "cache")).frame(NEWEST + dt.timedelta(minutes=5), NEWEST)

    assert not (tmp_path / "cache").exists() or not any((tmp_path / "cache").rglob("*.tar"))


@pytest.mark.usefixtures("dwd")
def test_a_frame_that_needs_a_tar_does_not_wait_for_itself_whichever_locks_its_key_and_the_tar_pick(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A forecast frame holds the lock of its key while its tar is read, and the tar has a lock of its own.

    The locks are a few, picked by the hash of a key, so a frame and its tar may pick the same one of a kind: with
    one lock of each kind that is every frame, and a frame that waited for a lock it held itself was a request that
    ended at the server's timeout.
    """
    monkeypatch.setattr(frames_module._SHARED, "frame_stripes", (threading.Lock(),))
    monkeypatch.setattr(frames_module._SHARED, "tar_stripes", (threading.Lock(),))
    done: list[bytes] = []

    def ask(run: dt.datetime, lead: int) -> None:
        done.append(DwdRadarFrames(Settings()).frame(run + dt.timedelta(minutes=lead), run).png)

    threads = [threading.Thread(target=ask, args=(run, 5), daemon=True) for run in (NEWEST, _RUNS[5], _RUNS[4])]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(20)

    assert len(done) == 3


@pytest.mark.usefixtures("dwd")
def test_an_analysis_frame_does_not_wait_for_the_download_of_a_forecast_tar(monkeypatch: pytest.MonkeyPatch) -> None:
    """The tar of a forecast is read before the lock of its frame is taken, so a cold analysis frame goes past it."""
    monkeypatch.setattr(frames_module._SHARED, "frame_stripes", (threading.Lock(),))
    started, release = threading.Event(), threading.Event()
    original = frames_module.download_file

    def slow(url: str, **kwargs: object) -> File:
        started.set()
        release.wait(10)
        return original(url, **kwargs)  # ty: ignore[invalid-argument-type]

    monkeypatch.setattr(frames_module, "download_file", slow)
    forecast = threading.Thread(
        target=lambda: DwdRadarFrames(Settings()).frame(NEWEST + dt.timedelta(minutes=5), NEWEST), daemon=True
    )
    forecast.start()
    assert started.wait(10)

    analysis = DwdRadarFrames(Settings()).frame(_RUNS[2], _RUNS[2])

    assert analysis.png.startswith(b"\x89PNG")
    assert forecast.is_alive()
    release.set()
    forecast.join(10)
    assert not forecast.is_alive()


def test_the_forecasts_of_the_newest_runs_asked_for_frame_by_frame_read_each_tar_once(
    dwd: Dwd, service: DwdRadarFrames
) -> None:
    """Three readers, one for each run whose forecast is served, interleaved: three downloads, not one a frame."""
    runs = (_RUNS[4], _RUNS[5], NEWEST)
    for lead in (5, 10):
        for run in runs:
            service.frame(run + dt.timedelta(minutes=lead), run)

    assert sorted(dwd.whole) == sorted(runs)
    assert frames_module.MAX_TARS > frames_module.FORECAST_RUNS


def test_a_forecast_frame_without_a_run_does_not_list_again_and_a_listing_that_fails_is_the_held_one(
    dwd: Dwd, service: DwdRadarFrames, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A time after the newest run is a forecast, not an unlisted analysis; a listing that fails is the held one."""
    service.runs()
    frames_module._SHARED.runs = (frames_module._SHARED.runs[0] - 11, _RUNS)  # ty: ignore[not-subscriptable]
    listed = dwd.listings

    service.frame(NEWEST + dt.timedelta(minutes=30))
    assert dwd.listings == listed

    url, reason = "https://opendata.dwd.de/", "500"

    def fail(*_args: object, **_kwargs: object) -> list[str]:
        raise DownloadError(url, reason)

    monkeypatch.setattr(frames_module, "list_remote_files_fsspec", fail)
    with pytest.raises(RadarFrameNotFoundError, match="lists no run"):
        service.frame(NEWEST + dt.timedelta(minutes=5), NEWEST + dt.timedelta(minutes=5))


def test_the_whole_tar_is_read_for_the_analysis_of_a_run_whose_forecast_is_served_only(
    dwd: Dwd, service: DwdRadarFrames
) -> None:
    """A layout that does not begin with the analysis is read whole for the newest runs, and refused for the others."""
    import io  # noqa: PLC0415
    import tarfile  # noqa: PLC0415

    buffer = io.BytesIO()
    with (
        tarfile.open(fileobj=io.BytesIO(dwd.tars[_RUNS[0]])) as source,
        tarfile.open(fileobj=buffer, mode="w") as target,
    ):
        for member in reversed(source.getmembers()):
            target.addfile(member, source.extractfile(member))
    dwd.tars[_RUNS[0]] = buffer.getvalue()

    with pytest.raises(DownloadError, match="not the analysis"):
        service.frame(_RUNS[0], _RUNS[0])
    assert dwd.whole == []
