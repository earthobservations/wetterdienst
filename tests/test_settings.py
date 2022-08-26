# -*- coding: utf-8 -*-
# Copyright (C) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest


@pytest.mark.cflake
def test_settings(caplog):
    """Check Settings object"""
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
