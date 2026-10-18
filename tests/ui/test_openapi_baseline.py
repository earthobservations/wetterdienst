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
    "what to do instead. The baseline itself is refreshed only in a release commit (`uv run poe openapi:baseline`)."
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
        "run `uv run poe openapi:baseline` in the release commit, see .github/RELEASE_STRATEGY.md"
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
                    ],
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
_THINGS = ("components", "schemas", "Things")


def _at(document: dict[str, Any], *path: str) -> Any:  # noqa: ANN401
    for part in path:
        document = document[part]
    return document


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
            lambda d: _at(d, *_THINGS)["properties"]["id"].update(description="the id", title="Id", default="x"),
            id="description-title-default",
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


def test_an_approved_break_is_left_out() -> None:
    """A finding named in `ACCEPTED_BREAKS` does not fail the check, and any other still does."""
    finding = next(iter(ACCEPTED_BREAKS))

    assert unaccepted([finding, "GET /x was removed"]) == ["GET /x was removed"]
