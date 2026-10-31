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

import pytest

import wetterdienst
from tests.provider.value_stubs import STUBS
from wetterdienst import Wetterdienst
from wetterdienst.model.plausibility import CHECKS, COVERAGE, Plausibility
from wetterdienst.provider.dwd.observation.parser import STATION_PRESSURE_PARAMETERS, out_of_range_bounds

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


def test_the_datasets_of_dwd_observation_are_those_with_a_parameter_the_rules_name() -> None:
    """The bounds of `range` and the pressures of `elevation` name parameters, which decides the datasets they cover."""
    from wetterdienst.provider.dwd.observation import DwdObservationMetadata  # noqa: PLC0415

    ranged, elevated = set(), set()
    for resolution in DwdObservationMetadata:
        for dataset in resolution:
            if any(out_of_range_bounds(parameter) for parameter in dataset):
                ranged.add(f"{resolution.name}/{dataset.name}")
            if any(parameter.name in STATION_PRESSURE_PARAMETERS for parameter in dataset):
                elevated.add(f"{resolution.name}/{dataset.name}")
    assert set(COVERAGE["range"]["dwd/observation"]) == ranged
    assert set(COVERAGE["elevation"]["dwd/observation"]) == elevated


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
