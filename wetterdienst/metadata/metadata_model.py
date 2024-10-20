from __future__ import annotations

from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from typing import Optional

from lxml.objectify import NoneElement
from pydantic import BaseModel, RootModel, field_validator, model_validator, SkipValidation, Field

from wetterdienst import Period, Resolution


class ParameterModel(BaseModel):
    name: str
    original: str
    unit: str
    unit_original: str
    dataset: SkipValidation["DatasetModel"] = Field(default=None, exclude=True, repr=False)



class DatasetModel(BaseModel):
    __name__ = "Dataset"
    name: str
    name_original: str
    parameters: list[ParameterModel]
    periods: list[Period] | None = None
    resolution: SkipValidation["ResolutionModel"] = Field(default=None, exclude=True, repr=False)

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

    # def __str__(self):
    #     return f"name='{self.name}' resolution='{self.resolution}' parameters={self.parameters}"
    #
    # def __repr__(self):
    #     return f"Dataset({self.__str__()})"


# parameter reference $ref which consists of "dataset/parameter"
# should be resolved into dataset and parameter before validation of pydanitc model
class ParameterRef(BaseModel):
    dataset: str
    parameter: str

    @model_validator(mode="before")
    def resolve_ref(cls, v):
        if v.keys() != {"$ref"}:
            raise ValueError("Only $ref is allowed")
        dataset, parameter = v["$ref"].split("/")
        return {"dataset": dataset, "parameter": parameter}


class ResolutionModel(BaseModel):
    value: Resolution
    datasets: list[DatasetModel]
    parameters: SkipValidation[list[ParameterModel]]
    periods: list[Period] | None = None

    @field_validator("parameters", mode="before")
    @classmethod
    def validate_parameters(cls, v, validation_info):
        # resolve references
        resolved_parameters = []
        for parameter_ref in v:
            parameter_ref = ParameterRef.model_validate(parameter_ref)
            for dataset in validation_info.data["datasets"]:
                if dataset.name == parameter_ref.dataset:
                    for parameter in dataset.parameters:
                        if parameter.name == parameter_ref.parameter:
                            resolved_parameters.append(parameter)
                            break
                    else:
                        raise KeyError(parameter_ref)
                    break
            else:
                raise KeyError(parameter_ref)
        return resolved_parameters

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
        for parameter in self.parameters:
            if parameter.name == item:
                return parameter
        raise KeyError(item)

    def __getattr__(self, item):
        for dataset in self.datasets:
            if dataset.name == item:
                return dataset
        for parameter in self.parameters:
            if parameter.name == item:
                return parameter
        raise AttributeError(item)

    def __iter__(self) -> Iterator[DatasetModel]:
        return iter(self.datasets)


class MetadataModel(RootModel):
    root: list[ResolutionModel]

    def __getitem__(self, item):
        if isinstance(item, int):
            return self.root[item]
        for resolution in self.root:
            if resolution.value.name.lower() == item or resolution.value.value == item:
                return resolution
        raise KeyError(item)

    def __getattr__(self, item):
        for resolution in self.root:
            if resolution.value.name.lower() == item or resolution.value.value == item:
                return resolution
        raise AttributeError(item)

    def __iter__(self) -> Iterator[ResolutionModel]:
        return iter(self.root)

    def __str__(self):
        return f"[{self.root}]"

    def __repr__(self):
        return f"Metadata({self.__str__()})"

    def search_parameter(self, parameter_search: ParameterTemplate) -> list[ParameterModel]:
        for resolution in self:
            if resolution.value.name.lower() == parameter_search.resolution or resolution.value.value == parameter_search.resolution:
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
