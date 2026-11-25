# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A request with `first` stops its work when its answer has timed out, and holds no rows after it (GH-4411, GH-4429).

`test_work_stops_at_timeout.py` holds the walk of a plain `values` to the timeout. A request that chooses rows
holds more than the walk: each station's rows, the rows chosen again while the groups span stations, and the last
choice and ordering of the whole. What is held here: the stations are read to the one in hand and no more, the place
of the cap is given back, the choice is not made once more after the last station, and every frame the walk held is
freed without a collection of cycles.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import gc
import threading
import weakref
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

import polars as pl
import pytest

from tests.ui.test_operations import _HANG, _async_client, _no_ambient_settings, _until  # noqa: F401
from wetterdienst.model.row_selection import RowSelection
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationValues

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

    from wetterdienst.model.result import ValuesResult

pytestmark = pytest.mark.usefixtures("_no_ambient_settings")

STATIONS = [f"{index:05d}" for index in range(12)]
PARAMETERS = "daily/climate_summary/temperature_air_mean_2m"
#: per-station groups, and groups that span stations: both are walked, held and chosen again in their own way
CHOICES = [
    pytest.param({"sort": "value", "first": "2"}, id="per station"),
    pytest.param({"sort": "-value", "first": "2", "by": "year"}, id="spanning"),
    pytest.param({"sort": "value", "first": "2", "max_rows": "3"}, id="cut"),
]


