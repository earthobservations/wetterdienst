# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The page on the plausibility checks says what the readers do (GH-3676).

`wetterdienst.model.plausibility.COVERAGE` names the networks and datasets each check runs on, and
`docs/data/plausibility.md` has them as a table. Three things are held to one another so that none can drift: what the
values core is told to judge (the tables of `model/judge.py` and `model/plausibility_ranges.py`, and the rules a
provider hands it: `Bound`, `Beside`, `StuckPeriod`), `COVERAGE`, and the table.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

import wetterdienst
from tests.provider.value_stubs import STUBS
from wetterdienst import Wetterdienst
from wetterdienst.model.judge import CONSTANT_RUNS, ELEVATION_NETWORKS, FLOORS, RUNS, plan_for
from wetterdienst.model.plausibility import CHECKS, COVERAGE, Plausibility
from wetterdienst.model.plausibility_ranges import SCOPE

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from wetterdienst.model.metadata import DatasetModel

ROOT = Path(__file__).parent.parent
PAGE = ROOT / "docs" / "data" / "plausibility.md"
PROVIDER_DIR = Path(wetterdienst.__file__).parent / "provider"

#: the rule a provider hands the core, and the check it belongs to
_PROVIDER_RULES = {"Bound": "range", "Beside": "consistency", "StuckPeriod": "stuck"}


def _declared() -> dict[str, set[str]]:
    """Read which checks the core judges each network with: `{check: {provider/network}}`.

    From the tables the core reads (the scope of the ranges, the constants, the runs, the floors) and from the rules a
    provider hands it.
    """
    found: dict[str, set[str]] = {check: set() for check in CHECKS}
    found["range"] |= set(SCOPE)
    found["elevation"] |= set(ELEVATION_NETWORKS)
    found["stuck"] |= set(CONSTANT_RUNS) | set(RUNS)
    found["floor"] |= set(FLOORS)
    for path in sorted(PROVIDER_DIR.rglob("*.py")):
        parts = path.relative_to(PROVIDER_DIR).parts
        if len(parts) < 3:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            name = getattr(getattr(node, "func", None), "id", None) if isinstance(node, ast.Call) else None
            if name in _PROVIDER_RULES:
                found[_PROVIDER_RULES[name]].add(f"{parts[0]}/{parts[1]}")
    return found


def _table() -> dict[str, dict[str, tuple[str, ...]]]:
    """Read the coverage table of the page: `{check: {network: datasets}}`."""
    text = PAGE.read_text(encoding="utf-8")
    block = text.split("<!-- coverage:start -->")[1].split("<!-- coverage:end -->")[0]
    table: dict[str, dict[str, tuple[str, ...]]] = {}
    for line in block.splitlines():
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if len(cells) != 3 or cells[0] in {"check", "---"}:
            continue
        check, network, datasets = (cell.replace("`", "") for cell in cells)
        table.setdefault(check, {})[network] = tuple(dataset.strip() for dataset in datasets.split(","))
    return table


def test_the_table_of_the_page_is_the_coverage_of_the_code() -> None:
    """Every row of the page is a check, a network and the datasets `COVERAGE` names, and none is missing."""
    assert _table() == COVERAGE


def test_the_coverage_is_the_networks_whose_providers_declare_a_rule_of_each_check() -> None:
    """A network is in a check's coverage if and only if a rule of that check is declared in its provider."""
    declared = _declared()
    assert set(COVERAGE) == set(CHECKS)
    for check in CHECKS:
        assert set(COVERAGE[check]) == declared[check], check


def test_every_dataset_of_the_coverage_exists() -> None:
    """The datasets are `resolution/dataset` of the metadata of their network."""
    for check, networks in COVERAGE.items():
        for network, datasets in networks.items():
            provider, name = network.split("/")
            metadata = Wetterdienst.resolve(provider, name).metadata
            existing = {f"{resolution.name}/{dataset.name}" for resolution in metadata for dataset in resolution}
            assert set(datasets) <= existing, f"{check} {network}: {sorted(set(datasets) - existing)}"
            assert len(datasets) == len(set(datasets)), f"{check} {network}: a dataset is listed twice"


def _datasets(network: str, *, has: Callable[[str, DatasetModel], bool]) -> set[str]:
    """Give the datasets (`resolution/dataset`) of a network for which `has(resolution name, dataset)` holds."""
    provider, name = network.split("/")
    metadata = Wetterdienst.resolve(provider, name).metadata
    return {
        f"{resolution.name}/{dataset.name}"
        for resolution in metadata
        for dataset in resolution
        if has(resolution.name, dataset)
    }


