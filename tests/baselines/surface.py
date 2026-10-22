# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The Python surface of the last release: the baseline of its names and signatures (GH-3131).

`tests/public_surface.snapshot.json` is the frozen part of the Python API as the pull request leaves it (see
`tests/public_surface.py` for what it holds, among it the request class each provider package exports, whose
internals below the package stay free). `tests/baselines/surface.baseline.json` is the same surface **as it was
released**, so that a removal fails even where the snapshot was regenerated with it. The rule is that the code must
still offer all the baseline offered, and must not ask more of a call:

- a name that is gone breaks: an export of `wetterdienst`, a member of `Period` or `Resolution` or a field of
  `Settings` and `Options` (which are the `WD_*` and `WD_TS_*` variables), a method of `Wetterdienst` or
  `TimeseriesRequest`, a network of the registry, a request class a provider package exported; so does a member of
  an enum with another value;
- a signature breaks when a parameter is gone, becomes required or keyword-only, changes its default, is inserted
  before one that a call passes by position, or is added and required (`tests/baselines/common.py`);
- a new name, a new optional parameter after the others and a keyword-only parameter that becomes positional pass.

The constructor of a network whose extra is not installed here cannot be read, and is not compared (its network is
compared by name).

Refresh with `uv run poe surface:baseline`, in the release commit only (see `tests/baselines/common.py`).
"""

from __future__ import annotations

from typing import Any

from tests.baselines.common import DIRECTORY, RELEASE, read, signature_breaks, write
from tests.public_surface import build_surface

BASELINE = DIRECTORY / "surface.baseline.json"

#: what an approved break says: the finding as `breaking_changes` words it, then why it is no break of a caller
ACCEPTED_BREAKS: dict[str, str] = {
    "Settings: read_bufr was removed": (
        "it parsed the BUFR products of the DWD radar sites onto RadarResult.df, and DWD publishes no radar product "
        "as BUFR any more (GH-3287): the setting does nothing, and Settings(read_bufr=...) is refused with the reason"
    ),
}


def read_baseline() -> dict[str, Any]:
    """Read the committed baseline."""
    return read(BASELINE)


def write_baseline() -> None:
    """Write the surface as the baseline of the version in `pyproject.toml`."""
    write(BASELINE, build_surface())


def breaking_changes(baseline: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """Name each thing that `baseline` offers and `current` does not, or asks more of a call for."""
    found: list[str] = []
    for section, old in baseline.items():
        if section == RELEASE:
            continue
        if section not in current:
            found.append(f"{section} was removed")
        elif section == "requests":
            # the constructor of a network whose extra is missing is not in the current surface: its name is compared
            kept = {key: value for key, value in old.items() if key in current[section]}
            found += _compare(section, kept, current[section])
        else:
            found += _compare(section, old, current[section])
    return sorted(found)


def _compare(where: str, old: Any, new: Any) -> list[str]:  # noqa: ANN401
    if isinstance(old, dict) and isinstance(new, dict):
        found = [f"{where}: {key} was removed" for key in old if key not in new]
        for key, value in old.items():
            if key in new:
                found += _compare(f"{where}.{key}", value, new[key])
        return found
    if isinstance(old, list) and isinstance(new, list):
        return [f"{where}: {name} was removed" for name in old if name not in new]
    if isinstance(old, str) and isinstance(new, str) and old.startswith("("):
        return signature_breaks(where, old, new)
    return [] if old == new else [f"{where}: changed from {old!r} to {new!r}"]


if __name__ == "__main__":
    write_baseline()
