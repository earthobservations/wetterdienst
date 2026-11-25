# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What a `filter` holds while it reads long stations is bounded by the rows matched, and by the limit (GH-4436).

Thirty stations of 100,000 daily readings are read in a process of their own (`filter_read_probe.py`: the peak of a
process never goes down), and the growth of its peak memory is what each way of holding them comes to. Holding every
reading is the reference (about 840 MB where this was written); a filter that matches nothing lets each station go as
it is read, a limit stops the walk at the third station, and `max_rows` keeps what the answer can hold.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

_PROBE = Path(__file__).with_name("filter_read_probe.py")
_STATIONS, _READINGS = 30, 100_000


def _run(text: str, *, held: int = 0, max_rows: int = 0) -> dict[str, Any]:
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-I", str(_PROBE), str(_STATIONS), str(_READINGS), text, str(held), str(max_rows)],
        capture_output=True,
        text=True,
        check=False,
        timeout=250,
    )
    assert done.returncode == 0, done.stderr[-2000:]
    return json.loads(done.stdout.splitlines()[-1])


@pytest.fixture(scope="module")
def everything() -> dict[str, Any]:
    """Hold every reading: the reference that the others are measured against."""
    result = _run("value<=20")
    assert result["rows"] == _STATIONS * _READINGS
    return result


def test_a_filter_that_matches_nothing_holds_no_more_than_the_station_in_hand(everything: dict[str, Any]) -> None:
    """The readings that do not match are let go as each station is read, so a long walk does not pile up."""
    result = _run("value>=100")
    assert result["outcome"] == "answered"
    assert result["rows"] == 0
    assert result["stations_read"] == _STATIONS
    assert result["growth_mb"] < 0.5 * everything["growth_mb"], (result, everything)


def test_a_limit_stops_the_walk_where_the_rows_held_cross_it_and_so_bounds_the_memory(
    everything: dict[str, Any],
) -> None:
    """With 250,000 rows allowed the third station (300,000) ends the walk: 27 stations are never read."""
    result = _run("value<=20", held=250_000)
    assert result["outcome"] == "refused"
    assert result["rows"] == 3 * _READINGS
    assert result["stations_read"] == 3
    assert result["growth_mb"] < 0.5 * everything["growth_mb"], (result, everything)


def test_max_rows_keeps_what_is_held_to_the_rows_of_the_answer(everything: dict[str, Any]) -> None:
    """Everything matches and 1,000 rows are asked for: all stations are read, 1,000 rows are held."""
    result = _run("value<=20", held=250_000, max_rows=1000)
    assert result["outcome"] == "answered"
    assert result["rows"] == 1000
    assert result["stations_read"] == _STATIONS
    assert result["growth_mb"] < 0.5 * everything["growth_mb"], (result, everything)