class Walk:
    """A DWD observation whose stations are read in order, each held until the test lets it go, and what it held."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        """Stand the provider in for the DWD observations, with a cache directory of its own."""
        self.read: list[str] = []
        self.ended = 0
        self.completed = 0
        self.frames: list[weakref.ref[Any]] = []
        self.finishes = 0
        self.lock = threading.Lock()
        self._holds: dict[str, threading.Event] = {}
        walk = self

        class Values(DwdObservationValues):
            def query(self, **rows: Any) -> Iterator[ValuesResult]:  # noqa: ANN401
                try:
                    for result in super().query(**rows):
                        with walk.lock:
                            walk.frames.append(weakref.ref(result.df))
                        yield result
                    with walk.lock:
                        walk.completed += 1
                finally:
                    with walk.lock:
                        walk.ended += 1

            def _collect_station_parameter_or_dataset(
                self,
                station_id: str,
                parameter_or_dataset: object,  # noqa: ARG002
            ) -> pl.DataFrame:
                with walk.lock:
                    walk.read.append(station_id)
                hold = walk._holds.get(station_id)
                if hold is not None:
                    hold.wait(_HANG)
                index = int(station_id)
                days = [dt.datetime(2000, 1, day, tzinfo=ZoneInfo("UTC")) for day in range(1, 6)]
                return pl.DataFrame(
                    {
                        "timestamp": days,
                        "parameter": ["tmk"] * 5,
                        # a tenth of a degree, in the unit of the source: distinct values, with ties between stations
                        "value": [(index * 3 + day) % 7 / 10 for day in range(5)],
                    },
                    schema_overrides={"timestamp": pl.Datetime("us", "UTC")},
                )

        size = len(STATIONS)
        utc = ZoneInfo("UTC")
        stations = pl.DataFrame(
            {
                "resolution": ["daily"] * size,
                "dataset": ["climate_summary"] * size,
                "station_id": STATIONS,
                "start_timestamp": [dt.datetime(1900, 1, 1, tzinfo=utc)] * size,
                "end_timestamp": [dt.datetime(2030, 1, 1, tzinfo=utc)] * size,
                "latitude": [50.0 + index / 10 for index in range(size)],
                "longitude": [8.0 + index / 10 for index in range(size)],
                "elevation": [100.0] * size,
                "name": STATIONS,
                "region": ["x"] * size,
            }
        )
        monkeypatch.setattr(DwdObservationRequest, "_all", lambda self: stations.lazy())  # noqa: ARG005
        monkeypatch.setattr(DwdObservationRequest, "_values", Values)
        monkeypatch.setenv("WD_CACHE_DIR", str(tmp_path / "cache"))
        # every station is chosen again as it comes where the groups span stations
        monkeypatch.setattr(TimeseriesValues, "_COMPACT_CELLS", 1)
        finish = RowSelection.finish

        def counting(self: RowSelection, frames: Any, schema: Any = None) -> pl.DataFrame:  # noqa: ANN401
            with walk.lock:
                walk.finishes += 1
            return finish(self, frames, schema)

        monkeypatch.setattr(RowSelection, "finish", counting)

    def hold(self, station: str) -> None:
        """Have the collection of `station` wait until `release`."""
        self._holds[station] = threading.Event()

    def release(self) -> None:
        """Let every held station go."""
        for event in self._holds.values():
            event.set()

    def snapshot(self) -> list[str]:
        """Give the stations read so far."""
        with self.lock:
            return list(self.read)

    async def until_ended(self) -> None:
        """Wait until the walk is over: its thread is done and its place of the cap is given back."""
        await _until(lambda: self.ended >= 1, "a walk that ended")


@pytest.fixture
def walk(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Walk]:
    """Give the walk, and let every held station go at the end so that no thread outlives the test."""
    provider = Walk(monkeypatch, tmp_path)
    try:
        yield provider
    finally:
        provider.release()


@pytest.fixture
def no_collector() -> Iterator[None]:
    """Switch the collector of cycles off, so that only what is freed by counting references is freed."""
    gc.collect()
    gc.disable()
    try:
        yield
    finally:
        gc.enable()


def _params(stations: list[str], **more: str) -> dict[str, str]:
    return {
        "provider": "dwd",
        "network": "observation",
        "parameters": PARAMETERS,
        "stations": ",".join(stations),
        "timestamp": "2000-01-01/2000-01-10",
        **more,
    }


async def _served(client: Any) -> int:  # noqa: ANN401
    """Ask for one station until the request is no longer refused for want of a place; give its status."""
    import time  # noqa: PLC0415

    deadline = time.monotonic() + _HANG
    while (status := (await client.get("/api/v1/values", params=_params(STATIONS[:1]))).status_code) == 503:
        assert time.monotonic() < deadline, "the place was not given back"
        await asyncio.sleep(0.01)
    return status


async def _time_out(
    walk: Walk, monkeypatch: pytest.MonkeyPatch, choice: dict[str, str], *, hold: str
) -> tuple[list[str], int]:
    """Time a request that chooses rows out in `hold`, let the walk go; give the stations read then, the walks done."""
    monkeypatch.setenv("WD_RESTAPI_MAX_CONCURRENT", "1")
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "0.3")
    walk.hold(hold)
    async with _async_client() as client:
        timed_out = await client.get("/api/v1/values", params=_params(STATIONS[:8], **choice))
        assert timed_out.status_code == 504, timed_out.text
        at_timeout = walk.snapshot()
        monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "60")
        walk.release()
        await walk.until_ended()
        completed = walk.completed
        # the one place of the cap is free again: the next request is served
        assert await _served(client) == 200
    return at_timeout, completed


@pytest.mark.parametrize("choice", CHOICES)
def test_a_request_that_chooses_rows_stops_at_the_station_in_hand(
    walk: Walk, monkeypatch: pytest.MonkeyPatch, choice: dict[str, str]
) -> None:
    """The stations after the one in hand are not read, whether the groups stay in a station, span them, or are cut."""
    at_timeout, completed = asyncio.run(_time_out(walk, monkeypatch, choice, hold="00001"))
    final = walk.snapshot()
    assert final[: len(at_timeout)] == at_timeout
    # the station in hand at most is read after the answer
    assert final[len(at_timeout) + 1 :] == []
    assert len(final) < 8
    assert completed == 0


def test_the_choice_of_the_whole_is_not_made_after_the_last_station_when_the_answer_is_gone(
    walk: Walk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """One long station times out in it: the rows chosen are not ordered and cut for nobody (`finish` is not called)."""
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "0.3")
    walk.hold("00000")

    async def run() -> int:
        async with _async_client() as client:
            response = await client.get("/api/v1/values", params=_params(STATIONS[:1], sort="value", first="2"))
            monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "60")
            walk.release()
            await walk.until_ended()
            return response.status_code

    assert asyncio.run(run()) == 504
    assert walk.completed == 0
    assert walk.finishes == 0


def test_the_choice_again_of_a_walk_that_timed_out_is_not_made_for_the_stations_after_the_one_in_hand(
    walk: Walk, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Spanning groups are chosen again at each station: at most the station in hand makes one after the timeout."""
    monkeypatch.setenv("WD_RESTAPI_MAX_CONCURRENT", "1")
    # long enough for three stations to be read and chosen over on a machine that runs the whole suite on every core: at
    # 0.3 s two were, and the test failed there (GH-4440); the walk is held at the fourth, so a longer wait costs time only
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "4")
    walk.hold("00003")
    choice = {"sort": "-value", "first": "2", "by": "year"}

    async def run() -> int:
        async with _async_client() as client:
            assert (await client.get("/api/v1/values", params=_params(STATIONS[:10], **choice))).status_code == 504
            at_timeout = walk.finishes
            monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "60")
            walk.release()
            await walk.until_ended()
            return at_timeout

    at_timeout = asyncio.run(run())
    # three stations were chosen over when the answer went; the one in hand makes one more, and nothing after it does
    assert at_timeout == 3
    assert walk.finishes <= at_timeout + 1
    assert walk.finishes < 10


@pytest.mark.usefixtures("no_collector")
@pytest.mark.parametrize("choice", CHOICES)
def test_the_rows_a_walk_held_are_freed_without_a_collection(
    walk: Walk, monkeypatch: pytest.MonkeyPatch, choice: dict[str, str]
) -> None:
    """Every frame the walk handed over, and the rows chosen again from them, are gone once its place is given back."""
    asyncio.run(_time_out(walk, monkeypatch, choice, hold="00002"))
    assert walk.frames, "the walk handed over nothing"
    alive = [frame for frame in walk.frames if frame() is not None]
    assert alive == []
