# Copyright (c) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Metadata models for a provider."""

from __future__ import annotations

import difflib
import logging
import re
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Annotated, Any, Literal, NotRequired, TypeVar, cast

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SerializerFunctionWrapHandler,
    SkipValidation,
    field_validator,
    model_serializer,
    model_validator,
    with_config,
)
from pydantic.json_schema import SkipJsonSchema  # noqa: TC002, needed at runtime by pydantic
from pydantic_extra_types.timezone_name import (
    TimeZoneName,  # noqa: TC002, needs to stay here for pydantic model to work
)

# not `typing.TypedDict`: pydantic refuses that as a response model on Python below 3.12 (GH-2090)
from typing_extensions import TypedDict

from wetterdienst.exceptions import InvalidEnumerationError, InvalidParameterError
from wetterdienst.metadata.aliases import find_alias, use_alias
from wetterdienst.metadata.parameter_table import PARAMETERS
from wetterdienst.metadata.period import Period  # noqa: TC001, needs to stay here for pydantic model to work
from wetterdienst.metadata.renamed import RENAMED_PARAMETERS, RENAMED_PARAMETERS_IN_DATASET, RENAMED_RESOLUTIONS
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.metadata.unit_type import UnitType  # noqa: TC001, needs to stay here for the TypedDicts to work

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pydantic_core.core_schema import ValidationInfo

    from wetterdienst.model.request import _PARAMETER_TYPE

log = logging.getLogger(__name__)

POSSIBLE_SEPARATORS = ("/", ".", ":")

# for any provider that does not publish their data under a dedicated dataset name
DATASET_NAME_DEFAULT = "data"

# how close a typo has to be before it is offered as "did you mean"
_SUGGESTION_CUTOFF = 0.6

_EXPECTED_PARAMETER = (
    "a 'resolution/dataset' or 'resolution/dataset/parameter' string, a tuple of its parts, "
    "a DatasetModel or a ParameterModel"
)


#: what the data of a timeseries network is: measured (`observation`), forecast, or computed from
#: measurements (`derived`). A timeseries network has stations, values and a metadata model.
TimeseriesKind = Literal["observation", "forecast", "derived"]

#: what a network in the registry is: a timeseries network of one of the `TimeseriesKind`s, or a standalone one,
#: which has its own request class and result and no stations or values to request (the radar products and the
#: warnings of `dwd`). Which one decides where a network can be requested: see `Wetterdienst.discover()`.
NetworkKind = Literal["observation", "forecast", "derived", "radar", "alerts"]

#: the continents a network can have stations on (Europe and Asia are two, as the station lists treat them)
Continent = Literal["africa", "antarctica", "asia", "europe", "north_america", "oceania", "south_america"]

#: how far a network reaches: `global` (stations on at least five continents), `national` (one country, with its
#: territories) or `regional` (everything between: one or several countries or continents); see `Extent`
ExtentScope = Literal["global", "national", "regional"]

#: the box of the Earth, `[west, south, east, north]`, which the bbox of a global network is
WORLD_BBOX = (-180.0, -90.0, 180.0, 90.0)


# what a member of the extent says, in the schema of `/api/coverage` and `/api/providers` alike
_SCOPE = (
    "How far the network reaches: `global` (stations on at least five continents), `national` (one country, with its "
    "territories) or `regional` (everything between: one or several countries or continents)."
)
_CONTINENTS = (
    "The continents the network is meant to serve, as the provider's own areas say: descriptive, so that a few "
    "outlying territories may be named or left out. `bbox` and the station lists are the exact answer."
)
_COUNTRIES = (
    "ISO 3166-1 alpha-2 codes of the countries a `regional` network is bound to, where that list is short and exact. "
    "Left out of an answer where empty, and for `national`: the country is the `country_code` of the provider."
)
_BBOX = (
    "`[west, south, east, north]` in degrees, around every station of the network (the Earth for `global`). It does "
    "not cross the antimeridian: a network with stations on both sides of it has the wide box."
)


# What `Wetterdienst.discover()` and `TimeseriesRequest.discover()` answer, and the REST API's
# `/api/coverage` describes: the tests check a real answer of every provider against these, and
# `extra="forbid"` makes a key added there fail.
@with_config(ConfigDict(extra="forbid"))
class CoverageNetwork(TypedDict):
    """A network in the list of every provider and its networks.

    Whether the credentials are accepted is not in it: that takes a request to the provider, which a list of
    every provider does not make, and `/api/auth` answers it for one network (GH-2564, GH-2641).
    """

    # a network that cannot be imported on this server is not listed at all (GH-2801)
    name_short: str
    country: str
    # `observation`, `forecast` and `derived` are the timeseries networks, which have stations and values; `radar`
    # and `alerts` are standalone, and the endpoints of the timeseries refuse them with a 404
    kind: NetworkKind
    # how far the network reaches, not where its provider is: this list is kept short, so it has the scope only, and the
    # full extent is in `/api/providers` and, for each dataset, in the coverage of one network (GH-3456)
    scope: ExtentScope
    url: str
    auth: bool
    configured: bool
    date_required: bool


@with_config(ConfigDict(extra="forbid"))
class ExtentDict(TypedDict):
    """`Extent` as `Wetterdienst.discover()` and `TimeseriesRequest.discover()` give it: a plain dict, as JSON has it.

    `country_codes` is left out where there are none and for a national network, and a whole degree has no `.0`
    (`Extent.model_dump(mode="json")`). The REST API describes the same member by `Extent`, in its own types.
    """

    scope: ExtentScope
    continents: list[Continent]
    country_codes: NotRequired[list[str]]
    bbox: list[float]


@with_config(ConfigDict(extra="forbid"))
class CoverageParameter(TypedDict):
    """A parameter of a dataset, with the unit its values come back in and, where it differs, the provider's.

    `unit` is the unit of the values for a caller who passes no options: the target of the `unit_type`, the one
    `glossary` gives (`degree_celsius` for a temperature, `decimal` (0 to 1) for a percentage), under the
    environment's `unit_targets` and `convert_units`. A `unit_targets` a caller passes to `values` is not
    followed: `coverage` takes no options. `unit_source` is the unit the provider publishes the parameter in
    (`degree_kelvin`, `percent`), which the values come in with `convert_units` off. Absent: the same as `unit`.
    """

    name: str
    name_original: str
    unit_type: UnitType
    unit: str
    unit_source: NotRequired[
        Annotated[
            str,
            Field(
                description="The unit the provider publishes the parameter in, which the values come in with "
                "`convert_units` off. Absent: the same as `unit`.",
            ),
        ]
    ]
    description: str | None
    # `dwd/dmo` only: the lead times whose run carries the parameter, `short` before `long`
    lead_times: NotRequired[list[Literal["short", "long"]]]


