from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, SkipValidation

from wetterdienst import Period, Resolution  # noqa: TCH001, needs to stay here for pydantic model to work
from wetterdienst.util.python import to_list

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from wetterdienst.core.timeseries.request import _PARAMETER_TYPE

log = logging.getLogger(__name__)

# for any provider that does not publish their data under a dedicated dataset name
DATASET_NAME_DEFAULT = "data"


class ParameterModel(BaseModel):
    name: str
    name_original: str
    unit: str
    unit_original: str
    description: str | None = None
    dataset: SkipValidation[DatasetModel] = Field(default=None, exclude=True, repr=False)

    def __eq__(self, other):
        return (
            self.name == other.name
            and self.name_original == other.name_original
            and self.unit == other.unit
            and self.unit_original == other.unit_original
            and self.description == other.description
            # don't compare the dataset object itself because it'd be circular
            and self.dataset.name == other.dataset.name
            and self.dataset.resolution.name == other.dataset.resolution.name
        )


class DatasetModel(BaseModel):
    __name__ = "Dataset"
    name: str
    name_original: str
    grouped: bool  # if parameters are grouped together e.g. in one file
    periods: list[Period] | None = None
    description: str | None = None
    parameters: list[ParameterModel]
    resolution: SkipValidation[ResolutionModel] = Field(default=None, exclude=True, repr=False)

    def __init__(self, **data):
        super().__init__(**data)
        for parameter in self.parameters:
            parameter.dataset = self

    def __eq__(self, other):
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

    def __getitem__(self, item):
        if isinstance(item, int):
            return self.parameters[item]
        for parameter in self.parameters:
            if parameter.name == item or parameter.name_original == item:
                return parameter
        raise KeyError(item)

    def __getattr__(self, item):
        for parameter in self.parameters:
            if parameter.name == item or parameter.name_original == item:
                return parameter
        raise AttributeError(item)

    def __iter__(self) -> Iterator[ParameterModel]:
        return iter(parameter for parameter in self.parameters if not parameter.name.startswith("quality"))


class ResolutionModel(BaseModel):
    name: str
    name_original: str
    value: Resolution = Field(alias="name", exclude=True, repr=False)  # this is just to make the code more readable
    datasets: list[DatasetModel]
    periods: list[Period] | None = None
    description: str | None = None

    def __init__(self, **data):
        super().__init__(**data)
        for dataset in self.datasets:
            dataset.resolution = self
            # propagate periods to dataset
            dataset.periods = dataset.periods or self.periods

    def __getitem__(self, item):
        if isinstance(item, int):
            return self.datasets[item]
        for dataset in self.datasets:
            if dataset.name == item:
                return dataset
        raise KeyError(item)

    def __getattr__(self, item):
        for dataset in self.datasets:
            if dataset.name == item:
                return dataset
        raise AttributeError(item)

    def __iter__(self) -> Iterator[DatasetModel]:
        return iter(self.datasets)


class MetadataModel(BaseModel):
    resolutions: list[ResolutionModel]

    def __getitem__(self, item):
        if isinstance(item, int):
            return self.resolutions[item]
        for resolution in self.resolutions:
            if resolution.value.name.lower() == item or resolution.value.value == item:
                return resolution
        raise KeyError(item)

    def __getattr__(self, item):
        for resolution in self.resolutions:
            if resolution.value.name.lower() == item or resolution.value.value == item:
                return resolution
        raise AttributeError(item)

    def __iter__(self) -> Iterator[ResolutionModel]:
        return iter(self.resolutions)

    def search_parameter(self, parameter_search: ParameterTemplate) -> list[ParameterModel]:
        for resolution in self:
            if (
                resolution.value.name.lower() == parameter_search.resolution
                or resolution.value.value == parameter_search.resolution
            ):
                break
        else:
            raise KeyError(parameter_search.resolution)
        for dataset in resolution:
            if dataset.name == parameter_search.dataset or dataset.name_original == parameter_search.dataset:
                break
        else:
            raise KeyError(parameter_search.dataset)
        if not parameter_search.parameter:
            return [*dataset]
        for parameter in dataset:
            if parameter.name == parameter_search.parameter or parameter.name_original == parameter_search.parameter:
                return [parameter]
        raise KeyError(parameter_search.parameter)


@dataclass
class ParameterTemplate:
    resolution: str
    dataset: str
    parameter: str | None = None

    @classmethod
    def parse(cls, value: str | Iterable[str] | DatasetModel | ParameterModel) -> ParameterTemplate:
        if isinstance(value, DatasetModel):
            return ParameterTemplate(value.resolution.name, value.name)
        if isinstance(value, ParameterModel):
            return ParameterTemplate(value.dataset.resolution.name, value.dataset.name, value.name)
        resolution = None
        dataset = None
        parameter = None
        if isinstance(value, str):
            if value.count("/") == 0:
                raise ValueError("expected 'resolution/dataset/parameter' or 'resolution/dataset'")
            value = value.split("/")
        try:
            resolution, dataset, parameter = value
        except ValueError:
            try:
                resolution, dataset = value
            except ValueError:
                pass
        return ParameterTemplate(resolution, dataset, parameter)


def parse_parameter(parameter: _PARAMETER_TYPE, metadata: MetadataModel) -> list[ParameterModel]:
    """Method to parse parameters, either from string or tuple or MetadataModel or sequence of those."""
    parameters_found = []
    for parameter in to_list(parameter):
        parameter_template = ParameterTemplate.parse(parameter)
        try:
            parameters_found.extend(metadata.search_parameter(parameter_template))
        except KeyError:
            log.info(f"{parameter_template} not found in {metadata.__class__}")
    unique_resolutions = set(parameter.dataset.resolution.value.value for parameter in parameters_found)
    # TODO: for now we only support one resolution
    if len(unique_resolutions) > 1:
        raise ValueError(f"All parameters must have the same resolution. Found: {unique_resolutions}")
    return parameters_found
