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
@pytest.mark.ui
def test_app_layout(wetterdienst_ui, dash_tre):

    # Sanity check if we are on the right page.
    assert dash_tre.find_element("h1").text == "Wetterdienst UI"

    # Roughly verify the application elements.
    assert dash_tre.find_element("#navigation")
    assert dash_tre.find_element("#map")
    assert dash_tre.find_element("#graph")


@pytest.mark.slow
@pytest.mark.ui
def test_app_data_stations(wetterdienst_ui, dash_tre):
    """
    Verify if data for "stations" has been correctly propagated.
    """

    # Wait for data element.
    dash_tre.wait_for_element_by_id("hidden-div-metadata", timeout=5)
    time.sleep(0.5)

    # Read payload from data element.
    dom: BeautifulSoup = dash_tre.dash_innerhtml_dom
    data_element = dom.find(attrs={"id": "hidden-div-metadata"})
    data = json.loads(data_element.text)

    # Verify data.
    assert data["columns"] == [
        "station_id",
        "from_date",
        "to_date",
        "height",
        "latitude",
        "longitude",
        "station_name",
        "state",
    ]
    assert len(data["data"]) == 511


@pytest.mark.slow
@pytest.mark.ui
def test_app_data_values(wetterdienst_ui, dash_tre):
    """
    Verify if data for "values" has been correctly propagated.
    """

    # Select weather station.
    dash_tre.wait_for_element_by_id("select-weather-stations")
    dash_tre.select_dcc_dropdown("#select-weather-stations", value="Anklam")

    # Select variable.
    dash_tre.wait_for_element_by_id("select-variable")
    dash_tre.wait_for_element_by_id_clickable("select-variable")
    dash_tre.select_dcc_dropdown("#select-variable", value="temperature_air_200")

    # Wait for data element.
    dash_tre.wait_for_element_by_id("hidden-div")

    # Read payload from data element.
    dom: BeautifulSoup = dash_tre.dash_innerhtml_dom
    data_element = dom.find(attrs={"id": "hidden-div"})
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
