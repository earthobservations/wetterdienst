# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE.rst for more info.
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
    """ Test for climate_observations jupyter notebook """
    FIXTURE.check(EXAMPLE_DIR / "climate_observations.ipynb")
