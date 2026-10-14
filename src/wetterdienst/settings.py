# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Settings for the wetterdienst package."""

from __future__ import annotations

import atexit
import contextlib
import functools
import json
import logging
import os
import platform
import re
import shutil
import sys
import tempfile
import threading
import warnings
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Self

import platformdirs
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    SecretStr,
    ValidationError,
    field_validator,
)
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict, SettingsError

from wetterdienst.options import (
    Options,
    _decode_nested_as_json_would,
    _quiet,
    options_from_mapping,
)

log = logging.getLogger(__name__)

#: what pydantic renders a secret as, and so what a credential looks like after a JSON round-trip
_MASK = "*" * 10


def _as_given(value: object) -> object:
    """Pass an element of a credential pair on for the field to wrap, an all-digit one as its text.

    A secret is passed through as it is: ``str()`` of a ``SecretStr`` is its mask, so a pair that
    has already been validated once -- which is what a ``model_dump()`` round-trip hands back --
    would come back as ten asterisks and fail at the provider later with nothing to say why. An
    ``int`` is taken as its decimal text: the environment decodes a pair as JSON where it parses,
    so an all-digit id arrives as one (JSON has no number with a leading zero, so such an id must
    be quoted in a pair). Anything else -- ``null``, ``true``, a float, an object -- is left for the field to
    refuse, which names the element; ``str()`` took the text of its repr, ``'None'`` or ``'True'``,
    for the credential (GH-2434).
    """
    if isinstance(value, int) and not isinstance(value, bool):
        return str(value)
    return value


def _stripped(value: object) -> object:
    """Pass a credential, or an element of a pair, on without the whitespace around its text (GH-2557).

    A secret is read out for it, and the field wraps the text again. An element that is no text is
    passed on as `_as_given` does, for the field to refuse or take.
    """
    if isinstance(value, SecretStr):
        value = value.get_secret_value()
    if isinstance(value, str):
        return value.strip()
    return _as_given(value)


def _blank_first(first: object, second: object, *, none_ok: bool = False) -> bool:
    """Tell a pair whose first element is blank from one that is refused, for the first to read as unset.

    The second element must be text that is not the mask a dumped credential leaves behind, or none
    where `none_ok` says a pair may have none (a Frost secret): anything else is passed on for the
    field, or the mask check, to refuse, as it was before the first element was read as blank
    (GH-2557).
    """
    return first == "" and ((second is None and none_ok) or (isinstance(second, str) and second != _MASK))


def reveal(secret: SecretStr | None) -> str | None:
    """Return what a secret holds, or None where there is no secret.

    The one place a credential is meant to be read back out, so that the sites that need the value
    say plainly that they are taking it out of hiding.
    """
    return secret.get_secret_value() if secret is not None else None


