# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from pathlib import Path

import pytest
from pytest_notebook.nb_regression import NBRegressionError, NBRegressionFixture
from pytest_notebook.notebook import NBConfigValidationError

EXAMPLE_DIR = Path(__file__).parent.parent.parent / "examples"


@pytest.mark.slow
@pytest.mark.remote
def test_wetterdienst_notebook():
    """Test for climate_observations jupyter notebook"""
    fixture = NBRegressionFixture(
        exec_notebook=True,
        force_regen=True,
    )
    try:
        fixture.check(EXAMPLE_DIR / "wetterdienst_notebook.ipynb")
    except (NBConfigValidationError, NBRegressionError):
        # only raise execution errors, diff changes on daily basis due to station listing changes
        pass
