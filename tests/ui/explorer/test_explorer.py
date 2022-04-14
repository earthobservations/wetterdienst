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
from selenium.common.exceptions import ElementNotInteractableException


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


@pytest.mark.xfail
@pytest.mark.slow
@pytest.mark.cflake
@pytest.mark.explorer
def test_app_data_stations_success(wetterdienst_ui, dash_tre):
    """
    Verify if data for "stations_result" has been correctly propagated.
    """

    # Wait for data element.
    dash_tre.wait_for_element_by_id("dataframe-stations_result", timeout=10)
    time.sleep(1)

    # Read payload from data element.
    dom: BeautifulSoup = dash_tre.dash_innerhtml_dom
    data_element = dom.find(attrs={"id": "dataframe-stations_result"})
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
    assert len(data["data"]) >= 511


@pytest.mark.slow
@pytest.mark.cflake
@pytest.mark.explorer
def test_app_data_stations_failed(wetterdienst_ui, dash_tre):
    """
    Verify if data for "stations_result" has been correctly propagated.
    """
    # Select provider.
    dash_tre.wait_for_element_by_id("select-provider")
    dash_tre.select_dcc_dropdown("#select-provider", value="DWD")

    # Select network.
    dash_tre.wait_for_element_by_id("select-network")
    dash_tre.select_dcc_dropdown("#select-network", value="OBSERVATION")

    # Select resolution.
    dash_tre.wait_for_element_by_id("select-resolution")
    dash_tre.select_dcc_dropdown("#select-resolution", value="DAILY")

    # Select dataset.
    dash_tre.wait_for_element_by_id("select-dataset")
    dash_tre.select_dcc_dropdown("#select-dataset", value="CLIMATE_SUMMARY")

    # Select parameter.
    dash_tre.wait_for_element_by_id("select-parameter")
    dash_tre.select_dcc_dropdown("#select-parameter", value="PRECIPITATION_HEIGHT")

    # Select period.
    dash_tre.wait_for_element_by_id("select-period")
    dash_tre.select_dcc_dropdown("#select-period", value="NOW")

    # Wait for data element.
    dash_tre.wait_for_element_by_id("dataframe-stations_result", timeout=5)
    time.sleep(0.5)

    # Wait for status element.
    dash_tre.wait_for_contains_text("#status-response-stations_result", "No data", timeout=2)
    dash_tre.wait_for_contains_text("#status-response-values", "No data", timeout=2)
    dash_tre.wait_for_contains_text("#map", "No data to display", timeout=2)


@pytest.mark.slow
@pytest.mark.cflake
@pytest.mark.explorer
def test_options_reset(wetterdienst_ui, dash_tre):
    """
    Verify if data for "stations_result" has been correctly propagated.
    """
    # Select provider.
    dash_tre.wait_for_element_by_id("select-provider")
    dash_tre.select_dcc_dropdown("#select-provider", value="DWD")

    # Select network.
    dash_tre.wait_for_element_by_id("select-network")
    dash_tre.select_dcc_dropdown("#select-network", value="OBSERVATION")

    # Select resolution.
    dash_tre.wait_for_element_by_id("select-resolution")
    dash_tre.select_dcc_dropdown("#select-resolution", value="DAILY")

    # Select dataset.
    dash_tre.wait_for_element_by_id("select-dataset")
    dash_tre.select_dcc_dropdown("#select-dataset", value="CLIMATE_SUMMARY")

    # Select parameter.
    dash_tre.wait_for_element_by_id("select-parameter")
    dash_tre.select_dcc_dropdown("#select-parameter", value="PRECIPITATION_HEIGHT")

    # Select period.
    dash_tre.wait_for_element_by_id("select-period")
    dash_tre.select_dcc_dropdown("#select-period", value="HISTORICAL")

    # Set another provider
    dash_tre.wait_for_element_by_id("select-provider")
    dash_tre.select_dcc_dropdown("#select-provider", value="ECCC")

    # Check other options for reset
    dash_tre.wait_for_contains_text("#select-network", "")
    dash_tre.wait_for_contains_text("#select-resolution", "")
    dash_tre.wait_for_contains_text("#select-dataset", "")
    dash_tre.wait_for_contains_text("#select-parameter", "")
    dash_tre.wait_for_contains_text("#select-period", "")


