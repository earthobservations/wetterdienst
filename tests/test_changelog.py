# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the changelogs.

The compare links at the foot of a changelog are maintained by hand and are easy to forget when
releasing -- a release that adds a dated section and leaves them alone reads as complete, while
the new version's heading links nowhere and `[Unreleased]` still compares against the version
before it. These tests tie the two halves of each file together, for the library's changelog
(tags `vX.Y.Z`) and the app's (tags `app-vX.Y.Z`).
"""

import re
from itertools import pairwise
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent

# the changelog and the prefix of its release tags
CHANGELOGS = {
    "CHANGELOG.md": "v",
    "CHANGELOG_APP.md": "app-v",
}


def _read(name: str) -> tuple[list[str], dict[str, str]]:
    text = (ROOT / name).read_text(encoding="utf8")
    headings = re.findall(r"(?m)^## \[(\d+\.\d+\.\d+)\] - \d{4}-\d{2}-\d{2}$", text)
    links = dict(re.findall(r"(?m)^\[([^\]]+)\]: (\S+)$", text))
    return headings, links


@pytest.mark.parametrize("name", CHANGELOGS)
def test_every_released_version_has_a_compare_link(name: str) -> None:
    """Test that each dated section is a link to the diff it stands for."""
    headings, links = _read(name)
    assert headings, f"no dated sections in {name}"
    linked = set(links) - {"Unreleased"}

    assert set(headings) == linked


@pytest.mark.parametrize("name", CHANGELOGS)
def test_unreleased_compares_from_the_newest_version(name: str) -> None:
    """Test that `[Unreleased]` is the diff since the version most recently released.

    Left alone by a release it goes on describing the release before it as unreleased, and points
    at a range that has since been cut.
    """
    headings, links = _read(name)
    tag = CHANGELOGS[name]

    assert links["Unreleased"].endswith(f"/compare/{tag}{headings[0]}...HEAD")


@pytest.mark.parametrize("name", CHANGELOGS)
def test_each_version_compares_against_the_one_before_it(name: str) -> None:
    """Test that the compare ranges form an unbroken chain down to the first release."""
    headings, links = _read(name)
    tag = CHANGELOGS[name]
    for newer, older in pairwise(headings):
        assert links[newer].endswith(f"/compare/{tag}{older}...{tag}{newer}"), newer
    # the first release has nothing to compare against and points at its own tag
    assert links[headings[-1]].endswith(f"/releases/tag/{tag}{headings[-1]}")
