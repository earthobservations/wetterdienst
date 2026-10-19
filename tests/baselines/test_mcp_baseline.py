# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The comparison of the MCP tools with the last release, tested with tools made here (GH-3131).

`tests/baselines/test_baselines.py` holds the real tools to their baseline; these are the differ's own tests: each
kind of break is found, and each kind of addition passes.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from tests.baselines.common import unaccepted
from tests.baselines.mcp import ACCEPTED_BREAKS, _prune, breaking_changes


def _surface() -> dict[str, Any]:
    return {
        "tools": {
            "values": {
                "type": "object",
                "required": ["provider"],
                "properties": {
                    "provider": {"type": "string"},
                    "mode": {"$ref": "#/$defs/Mode", "default": "a"},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 100, "default": 10},
                    "stations": {"anyOf": [{"type": "array", "items": {"type": "string"}}, {"type": "null"}]},
                },
                "$defs": {"Mode": {"type": "string", "enum": ["a", "b"]}},
            },
            "coverage": {"type": "object", "properties": {}},
        }
    }


def _changed(edit: Any) -> list[str]:  # noqa: ANN401
    """Edit a copy of the tools and say what the edit breaks."""
    current = copy.deepcopy(_surface())
    edit(current)
    return breaking_changes(_surface(), current)


def _values(surface: dict[str, Any]) -> dict[str, Any]:
    return surface["tools"]["values"]


def test_tools_are_not_a_break_of_themselves() -> None:
    """The differ finds nothing where nothing changed."""
    assert breaking_changes(_surface(), _surface()) == []


@pytest.mark.parametrize(
    ("edit", "expected"),
    [
        pytest.param(lambda s: s["tools"].pop("coverage"), "tool coverage was removed", id="tool"),
        pytest.param(
            lambda s: s["tools"].update(cover=s["tools"].pop("coverage")), "tool coverage was removed", id="renamed"
        ),
        pytest.param(
            lambda s: _values(s)["properties"].pop("limit"), "tool values: argument limit was removed", id="argument"
        ),
        pytest.param(
            lambda s: _values(s)["properties"].update(station=_values(s)["properties"].pop("stations")),
            "argument stations was removed",
            id="argument-renamed",
        ),
        pytest.param(
            lambda s: _values(s).update(required=["provider", "limit"]),
            "argument limit became required",
            id="became-required",
        ),
        pytest.param(
            lambda s: (
                _values(s)["properties"].update(extra={"type": "string"}),
                _values(s).update(required=["provider", "extra"]),
            ),
            "argument extra was added and is required",
            id="new-required",
        ),
        pytest.param(
            lambda s: _values(s)["properties"]["provider"].update(type="integer"),
            "argument provider: type changed from string to integer",
            id="type",
        ),
        pytest.param(
            lambda s: _values(s)["$defs"]["Mode"]["enum"].remove("b"),
            'argument mode: enum members "b" were removed',
            id="enum-member-through-a-reference",
        ),
        pytest.param(
            lambda s: _values(s)["properties"]["mode"].update(default="b"),
            'argument mode: default changed from "a" to "b"',
            id="default",
        ),
        pytest.param(
            lambda s: _values(s)["properties"]["limit"].update(maximum=50),
            "argument limit: maximum became <= 50 (was <= 100)",
            id="bound",
        ),
        pytest.param(
            lambda s: _values(s)["properties"]["limit"].update(minimum=5),
            "argument limit: minimum became >= 5",
            id="lower-bound",
        ),
        pytest.param(
            lambda s: _values(s)["properties"]["provider"].update(pattern="^[a-z]+$"),
            "argument provider: now has the pattern",
            id="pattern",
        ),
        pytest.param(
            lambda s: _values(s)["properties"]["stations"]["anyOf"][0].update(items={"type": "integer"}),
            "argument stations[]: type changed from string to integer",
            id="items-of-an-alternative",
        ),
        pytest.param(
            lambda s: _values(s)["properties"]["stations"]["anyOf"].pop(0),
            "argument stations: array is no longer one of the alternatives",
            id="alternative",
        ),
    ],
)
def test_a_break_is_found(edit: Any, expected: str) -> None:  # noqa: ANN401
    """Each tool and argument the last release offered is found missing or different."""
    found = _changed(edit)

    assert any(expected in finding for finding in found), found


@pytest.mark.parametrize(
    "edit",
    [
        pytest.param(lambda s: s["tools"].update(alerts={"type": "object", "properties": {}}), id="tool"),
        pytest.param(lambda s: _values(s)["properties"].update(extra={"type": "string"}), id="optional-argument"),
        pytest.param(lambda s: _values(s)["$defs"]["Mode"]["enum"].append("c"), id="enum-member"),
        pytest.param(lambda s: _values(s)["properties"]["limit"].update(maximum=1000, minimum=0), id="looser-bound"),
        pytest.param(lambda s: _values(s)["properties"]["limit"].pop("maximum"), id="no-bound"),
        pytest.param(lambda s: _values(s).update(required=[]), id="no-longer-required"),
        pytest.param(
            lambda s: _values(s)["properties"]["provider"].update(description="the provider", title="Provider"),
            id="description",
        ),
        pytest.param(
            lambda s: _values(s)["properties"]["stations"]["anyOf"].append({"type": "string"}), id="new-alternative"
        ),
    ],
)
def test_an_addition_is_not_a_break(edit: Any) -> None:  # noqa: ANN401
    """A new tool, an optional argument, an enum member and a looser bound pass."""
    assert _changed(edit) == []


def test_the_prose_of_a_schema_is_left_out_but_not_a_member_called_description() -> None:
    """A title or a description says more than it promises, and an argument named `description` is one."""
    schema = {
        "type": "object",
        "title": "Args",
        "description": "the arguments",
        "properties": {
            "description": {"type": "string", "description": "free text", "title": "Description"},
            "mode": {"$ref": "#/$defs/Mode"},
        },
        "$defs": {"Mode": {"type": "string", "enum": ["a"], "description": "a mode", "examples": ["a"]}},
    }

    assert _prune(schema) == {
        "type": "object",
        "properties": {"description": {"type": "string"}, "mode": {"$ref": "#/$defs/Mode"}},
        "$defs": {"Mode": {"type": "string", "enum": ["a"]}},
    }


def test_an_approved_break_is_left_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """A finding named in `ACCEPTED_BREAKS` does not fail the check, and any other still does."""
    finding = "tool values: argument limit was removed"
    monkeypatch.setitem(ACCEPTED_BREAKS, finding, "a reason that is long enough")

    assert unaccepted([finding, "tool coverage was removed"], ACCEPTED_BREAKS) == ["tool coverage was removed"]
