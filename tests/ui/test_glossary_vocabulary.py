# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The glossary answers exactly the parameters the networks offer, on every surface (GH-3876).

The canonical table also names the quality marks of the sources (`quality`, `quality_wind`, ...). They are no
parameters: they are never requested and come back in the `quality_flags` column, which the quality-flags page of the
docs explains. Listing them made the glossary page say 641 where the homepage said 635 for the same vocabulary.

Offline: everything is read out of the metadata models.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from wetterdienst import Wetterdienst
from wetterdienst.metadata.parameter_table import PARAMETER_TABLE
from wetterdienst.model.metadata import ParameterModel, is_quality_flag
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli
from wetterdienst.ui.core import get_glossary
from wetterdienst.ui.providers import get_providers

QUALITY_NAMES = {"quality", "quality_3", "quality_6", "quality_general", "quality_precipitation", "quality_wind"}


def _offered() -> set[str]:
    """Collect the names every network declares: a parameter of a dataset, which a request can ask for."""
    metadata = [
        Wetterdienst.resolve(provider, network).metadata
        for provider, networks in Wetterdienst.registry.items()
        for network in networks
        if not Wetterdienst.is_standalone(provider, network)
    ]
    return {
        parameter.name for model in metadata for resolution in model for dataset in resolution for parameter in dataset
    }


def _names(entries: list) -> list[str]:
    return [entry["name"] for entry in entries]


@pytest.fixture
def client() -> TestClient:
    """Make a client of the app."""
    return TestClient(restapi.app, raise_server_exceptions=False)


def test_the_glossary_is_the_union_of_the_declared_parameters() -> None:
    """None of the offered parameters is missing and none is extra, so the counts cannot drift apart again."""
    offered = _offered()
    listed = _names(get_glossary())

    assert len(listed) == len(set(listed))
    assert set(listed) - offered == set()
    assert offered - set(listed) == set()
    assert not set(listed) & QUALITY_NAMES
    # the homepage counts the same names
    assert get_providers().metadata.counts.parameters == len(listed)


def test_the_quality_flags_are_the_six_marked_entries() -> None:
    """The table marks the six quality names, and `is_quality_flag` reads the mark."""
    assert {parameter.name for parameter in PARAMETER_TABLE if parameter.quality_flag} == QUALITY_NAMES
    for name in QUALITY_NAMES:
        assert is_quality_flag(ParameterModel(name=name, name_original="x", unit="dimensionless"))
    assert not is_quality_flag(ParameterModel(name="temperature_air_mean_2m", name_original="x", unit="degree_celsius"))


@pytest.mark.parametrize("path", ["/api/glossary", "/api/v1/glossary"])
def test_rest_answers_the_union(client: TestClient, path: str) -> None:
    """The glossary has one entry per offered parameter on the alias and on v1, and the filters still work."""
    response = client.get(path)
    assert response.status_code == 200
    assert set(_names(response.json())) == _offered()

    radiation = client.get(path, params={"parameter": "radiation"}).json()
    assert radiation
    assert all("radiation" in name for name in _names(radiation))
    temperature = client.get(path, params={"unit_type": "temperature"}).json()
    assert temperature
    assert {entry["unit_type"] for entry in temperature} == {"temperature"}
    assert len(client.get(path, params={"limit": 3}).json()) == 3


@pytest.mark.parametrize("name", sorted(QUALITY_NAMES))
def test_a_quality_name_is_found_like_any_unknown_name(client: TestClient, name: str) -> None:
    """Asked for by its name, a quality flag is a 200 with nothing in it, as for `not_a_parameter`."""
    response = client.get("/api/glossary", params={"parameter": name})
    assert response.status_code == 200
    assert response.json() == []


def test_cli_answers_the_union() -> None:
    """`wetterdienst glossary` lists the same names."""
    result = CliRunner().invoke(cli, ["glossary"])
    assert result.exit_code == 0
    assert set(_names(json.loads(result.stdout))) == _offered()


def test_mcp_answers_the_union() -> None:
    """The MCP tool `glossary` lists the same names."""
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def _call() -> object:
        async with Client(build_mcp_server(restapi.app)) as mcp:
            return (await mcp.call_tool("glossary", {})).structured_content

    answer = asyncio.run(_call())
    entries = answer["result"] if isinstance(answer, dict) and "result" in answer else answer
    assert set(_names(entries)) == _offered()
