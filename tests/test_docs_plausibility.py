# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The page on the plausibility checks says what the readers do (GH-3676).

`wetterdienst.model.plausibility.COVERAGE` names the networks and datasets each check runs on, and
`docs/data/plausibility.md` has them as a table. Three things are held to one another so that none can drift: the rules
the providers declare (`OutOfRange`, `NoReading`, `Floor` and `station_pressure_range`, with the check each belongs
to), `COVERAGE`, and the table.
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
from wetterdienst.model.plausibility import CHECKS, COVERAGE, Plausibility
from wetterdienst.provider.dwd.observation.parser import STATION_PRESSURE_PARAMETERS, out_of_range_bounds

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable

    from wetterdienst.model.metadata import DatasetModel

ROOT = Path(__file__).parent.parent
PAGE = ROOT / "docs" / "data" / "plausibility.md"
PROVIDER_DIR = Path(wetterdienst.__file__).parent / "provider"

#: the check a rule belongs to where its call names none
_DEFAULT_CHECK = {"OutOfRange": "range", "NoReading": "stuck", "Floor": "floor", "station_pressure_range": "elevation"}


def _declared() -> dict[str, set[str]]:
    """Read from the providers which checks the rules of each network belong to: `{check: {provider/network}}`."""
    found: dict[str, set[str]] = {check: set() for check in CHECKS}
    for path in sorted(PROVIDER_DIR.rglob("*.py")):
        parts = path.relative_to(PROVIDER_DIR).parts
        if len(parts) < 3:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", getattr(node.func, "attr", None))
            if name not in _DEFAULT_CHECK:
                continue
            check = _DEFAULT_CHECK[name]
            for keyword in node.keywords:
                if keyword.arg == "check":
                    assert isinstance(keyword.value, ast.Constant), f"{path}: the check of a rule is a literal"
                    check = keyword.value.value
            found[check].add(f"{parts[0]}/{parts[1]}")
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
    """Derive the datasets of `COVERAGE` from the rules the readers declare and from the metadata of the networks.

    Each is read off the constants the reader builds its rules from, so that a dataset that gains a parameter the rule
    names, or a resolution that gains a bound, shows here. Derived for every check and network of `COVERAGE` but one
    kind: a network whose reader applies a rule to every dataset it has (the road and SYNOP networks have one each) is
    held to all of them, which is what `COVERAGE` says, and not to a reading of its code.
    """
    from wetterdienst.provider.dmi.observation import api as dmi  # noqa: PLC0415
    from wetterdienst.provider.dwd.dmo import api as dmo  # noqa: PLC0415
    from wetterdienst.provider.dwd.observation.parser import STATION_CONSTANT_PARAMETERS  # noqa: PLC0415
    from wetterdienst.provider.meteofrance.observation import api as meteofrance  # noqa: PLC0415
    from wetterdienst.provider.rmi.observation import api as rmi  # noqa: PLC0415

    def named(dataset: DatasetModel, names: Iterable[str]) -> bool:
        return any(parameter.name_original in set(names) for parameter in dataset)

    everything = {"dwd/road": ("15_minutes/data",), "meteofrance/synop": ("subdaily/data",)}
    constant = {f"{dataset.resolution.name}/{dataset.name}" for dataset, _ in STATION_CONSTANT_PARAMETERS}
    return {
        "range": {
            "dmi/observation": _datasets("dmi/observation", has=lambda resolution, _: resolution in dmi._RANGES),  # noqa: SLF001
            "dwd/observation": _datasets(
                "dwd/observation", has=lambda _, dataset: any(out_of_range_bounds(parameter) for parameter in dataset)
            ),
            "meteofrance/observation": _datasets(
                "meteofrance/observation",
                has=lambda resolution, dataset: named(dataset, meteofrance._TEMPERATURE_COLUMNS.get(resolution, ())),  # noqa: SLF001
            ),
            "rmi/observation": _datasets("rmi/observation", has=lambda resolution, _: resolution in rmi._RANGES),  # noqa: SLF001
            **{network: set(datasets) for network, datasets in everything.items()},
        },
        "elevation": {
            "dwd/observation": _datasets(
                "dwd/observation",
                has=lambda _, dataset: any(parameter.name in STATION_PRESSURE_PARAMETERS for parameter in dataset),
            ),
            "meteofrance/synop": set(everything["meteofrance/synop"]),
        },
        "stuck": {
            "dwd/observation": constant,
            "dwd/road": set(everything["dwd/road"]),
            # the periods of a station are read for the sunshine, a parameter of every resolution the ranges name
            "rmi/observation": _datasets(
                "rmi/observation",
                has=lambda resolution, dataset: resolution in rmi._RANGES and named(dataset, ["sun_duration"]),  # noqa: SLF001
            ),
        },
        "consistency": {
            "dwd/road": set(everything["dwd/road"]),
            "meteofrance/observation": _datasets(
                "meteofrance/observation",
                has=lambda _, dataset: (
                    named(dataset, [meteofrance._HUMIDITY_COLUMN])  # noqa: SLF001
                    and named(dataset, [meteofrance._DEW_POINT_COLUMN])  # noqa: SLF001
                ),
            ),
            "meteofrance/synop": set(everything["meteofrance/synop"]),
        },
        "floor": {
            "dwd/dmo": _datasets("dwd/dmo", has=lambda _, dataset: named(dataset, dmo._DMO_NON_NEGATIVE)),  # noqa: SLF001
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