@with_config(ConfigDict(extra="forbid"))
class CoverageDataset(TypedDict):
    """A dataset of a resolution."""

    description: str | None
    parameters: list[CoverageParameter]
    # where the stations of the dataset are (GH-3456): its own where they are fewer than its network's (`dwd/dmo`
    # `icon_eu`), else the network's
    extent: ExtentDict


@with_config(ConfigDict(extra="forbid"))
class CoverageResolution(TypedDict):
    """A resolution of a network."""

    description: str | None
    datasets: dict[str, CoverageDataset]


# any of the three models that carry a canonical and a source name and are looked up by either
_NamedModel = TypeVar("_NamedModel", "ResolutionModel", "DatasetModel", "ParameterModel")


def _names(model: _NamedModel) -> tuple[str, ...]:
    """All lowercase names a model may be addressed by.

    That is the canonical name and the source's own name, plus for a resolution the name of the
    ``Resolution`` enum member ("minute_1" next to "1_minute"), which is what a user reading the
    enum rather than the docs is likely to type.
    """
    names = (model.name.lower(), model.name_original.lower())
    if isinstance(model, ResolutionModel):
        return (*names, model.value.name.lower())
    return names


def _find(models: Iterable[_NamedModel], item: str) -> _NamedModel | None:
    """Find a model by any of its names, case-insensitively, or return None."""
    item_search = item.strip().lower()
    for model in models:
        if item_search in _names(model):
            return model
    return None


# a `_mean_` temperature of a reading, not of an extreme: `temperature_air_mean_2m`,
# `temperature_soil_mean_0_05m`, `temperature_surface_mean`, `error_absolute_temperature_air_mean_2m`.
# `temperature_air_max_2m_mean` (the mean of the daily maxima) is none: no spot name succeeds it
_MEAN_OF_A_READING = re.compile(r"^((?:error_absolute_)?temperature_[a-z_]+?)_mean((?:_\d+(?:_\d+)?m)?)$")


# the resolutions from which a source that says nothing about the statistic keeps the `_mean_` name
_COARSE_RESOLUTIONS = frozenset({"daily", "monthly", "annual"})


def _spot_name(name: str) -> str | None:
    """Name the reading at one moment that a sub-daily `_mean_` temperature became, or None.

    A sub-daily temperature whose source states no mean is named `temperature_air_2m`, no longer
    `temperature_air_mean_2m` (GH-2651, GH-2657). Which datasets that moved is not declared
    anywhere, so the caller keeps the candidate only where the dataset has it.
    """
    match = _MEAN_OF_A_READING.match(name)
    return f"{match.group(1)}{match.group(2)}" if match else None


def _renamed_hint(item: str, canonical: Iterable[str], dataset: DatasetModel | None) -> str:
    """Name what a parameter the dataset does not have is called there, or return nothing.

    Looked up in this order, and only where the dataset has the name offered, so that the hint
    never sends a caller to a parameter that is not there:

    1. the rename declared for this dataset (`RENAMED_PARAMETERS_IN_DATASET`), for a name another
       dataset of the provider still has: `wind_speed` is `wind_speed_mean_last_10min` in
       `hourly/data` but stays `wind_speed` in `daily/data`;
    2. the rename for 1.0 that holds everywhere (`RENAMED_PARAMETERS`), followed once through the
       rename declared for this dataset where the dataset lacks its target: a misspelling of before
       0.139.0 (`soil_moisture_gras_sand_00cm_60cm`) is renamed to the daily name
       (`soil_moisture_grass_sand_00cm_60cm`), which `monthly/soil` has as a mean (GH-3276);
    3. the spot name of a sub-daily `_mean_` temperature, which no table lists since the move
       covers the sub-daily temperatures of most providers (GH-2673).

    The first two say "renamed", the third does not: a dataset that never had the `_mean_` name was
    not renamed, but is the one place the caller means. What none of them can name is a guess for
    the caller to weigh, which is the difflib one in the message.
    """
    # canonical names only: a source's own name may resolve to another parameter (Frost's `wind_speed`)
    names = set(canonical)
    in_dataset: dict[str, str] = {}
    if dataset is not None and dataset.resolution is not None:
        resolution = dataset.resolution
        in_dataset = (
            RENAMED_PARAMETERS_IN_DATASET.get(resolution.metadata_name, {}).get((resolution.name, dataset.name)) or {}
        )
        new = in_dataset.get(item)
        if new in names:
            return f" It was renamed to '{new}' in this dataset."
    new = RENAMED_PARAMETERS.get(item)
    if new in names:
        # a name this dataset had, renamed for 1.0: say so rather than guess at a near spelling
        return f" It was renamed to '{new}'."
    # the name it was renamed to everywhere is one the dataset lacks and renamed again: follow it once
    new = in_dataset.get(new) if new else None
    if new in names:
        return f" It was renamed to '{new}'."
    spot = _spot_name(item)
    # a daily or coarser `_mean_` is a mean of the interval where the source says so, not a renamed one
    coarse = dataset is not None and dataset.resolution is not None and dataset.resolution.name in _COARSE_RESOLUTIONS
    if spot in names and not coarse:
        return f" It is named '{spot}' here, a reading at one moment, not a mean."
    return ""


# the leading tokens of a parameter name that say which quantity it is: `temperature_dew`
# (`temperature_dew_point_mean_2m`), `wind_gust` (`wind_gust_max`). `error_absolute_` is no quantity
# but says the name is the error of one, so the tokens after it are the quantity and the prefix must agree
_QUANTITY_TOKENS = 2
_ERROR_PREFIX = ("error", "absolute")
# how close two such tokens have to be to count as one spelled wrongly ("sped", "realtive")
_TOKEN_CUTOFF = 0.75
# the token that makes a name the gust of a quantity, whatever the quantity tokens before it: `wind_direction_gust_max`
# is the direction of the gust, `wind_direction_mean_last_10min` that of the mean wind (GH-3009)
_GUST_TOKEN = "gust"  # noqa: S105


