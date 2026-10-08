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
import tempfile
import threading
from collections import defaultdict
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Annotated, Literal

import platformdirs
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    PrivateAttr,
    SecretStr,
    ValidationError,
    field_serializer,
    field_validator,
    model_validator,
)
from pydantic_settings import BaseSettings, SettingsConfigDict, SettingsError

from wetterdienst.exceptions import InvalidEnumerationError
from wetterdienst.metadata.parameter_table import PARAMETER_TABLE, PARAMETERS
from wetterdienst.metadata.renamed import RENAMED_PARAMETERS
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.unit import UnitConverter

log = logging.getLogger(__name__)

_UNIT_CONVERTER_TARGETS = UnitConverter().targets.keys()


#: what pydantic renders a secret as, and so what a credential looks like after a JSON round-trip
_MASK = "*" * 10

#: the share of readings a station must cover not to be skipped: a threshold above 1 skips every
#: station, one of 0 or below none, so neither is one. The REST request model takes it too, so the
#: two cannot drift apart (GH-2334)
SkipThreshold = Annotated[float, Field(gt=0, le=1)]


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


#: how far a station may be from the target point to still be used, in km
_STATION_DISTANCE_HOMOGENEOUS = 40.0
#: the same for a quantity that decorrelates faster -- see `CanonicalParameter.interpolation`
_STATION_DISTANCE_HETEROGENEOUS = 20.0
#: how far the heterogeneous radius reaches at a given resolution, relative to its hourly value.
#: a quantity that decorrelates fast in space does so less the longer it is accumulated: gauge
#: studies put the correlation length of precipitation at roughly 8 km over 10 minutes, 27 km over
#: three hours and 33 to 94 km over a day, the upper end for the stratiform rain that dominates
#: north-western Europe. One radius cannot serve both ends of that, so the radius follows the
#: accumulation period.
#:
#: The table stops widening at 2.0 rather than following the correlation length up. Past a day,
#: what binds is terrain and not correlation: the interpolation reads UTM x/y and never station
#: elevation, so 40 km is as far as it may reach in complex ground -- the same bound the homogeneous
#: radius is held to, which is why the two meet at `daily` with the defaults. Precipitation is more
#: orographically driven than temperature, not less, so it does not get to reach farther.
#:
#: The fine end is not tightened all the way to the correlation length either: the interpolation
#: needs four surrounding stations, and even the DWD network rarely has four rain gauges within
#: 8 km of a point, so 15 km at `minute_10` is as tight as still answers at all.
#:
#: The factors are pure multipliers of whatever `ts_geo_station_distance_heterogeneous` says. A
#: radius the user raises is followed rather than clipped: they have made the terrain judgement the
#: table encodes, and a setting that silently does nothing is the failure this module validates
#: against everywhere else. The homogeneous radius does not scale at all -- terrain does not care
#: how long a quantity was accumulated for
_STATION_DISTANCE_RESOLUTION_FACTORS: dict[str, float] = {
    Resolution.MINUTE_1.value: 0.75,
    Resolution.MINUTE_5.value: 0.75,
    Resolution.MINUTE_6.value: 0.75,
    Resolution.MINUTE_10.value: 0.75,
    Resolution.MINUTE_15.value: 0.75,
    Resolution.HOURLY.value: 1.0,
    Resolution.HOUR_6.value: 1.5,
    Resolution.SUBDAILY.value: 1.5,
    Resolution.DAILY.value: 2.0,
    Resolution.MONTHLY.value: 2.0,
    Resolution.ANNUAL.value: 2.0,
}
#: every `Resolution` is named above, so this catches a resolution name from outside that
#: vocabulary, which is left as it is rather than guessed at
_STATION_DISTANCE_RESOLUTION_FACTOR_DEFAULT = 1.0


def _build_geo_station_distance(
    homogeneous: float,
    heterogeneous: float,
    overrides: dict[str, float],
) -> defaultdict[str, float]:
    """Build the per-parameter search radius from the two radii, the parameter table and overrides.

    Which names get the shorter radius used to be written out here, a copy of a classification the
    table already holds. Only those names are put in the dict; the default factory answers for
    every other parameter, so the setting a user sees and overrides stays the short list of
    exceptions rather than every name in the table.
    """
    d: defaultdict[str, float] = defaultdict(lambda: homogeneous)
    for parameter in PARAMETER_TABLE:
        if parameter.interpolation == "heterogeneous":
            d[parameter.name] = heterogeneous
    d.update(overrides)
    return d


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