class Auth(BaseModel):
    """Authentication credentials for providers requiring API keys.

    Held as `SecretStr`, so that rendering the settings -- or a request, whose dataclass repr embeds
    them -- does not print them. They are not logged anywhere in normal operation; what exposes them
    is every ordinary way of looking at an object on a failure path: a pytest assertion diff, an
    unhandled traceback, `print(request)`, a debugger, a notebook. Anyone pasting such a traceback
    into an issue or a CI log would publish every credential they had configured (GH-1920).

    `reveal()` takes a value back out, and is the only thing that should.
    """

    # a credential assigned after construction (`settings.auth.knmi = ...`) is wrapped, split and
    # checked as one given to the constructor is; without it a plain `str` was kept, which `reveal()`
    # could not read and which printed as it was (GH-2387)
    # a credential refused is not repeated in the error, which pydantic otherwise echoes as its
    # `input_value` -- and a malformed credential is the one whose traceback gets pasted (GH-2435)
    model_config = ConfigDict(validate_assignment=True, hide_input_in_errors=True)

    aemet: SecretStr | None = Field(default=None)
    knmi: SecretStr | None = Field(default=None)
    metno_frost: tuple[SecretStr, SecretStr] | None = Field(default=None)
    ceda: tuple[SecretStr, SecretStr] | None = Field(default=None)

    @field_validator("aemet", "knmi", "metno_frost", "ceda", mode="before")
    @classmethod
    def reject_a_masked_credential(cls, value: object) -> object:
        """Refuse the mask that a dumped credential leaves behind.

        Dumping the settings to JSON writes ten asterisks where a credential is -- that is the point
        of holding them as secrets. Reading such a dump back would otherwise take the mask for the
        credential and fail at the provider much later, with nothing at all to say why.
        """
        items = value if isinstance(value, (tuple, list)) else (value,)
        for item in items:
            text = item.get_secret_value() if isinstance(item, SecretStr) else item
            if text == _MASK:
                msg = "the value is the mask a dumped credential leaves behind, not a credential"
                raise ValueError(msg)
        return value

    @field_validator("aemet", "knmi", mode="before")
    @classmethod
    def strip_a_key(cls, value: object) -> object:
        """Keep a key without the whitespace around it, text of nothing but whitespace reading as unset.

        The padding arrives from a `.env` value or a file saved with CRLF endings, and was sent to the
        provider as part of the key, which refused it with nothing to say why (GH-2557). Only text is
        stripped: any other value is passed on as it is, for the field to take or refuse.
        """
        if isinstance(value, SecretStr):
            value = value.get_secret_value()
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("metno_frost", mode="before")
    @classmethod
    def validate_metno_frost(
        cls,
        value: object,
    ) -> object:
        """Parse the Frost (client_id, secret) pair, a lone client id counting as one with no secret.

        An all-digit client id arrives as an `int`, as the environment decodes a nested value as JSON
        where it parses, and is still an id. Text starting with `[` is a pair, not a client id: it is
        decoded as JSON, and refused where it does not decode (GH-2464). Other text is refused, before
        any decoding, where it holds a character a client id cannot, such as `id:secret` (GH-2487). A
        lone client id is the text stripped of the whitespace around it, and text of nothing but
        whitespace, or an empty one, is no client id but unset (GH-2542). The same goes for the
        elements of a pair: each is kept without its padding, and a pair whose client id is blank is
        unset, as a lone one is, where it sent empty Basic auth (GH-2557). A mapping, or any other
        value that is not iterable -- a float, `true`, a JSON object -- is left for the field to
        refuse, which names it, where reading it as a pair failed with a bare `TypeError` or took
        the object's keys (GH-2379).
        """
        if value is None:
            return None
        value = _as_given(value)
        if isinstance(value, (str, SecretStr)):
            given = value.get_secret_value() if isinstance(value, SecretStr) else value
            text = given.strip()
            # a client id is a UUID and never starts with `[`, so such text is a pair: the
            # environment hands one on as its raw text where it is not valid JSON, and it was taken
            # whole as the client id, secret and all. One given as text in Python is read as the
            # environment reads it (GH-2464)
            if not text.startswith("["):
                # nor does it hold a character a Frost client id cannot -- anything but ASCII letters,
                # digits and `-`. Text that does is a pair written as `id:secret` (the shape
                # WD_AUTH__CEDA takes), `id,secret`, `id;secret` or `("id", "secret")`, which was
                # taken whole as the client id. The message stays constant, as the text holds the
                # secret (GH-2487). The mask a dumped credential leaves behind is left for the check
                # that names it, which compares it as given, so a padded mask is refused here
                if given != _MASK and re.search(r"[^0-9A-Za-z-]", text):
                    msg = (
                        'metno_frost is not a client id (letters, digits and "-" only); '
                        'write a pair as ["client_id", "secret"]'
                    )
                    raise ValueError(msg)
                # the client id is the stripped text, as it is the text that was checked: a newline
                # from a `.env` value, a `\r` from a file saved with CRLF endings, or an NBSP was
                # sent on as part of the id. Text with nothing but whitespace, or none, is no client
                # id, and reads as unset, as an empty value in the environment does (GH-2542)
                return (text, "") if text else None
            # decoding text that starts with `[` gives a list or fails: a `JSONDecodeError`, a
            # `ValueError` for an integer too long to convert, a `RecursionError` for nesting too
            # deep. The refusal is raised outside the handler, so that the decode error, which holds
            # the text it failed on, is not kept as its context
            decoded = None
            with contextlib.suppress(ValueError, RecursionError):
                decoded = json.loads(text)
            if decoded is None:
                msg = 'metno_frost looks like a pair but is not valid JSON: write it as ["client_id", "secret"]'
                raise ValueError(msg)
            value = decoded
        if isinstance(value, Mapping) or not isinstance(value, Iterable):
            return value
        as_tuple = tuple(value)
        if len(as_tuple) != 2:
            msg = f"metno_frost must be a (client_id, secret) pair, got {len(as_tuple)} element(s)"
            raise ValueError(msg)
        client_id, secret = _stripped(as_tuple[0]), _stripped(as_tuple[1])
        if _blank_first(client_id, secret, none_ok=True):
            return None
        # a client id with no secret, as a lone client id gives (GH-2434)
        return client_id, "" if secret is None else secret

    @field_validator("ceda", mode="before")
    @classmethod
    def validate_ceda(
        cls,
        value: object,
    ) -> object:
        """Parse the CEDA (username, password) pair, e.g. from ``WD_AUTH__CEDA=username:password``.

        A mapping, or a value that is neither that text nor iterable -- a number, `true` or a JSON
        object, which the environment decodes as JSON -- is left for the field to refuse, which names
        it, where reading it as a pair failed with a bare `TypeError` or took the object's keys
        (GH-2379). Text starting with `[` is a pair, not `username:password`: it is decoded as JSON,
        and refused where it does not decode (GH-2483). Each half is kept without the whitespace
        around it, and text of nothing but whitespace, or a pair with a blank username, is unset
        (GH-2557).
        """
        if value is None:
            return None
        if isinstance(value, SecretStr):
            # the pair given as a single secret: read it out to split it, and the halves are wrapped
            # again by the field
            value = value.get_secret_value()
        if isinstance(value, str):
            if not value.strip():
                return None
            # an account name is not expected to start with `[`, so such text is a pair: the
            # environment hands one on as its raw text where it is not valid JSON, and it was split
            # at the first colon in it, brackets and quotes kept in both halves. One given as text in
            # Python is read as the environment reads it
            if value.lstrip().startswith("["):
                # decoding gives a list or fails: a `JSONDecodeError`, a `ValueError` for an integer
                # too long to convert, a `RecursionError` for nesting too deep. The refusal is raised
                # outside the handler, so that the decode error, which holds the text it failed on,
                # is not kept as its context
                decoded = None
                with contextlib.suppress(ValueError, RecursionError):
                    decoded = json.loads(value.strip())
                if decoded is None:
                    msg = 'ceda looks like a pair but is not valid JSON: write it as ["username", "password"]'
                    raise ValueError(msg)
                value = decoded
            else:
                username, sep, password = value.partition(":")
                if not sep:
                    msg = "ceda must be given as 'username:password'"
                    raise ValueError(msg)
                username, password = username.strip(), password.strip()
                return None if _blank_first(username, password) else (username, password)
        if isinstance(value, Mapping) or not isinstance(value, Iterable):
            return value
        as_tuple = tuple(value)
        if len(as_tuple) != 2:
            msg = f"ceda must be a (username, password) pair, got {len(as_tuple)} element(s)"
            raise ValueError(msg)
        username, password = _stripped(as_tuple[0]), _stripped(as_tuple[1])
        return None if _blank_first(username, password) else (username, password)


