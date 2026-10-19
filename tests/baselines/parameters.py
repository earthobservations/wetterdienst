# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The parameters of every dataset in the last release, and the renames since (GH-3131).

A request names what it wants as `resolution/dataset/parameter`, so each provider's network, resolution, dataset and
parameter name is an input a caller has written down. `tests/baselines/parameters.baseline.json` is that list **as it
was released**, with the tables of renames at the time (`wetterdienst.metadata.renamed`). The rule is that a name of
the baseline must still be there, or have been renamed:

- a provider, network, resolution or dataset that is gone breaks (a resolution renamed in `RENAMED_RESOLUTIONS`
  does not), and so does a parameter that is neither in its dataset any more nor renamed to a name that is: through
  the rename of the dataset (`RENAMED_PARAMETERS_IN_DATASET`), the one that holds everywhere (`RENAMED_PARAMETERS`),
  or the spot name a sub-daily `_mean_` temperature became, as many times as it was renamed since;
- an entry of the rename tables of the baseline that is no longer in the table breaks: the hint that names the new
  spelling of a name already gone is what a caller who still writes the old one is told, and it stays;
- a new provider, network, resolution, dataset, parameter or rename passes.

After 1.0 a rename keeps the old name as an alias for two minors and a removal is a major (the compatibility policy);
this holds the other half of it: a name that is neither there nor in a rename table fails the check.

A network whose extra is not installed here is not compared, but its name is (`networks` is the registry's).

Refresh with `uv run poe parameters:baseline`, in the release commit only (see `tests/baselines/common.py`).
"""

from __future__ import annotations

from typing import Any

from tests.baselines.common import DIRECTORY, RELEASE, read, write

BASELINE = DIRECTORY / "parameters.baseline.json"

#: what an approved break says: the finding as `breaking_changes` words it, then why it is no break of a caller
ACCEPTED_BREAKS: dict[str, str] = {}

#: a rename that ends up in a name that is renamed again is followed this far
_CHAIN = 10


def build_surface() -> dict[str, Any]:
    """List the parameters of every dataset of every network the registry resolves, and the tables of renames."""
    from wetterdienst import Wetterdienst  # noqa: PLC0415
    from wetterdienst.metadata.renamed import (  # noqa: PLC0415
        RENAMED_PARAMETERS,
        RENAMED_PARAMETERS_IN_DATASET,
        RENAMED_RESOLUTIONS,
    )

    parameters: dict[str, dict[str, dict[str, list[str]]]] = {}
    metadata_names = {}
    for provider, networks in sorted(Wetterdienst.registry.items()):
        for network in sorted(networks):
            if Wetterdienst.is_standalone(provider, network):
                continue
            try:
                metadata = Wetterdienst.resolve(provider, network).metadata
            except ImportError:
                continue
            metadata_names[metadata.name] = f"{provider}/{network}"
            parameters[f"{provider}/{network}"] = {
                resolution.name: {
                    dataset.name: sorted(parameter.name for parameter in dataset) for dataset in resolution
                }
                for resolution in metadata
            }
    in_dataset = {
        metadata_names[name]: {
            f"{resolution}/{dataset}": dict(sorted(renames.items()))
            for (resolution, dataset), renames in sorted(datasets.items())
        }
        for name, datasets in sorted(RENAMED_PARAMETERS_IN_DATASET.items())
        if name in metadata_names
    }
    return {
        "networks": sorted(
            f"{provider}/{network}"
            for provider, networks in Wetterdienst.registry.items()
            for network in networks
            if not Wetterdienst.is_standalone(provider, network)
        ),
        "parameters": parameters,
        "renamed": {
            "parameters": dict(sorted(RENAMED_PARAMETERS.items())),
            "in_dataset": in_dataset,
            "resolutions": dict(sorted(RENAMED_RESOLUTIONS.items())),
        },
    }


def read_baseline() -> dict[str, Any]:
    """Read the committed baseline."""
    return read(BASELINE)


def write_baseline() -> None:
    """Write the parameters as the baseline of the version in `pyproject.toml`."""
    write(BASELINE, build_surface())


def breaking_changes(baseline: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """Name each name of `baseline` that `current` neither has nor says was renamed."""
    found = _renames(baseline["renamed"], current["renamed"])
    for network, resolutions in baseline["parameters"].items():
        if network not in current["parameters"]:
            # a network whose extra is missing here is no finding, a network that is gone from the registry is
            if network not in current["networks"]:
                found.append(f"{network} was removed")
            continue
        for resolution, datasets in resolutions.items():
            found += _resolution(current, network, resolution, datasets)
    return sorted(found)


def _resolution(current: dict[str, Any], network: str, resolution: str, datasets: dict[str, list[str]]) -> list[str]:
    new_resolutions = current["parameters"][network]
    where = f"{network}/{resolution}"
    if resolution not in new_resolutions:
        renamed = current["renamed"]["resolutions"].get(resolution)
        if renamed in new_resolutions:
            return []
        return [f"{where} was removed"]
    found = []
    for dataset, names in datasets.items():
        if dataset not in new_resolutions[resolution]:
            found.append(f"{where}/{dataset} was removed")
            continue
        current_names = set(new_resolutions[resolution][dataset])
        found += [
            f"{where}/{dataset}/{name} was removed"
            for name in names
            if name not in current_names
            and not _renamed(current["renamed"], network, f"{resolution}/{dataset}", name, current_names)
        ]
    return found


def _renamed(renamed: dict[str, Any], network: str, dataset: str, name: str, names: set[str]) -> bool:
    """Say whether a name that the dataset has not is renamed, perhaps more than once, to one that it has."""
    from wetterdienst.model.metadata import _spot_name  # noqa: PLC0415

    seen = {name}
    for _ in range(_CHAIN):
        new = (
            renamed["in_dataset"].get(network, {}).get(dataset, {}).get(name)
            or renamed["parameters"].get(name)
            or _spot_name(name)
        )
        if new is None or new in seen:
            return False
        if new in names:
            return True
        seen.add(new)
        name = new
    return False


def _renames(old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    """Find an entry of a table of renames that is gone: the old name would be refused with no hint."""
    found = [f"rename of {name} was removed" for name in old["parameters"] if name not in new["parameters"]]
    found += [
        f"rename of resolution {name} was removed" for name in old["resolutions"] if name not in new["resolutions"]
    ]
    for network, datasets in old["in_dataset"].items():
        for dataset, renames in datasets.items():
            kept = new["in_dataset"].get(network, {}).get(dataset, {})
            found += [f"rename of {name} in {network}/{dataset} was removed" for name in renames if name not in kept]
    return found


__all__ = ["ACCEPTED_BREAKS", "BASELINE", "RELEASE", "breaking_changes", "build_surface"]

if __name__ == "__main__":
    write_baseline()
