"""The search of the budget across the step of the block's ids (GH-4520).

The `metadata` block lists the ids of the stations of an answer for `MAX_LISTED_STATION_IDS` of them or fewer, so a cut
of 100 stations is bigger than one of 101 by the ids. `fits` of the search is then false below the step and true above
it for a budget that falls between the two, which a plain bisection reads as the end of what fits. These tests do not
tune a stub to steer clear of that: they sweep the size of what the block carries and the rank, and hold the search to
a count of every cut.
"""

from __future__ import annotations

from dataclasses import replace
from typing import TYPE_CHECKING, Any

import polars as pl
import pytest

from tests.ui.test_mcp_budget import (
    _A_RANK,
    _NOW,
    _VALUES,
    _a_legend_of,
    _client_sees,
    _compact,
    _stations_by_rank,
    _stations_of,
    _stub_values,
    _the_client_gets,
    _tool_client,
    _values_of,
)
from tests.ui.test_operations import _no_ambient_settings  # noqa: F401
from wetterdienst.ui import budget, restapi
from wetterdienst.ui.budget import ANSWER_BUDGET, _largest
from wetterdienst.ui.response_metadata import MAX_LISTED_STATION_IDS

if TYPE_CHECKING:
    from collections.abc import Callable


def _brute_force(low: int, high: int, fits: Callable[[int], bool]) -> int | None:
    """Give the largest `n` that fits by asking every `n`: what the search has to find, however it gets there."""
    return max((n for n in range(low, high + 1) if fits(n)), default=None)


# --- the search itself ----------------------------------------------------------------------------------------------


