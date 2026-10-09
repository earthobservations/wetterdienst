# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.#
"""Tests for settings."""

import atexit
import collections
import copy
import functools
import json
import logging
import os
import re
import tempfile
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from unittest import mock

import platformdirs
import pytest
from multidict import CIMultiDict
from pydantic import SecretStr, ValidationError
from pydantic_settings import SettingsError

from wetterdienst.metadata.resolution import Resolution
from wetterdienst.settings import (
    _STATION_DISTANCE_RESOLUTION_FACTORS,
    Auth,
    Settings,
    _describe_settings_error,
    _remove_unless_forked,
    _temporary_cache_dir,
    check_settings,
    default_cache_dir,
    reveal,
)

WD_CACHE_DIR_PATTERN = re.compile(r"[\s\S]*wetterdienst(\\Cache)?")
WD_CACHE_ENABLED_PATTERN = re.compile(r"Wetterdienst cache is enabled [CACHE_DIR:[\s\S]*wetterdienst(\\Cache)?]$")


def test_default_settings(caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test default settings."""
    monkeypatch.delenv("WD_CACHE_DIR", raising=False)
    monkeypatch.delenv("WD_RESTAPI_SQL", raising=False)
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
    assert default_settings.ts_geo_station_distance["precipitation_amount"] == 20.0
    assert default_settings.ts_geo_station_distance["snow_depth_new"] == 20.0
    assert default_settings.ts_geo_station_distance["temperature_air_mean_2m"] == 40.0
    assert default_settings.ts_geo_use_nearby_station_distance == 1
    assert not default_settings.use_certifi
    assert not default_settings.read_bufr
    # SQL from REST API and MCP clients stays off until the operator turns it on
    assert not default_settings.restapi_sql
    assert re.match(WD_CACHE_ENABLED_PATTERN, caplog.messages[0])


@mock.patch.dict(os.environ, {})
def test_settings_envs(caplog: pytest.LogCaptureFixture) -> None:
    """Test default settings but with multiple envs set."""
    os.environ["WD_CACHE_DISABLE"] = "1"
    os.environ["WD_TS_SHAPE"] = "wide"
    os.environ["WD_TS_GEO_STATION_DISTANCE"] = '{"precipitation_amount":40.0,"humidity_relative":42}'
    caplog.set_level(logging.INFO)
    settings = Settings()
    assert (
        caplog.messages[0]
        == "option 'ts_drop_nulls' is only available with option 'ts_shape=long' and is thus ignored in this request."
    )
    assert caplog.messages[1] == "Wetterdienst cache is disabled"
    assert settings.ts_shape == "wide"
    # user-supplied overrides are respected; other defaults remain; fallback returns 40 km
    assert settings.ts_geo_station_distance["precipitation_amount"] == 40.0
    assert settings.ts_geo_station_distance["humidity_relative"] == 42.0
    assert settings.ts_geo_station_distance["snow_depth_new"] == 20.0
    # default dict returns 40.0 for any other key
    assert settings.ts_geo_station_distance["temperature_air_mean_2m"] == 40.0


@mock.patch.dict(os.environ, {})
def test_settings_mixed(caplog: pytest.LogCaptureFixture) -> None:
    """Test mixed settings."""
    os.environ["WD_CACHE_DISABLE"] = "1"
    os.environ["WD_TS_SKIP_THRESHOLD"] = "0.89"
    os.environ["WD_TS_GEO_STATION_DISTANCE"] = '{"precipitation_amount":40.0,"humidity_relative":42}'
    caplog.set_level(logging.INFO)
    settings = Settings(
        ts_skip_threshold=0.81,
        ts_convert_units=False,
        ts_geo_station_distance={"wind_speed": 43},
    )
    assert settings.cache_disable
    assert caplog.messages[0] == "Wetterdienst cache is disabled"  # env variable
    assert settings.ts_shape  # default variable
    assert settings.ts_skip_threshold == 0.81  # argument variable overrules env variable
    assert not settings.ts_convert_units  # argument variable
    # user-supplied overrides win; other pre-populated defaults remain; fallback returns 40 km
    # the argument and the env variable are merged, key by key
    assert settings.ts_geo_station_distance["precipitation_amount"] == 40.0
    assert settings.ts_geo_station_distance["humidity_relative"] == 42.0
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
    assert settings.ts_geo_station_distance["precipitation_amount"] == 30.0
    assert settings.ts_geo_station_distance["snow_depth_new"] == 30.0
    # homogeneous, from the defaultdict fallback
    assert settings.ts_geo_station_distance["temperature_air_mean_2m"] == 50.0
    assert settings.ts_geo_station_distance["humidity_relative"] == 50.0


def test_settings_geo_station_distance_radii_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the two radii are settable from the environment, next to the per-parameter dict."""
    monkeypatch.setenv("WD_TS_GEO_STATION_DISTANCE_HOMOGENEOUS", "50")
    monkeypatch.setenv("WD_TS_GEO_STATION_DISTANCE_HETEROGENEOUS", "30")
    monkeypatch.setenv("WD_TS_GEO_STATION_DISTANCE", '{"precipitation_amount":25}')
    settings = Settings()
    assert settings.ts_geo_station_distance_homogeneous == 50.0
    assert settings.ts_geo_station_distance_heterogeneous == 30.0
    # the per-parameter override wins over the radius of its kind
    assert settings.ts_geo_station_distance["precipitation_amount"] == 25.0
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
    assert settings.ts_geo_station_distance["precipitation_amount"] == 30.0
    # an override that was actually given survives the round-trip
    overridden = Settings(ts_geo_station_distance={"precipitation_amount": 25.0})
    assert Settings(**overridden.model_dump()).ts_geo_station_distance["precipitation_amount"] == 25.0


def test_settings_geo_station_distance_survives_revalidation() -> None:
    """Test that validating the same settings twice does not turn the table into overrides.

    `Settings.model_validate(settings)` re-runs every after-validator on the same instance.
    Capturing the overrides again there would take the already-expanded mapping for what the user
    wrote, and those 34 entries would then outrank a radius set afterwards.
    """
    settings = Settings(ts_geo_station_distance_heterogeneous=30.0)
    revalidated = Settings.model_validate(settings)
    assert revalidated.model_dump()["ts_geo_station_distance"] == {}
    assert revalidated.ts_geo_station_distance["precipitation_amount"] == 30.0
    # a radius changed afterwards still reaches the mapping on the next validation
    revalidated.ts_geo_station_distance_heterogeneous = 50.0
    assert Settings.model_validate(revalidated).ts_geo_station_distance["precipitation_amount"] == 50.0


def test_settings_geo_station_distance_for_scales_with_resolution() -> None:
    """Test that the radius of a heterogeneous parameter follows the accumulation period.

    Precipitation decorrelates over roughly 8 km in ten minutes but tens of kilometres over a day,
    which one fixed radius cannot express: it is too wide at `minute_10` and too tight at `daily`.
    """
    settings = Settings()
    assert settings.ts_geo_station_distance_for("precipitation_amount", "10_minutes") == 15.0
    assert settings.ts_geo_station_distance_for("precipitation_amount", "hourly") == 20.0
    assert settings.ts_geo_station_distance_for("precipitation_amount", "6_hour") == 30.0
    assert settings.ts_geo_station_distance_for("precipitation_amount", "daily") == 40.0
    assert settings.ts_geo_station_distance_for("precipitation_amount", "annual") == 40.0
    # a name from outside the resolution vocabulary is left as it is rather than guessed at
    assert settings.ts_geo_station_distance_for("precipitation_amount", "every other tuesday") == 20.0


def test_settings_geo_station_distance_factors_name_every_resolution() -> None:
    """Test that no resolution falls through to the unscaled default.

    The default exists for a name from outside the vocabulary, not for a resolution the table
    forgot: a resolution left out would hold a heterogeneous parameter to the hourly radius at
    every interval, which is a fifth too wide at `10_minutes` and half as wide as it should be at
    `daily`, and nothing about the result would say so.
    """
    assert set(_STATION_DISTANCE_RESOLUTION_FACTORS) == {resolution.value for resolution in Resolution}


def test_settings_geo_station_distance_for_stops_widening_past_a_day() -> None:
    """Test that the table stops at twice the base radius rather than following correlation up.

    Past a day what binds is terrain and not correlation -- the interpolation reads UTM x/y and
    never station elevation -- so the widest the defaults reach is the 40 km the homogeneous radius is
    held to, which is why the two meet at `daily`.
    """
    settings = Settings()
    assert settings.ts_geo_station_distance_for("precipitation_amount", "daily") == 40.0
    assert settings.ts_geo_station_distance_for("precipitation_amount", "monthly") == 40.0
    assert settings.ts_geo_station_distance_for("precipitation_amount", "annual") == 40.0
    assert settings.ts_geo_station_distance_for("temperature_air_mean_2m", "daily") == 40.0


def test_settings_geo_station_distance_for_scales_the_radius_that_was_set() -> None:
    """Test that the factors multiply whatever base radius the user set, at every resolution.

    A radius raised by hand is followed rather than clipped: the user has made the terrain
    judgement the factors encode, and a setting that silently does nothing is the failure this
    module validates against everywhere else.
    """
    settings = Settings(ts_geo_station_distance_heterogeneous=30.0)
    assert settings.ts_geo_station_distance_for("precipitation_amount", "10_minutes") == 22.5
    assert settings.ts_geo_station_distance_for("precipitation_amount", "hourly") == 30.0
    assert settings.ts_geo_station_distance_for("precipitation_amount", "daily") == 60.0
    # every step of the setting moves the radius, with no range where it does nothing
    radii = [
        Settings(ts_geo_station_distance_heterogeneous=base).ts_geo_station_distance_for(
            "precipitation_amount",
            "daily",
        )
        for base in (20.0, 25.0, 30.0, 35.0)
    ]
    assert radii == [40.0, 50.0, 60.0, 70.0]


def test_settings_geo_station_distance_for_leaves_homogeneous_parameters_alone() -> None:
    """Test that the homogeneous radius is the same at every resolution.

    What bounds it is terrain rather than correlation -- daily temperature stays correlated over
    hundreds of kilometres, while `apply_interpolation` works on UTM x/y and never reads station
    elevation -- and terrain does not care how long the quantity was accumulated for.
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
    settings = Settings(ts_geo_station_distance={"precipitation_amount": 25.0})
    assert settings.ts_geo_station_distance_for("precipitation_amount", "10_minutes") == 25.0
    assert settings.ts_geo_station_distance_for("precipitation_amount", "daily") == 25.0
    # the parameters that were not named still scale
    assert settings.ts_geo_station_distance_for("snow_depth_new", "daily") == 40.0


def test_settings_geo_station_distance_resolution_factors() -> None:
    """Test that the factors are settable, and that the ones left out keep their default."""
    settings = Settings(ts_geo_station_distance_resolution_factors={"daily": 3.0})
    assert settings.ts_geo_station_distance_for("precipitation_amount", "daily") == 60.0
    assert settings.ts_geo_station_distance_for("precipitation_amount", "10_minutes") == 15.0
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
        assert flat.ts_geo_station_distance_for("precipitation_amount", resolution) == 20.0


def test_settings_geo_station_distance_resolution_factors_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the factors are settable from the environment, like the radii next to them."""
    monkeypatch.setenv("WD_TS_GEO_STATION_DISTANCE_RESOLUTION_FACTORS", '{"daily":3.0}')
    settings = Settings()
    assert settings.ts_geo_station_distance_resolution_factor("daily") == 3.0
    assert settings.ts_geo_station_distance_for("precipitation_amount", "daily") == 60.0


def test_settings_geo_station_distance_resolution_factors_reject_unknown_resolution() -> None:
    """Test that a resolution that does not exist is rejected rather than silently ignored."""
    with pytest.raises(ValidationError, match=r"\['dayly'\] not in"):
        Settings(ts_geo_station_distance_resolution_factors={"dayly": 2.0})


def test_settings_geo_station_distance_resolution_factors_reject_negative() -> None:
    """Test that a negative factor is rejected, as a negative radius is."""
    with pytest.raises(ValidationError, match="Negative factors in ts_geo_station_distance_resolution_factors"):
        Settings(ts_geo_station_distance_resolution_factors={"daily": -1.0})


def test_settings_geo_station_distance_for_reads_the_radii_live() -> None:
    """Test which settings an already-built `Settings` object still lets you change.

    The two radii and the factors are read when a radius is worked out, so assigning to them takes
    effect at once. The per-parameter mapping is not: the overrides are taken when the settings are
    built, and what the field holds afterwards is the expansion of them, so an assignment to it is
    discarded rather than picked up. This pins the difference so it stays documented.
    """
    settings = Settings()
    settings.ts_geo_station_distance_heterogeneous = 30.0
    assert settings.ts_geo_station_distance_for("precipitation_amount", "hourly") == 30.0
    settings.ts_geo_station_distance_resolution_factors = {"daily": 3.0}
    assert settings.ts_geo_station_distance_for("precipitation_amount", "daily") == 90.0
    # the mapping is not a way in, before or after another validation
    other = Settings()
    other.ts_geo_station_distance = {"precipitation_amount": 25.0}
    assert other.ts_geo_station_distance_for("precipitation_amount", "hourly") == 20.0
    assert Settings.model_validate(other).ts_geo_station_distance_for("precipitation_amount", "hourly") == 20.0


def test_settings_geo_station_distance_rejects_unknown_parameter() -> None:
    """Test that a parameter name that is not canonical is rejected rather than silently ignored."""
    with pytest.raises(ValidationError, match=r"\['precipitation_heigt'\] not in the canonical parameters"):
        Settings(ts_geo_station_distance={"precipitation_heigt": 25.0})


def test_settings_geo_station_distance_names_a_renamed_parameter() -> None:
    """A key renamed for 1.0 is refused with the name it has now (GH-2036)."""
    with pytest.raises(ValidationError, match=r"'humidity' is now 'humidity_relative'"):
        Settings(ts_geo_station_distance={"humidity": 25.0})


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
        ValidationError, match=r"Negative distances in ts_geo_station_distance: \['precipitation_amount'\]"
    ):
        Settings(ts_geo_station_distance={"precipitation_amount": -5.0})


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


