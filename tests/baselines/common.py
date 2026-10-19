# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What every baseline of the contract has in common (GH-3131).

A baseline is a surface **as the last release offered it**: what a caller written against that release relies on.
Unlike a snapshot, which shows every change as a diff, a baseline is compared with the code and fails on a removal or
a change, whether or not the snapshot was regenerated with it. The rule is the same for each surface:

- what the baseline offers must still be offered, with the same meaning; an addition always passes;
- a break that is meant is named in the `ACCEPTED_BREAKS` of that surface, with the reason, and a **Breaking** entry
  in the changelog says what to do instead. An entry for a break that is not there any more is reported;
- the baseline is refreshed only in the release commit (`uv run poe contracts:baseline`), when `x-release` in each
  one becomes the version of `pyproject.toml`, which a test of each surface enforces. The entries of
  `ACCEPTED_BREAKS` are removed with it.

The OpenAPI document is one of them (`tests/ui/openapi_baseline.py`); the others are under `tests/baselines`: the
command line, the Python surface, the MCP tools and the parameters of every dataset.
"""

from __future__ import annotations

import ast
import json
import tomllib
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Collection, Mapping

#: where a baseline says which release it is the surface of
RELEASE = "x-release"
PYPROJECT = Path(__file__).parents[2] / "pyproject.toml"
DIRECTORY = Path(__file__).parent

#: how a positional parameter may change: a keyword-only one may become positional, a positional-only one may accept
#: the keyword, and no other move keeps every call working
_KINDS_KEPT = {
    ("POSITIONAL_ONLY", "POSITIONAL_ONLY"),
    ("POSITIONAL_ONLY", "POSITIONAL_OR_KEYWORD"),
    ("POSITIONAL_OR_KEYWORD", "POSITIONAL_OR_KEYWORD"),
    ("KEYWORD_ONLY", "KEYWORD_ONLY"),
    ("KEYWORD_ONLY", "POSITIONAL_OR_KEYWORD"),
}


def project_version() -> str:
    """Give the version `pyproject.toml` declares, which is that of the last release until the release commit."""
    return tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))["project"]["version"]


def read(path: Path) -> dict[str, Any]:
    """Read a baseline."""
    return json.loads(path.read_text(encoding="utf-8"))


def write(path: Path, surface: Mapping[str, Any]) -> None:
    """Write a surface as the baseline of the version in `pyproject.toml`."""
    document = {**surface, RELEASE: project_version()}
    path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {path} for {project_version()}")  # noqa: T201


def unaccepted(findings: Collection[str], accepted: Mapping[str, str]) -> list[str]:
    """Leave out the findings that the accepted breaks approve."""
    return sorted(finding for finding in findings if finding not in accepted)


def stale(findings: Collection[str], accepted: Mapping[str, str]) -> list[str]:
    """Name the accepted breaks that are no finding any more: the break was undone, or the baseline was refreshed."""
    return sorted(entry for entry in accepted if entry not in findings)


def without_reason(accepted: Mapping[str, str]) -> list[str]:
    """Name the accepted breaks that give no reason worth the name (the reason is what a reviewer reads)."""
    return [entry for entry, reason in accepted.items() if len(reason) <= 20]


def _parameters(signature: str) -> list[tuple[str, str, str | None]]:
    """Read the parameters of a signature as `signature_of` of `tests/public_surface.py` writes it.

    Give each as its name, its kind and the source of its default, which is None where there is none.
    """
    function = ast.parse(f"def f{signature}: pass").body[0]
    assert isinstance(function, ast.FunctionDef)
    arguments = function.args
    positional = [*arguments.posonlyargs, *arguments.args]
    defaults: list[ast.expr | None] = [None] * (len(positional) - len(arguments.defaults)) + list(arguments.defaults)
    found: list[tuple[str, str, str | None]] = []
    for index, (argument, default) in enumerate(zip(positional, defaults, strict=True)):
        kind = "POSITIONAL_ONLY" if index < len(arguments.posonlyargs) else "POSITIONAL_OR_KEYWORD"
        found.append((argument.arg, kind, None if default is None else ast.unparse(default)))
    if arguments.vararg:
        found.append((arguments.vararg.arg, "VAR_POSITIONAL", None))
    for argument, default in zip(arguments.kwonlyargs, arguments.kw_defaults, strict=True):
        found.append((argument.arg, "KEYWORD_ONLY", None if default is None else ast.unparse(default)))
    if arguments.kwarg:
        found.append((arguments.kwarg.arg, "VAR_KEYWORD", None))
    return found


def signature_breaks(where: str, old: str, new: str) -> list[str]:
    """Name what a signature no longer accepts that it did, or asks more of a call for.

    A signature is written as `signature_of` of `tests/public_surface.py` writes it: names, kinds and defaults. A
    call written against the old one breaks when a parameter is gone, becomes required or keyword-only, or changes its
    default, when a parameter is inserted before one that a call may pass by position, and when a new one is required.
    A new optional parameter after the others, and a keyword-only one that becomes positional, do not. A default
    written `...` stands for a value the snapshot does not print, and is not compared.
    """
    if old == new:
        return []
    olds = _parameters(old)
    news = _parameters(new)
    found = []
    for kind in ("VAR_POSITIONAL", "VAR_KEYWORD"):
        if any(k == kind for _, k, _ in olds) and not any(k == kind for _, k, _ in news):
            found.append(f"{where}: {'*args' if kind == 'VAR_POSITIONAL' else '**kwargs'} was removed")
    old_by_name = {name: (kind, default) for name, kind, default in olds if not kind.startswith("VAR_")}
    new_by_name = {name: (kind, default) for name, kind, default in news if not kind.startswith("VAR_")}
    for name, (kind, default) in old_by_name.items():
        if name not in new_by_name:
            found.append(f"{where}: parameter {name} was removed")
        else:
            found += _kept(where, name, (kind, default), new_by_name[name])
    found += [
        f"{where}: parameter {name} was added and is required"
        for name, (_, default) in new_by_name.items()
        if name not in old_by_name and default is None
    ]
    return found + _positions(where, old_by_name, new_by_name)


def _kept(where: str, name: str, old: tuple[str, str | None], new: tuple[str, str | None]) -> list[str]:
    """Find what became of a parameter that is still there: its kind, whether it is required, its default."""
    (kind, default), (new_kind, new_default) = old, new
    found = []
    if kind != new_kind and (kind, new_kind) not in _KINDS_KEPT:
        found.append(f"{where}: parameter {name} changed from {kind.lower()} to {new_kind.lower()}")
    if default is not None and new_default is None:
        found.append(f"{where}: parameter {name} became required")
    elif default is not None and new_default != default and "..." not in {default, new_default}:
        found.append(f"{where}: default of {name} changed from {default} to {new_default}")
    return found


def _positions(where: str, old: dict[str, tuple[str, str | None]], new: dict[str, tuple[str, str | None]]) -> list[str]:
    """Find a call by position that no longer means what it did: parameters reordered, or one put before the others."""
    old_order = [name for name, (kind, _) in old.items() if kind.startswith("POSITIONAL")]
    new_order = [name for name, (kind, _) in new.items() if kind.startswith("POSITIONAL")]
    if [name for name in old_order if name in new_order] != [name for name in new_order if name in old_order]:
        return [f"{where}: the positional parameters were reordered"]
    inserted = False
    for name in new_order:
        if name not in old_order:
            inserted = True
        elif inserted:
            return [f"{where}: a parameter was inserted before {name}, which a call may pass by position"]
    return []
