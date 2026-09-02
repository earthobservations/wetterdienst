# Copyright (c) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Metadata models for a provider."""

from __future__ import annotations

import difflib
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field, SkipValidation, field_validator
from pydantic_extra_types.timezone_name import (
    TimeZoneName,  # noqa: TC002, needs to stay here for pydantic model to work
)

from wetterdienst.metadata.parameter_table import PARAMETERS
from wetterdienst.metadata.period import Period  # noqa: TC001, needs to stay here for pydantic model to work
from wetterdienst.metadata.resolution import Resolution  # noqa: TC001, needs to stay here for pydantic model to work

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pydantic_core.core_schema import ValidationInfo

    from wetterdienst.metadata.unit_type import UnitType
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


def _not_found(kind: str, item: str, models: Iterable[_NamedModel]) -> str:
    """Build the message for a name that no model matched.

    Names a close match where there is one, because the common failure is a typo or a name taken
    from another provider, and the available-names list alone leaves the user to spot the
    difference themselves.
    """
    models = list(models)
    candidates = sorted({name for model in models for name in _names(model)})
    close = difflib.get_close_matches(str(item).strip().lower(), candidates, n=1, cutoff=_SUGGESTION_CUTOFF)
    suggestion = f" Did you mean '{close[0]}'?" if close else ""
    available = ", ".join(
        f"{model.name}/{model.name_original}" if model.name != model.name_original else model.name for model in models
    )
    return f"'{item}'.{suggestion} Available {kind}: {available}"


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
    resolution: SkipValidation[ResolutionModel] = Field(default=None, exclude=True, repr=False)  # ty: ignore[invalid-assignment]

    def __init__(self, **data: dict) -> None:
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
            raise KeyError(_not_found("parameters", item, self.parameters))
        return parameter

    def __getattr__(self, item: str) -> ParameterModel:
        """Get a parameter by name."""
        parameter = _find(self.parameters, item)
        if parameter is None:
            raise AttributeError(_not_found("parameters", item, self.parameters))
        return parameter

    def __iter__(self) -> Iterator[ParameterModel]:  # ty: ignore[invalid-method-override]
        """Iterate over all parameters."""
        return iter(parameter for parameter in self.parameters if not parameter.name.startswith("quality"))


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

    @field_validator("datasets", mode="before")
    @classmethod
    def validate_datasets(cls, v: list[dict], validation_info: ValidationInfo) -> list[DatasetModel]:
        """Validate datasets and set resolution for each dataset.

        Reads the two cascading fields with ``get``: a field that failed its own validation is not
        in ``validation_info.data`` at all, and indexing it would replace pydantic's report of what
        was actually wrong -- an unknown period, say -- with a bare ``KeyError('periods')``.
        """
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
        return v  # ty: ignore[invalid-return-type]

    def __init__(self, **data: dict) -> None:
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

    def __iter__(self) -> Iterator[DatasetModel]:  # ty: ignore[invalid-method-override]
        """Iterate over all datasets."""
        return iter(self.datasets)


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
    copyright: str
    url: str
    kind: Literal["observation", "forecast", "derived"]
    timezone: TimeZoneName
    auth: bool = False
    resolutions: list[ResolutionModel]

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
            return super().__getattr__(item)  # ty: ignore[unresolved-attribute]
        return resolution

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
            raise KeyError(_not_found("parameters", parameter_search.parameter, dataset))
        if parameter.name.startswith("quality"):
            msg = (
                f"'{parameter_search.parameter}' is a quality flag. Quality flags are returned in the "
                f"'quality' column next to the parameter they belong to and cannot be requested on their own."
            )
            raise KeyError(msg)
        return [parameter]


def build_metadata_model(metadata: dict, name: str) -> MetadataModel:
    """Build a MetadataModel from a dictionary.

    Attaches the descriptions kept in ``metadata.source_descriptions``, for parameters, datasets and
    resolutions alike. Those are the curated descriptions the provider docs tables have always
    carried. A description a provider module already declares wins, since that is a transcription of
    the source's own wording and is only kept where it says at least as much as the curated text.
    ``DERIVED_DESCRIPTIONS`` fills only what no source supplies at all.
    """
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
                                ),
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
        # the parts are names, so an enum member mixed into a tuple -- (Resolution.DAILY, "kl") --
        # is rejected here, naming the accepted forms, rather than searched for and not found
        for part in parts:
            if not isinstance(part, str):
                msg = f"{value!r}: expected the parts as strings, got {type(part).__name__} '{part}'"
                raise TypeError(msg)
        parts = [part.strip().lower() for part in parts]
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


def parse_parameters(parameters: _PARAMETER_TYPE, metadata: MetadataModel) -> list[ParameterModel]:
    """Parse one parameter or a sequence of them into the provider's parameter models.

    A parameter the provider does not have, or one that is not shaped like a parameter at all, is
    not fatal on its own -- the other parameters are still resolved and returned -- but it is
    logged as a warning naming the reason, because silently returning less data than was asked for
    is otherwise invisible. Only a request where nothing at all resolves fails, which the caller
    raises. A part that is not a string is a ``TypeError`` and does propagate: it says the caller
    passed the wrong kind of object rather than misspelled a name.
    """
    if isinstance(parameters, str | DatasetModel | ParameterModel):
        # "daily/climate_summary" -> ["daily/climate_summary"]
        parameters = [parameters]
    elif isinstance(parameters, Iterable):
        # materialized first: the check below would otherwise exhaust an iterator
        parameters = list(parameters)
        if parameters and all(
            isinstance(p, str) and all(sep not in p for sep in POSSIBLE_SEPARATORS) for p in parameters
        ):
            # ("daily", "climate_summary") -> [("daily", "climate_summary")]
            parameters = [parameters]  # ty: ignore[invalid-assignment]
    else:
        msg = f"expected {_EXPECTED_PARAMETER}, or a sequence of those, got {type(parameters).__name__}"
        raise TypeError(msg)
    parameters_found = []
    seen = set()
    for parameter in parameters:
        try:
            parameter_search = ParameterSearch.parse(parameter)
            found = metadata.search_parameter(parameter_search)
        except ValueError as e:
            # malformed, e.g. a trailing separator -- skipped like an unknown name, so that one
            # bad entry does not take the parameters around it down with it
            log.warning(f"{parameter!r} could not be parsed as a parameter: {e.args[0]}")
            continue
        except KeyError as e:
            log.warning(f"{parameter_search.concat()} not found in {metadata.name}: {e.args[0]}")
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
    return parameters_found