def _same_token(a: str, b: str) -> bool:
    """Say whether two name tokens are one, up to a misspelling."""
    return a == b or difflib.SequenceMatcher(None, a, b).ratio() >= _TOKEN_CUTOFF


def _split_error_prefix(name: str) -> tuple[bool, list[str]]:
    """Return whether `name` is the error of a quantity (even misspelled), and its tokens after the prefix."""
    tokens = name.split("_")
    if len(tokens) > len(_ERROR_PREFIX) and all(_same_token(a, b) for a, b in zip(tokens, _ERROR_PREFIX, strict=False)):
        return True, tokens[len(_ERROR_PREFIX) :]
    return False, tokens


def _keeps_the_quantity(item: str, candidate: str) -> bool:
    """Say whether `candidate` leads with the same quantity as `item`, up to a misspelled token.

    The difflib guess is made over the whole name, and a long name that differs in its first tokens
    can still be the closest: `temperature_dew_point_mean_2m` is nearer to `temperature_air_mean_2m`
    than to anything else a dataset without the dew point holds, and the air temperature is no dew
    point (GH-2924). So a guess is offered only where the tokens that name the quantity agree. What
    follows them, the statistic and the level, is not compared: `temperature_air_max_0_05m` may still
    be answered with the minimum. The gust is the exception: it is compared wherever it stands, as the direction
    of a gust is no direction of the wind (GH-3009).

    A name of one token (`rsk`, a source's own code, or `pressure`) has no quantity tokens to compare, and a missing
    underscore (`windspeed`) is a typo of the whole name, not of a token.
    """
    if item.replace("_", "") == candidate.replace("_", ""):
        return True
    item_error, item_tokens = _split_error_prefix(item)
    candidate_error, candidate_tokens = _split_error_prefix(candidate)
    if item_error != candidate_error:
        return False
    if len(item_tokens) == 1 or len(candidate_tokens) == 1:
        return True
    leading = zip(item_tokens[:_QUANTITY_TOKENS], candidate_tokens[:_QUANTITY_TOKENS], strict=False)
    if not all(_same_token(a, b) for a, b in leading):
        return False
    # the quantity tokens agree (`wind_direction`), but the direction of a gust is not that of the mean wind
    return _names_a_gust(item_tokens) == _names_a_gust(candidate_tokens)


def _names_a_gust(tokens: list[str]) -> bool:
    """Say whether a name is the gust of a quantity, up to a misspelled token."""
    return any(_same_token(token, _GUST_TOKEN) for token in tokens)


def _not_found(kind: str, item: str, models: Iterable[_NamedModel], dataset: DatasetModel | None = None) -> str:
    """Build the message for a name that no model matched.

    Names a close match where there is one, because the common failure is a typo or a name taken
    from another provider, and the available-names list alone leaves the user to spot the
    difference themselves. A parameter's close match has to be of the same quantity (see
    `_keeps_the_quantity`); where it is not, nothing is guessed. A parameter that is called
    something else in this dataset is answered with its name there instead of a guess (see
    `_renamed_hint`); `dataset` is the one a parameter was looked up in.
    """
    models = list(models)
    candidates = sorted({name for model in models for name in _names(model)})
    item_search = str(item).strip().lower()
    suggestion = (
        _renamed_hint(item_search, {model.name.lower() for model in models}, dataset) if kind == "parameters" else ""
    )
    if kind == "resolutions" and RENAMED_RESOLUTIONS.get(item_search) in candidates:
        suggestion = f" It was renamed to '{RENAMED_RESOLUTIONS[item_search]}'."
    if not suggestion:
        if kind == "parameters":
            # a near spelling of another quantity is no hint, the list of available names is the answer then
            candidates = [candidate for candidate in candidates if _keeps_the_quantity(item_search, candidate)]
        close = difflib.get_close_matches(item_search, candidates, n=1, cutoff=_SUGGESTION_CUTOFF)
        suggestion = f" Did you mean '{close[0]}'?" if close else ""
    available = ", ".join(
        f"{model.name}/{model.name_original}" if model.name != model.name_original else model.name for model in models
    )
    return f"'{item}'.{suggestion} Available {kind}: {available}"


def is_quality_flag(parameter: ParameterModel) -> bool:
    """Say whether a parameter is a quality flag of the source: `quality` or a `quality_*` of the canonical table."""
    return parameter.name.startswith("quality")


class ParameterModel(BaseModel):  # noqa: PLW1641
    """Parameter model for a provider.

    A provider declares only what it itself knows: the canonical ``name`` as a foreign key into
    ``PARAMETERS``, the source's own ``name_original`` and the source's ``unit``. The ``unit_type``
    is a property of the measured quantity rather than of the provider, so it is read from the
    canonical table instead of being declared -- see ``unit_type`` below.
    """

    model_config = ConfigDict(extra="forbid")

    name: str
    name_original: str
    unit: str
    description: str | None = None
    # the back-reference its dataset sets once it holds this parameter, so it is None until then; typing
    # it optional would put a None check in front of every read of `parameter.dataset`
    dataset: SkipValidation[DatasetModel] = Field(default=None, exclude=True, repr=False)  # ty: ignore[invalid-assignment]

    @property
    def unit_type(self) -> UnitType:
        """The unit type of the measured quantity, from the canonical parameter table.

        Resolved on access rather than at import, so an unknown name is caught by
        ``tests/test_api.py::test_metadata_parameter_table`` rather than by every user paying a
        table lookup per declaration on every interpreter start.

        A plain property rather than a ``computed_field``, so it does not reappear in
        ``model_dump()``. It is derived from ``name``, and re-emitting it per declaration would
        put back at the serialization layer the duplication this model exists to remove. Callers
        that want it from a dump can look the name up in ``PARAMETERS``; ``discover()`` and the
        REST and CLI responses build their own dicts and report it as before.
        """
        try:
            return PARAMETERS[self.name].unit_type
        except KeyError:
            msg = f"'{self.name}' is not a canonical parameter name"
            raise KeyError(msg) from None

    def __eq__(self, other: object) -> bool:
        """Compare two parameters."""
        if not isinstance(other, ParameterModel):
            return False
        return (
            self.name == other.name
            and self.name_original == other.name_original
            # unit_type is derived from name, so comparing it would be redundant
            and self.unit == other.unit
            and self.description == other.description
            # don't compare the dataset object itself because it'd be circular
            and self.dataset.name == other.dataset.name
            and self.dataset.resolution.name == other.dataset.resolution.name
        )


