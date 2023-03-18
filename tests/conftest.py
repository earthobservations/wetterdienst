import os
import platform
import sys

import pytest

from wetterdienst import Settings


@pytest.fixture
def is_ci():
    return os.environ.get("CI", False)


@pytest.fixture
def is_linux():
    return platform.system() == "Linux"


@pytest.fixture
def is_linux_311(is_linux):
    python_version = sys.version_info[:2]
    return is_linux and python_version == (3, 11)


@pytest.fixture
def is_windows():
    return platform.system() == "Windows"


@pytest.fixture(scope="function")
def default_settings():
    return Settings.default()


# True settings
@pytest.fixture
def settings_skip_empty_true():
    return Settings(ts_skip_empty=True, ignore_env=True)


@pytest.fixture
def settings_dropna_true():
    return Settings(ts_dropna=True, ignore_env=True)


# False settings
@pytest.fixture
def settings_humanize_false():
    return Settings(ts_humanize=False, ignore_env=True)


@pytest.fixture
def settings_humanize_si_false():
    return Settings(ts_humanize=False, ts_si_units=False, ignore_env=True)


@pytest.fixture
def settings_humanize_si_false_wide_shape():
    return Settings(ts_shape="wide", ts_humanize=False, ts_si_units=False, ignore_env=True)


@pytest.fixture
def settings_humanize_false_wide_shape():
    return Settings(ts_shape="wide", ts_humanize=False, ignore_env=True)


@pytest.fixture
def settings_si_false():
    return Settings(ts_si_units=False, ignore_env=True)


@pytest.fixture
def settings_si_false_wide_shape():
    return Settings(ts_shape="wide", ts_si_units=False, ignore_env=True)


@pytest.fixture
def settings_wide_shape():
    return Settings(ts_shape="wide", ignore_env=True)
