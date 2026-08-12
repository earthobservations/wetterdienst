# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the documentation."""

import doctest
import re
from pathlib import Path

import pytest

from wetterdienst.metadata.parameter_table import PARAMETERS

ROOT = Path(__file__).parent.parent
PROVIDER = Path(ROOT / "src" / "wetterdienst" / "provider")
COVERAGE = Path(ROOT / "docs" / "data" / "provider")

EXCLUDE_PROVIDER_NETWORKS_FILES_STARTSWITH = ["_", ".", "metadata"]

# Providers that are excluded from the docs. "*" is a wildcard.
EXCLUDE_PROVIDER_NETWORKS = {
    "eumetnet": "*",
    "dwd": ["radar"],
}


@pytest.mark.remote
def test_readme() -> None:
    """Test to make sure that the wetterdienst example code in the README works."""
    readme_file = Path(__file__).parent.parent / "README.md"
    failures, _ = doctest.testfile(
        filename=str(readme_file),
        module_relative=False,
        optionflags=doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS,
    )
    assert failures == 0


def test_data_coverage() -> None:
    """Test to make sure that the docs correctly cover provider data."""

    def _check_startswith(name: str, startswith: list[str]) -> bool:
        return any(name.startswith(sw) for sw in startswith)

    for provider in PROVIDER.glob("*"):
        if (
            not provider.is_dir()
            or _check_startswith(provider.name, EXCLUDE_PROVIDER_NETWORKS_FILES_STARTSWITH)
            or EXCLUDE_PROVIDER_NETWORKS.get(provider.name) == "*"
        ):
            continue
        assert Path(COVERAGE / provider.name).is_dir()
        provider_readme = Path(COVERAGE / provider.name / "index.md")
        assert provider_readme.exists()
        provider_readme_content = provider_readme.read_text(encoding="utf8")
        for network in provider.glob("*"):
            if (
                not network.is_dir()
                or _check_startswith(network.name, EXCLUDE_PROVIDER_NETWORKS_FILES_STARTSWITH)
                or network.name in EXCLUDE_PROVIDER_NETWORKS.get(provider.name, [])
            ):
                continue
            assert f"{network.name}/index.md" in provider_readme_content
            assert Path(COVERAGE / provider.name / network.name).is_dir()
            network_readme = Path(COVERAGE / provider.name / network.name / "index.md")
            assert network_readme.exists()
            network_readme_content = network_readme.read_text(encoding="utf8")
            # check docs consistency
            for resolution in Path(COVERAGE, provider.name, network.name).glob("*"):
                if resolution.name == "index.md":
                    continue
                assert f"{resolution.stem}{resolution.suffix}" in network_readme_content


def _parameter_rows(path: Path) -> list[list[str]]:
    """Extract the rows of every parameter table in a provider docs page."""
    lines = path.read_text(encoding="utf8").splitlines()
    rows = []
    in_table = False
    for line in lines:
        if not line.startswith("|"):
            in_table = False
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells[0] == "name" and "original name" in cells:
            in_table = True
            continue
        if in_table and not all(set(cell) <= {"-", ":"} for cell in cells):
            rows.append(cells)
    return rows


def test_docs_parameters_link_to_glossary() -> None:
    """Test that every documented parameter is canonical and links to the glossary.

    This is what keeps the provider tables honest: a parameter renamed in a provider's metadata
    but not in its docs page shows up here rather than silently documenting a name that no longer
    exists.
    """
    errors = []
    for path in sorted(COVERAGE.glob("**/*.md")):
        page = str(path.relative_to(COVERAGE))
        for cells in _parameter_rows(path):
            match = re.fullmatch(r"\{term\}`([a-z0-9_]+)`", cells[0])
            if not match:
                errors.append(f"{page}: {cells[0]!r} does not link to the glossary")
            elif match.group(1) not in PARAMETERS:
                errors.append(f"{page}: {match.group(1)!r} is not a canonical parameter")
    assert not errors, "\n".join(errors)


