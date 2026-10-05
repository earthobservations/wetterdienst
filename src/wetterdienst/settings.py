# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Settings for the wetterdienst package."""

from __future__ import annotations

import json
import logging
import platform
import re
from collections import defaultdict
from collections.abc import Mapping
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

#: what a credential may arrive as: the text of one, or one that has already been validated once
_Secretish = str | SecretStr

#: the share of readings a station must cover not to be skipped: a threshold above 1 skips every
#: station, one of 0 or below none, so neither is one. The REST request model takes it too, so the
#: two cannot drift apart (GH-2334)
SkipThreshold = Annotated[float, Field(gt=0, le=1)]


def _as_given(value: object) -> _Secretish:
    """Pass a secret through as it is, and anything else on as text for the field to wrap.

    ``str()`` of a ``SecretStr`` is its mask, so a pair that has already been validated once --
    which is what a ``model_dump()`` round-trip hands back -- would come back as ten asterisks and
    fail at the provider later with nothing to say why. The single-valued fields never had this to
    worry about: pydantic passes an existing secret straight through.
    """
    return value if isinstance(value, SecretStr) else str(value)


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
    model_config = ConfigDict(validate_assignment=True)

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

    @field_validator("metno_frost", mode="before")
    @classmethod
    def validate_metno_frost(
        cls,
        value: object,
    ) -> object:
        """Parse the Frost (client_id, secret) pair, a lone client id counting as one with no secret.

        An all-digit client id arrives as an `int`, as the environment decodes a nested value as JSON
        where it parses, and is still an id. Any other value that is not a pair is left for the field
        to refuse, which names it, where reading it as one failed with a bare `TypeError` (GH-2379).
        """
        if value is None:
            return None
        if isinstance(value, int) and not isinstance(value, bool):
            value = str(value)
        if isinstance(value, (str, SecretStr)):
            return value, ""
        if not isinstance(value, (tuple, list)):
            return value
        as_tuple = tuple(value)
        if len(as_tuple) != 2:
            msg = f"metno_frost must be a (client_id, secret) pair, got {len(as_tuple)} element(s)"
            raise ValueError(msg)
        return _as_given(as_tuple[0]), _as_given(as_tuple[1])

    @field_validator("ceda", mode="before")
    @classmethod
    def validate_ceda(
        cls,
        value: object,
    ) -> object:
        """Parse the CEDA (username, password) pair, e.g. from ``WD_AUTH__CEDA=username:password``.

        A value that is neither that text nor a pair -- a number or `true`, which the environment
        decodes as JSON -- is left for the field to refuse, which names it, where reading it as a
        pair failed with a bare `TypeError` (GH-2379).
        """
        if value is None:
            return None
        if isinstance(value, SecretStr):
            # the pair given as a single secret: read it out to split it, and the halves are wrapped
            # again by the field
            value = value.get_secret_value()
        if isinstance(value, str):
            username, sep, password = value.partition(":")
            if not sep:
                msg = "ceda must be given as 'username:password'"
                raise ValueError(msg)
            return username, password
        if not isinstance(value, (tuple, list)):
            return value
        as_tuple = tuple(value)
        if len(as_tuple) != 2:
            msg = f"ceda must be a (username, password) pair, got {len(as_tuple)} element(s)"
            raise ValueError(msg)
        return _as_given(as_tuple[0]), _as_given(as_tuple[1])


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
    )

    cache_disable: bool = Field(default=False)
    cache_dir: Path = Field(default_factory=lambda: Path(platformdirs.user_cache_dir(appname="wetterdienst")))
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

        Runs more than once on the same instance -- `Settings.model_validate(settings)` re-runs
        every after-validator, and `TimeseriesRequest` does exactly that -- so the overrides are
        captured only the first time. Expanding the expansion would take the whole table for
        overrides the user never wrote, which would then outrank a radius set afterwards. Every
        assignment to a field runs it again too, so a radius assigned reaches the mapping at once.

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

    @model_validator(mode="after")
    def validate(self) -> Settings:
        """Validate the settings."""
        if self.ts_shape != "long":
            log.info(
                "option 'ts_drop_nulls' is only available with option 'ts_shape=long' and "
                "is thus ignored in this request.",
            )
        if self.cache_disable:
            log.info("Wetterdienst cache is disabled")
        else:
            log.info(f"Wetterdienst cache is enabled [CACHE_DIR:{self.cache_dir}]")
        return self

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

    pydantic's own account names the field rather than the variable an operator set, and repeats
    the value given -- which for `WD_AUTH__*` is a credential, and for `WD_FSSPEC_CLIENT_KWARGS`
    may hold request headers. Here each problem is the variable and pydantic's message, without
    the input it echoes (GH-2335). A validator's own message may still name what it refuses -- a
    unit or a parameter name -- which none of those on the credentials or the headers does.
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
        variable = "WD_" + "__".join(str(part) for part in problem["loc"]).upper() if problem["loc"] else "WD_*"
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
