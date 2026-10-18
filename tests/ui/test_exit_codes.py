# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The exit codes of the command line are 0, 1 and 2, and nothing else (GH-2561).

A script, a scheduler and a CI job branch on the exit code, so it is part of the contract and is frozen:

- **0**: an answer, empty or not, and `--help` and `--version`.
- **1**: a failure that is not the command line's to rephrase: a provider that failed or could not be reached, a
  credential or a package the machine lacks, a malformed `WD_*` setting, a target that cannot be written, and a
  defect. Whatever the REST API answers with a 5xx.
- **2**: a request that cannot be served as phrased, as click reports a usage error: no command, an unknown or
  missing option, a value out of range, a selection that is not exactly one, a provider or network that does not
  exist, a station that does not exist. Whatever the REST API answers with a 400, 404 or 422.

The reader of each command is made to raise each exception of the table of `test_api_contract.STATUS_TABLE`, so the
exit code is held to the status the REST API answers the same failure with. The stubs of the DWD network are those of
`test_surface_parity`.
"""

from __future__ import annotations

import ast
import logging
from pathlib import Path
from typing import TYPE_CHECKING

import click
import pytest
from click.testing import CliRunner

from tests.ui.test_api_contract import STATUS_TABLE
from tests.ui.test_surface_parity import PARAMETER, _no_ambient_settings, _serve_dwd  # noqa: F401
from wetterdienst.ui import cli as cli_module
from wetterdienst.ui.cli import cli

if TYPE_CHECKING:
    from collections.abc import Iterator

    from click.testing import Result

_SELECTION = {
    "values": ["--stations=00001", "--timestamp=2020-05"],
    "stations": ["--all"],
    "history": ["--stations=00001"],
    "interpolate": ["--station=00001", "--timestamp=2020-05-01"],
    "summarize": ["--station=00001", "--timestamp=2020-05-01"],
}
#: the function of `wetterdienst.ui.cli` that reads from the provider, for each command
_READERS = {
    "values": "get_values",
    "stations": "get_stations",
    "history": "get_stations",
    "interpolate": "get_interpolate",
    "summarize": "get_summarize",
}


def _run(*args: str, env: dict[str, str] | None = None) -> Result:
    return CliRunner().invoke(cli, list(args), env=env)


def _commands(command: click.Command, path: tuple[str, ...] = ()) -> Iterator[tuple[str, ...]]:
    """Walk every command of the tree, the groups included."""
    yield path
    if isinstance(command, click.Group):
        for name, sub in command.commands.items():
            yield from _commands(sub, (*path, name))


# --- 0 -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("path", [pytest.param(path, id=" ".join(path) or "wetterdienst") for path in _commands(cli)])
def test_help_of_every_command_is_exit_0(path: tuple[str, ...]) -> None:
    """`--help` is an answer, for the command and for every group and command under it."""
    assert _run(*path, "--help").exit_code == 0


@pytest.mark.parametrize("args", [("--version",), ("-v",), ("cache",), ("info",), ("about", "glossary", "--limit=1")])
def test_a_command_that_answers_is_exit_0(args: tuple[str, ...]) -> None:
    """A command that has what it is asked for exits 0."""
    result = _run(*args)

    assert result.exit_code == 0, result.output


@pytest.mark.parametrize(
    "args",
    [
        pytest.param(("values", "--stations=00001", "--timestamp=1930-06-01"), id="values-window"),
        pytest.param(("stations", "--name=Nowhereville"), id="stations-name"),
        pytest.param(("values", "--stations=99999", "--timestamp=2020-05"), id="values-unknown-station"),
    ],
)
def test_an_empty_answer_is_exit_0(args: tuple[str, ...], caplog: pytest.LogCaptureFixture) -> None:
    """A window without readings, a name nothing is called and an unknown id are answers, as REST's 200 is."""
    with caplog.at_level(logging.WARNING):
        result = _run(*args, "--provider=dwd", "--network=observation", f"--parameters={PARAMETER}")

    assert result.exit_code == 0, result.output


# --- 1 and 2: a failure is the exit code of its status -------------------------------------------


def _expected(status: int) -> int:
    """Give the exit code a failure has, from the status the REST API answers it with."""
    return 2 if status in (400, 404, 422) else 1


@pytest.mark.parametrize("command", list(_READERS))
@pytest.mark.parametrize(
    ("error", "status"), [pytest.param(case.values[0], case.values[1], id=case.id) for case in STATUS_TABLE]
)
def test_a_failure_exits_with_the_code_of_its_status(
    monkeypatch: pytest.MonkeyPatch, command: str, error: BaseException, status: int
) -> None:
    """The 4xx of the REST API is exit 2, the 5xx exit 1: a provider that failed and a defect alike."""

    def raises(**_kwargs: object) -> None:
        raise error

    monkeypatch.setattr(cli_module, _READERS[command], raises)

    result = _run(command, "--provider=dwd", "--network=observation", f"--parameters={PARAMETER}", *_SELECTION[command])

    assert result.exit_code == _expected(status), (result.exit_code, repr(result.exception), result.output)