@pytest.mark.parametrize("step", [1, 2, 7, 100])
@pytest.mark.parametrize("high", [1, 2, 6, 7, 8, 99, 100, 101, 102, 150, 400])
def test_the_search_finds_the_most_that_fits_whatever_the_budget_and_the_guess(step: int, high: int) -> None:
    """A size that drops by the ids at `step` is searched exactly, for every budget and every first guess."""
    unit, ids = 40, 900

    def size(n: int) -> int:
        return unit * n + (ids if n <= step else 0)

    for budget_size in range(0, unit * (high + 2) + ids + 1, 37):
        for guess in (1, step, step + 1, high // 2 or 1, high * 3):

            def fits(n: int, budget_size: int = budget_size) -> bool:
                return size(n) <= budget_size

            found = _largest(1, high, fits, guess, listed=lambda n: n <= step)
            assert found == _brute_force(1, high, fits), (step, high, budget_size, guess)


def test_a_search_without_a_step_probes_as_it_did() -> None:
    """Where the block lists no ids, the probes are the plain bisection's: no probe is added."""
    probed: list[int] = []

    def fits(n: int) -> bool:
        probed.append(n)
        return n <= 30

    assert _largest(1, 200, fits, 25) == 30
    assert probed[0] == 25
    assert len(probed) <= 9


def test_the_large_side_of_the_step_costs_one_probe_where_nothing_fits_there() -> None:
    """A budget that falls below the step is told by the first probe above it, and the search goes on below."""
    probed: list[int] = []

    def fits(n: int) -> bool:
        probed.append(n)
        return n * 10 + (900 if n <= 100 else 0) <= 950

    assert _largest(1, 400, fits, 90, listed=lambda n: n <= 100) == 5
    assert probed[0] == 101


# --- the stations of a rank -----------------------------------------------------------------------------------------


def _checked_searches(monkeypatch: pytest.MonkeyPatch) -> list[tuple[int, int, int | None]]:
    """Hold every search of the budget to a count of its range, and give what each was asked and found."""
    real = budget._largest  # noqa: SLF001
    searches: list[tuple[int, int, int | None]] = []

    def checked(
        low: int, high: int, fits: Callable[[int], bool], guess: int, *, listed: Callable[[int], bool] | None = None
    ) -> int | None:
        found = real(low, high, fits, guess, listed=listed)
        want = _brute_force(low, high, fits)
        assert found == want, f"the search of {low}..{high} found {found}, the largest that fits is {want}"
        searches.append((low, high, found))
        return found

    monkeypatch.setattr(budget, "_largest", checked)
    return searches


def _the_stations_of_a_rank(rank: int, *, listed: int) -> int:
    """Ask the tool for a rank of `listed` stations, and count the stations of the answer that is within the budget."""
    response = _tool_client().get("/api/stations", params={**_A_RANK, "rank": rank, "with_metadata": True})
    assert response.status_code == 200, response.text
    assert _compact(response.text) <= ANSWER_BUDGET
    body = response.json()
    assert "quality" in body["metadata"], (rank, listed)
    return len({station["station_id"] for station in body["stations"]})


@pytest.mark.parametrize("listing", [900, None])
def test_a_rank_is_cut_to_the_most_that_fits_whatever_the_size_of_the_block(
    monkeypatch: pytest.MonkeyPatch, listing: int | None
) -> None:
    """Sweep the legend and the rank: the stations kept are the largest cut that fits, and more rank is never fewer.

    The legend decides where the budget falls, so the sweep puts the cut on either side of the 100-id step, and at it;
    the rank decides the probes, through the digits of its note. `listing` is the stations the provider lists: 900
    of which the rank asks for some, or the rank's own number of them.
    """
    searches = _checked_searches(monkeypatch)
    ranks = (99, 100, 101, 102, 104, 108, 120)
    crossed = 0
    for legend in (6_500, 7_500, 8_000, 8_500, 9_000):
        monkeypatch.setattr("wetterdienst.ui.response_metadata.quality_legend", lambda *_, n=legend: _a_legend_of(n))
        kept: list[int] = []
        for rank in ranks:
            monkeypatch.setattr(
                restapi, "get_stations", lambda rank=rank, **_kwargs: _stations_by_rank(listing or rank, rank)
            )
            kept.append(_the_stations_of_a_rank(rank, listed=listing or rank))
        # an answer that is whole carries no note, and the one that follows may be cut to less than it: only the ranks
        # that are cut are held to the promise of GH-4036
        cut = [count for count, rank in zip(kept, ranks, strict=True) if count < rank]
        assert cut == sorted(cut), (legend, kept)
        crossed += any(MAX_LISTED_STATION_IDS - 4 <= count <= MAX_LISTED_STATION_IDS + 4 for count in cut)
    assert searches
    # the sweep does reach the step, or it holds nothing
    assert crossed >= 2


# --- the rows of an answer ----------------------------------------------------------------------------------------


def _values_of_many_stations(count: int) -> Any:  # noqa: ANN401
    """Give one timestamp of `count` stations: its rows are cut one by one, and each row is a station more."""
    stations = _stations_of(count)
    rows = [
        {
            "station_id": f"{i:05d}",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "timestamp": _NOW,
            "value": 10.0 + i / 10,
            "quality_flags": None,
        }
        for i in range(count)
    ]
    frame = pl.DataFrame(rows, schema_overrides={"timestamp": pl.Datetime(time_zone="UTC")}, orient="row")
    return replace(_values_of(_NOW, 1), df=frame, stations=stations)


@pytest.mark.parametrize("legend", [14_400, 14_525, 14_550, 14_700, 14_800])
def test_the_rows_of_one_timestamp_are_cut_to_the_most_that_fits_across_the_step(
    monkeypatch: pytest.MonkeyPatch, legend: int
) -> None:
    """Cut through a timestamp, each row is a station more: the block's ids go where the 101st comes in."""
    searches = _checked_searches(monkeypatch)
    monkeypatch.setattr("wetterdienst.ui.response_metadata.quality_legend", lambda *_: _a_legend_of(legend))
    _stub_values(monkeypatch, _values_of_many_stations(150))

    _, size = _the_client_gets(_client_sees("values", {**_VALUES, "with_metadata": True, "format": "json"}))

    assert size <= ANSWER_BUDGET
    assert searches