def default_cache_dir(appname: str = "wetterdienst") -> Path:
    """Return the user's cache directory for `appname`, or a temporary one where there is no home.

    platformdirs 4.12 raises `RuntimeError` where no home directory resolves (HOME unset and the
    uid missing from the password database), and earlier versions returned the path with its `~`
    unexpanded, which became a directory named `~` below the working directory. Either way
    `Settings()` used to fail or misplace the cache, even with the cache disabled (GH-2408).
    """
    try:
        path = platformdirs.user_cache_dir(appname=appname)
    except RuntimeError:
        path = None
    if path is not None and not path.startswith("~"):
        return Path(path)
    # `functools.cache` lets two threads that miss at once both make a directory
    with _temporary_cache_dir_lock:
        return _temporary_cache_dir(appname)


_temporary_cache_dir_lock = threading.Lock()


@functools.cache
def _temporary_cache_dir(appname: str) -> Path:
    """Create one private temporary cache directory per process, removed when the process exits.

    `mkdtemp` rather than a fixed name below the shared temporary directory, which another user
    could create first and fill. A `SettingsError` where none can be made, which the CLI and the
    REST API tell as they tell an invalid setting.
    """
    try:
        path = Path(tempfile.mkdtemp(prefix=f"{appname}-"))
    except OSError as error:
        msg = (
            f"no directory for the {appname} cache: the home directory could not be determined and no "
            "temporary directory could be created; set WD_CACHE_DIR to a writable directory, or HOME"
        )
        raise SettingsError(msg) from error
    atexit.register(_remove_unless_forked, path, os.getpid())
    log.warning(
        f"the home directory could not be determined, so the {appname} cache is kept in {path} and "
        "removed when this process exits; set WD_CACHE_DIR, or HOME, to keep it across runs"
    )
    return path


