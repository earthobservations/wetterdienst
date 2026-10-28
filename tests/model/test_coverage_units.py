# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The units `coverage` reports: `unit` is the unit of the values, `unit_source` the provider's own (GH-3537)."""

from types import SimpleNamespace
from typing import Any

import pytest

from wetterdienst import Wetterdienst
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.unit import UnitConverter
from wetterdienst.model.values import TimeseriesValues
from wetterdienst.ui.core import get_glossary, resolve_network

# a reading in each magnitude a conversion shows: zero, a unit, a plain value and a large one
_SAMPLES = (0.0, 1.0, 21.5, 100.0)


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
        # nothing to convert: both are the same
        (
            "dwd",
            "observation",
            "daily",
            "climate_summary",
            "temperature_air_mean_2m",
            "temperature",
            "degree_celsius",
            "degree_celsius",
        ),
    ],
)
def test_unit_is_the_unit_of_the_values_and_unit_source_the_providers(
    provider: str,
    network: str,
    resolution: str,
    dataset: str,
    name: str,
    unit_type: str,
    unit: str,
    unit_source: str,
) -> None:
    """Test that the unit of a parameter is the one its values come in, the provider's own beside it."""
    api = resolve_network(provider, network)
    assert issubclass(api, TimeseriesRequest)
    parameters = api.discover(resolutions=resolution, datasets=dataset)[resolution]["datasets"][dataset]["parameters"]
    parameter = next(p for p in parameters if p["name"] == name)
    assert parameter["unit_type"] == unit_type
    assert parameter["unit"] == unit
    assert parameter["unit_source"] == unit_source


def _parameters() -> list[tuple[str, str, type[TimeseriesRequest], str, str, dict[str, Any]]]:
    parameters = []
    for provider, network, api in _NETWORKS:
        for resolution, resolution_entry in api.discover().items():
            for dataset, dataset_entry in resolution_entry["datasets"].items():
                parameters.extend(
                    (provider, network, api, resolution, dataset, parameter)
                    for parameter in dataset_entry["parameters"]
                )
    return parameters


def test_every_parameter_has_the_unit_a_conversion_of_its_values_returns() -> None:
    """Test that, for every parameter of every network, `unit` is where `values` converts a value to.

    The conversion is the one `TimeseriesValues` builds for the parameter (`_create_conversions`), and the unit
    is read off the conversion it is, not off the same table: a value converted from `unit_source` to `unit`
    by the converter comes out the same as the value `values` returns.
    """
    converter = UnitConverter()
    values = SimpleNamespace(unit_converter=converter)
    wrong = []
    checked = 0
    for provider, network, api, resolution, dataset, parameter in _parameters():
        dataset_model = api.metadata[resolution][dataset]
        conversions = TimeseriesValues._create_conversions(values, dataset_model)  # ty: ignore[invalid-argument-type]  # noqa: SLF001
        lambda_, decimals = conversions[dataset_model[parameter["name"]].name_original.lower()]
        into_unit = converter._get_lambda(parameter["unit_source"], parameter["unit"])  # noqa: SLF001
        checked += 1
        for sample in _SAMPLES:
            if round(lambda_(sample), decimals) != round(into_unit(sample), decimals):
                wrong.append((provider, network, resolution, dataset, parameter["name"], sample))
                break
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


def test_unit_source_of_every_parameter_is_the_unit_the_provider_declares() -> None:
    """Test that `unit_source` is the unit of the provider's own declaration, parameter for parameter."""
    wrong = []
    checked = 0
    for provider, network, api in _NETWORKS:
        for resolution, resolution_entry in api.discover().items():
            for dataset, dataset_entry in resolution_entry["datasets"].items():
                declared = list(api.metadata[resolution][dataset])
                assert len(declared) == len(dataset_entry["parameters"])
                for model, parameter in zip(declared, dataset_entry["parameters"], strict=True):
                    checked += 1
                    if (model.name, model.unit) != (parameter["name"], parameter["unit_source"]):
                        wrong.append((provider, network, resolution, dataset, parameter["name"]))
    assert checked > 2000
    assert not wrong, f"{len(wrong)} parameters whose `unit_source` is not the declared unit: {wrong[:5]}"


def test_the_two_units_differ_for_the_parameters_that_are_converted() -> None:
    """Test that the checks above are not vacuous: a good part of the parameters is converted."""
    differing = sum(parameter["unit"] != parameter["unit_source"] for *_, parameter in _parameters())
    # 362 of 2048 in 29 networks when this was written: a floor, so that a new network does not fail it
    assert differing >= 300
