# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Every code a response warning can carry is told in the docs of the REST API (GH-3539)."""

from __future__ import annotations

import ast
import pathlib

SRC = pathlib.Path(__file__).parent.parent / "src" / "wetterdienst"
DOCS = pathlib.Path(__file__).parent.parent / "docs" / "usage" / "restapi.md"
#: where the code is in the call of each function that raises a warning
_CODE_ARGUMENT = {"warn_response": 1, "count_response_warning": 0}


def _codes_in_source() -> set[str]:
    """Give the code of every call of `warn_response` and `count_response_warning`, constants resolved by name."""
    trees = [ast.parse(path.read_text(encoding="utf-8")) for path in SRC.rglob("*.py")]
    constants = {
        target.id: node.value.value
        for tree in trees
        for node in tree.body
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant) and isinstance(node.value.value, str)
        for target in node.targets
        if isinstance(target, ast.Name)
    }
    codes: set[str] = set()
    for tree in trees:
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            name = getattr(node.func, "id", getattr(node.func, "attr", None))
            if name not in _CODE_ARGUMENT or len(node.args) <= _CODE_ARGUMENT[name]:
                continue
            argument = node.args[_CODE_ARGUMENT[name]]
            if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                codes.add(argument.value)
            elif isinstance(argument, ast.Name) and argument.id in constants:
                codes.add(constants[argument.id])
    return codes


def test_every_warning_code_is_in_the_docs() -> None:
    """A client reads the codes it knows, so a code that is raised and not told there is one nobody can know."""
    codes = _codes_in_source()
    assert {"unknown-station", "parameter-without-rows", "missing-value-marker"} <= codes, "the scan finds the codes"
    text = DOCS.read_text(encoding="utf-8")
    assert sorted(code for code in codes if f"`{code}`" not in text) == []