_COUNTRY_CODE = re.compile(r"[A-Z]{2}")


# Where the stations of a network are (GH-3456). The `country` of a provider is the country of the agency that runs it
# and says nothing of that: the forecast lists of `dwd/mosmix` have stations on every continent. A network declares
# its extent once, in its metadata, and the tests hold the declaration to its station list where it can be read: the
# box contains every station and is no wider than the stations by more than `EXTENT_SLACK`, a global network has
# stations on five continents. The `continents` are declared by hand, as the areas the network is meant to serve (a
# few outlying territories may be named or left out), and checked in one direction: each has a station within a
# margin of its box. A dataset whose list is narrower than its network's declares an extent of its own, which lies
# within the network's, and a dataset of a national network is national.
class Extent(BaseModel):
    """Where the stations of a network are, which the country of its provider does not say."""

    model_config = ConfigDict(extra="forbid", frozen=True, title="Extent")

    scope: ExtentScope = Field(description=_SCOPE)
    # tuples, so that an extent is hashable as the frozen model it is (and `ProviderTerms` with it); arrays in JSON
    continents: tuple[Continent, ...] = Field(min_length=1, description=_CONTINENTS)
    country_codes: tuple[str, ...] = Field(default=(), description=_COUNTRIES)
    bbox: tuple[float, ...] = Field(min_length=4, max_length=4, description=_BBOX)

    @field_validator("continents")
    @classmethod
    def _validate_continents(cls, value: tuple[Continent, ...]) -> tuple[Continent, ...]:
        """Refuse a continent named twice."""
        if len(set(value)) != len(value):
            msg = f"continents names a continent twice: {list(value)}"
            raise ValueError(msg)
        return value

    @field_validator("country_codes")
    @classmethod
    def _validate_country_codes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        """Refuse a code that is no two capital letters, and a country named twice."""
        for code in value:
            if not _COUNTRY_CODE.fullmatch(code):
                msg = f"{code!r} is no ISO 3166-1 alpha-2 code: two capital letters"
                raise ValueError(msg)
        if len(set(value)) != len(value):
            msg = f"country_codes names a country twice: {list(value)}"
            raise ValueError(msg)
        return value

    @field_validator("bbox")
    @classmethod
    def _validate_bbox(cls, value: tuple[float, ...]) -> tuple[float, ...]:
        """Refuse a box that is not `[west, south, east, north]` on Earth, with the west not east of the east."""
        west, south, east, north = value
        if not (-180 <= west <= east <= 180 and -90 <= south <= north <= 90):
            msg = f"bbox {list(value)} is no [west, south, east, north] on Earth, with west <= east and south <= north"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _validate_scope(self) -> Extent:
        """Hold the scope to what it says of the countries, continents and box."""
        problems = []
        if self.scope == "national" and len(self.country_codes) > 1:
            problems.append("a national network is one country's")
        if self.scope == "global":
            if self.country_codes:
                problems.append("a global network is bound to no country")
            if tuple(self.bbox) != WORLD_BBOX:
                problems.append(f"a global network has the box of the Earth {list(WORLD_BBOX)}")
            if len(self.continents) < 5:
                problems.append("a global network has stations on at least five continents")
        if self.scope == "regional":
            if len(self.country_codes) == 1:
                problems.append("a regional network is bound to no single country, which is a national one")
            if not self.country_codes and tuple(self.bbox) == WORLD_BBOX and len(self.continents) >= 5:
                problems.append("a network of the box of the Earth and five continents is a global one")
        if problems:
            msg = f"extent {self.scope!r}: {'; '.join(problems)}"
            raise ValueError(msg)
        return self

    # No return annotation, on purpose: pydantic makes the schema of an answer from it, and any type but the model's
    # own would take the members out of the OpenAPI document. In an answer the extent is kept short (GH-3456): no
    # `country_codes` where there are none or for a national network (the country is the provider's `country_code`), and
    # a whole degree without its `.0`.
    @model_serializer(mode="wrap", when_used="json")
    def _report(self, handler: SerializerFunctionWrapHandler):  # noqa: ANN202
        """Leave out of an answer what the rules above say already."""
        serialized = handler(self)
        if self.scope == "national" or not self.country_codes:
            serialized.pop("country_codes", None)
        serialized["bbox"] = [int(value) if float(value).is_integer() else value for value in serialized["bbox"]]
        return serialized

    def same_as(self, other: Extent) -> bool:
        """Tell whether two extents say the same, whatever the order they name the continents and countries in."""
        return (
            self.scope == other.scope
            and set(self.continents) == set(other.continents)
            and set(self.country_codes) == set(other.country_codes)
            and self.bbox == other.bbox
        )


