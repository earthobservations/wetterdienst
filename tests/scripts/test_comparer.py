# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the comparer of `scripts/repo_advisories.py`: the locked version against the ranges of an advisory.

The class of error that must not exist is the false "safe": a locked version that an advisory covers and the
comparer clears. The tables pin the ranges as found; the fuzz and the corpus of recorded advisories hold the
false negatives to zero.
"""

from __future__ import annotations

import json
import operator
import random
import re
from functools import cmp_to_key
from typing import Any

import pytest
from packaging.version import Version

from tests.scripts.support import RECORDED, ra

# (ecosystem, installed, vulnerable range as GitHub or the author wrote it, patched versions, affected?)
AFFECTED = [
    # the forms GitHub writes
    ("pip", "4.2.12", "= 4.2.12", "4.3.0", True),
    ("pip", "4.2.13", "= 4.2.12", "4.3.0", False),
    ("pip", "4.15.1", ">= 4.5.0, <= 4.16.0", None, True),
    ("pip", "4.16.1", ">= 4.5.0, <= 4.16.0", None, False),
    ("pip", "4.4.9", ">= 4.5.0, <= 4.16.0", None, False),
    ("pip", "4.16.0", ">= 4.5.0, <= 4.16.0", None, True),
    ("pip", "4.6.1", "< 4.6.2", "4.6.2", True),
    ("pip", "4.6.2", "< 4.6.2", "4.6.2", False),
    ("pip", "3.14.4", ">=2,<=3.14.4", None, True),
    ("pip", "3.14.5", ">=2,<=3.14.4", None, False),
    ("npm", "12.3.0", "7.2.0 - 12.3.0", None, True),
    ("npm", "7.2.0", "7.2.0 - 12.3.0", None, True),
    ("npm", "12.3.1", "7.2.0 - 12.3.0", None, False),
    ("npm", "7.1.9", "7.2.0 - 12.3.0", None, False),
    ("npm", "4.6.4", ">= 4.0.0, < 4.7.0", "4.7.0", True),
    ("npm", "4.7.0", ">= 4.0.0, < 4.7.0", "4.7.0", False),
    # a patched version is not affected, whatever the range says
    ("pip", "0.17.1", ">= 0.16.0, < 0.17.1", "0.17.1", False),
    ("pip", "6.21.2", "<= 6.21.2", ">= 6.21.2", False),
    ("pip", "6.22.0", "<= 6.22.0", ">= 6.21.2", False),
    # B1: a bounded patched range is one range ("and"), not two fixes
    ("npm", "3.0.0", "<= 3.30.0", "> 3.21.5, < 4.0.0-alpha.1", True),
    ("npm", "3.21.6", "<= 3.30.0", "> 3.21.5, < 4.0.0-alpha.1", False),
    ("npm", "3.21.5", ">= 3.4.3, <= 3.21.5", "> 3.21.5, < 4.0.0-alpha.1", True),
    ("npm", "3.10.0", ">= 3.4.3, <= 3.21.5", "> 3.21.5, < 4.0.0-alpha.1", True),
    ("npm", "4.4.5", ">= 4.0.0-alpha.1, <= 4.4.5", "> 4.4.5", True),
    ("npm", "6.2.6", ">=6.2.0, <=6.2.6", ">=6.2.7, <6.3.0", True),
    # B2: the fix of one release line is not the fix of another
    ("npm", "1.15.9", "<= 2.0.1-rc.16", ">= 1.15.9 || >= v2.0.1-rc.17", False),
    ("npm", "1.15.5", "<= 2.0.1-rc.16", ">= 1.15.9 || >= v2.0.1-rc.17", True),
    ("npm", "2.0.0", "<= 2.0.1-rc.16", ">= 1.15.9 || >= v2.0.1-rc.17", True),
    ("npm", "2.0.1-rc.17", "<= 2.0.1-rc.18", ">= 1.15.9 || >= v2.0.1-rc.17", False),
    ("pip", "1.7.0", ">= 1.0.0, <= 3.0.0", "1.5.3, 2.1.1", False),
    ("pip", "1.4.0", ">= 1.0.0, <= 3.0.0", "1.5.3, 2.1.1", True),
    ("pip", "2.0", ">= 1.0.0, <= 3.0.0", "1.5.3, 2.1.1", True),
    ("pip", "2.1.1", ">= 1.0.0, <= 3.0.0", "1.5.3, 2.1.1", False),
    ("pip", "0.16.3", ">= 0.1.0, < 0.17.5", "0.16.6, 0.17.1", True),
    ("pip", "0.16.6", ">= 0.1.0, < 0.17.5", "0.16.6, 0.17.1", False),
    ("pip", "0.17.0", ">= 0.1.0, < 0.17.5", "0.16.6, 0.17.1", True),
    # a fix below the lower bound of the range fixes nothing in it
    ("pip", "3.0.0", ">= 2.0.0, <= 4.0.0", "1.5.3", True),
    ("npm", "5.1.0", ">= 5.0.0, <= 5.2.0", "4.9.9", True),
    # `0`, `*` and partial forms name no fix and never override the range
    ("pip", "3.0.0", "<= 4.0.0", "0", True),
    ("pip", "3.0.0", "<= 4.0.0", "0.0.0", True),
    ("npm", "3.0.0", "<= 4.0.0", ">= 0.0.0", True),
    ("npm", "3.0.0", "<= 4.0.0", "0.0.0 || 0.0.0-0", True),
    ("pip", "3.0.0", "<= 4.0.0", "*", True),
    ("npm", "3.0.0", "<= 4.0.0", "3.x", True),
    ("npm", "3.0.0", "<= 4.0.0", "2", True),
    ("npm", "3.0.0", "<= 4.0.0", "5.0.0 || 3.x", True),
    # a range without an upper bound: affected where nothing is fixed or the fix is above, closed by a fix below
    ("pip", "3.14.4", ">=3.10.6", "3.10.11", False),
    ("pip", "3.10.8", ">=3.10.6", "3.10.11", True),
    ("pip", "5.0.0", ">= 4.5.0", None, True),
    ("pip", "3.2.0", "> 3.1.0", "3.3.2+", True),  # a fix written `3.3.2+`, as the cryptography advisory of 2021 has it
    ("pip", "3.4.0", "> 3.1.0", "3.3.2+", False),
    ("pip", "3.3.2", "> 3.1.0", "1.0+, 3.3.2+", False),
    ("pip", "5.0.0", ">= 4.5.0", "", True),
    ("pip", "5.0.0", ">= 4.5.0", "None", True),
    # what the authors of advisories write
    ("pip", "12.2.0", "≤ 12.2.0", ">= 12.3.0", True),
    ("pip", "12.3.0", "≤ 12.2.0", ">= 12.3.0", False),
    ("pip", "2.3.0", "=< 2.3.0", "2.3.1", True),
    ("pip", "2.3.2", "=< 2.3.0", "2.3.1", False),
    ("pip", "0.15.0", "0.15.0 and earlier", "0.16.0", True),
    ("pip", "0.16.0", "0.15.0 and earlier", "0.16.0", False),
    ("pip", "1.4.1", ">=1.3.3 and <= 1.4.1", "1.3.5, 1.4.2", True),
    ("pip", "1.4.2", ">=1.3.3 and <= 1.4.1", "1.3.5, 1.4.2", False),
    ("npm", "3.9.0", ">=3.8.1<3.15.3", ">=3.15.3", True),
    ("npm", "3.15.3", ">=3.8.1<3.15.3", ">=3.15.3", False),
    ("npm", "10.2.0", "10 <10.2.1 || 3 <3.1.3 || 4 <4.2.4", "10.2.1 || 3.1.3 || 4.2.4", True),
    ("npm", "10.2.1", "10 <10.2.1 || 3 <3.1.3 || 4 <4.2.4", "10.2.1 || 3.1.3 || 4.2.4", False),
    ("npm", "3.1.2", "10 <10.2.1 || 3 <3.1.3 || 4 <4.2.4", "10.2.1 || 3.1.3 || 4.2.4", True),
    ("npm", "8.13.1", "< 6.28.1; 7.0.0 < 7.29.1; 8.0.0 < 8.10.2", "6.28.1; 7.29.1; 8.10.2", False),
    ("npm", "8.10.1", "< 6.28.1; 7.0.0 < 7.29.1; 8.0.0 < 8.10.2", "6.28.1; 7.29.1; 8.10.2", True),
    ("npm", "7.5.0", "< 6.28.1; 7.0.0 < 7.29.1; 8.0.0 < 8.10.2", "6.28.1; 7.29.1; 8.10.2", True),
    ("npm", "2.1.5", "<1.1.17, >= 2.0.0 < 2.1.3, 4.0.0 - 5.0.7", "5.0.8, 3.0.3, 2.1.3, 1.1.17", False),
    ("npm", "2.1.2", "<1.1.17, >= 2.0.0 < 2.1.3, 4.0.0 - 5.0.7", "5.0.8, 3.0.3, 2.1.3, 1.1.17", True),
    ("npm", "5.0.7", "<1.1.17, >= 2.0.0 < 2.1.3, 4.0.0 - 5.0.7", "5.0.8, 3.0.3, 2.1.3, 1.1.17", True),
    ("npm", "5.0.13", "<1.1.17, >= 2.0.0 < 2.1.3, 4.0.0 - 5.0.7", "5.0.8, 3.0.3, 2.1.3, 1.1.17", False),
    ("npm", "11.0.3", "11.0.x", "11.1.0", True),
    ("npm", "11.1.0", "11.0.x", "11.1.0", False),
    ("npm", "19.9.9", "<20", "20", True),
    ("npm", "20.0.0", "<20", "20", False),
    ("pip", "9.9.9", "*", None, True),
    # B3: a lower and an upper bound per release line, as vite writes it
    ("npm", "3.1.0", ">=2.9.18,<3.0.0,>=3.2.9,<4.0.0", None, False),
    ("npm", "3.5.0", ">=2.9.18,<3.0.0,>=3.2.9,<4.0.0", None, True),
    ("npm", "2.9.18", ">=2.9.18,<3.0.0,>=3.2.9,<4.0.0", None, True),
    ("npm", "5.4.21", ">=2.9.18,<3.0.0,>=3.2.9,<4.0.0,>=4.5.3,<5.0.0,>=5.2.6,<=5.4.20", "5.4.21", False),
    ("npm", "5.4.20", ">=2.9.18,<3.0.0,>=3.2.9,<4.0.0,>=4.5.3,<5.0.0,>=5.2.6,<=5.4.20", "5.4.21", True),
    ("npm", "5.4.20", ">=2.9.18,<3.0.0,>=3.2.9,<4.0.0,>=4.5.3,<5.0.0,>=5.2.6,<=5.4.20", "5.4.21", True),
    # a pre-release is below its release; `-0` is the lowest pre-release
    ("npm", "2.0.1-rc.14", "<= 2.0.1-rc.14", None, True),
    ("npm", "2.0.1-rc.15", "<= 2.0.1-rc.14", None, False),
    ("npm", "2.0.1", "<= 2.0.1-rc.14", None, False),
    ("npm", "2.0.0", ">= 2.0.0-0, < 2.0.1-rc.15", None, True),
    ("npm", "2.0.1-rc.15", ">= 2.0.0-0, < 2.0.1-rc.15", None, False),
    ("pip", "2.0rc1", "< 2.0", "2.0", True),
]

UNCLEAR = [
    ("pip", "2.14.4", "all", "v1.8.2,v1.7.4,v1.6.2"),  # the real range of a 2021 pydantic advisory
    ("pip", "1.0", None, "1.1"),
    ("pip", "1.0", "", "1.1"),
    ("pip", "1.0", "   ", None),
    ("pip", "1.0", "~=1.4", "1.5"),
    ("pip", "1.0", "PyPDF2==2.10.5", None),  # the real range of a pypdf advisory
    ("npm", "1.2.3", "^1.2.0", "1.3.0"),
    ("npm", "1.2.3", "~1.2.0", "1.3.0"),
    ("npm", "1.2.3", ">= 1.2.0, < banana", None),
    ("npm", "1.2.3", "1.2.3 1.2.4", None),
    ("npm", "1.2.3", "||", None),
    ("npm", "1.2.3", "> 1.x", None),
    ("npm", "1.2.3", "<= 1", None),  # npm reads it as < 2.0.0, so not guessed
    ("npm", "not-a-version", "< 2.0.0", None),
    # B3: a comma list that is never true, or that is no "and" of one lower and one upper bound
    ("pip", "1.2.3", "1.2.3, 1.2.4", None),
    ("pip", "1.0", ">= 1.0, >= 2.0", None),
    ("pip", "1.0", ">= 3.0.0, < 2.0.0", None),
    ("pip", "1.0", ">= 1.0, <= 2.0, >= 3.0", None),
    ("pip", "1.0", ">= 3.0, < 3.0", None),
    ("npm", "1.2.3", "< 2.0.0 (up to and including 1.9.9)", None),
    ("npm", "1.2.3", "< 2.0.0 (1.9.9)", None),
    ("npm", "1.2.3", "(< 2.0.0", None),
    # the low list: a range written without spaces, `1.x.3`, a local version, a partial form in the middle
    ("pip", "1.0", "1.0-2", None),
    ("npm", "1.2.3", "1.x.3", None),
    ("npm", "1.2.3", ">= 1.x.3", None),
    ("pip", "1.0+local", "< 2", None),
    ("pip", "1.0", ">= 1.0+local", None),
    ("pip", "1.0", "< 2 " + "x" * 600, None),
    ("pip", "1.0", ",".join(f">= {i}.0" for i in range(200)), None),
    (
        "pip",
        "5.0",
        " || ".join(f">= {i}.0, < {i}.1" for i in range(60)),
        None,
    ),  # every part is fine, the whole is too long
]


# the second review: a fix of a lower release line, a fix written `> x`, the readings of what the grammar refuses
AFFECTED_AGAIN = [
    # R1: inside a range that ends, a fix of a lower release line clears nothing (the real h3 entries, and others)
    ("npm", "2.0.1-rc.16", "<= 2.0.1-rc.16", ">= 1.15.9 || >= v2.0.1-rc.17", True),
    ("npm", "2.0.1-rc.14", "<= 2.0.1-rc.14", ">=1.15.6 <2.0.0-0 || >=2.0.1-rc.15", True),
    ("npm", "2.0.0-0", "<= 2.0.1-rc.14", ">=1.15.6 <2.0.0-0 || >=2.0.1-rc.15", True),
    ("npm", "2.0.1-rc.14", "<= 2.0.1-rc.14", ">= 1.15.6, >= 2.0.1-rc.15", True),
    ("npm", "2.0.0-rc.3", "<= 2.0.1-rc.16", ">= 1.15.9 || >= v2.0.1-rc.17", True),
    ("npm", "1.15.8", "<= 2.0.1-rc.16", ">= 1.15.9 || >= v2.0.1-rc.17", True),
    ("pip", "2.1.0", "<= 2.3.0", "1.9.5", True),
    ("pip", "1.5.0", ">= 1.0.0, <= 3.0.0", "0.9.0", True),
    ("pip", "2.1.0", "<= 2.3.0", "2.0.5", False),  # the same release line clears it
    ("npm", "1.15.9", "<= 2.0.1-rc.16", ">= 1.15.9 || >= v2.0.1-rc.17", False),
    # R2: a lone `>` is a fix that the version itself has not reached
    ("npm", "1.15.5", "<= 2.0.1", "> 1.15.5", True),
    ("npm", "1.15.6", "<= 2.0.1", "> 1.15.5", False),
    ("npm", "2.0.0", "<= 2.5.0", "> 1.15.5 || > 2.0.1", True),
    ("npm", "2.0.2", "<= 2.5.0", "> 1.15.5 || > 2.0.1", False),
    ("npm", "3.5.0", ">= 3.0.0-alpha.1, <= 3.5.0", "> 3.5.0", True),
    # a fix below the lower bound is no fix of the range, and `0.0.0` is no fix at all
    ("pip", "6.0.0", ">= 5.0.0", "1.0.0", True),
    ("pip", "3.0.0", "*", "0.0.0", True),
    ("npm", "3.0.0", "*", "0.0.0", True),
    ("npm", "3.0.0", "*", "0.0.0-0", True),
    # a version that two ranges hold is cleared only if each of them clears it, against its own lower bound
    ("pip", "2.5.0", ">= 1.0.0 || >= 2.0.0, < 4.0.0", "1.5.0", True),
    ("pip", "2.5.0", ">= 1.0.0 || >= 2.0.0, < 4.0.0", "2.2.0", False),
    # a bounded patched range counts only above the lower bound of the vulnerable one
    ("pip", "2.5.0", ">= 2.0.0, <= 4.0.0", ">= 1.0.0, < 3.0.0", True),
    ("pip", "2.5.0", "<= 4.0.0", ">= 1.0.0, < 3.0.0", False),
    # the readings of what the strict grammar refuses: out under all is out, affected under all is affected
    ("pip", "1.0", "< 1.2.3, < 2.1.0", None, True),
    ("pip", "3.0", "< 1.2.3, < 2.1.0", None, False),
    ("pip", "1.0", ">= 1.0, < 2.0, < 3.0", None, True),
    ("pip", "1.0", ">= 1.0, != 1.5", None, True),
    ("npm", "17.0.6", "18.0.0,18.0.1", None, False),  # marked, GHSA-6v9c
    ("pip", "1.9.10", "<= 1.7.0,<=1.6.11", None, False),  # authlib, GHSA-r95x
    ("pip", "6.1.0", "<= 5.2.0, <= 4.3.2", None, False),  # zrender, GHSA-fhv8
    # a dash without spaces between two whole versions in order is a range, as lib0 GHSA-r5c8 writes it
    ("npm", "0.2.117", "0.2.1-0.2.117", None, True),
    ("npm", "0.2.1", "0.2.1-0.2.117", None, True),
    ("npm", "0.2.120", "0.2.1-0.2.117", None, False),
    ("npm", "0.1.0", "0.2.1-0.2.117", None, False),
    ("npm", "1.2.3", "1.0.0-2.0.0", None, True),
    ("npm", "3.0.0", "1.0.0-2.0.0", None, False),
    ("pip", "3.0.0", "1.0-2", None, False),  # out under both readings, so out
    # R6: a partial version where the zero-fill is exact
    ("pip", "2.5.0", ">= 2, < 3", None, True),
    ("pip", "3.0.0", ">= 2, < 3", None, False),
    ("pip", "9.0.0", "< 20", None, True),
]

UNCLEAR_AGAIN = [
    # R6: a partial version after `<=`, `>`, `=` or alone: the x-range reading differs from the exact one
    ("pip", "1.0.0", "<= 2", None),
    ("pip", "1.0.0", "> 3.10", None),
    ("pip", "1.0.0", "= 2", None),
    ("pip", "3.10.2", "3.10", None),
    ("pip", "1.0.0", "2", None),
    ("pip", "1.0.0", "1.0 - 2", None),
    ("npm", "1.2.3", ">=1.0.0-2.0.0", None),
    ("npm", "1.2.3", "<=1.0.0-2.0.0", None),
    # the readings disagree: affected under some, out under others
    ("pip", "1.5.0", "1.0-2", None),
    ("pip", "1.2.3", "1.2.3, 1.2.4", None),
    ("pip", "1.0", ">= 1.0, >= 2.0", None),
    ("npm", "5.0.13", ">= 3.0.0, < 5.0.7, >= 2.0.0, < 2.1.2, < 1.1.16", None),  # brace-expansion
    ("npm", "5.1.1", "<=0.0.125,>=1.0.0, <=1.6.0", None),  # vitest
    ("npm", "1.15.11", ">=v2.0.1-beta.0, <=v2.0.0-rc.8", None),  # h3
    ("pip", "2.0.0", "<3.0.0,>=2.0.0,<4.0.0,>=3.5.0", None),  # upper, lower, upper, lower is no pair
    ("pip", "6.0.0", ">=3.0.0,<2.0.0,>=5.0.0,<6.0.0", None),  # a pair that never holds
    # a text that is no range at all
    ("npm", "1.2.3", "(< 2.0.0 and a note", None),
]


@pytest.mark.parametrize(("ecosystem", "installed", "vulnerable", "patched", "expected"), AFFECTED_AGAIN)
def test_the_second_review_cases(
    ecosystem: str,
    installed: str,
    vulnerable: str,
    patched: str | None,
    expected: bool,  # noqa: FBT001
) -> None:
    """Test the ranges the first review round missed: lower-line fixes, `> x` fixes, readings, partial versions."""
    assert ra.is_affected(ecosystem, installed, vulnerable, patched) is expected


@pytest.mark.parametrize(("ecosystem", "installed", "vulnerable", "patched"), UNCLEAR_AGAIN)
def test_the_second_review_unclear_cases(ecosystem: str, installed: str, vulnerable: str, patched: str | None) -> None:
    """Test that what is ambiguous, and where the readings disagree, is unclear."""
    with pytest.raises(ra.UnclearRange):
        ra.assess(ecosystem, installed, vulnerable, patched)


def test_the_strict_grammar_still_refuses_what_only_the_readings_take() -> None:
    """Test that `parse_range` (the strict reading) refuses lists that are no "and" and pairs out of order or empty."""
    for text in (
        "< 1.2.3, < 2.1.0",
        "1.2.3, 1.2.4",
        "<3.0.0,>=2.0.0,<4.0.0,>=3.5.0",
        ">=3.0.0,<2.0.0,>=5.0.0,<6.0.0",
        ">=2.0.0,<3.0.0,>=4.0.0",
    ):
        with pytest.raises(ra.UnclearRange):
            ra.parse_range("pip", text)


def test_the_readings_of_a_comma_list_and_of_a_dash() -> None:
    """Test how many readings an ambiguous text has, and when a dash is a clear range."""
    readings, dash = ra._readings("pip", "< 1.2.3, < 2.1.0")  # noqa: SLF001
    assert (len(readings), dash) == (3, False)  # an "and" of all, an "or" of the parts, lower-upper pairs
    readings, dash = ra._readings("npm", "0.2.1-0.2.117")  # noqa: SLF001
    assert (len(readings), dash) == (2, True)  # a range and a pre-release; both ends whole and in order
    readings, dash = ra._readings("npm", "0.2.117-0.2.1")  # noqa: SLF001
    assert dash is False
    readings, dash = ra._readings("npm", ">= 1.0.0, < 2.0.0")  # noqa: SLF001
    assert (len(readings), dash) == (1, False)


def test_too_many_readings_are_unclear() -> None:
    """Test that a range with many ambiguous parts is refused instead of read in thousands of ways."""
    text = " || ".join("< 1.2.3, < 2.1.0" for _ in range(8))

    with pytest.raises(ra.UnclearRange, match="too many readings"):
        ra.assess("pip", "9.0.0", text, None)


@pytest.mark.parametrize(
    ("installed", "vulnerable", "patched", "verdict"),
    [
        ("3.5.0", ">= 1.0.0 || >= 3.0.0, < 4.0.0", "3.2.0", "fixed"),  # one of the ranges ends: not `closed`
        ("3.5.0", ">= 1.0.0", "3.2.0", "closed"),
        ("2.1.0", "<= 2.3.0", "1.9.5", "affected"),
        ("2.1.0", "<= 2.3.0", "2.0.5", "fixed"),
        ("1.6.0", ">= 1.0.0, < 3.0.0", "1.5.0", "fixed"),
    ],
)
def test_the_verdicts_of_the_second_review(installed: str, vulnerable: str, patched: str, verdict: str) -> None:
    """Test `closed` only when no range that holds the version ends, and the cross-line rule in the verdict."""
    assert ra.assess("pip", installed, vulnerable, patched) == verdict


@pytest.mark.parametrize(("ecosystem", "installed", "vulnerable", "patched", "expected"), AFFECTED)
def test_the_comparer_reads_the_ranges_as_found(
    ecosystem: str,
    installed: str,
    vulnerable: str,
    patched: str | None,
    expected: bool,  # noqa: FBT001
) -> None:
    """Test that the locked version is compared with the range as GitHub and the authors of advisories write it."""
    assert ra.is_affected(ecosystem, installed, vulnerable, patched) is expected


@pytest.mark.parametrize(("ecosystem", "installed", "vulnerable", "patched"), UNCLEAR)
def test_a_range_that_is_not_understood_is_unclear_never_safe(
    ecosystem: str, installed: str, vulnerable: str | None, patched: str | None
) -> None:
    """Test that a range or a version nobody can read raises, which the report lists as unclear and never as safe."""
    with pytest.raises(ra.UnclearRange):
        ra.is_affected(ecosystem, installed, vulnerable, patched)


@pytest.mark.parametrize(
    ("ecosystem", "installed", "vulnerable", "patched", "verdict"),
    [
        ("pip", "1.0", ">= 2.0, < 3.0", "3.0", "out"),
        ("pip", "2.5", ">= 2.0, < 3.0", "3.0", "affected"),
        ("pip", "2.5", ">= 2.0, < 3.0", "2.4", "fixed"),  # contradictory data: the fix named wins, and it is bounded
        ("pip", "3.14.4", ">=3.10.6", "3.10.11", "closed"),
        ("pip", "3.10.8", ">=3.10.6", "3.10.11", "affected"),
        ("pip", "5.0", ">= 4.5.0", None, "affected"),
        # a version that two ranges hold is fixed only if each of them has a fix below it that is above its own bound
        ("pip", "2.5", ">= 1.0, < 3.0 || >= 2.0, < 4.0", "1.5", "affected"),
        ("pip", "2.5", ">= 1.0, < 3.0 || >= 2.0, < 4.0", "2.2", "fixed"),
    ],
)
def test_the_verdicts_say_why_a_version_is_cleared(
    ecosystem: str, installed: str, vulnerable: str, patched: str | None, verdict: str
) -> None:
    """Test `out`, `fixed`, `closed` (read as fixed, and listed as such) and `affected`."""
    assert ra.assess(ecosystem, installed, vulnerable, patched) == verdict


def test_the_ranges_are_parsed_to_the_alternatives_they_mean() -> None:
    """Test the shape of an "and" of two bounds, an "or" of lines and the pairs per release line."""
    version = ra.parse_version

    assert ra.parse_range("pip", ">= 4.5.0, <= 4.16.0") == [
        [(">=", version("pip", "4.5.0")), ("<=", version("pip", "4.16.0"))]
    ]
    assert len(ra.parse_range("npm", ">=2.9.18,<3.0.0,>=3.2.9,<4.0.0")) == 2
    assert len(ra.parse_range("npm", "<1.1.17, >= 2.0.0 < 2.1.3, 4.0.0 - 5.0.7")) == 3
    assert len(ra.parse_range("npm", "< 6.28.1; 7.0.0 < 7.29.1")) == 2
    assert ra.parse_range("npm", "*") == [[]]


def test_a_not_equal_is_no_upper_bound_and_no_range_holds_one() -> None:
    """Test that `!=` bounds nothing: a range that holds one is unclear, and the helper does not count it."""
    version = ra.parse_version("pip", "1.0")

    assert not ra._has_upper_bound([("!=", version)])  # noqa: SLF001
    assert ra._has_upper_bound([("<", version)])  # noqa: SLF001
    assert ra._has_upper_bound([("<=", version)])  # noqa: SLF001
    assert ra._has_upper_bound([("=", version)])  # noqa: SLF001
    assert not ra._has_upper_bound([(">=", version)])  # noqa: SLF001
    with pytest.raises(ra.UnclearRange):
        ra.parse_range("pip", "!= 1.0")


def test_semver_precedence_follows_the_specification() -> None:
    """Test the order of the semver 2.0 specification: numeric before alphanumeric identifiers, a release last."""
    ordered = ["1.0.0-alpha", "1.0.0-alpha.1", "1.0.0-alpha.beta", "1.0.0-beta", "1.0.0-beta.2", "1.0.0-beta.11"]
    ordered += ["1.0.0-rc.1", "1.0.0", "1.0.1", "1.10.0", "2.0.0"]
    versions = [ra.SemVer.parse(text) for text in ordered]

    assert versions == sorted(versions)
    assert ra.SemVer.parse("1.0.0+build.1") == ra.SemVer.parse("1.0.0+build.2")
    assert str(ra.SemVer.parse("v1.2.3")) == "v1.2.3"
    assert ra.SemVer.parse("v1.2.3").release == (1, 2, 3)


@pytest.mark.parametrize(
    ("installed", "patched", "fixed"),
    [
        ("4.1.3", "4.2.4", "4.2.4"),
        ("4.2.4", "4.2.4", None),
        ("1.4.0", "1.3.5, 1.4.2", "1.4.2"),
        ("1.3.0", "1.3.5, 1.4.2", "1.3.5"),
        ("1.3.0", "1.4.2, 1.3.5", "1.3.5"),  # the lowest of its own release line, not the first written
        ("0.16.3", "0.17.1, 0.16.6", "0.16.6"),
        ("1.0", "2.0, 1.5", "1.5"),
        ("1.0", "3.0, 2.0", "2.0"),  # none of its line: the lowest
        ("6.1.0", ">= 6.21.2", "6.21.2"),
        ("1.0", None, None),
        ("1.0", "None", None),
        ("1.0", "", None),
        ("1.0", "0", None),
    ],
)
def test_the_fixed_version_is_the_lowest_one_above_the_locked_version(
    installed: str, patched: str | None, fixed: str | None
) -> None:
    """Test which fixed version an affected package is told to move to (its own release line first)."""
    assert ra.first_fixed("pip", installed, patched) == fixed


# --------------------------------------------------------------------------------------------------------------------
# the fuzz: ranges rendered in the spellings the parser knows, against an independent reading of them
# --------------------------------------------------------------------------------------------------------------------

PIP_VERSIONS = [
    "0.9.0",
    "0.10.0",
    "1.0.0",
    "1.0.1",
    "1.2.0",
    "1.2.3",
    "2.0.0rc1",
    "2.0.0",
    "2.0.0.post1",
    "2.1.0.dev1",
    "3.0.0b2",
    "3.0.0",
    "10.0.0",
]
NPM_VERSIONS = [
    "0.9.0",
    "1.0.0",
    "1.0.1",
    "1.2.0",
    "1.2.3",
    "2.0.0-rc.1",
    "2.0.0-rc.10",
    "2.0.0-rc.2",
    "2.0.0",
    "2.1.0-alpha.beta",
    "2.1.0",
    "3.0.0-0",
    "3.0.0",
    "10.0.0",
]


def _semver_compare(a: str, b: str) -> int:
    """Compare two npm versions by the specification, written apart from the script."""

    def split(text: str) -> tuple[tuple[int, ...], list[str]]:
        core, _, pre = text.partition("-")
        return tuple(int(x) for x in core.split(".")), pre.split(".") if pre else []

    (core_a, pre_a), (core_b, pre_b) = split(a), split(b)
    if core_a != core_b:
        return -1 if core_a < core_b else 1
    if pre_a == pre_b:
        return 0
    if not pre_a or not pre_b:
        return 1 if not pre_a else -1
    for x, y in zip(pre_a, pre_b, strict=False):
        if x == y:
            continue
        if x.isdigit() and y.isdigit():
            return -1 if int(x) < int(y) else 1
        if x.isdigit() != y.isdigit():
            return -1 if x.isdigit() else 1
        return -1 if x < y else 1
    return -1 if len(pre_a) < len(pre_b) else 1


def _cmp(ecosystem: str, a: str, b: str) -> int:
    if ecosystem == "npm":
        return _semver_compare(a, b)
    return (Version(a) > Version(b)) - (Version(a) < Version(b))


def _sorted(ecosystem: str, versions: list[str]) -> list[str]:
    return sorted(versions, key=cmp_to_key(lambda a, b: _cmp(ecosystem, a, b)))


OPERATORS = {">": operator.gt, ">=": operator.ge, "<": operator.lt, "<=": operator.le}


def _holds(ecosystem: str, version: str, interval: tuple[tuple[str, str] | None, tuple[str, str] | None]) -> bool:
    lower, upper = interval
    return (lower is None or OPERATORS[lower[0]](_cmp(ecosystem, version, lower[1]), 0)) and (
        upper is None or OPERATORS[upper[0]](_cmp(ecosystem, version, upper[1]), 0)
    )


def _line(ecosystem: str, version: str) -> tuple[int, ...]:
    """Return the release line of a version, written apart from the script: the major, the minor below 1.0."""
    release = (
        Version(version).release
        if ecosystem == "pip"
        else tuple(int(x) for x in version.split("-", maxsplit=1)[0].split("."))
    )
    release = (*release, 0, 0)
    return (0, release[1]) if release[0] == 0 else (release[0],)


def _interval(rng: random.Random, ecosystem: str, versions: list[str]) -> tuple[Any, Any]:
    ordered = _sorted(ecosystem, versions)
    shape = rng.choice(["both", "both", "both", "lower", "upper"])
    i, j = sorted(rng.sample(range(len(ordered)), 2))
    lower = (rng.choice([">", ">="]), ordered[i]) if shape in ("both", "lower") else None
    upper = (rng.choice(["<", "<="]), ordered[j]) if shape in ("both", "upper") else None
    return lower, upper


def _render(rng: random.Random, intervals: list[Any]) -> str:
    def one(interval: Any) -> str:  # noqa: ANN401
        lower, upper = interval
        if lower and upper:
            style = rng.choice(["comma", "tight", "space", "and", "unicode", "hyphen"])
            if style == "hyphen" and (lower[0], upper[0]) == (">=", "<="):
                return f"{lower[1]} - {upper[1]}"
            spaced = [f"{op} {v}" for op, v in (lower, upper)]
            if style == "tight":
                return ",".join(f"{op}{v}" for op, v in (lower, upper))
            if style == "space":
                return " ".join(f"{op}{v}" for op, v in (lower, upper))
            if style == "and":
                return " and ".join(spaced)
            if style == "unicode":
                return ", ".join(s.replace(">=", "≥").replace("<=", "≤") for s in spaced)
            return ", ".join(spaced)
        return rng.choice(["{op} {v}", "{op}{v}"]).format(op=(lower or upper)[0], v=(lower or upper)[1])

    pairs = all(lower and upper for lower, upper in intervals) and len(intervals) >= 2
    if pairs and rng.random() < 0.4:
        return ",".join(f"{lo[0]}{lo[1]},{up[0]}{up[1]}" for lo, up in intervals)
    return rng.choice([" || ", "; "]).join(one(i) for i in intervals)


@pytest.mark.parametrize(("ecosystem", "versions"), [("pip", PIP_VERSIONS), ("npm", NPM_VERSIONS)])
def test_fuzz_the_membership_agrees_with_an_independent_reading_of_the_ranges(
    ecosystem: str, versions: list[str]
) -> None:
    """Test 3,000 random ranges in every spelling against the ordering of `packaging` and a semver written apart."""
    rng = random.Random(4378)  # noqa: S311
    for _ in range(3000):
        intervals = [_interval(rng, ecosystem, versions) for _ in range(rng.choice([1, 1, 2, 3]))]
        text = _render(rng, intervals)
        installed = rng.choice(versions)
        expected = any(_holds(ecosystem, installed, interval) for interval in intervals)

        assert ra.in_range(ecosystem, installed, text) is expected, (installed, text)


def _patched(rng: random.Random, fixes: list[str]) -> tuple[str, set[str]]:
    """Render fixes in the spellings of `patched_versions`, with entries that name no fix mixed in.

    Returns the text and the fixes written `> x`, which the version x itself has not reached.
    """
    exclusive: set[str] = set()
    entries = []
    for version in fixes:
        form = rng.choice(["{v}", ">= {v}", ">={v}", "v{v}", "> {v}"])
        if form.startswith(">") and not form.startswith(">="):
            exclusive.add(version)
        entries.append(form.format(v=version))
    noise = rng.choice(["", "", "0", "*", "2.x", "2"])
    if noise:
        entries.append(noise)
    rng.shuffle(entries)
    return rng.choice([", ", ",", " || ", "; "]).join(entries), exclusive


@pytest.mark.parametrize(("ecosystem", "versions"), [("pip", PIP_VERSIONS), ("npm", NPM_VERSIONS)])
def test_fuzz_no_false_negative_and_no_unnamed_fix(ecosystem: str, versions: list[str]) -> None:
    """Test the property that matters: a covered version is cleared only by a fix that is named and reached.

    `assess` never says `affected` for a version that no range holds, and never clears one that a range holds
    unless some named fix is at or below it (the false negatives, held to zero), whatever the spelling of the
    fixes. In a range that ends, a fix of a lower release line never clears a version of a higher one: only a
    fix of the version's own line does. A fix written `> x` is not reached by x itself.
    """
    rng = random.Random(4379)  # noqa: S311
    covered = 0
    bounded_covered = 0
    for _ in range(6000):
        intervals = [_interval(rng, ecosystem, versions) for _ in range(rng.choice([1, 1, 2]))]
        vulnerable = _render(rng, intervals)
        installed = rng.choice(versions)
        fixes = rng.sample(versions, rng.choice([0, 1, 1, 2, 3]))
        patched, exclusive = _patched(rng, fixes) if fixes else (rng.choice(["", "None", "0", "*", "2.x"]), set())
        holding = [i for i in intervals if _holds(ecosystem, installed, i)]
        reached = [
            f
            for f in fixes
            if _cmp(ecosystem, f, installed) < 0 or (f not in exclusive and _cmp(ecosystem, f, installed) == 0)
        ]
        same_line = [f for f in reached if _line(ecosystem, f) == _line(ecosystem, installed)]
        ends = bool(holding) and all(upper is not None for _, upper in holding)

        verdict = ra.assess(ecosystem, installed, vulnerable, patched)

        context = (installed, vulnerable, patched)
        if not holding:
            assert verdict == "out", context
            continue
        covered += 1
        bounded_covered += ends
        if not reached:
            assert verdict == "affected", context  # the false negative: cleared by a fix nobody named
        if ends and not same_line:
            assert verdict == "affected", context  # cleared across release lines, inside a range that ends
        if verdict in ("fixed", "closed"):
            assert reached, context
            assert same_line or not ends, context
    assert covered > 800
    assert bounded_covered > 300


# --------------------------------------------------------------------------------------------------------------------
# the corpus: every entry of the recorded advisories of nuxt, vite, h3, pypdf, cryptography, fastmcp, aiohttp, ...
# --------------------------------------------------------------------------------------------------------------------

_VERSION_TEXT = re.compile(r"v?\d+\.\d+(?:\.\d+)?(?:[-+][0-9A-Za-z.-]+)?")


def _corpus() -> list[tuple[str, str, str, str]]:
    entries = []
    for name in sorted(RECORDED.glob("advisories_*.json")):
        for advisory in json.loads(name.read_text(encoding="utf-8")):
            for vulnerability in advisory["vulnerabilities"]:
                package = vulnerability.get("package") or {}
                ecosystem = {"pip": "pip", "npm": "npm"}.get(package.get("ecosystem"))
                if ecosystem:
                    entries.append(
                        (
                            ecosystem,
                            advisory["ghsa_id"],
                            vulnerability["vulnerable_version_range"] or "",
                            vulnerability["patched_versions"] or "",
                        )
                    )
    return entries


CORPUS = _corpus()


def _probes(ecosystem: str, *texts: str) -> list[str]:
    found: set[str] = set()
    for text in texts:
        for match in _VERSION_TEXT.findall(text):
            version = match.removeprefix("v")
            try:
                ra.parse_version(ecosystem, version)
            except ra.UnclearRange:
                continue
            found.add(version)
            core = version.split("-")[0].split("+")[0].split(".")
            if len(core) == 3 and core[2].isdigit():
                for bumped in (
                    f"{core[0]}.{core[1]}.{int(core[2]) + 1}",
                    f"{core[0]}.{core[1]}.{max(int(core[2]) - 1, 0)}",
                ):
                    found.add(bumped)
    return sorted(found)


def test_the_corpus_is_real_and_large() -> None:
    """Test that the recorded advisories hold the hard cases: the entries and the repositories they come from."""
    assert len(CORPUS) > 400
    assert any("||" in patched for *_, patched in CORPUS)
    assert any(", <" in patched for *_, patched in CORPUS)
    assert any(vulnerable.count(",") >= 5 for _, _, vulnerable, _ in CORPUS)


def test_the_corpus_has_almost_no_range_the_comparer_cannot_read() -> None:
    """Test that the ranges of 450 real entries are read, but for the few that are no range."""
    unclear = []
    for ecosystem, ghsa, vulnerable, _ in CORPUS:
        try:
            ra.parse_range(ecosystem, vulnerable)
        except ra.UnclearRange:
            unclear.append((ghsa, vulnerable))

    assert len(unclear) <= 6, unclear


def test_no_real_entry_clears_a_version_with_a_fix_nobody_named() -> None:
    """Test every real entry at every version its texts name and one patch either side of it.

    The oracle reads the numbers of the text apart from the comparer: a version that the range holds and that no
    version of `patched_versions` is at or below must be `affected`, and a version cleared must have one at or
    below it (or be inside a bounded range of fixed versions).
    """
    checked = 0
    for ecosystem, ghsa, vulnerable, patched in CORPUS:
        named = []
        for text in _VERSION_TEXT.findall(patched):
            try:
                named.append(ra.parse_version(ecosystem, text.removeprefix("v")))
            except ra.UnclearRange:
                continue
        for probe in _probes(ecosystem, vulnerable, patched):
            try:
                verdict = ra.assess(ecosystem, probe, vulnerable, patched)
                holds = ra.in_range(ecosystem, probe, vulnerable)
            except ra.UnclearRange:
                continue
            checked += 1
            installed = ra.parse_version(ecosystem, probe)
            at_or_below = [v for v in named if v <= installed]
            assert holds == (verdict != "out"), (ghsa, probe, vulnerable)
            if holds and not at_or_below:
                assert verdict == "affected", (ghsa, probe, vulnerable, patched)
            if verdict in ("fixed", "closed"):
                assert at_or_below, (ghsa, probe, vulnerable, patched)
    assert checked > 2000


def test_real_entries_of_h3_and_nuxt_and_vite_are_read_as_their_authors_meant() -> None:
    """Test entries copied from the recorded advisories: the h3 lines, nuxt's bounded fixes and vite's pairs."""
    h3 = "<= 2.0.1-rc.16", ">= 1.15.9 || >= v2.0.1-rc.17"
    nuxt = ">= 3.4.3, <= 3.21.5", "> 3.21.5, < 4.0.0-alpha.1"
    vite = ">=2.9.18,<3.0.0,>=3.2.9,<4.0.0,>=4.5.3,<5.0.0,>=5.2.6,<=5.4.20", "5.4.21"

    assert [ra.is_affected("npm", v, *h3) for v in ("1.15.8", "1.15.9", "1.15.11", "2.0.0", "2.0.1-rc.16")] == [
        True,
        False,
        False,
        True,
        True,
    ]
    assert [ra.is_affected("npm", v, *h3) for v in ("2.0.1-rc.17", "2.0.1")] == [False, False]
    assert [ra.is_affected("npm", v, *nuxt) for v in ("3.4.2", "3.4.3", "3.21.5", "3.21.6", "4.0.0")] == [
        False,
        True,
        True,
        False,
        False,
    ]
    assert [
        ra.is_affected("npm", v, *vite)
        for v in ("2.9.17", "2.9.18", "3.0.0", "3.2.9", "4.5.3", "5.2.5", "5.4.20", "5.4.21")
    ] == [
        False,
        True,
        False,
        True,
        True,
        False,
        True,
        False,
    ]


def test_no_real_entry_clears_across_release_lines_inside_a_range_that_ends() -> None:
    """Test every real entry at the versions its texts name: in a range that ends only a fix of its own line clears.

    The oracle reads the numbers of the texts apart from the comparer, and the release line as the major version (the
    minor below 1.0). A bounded range of fixed versions in `patched_versions` may clear too.
    """
    checked = 0
    for ecosystem, ghsa, vulnerable, patched in CORPUS:
        try:
            alternatives = ra.parse_range(ecosystem, vulnerable)
        except ra.UnclearRange:
            continue
        for probe in _probes(ecosystem, vulnerable, patched):
            installed = ra.parse_version(ecosystem, probe)
            holding = [c for c in alternatives if ra._holds(installed, c)]  # noqa: SLF001
            if not holding or not all(ra._has_upper_bound(c) for c in holding):  # noqa: SLF001
                continue
            try:
                verdict = ra.assess(ecosystem, probe, vulnerable, patched)
            except ra.UnclearRange:
                continue
            checked += 1
            if verdict in ("fixed", "closed"):
                named = [
                    text.removeprefix("v")
                    for text in _VERSION_TEXT.findall(patched)
                    if _parses(ecosystem, text.removeprefix("v"))
                ]
                same_line = [
                    v
                    for v in named
                    if _line(ecosystem, v) == _line(ecosystem, probe) and _cmp(ecosystem, v, probe) <= 0
                ]
                try:
                    in_patched_range = ra.in_range(ecosystem, probe, patched)
                except ra.UnclearRange:
                    in_patched_range = False
                assert same_line or in_patched_range, (ghsa, probe, vulnerable, patched)
    assert checked > 400


def _parses(ecosystem: str, text: str) -> bool:
    try:
        ra.parse_version(ecosystem, text)
    except ra.UnclearRange:
        return False
    return True


def test_the_strict_grammar_refuses_a_range_of_more_than_500_characters_however_fine_its_parts() -> None:
    """Test the length limit of `parse_range` itself, and of `in_range` through it."""
    text = " || ".join(f">= {i}.0, < {i}.1" for i in range(60))

    assert len(text) > 500
    with pytest.raises(ra.UnclearRange, match="too long"):
        ra.parse_range("pip", text)
    with pytest.raises(ra.UnclearRange, match="too long"):
        ra.in_range("pip", "5.0.0", text)
    assert ra.in_range("pip", "99.0.0", text[:200].rsplit(" || ", 1)[0]) is False
