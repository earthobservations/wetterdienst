# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""`aggregation` and `timestamp_position` on the surfaces: `coverage`, `glossary` and `metadata.parameters` (GH-3134).

The two fields are declared in the metadata of the providers (and tested there); these tests hold what a caller gets:
the right value for a few known rows, `null` where nothing is stated, the same answer on REST, the command line and
MCP, and the members of the two closed sets, which are the model's, the Python types' and the OpenAPI document's.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import replace
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, get_args

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from tests.ui.test_restapi import _values_result_of_shape
from wetterdienst import Wetterdienst
from wetterdienst.metadata.parameter_table import AGGREGATION_DEFINITIONS, PARAMETER_TABLE, Aggregation
from wetterdienst.model.metadata import TIMESTAMP_POSITION_DEFINITIONS, TimestampPosition
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.provider.dmi.observation import DmiObservationRequest
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli
from wetterdienst.ui.core import get_glossary, resolve_network
from wetterdienst.ui.response_metadata import response_metadata

if TYPE_CHECKING:
    from collections.abc import Iterator

AGGREGATIONS = set(get_args(Aggregation))
POSITIONS = set(get_args(TimestampPosition))
#: (provider, network, resolution, dataset, parameter, aggregation, timestamp_position): known rows of the metadata
KNOWN = [
    # the name decides the aggregation, and DWD says nothing of where the daily stamp sits in its dataset
    ("dwd", "observation", "daily", "climate_summary", "temperature_air_max_2m", "max", None),
    # a mixed dataset: the parameters of DMI hourly differ, and each has its own position
    ("dmi", "observation", "hourly", "data", "wind_direction_mean_last_10min", "mean", "end"),
    ("dmi", "observation", "hourly", "data", "cloud_cover_total", "instant", "instant"),
    # a plain name that states nothing is not a reading
    ("dwd", "observation", "daily", "climate_summary", "cloud_cover_total_mean", "mean", None),
]


@pytest.fixture
def client() -> TestClient:
    """Make a client of the app."""
    return TestClient(restapi.app, raise_server_exceptions=False)


def _parameter(answer: dict[str, Any], resolution: str, dataset: str, name: str) -> dict[str, Any]:
    return next(p for p in answer[resolution]["datasets"][dataset]["parameters"] if p["name"] == name)


def _timeseries_networks() -> Iterator[type[TimeseriesRequest]]:
    for provider, names in Wetterdienst.registry.items():
        for network in names:
            api = resolve_network(provider, network)
            if isinstance(api, type) and issubclass(api, TimeseriesRequest):
                yield api


# --- the known rows ---------------------------------------------------------------------------------


@pytest.mark.parametrize(("provider", "network", "resolution", "dataset", "name", "aggregation", "position"), KNOWN)
def test_coverage_gives_each_parameter_its_aggregation_and_position(
    client: TestClient,
    provider: str,
    network: str,
    resolution: str,
    dataset: str,
    name: str,
    aggregation: str | None,
    position: str | None,
) -> None:
    """The member is there, with the value of the row: `null` where the source states none, never absent."""
    answer = client.get(
        "/api/coverage",
        params={"provider": provider, "network": network, "resolutions": resolution, "datasets": dataset},
    ).json()
    entry = _parameter(answer, resolution, dataset, name)
    assert "aggregation" in entry
    assert "timestamp_position" in entry
    assert (entry["aggregation"], entry["timestamp_position"]) == (aggregation, position)


def _every_parameter() -> Iterator[dict[str, Any]]:
    for api in _timeseries_networks():
        for resolution in api.discover().values():
            for dataset in resolution["datasets"].values():
                yield from dataset["parameters"]


def test_a_name_the_source_states_nothing_of_is_null_and_a_reading_is_instant() -> None:
    """Some parameters say `null` (not stated, the strict rule) and some `instant` (a provider's declaration)."""
    aggregations = {parameter["aggregation"] for parameter in _every_parameter()}
    assert None in aggregations
    assert "instant" in aggregations


def test_every_parameter_of_every_network_has_both_members_in_their_sets() -> None:
    """Both members are required and nullable, and hold a member of their set where they hold a value."""
    seen = 0
    for parameter in _every_parameter():
        seen += 1
        assert parameter["aggregation"] is None or parameter["aggregation"] in AGGREGATIONS, parameter
        assert parameter["timestamp_position"] is None or parameter["timestamp_position"] in POSITIONS, parameter
    assert seen > 2000


