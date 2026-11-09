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
from tests.ui.openapi_diff import ACCEPTED_BREAKS, CLOSED_RESPONSE_ENUMS, breaking_changes, unaccepted
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
        # what a request takes may not be one thing less (a response may, GH-3889)
        pytest.param(
            lambda d: _parameter(d, "size")["anyOf"].pop(0),
            "integer is no longer one of the alternatives",
            id="request-union-alternative-removed",
        ),
        pytest.param(
            lambda d: _parameter(d, "size").update(anyOf=[{"type": "integer", "exclusiveMinimum": 0}]),
            "null is no longer one of the alternatives",
            id="request-became-not-nullable",
        ),
        # an enum of a response that is a free string now is a type change for a typed client (GH-3889)
        pytest.param(
            lambda d: _at(d, *_THINGS)["properties"].update(kind={"type": "string"}),
            'the enum members "a", "b" became a free string',
            id="response-enum-became-a-free-string",
        ),
        pytest.param(
            lambda d: _at(d, *_THINGS)["properties"].update(
                kind={"anyOf": [{"type": "string"}, {"type": "null"}]},
            ),
            'the enum members "a", "b" became a free string',
            id="response-enum-became-a-nullable-free-string",
        ),
        pytest.param(
            lambda d: _at(d, *_THINGS)["properties"]["kind"].update(type=["string", "null"]),
            "type changed from string to ['string', 'null']",
            id="response-type-list-widened",
        ),
        # a client typed from the document handles each alternative of a response and no other (GH-3869)
        pytest.param(
            lambda d: _at(d, *_THINGS)["properties"]["size"]["anyOf"].append({"type": "string"}),
            "string was added to the alternatives of the answer",
            id="response-union-alternative-added",
        ),
        pytest.param(
            lambda d: _at(d, *_THINGS)["properties"].update(
                tags={"anyOf": [_at(d, *_THINGS)["properties"]["tags"], {"type": "null"}]}
            ),
            "null was added to the alternatives of the answer",
            id="response-array-became-nullable",
        ),
        pytest.param(
            lambda d: _at(d, *_THINGS)["properties"].update(id={"anyOf": [{"type": "string"}, {"type": "null"}]}),
            "null was added to the alternatives of the answer",
            id="response-member-became-nullable",
        ),
        pytest.param(
            lambda d: _at(d, *_THINGS)["properties"]["tags"].update(
                items={"anyOf": [{"$ref": "#/components/schemas/Tag"}, {"type": "string"}]}
            ),
            "string was added to the alternatives of the answer",
            id="response-items-became-a-union",
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
        # an enum of a response may lose members, as a union an alternative; of a request it may not (GH-3889)
        pytest.param(lambda d: _at(d, *_THINGS)["properties"]["kind"]["enum"].remove("a"), id="response-enum-removed"),
        # an answer may be one thing less (`number | null` that is `number`): the client handles it already (GH-3889)
        pytest.param(
            lambda d: _at(d, *_THINGS)["properties"]["size"]["anyOf"].pop(0), id="response-union-alternative-removed"
        ),
        pytest.param(
            lambda d: _at(d, *_THINGS)["properties"].update(size={"type": "integer"}),
            id="response-union-became-its-alternative",
        ),
        # a new alternative that is only an enum member of an enum string is the enum gaining a member (GH-3889)
        pytest.param(
            lambda d: _at(d, *_THINGS)["properties"].update(
                kind={"anyOf": [_at(d, *_THINGS)["properties"]["kind"], {"const": "c"}]}
            ),
            id="response-enum-member-as-a-const-alternative",
        ),
        pytest.param(
            lambda d: _at(d, *_THINGS)["properties"].update(
                kind={"anyOf": [_at(d, *_THINGS)["properties"]["kind"], {"type": "string", "enum": ["c", "d"]}]}
            ),
            id="response-enum-members-as-an-enum-alternative",
        ),
        # what a request takes may be a free string now: looser, an addition
        pytest.param(
            lambda d: _at(d, *_FILTER)["properties"].update(mode={"type": "string", "default": "x"}),
            id="request-free-string",
        ),
        # what a request takes may be one more thing (the opposite of a response, which must not: GH-3869)
        pytest.param(lambda d: _parameter(d, "size")["anyOf"].append({"type": "string"}), id="request-union"),
        pytest.param(
            lambda d: _at(d, *_FILTER)["properties"].update(
                ids={"anyOf": [_at(d, *_FILTER)["properties"]["ids"], {"type": "null"}]}
            ),
            id="request-body-array-became-nullable",
        ),
        pytest.param(
            lambda d: _at(d, *_THINGS)["properties"]["size"]["anyOf"][0].update(description="how many", minimum=0),
            id="response-alternative-of-the-same-type",
        ),
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


def _shared_document() -> dict[str, Any]:
    """Build a document whose component `Shared` is a member of both the request body and the answer."""
    document = _document()
    document["components"]["schemas"]["Shared"] = {
        "type": "object",
        "properties": {"v": {"type": "integer"}, "w": {"anyOf": [{"type": "string"}, {"type": "null"}]}},
    }
    for name in ("Filter", "Things"):
        _at(document, "components", "schemas", name)["properties"]["shared"] = {"$ref": "#/components/schemas/Shared"}
    return document


def _shared_changed(edit: Any) -> list[str]:  # noqa: ANN401
    current = copy.deepcopy(_shared_document())
    edit(current)
    return breaking_changes(_shared_document(), current)


def test_a_component_in_a_request_and_an_answer_is_judged_by_each_use() -> None:
    """Widening a shared component is one finding, at the answer: a request that takes more is an addition (GH-3869)."""
    nullable = {"anyOf": [{"type": "integer"}, {"type": "null"}]}

    found = _shared_changed(lambda d: _at(d, "components", "schemas", "Shared")["properties"].update(v=nullable))

    assert found == [
        "GET /api/v1/things 200 application/json.shared.v: null was added to the alternatives of the answer"
    ]


def test_a_response_type_list_that_lost_a_type_is_narrowed_and_one_that_gained_is_a_finding() -> None:
    """`["number", "null"]` written as a list of types follows the rule of the union written as `anyOf` (GH-3889)."""
    wide = _document()
    _at(wide, *_THINGS)["properties"]["size"] = {"type": ["integer", "null"]}
    narrow = copy.deepcopy(wide)
    _at(narrow, *_THINGS)["properties"]["size"] = {"type": "integer"}

    assert breaking_changes(wide, narrow) == []
    assert breaking_changes(narrow, wide) == [
        "GET /api/v1/things 200 application/json.size: type changed from integer to ['integer', 'null']"
    ]


def test_a_response_enum_that_is_a_free_string_in_a_union_is_a_finding() -> None:
    """An enum string that is a free string beside `null` now is told as the enum, not as a string that was added."""
    baseline = _document()
    _at(baseline, *_THINGS)["properties"]["kind"] = {
        "anyOf": [{"type": "string", "enum": ["a", "b"]}, {"type": "null"}]
    }
    current = copy.deepcopy(baseline)
    _at(current, *_THINGS)["properties"]["kind"]["anyOf"][0] = {"type": "string"}

    assert breaking_changes(baseline, current) == [
        'GET /api/v1/things 200 application/json.kind: the enum members "a", "b" became a free string'
    ]


def test_a_new_enum_member_beside_a_nullable_enum_is_not_a_break() -> None:
    """The members may grow as an alternative of their own, beside `null`, without a string that was added."""
    baseline = _document()
    _at(baseline, *_THINGS)["properties"]["kind"] = {
        "anyOf": [{"type": "string", "enum": ["a", "b"]}, {"type": "null"}]
    }
    current = copy.deepcopy(baseline)
    _at(current, *_THINGS)["properties"]["kind"]["anyOf"].insert(1, {"type": "string", "const": "c"})

    assert breaking_changes(baseline, current) == []


def test_a_new_alternative_that_is_not_an_enum_member_is_still_a_finding_beside_an_enum() -> None:
    """Only an enum member is let through: a string that is free, or an object, is a new alternative."""
    for alternative in ({"type": "string"}, {"type": "object"}, {"type": "integer", "const": 1}):
        current = copy.deepcopy(_document())
        kind = _at(current, *_THINGS)["properties"]["kind"]
        _at(current, *_THINGS)["properties"]["kind"] = {"anyOf": [kind, alternative]}

        found = breaking_changes(_document(), current)

        assert len(found) == 1
        assert "was added to the alternatives of the answer" in found[0]


def test_dropping_one_of_several_object_alternatives_of_a_response_is_not_a_break() -> None:
    """A removed object among objects is a removed alternative, not a member that was removed of the one left."""
    baseline = _document()
    _at(baseline, *_THINGS)["properties"]["shape"] = {
        "oneOf": [
            {"type": "object", "properties": {"a": {"type": "string"}}},
            {"type": "object", "properties": {"b": {"type": "string"}}},
        ]
    }
    current = copy.deepcopy(baseline)
    _at(current, *_THINGS)["properties"]["shape"]["oneOf"].pop(0)

    assert breaking_changes(baseline, current) == []


def test_an_enum_that_became_a_free_string_in_a_component_of_a_request_and_an_answer_is_one_finding() -> None:
    """A shared component's enum that is free now is a looser request, an addition, and a type change of the answer."""
    baseline = _shared_document()
    _at(baseline, "components", "schemas", "Shared")["properties"]["e"] = {"type": "string", "enum": ["a", "b"]}
    current = copy.deepcopy(baseline)
    _at(current, "components", "schemas", "Shared")["properties"]["e"] = {"type": "string"}

    assert breaking_changes(baseline, current) == [
        'GET /api/v1/things 200 application/json.shared.e: the enum members "a", "b" became a free string'
    ]


def test_a_new_enum_member_of_a_component_of_a_request_and_an_answer_is_not_a_break() -> None:
    """A shared enum may grow, as a member or as an alternative of its own, at both uses."""
    baseline = _shared_document()
    _at(baseline, "components", "schemas", "Shared")["properties"]["e"] = {"type": "string", "enum": ["a", "b"]}
    grown = copy.deepcopy(baseline)
    _at(grown, "components", "schemas", "Shared")["properties"]["e"]["enum"].append("c")
    alternative = copy.deepcopy(baseline)
    _at(alternative, "components", "schemas", "Shared")["properties"]["e"] = {
        "anyOf": [{"type": "string", "enum": ["a", "b"]}, {"const": "c"}]
    }

    assert breaking_changes(baseline, grown) == []
    assert breaking_changes(baseline, alternative) == []


def test_a_union_that_lost_an_alternative_in_a_component_of_a_request_and_an_answer_is_a_finding_at_the_request() -> (
    None
):
    """A shared alternative that goes breaks the caller that sends it, and not the one that reads it (GH-3889)."""
    found = _shared_changed(
        lambda d: _at(d, "components", "schemas", "Shared")["properties"].update(w={"type": "string"})
    )

    assert found == [
        "GET /api/v1/things: request body application/json.shared.w: null is no longer one of the alternatives"
    ]


def test_a_request_type_list_that_lost_a_type_is_a_finding() -> None:
    """What a request takes may not be a type less, written as a list of types either (GH-3889)."""
    baseline = _document()
    _parameter(baseline, "limit")["type"] = ["integer", "null"]
    current = copy.deepcopy(baseline)
    _parameter(current, "limit")["type"] = "integer"

    found = breaking_changes(baseline, current)

    assert found == ["GET /api/v1/things: parameter limit (query): type changed from ['integer', 'null'] to integer"]


@pytest.mark.parametrize(
    "alternative",
    [
        pytest.param({"const": None}, id="const-null"),
        pytest.param({"enum": [None]}, id="enum-null"),
        pytest.param({"const": 1}, id="const-integer"),
        pytest.param({"const": {"k": 1}}, id="const-object"),
        pytest.param({"enum": ["c", None]}, id="enum-with-a-null"),
    ],
)
def test_an_alternative_without_a_type_is_an_enum_member_only_of_the_type_of_the_enum(
    alternative: dict[str, Any],
) -> None:
    """`{"const": null}` beside a string enum makes the answer nullable, the break GH-3869 made of it."""
    current = copy.deepcopy(_document())
    kind = _at(current, *_THINGS)["properties"]["kind"]
    _at(current, *_THINGS)["properties"]["kind"] = {"anyOf": [kind, alternative]}

    found = breaking_changes(_document(), current)

    assert len(found) == 1
    assert "was added to the alternatives of the answer" in found[0]


def test_an_alternative_without_a_type_that_is_an_enum_member_of_a_number_enum_passes() -> None:
    """An integer constant is a member of a number enum."""
    baseline = _document()
    _at(baseline, *_THINGS)["properties"]["kind"] = {"type": "number", "enum": [0.5, 1.5]}
    current = copy.deepcopy(baseline)
    _at(current, *_THINGS)["properties"]["kind"] = {
        "anyOf": [copy.deepcopy(_at(baseline, *_THINGS)["properties"]["kind"]), {"const": 2}]
    }

    assert breaking_changes(baseline, current) == []


def test_a_member_that_changed_in_an_object_alternative_is_found_where_another_was_dropped() -> None:
    """`oneOf[{x: string}, {y: string}]` that is `oneOf[{x: integer, y: string}]` has changed `x`, not dropped it."""
    baseline = _document()
    _at(baseline, *_THINGS)["properties"]["shape"] = {
        "oneOf": [
            {"type": "object", "properties": {"x": {"type": "string"}}},
            {"type": "object", "properties": {"y": {"type": "string"}}},
        ]
    }
    current = copy.deepcopy(baseline)
    _at(current, *_THINGS)["properties"]["shape"] = {
        "oneOf": [{"type": "object", "properties": {"x": {"type": "integer"}, "y": {"type": "string"}}}]
    }

    assert breaking_changes(baseline, current) == [
        "GET /api/v1/things 200 application/json.shape.x: type changed from string to integer"
    ]


def test_a_recursive_schema_whose_union_is_narrowed_ends_and_passes() -> None:
    """`child: Node | null` that is `child: Node` is a narrowed response, and compares in finite time (GH-3889)."""
    baseline = _document()
    node = {
        "type": "object",
        "properties": {"child": {"anyOf": [{"$ref": "#/components/schemas/Node"}, {"type": "null"}]}},
    }
    baseline["components"]["schemas"]["Node"] = node
    _at(baseline, *_THINGS)["properties"]["root"] = {"$ref": "#/components/schemas/Node"}
    current = copy.deepcopy(baseline)
    current["components"]["schemas"]["Node"] = {
        "type": "object",
        "properties": {"child": {"$ref": "#/components/schemas/Node"}},
    }

    assert breaking_changes(baseline, current) == []
    assert breaking_changes(current, baseline) == [
        "GET /api/v1/things 200 application/json.root.child: null was added to the alternatives of the answer"
    ]


def _closed_baseline(member: str) -> dict[str, Any]:
    """Make a document whose answer has a nullable enum `member` and a nullable enum `kind`, both of two members."""
    baseline = _document()
    properties = _at(baseline, *_THINGS)["properties"]
    properties[member] = {"anyOf": [{"type": "string", "enum": ["a", "b"]}, {"type": "null"}]}
    properties["kind"] = {"anyOf": [{"type": "string", "enum": ["a", "b"]}, {"type": "null"}]}
    return baseline


def test_the_closed_response_enums_are_the_two_of_the_answers() -> None:
    """Only a parameter's `aggregation` and `timestamp_position` are closed at 1.0.0 (maintainer, 2026-11-09)."""
    assert {"aggregation", "timestamp_position"} == CLOSED_RESPONSE_ENUMS


@pytest.mark.parametrize("member", ["aggregation", "timestamp_position"])
@pytest.mark.parametrize("as_alternative", [False, True], ids=["in-the-enum", "as-an-alternative"])
def test_a_new_member_of_a_closed_response_enum_is_a_break(*, member: str, as_alternative: bool) -> None:
    """`aggregation` and `timestamp_position` are closed at 1.0.0: a member added to either in an answer is a break."""
    baseline = _closed_baseline(member)
    current = copy.deepcopy(baseline)
    alternatives = _at(current, *_THINGS)["properties"][member]["anyOf"]
    if as_alternative:
        alternatives.insert(1, {"type": "string", "const": "c"})
    else:
        alternatives[0]["enum"].append("c")

    found = breaking_changes(baseline, current)

    assert found, "a new member of a closed enum passed"
    assert all(member in finding for finding in found)


@pytest.mark.parametrize("member", ["aggregation", "timestamp_position"])
@pytest.mark.parametrize("as_alternative", [False, True], ids=["in-the-enum", "as-an-alternative"])
def test_a_new_member_of_another_response_enum_still_passes(*, member: str, as_alternative: bool) -> None:
    """Only the two are closed: `kind`, beside them in the same answer, may gain a member in a minor release."""
    baseline = _closed_baseline(member)
    current = copy.deepcopy(baseline)
    alternatives = _at(current, *_THINGS)["properties"]["kind"]["anyOf"]
    if as_alternative:
        alternatives.insert(1, {"type": "string", "const": "c"})
    else:
        alternatives[0]["enum"].append("c")

    assert breaking_changes(baseline, current) == []


def test_a_closed_response_enum_may_lose_a_member() -> None:
    """The closure is of additions: a response enum that loses a member is none, as for every other."""
    baseline = _closed_baseline("aggregation")
    current = copy.deepcopy(baseline)
    _at(current, *_THINGS)["properties"]["aggregation"]["anyOf"][0]["enum"].remove("b")

    assert breaking_changes(baseline, current) == []


def _grown(baseline: dict[str, Any], *path: str) -> dict[str, Any]:
    """Copy a document and add a member `c` to the enum at `path`."""
    current = copy.deepcopy(baseline)
    _at(current, *path)["enum"].append("c")
    return current


def test_a_new_member_of_a_request_member_called_aggregation_is_an_addition() -> None:
    """The closure is of the answers: a request body member of that name may take more, as every enum of a request."""
    baseline = _document()
    _at(baseline, *_FILTER)["properties"]["aggregation"] = {"type": "string", "enum": ["a", "b"]}

    assert breaking_changes(baseline, _grown(baseline, *_FILTER, "properties", "aggregation")) == []


def test_a_response_aggregation_that_was_a_free_string_and_is_an_enum_now_is_no_break() -> None:
    """A free string that becomes an enum is narrowed, not grown: no member was added to a closed set."""
    baseline = _document()
    _at(baseline, *_THINGS)["properties"]["aggregation"] = {"type": "string"}
    current = copy.deepcopy(baseline)
    _at(current, *_THINGS)["properties"]["aggregation"] = {"type": "string", "enum": ["a", "b"]}

    assert breaking_changes(baseline, current) == []


@pytest.mark.parametrize(
    ("name", "node"),
    [
        pytest.param(
            "aggregation_method", {"type": "string", "enum": ["a", "b"]}, id="a-name-that-only-starts-with-it"
        ),
        pytest.param("unaggregation", {"type": "string", "enum": ["a", "b"]}, id="a-name-that-only-ends-with-it"),
        pytest.param(
            "aggregation",
            {"type": "object", "properties": {"mode": {"type": "string", "enum": ["a", "b"]}}},
            id="an-enum-under-an-object-called-so",
        ),
    ],
)
def test_a_new_member_of_another_enum_that_has_the_name_in_it_passes(name: str, node: dict[str, Any]) -> None:
    """Only the member that is called `aggregation` or `timestamp_position` itself is closed, not one near it."""
    baseline = _document()
    _at(baseline, *_THINGS)["properties"][name] = node
    path = ("properties", name) if "enum" in node else ("properties", name, "properties", "mode")

    assert breaking_changes(baseline, _grown(baseline, *_THINGS, *path)) == []
