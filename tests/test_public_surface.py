# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The public surface of the Python API is the committed snapshot, so a change to it is a diff in the PR (GH-3131).

See `tests/public_surface.py` for what the snapshot holds, what the others pin, and the command that regenerates it.
"""

from __future__ import annotations

import ast
import json
from typing import Any

import pytest

from tests.public_surface import SNAPSHOT, build_surface, signature_of

_REGENERATE = (
    "The public surface of the Python API is not tests/public_surface.snapshot.json. If the change is intended, "
    "regenerate the snapshot with `uv run poe surface:snapshot` and review the diff: a removed or renamed name, a "
    "parameter that is gone or has become required, or a changed default breaks a caller; an added name or an added "
    "optional parameter does not."
)


def _changes(served: object, committed: object, where: str = "") -> list[str]:
    """Name where two surfaces differ, down to the name, so that a failure says what changed."""
    if isinstance(served, dict) and isinstance(committed, dict):
        found = [f"{where}/{key} was removed" for key in committed.keys() - served.keys()]
        found += [f"{where}/{key} was added" for key in served.keys() - committed.keys()]
        for key in served.keys() & committed.keys():
            found += _changes(served[key], committed[key], f"{where}/{key}")
        return sorted(found)
    if isinstance(served, list) and isinstance(committed, list):
        found = [f"{where}: {name} was removed" for name in committed if name not in served]
        return found + [f"{where}: {name} was added" for name in served if name not in committed]
    return [] if served == committed else [f"{where}: {committed!r} is now {served!r}"]


def test_the_public_surface_is_the_committed_snapshot() -> None:
    """The exports, the settings and options, the entry points and the request constructors are what was reviewed."""
    committed: dict[str, Any] = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    served = build_surface()
    # the constructor of a network whose extra is not installed is not read here
    committed["requests"] = {key: value for key, value in committed["requests"].items() if key in served["requests"]}

    changes = _changes(served, committed)

    assert not changes, f"{_REGENERATE}\n" + "\n".join(changes[:40])


def test_every_network_of_the_registry_is_in_the_snapshot() -> None:
    """The networks are compared whole, so that one whose extra is missing here is still named."""
    committed = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    assert build_surface()["networks"] == committed["networks"]
    assert set(committed["requests"]) <= set(committed["networks"])


def test_the_snapshot_holds_the_entry_points_of_the_guide() -> None:
    """The snapshot has the calls the guide names, so that an empty or a truncated one cannot pass."""
    committed = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    assert {"Wetterdienst", "Options", "Settings", "Period", "Resolution"} <= set(committed["__all__"])
    assert {"resolve", "resolve_standalone", "discover", "is_valid", "is_configured"} <= set(committed["Wetterdienst"])
    assert {"all", "filter_by_station_id", "filter_by_name", "interpolate", "summarize"} <= set(
        committed["TimeseriesRequest"]
    )
    assert "dwd/observation" in committed["requests"]
    assert (
        committed["request_exports"]["dwd/observation"] == "wetterdienst.provider.dwd.observation.DwdObservationRequest"
    )
    assert {"cache_dir", "auth"} <= set(committed["Settings"])
    assert committed["Options"]


def _private_parameters(surface: object, where: str = "") -> list[str]:
    """Name each parameter that starts with an underscore in a signature of a surface, wherever it is in it."""
    if isinstance(surface, dict):
        return [name for key, value in surface.items() for name in _private_parameters(value, f"{where}/{key}")]
    if isinstance(surface, str) and surface.startswith("("):
        function = ast.parse(f"def f{surface}: pass").body[0]
        assert isinstance(function, ast.FunctionDef)
        arguments = function.args
        names = [a.arg for a in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs)]
        names += [a.arg for a in (arguments.vararg, arguments.kwarg) if a is not None]
        return [f"{where}: {name}" for name in names if name.startswith("_")]
    return []


def test_no_signature_of_the_surface_has_a_private_parameter() -> None:
    """A private field of a request is no constructor argument (`init=False`): 1.0 freezes what the signature names.

    A dataclass field that is a cache the request sets itself, without `init=False`, is a parameter of the
    constructor, and then part of the surface (`_snow_stations` of `dwd/mosmix`, GH-4128, and the three of `dwd/dmo`,
    GH-4142). Both the committed snapshot and the surface as the code serves it are read.
    """
    committed = json.loads(SNAPSHOT.read_text(encoding="utf-8"))

    assert _private_parameters(committed) == []
    assert _private_parameters(build_surface()) == []


def test_a_private_parameter_is_found_wherever_a_signature_has_one() -> None:
    """The check reads each kind of parameter, so that a private one cannot hide in a keyword-only or a variadic."""
    surface = {"x": {"y": "(a, /, b=None, *, _c=1)", "z": "(a, *_args, **_kwargs)", "w": "(a, b)"}}

    assert _private_parameters(surface) == ["/x/y: _c", "/x/z: _args", "/x/z: _kwargs"]


_SENTINEL = object()


def _defaults(a: int, b: None = None, *, c: int = 1, d: str = "x", e: object = _SENTINEL) -> None:
    """Stand in for a function with defaults of each kind."""


def _kinds(a: int, /, b: int, *args: int, **kwargs: int) -> None:
    """Stand in for a function with a parameter of each kind."""


@pytest.mark.parametrize(
    ("function", "expected"),
    [
        pytest.param(_defaults, "(a, b=None, *, c=1, d='x', e=...)", id="defaults"),
        pytest.param(_kinds, "(a, /, b, *args, **kwargs)", id="kinds"),
    ],
)
def test_a_signature_is_names_kinds_and_defaults(function: Any, expected: str) -> None:  # noqa: ANN401
    """The text of a signature is what a caller writes: no annotations, a default as its value when it is simple."""
    assert signature_of(function) == expected