def test_ctrl_c_is_exit_1(monkeypatch: pytest.MonkeyPatch) -> None:
    """An interrupted run is click's `Abort`: `Aborted!` and exit 1, not a code of its own."""

    def interrupted(**_kwargs: object) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(cli_module, "get_values", interrupted)

    result = _run("values", "--provider=dwd", "--network=observation", f"--parameters={PARAMETER}", "--stations=00001")

    assert result.exit_code == 1
    assert "Aborted!" in result.output


# --- 2: a request that cannot be served as phrased -----------------------------------------------


@pytest.mark.parametrize(
    "args",
    [
        pytest.param((), id="no-command"),
        pytest.param(("about",), id="no-subcommand"),
        pytest.param(("stripes",), id="no-stripes-command"),
        pytest.param(("nope",), id="unknown-command"),
        pytest.param(("stations", "--nope"), id="unknown-option"),
        pytest.param(("stations", "--all"), id="missing-option"),
        pytest.param(("values", "--provider=dwd"), id="missing-options"),
        pytest.param(
            ("stations", "--provider=dwd", "--network=observation", "--parameters=daily/kl"), id="no-selection"
        ),
        pytest.param(
            ("stations", "--provider=dwd", "--network=observation", "--parameters=daily/kl", "--all", "--name=x"),
            id="two-selections",
        ),
        pytest.param(
            ("stations", "--provider=dwd", "--network=observation", "--parameters=daily/kl", "--distance=-1"),
            id="out-of-range",
        ),
        pytest.param(
            ("stations", "--provider=dwd", "--network=observation", "--parameters=daily/kl", "--format=nope", "--all"),
            id="bad-choice",
        ),
        pytest.param(("stations", "--provider=nope", "--network=nope", "--parameters=x", "--all"), id="no-provider"),
        pytest.param(("stations", "--station=00001", "--provider=dwd"), id="renamed-option"),
    ],
)
def test_a_request_that_cannot_be_served_as_phrased_is_exit_2(args: tuple[str, ...]) -> None:
    """Click's usage errors and the refusals told as one: no traceback, the usage or one line, exit 2."""
    result = _run(*args)

    assert result.exit_code == 2, (result.exit_code, repr(result.exception), result.output)
    # told, not raised: click ends the run with the code, and no traceback is printed
    assert isinstance(result.exception, SystemExit)


# --- 1: the machine's, not the command line's ----------------------------------------------------


def test_a_malformed_setting_is_exit_1() -> None:
    """A `WD_*` variable that does not parse is the environment's to fix: one line naming it, exit 1."""
    result = _run(
        "stations",
        "--provider=dwd",
        "--network=observation",
        "--parameters=daily/kl",
        "--all",
        env={"WD_RESTAPI_TIMEOUT": "later", "WD_TS_HUMANIZE": "perhaps"},
    )

    assert result.exit_code == 1, result.output
    assert "WD_" in result.output


def test_a_target_that_cannot_be_written_is_exit_1(tmp_path: Path) -> None:
    """The request was right, the sink is not: exit 1 with a line naming the target."""
    result = _run(
        "values",
        "--provider=dwd",
        "--network=observation",
        f"--parameters={PARAMETER}",
        "--stations=00001",
        "--timestamp=2020-05",
        f"--target=file://{tmp_path / 'missing' / 'values.nope'}",
    )

    assert result.exit_code == 1, result.output


# --- nothing else --------------------------------------------------------------------------------


def _cli_source() -> ast.Module:
    return ast.parse(Path(cli_module.__file__).read_text(encoding="utf-8"))


def test_the_command_line_exits_with_no_code_but_0_1_and_2() -> None:
    """Every explicit exit of the command line is 1, and every click error it raises has the code 1 or 2.

    The codes of the rest are click's: 0 for success, 2 for a usage error, 1 for a `ClickException`, an `Abort`
    (Ctrl-C) and an exception nothing caught.
    """
    explicit = []
    raised = set()
    for node in ast.walk(_cli_source()):
        if isinstance(node, ast.Call) and ast.unparse(node.func) in {
            "sys.exit",
            "exit",
            "ctx.exit",
            "click.Context.exit",
        }:
            explicit.append(ast.unparse(node.args[0]) if node.args else "0")
        if isinstance(node, ast.Raise) and node.exc is not None:
            call = node.exc.func if isinstance(node.exc, ast.Call) else node.exc
            if ast.unparse(call).startswith("click."):
                raised.add(getattr(click, ast.unparse(call).removeprefix("click.")))

    assert explicit
    assert set(explicit) <= {"0", "1"}, explicit
    assert raised
    assert {error.exit_code for error in raised} <= {1, 2}, raised
    assert click.ClickException.exit_code == 1
    assert click.UsageError.exit_code == click.BadParameter.exit_code == click.NoSuchOption.exit_code == 2