def test_settings_skip_empty_stands_on_its_own() -> None:
    """Test that skip_empty survives a request that sets nothing else.

    It used to be switched off unless `ts_complete` was on, and neither the CLI nor the REST API
    ever set that -- so `--skip_empty`, `--skip_threshold` and `--skip_criteria`, and the three
    REST parameters of the same names, were discarded on every request that passed them.
    """
    # the settings the CLI and the REST API build a values request from, skip options included
    settings = Settings(
        ts_humanize=True,
        ts_shape="long",
        ts_convert_units=True,
        ts_unit_targets={},
        ts_skip_empty=True,
        ts_skip_criteria="mean",
        ts_skip_threshold=0.9,
        ts_drop_nulls=True,
    )

    assert settings.ts_skip_empty
    assert settings.ts_skip_criteria == "mean"
    assert settings.ts_skip_threshold == 0.9


# what each credential is set to below, so a test can look for it in what an object renders
_DUMMY_CREDENTIALS = {
    "aemet": "DUMMY-AEMET-KEY",
    "knmi": "DUMMY-KNMI-KEY",
    "metno_frost": ("DUMMY-FROST-ID", "DUMMY-FROST-SECRET"),
    "ceda": ("DUMMY-CEDA-USER", "DUMMY-CEDA-PASSWORD"),
}
_DUMMY_VALUES = sorted(
    {value for entry in _DUMMY_CREDENTIALS.values() for value in ((entry,) if isinstance(entry, str) else entry)},
)


def _rendered(settings: Settings) -> str:
    """Render the settings every way something else might, and return the lot as one string."""
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415

    request = DwdObservationRequest(parameters=[("daily", "kl")], periods="recent", settings=settings)
    return "".join(
        [
            repr(settings),
            str(settings),
            f"{settings}",
            str(settings.model_dump()),
            str(settings.model_dump(mode="json")),
            settings.model_dump_json(),
            # a request's dataclass repr embeds the settings, which is how this was found: an
            # unrelated test failed and pytest printed the request, credentials and all
            repr(request),
            str(request),
        ],
    )


def test_credentials_do_not_appear_in_what_settings_render() -> None:
    """No credential is printed by any ordinary way of looking at the settings, or at a request.

    They are not logged anywhere in normal operation. What exposes them is a failure path: a pytest
    assertion diff, an unhandled traceback, `print(request)`, a debugger. Anyone pasting one of
    those into an issue or a CI log would publish every credential they had configured (GH-1920).
    """
    settings = Settings(auth=_DUMMY_CREDENTIALS)

    rendered = _rendered(settings)

    assert not [value for value in _DUMMY_VALUES if value in rendered]
    # and the masking is visible rather than the field being dropped, so a reader can see that
    # something is there
    assert "**********" in rendered


def test_credentials_are_still_readable_where_they_are_needed() -> None:
    """Hiding them from a repr does not hide them from the code that sends them."""
    settings = Settings(auth=_DUMMY_CREDENTIALS)

    assert reveal(settings.auth.aemet) == "DUMMY-AEMET-KEY"
    assert reveal(settings.auth.knmi) == "DUMMY-KNMI-KEY"
    assert tuple(reveal(part) for part in settings.auth.metno_frost) == ("DUMMY-FROST-ID", "DUMMY-FROST-SECRET")
    assert tuple(reveal(part) for part in settings.auth.ceda) == ("DUMMY-CEDA-USER", "DUMMY-CEDA-PASSWORD")
    assert reveal(None) is None


def test_credentials_read_from_the_environment_are_secret_too() -> None:
    """The env vars are the way most of these are set, and take the same shape once parsed."""
    env = {
        "WD_AUTH__AEMET": "DUMMY-AEMET-KEY",
        "WD_AUTH__CEDA": "DUMMY-CEDA-USER:DUMMY-CEDA-PASSWORD",
    }
    with mock.patch.dict(os.environ, env, clear=False):
        settings = Settings()

    assert reveal(settings.auth.aemet) == "DUMMY-AEMET-KEY"
    assert tuple(reveal(part) for part in settings.auth.ceda) == ("DUMMY-CEDA-USER", "DUMMY-CEDA-PASSWORD")
    assert "DUMMY-CEDA-PASSWORD" not in _rendered(settings)


def test_a_credential_that_is_empty_is_still_no_credential() -> None:
    """An empty value stays falsy, which is what every "is this configured" check reads."""
    settings = Settings(auth={"aemet": ""})

    assert not settings.auth.aemet


def test_credentials_survive_a_round_trip_through_a_dump() -> None:
    """Settings taken apart and rebuilt keep the credentials they had, pairs included.

    `model_dump()` hands back the secrets themselves, and `str()` of a secret is its mask -- so a
    pair validator that texts its elements would rebuild the pair as ten asterisks and fail at the
    provider later with nothing to say why. The single-valued fields never had this to worry about,
    which is what made the asymmetry easy to miss.
    """
    settings = Settings(auth=_DUMMY_CREDENTIALS)

    rebuilt = Settings.model_validate(settings.model_dump())

    assert reveal(rebuilt.auth.aemet) == "DUMMY-AEMET-KEY"
    assert tuple(reveal(part) for part in rebuilt.auth.ceda) == ("DUMMY-CEDA-USER", "DUMMY-CEDA-PASSWORD")
    assert tuple(reveal(part) for part in rebuilt.auth.metno_frost) == ("DUMMY-FROST-ID", "DUMMY-FROST-SECRET")


def test_a_credential_given_as_one_secret_is_still_split_into_its_pair() -> None:
    """A pair handed over as a single secret is read apart the way the same text would be."""
    settings = Settings(auth={"ceda": SecretStr("DUMMY-CEDA-USER:DUMMY-CEDA-PASSWORD")})

    assert tuple(reveal(part) for part in settings.auth.ceda) == ("DUMMY-CEDA-USER", "DUMMY-CEDA-PASSWORD")


@pytest.mark.parametrize(
    "auth",
    [
        {"aemet": "*" * 10},
        {"ceda": ("*" * 10, "*" * 10)},
        {"metno_frost": ("DUMMY-FROST-ID", "*" * 10)},
    ],
)
def test_a_masked_value_is_refused_as_a_credential(auth: dict) -> None:
    """The mask a JSON dump leaves behind is not accepted as the credential it stands for.

    A JSON dump writes asterisks where a credential is, which is the point of holding them as
    secrets -- and there is no reading that back. Taken as the credential it would fail at the
    provider much later, with nothing at all to say why, so it is refused where it is given.
    """
    with pytest.raises(ValidationError, match="mask"):
        Settings(auth=auth)


@pytest.mark.usefixtures("_no_client_kwargs_configured")
def test_fsspec_client_kwargs_are_merged_into_the_defaults() -> None:
    """A dict of one's own keeps the timeout and the User-Agent it does not name (GH-2269).

    `{"trust_env": True}` is the proxy example the docs give; it used to replace the defaults whole,
    so requests fell back to aiohttp's five minutes for the whole request and went out unidentified.
    """
    defaults = Settings().fsspec_client_kwargs

    settings = Settings(fsspec_client_kwargs={"trust_env": True})

    assert settings.fsspec_client_kwargs == {**defaults, "trust_env": True}
    assert settings.fsspec_client_kwargs["timeout"] == 30
    assert settings.fsspec_client_kwargs["headers"]["User-Agent"].startswith("wetterdienst/")


@pytest.mark.usefixtures("_no_client_kwargs_configured")
def test_fsspec_client_kwargs_merge_headers_one_level_deep() -> None:
    """A header of one's own is sent alongside the User-Agent, not instead of it (GH-2269)."""
    user_agent = Settings().fsspec_client_kwargs["headers"]["User-Agent"]

    settings = Settings(fsspec_client_kwargs={"headers": {"X-Custom": "1"}})

    assert settings.fsspec_client_kwargs["headers"] == {"User-Agent": user_agent, "X-Custom": "1"}
    assert settings.fsspec_client_kwargs["timeout"] == 30


@pytest.mark.usefixtures("_no_client_kwargs_configured")
@pytest.mark.parametrize("name", ["User-Agent", "user-agent", "USER-AGENT"])
def test_fsspec_client_kwargs_take_the_callers_own_user_agent(name: str) -> None:
    """A User-Agent of one's own replaces the default, in whatever spelling, rather than doubling it.

    Header names are case-insensitive, so keeping the default beside a `user-agent` would send two.
    """
    settings = Settings(fsspec_client_kwargs={"headers": {name: "my-app/1.0"}})

    assert settings.fsspec_client_kwargs["headers"] == {name: "my-app/1.0"}


@pytest.mark.usefixtures("_no_client_kwargs_configured")
@pytest.mark.parametrize("timeout", [5, 2.5, None])
def test_fsspec_client_kwargs_take_the_callers_own_timeout(timeout: float | None) -> None:
    """A timeout of one's own wins, `None` included, which hands the choice back to aiohttp."""
    settings = Settings(fsspec_client_kwargs={"timeout": timeout})

    assert settings.fsspec_client_kwargs["timeout"] == timeout
    assert settings.fsspec_client_kwargs["headers"]["User-Agent"].startswith("wetterdienst/")