def _remove_unless_forked(path: Path, pid: int) -> None:
    """Remove `path` at exit, unless this is a forked child of the process that made it.

    A child inherits the exit handler with the directory, and one exiting first -- a recycled
    server worker -- would remove it from under its parent and its siblings.
    """
    if os.getpid() == pid:
        shutil.rmtree(path, ignore_errors=True)


def _default_fsspec_client_kwargs() -> dict:
    """Return the client kwargs every request goes out with unless the caller says otherwise."""
    return {
        "headers": {"User-Agent": f"wetterdienst/{__import__('wetterdienst').__version__} ({platform.system()})"},
        "timeout": 30,
    }


def _merge_fsspec_client_kwargs(given: dict) -> dict:
    """Lay the caller's client kwargs over the defaults, a key the caller gives winning.

    ``headers`` is merged one level deeper, so that a header of the caller's own does not drop the
    User-Agent. Header names are case-insensitive, so a default header is left out where the caller
    gives the same name in any spelling; keeping both would send it twice. Headers given as anything
    but a plain dict -- aiohttp also takes a list of pairs, or a ``CIMultiDict`` that may repeat a
    name -- are used as they are, since copying them into a dict would drop a repeated header.
    """
    defaults = _default_fsspec_client_kwargs()
    merged = {**defaults, **given}
    headers = given.get("headers")
    if isinstance(headers, dict):
        named = {str(name).lower() for name in headers}
        merged["headers"] = {
            **{name: value for name, value in defaults["headers"].items() if name.lower() not in named},
            **headers,
        }
    return merged


def _masked(value: object, *, keep_numbers: bool = False) -> object:
    """Mask every leaf of a client kwargs value, keeping the names of dict keys, booleans and ``None``.

    The value is the one the settings hold, not a JSON dump of it: aiohttp takes objects JSON cannot
    hold, such as a ``ClientTimeout`` or a ``yarl.URL``. Those are leaves like any other and are
    masked, so that rendering cannot raise (GH-2623).
    """
    if isinstance(value, dict):
        return {_key_of(key): _masked(item, keep_numbers=keep_numbers) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_masked(item, keep_numbers=keep_numbers) for item in value]
    # a number is kept only where it is a plain, bounded one: NaN and infinity are no JSON, and an
    # int of thousands of digits cannot be printed. Both compare false here, so they are masked
    if (
        value is None
        or isinstance(value, bool)
        or (keep_numbers and isinstance(value, (int, float)) and abs(value) < 10**9)
    ):
        return value
    return _MASK


def _key_of(key: object) -> str:
    """Return a dict key as the text it renders as: a name stays, anything else is masked."""
    return key if isinstance(key, str) else _MASK


def _redacted_client_kwargs(kwargs: object) -> Any:  # noqa: ANN401
    """Return the client kwargs rendered, see `_redact_client_kwargs`; anything but a dict is masked whole."""
    return _redact_client_kwargs(kwargs) if isinstance(kwargs, dict) else _masked(kwargs)


