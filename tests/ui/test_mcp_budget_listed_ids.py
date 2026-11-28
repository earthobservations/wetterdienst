"""The search of the budget across the step of the block's ids (GH-4520).

The `metadata` block lists the ids of the stations of an answer for `MAX_LISTED_STATION_IDS` of them or fewer, so a cut
of 100 stations is bigger than one of 101 by the ids. `fits` of the search is then false below the step and true above
it for a budget that falls between the two, which a plain bisection reads as the end of what fits. These tests do not
tune a stub to steer clear of that: they sweep the size of what the block carries and the rank, and hold the search to
a count of every cut.
"""

from __future__ import annotations

import datetime as dt
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
from tests.ui.test_station_ids import MANY, _client_size, _many, _tool_call
from wetterdienst.ui import budget, restapi
from wetterdienst.ui.budget import ANSWER_BUDGET, _largest
from wetterdienst.ui.response_metadata import MAX_LISTED_STATION_IDS

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence


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

    What is promised: every search of the budget finds the largest cut that fits (held to a count of its range), and
    more rank never returns fewer stations, an answer that is whole included (GH-4036, GH-4525): a whole answer is one
    that would also fit with the note of a cut, so the next rank, cut with its note, keeps as many.

    The legend decides where the budget falls, so the sweep puts the cut on either side of the 100-id step, at it, and
    the edge of what is whole; every rank in between is asked, since the digits of the note move with the rank.
    `listing` is the stations the provider lists: 900 of which the rank asks for some, or the rank's own number.
    """
    searches = _checked_searches(monkeypatch)
    ranks = range(95, 112)
    crossed = 0
    whole_then_cut = 0
    for legend in (6_500, 7_500, 8_000, 8_500, 9_000):
        monkeypatch.setattr("wetterdienst.ui.response_metadata.quality_legend", lambda *_, n=legend: _a_legend_of(n))
        kept: list[int] = []
        for rank in ranks:
            monkeypatch.setattr(
                restapi, "get_stations", lambda rank=rank, **_kwargs: _stations_by_rank(listing or rank, rank)
            )
            kept.append(_the_stations_of_a_rank(rank, listed=listing or rank))
        assert kept == sorted(kept), (legend, kept)
        crossed += any(MAX_LISTED_STATION_IDS - 4 <= count <= MAX_LISTED_STATION_IDS + 4 for count in kept)
        # a rank that is whole, followed by one that is cut: the pair that the note's room is for
        whole_then_cut += any(
            count == rank and later < rank + 1 for count, later, rank in zip(kept, kept[1:], ranks, strict=False)
        )
    assert searches
    # the sweep does reach the step, or it holds nothing
    assert crossed >= 2
    if listing is None:
        # and the edge of what is whole, for the legends that put it in the ranks asked
        assert whole_then_cut >= 2


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


def test_the_rows_of_one_timestamp_are_cut_to_the_most_that_fits_across_the_step(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cut through a timestamp, each row is a station more: the block's ids go where the 101st comes in.

    The legends are the ones where a plain bisection stops short of the most that fits at 101 rows or fewer; the sweep
    holds that the cuts fall on both sides of the step, so that a change to the block that moves them off it fails
    here instead of leaving the test to pass without testing the step.
    """
    searches = _checked_searches(monkeypatch)
    _stub_values(monkeypatch, _values_of_many_stations(150))
    kept = []
    listed = set()
    for legend in (14_400, 14_525, 14_550, 14_700, 14_800):
        monkeypatch.setattr("wetterdienst.ui.response_metadata.quality_legend", lambda *_, n=legend: _a_legend_of(n))
        answer, size = _the_client_gets(_client_sees("values", {**_VALUES, "with_metadata": True, "format": "json"}))
        assert size <= ANSWER_BUDGET, legend
        kept.append(len({row["station_id"] for row in answer["values"]}))
        listed.add(answer["metadata"]["request"]["stations"]["ids"] is not None)
    assert len(searches) == 5
    assert listed == {True, False}, kept
    assert min(kept) <= MAX_LISTED_STATION_IDS < max(kept), kept


# --- the other answers that are whole or cut, by the same rule (GH-4525) ---------------------------------------------


def _whole_then_cut(kept: list[int], asked: Sequence[int]) -> int:
    """Count the pairs of an answer that is whole (it keeps what was asked for) and the next one that is cut."""
    return sum(count == ask and later < ask + 1 for count, later, ask in zip(kept, kept[1:], asked, strict=False))


@pytest.mark.parametrize("legend", [None, 1_000, 2_500])
def test_a_longer_window_never_keeps_fewer_timestamps_whole_answers_included(
    monkeypatch: pytest.MonkeyPatch, legend: int | None
) -> None:
    """The timestamps kept grow with the window, the one that is whole and the first that is cut (GH-4525).

    A series of `hours` timestamps whose answer only just fits has no note; the window of one more hour is cut and
    carries one, so without room for the note in the whole answer it keeps fewer timestamps than the shorter window did.
    The legend moves the edge of what is whole.
    """
    if legend is not None:
        monkeypatch.setattr("wetterdienst.ui.response_metadata.quality_legend", lambda *_: _a_legend_of(legend))
    hours = range(78, 104)
    kept = []
    for count in hours:
        _stub_values(monkeypatch, _values_of(_NOW + dt.timedelta(hours=1), count))
        arguments = {**_VALUES, "with_metadata": legend is not None}
        answer, size = _the_client_gets(_client_sees("values", arguments))
        assert size <= ANSWER_BUDGET, (legend, count)
        kept.append(len({row["timestamp"] for row in answer["values"]}))
    assert kept == sorted(kept), (legend, kept)
    # the sweep holds the edge of what is whole, or it holds nothing
    assert _whole_then_cut(kept, hours) >= 1, (legend, kept)


def test_a_longer_list_of_ids_never_keeps_fewer_stations_whole_answers_included(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`station_ids`: the stations kept grow with the ids asked for, the answer that is whole and the first cut."""
    _many(monkeypatch)
    asked = range(106, 118)
    kept = []
    for count in asked:
        result = _tool_call({"wmo_id": ",".join(MANY[:count])})
        assert not result.is_error, result.content
        assert _client_size(result) <= ANSWER_BUDGET, count
        assert result.structured_content is not None
        data = result.structured_content.get("result", result.structured_content)
        kept.append(len(data["stations"]))
    assert kept == sorted(kept), kept
    assert _whole_then_cut(kept, asked) >= 1, kept
