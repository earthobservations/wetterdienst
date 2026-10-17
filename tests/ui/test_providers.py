# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What each provider is: `/api/providers`, `wetterdienst about providers` and the MCP tool `providers` (GH-2565).

Offline: the answer is read out of the metadata models, so nothing is stood in for.
"""

from __future__ import annotations

import json
from typing import Any

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from wetterdienst import Wetterdienst
from wetterdienst.model.metadata import MetadataModel
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli
from wetterdienst.ui.providers import get_providers

#: the members of the block of an answer about the library
CATALOGUE = {"api_version", "schema_version", "retrieved_at", "producer", "counts", "warnings"}


@pytest.fixture
def client() -> TestClient:
    """Make a client of the app."""
    return TestClient(restapi.app, raise_server_exceptions=False)


def _timeseries_metadata() -> list[tuple[str, str, MetadataModel]]:
    return [
        (provider, network, Wetterdienst.resolve(provider, network).metadata)
        for provider, networks in Wetterdienst.registry.items()
        for network in networks
        if not Wetterdienst.is_standalone(provider, network)
    ]


def _untimed(body: dict[str, Any]) -> dict[str, Any]:
    return {**body, "metadata": {**body["metadata"], "retrieved_at": ""}}


@pytest.mark.parametrize("field", ["name_english", "name_local", "country", "country_code", "license", "attribution"])
def test_the_networks_of_a_provider_agree_on_what_the_provider_is(field: str) -> None:
    """A provider is described once, by its first network, so the others must say the same of it."""
    declared: dict[str, set[str]] = {}
    for provider, _, metadata in _timeseries_metadata():
        declared.setdefault(provider, set()).add(repr(getattr(metadata, field)))
    assert {provider: values for provider, values in declared.items() if len(values) > 1} == {}


def test_a_country_has_one_code_and_a_code_one_country() -> None:
    """`country_code` is two capital letters, and the pairs of the registry are one to one."""
    pairs = {(metadata.country, metadata.country_code) for _, _, metadata in _timeseries_metadata()}
    assert all(code is not None and len(code) == 2 and code.isupper() for _, code in pairs)
    assert len({country for country, _ in pairs}) == len(pairs) == len({code for _, code in pairs})


@pytest.mark.parametrize(
    ("code", "valid"),
    [(None, True), ("DE", True), ("ZZ", True), ("de", False), ("DEU", False), ("", False)],
)
def test_the_country_code_is_an_alpha_2_code_or_null_for_several_countries(code: str | None, *, valid: bool) -> None:
    """A malformed code is refused when the declaration is built, not found in an answer; null is the multinational."""
    declared = _timeseries_metadata()[0][2].model_dump()
    if valid:
        assert MetadataModel.model_validate({**declared, "country_code": code}).country_code == code
    else:
        with pytest.raises(ValueError, match="ISO 3166-1 alpha-2"):
            MetadataModel.model_validate({**declared, "country_code": code})


def test_a_provider_of_several_countries_has_a_null_country_code(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """No registered provider is multinational yet, so one is stood in for: the answer says null, not a marker."""
    monkeypatch.setattr(Wetterdienst.resolve("dwd", "observation").metadata, "country_code", None)

    body = client.get("/api/v1/providers", params={"provider": "dwd"}).json()

    assert body["providers"][0]["provider"] == "dwd"
    assert body["providers"][0]["country_code"] is None


def test_the_providers_are_the_registry_and_sorted_by_name(client: TestClient) -> None:
    """Every provider of the registry is listed once, by the name a reader sorts them by."""
    response = client.get("/api/v1/providers")

    assert response.status_code == 200, response.text
    body = response.json()
    names = [provider["provider"] for provider in body["providers"]]
    assert sorted(names) == sorted(Wetterdienst.registry)
    english = [provider["name_english"].casefold() for provider in body["providers"]]
    assert english == sorted(english)
    assert set(body["metadata"]) == CATALOGUE
    assert body["metadata"]["counts"] == {
        "providers": len(Wetterdienst.registry),
        "networks": sum(len(networks) for networks in Wetterdienst.registry.values()),
    }
    assert body["metadata"]["warnings"] == []
    assert response.headers["X-Wetterdienst-API-Version"] == "1"


def test_a_provider_carries_the_terms_its_metadata_declares() -> None:
    """The licence and the credit line are the ones of the metadata models: read out, not written again."""
    answer = get_providers()

    for provider in answer.providers:
        metadata = Wetterdienst.resolve(provider.provider, provider.networks[0].network).metadata
        assert provider.license == metadata.license
        assert provider.attribution == metadata.attribution
        assert (provider.country, provider.country_code) == (metadata.country, metadata.country_code)
    dwd = next(provider for provider in answer.providers if provider.provider == "dwd")
    assert dwd.license is not None
    assert dwd.license.spdx_id == "CC-BY-4.0"
    assert (dwd.country, dwd.country_code) == ("Germany", "DE")


def test_the_networks_are_those_coverage_lists_with_what_they_offer(client: TestClient) -> None:
    """Each network says what `/api/coverage` says of it, and counts what its metadata holds."""
    coverage = client.get("/api/coverage").json()
    providers = {provider["provider"]: provider for provider in client.get("/api/providers").json()["providers"]}

    assert set(providers) == set(coverage)
    for name, networks in coverage.items():
        listed = {network["network"]: network for network in providers[name]["networks"]}
        assert set(listed) == set(networks)
        for network, described in networks.items():
            assert listed[network]["kind"] == described["kind"]
            assert listed[network]["url"] == described["url"]
            assert listed[network]["auth"] == described["auth"]
            assert listed[network]["date_required"] == described["date_required"]
    observation = next(n for n in providers["dwd"]["networks"] if n["network"] == "observation")
    metadata = Wetterdienst.resolve("dwd", "observation").metadata
    assert [r["name"] for r in observation["resolutions"]] == [r.name for r in metadata]
    assert observation["parameters"] == sum(len(d.parameters) for r in metadata for d in r.datasets)
    daily = next(r for r in observation["resolutions"] if r["name"] == "daily")
    assert {"name": "climate_summary", "parameters": len(metadata["daily"]["climate_summary"].parameters)} in daily[
        "datasets"
    ]


def test_the_standalone_networks_of_dwd_are_listed_without_resolutions(client: TestClient) -> None:
    """`dwd/radar` and `dwd/alerts` have no metadata model: they are listed with their kind and terms, no counts."""
    (dwd,) = client.get("/api/providers", params={"provider": "dwd"}).json()["providers"]

    standalone = {network["network"]: network for network in dwd["networks"] if network["kind"] in ("radar", "alerts")}
    assert set(standalone) == {"radar", "alerts"}
    for network in standalone.values():
        assert (network["resolutions"], network["parameters"], network["auth"]) == ([], 0, False)
        assert network["copyright"].startswith("© Deutscher Wetterdienst (DWD)")
    assert standalone["alerts"]["url"] == "https://opendata.dwd.de/weather/alerts/cap"


def test_one_provider_can_be_asked_for_and_an_unknown_one_is_a_404(client: TestClient) -> None:
    """`provider` narrows the answer, case-insensitively, and names the way to the list where it finds none."""
    (only,) = client.get("/api/providers", params={"provider": "DWD"}).json()["providers"]
    missing = client.get("/api/providers", params={"provider": "nowhere"})

    assert only["provider"] == "dwd"
    assert missing.status_code == 404
    assert "/api/providers" in missing.json()["detail"]


def test_the_alias_gives_the_same_answer(client: TestClient) -> None:
    """`/api/providers` is `/api/v1/providers`."""
    assert _untimed(client.get("/api/providers").json()) == _untimed(client.get("/api/v1/providers").json())


def test_the_answer_needs_no_credential_and_no_network(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing is downloaded or probed: a key is not read, and `auth` only says whether a network needs one."""
    monkeypatch.setattr(Wetterdienst, "is_valid", lambda _api: pytest.fail("a credential was probed"))
    monkeypatch.setattr(Wetterdienst, "is_configured", lambda _api: pytest.fail("a credential was read"))

    body = client.get("/api/providers").json()

    needs = {
        (provider["provider"], network["network"])
        for provider in body["providers"]
        for network in provider["networks"]
        if network["auth"]
    }
    assert ("aemet", "observation") in needs