def test_coverage_follows_the_model() -> None:
    """Give the effective value of the model: the provider's declaration, else the name's; own, else the dataset's."""
    for api in _timeseries_networks():
        described = api.discover()
        for resolution in api.metadata:
            for dataset in resolution:
                for parameter in dataset:
                    entry = _parameter(described, resolution.name, dataset.name, parameter.name)
                    assert entry["aggregation"] == parameter.effective_aggregation
                    assert entry["timestamp_position"] == parameter.effective_timestamp_position


def test_the_dataset_position_is_the_one_of_a_parameter_without_its_own() -> None:
    """A parameter that declares none has the position of its dataset, and its own where it declares one."""
    declared_own = declared_dataset = 0
    for api in _timeseries_networks():
        for resolution in api.metadata:
            for dataset in resolution:
                for parameter in dataset:
                    if parameter.timestamp_position is not None:
                        declared_own += 1
                        assert parameter.effective_timestamp_position == parameter.timestamp_position
                    elif dataset.timestamp_position is not None:
                        declared_dataset += 1
                        assert parameter.effective_timestamp_position == dataset.timestamp_position
    assert declared_own
    assert declared_dataset


# --- the glossary -----------------------------------------------------------------------------------


def test_glossary_has_the_canonical_aggregation_and_no_position(client: TestClient) -> None:
    """The value of the name, `null` for a plain name; the glossary knows no dataset and so no position."""
    entries = client.get("/api/glossary", params={"parameter": "temperature_air"}).json()
    by_name = {entry["name"]: entry for entry in entries}
    assert by_name["temperature_air_max_2m"]["aggregation"] == "max"
    assert by_name["temperature_air_max_2m_mean"]["aggregation"] == "mean_of_max"
    assert by_name["temperature_air_mean_2m"]["aggregation"] == "mean"
    assert by_name["temperature_air_2m"]["aggregation"] is None
    assert all("aggregation" in entry for entry in entries)
    assert not any("timestamp_position" in entry for entry in entries)


def test_glossary_is_the_table() -> None:
    """Every entry has the canonical value of its row of the table."""
    entries = get_glossary()
    assert entries
    table = {parameter.name: parameter.aggregation for parameter in PARAMETER_TABLE}
    assert {entry["name"]: entry["aggregation"] for entry in entries} == {
        name: table[name] for name in (entry["name"] for entry in entries)
    }


# --- the metadata block ------------------------------------------------------------------------------


def test_the_parameters_of_the_metadata_block_have_both() -> None:
    """`metadata.parameters` of a values answer says, per parameter, what the model says."""
    request = DmiObservationRequest(
        parameters=[
            ("hourly", "data", "wind_direction_mean_last_10min"),
            ("hourly", "data", "cloud_cover_total"),
            ("hourly", "data", "temperature_air_mean_2m"),
        ],
    )
    stations = replace(_values_result_of_shape("long").stations, request=request)

    metadata = response_metadata(stations, SimpleNamespace(provider="dmi", network="observation", with_metadata=True))

    got = {p.name: (p.aggregation, p.timestamp_position) for p in metadata.parameters or []}
    assert got["wind_direction_mean_last_10min"] == ("mean", "end")
    assert got["cloud_cover_total"] == ("instant", "instant")
    dumped = metadata.model_dump(mode="json")["parameters"]
    assert all({"aggregation", "timestamp_position"} <= set(entry) for entry in dumped)