class DatasetModel(BaseModel):  # noqa: PLW1641
    """Dataset model for a provider."""

    model_config = ConfigDict(extra="forbid")

    name: str
    name_original: str
    grouped: bool  # if parameters are grouped together e.g. in one file
    periods: list[Period]
    description: str | None = None
    date_required: bool
    parameters: list[ParameterModel]
    #: where the stations of the dataset are where that is less than the network's (`dwd/dmo` is global, its `icon_eu`
    #: dataset is Europe): null for a dataset that has the extent of its network (GH-3456)
    extent: Extent | SkipJsonSchema[None] = None
    # the back-reference its resolution sets once it holds this dataset (see `ParameterModel.dataset`)
    resolution: SkipValidation[ResolutionModel] = Field(default=None, exclude=True, repr=False)  # ty: ignore[invalid-assignment]

    def __init__(self, **data: Any) -> None:  # noqa: ANN401
        """Initialize the dataset model."""
        super().__init__(**data)
        for parameter in self.parameters:
            parameter.dataset = self

    def __eq__(self, other: object) -> bool:
        """Compare two datasets."""
        if not isinstance(other, DatasetModel):
            return False
        return (
            self.name == other.name
            and self.name_original == other.name_original
            and self.grouped == other.grouped
            and self.periods == other.periods
            and self.description == other.description
            and self.parameters == other.parameters
            # don't compare the resolution object itself because it'd be circular
            and self.resolution.name == other.resolution.name
        )

    def __getitem__(self, item: str | int) -> ParameterModel:
        """Get a parameter by name."""
        if isinstance(item, int):
            return self.parameters[item]
        parameter = _find(self.parameters, item)
        if parameter is None:
            parameter = self._aliased(item)
        if parameter is None:
            # the parameters of the dataset are those it iterates over, which the message lists (GH-2641)
            raise KeyError(_not_found("parameters", item, self, self))
        return parameter

    def __getattr__(self, item: str) -> ParameterModel:
        """Get a parameter by name."""
        parameter = _find(self.parameters, item)
        if parameter is None:
            parameter = self._aliased(item)
        if parameter is None:
            raise AttributeError(_not_found("parameters", item, self, self))
        return parameter

    def _aliased(self, item: str) -> ParameterModel | None:
        """Find the parameter that `item` is an alias of (`wetterdienst.metadata.aliases`), and tell the caller it is.

        None for a name that is no alias, or whose alias leads to a name this dataset does not have.
        """
        # the back-reference is None while the dataset is built, and an attribute looked up then is no alias
        resolution = self.__dict__.get("resolution")
        if resolution is None:
            return None
        alias = find_alias(resolution.metadata_name, resolution.name, self.name, item.strip().lower())
        parameter = _find(self.parameters, alias.new) if alias else None
        if alias is not None and parameter is not None:
            use_alias(item, alias)
        return parameter

    # on purpose, not pydantic's iteration over (name, value) pairs of the fields: a model here is iterated
    # as the collection of its parameters. The quality flags are not among them (`is_quality_flag`): they come back
    # in the `quality_flags` column of the parameter they belong to and cannot be requested, so everything that lists
    # what a dataset offers (this iterator, `discover()`, the list in a not-found message) leaves them out, while a
    # name that is looked up is found whatever it is, and answered with the explanation of `search_parameter`
    def __iter__(self) -> Iterator[ParameterModel]:  # ty: ignore[invalid-method-override]
        """Iterate over all parameters but the quality flags."""
        return iter(parameter for parameter in self.parameters if not is_quality_flag(parameter))


class ResolutionModel(BaseModel):
    """Resolution model for a provider."""

    model_config = ConfigDict(extra="forbid")

    name: str
    name_original: str
    value: Resolution = Field(alias="name", exclude=True, repr=False)  # this is just to make the code more readable
    periods: list[Period] | None = None
    description: str | None = None
    date_required: bool | None = None
    datasets: list[DatasetModel]
    # the name of the provider's metadata declaration, which `MetadataModel` sets once it holds this
    # resolution, so that a dataset can tell which provider it belongs to (see `RENAMED_PARAMETERS_IN_DATASET`)
    metadata_name: str = Field(default="", exclude=True, repr=False)

    @field_validator("datasets", mode="before")
    @classmethod
    def validate_datasets(cls, v: list[dict], validation_info: ValidationInfo) -> list[dict]:
        """Validate datasets and set resolution for each dataset.

        Reads the two cascading fields with ``get``: a field that failed its own validation is not
        in ``validation_info.data`` at all, and indexing it would replace pydantic's report of what
        was actually wrong -- an unknown period, say -- with a bare ``KeyError('periods')``.

        A dataset that would have inherited such a field is then left out rather than validated:
        it would otherwise be reported as missing a field it deliberately omits, once per dataset
        -- 110 times over for one mistyped period in a `DwdPhenologyMetadata` resolution -- burying
        the one error that is real. A dataset declaring the field itself is validated as usual, so
        anything else wrong with it is still reported.
        """
        if "periods" not in validation_info.data:
            v = [dataset for dataset in v if dataset.get("periods")]
        if "date_required" not in validation_info.data:
            v = [dataset for dataset in v if dataset.get("date_required") is not None]
        periods = validation_info.data.get("periods")
        date_required = validation_info.data.get("date_required")
        if periods:
            for dataset in v:
                if not dataset.get("periods"):
                    dataset["periods"] = periods
        if date_required is not None:
            for dataset in v:
                if dataset.get("date_required") is None:
                    dataset["date_required"] = date_required
        return v

    def __init__(self, **data: Any) -> None:  # noqa: ANN401
        """Initialize the resolution model."""
        super().__init__(**data)
        for dataset in self.datasets:
            dataset.resolution = self

    def __getitem__(self, item: str | int) -> DatasetModel:
        """Get a dataset by name."""
        if isinstance(item, int):
            return self.datasets[item]
        dataset = _find(self.datasets, item)
        if dataset is None:
            raise KeyError(_not_found("datasets", item, self.datasets))
        return dataset

    def __getattr__(self, item: str) -> DatasetModel:
        """Get a dataset by name."""
        dataset = _find(self.datasets, item)
        if dataset is None:
            raise AttributeError(_not_found("datasets", item, self.datasets))
        return dataset

    # on purpose, not pydantic's iteration over (name, value) pairs of the fields: a model here is iterated
    # as the collection of its datasets
    def __iter__(self) -> Iterator[DatasetModel]:  # ty: ignore[invalid-method-override]
        """Iterate over all datasets."""
        return iter(self.datasets)


class LicenseModel(BaseModel):
    """The terms a provider publishes its data under, as the provider states them (GH-2561).

    `spdx_id` is the identifier of the licence in the SPDX list, or an SPDX expression where the
    provider names two that both apply (`CC-BY-4.0 AND NLOD-2.0`, MET Norway's); null where the terms
    have no SPDX identifier, which is then told by `name` and `url` alone. `url` is a page of the
    licence or of the provider's own terms, whichever states them.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    spdx_id: str | None
    name: str
    url: str


def _extent_problems(extent: Extent, country_code: str | None) -> list[str]:
    """Say where the extent of a network is not the one of its provider: a national one names the provider's country."""
    if extent.scope == "national" and extent.country_codes != (country_code,):
        return [f"a national extent names {list(extent.country_codes)}, the country of the provider is {country_code}"]
    return []


