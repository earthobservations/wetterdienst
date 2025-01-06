from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, Field, SkipValidation, field_validator
from pydantic_extra_types.timezone_name import (
    TimeZoneName,  # noqa: TCH002, needs to stay here for pydantic model to work
)

from wetterdienst.metadata.period import Period  # noqa: TCH001, needs to stay here for pydantic model to work
from wetterdienst.metadata.resolution import Resolution  # noqa: TCH001, needs to stay here for pydantic model to work

if TYPE_CHECKING:
    from collections.abc import Iterator

    from wetterdienst.core.timeseries.request import _PARAMETER_TYPE

log = logging.getLogger(__name__)

POSSIBLE_SEPARATORS = ("/", ".", ":")

# for any provider that does not publish their data under a dedicated dataset name
DATASET_NAME_DEFAULT = "data"


class ParameterModel(BaseModel):
    name: str
    name_original: str
    unit_type: str
    unit: str
    description: str | None = None
    dataset: SkipValidation[DatasetModel] = Field(default=None, exclude=True, repr=False)

    def __eq__(self, other):
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

    def __getitem__(self, item):
        if isinstance(item, int):
            return self.parameters[item]
        item_search = item.strip().lower()
        for parameter in self.parameters:
            if parameter.name == item_search or parameter.name_original == item_search:
                return parameter
        else:
            available_parameters = [
                f"{parameter.name}/{parameter.name_original}"
                if parameter.name != parameter.name_original
                else parameter.name
                for parameter in self.parameters
            ]
            raise KeyError(f"'{item}'. Available parameters: {', '.join(available_parameters)}")

    def __getattr__(self, item):
        for parameter in self.parameters:
            if parameter.name == item or parameter.name_original == item:
                return parameter
        else:
            available_parameters = [
                f"{parameter.name}/{parameter.name_original}"
                if parameter.name != parameter.name_original
                else parameter.name
                for parameter in self.parameters
            ]
            raise AttributeError(f"'{item}'. Available parameters: {', '.join(available_parameters)}")

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
        else:
            available_datasets = [
                f"{dataset.name}/{dataset.name_original}" if dataset.name != dataset.name_original else dataset.name
                for dataset in self.datasets
            ]
            raise KeyError(f"'{item}'. Available datasets: {', '.join(available_datasets)}")

    def __getattr__(self, item: str) -> DatasetModel:
        item_search = item.strip().lower()
        for dataset in self.datasets:
            if dataset.name == item_search or dataset.name_original == item_search:
                return dataset
        else:
            available_datasets = [
                f"{dataset.name}/{dataset.name_original}" if dataset.name != dataset.name_original else dataset.name
                for dataset in self.datasets
            ]
            raise AttributeError(f"'{item}'. Available datasets: {', '.join(available_datasets)}")

    def __iter__(self) -> Iterator[DatasetModel]:
        return iter(self.datasets)


class MetadataModel(BaseModel):
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
        else:
            available_resolutions = [
                f"{resolution.name}/{resolution.name_original}"
                if resolution.name != resolution.name_original
                else resolution.name
                for resolution in self.resolutions
            ]
            raise KeyError(f"'{item}'. Available resolutions: {', '.join(available_resolutions)}")

    def __getattr__(self, item):
        item_search = item.strip().lower()
        for resolution in self.resolutions:
            if (
                resolution.name == item_search
                or resolution.name_original == item_search
                or resolution.value.name.lower() == item_search
            ):
                return resolution
        else:
            return super().__getattr__(item)

    def __iter__(self) -> Iterator[ResolutionModel]:
        return iter(self.resolutions)

    def search_parameter(self, parameter_search: ParameterSearch) -> list[ParameterModel]:
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
    metadata = MetadataModel.model_validate(metadata)
    metadata.__name__ = name
    return metadata


@dataclass
class ParameterSearch:
    resolution: str
    dataset: str
    parameter: str | None = None

    @classmethod
    def parse(cls, value: str | Iterable[str] | DatasetModel | ParameterModel) -> ParameterSearch:
        if isinstance(value, DatasetModel):
            return ParameterSearch(value.resolution.name, value.name)
        if isinstance(value, ParameterModel):
            return ParameterSearch(value.dataset.resolution.name, value.dataset.name, value.name)
        resolution = None
        dataset = None
        parameter = None
        if isinstance(value, str):
            if all(value.count(sep) == 0 for sep in POSSIBLE_SEPARATORS):
                raise ValueError(
                    f"expected 'resolution/dataset' or 'resolution/dataset/parameter' "
                    f"(separator any of {POSSIBLE_SEPARATORS})"
                )
            for sep in POSSIBLE_SEPARATORS:
                if sep in value:
                    value = value.replace(sep, "/")
            value = value.split("/")
        try:
            resolution, dataset, parameter = value
        except ValueError:
            try:
                resolution, dataset = value
            except ValueError:
                pass
        resolution = resolution and resolution.strip().lower()
        dataset = dataset and dataset.strip().lower()
        parameter = parameter and parameter.strip().lower()
        return ParameterSearch(resolution, dataset, parameter)

    def concat(self) -> str:
        return "/".join(filter(None, [self.resolution, self.dataset, self.parameter]))


def parse_parameters(parameters: _PARAMETER_TYPE, metadata: MetadataModel) -> list[ParameterModel]:
    """Method to parse parameters, either from string or tuple or MetadataModel or sequence of those."""
    if isinstance(parameters, str | DatasetModel | ParameterModel):
        # "daily/climate_summary" -> ["daily/climate_summary"]
        parameters = [
            parameters,
        ]
    elif isinstance(parameters, Iterable):
        if all(isinstance(p, str) for p in parameters) and all(
            all(sep not in p for sep in POSSIBLE_SEPARATORS) for p in parameters
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
    unique_resolutions = set(parameter.dataset.resolution.value.value for parameter in parameters_found)
    # TODO: for now we only support one resolution
    if len(unique_resolutions) > 1:
        raise ValueError(f"All parameters must have the same resolution. Found: {unique_resolutions}")
    return parameters_found