def test_the_block_of_a_values_answer_over_rest(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The rendered block of the route has both members for the parameter of the stubbed answer."""
    from tests.ui.test_response_metadata import _params, _stub_result  # noqa: PLC0415

    _stub_result(monkeypatch, "/api/values")
    heavy = client.get("/api/values", params=_params("/api/values", with_metadata="true")).json()
    temperature = next(p for p in heavy["metadata"]["parameters"] if p["name"] == "temperature_air_mean_2m")
    assert temperature["aggregation"] == "mean"
    assert "timestamp_position" in temperature


# --- the sets ------------------------------------------------------------------------------------------


def test_the_members_are_the_closed_sets_of_the_model() -> None:
    """The `Literal`s are the sets the definitions are written for, and what the metadata declares is in them."""
    assert set(AGGREGATION_DEFINITIONS) == AGGREGATIONS
    assert set(TIMESTAMP_POSITION_DEFINITIONS) == POSITIONS
    assert {
        "instant", "mean", "max", "min", "sum", "count", "mean_of_max", "mean_of_min", "probability",
        "occurrence", "date", "change", "uncertainty", "code", "at_max",
    } == AGGREGATIONS  # fmt: skip
    assert {"instant", "start", "end", "middle"} == POSITIONS


def _enum_of(schema: dict[str, Any], model: str, member: str) -> list[str]:
    """Give the members of the enum of a nullable member of a model of the OpenAPI document."""
    (enum,) = (
        alternative["enum"]
        for alternative in schema["components"]["schemas"][model]["properties"][member]["anyOf"]
        if "enum" in alternative
    )
    return enum


def test_the_openapi_enums_are_the_sets_in_order(client: TestClient) -> None:
    """The three models that carry the members describe them as the enum of the `Literal`, `null` besides."""
    schema = client.get("/openapi.json").json()
    for model, member, members in [
        ("CoverageParameter", "aggregation", get_args(Aggregation)),
        ("CoverageParameter", "timestamp_position", get_args(TimestampPosition)),
        ("GlossaryEntry", "aggregation", get_args(Aggregation)),
        ("ParameterInfo", "aggregation", get_args(Aggregation)),
        ("ParameterInfo", "timestamp_position", get_args(TimestampPosition)),
    ]:
        assert _enum_of(schema, model, member) == list(members), (model, member)
        assert model in schema["components"]["schemas"]
        assert member in schema["components"]["schemas"][model]["required"], "required, and nullable"
    assert "timestamp_position" not in schema["components"]["schemas"]["GlossaryEntry"]["properties"]


# --- one answer on every surface -------------------------------------------------------------------------


def _mcp(tool: str, arguments: dict[str, str]) -> Any:  # noqa: ANN401
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def call() -> Any:  # noqa: ANN401
        async with Client(build_mcp_server(restapi.app)) as mcp:
            return (await mcp.call_tool(tool, arguments)).structured_content

    return asyncio.run(call())


def test_coverage_is_the_same_on_rest_the_command_line_and_mcp(client: TestClient) -> None:
    """The three give the same parameters, the two members included."""
    arguments = {"provider": "dmi", "network": "observation", "resolutions": "hourly", "datasets": "data"}
    rest = client.get("/api/coverage", params=arguments).json()
    run = CliRunner().invoke(
        cli, ["about", "coverage", "--provider=dmi", "--network=observation", "--resolutions=hourly", "--datasets=data"]
    )
    assert run.exit_code == 0, run.output
    assert json.loads(run.output) == rest
    assert _mcp("coverage", arguments) == rest
    assert _parameter(rest, "hourly", "data", "cloud_cover_total")["aggregation"] == "instant"


def test_glossary_is_the_same_on_rest_the_command_line_and_mcp(client: TestClient) -> None:
    """The three give the same entries, `aggregation` included."""
    rest = client.get("/api/glossary", params={"parameter": "wind_direction_gust"}).json()
    run = CliRunner().invoke(cli, ["about", "glossary", "--parameter=wind_direction_gust"])
    assert run.exit_code == 0, run.output
    assert json.loads(run.output) == rest
    assert _mcp("glossary", {"parameter": "wind_direction_gust"}) == {"result": rest}
    assert {entry["aggregation"] for entry in rest} >= {"at_max"}


def test_the_tools_and_instructions_say_what_the_members_are(client: TestClient) -> None:
    """The MCP instructions and the descriptions of the three routes name both members and that `null` is not stated."""
    from wetterdienst.ui.mcp import INSTRUCTIONS  # noqa: PLC0415

    flat = " ".join(INSTRUCTIONS.split())
    for phrase in ("`aggregation`", "`timestamp_position`", "`instant` is a single reading", "`null`", "not a reading"):
        assert phrase in flat, phrase
    paths = client.get("/openapi.json").json()["paths"]
    for path, members in [
        ("/api/v1/coverage", ("aggregation", "timestamp_position")),
        ("/api/v1/glossary", ("aggregation",)),
        ("/api/v1/values", ("aggregation", "timestamp_position")),
    ]:
        description = paths[path]["get"]["description"]
        assert all(f"`{member}`" in description for member in members), path
