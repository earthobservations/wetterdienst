# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The legend of the `quality_flags` tokens says what each network's readers write (GH-3060)."""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

import wetterdienst
from tests.provider.value_stubs import STUBS, ValueStub
from wetterdienst import Wetterdienst
from wetterdienst.model.quality_legend import LEGENDS, RAW, quality_legend

PROVIDER_DIR = Path(wetterdienst.__file__).parent / "provider"

#: the networks whose `quality_flags` are not built by `join_quality_flags`, and where they come from instead
NOT_JOINED = {
    "eaufrance/hubeau": "Hub'Eau's code_qualification_obs, written as a plain whole number",
    "lhmt/observation": "the service publishes no flag",
    "wsv/pegel": "the service publishes no flag",
}


#: what a reader names when a plausibility check judges its values: the rules of `model/quality_flags.py`, which a
#: `raw` text turns into the tokens `suspect` and `rejected`, written before `raw` (GH-3676)
JUDGEMENTS = {"OutOfRange", "NoReading", "Floor", "station_pressure_range"}


def _kinds_written() -> dict[str, set[str | None]]:
    """Read from the readers what each network passes to `join_quality_flags`: `None` for a plain flag, else a kind.

    A network whose readers declare a judgement writes the kinds `suspect` and `rejected` as well, though no reader
    passes them: `join_quality_flags` writes them for the `raw` text of a rule.
    """
    found: dict[str, set[str | None]] = {}
    for path in sorted(PROVIDER_DIR.rglob("*.py")):
        parts = path.relative_to(PROVIDER_DIR).parts
        if len(parts) < 3:
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            is_call = isinstance(node, ast.Call) and getattr(node.func, "id", getattr(node.func, "attr", None))
            if is_call != "join_quality_flags":
                continue
            assert isinstance(node, ast.Call)
            kinds = found.setdefault(f"{parts[0]}/{parts[1]}", set())
            if node.args and not (isinstance(node.args[0], ast.Constant) and node.args[0].value is None):
                kinds.add(None)
            kinds.update(keyword.arg for keyword in node.keywords)
        if any(isinstance(node, ast.Call) and getattr(node.func, "id", None) in JUDGEMENTS for node in ast.walk(tree)):
            found.setdefault(f"{parts[0]}/{parts[1]}", set()).update({"suspect", "rejected"})
    return found


def test_every_network_has_a_legend_or_says_it_has_no_flag() -> None:
    """A network added to the library takes a stand: the kinds of its tokens, or an empty legend."""
    registered = {
        f"{provider}/{network}"
        for provider, networks in Wetterdienst.registry.items()
        for network in networks
        if not Wetterdienst.is_standalone(provider, network)
    }
    assert registered - set(LEGENDS) == set(), "add the network to LEGENDS in model/quality_legend.py"
    assert set(LEGENDS) - registered == set(), "LEGENDS names a network that is not registered"


def test_the_kinds_the_readers_write_are_the_kinds_the_legend_tells() -> None:
    """A reader that writes a further kind, or stops writing one, fails until the legend follows."""
    written = _kinds_written()
    assert written, "the search found no reader"
    for network, legend in LEGENDS.items():
        if network in NOT_JOINED:
            assert network not in written, f"{network} builds its flags with `join_quality_flags` now: {NOT_JOINED}"
            continue
        assert {kind.kind for kind in legend} == written[network], network


def test_a_network_not_built_by_join_declares_what_it_writes() -> None:
    """The networks that write their flags themselves are named, so that they cannot be forgotten."""
    assert set(NOT_JOINED) <= set(LEGENDS)
    for network, reason in NOT_JOINED.items():
        legend = LEGENDS[network]
        plain = [kind for kind in legend if kind.kind is None]
        assert len(plain) == (0 if "no flag" in reason else 1), network
        assert len(legend) == len(plain), network


@pytest.mark.parametrize("network", sorted(LEGENDS))
def test_the_legend_is_in_the_order_of_the_column(network: str) -> None:
    """The source's own flag comes first, a kind is written with its prefix, and `raw` is the last token."""
    legend = quality_legend(*network.split("/"))
    kinds = [kind.kind for kind in legend]
    assert len(kinds) == len(set(kinds)), "a kind is told once"
    assert None not in kinds or kinds[0] is None, "the source's own flag comes first"
    for kind in legend:
        assert kind.written.startswith(f"{kind.kind}:") if kind.kind else kind.written == "<code>", kind
        assert kind.meaning
        if kind.codes is not None:
            codes = [code.code for code in kind.codes]
            assert codes
            assert len(codes) == len(set(codes)), f"{network}: a code is told once"
    if "raw" in kinds:
        assert kinds[-1] == "raw"
        assert legend[-1] == RAW


def test_a_legend_is_a_copy() -> None:
    """The legend a caller gets can be changed without changing the next caller's."""
    quality_legend("dwd", "observation").clear()
    assert quality_legend("dwd", "observation")


@pytest.mark.parametrize("stub", STUBS, ids=lambda stub: stub.provider)
def test_the_tokens_a_stubbed_source_gets_are_told_by_the_legend(
    stub: ValueStub, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Run the reader on its stub and find every kind of token it writes in the legend of its network."""
    network = stub.provider.split(" ")[0]
    told = {kind.kind for kind in quality_legend(*network.split("/"))}
    df = stub.build(monkeypatch, drop_nulls=False)
    tokens = (
        df.get_column("quality_flags")
        .drop_nulls()
        .str.split(",")
        .explode(empty_as_null=False)
        .drop_nulls()
        .unique()
        .to_list()
        if "quality_flags" in df.columns
        else []
    )
    written = {token.split(":", 1)[0] if ":" in token else None for token in tokens}
    assert written <= told, f"{network}: tokens of kinds {sorted(map(str, written - told))} are not in the legend"
