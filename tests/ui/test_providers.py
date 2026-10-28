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


@pytest.mark.parametrize(
    "field", ["name_short", "name_english", "name_local", "country", "country_code", "license", "attribution"]
)
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
    # an extent that is no one country's, so that the country of the provider is not the one it names
    declared = _timeseries_metadata()[0][2].model_dump()
    declared["extent"] = {
        **declared["extent"],
        "scope": "regional",
        "continents": ["europe", "africa"],
        "country_codes": [],
    }
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


def _declared_parameters() -> set[str]:
    """Give the different canonical names the networks with a metadata model declare."""
    return {
        parameter.name
        for provider, networks in Wetterdienst.registry.items()
        for network in networks
        if not Wetterdienst.is_standalone(provider, network)
        for resolution in Wetterdienst.resolve(provider, network).metadata
        for dataset in resolution
        for parameter in dataset
    }


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
        "parameters": len(_declared_parameters()),
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
        assert provider.name_short == metadata.name_short
    dwd = next(provider for provider in answer.providers if provider.provider == "dwd")
    assert dwd.license is not None
    assert dwd.license.spdx_id == "CC-BY-4.0"
    assert (dwd.country, dwd.country_code) == ("Germany", "DE")


def test_the_networks_are_those_coverage_lists_with_what_they_offer(client: TestClient) -> None:
    """Each network says what `/api/coverage` says of it, and counts what its metadata holds."""
    coverage = client.get("/api/coverage").json()
    providers = {
        provider["provider"]: provider
        for provider in client.get("/api/providers", params={"with_datasets": "true"}).json()["providers"]
    }

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
    (dwd,) = client.get("/api/providers", params={"provider": "dwd", "with_datasets": "true"}).json()["providers"]

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


