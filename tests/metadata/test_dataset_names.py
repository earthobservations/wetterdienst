# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests that the name of every dataset is lower case (GH-3607).

`shape_provider_frame` lower-cases the `dataset` column of every frame a provider hands the core, and the core compares
that column with the declared `dataset.name` in many places (the station and row filters of interpolate and summarize,
`core/util.py`, the units and plot prefixes of `model/result.py`; `_as_asked` and `_widen_df` lower-case it). A name
with upper case would never be equal to what the frame holds there, so the rule is held here, for every network of the
registry, and not left to a provider to remember.
"""

from __future__ import annotations

import pytest

from wetterdienst import Wetterdienst


def _dataset_names() -> list[tuple[str, str, str]]:
    """Give the ``(network, resolution, dataset name)`` of every dataset of every timeseries network of the registry."""
    names = []
    for provider, networks in Wetterdienst.registry.items():
        for network in networks:
            if Wetterdienst.is_standalone(provider, network):
                # no metadata model: dwd/radar and dwd/alerts have no datasets in this sense
                continue
            metadata = Wetterdienst.resolve(provider, network).metadata
            names.extend(
                (f"{provider}/{network}", resolution.name, dataset.name)
                for resolution in metadata
                for dataset in resolution
            )
    return names


def _upper_case(names: list[tuple[str, str, str]]) -> list[str]:
    """Give the ``network/resolution/dataset`` of the names that are not lower case."""
    return [f"{network}/{resolution}/{dataset}" for network, resolution, dataset in names if dataset != dataset.lower()]


def test_every_dataset_name_is_lower_case() -> None:
    """A dataset name has no upper case, so that it equals what `shape_provider_frame` writes to the frame."""
    names = _dataset_names()
    # the walk reaches datasets at all, so that an empty one cannot pass
    assert len({network for network, _, _ in names}) > 20
    assert _upper_case(names) == []


@pytest.mark.parametrize("dataset", ["Climate_Summary", "kl_Daily"])
def test_the_check_catches_a_name_with_upper_case(dataset: str) -> None:
    """The check names a dataset whose name has upper case, which no dataset has today."""
    assert _upper_case([("dwd/observation", "daily", dataset), ("dwd/observation", "daily", "kl")]) == [
        f"dwd/observation/daily/{dataset}"
    ]
