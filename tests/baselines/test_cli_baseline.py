# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The comparison of the command line with the last release, tested with commands made here (GH-3131).

`tests/baselines/test_baselines.py` holds the real command line to its baseline; these are the differ's own tests:
each kind of break is found, and each kind of addition passes.
"""

from __future__ import annotations

import copy
from typing import Any

import click
import pytest

from tests.baselines.cli import ACCEPTED_BREAKS, breaking_changes, describe, exit_codes
from tests.baselines.common import unaccepted


@click.group()
def _root() -> None:
    """Stand in for the command line."""


@_root.command("show")
@click.option("--provider", required=True)
@click.option("--mode", type=click.Choice(["a", "b"]), default="a")
@click.option("--limit", type=click.IntRange(min=1, max=100), default=10)
@click.option("--debug/--no-debug", default=False)
@click.option("-n", "--name", default=None)
@click.option("--many", multiple=True)
def _show(**kwargs: Any) -> None:  # noqa: ANN401
    """Stand in for a command."""


@_root.group("sub")
def _sub() -> None:
    """Stand in for a group."""


@_sub.command("deep")
@click.option("--flag", is_flag=True)
def _deep(**kwargs: Any) -> None:  # noqa: ANN401
    """Stand in for a command in a group."""


def _surface() -> dict[str, Any]:
    return {"exit_codes": [0, 1, 2], "commands": describe(_root, "tool")}


def _changed(edit: Any) -> list[str]:  # noqa: ANN401
    """Edit a copy of the surface and say what the edit breaks."""
    current = copy.deepcopy(_surface())
    edit(current)
    return breaking_changes(_surface(), current)


def _option(surface: dict[str, Any], spelling: str, command: str = "tool show") -> dict[str, Any]:
    return surface["commands"][command]["options"][spelling]


def test_the_commands_are_described_by_their_path_and_the_options_by_each_spelling() -> None:
    """A command is its path, an option each of its spellings: one that is dropped is found by name."""
    surface = _surface()

    assert list(surface["commands"]) == ["tool", "tool show", "tool sub", "tool sub deep"]
    assert {"--provider", "--mode", "--limit", "--debug", "--no-debug", "-n", "--name", "--many", "--help"} == set(
        surface["commands"]["tool show"]["options"]
    )
    assert _option(surface, "--mode")["choices"] == ["a", "b"]
    assert _option(surface, "--limit")["min"] == 1
    assert _option(surface, "--limit")["max"] == 100
    assert _option(surface, "--provider")["required"] is True
    assert _option(surface, "--many")["multiple"] is True
    assert _option(surface, "-n")["spellings"] == ["--name", "-n"]


def test_the_real_exit_codes_are_0_1_and_2() -> None:
    """The codes of the command line are the ones `tests/ui/test_exit_codes.py` freezes."""
    assert exit_codes() == [0, 1, 2]


def test_a_command_line_is_not_a_break_of_itself() -> None:
    """The differ finds nothing where nothing changed."""
    assert breaking_changes(_surface(), _surface()) == []


@pytest.mark.parametrize(
    ("edit", "expected"),
    [
        pytest.param(lambda s: s["commands"].pop("tool show"), "tool show was removed", id="command"),
        pytest.param(lambda s: s["commands"].pop("tool sub"), "tool sub was removed", id="group"),
        pytest.param(lambda s: s["commands"].pop("tool sub deep"), "tool sub deep was removed", id="command-in-group"),
        pytest.param(
            lambda s: s["commands"]["tool show"]["options"].pop("--mode"), "tool show: --mode was removed", id="option"
        ),
        pytest.param(
            lambda s: s["commands"]["tool show"]["options"].pop("-n"), "tool show: -n was removed", id="spelling"
        ),
        pytest.param(
            lambda s: s["commands"]["tool show"]["options"].pop("--no-debug"),
            "tool show: --no-debug was removed",
            id="secondary-spelling",
        ),
        pytest.param(
            lambda s: s["commands"]["tool show"]["options"].update(
                {"--provider-name": s["commands"]["tool show"]["options"].pop("--provider")}
            ),
            "tool show: --provider was removed",
            id="renamed",
        ),
        pytest.param(
            lambda s: _option(s, "--limit").update(type="text"), "--limit: type changed from integer range", id="type"
        ),
        pytest.param(
            lambda s: _option(s, "--limit").update(default=20), "--limit: default changed from 10 to 20", id="default"
        ),
        pytest.param(
            lambda s: _option(s, "--limit").update(default=None),
            "--limit: default changed from 10 to None",
            id="no-default",
        ),
        pytest.param(
            lambda s: _option(s, "--name").update(default="x"),
            "--name: default changed from None to 'x'",
            id="default-added",
        ),
        pytest.param(
            lambda s: _option(s, "--mode")["choices"].remove("b"), "--mode: choices b were removed", id="choice"
        ),
        pytest.param(
            lambda s: _option(s, "--name").update(choices=["x"]),
            "--name: now takes only the choices x",
            id="choices-added",
        ),
        pytest.param(lambda s: _option(s, "--limit").update(min=2), "--limit: min became 2 (was 1)", id="min"),
        pytest.param(lambda s: _option(s, "--limit").update(max=50), "--limit: max became 50 (was 100)", id="max"),
        pytest.param(lambda s: _option(s, "--name").update(max=5), "--name: max became 5", id="range-added"),
        pytest.param(lambda s: _option(s, "--name").update(required=True), "--name: became required", id="required"),
        pytest.param(lambda s: _option(s, "--many").update(multiple=False), "--many: multiple changed", id="multiple"),
        pytest.param(lambda s: _option(s, "--many").update(nargs=2), "--many: nargs changed from 1 to 2", id="nargs"),
        pytest.param(
            lambda s: _option(s, "--flag", "tool sub deep").update(is_flag=False),
            "--flag: is_flag changed from True to False",
            id="flag",
        ),
        pytest.param(
            lambda s: _option(s, "--name").update(envvar="WD_NAME"), "--name: envvar changed from None", id="envvar"
        ),
        pytest.param(
            lambda s: _option(s, "--name").update(param_type_name="argument"),
            "--name: param_type_name changed",
            id="kind",
        ),
        pytest.param(
            lambda s: s["commands"]["tool show"]["options"].update(
                {
                    "--new": {
                        **_option(s, "--name"),
                        "required": True,
                        "default": None,
                        "spellings": ["--new"],
                    }
                }
            ),
            "tool show: --new was added and is required",
            id="new-required-option",
        ),
        pytest.param(
            lambda s: s.update(exit_codes=[0, 1, 2, 3]), "exit codes changed from [0, 1, 2] to [0, 1, 2, 3]", id="code"
        ),
        pytest.param(
            lambda s: s.update(exit_codes=[0, 2]), "exit codes changed from [0, 1, 2] to [0, 2]", id="code-gone"
        ),
    ],
)
def test_a_break_is_found(edit: Any, expected: str) -> None:  # noqa: ANN401
    """Each thing the last release offered is found missing or different, down to the spelling of an option."""
    found = _changed(edit)

    assert any(expected in finding for finding in found), found


def _added_option(surface: dict[str, Any], spellings: list[str], **changes: Any) -> None:  # noqa: ANN401
    option = {**_option(surface, "--name"), "spellings": spellings, **changes}
    surface["commands"]["tool show"]["options"].update(dict.fromkeys(spellings, option))


@pytest.mark.parametrize(
    "edit",
    [
        pytest.param(
            lambda s: s["commands"].update({"tool new": {"options": {"--x": _option(s, "--provider")}}}), id="command"
        ),
        pytest.param(lambda s: _added_option(s, ["--other"]), id="option"),
        pytest.param(
            lambda s: _added_option(s, ["--with-default"], required=False, default="x"), id="option-with-default"
        ),
        pytest.param(
            lambda s: s["commands"]["tool show"]["options"].update(
                {"-p": {**_option(s, "--provider"), "spellings": ["--provider", "-p"]}}
            ),
            id="spelling-of-a-required-option",
        ),
        pytest.param(lambda s: _option(s, "--mode")["choices"].append("c"), id="choice"),
        pytest.param(lambda s: _option(s, "--limit").update(min=0, max=1000), id="wider-range"),
        pytest.param(lambda s: _option(s, "--limit").update(min=None, max=None), id="range-dropped"),
        pytest.param(lambda s: _option(s, "--provider").update(required=False), id="no-longer-required"),
    ],
)
def test_an_addition_is_not_a_break(edit: Any) -> None:  # noqa: ANN401
    """A new command, option, spelling or choice, a wider range and an option no longer required pass."""
    assert _changed(edit) == []


def test_an_approved_break_is_left_out(monkeypatch: pytest.MonkeyPatch) -> None:
    """A finding named in `ACCEPTED_BREAKS` does not fail the check, and any other still does."""
    finding = "tool show: --mode was removed"
    monkeypatch.setitem(ACCEPTED_BREAKS, finding, "a reason that is long enough")

    assert unaccepted([finding, "tool sub was removed"], ACCEPTED_BREAKS) == ["tool sub was removed"]
