# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The OpenAPI document of the REST API is the committed snapshot, so the contract cannot drift unreviewed (GH-2561).

See `tests/ui/openapi_snapshot.py` for what the snapshot is and the command that regenerates it.
"""

from __future__ import annotations

import json
import tomllib
from pathlib import Path
from typing import Any

import pytest

from tests.ui.openapi_snapshot import (
    GENERATED_WITH,
    SNAPSHOT,
    build_document,
    installed_versions,
    locked_versions,
    without_version,
)
from wetterdienst import __version__
from wetterdienst.ui.response_metadata import API_VERSION
from wetterdienst.ui.restapi import API_PREFIX

_REGENERATE = (
    "The OpenAPI document served by the REST API is not tests/ui/openapi.snapshot.json. If the change is "
    "intended, regenerate the snapshot with `uv run poe openapi:snapshot` and review the diff: a removed or "
    "renamed path, parameter or member, a changed type or a status that is gone breaks the API version it is "
    "served under; an added optional parameter, member or path does not."
)


def _snapshot() -> dict[str, Any]:
    return json.loads(SNAPSHOT.read_text(encoding="utf-8"))


def _changes(served: object, committed: object, where: str = "#") -> list[str]:
    """Name where two documents differ, down to the member, so that a failure says what changed."""
    if isinstance(served, dict) and isinstance(committed, dict):
        found = [f"{where}/{key} was removed" for key in committed.keys() - served.keys()]
        found += [f"{where}/{key} was added" for key in served.keys() - committed.keys()]
        for key in served.keys() & committed.keys():
            found += _changes(served[key], committed[key], f"{where}/{key}")
        return sorted(found)
    if isinstance(served, list) and isinstance(committed, list):
        if len(served) != len(committed):
            return [f"{where} has {len(served)} items, not {len(committed)}"]
        return [
            change
            for i, (a, b) in enumerate(zip(served, committed, strict=True))
            for change in _changes(a, b, f"{where}[{i}]")
        ]
    return [] if served == committed else [f"{where} changed"]


def test_the_served_openapi_document_is_the_committed_snapshot() -> None:
    """A change to the contract is a change to the snapshot in the same pull request."""
    committed = _snapshot()
    committed.pop(GENERATED_WITH)
    # the document differs in detail between versions of FastAPI and pydantic, so it is held to the snapshot where
    # they are the locked ones: after an update of the lock, the failure says to regenerate
    if installed_versions() != locked_versions():
        pytest.skip(f"the snapshot is written with {locked_versions()}, and {installed_versions()} is installed")

    changes = _changes(without_version(build_document()), committed)

    assert not changes, f"{_REGENERATE}\n" + "\n".join(changes[:40])


def test_the_snapshot_holds_the_metadata_block_in_every_data_answer() -> None:
    """The `metadata` block is required in the answers of the data routes, whatever the versions installed."""
    schemas = _snapshot()["components"]["schemas"]

    for name in (
        "_StationsWithMetadataDict",
        "_StationsWithMetadataOgcFeatureCollection",
        "_ValuesWithSettingsDict",
        "_ValuesWithSettingsOgcFeatureCollection",
        "_InterpolatedValuesWithSettingsDict",
        "_InterpolatedValuesWithSettingsOgcFeatureCollection",
        "_SummarizedValuesWithSettingsDict",
        "_SummarizedValuesWithSettingsOgcFeatureCollection",
    ):
        assert "metadata" in schemas[name]["required"], name
    block = schemas["ResponseMetadata"]
    assert {"api_version", "schema_version", "retrieved_at", "provider", "request", "counts", "crs", "warnings"} <= set(
        block["required"]
    )
    assert "parameters" not in block["required"]
    assert "quality" not in block["required"]


def test_the_two_prefixes_are_one_contract() -> None:
    """Only the versioned paths are in the document: the alias is served, and not documented."""
    paths = _snapshot()["paths"]

    assert paths
    assert {path for path in paths if path.startswith("/api")} == {
        path for path in paths if path.startswith("/api/v1/")
    }


# --- the document is complete (GH-3129) --------------------------------------------------------

_PYPROJECT = tomllib.loads((Path(__file__).parents[2] / "pyproject.toml").read_text(encoding="utf-8"))


def test_the_document_is_of_the_version_that_serves_it() -> None:
    """`info.version` is the version of wetterdienst that serves the document; the snapshot leaves it out."""
    assert build_document()["info"]["version"] == __version__


def test_the_snapshot_has_no_version() -> None:
    """The version is the package's and changes at each release, so the file does not hold it (GH-3720)."""
    assert "version" not in _snapshot()["info"]


