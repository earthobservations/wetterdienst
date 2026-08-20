# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.#
"""Tests for settings."""

import logging
import os
import re
from pathlib import Path
from unittest import mock

import pytest
from pydantic import ValidationError

from wetterdienst.settings import Settings

WD_CACHE_DIR_PATTERN = re.compile(r"[\s\S]*wetterdienst(\\Cache)?")
WD_CACHE_ENABLED_PATTERN = re.compile(r"Wetterdienst cache is enabled [CACHE_DIR:[\s\S]*wetterdienst(\\Cache)?]$")


def test_default_settings(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test default settings."""
    monkeypatch.delenv("WD_CACHE_DIR", raising=False)
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
    # specific heterogeneous parameters use 20 km; the defaultdict fallback returns 40 km
    assert default_settings.ts_geo_station_distance_homogeneous == 40.0
    assert default_settings.ts_geo_station_distance_heterogeneous == 20.0
    assert default_settings.ts_geo_station_distance["precipitation_height"] == 20.0
    assert default_settings.ts_geo_station_distance["snow_depth_new"] == 20.0
    assert default_settings.ts_geo_station_distance["temperature_air_mean_2m"] == 40.0
    assert default_settings.ts_geo_use_nearby_station_distance == 1
    assert not default_settings.use_certifi
    assert not default_settings.read_bufr
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
    os.environ["WD_TS_GEO_STATION_DISTANCE"] = '{"precipitation_height":40.0,"humidity":42}'
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
    # user-supplied overrides are respected; other defaults remain; fallback returns 40 km
    assert settings.ts_geo_station_distance["precipitation_height"] == 40.0
    assert settings.ts_geo_station_distance["humidity"] == 42.0
    assert settings.ts_geo_station_distance["snow_depth_new"] == 20.0
    # default dict returns 40.0 for any other key
    assert settings.ts_geo_station_distance["temperature_air_mean_2m"] == 40.0


@mock.patch.dict(os.environ, {})
def test_settings_mixed(caplog: pytest.LogCaptureFixture) -> None:
    """Test mixed settings."""
    os.environ["WD_CACHE_DISABLE"] = "1"
    os.environ["WD_TS_SKIP_THRESHOLD"] = "0.89"
    os.environ["WD_TS_GEO_STATION_DISTANCE"] = '{"precipitation_height":40.0,"humidity":42}'
    caplog.set_level(logging.INFO)
    settings = Settings(
        ts_skip_threshold=0.81,
        ts_convert_units=False,
        ts_geo_station_distance={"wind_speed": 43},
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
    # user-supplied overrides win; other pre-populated defaults remain; fallback returns 40 km
    # the argument and the env variable are merged, key by key
    assert settings.ts_geo_station_distance["precipitation_height"] == 40.0
    assert settings.ts_geo_station_distance["humidity"] == 42.0
    assert settings.ts_geo_station_distance["wind_speed"] == 43.0
    assert settings.ts_geo_station_distance["snow_depth_new"] == 20.0
    # default dict returns 40.0 for any other key
    assert settings.ts_geo_station_distance["temperature_air_mean_2m"] == 40.0


def test_settings_geo_station_distance_radii() -> None:
    """Test that the two radii settings move every parameter of their kind.

    The radii used to be module constants, so the only way to widen the search was to name every
    parameter individually in `ts_geo_station_distance` -- 514 names to write out for a change that
    is one number.
    """
    settings = Settings(ts_geo_station_distance_homogeneous=50.0, ts_geo_station_distance_heterogeneous=30.0)
    # heterogeneous, from the parameter table
    assert settings.ts_geo_station_distance["precipitation_height"] == 30.0
    assert settings.ts_geo_station_distance["snow_depth_new"] == 30.0
    # homogeneous, from the defaultdict fallback
    assert settings.ts_geo_station_distance["temperature_air_mean_2m"] == 50.0
    assert settings.ts_geo_station_distance["humidity"] == 50.0


def test_settings_geo_station_distance_radii_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the two radii are settable from the environment, next to the per-parameter dict."""
    monkeypatch.setenv("WD_TS_GEO_STATION_DISTANCE_HOMOGENEOUS", "50")
    monkeypatch.setenv("WD_TS_GEO_STATION_DISTANCE_HETEROGENEOUS", "30")
    monkeypatch.setenv("WD_TS_GEO_STATION_DISTANCE", '{"precipitation_height":25}')
    settings = Settings()
    assert settings.ts_geo_station_distance_homogeneous == 50.0
    assert settings.ts_geo_station_distance_heterogeneous == 30.0
    # the per-parameter override wins over the radius of its kind
    assert settings.ts_geo_station_distance["precipitation_height"] == 25.0
    assert settings.ts_geo_station_distance["snow_depth_new"] == 30.0
    assert settings.ts_geo_station_distance["temperature_air_mean_2m"] == 50.0


def test_settings_geo_station_distance_round_trips() -> None:
    """Test that dumped settings can be fed back in without changing what they mean.

    The field holds the expanded mapping, so dumping it used to hand back every heterogeneous
    parameter as an explicit override, which then won over a radius set alongside it -- the same
    "set a number, nothing happens" failure the validation here is about.
    """
    dumped = Settings().model_dump()
    assert dumped["ts_geo_station_distance"] == {}
    dumped["ts_geo_station_distance_heterogeneous"] = 30.0
    settings = Settings(**dumped)
    assert settings.ts_geo_station_distance["precipitation_height"] == 30.0
    # an override that was actually given survives the round-trip
    overridden = Settings(ts_geo_station_distance={"precipitation_height": 25.0})
    assert Settings(**overridden.model_dump()).ts_geo_station_distance["precipitation_height"] == 25.0


def test_settings_geo_station_distance_survives_revalidation() -> None:
    """Test that validating the same settings twice does not turn the table into overrides.

    `TimeseriesRequest` runs `Settings.model_validate(settings)` on what it is handed, which re-runs
    every after-validator on the same instance. Capturing the overrides again there would take the
    already-expanded mapping for what the user wrote, and those 34 entries would then outrank a
    radius set afterwards.
    """
    settings = Settings(ts_geo_station_distance_heterogeneous=30.0)
    revalidated = Settings.model_validate(settings)
    assert revalidated.model_dump()["ts_geo_station_distance"] == {}
    assert revalidated.ts_geo_station_distance["precipitation_height"] == 30.0
    # a radius changed afterwards still reaches the mapping on the next validation
    revalidated.ts_geo_station_distance_heterogeneous = 50.0
    assert Settings.model_validate(revalidated).ts_geo_station_distance["precipitation_height"] == 50.0


def test_settings_geo_station_distance_for_scales_with_resolution() -> None:
    """Test that the radius of a heterogeneous parameter follows the accumulation period.

    Precipitation decorrelates over roughly 8 km in ten minutes but tens of kilometres over a day,
    which one fixed radius cannot express: it is too wide at `minute_10` and too tight at `daily`.
    """
    settings = Settings()
    assert settings.ts_geo_station_distance_for("precipitation_height", "10_minutes") == 15.0
    assert settings.ts_geo_station_distance_for("precipitation_height", "hourly") == 20.0
    assert settings.ts_geo_station_distance_for("precipitation_height", "6_hour") == 30.0
    assert settings.ts_geo_station_distance_for("precipitation_height", "daily") == 40.0
    assert settings.ts_geo_station_distance_for("precipitation_height", "annual") == 60.0
    # a resolution the factors say nothing about is left as it is
    assert settings.ts_geo_station_distance_for("precipitation_height", "undefined") == 20.0


def test_settings_geo_station_distance_for_leaves_homogeneous_parameters_alone() -> None:
    """Test that the homogeneous radius is the same at every resolution.

    What bounds it is terrain rather than correlation -- daily temperature stays correlated over
    hundreds of kilometres, while `apply_interpolation` works on UTM x/y and never reads station
    height -- and terrain does not care how long the quantity was accumulated for.
    """
    settings = Settings()
    for resolution in ("10_minutes", "hourly", "daily", "annual"):
        assert settings.ts_geo_station_distance_for("temperature_air_mean_2m", resolution) == 40.0
    # a name the table does not know falls back the same way the mapping does
    assert settings.ts_geo_station_distance_for("not_a_parameter", "daily") == 40.0


def test_settings_geo_station_distance_for_takes_an_override_as_written() -> None:
    """Test that a radius set by hand is not scaled.

    A number written out for a parameter means that number; scaling it would answer a question the
    user did not ask, and there would be no way to ask for a fixed radius at all.
    """
    settings = Settings(ts_geo_station_distance={"precipitation_height": 25.0})
    assert settings.ts_geo_station_distance_for("precipitation_height", "10_minutes") == 25.0
    assert settings.ts_geo_station_distance_for("precipitation_height", "daily") == 25.0
    # the parameters that were not named still scale
    assert settings.ts_geo_station_distance_for("snow_depth_new", "daily") == 40.0


def test_settings_geo_station_distance_resolution_factors() -> None:
    """Test that the factors are settable, and that the ones left out keep their default."""
    settings = Settings(ts_geo_station_distance_resolution_factors={"daily": 3.0})
    assert settings.ts_geo_station_distance_for("precipitation_height", "daily") == 60.0
    assert settings.ts_geo_station_distance_for("precipitation_height", "10_minutes") == 15.0
    # flattening every factor turns the scaling off
    flat = Settings(
        ts_geo_station_distance_resolution_factors=dict.fromkeys(
            (
                "1_minute",
                "5_minutes",
                "6_minutes",
                "10_minutes",
                "15_minutes",
                "hourly",
                "6_hour",
                "subdaily",
                "daily",
                "monthly",
                "annual",
            ),
            1.0,
        ),
    )
    for resolution in ("10_minutes", "hourly", "daily", "annual"):
        assert flat.ts_geo_station_distance_for("precipitation_height", resolution) == 20.0


def test_settings_geo_station_distance_resolution_factors_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the factors are settable from the environment, like the radii next to them."""
    monkeypatch.setenv("WD_TS_GEO_STATION_DISTANCE_RESOLUTION_FACTORS", '{"daily":3.0}')
    settings = Settings()
    assert settings.ts_geo_station_distance_resolution_factor("daily") == 3.0
    assert settings.ts_geo_station_distance_for("precipitation_height", "daily") == 60.0


def test_settings_geo_station_distance_resolution_factors_reject_unknown_resolution() -> None:
    """Test that a resolution that does not exist is rejected rather than silently ignored."""
    with pytest.raises(ValidationError, match=r"\['dayly'\] not in"):
        Settings(ts_geo_station_distance_resolution_factors={"dayly": 2.0})


def test_settings_geo_station_distance_resolution_factors_reject_negative() -> None:
    """Test that a negative factor is rejected, as a negative radius is."""
    with pytest.raises(ValidationError, match="Negative factors in ts_geo_station_distance_resolution_factors"):
        Settings(ts_geo_station_distance_resolution_factors={"daily": -1.0})


def test_settings_geo_station_distance_rejects_unknown_parameter() -> None:
    """Test that a parameter name that is not canonical is rejected rather than silently ignored."""
    with pytest.raises(ValidationError, match=r"\['precipitation_heigt'\] not in the canonical parameters"):
        Settings(ts_geo_station_distance={"precipitation_heigt": 25.0})


def test_settings_geo_station_distance_rejects_default_key() -> None:
    """Test that the retired "default" key names its replacements instead of quietly taking effect.

    It used to rebuild the mapping around the given number, which threw away the shorter radius of
    every heterogeneous parameter along with the fallback -- `{"default": 30}` gave precipitation
    30 km too.
    """
    with pytest.raises(ValidationError, match="the 'default' key of ts_geo_station_distance is gone"):
        Settings(ts_geo_station_distance={"default": 30.0})


def test_settings_geo_station_distance_rejects_negative() -> None:
    """Test that a negative radius is rejected, as it is for `ts_geo_use_nearby_station_distance`."""
    with pytest.raises(
        ValidationError, match=r"Negative distances in ts_geo_station_distance: \['precipitation_height'\]"
    ):
        Settings(ts_geo_station_distance={"precipitation_height": -5.0})


def test_settings_geo_station_distance_warns_on_never_interpolated_parameter(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test that a radius set for a parameter that is never interpolated is called out.

    The name is canonical, so it cannot be a typo, but nothing reads the radius: interpolation
    skips the parameter before the distance is ever compared.
    """
    caplog.set_level(logging.WARNING)
    Settings(ts_geo_station_distance={"wind_direction": 25.0})
    assert (
        "option 'ts_geo_station_distance' sets a radius for ['wind_direction'], which are never interpolated"
        in caplog.text
    )


def test_settings_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that Settings loads values from a .env file in the working directory."""
    monkeypatch.delenv("WD_CACHE_DISABLE", raising=False)
    (tmp_path / ".env").write_text("WD_CACHE_DISABLE=true\n")
    monkeypatch.chdir(tmp_path)
    settings = Settings()
    assert settings.cache_disable


def test_settings_env_file_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that Settings loads without error when no .env file exists."""
    monkeypatch.delenv("WD_CACHE_DISABLE", raising=False)
    monkeypatch.chdir(tmp_path)
    settings = Settings()
    assert not settings.cache_disable


def test_settings_env_nested_delimiter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that WD_ env vars with __ delimiter set individual keys in dict fields."""
    monkeypatch.setenv("WD_TS_UNIT_TARGETS__temperature", "degree_fahrenheit")
    settings = Settings()
    assert settings.ts_unit_targets["temperature"] == "degree_fahrenheit"


def test_use_certifi_setting() -> None:
    """Test use_certifi setting."""
    # Test default value
    settings = Settings()
    assert not settings.use_certifi

    # Test explicit value
    settings = Settings(use_certifi=True)
    assert settings.use_certifi

    # Test from environment
    with mock.patch.dict(os.environ, {"WD_USE_CERTIFI": "true"}):
        settings = Settings()
        assert settings.use_certifi

    with mock.patch.dict(os.environ, {"WD_USE_CERTIFI": "false"}):
        settings = Settings()
        assert not settings.use_certifi
