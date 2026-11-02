# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the options of a request."""

import logging
import os
import re
from dataclasses import dataclass
from pathlib import Path
from unittest import mock

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


#: the modes of the checks, as they are without a setting (GH-3676)
DEFAULT_PLAUSIBILITY = {
    "range": "hard",
    "elevation": "hard",
    "stuck": "soft",
    "consistency": "hard",
    "floor": "hard",
    "limits": "hard",
}

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
    Case("station_window_end_buffer", None, "7", 7, [-1, 3661, 1.5], "-1"),
    Case(
        "plausibility",
        DEFAULT_PLAUSIBILITY,
        '{"range":"soft"}',
        {**DEFAULT_PLAUSIBILITY, "range": "soft"},
        [{"range": "off"}, {"nonsense": "soft"}, 5],
        '{"range":"off"}',
    ),
    Case(
        "limits",
        {},
        '{"temperature_air_mean_2m":[-30,45],"precipitation_amount":[null,200]}',
        {"temperature_air_mean_2m": (-30.0, 45.0), "precipitation_amount": (None, 200.0)},
        [
            {"nonsense": [1, 2]},
            {"temperature_air_mean_2m": [5, 1]},
            {"temperature_air_mean_2m": [None, None]},
            {"temperature_air_mean_2m": [float("nan"), 1]},
            5,
        ],
        '{"nonsense":[1,2]}',
    ),
]
CASE_IDS = [case.name for case in CASES]
#: the options a mapping is merged into from the environment, so a given value does not replace it
MAPPINGS = {
    "unit_targets",
    "geo_station_distance",
    "geo_station_distance_resolution_factors",
    "plausibility",
    "limits",
}


@pytest.fixture(autouse=True)
def _no_ambient_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep the WD_* variables and the `.env` of whoever runs the tests out of the options."""
    for name in list(os.environ):
        if name.startswith("WD_"):
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


def test_options_are_exported() -> None:
    """`Options` is part of the package's public names."""
    assert wetterdienst.Options is Options
    assert "Options" in wetterdienst.__all__


def test_the_cases_cover_every_option() -> None:
    """Each option has a case, and the settings have none of them."""
    assert set(Options.model_fields) == set(CASE_IDS)
    assert not set(Settings.model_fields) & set(Options.model_fields)


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_options_default(case: Case) -> None:
    """Each option has its default."""
    assert Options().model_dump()[case.name] == case.default


@pytest.mark.parametrize("case", CASES, ids=CASE_IDS)
def test_options_read_the_environment(case: Case, monkeypatch: pytest.MonkeyPatch) -> None:
    """Each option is read from ``WD_TS_<NAME>``."""
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


def test_options_read_a_nested_environment_variable(monkeypatch: pytest.MonkeyPatch) -> None:
    """An entry of a mapping is set by ``__`` and its key."""
    monkeypatch.setenv("WD_TS_GEO_STATION_DISTANCE__PRECIPITATION_AMOUNT", "25")
    assert Options().geo_station_distance["precipitation_amount"] == 25.0


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


# the check of the environment


def test_check_settings_tells_a_malformed_option_once(monkeypatch: pytest.MonkeyPatch) -> None:
    """A malformed ``WD_TS_*`` variable is told by its name, once."""
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
    """The check logs the notices of the options once, as building them logs them."""
    never = next(name for name, parameter in PARAMETERS.items() if not parameter.interpolation)
    monkeypatch.setenv("WD_TS_SHAPE", "wide")
    monkeypatch.setenv("WD_TS_GEO_STATION_DISTANCE", f'{{"{never}": 3}}')
    with caplog.at_level(logging.INFO):
        assert check_settings() == []
    assert sum("drop_nulls" in record.getMessage() for record in caplog.records) == 1
    assert sum("sets a radius" in record.getMessage() for record in caplog.records) == 1


