# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The served OpenAPI document offers all that the last release offered (GH-3131).

See `tests/ui/openapi_baseline.py` for the baseline and the command that refreshes it, and `tests/ui/openapi_diff.py`
for what is compared. The cases below are the differ's own tests: each kind of break is found, and each kind of
addition passes.
"""

from __future__ import annotations

import copy
from typing import Any

import pytest

from tests.ui.openapi_baseline import RELEASE, project_version, read_baseline
from tests.ui.openapi_diff import ACCEPTED_BREAKS, breaking_changes, unaccepted
from tests.ui.openapi_snapshot import build_document, installed_versions, locked_versions

_BREAK = (
    "The served OpenAPI document no longer offers what the last release did (tests/ui/openapi.baseline.json). "
    "A client written against that release breaks on it: restore it, or, for a change that is meant, name it in "
    "ACCEPTED_BREAKS of tests/ui/openapi_diff.py with the reason, add a **Breaking** entry to the changelog, and say "
    "what to do instead. The baseline itself is refreshed only in a release commit (`uv run poe contracts:baseline`)."
)


def test_the_document_offers_all_the_last_release_offered() -> None:
    """A path, parameter, status, member or enum member of the last release is still there, with its type."""
    # the document differs in detail between versions of FastAPI and pydantic, as the snapshot test says
    if installed_versions() != locked_versions():
        pytest.skip(f"the baseline is compared with the versions {locked_versions()}, {installed_versions()} installed")

    found = unaccepted(breaking_changes(read_baseline(), build_document()))

    assert not found, f"{_BREAK}\n" + "\n".join(found[:40])


def test_the_baseline_is_the_document_of_the_release_in_pyproject() -> None:
    """The release commit refreshes the baseline: `x-release` is the version `pyproject.toml` has when it is made."""
    assert read_baseline()[RELEASE] == project_version(), (
        "run `uv run poe contracts:baseline` in the release commit, see .github/RELEASE_STRATEGY.md"
    )


def test_every_approved_break_says_why() -> None:
    """An entry of `ACCEPTED_BREAKS` is a finding as the differ words it, and a reason."""
    for finding, reason in ACCEPTED_BREAKS.items():
        assert finding.split(" ")[0] in {"GET", "PUT", "POST", "DELETE", "PATCH"} or finding.startswith("/"), finding
        assert len(reason) > 20, finding


# --- the differ ----------------------------------------------------------------------------------


def _document() -> dict[str, Any]:
    """Make a small document with a parameter, an enum, a union and an object in a response."""
    return {
        "openapi": "3.1.0",
        "paths": {
            "/api/v1/things": {
                "get": {
                    "operationId": "things_api_things_get",
                    "parameters": [
                        {
                            "name": "kind",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string", "enum": ["a", "b"]},
                        },
                        {
                            "name": "ids",
                            "in": "query",
                            "required": False,
                            "style": "form",
                            "explode": False,
                            "schema": {"type": "array", "items": {"type": "string"}},
                        },
                        {
                            "name": "limit",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "integer", "default": 10, "minimum": 1, "maximum": 100},
                        },
                        {
                            "name": "code",
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string", "pattern": "^[a-z]+$", "maxLength": 8},
                        },
                        {
                            "name": "size",
                            "in": "query",
                            "required": False,
                            "schema": {
                                "anyOf": [{"type": "integer", "exclusiveMinimum": 0}, {"type": "null"}],
                                "default": None,
                            },
                        },
                    ],
                    "requestBody": {
                        "required": False,
                        "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Filter"}}},
                    },
                    "responses": {
                        "200": {
                            "description": "ok",
                            "content": {"application/json": {"schema": {"$ref": "#/components/schemas/Things"}}},
                        },
                        "404": {"description": "none", "headers": {"Retry-After": {"schema": {"type": "integer"}}}},
                    },
                }
            }
        },
        "components": {
            "schemas": {
                "Things": {
                    "type": "object",
                    "required": ["id", "kind"],
                    "properties": {
                        "id": {"type": "string"},
                        "kind": {"type": "string", "enum": ["a", "b"]},
                        "size": {"anyOf": [{"type": "integer"}, {"type": "null"}]},
                        "tags": {"type": "array", "items": {"$ref": "#/components/schemas/Tag"}},
                    },
                },
                "Filter": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {"type": "string", "minLength": 1, "maxLength": 20},
                        "mode": {"type": "string", "enum": ["x", "y"], "default": "x"},
                        "ids": {"type": "array", "items": {"type": "string"}, "maxItems": 50},
                    },
                },
                "Tag": {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}},
            }
        },
    }


def _changed(edit: Any) -> list[str]:  # noqa: ANN401
    """Edit a copy of the document and say what the edit breaks."""
    current = copy.deepcopy(_document())
    edit(current)
    return breaking_changes(_document(), current)


_OP = ("paths", "/api/v1/things", "get")
_FILTER = ("components", "schemas", "Filter")
_THINGS = ("components", "schemas", "Things")


def _at(document: dict[str, Any], *path: str) -> Any:  # noqa: ANN401
    for part in path:
        document = document[part]
    return document


def _parameter(document: dict[str, Any], name: str) -> dict[str, Any]:
    """Give the schema of a parameter of the operation by its name."""
    return next(p for p in _at(document, *_OP)["parameters"] if p["name"] == name)["schema"]


def test_a_document_is_not_a_break_of_itself() -> None:
    """The differ finds nothing where nothing changed."""
    assert breaking_changes(_document(), _document()) == []


@pytest.mark.parametrize(
    ("edit", "expected"),
    [
        pytest.param(lambda d: d["paths"].pop("/api/v1/things"), "/api/v1/things was removed", id="path-removed"),
        pytest.param(
            lambda d: _at(d, "paths", "/api/v1/things").pop("get"), "GET /api/v1/things was removed", id="operation"
        ),
        pytest.param(lambda d: _at(d, *_OP).update(operationId="things_get"), "operationId changed", id="operation-id"),
        pytest.param(
            lambda d: _at(d, *_OP)["parameters"].pop(0), "parameter kind (query) was removed", id="param-removed"
        ),
        pytest.param(
            lambda d: _at(d, *_OP)["parameters"][0].update(name="type"),
            "parameter kind (query) was removed",
            id="param-renamed",
        ),
        pytest.param(
            lambda d: _at(d, *_OP)["parameters"][0].update(required=True),
            "parameter kind (query) became required",
            id="required",
        ),
        pytest.param(
            lambda d: _at(d, *_OP)["parameters"].append({"name": "x", "in": "query", "required": True, "schema": {}}),
            "parameter x (query) was added and is required",
            id="new-required",
        ),
        pytest.param(
            lambda d: _at(d, *_OP)["parameters"][0]["schema"]["enum"].remove("b"),
            'enum members "b" were removed',
            id="param-enum-removed",
        ),
        pytest.param(
            lambda d: _at(d, *_OP)["parameters"][0]["schema"].update(type="integer"),
            "type changed from string to integer",
            id="param-type",
        ),
        pytest.param(
            lambda d: _at(d, *_OP)["parameters"][1].update(explode=True),
            "explode changed from False to True",
            id="explode",
        ),
        pytest.param(lambda d: _at(d, *_OP)["responses"].pop("404"), "response 404 was removed", id="status-removed"),
        pytest.param(
            lambda d: _at(d, *_OP)["responses"]["404"]["headers"].clear(), "header Retry-After was removed", id="header"
        ),
        pytest.param(
            lambda d: _at(d, *_OP)["responses"]["200"].update(content={"text/csv": {}}),
            "media type application/json was removed",
            id="media-type",
        ),
        pytest.param(lambda d: _at(d, *_THINGS)["properties"].pop("id"), "member id was removed", id="member-removed"),
        pytest.param(
            lambda d: _at(d, *_THINGS)["properties"].update(identifier=_at(d, *_THINGS)["properties"].pop("id")),
            "member id was removed",
            id="member-renamed",
        ),
        pytest.param(
            lambda d: _at(d, *_THINGS)["properties"]["id"].update(type="integer"),
            "type changed from string to integer",
            id="member-type",
        ),
        pytest.param(
            lambda d: _at(d, *_THINGS)["required"].remove("id"),
            "member id is no longer always there",
            id="required-gone",
        ),
        pytest.param(
            lambda d: _at(d, *_THINGS)["properties"]["kind"]["enum"].remove("a"),
            'enum members "a" were removed',
            id="response-enum-removed",
        ),
        pytest.param(
            lambda d: _at(d, *_THINGS)["properties"]["size"]["anyOf"].pop(0),
            "integer is no longer one of the alternatives",
            id="union-alternative",
        ),
        pytest.param(
            lambda d: _at(d, "components", "schemas", "Tag")["properties"].pop("name"),
            "member name was removed",
            id="through-a-reference",
        ),
        pytest.param(
            lambda d: _at(d, *_THINGS)["properties"]["tags"].update(items={"type": "string"}),
            "type changed from object to string",
            id="items",
        ),
        pytest.param(
            lambda d: _parameter(d, "limit").update(default=20), "default changed from 10 to 20", id="default-changed"
        ),
        pytest.param(
            lambda d: _parameter(d, "limit").pop("default"), "default changed from 10 to null", id="default-removed"
        ),
        pytest.param(
            lambda d: _parameter(d, "kind").update(default="a"), 'default changed from null to "a"', id="default-added"
        ),
        pytest.param(
            lambda d: _parameter(d, "size").update(default=5), "default changed from null to 5", id="union-default"
        ),
        pytest.param(lambda d: _parameter(d, "limit").update(minimum=2), "minimum became >= 2 (was >= 1)", id="min"),
        pytest.param(
            lambda d: _parameter(d, "limit").update(maximum=50), "maximum became <= 50 (was <= 100)", id="max"
        ),
        pytest.param(
            lambda d: _parameter(d, "limit").update(exclusiveMinimum=1), "minimum became > 1 (was >= 1)", id="min-open"
        ),
        pytest.param(
            lambda d: _parameter(d, "kind").update(maximum=9, type="string"), "maximum became <= 9", id="bound-added"
        ),
        pytest.param(
            lambda d: _parameter(d, "code").update(maxLength=4), "maxLength became 4 (was 8)", id="max-length"
        ),
        pytest.param(lambda d: _parameter(d, "code").update(minLength=3), "minLength became 3", id="min-length-added"),
        pytest.param(
            lambda d: _parameter(d, "size")["anyOf"][0].update(exclusiveMinimum=5),
            "minimum became > 5 (was > 0)",
            id="bound-of-an-alternative",
        ),
        pytest.param(
            lambda d: _parameter(d, "code").update(pattern="^[a-c]+$"),
            "pattern changed from ^[a-z]+$ to ^[a-c]+$",
            id="pattern-changed",
        ),
        pytest.param(
            lambda d: _parameter(d, "kind").update(pattern="^a"), "now has the pattern ^a", id="pattern-added"
        ),
        pytest.param(
            lambda d: _at(d, *_FILTER)["properties"]["name"].update(maxLength=10),
            "request body application/json.name: maxLength became 10 (was 20)",
            id="body-max-length",
        ),
        pytest.param(
            lambda d: _at(d, *_FILTER)["properties"]["name"].update(minLength=2),
            "request body application/json.name: minLength became 2 (was 1)",
            id="body-min-length",
        ),
        pytest.param(
            lambda d: _at(d, *_FILTER)["properties"]["mode"].update(default="y"),
            "request body application/json.mode: default changed",
            id="body-default",
        ),
        pytest.param(
            lambda d: _at(d, *_FILTER)["properties"]["mode"]["enum"].remove("y"),
            'request body application/json.mode: enum members "y" were removed',
            id="body-enum",
        ),
        pytest.param(
            lambda d: _at(d, *_FILTER)["properties"]["ids"].update(maxItems=5),
            "ids: maxItems became 5 (was 50)",
            id="body-max-items",
        ),
        pytest.param(
            lambda d: _at(d, *_FILTER)["properties"]["ids"].update(minItems=1),
            "ids: minItems became 1",
            id="body-min-items",
        ),
        pytest.param(
            lambda d: _at(d, *_FILTER)["properties"]["ids"]["items"].update(pattern="^[0-9]+$"),
            "ids[]: now has the pattern ^[0-9]+$",
            id="body-pattern-of-the-items",
        ),
    ],
)
def test_a_break_is_found(edit: Any, expected: str) -> None:  # noqa: ANN401
    """Each thing the last release offered is found missing or different, down to the member of a member."""
    found = _changed(edit)

    assert any(expected in finding for finding in found), found


@pytest.mark.parametrize(
    "edit",
    [
        pytest.param(lambda d: d["paths"].update({"/api/v1/new": {"get": {"responses": {}}}}), id="path"),
        pytest.param(lambda d: _at(d, "paths", "/api/v1/things").update(post={"responses": {}}), id="operation"),
        pytest.param(
            lambda d: _at(d, *_OP)["parameters"].append({"name": "x", "in": "query", "schema": {"type": "string"}}),
            id="optional-parameter",
        ),
        pytest.param(lambda d: _at(d, *_OP)["parameters"][0]["schema"]["enum"].append("c"), id="parameter-enum-member"),
        pytest.param(lambda d: _at(d, *_OP)["responses"].update({"500": {"description": "bug"}}), id="status"),
        pytest.param(lambda d: _at(d, *_OP)["responses"]["200"]["content"].update({"text/csv": {}}), id="media-type"),
        pytest.param(lambda d: _at(d, *_THINGS)["properties"].update(extra={"type": "string"}), id="member"),
        pytest.param(lambda d: _at(d, *_THINGS)["required"].append("size"), id="member-now-required-in-a-response"),
        pytest.param(lambda d: _at(d, *_THINGS)["properties"]["kind"]["enum"].append("c"), id="response-enum-member"),
        pytest.param(lambda d: _at(d, *_THINGS)["properties"]["size"]["anyOf"].append({"type": "string"}), id="union"),
        pytest.param(
            lambda d: _at(d, *_THINGS)["properties"]["id"].update(
                description="the id", title="Id", default="x", minLength=3, pattern="^a", examples=["abc"]
            ),
            id="description-title-and-constraints-of-an-answer",
        ),
        pytest.param(lambda d: _parameter(d, "limit").update(minimum=0), id="looser-minimum"),
        pytest.param(lambda d: _parameter(d, "limit").update(maximum=500), id="looser-maximum"),
        pytest.param(lambda d: _parameter(d, "limit").pop("minimum"), id="minimum-dropped"),
        pytest.param(
            lambda d: _parameter(d, "limit").update(exclusiveMaximum=500), id="an-exclusive-bound-beyond-the-maximum"
        ),
        pytest.param(lambda d: _parameter(d, "code").update(maxLength=64, minLength=0), id="looser-length"),
        pytest.param(lambda d: _parameter(d, "code").pop("pattern"), id="pattern-dropped"),
        pytest.param(lambda d: _parameter(d, "size")["anyOf"][0].pop("exclusiveMinimum"), id="bound-of-an-alternative"),
        pytest.param(lambda d: _parameter(d, "limit").update(description="how many", title="Limit"), id="describing"),
        pytest.param(lambda d: _at(d, *_FILTER)["properties"]["name"].update(maxLength=40), id="body-looser-length"),
        pytest.param(lambda d: _at(d, *_FILTER)["properties"]["mode"]["enum"].append("z"), id="body-enum-member"),
        pytest.param(lambda d: _at(d, *_FILTER)["properties"]["ids"].update(maxItems=500, minItems=0), id="body-items"),
        pytest.param(
            lambda d: _at(d, *_FILTER)["properties"].update(extra={"type": "string", "minLength": 4, "default": "q"}),
            id="body-new-member-with-constraints",
        ),
        pytest.param(lambda d: d.update(info={"title": "Wetterdienst"}, servers=[], tags=[]), id="info"),
        pytest.param(lambda d: _at(d, *_OP).update(deprecated=True), id="deprecated"),
    ],
)
def test_an_addition_is_not_a_break(edit: Any) -> None:  # noqa: ANN401
    """New paths, operations, optional parameters, statuses, media types, members and enum members pass."""
    assert _changed(edit) == []


def test_a_reference_that_moved_is_not_a_break() -> None:
    """The same response written inline or as a reference to a component compares alike."""
    inline = _document()["paths"]["/api/v1/things"]["get"]["responses"]["404"]

    def move(document: dict[str, Any]) -> None:
        document["components"]["responses"] = {"NotFound": inline}
        _at(document, *_OP)["responses"]["404"] = {"$ref": "#/components/responses/NotFound"}

    assert _changed(move) == []


def test_a_recursive_schema_ends() -> None:
    """A schema that holds itself is compared once."""
    baseline = _document()
    baseline["components"]["schemas"]["Tag"]["properties"]["children"] = {
        "type": "array",
        "items": {"$ref": "#/components/schemas/Tag"},
    }

    assert breaking_changes(baseline, copy.deepcopy(baseline)) == []


def test_an_approved_break_is_left_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """A finding named in `ACCEPTED_BREAKS` does not fail the check, and any other still does."""
    finding = "GET /y 200: media type application/json was removed"
    monkeypatch.setitem(ACCEPTED_BREAKS, finding, "a reason")

    assert unaccepted([finding, "GET /x was removed"]) == ["GET /x was removed"]
