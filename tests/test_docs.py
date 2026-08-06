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
