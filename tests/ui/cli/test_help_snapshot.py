# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The `--help` of every command is the committed snapshot, so a change to an option is a diff in the PR (GH-3131).

See `tests/ui/cli/help_snapshot.py` for what the snapshot is and the command that regenerates it.
"""

from __future__ import annotations

import difflib
import re

import click
import pytest

from tests.ui.cli.help_snapshot import SNAPSHOT, build_snapshot, installed, locked
from wetterdienst.ui.cli import cli

_REGENERATE = (
    "The help of the command line is not tests/ui/cli/help.snapshot.txt. If the change is intended, regenerate the "
    "snapshot with `uv run poe cli:snapshot` and review the diff: a removed or renamed option or command, a choice "
    "that is gone or a changed default breaks the scripts that use it; an added option or command does not."
)


def _snapshot() -> str:
    """Give the snapshot without the line that says which version of click wrote it."""
    return SNAPSHOT.read_text(encoding="utf-8").split("\n\n", 1)[1]


def test_the_help_of_every_command_is_the_committed_snapshot() -> None:
    """A change to the options, the choices, the defaults or the examples of a command is a change to the snapshot."""
    # click lays its help out differently between versions: it is held to the snapshot where it is the locked one
    if installed() != locked():
        pytest.skip(f"the snapshot is written with click {locked()}, and {installed()} is installed")

    served = build_snapshot()
    committed = _snapshot()

    diff = list(
        difflib.unified_diff(committed.splitlines(), served.splitlines(), "snapshot", "served", n=1, lineterm="")
    )
    assert not diff, f"{_REGENERATE}\n" + "\n".join(diff[:60])


def _paths(command: click.Command, path: tuple[str, ...] = ("wetterdienst",)) -> list[tuple[str, ...]]:
    found = [path]
    if isinstance(command, click.Group):
        for name, sub in command.commands.items():
            found += _paths(sub, (*path, name))
    return found


def test_the_snapshot_has_the_help_of_every_command_and_group() -> None:
    """Whatever the version of click, no command is missing from the snapshot, and none is in it that is gone."""
    in_snapshot = re.findall(r"^\$ (.+) --help$", _snapshot(), flags=re.MULTILINE)

    assert sorted(in_snapshot) == sorted(" ".join(path) for path in _paths(cli))


def test_the_snapshot_names_every_option_of_every_command() -> None:
    """Whatever the version of click, each option a command has is in the help of that command in the snapshot."""
    sections = dict(re.findall(r"^\$ (.+?) --help\n\n(.*?)(?=^\$ |\Z)", _snapshot(), flags=re.MULTILINE | re.DOTALL))

    def walk(command: click.Command, path: tuple[str, ...]) -> None:
        text = sections[" ".join(path)]
        for parameter in command.params:
            if getattr(parameter, "hidden", False):
                continue
            for option in (*parameter.opts, *parameter.secondary_opts):
                assert option in text, f"{' '.join(path)} {option}"
        if isinstance(command, click.Group):
            for name, sub in command.commands.items():
                walk(sub, (*path, name))

    walk(cli, ("wetterdienst",))