def _redact_client_kwargs(kwargs: dict[str, Any]) -> dict[str, Any]:
    """Return ``fsspec_client_kwargs`` as the settings render them, every value masked but the harmless.

    The kwargs are handed to aiohttp as they are, so they may hold a proxy URL with its
    ``user:password@``, ``proxy_auth``, cookies, or request headers such as ``Authorization`` or
    ``X-Auth-Token``. Which of those carry a secret cannot be listed, so this fails closed: all is
    masked, a URL included, since cutting the userinfo from one takes a parser that agrees with the
    client's. What stays is a numeric timeout, the User-Agent header, booleans, ``None`` and the
    names of keys and headers, which say what was configured. ``kwargs`` are the ones the settings
    hold, not a JSON dump: a value JSON cannot hold, such as a ``ClientTimeout``, is masked like the
    rest, so that this cannot raise.
    """
    redacted = {}
    for key, value in kwargs.items():
        if key == "headers" and isinstance(value, dict):
            redacted[key] = {
                _key_of(name): item
                if isinstance(name, str) and name.lower() == "user-agent" and isinstance(item, str)
                else _masked(item)
                for name, item in value.items()
            }
        else:
            redacted[_key_of(key)] = _masked(value, keep_numbers=key == "timeout")
    return redacted


#: the modules that are no caller of the shim: wetterdienst itself, and the libraries it goes through
_SKIPPED_MODULES = ("wetterdienst", "pydantic", "pydantic_settings")

#: the ``ts_*`` settings the settings carried until options took them over (GH-2639), by the name of
#: the option each became. Written out, so that an option added later is not a keyword that never
#: existed; a test holds the names to the fields of `Options`. Still accepted, with a warning, until
#: they are dropped for good
_REMOVED_SETTINGS: dict[str, str] = {
    f"ts_{name}": name
    for name in (
        "humanize",
        "shape",
        "convert_units",
        "unit_targets",
        "skip_empty",
        "skip_threshold",
        "skip_criteria",
        "drop_nulls",
        "geo_station_distance_homogeneous",
        "geo_station_distance_heterogeneous",
        "geo_station_distance",
        "geo_station_distance_resolution_factors",
        "geo_use_nearby_station_distance",
        "geo_min_gain_of_value_pairs",
        "geo_num_additional_stations",
    )
}
#: the members derived from them, which `Options` has by the same name
_REMOVED_MEMBERS: dict[str, str] = {
    f"ts_{name}": name
    for name in ("tidy", "drop_nulls_effective", "geo_station_distance_for", "geo_station_distance_resolution_factor")
}


def _is_skipped(module: object) -> bool:
    """Tell whether a frame of this module, by its ``__name__``, is no caller of the shim."""
    return isinstance(module, str) and any(
        module == skipped or module.startswith(f"{skipped}.") for skipped in _SKIPPED_MODULES
    )


def _caller_stacklevel() -> int:
    """Return the stacklevel, for `_warn_removed`, that points at the code outside wetterdienst and pydantic.

    The shim is reached through `__init__`, `model_validate` (which a request calls for settings
    given as a dict), `__getattr__` and `__setattr__`, some of them through frames of pydantic and
    of the generated dataclass `__init__`. A warning attributed to one of those is not shown by
    default, which shows a `DeprecationWarning` only for code in ``__main__``. The frames are told
    by the module they run in and not by their file, which is none for ``python -c`` or a REPL.
    """
    level = 2
    frame = sys._getframe(2)  # noqa: SLF001
    while frame.f_back is not None and _is_skipped(frame.f_globals.get("__name__")):
        level += 1
        frame = frame.f_back
    return level


def _warn_removed(name: str) -> None:
    """Warn that a ``ts_*`` setting is deprecated and what to use instead."""
    if name in _REMOVED_MEMBERS:
        use = f"read request.options.{_REMOVED_MEMBERS[name]}"
    else:
        option = _REMOVED_SETTINGS[name]
        use = f"set options=Options({option}=...) on the request and read request.options.{option}"
    warnings.warn(
        f"the setting '{name}' is deprecated: it is an option of the request now; {use}. "
        "The WD_TS_* variables are unchanged",
        DeprecationWarning,
        stacklevel=_caller_stacklevel(),
    )


