# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A route is told a name "was renamed" only if it had that name in 0.139.0 (GH-3869).

`RENAMED_REQUEST_PARAMETERS` names the old spelling of a parameter and the one that replaced it. Whether a route had
the old name is read from the release the renames are counted from (`tests/ui/routes_0_139_0.json`, the parameters of
each REST route and the options of each command in the code of `v0.139.0`): `stations` takes a `timestamp` only and
never had a `date`, so a `date` there is a name the route does not know, as it is on any other route. The same is true
of the MCP tool and the command, which take the route's parameters.

For every route and every old name, REST, MCP and the command line answer "renamed" exactly when the route had the
name in 0.139.0 (and has the new one, and not the old one still), and otherwise as for any parameter they do not know.
"""

from __future__ import annotations

import asyncio

import click
import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from tests.ui.routes_0_139_0 import RELEASE, read_routes
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli
from wetterdienst.ui.core import (
    OLD_NAMES_OF_ROUTE,
    OLD_UNDERSCORE_OPTIONS_OF_ROUTE,
    RENAMED_REQUEST_PARAMETERS,
    old_names_of_route,
)

BASELINE = read_routes()
# what a refusal says of a rename, and an answer for an unknown name never does
_RENAME_MARKER = "was renamed"


def _rest_routes() -> dict[str, tuple[str, set[str]]]:
    """Give the path and the parameters of every route the MCP tools are made of, by the name of the tool."""
    from wetterdienst.ui.mcp import _TOOL_NAMES  # noqa: PLC0415

    document = restapi.app.openapi()
    found = {}
    for path, item in document["paths"].items():
        route = path.removeprefix("/api/v1/").replace("/", "_")
        if path.startswith("/api/v1/") and route in _TOOL_NAMES.values():
            found[route] = (path, {parameter["name"] for parameter in item["get"].get("parameters", [])})
    return found


def _commands(group: click.Group, prefix: tuple[str, ...] = ()) -> dict[str, tuple[tuple[str, ...], click.Command]]:
    """Give each command by its route: the name of its tool, `coverage` for `about coverage`."""
    found = {}
    for name, command in group.commands.items():
        if isinstance(command, click.Group):
            found.update(_commands(command, (*prefix, name)))
        else:
            path = (*prefix, name)
            found["_".join(part for part in path if part != "about")] = (path, command)
    return found


def _visible(command: click.Command) -> set[str]:
    """Give the options a command takes, without the hidden ones, which are refusals."""
    return {
        opt.removeprefix("--")
        for param in command.params
        if isinstance(param, click.Option) and not param.hidden
        for opt in param.opts
    }


REST = _rest_routes()
COMMANDS = _commands(cli)


def _renamed_expected(had: set[str], taken: set[str], old: str) -> bool:
    """Tell whether the answer is a rename: the route had the old name, has the new one, and has not the old still."""
    new = RENAMED_REQUEST_PARAMETERS[old]
    return old in had and new in taken and old not in taken


def _mcp_answers() -> dict[tuple[str, str], str]:
    """Give the refusal of each tool for each old name it does not take as an argument."""
    from fastmcp import Client  # noqa: PLC0415
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def ask() -> dict[tuple[str, str], str]:
        answers = {}
        async with Client(build_mcp_server(restapi.app)) as client:
            tools = {tool.name: set(tool.input_schema.get("properties", {})) for tool in await client.list_tools()}
            for tool, taken in tools.items():
                for old in RENAMED_REQUEST_PARAMETERS:
                    if old in taken:
                        continue
                    try:
                        await client.call_tool(tool, {old: "x"})
                    except ToolError as error:
                        answers[tool, old] = str(error)
                    else:
                        answers[tool, old] = "answered"
        return answers

    return asyncio.run(ask())


def test_the_release_is_the_one_the_table_is_counted_from() -> None:
    """The file is the parameters of 0.139.0, with the routes REST and the command line had then."""
    assert RELEASE == "0.139.0"
    assert {"stations", "values", "alerts"} <= set(BASELINE["rest"])
    assert {"stations", "values", "alerts"} <= set(BASELINE["cli"])


def test_the_table_of_old_names_is_what_the_release_took() -> None:
    """`OLD_NAMES_OF_ROUTE` is each route's old names, as the code of the release declared them, not from memory."""
    derived = {}
    for routes in BASELINE.values():
        for route, names in routes.items():
            had = frozenset(old for old in RENAMED_REQUEST_PARAMETERS if old in {n.replace("-", "_") for n in names})
            if had:
                derived[route] = derived.get(route, frozenset()) | had

    assert derived == OLD_NAMES_OF_ROUTE


def test_a_route_added_since_the_release_had_no_old_name() -> None:
    """`providers` is no route of 0.139.0, so nothing was ever renamed on it."""
    assert "providers" not in BASELINE["rest"]
    assert old_names_of_route("providers") == frozenset()
    assert old_names_of_route("a-route-nobody-has") == frozenset()


def test_every_route_of_the_tools_is_compared() -> None:
    """The comparisons below are not empty: the routes are found, and the table has rows that decide something."""
    assert {"stations", "values", "providers", "coverage", "glossary", "alerts"} <= set(REST)
    assert {"stations", "values", "coverage", "glossary", "alerts"} <= set(COMMANDS)
    assert any(
        _renamed_expected(set(BASELINE["rest"].get(route, ())), REST[route][1], old)
        for route in REST
        for old in old_names_of_route(route)
    )


