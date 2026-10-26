# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What the MCP instructions tell a model about the country of a provider and the stations near a place (GH-3456).

A model asked for the forecast for Los Angeles refused it: `dwd/mosmix` is a German provider's, it took it for a
forecast for Germany. The `country` of a provider is its operator's, and says nothing of where its stations are. The
instructions are kept generic (no word about a particular provider or network, whose reach the data and not the text
has to answer), and say two things, which these tests hold to:

- the `country` of a provider is its operator's and no reason to refuse a place, and the same two steps, `stations`
  then `values`, serve a network of every `kind`, for a point and not only a name: by key phrases, not by the exact
  wording, which is improved without a new version, and
- the arguments the example call names are arguments of the tool that takes them.
"""

from __future__ import annotations

import ast
import asyncio
import re
from typing import TYPE_CHECKING, Any

import pytest

from wetterdienst.ui import restapi
from wetterdienst.ui.mcp import INSTRUCTIONS
from wetterdienst.ui.providers import Provider

if TYPE_CHECKING:
    from collections.abc import Callable


def _text(*phrases: str) -> Callable[[str], bool]:
    """Say whether a text holds every phrase, in any case and whatever the white space."""

    def holds(text: str) -> bool:
        flat = " ".join(text.lower().split())
        return all(phrase.lower() in flat for phrase in phrases)

    return holds


@pytest.mark.parametrize(
    ("what", "holds"),
    [
        pytest.param("the country as the operator's", _text("`country`", "operator", "not the extent"), id="country"),
        pytest.param(
            "that it is no reason to refuse a place", _text("never conclude", "cannot serve a place"), id="refusal"
        ),
        pytest.param(
            "what to look at instead",
            _text("`kind`", "its `extent`", "what `stations` returns near the place"),
            id="instead",
        ),
        pytest.param(
            "the same steps for every kind", _text("same two steps", "any `kind`", "`forecast`"), id="every-kind"
        ),
        pytest.param(
            "the providers tool as the one for what reaches a place",
            _text("`providers`", "`extent` of each", "networks reach a place"),
            id="providers",
        ),
        pytest.param(
            "a point for the stations", _text("`latitude`", "`longitude`", "`rank`", "`distance`"), id="point"
        ),
    ],
)
def test_the_instructions_say(what: str, holds: Callable[[str], bool]) -> None:
    """The instructions carry what a model needs to not take the country of a provider for where its data is."""
    assert holds(INSTRUCTIONS), f"the instructions no longer say {what}"


def test_the_instructions_name_no_network_for_its_reach() -> None:
    """They say nothing of where a particular network has stations: that is for the data to answer, and it changes."""
    section = INSTRUCTIONS.partition("The same two steps serve a network")[2].partition("## Choosing a tool")[0]
    assert section, "the generic paragraph is gone"
    # a provider/network pair of the registry, named in the paragraph, would be a fact about its reach
    assert not re.search(r"\b(dwd|noaa|eccc|metno|knmi)/\w+", section)
    assert not _text("worldwide")(section)
    assert not _text("global")(section)


def test_the_instructions_stay_compact() -> None:
    """They are read on every connection: the paragraph on the country and the point fits in what it costs."""
    assert len(INSTRUCTIONS) < 7800


def test_the_country_of_a_provider_is_described_as_the_operators() -> None:
    """The schema, which the REST docs and the MCP tool schemas of `providers` come from, says what `country` is."""
    properties = Provider.model_json_schema()["properties"]
    assert _text("agency that runs", "not the extent of its data")(properties["country"]["description"])
    assert _text("operator's", "not the extent of its data")(properties["country_code"]["description"])


def _tools() -> dict[str, Any]:
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def listed() -> dict[str, Any]:
        async with Client(build_mcp_server(restapi.app)) as client:
            return {tool.name: tool for tool in await client.list_tools()}

    return asyncio.run(listed())


def test_the_providers_tool_says_what_its_country_is() -> None:
    """The tool a model asks which networks reach a place is described with the operator's country and the extent."""
    description = _tools()["providers"].description or ""

    assert _text("country of the agency that runs it", "not the extent of its data", "`extent`")(description)


def test_the_example_names_arguments_the_tool_takes() -> None:
    """The `stations` call of the instructions, written with placeholders, uses only arguments the tool has."""
    calls = re.findall(r"^\s+stations\((.*<provider>.*)\)\s*$", INSTRUCTIONS, flags=re.MULTILINE)
    assert len(calls) == 1, "the instructions have no single example with placeholders"
    # the placeholders are no Python: read the names of the arguments, as a model would write them
    call = ast.parse(re.sub(r"<(\w+)>", r"\1", f"stations({calls[0]})"), mode="eval").body
    assert isinstance(call, ast.Call)
    named = {keyword.arg for keyword in call.keywords}

    taken = set(_tools()["stations"].input_schema["properties"])

    assert {"provider", "network", "parameters", "latitude", "longitude", "rank"} <= named
    assert named <= taken, f"stations does not take {sorted(named - taken)}"
