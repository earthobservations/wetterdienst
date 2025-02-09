# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the documentation."""

import doctest
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
PROVIDER = Path(ROOT / "wetterdienst" / "provider")
COVERAGE = Path(ROOT / "docs" / "data" / "provider")

EXCLUDE_PROVIDER_NETWORKS_STARTSWITH = ["_", ".", "metadata"]

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

    mkdocs_content = Path(ROOT / "mkdocs.yml").read_text()

    for provider in PROVIDER.glob("*"):
        if (
            _check_startswith(provider.name, EXCLUDE_PROVIDER_NETWORKS_STARTSWITH)
            or EXCLUDE_PROVIDER_NETWORKS.get(provider.name) == "*"
        ):
            continue
        assert Path(COVERAGE / provider.name).is_dir()
        provider_readme = Path(COVERAGE / provider.name / "index.md")
        assert provider_readme.exists()
        assert str(provider_readme).split("docs/")[1] in mkdocs_content
        for network in Path(PROVIDER / provider.name).glob("*"):
            if _check_startswith(
                network.name,
                EXCLUDE_PROVIDER_NETWORKS_STARTSWITH,
            ) or network.name in EXCLUDE_PROVIDER_NETWORKS.get(provider.name, []):
                continue
            assert Path(COVERAGE / provider.name / network.name).is_dir()
            provider_network_readme = Path(COVERAGE / provider.name / network.name / "index.md")
            assert provider_network_readme.exists()
            assert str(provider_network_readme).split("docs/")[1] in mkdocs_content