@pytest.mark.usefixtures("_no_client_kwargs_configured")
def test_fsspec_client_kwargs_from_the_environment_are_merged_too(monkeypatch: pytest.MonkeyPatch) -> None:
    """`WD_FSSPEC_CLIENT_KWARGS` is merged into the defaults the same way as an argument (GH-2269)."""
    monkeypatch.setenv("WD_FSSPEC_CLIENT_KWARGS", '{"trust_env": true, "headers": {"X-Custom": "1"}}')

    kwargs = Settings().fsspec_client_kwargs

    assert kwargs["trust_env"] is True
    assert kwargs["timeout"] == 30
    assert kwargs["headers"]["X-Custom"] == "1"
    assert kwargs["headers"]["User-Agent"].startswith("wetterdienst/")


@pytest.mark.usefixtures("_no_client_kwargs_configured")
def test_fsspec_client_kwargs_survive_a_round_trip_through_a_dump() -> None:
    """Merging what a dump hands back changes nothing, so a rebuilt `Settings` asks the same way."""
    settings = Settings(fsspec_client_kwargs={"trust_env": True, "headers": {"user-agent": "my-app/1.0"}})

    rebuilt = Settings(**settings.model_dump())

    assert rebuilt.fsspec_client_kwargs == settings.fsspec_client_kwargs


@pytest.mark.usefixtures("_no_client_kwargs_configured")
@pytest.mark.parametrize(
    "headers",
    [CIMultiDict([("Accept", "a"), ("Accept", "b")]), [("Accept", "a"), ("Accept", "b")]],
    ids=["multidict", "pairs"],
)
def test_fsspec_client_kwargs_keep_headers_that_are_not_a_dict_as_given(headers: object) -> None:
    """Headers in another form aiohttp takes are passed on untouched, a repeated name included.

    Copying a `CIMultiDict` or a list of pairs into a dict to merge it would keep one value of a
    header given twice, where aiohttp sends both.
    """
    settings = Settings(fsspec_client_kwargs={"headers": headers})

    assert settings.fsspec_client_kwargs["headers"] is headers
    assert settings.fsspec_client_kwargs["timeout"] == 30


def test_settings_geo_station_choice_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test the settings that choose the stations to interpolate from are settable from the environment.

    The environment gives a string, which a strict number field refused.
    """
    monkeypatch.setenv("WD_TS_GEO_USE_NEARBY_STATION_DISTANCE", "0.5")
    monkeypatch.setenv("WD_TS_GEO_MIN_GAIN_OF_VALUE_PAIRS", "0.2")
    monkeypatch.setenv("WD_TS_GEO_NUM_ADDITIONAL_STATIONS", "5")
    settings = Settings()
    assert settings.ts_geo_use_nearby_station_distance == 0.5
    assert settings.ts_geo_min_gain_of_value_pairs == 0.2
    assert settings.ts_geo_num_additional_stations == 5


@pytest.mark.parametrize(
    ("unit_targets", "message"),
    [
        pytest.param(
            {"temperature": "furlong"},
            "Invalid unit targets: Unit furlong not supported for type temperature.",
            id="unknown-unit",
        ),
        pytest.param(
            {"temperature": "meter"},
            "Invalid unit targets: Unit meter not supported for type temperature.",
            id="unit-of-another-quantity",
        ),
        pytest.param(
            {"precipitation_intensity": "millimeter_per_second"},
            "Invalid unit targets: Unit millimeter_per_second is what a source publishes in and cannot be a "
            "target for type precipitation_intensity",
            id="source-only-unit",
        ),
    ],
)
def test_settings_unit_targets_refuse_a_unit_the_converter_cannot_report_in(
    monkeypatch: pytest.MonkeyPatch,
    unit_targets: dict[str, str],
    message: str,
) -> None:
    """A unit target is refused for its unit too, not only its quantity (GH-2306).

    It used to pass here and be refused only once a values request had fetched its stations.
    """
    monkeypatch.delenv("WD_TS_UNIT_TARGETS", raising=False)
    with pytest.raises(ValidationError, match=re.escape(message)):
        Settings(ts_unit_targets=unit_targets)


def test_settings_unit_targets_name_only_the_unknown_quantities(monkeypatch: pytest.MonkeyPatch) -> None:
    """The refusal names the unknown quantities, sorted, rather than every one given (GH-2306)."""
    monkeypatch.delenv("WD_TS_UNIT_TARGETS", raising=False)
    with pytest.raises(ValidationError) as excinfo:
        Settings(ts_unit_targets={"temperature": "degree_fahrenheit", "foo": "bar", "abc": "x"})
    # the message alone, without pydantic's echo of the input after it
    message = str(excinfo.value).split(" [type=")[0]
    assert "Invalid unit targets: quantities not supported: abc, foo. Supported quantities are: angle, " in message
    assert "temperature" in message  # in the sorted list of supported ones
    assert "'temperature'" not in message


def test_settings_unit_targets_build_no_converter_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """The empty default, which every `Settings()` has, is not resolved by a converter (GH-2306)."""
    monkeypatch.delenv("WD_TS_UNIT_TARGETS", raising=False)
    with mock.patch("wetterdienst.settings.UnitConverter") as converter:
        Settings()
    converter.assert_not_called()


@pytest.fixture
def _no_ambient_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep the WD_* variables and the `.env` of whoever runs the tests out of the settings."""
    for name in list(os.environ):
        if name.startswith("WD_") and name != "WD_CACHE_DIR":
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize(
    ("env", "lines"),
    [
        pytest.param(
            {"WD_CACHE_DISABLE": "secret-ish"},
            ["WD_CACHE_DISABLE is invalid: Input should be a valid boolean, unable to interpret input"],
            id="top-level",
        ),
        pytest.param(
            {"WD_AUTH__CEDA": "secret-ish"},
            ["WD_AUTH__CEDA is invalid: ceda must be given as 'username:password'"],
            id="nested",
        ),
        pytest.param(
            {"WD_TS_GEO_STATION_DISTANCE": '{"precipitation_amount": "secret-ish"}'},
            [
                (
                    "WD_TS_GEO_STATION_DISTANCE__PRECIPITATION_AMOUNT is invalid: "
                    "Input should be a valid number, unable to parse string as a number"
                )
            ],
            id="within-a-dict",
        ),
        pytest.param(
            {"WD_CACHE_DISABLE": "secret-ish", "WD_TS_SHAPE": "secret-ish"},
            [
                "WD_CACHE_DISABLE is invalid: Input should be a valid boolean, unable to interpret input",
                "WD_TS_SHAPE is invalid: Input should be 'wide' or 'long'",
            ],
            id="several",
        ),
        pytest.param(
            {"WD_TS_UNIT_TARGETS": "secret-ish"},
            ["WD_TS_UNIT_TARGETS is invalid: not valid JSON"],
            id="not-json",
        ),
    ],
)
def test_check_settings_names_the_variable_without_its_value(
    monkeypatch: pytest.MonkeyPatch,
    env: dict[str, str],
    lines: list[str],
) -> None:
    """A malformed `WD_*` setting is told by its variable, a line each, and never by its value (GH-2335)."""
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    assert check_settings() == lines


@pytest.mark.usefixtures("_no_ambient_settings")
def test_check_settings_reads_dotenv(tmp_path: Path) -> None:
    """The check reads `.env` as the settings do, and finds nothing wrong with valid ones (GH-2335)."""
    assert check_settings() == []
    (tmp_path / ".env").write_text("WD_CACHE_DISABLE=secret-ish\n")
    assert check_settings() == [
        "WD_CACHE_DISABLE is invalid: Input should be a valid boolean, unable to interpret input"
    ]


@pytest.mark.usefixtures("_no_ambient_settings")
def test_check_settings_finds_nothing_wrong_with_a_dotenv_key_that_is_no_setting(tmp_path: Path) -> None:
    """A `.env` key that is no setting is ignored, as in the environment, so it is nothing to report (GH-2349)."""
    (tmp_path / ".env").write_text("WD_CACHE_DIABLE=secret-ish\nOTHER_SECRET=secret-ish\n")
    assert check_settings() == []


@pytest.mark.parametrize("threshold", [0, -0.5, 1.01, 5])
def test_settings_skip_threshold_refuses_a_value_outside_zero_to_one(
    monkeypatch: pytest.MonkeyPatch,
    threshold: float,
) -> None:
    """A skip threshold outside (0, 1] is refused, as the CLI option refuses it (GH-2334).

    It used to be taken, and one above 1 skipped every station with no hint at the setting.
    """
    monkeypatch.delenv("WD_TS_SKIP_THRESHOLD", raising=False)
    with pytest.raises(ValidationError, match="ts_skip_threshold"):
        Settings(ts_skip_threshold=threshold)


