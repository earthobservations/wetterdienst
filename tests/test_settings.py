from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pytest

from wetterdienst import Settings


@pytest.mark.cflake
def test_settings():
    """Check Settings object"""
    Settings.default()

    assert not Settings.cache_disable
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

    def settings_tidy_concurrent(tidy: bool):
        with Settings:
            Settings.tidy = tidy

            return Settings.tidy

    random_booleans = np.random.choice([True, False], 1000).tolist()

    with ThreadPoolExecutor() as p:
        tidy_array = list(p.map(settings_tidy_concurrent, random_booleans))

    assert random_booleans == tidy_array
