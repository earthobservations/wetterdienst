# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The OpenAPI document of the REST API is the committed snapshot, so the contract cannot drift unreviewed (GH-2561).

See `tests/ui/openapi_snapshot.py` for what the snapshot is and the command that regenerates it.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from tests.ui.openapi_snapshot import GENERATED_WITH, SNAPSHOT, build_document, installed_versions, locked_versions

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

    changes = _changes(build_document(), committed)

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
