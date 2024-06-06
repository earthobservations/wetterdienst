# Copyright (C) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import logging
import os
import re
from unittest import mock

from wetterdienst.settings import Settings

WD_CACHE_DIR_PATTERN = re.compile(r"[\s\S]*wetterdienst(\\Cache)?")
WD_CACHE_ENABLED_PATTERN = re.compile(r"Wetterdienst cache is enabled [CACHE_DIR:[\s\S]*wetterdienst(\\Cache)?]$")


def test_default_settings(caplog):
    caplog.set_level(logging.INFO)
    default_settings = Settings.default()
    assert not default_settings.cache_disable
    assert re.match(WD_CACHE_DIR_PATTERN, str(default_settings.cache_dir))
    assert default_settings.fsspec_client_kwargs == {}
    assert default_settings.ts_humanize
    assert default_settings.ts_shape == "long"
    assert default_settings.ts_si_units
    assert not default_settings.ts_skip_empty
    assert default_settings.ts_skip_threshold == 0.95
    assert not default_settings.ts_dropna
    assert default_settings.ts_interpolation_station_distance == {
        "default": 40.0,
        "precipitation_height": 20.0,
    }
    assert default_settings.ts_interpolation_use_nearby_station_distance == 1
    log_message = caplog.messages[0]
    assert re.match(WD_CACHE_ENABLED_PATTERN, log_message)


@mock.patch.dict(os.environ, {})
def test_settings_envs(caplog):
    """Test default settings but with multiple envs set"""
    os.environ["WD_CACHE_DISABLE"] = "1"
    os.environ["WD_TS_SHAPE"] = "wide"
    os.environ["WD_TS_INTERPOLATION_STATION_DISTANCE"] = "precipitation_height=40.0,other=42"
    caplog.set_level(logging.INFO)
    settings = Settings()
    assert caplog.messages[0] == "Wetterdienst cache is disabled"
    assert settings.ts_shape == "wide"
    assert settings.ts_interpolation_station_distance == {
        "default": 40.0,
        "precipitation_height": 40.0,
        "other": 42.0,
    }


@mock.patch.dict(os.environ, {})
def test_settings_ignore_envs(caplog):
    os.environ["WD_CACHE_DISABLE"] = "1"
    os.environ["WD_TS_SHAPE"] = "wide"
    os.environ["WD_TS_INTERPOLATION_STATION_DISTANCE"] = "precipitation_height=40.0,other=42"
    caplog.set_level(logging.INFO)
    settings = Settings(ignore_env=True)
    log_message = caplog.messages[0]
    assert re.match(WD_CACHE_ENABLED_PATTERN, log_message)
    assert settings.ts_shape == "long"
    assert settings.ts_interpolation_station_distance == {
        "default": 40.0,
        "precipitation_height": 20.0,
    }


@mock.patch.dict(os.environ, {})
def test_settings_mixed(caplog):
    """Check leaking of Settings through threads"""
    os.environ["WD_CACHE_DISABLE"] = "1"
    os.environ["WD_TS_SKIP_THRESHOLD"] = "0.89"
    os.environ["WD_TS_INTERPOLATION_STATION_DISTANCE"] = "precipitation_height=40.0,other=42"
    caplog.set_level(logging.INFO)
    settings = Settings(
        ts_skip_threshold=0.81,
        ts_si_units=False,
        ts_interpolation_station_distance={"just_another": 43},
    )
    log_message = caplog.messages[0]
    assert settings.cache_disable
    assert log_message == "Wetterdienst cache is disabled"  # env variable
    assert settings.ts_shape  # default variable
    assert settings.ts_skip_threshold == 0.81  # argument variable overrules env variable
    assert not settings.ts_si_units  # argument variable
    assert settings.ts_interpolation_station_distance == {
        "default": 40.0,
        "precipitation_height": 40.0,
        "other": 42.0,
        "just_another": 43.0,
    }
