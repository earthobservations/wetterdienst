"""Size on disk of the packages installed in a virtual environment, by distribution (GH-3238).

Run with the interpreter of the environment to measure:

    v-altair/bin/python research/altair_vl_convert/install_size.py

Sums the bytes of every file a distribution's RECORD lists (apparent size, so a clone or hard link
from uv's cache is counted as a full copy, as a fresh `pip install` would write it). The `.pyc`
files the interpreter writes later are in no RECORD and not counted.
"""

from __future__ import annotations

import sys
from importlib import metadata
from pathlib import Path


def size_of(dist: metadata.Distribution) -> int:
    """Return the bytes of the files a distribution's RECORD lists that exist."""
    total = 0
    for file in dist.files or []:
        path = Path(str(dist.locate_file(file)))
        if path.is_file() and not path.is_symlink():
            total += path.stat().st_size
    return total


def main() -> None:
    """Print one line per distribution, largest first, and the total."""
    sizes = {dist.metadata["Name"]: size_of(dist) for dist in metadata.distributions()}
    total = sum(sizes.values())
    for name, size in sorted(sizes.items(), key=lambda item: -item[1]):
        print(f"{name:32s}{size / 1024 / 1024:10.2f} MiB")  # noqa: T201
    print(f"{'TOTAL (' + sys.version.split()[0] + ')':32s}{total / 1024 / 1024:10.2f} MiB")  # noqa: T201


if __name__ == "__main__":
    main()
