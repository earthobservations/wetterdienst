# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Fixtures for DWD radar tests."""

import pytest


@pytest.fixture
def radar_locations() -> list[str]:
    """Provide a list of radar locations."""
    return [
        "asb",
        "boo",
        "drs",
        "eis",
        "ess",
        "fbg",
        "fld",
        "hnr",
        "isn",
        "mem",
        "mhp",
        "neu",
        "nhb",
        "oft",
        "pro",
        "ros",
        "tur",
        "umd",
    ]


@pytest.fixture
def prefixed_radar_locations(radar_locations: list[str]) -> list[str]:
    """Provide a list of prefixed radar locations."""
    return [f"de{location}" for location in radar_locations]


@pytest.fixture
def station_reference_pattern_sorted(radar_locations: list[str]) -> str:
    """Provide a sorted station reference pattern."""
    return "".join([f"({location})?(,)?" for location in radar_locations])


@pytest.fixture
def station_reference_pattern_sorted_prefixed(prefixed_radar_locations: list[str]) -> str:
    """Provide a sorted station reference pattern with prefixed locations."""
    return "".join([f"({location})?(,)?" for location in prefixed_radar_locations])
