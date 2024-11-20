from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import TYPE_CHECKING

from pydantic import BaseModel, Field, SkipValidation, field_validator

from wetterdienst import Period, Resolution  # noqa: TCH001, needs to stay here for pydantic model to work
from wetterdienst.util.python import to_list

if TYPE_CHECKING:
    from collections.abc import Iterable, Iterator

    from wetterdienst.core.timeseries.request import _PARAMETER_TYPE

from wetterdienst.metadata.parameter import Parameter
from wetterdienst.metadata.unit import OriginUnit, SIUnit

PARAMETER_NAMES = {parameter.name.lower() for parameter in Parameter}
UNIT_NAMES = {unit.name.lower() for unit in SIUnit}
UNIT_ORIGINAL_NAMES = {unit.name.lower() for unit in OriginUnit}

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

    @field_validator("name", mode="after")
    @classmethod
    def validate_name_original(cls, value):
        if value.startswith("quality"):
            return value
        if value in PARAMETER_NAMES:
            return value
        raise ValueError(f"Parameter name '{value}' not in {PARAMETER_NAMES}")

    @field_validator("unit", mode="after")
    @classmethod
    def validate_unit(cls, value):
        if value in UNIT_NAMES:
            return value
        raise ValueError(f"Unit name '{value}' not in {UNIT_NAMES}")

    @field_validator("unit_original", mode="after")
    @classmethod
    def validate_unit_original(cls, value):
        if value in UNIT_ORIGINAL_NAMES:
            return value
        raise ValueError(f"Unit name '{value}' not in {UNIT_ORIGINAL_NAMES}")

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
    periods: list[Period]
    description: str | None = None
    date_required: bool
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
        item_search = item.strip().lower()
        for parameter in self.parameters:
            if parameter.name == item_search or parameter.name_original == item_search:
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
    periods: list[Period] | None = None
    description: str | None = None
    date_required: bool | None = None
    datasets: list[DatasetModel]

    @field_validator("datasets", mode="before")
    @classmethod
    def validate_datasets(cls, v, validation_info):
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

    def __init__(self, **data):
        super().__init__(**data)
        for dataset in self.datasets:
            dataset.resolution = self

    def __getitem__(self, item: str | int) -> DatasetModel:
        if isinstance(item, int):
            return self.datasets[item]
        item_search = item.strip().lower()
        for dataset in self.datasets:
            if dataset.name == item_search or dataset.name_original == item_search:
                return dataset
        raise KeyError(item)

    def __getattr__(self, item: str) -> DatasetModel:
        item_search = item.strip().lower()
        for dataset in self.datasets:
            if dataset.name == item_search or dataset.name_original == item_search:
                return dataset
        raise AttributeError(item)

    def __iter__(self) -> Iterator[DatasetModel]:
        return iter(self.datasets)


class MetadataModel(BaseModel):
    resolutions: list[ResolutionModel]

    def __getitem__(self, item: str | int):
        if isinstance(item, int):
            return self.resolutions[item]
        item_search = item.strip().lower()
        for resolution in self.resolutions:
            if (
                resolution.name == item_search
                or resolution.name_original == item_search
                or resolution.value.name.lower() == item_search
            ):
                return resolution
        raise KeyError(item)

    def __getattr__(self, item):
        item_search = item.strip().lower()
        for resolution in self.resolutions:
            if (
                resolution.name == item_search
                or resolution.name_original == item_search
                or resolution.value.name.lower() == item_search
            ):
                return resolution
        return super().__getattr__(item)

    def __iter__(self) -> Iterator[ResolutionModel]:
        return iter(self.resolutions)

    def search_parameter(self, parameter_search: ParameterTemplate) -> list[ParameterModel]:
        for resolution in self:
            if (
                resolution.name == parameter_search.resolution
                or resolution.name_original == parameter_search.resolution
                or resolution.value.name.lower() == parameter_search.resolution
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


def build_metadata_model(metadata: dict, name: str) -> MetadataModel:
    metadata = MetadataModel.model_validate(metadata)
    metadata.__name__ = name
    return metadata


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

    def concat(self) -> str:
        return "/".join(filter(None, [self.resolution, self.dataset, self.parameter]))


def parse_parameters(parameter: _PARAMETER_TYPE, metadata: MetadataModel) -> list[ParameterModel]:
    """Method to parse parameters, either from string or tuple or MetadataModel or sequence of those."""
    parameters_found = []
    for parameter in to_list(parameter):
        parameter_template = ParameterTemplate.parse(parameter)
        try:
            parameters_found.extend(metadata.search_parameter(parameter_template))
        except KeyError:
            log.info(f"{parameter_template.concat()} not found in {metadata.__name__}")
    unique_resolutions = set(parameter.dataset.resolution.value.value for parameter in parameters_found)
    # TODO: for now we only support one resolution
    if len(unique_resolutions) > 1:
        raise ValueError(f"All parameters must have the same resolution. Found: {unique_resolutions}")
    return parameters_found