def test_settings_skip_threshold_refuses_an_environment_value_outside_zero_to_one(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`WD_TS_SKIP_THRESHOLD` is held to (0, 1] as the argument is (GH-2334)."""
    monkeypatch.setenv("WD_TS_SKIP_THRESHOLD", "5")
    with pytest.raises(ValidationError, match="ts_skip_threshold"):
        Settings()


def test_settings_skip_threshold_takes_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """The upper bound is in the range: 1 asks for every reading (GH-2334)."""
    monkeypatch.setenv("WD_TS_SKIP_THRESHOLD", "1")
    assert Settings().ts_skip_threshold == 1


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize("field", ["ts_geo_station_distance", "ts_geo_station_distance_resolution_factors"])
@pytest.mark.parametrize("value", [5, "abc", [1.0]])
def test_settings_geo_station_distance_mappings_refuse_anything_but_a_mapping(field: str, value: object) -> None:
    """A non-empty value that is not a mapping is refused by pydantic, named by its field (GH-2353).

    The key checks used to look for keys in it, and failed with a bare `TypeError` naming nothing.
    """
    with pytest.raises(ValidationError, match=rf"{field}\n  Input should be a valid dictionary"):
        Settings(**{field: value})


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize("field", ["ts_geo_station_distance", "ts_geo_station_distance_resolution_factors"])
@pytest.mark.parametrize("value", ["5", '"abc"', "[1.0]"])
def test_settings_geo_station_distance_mappings_refuse_anything_but_a_mapping_from_env(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str,
) -> None:
    """A `WD_*` variable holding JSON that is no object is refused the same way (GH-2353)."""
    monkeypatch.setenv(f"WD_{field.upper()}", value)
    with pytest.raises(ValidationError, match=rf"{field}\n  Input should be a valid dictionary"):
        Settings()


@pytest.mark.usefixtures("_no_ambient_settings")
def test_settings_dotenv_ignores_a_key_that_is_no_setting(tmp_path: Path) -> None:
    """A `.env` shared with another program does not stop the settings from loading (GH-2349).

    Its key used to be refused, and its value echoed, by every `Settings()`. A key without the
    prefix is not taken for a setting even where it names one, and the settings in the same file
    are still read.
    """
    (tmp_path / ".env").write_text("POSTGRES_PASSWORD=secret-ish\nTS_SHAPE=wide\nWD_CACHE_DISABLE=true\n")
    settings = Settings()
    assert settings.cache_disable
    assert settings.ts_shape == "long"


@pytest.mark.usefixtures("_no_ambient_settings")
def test_settings_dotenv_ignores_a_misspelt_wd_key(tmp_path: Path) -> None:
    """A misspelt `WD_*` key in `.env` is ignored, as the same variable in the environment is (GH-2349)."""
    (tmp_path / ".env").write_text("WD_CACHE_DIABLE=true\n")
    assert not Settings().cache_disable


@pytest.mark.usefixtures("_no_ambient_settings")
def test_settings_keyword_that_is_no_setting_is_still_refused() -> None:
    """Only `.env` is let off: a misspelt keyword to the constructor is still refused (GH-2349)."""
    with pytest.raises(ValidationError, match="cache_disabel\n  Extra inputs are not permitted"):
        Settings(cache_disabel=True)


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        pytest.param("ts_skip_threshold", 5, "Input should be less than or equal to 1", id="bounded"),
        pytest.param("ts_shape", "foo", "Input should be 'wide' or 'long'", id="literal"),
        pytest.param(
            "ts_geo_station_distance",
            {"precipitation_heigt": 25.0},
            "['precipitation_heigt'] not in the canonical parameters",
            id="dict-keys",
        ),
        pytest.param(
            "ts_unit_targets",
            {"temperature": "furlong"},
            "Unit furlong not supported for type temperature",
            id="unit-targets",
        ),
    ],
)
def test_settings_assignment_is_validated(field: str, value: object, message: str) -> None:
    """A field assigned after construction is refused as the constructor refuses it (GH-2342).

    It used to be taken as it was: a skip threshold of 5 skipped every station, and a shape out of
    its choices failed later, far from the assignment. A refused assignment leaves the field as it
    was.
    """
    settings = Settings()
    before = copy.copy(getattr(settings, field))
    with pytest.raises(ValidationError, match=rf"{field}\n  [^\n]*{re.escape(message)}"):
        setattr(settings, field, value)
    assert getattr(settings, field) == before


@pytest.mark.usefixtures("_no_ambient_settings")
def test_settings_assignment_takes_a_valid_value() -> None:
    """A valid assignment is taken, and coerced to the field's type as the constructor does (GH-2342)."""
    settings = Settings()
    settings.ts_skip_threshold = 0.5
    settings.ts_skip_criteria = "mean"
    settings.cache_dir = "some/dir"
    assert settings.ts_skip_threshold == 0.5
    assert settings.ts_skip_criteria == "mean"
    assert settings.cache_dir == Path("some/dir")


@pytest.mark.usefixtures("_no_ambient_settings")
def test_settings_assignment_rewrites_fields_as_construction_does() -> None:
    """The validators that rewrite a field give on assignment what they give on construction (GH-2342).

    The client kwargs are laid over the defaults, empty unit targets become an empty dict, and a
    radius assigned reaches the per-parameter mapping at once, the overrides it was built with kept.
    """
    settings = Settings()
    settings.fsspec_client_kwargs = {"trust_env": True}
    assert settings.fsspec_client_kwargs == Settings(fsspec_client_kwargs={"trust_env": True}).fsspec_client_kwargs
    settings.ts_unit_targets = None
    assert settings.ts_unit_targets == Settings(ts_unit_targets=None).ts_unit_targets == {}

    assigned = Settings(ts_geo_station_distance={"precipitation_amount": 25.0})
    assigned.ts_geo_station_distance_homogeneous = 33.0
    assigned.ts_geo_station_distance_heterogeneous = 11.0
    constructed = Settings(
        ts_geo_station_distance={"precipitation_amount": 25.0},
        ts_geo_station_distance_homogeneous=33.0,
        ts_geo_station_distance_heterogeneous=11.0,
    )
    assert assigned.ts_geo_station_distance == constructed.ts_geo_station_distance
    assert assigned.ts_geo_station_distance["temperature_air_mean_2m"] == 33.0
    assert assigned.ts_geo_station_distance["precipitation_duration"] == 11.0
    assert assigned.ts_geo_station_distance["precipitation_amount"] == 25.0
    assert assigned.model_dump()["ts_geo_station_distance"] == {"precipitation_amount": 25.0}


@pytest.mark.usefixtures("_no_ambient_settings")
def test_settings_wide_shape_leaves_drop_nulls_as_given_and_turns_it_off_in_effect() -> None:
    """The wide shape turns the dropping of nulls off in effect, not in the field (GH-2388)."""
    assert Settings(ts_shape="wide").ts_drop_nulls is True
    assert Settings(ts_shape="wide").ts_drop_nulls_effective is False
    assert Settings(ts_shape="wide", ts_drop_nulls=False).ts_drop_nulls is False
    assert Settings().ts_drop_nulls_effective is True
    assert Settings(ts_drop_nulls=False).ts_drop_nulls_effective is False


@pytest.mark.usefixtures("_no_ambient_settings")
def test_settings_drop_nulls_again_once_the_shape_assigned_is_long_again() -> None:
    """A `Settings` once wide drops nulls again once long, as one never wide does (GH-2388).

    The wide shape used to write False into `ts_drop_nulls`, for good, and since GH-2342 an
    assignment did so too.
    """
    settings = Settings()
    settings.ts_shape = "wide"
    assert settings.ts_drop_nulls_effective is False
    settings.ts_shape = "long"
    assert settings.ts_drop_nulls is True
    assert settings.ts_drop_nulls_effective is True

    settings = Settings(ts_shape="wide", ts_drop_nulls=False)
    settings.ts_shape = "long"
    assert settings.ts_drop_nulls_effective is False


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize("value", ["12345", "-12345", "123456789012345678901234567890"])
def test_settings_auth_metno_frost_takes_an_all_digit_client_id_as_one(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    """An all-digit Frost client id, which the environment decodes as a number, is still an id (GH-2379)."""
    monkeypatch.setenv("WD_AUTH__METNO_FROST", value)
    assert tuple(reveal(part) for part in Settings().auth.metno_frost) == (value, "")
    assert tuple(reveal(part) for part in Settings(auth={"metno_frost": int(value)}).auth.metno_frost) == (value, "")


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize(
    ("name", "value"),
    [
        ("WD_AUTH__CEDA", "5"),
        ("WD_AUTH__CEDA", "true"),
        ("WD_AUTH__CEDA", '{"user": "x", "password": "y"}'),
        ("WD_AUTH__METNO_FROST", "true"),
        ("WD_AUTH__METNO_FROST", "1.5"),
        ("WD_AUTH__METNO_FROST", '{"id": "x", "secret": "y"}'),
    ],
)
def test_check_settings_names_an_auth_variable_that_is_no_credential(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
) -> None:
    """A credential the environment decodes as something other than text or a pair is told by its variable.

    Reading it as a pair used to fail with a bare `TypeError` that named nothing, which the check did
    not catch; a JSON object was taken apart into its keys (GH-2379).
    """
    monkeypatch.setenv(name, value)
    assert check_settings() == [f"{name} is invalid: Input should be a valid tuple"]


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize(
    ("auth", "field"),
    [
        ({"ceda": 5}, "ceda"),
        ({"ceda": True}, "ceda"),
        ({"metno_frost": 1.5}, "metno_frost"),
        ({"metno_frost": {"id": "x", "secret": "y"}}, "metno_frost"),
    ],
)
def test_settings_auth_refuses_a_value_that_is_no_credential_by_its_field(auth: dict, field: str) -> None:
    """A credential given as something other than text or a pair is refused by its field (GH-2379)."""
    with pytest.raises(ValidationError) as excinfo:
        Settings(auth=auth)
    assert [error["loc"] for error in excinfo.value.errors()] == [("auth", field)]


@pytest.mark.usefixtures("_no_ambient_settings")
def test_settings_auth_validates_an_assigned_credential() -> None:
    """A credential assigned after construction is held as one given to the constructor is (GH-2387)."""
    settings = Settings()
    settings.auth.knmi = "DUMMY-KNMI-KEY"
    settings.auth.ceda = "DUMMY-CEDA-USER:DUMMY-CEDA-PASSWORD"
    settings.auth.metno_frost = "DUMMY-FROST-ID"

    assert isinstance(settings.auth.knmi, SecretStr)
    assert reveal(settings.auth.knmi) == "DUMMY-KNMI-KEY"
    assert all(isinstance(part, SecretStr) for part in settings.auth.ceda)
    assert tuple(reveal(part) for part in settings.auth.ceda) == ("DUMMY-CEDA-USER", "DUMMY-CEDA-PASSWORD")
    assert tuple(reveal(part) for part in settings.auth.metno_frost) == ("DUMMY-FROST-ID", "")
    assert "DUMMY" not in repr(settings)


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("aemet", "*" * 10),
        ("ceda", ("*" * 10, "*" * 10)),
        ("metno_frost", ("DUMMY-FROST-ID", "*" * 10)),
    ],
)
def test_settings_auth_refuses_a_masked_value_assigned_as_a_credential(field: str, value: object) -> None:
    """The mask a JSON dump leaves behind is refused on assignment as in the constructor (GH-2387)."""
    settings = Settings()
    with pytest.raises(ValidationError, match="mask"):
        setattr(settings.auth, field, value)
    assert getattr(settings.auth, field) is None


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize("field", ["ceda", "metno_frost"])
@pytest.mark.parametrize("container", [collections.deque, iter], ids=["deque", "iterator"])
def test_settings_auth_reads_a_pair_from_another_iterable(field: str, container: Callable) -> None:
    """A pair given as another iterable than a tuple or list is read as one, and its mask refused (GH-2379).

    Leaving every value but a tuple or list for the field passed these on unread, and the mask in them
    went unseen.
    """
    pair = Settings(auth={field: container(["DUMMY-ID", "DUMMY-SECRET"])}).auth
    assert tuple(reveal(part) for part in getattr(pair, field)) == ("DUMMY-ID", "DUMMY-SECRET")
    with pytest.raises(ValidationError, match="mask"):
        Settings(auth={field: container(["DUMMY-ID", "*" * 10])})


def _no_home(appname: str) -> str:
    """Raise what platformdirs 4.12 raises where no home directory resolves."""
    msg = f"could not determine the home directory for '~/.cache/{appname}', set HOME or an absolute XDG variable"
    raise RuntimeError(msg)


@pytest.fixture
def fresh_temporary_cache_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Iterator[Path]:
    """Create the fallback cache directory below `tmp_path`, anew for each test, with no exit handler."""
    monkeypatch.delenv("WD_CACHE_DIR", raising=False)
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    monkeypatch.setattr(atexit, "register", lambda *_args, **_kwargs: None)
    _temporary_cache_dir.cache_clear()
    yield tmp_path
    _temporary_cache_dir.cache_clear()


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize("cache_disable", [False, True])
def test_settings_fall_back_to_a_temporary_cache_dir_where_no_home_resolves(
    fresh_temporary_cache_dir: Path,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    *,
    cache_disable: bool,
) -> None:
    """`Settings()` no longer raises where platformdirs finds no home, cache disabled or not (GH-2408)."""
    monkeypatch.setattr(platformdirs, "user_cache_dir", _no_home)
    at_exit = []
    monkeypatch.setattr(atexit, "register", lambda *args, **kwargs: at_exit.append((args, kwargs)))
    caplog.set_level(logging.WARNING)
    settings = Settings(cache_disable=cache_disable)
    assert settings.cache_dir.parent == fresh_temporary_cache_dir
    assert settings.cache_dir.name.startswith("wetterdienst-")
    assert settings.cache_dir.is_dir()
    # one directory per process, not one per `Settings()`
    assert Settings().cache_dir == settings.cache_dir
    # and removed when the process exits
    assert at_exit == [((_remove_unless_forked, settings.cache_dir, os.getpid()), {})]
    warnings = [record.getMessage() for record in caplog.records if record.levelno == logging.WARNING]
    assert len(warnings) == 1
    assert "WD_CACHE_DIR" in warnings[0]
    assert "HOME" in warnings[0]


