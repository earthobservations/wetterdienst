# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A source's way of writing a missing value leaves no sentinel in the values a provider returns (GH-2615)."""

import polars as pl
import pytest

from tests.provider.physical_ranges import out_of_range
from tests.provider.value_stubs import NO_STUB, STUBS, ValueStub
from wetterdienst import Wetterdienst


def _carried(df: pl.DataFrame, stub: ValueStub) -> list[tuple[str, float]]:
    """Give the sentinels of the stub that the output holds, as (parameter, value)."""
    parameter = df.get_column("parameter").cast(pl.String)
    return [
        (name, value)
        for name, value in stub.sentinels
        if not df.filter((parameter == name) & (pl.col("value") == value)).is_empty()
    ]


@pytest.mark.parametrize("stub", STUBS, ids=lambda stub: stub.provider)
def test_a_stub_source_leaves_no_sentinel_in_the_values(
    stub: ValueStub,
    monkeypatch: pytest.MonkeyPatch,
    physical_range_findings: list[str],
) -> None:
    """Serve the way a source writes a missing value through the provider's reader, and look for it in the output.

    A provider that is known to let it through is held to that: the sentinel has to be there, so that a fix fails
    this test and takes the `leak` out of the stub with it.
    """
    df = stub.build(monkeypatch)

    parameter, value = stub.reading
    arrived = df.filter(pl.col("parameter").cast(pl.String) == parameter).get_column("value").to_list()
    assert value in arrived, f"{stub.provider}: the reading {parameter}={value} did not arrive, got {arrived}"
    if stub.empty_at:
        at = df.filter(pl.col("timestamp") == stub.empty_at)
        assert at.is_empty(), f"{stub.provider}: {at.height} values at {stub.empty_at}, where the source has none"
    carried = _carried(df, stub)
    # what is outside the range of its parameter, less the sentinels the stub names: a number that is neither
    # a reading nor one of them is a sentinel the stub does not know of yet
    outside = out_of_range(df)
    unnamed = [
        (str(row["parameter"]), row["value"])
        for row in outside.to_dicts()
        if (str(row["parameter"]), row["value"]) not in stub.sentinels
    ]
    assert unnamed == [], f"{stub.provider}: values outside the range of their parameter, not named: {unnamed[:5]}"
    if stub.leak:
        # all of them: a fix that is only partial changes what the stub holds, and the stub is to say so
        assert carried == list(stub.sentinels), (
            f"{stub.provider}: {stub.leak} is fixed for {sorted(set(stub.sentinels) - set(carried))}, "
            "remove it from `sentinels`, and `leak` when none is left"
        )
        # the range check has seen what it can of the leak too
        physical_range_findings.clear()
        return
    assert carried == [], f"{stub.provider}: the sentinel {carried} reached the output"


def test_every_network_has_a_stub_or_a_reason() -> None:
    """A network added to the library takes a stand: a stub of its source, or the reason it has none yet."""
    registered = {
        f"{provider}/{network}" for provider, networks in Wetterdienst.registry.items() for network in networks
    }
    stubbed = {stub.provider.split(" ")[0] for stub in STUBS}
    assert registered - stubbed - set(NO_STUB) == set(), "add a stub to STUBS, or a reason to NO_STUB"
    assert set(NO_STUB) - registered == set(), "NO_STUB names a network that is not registered"
    assert set(NO_STUB) & stubbed == set(), "NO_STUB names a network that has a stub"
    assert stubbed - registered == set()