def test_the_command_line_gives_the_answer_of_rest(client: TestClient) -> None:
    """The same request gives the same answer on both surfaces, but for the time it was made at."""
    rest = client.get("/api/providers", params={"provider": "wsv"}).json()

    result = CliRunner().invoke(cli, ["about", "providers", "--provider=wsv"])

    assert result.exit_code == 0, result.output
    assert _untimed(json.loads(result.stdout)) == _untimed(rest)


def test_the_command_line_refuses_an_unknown_provider() -> None:
    """A provider that is not there is a usage error that says how to list them."""
    result = CliRunner().invoke(cli, ["about", "providers", "--provider=nowhere"])

    assert result.exit_code == 2
    assert "wetterdienst about providers" in result.output


def test_the_mcp_tool_is_the_endpoint() -> None:
    """An agent asks `providers` and gets the answer, the block first."""
    pytest.importorskip("fastmcp")
    import asyncio  # noqa: PLC0415

    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def call() -> dict[str, Any]:
        async with Client(build_mcp_server(restapi.app)) as client:
            return (await client.call_tool("providers", {"provider": "dwd"})).structured_content or {}

    answer = asyncio.run(call())
    assert answer["providers"][0]["provider"] == "dwd"
    assert set(answer["metadata"]) == CATALOGUE


def test_a_network_that_cannot_be_imported_is_left_out_and_told(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A deployment missing a dependency lists what it has, and says what is missing in the warnings."""
    real = Wetterdienst.resolve

    def broken(provider: str, network: str) -> Any:  # noqa: ANN401
        if (provider, network) == ("dwd", "road"):
            msg = "No module named 'pdbufr'"
            raise ImportError(msg)
        return real(provider, network)

    monkeypatch.setattr(Wetterdienst, "resolve", broken)

    body = client.get("/api/providers", params={"provider": "dwd"}).json()

    assert "road" not in {network["network"] for network in body["providers"][0]["networks"]}
    assert [warning["code"] for warning in body["metadata"]["warnings"]] == ["network-not-importable"]
    assert "dwd/road" in body["metadata"]["warnings"][0]["message"]
