from pathlib import Path

from pytest_notebook.nb_regression import NBRegressionFixture

EXAMPLE_DIR = Path(__file__).parent.parent.parent / "example"

FIXTURE = NBRegressionFixture(
    exec_timeout=50,
    diff_ignore=("/metadata/language_info",),  # Python version will be different
    force_regen=True,
    coverage=False,
    diff_color_words=False,
)


def test_simple_example():
    """ Test for simple_example jupyter notebook """
    FIXTURE.check(EXAMPLE_DIR / "simple_example.ipynb")
