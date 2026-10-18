# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The public surface of the Python API as committed, and the command that regenerates it (GH-3131).

From 1.0 the top-level exports, `Wetterdienst` and `discover`, the request, the results, `Settings` and `Options`,
the exceptions and the metadata enums are frozen (GH-2561); `wetterdienst.provider.*` internals, `util` and the model
internals are not. `tests/public_surface.snapshot.json` holds, of the frozen part, what the other tests do not pin:

- `wetterdienst.__all__`, and the members of `Period` and `Resolution`;
- the names of the fields of `Settings` and of `Options`, which are the `WD_*` and `WD_TS_*` variables;
- the signatures of `Wetterdienst`'s public methods, of `TimeseriesRequest` and its public methods, and of the
  constructor of each request class the registry resolves, with the standalone ones, and the networks of the registry.
  The constructor of a network whose extra is not installed cannot be read and is left out of the comparison.

The results (their fields, public methods and the signatures the guide shows) are pinned by
`tests/model/test_results.py`, the exceptions by `tests/test_exceptions.py`, and the types by `tests/typed_caller.py`.

A signature is its parameters' names, kinds and defaults, which is what a caller writes. A default is its value
where that is None, a bool, a number or a string, else `...`; the annotations are left out, as the checker holds them.

`tests/test_public_surface.py` fails when the code has another surface, so a change to it is a change to this file in
the same pull request, where a reviewer sees it as a diff. Regenerate with

    uv run poe surface:snapshot

and read the diff: a removed or renamed name, a parameter that is gone or has become required, or a changed default
breaks a caller; an added name or an added optional parameter does not.
"""

from __future__ import annotations

import inspect
import json
from pathlib import Path
from typing import Any

SNAPSHOT = Path(__file__).parent / "public_surface.snapshot.json"


class _Text:
    """A default that prints as the text it stands for."""

    def __init__(self, text: str) -> None:
        self.text = text

    def __repr__(self) -> str:
        return self.text


def signature_of(target: Any) -> str:  # noqa: ANN401
    """Write the signature of a callable as its parameters' names, kinds and defaults."""
    signature = inspect.signature(target)
    parameters = []
    for parameter in signature.parameters.values():
        default: Any = parameter.default
        if default is not inspect.Parameter.empty:
            default = _Text(repr(default) if default is None or isinstance(default, (bool, int, float, str)) else "...")
        parameters.append(parameter.replace(annotation=inspect.Parameter.empty, default=default))
    return str(inspect.Signature(parameters))


def _public(cls: type) -> dict[str, str]:
    """Give the public methods of a class by name with their signatures, and the other public attributes as such."""
    surface = {}
    for name in sorted(vars(cls)):
        if name.startswith("_"):
            continue
        member = inspect.getattr_static(cls, name)
        if isinstance(member, (classmethod, staticmethod)) or inspect.isfunction(member):
            surface[name] = signature_of(getattr(cls, name))
        elif isinstance(member, property):
            surface[name] = "property"
    return surface


def _requests() -> dict[str, str]:
    """Give the constructor of each request class the registry resolves, but of a network whose extra is missing."""
    from wetterdienst import Wetterdienst  # noqa: PLC0415
    from wetterdienst.exceptions import MissingDependencyError  # noqa: PLC0415

    found = {}
    for provider, networks in sorted(Wetterdienst.registry.items()):
        for network in sorted(networks):
            try:
                resolve = (
                    Wetterdienst.resolve_standalone
                    if Wetterdienst.is_standalone(provider, network)
                    else Wetterdienst.resolve
                )
                found[f"{provider}/{network}"] = signature_of(resolve(provider, network))
            except (MissingDependencyError, ImportError):
                continue
    return found


def build_surface() -> dict[str, Any]:
    """Describe the frozen surface of the Python API as the code has it."""
    import wetterdienst  # noqa: PLC0415
    from wetterdienst import Options, Period, Resolution, Settings, Wetterdienst  # noqa: PLC0415
    from wetterdienst.model.request import TimeseriesRequest  # noqa: PLC0415

    return {
        "__all__": sorted(wetterdienst.__all__),
        "Period": {member.name: member.value for member in Period},
        "Resolution": {member.name: member.value for member in Resolution},
        "Settings": sorted(Settings.model_fields),
        "Options": sorted(Options.model_fields),
        "Wetterdienst": _public(Wetterdienst),
        "networks": sorted(
            f"{provider}/{network}" for provider, networks in Wetterdienst.registry.items() for network in networks
        ),
        "TimeseriesRequest": {"__init__": signature_of(TimeseriesRequest), **_public(TimeseriesRequest)},
        "requests": _requests(),
    }


def write_snapshot() -> None:
    """Write the surface as the snapshot."""
    SNAPSHOT.write_text(json.dumps(build_surface(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    write_snapshot()
    print(f"wrote {SNAPSHOT}")  # noqa: T201
