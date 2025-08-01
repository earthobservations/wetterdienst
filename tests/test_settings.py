# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.#
"""Tests for settings."""

import logging
import os
import re
from unittest import mock

import pytest

from wetterdienst.settings import Settings

WD_CACHE_DIR_PATTERN = re.compile(r"[\s\S]*wetterdienst(\\Cache)?")
WD_CACHE_ENABLED_PATTERN = re.compile(r"Wetterdienst cache is enabled [CACHE_DIR:[\s\S]*wetterdienst(\\Cache)?]$")


def test_default_settings(caplog: pytest.LogCaptureFixture) -> None:
    """Test default settings."""
    caplog.set_level(logging.INFO)
    default_settings = Settings()
    assert not default_settings.cache_disable
    assert re.match(WD_CACHE_DIR_PATTERN, str(default_settings.cache_dir))
    assert "headers" in default_settings.fsspec_client_kwargs
    assert "User-Agent" in default_settings.fsspec_client_kwargs["headers"]
    assert default_settings.fsspec_client_kwargs["headers"]["User-Agent"].startswith("wetterdienst/")
    assert default_settings.ts_humanize
    assert default_settings.ts_shape == "long"
    assert default_settings.ts_convert_units
    assert not default_settings.ts_skip_empty
    assert default_settings.ts_skip_threshold == 0.95
    assert default_settings.ts_drop_nulls
    assert default_settings.ts_interp_station_distance == {
        "precipitation_height": 20.0,
    }
    # default dict returns 40.0 for any other key
    assert default_settings.ts_interp_station_distance["foo"] == 40.0
    assert default_settings.ts_interp_use_nearby_station_distance == 1
    assert (
        caplog.messages[0]
        == "option 'ts_complete' is only available with option 'ts_drop_nulls=False' and is thus ignored in this request."  # noqa: E501
    )
    assert (
        caplog.messages[1]
        == "option 'skip_empty' is only available with options `ts_drop_nulls=False` and 'ts_complete=True' and is thus ignored in this request."  # noqa: E501
    )
    assert re.match(WD_CACHE_ENABLED_PATTERN, caplog.messages[2])


@mock.patch.dict(os.environ, {})
def test_settings_envs(caplog: pytest.LogCaptureFixture) -> None:
    """Test default settings but with multiple envs set."""
    os.environ["WD_CACHE_DISABLE"] = "1"
    os.environ["WD_TS_SHAPE"] = "wide"
    os.environ["WD_TS_INTERP_STATION_DISTANCE"] = '{"precipitation_height":40.0,"other":42}'
    caplog.set_level(logging.INFO)
    settings = Settings()
    assert (
        caplog.messages[0]
        == "option 'ts_drop_nulls' is only available with option 'ts_shape=long' and is thus ignored in this request."
    )
    assert (
        caplog.messages[1]
        == "option 'skip_empty' is only available with options `ts_drop_nulls=False` and 'ts_complete=True' and is thus ignored in this request."  # noqa: E501
    )
    assert caplog.messages[2] == "Wetterdienst cache is disabled"
    assert settings.ts_shape == "wide"
    assert settings.ts_interp_station_distance == {
        "precipitation_height": 40.0,
        "other": 42.0,
    }
    # default dict returns 40.0 for any other key
    assert settings.ts_interp_station_distance["foo"] == 40.0


@mock.patch.dict(os.environ, {})
def test_settings_mixed(caplog: pytest.LogCaptureFixture) -> None:
    """Test mixed settings."""
    os.environ["WD_CACHE_DISABLE"] = "1"
    os.environ["WD_TS_SKIP_THRESHOLD"] = "0.89"
    os.environ["WD_TS_INTERP_STATION_DISTANCE"] = '{"precipitation_height":40.0,"other":42}'
    caplog.set_level(logging.INFO)
    settings = Settings(
        ts_skip_threshold=0.81,
        ts_convert_units=False,
        ts_interp_station_distance={"just_another": 43},
    )
    assert settings.cache_disable
    assert (
        caplog.messages[0]
        == "option 'ts_complete' is only available with option 'ts_drop_nulls=False' and is thus ignored in this request."  # noqa: E501
    )
    assert (
        caplog.messages[1]
        == "option 'skip_empty' is only available with options `ts_drop_nulls=False` and 'ts_complete=True' and is thus ignored in this request."  # noqa: E501
    )
    assert caplog.messages[2] == "Wetterdienst cache is disabled"  # env variable
    assert settings.ts_shape  # default variable
    assert settings.ts_skip_threshold == 0.81  # argument variable overrules env variable
    assert not settings.ts_convert_units  # argument variable
    assert settings.ts_interp_station_distance == {
        "precipitation_height": 40.0,
        "other": 42.0,
        "just_another": 43.0,
    }
    # default dict returns 40.0 for any other key
    assert settings.ts_interp_station_distance["foo"] == 40.0