class Settings(BaseSettings):
    """Settings for the wetterdienst package."""

    model_config = SettingsConfigDict(
        env_file=".env",
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
    ts_humanize: bool = True
    ts_shape: Literal["wide", "long"] = "long"
    ts_convert_units: bool = True
    ts_unit_targets: dict[str, str] = Field(default_factory=dict)
    # skip a station whose requested parameters are covered too sparsely to be worth
    # returning. The coverage is measured against how many readings the requested window can
    # hold, so the option stands on its own and needs no particular shape of frame under it
    ts_skip_empty: bool = False
    ts_skip_threshold: SkipThreshold = 0.95
    ts_skip_criteria: Literal["min", "mean", "max"] = "min"
    ts_drop_nulls: bool = True
    # how far a station may be from the target point to still be interpolated or summarized from.
    # the two radii follow `CanonicalParameter.interpolation`: a homogeneous quantity such as air
    # temperature varies slowly across a region and may be drawn from farther away than a
    # heterogeneous one such as precipitation, which decorrelates within a few tens of kilometres
    ts_geo_station_distance_homogeneous: Annotated[float, Field(ge=0)] = _STATION_DISTANCE_HOMOGENEOUS
    ts_geo_station_distance_heterogeneous: Annotated[float, Field(ge=0)] = _STATION_DISTANCE_HETEROGENEOUS
    # per-parameter overrides of the two radii above, given as canonical parameter names. holds the
    # overrides alone while validating and the mapping -- radii, table and overrides -- from
    # `expand_ts_geo_station_distance` on. that mapping is the radius at hourly resolution;
    # `ts_geo_station_distance_for` gives the one a request actually uses
    ts_geo_station_distance: defaultdict[str, float] = Field(default_factory=dict)
    # how the heterogeneous radius grows with the accumulation period, keyed by resolution. Only
    # the resolutions named here differ from `_STATION_DISTANCE_RESOLUTION_FACTORS`; the rest keep
    # their factor, so the setting stays the list of departures rather than all eleven
    ts_geo_station_distance_resolution_factors: dict[str, float] = Field(default_factory=dict)
    #: what was passed for `ts_geo_station_distance`, kept for serialization and re-expansion.
    #: `None` until the field has been expanded once -- an empty dict is a valid set of overrides
    _ts_geo_station_distance_overrides: dict[str, float] | None = PrivateAttr(default=None)
    # this setting is used to define how far away a station can be so that no interpolation is done
    # but instead the station is used directly
    ts_geo_use_nearby_station_distance: Annotated[float, Field(ge=0)] | None = 1.0
    # this rather complicated setting is used in the process of figuring out how many additional stations will be used
    # the gain defines how many additional timestamps can be interpolated by adding the specific station and thus
    # getting more timestamps with the required minimum of four values
    # so basically this setting considers the extra effort against the gain of additional interpolated timestamps
    ts_geo_min_gain_of_value_pairs: Annotated[float, Field(ge=0)] = 0.10
    # this setting defines how many additional stations are used in the interpolation process independent of the gain
    # of value pairs, so if the gain is not reached anymore, there at least `num` more stations added to the list
    ts_geo_num_additional_stations: Annotated[int, Field(ge=0)] = 3

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

    @field_validator("ts_unit_targets", mode="before")
    @classmethod
    def validate_ts_unit_targets_before(cls, values: dict[str, str] | None) -> dict[str, str]:
        """Validate the unit targets."""
        return values or {}

    @field_validator("ts_unit_targets", mode="after")
    @classmethod
    def validate_ts_unit_targets_after(cls, values: dict[str, str]) -> dict[str, str]:
        """Validate the unit targets, the units as well as the quantities.

        A unit the converter has no such name for, or holds back as one a source publishes in, used
        to pass here and be refused only once a values request had fetched its stations (GH-2306).
        """
        if not values:
            # the default, which every `Settings()` is built with, so no converter is built for it
            return values
        unknown = sorted(values.keys() - _UNIT_CONVERTER_TARGETS)
        if unknown:
            msg = (
                f"Invalid unit targets: quantities not supported: {', '.join(unknown)}. "
                f"Supported quantities are: {', '.join(sorted(_UNIT_CONVERTER_TARGETS))}"
            )
            raise ValueError(msg)
        try:
            UnitConverter().update_targets(values)
        except InvalidEnumerationError as e:
            msg = f"Invalid unit targets: {e}"
            raise ValueError(msg) from e
        return values

    @field_validator("ts_geo_station_distance", mode="before")
    @classmethod
    def validate_ts_geo_station_distance_keys(cls, values: object) -> object:
        """Check the overridden parameter names, which used to be taken on trust.

        A name that is not a canonical parameter can never be looked up, so the override silently
        did nothing and the parameter the user meant kept its default radius -- a typo was
        indistinguishable from having set nothing at all. An empty value means no overrides; any
        other that is not a mapping is left for the field to refuse, which names it, where looking
        for keys in it failed with a bare `TypeError` that named nothing (GH-2353).
        """
        if not values:
            return {}
        if not isinstance(values, Mapping):
            return values
        if "default" in values:
            msg = (
                "the 'default' key of ts_geo_station_distance is gone, as it replaced the fallback radius and "
                "the pre-populated per-parameter ones alike; set ts_geo_station_distance_homogeneous and "
                "ts_geo_station_distance_heterogeneous instead"
            )
            raise ValueError(msg)
        unknown = sorted(set(values) - PARAMETERS.keys())
        if unknown:
            msg = f"Invalid parameters in ts_geo_station_distance: {unknown} not in the canonical parameters"
            renamed = [
                f"'{name}' is now '{RENAMED_PARAMETERS[name]}'" for name in unknown if name in RENAMED_PARAMETERS
            ]
            if renamed:
                msg += f" ({', '.join(renamed)})"
            raise ValueError(msg)
        never_interpolated = sorted(name for name in values if not PARAMETERS[name].interpolation)
        if never_interpolated:
            log.warning(
                f"option 'ts_geo_station_distance' sets a radius for {never_interpolated}, which are never "
                "interpolated, and is thus ignored for them in this request.",
            )
        return values

    @field_validator("ts_geo_station_distance", mode="after")
    @classmethod
    def validate_ts_geo_station_distance_values(cls, values: dict[str, float]) -> dict[str, float]:
        """Reject negative radii, as `ts_geo_use_nearby_station_distance` next to it already does."""
        negative = sorted(name for name, distance in values.items() if distance < 0)
        if negative:
            msg = f"Negative distances in ts_geo_station_distance: {negative}"
            raise ValueError(msg)
        return values

    @field_validator("ts_geo_station_distance_resolution_factors", mode="before")
    @classmethod
    def validate_ts_geo_station_distance_resolution_factors_keys(cls, values: object) -> object:
        """Check the resolutions, which are a closed vocabulary like the unit types are.

        An empty value means no factors of one's own, and any other that is not a mapping is left
        for the field to refuse, as for `ts_geo_station_distance`.
        """
        if not values:
            return {}
        if not isinstance(values, Mapping):
            return values
        resolutions = {resolution.value for resolution in Resolution}
        unknown = sorted(set(values) - resolutions)
        if unknown:
            msg = f"Invalid resolutions in ts_geo_station_distance_resolution_factors: {unknown} not in {sorted(resolutions)}"  # noqa: E501
            raise ValueError(msg)
        return values

    @field_validator("ts_geo_station_distance_resolution_factors", mode="after")
    @classmethod
    def validate_ts_geo_station_distance_resolution_factors_values(cls, values: dict[str, float]) -> dict[str, float]:
        """Reject negative factors, which would turn a radius into a distance behind the point."""
        negative = sorted(name for name, factor in values.items() if factor < 0)
        if negative:
            msg = f"Negative factors in ts_geo_station_distance_resolution_factors: {negative}"
            raise ValueError(msg)
        return values

    @model_validator(mode="after")
    def expand_ts_geo_station_distance(self) -> Settings:
        """Layer the per-parameter overrides onto the two radii and the parameter table.

        Built here rather than in the field's default so that the two radii, which are fields of
        their own and may themselves be overridden, are already known.

        Runs more than once on the same instance -- every assignment to a field re-runs it
        (`validate_assignment`), as does `Settings.model_validate(settings)` -- so the overrides are
        captured only the first time. Expanding the expansion would take the whole table for
        overrides the user never wrote, which would then outrank a radius set afterwards. Re-running
        on assignment is also what makes a radius assigned reach the mapping at once.

        The mapping is written past validation: assigning it would validate it, which runs this
        validator again without end.
        """
        if self._ts_geo_station_distance_overrides is None:
            self._ts_geo_station_distance_overrides = dict(self.ts_geo_station_distance)
        self.__dict__["ts_geo_station_distance"] = _build_geo_station_distance(
            self.ts_geo_station_distance_homogeneous,
            self.ts_geo_station_distance_heterogeneous,
            self._ts_geo_station_distance_overrides,
        )
        return self

    @field_serializer("ts_geo_station_distance")
    def serialize_ts_geo_station_distance(self, _value: dict[str, float]) -> dict[str, float]:
        """Dump the overrides that were given, not the mapping they were expanded into.

        Dumping the expanded mapping would make the settings unable to round-trip: every
        heterogeneous parameter would come back as an explicit override and win over a
        `ts_geo_station_distance_heterogeneous` set alongside it, which is the very "set a number,
        nothing happens" failure the validation here is about.
        """
        return self._ts_geo_station_distance_overrides or {}

    def ts_geo_station_distance_resolution_factor(self, resolution: str) -> float:
        """Return the factor the heterogeneous radius is stretched by at this resolution."""
        return self.ts_geo_station_distance_resolution_factors.get(
            resolution,
            _STATION_DISTANCE_RESOLUTION_FACTORS.get(resolution, _STATION_DISTANCE_RESOLUTION_FACTOR_DEFAULT),
        )

    def ts_geo_station_distance_for(self, parameter_name: str, resolution: str) -> float:
        """Return how far a station may be to still be used for this parameter at this resolution.

        `ts_geo_station_distance` answers the same question without the resolution, which is the
        radius before it is scaled -- the radius at hourly resolution. A radius the user set for the
        parameter by hand is returned as it was given: a number written out means that number, at
        every resolution.

        The two radii and the factors are read here, so assigning to them on an existing `Settings`
        object takes effect at once. `ts_geo_station_distance` is not: the overrides are taken when
        the settings are built, and the mapping the field then holds is the expansion of them, so
        a new mapping assigned to it afterwards is checked and then discarded, the expansion being
        run again from the overrides the settings were built with. Build a new `Settings` to change
        the per-parameter radii.
        """
        overrides = self._ts_geo_station_distance_overrides or {}
        if parameter_name in overrides:
            return overrides[parameter_name]
        parameter = PARAMETERS.get(parameter_name)
        if parameter is None or parameter.interpolation != "heterogeneous":
            return self.ts_geo_station_distance_homogeneous
        return self.ts_geo_station_distance_heterogeneous * self.ts_geo_station_distance_resolution_factor(resolution)

    @property
    def ts_tidy(self) -> bool:
        """Return whether the time series is in tidy format."""
        return self.ts_shape == "long"

    @property
    def ts_drop_nulls_effective(self) -> bool:
        """Return whether rows without a value are dropped, which they are in the long shape alone.

        `ts_drop_nulls` keeps what the caller gave, and the wide shape does not turn it off: the
        field used to be rewritten to False, for good, so a `Settings` once wide dropped no nulls
        once it was long again (GH-2388). This is the value in effect.
        """
        return self.ts_drop_nulls and self.ts_tidy

    def model_post_init(self, _context: object, /) -> None:
        """Log what the settings were built with, once, as they are built.

        Not a model validator: those run again for every assignment (`validate_assignment`) and for
        `Settings.model_validate(settings)`, and logged these lines each time. So a field assigned
        afterwards -- `ts_shape` included -- logs nothing; the lines say how the settings began.
        """
        if self.ts_shape != "long":
            log.info(
                "option 'ts_drop_nulls' is only available with option 'ts_shape=long' and "
                "is thus ignored in this request.",
            )
        if self.cache_disable:
            log.info("Wetterdienst cache is disabled")
        else:
            log.info(f"Wetterdienst cache is enabled [CACHE_DIR:{self.cache_dir}]")

    def __repr__(self) -> str:
        """Return the settings as a JSON string."""
        return json.dumps(self.model_dump(mode="json"))

    def __str__(self) -> str:
        """Return the settings as a string."""
        return f"""Settings({json.dumps(self.model_dump(mode="json"), indent=4)})"""


def _describe_settings_error(error: ValidationError | SettingsError) -> list[str]:
    """Tell what is wrong with the settings, a line for each problem, by the `WD_*` variable that sets it.

    For an error of settings built from the environment and `.env` alone, as `check_settings`
    builds them. Neither hands on a key that is no setting (GH-2349), so every problem is a
    setting's.

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
            return [f"WD_{match.group(1).upper()} is invalid: not valid JSON"]
        return [str(error)]
    lines = []
    for problem in error.errors(include_url=False):
        # an element of a pair, such as the secret in `WD_AUTH__METNO_FROST`, is no variable of its
        # own, and is told by its index after the name that holds it: `WD_AUTH__METNO_FROST[1]`
        variable = "WD_" if problem["loc"] else "WD_*"
        for part in problem["loc"]:
            if isinstance(part, int):
                variable += f"[{part}]"
            else:
                variable += ("" if variable == "WD_" else "__") + str(part).upper()
        lines.append(f"{variable} is invalid: {problem['msg'].removeprefix('Value error, ')}")
    return lines


def check_settings() -> list[str]:
    """Build the settings from the environment and `.env` alone, and tell what is wrong with them.

    An empty list means they are valid.
    """
    try:
        Settings()
    except (ValidationError, SettingsError) as e:
        return _describe_settings_error(e)
    return []
