# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the Stripes app."""

import datetime as dt
from zoneinfo import ZoneInfo

import pytest
from streamlit.testing.v1 import AppTest

from wetterdienst import __version__
from wetterdienst.ui.streamlit.stripes import app


@pytest.mark.cflake
@pytest.mark.remote
def test_stripes() -> None:
    """Test the Stripes app."""
    app_test = AppTest.from_file(app.__file__)
    app_test.run()
    assert app_test.error == []
    assert app_test.title[0].value == f"Stripes (v{__version__})"
    subheaders = [subheader.value for subheader in app_test.subheader]
    assert subheaders == ["Introduction", "Station", "Climate Stripes", "Credits", "Data", "Settings"]
    kind = app_test.selectbox[0]
    assert kind.value == "temperature"
    selected_station = app_test.selectbox[1].value
    del selected_station["end_date"]
    assert selected_station == {
        "resolution": "annual",
        "dataset": "climate_summary",
        "station_id": "15000",
        "start_date": dt.datetime(2011, 4, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
        "latitude": 50.7983,
        "longitude": 6.0244,
        "height": 231.0,
        "name": "Aachen-Orsbach",
        "state": "Nordrhein-Westfalen",
    }
    # change kind to precipitation and run the app again
    kind.select("precipitation")
    app_test.run()
