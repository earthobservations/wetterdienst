# -*- coding: utf-8 -*-
# Copyright (C) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import logging
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest


@pytest.mark.skip(reason="implementation is currently not working in concurrent environment")
@pytest.mark.cflake
def test_settings(caplog):
    """Check Settings object"""
    caplog.set_level(logging.INFO)

    from wetterdienst import Settings

    Settings.default()

    assert not Settings.cache_disable
    assert caplog.messages[0] == "Wetterdienst cache is enabled"

    Settings.cache_disable = True

    assert Settings.cache_disable
    assert caplog.messages[-1] == "Wetterdienst cache is disabled"

    Settings.cache_disable = False

    assert not Settings.cache_disable
    assert caplog.messages[-1] == "Wetterdienst cache is enabled"

    assert Settings.tidy
    assert Settings.humanize
    assert Settings.si_units

    Settings.tidy = False
    assert not Settings.tidy

    with Settings:
        Settings.humanize = False
        assert not Settings.humanize

    assert Settings.humanize

    Settings.default()

    assert Settings.tidy


@pytest.mark.skip(reason="implementation is currently not working in concurrent environment")
def test_settings_concurrent():
    """Check leaking of Settings through threads"""
    from wetterdienst import Settings

    def settings_tidy_concurrent(tidy: bool):
        with Settings:
            Settings.tidy = tidy

            return Settings.tidy

    random_booleans = np.random.choice([True, False], 1000).tolist()

    with ThreadPoolExecutor() as p:
        tidy_array = list(p.map(settings_tidy_concurrent, random_booleans))

    assert random_booleans == tidy_array


@pytest.mark.skip(reason="implementation is currently not working in concurrent environment")
@pytest.mark.cflake
def test_settings_cache_disable(caplog):
    """Check Settings object with default cache_disable in env"""

    from wetterdienst import Settings

    with Settings:
        import os

        os.environ["WD_CACHE_DISABLE"] = "True"

        caplog.set_level(logging.INFO)

        Settings.reset()

        assert Settings.cache_disable

        assert caplog.messages[-1] == "Wetterdienst cache is disabled"
