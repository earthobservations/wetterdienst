import pytest
from dash.testing.application_runners import import_app
from dash.testing.composite import DashComposite
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC


@pytest.fixture
def dash_tre(request, dash_thread_server, tmpdir):
    with DashCompositePlus(
        dash_thread_server,
        browser=request.config.getoption("webdriver"),
        remote=request.config.getoption("remote"),
        remote_url=request.config.getoption("remote_url"),
        headless=request.config.getoption("headless"),
        options=request.config.hook.pytest_setup_options(),
        download_path=tmpdir.mkdir("download").strpath,
        percy_assets_root=request.config.getoption("percy_assets"),
        percy_finalize=request.config.getoption("nopercyfinalize"),
        pause=request.config.getoption("pause"),
    ) as dc:
        yield dc


class DashCompositePlus(DashComposite):
    """
    Improve vanilla library with some convenience event handlers.
    """

    def wait_for_element_by_id_clickable(self, element_id, timeout=None):
        """
        Explicit wait until the element is clickable.

        Derived from `dash.testing.browser::wait_for_element_by_id()` and
        https://stackoverflow.com/q/56085152.
        """
        return self._wait_for(
            EC.element_to_be_clickable,
            ((By.ID, element_id),),
            timeout,
            "timeout {}s => waiting for element id {}".format(
                timeout if timeout else self._wait_timeout, element_id
            ),
        )


@pytest.fixture(scope="function")
def wetterdienst_ui(dash_tre):

    # Import Dash application in testing mode.
    app = import_app("wetterdienst.ui.dash.app")

    # Start testing server and wait until page is loaded.
    dash_tre.start_server(app)
    dash_tre.wait_for_page(timeout=10)