def _documented_descriptions(path: Path) -> dict[tuple[str, str, str], str]:
    """Return {(dataset, canonical name, original name): description} for one provider docs page.

    Keyed by dataset as well: one page can document the same parameter in two datasets with
    different wording, e.g. daily ``snow_depth`` in climate_summary and in water_equivalent.
    """
    documented = {}
    dataset = None
    header = None
    for line in path.read_text(encoding="utf8").splitlines():
        if line.startswith("### "):
            dataset, header = line[4:].strip(), None
            continue
        if not line.startswith("|"):
            header = None
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        if cells and cells[0] == "name" and "original name" in cells:
            header = cells if "description" in cells else None
            continue
        if header is None or all(set(cell) <= {"-", ":"} for cell in cells) or len(cells) < len(header):
            continue
        name = re.sub(r"\{term\}`([^`]+)`", r"\1", cells[header.index("name")])
        documented[dataset, name, cells[header.index("original name")]] = cells[header.index("description")]
    return documented


def _documented_resolutions() -> list[tuple[str, str, object, Path]]:
    """Yield (provider, network, resolution model, docs page) for every documented resolution."""
    from wetterdienst import Wetterdienst  # noqa: PLC0415

    found = []
    for provider, networks in Wetterdienst.registry.items():
        for network in networks:
            try:
                api = Wetterdienst(provider, network)
            except Exception:  # noqa: BLE001, S112
                continue
            metadata = getattr(api, "metadata", None)
            if metadata is None:
                continue
            for resolution in metadata:
                path = Path(COVERAGE / provider / network / f"{resolution.name}.md")
                if path.exists():
                    found.append((provider, network, resolution, path))
    return found


def test_docs_parameter_descriptions_match_the_model() -> None:
    """Test that the docs description column agrees with the model.

    The model is the source: these descriptions used to live only in the markdown tables, where the
    REST API, MCP and CLI could not reach them and where the two copies drifted apart in both
    directions. Editing a description in the docs alone now fails here.
    """
    mismatches = []
    for provider, network, resolution, path in _documented_resolutions():
        documented = _documented_descriptions(path)
        for dataset in resolution:
            for parameter in dataset.parameters:
                if parameter.name == "quality" or not parameter.description:
                    continue
                shown = documented.get((dataset.name, parameter.name, parameter.name_original))
                if shown in (None, "", "-"):
                    continue
                if shown.rstrip(".") != parameter.description.rstrip("."):
                    mismatches.append(
                        f"{provider}/{network}/{resolution.name} {parameter.name}: "
                        f"docs {shown!r} != model {parameter.description!r}",
                    )
    assert not mismatches, "\n".join(mismatches[:10])


def _documented_dataset_descriptions(path: Path) -> dict[str, str]:
    """Return {dataset: description} from the '#### metadata' tables of one docs page."""
    documented = {}
    dataset = None
    in_table = False
    prop = {}
    for line in path.read_text(encoding="utf8").splitlines():
        if line.startswith("### ") and not line.startswith("#### "):
            dataset = line[4:].strip()
        if line.startswith("|"):
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if cells[:1] == ["property"]:
                in_table, prop = True, {}
                continue
            if in_table and not all(set(cell) <= {"-", ":"} for cell in cells) and len(cells) >= 2:
                prop[cells[0]] = cells[1]
        elif in_table:
            if dataset and prop.get("description"):
                documented[dataset] = prop["description"]
            in_table, prop = False, {}
    if in_table and dataset and prop.get("description"):
        documented[dataset] = prop["description"]
    return documented


def test_docs_dataset_descriptions_match_the_model() -> None:
    """Test that the docs dataset metadata tables agree with the model.

    Same reason as the parameter descriptions: the text used to live only in markdown. The docs
    append a "([details](url))" pointer that is page formatting rather than part of the
    description, so it is ignored here.
    """
    mismatches = []
    for provider, network, resolution, path in _documented_resolutions():
        documented = _documented_dataset_descriptions(path)
        for dataset in resolution:
            shown = documented.get(dataset.name)
            if not shown or not dataset.description:
                continue
            shown = re.sub(r"\s*\(\[[^\]]+\]\([^)]*\)\)\s*$", "", shown).strip().rstrip(".")
            if shown != dataset.description.rstrip("."):
                mismatches.append(
                    f"{provider}/{network}/{resolution.name}/{dataset.name}: "
                    f"docs {shown!r} != model {dataset.description!r}",
                )
    assert not mismatches, "\n".join(mismatches[:10])