def test_options_replace_does_not_repeat_the_warning_for_a_radius(caplog: pytest.LogCaptureFixture) -> None:
    """A copy does not warn again about a radius for a parameter that is never interpolated."""
    never = next(name for name, parameter in PARAMETERS.items() if not parameter.interpolation)
    with caplog.at_level(logging.WARNING, logger="wetterdienst.options"):
        options = Options(geo_station_distance={never: 10})
        options.replace(shape="wide").replace(shape="long")
    assert len([record for record in caplog.records if record.name == "wetterdienst.options"]) == 1


def test_options_ignore_an_empty_variable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """An empty variable is no value, in the environment as in a ``.env``, as it is for the settings."""
    monkeypatch.setenv("WD_TS_SHAPE", "")
    assert Options().shape == "long"
    monkeypatch.delenv("WD_TS_SHAPE")
    (tmp_path / ".env").write_text("WD_TS_SKIP_THRESHOLD=\n")
    assert Options().skip_threshold == 0.95


def test_options_take_none_where_it_means_unset() -> None:
    """No unit targets and no nearby-station distance can be given as none."""
    assert Options(unit_targets=None).unit_targets == {}
    assert Options(geo_use_nearby_station_distance=None).geo_use_nearby_station_distance is None


def test_options_are_hashable_by_value() -> None:
    """Frozen options can be a key: equal options hash alike, and the mappings they hold do not stand in the way."""
    assert hash(Options()) == hash(Options())
    assert hash(Options(geo_station_distance={"wind_speed": 43})) == hash(
        Options(geo_station_distance={"wind_speed": 43})
    )
    assert len({Options(), Options(), Options(shape="wide")}) == 2


# the options one by one, as the settings once held them


def test_options_geo_station_distance_for_scales_with_resolution() -> None:
    """Test that the radius of a heterogeneous parameter follows the accumulation period.

    Precipitation decorrelates over roughly 8 km in ten minutes but tens of kilometres over a day,
    which one fixed radius cannot express: it is too wide at `minute_10` and too tight at `daily`.
    """
    options = Options()
    assert options.geo_station_distance_for("precipitation_amount", "10_minutes") == 15.0
    assert options.geo_station_distance_for("precipitation_amount", "hourly") == 20.0
    assert options.geo_station_distance_for("precipitation_amount", "6_hours") == 30.0
    assert options.geo_station_distance_for("precipitation_amount", "daily") == 40.0
    assert options.geo_station_distance_for("precipitation_amount", "annual") == 40.0
    # a name from outside the resolution vocabulary is left as it is rather than guessed at
    assert options.geo_station_distance_for("precipitation_amount", "every other tuesday") == 20.0


def test_options_geo_station_distance_radii() -> None:
    """Test that the two radii options move every parameter of their kind.

    The radii used to be module constants, so the only way to widen the search was to name every
    parameter individually in `geo_station_distance` -- 514 names to write out for a change that
    is one number.
    """
    options = Options(geo_station_distance_homogeneous=50.0, geo_station_distance_heterogeneous=30.0)
    # heterogeneous, from the parameter table
    assert options.geo_station_distance["precipitation_amount"] == 30.0
    assert options.geo_station_distance["snow_depth_new"] == 30.0
    # homogeneous, from the defaultdict fallback
    assert options.geo_station_distance["temperature_air_mean_2m"] == 50.0
    assert options.geo_station_distance["humidity_relative"] == 50.0


