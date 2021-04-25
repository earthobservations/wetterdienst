# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from pathlib import Path

import pytest
from pytest_notebook.nb_regression import NBRegressionFixture

EXAMPLE_DIR = Path(__file__).parent.parent.parent / "example"


@pytest.mark.slow
@pytest.mark.skip(
    "nbconvert stack has problems, see "
    "https://github.com/jupyter/jupyter_client/issues/637"
)
def test_jupyter_example():
    """ Test for climate_observations jupyter notebook """
    fixture = NBRegressionFixture(
        diff_ignore=(
            "/metadata/language_info",  # Python version depends on testing
            "/cells/*/outputs/",
        ),
        force_regen=True,
    )

    fixture.check(EXAMPLE_DIR / "climate_observations.ipynb")
