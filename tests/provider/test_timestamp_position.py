# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A dataset declared `start` on the library's word is one whose reader stamps the first day (GH-3134).

`docs/data/time_reference.md` is the evidence of a position the provider states, and `tests/test_docs.py` holds it to
the metadata. A stamp the reader builds itself has no such row: `LIBRARY_BUILT_START` lists those datasets, and the
check in `conftest.py` holds every frame a test builds for one to the claim. What is held here is that the check has
something to see: that the frame it judges is not one that no test ever builds, and that it can fail.
"""

from __future__ import annotations

import datetime as dt

import polars as pl
import pytest

from tests.provider import frames
from tests.provider.timestamps import LIBRARY_BUILT_START, library_built_problem
from wetterdienst import Wetterdienst

UTC = dt.UTC


def _frame(*stamps: dt.datetime) -> pl.DataFrame:
    return pl.DataFrame({"timestamp": list(stamps)}, schema={"timestamp": pl.Datetime("us", "UTC")})


def test_a_stamp_on_the_first_day_of_its_period_is_no_problem() -> None:
    """Test that midnight on the 1st passes for a month, and 1 January for a year."""
    assert (
        library_built_problem(
            _frame(dt.datetime(2024, 3, 1, tzinfo=UTC), dt.datetime(2024, 4, 1, tzinfo=UTC)), "monthly"
        )
        is None
    )
    assert library_built_problem(_frame(dt.datetime(2024, 1, 1, tzinfo=UTC)), "annual") is None
    assert library_built_problem(_frame(), "annual") is None


@pytest.mark.parametrize(
    ("resolution", "stamp"),
    [
        ("monthly", dt.datetime(2024, 3, 2, tzinfo=UTC)),
        ("monthly", dt.datetime(2024, 3, 1, 6, tzinfo=UTC)),
        ("monthly", dt.datetime(2024, 3, 31, tzinfo=UTC)),
        ("annual", dt.datetime(2024, 2, 1, tzinfo=UTC)),
        ("annual", dt.datetime(2024, 12, 31, tzinfo=UTC)),
    ],
)
def test_a_stamp_inside_the_period_is_a_problem(resolution: str, stamp: dt.datetime) -> None:
    """Test that the end of a period, its middle and a time of day after its start are all found."""
    assert library_built_problem(_frame(stamp), resolution) is not None


def test_every_entry_names_datasets_the_network_declares() -> None:
    """Test that each entry is a monthly or annual resolution, and its datasets are in it."""
    errors = []
    for (provider, network, resolution), (datasets, where) in LIBRARY_BUILT_START.items():
        metadata = Wetterdienst.resolve(provider, network).metadata
        if resolution not in ("monthly", "annual"):
            errors.append(f"{provider}/{network}/{resolution}: the check knows a month and a year only")
            continue
        declared = {dataset.name for dataset in metadata[resolution]}
        errors.extend(
            f"{provider}/{network}/{resolution}: no dataset {name!r}" for name in sorted(set(datasets or ()) - declared)
        )
        if not where:
            errors.append(f"{provider}/{network}/{resolution}: says nothing of where the reader builds the stamp")
    assert not errors, "\n".join(errors)


def test_a_test_builds_a_frame_for_every_entry() -> None:
    """Test that the frame snapshot holds a values frame of each entry, so the check of `conftest.py` sees one.

    An entry holds for a dataset or all of a resolution, and the reader that builds the stamp is the same for all of
    them, so one dataset's frame is evidence for its resolution; an entry that names datasets needs one of those.
    """
    built = {entry[0] for entries in frames.load()["values"].values() for entry in entries}
    errors = []
    for (provider, network, resolution), (datasets, _) in LIBRARY_BUILT_START.items():
        request = Wetterdienst.resolve(provider, network)
        names = datasets or tuple(dataset.name for dataset in request.metadata[resolution])
        labels = {f"{request._values.__name__} {resolution}/{name}" for name in names}  # noqa: SLF001
        if not labels & built:
            errors.append(f"{provider}/{network}/{resolution}: no offline test builds {sorted(labels)[:3]}...")
    assert not errors, "\n".join(errors)
