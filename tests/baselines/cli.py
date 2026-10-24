# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The command line of the last release: the baseline of its commands and options, and what compares with it (GH-3131).

`tests/ui/cli/help.snapshot.txt` is the `--help` of every command as the pull request leaves it. This is the
command line **as it was released**, as data a script is written against, so that a removal fails even where the
snapshot was regenerated with it:

- each command and group, by its path (`wetterdienst stripes image`);
- each option of it by each of its spellings (`--stations`, `-v`), with its type (and the choices, or the range, of
  that type), whether it is required, takes several values, or is a flag, its number of arguments, its default and the
  environment variable it reads;
- the exit codes the command line can end with.

Not compared: the help text, which describes more than it promises. The rule is that the command line must still offer
all the baseline offered, and must not ask more of a call:

- a command, an option or a spelling of one that is gone, or a type, `nargs`, `multiple` or flag that changed, breaks;
- a choice that is gone, a range that is narrower, an option that was free text and now takes choices, or one that
  is newly required, breaks; a changed default breaks;
- a new command, option, spelling or choice, a wider range, and an option that stopped being required, pass;
- an exit code that is not one of the baseline's, or one of it that is gone, is a finding: a script branches on them
  (`tests/ui/test_exit_codes.py` pins what each means).

Refresh with `uv run poe cli:baseline`, in the release commit only (see `tests/baselines/common.py`).
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import click

from tests.baselines.common import DIRECTORY, read, write

BASELINE = DIRECTORY / "cli.baseline.json"

#: what an approved break says: the finding as `breaking_changes` words it, then why it is no break of a script
ACCEPTED_BREAKS: dict[str, str] = {}

#: the keys of an option that are compared as they are: a change is a finding
_SAME = ("param_type_name", "nargs", "multiple", "is_flag", "count", "envvar", "flag_value")
#: the keys of a type that describe a range, with whether it is a lower bound
_RANGE = (("min", True), ("max", False))


def _default(value: Any) -> Any:  # noqa: ANN401
    """Write a default as JSON: a callable or an object is only named, as the default is not its value to compare."""
    if value is None or isinstance(value, (bool, int, float, str)):
        return value
    if isinstance(value, (list, tuple)):
        return [_default(item) for item in value]
    return f"<{type(value).__name__}>"


def _option(info: dict[str, Any]) -> dict[str, Any]:
    """Describe an option or an argument by what a script depends on."""
    kind = info["type"]
    return {
        **{key: info[key] for key in _SAME},
        "type": kind["name"],
        "choices": sorted(kind["choices"]) if "choices" in kind else None,
        "min": kind.get("min"),
        "max": kind.get("max"),
        "spellings": sorted(_spellings(info)),
        "required": info["required"],
        "default": _default(info["default"]),
    }


def _spellings(param: dict[str, Any]) -> list[str]:
    """Give the spellings an option is written with, or the name of an argument."""
    if param["param_type_name"] == "argument":
        return [f"<{param['name']}>"]
    return [*param["opts"], *param["secondary_opts"]]


def _walk(info: dict[str, Any], path: str, found: dict[str, Any]) -> None:
    # an option by each of its spellings, so that one dropped is found
    options = {spelling: _option(param) for param in info["params"] for spelling in _spellings(param)}
    found[path] = {"options": dict(sorted(options.items()))}
    for name, sub in sorted(info.get("commands", {}).items()):
        _walk(sub, f"{path} {name}", found)


def exit_codes() -> list[int]:
    """Give the exit codes the command line can end with: 0, click's code for an error, and its explicit exits.

    As `tests/ui/test_exit_codes.py` reads them: the arguments of every `sys.exit` of the module, the codes of the
    `click` errors it raises, and click's own, which are 1 for any `ClickException`, an interrupt and a defect, and 2
    for a usage error.
    """
    from wetterdienst.ui import cli as module  # noqa: PLC0415

    codes = {0, click.ClickException.exit_code, click.UsageError.exit_code}
    for node in ast.walk(ast.parse(Path(module.__file__).read_text(encoding="utf-8"))):
        if isinstance(node, ast.Call) and ast.unparse(node.func) in {
            "sys.exit",
            "exit",
            "ctx.exit",
            "click.Context.exit",
        }:
            codes.add(int(ast.unparse(node.args[0])) if node.args else 0)
        if isinstance(node, ast.Raise) and node.exc is not None:
            call = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
            if ast.unparse(call).startswith("click."):
                codes.add(getattr(click, ast.unparse(call).removeprefix("click.")).exit_code)
    return sorted(codes)


def describe(command: click.Command, name: str = "wetterdienst") -> dict[str, Any]:
    """Describe a command and every command under it, by path."""
    commands: dict[str, Any] = {}
    _walk(command.to_info_dict(click.Context(command, info_name=name)), name, commands)
    return commands


def build_surface() -> dict[str, Any]:
    """Describe the command line as the code has it."""
    from wetterdienst.ui.cli import cli  # noqa: PLC0415

    return {"exit_codes": exit_codes(), "commands": describe(cli)}


def read_baseline() -> dict[str, Any]:
    """Read the committed baseline."""
    return read(BASELINE)


def write_baseline() -> None:
    """Write the command line as the baseline of the version in `pyproject.toml`."""
    write(BASELINE, build_surface())


def breaking_changes(baseline: dict[str, Any], current: dict[str, Any]) -> list[str]:
    """Name each thing that `baseline` offers and `current` does not, or asks more of a call for."""
    found = []
    if baseline["exit_codes"] != current["exit_codes"]:
        found.append(f"exit codes changed from {baseline['exit_codes']} to {current['exit_codes']}")
    for path, old_command in baseline["commands"].items():
        new_command = current["commands"].get(path)
        if new_command is None:
            found.append(f"{path} was removed")
            continue
        for spelling, old_option in old_command["options"].items():
            new_option = new_command["options"].get(spelling)
            if new_option is None:
                found.append(f"{path}: {spelling} was removed")
            else:
                found += _option_breaks(f"{path}: {spelling}", old_option, new_option)
        found += [
            f"{path}: {spelling} was added and is required"
            for spelling, option in new_command["options"].items()
            # an option once, whatever its spellings, and a new spelling of an option there was is no new option
            if spelling == option["spellings"][0]
            and option["required"]
            and not set(option["spellings"]) & set(old_command["options"])
        ]
    return sorted(found)


def _option_breaks(where: str, old: dict[str, Any], new: dict[str, Any]) -> list[str]:
    found = [
        f"{where}: {key} changed from {old[key]} to {new[key]}" for key in (*_SAME, "type") if old[key] != new[key]
    ]
    if new["required"] and not old["required"]:
        found.append(f"{where}: became required")
    if old["default"] != new["default"]:
        found.append(f"{where}: default changed from {old['default']!r} to {new['default']!r}")
    if old["choices"] is None and new["choices"] is not None:
        found.append(f"{where}: now takes only the choices {', '.join(new['choices'])}")
    elif old["choices"] is not None and new["choices"] is not None:
        gone = sorted(set(old["choices"]) - set(new["choices"]))
        found += [f"{where}: choices {', '.join(gone)} were removed"] if gone else []
    for key, lower in _RANGE:
        before, after = old[key], new[key]
        if after is not None and (before is None or (after > before if lower else after < before)):
            found.append(f"{where}: {key} became {after}" + ("" if before is None else f" (was {before})"))
    return found


if __name__ == "__main__":
    write_baseline()