@dataclass(frozen=True)
class ProviderTerms:
    """What a network without a metadata model says of its provider: the same fields a `MetadataModel` has for it.

    The radar products and the warnings of `dwd` are standalone networks (`NetworkKind`), have no resolutions or
    parameters to declare and so no `MetadataModel`, but an answer about them names who published the data and
    under which terms all the same (GH-3059).
    """

    name_local: str
    name_english: str
    country: str
    country_code: str | None
    copyright: str
    license: LicenseModel | None
    attribution: str | None
    url: str
    extent: Extent

    def __post_init__(self) -> None:
        """Hold a national network to the country of its provider, as `MetadataModel` does."""
        problems = _extent_problems(self.extent, self.country_code)
        if problems:
            msg = f"the extent of the network: {'; '.join(problems)}"
            raise ValueError(msg)


CC_BY_4_0 = LicenseModel(
    spdx_id="CC-BY-4.0",
    name="Creative Commons Attribution 4.0 International",
    url="https://creativecommons.org/licenses/by/4.0/",
)
CC0_1_0 = LicenseModel(
    spdx_id="CC0-1.0",
    name="Creative Commons Zero v1.0 Universal",
    url="https://creativecommons.org/publicdomain/zero/1.0/",
)
OGL_UK_3_0 = LicenseModel(
    spdx_id="OGL-UK-3.0",
    name="UK Open Government Licence v3.0",
    url="https://www.nationalarchives.gov.uk/doc/open-government-licence/version/3/",
)
ETALAB_2_0 = LicenseModel(
    spdx_id="etalab-2.0",
    name="Etalab Open License 2.0",
    url="https://www.data.gouv.fr/pages/legal/licences/etalab-2.0",
)


class MetadataModel(BaseModel):
    """Metadata model for a provider."""

    model_config = ConfigDict(extra="forbid")

    # the name the declaration is bound to, e.g. "DwdObservationMetadata", set by
    # `build_metadata_model`. Unlike the three provider names below it is a name of ours, so it
    # identifies the provider in messages about a request that could not be resolved against it
    # but stays out of the serialized metadata.
    name: str = Field(default="", exclude=True, repr=False)
    name_short: str
    name_english: str
    name_local: str
    country: str
    #: the ISO 3166-1 alpha-2 code of `country` (`DE`); null for a provider of several countries (the declaration
    #: says so by writing `"country_code": None`, so that a new provider cannot leave the question out)
    country_code: str | None
    copyright: str
    #: the terms the provider publishes its data under; null where it states none (the declaration says so
    #: by writing `"license": None`, so that a new provider cannot leave the question out)
    license: LicenseModel | None
    #: the credit line a user of the data has to give: the provider's own wording where it states one, else
    #: its name as the rights holder; null where the provider states none or asks for none
    attribution: str | None
    url: str
    kind: TimeseriesKind
    #: where the stations of the network are, which is no statement about the provider's `country` (a declaration
    #: has to give it, so that a new network cannot leave the question out)
    extent: Extent
    timezone: TimeZoneName
    auth: bool = False
    resolutions: list[ResolutionModel]

    @field_validator("country_code")
    @classmethod
    def _validate_country_code(cls, value: str | None) -> str | None:
        """Refuse a country code that is no two capital letters, which is how an alpha-2 code is written."""
        if value is not None and not _COUNTRY_CODE.fullmatch(value):
            msg = f"{value!r} is no ISO 3166-1 alpha-2 code: two capital letters, or null for several countries"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def _validate_extent_country(self) -> MetadataModel:
        """Hold a national network to the country of its provider, which is the one the extent names."""
        problems = _extent_problems(self.extent, self.country_code)
        if problems:
            raise ValueError(problems[0])
        return self

    @model_validator(mode="after")
    def _validate_dataset_extents(self) -> MetadataModel:
        """Hold the extent of a dataset to lie within its network's, to differ from it, and to be national in one."""
        network = self.extent
        west, south, east, north = network.bbox
        problems = []
        for resolution in self.resolutions:
            for dataset in resolution.datasets:
                own = dataset.extent
                if own is None:
                    continue
                label = f"{resolution.name}/{dataset.name}"
                inside = own.bbox[0] >= west and own.bbox[1] >= south and own.bbox[2] <= east and own.bbox[3] <= north
                if not inside:
                    problems.append(
                        f"{label}: its bbox {list(own.bbox)} is not within the network's {list(network.bbox)}"
                    )
                if not set(own.continents) <= set(network.continents):
                    ours, theirs = list(own.continents), list(network.continents)
                    problems.append(f"{label}: its continents {ours} are not the network's {theirs}")
                if network.country_codes and not set(own.country_codes) <= set(network.country_codes):
                    ours, theirs = list(own.country_codes), list(network.country_codes)
                    problems.append(f"{label}: its country_codes {ours} are not the network's {theirs}")
                problems += [f"{label}: {problem}" for problem in _extent_problems(own, self.country_code)]
                if network.scope == "national" and own.scope != "national":
                    problems.append(f"{label}: a dataset of a national network is national, not {own.scope}")
                if own.same_as(network):
                    problems.append(f"{label}: its extent is the network's, which a dataset leaves out")
        if problems:
            msg = "the extent of a dataset lies within the extent of its network: " + "; ".join(problems)
            raise ValueError(msg)
        return self

    def model_post_init(self, _context: object, /) -> None:
        """Tell each resolution which declaration it belongs to."""
        super().model_post_init(_context)
        for resolution in self.resolutions:
            resolution.metadata_name = self.name

    def __getitem__(self, item: str | int) -> ResolutionModel:
        """Get a resolution by name."""
        if isinstance(item, int):
            return self.resolutions[item]
        resolution = _find(self.resolutions, item)
        if resolution is None:
            raise KeyError(_not_found("resolutions", item, self.resolutions))
        return resolution

    def __getattr__(self, item: str) -> ResolutionModel:
        """Get a resolution by name.

        Alternatively, this still finds any other attribute that is not a resolution.
        """
        resolution = _find(self.resolutions, item)
        if resolution is None:
            # pydantic defines `__getattr__` only outside `TYPE_CHECKING`, so a checker does not see it
            return super().__getattr__(item)  # ty: ignore[unresolved-attribute]
        return resolution

    # on purpose, not pydantic's iteration over (name, value) pairs of the fields: a model here is iterated
    # as the collection of its resolutions
    def __iter__(self) -> Iterator[ResolutionModel]:  # ty: ignore[invalid-method-override]
        """Iterate over all resolutions."""
        return iter(self.resolutions)

    def search_parameter(self, parameter_search: ParameterSearch) -> list[ParameterModel]:
        """Search for a parameter in the metadata.

        Raises a ``KeyError`` naming the part that did not match -- resolution, dataset or
        parameter -- with the names that would have matched, so a caller that drops the request
        can say why it dropped it.
        """
        resolution = _find(self.resolutions, parameter_search.resolution)
        if resolution is None:
            raise KeyError(_not_found("resolutions", parameter_search.resolution, self.resolutions))
        dataset = _find(resolution.datasets, parameter_search.dataset)
        if dataset is None:
            raise KeyError(_not_found("datasets", parameter_search.dataset, resolution.datasets))
        if not parameter_search.parameter:
            # iterating the dataset leaves out its quality flags, see DatasetModel.__iter__
            return [*dataset]
        # searched over all parameters rather than over the dataset's iterator, so that a quality
        # flag is answered with the explanation below instead of with "no such parameter"
        parameter = _find(dataset.parameters, parameter_search.parameter)
        if parameter is None:
            parameter = dataset._aliased(parameter_search.parameter)  # noqa: SLF001
        if parameter is None:
            raise KeyError(_not_found("parameters", parameter_search.parameter, dataset, dataset))
        if is_quality_flag(parameter):
            msg = (
                f"'{parameter_search.parameter}' is a quality flag. Quality flags are returned in the "
                f"'quality_flags' column next to the parameter they belong to and cannot be requested on their own."
            )
            raise KeyError(msg)
        return [parameter]


