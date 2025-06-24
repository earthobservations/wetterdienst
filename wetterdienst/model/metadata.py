# Copyright (c) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Metadata models for a provider."""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field, SkipValidation, field_validator
from pydantic_extra_types.timezone_name import (
    TimeZoneName,  # noqa: TC002, needs to stay here for pydantic model to work
)

from wetterdienst.metadata.period import Period  # noqa: TC001, needs to stay here for pydantic model to work
from wetterdienst.metadata.resolution import Resolution  # noqa: TC001, needs to stay here for pydantic model to work

if TYPE_CHECKING:
    from collections.abc import Iterator

    from pydantic_core.core_schema import ValidationInfo

    from wetterdienst.model.request import _PARAMETER_TYPE

log = logging.getLogger(__name__)

POSSIBLE_SEPARATORS = ("/", ".", ":")

# for any provider that does not publish their data under a dedicated dataset name
DATASET_NAME_DEFAULT = "data"


class ParameterModel(BaseModel):  # noqa: PLW1641
    """Parameter model for a provider."""

    name: str
    name_original: str
    unit_type: str
    unit: str
    description: str | None = None
    dataset: SkipValidation[DatasetModel] = Field(default=None, exclude=True, repr=False)

    def __eq__(self, other: ParameterModel) -> bool:
        """Compare two parameters."""
        if not isinstance(other, ParameterModel):
            return False
        return (
            self.name == other.name
            and self.name_original == other.name_original
            and self.unit_type == other.unit_type
            and self.unit == other.unit
            and self.description == other.description
            # don't compare the dataset object itself because it'd be circular
            and self.dataset.name == other.dataset.name
            and self.dataset.resolution.name == other.dataset.resolution.name
        )


class DatasetModel(BaseModel):  # noqa: PLW1641
    """Dataset model for a provider."""

    name: str
    name_original: str
    grouped: bool  # if parameters are grouped together e.g. in one file
    periods: list[Period]
    description: str | None = None
    date_required: bool
    parameters: list[ParameterModel]
    resolution: SkipValidation[ResolutionModel] = Field(default=None, exclude=True, repr=False)

    def __init__(self, **data: dict) -> None:
        """Initialize the dataset model."""
        super().__init__(**data)
        for parameter in self.parameters:
            parameter.dataset = self

    def __eq__(self, other: DatasetModel) -> bool:
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
        item_search = item.strip().lower()
        for parameter in self.parameters:
            if item_search in (parameter.name, parameter.name_original):
                return parameter
        available_parameters = [
            f"{parameter.name}/{parameter.name_original}"
            if parameter.name != parameter.name_original
            else parameter.name
            for parameter in self.parameters
        ]
        msg = f"'{item}'. Available parameters: {', '.join(available_parameters)}"
        raise KeyError(msg)

    def __getattr__(self, item: str) -> ParameterModel:
        """Get a parameter by name."""
        for parameter in self.parameters:
            if item in (parameter.name, parameter.name_original):
                return parameter
        available_parameters = [
            f"{parameter.name}/{parameter.name_original}"
            if parameter.name != parameter.name_original
            else parameter.name
            for parameter in self.parameters
        ]
        msg = f"'{item}'. Available parameters: {', '.join(available_parameters)}"
        raise AttributeError(msg)

    def __iter__(self) -> Iterator[ParameterModel]:
        """Iterate over all parameters."""
        return iter(parameter for parameter in self.parameters if not parameter.name.startswith("quality"))


class ResolutionModel(BaseModel):
    """Resolution model for a provider."""

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
        """Validate datasets and set resolution for each dataset."""
        periods = validation_info.data["periods"]
        date_required = validation_info.data["date_required"]
        if periods:
            for dataset in v:
                if not dataset.get("periods"):
                    dataset["periods"] = periods
        if date_required is not None:
            for dataset in v:
                if dataset.get("date_required") is None:
                    dataset["date_required"] = date_required
        return v

    def __init__(self, **data: dict) -> None:
        """Initialize the resolution model."""
        super().__init__(**data)
        for dataset in self.datasets:
            dataset.resolution = self

    def __getitem__(self, item: str | int) -> DatasetModel:
        """Get a dataset by name."""
        if isinstance(item, int):
            return self.datasets[item]
        item_search = item.strip().lower()
        for dataset in self.datasets:
            if item_search in (dataset.name, dataset.name_original):
                return dataset
        available_datasets = [
            f"{dataset.name}/{dataset.name_original}" if dataset.name != dataset.name_original else dataset.name
            for dataset in self.datasets
        ]
        msg = f"'{item}'. Available datasets: {', '.join(available_datasets)}"
        raise KeyError(msg)

    def __getattr__(self, item: str) -> DatasetModel:
        """Get a dataset by name."""
        item_search = item.strip().lower()
        for dataset in self.datasets:
            if item_search in (dataset.name, dataset.name_original):
                return dataset
        available_datasets = [
            f"{dataset.name}/{dataset.name_original}" if dataset.name != dataset.name_original else dataset.name
            for dataset in self.datasets
        ]
        msg = f"'{item}'. Available datasets: {', '.join(available_datasets)}"
        raise AttributeError(msg)

    def __iter__(self) -> Iterator[DatasetModel]:
        """Iterate over all datasets."""
        return iter(self.datasets)


