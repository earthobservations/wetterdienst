# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the changelog.

The compare links at the foot of the changelog are maintained by hand and are easy to forget when
releasing -- a release that adds a dated section and leaves them alone reads as complete, while
the new version's heading links nowhere and `[Unreleased]` still compares against the version
before it. These tests tie the two halves of the file together.
"""

import re
from itertools import pairwise
from pathlib import Path

CHANGELOG_FILE = Path(__file__).parent.parent / "CHANGELOG.md"
CHANGELOG = CHANGELOG_FILE.read_text(encoding="utf8")

VERSION_HEADINGS = re.findall(r"(?m)^## \[(\d+\.\d+\.\d+)\] - \d{4}-\d{2}-\d{2}$", CHANGELOG)
COMPARE_LINKS = dict(re.findall(r"(?m)^\[([^\]]+)\]: (\S+)$", CHANGELOG))


def test_every_released_version_has_a_compare_link() -> None:
    """Test that each dated section is a link to the diff it stands for."""
    assert VERSION_HEADINGS, "no dated sections in the changelog"
    linked = set(COMPARE_LINKS) - {"Unreleased"}

    assert set(VERSION_HEADINGS) == linked


def test_unreleased_compares_from_the_newest_version() -> None:
    """Test that `[Unreleased]` is the diff since the version most recently released.

    Left alone by a release it goes on describing the release before it as unreleased, and points
    at a range that has since been cut.
    """
    newest = VERSION_HEADINGS[0]

    assert COMPARE_LINKS["Unreleased"].endswith(f"/compare/v{newest}...HEAD")


def test_each_version_compares_against_the_one_before_it() -> None:
    """Test that the compare ranges form an unbroken chain down to the first release."""
    for newer, older in pairwise(VERSION_HEADINGS):
        assert COMPARE_LINKS[newer].endswith(f"/compare/v{older}...v{newer}"), newer
    # the first release has nothing to compare against and points at its own tag
    assert COMPARE_LINKS[VERSION_HEADINGS[-1]].endswith(f"/releases/tag/v{VERSION_HEADINGS[-1]}")