@pytest.mark.xfail(raises=ElementNotInteractableException)
@pytest.mark.slow
@pytest.mark.cflake
@pytest.mark.explorer
def test_app_data_values(wetterdienst_ui, dash_tre):
    """
    Verify if data for "values" has been correctly propagated.
    """
    # Select provider.
    dash_tre.wait_for_element_by_id("select-provider")
    dash_tre.select_dcc_dropdown("#select-provider", value="DWD")

    # Select network.
    dash_tre.wait_for_element_by_id("select-network")
    dash_tre.select_dcc_dropdown("#select-network", value="OBSERVATION")

    # Select resolution.
    dash_tre.wait_for_element_by_id("select-resolution")
    dash_tre.select_dcc_dropdown("#select-resolution", value="HOURLY")

    # Select dataset.
    dash_tre.wait_for_element_by_id("select-dataset")
    dash_tre.select_dcc_dropdown("#select-dataset", value="TEMPERATURE_AIR")
    time.sleep(0.5)

    # Select parameter.
    dash_tre.wait_for_element_by_id("select-parameter")
    dash_tre.select_dcc_dropdown("#select-parameter", value="TEMPERATURE_AIR_MEAN_200")
    time.sleep(0.5)

    # Select period.
    dash_tre.wait_for_element_by_id("select-period")
    dash_tre.select_dcc_dropdown("#select-period", value="RECENT")
    time.sleep(0.5)

    # Select weather station.
    dash_tre.wait_for_element_by_id("select-station")
    dash_tre.select_dcc_dropdown("#select-station", value="Anklam")
    time.sleep(0.5)

    # Wait for data element.
    dash_tre.wait_for_element_by_id("dataframe-values")
    time.sleep(0.5)

    # Wait for status element.
    dash_tre.wait_for_contains_text("#status-response", "Records", timeout=20)
    dash_tre.wait_for_contains_text("#status-response", "Begin date", timeout=20)

    # Read payload from data element.
    dom: BeautifulSoup = dash_tre.dash_innerhtml_dom
    data_element = dom.find(attrs={"id": "dataframe-values"})
    data = json.loads(data_element.text)

    # Verify data.
    assert data["columns"] == ["station_id", "dataset", "parameter", "date", "value"]
    assert len(data["data"]) == 13200


@pytest.mark.slow
@pytest.mark.cflake
@pytest.mark.explorer
def test_dwd_mosmix_options(wetterdienst_ui, dash_tre):
    """
    Verify if data for "values" has been correctly propagated.
    """
    # Select provider.
    dash_tre.wait_for_element_by_id("select-provider")
    dash_tre.select_dcc_dropdown("#select-provider", value="DWD")

    # Select network.
    dash_tre.wait_for_element_by_id("select-network")
    dash_tre.select_dcc_dropdown("#select-network", value="MOSMIX")

    # Select resolution.
    dash_tre.wait_for_element_by_id("select-resolution")
    dash_tre.select_dcc_dropdown("#select-resolution", value="SMALL")

    # Select dataset.
    dash_tre.wait_for_element_by_id("select-dataset")
    dash_tre.select_dcc_dropdown("#select-dataset", value="SMALL")
    time.sleep(0.5)

    # Select parameter.
    dash_tre.wait_for_element_by_id("select-parameter")
    dash_tre.select_dcc_dropdown("#select-parameter", value="TEMPERATURE_AIR_MEAN_200")
    time.sleep(0.5)

    # Select period.
    dash_tre.wait_for_element_by_id("select-period")
    dash_tre.select_dcc_dropdown("#select-period", value="FUTURE")
    time.sleep(0.5)
