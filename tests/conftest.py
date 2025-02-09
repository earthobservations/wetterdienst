# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Fixtures for tests."""

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


@pytest.fixture
def default_settings() -> Settings:
    """Provide default settings."""
    return Settings()


@pytest.fixture
def settings_drop_nulls_false() -> Settings:
    """Provide no drop nulls settings."""
    return Settings(ts_drop_nulls=False)


@pytest.fixture
def settings_convert_units_false() -> Settings:
    """Provide no unit conversion settings."""
    return Settings(ts_convert_units=False)


@pytest.fixture
def settings_drop_nulls_false_complete_true() -> Settings:
    """Provide drop nulls and complete settings."""
    return Settings(ts_drop_nulls=False, ts_complete=True)


# True settings
@pytest.fixture
def settings_drop_nulls_false_complete_true_skip_empty_true() -> Settings:
    """Provide drop nulls, complete and skip empty settings."""
    return Settings(ts_drop_nulls=False, ts_complete=True, ts_skip_empty=True)


# False settings
@pytest.fixture
def settings_humanize_false_drop_nulls_false() -> Settings:
    """Provide no humanize and no drop nulls settings."""
    return Settings(ts_humanize=False, ts_drop_nulls=False)


@pytest.fixture
def settings_humanize_false_convert_units_false() -> Settings:
    """Provide no humanize and no unit conversion settings."""
    return Settings(ts_humanize=False, ts_convert_units=False)


@pytest.fixture
def settings_humanize_false_convert_units_false_wide_shape_drop_nulls_true_complete_true() -> Settings:
    """Provide wide shape, no humanize, no unit conversion, drop nulls and complete settings."""
    return Settings(ts_shape="wide", ts_humanize=False, ts_convert_units=False, ts_drop_nulls=False, ts_complete=True)


@pytest.fixture
def settings_humanize_false_wide_shape_drop_nulls_complete() -> Settings:
    """Provide wide shape and no humanize settings."""
    return Settings(ts_shape="wide", ts_humanize=False, ts_drop_nulls=False, ts_complete=True)


@pytest.fixture
def settings_convert_units_false_wide_shape() -> Settings:
    """Provide wide shape and no unit conversion settings."""
    return Settings(ts_shape="wide", ts_convert_units=False)


@pytest.fixture
def settings_wide_shape() -> Settings:
    """Provide wide shape settings."""
    return Settings(ts_shape="wide")


@pytest.fixture
def metadata() -> dict:
    """Provide metadata."""
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
