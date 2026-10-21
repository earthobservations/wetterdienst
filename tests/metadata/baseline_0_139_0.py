# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The parameters of release 0.139.0 that the current metadata no longer declares (GH-3168).

`tests/metadata/gone_since_0_139_0.json` lists, for every dataset of every provider, the canonical parameter names that
0.139.0 declared and the checkout does not. `tests/metadata/test_gone_since_0_139_0.py` holds each of them to an
answer: a renamed name is refused with the new one, anything else is a removal listed with its reason.

The file is generated, not written. It reads the metadata of the tag `v0.139.0` out of git (`git archive`, into a
temporary directory, imported in a subprocess so that it cannot mix with the checkout's own modules) and keeps what the
checkout lacks. Regenerate it, and read the diff, with

    uv run poe renames:baseline

It needs the tag (`git fetch --tags`); the test itself reads only the JSON and works offline.

The file is the whole difference between the release and the checkout as of the last regeneration, not only the names
that were gone when it was first written, and regenerating it on an unchanged checkout changes nothing. A name that is
back in the metadata drops out. A name that goes later is added, and then `test_gone_since_0_139_0.py` asks for its
answer: a rename in `renamed.py` that refuses it with the new name, or an entry in `REMOVED` (or `SOURCE_NAMES`) with
the reason. Regenerate when a parameter of 0.139.0 is renamed, removed or back, so that the test holds it to an
answer; a name that came back fails the test until then, and otherwise the file is merely older than the checkout.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tarfile
import tempfile
from io import BytesIO
from pathlib import Path

from wetterdienst.metadata.renamed import RENAMED_RESOLUTIONS

RELEASE = "0.139.0"
TAG = f"v{RELEASE}"
GONE = Path(__file__).parent / "gone_since_0_139_0.json"

# run by the interpreter of the checkout with only the archived `src` on its path. `tzfpy`, which that release imported
# at module level and the checkout no longer depends on, is stubbed: nothing here looks up a time zone
_DUMP = """
import importlib, json, pkgutil, sys, types

sys.path.insert(0, sys.argv[1])
sys.modules.setdefault("tzfpy", types.SimpleNamespace(get_tz=lambda *args: None))
import wetterdienst.provider as provider
from wetterdienst.model.metadata import MetadataModel

found = {}
for info in pkgutil.walk_packages(provider.__path__, "wetterdienst.provider."):
    module = importlib.import_module(info.name)
    for value in vars(module).values():
        if isinstance(value, MetadataModel):
            found[value.name] = {
                f"{resolution.name}/{dataset.name}": [parameter.name for parameter in dataset]
                for resolution in value
                for dataset in resolution
            }
json.dump(found, sys.stdout)
"""


def declared_in_release() -> dict[str, dict[str, list[str]]]:
    """Read the parameter names of every dataset of the release, by metadata declaration and `resolution/dataset`."""
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


def declared_now() -> dict[str, dict[str, set[str]]]:
    """Read the same of the checkout."""
    from tests.test_api import ALL_METADATA  # noqa: PLC0415

    return {
        metadata.name: {
            f"{resolution.name}/{dataset.name}": {parameter.name for parameter in dataset}
            for resolution in metadata
            for dataset in resolution
        }
        for metadata in ALL_METADATA
    }


def gone() -> dict[str, dict[str, list[str]]]:
    """Keep what the release declared and the checkout does not, sorted so that the file diffs well."""
    now = declared_now()
    result: dict[str, dict[str, list[str]]] = {}
    for metadata_name, datasets in sorted(declared_in_release().items()):
        for old_key, names in sorted(datasets.items()):
            # a resolution renamed since (`6_hour`) is the same dataset, with RENAMED_RESOLUTIONS to say so
            resolution, dataset = old_key.split("/")
            key = f"{RENAMED_RESOLUTIONS.get(resolution, resolution)}/{dataset}"
            missing = sorted(set(names) - now.get(metadata_name, {}).get(key, set()))
            if missing:
                result.setdefault(metadata_name, {})[key] = missing
    return result


def read_gone() -> dict[str, dict[str, list[str]]]:
    """Read the committed file."""
    return json.loads(GONE.read_text(encoding="utf-8"))["gone"]


def write_gone() -> None:
    """Write the file for the checkout."""
    document = {"release": RELEASE, "gone": gone()}
    GONE.write_text(json.dumps(document, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write_gone()
    count = sum(len(names) for datasets in read_gone().values() for names in datasets.values())
    print(f"wrote {GONE}: {count} parameters of {TAG} that are gone")  # noqa: T201
