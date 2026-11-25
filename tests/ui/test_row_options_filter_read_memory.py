# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What a `filter` holds while it reads long stations is bounded by the rows matched, and by the limit (GH-4436).

Thirty stations of 20,000 daily readings are read, and what `all` holds after each station is what its frames occupy
(`estimated_size`, the same on every system: a peak of the process is not, and never goes down). Holding every reading
is the reference; a filter that matches nothing lets each station go as it is read, a limit stops the walk at the third
station, and `max_rows` keeps what the answer can hold.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any, NamedTuple

import polars as pl
import pytest

from wetterdienst.model.row_selection import RowsOverLimitError
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationValues
from wetterdienst.settings import Settings

if TYPE_CHECKING:
    from collections.abc import Callable

_STATIONS, _READINGS = 30, 20_000
_START = dt.datetime(1900, 1, 1, tzinfo=dt.UTC)


class Held(NamedTuple):
    """What a walk held at most (bytes), after how many stations, and what it answered."""

    peak: int
    stations_read: int
    rows: int
    refused: bool


@pytest.fixture
def walk(monkeypatch: pytest.MonkeyPatch) -> Callable[..., Held]:
    """Give a function that reads the stations with the options and says what was held, at most, as they were read."""
    ids = [f"{number:05d}" for number in range(1, _STATIONS + 1)]
    stations = pl.DataFrame(
        {
            "resolution": ["daily"] * _STATIONS,
            "dataset": ["climate_summary"] * _STATIONS,
            "station_id": ids,
            "start_timestamp": [_START] * _STATIONS,
            "end_timestamp": [None] * _STATIONS,
            "latitude": [53.0] * _STATIONS,
            "longitude": [10.0] * _STATIONS,
            "elevation": [10.0] * _STATIONS,
            "name": ids,
            "state": ["Hamburg"] * _STATIONS,
        },
        schema_overrides={"end_timestamp": pl.Datetime(time_zone="UTC")},
    )
    monkeypatch.setattr(DwdObservationRequest, "_all", lambda _self: stations.lazy())
    read: list[str] = []

    def collect(self: object, station_id: str, parameter_or_dataset: Any) -> pl.DataFrame:  # noqa: ANN401, ARG001
        dataset = getattr(parameter_or_dataset, "dataset", parameter_or_dataset)
        name = next(p.name_original for p in dataset if p.name == "temperature_air_min_2m")
        read.append(station_id)
        return pl.DataFrame(
            {
                "timestamp": pl.datetime_range(
                    _START, _START + dt.timedelta(days=_READINGS - 1), "1d", time_zone="UTC", eager=True
                ),
                "parameter": [name] * _READINGS,
                "value": [float(day % 61) / 2 - 10 for day in range(_READINGS)],
                "quality_flags": ["1"] * _READINGS,
                "resolution": ["daily"] * _READINGS,
                "dataset": [dataset.name] * _READINGS,
            },
            schema_overrides={"value": pl.Float64},
        )

    monkeypatch.setattr(DwdObservationValues, "_collect_station_parameter_or_dataset", collect)
    sizes: list[int] = []
    hold = TimeseriesValues._hold  # noqa: SLF001

    def measuring(self: TimeseriesValues, selection: Any, rows: int, cells: int, data: list[pl.DataFrame]) -> Any:  # noqa: ANN401
        sizes.append(sum(frame.estimated_size() for frame in data))
        return hold(self, selection, rows, cells, data)

    monkeypatch.setattr(TimeseriesValues, "_hold", measuring)

    def run(text: str, *, limit: int | None = None, max_rows: int | None = None) -> Held:
        sizes.clear()
        read.clear()
        request = DwdObservationRequest(
            parameters="daily/climate_summary/temperature_air_min_2m",
            start=_START,
            end=_START + dt.timedelta(days=_READINGS),
            settings=Settings(cache_disable=True),
        ).all()
        reader = request.values()
        reader._held_rows_limit = limit  # noqa: SLF001
        options: dict[str, Any] = {"filter": text, **({"max_rows": max_rows} if max_rows else {})}
        try:
            rows, refused = reader.all(**options).df.height, False
        except RowsOverLimitError as error:
            rows, refused = error.rows, True
        return Held(max(sizes, default=0), len(read), rows, refused)

    return run


def test_a_filter_that_matches_nothing_holds_nothing_while_it_reads_every_station(walk: Callable[..., Held]) -> None:
    """The readings that do not match are let go as each station is read, so a long walk does not pile up."""
    everything = walk("value<=20")
    assert everything.rows == _STATIONS * _READINGS
    # the reference is what a station comes to, thirty times over: a probe that measured nothing would pass the rest
    assert everything.peak > 5_000_000
    nothing = walk("value>=100")
    assert (nothing.rows, nothing.stations_read, nothing.refused) == (0, _STATIONS, False)
    assert nothing.peak < everything.peak / 100


def test_a_limit_stops_the_walk_where_the_rows_held_cross_it(walk: Callable[..., Held]) -> None:
    """With 50,000 rows allowed the third station (60,000) ends the walk: 27 stations are never read."""
    everything = walk("value<=20")
    stopped = walk("value<=20", limit=50_000)
    assert stopped.refused
    assert (stopped.rows, stopped.stations_read) == (3 * _READINGS, 3)
    assert stopped.peak <= 3 * everything.peak / _STATIONS * 1.01
    # the limit is the rows: with one station more of room the walk goes one station further
    assert walk("value<=20", limit=60_000).stations_read == 4


def test_max_rows_keeps_what_is_held_to_the_rows_of_the_answer(walk: Callable[..., Held]) -> None:
    """Everything matches and 1,000 rows are asked for: all stations are read, 1,000 rows are held."""
    everything = walk("value<=20")
    capped = walk("value<=20", limit=50_000, max_rows=1000)
    assert (capped.rows, capped.stations_read, capped.refused) == (1000, _STATIONS, False)
    assert capped.peak < everything.peak / 100
