import os
import platform
import sys

import pytest

from wetterdienst import Info, Settings
from wetterdienst.util.eccodes import ensure_eccodes, ensure_pdbufr

IS_CI = os.environ.get("CI", False) and True
IS_LINUX = platform.system() == "Linux"
IS_LINUX_39 = IS_LINUX and sys.version_info[:2] == (3, 11)
IS_WINDOWS = platform.system() == "Windows"
ENSURE_ECCODES_PDBUFR = ensure_eccodes() and ensure_pdbufr()

info = Info()


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
def settings_si_true():
    return Settings(ts_si_units=True, ignore_env=True)


@pytest.fixture
def settings_wide_shape():
    return Settings(ts_shape="wide", ignore_env=True)


@pytest.fixture
def metadata():
    return {
        "producer": {
            "doi": "10.5281/zenodo.3960624",
            "name": "wetterdienst",
            "version": info.version,
            "repository": "https://github.com/earthobservations/wetterdienst",
            "documentation": "https://wetterdienst.readthedocs.io",
        },
        "provider": {
            "copyright": "© Deutscher Wetterdienst (DWD), Climate Data Center (CDC)",
            "country": "Germany",
            "name_english": "German Weather Service",
            "name_local": "Deutscher Wetterdienst",
            "url": "https://opendata.dwd.de/climate_environment/CDC/",
        },
    }
