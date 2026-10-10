# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The stations a provider's reader gives for a stub of its catalogue break none of the catalogue rules (GH-2616)."""

import pytest

from tests.provider.station_catalogue import assert_sound
from tests.provider.station_catalogue_stubs import STUBS, Stub


@pytest.mark.parametrize("stub", STUBS, ids=lambda stub: stub.catalogue)
def test_a_stub_catalogue_is_sound(stub: Stub, monkeypatch: pytest.MonkeyPatch) -> None:
    """Hold the stations of every stubbed catalogue to the rules, naming the provider, station and rule that fails."""
    assert_sound(stub.build(monkeypatch), stub.catalogue, bbox=stub.bbox, accepted=stub.accepted, now=stub.now)
