# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The `--help` of every command of the command line as committed, and the command that regenerates it (GH-3131).

The options of a command, with their names, choices, defaults and what each one says, are what a script is written
against. `tests/ui/cli/help.snapshot.txt` is the help of the root command and of every command and group below it, as
`wetterdienst COMMAND --help` prints it, and `tests/ui/cli/test_help_snapshot.py` fails when the command line prints
anything else, so a change to an option is a change to this file in the same pull request, where a reviewer sees it as
a diff. Regenerate with

    uv run poe cli:snapshot

and read the diff: a removed or renamed option or command, a choice that is gone, or a changed default breaks the
scripts that use it; an added option or command does not.

The text is click's, so it is written with the version of click that `uv.lock` pins.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import click

from tests.ui.openapi_snapshot import _clean_environment, installed_versions, locked_versions

if TYPE_CHECKING:
    from collections.abc import Iterator

SNAPSHOT = Path(__file__).parent / "help.snapshot.txt"
#: the package whose version shapes the text
SHAPED_BY = ("click",)
#: where the snapshot says which version wrote it. Information only: the first line, not part of the help
GENERATED_WITH = "# generated with click"
#: the width every help is laid out in, as the documentation lays it out
WIDTH = 100


def installed() -> dict[str, str]:
    """Give the version of click as installed."""
    return installed_versions(SHAPED_BY)


def locked() -> dict[str, str]:
    """Give the version of click that `uv.lock` pins, which the snapshot is written with."""
    return locked_versions(SHAPED_BY)


def _helps(
    command: click.Command, path: list[str], parent: click.Context | None = None
) -> Iterator[tuple[list[str], str]]:
    ctx = click.Context(command, info_name=path[-1], parent=parent, max_content_width=WIDTH, terminal_width=WIDTH)
    yield path, command.get_help(ctx)
    if isinstance(command, click.Group):
        for name in command.list_commands(ctx):
            yield from _helps(command.get_command(ctx, name), [*path, name], ctx)


def build_snapshot() -> str:
    """Print the help of every command, as a server that sets no `WD_*` variable would print it."""
    from wetterdienst.ui.cli import cli  # noqa: PLC0415

    with _clean_environment():
        helps = list(_helps(cli, ["wetterdienst"]))
    return "".join(f"$ {' '.join(path)} --help\n\n{text}\n\n\n" for path, text in helps)


def write_snapshot() -> None:
    """Write the help of every command as the snapshot, with the version of click that wrote it."""
    text = f"{GENERATED_WITH} {installed()['click']}\n\n{build_snapshot()}"
    SNAPSHOT.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    write_snapshot()
    print(f"wrote {SNAPSHOT}")  # noqa: T201
