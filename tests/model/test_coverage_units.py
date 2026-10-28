# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The units `coverage` reports: `unit` of the values, `unit_source` the provider's where it differs (GH-3537)."""

import datetime as dt
import json
import os
from collections.abc import Iterator
from types import SimpleNamespace
from typing import Any

import polars as pl
import pytest

from wetterdienst import Wetterdienst
from wetterdienst.model.metadata import DatasetModel, ParameterModel
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.unit import UnitConverter
from wetterdienst.options import Options
from wetterdienst.ui.core import get_glossary, resolve_network

_SAMPLE = 21.5
_FAHRENHEIT = '{"temperature": "degree_fahrenheit"}'


@pytest.fixture(autouse=True)
def _no_options_in_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test against the built-in options: a developer's shell may have set some, which `coverage` follows."""
    for name in [name for name in os.environ if name.startswith("WD_TS_")]:
        monkeypatch.delenv(name)


def _networks() -> list[tuple[str, str, type[TimeseriesRequest]]]:
    """Every timeseries network, the standalone ones (`dwd/radar`, `dwd/alerts`) having no parameters."""
    networks = []
    for provider, names in Wetterdienst.registry.items():
        for network in names:
            api = resolve_network(provider, network)
            if isinstance(api, type) and issubclass(api, TimeseriesRequest):
                networks.append((provider, network, api))
    return networks


_NETWORKS = _networks()


def _parameters() -> Iterator[tuple[str, str, type[TimeseriesRequest], str, str, dict[str, Any]]]:
    """Every parameter of every network as `coverage` describes it, with where it is."""
    for provider, network, api in _NETWORKS:
        for resolution, resolution_entry in api.discover().items():
            for dataset, dataset_entry in resolution_entry["datasets"].items():
                for parameter in dataset_entry["parameters"]:
                    yield provider, network, api, resolution, dataset, parameter


def _value_in_the_answer(api: type[TimeseriesRequest], dataset: DatasetModel, parameter: ParameterModel) -> float:
    """Give what the provider's own `values` class returns for a reading of 21.5, without any download.

    The provider's `_process_dataset` is run with a stubbed collection, with the options of the environment as a
    request that passes none gets them, so a provider that overrides the conversion is the one caught.
    """
    values_class = api._values  # noqa: SLF001
    values = object.__new__(values_class)
    options = Options()
    values.sr = SimpleNamespace(options=options, start=None, end=None)  # ty: ignore[invalid-assignment]
    values.unit_converter = UnitConverter()
    values.unit_converter.update_targets(options.unit_targets)
    values._data_updated = []  # noqa: SLF001
    frame = pl.DataFrame(
        {
            "parameter": [parameter.name_original],
            "timestamp": [dt.datetime(2020, 1, 1, tzinfo=dt.UTC)],
            "value": [_SAMPLE],
        },
    )
    values._collect_station_parameter_or_dataset = lambda station_id, parameter_or_dataset: frame  # noqa: ARG005, SLF001
    answer = values._process_dataset("1", dataset, [parameter])  # noqa: SLF001
    return answer["value"][0]


