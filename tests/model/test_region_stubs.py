# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The regions of a network are told apart by the comparison of a selection by `region` (GH-4418).

A region asked for is compared whole after it is folded as a name is (case, accents, transliteration, the break between
words). Two regions of one list that fold to the same text would be selected together by either, so no network may have
two. Held to every stub of a station catalogue; the live lists (DWD's four networks, Geosphere, MeteoSwiss, ECCC,
Hub'Eau, FMI, Météo-France and NOAA GHCN, 12 to 164 regions each) were checked the same way when the selection was
written.
"""

from __future__ import annotations

import polars as pl
import pytest

from tests.provider.station_catalogue_stubs import STUBS, Stub
from wetterdienst.model.regions import region_keys, select_regions


@pytest.mark.parametrize("stub", STUBS, ids=lambda stub: stub.catalogue)
def test_no_two_regions_of_a_stub_fold_together_and_each_is_found_by_itself(
    stub: Stub, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Every region of the stub is its own after the folding, and a search for it finds it and no other."""
    regions = stub.build(monkeypatch).get_column("region").drop_nulls().unique().to_list()

    owners: dict[str, set[str]] = {}
    for region in regions:
        for key in dict.fromkeys(region_keys(region)):
            owners.setdefault(key, set()).add(region)
    assert {key: sorted(found) for key, found in owners.items() if len(found) > 1} == {}, stub.catalogue
    for region in regions:
        assert select_regions(regions, [region], network=stub.catalogue) == [region]
        assert select_regions(regions, [region.upper()], network=stub.catalogue) == [region]


def test_two_regions_that_fold_together_are_both_selected() -> None:
    """The reason for the test above: the folded text is the only thing that tells two regions apart."""
    both = pl.Series(["Hessen", "HESSEN"]).to_list()

    assert select_regions(both, ["hessen"], network="N") == ["HESSEN", "Hessen"]
