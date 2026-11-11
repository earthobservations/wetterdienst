# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the command line's shell completion, its `--quiet` and its colour (GH-3134)."""

from __future__ import annotations

import io
import logging
import os
import subprocess
import sys
import textwrap
import time
from typing import TYPE_CHECKING, Any

import click
import pytest
from click.testing import CliRunner

from tests.conftest import is_no_such_option
from wetterdienst import Wetterdienst
from wetterdienst.exceptions import NoInternetError
from wetterdienst.ui import cli as cli_module
from wetterdienst.ui.cli import cli
from wetterdienst.util.cli import no_color
from wetterdienst.util.response_warnings import (
    FILE_SKIPPED,
    RESPONSE_WARNING_RECORD,
    warn_response,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path

#: what the command line does with the three, in a process of its own: the entry point as `pyproject.toml` has it,
#: with every connection refused, so that a completion (or a command) that reached for the network fails loudly
_PROCESS = textwrap.dedent(
    """
    import socket
    import sys

    def refuse(*_args, **_kwargs):
        raise OSError("the network is not for this test")

    socket.socket.connect = refuse
    socket.socket.connect_ex = refuse
    socket.getaddrinfo = refuse

    from wetterdienst.ui.cli import cli

    cli(prog_name="wetterdienst")
    """,
)
#: dumps the providers that were imported when the process ends (a completion ends it with `sys.exit`)
_DUMP_PROVIDERS = textwrap.dedent(
    """
    import atexit
    import os
    import sys

    atexit.register(
        lambda: open(os.environ["PROVIDERS_FILE"], "w").write(
            "\\n".join(sorted(m for m in sys.modules if m.startswith("wetterdienst.provider.")))
        )
    )
    """,
)
#: how a terminal that wants colour asks for it, which nothing the command line writes may answer
_FORCE_COLOR = {"FORCE_COLOR": "1", "CLICOLOR_FORCE": "1", "TERM": "xterm-256color"}
_ESC = "\x1b"
_WARNING = "No parameter matches the given filters."
_NOTHING = ["glossary", "--parameter", "zzzz-matches-nothing"]


def _environment(**extra: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in {"NO_COLOR", "FORCE_COLOR", "CLICOLOR_FORCE"}}
    env.pop("_WETTERDIENST_COMPLETE", None)
    return {**env, **extra}


def _run(args: list[str], *, source: str = _PROCESS, **env: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", source, *args],
        env=_environment(**env),
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )


def _complete(line: str, *, source: str = _PROCESS, **env: str) -> subprocess.CompletedProcess[str]:
    """Ask the process what bash would be offered after `line`, as the script `bash_source` prints does."""
    return _run(
        [],
        source=source,
        _WETTERDIENST_COMPLETE="bash_complete",
        COMP_WORDS=line,
        COMP_CWORD=str(len(line.split(" ")) - 1),
        **env,
    )


def _offered(line: str) -> list[str]:
    done = _complete(line)
    assert done.returncode == 0, done.stderr
    # nothing but the offers on stdout, and nothing on stderr: a line printed at import would be completed as a word
    assert done.stderr == ""
    # no offer is an empty line, which the script of the shell reads as none
    lines = [line for line in done.stdout.splitlines() if line]
    assert all(line.startswith("plain,") for line in lines), done.stdout
    return [line.removeprefix("plain,") for line in lines]


# --- completion ---------------------------------------------------------------------------------------------------


def test_a_real_completion_offers_the_commands_and_the_options_and_is_quick() -> None:
    """A TAB is a process that imports the command line, answers and ends: with no network, in seconds (GH-3134).

    Measured on a laptop it was 0.6 to 1.0 s, nearly all of it the import of `wetterdienst.ui.cli`, and is 0.07 s
    since GH-3809 (`tests/ui/cli/test_cli_imports.py` holds what is imported); the bound is generous so that a loaded
    runner does not fail it, and a completion that fetched anything would not meet it.
    """
    started = time.perf_counter()
    commands = _offered("wetterdienst va")
    options = _offered("wetterdienst values --qu")
    elapsed = (time.perf_counter() - started) / 2

    assert commands == ["values"]
    assert options == ["--quiet"]
    assert elapsed < 30, elapsed


def test_a_provider_is_completed_from_the_registry() -> None:
    """`--provider` offers the keys of the registry, as typed so far, on every command that takes it."""
    assert _offered("wetterdienst values --provider d") == ["dmi", "dwd"]
    assert _offered("wetterdienst coverage --provider eau") == ["eaufrance"]
    assert _offered("wetterdienst providers --provider zz") == []
    assert sorted(_offered("wetterdienst stations --provider ")) == sorted(Wetterdienst.get_provider_names())


def test_a_network_is_completed_from_the_provider_on_the_line() -> None:
    """`--network` offers the networks of the `--provider` given before it, and else every network."""
    assert _offered("wetterdienst values --provider dwd --network ") == Wetterdienst.get_network_names("dwd")
    assert _offered("wetterdienst values --network mosmix --provider dwd --network m") == ["mosmix"]
    assert _offered("wetterdienst values --provider noaa --network ") == ["ghcn"]
    everything = {network for networks in Wetterdienst.registry.values() for network in networks}
    assert set(_offered("wetterdienst coverage --network ")) == everything
    # a provider that does not exist offers no network of its own: the whole list, as without one
    assert set(_offered("wetterdienst values --provider nowhere --network ")) == everything
    # bash hands `--provider=dwd` over as `--provider`, `=` and `dwd`: the provider is the one after the `=`
    assert _offered("wetterdienst values --provider = noaa --network ") == ["ghcn"]
    assert _offered("wetterdienst values --provider = dwd --network m") == ["mosmix"]


def test_a_completion_imports_no_provider_beyond_the_command_line(tmp_path: Path) -> None:
    """Completing `--provider` and `--network` imports no provider the command line did not import already."""
    dump = _DUMP_PROVIDERS + _PROCESS
    baseline = tmp_path / "baseline.txt"
    completed = tmp_path / "completed.txt"
    # the same process without a completion: `--version` ends it as the entry point does
    version = _run(["--version"], source=dump, PROVIDERS_FILE=str(baseline))
    assert version.returncode == 0, version.stderr
    done = _complete("wetterdienst values --provider dwd --network ", source=dump, PROVIDERS_FILE=str(completed))
    assert done.returncode == 0, done.stderr

    assert completed.read_text() == baseline.read_text()
    assert "wetterdienst.provider.noaa.ghcn" not in completed.read_text()


@pytest.mark.parametrize("shell", ["bash", "zsh", "fish"])
def test_the_completion_script_is_printed_for_each_shell(shell: str) -> None:
    """`_WETTERDIENST_COMPLETE=<shell>_source wetterdienst` prints a script that calls back with that variable."""
    done = _run([], _WETTERDIENST_COMPLETE=f"{shell}_source")

    assert done.returncode == 0, done.stderr
    # click's own note where bash is older than 4.4 (macOS has 3.2 in /bin/bash) or cannot be found, not ours
    assert all("Bash" in line for line in done.stderr.splitlines()), done.stderr
    assert f"{shell}_complete" in done.stdout
    assert "_WETTERDIENST_COMPLETE" in done.stdout
    assert "wetterdienst" in done.stdout
    assert _ESC not in done.stdout


# --- --quiet ------------------------------------------------------------------------------------------------------


@pytest.fixture
def levels() -> Iterator[None]:
    """Give the levels of the two loggers `--quiet` sets back as they were after the test."""
    loggers = [logging.getLogger(), logging.getLogger("wetterdienst")]
    before = [logger.level for logger in loggers]
    yield
    for logger, level in zip(loggers, before, strict=True):
        logger.setLevel(level)


@pytest.mark.usefixtures("levels")
def test_quiet_keeps_the_data_and_the_exit_code_and_drops_a_warning_that_is_no_response_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The warning of an empty answer is written without `--quiet` and not with it; stdout and the code are the same.

    It is the command's own sentence, not a warning the answer carries: the empty answer is stdout.
    """
    runner = CliRunner()
    with caplog.at_level(logging.INFO):
        loud = runner.invoke(cli, _NOTHING)
        assert _WARNING in caplog.text
        caplog.clear()
        quiet = runner.invoke(cli, [*_NOTHING, "--quiet"])
        assert caplog.text == ""

    assert (loud.exit_code, quiet.exit_code) == (0, 0)
    assert quiet.stdout == loud.stdout == "[]\n"


@pytest.mark.usefixtures("levels")
def test_quiet_gives_the_level_back_when_the_command_ends(caplog: pytest.LogCaptureFixture) -> None:
    """A level `--quiet` set is for the length of the command: the next one in the same process logs as it did."""
    runner = CliRunner()
    with caplog.at_level(logging.INFO):
        before = (logging.getLogger().level, logging.getLogger("wetterdienst").level)
        runner.invoke(cli, [*_NOTHING, "--quiet"])
        assert (logging.getLogger().level, logging.getLogger("wetterdienst").level) == before
        runner.invoke(cli, _NOTHING)
        assert _WARNING in caplog.text


@pytest.mark.usefixtures("levels")
def test_quiet_keeps_the_errors_and_the_warnings_about_the_answer_and_drops_the_rest(
    caplog: pytest.LogCaptureFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Below ERROR only the warnings about the answer are written, not progress, other warnings or a library's."""
    skipped = "2 files were skipped: the answer lacks them"

    def failing(**_kwargs: Any) -> None:  # noqa: ANN401
        # the progress bars log at INFO through `TqdmToLogger`, the retries of a download at WARNING
        logging.getLogger("wetterdienst.model.values").info("progress 1/3")
        logging.getLogger("wetterdienst.model.values").warning("a retry")
        logging.getLogger("fsspec").warning("from a library")
        logging.getLogger().warning("from the root")
        # what the answer carries in `metadata.warnings` as well, and the log line of it
        warn_response(logging.getLogger("wetterdienst.model.values"), FILE_SKIPPED, skipped)
        raise NoInternetError("no connection could be made to https://opendata.example.org")  # noqa: EM101, TRY003

    monkeypatch.setattr(cli_module, "get_glossary", failing)
    runner = CliRunner()
    with caplog.at_level(logging.DEBUG):
        loud = runner.invoke(cli, _NOTHING)
        assert {"progress 1/3", "a retry", "from a library", "from the root", skipped} <= set(caplog.messages)
        caplog.clear()
        quiet = runner.invoke(cli, [*_NOTHING, "--quiet"])

    assert caplog.messages == [
        skipped,
        "no connection could be made to https://opendata.example.org",
    ]
    assert [record.levelno for record in caplog.records] == [logging.WARNING, logging.ERROR]
    assert (loud.exit_code, quiet.exit_code) == (1, 1)


@pytest.mark.usefixtures("levels")
def test_quiet_filters_the_handlers_for_the_length_of_the_command_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """The handler that writes to stderr gets the filter while the command runs and is given back as it was."""
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    root = logging.getLogger()
    root.addHandler(handler)
    root.setLevel(logging.INFO)
    log = logging.getLogger("wetterdienst.model.values")

    def noisy(**_kwargs: Any) -> list[Any]:  # noqa: ANN401
        log.info("progress")
        log.warning("a retry")
        warn_response(log, FILE_SKIPPED, "a file was skipped")
        return []

    monkeypatch.setattr(cli_module, "get_glossary", noisy)
    try:
        CliRunner().invoke(cli, [*_NOTHING, "--quiet"])
        assert stream.getvalue().splitlines() == ["a file was skipped"]
        assert handler.filters == []
        stream.truncate(0)
        stream.seek(0)
        CliRunner().invoke(cli, _NOTHING)
        assert {"progress", "a retry", "a file was skipped"} <= set(stream.getvalue().splitlines())
    finally:
        root.removeHandler(handler)


def test_a_response_warning_is_marked_in_its_log_record(caplog: pytest.LogCaptureFixture) -> None:
    """`--quiet` tells the warnings of the answer by the attribute `warn_response` sets, holding the code."""
    log = logging.getLogger("wetterdienst.test_quiet")
    with caplog.at_level(logging.INFO):
        warn_response(log, FILE_SKIPPED, "a file was skipped")
        log.warning("an ordinary warning")

    marked, ordinary = caplog.records
    assert getattr(marked, RESPONSE_WARNING_RECORD) == FILE_SKIPPED
    assert not hasattr(ordinary, RESPONSE_WARNING_RECORD)


def test_quiet_leaves_a_usage_error_to_click() -> None:
    """A request that cannot be served is still said, and is still exit 2."""
    result = CliRunner().invoke(cli, ["glossary", "--unit-type", "nonsense", "--quiet"])

    assert result.exit_code == 2
    assert "Invalid value for '--unit-type'" in result.stderr


@pytest.mark.parametrize("flags", [["--quiet", "--debug"], ["--debug", "--quiet"], ["--quiet=true", "--debug=true"]])
@pytest.mark.usefixtures("levels")
def test_quiet_and_debug_together_are_a_usage_error(flags: list[str]) -> None:
    """One logs less than the default and the other more: neither is guessed, whichever comes first."""
    result = CliRunner().invoke(cli, [*_NOTHING, *flags])

    assert result.exit_code == 2
    assert "--quiet and --debug cannot be used together" in result.stderr
    assert result.stdout == ""


@pytest.mark.parametrize("flags", [["--quiet=false", "--debug"], ["--quiet", "--debug=false"], ["--debug=false"]])
@pytest.mark.usefixtures("levels")
def test_quiet_and_debug_given_false_are_no_conflict(flags: list[str]) -> None:
    """A boolean option takes `=false` on every command, so `--quiet=false --debug` is `--debug`."""
    result = CliRunner().invoke(cli, [*_NOTHING, *flags])

    assert result.exit_code == 0, result.stderr


def _commands(command: click.Command, path: tuple[str, ...] = ()) -> Iterator[tuple[tuple[str, ...], click.Command]]:
    yield path, command
    if isinstance(command, click.Group):
        for name, sub in command.commands.items():
            yield from _commands(sub, (*path, name))


def test_every_command_with_debug_has_quiet_but_the_server() -> None:
    """`--quiet` is beside `--debug` on every command that logs; `restapi` has `--debug` alone, and says why."""
    for path, command in _commands(cli):
        names = {opt for param in command.params for opt in getattr(param, "opts", [])}
        if "--debug" not in names:
            continue
        assert ("--quiet" in names) == (path != ("restapi",)), path


def test_quiet_does_not_reach_the_server() -> None:
    """The server's log is uvicorn's, which `--quiet` would leave as it is: the option is refused there."""
    result = CliRunner().invoke(cli, ["restapi", "--quiet"])

    assert result.exit_code == 2
    assert is_no_such_option(result.stderr, "--quiet")


def test_a_real_quiet_command_writes_nothing_to_stderr_and_the_data_to_stdout() -> None:
    """In a process of its own, as a scheduler runs it: stderr is empty with `--quiet` and is not without."""
    loud = _run(_NOTHING)
    quiet = _run([*_NOTHING, "--quiet"])

    assert (loud.returncode, quiet.returncode) == (0, 0)
    assert _WARNING in loud.stderr
    assert quiet.stderr == ""
    assert quiet.stdout == loud.stdout == "[]\n"


# --- NO_COLOR -----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, False), ("", False), ("1", True), ("0", True), ("false", True), ("anything", True), (" ", True)],
)
def test_no_color_is_any_value_but_an_empty_one(
    value: str | None,
    expected: bool,  # noqa: FBT001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """https://no-color.org: set and not empty, whatever it says."""
    if value is None:
        monkeypatch.delenv("NO_COLOR", raising=False)
    else:
        monkeypatch.setenv("NO_COLOR", value)

    assert no_color() is expected


def test_no_command_writes_an_escape_code_even_where_colour_is_forced() -> None:
    """The command line styles nothing: not its help, a usage error, a warning, an error or its data (GH-3134).

    `FORCE_COLOR` and `CLICOLOR_FORCE` are how a terminal asks for colour and Python itself would give a traceback
    one; none of what is written below has an escape code, in a pipe or where colour is forced.
    """
    runs = [
        ["--help"],
        ["values", "--help"],
        _NOTHING,
        ["glossary", "--unit-type", "nonsense"],
        ["values", "--unknown-option"],
        ["values", "--provider", "nowhere", "--network", "observation", "--parameters", "daily/kl", "--all"],
    ]
    for args in runs:
        done = _run(args, **_FORCE_COLOR)
        assert _ESC not in done.stdout + done.stderr, (args, done.stdout, done.stderr)


def test_the_help_and_the_errors_of_every_command_carry_no_colour() -> None:
    """With colour forced on (`CliRunner(color=True)` keeps what click styles), every `--help` and error is plain."""
    runner = CliRunner()
    for path, _command in _commands(cli):
        result = runner.invoke(cli, [*path, "--help"], color=True)
        assert result.exit_code == 0, path
        assert _ESC not in result.output, path
    bad = runner.invoke(cli, ["values", "--unknown-option"], color=True)
    assert bad.exit_code == 2
    assert _ESC not in bad.output


@pytest.fixture
def deprecated_command() -> Iterator[None]:
    """Add a command that click announces in red, which no command of the line is yet: a rename after 1.0 may be."""

    @click.command("old", deprecated=True)
    def old() -> None:
        click.echo("data")

    cli.add_command(old)
    yield
    del cli.commands["old"]  # ty: ignore[unresolved-attribute]


@pytest.mark.usefixtures("deprecated_command")
def test_what_click_styles_is_plain_with_no_color(monkeypatch: pytest.MonkeyPatch) -> None:
    """Click writes the deprecation of a command in red; `NO_COLOR` strips it, and an empty `NO_COLOR` does not."""
    runner = CliRunner()

    monkeypatch.delenv("NO_COLOR", raising=False)
    plain = runner.invoke(cli, ["old"], color=True)
    assert f"{_ESC}[31m" in plain.stderr  # the test can see colour, so the next two are not blind

    monkeypatch.setenv("NO_COLOR", "")
    assert f"{_ESC}[31m" in runner.invoke(cli, ["old"], color=True).stderr

    monkeypatch.setenv("NO_COLOR", "1")
    stripped = runner.invoke(cli, ["old"], color=True)
    assert _ESC not in stripped.stderr + stripped.stdout
    assert "DeprecationWarning: The command 'old' is deprecated." in stripped.stderr
    assert stripped.stdout == "data\n"
    assert stripped.exit_code == 0


# the server is uvicorn's: it colours the level of its log lines on a terminal and does not read NO_COLOR itself
@pytest.mark.parametrize(("value", "use_colors"), [(None, None), ("", None), ("1", False), ("0", False)])
def test_the_server_is_told_not_to_colour_with_no_color(
    value: str | None,
    use_colors: bool | None,  # noqa: FBT001
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`wetterdienst restapi` hands uvicorn `use_colors=False` under `NO_COLOR`, else its own terminal check."""
    from wetterdienst.ui import restapi  # noqa: PLC0415

    seen: dict[str, Any] = {}
    uvicorn = type("Uvicorn", (), {"run": staticmethod(lambda **kwargs: seen.update(kwargs))})
    monkeypatch.setattr(restapi, "import_optional", lambda *_args, **_kwargs: uvicorn)
    monkeypatch.setattr(restapi, "setup_logging", lambda: None)
    monkeypatch.setenv("WD_RESTAPI_ALLOWED_HOSTS", "")  # restored afterwards: start_service sets the variable
    if value is None:
        monkeypatch.delenv("NO_COLOR", raising=False)
    else:
        monkeypatch.setenv("NO_COLOR", value)

    restapi.start_service("0.0.0.0:7890")

    assert seen["use_colors"] is use_colors


# --- an image under --quiet ---------------------------------------------------------------------------------------

#: a command of its own that draws a figure as `render_image` does, as `stripes image` and a PNG of `values` do
_DRAW = textwrap.dedent(
    """
    import plotly.graph_objects as go

    from wetterdienst.io.export import render_image
    from wetterdienst.ui.cli import _apply_log_level, cli, debug_opt


    @cli.command("draw")
    @debug_opt
    def draw(debug: bool) -> None:
        _apply_log_level(debug=debug)
        print(len(render_image(go.Figure(go.Scatter(x=[1, 2], y=[1, 2])), "png")))


    cli(prog_name="wetterdienst")
    """,
)


def test_quiet_leaves_no_line_of_the_image_libraries_when_the_interpreter_ends() -> None:
    """Kaleido and its browser write what they cleaned up as the process ends, after the command: not under --quiet."""
    pytest.importorskip("kaleido")
    pytest.importorskip("plotly")
    quiet = _run(["draw", "--quiet"], source=_DRAW)
    if quiet.returncode != 0 and "Chrome" in quiet.stderr:
        pytest.skip("no browser for Kaleido")

    assert quiet.returncode == 0, quiet.stderr
    assert quiet.stdout.strip().isdigit(), quiet.stdout
    assert quiet.stderr == ""