def resolve_options(options: Options | Mapping[str, Any] | None, settings: Settings) -> Options:
    """Settle the options of a request from what it was given.

    None gives the options the removed ``ts_*`` settings made, where the settings were given or
    assigned any, and otherwise those of the environment. A mapping gives `options_from_mapping`,
    and an `Options` is used as it is.

    Options given beside settings that carry ``ts_*`` settings of their own are refused: one of the
    two would be ignored, and which one is not a thing to leave a caller to guess. What the settings
    carry is compared with the options of the environment and ``.env``, so an operator's ``WD_TS_*``
    never counts against a caller who passes options. Options that are the very ones the settings
    carry are no conflict, which is what a request copied with `dataclasses.replace` gives.

    Raises:
        ValueError: Where both are given.

    """
    carried = settings._ts_options  # noqa: SLF001
    if options is None:
        return carried if carried is not None else Options()
    baseline = None
    if isinstance(options, Options):
        given = options
    else:
        with _quiet():
            baseline = Options()
        given = options_from_mapping(options, baseline)
    if carried is None or given.model_dump() == carried.model_dump():
        return given
    if baseline is None:
        with _quiet():
            baseline = Options()
    baseline_dump = baseline.model_dump()
    differing = [f"ts_{name}" for name, value in carried.model_dump().items() if value != baseline_dump[name]]
    if differing:
        msg = (
            f"the request was given options and settings that carry {', '.join(differing)}; "
            "set the request's options through options= alone"
        )
        raise ValueError(msg)
    return given


