# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the options of a request."""

import logging
import os
from dataclasses import dataclass
from pathlib import Path

import pytest
from pydantic import ValidationError
from pydantic_settings import SettingsError

import wetterdienst
from wetterdienst import Options
from wetterdienst.metadata.parameter_table import PARAMETERS
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.options import _STATION_DISTANCE_RESOLUTION_FACTORS
from wetterdienst.settings import Settings, _describe_settings_error, check_settings


@dataclass(frozen=True)
class Case:
    """One option: its default, a value for the environment, values that are out of bounds."""

    name: str
    default: object
    env: str
    parsed: object
    bad: list[object]
    bad_env: str

    @property
    def variable(self) -> str:
        """Return the environment variable that sets it."""
        return f"WD_TS_{self.name.upper()}"

    def __repr__(self) -> str:
        """Name the case for the test id."""
        return self.name


#: what an option is dumped as: the per-parameter radii as the overrides that were given
CASES = [
    Case("humanize", default=True, env="false", parsed=False, bad=["maybe"], bad_env="maybe"),
    Case("shape", "long", "wide", "wide", ["tall"], "tall"),
    Case("convert_units", default=True, env="false", parsed=False, bad=["maybe"], bad_env="maybe"),
    Case(
        "unit_targets",
        {},
        '{"temperature":"degree_fahrenheit"}',
        {"temperature": "degree_fahrenheit"},
        [{"foo": "bar"}, 5],
        '{"foo":"bar"}',
    ),
    Case("skip_empty", default=False, env="true", parsed=True, bad=["maybe"], bad_env="maybe"),
    Case("skip_threshold", 0.95, "0.5", 0.5, [0, -0.5, 1.01], "5"),
    Case("skip_criteria", "min", "max", "max", ["median"], "median"),
    Case("drop_nulls", default=True, env="false", parsed=False, bad=["maybe"], bad_env="maybe"),
    Case("geo_station_distance_homogeneous", 40.0, "50", 50.0, [-1], "-1"),
    Case("geo_station_distance_heterogeneous", 20.0, "30", 30.0, [-1], "-1"),
    Case(
        "geo_station_distance",
        {},
        '{"precipitation_amount":25}',
        {"precipitation_amount": 25.0},
        [{"nonsense": 1}, {"precipitation_amount": -1}, {"default": 1}, 5],
        '{"nonsense":1}',
    ),
    Case(
        "geo_station_distance_resolution_factors",
        {},
        '{"daily":3.0}',
        {"daily": 3.0},
        [{"fortnightly": 1.0}, {"daily": -1.0}, 5],
        '{"fortnightly":1.0}',
    ),
    Case("geo_use_nearby_station_distance", 1.0, "0.5", 0.5, [-1], "-1"),
    Case("geo_min_gain_of_value_pairs", 0.1, "0.2", 0.2, [-0.1], "-0.1"),
    Case("geo_num_additional_stations", 3, "5", 5, [-1], "-1"),
]
CASE_IDS = [case.name for case in CASES]
#: the options a mapping is merged into from the environment, so a given value does not replace it
MAPPINGS = {"unit_targets", "geo_station_distance", "geo_station_distance_resolution_factors"}


@pytest.fixture(autouse=True)
def _no_ambient_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep the WD_* variables and the `.env` of whoever runs the tests out of the options."""
    for name in list(os.environ):
        if name.startswith("WD_"):
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


def _dump_settings(settings: Settings) -> dict[str, object]:
    """Return the settings' request options as `Options` dumps them, by the name without ``ts_``."""
    return {name.removeprefix("ts_"): value for name, value in settings.model_dump().items() if name.startswith("ts_")}


def test_options_are_exported() -> None:
    """`Options` is part of the package's public names."""
    assert wetterdienst.Options is Options
    assert "Options" in wetterdienst.__all__


