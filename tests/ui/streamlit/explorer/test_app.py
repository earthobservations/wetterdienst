import datetime as dt
import json
from zoneinfo import ZoneInfo

import pytest
from streamlit.testing.v1 import AppTest

from wetterdienst import __version__
from wetterdienst.provider.dwd.observation import DwdObservationMetadata
from wetterdienst.ui.streamlit.explorer import app


@pytest.mark.cflake
@pytest.mark.remote
def test_explorer():
    app_test = AppTest.from_file(app.__file__)
    app_test.run()
    assert app_test.error == []
    assert app_test.title[0].value == f"Wetterdienst Explorer v{__version__}"
    subheaders = [subheader.value for subheader in app_test.subheader]
    assert subheaders == ["Introduction", "Request", "Station", "Values", "Plot", "Credits", "General", "Plotting"]
    assert app_test.selectbox[0].value == "dwd"
    assert app_test.selectbox[1].value == "observation"
    assert app_test.selectbox[2].value == DwdObservationMetadata.daily
    assert app_test.selectbox[3].value == DwdObservationMetadata.daily.climate_summary
    assert app_test.selectbox[4].value == DwdObservationMetadata.daily.climate_summary
    selected_station = app_test.selectbox[5].value
    assert selected_station == {
        "station_id": "00001",
        "start_date": dt.datetime(1937, 1, 1, 0, 0, tzinfo=ZoneInfo(key="UTC")),
        "end_date": dt.datetime(1986, 6, 30, 0, 0, tzinfo=ZoneInfo(key="UTC")),
        "latitude": 47.8413,
        "longitude": 8.8493,
        "height": 478.0,
        "name": "Aach",
        "state": "Baden-Württemberg",
    }
    stats = json.loads(app_test.json[1].value)
    assert stats == [
        {
            "parameter": "cloud_cover_total",
            "count": 17348,
            "min_date": "1937-01-01T00:00:00+00:00",
            "max_date": "1986-06-30T00:00:00+00:00",
        },
        {
            "parameter": "humidity",
            "count": 11292,
            "min_date": "1955-08-01T00:00:00+00:00",
            "max_date": "1986-06-30T00:00:00+00:00",
        },
        {
            "parameter": "precipitation_form",
            "count": 17347,
            "min_date": "1937-01-01T00:00:00+00:00",
            "max_date": "1986-06-30T00:00:00+00:00",
        },
        {
            "parameter": "precipitation_height",
            "count": 17347,
            "min_date": "1937-01-01T00:00:00+00:00",
            "max_date": "1986-06-30T00:00:00+00:00",
        },
        {
            "parameter": "pressure_vapor",
            "count": 11292,
            "min_date": "1955-08-01T00:00:00+00:00",
            "max_date": "1986-06-30T00:00:00+00:00",
        },
        {
            "parameter": "snow_depth",
            "count": 17348,
            "min_date": "1937-01-01T00:00:00+00:00",
            "max_date": "1986-06-30T00:00:00+00:00",
        },
        {
            "parameter": "temperature_air_max_2m",
            "count": 17348,
            "min_date": "1937-01-01T00:00:00+00:00",
            "max_date": "1986-06-30T00:00:00+00:00",
        },
        {
            "parameter": "temperature_air_mean_2m",
            "count": 17348,
            "min_date": "1937-01-01T00:00:00+00:00",
            "max_date": "1986-06-30T00:00:00+00:00",
        },
        {
            "parameter": "temperature_air_min_0_05m",
            "count": 11262,
            "min_date": "1955-08-01T00:00:00+00:00",
            "max_date": "1986-05-31T00:00:00+00:00",
        },
        {
            "parameter": "temperature_air_min_2m",
            "count": 17348,
            "min_date": "1937-01-01T00:00:00+00:00",
            "max_date": "1986-06-30T00:00:00+00:00",
        },
    ]
    assert len(app_test.dataframe[0].value) > 150_000
