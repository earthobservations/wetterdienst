from pathlib import Path

from pytest_notebook.nb_regression import NBRegressionFixture

EXAMPLE_DIR = Path(__file__).parent.parent.parent / "example"

FIXTURE = NBRegressionFixture(
    diff_ignore=(
        "/metadata/language_info",  # Python version depends on testing
        "/cells/*/outputs/*/data/image/png",  # pictures have random hashes
        "/cells/*/outputs/*/text"
    ),
    force_regen=True,
)


def test_simple_example():
    """ Test for simple_example jupyter notebook """
    FIXTURE.check(EXAMPLE_DIR / "simple_example.ipynb")
