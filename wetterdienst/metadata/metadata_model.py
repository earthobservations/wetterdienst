from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, SkipValidation

from wetterdienst import Period, Resolution  # noqa: TCH001, needs to stay here for pydantic model to work

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator


class ParameterModel(BaseModel):
    name: str
    original: str
    unit: str
    unit_original: str
    dataset: SkipValidation[DatasetModel] = Field(default=None, exclude=True, repr=False)


class DatasetModel(BaseModel):
    __name__ = "Dataset"
    name: str
    name_original: str
    grouped: bool  # if parameters are grouped together e.g. in one file
    periods: list[Period] | None = None
    parameters: list[ParameterModel]
    resolution: SkipValidation[ResolutionModel] = Field(default=None, exclude=True, repr=False)

    def __init__(self, **data):
        super().__init__(**data)
        for parameter in self.parameters:
            parameter.dataset = self

    def __getitem__(self, item):
        if isinstance(item, int):
            return self.parameters[item]
        for parameter in self.parameters:
            if parameter.name == item or parameter.original == item:
                return parameter
        raise KeyError(item)

    def __getattr__(self, item):
        for parameter in self.parameters:
            if parameter.name == item or parameter.original == item:
                return parameter
        raise AttributeError(item)

    def __iter__(self) -> Iterator[ParameterModel]:
        return iter(self.parameters)


class ResolutionModel(BaseModel):
    name: Resolution
    name_original: str
    value: Resolution = Field(alias="name", exclude=True, repr=False)  # this is just to make the code more readable
    datasets: list[DatasetModel]
    periods: list[Period] | None = None

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
            if parameter.name == parameter_search.parameter:
                return [parameter]
        raise KeyError(parameter_search.parameter)


@dataclass
class ParameterTemplate:
    resolution: str
    dataset: str
    parameter: str | None

    @classmethod
    def parse(cls, value: str | Iterable[str]) -> ParameterTemplate:
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