def test_the_info_is_the_projects_own() -> None:
    """The title, licence, contact and servers are what `pyproject.toml` says, not FastAPI's default."""
    document = build_document()
    info, urls = document["info"], _PYPROJECT["project"]["urls"]

    assert info["title"] == "Wetterdienst"
    assert info["summary"] == _PYPROJECT["project"]["description"]
    assert info["description"].strip()
    assert info["license"]["identifier"] == _PYPROJECT["project"]["license-expression"] == "MIT"
    assert info["license"]["url"].startswith(urls["Repository"])
    assert info["contact"]["url"] == urls["Issues"]
    assert urls["Restapi"].rstrip("/") in [server["url"] for server in document["servers"]]
    assert all(server["description"] for server in document["servers"])


def test_every_operation_is_in_a_tag_that_is_described() -> None:
    """A group of the document says what it is for, and every operation is in one."""
    document = build_document()
    tags = {tag["name"]: tag["description"] for tag in document["tags"]}

    assert tags
    assert all(tags.values())
    operations = [operation for item in document["paths"].values() for operation in item.values()]
    assert operations
    assert all(operation["tags"] and set(operation["tags"]) <= set(tags) for operation in operations)
    assert {name for operation in operations for name in operation["tags"]} == set(tags), "a tag nothing is in"


def test_every_operation_is_described_and_has_an_id_of_its_own() -> None:
    """Each has a description, a unique `operationId`, and a description for each query parameter."""
    document = build_document()
    operations = [(path, operation) for path, item in document["paths"].items() for operation in item.values()]

    ids = [operation["operationId"] for _, operation in operations]
    assert len(ids) == len(set(ids))
    for path, operation in operations:
        assert operation["description"].strip(), path
        missing = [
            parameter["name"] for parameter in operation.get("parameters", []) if not parameter.get("description")
        ]
        assert not missing, f"{path}: {missing} have no description"


def test_every_json_answer_has_a_schema() -> None:
    """No route documents its JSON as `{}`: the health check and the version have a model, as the others have."""
    document = build_document()

    bare = [
        path
        for path, item in document["paths"].items()
        for operation in item.values()
        for media, content in operation["responses"]["200"].get("content", {}).items()
        if media == "application/json" and not content.get("schema")
    ]
    assert not bare, bare
    health = document["paths"]["/health"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert health == {"$ref": "#/components/schemas/Health"}
    version = document["paths"]["/api/v1/version"]["get"]["responses"]["200"]["content"]["application/json"]["schema"]
    assert version == {"$ref": "#/components/schemas/VersionAnswer"}


def test_the_pages_and_the_image_say_their_media_type() -> None:
    """The index is HTML, `robots.txt` text, and the stripes image an image of each format it renders."""
    paths = build_document()["paths"]

    assert set(paths["/"]["get"]["responses"]["200"]["content"]) == {"text/html"}
    assert set(paths["/robots.txt"]["get"]["responses"]["200"]["content"]) == {"text/plain"}
    assert set(paths["/api/v1/stripes/image"]["get"]["responses"]["200"]["content"]) == {
        "image/png",
        "image/jpeg",
        "image/svg+xml",
        "application/pdf",
    }


def test_the_api_version_is_in_the_info_and_in_the_paths() -> None:
    """`info.x-api-version` is the version of the contract, the one of `/api/v<version>` and of the metadata block."""
    document = build_document()

    assert document["info"]["x-api-version"] == API_VERSION == "1"
    assert f"/api/v{document['info']['x-api-version']}" == API_PREFIX
    assert all(path.startswith(f"{API_PREFIX}/") for path in document["paths"] if path.startswith("/api"))
