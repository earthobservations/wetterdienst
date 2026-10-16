# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The OpenAPI document of the REST API as committed, and the one command that regenerates it (GH-2561).

The document is the contract of the API: what a client generated from it and an MCP tool built from it
rely on. `tests/ui/openapi.snapshot.json` is that document as last reviewed, and
`tests/ui/test_openapi_snapshot.py` fails when the served document is not it, so a change to the contract
is a change to this file in the same pull request, where a reviewer sees it as a diff. Regenerate with

    uv run poe openapi:snapshot

and read the diff: a removed or renamed path, parameter or member, a changed type, or a status that is
gone is a break of the version the API is served under; an added optional parameter, member or path is not.
"""

from __future__ import annotations

import contextlib
import importlib.metadata
import json
import os
import tempfile
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Iterator

SNAPSHOT = Path(__file__).parent / "openapi.snapshot.json"
#: the packages whose version shapes the document: FastAPI writes it, pydantic writes the schemas in it
_SHAPED_BY = ("fastapi", "pydantic")
#: where the snapshot says which versions wrote it. Information only, and not part of the served document
GENERATED_WITH = "x-generated-with"
LOCK = Path(__file__).parents[2] / "uv.lock"


def installed_versions() -> dict[str, str]:
    """Give the versions of the packages that shape the document, as installed."""
    return {name: importlib.metadata.version(name) for name in _SHAPED_BY}


def locked_versions() -> dict[str, str]:
    """Give the versions of those packages that `uv.lock` pins, which the snapshot is written with."""
    packages = tomllib.loads(LOCK.read_text(encoding="utf-8"))["package"]
    return {package["name"]: package["version"] for package in packages if package["name"] in _SHAPED_BY}


@contextlib.contextmanager
def _clean_environment() -> Iterator[None]:
    """Keep the `WD_*` variables and the `.env` of whoever runs this out of the document.

    The defaults of the settings parameters are the server's (GH-2393), so the document depends on the
    environment it is built in; the snapshot is the one of a server that sets nothing.
    """
    kept = {
        name: value
        for name, value in os.environ.items()
        if name.upper().startswith("WD_") and name.upper() != "WD_CACHE_DIR"
    }
    cwd = Path.cwd()
    with tempfile.TemporaryDirectory() as empty:
        for name in kept:
            del os.environ[name]
        os.chdir(empty)
        try:
            yield
        finally:
            os.chdir(cwd)
            os.environ.update(kept)


def build_document() -> dict[str, Any]:
    """Build the OpenAPI document of the app anew, as a server that sets no `WD_*` variable serves it."""
    from wetterdienst.ui import restapi  # noqa: PLC0415

    with _clean_environment():
        kept = restapi.app.openapi_schema
        restapi.app.openapi_schema = None
        try:
            # through JSON, as it is served: tuples and enums are what a client reads
            return json.loads(json.dumps(restapi.app.openapi()))
        finally:
            restapi.app.openapi_schema = kept


def write_snapshot() -> None:
    """Write the document as the snapshot, with the versions that wrote it."""
    document = {**build_document(), GENERATED_WITH: installed_versions()}
    SNAPSHOT.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write_snapshot()
    print(f"wrote {SNAPSHOT}")  # noqa: T201
