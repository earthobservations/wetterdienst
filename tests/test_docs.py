# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import doctest
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
PROVIDER = Path(ROOT / "wetterdienst" / "provider")
COVERAGE = Path(ROOT / "docs" / "data" / "coverage")

EXCLUDE_PROVIDER_NETWORKS_STARTSWITH = ["_", ".", "metadata"]

# Providers that are excluded from the docs. "*" is a wildcard.
EXCLUDE_PROVIDER_NETWORKS = {
    "eumetnet": "*",
    "dwd": ["radar"],
}


@pytest.mark.xfail
def test_readme():
    readme_file = Path(__file__).parent.parent / "README.rst"
    failures, _ = doctest.testfile(
        filename=str(readme_file),
        module_relative=False,
        optionflags=doctest.NORMALIZE_WHITESPACE | doctest.ELLIPSIS,
    )
    assert failures == 0


def test_data_coverage():
    """Test to make sure that provider data is correctly covered by the docs."""

    def _check_startswith(name, startswith):
        for sw in startswith:
            if name.startswith(sw):
                return True
        return False

    for provider in PROVIDER.glob("*"):
        if (
            _check_startswith(provider.name, EXCLUDE_PROVIDER_NETWORKS_STARTSWITH)
            or EXCLUDE_PROVIDER_NETWORKS.get(provider.name) == "*"
        ):
            continue
        assert Path(COVERAGE / f"{provider.name}.rst").exists()
        assert Path(COVERAGE / provider.name).is_dir()
        provider_coverage = Path(COVERAGE / f"{provider.name}.rst").read_text()
        for network in Path(PROVIDER / provider.name).glob("*"):
            if _check_startswith(
                network.name,
                EXCLUDE_PROVIDER_NETWORKS_STARTSWITH,
            ) or network.name in EXCLUDE_PROVIDER_NETWORKS.get(provider.name, []):
                continue
            assert f"{provider.name}/{network.name}" in provider_coverage
            assert Path(COVERAGE / provider.name / f"{network.name}.rst").exists()
            assert Path(COVERAGE / provider.name / network.name).is_dir()
            network_coverage = Path(COVERAGE / provider.name / f"{network.name}.rst").read_text()
            assert f"{network.name}/" in network_coverage
