# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.#
"""Tests for settings."""

import ast
import atexit
import collections
import dataclasses
import functools
import json
import logging
import os
import re
import tempfile
import threading
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, get_args, get_origin
from unittest import mock

import platformdirs
import pytest
from aiohttp import ClientTimeout
from multidict import CIMultiDict
from pydantic import SecretStr, ValidationError
from pydantic_settings import SettingsError
from yarl import URL

import wetterdienst.settings
from wetterdienst.settings import (
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
    assert not default_settings.use_certifi
    # SQL from REST API and MCP clients stays off until the operator turns it on
    assert not default_settings.restapi_sql
    assert re.match(WD_CACHE_ENABLED_PATTERN, caplog.messages[0])


@mock.patch.dict(os.environ, {})
def test_settings_envs(caplog: pytest.LogCaptureFixture) -> None:
    """Test default settings but with multiple envs set, those of the options being no settings'."""
    os.environ["WD_CACHE_DISABLE"] = "1"
    os.environ["WD_TS_SHAPE"] = "wide"
    os.environ["WD_TS_GEO_STATION_DISTANCE"] = '{"precipitation_amount":40.0,"humidity_relative":42}'
    caplog.set_level(logging.INFO)
    settings = Settings()
    # the options of the environment are `Options`' to read: the settings say nothing of the wide shape
    assert caplog.messages == ["Wetterdienst cache is disabled"]
    assert settings.cache_disable
    assert "ts_shape" not in settings.model_dump()


@mock.patch.dict(os.environ, {})
def test_settings_mixed(caplog: pytest.LogCaptureFixture) -> None:
    """Test mixed settings."""
    os.environ["WD_CACHE_DISABLE"] = "1"
    os.environ["WD_USE_CERTIFI"] = "0"
    caplog.set_level(logging.INFO)
    settings = Settings(use_certifi=True)
    assert settings.cache_disable
    assert caplog.messages[0] == "Wetterdienst cache is disabled"  # env variable
    assert settings.use_certifi  # argument variable overrules env variable


def test_settings_env_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that Settings loads values from a .env file in the working directory."""
    monkeypatch.delenv("WD_CACHE_DISABLE", raising=False)
    (tmp_path / ".env").write_text("WD_CACHE_DISABLE=true\n")
    monkeypatch.chdir(tmp_path)
    settings = Settings()
    assert settings.cache_disable


def test_settings_env_file_is_read_as_utf8(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that a .env file is read as UTF-8, whatever the locale's encoding is (Python 3.15 made it the default)."""
    monkeypatch.delenv("WD_CACHE_DIR", raising=False)
    (tmp_path / ".env").write_bytes("WD_CACHE_DIR=Wetterdienst-Täler\n".encode())
    monkeypatch.chdir(tmp_path)
    assert Settings.model_config["env_file_encoding"] == "utf-8"
    assert Settings().cache_dir.name == "Wetterdienst-Täler"


def test_settings_env_file_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Test that Settings loads without error when no .env file exists."""
    monkeypatch.delenv("WD_CACHE_DISABLE", raising=False)
    monkeypatch.chdir(tmp_path)
    settings = Settings()
    assert not settings.cache_disable


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
        pytest.param("use_certifi", "maybe", "Input should be a valid boolean", id="boolean"),
        pytest.param("fsspec_client_kwargs", 5, "Input should be a valid dictionary", id="dict"),
    ],
)
def test_settings_assignment_is_validated(field: str, value: object, message: str) -> None:
    """A field assigned after construction is refused as the constructor refuses it (GH-2342).

    A refused assignment leaves the field as it was.
    """
    settings = Settings()
    before = getattr(settings, field)
    with pytest.raises(ValidationError, match=rf"{field}\n  [^\n]*{re.escape(message)}"):
        setattr(settings, field, value)
    assert getattr(settings, field) == before


@pytest.mark.usefixtures("_no_ambient_settings")
def test_settings_assignment_takes_a_valid_value() -> None:
    """A valid assignment is taken, and coerced to the field's type as the constructor does (GH-2342)."""
    settings = Settings()
    settings.use_certifi = True
    settings.cache_dir = "some/dir"
    assert settings.use_certifi
    assert settings.cache_dir == Path("some/dir")


@pytest.mark.usefixtures("_no_ambient_settings")
def test_settings_assignment_rewrites_fields_as_construction_does() -> None:
    """The validators that rewrite a field give on assignment what they give on construction (GH-2342).

    The client kwargs are laid over the defaults.
    """
    settings = Settings()
    settings.fsspec_client_kwargs = {"trust_env": True}
    assert settings.fsspec_client_kwargs == Settings(fsspec_client_kwargs={"trust_env": True}).fsspec_client_kwargs


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


def test_settings_request_built_from_settings_logs_them_once(caplog: pytest.LogCaptureFixture) -> None:
    """A request handed a `Settings` does not validate it again, which logged its notices twice (GH-2476).

    The CLI builds the settings and then the request from them; every command logged the cache line
    twice.
    """
    from wetterdienst.provider.dwd.observation import DwdObservationRequest  # noqa: PLC0415

    with caplog.at_level(logging.INFO, logger="wetterdienst.settings"):
        settings = Settings()
        request = DwdObservationRequest(parameters=["daily/kl"], settings=settings)
    assert request.settings is settings
    messages = [record.getMessage() for record in caplog.records if record.name == "wetterdienst.settings"]
    assert sum(message.startswith("Wetterdienst cache is") for message in messages) == 1


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
        settings = Settings(cache_disable=False)
        messages = _settings_log_messages(caplog)
        assert len(messages) == 1
        assert messages[0].startswith("Wetterdienst cache is enabled")
        settings.use_certifi = True
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


def _client_kwargs_json_cannot_hold() -> dict:
    """Return client kwargs aiohttp accepts and JSON cannot hold, one carrying a password."""
    return {
        "timeout": ClientTimeout(total=5),
        "proxy": URL("http://proxy-user:QSECRET@proxy.example:3128"),
        "headers": {"User-Agent": "mine/1", "Authorization": SecretValue("HEADER-SECRET")},
        "cookies": {("a", "tuple"): b"COOKIE-SECRET"},
    }


@dataclasses.dataclass(frozen=True)
class SecretValue:
    """A header value of a type JSON cannot hold, whose repr gives the secret away."""

    value: str


@pytest.mark.usefixtures("_no_ambient_settings")
def test_settings_render_client_kwargs_that_json_cannot_hold() -> None:
    """A ``ClientTimeout`` or a ``yarl.URL`` in the client kwargs is masked, not a serialization error (GH-2623).

    aiohttp takes both, but the settings rendered ``model_dump(mode="json")``, which raised for
    them, and so did stamina's retry log that renders the settings of a failed listing.
    """
    settings = Settings(fsspec_client_kwargs=_client_kwargs_json_cannot_hold())

    for rendered in (repr(settings), str(settings), f"{settings}"):
        assert "QSECRET" not in rendered
        assert "HEADER-SECRET" not in rendered
        assert "COOKIE-SECRET" not in rendered
        assert "mine/1" in rendered
        assert "Authorization" in rendered
    # the rendering still is the JSON it was, with the unknown masked and the rest as before
    rendered = json.loads(repr(settings))
    assert rendered["fsspec_client_kwargs"]["timeout"] == "*" * 10
    assert rendered["fsspec_client_kwargs"]["proxy"] == "*" * 10
    assert rendered["cache_disable"] is False
    # what the settings are used from is not touched
    assert settings.fsspec_client_kwargs["timeout"] == ClientTimeout(total=5)
    assert settings.fsspec_client_kwargs["proxy"] == URL("http://proxy-user:QSECRET@proxy.example:3128")


@pytest.mark.usefixtures("_no_ambient_settings")
def test_settings_render_the_masked_client_kwargs_to_pydantic_and_rich() -> None:
    """The fields pydantic's repr and rich's pretty printer read hold the masked client kwargs (GH-2623).

    Rich prints ``__rich_repr__`` of a pydantic model, which is built from ``__repr_args__`` and not
    from ``__repr__``, so a masking of ``__repr__`` alone left it printing the proxy's password.
    """
    for client_kwargs, secrets in (
        (_CLIENT_KWARGS_WITH_CREDENTIALS, _CLIENT_KWARGS_SECRETS),
        (_client_kwargs_json_cannot_hold(), ["QSECRET", "HEADER-SECRET", "COOKIE-SECRET"]),
    ):
        settings = Settings(fsspec_client_kwargs=client_kwargs)

        for rendered in (
            settings.__repr_str__(", "),
            " ".join(f"{name}={value!r}" for name, value in settings.__rich_repr__()),
            " ".join(f"{name}={value!r}" for name, value in settings.__repr_args__()),
        ):
            assert [secret for secret in secrets if secret in rendered] == []
            assert "mine/1" in rendered


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize(
    "timeout",
    [float("nan"), float("inf"), 10**5000],
    ids=["nan", "infinity", "5000-digit-int"],
)
def test_settings_render_a_timeout_that_is_no_plain_number_as_json(timeout: float) -> None:
    """A timeout JSON cannot print is masked, so the rendering stays valid JSON that can be printed (GH-2623)."""
    settings = Settings(fsspec_client_kwargs={"timeout": timeout})

    assert json.loads(repr(settings), parse_constant=pytest.fail)["fsspec_client_kwargs"]["timeout"] == "*" * 10
    assert "*" * 10 in str(settings)


@pytest.mark.usefixtures("_no_ambient_settings")
def test_a_failed_listing_with_client_kwargs_json_cannot_hold_raises_its_own_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A listing that fails is retried and raises the failure, not the settings' serialization error (GH-2623).

    stamina's hook calls ``repr`` on every argument of the call it retries, the settings among
    them, so the first failure raised the error of rendering them from inside the retry.
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
    settings = Settings(cache_dir=tmp_path, fsspec_client_kwargs=_client_kwargs_json_cannot_hold())

    for listing in (list_remote_files_fsspec, list_remote_directory_fsspec):
        with stamina.set_testing(True, attempts=2), pytest.raises(OSError, match="boom"):
            listing("https://example.com/dir/", settings)


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
    that fails in a way worth asking again logs them at WARNING on its first retry. The failure here
    is a reset connection, which names no proxy, so the settings are the only place the password
    could come from.
    """
    import stamina  # noqa: PLC0415
    from aiohttp import ClientOSError  # noqa: PLC0415

    from wetterdienst.exceptions import DownloadError  # noqa: PLC0415
    from wetterdienst.util.network import (  # noqa: PLC0415
        HTTPFileSystem,
        list_remote_directory_fsspec,
        list_remote_files_fsspec,
    )

    def fail(_self: object, _url: str, **_kwargs: object) -> list:
        raise ClientOSError(104, "boom")

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
            pytest.raises(DownloadError, match="boom"),
        ):
            call()

        assert caplog.records, "stamina logged nothing, so this test would pass for the wrong reason"
        for record in caplog.records:
            # the message and everything stamina attaches to the record, as a formatter might render it
            carried = record.getMessage() + "".join(str(value) for value in record.__dict__.values())
            assert [secret for secret in _CLIENT_KWARGS_SECRETS if secret in carried] == []


def _holds_settings(value: object, *, depth: int = 0) -> bool:
    """Whether ``value`` is, or holds in a container it is built from, a ``Settings`` object."""
    if isinstance(value, Settings):
        return True
    if depth > 4:
        return False
    if isinstance(value, dict):
        value = [*value.keys(), *value.values()]
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(_holds_settings(item, depth=depth + 1) for item in value)
    return False


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize("by_keyword", [False, True], ids=["positional", "keyword"])
def test_a_retried_listing_puts_no_settings_object_into_stamina_s_log_record(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
    *,
    by_keyword: bool,
) -> None:
    """Stamina's log record carries no ``Settings`` object, whatever a handler does with its fields (GH-2904).

    The retry decorator hands the arguments of the call to stamina's hook, which attaches them to
    the record as ``stamina.args`` (as their ``repr``) and ``stamina.kwargs`` (as they are), so a
    keyword call put the live settings there. A formatter that renders ``str`` gets the masked form,
    but a handler that serialises a pydantic object by its fields reads the raw client kwargs. The
    retry is a ``retry_context``, which has no arguments to hand over.
    """
    import stamina  # noqa: PLC0415
    from aiohttp import ClientOSError  # noqa: PLC0415

    from wetterdienst.exceptions import DownloadError  # noqa: PLC0415
    from wetterdienst.util.network import (  # noqa: PLC0415
        HTTPFileSystem,
        list_remote_directory_fsspec,
        list_remote_files_fsspec,
    )

    calls = []

    def fail(_self: object, _url: str, **_kwargs: object) -> list:
        calls.append(_url)
        raise ClientOSError(104, "boom")

    monkeypatch.setattr(HTTPFileSystem, "find", fail)
    monkeypatch.setattr(HTTPFileSystem, "ls", fail)
    settings = Settings(cache_dir=tmp_path, fsspec_client_kwargs=_CLIENT_KWARGS_WITH_CREDENTIALS)

    for listing in (list_remote_files_fsspec, list_remote_directory_fsspec):
        caplog.clear()
        calls.clear()
        call = (
            functools.partial(listing, "https://example.com/dir/", settings=settings)
            if by_keyword
            else functools.partial(listing, "https://example.com/dir/", settings)
        )
        with (
            stamina.set_testing(True, attempts=2),
            caplog.at_level(logging.DEBUG, logger="stamina"),
            pytest.raises(DownloadError, match="boom"),
        ):
            call()

        # retried, and said so, so that the test cannot pass because stamina never logged
        assert len(calls) == 2
        scheduled = [record for record in caplog.records if record.getMessage() == "stamina.retry_scheduled"]
        assert len(scheduled) == 1
        for record in caplog.records:
            assert [name for name, value in record.__dict__.items() if _holds_settings(value)] == []
        assert scheduled[0].__dict__["stamina.args"] == ()
        assert scheduled[0].__dict__["stamina.kwargs"] == {}


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


def _type_checking_signature() -> ast.arguments:
    """Return the arguments of the `__init__` that `Settings` shows a type checker (`if TYPE_CHECKING:`)."""
    module = ast.parse(Path(wetterdienst.settings.__file__).read_text(encoding="utf8"))
    cls = next(node for node in module.body if isinstance(node, ast.ClassDef) and node.name == "Settings")
    guard = next(
        node
        for node in cls.body
        if isinstance(node, ast.If) and isinstance(node.test, ast.Name) and node.test.id == "TYPE_CHECKING"
    )
    init = next(node for node in guard.body if isinstance(node, ast.FunctionDef) and node.name == "__init__")
    return init.args


def _takes(argument: Any, annotation: Any) -> bool:  # noqa: ANN401
    """Whether an argument of this type takes what a field annotated so holds (`dict[str, Any]` is a `Mapping`)."""
    if argument == annotation:
        return True
    origin, held = get_origin(argument), get_origin(annotation)
    return (
        origin is not None
        and held is not None
        and issubclass(held, origin)
        and get_args(argument) == get_args(annotation)
    )


def test_the_constructor_a_type_checker_reads_has_the_fields_of_the_settings() -> None:
    """The stub of `Settings.__init__` is the fields as keyword-only arguments, by name and by type (GH-3042).

    `BaseSettings.__init__` takes `**values: Any`, which hides the fields from a type checker, so the
    class shows it a signature of its own under `TYPE_CHECKING`. It cannot be read at runtime, so this
    reads the source, and holds it to `Settings.model_fields` so that a field added to the settings cannot
    be left out of it. An argument takes the type of its field or a union that has it as a member (a path
    may be given as text, `auth` as a mapping).
    """
    args = _type_checking_signature()
    namespace = vars(wetterdienst.settings)
    stub = {arg.arg: eval(ast.unparse(arg.annotation), namespace) for arg in args.kwonlyargs}  # noqa: S307

    assert [arg.arg for arg in args.posonlyargs] == ["self"]
    assert args.args == []
    assert args.vararg is None
    assert args.kwarg is None
    assert all(default is not None for default in args.kw_defaults), "an argument without a default is required"
    assert set(stub) == set(Settings.model_fields)
    for name, field in Settings.model_fields.items():
        assert any(_takes(member, field.annotation) for member in (stub[name], *get_args(stub[name]))), name
