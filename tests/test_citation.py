# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the citation metadata.

CITATION.cff is maintained by hand and is easy to forget when releasing, so these tests tie it to
the sources of truth it duplicates: the version in pyproject.toml, the release date in CHANGELOG.md
and the DOI badge in the README.
"""

import re
from pathlib import Path
from typing import Any

import pytest
import tomllib
import yaml

ROOT = Path(__file__).parent.parent
CITATION_FILE = ROOT / "CITATION.cff"
PYPROJECT_FILE = ROOT / "pyproject.toml"
CHANGELOG_FILE = ROOT / "CHANGELOG.md"
README_FILE = ROOT / "README.md"


@pytest.fixture
def citation() -> dict[str, Any]:
    """Provide the parsed citation metadata."""
    return yaml.safe_load(CITATION_FILE.read_text(encoding="utf8"))


def test_citation_is_well_formed(citation: dict[str, Any]) -> None:
    """Test that the citation metadata carries the fields required by the CFF schema."""
    assert citation["cff-version"] == "1.2.0"
    assert citation["message"]
    assert citation["title"] == "wetterdienst"
    assert citation["authors"]
    assert all(author["family-names"] and author["given-names"] for author in citation["authors"])
    # an empty `identifiers:` key parses as None and makes the file invalid
    assert citation["identifiers"]
    assert all(identifier["type"] and identifier["value"] for identifier in citation["identifiers"])


def test_citation_version_matches_pyproject(citation: dict[str, Any]) -> None:
    """Test that the citation names the version that is being released.

    Read from pyproject.toml rather than `wetterdienst.__version__`, as the latter reports the
    version of the installed distribution, which may lag behind an unsynced version bump.
    """
    pyproject = tomllib.loads(PYPROJECT_FILE.read_text(encoding="utf8"))
    assert citation["version"] == pyproject["project"]["version"]


def test_citation_date_matches_changelog(citation: dict[str, Any]) -> None:
    """Test that the release date of the citation matches the changelog entry of that version."""
    version = re.escape(citation["version"])
    entry = re.search(
        rf"^## \[{version}\] - (\d{{4}}-\d{{2}}-\d{{2}})$", CHANGELOG_FILE.read_text(encoding="utf8"), re.MULTILINE
    )
    assert entry, f"no changelog entry for version {citation['version']}"
    assert str(citation["date-released"]) == entry.group(1)


def test_citation_doi_matches_readme(citation: dict[str, Any]) -> None:
    """Test that the citation and the README agree on the concept DOI."""
    badge = re.search(r"zenodo\.org/badge/DOI/(10\.5281/zenodo\.\d+)\.svg", README_FILE.read_text(encoding="utf8"))
    assert badge, "no citation badge in the README"
    assert citation["doi"] == badge.group(1)
    assert badge.group(1) in {identifier["value"] for identifier in citation["identifiers"]}
