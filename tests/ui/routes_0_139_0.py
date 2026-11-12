# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What each route of release 0.139.0 took as its parameters, and so which old names a route really had (GH-3869).

`RENAMED_REQUEST_PARAMETERS` says `date` became `timestamp`, `station` became `stations`: a rename of the parameters a
route had. A route that never took `date` (`stations` takes a `timestamp` only) was never renamed, and telling its
caller that `date` was is a claim about the past that is false. Which route had which old name is read from the release
the renames are counted from, `v0.139.0`, which is the last one before them (`gone_since_0_139_0.json` is the same for
the parameters of the datasets):

- over REST, the query parameters of each path (and the MCP tools take those, by the same name, as their arguments);
- on the command line, the options of each command.

A route is named as its MCP tool is: `stations`, `stripes_values`; the command `coverage` is `coverage`.

The file is generated, not written. It reads the code of the tag out of git (`git archive`, into a temporary directory,
imported in a subprocess so that it cannot mix with the checkout's own modules). Regenerate it, and read the diff, with

    uv run poe routes:baseline

It needs the tag (`git fetch --tags`); the command line of that release imports `cloup`, which the checkout no longer
depends on, so the task asks `uv` for it for the run. The tests read the JSON only and work offline. What the code
declares is `OLD_NAMES_OF_ROUTE` in `wetterdienst/ui/core.py`, and `tests/ui/test_renamed_routes.py` holds it to this
file, so that a route is never named a rename it did not have by a table written from memory.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tarfile
import tempfile
from io import BytesIO
from pathlib import Path

RELEASE = "0.139.0"
TAG = f"v{RELEASE}"
ROUTES = Path(__file__).parent / "routes_0_139_0.json"

# run by the interpreter of the checkout with only the archived `src` on its path. `tzfpy`, which that release imported
# at module level and the checkout no longer depends on, is stubbed: nothing here looks up a time zone
_DUMP = """
import json, sys, types

sys.path.insert(0, sys.argv[1])
sys.modules.setdefault("tzfpy", types.SimpleNamespace(get_tz=lambda *args: None))
import click
from wetterdienst.ui.cli import cli
from wetterdienst.ui.restapi import app

rest = {}
for path, item in app.openapi()["paths"].items():
    if path.startswith("/api/"):
        rest[path.removeprefix("/api/").replace("/", "_")] = sorted(
            parameter["name"] for parameter in item["get"].get("parameters", [])
        )

commands = {}


def walk(command, names):
    if isinstance(command, click.Group):
        for name, sub in command.commands.items():
            walk(sub, [*names, name])
    else:
        commands["_".join(name for name in names if name != "about")] = sorted(
            opt.removeprefix("--")
            for param in command.params
            for opt in (*param.opts, *param.secondary_opts)
            if opt.startswith("--") and not getattr(param, "hidden", False)
        )


walk(cli, [])
json.dump({"rest": rest, "cli": commands}, sys.stdout)
"""


def release_routes() -> dict[str, dict[str, list[str]]]:
    """Read the parameters of every route of the release, over REST and on the command line, by route."""
    archive = subprocess.run(  # noqa: S603
        ["git", "archive", TAG, "src"],  # noqa: S607
        check=True,
        capture_output=True,
        cwd=Path(__file__).parents[2],
    ).stdout
    with tempfile.TemporaryDirectory() as directory, tarfile.open(fileobj=BytesIO(archive)) as tar:
        tar.extractall(directory, filter="data")
        # `-I`: nothing of the checkout's own path or environment variables leaks into the old modules
        out = subprocess.run(  # noqa: S603
            [sys.executable, "-I", "-c", _DUMP, str(Path(directory) / "src")],
            check=True,
            capture_output=True,
            text=True,
        ).stdout
    return json.loads(out)


def read_routes() -> dict[str, dict[str, list[str]]]:
    """Read the committed file."""
    return json.loads(ROUTES.read_text(encoding="utf-8"))["routes"]


def write_routes() -> None:
    """Write the file for the tag."""
    document = {"release": RELEASE, "routes": release_routes()}
    ROUTES.write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write_routes()
    print(f"wrote {ROUTES}: {sum(len(routes) for routes in read_routes().values())} routes of {TAG}")  # noqa: T201