def _canonical_description(name: str) -> str | None:
    """Return the canonical sentence of a quantity, or None for a name the table does not know.

    An unknown name is left for ``tests/test_api.py::test_metadata_parameter_table`` to report, as
    it is for ``ParameterModel.unit_type``, rather than failing the import of the provider.
    """
    canonical = PARAMETERS.get(name)
    return canonical.description if canonical else None


def build_metadata_model(metadata: dict, name: str) -> MetadataModel:
    """Build a MetadataModel from a dictionary.

    Attaches the descriptions kept in ``metadata.source_descriptions``, for parameters, datasets and
    resolutions alike. Those are the curated descriptions the provider docs tables have always
    carried. A description a provider module already declares wins, since that is a transcription of
    the source's own wording and is only kept where it says at least as much as the curated text.
    ``DERIVED_DESCRIPTIONS`` fills only what no source supplies at all. A parameter none of these
    describes reads the canonical sentence of its quantity from ``PARAMETERS``, so a provider whose
    field means exactly what the quantity means keeps no copy of the sentence to drift from it.

    ``name`` becomes ``MetadataModel.name``. A declaration cannot set it itself: it is the one
    top-level key ``extra="forbid"`` does not reject, and it is a plausible one to write next to
    ``name_short``, ``name_english`` and ``name_local``, where it would be silently overwritten.
    """
    if "name" in metadata:
        msg = f"{name}: 'name' is the name the model is built with and cannot be declared"
        raise ValueError(msg)
    from wetterdienst.metadata.source_descriptions import (  # noqa: PLC0415
        DATASET_DESCRIPTIONS,
        DERIVED_DESCRIPTIONS,
        RESOLUTION_DESCRIPTIONS,
        SOURCE_DESCRIPTIONS,
    )

    # a derived description only fills a gap, never displaces one the source wrote
    parameters = {
        **DERIVED_DESCRIPTIONS.get(name, {}),
        **SOURCE_DESCRIPTIONS.get(name, {}),
    }
    datasets = DATASET_DESCRIPTIONS.get(name, {})
    resolutions = RESOLUTION_DESCRIPTIONS.get(name, {})
    # copied rather than written into: providers commonly build one resolution's parameter list
    # from another's by comprehension, which reuses the very same dicts. Writing a description
    # into those would attach it to every resolution sharing them -- AEMET's annual parameters are
    # its monthly ones minus humidity, so annual read "Monthly mean temperature".
    metadata = {
        **metadata,
        "name": name,
        "resolutions": [
            {
                **resolution,
                "description": resolution.get("description") or resolutions.get(resolution["name"]),
                "datasets": [
                    {
                        **dataset,
                        "description": dataset.get("description")
                        or datasets.get((resolution["name"], dataset["name"])),
                        "parameters": [
                            {
                                **parameter,
                                "description": parameter.get("description")
                                or parameters.get(
                                    (resolution["name"], dataset["name"], parameter["name_original"]),
                                )
                                or _canonical_description(parameter["name"]),
                            }
                            for parameter in dataset["parameters"]
                        ],
                    }
                    for dataset in resolution["datasets"]
                ],
            }
            for resolution in metadata["resolutions"]
        ],
    }
    return MetadataModel.model_validate(metadata)


def _name_of(part: object) -> object:
    """Give a ``Resolution`` member the name it is searched for by, its value, and anything else as it is.

    ``Resolution`` is one of the two names the package exports, so ``(Resolution.DAILY, "kl")`` is
    taken as ``("daily", "kl")``. Any other enumeration names nothing in the metadata and is left for
    the caller to be refused with the other parts that are not names.
    """
    return part.value if isinstance(part, Resolution) else part


ON_UNKNOWN = ("raise", "warn")


def check_on_unknown(on_unknown: str) -> None:
    """Refuse an ``on_unknown`` that is neither ``"raise"`` nor ``"warn"``, listing the two."""
    if on_unknown not in ON_UNKNOWN:
        msg = f"{on_unknown!r} is not a valid on_unknown. Valid values: {', '.join(ON_UNKNOWN)}"
        raise InvalidEnumerationError(msg)


