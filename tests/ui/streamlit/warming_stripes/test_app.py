import datetime as dt
from zoneinfo import ZoneInfo

import pytest
from streamlit.testing.v1 import AppTest

from wetterdienst import __version__
from wetterdienst.ui.streamlit.warming_stripes import app


@pytest.mark.cflake
@pytest.mark.remote
def test_warming_stripes():
    app_test = AppTest.from_file(app.__file__)
    app_test.run()
    assert app_test.error == []
    assert app_test.title[0].value == f"Warming Stripes (v{__version__})"
    subheaders = [subheader.value for subheader in app_test.subheader]
    assert subheaders == ["Introduction", "Station", "Warming Stripes", "Credits", "Data", "Settings"]
    selected_station = app_test.selectbox[0].value
    assert selected_station == {
        "station_id": "15000",
        "start_date": dt.datetime(2011, 4, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
        "end_date": dt.datetime(2023, 12, 31, 0, 0, tzinfo=ZoneInfo(key="UTC")),
        "latitude": 50.7983,
        "longitude": 6.0244,
        "height": 231.0,
        "name": "Aachen-Orsbach",
        "state": "Nordrhein-Westfalen",
    }
