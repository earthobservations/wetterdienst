from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Iterator

import jsonref
from pydantic import BaseModel, field_validator, RootModel, model_validator, ValidationError


class Parameter(BaseModel):
    name: str
    original: str
    resolution: str
    dataset: str


class Dataset(BaseModel):
    name: str
    resolution: str
    parameters: list[Parameter]

    @field_validator("parameters", mode="before")
    @classmethod
    def validate_parameters(cls, v, validation_info):
        resolution_name = validation_info.data["resolution"]
        dataset_name = validation_info.data["name"]
        for parameter in v:
            parameter["resolution"] = resolution_name
            parameter["dataset"] = dataset_name
        return v

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

    def __iter__(self) -> Iterator[Parameter]:
        return iter(self.parameters)

    def __str__(self):
        return f"name='{self.name}' resolution='{self.resolution}' parameters={self.parameters}"

    def __repr__(self):
        return f"Dataset({self.__str__()})"


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


class Resolution(BaseModel):
    name: str
    datasets: list[Dataset]
    parameters: list[Parameter]

    @field_validator("datasets", mode="before")
    @classmethod
    def validate_datasets(cls, v, validation_info):
        resolution_name = validation_info.data["name"]
        for dataset in v:
            dataset["resolution"] = resolution_name
        return v

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

    def __iter__(self) -> Iterator[Dataset]:
        return iter(self.datasets)

    def __str__(self):
        return f"name='{self.name}' datasets={self.datasets} parameters={self.parameters}"

    def __repr__(self):
        return f"Resolution({self.__str__()})"


class MetadataModel(RootModel):
    root: list[Resolution]

    def __getitem__(self, item):
        if isinstance(item, int):
            return self.root[item]
        for resolution in self.root:
            if resolution.name == item:
                return resolution
        raise KeyError(item)

    def __getattr__(self, item):
        for resolution in self.root:
            if resolution.name == item:
                return resolution
        raise AttributeError(item)


    def __iter__(self) -> Iterator[Resolution]:
        return iter(self.root)

    def __str__(self):
        return f"[{self.root}]"

    def __repr__(self):
        return f"Metadata({self.__str__()})"

    def search_parameter(self, parameter_search: "ParameterTemplate") -> list[Parameter]:
        for resolution in self:
            if resolution.name == parameter_search.resolution:
                break
        else:
            raise KeyError(parameter_search.resolution)
        for dataset in resolution:
            if dataset.name == parameter_search.dataset:
                break
        else:
            raise KeyError(parameter_search.dataset)
        if parameter_search.parameter is None:
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
    def parse(cls, value: str | Iterable[str]) -> "ParameterTemplate":
        resolution = None
        dataset = None
        parameter = None
        if isinstance(value, str):
            if value.count("/") == 0:
                raise ValueError("expected 'resolution/dataset/parameter' or 'resolution/dataset'")
            value =  value.split("/")
        try:
            resolution, dataset, parameter = value
        except ValueError:
            try:
                resolution, dataset = value
            except ValueError:
                pass
        return ParameterTemplate(resolution, dataset, parameter)