class MetadataModel(BaseModel):
    """Metadata model for a provider."""

    name_short: str
    name_english: str
    name_local: str
    country: str
    copyright: str
    url: str
    kind: Literal["observation", "forecast"]
    timezone: TimeZoneName
    timezone_data: TimeZoneName | Literal["dynamic"]
    resolutions: list[ResolutionModel]

    def __getitem__(self, item: str | int) -> ResolutionModel:
        """Get a resolution by name."""
        if isinstance(item, int):
            return self.resolutions[item]
        item_search = item.strip().lower()
        for resolution in self.resolutions:
            if item_search in (resolution.name, resolution.name_original, resolution.value.name.lower()):
                return resolution
        available_resolutions = [
            f"{resolution.name}/{resolution.name_original}"
            if resolution.name != resolution.name_original
            else resolution.name
            for resolution in self.resolutions
        ]
        msg = f"'{item}'. Available resolutions: {', '.join(available_resolutions)}"
        raise KeyError(msg)

    def __getattr__(self, item: str) -> ResolutionModel:
        """Get a resolution by name.

        Alternatively, this still finds any other attribute that is not a resolution.
        """
        item_search = item.strip().lower()
        for resolution in self.resolutions:
            if item_search in (resolution.name, resolution.name_original, resolution.value.name.lower()):
                return resolution
        return super().__getattr__(item)

    def __iter__(self) -> Iterator[ResolutionModel]:
        """Iterate over all resolutions."""
        return iter(self.resolutions)

    def search_parameter(self, parameter_search: ParameterSearch) -> list[ParameterModel]:
        """Search for a parameter in the metadata."""
        for resolution in self:
            if (
                resolution.name == parameter_search.resolution
                or resolution.name_original.lower() == parameter_search.resolution
                or resolution.value.name.lower() == parameter_search.resolution
            ):
                break
        else:
            raise KeyError(parameter_search.resolution)
        for dataset in resolution:
            if dataset.name == parameter_search.dataset or dataset.name_original.lower() == parameter_search.dataset:
                break
        else:
            raise KeyError(parameter_search.dataset)
        if not parameter_search.parameter:
            return [*dataset]
        for parameter in dataset:
            if (
                parameter.name == parameter_search.parameter
                or parameter.name_original.lower() == parameter_search.parameter
            ):
                return [parameter]
        raise KeyError(parameter_search.parameter)


def build_metadata_model(metadata: dict, name: str) -> MetadataModel:
    """Build a MetadataModel from a dictionary."""
    metadata = MetadataModel.model_validate(metadata)
    metadata.__name__ = name
    return metadata


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
        parameter = None
        if isinstance(value, str):
            if all(value.count(sep) == 0 for sep in POSSIBLE_SEPARATORS):
                msg = (
                    f"expected 'resolution/dataset' or 'resolution/dataset/parameter' "
                    f"(separator any of {POSSIBLE_SEPARATORS})"
                )
                raise ValueError(msg)
            for sep in POSSIBLE_SEPARATORS:
                if sep in value:
                    value = value.replace(sep, "/")
            value = value.split("/")
        try:
            resolution, dataset, parameter = value
        except ValueError as e:
            try:
                resolution, dataset = value
            except ValueError as inner_e:
                raise inner_e from e
        resolution = resolution and resolution.strip().lower()
        dataset = dataset and dataset.strip().lower()
        parameter = parameter and parameter.strip().lower()
        return ParameterSearch(resolution, dataset, parameter)

    def concat(self) -> str:
        """Concatenate resolution, dataset and parameter with '/'."""
        return "/".join(filter(None, [self.resolution, self.dataset, self.parameter]))


def parse_parameters(parameters: _PARAMETER_TYPE, metadata: MetadataModel) -> list[ParameterModel]:
    """Parse parameters, either from string or tuple or MetadataModel or sequence of those."""
    if isinstance(parameters, str | DatasetModel | ParameterModel):
        # "daily/climate_summary" -> ["daily/climate_summary"]
        parameters = [
            parameters,
        ]
    elif (
        isinstance(parameters, Iterable)
        and all(isinstance(p, str) for p in parameters)
        and all(all(sep not in p for sep in POSSIBLE_SEPARATORS) for p in parameters)
    ):
        # ("daily", "climate_summary") -> [("daily", "climate_summary")]
        parameters = [
            parameters,
        ]
    parameters_found = []
    for parameter in parameters:
        parameter_search = ParameterSearch.parse(parameter)
        try:
            parameters_found.extend(metadata.search_parameter(parameter_search))
        except KeyError:
            log.info(f"{parameter_search.concat()} not found in {metadata.__name__}")
    return parameters_found