@pytest.mark.parametrize(
    ("provider", "network", "resolution", "dataset", "name", "unit_type", "unit", "unit_source"),
    [
        # a temperature the source publishes in Kelvin, as the model that misread it saw it
        ("dwd", "mosmix", "hourly", "large", "temperature_air_2m", "temperature", "degree_celsius", "degree_kelvin"),
        (
            "meteofrance",
            "synop",
            "subdaily",
            "data",
            "temperature_air_2m",
            "temperature",
            "degree_celsius",
            "degree_kelvin",
        ),
        # a probability the source publishes as 85.00 and `values` returns as 0.85
        (
            "dwd",
            "mosmix",
            "hourly",
            "large",
            "probability_precipitation_amount_gt_0_2mm_last_24h",
            "fraction",
            "decimal",
            "percent",
        ),
        # minutes the values come back in as seconds
        ("dwd", "observation", "hourly", "sun", "sunshine_duration", "time", "second", "minute"),
        # nothing to convert: no `unit_source`, which says the same as `unit`
        (
            "dwd",
            "observation",
            "daily",
            "climate_summary",
            "temperature_air_mean_2m",
            "temperature",
            "degree_celsius",
            None,
        ),
    ],
)
def test_unit_is_the_unit_of_the_values_and_unit_source_the_providers_where_it_differs(
    provider: str,
    network: str,
    resolution: str,
    dataset: str,
    name: str,
    unit_type: str,
    unit: str,
    unit_source: str | None,
) -> None:
    """Test that the unit of a parameter is the one its values come in, the provider's own beside it if another."""
    api = resolve_network(provider, network)
    assert issubclass(api, TimeseriesRequest)
    parameters = api.discover(resolutions=resolution, datasets=dataset)[resolution]["datasets"][dataset]["parameters"]
    parameter = next(p for p in parameters if p["name"] == name)
    assert parameter["unit_type"] == unit_type
    assert parameter["unit"] == unit
    assert parameter.get("unit_source") == unit_source
    assert ("unit_source" in parameter) == (unit_source is not None)


def test_every_parameter_has_the_unit_its_providers_values_come_back_in() -> None:
    """Test that, for every parameter of every network, `unit` is the unit the provider's own `values` give.

    A reading of 21.5 goes through the `_process_dataset` of the provider's values class, and comes out as the same
    reading converted from `unit_source` (or from `unit`, where there is none) to `unit`. A `unit` that named
    another unit than the one converted to would not match it.
    """
    converter = UnitConverter()
    wrong = []
    checked = 0
    for provider, network, api, resolution, dataset, parameter in _parameters():
        dataset_model = api.metadata[resolution][dataset]
        parameter_model = dataset_model[parameter["name"]]
        got = _value_in_the_answer(api, dataset_model, parameter_model)
        expected = converter._get_lambda(parameter.get("unit_source", parameter["unit"]), parameter["unit"])(_SAMPLE)  # noqa: SLF001
        checked += 1
        if abs(got - expected) > 1e-3 * max(1.0, abs(expected)):
            wrong.append((provider, network, resolution, dataset, parameter["name"], got, expected))
    assert checked > 2000
    assert not wrong, f"{len(wrong)} parameters whose `unit` is not what their values are converted to: {wrong[:5]}"


def test_unit_of_every_parameter_is_the_unit_of_the_glossary() -> None:
    """Test that `coverage` and `glossary` give a parameter the same unit, whichever network it is in."""
    glossary = {entry["name"]: entry for entry in get_glossary()}
    wrong = []
    for provider, network, _, resolution, dataset, parameter in _parameters():
        entry = glossary[parameter["name"]]
        if (parameter["unit_type"], parameter["unit"]) != (entry["unit_type"], entry["unit"]):
            wrong.append((provider, network, resolution, dataset, parameter["name"], parameter["unit"], entry["unit"]))
    assert not wrong, f"{len(wrong)} parameters whose `unit` is not the glossary's: {wrong[:5]}"


def test_unit_source_is_there_exactly_where_the_declared_unit_differs_from_unit() -> None:
    """Test that `unit_source` is the declared unit where that is not `unit`, and absent where it is."""
    wrong = []
    checked = 0
    differing = 0
    for provider, network, api in _NETWORKS:
        for resolution, resolution_entry in api.discover().items():
            for dataset, dataset_entry in resolution_entry["datasets"].items():
                declared = list(api.metadata[resolution][dataset])
                assert len(declared) == len(dataset_entry["parameters"])
                for model, parameter in zip(declared, dataset_entry["parameters"], strict=True):
                    checked += 1
                    expected = model.unit if model.unit != parameter["unit"] else None
                    differing += expected is not None
                    if (model.name, expected) != (parameter["name"], parameter.get("unit_source")):
                        wrong.append((provider, network, resolution, dataset, parameter["name"]))
    assert checked > 2000
    assert not wrong, f"{len(wrong)} parameters whose `unit_source` is not the declared unit or absent: {wrong[:5]}"
    # 362 of 2048 in 29 networks when this was written: a floor, so that a new network does not fail it, and so that
    # the checks above are not vacuous
    assert differing >= 300


