# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.#
"""Tests for settings."""

import copy
import logging
import os
import re
from pathlib import Path
from unittest import mock

import pytest
from multidict import CIMultiDict
from pydantic import SecretStr, ValidationError

from wetterdienst.metadata.resolution import Resolution
from wetterdienst.settings import _STATION_DISTANCE_RESOLUTION_FACTORS, Settings, check_settings, reveal

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

    `TimeseriesRequest` runs `Settings.model_validate(settings)` on what it is handed, which re-runs
    every after-validator on the same instance. Capturing the overrides again there would take the
    already-expanded mapping for what the user wrote, and those 34 entries would then outrank a
    radius set afterwards.
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