def _derived() -> dict[str, dict[str, set[str]]]:
    """Derive the datasets of `COVERAGE` from what the core is told and from the metadata of the networks.

    Each is read off the plan the core makes of a dataset (`plan_for`) or off the parameters a provider's rule names,
    so that a dataset that gains a parameter the rule names, or a resolution that gains a bound, shows here. A network
    whose provider hands the core a rule for every dataset it has (the road and SYNOP networks have one each) is held
    to all of them, which is what `COVERAGE` says, and not to a reading of its code.
    """

    def named(dataset: DatasetModel, names: Iterable[str]) -> bool:
        return any(parameter.name in set(names) for parameter in dataset)

    everything = {"dwd/road": ("15_minutes/data",), "meteofrance/synop": ("subdaily/data",)}
    return {
        "range": {
            **{
                network: _datasets(network, has=lambda _, dataset, n=network: bool(plan_for(n, dataset).ranges))
                for network in SCOPE
            },
            "meteofrance/observation": _datasets(
                "meteofrance/observation",
                has=lambda _, dataset: any(parameter.unit_type == "temperature" for parameter in dataset),
            ),
            "meteofrance/synop": set(everything["meteofrance/synop"]),
        },
        "elevation": {
            "dwd/observation": _datasets(
                "dwd/observation",
                has=lambda _, dataset: bool(plan_for("dwd/observation", dataset).pressure),
            ),
            "meteofrance/synop": set(everything["meteofrance/synop"]),
        },
        "stuck": {
            "dwd/observation": _datasets(
                "dwd/observation", has=lambda _, dataset: bool(plan_for("dwd/observation", dataset).constants)
            ),
            "dwd/road": set(everything["dwd/road"]),
            # the periods of a station are read for the sunshine, a parameter of every resolution of the network
            "rmi/observation": _datasets(
                "rmi/observation", has=lambda _, dataset: named(dataset, ["sunshine_duration"])
            ),
        },
        "consistency": {
            "dwd/road": set(everything["dwd/road"]),
            "meteofrance/observation": _datasets(
                "meteofrance/observation",
                has=lambda _, dataset: (
                    named(dataset, ["humidity_relative"]) and named(dataset, ["temperature_dew_point_2m"])
                ),
            ),
            "meteofrance/synop": set(everything["meteofrance/synop"]),
        },
        "floor": {
            "dwd/dmo": _datasets("dwd/dmo", has=lambda _, dataset: bool(plan_for("dwd/dmo", dataset).floors)),
        },
    }


def test_the_datasets_of_the_coverage_follow_the_rules_and_the_metadata() -> None:
    """The datasets of every check and network are those the constants of the reader and the metadata give.

    Held by derivation for every row: the DWD observation datasets with a parameter that has a bound or is a station
    pressure, the datasets of DMI and RMI whose resolution has a range, those of Météo-France with a temperature,
    or with a humidity and a dew point in one file, the DMO datasets with an element that cannot be negative. The
    road and SYNOP networks each have one dataset, which every rule of theirs covers; that is stated, not derived.
    """
    derived = _derived()
    for check, networks in COVERAGE.items():
        assert set(networks) == set(derived[check]), check
        for network, datasets in networks.items():
            assert set(datasets) == derived[check][network], f"{check} {network}"


def test_a_stub_names_only_checks_that_run_where_it_reads() -> None:
    """The `verdicts` of a stub are checks the network runs on that dataset: the stubs and the page agree."""
    for stub in STUBS:
        network, dataset = stub.provider.split(" ")[:2]
        for _, _, checks in stub.verdicts:
            for check in checks.split("+"):
                assert dataset in COVERAGE[check].get(network, ()), f"{stub.provider}: {check} is not covered"


def test_the_modes_the_page_names_are_the_defaults_of_the_option() -> None:
    """`stuck` is the one check that is soft by default, as the page and the docs of the option say."""
    soft = {check for check in CHECKS if Plausibility().mode(check) == "soft"}
    assert soft == {"stuck"}
    text = PAGE.read_text(encoding="utf-8")
    for check in CHECKS:
        row = next(line for line in text.splitlines() if line.startswith(f"| `{check}` | "))
        assert f"| {'**soft**' if check in soft else 'hard'} |" in row, check


@pytest.mark.parametrize("name", ["quality-flags.md", "special_values.md"])
def test_the_pages_on_the_values_link_the_page_on_the_checks(name: str) -> None:
    """The pages a reader of `quality_flags` comes from point to the checks."""
    assert "plausibility.md" in (ROOT / "docs" / "data" / name).read_text(encoding="utf-8")


def test_the_usage_docs_show_the_option() -> None:
    """The Python, command line and REST docs each say how to set the modes, with their own name for it."""
    usage = ROOT / "docs" / "usage"
    assert "Options(plausibility=" in (usage / "python-api.md").read_text(encoding="utf-8")
    assert "--plausibility-range" in (usage / "cli.md").read_text(encoding="utf-8")
    assert re.search(r"plausibility_range==soft", (usage / "restapi.md").read_text(encoding="utf-8"))
    assert "WD_TS_PLAUSIBILITY__" in (usage / "settings.md").read_text(encoding="utf-8")
