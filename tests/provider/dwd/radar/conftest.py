# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import pytest


@pytest.fixture(scope="function")
def radar_locations():
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


@pytest.fixture(scope="function")
def prefixed_radar_locations(radar_locations):
    return [f"de{location}" for location in radar_locations]


@pytest.fixture(scope="function")
def station_reference_pattern_sorted(radar_locations):
    return "".join([f"({location})?(,)?" for location in radar_locations])


@pytest.fixture(scope="function")
def station_reference_pattern_sorted_prefixed(prefixed_radar_locations):
    return "".join([f"({location})?(,)?" for location in prefixed_radar_locations])
