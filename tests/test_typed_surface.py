# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for what a type checker makes of the package for the people who use it.

The package ships a `py.typed` marker (PEP 561), so a caller's checker reads the annotations of the
public surface instead of taking everything for `Any`. These tests hold up the three things that
promise rests on: the marker, the surface as a checker reads it, and the `ignore` comments that stand
between the annotations and the truth.
"""

import ast
import importlib.resources
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent
SRC = ROOT / "src" / "wetterdienst"
CALLER = Path(__file__).parent / "typed_caller.py"

# `# ty: ignore[rule-code]`, the only form of ignore the package keeps
NARROW_IGNORE = re.compile(r"#\s*ty:\s*ignore\[[a-z][a-z-]*(?:,\s*[a-z][a-z-]*)*\]")
# any other way to silence a checker: a blanket `ty: ignore`, mypy's and pyright's, a `type: ignore`
ANY_IGNORE = re.compile(r"#\s*(?:ty|type|pyright|mypy):\s*ignore")


def test_the_package_ships_the_py_typed_marker() -> None:
    """Test that a type checker is told the package is typed.

    Without the marker a checker treats the package as untyped and gives a caller `Any` for all of it,
    whatever the annotations say.
    """
    assert importlib.resources.files("wetterdienst").joinpath("py.typed").is_file()


def test_the_public_surface_type_checks_as_a_caller_sees_it() -> None:
    """Test that the type of each result of the documented API is what `tests/typed_caller.py` says.

    The script is checked by the checker the project uses on its own code, which reads the package
    from `src/`. An `assert_type` that no longer holds names the result that turned into `Any`, or
    into something a caller must cast. This run reads the checkout; `poe typecheck:installed`
    (`tests/check_installed_typing.py`) runs the same script against the built wheel, installed as a caller
    installs it. (mypy and pyright, which the marker matters to, were run by hand against a built wheel;
    see GH-2622.)
    """
    completed = subprocess.run(  # noqa: S603
        [
            sys.executable,
            "-m",
            "ty",
            "check",
            "--error-on-warning",
            "--output-format",
            "concise",
            "--python",
            sys.prefix,
            str(CALLER),
        ],
        capture_output=True,
        text=True,
        check=False,
        cwd=ROOT,
    )

    assert completed.returncode == 0, completed.stdout + completed.stderr


def _ignore_comments() -> list[tuple[Path, int, str, str]]:
    """List every comment that silences a checker: file, line, the line itself and the one above it."""
    found = []
    for path in sorted(SRC.rglob("*.py")):
        lines = path.read_text(encoding="utf8").splitlines()
        for number, line in enumerate(lines, start=1):
            if ANY_IGNORE.search(line):
                found.append((path, number, line, lines[number - 2] if number > 1 else ""))
    return found


def test_the_ignore_comments_name_the_rule_they_silence() -> None:
    """Test that no comment silences a checker wholesale.

    A blanket ignore also hides the next defect on the line, which is the one nobody has looked at.
    """
    blanket = [
        f"{path.relative_to(ROOT)}:{number}: {line.strip()}"
        for path, number, line, _ in _ignore_comments()
        if not NARROW_IGNORE.search(line)
    ]

    assert not blanket, "name the rule, as in `# ty: ignore[invalid-assignment]`:\n" + "\n".join(blanket)


def test_the_ignore_comments_say_why() -> None:
    """Test that each ignore has the reason for it in the comment on the line above.

    An ignore is a claim that the checker is wrong or that the code is right in spite of it, and the
    reader of the line cannot check a claim that is not made. The reason says which of the two it is.
    """
    unexplained = [
        f"{path.relative_to(ROOT)}:{number}: {line.strip()}"
        for path, number, line, above in _ignore_comments()
        if not above.strip().startswith("#") and not line.strip().startswith("#")
    ]

    assert not unexplained, "put the reason in a comment on the line above:\n" + "\n".join(unexplained)


def test_the_ignore_comments_are_still_needed() -> None:
    """Test that `ty` is set to report an ignore that silences nothing (`unused-ignore-comment`).

    `poe typecheck` then fails on one, so a fix that makes an ignore pointless takes it out in the
    same change. Only the setting is read here; the check itself is the typecheck.
    """
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf8")

    assert re.search(r'(?m)^unused-ignore-comment = "(?:warn|error)"$', pyproject)


def _imports_of(path: Path) -> set[str]:
    """Name what a module takes from another module of the package at its top level."""
    names = set()
    for node in ast.parse(path.read_text(encoding="utf8")).body:
        if isinstance(node, ast.ImportFrom) and (node.module or "").startswith("wetterdienst."):
            names.update(alias.asname or alias.name for alias in node.names)
    return names


def _all_of(path: Path) -> set[str] | None:
    """Read the names of the `__all__` a module declares, or None if it declares none."""
    for node in ast.parse(path.read_text(encoding="utf8")).body:
        if isinstance(node, ast.Assign) and any(getattr(target, "id", None) == "__all__" for target in node.targets):
            return set(ast.literal_eval(node.value))
    return None


@pytest.mark.parametrize(
    "path",
    [path for path in sorted(SRC.rglob("__init__.py")) if _imports_of(path)],
    ids=lambda path: str(path.parent.relative_to(SRC.parent)),
)
def test_a_package_that_imports_names_exports_them(path: Path) -> None:
    """Test that a package which re-exports names says so in `__all__`.

    A checker reading a typed package takes a name that a module merely imports for private, so
    `from wetterdienst.provider.dwd.observation import DwdObservationRequest` is an error in a
    caller's strict mode unless the package lists it.
    """
    exported = _all_of(path)

    assert exported is not None, f"{path.relative_to(ROOT)} imports names and declares no __all__"
    assert _imports_of(path) <= exported


def _module_level_assignments(path: Path) -> dict[str, list[ast.AST]]:
    """Map each name a module assigns at its top level to the assignments, in the order written."""
    found: dict[str, list[ast.AST]] = {}
    for node in ast.parse(path.read_text(encoding="utf8")).body:
        targets = (
            node.targets if isinstance(node, ast.Assign) else [node.target] if isinstance(node, ast.AnnAssign) else []
        )
        for target in targets:
            if isinstance(target, ast.Name):
                found.setdefault(target.id, []).append(node)
    return found


def test_a_provider_metadata_name_is_bound_once_to_the_model() -> None:
    """Test that `XMetadata = build_metadata_model(...)` is the only assignment of `XMetadata`.

    A provider used to declare its metadata as a dict under the name that it then rebound to the model.
    ty follows the rebinding, so a caller's `DwdObservationMetadata.daily` type-checked under it, but mypy
    takes the first assignment for the declared type and read `DwdObservationMetadata` as a dict (and
    `DwdObservationRequest.metadata` with it), where every attribute is an error. The dict has a name of its
    own, and the public name is bound to the model alone.
    """
    rebound = []
    for path in sorted(SRC.joinpath("provider").rglob("*.py")):
        for name, assignments in _module_level_assignments(path).items():
            builds_model = any(
                isinstance(node, ast.Assign | ast.AnnAssign)
                and isinstance(node.value, ast.Call)
                and getattr(node.value.func, "id", getattr(node.value.func, "attr", None)) == "build_metadata_model"
                for node in assignments
            )
            if builds_model and len(assignments) > 1:
                rebound.append(f"{path.relative_to(ROOT)}: {name}")

    assert not rebound, "give the dict of the metadata a name of its own:\n" + "\n".join(rebound)
