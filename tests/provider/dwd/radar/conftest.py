import pytest


@pytest.fixture
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
        "neu",
        "nhb",
        "oft",
        "pro",
        "ros",
        "tur",
        "umd",
    ]


@pytest.fixture
def prefixed_radar_locations(radar_locations):
    return [f"de{location}" for location in radar_locations]