@dataclass
class ParameterSearch:
    """Dataclass to hold a search for a parameter."""

    resolution: str
    dataset: str
    parameter: str | None = None

    @classmethod
    def parse(cls, value: str | Iterable[str] | DatasetModel | ParameterModel) -> ParameterSearch:
        """Parse a string or tuple or DatasetModel or ParameterModel into a ParameterSearch object."""
        if isinstance(value, DatasetModel):
            return ParameterSearch(value.resolution.name, value.name)
        if isinstance(value, ParameterModel):
            return ParameterSearch(value.dataset.resolution.name, value.dataset.name, value.name)
        if isinstance(value, str):
            normalized = value
            for sep in POSSIBLE_SEPARATORS:
                normalized = normalized.replace(sep, "/")
            parts = normalized.split("/")
        elif isinstance(value, Iterable):
            parts = list(value)
        else:
            msg = f"expected {_EXPECTED_PARAMETER}, got {type(value).__name__}"
            raise TypeError(msg)
        named = [_name_of(part) for part in parts]
        for part in named:
            if not isinstance(part, str):
                msg = f"{value!r}: expected the parts as strings, got {type(part).__name__} '{part}'"
                raise TypeError(msg)
        parts = [part.strip().lower() for part in cast("list[str]", named)]
        if len(parts) not in (2, 3) or not all(parts):
            msg = (
                f"{value!r}: expected 'resolution/dataset' or 'resolution/dataset/parameter' "
                f"(separator any of {POSSIBLE_SEPARATORS}), or the same as a tuple of its parts"
            )
            raise ValueError(msg)
        parameter = parts[2] if len(parts) == 3 else None
        return ParameterSearch(parts[0], parts[1], parameter)

    def concat(self) -> str:
        """Concatenate resolution, dataset and parameter with '/'."""
        return "/".join(filter(None, [self.resolution, self.dataset, self.parameter]))


def _entries(parameters: _PARAMETER_TYPE) -> list[str | Iterable[str] | DatasetModel | ParameterModel]:
    """Split what was asked for into the entries that are each one search, enumeration members as names."""
    if isinstance(parameters, str | DatasetModel | ParameterModel):
        # "daily/climate_summary" -> ["daily/climate_summary"]
        return [parameters]
    if not isinstance(parameters, Iterable):
        msg = f"expected {_EXPECTED_PARAMETER}, or a sequence of those, got {type(parameters).__name__}"
        raise TypeError(msg)
    # materialized first: the check below would otherwise exhaust an iterator
    entries = cast("list[str | Iterable[str] | DatasetModel | ParameterModel]", [_name_of(p) for p in parameters])
    names = [p for p in entries if isinstance(p, str)]
    if entries and len(names) == len(entries) and all(sep not in p for p in names for sep in POSSIBLE_SEPARATORS):
        # ("daily", "climate_summary") -> [("daily", "climate_summary")]
        return [names]
    return entries


def parse_parameters(
    parameters: _PARAMETER_TYPE,
    metadata: MetadataModel,
    on_unknown: Literal["raise", "warn"] = "raise",
) -> list[ParameterModel]:
    """Parse one parameter or a sequence of them into the provider's parameter models.

    A parameter the provider does not have, or one that is not shaped like a parameter at all, is
    refused with an `InvalidParameterError` naming every such entry with its close match and the
    names that would have matched, because returning less than was asked for without saying so is
    the answer a caller cannot see. With ``on_unknown="warn"`` each is logged as a warning instead
    and the others are still resolved and returned; only a request where nothing at all resolves
    fails then, which the caller raises. A part that is not a string, nor an enumeration member
    with a string value, is a ``TypeError`` and does propagate: it says the caller passed the wrong
    kind of object rather than misspelled a name.
    """
    check_on_unknown(on_unknown)
    entries = _entries(parameters)
    parameters_found = []
    seen = set()
    problems = []
    for parameter in entries:
        try:
            parameter_search = ParameterSearch.parse(parameter)
            found = metadata.search_parameter(parameter_search)
        except ValueError as e:
            # malformed, e.g. a trailing separator
            problems.append(f"{parameter!r} could not be parsed as a parameter: {e.args[0]}")
            continue
        except KeyError as e:
            problems.append(f"{parameter_search.concat()} not found in {metadata.name}: {e.args[0]}")
            continue
        for parameter_found in found:
            # requests commonly overlap e.g. a dataset and one of its parameters, which would
            # otherwise be queried and returned twice
            key = (
                parameter_found.dataset.resolution.name,
                parameter_found.dataset.name,
                parameter_found.name,
            )
            if key not in seen:
                seen.add(key)
                parameters_found.append(parameter_found)
    if problems and on_unknown == "raise":
        error = InvalidParameterError("; ".join(problems))
        error.resolved = bool(parameters_found)
        raise error
    # warned about once the whole request is read, so that a request with one bad entry among
    # others names all of them whichever way it goes on
    for problem in problems:
        log.warning(problem)
    return parameters_found


def group_parameters_by_dataset(
    parameters: Iterable[ParameterModel],
) -> list[tuple[DatasetModel, list[ParameterModel]]]:
    """Group parameters by the dataset they belong to, in order of first appearance.

    Not ``itertools.groupby``, which only groups *consecutive* items: ``parse_parameters`` keeps
    the order the caller asked in, so datasets interleaved across parameters -- say
    ``[daily/kl/temperature_air_mean_2m, daily/more_precip/..., daily/kl/precipitation_amount]`` --
    produce one group per run rather than one per dataset. Downstream that means a dataset fetched
    and parsed once per run instead of once, and, where the groups build a stations frame, one
    duplicated station row per extra run.

    Keyed on the resolution and dataset names rather than on the model, which defines ``__eq__``
    without ``__hash__`` and is therefore unhashable.
    """
    groups: dict[tuple[str, str], tuple[DatasetModel, list[ParameterModel]]] = {}
    for parameter in parameters:
        dataset = parameter.dataset
        key = (dataset.resolution.name, dataset.name)
        if key not in groups:
            groups[key] = (dataset, [])
        groups[key][1].append(parameter)
    return list(groups.values())