def test_options_cover_the_request_half_of_the_settings() -> None:
    """Every `ts_*` setting has an option of the same name without the prefix, and nothing else does."""
    settings_ts = {name.removeprefix("ts_") for name in Settings.model_fields if name.startswith("ts_")}
    assert set(Options.model_fields) == settings_ts == set(CASE_IDS)


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_options_default(case: Case) -> None:
    """Each option has its default, which is the one the setting has."""
    assert Options().model_dump()[case.name] == case.default
    assert _dump_settings(Settings())[case.name] == case.default


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_options_read_the_environment(case: Case, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each option is read from ``WD_TS_<NAME>``, the variable the setting is read from."""
    monkeypatch.setenv(case.variable, case.env)
    assert Options().model_dump()[case.name] == case.parsed


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_options_read_dotenv(case: Case, tmp_path: Path) -> None:
    """Each option is read from the same variable in a ``.env``, which holds other keys as well."""
    (tmp_path / ".env").write_text(f"WD_CACHE_DISABLE=true\nOTHER_SECRET=secret-ish\n{case.variable}={case.env}\n")
    assert Options().model_dump()[case.name] == case.parsed


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_options_take_a_constructor_argument(case: Case) -> None:
    """Each option is given as its name, without a prefix."""
    assert Options(**{case.name: case.parsed}).model_dump()[case.name] == case.parsed


@pytest.mark.parametrize("case", [case for case in CASES if case.name not in MAPPINGS], ids=lambda case: case.name)
def test_options_argument_wins_over_the_environment(case: Case, monkeypatch: pytest.MonkeyPatch) -> None:
    """A value given outranks the environment, as for the settings."""
    monkeypatch.setenv(case.variable, case.env)
    assert Options(**{case.name: case.default}).model_dump()[case.name] == case.default


def test_options_argument_is_merged_into_a_mapping_from_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """A mapping given and one in the environment are merged key by key, as the settings merge them."""
    monkeypatch.setenv("WD_TS_GEO_STATION_DISTANCE", '{"precipitation_amount":25}')
    options = Options(geo_station_distance={"wind_speed": 43})
    assert options.geo_station_distance["precipitation_amount"] == 25.0
    assert options.geo_station_distance["wind_speed"] == 43.0


# old route, removed in stage 5 (the ts_* lines only; the rest of the test stays)
def test_options_read_a_nested_environment_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """An entry of a mapping is set by ``__`` and its key."""
    monkeypatch.setenv("WD_TS_GEO_STATION_DISTANCE__PRECIPITATION_AMOUNT", "25")
    assert Options().geo_station_distance["precipitation_amount"] == 25.0
    assert Settings().ts_geo_station_distance["precipitation_amount"] == 25.0


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_options_refuse_a_value_out_of_bounds(case: Case, monkeypatch: pytest.MonkeyPatch) -> None:
    """A value out of bounds or outside its choices is refused, by the option's name, from the constructor and from the environment."""  # noqa: E501
    for bad in case.bad:
        with pytest.raises(ValidationError, match=case.name):
            Options(**{case.name: bad})
    monkeypatch.setenv(case.variable, case.bad_env)
    with pytest.raises(ValidationError, match=case.name):
        Options()


def test_options_refuse_an_option_that_does_not_exist() -> None:
    """A misspelt name is refused, not dropped."""
    with pytest.raises(ValidationError, match="shpae"):
        Options(shpae="wide")
    with pytest.raises(ValidationError, match="ts_shape"):
        Options(ts_shape="wide")


def test_options_do_not_repeat_a_value_they_refuse() -> None:
    """The error names the option but does not echo what it was given (GH-2435)."""
    with pytest.raises(ValidationError) as error:
        Options(unit_targets={"foo": "secret-ish"})
    assert "secret-ish" not in str(error.value)
    with pytest.raises(ValidationError) as error:
        Options(shape="secret-ish")
    assert "secret-ish" not in str(error.value)


def test_options_are_frozen() -> None:
    """An option cannot be assigned after construction."""
    options = Options()
    with pytest.raises(ValidationError, match="frozen"):
        options.shape = "wide"
    with pytest.raises(ValidationError, match="frozen"):
        options.geo_station_distance = {}
    assert options.shape == "long"


def test_options_replace_makes_a_changed_copy() -> None:
    """`replace` leaves the original as it was and changes only what it is told."""
    options = Options(skip_empty=True, geo_station_distance={"wind_speed": 43})
    changed = options.replace(shape="wide", skip_threshold=0.5)
    assert changed is not options
    assert (options.shape, options.skip_threshold) == ("long", 0.95)
    assert (changed.shape, changed.skip_threshold) == ("wide", 0.5)
    assert changed.skip_empty
    assert changed.geo_station_distance["wind_speed"] == 43.0
    assert options.replace() is options


def test_options_replace_validates_the_copy() -> None:
    """A change is checked as a new instance is checked."""
    options = Options()
    with pytest.raises(ValidationError, match="skip_threshold"):
        options.replace(skip_threshold=2)
    with pytest.raises(ValidationError, match="shape"):
        options.replace(shape="tall")
    with pytest.raises(ValidationError, match="geo_station_distance"):
        options.replace(geo_station_distance={"nonsense": 1})
    with pytest.raises(ValidationError, match="shpae"):
        options.replace(shpae="wide")
    assert options.shape == "long"


def test_options_replace_reads_neither_the_environment_nor_dotenv(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A copy is made of the options alone: what the environment says now is not laid over them."""
    options = Options(shape="long", unit_targets={})
    monkeypatch.setenv("WD_TS_SHAPE", "wide")
    monkeypatch.setenv("WD_TS_GEO_STATION_DISTANCE", '{"precipitation_amount":25}')
    monkeypatch.setenv("WD_TS_UNIT_TARGETS", '{"temperature":"degree_fahrenheit"}')
    (tmp_path / ".env").write_text("WD_TS_HUMANIZE=false\n")
    changed = options.replace(skip_empty=True)
    assert changed.shape == "long"
    assert changed.humanize
    assert changed.unit_targets == {}
    assert changed.model_dump()["geo_station_distance"] == {}
    # a mapping can be taken away, which an environment merged into it would not allow
    assert Options().replace(geo_station_distance={}).model_dump()["geo_station_distance"] == {}
    # and a new instance still reads it
    assert Options().shape == "wide"


def test_options_replace_does_not_leave_the_environment_unread(monkeypatch: pytest.MonkeyPatch) -> None:
    """After a copy was made, a new instance reads the environment again."""
    Options().replace(shape="wide")
    monkeypatch.setenv("WD_TS_SHAPE", "wide")
    assert Options().shape == "wide"


def test_options_replace_keeps_the_per_parameter_radii_as_given() -> None:
    """A radius changed with `replace` reaches the parameters that took it from the table."""
    options = Options(geo_station_distance={"wind_speed": 43})
    changed = options.replace(geo_station_distance_heterogeneous=5.0)
    assert changed.geo_station_distance["precipitation_amount"] == 5.0
    assert changed.geo_station_distance["wind_speed"] == 43.0
    assert changed.model_dump()["geo_station_distance"] == {"wind_speed": 43.0}


def test_options_geo_station_distance_round_trips() -> None:
    """A dump builds the same options again, the overrides alone being dumped for the mapping."""
    options = Options(geo_station_distance_heterogeneous=5.0, geo_station_distance={"wind_speed": 43})
    dump = options.model_dump()
    assert dump["geo_station_distance"] == {"wind_speed": 43.0}
    again = Options(**dump)
    assert again == options
    assert again.model_dump() == dump
    # the radius set alongside still moves what the table says
    assert again.geo_station_distance["precipitation_amount"] == 5.0
    assert Options.model_validate(dump) == options
    assert Options.model_validate_json(options.model_dump_json()) == options


def test_options_geo_station_distance_is_the_expansion_of_the_radii() -> None:
    """The mapping holds the two radii, the table and the overrides; the default answers for the rest."""
    options = Options(geo_station_distance_homogeneous=50.0, geo_station_distance_heterogeneous=30.0)
    assert options.geo_station_distance["precipitation_amount"] == 30.0
    assert options.geo_station_distance["temperature_air_mean_2m"] == 50.0
    assert Options().geo_station_distance["humidity_relative"] == 40.0
    assert Options().geo_station_distance["snow_depth_new"] == 20.0


def test_options_geo_station_distance_for_follows_resolution() -> None:
    """The radius of a heterogeneous parameter scales by resolution, one set by hand or a homogeneous one does not."""
    options = Options(geo_station_distance={"wind_speed": 43})
    assert options.geo_station_distance_for("precipitation_amount", "hourly") == 20.0
    assert options.geo_station_distance_for("precipitation_amount", "daily") == 40.0
    assert options.geo_station_distance_for("precipitation_amount", Resolution.MINUTE_10.value) == 15.0
    assert options.geo_station_distance_for("temperature_air_mean_2m", "daily") == 40.0
    assert options.geo_station_distance_for("wind_speed", "daily") == 43.0
    assert options.geo_station_distance_for("unknown_parameter", "daily") == 40.0
    assert options.geo_station_distance_for("precipitation_amount", "not_a_resolution") == 20.0
    factors = Options(geo_station_distance_resolution_factors={"daily": 3.0})
    assert factors.geo_station_distance_resolution_factor("daily") == 3.0
    assert factors.geo_station_distance_resolution_factor("hourly") == 1.0
    assert factors.geo_station_distance_for("precipitation_amount", "daily") == 60.0


@pytest.mark.parametrize(("shape", "tidy"), [("long", True), ("wide", False)])
@pytest.mark.parametrize("drop_nulls", [True, False])
def test_options_derived_members(shape: str, tidy: bool, drop_nulls: bool) -> None:  # noqa: FBT001
    """`tidy` is the long shape, and nulls are dropped in it alone, whatever `drop_nulls` keeps."""
    options = Options(shape=shape, drop_nulls=drop_nulls)
    assert options.tidy is tidy
    assert options.drop_nulls_effective is (drop_nulls and tidy)
    assert options.drop_nulls is drop_nulls


def test_options_log_the_ignored_drop_nulls_once(caplog: pytest.LogCaptureFixture) -> None:
    """A wide shape says so once as the options are built, and not again for a copy."""
    with caplog.at_level(logging.INFO, logger="wetterdienst.options"):
        options = Options(shape="wide")
        options.replace(skip_empty=True)
        options.replace(shape="long").replace(shape="wide")
        Options(shape="long")
    messages = [record.getMessage() for record in caplog.records if record.name == "wetterdienst.options"]
    assert messages == [
        "option 'drop_nulls' is only available with option 'shape=long' and is thus ignored in this request."
    ]


def test_options_warn_about_a_radius_for_a_parameter_never_interpolated(caplog: pytest.LogCaptureFixture) -> None:
    """A radius for a parameter that is never interpolated is allowed, and said to be ignored."""
    never = next(name for name, parameter in PARAMETERS.items() if not parameter.interpolation)
    with caplog.at_level(logging.WARNING, logger="wetterdienst.options"):
        Options(geo_station_distance={never: 10})
    messages = [record.getMessage() for record in caplog.records if record.name == "wetterdienst.options"]
    assert messages == [
        (
            f"option 'geo_station_distance' sets a radius for ['{never}'], which are never interpolated, "
            "and is thus ignored for them in this request."
        )
    ]


def test_options_repr_shows_what_was_given_for_the_radii() -> None:
    """The repr is short: the overrides, not the table they are expanded into."""
    text = repr(Options(geo_station_distance={"wind_speed": 43}))
    assert "geo_station_distance={'wind_speed': 43.0}" in text
    assert "precipitation_amount" not in text
    assert text.startswith("Options(humanize=True, shape='long'")


def test_options_equality_is_by_value() -> None:
    """Options built the same compare equal, and options built differently do not."""
    assert Options() == Options()
    assert Options(shape="wide") != Options()
    assert Options(geo_station_distance={"wind_speed": 43}) != Options()


# parity with the settings they are to replace


# old route, removed in stage 5
def test_options_equal_the_settings_for_every_variable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With every ``WD_TS_*`` variable set, each setting `ts_x` that `Settings` reads equals option `x`."""
    for case in CASES:
        monkeypatch.setenv(case.variable, case.env)
    options = Options().model_dump()
    from_settings = _dump_settings(Settings())
    assert options == from_settings
    assert options == {case.name: case.parsed for case in CASES}


def test_options_equal_the_settings_for_every_variable_in_dotenv(tmp_path: Path) -> None:
    """The same from a ``.env``."""
    (tmp_path / ".env").write_text("".join(f"{case.variable}={case.env}\n" for case in CASES))
    assert Options().model_dump() == _dump_settings(Settings())
    assert Options().model_dump() == {case.name: case.parsed for case in CASES}


# old route, removed in stage 5
@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_options_and_settings_take_and_refuse_the_same_values(case: Case) -> None:
    """A value one takes the other takes, and a value one refuses the other refuses, the dumps being equal."""
    good = Options(**{case.name: case.parsed})
    assert _dump_settings(Settings(**{f"ts_{case.name}": case.parsed})) == good.model_dump()
    for bad in case.bad:
        with pytest.raises(ValidationError):
            Options(**{case.name: bad})
        with pytest.raises(ValidationError):
            Settings(**{f"ts_{case.name}": bad})


# old route, removed in stage 5
def test_options_and_settings_agree_on_the_radius_for_every_parameter_and_resolution() -> None:
    """`geo_station_distance_for` is the same for any combination of radii, factors and overrides."""
    given = {
        "geo_station_distance_homogeneous": 55.0,
        "geo_station_distance_heterogeneous": 12.5,
        "geo_station_distance": {"wind_speed": 43, "precipitation_amount": 7},
        "geo_station_distance_resolution_factors": {"daily": 3.0, Resolution.MINUTE_10.value: 0.5},
    }
    options = Options(**given)
    settings = Settings(**{f"ts_{name}": value for name, value in given.items()})
    assert set(_STATION_DISTANCE_RESOLUTION_FACTORS) == {resolution.value for resolution in Resolution}
    for resolution in [*_STATION_DISTANCE_RESOLUTION_FACTORS, "not_a_resolution"]:
        assert options.geo_station_distance_resolution_factor(resolution) == (
            settings.ts_geo_station_distance_resolution_factor(resolution)
        )
        for parameter in [*PARAMETERS, "unknown_parameter"]:
            assert options.geo_station_distance_for(parameter, resolution) == (
                settings.ts_geo_station_distance_for(parameter, resolution)
            )
    assert dict(options.geo_station_distance) == dict(settings.ts_geo_station_distance)
    assert options.tidy == settings.ts_tidy
    assert options.drop_nulls_effective == settings.ts_drop_nulls_effective


# the check of the environment


def test_check_settings_tells_a_malformed_option_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """A malformed ``WD_TS_*`` variable is told by its name, once, though both classes read it."""
    monkeypatch.setenv("WD_TS_SHAPE", "secret-ish")
    assert check_settings() == ["WD_TS_SHAPE is invalid: Input should be 'wide' or 'long'"]


def test_check_settings_tells_a_malformed_option_that_is_not_json_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """The same for a mapping that does not parse."""
    monkeypatch.setenv("WD_TS_UNIT_TARGETS", "secret-ish")
    assert check_settings() == ["WD_TS_UNIT_TARGETS is invalid: not valid JSON"]


def test_check_settings_tells_a_host_setting_and_an_option_together(monkeypatch: pytest.MonkeyPatch) -> None:
    """A problem of each is told, a line for each."""
    monkeypatch.setenv("WD_CACHE_DISABLE", "secret-ish")
    monkeypatch.setenv("WD_TS_SKIP_THRESHOLD", "5")
    lines = check_settings()
    assert [line.split(" is invalid")[0] for line in lines] == ["WD_CACHE_DISABLE", "WD_TS_SKIP_THRESHOLD"]


def test_check_settings_reads_dotenv_for_the_options(tmp_path: Path) -> None:
    """The check reads a ``.env`` for the options as the options do."""
    assert check_settings() == []
    (tmp_path / ".env").write_text("WD_TS_SKIP_THRESHOLD=secret-ish\n")
    (line,) = check_settings()
    assert line.startswith("WD_TS_SKIP_THRESHOLD is invalid: ")
    assert "secret-ish" not in line


def test_describe_settings_error_names_an_option_by_its_variable() -> None:
    """With the prefix of the options, a field is told as the variable that sets it."""
    with pytest.raises(ValidationError) as error:
        Options(shape="secret-ish", skip_threshold=5)
    assert _describe_settings_error(error.value, "WD_TS_") == [
        "WD_TS_SHAPE is invalid: Input should be 'wide' or 'long'",
        "WD_TS_SKIP_THRESHOLD is invalid: Input should be less than or equal to 1",
    ]
    with pytest.raises(ValidationError) as error:
        Options(geo_station_distance={"nonsense": 1})
    (line,) = _describe_settings_error(error.value, "WD_TS_")
    assert line.startswith("WD_TS_GEO_STATION_DISTANCE is invalid: Invalid parameters in geo_station_distance: ")


def test_check_settings_tells_an_option_that_is_not_told_by_the_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    """An option is checked though `Settings` could not be built, which it stops at before validating anything."""
    monkeypatch.setenv("WD_FSSPEC_CLIENT_KWARGS", "secret-ish")
    monkeypatch.setenv("WD_TS_SHAPE", "tall")
    assert check_settings() == [
        "WD_FSSPEC_CLIENT_KWARGS is invalid: not valid JSON",
        "WD_TS_SHAPE is invalid: Input should be 'wide' or 'long'",
    ]


@pytest.mark.parametrize("from_dotenv", [False, True], ids=["environment", "dotenv"])
def test_options_refuse_a_value_nested_too_deeply_to_decode(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    from_dotenv: bool,
) -> None:
    """A mapping nested too deeply is refused as one that is not JSON, not raised as a `RecursionError` (GH-2543).

    `check_settings()` builds the options after the settings and no longer stops at the settings'
    own refusal of the same variable, so the options must refuse it themselves.
    """
    value = "[" * 30_000 + "TOPSECRET"
    if from_dotenv:
        (tmp_path / ".env").write_text(f"WD_TS_UNIT_TARGETS={value}\n")
    else:
        monkeypatch.setenv("WD_TS_UNIT_TARGETS", value)
    with pytest.raises(SettingsError) as error:
        Options()
    assert "TOPSECRET" not in str(error.value)
    assert check_settings() == ["WD_TS_UNIT_TARGETS is invalid: not valid JSON"]
    # told by the options alone
    assert _describe_settings_error(error.value, "WD_TS_") == ["WD_TS_UNIT_TARGETS is invalid: not valid JSON"]


def test_check_settings_gives_the_notices_of_an_option_once(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The check logs what `Settings` logs for its `ts_*` settings and nothing of its own for the same options."""
    never = next(name for name, parameter in PARAMETERS.items() if not parameter.interpolation)
    monkeypatch.setenv("WD_TS_SHAPE", "wide")
    monkeypatch.setenv("WD_TS_GEO_STATION_DISTANCE", f'{{"{never}": 3}}')
    with caplog.at_level(logging.INFO):
        assert check_settings() == []
    assert not [record for record in caplog.records if record.name == "wetterdienst.options"]
    assert sum("drop_nulls" in record.getMessage() for record in caplog.records) == 1
    assert sum("sets a radius" in record.getMessage() for record in caplog.records) == 1


def test_options_replace_does_not_repeat_the_warning_for_a_radius(caplog: pytest.LogCaptureFixture) -> None:
    """A copy does not warn again about a radius for a parameter that is never interpolated."""
    never = next(name for name, parameter in PARAMETERS.items() if not parameter.interpolation)
    with caplog.at_level(logging.WARNING, logger="wetterdienst.options"):
        options = Options(geo_station_distance={never: 10})
        options.replace(shape="wide").replace(shape="long")
    assert len([record for record in caplog.records if record.name == "wetterdienst.options"]) == 1


# old route, removed in stage 5 (the ts_* lines only; the rest of the test stays)
def test_options_ignore_an_empty_variable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """An empty variable is no value, in the environment as in a ``.env``, as it is for the settings."""
    monkeypatch.setenv("WD_TS_SHAPE", "")
    assert Options().shape == "long"
    assert Settings().ts_shape == "long"
    monkeypatch.delenv("WD_TS_SHAPE")
    (tmp_path / ".env").write_text("WD_TS_SKIP_THRESHOLD=\n")
    assert Options().skip_threshold == 0.95


# old route, removed in stage 5 (the ts_* lines only; the rest of the test stays)
def test_options_and_settings_take_none_where_it_means_unset() -> None:
    """No unit targets and no nearby-station distance can be given as none."""
    assert Options(unit_targets=None).unit_targets == {}
    assert Settings(ts_unit_targets=None).ts_unit_targets == {}
    assert Options(geo_use_nearby_station_distance=None).geo_use_nearby_station_distance is None
    assert Settings(ts_geo_use_nearby_station_distance=None).ts_geo_use_nearby_station_distance is None


def test_options_are_hashable_by_value() -> None:
    """Frozen options can be a key: equal options hash alike, and the mappings they hold do not stand in the way."""
    assert hash(Options()) == hash(Options())
    assert hash(Options(geo_station_distance={"wind_speed": 43})) == hash(
        Options(geo_station_distance={"wind_speed": 43})
    )
    assert len({Options(), Options(), Options(shape="wide")}) == 2
