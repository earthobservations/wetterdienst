# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Options of a request: how the values come back, and how far a station may be to be interpolated from.

`Settings` is the host's configuration -- cache, network client, credentials -- and is read by the
providers. What is here is the request's: no provider reads it, only the values, the interpolation
and the summary do. The defaults come from the ``WD_TS_*`` variables, which `Settings` read as its
``ts_*`` settings until GH-2639, so an operator who set ``WD_TS_SHAPE`` changes nothing.
"""

from __future__ import annotations

import contextlib
import contextvars
import functools
import logging
from collections import defaultdict
from collections.abc import Iterator, Mapping
from typing import TYPE_CHECKING, Annotated, Any, Literal, Self, get_args

from pydantic import Field, PrivateAttr, field_serializer, field_validator, model_validator
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from wetterdienst.exceptions import InvalidEnumerationError
from wetterdienst.metadata.aliases import PARAMETER_ALIASES, use_alias
from wetterdienst.metadata.parameter_table import PARAMETER_TABLE, PARAMETERS
from wetterdienst.metadata.renamed import RENAMED_PARAMETERS, RENAMED_RESOLUTIONS
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.plausibility import ALL, Mode, Plausibility
from wetterdienst.model.unit import UnitConverter

if TYPE_CHECKING:
    from pydantic.fields import FieldInfo

log = logging.getLogger(__name__)

_UNIT_CONVERTER_TARGETS = UnitConverter().targets.keys()

#: the share of readings a station must cover not to be skipped: a threshold above 1 skips every
#: station, one of 0 or below none, so neither is one. The REST request model takes it too, so the
#: two cannot drift apart (GH-2334)
SkipThreshold = Annotated[float, Field(gt=0, le=1)]

#: how many days after its published end a station is still kept for a request window, at most: ten years,
#: which is more than the longest default (732 days, the annual index) several times over and leaves a typo
#: of a year in the wrong unit refused instead of keeping every station that ever reported. The REST request
#: model takes it too (GH-3220)
StationWindowEndBuffer = Annotated[int, Field(ge=0, le=3660)]

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
#: The factors are pure multipliers of whatever the heterogeneous radius says. A radius the user
#: raises is followed rather than clipped: they have made the terrain judgement the table encodes,
#: and a setting that silently does nothing is the failure this module validates against everywhere
#: else. The homogeneous radius does not scale at all -- terrain does not care how long a quantity
#: was accumulated for
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


#: whether `Options.replace` is building a copy, which reads from its fields alone and says nothing
#: a first instance has already said. A context variable so that threads and tasks do not see each other's
_REPLACING: contextvars.ContextVar[bool] = contextvars.ContextVar("wetterdienst_options_replacing", default=False)
#: whether the notices an instance gives as it is built -- the ignored `drop_nulls`, a radius for a
#: parameter never interpolated -- are held back, as for a copy and for the check of the environment,
#: which builds options only to see whether they are valid
_QUIET: contextvars.ContextVar[bool] = contextvars.ContextVar("wetterdienst_options_quiet", default=False)


@contextlib.contextmanager
def _quiet() -> Iterator[None]:
    """Build options without the notices they give as they are built, in this context alone."""
    token = _QUIET.set(True)
    try:
        yield
    finally:
        _QUIET.reset(token)


@functools.cache
def _reading_nested_as_json_would(source_class: type[PydanticBaseSettingsSource]) -> type[PydanticBaseSettingsSource]:
    """Give a source class the reading of a value nested too deeply as of one that is not valid JSON (GH-2543).

    The source decodes a dict, a pair or a nested setting as JSON before any validator sees it, and
    for text such as 100000 opening brackets the decoder raises a ``RecursionError``. That is no
    ``ValueError``, so it escaped the source's handling of text that is not JSON: it was neither
    kept as the raw text for the validator to refuse nor reported by `check_settings`, and
    ``Settings()`` raised it. As a ``ValueError`` it is dealt with as any other malformed value is.
    """

    # the base is a parameter: a source class of pydantic-settings, which this subclasses for every one it is given
    class Reading(source_class):  # ty: ignore[unsupported-base]
        def decode_complex_value(self, field_name: str, field: FieldInfo, value: Any) -> Any:  # noqa: ANN401
            # `WD_TS_PLAUSIBILITY=soft` is a mode for every check, no JSON: a check named in its own variable wins
            if field_name == "plausibility" and isinstance(value, (str, bytes)):
                bare = value.decode() if isinstance(value, bytes) else value
                if bare.strip() in get_args(Mode):
                    return {ALL: bare.strip()}
            try:
                return super().decode_complex_value(field_name, field, value)
            except RecursionError as error:
                msg = "nested too deeply to decode as JSON"
                raise ValueError(msg) from error

    Reading.__name__ = Reading.__qualname__ = source_class.__name__
    return Reading


def _decode_nested_as_json_would(source: PydanticBaseSettingsSource) -> PydanticBaseSettingsSource:
    """Give a source, as configured, the reading of `_reading_nested_as_json_would`."""
    source.__class__ = _reading_nested_as_json_would(type(source))
    return source


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


def _checked_unit_targets(values: dict[str, str]) -> dict[str, str]:
    """Check the unit targets, the units as well as the quantities.

    A unit the converter has no such name for, or holds back as one a source publishes in, used
    to pass here and be refused only once a values request had fetched its stations (GH-2306).
    """
    if not values:
        # the default, which every instance is built with, so no converter is built for it
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


def _checked_geo_station_distance_keys(values: object, prefix: str, logger: logging.Logger | None) -> object:
    """Check the overridden parameter names, which used to be taken on trust.

    A name that is not a canonical parameter can never be looked up, so the override silently
    did nothing and the parameter the user meant kept its default radius -- a typo was
    indistinguishable from having set nothing at all. An empty value means no overrides; any
    other that is not a mapping is left for the field to refuse, which names it, where looking
    for keys in it failed with a bare `TypeError` that named nothing (GH-2353).

    `prefix` is what the field's name starts with where it is given, so that the message names it
    as the caller wrote it. `logger` is where a radius for a parameter never interpolated is
    warned about, none to say nothing.
    """
    if not values:
        return {}
    if not isinstance(values, Mapping):
        return values
    if "default" in values:
        msg = (
            f"the 'default' key of {prefix}geo_station_distance is gone, as it replaced the fallback radius and "
            "the pre-populated per-parameter ones alike; set "
            f"{prefix}geo_station_distance_homogeneous and {prefix}geo_station_distance_heterogeneous instead"
        )
        raise ValueError(msg)
    values = _with_aliases_resolved(values, prefix, logger)
    unknown = sorted(set(values) - PARAMETERS.keys())
    if unknown:
        msg = f"Invalid parameters in {prefix}geo_station_distance: {unknown} not in the canonical parameters"
        renamed = [f"'{name}' is now '{RENAMED_PARAMETERS[name]}'" for name in unknown if name in RENAMED_PARAMETERS]
        if renamed:
            msg += f" ({', '.join(renamed)})"
        raise ValueError(msg)
    never_interpolated = sorted(name for name in values if not PARAMETERS[name].interpolation)
    if never_interpolated and logger is not None:
        logger.warning(
            f"option '{prefix}geo_station_distance' sets a radius for {never_interpolated}, which are never "
            "interpolated, and is thus ignored for them in this request.",
        )
    return values


def _with_aliases_resolved(
    values: Mapping[str, float], prefix: str, logger: logging.Logger | None
) -> Mapping[str, float]:
    """Write the new name for a key that is an alias of a name every dataset renamed, and warn that it was one.

    The warning is given where `logger` is, which is where the options are built for the caller: a copy made by
    `replace` and the first pass of `options_from_mapping` say nothing, so that an alias is told once. A parameter
    given under both names is refused, as which radius is meant cannot be told.

    Only an alias of every dataset (`PARAMETER_ALIASES`) is a name here: an alias of one dataset is the old name of a
    parameter that other datasets keep, so the key is a canonical name still, and sets the radius of those.
    """
    aliased = {name: PARAMETER_ALIASES[name] for name in values if name in PARAMETER_ALIASES and name not in PARAMETERS}
    if not aliased:
        return values
    for name, alias in aliased.items():
        if alias.new in values:
            msg = (
                f"{prefix}geo_station_distance gives '{name}', which was renamed to '{alias.new}', and "
                f"'{alias.new}' as well: give the radius of the parameter once, under '{alias.new}'"
            )
            raise ValueError(msg)
    if logger is not None:
        for name, alias in aliased.items():
            use_alias(name, alias)
    return {aliased[name].new if name in aliased else name: radius for name, radius in values.items()}


def _checked_geo_station_distance_values(values: dict[str, float], prefix: str) -> dict[str, float]:
    """Reject negative radii, as the distance to a nearby station next to it already does."""
    negative = sorted(name for name, distance in values.items() if distance < 0)
    if negative:
        msg = f"Negative distances in {prefix}geo_station_distance: {negative}"
        raise ValueError(msg)
    return values


def _checked_resolution_factors_keys(values: object, prefix: str) -> object:
    """Check the resolutions, which are a closed vocabulary like the unit types are.

    An empty value means no factors of one's own, and any other that is not a mapping is left
    for the field to refuse, as for the per-parameter radii.
    """
    if not values:
        return {}
    if not isinstance(values, Mapping):
        return values
    resolutions = {resolution.value for resolution in Resolution}
    unknown = sorted(set(values) - resolutions)
    if unknown:
        msg = f"Invalid resolutions in {prefix}geo_station_distance_resolution_factors: {unknown} not in {sorted(resolutions)}"  # noqa: E501
        renamed = [f"'{name}' is now '{RENAMED_RESOLUTIONS[name]}'" for name in unknown if name in RENAMED_RESOLUTIONS]
        if renamed:
            msg += f" ({', '.join(renamed)})"
        raise ValueError(msg)
    return values


def _checked_resolution_factors_values(values: dict[str, float], prefix: str) -> dict[str, float]:
    """Reject negative factors, which would turn a radius into a distance behind the point."""
    negative = sorted(name for name, factor in values.items() if factor < 0)
    if negative:
        msg = f"Negative factors in {prefix}geo_station_distance_resolution_factors: {negative}"
        raise ValueError(msg)
    return values


def _resolution_factor(factors: dict[str, float], resolution: str) -> float:
    """Return the factor the heterogeneous radius is stretched by at this resolution."""
    return factors.get(
        resolution,
        _STATION_DISTANCE_RESOLUTION_FACTORS.get(resolution, _STATION_DISTANCE_RESOLUTION_FACTOR_DEFAULT),
    )


def _station_distance_for(
    overrides: dict[str, float],
    homogeneous: float,
    heterogeneous: float,
    factors: dict[str, float],
    parameter_name: str,
    resolution: str,
) -> float:
    """Return how far a station may be to still be used for this parameter at this resolution.

    A radius set for the parameter by hand is returned as it was given: a number written out means
    that number, at every resolution.
    """
    if parameter_name in overrides:
        return overrides[parameter_name]
    parameter = PARAMETERS.get(parameter_name)
    if parameter is None or parameter.interpolation != "heterogeneous":
        return homogeneous
    return heterogeneous * _resolution_factor(factors, resolution)


def _note_drop_nulls_ignored(shape: str, prefix: str, logger: logging.Logger) -> None:
    """Log that dropping nulls does nothing in the wide shape."""
    if shape != "long":
        logger.info(
            f"option '{prefix}drop_nulls' is only available with option '{prefix}shape=long' and "
            "is thus ignored in this request.",
        )


class Options(BaseSettings):
    """How the values of a request come back and how its stations are chosen.

    ``plausibility`` names the mode of each check that judges a value (``Options(plausibility={"range": "soft"})``,
    ``WD_TS_PLAUSIBILITY__RANGE=soft``): a ``hard`` check nulls the value and keeps the number as
    ``rejected:<check>,raw:<number>`` in ``quality_flags``, a ``soft`` one keeps the value and flags it
    ``suspect:<check>`` (GH-3676). A check that is not named keeps its mode, from the environment or its default.

    The defaults are read from ``WD_TS_*`` (``WD_TS_SHAPE`` for `shape`), from the environment and
    from a ``.env``, so that an operator sets them once for the host. An instance is frozen:
    `replace` makes a changed copy, validated as a new one. The mappings it holds are not copied,
    so change them through `replace` and not in place.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        # read only the options from `.env`, as from the environment, as `Settings` does (GH-2349)
        dotenv_filtering="only_existing",
        env_ignore_empty=True,
        env_prefix="WD_TS_",
        env_nested_delimiter="__",
        frozen=True,
        extra="forbid",
        # the error does not repeat the value refused, as for `Settings` (GH-2435)
        hide_input_in_errors=True,
    )

    humanize: bool = True
    shape: Literal["wide", "long"] = "long"
    convert_units: bool = True
    unit_targets: dict[str, str] = Field(default_factory=dict)
    # skip a station whose requested parameters are covered too sparsely to be worth
    # returning. The coverage is measured against how many readings the requested window can
    # hold, so the option stands on its own and needs no particular shape of frame under it. A request
    # without a window is measured against the span of the station's series with its empty readings in
    # it, and a resolution with no fixed interval against the readings it has with them in, so
    # `drop_nulls` does not change which stations are skipped (GH-3578)
    skip_empty: bool = False
    skip_threshold: SkipThreshold = 0.95
    skip_criteria: Literal["min", "mean", "max"] = "min"
    drop_nulls: bool = True
    # how long after the end its catalogue publishes a station is still kept for a request window, in
    # days: the end a source publishes lags a station that is still reporting. None keeps the rule per
    # resolution (two days, 62 for monthly, 732 for annual: `wetterdienst.model.request.limit_to_window`),
    # 0 compares the end with the window exactly. The start the catalogue publishes is exact (its first
    # reading), so no buffer is taken on that side (GH-3220)
    station_window_end_buffer: StationWindowEndBuffer | None = None
    # how far a station may be from the target point to still be interpolated or summarized from.
    # the two radii follow `CanonicalParameter.interpolation`: a homogeneous quantity such as air
    # temperature varies slowly across a region and may be drawn from farther away than a
    # heterogeneous one such as precipitation, which decorrelates within a few tens of kilometres
    geo_station_distance_homogeneous: Annotated[float, Field(ge=0)] = _STATION_DISTANCE_HOMOGENEOUS
    geo_station_distance_heterogeneous: Annotated[float, Field(ge=0)] = _STATION_DISTANCE_HETEROGENEOUS
    # per-parameter overrides of the two radii above, given as canonical parameter names. holds the
    # overrides alone while validating and the mapping -- radii, table and overrides -- from
    # `expand_geo_station_distance` on. that mapping is the radius at hourly resolution;
    # `geo_station_distance_for` gives the one a request actually uses
    geo_station_distance: defaultdict[str, float] = Field(default_factory=dict)
    # how the heterogeneous radius grows with the accumulation period, keyed by resolution. Only
    # the resolutions named here differ from `_STATION_DISTANCE_RESOLUTION_FACTORS`; the rest keep
    # their factor, so the option stays the list of departures rather than all eleven
    geo_station_distance_resolution_factors: dict[str, float] = Field(default_factory=dict)
    #: what was passed for `geo_station_distance`, kept for serialization and re-expansion.
    #: `None` until the field has been expanded once -- an empty dict is a valid set of overrides
    _geo_station_distance_overrides: dict[str, float] | None = PrivateAttr(default=None)
    # this option is used to define how far away a station can be so that no interpolation is done
    # but instead the station is used directly
    geo_use_nearby_station_distance: Annotated[float, Field(ge=0)] | None = 1.0
    # this rather complicated option is used in the process of figuring out how many additional stations will be used
    # the gain defines how many additional timestamps can be interpolated by adding the specific station and thus
    # getting more timestamps with the required minimum of four values
    # so basically this option considers the extra effort against the gain of additional interpolated timestamps
    geo_min_gain_of_value_pairs: Annotated[float, Field(ge=0)] = 0.10
    # this option defines how many additional stations are used in the interpolation process independent of the gain
    # of value pairs, so if the gain is not reached anymore, there at least `num` more stations added to the list
    geo_num_additional_stations: Annotated[int, Field(ge=0)] = 3
    # the mode of every plausibility check, `hard` (null the value, keep the number as `rejected:<check>,raw:`) or
    # `soft` (keep the value, flag it `suspect:<check>`): the checks are the fields of `Plausibility`, set from
    # `WD_TS_PLAUSIBILITY__<CHECK>`. A check not named keeps its default (GH-3676)
    plausibility: Plausibility = Field(
        default_factory=Plausibility,
        description="What a plausibility check does to a value it finds implausible: `hard` nulls it and keeps the "
        "number as `rejected:<check>,raw:<number>` in `quality_flags`, `soft` keeps it and flags it "
        "`suspect:<check>`. One mode per check (`range`, `elevation`, `stuck`, `consistency`, `floor`), or a bare "
        "`soft` or `hard` for every check at once, which a check named beside it overrides; the "
        "missing-value codes a source documents are no check and are not configurable. Interpolation and "
        "summary always leave out a suspect value.",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],  # noqa: ARG003
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Take the sources as they are, but have the environment and `.env` refuse a value nested too deeply.

        A copy made by `replace` takes the fields it is given alone: the environment would otherwise
        be merged into a mapping handed over, and an override it set could not be taken away.
        """
        if _REPLACING.get():
            return (init_settings,)
        return (
            init_settings,
            _decode_nested_as_json_would(env_settings),
            _decode_nested_as_json_would(dotenv_settings),
            file_secret_settings,
        )

    @field_validator("unit_targets", mode="before")
    @classmethod
    def validate_unit_targets_before(cls, values: dict[str, str] | None) -> dict[str, str]:
        """Take no unit targets for none."""
        return values or {}

    @field_validator("unit_targets", mode="after")
    @classmethod
    def validate_unit_targets_after(cls, values: dict[str, str]) -> dict[str, str]:
        """Validate the unit targets, the units as well as the quantities."""
        return _checked_unit_targets(values)

    @field_validator("geo_station_distance", mode="before")
    @classmethod
    def validate_geo_station_distance_keys(cls, values: object) -> object:
        """Check the overridden parameter names."""
        return _checked_geo_station_distance_keys(values, "", None if _QUIET.get() else log)

    @field_validator("geo_station_distance", mode="after")
    @classmethod
    def validate_geo_station_distance_values(cls, values: dict[str, float]) -> dict[str, float]:
        """Reject negative radii."""
        return _checked_geo_station_distance_values(values, "")

    @field_validator("geo_station_distance_resolution_factors", mode="before")
    @classmethod
    def validate_geo_station_distance_resolution_factors_keys(cls, values: object) -> object:
        """Check the resolutions."""
        return _checked_resolution_factors_keys(values, "")

    @field_validator("geo_station_distance_resolution_factors", mode="after")
    @classmethod
    def validate_geo_station_distance_resolution_factors_values(cls, values: dict[str, float]) -> dict[str, float]:
        """Reject negative factors."""
        return _checked_resolution_factors_values(values, "")

    @model_validator(mode="after")
    def expand_geo_station_distance(self) -> Self:
        """Layer the per-parameter overrides onto the two radii and the parameter table.

        Built here rather than in the field's default so that the two radii, which are fields of
        their own and may themselves be overridden, are already known.

        Runs more than once on the same instance, as `Options.model_validate(options)` runs it
        again, so the overrides are captured only the first time: expanding the expansion would
        take the whole table for overrides the user never wrote, which would then outrank a radius
        given afterwards.

        The mapping is written past validation, as the instance is frozen.
        """
        if self._geo_station_distance_overrides is None:
            self._geo_station_distance_overrides = dict(self.geo_station_distance)
        self.__dict__["geo_station_distance"] = _build_geo_station_distance(
            self.geo_station_distance_homogeneous,
            self.geo_station_distance_heterogeneous,
            self._geo_station_distance_overrides,
        )
        return self

    @field_serializer("geo_station_distance")
    def serialize_geo_station_distance(self, _value: dict[str, float]) -> dict[str, float]:
        """Dump the overrides that were given, not the mapping they were expanded into.

        Dumping the expanded mapping would make the options unable to round-trip: every
        heterogeneous parameter would come back as an explicit override and win over a
        `geo_station_distance_heterogeneous` set alongside it, which is the very "set a number,
        nothing happens" failure the validation here is about.
        """
        return self._geo_station_distance_overrides or {}

    def geo_station_distance_resolution_factor(self, resolution: str) -> float:
        """Return the factor the heterogeneous radius is stretched by at this resolution."""
        return _resolution_factor(self.geo_station_distance_resolution_factors, resolution)

    def geo_station_distance_for(self, parameter_name: str, resolution: str) -> float:
        """Return how far a station may be to still be used for this parameter at this resolution.

        `geo_station_distance` answers the same question without the resolution, which is the
        radius before it is scaled -- the radius at hourly resolution. A radius the user set for the
        parameter by hand is returned as it was given: a number written out means that number, at
        every resolution.
        """
        return _station_distance_for(
            self._geo_station_distance_overrides or {},
            self.geo_station_distance_homogeneous,
            self.geo_station_distance_heterogeneous,
            self.geo_station_distance_resolution_factors,
            parameter_name,
            resolution,
        )

    @property
    def tidy(self) -> bool:
        """Return whether the time series is in tidy format."""
        return self.shape == "long"

    @property
    def drop_nulls_effective(self) -> bool:
        """Return whether rows without a value are dropped, which they are in the long shape alone.

        `drop_nulls` keeps what the caller gave, and the wide shape does not turn it off, so an
        option once wide dropped no nulls once it is long again (GH-2388). This is the value in
        effect.
        """
        return self.drop_nulls and self.tidy

    def replace(self, **changes: Any) -> Options:  # noqa: ANN401
        """Return a copy with `changes` made, validated as a new instance is.

        The copy is built from this one's fields alone, so neither the environment nor a `.env` is
        read again, and it logs nothing that a first instance has already said.
        """
        if not changes:
            return self
        changes = _with_plausibility_merged(changes, self.plausibility)
        token = _REPLACING.set(True)
        try:
            with _quiet():
                return type(self)(**{**self.model_dump(), **changes})
        finally:
            _REPLACING.reset(token)

    def model_post_init(self, _context: object, /) -> None:
        """Log what the options were built with, once, as they are built.

        Not a model validator: those run again for `Options.model_validate(options)`, and logged
        this line each time.
        """
        if not _QUIET.get():
            _note_drop_nulls_ignored(self.shape, "", log)

    def __hash__(self) -> int:
        """Hash the options by what they dump, the mappings they hold keeping the fields from being hashed."""
        return hash(self.model_dump_json())

    def __repr_args__(self) -> Iterator[tuple[str | None, Any]]:
        """Show the overrides that were given for `geo_station_distance`, not the table they expand into."""
        for name, value in super().__repr_args__():
            yield name, (self._geo_station_distance_overrides or {}) if name == "geo_station_distance" else value


def _with_plausibility_merged(changes: Mapping[str, Any], current: Plausibility) -> dict[str, Any]:
    """Lay the modes a caller names over the ones the options have, so that a check not named keeps its mode.

    The other options are replaced wholesale, as they are named. The checks are independent of one another, so naming
    one is not a statement about the rest (GH-3676): ``replace(plausibility={"range": "soft"})`` leaves ``stuck`` as it
    was. What is not a mapping is left for the field to refuse.
    """
    named = changes.get("plausibility")
    if isinstance(named, Mapping):
        return {**changes, "plausibility": {**current.model_dump(), **named}}
    return dict(changes)


def _options_from_fields(fields: Mapping[str, Any]) -> Options:
    """Build options from their fields alone, neither the environment nor a ``.env`` read, and with no notice given."""
    token = _REPLACING.set(True)
    try:
        with _quiet():
            return Options(**fields)
    finally:
        _REPLACING.reset(token)


def options_from_mapping(given: Mapping[str, Any], base: Options | None = None) -> Options:
    """Build options from the ones a caller names, the rest as ``Options()`` has them.

    The environment sets what is not named, as it does for ``Options()``; what is named replaces its
    default wholesale. ``Options(**given)`` would merge the environment into a mapping that was
    named -- a ``WD_TS_UNIT_TARGETS`` the caller never meant to keep would add to theirs -- so the
    named options are laid over a base the environment has already shaped, as `Options.replace` does.
    A shape that drops no nulls and a radius for a parameter never interpolated are noted, as they
    are for options built the usual way. `base` is the ``Options()`` of the environment, for a
    caller that has built it already.
    """
    if base is None:
        with _quiet():
            base = Options()
    options = _options_from_fields({**base.model_dump(), **_with_plausibility_merged(given, base.plausibility)})
    if options.shape != base.shape:
        _note_drop_nulls_ignored(options.shape, "", log)
    if "geo_station_distance" in given:
        _checked_geo_station_distance_keys(given["geo_station_distance"], "", log)
    return options


def resolve_options(options: Options | Mapping[str, Any] | None) -> Options:
    """Settle the options of a request from what it was given.

    None gives the options of the environment and ``.env``. A mapping gives `options_from_mapping`,
    and an `Options` is used as it is.
    """
    if options is None:
        with _quiet():
            return Options()
    if isinstance(options, Options):
        return options
    return options_from_mapping(options)