@pytest.mark.parametrize(
    ("route", "old"),
    [(route, old) for route in sorted(REST) for old in RENAMED_REQUEST_PARAMETERS if old not in REST[route][1]],
)
def test_rest_says_renamed_exactly_where_the_route_had_the_name(route: str, old: str) -> None:
    """Over REST, an old name is told as renamed on a route that had it, and is an unknown parameter on any other."""
    expected = _renamed_expected(set(BASELINE["rest"].get(route, ())), REST[route][1], old)

    response = TestClient(restapi.app, raise_server_exceptions=False).get(REST[route][0], params={old: "x"})

    assert response.status_code == 422, response.text
    errors = {error["type"] for error in response.json()["errors"] if error["loc"] == ["query", old]}
    assert errors == ({"renamed"} if expected else {"extra_forbidden"})
    assert (f"{old} was renamed to {RENAMED_REQUEST_PARAMETERS[old]}" in response.text) is expected


@pytest.fixture(scope="module")
def mcp_answers() -> dict[tuple[str, str], str]:
    """Ask every tool for every old name once."""
    pytest.importorskip("fastmcp")
    return _mcp_answers()


@pytest.mark.parametrize(
    ("route", "old"),
    [(route, old) for route in sorted(REST) for old in RENAMED_REQUEST_PARAMETERS if old not in REST[route][1]],
)
def test_mcp_says_renamed_exactly_where_the_route_had_the_name(
    mcp_answers: dict[tuple[str, str], str], route: str, old: str
) -> None:
    """A tool is told it was given an old name renamed only where the route had it: the same answer as REST."""
    expected = _renamed_expected(set(BASELINE["rest"].get(route, ())), REST[route][1], old)
    answer = mcp_answers[route, old]

    if expected:
        assert answer == f"{old} was renamed to {RENAMED_REQUEST_PARAMETERS[old]}"
    else:
        assert _RENAME_MARKER not in answer
        assert f"{old} is not an argument of {route}" in answer


@pytest.mark.parametrize(
    ("route", "old"),
    [
        (route, old)
        for route in sorted(COMMANDS)
        for old in RENAMED_REQUEST_PARAMETERS
        if old not in _visible(COMMANDS[route][1])
    ],
)
def test_the_command_line_says_renamed_exactly_where_the_command_had_the_option(route: str, old: str) -> None:
    """On the command line, an old option is a rename on a command that had it, and click's refusal otherwise."""
    path, command = COMMANDS[route]
    new = RENAMED_REQUEST_PARAMETERS[old]
    had = {name.replace("-", "_") for name in BASELINE["cli"].get(route, ())}
    expected = _renamed_expected(had, {name.replace("-", "_") for name in _visible(command)}, old)

    result = CliRunner().invoke(cli, [*path, f"--{old}=x"])

    assert result.exit_code == 2, result.output
    if expected:
        assert f"Error: --{old} was renamed to --{new}." in result.output
    else:
        assert "was renamed" not in result.output
        assert f"No such option: --{old}" in result.output or f"No such option '--{old}'" in result.output


def test_the_three_surfaces_agree_where_they_share_a_route(mcp_answers: dict[tuple[str, str], str]) -> None:
    """REST, MCP and the command line are told the same of the same route: a rename is a rename on every surface."""
    disagreements = []
    for route in sorted(set(REST) & set(COMMANDS)):
        path, command = COMMANDS[route]
        for old in RENAMED_REQUEST_PARAMETERS:
            if old in REST[route][1] or old in _visible(command):
                continue
            rest = _renamed_expected(set(BASELINE["rest"].get(route, ())), REST[route][1], old)
            mcp = f"{old} was renamed" in mcp_answers[route, old]
            result = CliRunner().invoke(cli, [*path, f"--{old}=x"])
            on_cli = f"--{old} was renamed" in result.output
            new_on_cli = RENAMED_REQUEST_PARAMETERS[old].replace("_", "-") in _visible(command)
            if not (rest == mcp and (on_cli == rest or not new_on_cli)):
                disagreements.append((route, old, rest, mcp, on_cli))

    assert disagreements == []


#: the command `stripes values` of 0.139.0 is `stripes image` now (0.173.0), so its options are the latter's
_COMMAND_NOW = {"stripes_values": "stripes_image"}


def test_the_table_of_underscored_options_is_what_the_release_took() -> None:
    """`OLD_UNDERSCORE_OPTIONS_OF_ROUTE` is each command's options spelled with an underscore in 0.139.0."""
    derived = {
        _COMMAND_NOW.get(route, route): frozenset(name for name in names if "_" in name)
        for route, names in BASELINE["cli"].items()
        if any("_" in name for name in names)
    }

    assert derived == OLD_UNDERSCORE_OPTIONS_OF_ROUTE


def _underscored(command: click.Command) -> list[str]:
    """Give the current options of a command, as the underscored spelling a caller may have had."""
    return sorted({name.replace("-", "_") for name in _visible(command) if "-" in name})


@pytest.mark.parametrize(
    ("route", "name"),
    [(route, name) for route in sorted(COMMANDS) for name in _underscored(COMMANDS[route][1])],
)
def test_the_command_line_says_renamed_for_an_underscore_only_where_the_command_had_it(route: str, name: str) -> None:
    """`stations --name_threshold` is click's refusal (0.139.0 had `--name-threshold`)."""
    path, _ = COMMANDS[route]
    baseline_route = next((old for old, now in _COMMAND_NOW.items() if now == route), route)
    expected = name in {n for n in BASELINE["cli"].get(baseline_route, ()) if "_" in n}

    result = CliRunner().invoke(cli, [*path, f"--{name}=x"])

    assert result.exit_code == 2, result.output
    if expected:
        assert f"Error: --{name} was renamed to --{name.replace('_', '-')}." in result.output
    else:
        assert _RENAME_MARKER not in result.output
        assert f"No such option '--{name}'" in result.output or f"No such option: --{name}" in result.output
