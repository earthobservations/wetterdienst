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


@pytest.mark.xfail
@pytest.mark.slow
@pytest.mark.ui
def test_app_data_values(wetterdienst_ui, dash_duo):
    """
    Verify if data for "values" has been correctly propagated.
    """

    dash_duo.wait_for_element_by_id("hidden-div")

    dom: BeautifulSoup = dash_duo.dash_innerhtml_dom

    data_element = dom.find(attrs={"id": "hidden-div"})
    data = json.loads(data_element.text)
    assert data["columns"] == ["todo-fixme"]
    assert len(data["data"]) == -999
