from pathlib import Path

import pytest
from pytest_notebook.nb_regression import NBRegressionFixture

EXAMPLE_DIR = Path(__file__).parent.parent.parent / "example"

FIXTURE = NBRegressionFixture(
    diff_ignore=(
        "/metadata/language_info",  # Python version depends on testing
        "/cells/*/outputs/",
    ),
    force_regen=True,
)


@pytest.mark.slow
def test_jupyter_example():
    """ Test for simple_example jupyter notebook """
    FIXTURE.check(EXAMPLE_DIR / "simple_example.ipynb")