@pytest.mark.usefixtures("_no_ambient_settings")
def test_settings_fall_back_to_a_temporary_cache_dir_for_an_unexpanded_home(
    fresh_temporary_cache_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Platformdirs before 4.12 returned `~/...` unexpanded, which made a `~` directory below the cwd (GH-2408)."""
    monkeypatch.setattr(platformdirs, "user_cache_dir", lambda appname: f"~/.cache/{appname}")
    assert Settings().cache_dir.parent == fresh_temporary_cache_dir


@pytest.mark.usefixtures("_no_ambient_settings", "fresh_temporary_cache_dir")
def test_settings_take_the_cache_dir_given_where_no_home_resolves(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A `WD_CACHE_DIR` given means the default is never asked for (GH-2408)."""
    monkeypatch.setattr(platformdirs, "user_cache_dir", _no_home)
    monkeypatch.setenv("WD_CACHE_DIR", str(tmp_path / "given"))
    assert Settings().cache_dir == tmp_path / "given"
    assert Settings(cache_dir=tmp_path / "keyword").cache_dir == tmp_path / "keyword"


@pytest.mark.usefixtures("_no_ambient_settings", "fresh_temporary_cache_dir")
def test_settings_name_wd_cache_dir_and_home_where_no_cache_dir_can_be_made(monkeypatch: pytest.MonkeyPatch) -> None:
    """With neither a home nor a temporary directory, the error says what to set (GH-2408)."""
    monkeypatch.setattr(platformdirs, "user_cache_dir", _no_home)

    def refuse(**_kwargs: object) -> str:
        raise FileNotFoundError(2, "No usable temporary directory found")

    monkeypatch.setattr(tempfile, "mkdtemp", refuse)
    with pytest.raises(SettingsError, match=r"set WD_CACHE_DIR to a writable directory, or HOME"):
        Settings(cache_disable=True)
    # told by the CLI and the REST API as an invalid setting is, not as a bare exception type
    (problem,) = check_settings()
    assert "set WD_CACHE_DIR to a writable directory, or HOME" in problem


def test_settings_leave_the_temporary_cache_dir_to_the_process_that_made_it(tmp_path: Path) -> None:
    """A forked child exiting does not remove the directory its parent still uses (GH-2408)."""
    path = tmp_path / "wetterdienst-cache"
    path.mkdir()
    _remove_unless_forked(path, os.getpid() + 1)
    assert path.is_dir()
    _remove_unless_forked(path, os.getpid())
    assert not path.exists()


@pytest.mark.usefixtures("_no_ambient_settings")
def test_settings_make_one_temporary_cache_dir_for_threads_that_miss_at_once(
    fresh_temporary_cache_dir: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A second thread asking while the first makes the directory gets the same one (GH-2408)."""
    monkeypatch.setattr(platformdirs, "user_cache_dir", _no_home)
    mkdtemp = tempfile.mkdtemp
    made = []
    second: list[Path] = []

    def mkdtemp_while_another_thread_asks(**kwargs: object) -> str:
        made.append(mkdtemp(**kwargs))
        if len(made) == 1:
            other = threading.Thread(target=lambda: second.append(default_cache_dir()))
            other.start()
            # with the lock the other thread waits for this one, and is still waiting here
            other.join(timeout=0.2)
            threads.append(other)
        return made[-1]

    threads: list[threading.Thread] = []
    monkeypatch.setattr(tempfile, "mkdtemp", mkdtemp_while_another_thread_asks)
    first = default_cache_dir()
    threads[0].join()
    assert len(made) == 1
    assert second == [first]
    assert first.parent == fresh_temporary_cache_dir


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize("secret", [None, ""], ids=["null", "empty"])
def test_settings_auth_metno_frost_takes_a_null_secret_as_an_empty_one(
    monkeypatch: pytest.MonkeyPatch, secret: str | None
) -> None:
    """A Frost client id paired with `null` is one with no secret, as a lone client id is (GH-2434)."""
    monkeypatch.setenv("WD_AUTH__METNO_FROST", json.dumps(["DUMMY-FROST-ID", secret]))
    assert tuple(reveal(part) for part in Settings().auth.metno_frost) == ("DUMMY-FROST-ID", "")
    pair = Settings(auth={"metno_frost": ["DUMMY-FROST-ID", secret]}).auth.metno_frost
    assert tuple(reveal(part) for part in pair) == ("DUMMY-FROST-ID", "")


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize("field", ["ceda", "metno_frost"])
def test_settings_auth_takes_all_digit_elements_of_a_pair_as_text(monkeypatch: pytest.MonkeyPatch, field: str) -> None:
    """An all-digit element of a pair, which the environment decodes as a number, is its text (GH-2434)."""
    monkeypatch.setenv(f"WD_AUTH__{field.upper()}", "[12345, 67890]")
    assert tuple(reveal(part) for part in getattr(Settings().auth, field)) == ("12345", "67890")


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize(
    ("field", "pair", "index"),
    [
        ("metno_frost", [None, "DUMMY-FROST-SECRET"], 0),
        ("metno_frost", ["DUMMY-FROST-ID", True], 1),
        ("metno_frost", ["DUMMY-FROST-ID", 1.5], 1),
        ("metno_frost", ["DUMMY-FROST-ID", {"secret": "x"}], 1),
        ("ceda", [None, "DUMMY-CEDA-PASSWORD"], 0),
        ("ceda", ["DUMMY-CEDA-USER", None], 1),
        ("ceda", ["DUMMY-CEDA-USER", True], 1),
        ("ceda", [False, "DUMMY-CEDA-PASSWORD"], 0),
        ("ceda", [["DUMMY-CEDA-USER"], "DUMMY-CEDA-PASSWORD"], 0),
    ],
)
def test_settings_auth_refuses_an_element_of_a_pair_that_is_no_credential(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    pair: list,
    index: int,
) -> None:
    """An element of a pair that is neither text nor a number is refused by its index (GH-2434).

    It was taken as the text of its repr, `'None'` or `'True'`, and sent to the provider as the credential.
    """
    with pytest.raises(ValidationError) as excinfo:
        Settings(auth={field: pair})
    assert [error["loc"] for error in excinfo.value.errors()] == [("auth", field, index)]

    variable = f"WD_AUTH__{field.upper()}"
    monkeypatch.setenv(variable, json.dumps(pair))
    assert check_settings() == [f"{variable}[{index}] is invalid: Input should be a valid string"]


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize(
    "build",
    [
        pytest.param(lambda: Settings(auth={"ceda": "DUMMY-USER;TOPSECRET"}), id="ceda-text"),
        pytest.param(lambda: Settings(auth={"ceda": ("DUMMY-USER", {"password": "TOPSECRET"})}), id="ceda-element"),
        pytest.param(lambda: Settings(auth={"metno_frost": ("TOPSECRET", "*" * 10)}), id="metno-frost-mask"),
        pytest.param(lambda: Settings(auth="TOPSECRET"), id="auth-whole"),
        pytest.param(lambda: Auth(ceda="DUMMY-USER;TOPSECRET"), id="auth-model"),
        pytest.param(lambda: setattr(Settings(), "auth", {"ceda": "DUMMY-USER;TOPSECRET"}), id="assign-auth"),
        pytest.param(lambda: setattr(Settings().auth, "ceda", "DUMMY-USER;TOPSECRET"), id="assign-ceda"),
    ],
)
def test_settings_auth_does_not_repeat_a_refused_credential(build: Callable[[], object]) -> None:
    """A credential refused is not repeated in the error, which pydantic echoes as its input (GH-2435)."""
    with pytest.raises(ValidationError) as excinfo:
        build()
    assert "TOPSECRET" not in str(excinfo.value)


@pytest.mark.usefixtures("_no_ambient_settings")
def test_settings_auth_does_not_repeat_a_refused_credential_from_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A credential refused from the environment is not repeated in the error either (GH-2435)."""
    monkeypatch.setenv("WD_AUTH__CEDA", "DUMMY-USER;TOPSECRET")
    with pytest.raises(ValidationError) as excinfo:
        Settings()
    assert "TOPSECRET" not in str(excinfo.value)


@pytest.mark.parametrize(
    ("loc", "variable"),
    [
        (("auth", "ceda", 1), "WD_AUTH__CEDA[1]"),
        (("setting", 0, "key"), "WD_SETTING[0]__KEY"),
        ((), "WD_*"),
    ],
)
def test_describe_settings_error_names_an_element_where_it_stands(loc: tuple, variable: str) -> None:
    """An index in a problem's location is told where it stands, after the name holding it (GH-2434)."""
    error = ValidationError.from_exception_data("Settings", [{"type": "missing", "loc": loc, "input": None}])
    assert _describe_settings_error(error) == [f"{variable} is invalid: Field required"]


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize(
    "value",
    [
        "[DUMMY-FROST-ID, TOPSECRET]",
        '[0123, "TOPSECRET"]',
        '["DUMMY-FROST-ID", "TOPSECRET"',
        '  ["DUMMY-FROST-ID",TOPSECRET]',
    ],
    ids=["unquoted", "leading-zero", "unclosed", "leading-space"],
)
def test_settings_auth_metno_frost_refuses_a_pair_that_is_not_valid_json(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    """A Frost pair that is not valid JSON is refused, not taken whole as the client id (GH-2464).

    The environment hands on such a pair as its raw text, which was read as a lone client id with
    the secret inside it. Neither the error nor `check_settings()` repeats the secret.
    """
    message = 'metno_frost looks like a pair but is not valid JSON: write it as ["client_id", "secret"]'
    monkeypatch.setenv("WD_AUTH__METNO_FROST", value)
    assert check_settings() == [f"WD_AUTH__METNO_FROST is invalid: {message}"]
    with pytest.raises(ValidationError, match=re.escape(message)) as excinfo:
        Settings()
    assert "TOPSECRET" not in str(excinfo.value)
    assert "TOPSECRET" not in repr(excinfo.value)

    monkeypatch.delenv("WD_AUTH__METNO_FROST")
    builds: list[Callable[[], object]] = [
        lambda: Settings(auth={"metno_frost": value}),
        lambda: Settings(auth={"metno_frost": SecretStr(value)}),
        lambda: setattr(Settings().auth, "metno_frost", value),
    ]
    for build in builds:
        with pytest.raises(ValidationError, match=re.escape(message)) as excinfo:
            build()
        assert "TOPSECRET" not in str(excinfo.value)


@pytest.mark.usefixtures("_no_ambient_settings")
def test_settings_auth_metno_frost_still_takes_a_lone_client_id_and_a_valid_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A lone client id and a pair written as valid JSON are still read as before (GH-2464)."""
    monkeypatch.setenv("WD_AUTH__METNO_FROST", "DUMMY-FROST-ID")
    assert tuple(reveal(part) for part in Settings().auth.metno_frost) == ("DUMMY-FROST-ID", "")
    monkeypatch.setenv("WD_AUTH__METNO_FROST", ' ["DUMMY-FROST-ID", "DUMMY-FROST-SECRET"]')
    assert tuple(reveal(part) for part in Settings().auth.metno_frost) == ("DUMMY-FROST-ID", "DUMMY-FROST-SECRET")
    assert check_settings() == []


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize("wrap", [str, SecretStr], ids=["str", "secret"])
def test_settings_auth_metno_frost_reads_a_pair_given_as_json_text_in_python(wrap: Callable[[str], object]) -> None:
    """A pair given in Python as valid JSON text is read as the pair, as from the environment (GH-2464).

    It was taken whole as the client id, and a refusal of what starts with `[` would have told the
    caller to fix JSON that is already valid.
    """
    text = '["DUMMY-FROST-ID", "DUMMY-FROST-SECRET"]'
    expected = ("DUMMY-FROST-ID", "DUMMY-FROST-SECRET")
    assert tuple(reveal(part) for part in Settings(auth={"metno_frost": wrap(text)}).auth.metno_frost) == expected
    settings = Settings()
    settings.auth.metno_frost = wrap(text)
    assert tuple(reveal(part) for part in settings.auth.metno_frost) == expected
    with pytest.raises(ValidationError, match=r"got 3 element\(s\)"):
        Settings(auth={"metno_frost": wrap('["a", "b", "c"]')})


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize(
    ("value", "from_environment"),
    [
        ("[DUMMY-FROST-ID, TOPSECRET]", False),
        ("[DUMMY-FROST-ID, TOPSECRET]", True),
        ("[" + "1" * 5000 + ', "TOPSECRET"]', False),
        ("[" + "1" * 5000 + ', "TOPSECRET"]', True),
        # the environment's own decoding fails on this before the settings see it
        ("[" * 100_000 + "TOPSECRET", False),
    ],
    ids=["unquoted", "unquoted-env", "integer-too-long", "integer-too-long-env", "nested-too-deep"],
)
def test_settings_auth_metno_frost_refusal_keeps_no_exception_holding_the_secret(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
    *,
    from_environment: bool,
) -> None:
    """The refusal of a Frost pair keeps no exception that holds the refused text (GH-2464).

    A JSON decode error holds the text it failed on as its `doc`, and an exception raised while it
    is handled keeps it as its context, which pydantic keeps in the error's `ctx` -- where an error
    reporter or a debugger walking the chain reaches it. Text that fails to decode another way --
    an integer too long to convert, nesting too deep -- gets the same refusal, rather than an error
    of its own or an escaping `RecursionError`.
    """
    message = 'metno_frost looks like a pair but is not valid JSON: write it as ["client_id", "secret"]'
    if from_environment:
        monkeypatch.setenv("WD_AUTH__METNO_FROST", value)
    with pytest.raises(ValidationError, match=re.escape(message)) as excinfo:
        Settings() if from_environment else Settings(auth={"metno_frost": value})
    for error in excinfo.value.errors():
        exception: BaseException | None = error.get("ctx", {}).get("error")
        while exception is not None:
            assert "TOPSECRET" not in repr(exception.args)
            assert "TOPSECRET" not in repr(vars(exception))
            exception = exception.__cause__ or exception.__context__


@pytest.mark.usefixtures("_no_ambient_settings")
def test_settings_auth_metno_frost_reads_a_pair_after_any_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    """A pair after whitespace that JSON does not take, such as a pasted no-break space, is still read (GH-2464)."""
    monkeypatch.setenv("WD_AUTH__METNO_FROST", '\xa0["DUMMY-FROST-ID", "DUMMY-FROST-SECRET"]\xa0')
    assert tuple(reveal(part) for part in Settings().auth.metno_frost) == ("DUMMY-FROST-ID", "DUMMY-FROST-SECRET")


@pytest.mark.parametrize("ts_shape", ["long", "wide"])
def test_settings_request_built_from_settings_logs_them_once(caplog: pytest.LogCaptureFixture, ts_shape: str) -> None:
    """A request handed a `Settings` does not validate it again, which logged its notices twice (GH-2476).

    The CLI builds the settings and then the request from them; every command logged the cache line
    twice, and the `ts_drop_nulls` notice too for a wide shape.
    """
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415

    with caplog.at_level(logging.INFO, logger="wetterdienst.settings"):
        settings = Settings(ts_shape=ts_shape)
        request = DwdObservationRequest(parameters=["daily/kl"], settings=settings)
    assert request.settings is settings
    messages = [record.getMessage() for record in caplog.records if record.name == "wetterdienst.settings"]
    assert sum(message.startswith("Wetterdienst cache is") for message in messages) == 1
    assert sum("ts_drop_nulls" in message for message in messages) == (ts_shape == "wide")


def test_settings_request_validates_settings_given_as_a_dict() -> None:
    """A request handed its settings as a dict still validates them into a `Settings` (GH-2476)."""
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415

    request = DwdObservationRequest(parameters=["daily/kl"], settings={"ts_shape": "wide"})
    assert isinstance(request.settings, Settings)
    assert request.settings.ts_shape == "wide"


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize(
    "value",
    [
        '["DUMMY-USER", "TOP:SECRET"',
        "[DUMMY-USER, TOP:SECRET]",
        "[DUMMY-USER, TOPSECRET]",
        '  ["DUMMY-USER",TOP:SECRET]',
    ],
    ids=["unclosed-colon", "unquoted-colon", "unquoted", "leading-space"],
)
def test_settings_auth_ceda_refuses_a_pair_that_is_not_valid_json(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    """A CEDA pair that is not valid JSON is refused, not split at a colon inside it (GH-2483).

    The environment hands on such a pair as its raw text, which was split at its first colon with
    the brackets and quotes kept in both halves. Neither the error nor `check_settings()` repeats
    the password.
    """
    message = 'ceda looks like a pair but is not valid JSON: write it as ["username", "password"]'
    monkeypatch.setenv("WD_AUTH__CEDA", value)
    assert check_settings() == [f"WD_AUTH__CEDA is invalid: {message}"]
    with pytest.raises(ValidationError, match=re.escape(message)) as excinfo:
        Settings()
    assert "SECRET" not in str(excinfo.value)
    assert "SECRET" not in repr(excinfo.value)

    monkeypatch.delenv("WD_AUTH__CEDA")
    builds: list[Callable[[], object]] = [
        lambda: Settings(auth={"ceda": value}),
        lambda: Settings(auth={"ceda": SecretStr(value)}),
        lambda: setattr(Settings().auth, "ceda", value),
    ]
    for build in builds:
        with pytest.raises(ValidationError, match=re.escape(message)) as excinfo:
            build()
        assert "SECRET" not in str(excinfo.value)


@pytest.mark.usefixtures("_no_ambient_settings")
def test_settings_auth_ceda_still_takes_username_password_text_and_a_valid_pair(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`username:password` text and a pair written as valid JSON are still read as before (GH-2483)."""
    monkeypatch.setenv("WD_AUTH__CEDA", "DUMMY-USER:DUMMY:PASSWORD")
    assert tuple(reveal(part) for part in Settings().auth.ceda) == ("DUMMY-USER", "DUMMY:PASSWORD")
    monkeypatch.setenv("WD_AUTH__CEDA", ' ["DUMMY-USER", "DUMMY:PASSWORD"]')
    assert tuple(reveal(part) for part in Settings().auth.ceda) == ("DUMMY-USER", "DUMMY:PASSWORD")
    assert check_settings() == []
    monkeypatch.setenv("WD_AUTH__CEDA", "DUMMY-USER")
    assert check_settings() == ["WD_AUTH__CEDA is invalid: ceda must be given as 'username:password'"]


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize("wrap", [str, SecretStr], ids=["str", "secret"])
def test_settings_auth_ceda_reads_a_pair_given_as_json_text_in_python(wrap: Callable[[str], object]) -> None:
    """A pair given in Python as valid JSON text is read as the pair, as from the environment (GH-2483).

    It was split at a colon in it, and a refusal of what starts with `[` would have told the caller
    to fix JSON that is already valid.
    """
    text = '["DUMMY-USER", "DUMMY:PASSWORD"]'
    expected = ("DUMMY-USER", "DUMMY:PASSWORD")
    assert tuple(reveal(part) for part in Settings(auth={"ceda": wrap(text)}).auth.ceda) == expected
    settings = Settings()
    settings.auth.ceda = wrap(text)
    assert tuple(reveal(part) for part in settings.auth.ceda) == expected
    with pytest.raises(ValidationError, match=r"got 3 element\(s\)"):
        Settings(auth={"ceda": wrap('["a", "b", "c"]')})


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize(
    ("value", "from_environment"),
    [
        ("[DUMMY-USER, TOP:SECRET]", False),
        ("[DUMMY-USER, TOP:SECRET]", True),
        ("[" + "1" * 5000 + ', "TOP:SECRET"]', False),
        ("[" + "1" * 5000 + ', "TOP:SECRET"]', True),
        # the environment's own decoding fails on this before the settings see it
        ("[" * 100_000 + "TOP:SECRET", False),
    ],
    ids=["unquoted", "unquoted-env", "integer-too-long", "integer-too-long-env", "nested-too-deep"],
)
def test_settings_auth_ceda_refusal_keeps_no_exception_holding_the_password(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
    *,
    from_environment: bool,
) -> None:
    """The refusal of a CEDA pair keeps no exception that holds the refused text (GH-2483).

    A JSON decode error holds the text it failed on as its `doc`, and an exception raised while it
    is handled keeps it as its context, which pydantic keeps in the error's `ctx`. Text that fails
    to decode another way -- an integer too long to convert, nesting too deep -- gets the same
    refusal, rather than an error of its own or an escaping `RecursionError`.
    """
    message = 'ceda looks like a pair but is not valid JSON: write it as ["username", "password"]'
    if from_environment:
        monkeypatch.setenv("WD_AUTH__CEDA", value)
    with pytest.raises(ValidationError, match=re.escape(message)) as excinfo:
        Settings() if from_environment else Settings(auth={"ceda": value})
    for error in excinfo.value.errors():
        exception: BaseException | None = error.get("ctx", {}).get("error")
        while exception is not None:
            assert "SECRET" not in repr(exception.args)
            assert "SECRET" not in repr(vars(exception))
            exception = exception.__cause__ or exception.__context__


@pytest.mark.usefixtures("_no_ambient_settings")
def test_settings_auth_ceda_reads_a_pair_after_any_whitespace(monkeypatch: pytest.MonkeyPatch) -> None:
    """A pair after whitespace that JSON does not take, such as a pasted no-break space, is still read (GH-2483)."""
    monkeypatch.setenv("WD_AUTH__CEDA", '\xa0["DUMMY-USER", "DUMMY:PASSWORD"]\xa0')
    assert tuple(reveal(part) for part in Settings().auth.ceda) == ("DUMMY-USER", "DUMMY:PASSWORD")


def _settings_log_messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.name == "wetterdienst.settings"]


def test_settings_log_once_not_per_assignment(caplog: pytest.LogCaptureFixture) -> None:
    """Assigning a field or revalidating an instance does not log the settings' notices again (GH-2504)."""
    with caplog.at_level(logging.INFO, logger="wetterdienst.settings"):
        # given explicitly, so neither the environment nor a `.env` changes what is logged
        settings = Settings(cache_disable=False, ts_shape="wide")
        messages = _settings_log_messages(caplog)
        assert len(messages) == 2
        assert "ts_drop_nulls" in messages[0]
        assert messages[1].startswith("Wetterdienst cache is enabled")
        settings.ts_skip_empty = True
        settings.ts_shape = "long"
        settings.ts_shape = "wide"
        settings.cache_disable = True
        Settings.model_validate(settings)
    assert _settings_log_messages(caplog) == messages


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize(
    "value",
    [
        "DUMMY-FROST-ID:TOPSECRET",
        "DUMMY-FROST-ID,TOPSECRET",
        "DUMMY-FROST-ID TOPSECRET",
        "DUMMY-FROST-ID\tTOPSECRET",
        '("DUMMY-FROST-ID", "TOPSECRET")',
        "{DUMMY-FROST-ID: TOPSECRET}",
        "DUMMY-FROST-ID:",
        "DUMMY-FROST-ID;TOPSECRET",
        "DUMMY-FROST-ID|TOPSECRET",
        "DUMMY-FROST-ID=TOPSECRET",
        "DUMMY-FROST-ID/TOPSECRET",
        "DUMMY-FROST-ID@TOPSECRET",
        "DUMMY-FROST-ID_TOPSECRET",
    ],
    ids=[
        "colon",
        "comma",
        "space",
        "tab",
        "tuple",
        "braces",
        "colon-no-secret",
        "semicolon",
        "pipe",
        "equals",
        "slash",
        "at",
        "underscore",
    ],
)
def test_settings_auth_metno_frost_refuses_a_pair_written_as_a_lone_text(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    """A Frost pair written as `id:secret` or the like is refused, not taken whole as the client id (GH-2487).

    `id:secret` is the shape WD_AUTH__CEDA takes, so it is an easy one to carry over. Any character
    but a letter, digit or `-` -- all a UUID holds -- is refused, whichever joins the pair. The
    message is the same for each and neither it nor `check_settings()` repeats the text.
    """
    message = 'metno_frost is not a client id (letters, digits and "-" only); write a pair as ["client_id", "secret"]'
    monkeypatch.setenv("WD_AUTH__METNO_FROST", value)
    assert check_settings() == [f"WD_AUTH__METNO_FROST is invalid: {message}"]
    with pytest.raises(ValidationError, match=re.escape(message)) as excinfo:
        Settings()
    assert "TOPSECRET" not in str(excinfo.value)
    assert "TOPSECRET" not in repr(excinfo.value)

    monkeypatch.delenv("WD_AUTH__METNO_FROST")
    builds: list[Callable[[], object]] = [
        lambda: Settings(auth={"metno_frost": value}),
        lambda: Settings(auth={"metno_frost": SecretStr(value)}),
        lambda: setattr(Settings().auth, "metno_frost", value),
    ]
    for build in builds:
        with pytest.raises(ValidationError, match=re.escape(message)) as excinfo:
            build()
        assert "TOPSECRET" not in str(excinfo.value)
        assert "TOPSECRET" not in repr(excinfo.value)


@pytest.mark.usefixtures("_no_ambient_settings")
def test_settings_auth_metno_frost_still_takes_a_uuid_client_id_even_padded_with_whitespace(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A UUID client id is still a lone client id, whitespace around it does not count (GH-2487)."""
    client_id = "8e1b6a2c-3f4d-4c5e-9a7b-0d1e2f3a4b5c"
    monkeypatch.setenv("WD_AUTH__METNO_FROST", client_id)
    assert tuple(reveal(part) for part in Settings().auth.metno_frost) == (client_id, "")
    monkeypatch.setenv("WD_AUTH__METNO_FROST", f" {client_id}\n")
    assert check_settings() == []
    client, secret = Settings().auth.metno_frost
    assert reveal(client).strip() == client_id
    assert reveal(secret) == ""


@pytest.mark.usefixtures("_no_ambient_settings")
def test_settings_auth_metno_frost_names_a_lone_mask_as_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """A lone mask, as a dumped credential leaves it, is still named as one, not refused as a pair (GH-2487)."""
    message = "the value is the mask a dumped credential leaves behind, not a credential"
    monkeypatch.setenv("WD_AUTH__METNO_FROST", "*" * 10)
    assert check_settings() == [f"WD_AUTH__METNO_FROST is invalid: {message}"]
    monkeypatch.delenv("WD_AUTH__METNO_FROST")
    with pytest.raises(ValidationError, match=re.escape(message)):
        Settings(auth={"metno_frost": "*" * 10})
    # a mask padded with whitespace is not the mask, and not a client id either
    for padded in (f" {'*' * 10} ", f"{'*' * 10}\n"):
        monkeypatch.setenv("WD_AUTH__METNO_FROST", padded)
        assert len(check_settings()) == 1
        with pytest.raises(ValidationError, match="is not a client id"):
            Settings(auth={"metno_frost": padded})


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize(
    "padding",
    ["\n", " ", "\t", "\r\n", "\xa0", "\N{LINE SEPARATOR}", "\x1f"],
    ids=["newline", "space", "tab", "crlf", "nbsp", "line-separator", "unit-separator"],
)
def test_settings_auth_metno_frost_keeps_a_lone_client_id_without_its_padding(
    monkeypatch: pytest.MonkeyPatch,
    padding: str,
) -> None:
    r"""A lone client id is kept as the stripped text that was checked, not with its padding (GH-2542).

    A newline arrives from a `.env` value, a `\r` from a file saved with CRLF endings. `str.strip()` also removes NBSP,
    U+2028 and the control characters \x1c-\x1f, which are no more part of a client id.
    """
    client_id = "8e1b6a2c-3f4d-4c5e-9a7b-0d1e2f3a4b5c"
    padded = f"{padding}{client_id}{padding}"
    monkeypatch.setenv("WD_AUTH__METNO_FROST", padded)
    assert check_settings() == []
    assert tuple(reveal(part) for part in Settings().auth.metno_frost) == (client_id, "")
    monkeypatch.delenv("WD_AUTH__METNO_FROST")
    builds: list[Callable[[], Settings]] = [
        lambda: Settings(auth={"metno_frost": padded}),
        lambda: Settings(auth={"metno_frost": SecretStr(padded)}),
    ]
    for build in builds:
        assert tuple(reveal(part) for part in build().auth.metno_frost) == (client_id, "")
    settings = Settings()
    settings.auth.metno_frost = padded
    assert tuple(reveal(part) for part in settings.auth.metno_frost) == (client_id, "")


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize("value", ["", "   ", "\n", "\t \r\n", "\xa0", "\N{LINE SEPARATOR}", "\x1f"])
def test_settings_auth_metno_frost_reads_whitespace_only_text_as_unset(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    """Text of nothing but whitespace is no client id, and reads as unset as an empty value does (GH-2542)."""
    monkeypatch.setenv("WD_AUTH__METNO_FROST", value)
    assert check_settings() == []
    assert Settings().auth.metno_frost is None
    monkeypatch.delenv("WD_AUTH__METNO_FROST")
    assert Settings(auth={"metno_frost": value}).auth.metno_frost is None
    assert Settings(auth={"metno_frost": SecretStr(value)}).auth.metno_frost is None
    settings = Settings()
    settings.auth.metno_frost = value
    assert settings.auth.metno_frost is None


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize(
    ("variable", "error"),
    [
        ("WD_AUTH__CEDA", ValidationError),
        ("WD_AUTH__METNO_FROST", ValidationError),
        ("WD_AUTH", SettingsError),
        ("WD_FSSPEC_CLIENT_KWARGS", SettingsError),
    ],
)
@pytest.mark.parametrize("from_dotenv", [False, True], ids=["environment", "dotenv"])
def test_settings_value_nested_too_deeply_is_refused_as_text_that_is_not_json_is(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    variable: str,
    error: type[Exception],
    *,
    from_dotenv: bool,
) -> None:
    """A value nested too deeply to decode is reported like any other that is not valid JSON (GH-2543).

    The decoder of the environment and of `.env` raised a `RecursionError` for it, which neither
    `check_settings()` nor `Settings()` handled: both raised it, and so did anything that builds the
    settings, such as `MetOfficeObservationRequest.is_configured()`. It is refused with the
    error that text which is not JSON gets, naming the variable and not repeating the value.
    """
    # deeper than the decoder takes, and below the 32767 characters Windows allows in a variable
    value = "[" * 30_000 + "TOPSECRET"
    if from_dotenv:
        (tmp_path / ".env").write_text(f"{variable}={value}\n")
    else:
        monkeypatch.setenv(variable, value)
    (problem,) = check_settings()
    assert problem.startswith(f"{variable} is invalid: ")
    assert "TOPSECRET" not in problem
    with pytest.raises(error) as excinfo:
        Settings()
    assert "TOPSECRET" not in str(excinfo.value)
    # the configuration check of a provider that needs a credential, which builds the settings
    from wetterdienst.provider.metoffice.observation.api import MetOfficeObservationRequest  # noqa: PLC0415

    with pytest.raises(error):
        MetOfficeObservationRequest.is_configured()


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize("from_dotenv", [False, True], ids=["environment", "dotenv"])
def test_settings_key_nested_too_deeply_under_a_dict_setting_is_kept_as_text(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    from_dotenv: bool,
) -> None:
    """A key of a dict setting may hold text, so one nested too deeply is kept as it is, not decoded (GH-2543).

    `WD_FSSPEC_CLIENT_KWARGS__HEADERS` is a key of a dict, which the environment decodes as JSON and
    keeps as text where that fails, `[abc` as well as 30000 brackets. It raised a `RecursionError`
    before; it is read as any text that is not JSON is.
    """
    if from_dotenv:
        (tmp_path / ".env").write_text(f"WD_FSSPEC_CLIENT_KWARGS__HEADERS={'[' * 30_000}\n")
    else:
        monkeypatch.setenv("WD_FSSPEC_CLIENT_KWARGS__HEADERS", "[" * 30_000)
    assert check_settings() == []
    assert Settings().fsspec_client_kwargs["headers"] == "[" * 30_000


_PADDINGS = ["\n", " ", "\t", "\r\n", "\xa0", "\N{LINE SEPARATOR}", "\x1f"]
_PADDING_IDS = ["newline", "space", "tab", "crlf", "nbsp", "line-separator", "unit-separator"]


def _revealed_pair(pair: tuple[SecretStr, SecretStr] | None) -> tuple[str | None, ...] | None:
    return None if pair is None else tuple(reveal(part) for part in pair)


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize("name", ["knmi", "aemet"])
@pytest.mark.parametrize("padding", _PADDINGS, ids=_PADDING_IDS)
def test_settings_auth_key_is_kept_without_its_padding(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    padding: str,
) -> None:
    """A KNMI or AEMET key is kept without the whitespace around it, as it came from a `.env` value (GH-2557)."""
    padded = f"{padding}DUMMY-KEY{padding}"
    monkeypatch.setenv(f"WD_AUTH__{name.upper()}", padded)
    assert check_settings() == []
    assert reveal(getattr(Settings().auth, name)) == "DUMMY-KEY"
    monkeypatch.delenv(f"WD_AUTH__{name.upper()}")
    assert reveal(getattr(Settings(auth={name: padded}).auth, name)) == "DUMMY-KEY"
    assert reveal(getattr(Settings(auth={name: SecretStr(padded)}).auth, name)) == "DUMMY-KEY"
    settings = Settings()
    setattr(settings.auth, name, padded)
    assert reveal(getattr(settings.auth, name)) == "DUMMY-KEY"


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize("name", ["knmi", "aemet"])
@pytest.mark.parametrize("value", ["", "   ", "\n", "\t \r\n", "\xa0", "\x1f"])
def test_settings_auth_key_of_whitespace_only_reads_as_unset(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
) -> None:
    """A KNMI or AEMET key of nothing but whitespace is unset, as an empty value is (GH-2557)."""
    monkeypatch.setenv(f"WD_AUTH__{name.upper()}", value)
    assert check_settings() == []
    assert getattr(Settings().auth, name) is None
    monkeypatch.delenv(f"WD_AUTH__{name.upper()}")
    assert getattr(Settings(auth={name: value}).auth, name) is None
    assert getattr(Settings(auth={name: SecretStr(value)}).auth, name) is None
    settings = Settings()
    setattr(settings.auth, name, value)
    assert getattr(settings.auth, name) is None


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize("name", ["knmi", "aemet"])
def test_settings_auth_key_still_refuses_a_padded_mask(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    """A mask with whitespace around it is still the mask a dumped credential leaves behind (GH-2557)."""
    monkeypatch.setenv(f"WD_AUTH__{name.upper()}", f"{'*' * 10}\n")
    assert len(check_settings()) == 1
    with pytest.raises(ValidationError, match="mask a dumped credential"):
        Settings(auth={name: f" {'*' * 10} "})


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize("padding", _PADDINGS, ids=_PADDING_IDS)
def test_settings_auth_ceda_is_kept_without_the_padding_of_either_half(
    monkeypatch: pytest.MonkeyPatch,
    padding: str,
) -> None:
    """A CEDA username and password are each kept without their padding, in text and in a pair (GH-2557)."""
    text = f"{padding}DUMMY-USER{padding}:{padding}DUMMY:PASSWORD{padding}"
    padded_pair = [f"{padding}DUMMY-USER{padding}", f"{padding}DUMMY:PASSWORD{padding}"]
    expected = ("DUMMY-USER", "DUMMY:PASSWORD")
    monkeypatch.setenv("WD_AUTH__CEDA", text)
    assert check_settings() == []
    assert _revealed_pair(Settings().auth.ceda) == expected
    monkeypatch.setenv("WD_AUTH__CEDA", json.dumps(padded_pair))
    assert _revealed_pair(Settings().auth.ceda) == expected
    monkeypatch.delenv("WD_AUTH__CEDA")
    for given in (text, SecretStr(text), tuple(padded_pair), [SecretStr(part) for part in padded_pair]):
        assert _revealed_pair(Settings(auth={"ceda": given}).auth.ceda) == expected
    settings = Settings()
    settings.auth.ceda = text
    assert _revealed_pair(settings.auth.ceda) == expected


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize(
    "value",
    ["   ", "\n", ":secret", "  :secret", "\n:secret\n", '["", "secret"]', '[" ", "secret"]'],
)
def test_settings_auth_ceda_reads_a_blank_username_as_unset(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    """CEDA text of nothing but whitespace, or a pair whose username is blank, is unset (GH-2557)."""
    monkeypatch.setenv("WD_AUTH__CEDA", value)
    assert check_settings() == []
    assert Settings().auth.ceda is None
    monkeypatch.delenv("WD_AUTH__CEDA")
    assert Settings(auth={"ceda": value}).auth.ceda is None
    assert Settings(auth={"ceda": SecretStr(value)}).auth.ceda is None
    assert Settings(auth={"ceda": ("", "secret")}).auth.ceda is None
    assert Settings(auth={"ceda": (" \n", "secret")}).auth.ceda is None


@pytest.mark.usefixtures("_no_ambient_settings")
def test_settings_auth_ceda_keeps_a_blank_password(monkeypatch: pytest.MonkeyPatch) -> None:
    """A blank password is still a password, as it was: only a blank username reads as unset (GH-2557)."""
    monkeypatch.setenv("WD_AUTH__CEDA", "DUMMY-USER: \n")
    assert _revealed_pair(Settings().auth.ceda) == ("DUMMY-USER", "")


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize("padding", _PADDINGS, ids=_PADDING_IDS)
def test_settings_auth_metno_frost_pair_is_kept_without_the_padding_of_its_elements(
    monkeypatch: pytest.MonkeyPatch,
    padding: str,
) -> None:
    """Each element of a Frost pair is kept without its padding, as a lone client id is (GH-2557)."""
    client_id = "8e1b6a2c-3f4d-4c5e-9a7b-0d1e2f3a4b5c"
    expected = (client_id, "DUMMY-SECRET")
    padded_id, padded_secret = f"{padding}{client_id}{padding}", f"{padding}DUMMY-SECRET{padding}"
    monkeypatch.setenv("WD_AUTH__METNO_FROST", json.dumps([padded_id, padded_secret]))
    assert check_settings() == []
    assert _revealed_pair(Settings().auth.metno_frost) == expected
    monkeypatch.delenv("WD_AUTH__METNO_FROST")
    for given in (
        (padded_id, padded_secret),
        [SecretStr(padded_id), SecretStr(padded_secret)],
        json.dumps([padded_id, padded_secret]),
    ):
        assert _revealed_pair(Settings(auth={"metno_frost": given}).auth.metno_frost) == expected
    assert _revealed_pair(Settings(auth={"metno_frost": (padded_id, None)}).auth.metno_frost) == (client_id, "")
    settings = Settings()
    settings.auth.metno_frost = (padded_id, padded_secret)
    assert _revealed_pair(settings.auth.metno_frost) == expected


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize(
    "given",
    [
        ("", ""),
        ("", None),
        (" ", "secret"),
        ("\n", "secret"),
        (SecretStr(" "), SecretStr("secret")),
        '["", ""]',
        '[" ", ""]',
        '["\\n", "secret"]',
    ],
)
def test_settings_auth_metno_frost_reads_a_pair_with_a_blank_client_id_as_unset(
    monkeypatch: pytest.MonkeyPatch,
    given: object,
) -> None:
    """A Frost pair with a blank client id is unset, as a lone blank one is, not empty Basic auth (GH-2557)."""
    assert Settings(auth={"metno_frost": given}).auth.metno_frost is None
    settings = Settings()
    settings.auth.metno_frost = given
    assert settings.auth.metno_frost is None
    if isinstance(given, str):
        monkeypatch.setenv("WD_AUTH__METNO_FROST", given)
        assert check_settings() == []
        assert Settings().auth.metno_frost is None


@pytest.mark.usefixtures("_no_ambient_settings")
def test_settings_auth_metno_frost_pair_still_refuses_a_null_client_id() -> None:
    """A client id that is no text at all is refused as it was, not read as a blank one (GH-2557)."""
    with pytest.raises(ValidationError, match="metno_frost"):
        Settings(auth={"metno_frost": (None, "secret")})


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize("name", ["knmi", "aemet"])
def test_settings_auth_key_still_refuses_what_is_not_text(name: str) -> None:
    """A KNMI or AEMET key that is no text is left for the field to refuse, not read as its digits (GH-2557)."""
    with pytest.raises(ValidationError, match=name):
        Settings(auth={name: 12345})


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize(
    ("name", "given"),
    [
        pytest.param("ceda", ("", None), id="ceda-none-password"),
        pytest.param("ceda", (" ", 1.5), id="ceda-float-password"),
        pytest.param("ceda", ("", "*" * 10), id="ceda-mask-password"),
        pytest.param("ceda", f" :{'*' * 10}", id="ceda-text-mask-password"),
        pytest.param("ceda", '[" ", 1.5]', id="ceda-json-float-password"),
        pytest.param("metno_frost", ("", {"a": 1}), id="frost-object-secret"),
        pytest.param("metno_frost", ("", ["x"]), id="frost-list-secret"),
        pytest.param("metno_frost", ("", "*" * 10), id="frost-mask-secret"),
    ],
)
def test_settings_auth_pair_with_a_blank_first_element_still_refuses_its_second(name: str, given: object) -> None:
    """A pair reads as unset for a blank username or client id only where the rest of it is valid (GH-2557)."""
    with pytest.raises(ValidationError, match=name):
        Settings(auth={name: given})


_CLIENT_KWARGS_WITH_CREDENTIALS = {
    "proxy": "http://proxy-user:PROXY-SECRET@proxy.example:3128",
    "headers": {"Authorization": "Bearer HEADER-SECRET", "X-Auth-Token": "TOKEN-SECRET", "User-Agent": "mine/1"},
    "proxy_headers": {"Proxy-Authorization": "Basic PROXY-HEADER-SECRET"},
    "timeout": 12,
}
_CLIENT_KWARGS_SECRETS = ["PROXY-SECRET", "HEADER-SECRET", "TOKEN-SECRET", "PROXY-HEADER-SECRET"]


@pytest.mark.usefixtures("_no_ambient_settings")
def test_settings_render_without_the_credentials_in_their_client_kwargs() -> None:
    """A proxy's password and a request header's value are not printed with the settings (GH-2593).

    `WD_FSSPEC_CLIENT_KWARGS` goes to aiohttp as it is, so it holds whatever the operator needs to
    reach upstream: a proxy URL with its userinfo, or an `Authorization` header. What stays is what
    says how the client was configured -- the names of the keys and headers, the timeout.
    """
    settings = Settings(fsspec_client_kwargs=_CLIENT_KWARGS_WITH_CREDENTIALS)

    for rendered in (repr(settings), str(settings), f"{settings}"):
        assert [secret for secret in _CLIENT_KWARGS_SECRETS if secret in rendered] == []
        assert "proxy-user" not in rendered
        assert "proxy.example" not in rendered
        assert "X-Auth-Token" in rendered
        assert "mine/1" in rendered
    assert json.loads(repr(settings))["fsspec_client_kwargs"]["timeout"] == 12
    # what the settings are used from is not touched: only the rendering is
    assert settings.fsspec_client_kwargs["proxy"] == _CLIENT_KWARGS_WITH_CREDENTIALS["proxy"]
    assert settings.model_dump()["fsspec_client_kwargs"]["headers"]["Authorization"] == "Bearer HEADER-SECRET"


@pytest.mark.usefixtures("_no_ambient_settings")
def test_settings_render_hides_headers_given_as_a_list_of_pairs() -> None:
    """Headers aiohttp takes as a list of pairs are masked as a dict of them is (GH-2593)."""
    settings = Settings(fsspec_client_kwargs={"headers": [("Authorization", "Bearer HEADER-SECRET")]})

    assert "HEADER-SECRET" not in repr(settings) + str(settings)


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize("by_keyword", [False, True], ids=["positional", "keyword"])
def test_a_retried_listing_does_not_log_the_credentials_in_the_settings(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    *,
    by_keyword: bool,
) -> None:
    """Stamina's retry log, which renders the arguments of the call it retries, holds no password (GH-2593).

    `list_remote_files_fsspec` and `list_remote_directory_fsspec` take the settings, so a listing
    that fails for any reason logs them at WARNING on its first retry. The failure here is a plain
    `OSError`, which names no proxy, so the settings are the only place the password could come from.
    """
    import stamina  # noqa: PLC0415

    from wetterdienst.util.network import (  # noqa: PLC0415
        HTTPFileSystem,
        list_remote_directory_fsspec,
        list_remote_files_fsspec,
    )

    def fail(_self: object, _url: str, **_kwargs: object) -> list:
        msg = "boom"
        raise OSError(msg)

    monkeypatch.setattr(HTTPFileSystem, "find", fail)
    monkeypatch.setattr(HTTPFileSystem, "ls", fail)
    settings = Settings(cache_dir=tmp_path, fsspec_client_kwargs=_CLIENT_KWARGS_WITH_CREDENTIALS)

    for listing in (list_remote_files_fsspec, list_remote_directory_fsspec):
        caplog.clear()
        call = (
            functools.partial(listing, "https://example.com/dir/", settings=settings)
            if by_keyword
            else functools.partial(listing, "https://example.com/dir/", settings)
        )
        with (
            stamina.set_testing(True, attempts=2),
            caplog.at_level(logging.DEBUG, logger="stamina"),
            pytest.raises(OSError, match="boom"),
        ):
            call()

        assert caplog.records, "stamina logged nothing, so this test would pass for the wrong reason"
        for record in caplog.records:
            # the message and everything stamina attaches to the record, as a formatter might render it
            carried = record.getMessage() + "".join(str(value) for value in record.__dict__.values())
            assert [secret for secret in _CLIENT_KWARGS_SECRETS if secret in carried] == []


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize(
    "client_kwargs",
    [
        pytest.param({"proxy": "user:QSECRET@proxy.example:3128"}, id="proxy-without-scheme"),
        pytest.param({"proxy": "http://proxy.example:3128/p?token=QSECRET"}, id="proxy-query"),
        pytest.param({"proxy": "http://user:pa/QSECRET@proxy.example:3128"}, id="proxy-slash-in-password"),
        pytest.param({"proxy": "http://user:QSECRET"}, id="proxy-without-host"),
        pytest.param({"proxy": "http://[::1:QSECRET"}, id="proxy-unparsable"),
        pytest.param({"headers": {"X-Api-Key": 123456789}}, id="number-in-headers"),
        pytest.param({"cookies": {"session": 123456789}}, id="number-in-cookies"),
        pytest.param({"cookies": {"user-agent": "QSECRET"}}, id="user-agent-in-cookies"),
        pytest.param({"proxy_headers": {"User-Agent": "QSECRET"}}, id="user-agent-in-proxy-headers"),
        pytest.param({"proxy_auth": ["user", "QSECRET"]}, id="proxy-auth-pair"),
        pytest.param({"headers": [["X-Token", "QSECRET"]]}, id="headers-as-pairs"),
    ],
)
def test_settings_render_masks_what_is_not_a_known_safe_value(client_kwargs: dict) -> None:
    """Everything but the timeout, the User-Agent header, booleans and key names is masked (GH-2593).

    A URL is masked whole, since cutting the userinfo from one takes a parser that agrees with the
    client's; the User-Agent is exempt as a header only; and aiohttp sends a number in a header or a
    cookie as its text, so a number is safe only as the timeout.
    """
    rendered = repr(Settings(fsspec_client_kwargs={**client_kwargs, "timeout": 7}))

    assert "QSECRET" not in rendered
    assert "123456789" not in rendered
    assert json.loads(rendered)["fsspec_client_kwargs"]["timeout"] == 7
