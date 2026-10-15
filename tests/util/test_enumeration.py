# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for enumeration utilities."""

from enum import Enum

import pytest

from wetterdienst.exceptions import InvalidEnumerationError
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.util.enumeration import parse_enumeration_from_template


class _Narrow(Enum):
    """An intermediate enumeration with a member that the base enumeration has none like."""

    ONLY = "only"


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


def test_parse_enumeration_from_template_invalid_lists_the_valid_values() -> None:
    """Test that the refusal says what would have been accepted (GH-2636)."""
    with pytest.raises(InvalidEnumerationError) as raised:
        parse_enumeration_from_template("100_minutes", Resolution)
    message = str(raised.value)
    assert message.startswith("100_minutes could not be parsed from Resolution. Valid values: 1_minute, 5_minutes, ")
    assert message.endswith("monthly, annual")


def test_parse_enumeration_from_template_invalid_for_the_base_lists_its_values() -> None:
    """Test that a member of the intermediate enumeration that the base lacks lists the base's values (GH-2636)."""
    with pytest.raises(InvalidEnumerationError) as raised:
        parse_enumeration_from_template("only", _Narrow, Resolution)
    assert "Valid values: 1_minute," in str(raised.value)