def test_an_answer_where_nothing_converts_has_no_unit_source_at_all() -> None:
    """Test that `dwd/phenology`, whose parameters are all published in their target unit, has no new member (GH-3537).

    The answer is as long as it was before `unit_source`: every parameter has the unit it declares and nothing
    more, so the answer a model reads is not longer for a member that would say the same as `unit`.
    """
    api = resolve_network("dwd", "phenology")
    assert issubclass(api, TimeseriesRequest)
    answer = api.discover()
    parameters = [
        (resolution, dataset, parameter)
        for resolution, resolution_entry in answer.items()
        for dataset, dataset_entry in resolution_entry["datasets"].items()
        for parameter in dataset_entry["parameters"]
    ]
    assert len(parameters) > 10
    assert "unit_source" not in json.dumps(answer)
    for resolution, dataset, parameter in parameters:
        assert parameter["unit"] == api.metadata[resolution][dataset][parameter["name"]].unit
        assert set(parameter) == {"name", "name_original", "unit_type", "unit", "description"}


def test_coverage_follows_the_unit_targets_of_the_environment_as_values_and_glossary_do(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that a server started with `WD_TS_UNIT_TARGETS` has `coverage` say what `values` return (GH-3537)."""
    monkeypatch.setenv("WD_TS_UNIT_TARGETS", _FAHRENHEIT)
    api = resolve_network("dwd", "mosmix")
    assert issubclass(api, TimeseriesRequest)
    parameters = api.discover(resolutions="hourly", datasets="large")["hourly"]["datasets"]["large"]["parameters"]
    temperature = next(p for p in parameters if p["name"] == "temperature_air_2m")
    assert (temperature["unit"], temperature["unit_source"]) == ("degree_fahrenheit", "degree_kelvin")
    glossary = next(e for e in get_glossary(parameter="temperature_air_2m") if e["name"] == "temperature_air_2m")
    assert glossary["unit"] == temperature["unit"]
    dataset = api.metadata["hourly"]["large"]
    got = _value_in_the_answer(api, dataset, dataset["temperature_air_2m"])
    assert got == pytest.approx(UnitConverter()._get_lambda("degree_kelvin", "degree_fahrenheit")(_SAMPLE), abs=1e-3)  # noqa: SLF001
    # a quantity the target does not name keeps its default
    probability = next(p for p in parameters if p["name"] == "probability_precipitation_amount_gt_0_2mm_last_24h")
    assert (probability["unit"], probability["unit_source"]) == ("decimal", "percent")


def test_coverage_says_the_unit_the_provider_publishes_where_the_environment_turns_conversion_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test that with `WD_TS_CONVERT_UNITS` off `unit` is the provider's, as the values are, and nothing differs."""
    monkeypatch.setenv("WD_TS_CONVERT_UNITS", "false")
    api = resolve_network("dwd", "mosmix")
    assert issubclass(api, TimeseriesRequest)
    answer = api.discover(resolutions="hourly", datasets="large")
    parameters = answer["hourly"]["datasets"]["large"]["parameters"]
    temperature = next(p for p in parameters if p["name"] == "temperature_air_2m")
    assert temperature["unit"] == "degree_kelvin"
    assert "unit_source" not in json.dumps(answer)
    dataset = api.metadata["hourly"]["large"]
    assert _value_in_the_answer(api, dataset, dataset["temperature_air_2m"]) == _SAMPLE
