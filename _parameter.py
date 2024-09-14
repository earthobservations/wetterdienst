from pathlib import Path
from typing import Iterator

import jsonref
from pydantic import BaseModel, field_validator, Field, RootModel

FILE = Path("./dwd.json")


class _Parameter(BaseModel):
    name: str
    original: str
    resolution: str
    dataset: str


class _Dataset(BaseModel):
    name: str
    resolution: str
    parameters_: dict[str, _Parameter] = Field(alias="parameters", serialization_alias="parameters")

    @property
    def parameters(self):
        return list(self.parameters_.values())

    @field_validator("parameters_", mode="before")
    @classmethod
    def validate_parameters(cls, v, validation_info):
        resolution_name = validation_info.data["resolution"]
        dataset_name = validation_info.data["name"]
        for name, parameter in v.items():
            parameter["name"] = name
            parameter["resolution"] = resolution_name
            parameter["dataset"] = dataset_name
        return v

    def __getitem__(self, item):
        if isinstance(item, int):
            return self.parameters[item]
        try:
            return self.parameters_[item]
        except KeyError as e:
            for parameter in self.parameters:
                if parameter.original == item:
                    return parameter
            raise KeyError(item) from e

    def __getattr__(self, item):
        try:
            return self.parameters_[item]
        except KeyError as e:
            for parameter in self.parameters:
                if parameter.original == item:
                    return parameter
            raise KeyError(item) from e

    def __iter__(self) -> Iterator[_Parameter]:
        return iter(self.parameters)

    def __str__(self):
        return f"name='{self.name}' resolution='{self.resolution}' parameters={self.parameters}"

    def __repr__(self):
        return f"_Dataset({self.__str__()})"


class _Resolution(BaseModel):
    name: str
    datasets_: dict[str, _Dataset] = Field(alias="datasets", serialization_alias="datasets")
    parameters_: dict[str, _Parameter] = Field(alias="parameters", serialization_alias="parameters")

    @property
    def datasets(self):
        return list(self.datasets_.values())

    @property
    def parameters(self):
        return list(self.parameters_.values())

    @field_validator("datasets_", mode="before")
    @classmethod
    def validate_datasets(cls, v, validation_info):
        resolution_name = validation_info.data["name"]
        for name, dataset in v.items():
            dataset["name"] = name
            dataset["resolution"] = resolution_name
        return v

    @field_validator("parameters_", mode="before")
    @classmethod
    def validate_parameters(cls, v):
        for name, parameter in v.items():
            parameter["name"] = name
        return v

    def __getitem__(self, item):
        if isinstance(item, int):
            return self.datasets[item]
        try:
            return self.datasets_[item]
        except KeyError as e:
            try:
                return self.parameters_[item]
            except KeyError as e:
                raise KeyError(item) from e

    def __getattr__(self, item):
        return self.datasets_[item]

    def __iter__(self) -> Iterator[_Dataset]:
        return iter(self.datasets)

    def __str__(self):
        return f"name='{self.name}' datasets={self.datasets} parameters={self.parameters}"

    def __repr__(self):
        return f"_Resolution({self.__str__()})"


class _Metadata(BaseModel):
    resolutions: dict[str, _Resolution]

    @field_validator("resolutions", mode="before")
    @classmethod
    def validate_parameters(cls, v):
        for name, resolution in v.items():
            resolution["name"] = name
        return v

    def __getitem__(self, item):
        if isinstance(item, int):
            return list(self.resolutions.values())[item]
        return self.resolutions[item]

    def __getattr__(self, item):
        return self.resolutions[item]

    def __iter__(self) -> Iterator[_Resolution]:
        return iter(self.resolutions.values())

    def __str__(self):
        return f"resolutions={list(self.resolutions.values())}"

    def __repr__(self):
        return f"_Metadata({self.__str__()})"


parameters_raw = jsonref.loads(FILE.read_text())
parameters = _Metadata.model_validate(parameters_raw)

# print(parameters["minute_1"]["precipitation"]["precipitation_height"])
# print(parameters.minute_1.precipitation.precipitation_height)
# print(parameters["minute_1"].precipitation["precipitation_height"])
# print(parameters.minute_1["precipitation"].rs_01)
#
# print(parameters.minute_1[0][1])
#
# print(parameters.minute_1.parameters[0])

precipitation_height = parameters.minute_1.precipitation.precipitation_height

print(precipitation_height)

# print(parameters.minute_1.precipitation[precipitation_height])


def parse_parameter(parameter: str | tuple[str, str] | list[str] | _Parameter) -> _Parameter:
    resolution = "minute_1"
    dataset = None
    try:
        parameter, dataset = parameter
    except ValueError:
        pass
    try:
        parameter = parameter.name
        dataset = parameter.dataset
    except AttributeError:
        pass
    datasets = parameters[resolution]
    if dataset:
        return datasets[dataset][parameter]
    return datasets[parameter]

par = parse_parameter("precipitation_height")
print(par)

par = parse_parameter(("precipitation_height", "precipitation"))
print(par)

par = parse_parameter(par)
print(par)
