import pytest
from dash.testing.application_runners import import_app


@pytest.fixture(scope="function")
def wetterdienst_ui(dash_duo):
    app = import_app("wetterdienst.ui.app")
    dash_duo.start_server(app)
    dash_duo.wait_for_page(timeout=5)
