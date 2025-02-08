# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for enumeration utilities."""

import pytest

from wetterdienst.exceptions import InvalidEnumerationError
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.util.enumeration import parse_enumeration_from_template


@pytest.mark.parametrize(
    "value",
    [
        "minute_1",
        "MINUTE_1",
        "1_minute",
        "1_MINUTE",
    ],
)
def test_parse_enumeration_from_template(value: str) -> None:
    """Test parsing an enumeration."""
    assert parse_enumeration_from_template(value, Resolution) == Resolution.MINUTE_1


def test_parse_enumeration_from_template_invalid() -> None:
    """Test parsing an invalid enumeration."""
    with pytest.raises(InvalidEnumerationError):
        parse_enumeration_from_template("100_minutes", Resolution)
