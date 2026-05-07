# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Fixtures for tests."""

import os
import platform
import sys
import time
from typing import Any

import fsspec.utils as _fsspec_utils
import pytest

from wetterdienst import Info, Settings
from wetterdienst.util.eccodes import ensure_eccodes, ensure_pdbufr

IS_CI = bool(os.environ.get("CI"))
IS_LINUX = platform.system() == "Linux"
IS_LINUX_39 = IS_LINUX and sys.version_info[:2] == (3, 11)
IS_WINDOWS = platform.system() == "Windows"
IS_PYTHON_3_10 = sys.version_info[:2] == (3, 10)
IS_PYTHON_3_14 = sys.version_info[:2] == (3, 14)
ENSURE_ECCODES_PDBUFR = ensure_eccodes() and ensure_pdbufr()

info = Info()


@pytest.fixture(autouse=True, scope="session")
def _worker_unique_cache_dir(tmp_path_factory: pytest.TempPathFactory, worker_id: str) -> None:
    """Give each pytest-xdist worker its own cache directory.

    Multiple workers writing to the same fsspec cache metadata file
    concurrently causes PermissionError (WinError 5) on Windows because
    os.replace() fails when the destination file is held open by another
    process. A per-worker directory eliminates that race entirely.

    The WD_CACHE_DIR env-var is honoured by pydantic-settings at
    Settings() instantiation time, so it takes effect for every Settings()
    created during the session.
    """
    cache = tmp_path_factory.mktemp(f"wd-cache-{worker_id}", numbered=False)
    os.environ["WD_CACHE_DIR"] = str(cache)
    yield
    del os.environ["WD_CACHE_DIR"]


@pytest.fixture(autouse=True, scope="session")
def _patch_windows_atomic_write() -> None:
    """Retry os.replace() inside fsspec on Windows to survive PermissionError.

    Tests that download hundreds of files concurrently (e.g. 1 536 files for
    the 1-minute precipitation dataset) schedule many async tasks in the same
    xdist worker.  All those tasks race to atomically update the single fsspec
    TTL-cache metadata file via os.replace().  On Windows, os.replace() raises
    PermissionError (WinError 5) when the destination is held open by another
    thread at the same instant.

    The fix proxies the ``os`` namespace visible inside ``fsspec.utils`` with
    a thin wrapper whose ``replace()`` retries with exponential back-off
    before re-raising.  The original binding is restored at session teardown.
    """
    if not IS_WINDOWS:
        yield
        return

    _orig_os = _fsspec_utils.os

    class _OsWithRetry:
        """Proxy around the ``os`` module that retries ``replace()`` on Windows."""

        def __getattr__(self, name: str) -> Any:  # noqa: ANN401
            return getattr(_orig_os, name)

        def replace(self, src: str, dst: str) -> None:
            delays = (0.05, 0.1, 0.2, 0.4)
            for delay in delays:
                try:
                    return _orig_os.replace(src, dst)
                except PermissionError:
                    time.sleep(delay)
            # final attempt — let it raise naturally
            return _orig_os.replace(src, dst)

    _fsspec_utils.os = _OsWithRetry()
    yield
    _fsspec_utils.os = _orig_os


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