def test_the_warning_of_a_network_that_cannot_be_imported_leaves_the_path_of_the_server_out(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The text of an `ImportError` can name a path of the server, which stays in the log (GH-3086)."""
    real = Wetterdienst.resolve

    def broken(provider: str, network: str) -> Any:  # noqa: ANN401
        if (provider, network) == ("dwd", "road"):
            msg = "cannot import name 'x' from 'y' (/srv/secret/site-packages/y/__init__.py)"
            raise ImportError(msg)
        if (provider, network) == ("dwd", "mosmix"):
            msg = "No module named 'pdbufr'"
            raise ModuleNotFoundError(msg, name="pdbufr")
        return real(provider, network)

    monkeypatch.setattr(Wetterdienst, "resolve", broken)

    body = client.get("/api/providers", params={"provider": "dwd"}).json()

    messages = [warning["message"] for warning in body["metadata"]["warnings"]]
    assert len(messages) == 2
    assert "/srv/secret" not in " ".join(messages)
    assert any("dwd/road" in message for message in messages)
    # a module that is missing is named, as that is for the caller to tell the operator
    assert any("dwd/mosmix" in message and "'pdbufr'" in message for message in messages)


def test_a_network_says_where_its_stations_are(client: TestClient) -> None:
    """Each network of the answer has its extent, which the `country` of its provider does not say (GH-3456)."""
    body = client.get("/api/providers").json()

    extents = {
        f"{provider['provider']}/{network['network']}": network["extent"]
        for provider in body["providers"]
        for network in provider["networks"]
    }
    assert len(extents) == body["metadata"]["counts"]["networks"]
    # `country_codes` is left out of an answer where there are none and for a national network: it is the `country_code`
    assert all(
        {"scope", "continents", "bbox"} <= set(extent) <= {"scope", "continents", "country_codes", "bbox"}
        for extent in extents.values()
    )
    assert all("country_codes" not in extent for extent in extents.values() if extent["scope"] != "regional")
    # DWD is German, and so is its observation network; its forecast lists are the world's
    assert extents["dwd/observation"]["scope"] == "national"
    assert extents["dwd/observation"]["bbox"] == [5.8, 47.2, 15.1, 55.1]
    assert extents["dwd/mosmix"]["scope"] == "global"
    assert extents["dwd/mosmix"]["bbox"] == [-180, -90, 180, 90]
    assert {"north_america", "south_america", "africa", "asia", "oceania"} <= set(extents["dwd/mosmix"]["continents"])


def test_the_list_of_every_network_has_the_scope_and_not_the_extent(client: TestClient) -> None:
    """`/api/coverage` is kept short: it says how far each network reaches, and `/api/providers` where (GH-3456)."""
    providers = client.get("/api/providers").json()["providers"]
    coverage = client.get("/api/coverage").json()

    for provider in providers:
        for network in provider["networks"]:
            listed = coverage[provider["provider"]][network["network"]]
            assert listed["scope"] == network["extent"]["scope"]
            assert "extent" not in listed


def test_the_coverage_of_a_network_has_the_full_extent_of_each_dataset(client: TestClient) -> None:
    """With a provider and network, each dataset has its extent in full: its own, or else its network's."""
    providers = client.get("/api/providers", params={"provider": "dwd"}).json()["providers"][0]["networks"]
    network = next(n for n in providers if n["network"] == "mosmix")["extent"]

    coverage = client.get("/api/coverage", params={"provider": "dwd", "network": "mosmix"}).json()

    for resolution in coverage.values():
        for dataset in resolution["datasets"].values():
            assert dataset["extent"] == network
    assert network["scope"] == "global"
    assert network["bbox"] == [-180, -90, 180, 90]


def test_the_command_line_says_where_the_stations_are(client: TestClient) -> None:
    """`wetterdienst about providers` and `wetterdienst about coverage` have the extent the REST API has."""
    rest = client.get("/api/providers", params={"provider": "dwd"}).json()
    result = CliRunner().invoke(cli, ["about", "providers", "--provider=dwd"])
    assert result.exit_code == 0, result.output
    extents = {n["network"]: n["extent"] for n in json.loads(result.stdout)["providers"][0]["networks"]}
    assert extents == {n["network"]: n["extent"] for n in rest["providers"][0]["networks"]}

    result = CliRunner().invoke(cli, ["about", "coverage"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["dwd"]["mosmix"]["scope"] == "global"
    result = CliRunner().invoke(cli, ["about", "coverage", "--provider=dwd", "--network=dmo"])
    assert result.exit_code == 0, result.output
    assert json.loads(result.stdout)["hourly"]["datasets"]["icon_eu"]["extent"]["scope"] == "regional"


def test_the_mcp_tool_has_the_extent() -> None:
    """The tool `providers` answers the extent."""
    pytest.importorskip("fastmcp")
    import asyncio  # noqa: PLC0415

    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def call() -> dict[str, Any]:
        async with Client(build_mcp_server(restapi.app)) as client:
            return (await client.call_tool("providers", {"provider": "dwd"})).structured_content or {}

    networks = {n["network"]: n for n in asyncio.run(call())["providers"][0]["networks"]}
    assert networks["mosmix"]["extent"]["scope"] == "global"
    assert networks["observation"]["extent"]["scope"] == "national"
    assert "country_codes" not in networks["observation"]["extent"]


def test_a_dataset_narrower_than_its_network_has_an_extent_of_its_own(client: TestClient) -> None:
    """`dwd/dmo` is global and its `icon_eu` dataset is Europe's; every other dataset leaves `extent` out."""
    body = client.get("/api/providers", params={"with_datasets": "true"}).json()

    datasets = {
        (f"{provider['provider']}/{network['network']}", resolution["name"], dataset["name"]): dataset
        for provider in body["providers"]
        for network in provider["networks"]
        for resolution in network["resolutions"]
        for dataset in resolution["datasets"]
    }
    with_extent = {key for key, dataset in datasets.items() if "extent" in dataset}
    assert with_extent == {("dwd/dmo", "hourly", "icon_eu")}
    own = datasets["dwd/dmo", "hourly", "icon_eu"]["extent"]
    assert own["scope"] == "regional"
    assert "europe" in own["continents"]
    assert datasets["dwd/dmo", "hourly", "icon"].keys() == {"name", "parameters"}


def test_the_coverage_of_a_dataset_says_where_it_is_narrower_than_its_network(client: TestClient) -> None:
    """`/api/coverage` of a network gives each dataset its own extent where it has one, else its network's."""
    coverage = client.get("/api/coverage", params={"provider": "dwd", "network": "dmo"}).json()

    assert coverage["hourly"]["datasets"]["icon_eu"]["extent"]["bbox"] == [-13, 13, 50, 71]
    assert coverage["hourly"]["datasets"]["icon_eu"]["extent"]["scope"] == "regional"
    assert coverage["hourly"]["datasets"]["icon"]["extent"]["scope"] == "global"


def test_the_mcp_coverage_tool_is_short_for_every_network_and_full_for_one() -> None:
    """The tool `coverage` has the scope of each network in its list, and the extent of each dataset of one network."""
    pytest.importorskip("fastmcp")
    import asyncio  # noqa: PLC0415

    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def call(arguments: dict[str, str]) -> dict[str, Any]:
        async with Client(build_mcp_server(restapi.app)) as client:
            return (await client.call_tool("coverage", arguments)).structured_content or {}

    listed = asyncio.run(call({}))
    assert listed["dwd"]["mosmix"]["scope"] == "global"
    assert listed["dwd"]["observation"]["scope"] == "national"
    assert all("extent" not in network for networks in listed.values() for network in networks.values())

    one = asyncio.run(call({"provider": "dwd", "network": "dmo"}))
    assert one["hourly"]["datasets"]["icon"]["extent"]["scope"] == "global"
    assert one["hourly"]["datasets"]["icon_eu"]["extent"]["scope"] == "regional"


# the compact answer by default, the lists with `with_datasets=true`, and the credit line named (GH-3536)

#: how much of the long answer the compact one may be, in characters of the JSON: 0.57 for every provider and 0.30
#: for `dwd` when it was made, so a provider or a network to come moves neither much, and the lists of datasets,
#: which are the rest, cannot come back unseen
_COMPACT_SHARE = {None: 0.7, "dwd": 0.4}


def _resolutions_of(body: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        network["resolutions"]
        for provider in body["providers"]
        for network in provider["networks"]
        if "resolutions" in network
    ]


@pytest.mark.parametrize("provider", [None, "dwd"])
def test_the_default_answer_is_compact(client: TestClient, provider: str | None) -> None:
    """Without `with_datasets`, no network lists its resolutions and datasets, and the answer stays small."""
    params = {"provider": provider} if provider else {}
    response = client.get("/api/providers", params=params)
    full = client.get("/api/providers", params={**params, "with_datasets": "true"})

    body = response.json()
    assert _resolutions_of(body) == []
    share = len(response.text) / len(full.text)
    assert share < _COMPACT_SHARE[provider], (
        f"the default answer is {share:.0%} of the long one ({len(response.text)} of {len(full.text)} characters), "
        f"more than the {_COMPACT_SHARE[provider]:.0%} it may be: the lists of datasets are back in it, or the "
        "short form grew by a member that is no summary"
    )
    # everything else of a network is there: what a question of licence, credit or reach needs
    for described in body["providers"]:
        assert {"country", "country_code", "license", "attribution", "name_english"} <= set(described)
        for network in described["networks"]:
            assert set(network) == {
                "network",
                "kind",
                "extent",
                "url",
                "copyright",
                "auth",
                "date_required",
                "parameters",
            }
            assert network["copyright"]


@pytest.mark.parametrize("provider", [None, "dwd"])
def test_with_datasets_brings_the_lists_back_and_nothing_else_changes(client: TestClient, provider: str | None) -> None:
    """`with_datasets=true` is the compact answer with `resolutions` in each network, those that metadata lists."""
    params = {"provider": provider} if provider else {}
    compact = client.get("/api/providers", params=params).json()
    full = client.get("/api/providers", params={**params, "with_datasets": "true"}).json()

    assert len(_resolutions_of(full)) == compact["metadata"]["counts"]["networks"]
    for described in full["providers"]:
        for network in described["networks"]:
            if network["kind"] in ("radar", "alerts"):
                assert network["resolutions"] == []
                continue
            metadata = Wetterdienst.resolve(described["provider"], network["network"]).metadata
            assert [
                (resolution["name"], [(d["name"], d["parameters"]) for d in resolution["datasets"]])
                for resolution in network["resolutions"]
            ] == [
                (resolution.name, [(dataset.name, len(dataset.parameters)) for dataset in resolution])
                for resolution in metadata
            ]
    assert len(json.dumps(full)) > 1.5 * len(json.dumps(compact))
    # the same answer with the lists taken out
    for described in full["providers"]:
        for network in described["networks"]:
            del network["resolutions"]
    assert _untimed(full) == _untimed(compact)


def test_with_datasets_false_is_the_default(client: TestClient) -> None:
    """`with_datasets=false` is the answer without the parameter."""
    assert _untimed(client.get("/api/providers", params={"with_datasets": "false"}).json()) == _untimed(
        client.get("/api/providers").json()
    )


def test_the_command_line_and_the_python_function_have_the_option() -> None:
    """`--with-datasets` and `get_providers(with_datasets=True)` give the lists; the default is the compact answer."""
    compact = CliRunner().invoke(cli, ["about", "providers", "--provider=dwd"])
    bare = CliRunner().invoke(cli, ["about", "providers", "--provider=dwd", "--with-datasets"])
    explicit = CliRunner().invoke(cli, ["about", "providers", "--provider=dwd", "--with-datasets=true"])

    assert compact.exit_code == bare.exit_code == explicit.exit_code == 0
    assert _resolutions_of(json.loads(compact.stdout)) == []
    assert _untimed(json.loads(bare.stdout)) == _untimed(json.loads(explicit.stdout))
    assert len(_resolutions_of(json.loads(bare.stdout))) == len(json.loads(bare.stdout)["providers"][0]["networks"])
    assert all(network.resolutions is None for network in get_providers("dwd").providers[0].networks)
    assert all(
        network.resolutions is not None for network in get_providers("dwd", with_datasets=True).providers[0].networks
    )


def test_the_mcp_tool_takes_with_datasets() -> None:
    """The tool `providers` is compact, and lists the datasets with `with_datasets=true`."""
    pytest.importorskip("fastmcp")
    import asyncio  # noqa: PLC0415

    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def call(arguments: dict[str, Any]) -> dict[str, Any]:
        async with Client(build_mcp_server(restapi.app)) as client:
            return (await client.call_tool("providers", arguments)).structured_content or {}

    assert _resolutions_of(asyncio.run(call({"provider": "dwd"}))) == []
    assert len(_resolutions_of(asyncio.run(call({"provider": "dwd", "with_datasets": True})))) == len(
        get_providers("dwd").providers[0].networks
    )


def test_every_network_has_a_copyright() -> None:
    """`copyright` is the fallback credit line, so no network of any provider is without it."""
    for provider in get_providers().providers:
        for network in provider.networks:
            assert network.copyright.strip(), f"{provider.provider}/{network.network}"


def test_the_descriptions_name_the_credit_line_and_its_fallback() -> None:
    """`attribution` is the line to cite, `copyright` the one to cite where it is null: said where a caller reads it."""
    document = restapi.app.openapi()
    schemas = document["components"]["schemas"]
    attribution = schemas["Provider"]["properties"]["attribution"]["description"]
    copyright_ = schemas["ProviderNetwork"]["properties"]["copyright"]["description"]
    operation = document["paths"]["/api/v1/providers"]["get"]["description"]

    for text in (attribution, copyright_, operation):
        assert "cite" in text
        assert "attribution" in text or "`copyright`" in text
    assert "null" in attribution.lower()
    assert "`copyright`" in attribution
    assert "`attribution`" in copyright_
    assert "null" in copyright_.lower()
    assert "where it is null, cite the `copyright`" in operation

    result = CliRunner().invoke(cli, ["about", "providers", "--help"])
    assert "where it is null, cite the `copyright`" in " ".join(result.output.split())


def test_the_mcp_instructions_name_the_credit_line_without_a_provider() -> None:
    """The instructions say to cite `attribution`, and `copyright` where it is null, with no provider as an example."""
    pytest.importorskip("fastmcp")
    from wetterdienst.ui.mcp import INSTRUCTIONS  # noqa: PLC0415

    text = " ".join(INSTRUCTIONS.split())
    assert "Cite `attribution`, or the `copyright` where it is null" in text