def test_options_geo_station_distance_radii_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the two radii are settable from the environment, next to the per-parameter dict."""
    monkeypatch.setenv("WD_TS_GEO_STATION_DISTANCE_HOMOGENEOUS", "50")
    monkeypatch.setenv("WD_TS_GEO_STATION_DISTANCE_HETEROGENEOUS", "30")
    monkeypatch.setenv("WD_TS_GEO_STATION_DISTANCE", '{"precipitation_amount":25}')
    options = Options()
    assert options.geo_station_distance_homogeneous == 50.0
    assert options.geo_station_distance_heterogeneous == 30.0
    # the per-parameter override wins over the radius of its kind
    assert options.geo_station_distance["precipitation_amount"] == 25.0
    assert options.geo_station_distance["snow_depth_new"] == 30.0
    assert options.geo_station_distance["temperature_air_mean_2m"] == 50.0


def test_options_geo_station_distance_for_stops_widening_past_a_day() -> None:
    """Test that the table stops at twice the base radius rather than following correlation up.

    Past a day what binds is terrain and not correlation -- the interpolation reads UTM x/y and
    never station elevation -- so the widest the defaults reach is the 40 km the homogeneous radius is
    held to, which is why the two meet at `daily`.
    """
    options = Options()
    assert options.geo_station_distance_for("precipitation_amount", "daily") == 40.0
    assert options.geo_station_distance_for("precipitation_amount", "monthly") == 40.0
    assert options.geo_station_distance_for("precipitation_amount", "annual") == 40.0
    assert options.geo_station_distance_for("temperature_air_mean_2m", "daily") == 40.0


def test_options_geo_station_distance_for_scales_the_radius_that_was_set() -> None:
    """Test that the factors multiply whatever base radius the user set, at every resolution.

    A radius raised by hand is followed rather than clipped: the user has made the terrain
    judgement the factors encode, and a setting that silently does nothing is the failure this
    module validates against everywhere else.
    """
    options = Options(geo_station_distance_heterogeneous=30.0)
    assert options.geo_station_distance_for("precipitation_amount", "10_minutes") == 22.5
    assert options.geo_station_distance_for("precipitation_amount", "hourly") == 30.0
    assert options.geo_station_distance_for("precipitation_amount", "daily") == 60.0
    # every step of the setting moves the radius, with no range where it does nothing
    radii = [
        Options(geo_station_distance_heterogeneous=base).geo_station_distance_for(
            "precipitation_amount",
            "daily",
        )
        for base in (20.0, 25.0, 30.0, 35.0)
    ]
    assert radii == [40.0, 50.0, 60.0, 70.0]


def test_options_geo_station_distance_for_leaves_homogeneous_parameters_alone() -> None:
    """Test that the homogeneous radius is the same at every resolution.

    What bounds it is terrain rather than correlation -- daily temperature stays correlated over
    hundreds of kilometres, while `apply_interpolation` works on UTM x/y and never reads station
    elevation -- and terrain does not care how long the quantity was accumulated for.
    """
    options = Options()
    for resolution in ("10_minutes", "hourly", "daily", "annual"):
        assert options.geo_station_distance_for("temperature_air_mean_2m", resolution) == 40.0
    # a name the table does not know falls back the same way the mapping does
    assert options.geo_station_distance_for("not_a_parameter", "daily") == 40.0


def test_options_geo_station_distance_for_takes_an_override_as_written() -> None:
    """Test that a radius set by hand is not scaled.

    A number written out for a parameter means that number; scaling it would answer a question the
    user did not ask, and there would be no way to ask for a fixed radius at all.
    """
    options = Options(geo_station_distance={"precipitation_amount": 25.0})
    assert options.geo_station_distance_for("precipitation_amount", "10_minutes") == 25.0
    assert options.geo_station_distance_for("precipitation_amount", "daily") == 25.0
    # the parameters that were not named still scale
    assert options.geo_station_distance_for("snow_depth_new", "daily") == 40.0


def test_options_geo_station_distance_resolution_factors() -> None:
    """Test that the factors are settable, and that the ones left out keep their default."""
    options = Options(geo_station_distance_resolution_factors={"daily": 3.0})
    assert options.geo_station_distance_for("precipitation_amount", "daily") == 60.0
    assert options.geo_station_distance_for("precipitation_amount", "10_minutes") == 15.0
    # flattening every factor turns the scaling off
    flat = Options(
        geo_station_distance_resolution_factors=dict.fromkeys(
            (
                "1_minute",
                "5_minutes",
                "6_minutes",
                "10_minutes",
                "15_minutes",
                "hourly",
                "6_hours",
                "subdaily",
                "daily",
                "monthly",
                "annual",
            ),
            1.0,
        ),
    )
    for resolution in ("10_minutes", "hourly", "daily", "annual"):
        assert flat.geo_station_distance_for("precipitation_amount", resolution) == 20.0


def test_options_geo_station_distance_resolution_factors_from_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that the factors are settable from the environment, like the radii next to them."""
    monkeypatch.setenv("WD_TS_GEO_STATION_DISTANCE_RESOLUTION_FACTORS", '{"daily":3.0}')
    options = Options()
    assert options.geo_station_distance_resolution_factor("daily") == 3.0
    assert options.geo_station_distance_for("precipitation_amount", "daily") == 60.0