class Settings(BaseSettings):
    """Settings for the wetterdienst package."""

    model_config = SettingsConfigDict(
        env_file=".env",
        # UTF-8 on every Python, not the locale's encoding: Python 3.15 reads text as UTF-8 by default
        # (PEP 686) and earlier versions on Windows read the ANSI code page, so a `.env` holding a
        # non-ASCII value would otherwise mean different things by version
        env_file_encoding="utf-8",
        # read only the settings from `.env`, as from the environment. A `.env` is often shared with
        # other programs, and by default each of its other keys is handed on too, which the settings
        # refuse as no field of theirs: one line of someone else's made every `Settings()` fail and
        # echoed its value (GH-2349). The constructor still refuses a keyword that is no setting
        dotenv_filtering="only_existing",
        env_ignore_empty=True,
        env_prefix="WD_",
        env_nested_delimiter="__",
        # a field assigned after construction is checked as one given to the constructor is, and the
        # model validators below run again; without it a value out of bounds or outside its choices
        # was taken as it was and failed later, far from the assignment (GH-2342)
        validate_assignment=True,
        # the error does not repeat the value refused: `Auth`'s own setting hides it only in an error
        # raised by `Auth` itself, not in one raised through the settings, and a value given for
        # `auth` as a whole, or for `fsspec_client_kwargs` with its headers, is echoed here (GH-2435)
        hide_input_in_errors=True,
    )

    cache_disable: bool = Field(default=False)
    cache_dir: Path = Field(default_factory=default_cache_dir)
    fsspec_client_kwargs: dict = Field(default_factory=_default_fsspec_client_kwargs)
    auth: Auth = Field(default_factory=Auth)
    use_certifi: bool = Field(default=False)
    # opt-in: parse DWD radar BUFR files into a polars DataFrame (RadarResult.df). Requires the
    # optional eccodes + pdbufr dependencies; off by default because parsing is expensive.
    read_bufr: bool = Field(default=False)
    # opt-in: let REST API and MCP clients pass `sql` / `sql_values` clauses. Off by default because
    # the clause runs in DuckDB on this host with only per-request limits (see `_filter_by_sql`);
    # the library and the CLI, whose caller is the host's own user, are not gated
    restapi_sql: bool = Field(default=False)
    #: what the removed ``ts_*`` settings were given or assigned as, laid over the options of the
    #: environment. `None` until one is: a request then takes the options of the environment alone
    _ts_options: Options | None = PrivateAttr(default=None)

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],  # noqa: ARG003
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Take the sources as they are, but have the environment and `.env` refuse a value nested too deeply."""
        return (
            init_settings,
            _decode_nested_as_json_would(env_settings),
            _decode_nested_as_json_would(dotenv_settings),
            file_secret_settings,
        )

    def __init__(self, /, **values: Any) -> None:  # noqa: ANN401
        """Build the settings, taking the removed ``ts_*`` settings that are given as the options they became (GH-2639).

        They are no fields of the settings any more, and the environment's ``WD_TS_*`` is `Options`'
        to read, so this is only what a caller wrote out: ``Settings(ts_shape="wide")``. They are
        removed from the input before the settings validate it, so that they are not refused as
        settings that do not exist. Taken here and not by a validator, which would turn an error of
        a default (the cache directory) into one of the validation.
        """
        removed = {name: values.pop(name) for name in tuple(values) if name in _REMOVED_SETTINGS}
        super().__init__(**values)
        self._take_removed_ts_settings(removed)

    @classmethod
    def model_validate(cls, obj: Any, **kwargs: Any) -> Self:  # noqa: ANN401
        """Validate settings from a mapping or an instance, taking the removed ``ts_*`` settings as `__init__` does."""
        removed = {}
        if isinstance(obj, Mapping):
            removed = {name: obj[name] for name in obj if name in _REMOVED_SETTINGS}
            obj = {name: value for name, value in obj.items() if name not in removed}
        settings = super().model_validate(obj, **kwargs)
        settings._take_removed_ts_settings(removed)  # noqa: SLF001
        return settings

    def _take_removed_ts_settings(self, removed: dict[str, Any]) -> None:
        """Warn of the removed ``ts_*`` settings given, and keep them as the options they became."""
        if not removed:
            return
        for name in removed:
            _warn_removed(name)
        self._ts_options = Options(**{_REMOVED_SETTINGS[name]: value for name, value in removed.items()})

    def model_copy(self, *, update: Mapping[str, Any] | None = None, deep: bool = False) -> Self:
        """Copy the settings, taking a removed ``ts_*`` setting in `update` as an assignment to the copy."""
        removed = {name: value for name, value in (update or {}).items() if name in _REMOVED_SETTINGS}
        rest = {name: value for name, value in (update or {}).items() if name not in removed}
        settings = super().model_copy(update=rest or None, deep=deep)
        for name, value in removed.items():
            setattr(settings, name, value)
        return settings

    def __getattr__(self, name: str) -> object:
        """Read a removed ``ts_*`` setting from the options it became, and say it is removed (GH-2639)."""
        option = _REMOVED_SETTINGS.get(name) or _REMOVED_MEMBERS.get(name)
        if option is None:
            # pydantic defines `__getattr__` (private attributes and extras) outside the type-checking view
            return super().__getattr__(name)  # ty: ignore[unresolved-attribute]
        _warn_removed(name)
        return getattr(self._options_of_ts_settings(), option)

    def __setattr__(self, name: str, value: object) -> None:
        """Assign a removed ``ts_*`` setting to the options it became, and say it is removed (GH-2639).

        The options are frozen, so this makes a changed copy: a request built from the settings
        before keeps the options it had, and one built after has the changed ones.
        """
        option = _REMOVED_SETTINGS.get(name)
        if option is None:
            super().__setattr__(name, value)
            return
        _warn_removed(name)
        self._ts_options = self._options_of_ts_settings().replace(**{option: value})

    def _options_of_ts_settings(self) -> Options:
        """Return the options of the environment with the removed ``ts_*`` settings laid over them."""
        if self._ts_options is not None:
            return self._ts_options
        with _quiet():
            return Options()

    @field_validator("fsspec_client_kwargs", mode="before")
    @classmethod
    def merge_fsspec_client_kwargs(cls, value: object) -> object:
        """Merge the caller's client kwargs into the defaults rather than replace them (GH-2269).

        A dict of one's own -- the ``{"trust_env": True}`` the docs give for a proxy -- used to
        replace the defaults whole, and with them the timeout and the User-Agent: requests then fell
        back to aiohttp's own five minutes for the whole request, and went out with aiohttp's
        User-Agent rather than wetterdienst's. Anything but a mapping is left for the field to
        refuse.
        """
        return _merge_fsspec_client_kwargs(dict(value)) if isinstance(value, Mapping) else value

    def model_post_init(self, _context: object, /) -> None:
        """Log what the settings were built with, once, as they are built.

        Not a model validator: those run again for every assignment (`validate_assignment`) and for
        `Settings.model_validate(settings)`, and logged these lines each time. So a field assigned
        afterwards logs nothing; the lines say how the settings began.
        """
        if self.cache_disable:
            log.info("Wetterdienst cache is disabled")
        else:
            log.info(f"Wetterdienst cache is enabled [CACHE_DIR:{self.cache_dir}]")

    def _rendered(self) -> dict[str, Any]:
        """Return the settings as they are rendered: ``fsspec_client_kwargs`` without its credentials.

        stamina's retry log writes ``repr`` of every argument of a retried call, and the listings
        take the settings (GH-2593). ``model_dump`` is left as it is, so that a dump
        still round-trips into ``Settings(**dump)``.

        The client kwargs are not dumped as JSON, which raises for what aiohttp takes but JSON cannot
        hold -- a ``ClientTimeout``, a ``yarl.URL`` -- and would so raise inside that log (GH-2623).
        They are masked from the value the settings hold, where what is not known is a leaf like any
        other.
        """
        dumped = self.model_dump(mode="json", exclude={"fsspec_client_kwargs"})
        redacted = _redacted_client_kwargs(self.fsspec_client_kwargs)
        # in the order of the fields, as the dump has it
        return {
            name: redacted if name == "fsspec_client_kwargs" else dumped[name]
            for name in type(self).model_fields
            if name == "fsspec_client_kwargs" or name in dumped
        }

    def __repr_args__(self) -> Iterable[tuple[str | None, Any]]:
        """Give the client kwargs masked to everything that renders the fields: pydantic's repr and rich (GH-2623)."""
        for name, value in super().__repr_args__():
            yield name, _redacted_client_kwargs(value) if name == "fsspec_client_kwargs" else value

    def __repr__(self) -> str:
        """Return the settings as a JSON string, the client kwargs' credentials masked."""
        return json.dumps(self._rendered())

    def __str__(self) -> str:
        """Return the settings as a string, the client kwargs' credentials masked."""
        return f"""Settings({json.dumps(self._rendered(), indent=4)})"""


