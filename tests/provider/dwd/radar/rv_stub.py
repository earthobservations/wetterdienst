# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A stand-in for DWD's directory of the RV composite, made of one real file (GH-3788).

`files/composite_rv_20261119_2110_000-hd5` is the radar analysis of 2026-11-19 21:10 UTC as DWD published it (318 KB,
rain over Germany). `rv_tar` makes the `.tar` of a run from it: a member for each lead time, each the real file with
the time it is valid at (and nothing else) set to what the name says. `Dwd` serves the listing, the range requests and
the whole downloads of such runs, and counts what was asked for.
"""

from __future__ import annotations

import datetime as dt
import io
import shutil
import tarfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import h5py

from wetterdienst.provider.dwd.radar import frames as frames_module
from wetterdienst.provider.dwd.radar.frames import RV_URL, forget_everything, member_name
from wetterdienst.util.network import File

if TYPE_CHECKING:
    import pytest

UTC = dt.UTC
FIXTURE = Path(__file__).parent / "files" / "composite_rv_20261119_2110_000-hd5"
#: the time the fixture is valid at, which is its run
FIXTURE_TIME = dt.datetime(2026, 11, 19, 21, 10, tzinfo=UTC)


def member_file(time: dt.datetime, directory: Path) -> bytes:
    """Give the fixture as the file valid at `time`: its 5 minutes end then, the rest of it is DWD's."""
    path = directory / f"{time:%Y%m%d%H%M}.hd5"
    shutil.copyfile(FIXTURE, path)
    start = time - dt.timedelta(minutes=5)
    with h5py.File(path, "r+") as f:
        what = f["dataset1/what"]
        what.attrs["enddate"] = time.strftime("%Y%m%d").encode()
        what.attrs["endtime"] = time.strftime("%H%M%S").encode()
        what.attrs["startdate"] = start.strftime("%Y%m%d").encode()
        what.attrs["starttime"] = start.strftime("%H%M%S").encode()
    return path.read_bytes()


def rv_tar(run: dt.datetime, directory: Path, leads: range = range(0, 121, 5)) -> bytes:
    """Make the `.tar` of a run: the file of every lead time, the analysis first, as DWD's are."""
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w") as archive:
        for lead in leads:
            data = member_file(run + dt.timedelta(minutes=lead), directory)
            info = tarfile.TarInfo(member_name(run, lead))
            info.size = len(data)
            archive.addfile(info, io.BytesIO(data))
    return buffer.getvalue()


@dataclass
class Dwd:
    """What DWD's directory of the RV composite serves, and what was asked of it."""

    tars: dict[dt.datetime, bytes] = field(repr=False)
    #: whether the server answers a range, as DWD's does; one that does not sends the whole file
    ranges: bool = True
    #: every (start, end) asked for by range, by run
    ranged: list[tuple[dt.datetime, int, int]] = field(default_factory=list)
    #: every run a whole file was asked for
    whole: list[dt.datetime] = field(default_factory=list)
    listings: int = 0

    def listing(self) -> list[str]:
        """Give the lines of the directory: the runs, and the `LATEST` alias, which is no run."""
        names = [f"{RV_URL}composite_rv_{run:%Y%m%d_%H%M}.tar" for run in sorted(self.tars)]
        return [*names, f"{RV_URL}composite_rv_LATEST.tar"]

    def install(self, monkeypatch: pytest.MonkeyPatch) -> Dwd:
        """Stand in for the network of the frames, and start from nothing held."""
        forget_everything()

        def list_files(url: str, settings: object, cache_expiry: object) -> list[str]:  # noqa: ARG001
            assert url == RV_URL
            self.listings += 1
            return self.listing()

        def run_of(url: str) -> dt.datetime:
            stamp = url.rsplit("/", 1)[-1].removeprefix("composite_rv_").removesuffix(".tar")
            return dt.datetime.strptime(stamp, "%Y%m%d_%H%M").replace(tzinfo=UTC)

        def read_range(_self: object, url: str, start: int, end: int) -> bytes:
            run = run_of(url)
            if run not in self.tars:
                raise frames_module.RadarFrameNotFoundError(url)
            self.ranged.append((run, start, end))
            return self.tars[run][start:end] if self.ranges else self.tars[run]

        def download(url: str, **_kwargs: object) -> File:
            run = run_of(url)
            if run not in self.tars:
                return File(url=url, content=FileNotFoundError(url), status=404)
            self.whole.append(run)
            return File(url=url, content=io.BytesIO(self.tars[run]), status=200)

        monkeypatch.setattr(frames_module, "list_remote_files_fsspec", list_files)
        monkeypatch.setattr(frames_module.DwdRadarFrames, "_range", read_range)
        monkeypatch.setattr(frames_module, "download_file", download)
        return self