def test_options_geo_station_distance_resolution_factors_reject_unknown_resolution() -> None:
    """Test that a resolution that does not exist is rejected rather than silently ignored."""
    with pytest.raises(ValidationError, match=r"\['dayly'\] not in"):
        Options(geo_station_distance_resolution_factors={"dayly": 2.0})


def test_options_geo_station_distance_resolution_factors_reject_negative() -> None:
    """Test that a negative factor is rejected, as a negative radius is."""
    with pytest.raises(ValidationError, match="Negative factors in geo_station_distance_resolution_factors"):
        Options(geo_station_distance_resolution_factors={"daily": -1.0})


def test_options_geo_station_distance_rejects_unknown_parameter() -> None:
    """Test that a parameter name that is not canonical is rejected rather than silently ignored."""
    with pytest.raises(ValidationError, match=r"\['precipitation_heigt'\] not in the canonical parameters"):
        Options(geo_station_distance={"precipitation_heigt": 25.0})


def test_options_geo_station_distance_names_a_renamed_parameter() -> None:
    """A key renamed for 1.0 is refused with the name it has now (GH-2036)."""
    with pytest.raises(ValidationError, match=r"'humidity' is now 'humidity_relative'"):
        Options(geo_station_distance={"humidity": 25.0})


def test_options_geo_station_distance_rejects_default_key() -> None:
    """Test that the retired "default" key names its replacements instead of quietly taking effect.

    It used to rebuild the mapping around the given number, which threw away the shorter radius of
    every heterogeneous parameter along with the fallback -- `{"default": 30}` gave precipitation
    30 km too.
    """
    with pytest.raises(ValidationError, match="the 'default' key of geo_station_distance is gone"):
        Options(geo_station_distance={"default": 30.0})


def test_options_geo_station_distance_rejects_negative() -> None:
    """Test that a negative radius is rejected, as it is for `geo_use_nearby_station_distance`."""
    with pytest.raises(
        ValidationError, match=r"Negative distances in geo_station_distance: \['precipitation_amount'\]"
    ):
        Options(geo_station_distance={"precipitation_amount": -5.0})