def _describe_settings_error(error: ValidationError | SettingsError, prefix: str = "WD_") -> list[str]:
    """Tell what is wrong with the settings, a line for each problem, by the environment variable that sets it.

    For an error of settings built from the environment and `.env` alone, as `check_settings`
    builds them. Neither hands on a key that is no setting (GH-2349), so every problem is a
    setting's. `prefix` is the one the settings read their variables with: ``WD_`` for `Settings`,
    ``WD_TS_`` for `Options`.

    pydantic's own account names the field rather than the variable an operator set, and each of
    its `errors()` holds the value given -- which for `WD_AUTH__*` is a credential, and for
    `WD_FSSPEC_CLIENT_KWARGS` may hold request headers. Here each problem is the variable and
    pydantic's message, without that input (GH-2335), which the settings leave out of the error's
    text as well (GH-2435). A validator's own message may still name what it refuses -- a unit or a
    parameter name -- which none of those on the credentials or the headers does.
    """
    if isinstance(error, SettingsError):
        # a dict, a pair or a nested setting is read as JSON, and pydantic-settings says which field
        # it could not parse, but not where in the value
        match = re.search(r'error parsing value for field "(\w+)"', str(error))
        if match:
            return [f"{prefix}{match.group(1).upper()} is invalid: not valid JSON"]
        return [str(error)]
    lines = []
    for problem in error.errors(include_url=False):
        # an element of a pair, such as the secret in `WD_AUTH__METNO_FROST`, is no variable of its
        # own, and is told by its index after the name that holds it: `WD_AUTH__METNO_FROST[1]`
        variable = prefix if problem["loc"] else f"{prefix}*"
        for part in problem["loc"]:
            if isinstance(part, int):
                variable += f"[{part}]"
            else:
                variable += ("" if variable == prefix else "__") + str(part).upper()
        lines.append(f"{variable} is invalid: {problem['msg'].removeprefix('Value error, ')}")
    return lines


def check_settings() -> list[str]:
    """Build the settings and the options from the environment and `.env` alone, and tell what is wrong with them.

    An empty list means they are valid.
    """
    lines: list[str] = []
    for build, prefix in ((Settings, "WD_"), (Options, "WD_TS_")):
        try:
            build()
        except (ValidationError, SettingsError) as e:
            lines.extend(_describe_settings_error(e, prefix))
    return lines
