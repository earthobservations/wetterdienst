# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""
Setup::

    brew install geckodriver

Run tests::

    pytest -vvvv --webdriver Firefox -k test_ui --capture=no

Documentation:

- https://dash.plotly.com/testing#browser-apis
- https://dash.plotly.com/testing#dash-apis

"""
import json
import time

import pytest
from bs4 import BeautifulSoup


@pytest.mark.slow
@pytest.mark.cflake
@pytest.mark.explorer
def test_app_layout(wetterdienst_ui, dash_tre):

    # Sanity check if we are on the right page.
    assert dash_tre.find_element("h1").text == "Wetterdienst Explorer"

    # Roughly verify the application elements.
    assert dash_tre.find_element("#navigation")
    assert dash_tre.find_element("#map")
    assert dash_tre.find_element("#graph")


@pytest.mark.slow
@pytest.mark.cflake
@pytest.mark.explorer
def test_app_data_stations_success(wetterdienst_ui, dash_tre):
    """
    Verify if data for "stations" has been correctly propagated.
    """

    # Wait for data element.
    dash_tre.wait_for_element_by_id("dataframe-stations", timeout=5)
    time.sleep(1)

    # Read payload from data element.
    dom: BeautifulSoup = dash_tre.dash_innerhtml_dom
    data_element = dom.find(attrs={"id": "dataframe-stations"})
    data = json.loads(data_element.text)

    # Verify data.
    assert data["columns"] == [
        "station_id",
        "from_date",
        "to_date",
        "height",
        "latitude",
        "longitude",
        "name",
        "state",
    ]
    assert len(data["data"]) == 511


@pytest.mark.slow
@pytest.mark.cflake
@pytest.mark.explorer
def test_app_data_stations_failed(wetterdienst_ui, dash_tre):
    """
    Verify if data for "stations" has been correctly propagated.
    """

    # Select parameter.
    dash_tre.wait_for_element_by_id("select-parameter")
    dash_tre.select_dcc_dropdown("#select-parameter", value="extreme_wind")

    # Wait for data element.
    dash_tre.wait_for_element_by_id("dataframe-stations", timeout=5)
    time.sleep(0.5)

    # Wait for status element.
    dash_tre.wait_for_contains_text("#status-response-stations", "No data", timeout=2)
    dash_tre.wait_for_contains_text("#status-response-values", "No data", timeout=2)
    dash_tre.wait_for_contains_text("#map", "No data to display", timeout=2)
    dash_tre.wait_for_contains_text("#graph", "No variable selected", timeout=2)


@pytest.mark.slow
@pytest.mark.cflake
@pytest.mark.explorer
def test_app_data_values(wetterdienst_ui, dash_tre):
    """
    Verify if data for "values" has been correctly propagated.
    """

    # Select parameter.
    dash_tre.wait_for_element_by_id("select-parameter")
    dash_tre.select_dcc_dropdown("#select-parameter", value="air_temperature")

    # Select time resolution.
    dash_tre.wait_for_element_by_id("select-resolution")
    dash_tre.select_dcc_dropdown("#select-resolution", value="hourly")

    # Select period.
    dash_tre.wait_for_element_by_id("select-period")
    dash_tre.select_dcc_dropdown("#select-period", value="recent")

    # Select weather station.
    dash_tre.wait_for_element_by_id("select-station")
    dash_tre.select_dcc_dropdown("#select-station", value="Anklam")

    # Select variable.
    dash_tre.wait_for_element_by_id("select-variable")
    dash_tre.wait_for_element_by_id_clickable("select-variable")
    dash_tre.select_dcc_dropdown("#select-variable", value="temperature_air_200")

    # Wait for data element.
    dash_tre.wait_for_element_by_id("dataframe-values")

    # Wait for status element.
    dash_tre.wait_for_contains_text("#status-response", "Records", timeout=2)
    dash_tre.wait_for_contains_text("#status-response", "Begin date", timeout=2)

    # Read payload from data element.
    dom: BeautifulSoup = dash_tre.dash_innerhtml_dom
    data_element = dom.find(attrs={"id": "dataframe-values"})
    data = json.loads(data_element.text)

    # Verify data.
    assert data["columns"] == [
        "station_id",
        "date",
        "qn_9",
        "temperature_air_200",
        "humidity",
    ]
    assert len(data["data"]) == 13081