def test_options_env_nested_delimiter(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that WD_ env vars with __ delimiter set individual keys in dict fields."""
    monkeypatch.setenv("WD_TS_UNIT_TARGETS__temperature", "degree_fahrenheit")
    options = Options()
    assert options.unit_targets["temperature"] == "degree_fahrenheit"


def test_options_skip_empty_stands_on_its_own() -> None:
    """Test that skip_empty survives a request that sets nothing else.

    It used to be switched off unless `ts_complete` was on, and neither the CLI nor the REST API
    ever set that -- so `--skip_empty`, `--skip_threshold` and `--skip_criteria`, and the three
    REST parameters of the same names, were discarded on every request that passed them.
    """
    # the options the CLI and the REST API build a values request from, skip options included
    options = Options(
        humanize=True,
        shape="long",
        convert_units=True,
        unit_targets={},
        skip_empty=True,
        skip_criteria="mean",
        skip_threshold=0.9,
        drop_nulls=True,
    )

    assert options.skip_empty
    assert options.skip_criteria == "mean"
    assert options.skip_threshold == 0.9


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
def test_options_unit_targets_refuse_a_unit_the_converter_cannot_report_in(
    monkeypatch: pytest.MonkeyPatch,
    unit_targets: dict[str, str],
    message: str,
) -> None:
    """A unit target is refused for its unit too, not only its quantity (GH-2306).

    It used to pass here and be refused only once a values request had fetched its stations.
    """
    monkeypatch.delenv("WD_TS_UNIT_TARGETS", raising=False)
    with pytest.raises(ValidationError, match=re.escape(message)):
        Options(unit_targets=unit_targets)


def test_options_unit_targets_name_only_the_unknown_quantities(monkeypatch: pytest.MonkeyPatch) -> None:
    """The refusal names the unknown quantities, sorted, rather than every one given (GH-2306)."""
    monkeypatch.delenv("WD_TS_UNIT_TARGETS", raising=False)
    with pytest.raises(ValidationError) as excinfo:
        Options(unit_targets={"temperature": "degree_fahrenheit", "foo": "bar", "abc": "x"})
    # the message alone, without pydantic's echo of the input after it
    message = str(excinfo.value).split(" [type=")[0]
    assert "Invalid unit targets: quantities not supported: abc, foo. Supported quantities are: angle, " in message
    assert "temperature" in message  # in the sorted list of supported ones
    assert "'temperature'" not in message


def test_options_skip_threshold_takes_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """The upper bound is in the range: 1 asks for every reading (GH-2334)."""
    monkeypatch.setenv("WD_TS_SKIP_THRESHOLD", "1")
    assert Options().skip_threshold == 1


@pytest.mark.parametrize("field", ["geo_station_distance", "geo_station_distance_resolution_factors"])
@pytest.mark.parametrize("value", [5, "abc", [1.0]])
def test_options_geo_station_distance_mappings_refuse_anything_but_a_mapping(field: str, value: object) -> None:
    """A non-empty value that is not a mapping is refused by pydantic, named by its field (GH-2353).

    The key checks used to look for keys in it, and failed with a bare `TypeError` naming nothing.
    """
    with pytest.raises(ValidationError, match=rf"{field}\n  Input should be a valid dictionary"):
        Options(**{field: value})


@pytest.mark.parametrize("field", ["geo_station_distance", "geo_station_distance_resolution_factors"])
@pytest.mark.parametrize("value", ["5", '"abc"', "[1.0]"])
def test_options_geo_station_distance_mappings_refuse_anything_but_a_mapping_from_env(
    monkeypatch: pytest.MonkeyPatch,
    field: str,
    value: str,
) -> None:
    """A `WD_*` variable holding JSON that is no object is refused the same way (GH-2353)."""
    monkeypatch.setenv(f"WD_TS_{field.upper()}", value)
    with pytest.raises(ValidationError, match=rf"{field}\n  Input should be a valid dictionary"):
        Options()


def test_options_geo_station_distance_survives_revalidation() -> None:
    """Test that validating the same options twice does not turn the table into overrides.

    `Options.model_validate(options)` re-runs every after-validator on the same instance.
    Capturing the overrides again there would take the already-expanded mapping for what the user
    wrote, and those 34 entries would then outrank a radius set afterwards.
    """
    options = Options(geo_station_distance_heterogeneous=30.0)
    revalidated = Options.model_validate(options)
    assert revalidated.model_dump()["geo_station_distance"] == {}
    assert revalidated.geo_station_distance["precipitation_amount"] == 30.0
    # a radius changed through a copy still reaches the mapping
    wider = revalidated.replace(geo_station_distance_heterogeneous=50.0)
    assert wider.geo_station_distance["precipitation_amount"] == 50.0


def test_options_geo_station_distance_factors_name_every_resolution() -> None:
    """Test that no resolution falls through to the unscaled default.

    The default exists for a name from outside the vocabulary, not for a resolution the table
    forgot: a resolution left out would hold a heterogeneous parameter to the hourly radius at
    every interval, which is a fifth too wide at `10_minutes` and half as wide as it should be at
    `daily`, and nothing about the result would say so.
    """
    assert set(_STATION_DISTANCE_RESOLUTION_FACTORS) == {resolution.value for resolution in Resolution}


def test_options_unit_targets_build_no_converter_when_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """The empty default, which every `Options()` has, is not resolved by a converter (GH-2306)."""
    monkeypatch.delenv("WD_TS_UNIT_TARGETS", raising=False)
    with mock.patch("wetterdienst.options.UnitConverter") as converter:
        Options()
    converter.assert_not_called()
