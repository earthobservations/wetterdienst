# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What the command line imports for `--help`, `--version` and a completion, and that a command imports its own.

(GH-3809)

A TAB press starts a process that imports `wetterdienst.ui.cli`, answers and ends. That import was 0.5 s of polars,
pydantic, sympy and every provider the command line could ever ask for; `--help` and `--version` paid it as well. The
tests here compare the modules a clean process has imported, not the time it took: a new import at the top of
`ui/cli.py` (or of anything it imports) that brings a heavy package back fails them by name, on a runner of any speed.

The second half runs the commands in a clean process too: a command now imports what it uses when it runs, in the
order its own code gives, and only a process with nothing imported yet shows an import that fails or loops in that
order. The test session has imported everything, in the order of whichever test came first.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import textwrap
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from pathlib import Path

#: the top-level packages that cost the import: none of them is needed to print a help, a version or a completion
HEAVY = (
    "aiohttp",
    "fsspec",
    "kaleido",
    "lxml",
    "measurement",
    "numpy",
    "pandas",
    "plotly",
    "polars",
    "pyarrow",
    "pydantic",
    "pydantic_core",
    "pydantic_settings",
    "rapidfuzz",
    "scipy",
    "shapely",
    "sympy",
)
#: the modules of the package that hold what those need, which the command line imports in the command that uses them
HEAVY_OWN = (
    "wetterdienst.io.export",
    "wetterdienst.io.sinks",
    "wetterdienst.model.limits",
    "wetterdienst.model.metadata",
    "wetterdienst.model.plausibility",
    "wetterdienst.model.request",
    "wetterdienst.options",
    "wetterdienst.settings",
    "wetterdienst.ui.core",
    "wetterdienst.ui.mcp",
    "wetterdienst.ui.providers",
    "wetterdienst.ui.render",
    "wetterdienst.ui.response_metadata",
    "wetterdienst.ui.restapi",
)
#: every module of the package that importing `wetterdienst.ui.cli` imports, and so every one that `--help`, `--version`
#: and a completion may import. A module added to the top of `ui/cli.py` is added here, if it is as light as these
#: (no third-party package of `HEAVY`, nothing that reads a file or a setting at import); else it is imported by the
#: command that uses it
ALLOWED = frozenset(
    {
        "wetterdienst",
        "wetterdienst.api",
        "wetterdienst.boot",
        "wetterdienst.exceptions",
        "wetterdienst.io",
        "wetterdienst.io.formats",
        "wetterdienst.metadata",
        "wetterdienst.metadata.period",
        "wetterdienst.metadata.resolution",
        "wetterdienst.metadata.unit_type",
        "wetterdienst.model",
        "wetterdienst.model.plausibility_modes",
        "wetterdienst.ui",
        "wetterdienst.ui.cli",
        "wetterdienst.util",
        "wetterdienst.util.cli",
        "wetterdienst.util.extras",
        "wetterdienst.util.response_warnings",
        "wetterdienst.util.ui",
        "wetterdienst.util.url",
    },
)

#: a process that does what `wetterdienst` does, with every connection refused, and tells which modules it imported
_PROCESS = textwrap.dedent(
    """
    import json
    import os
    import socket
    import sys

    def refuse(*_args, **_kwargs):
        raise OSError("the network is not for this test")

    socket.socket.connect = refuse
    socket.socket.connect_ex = refuse
    socket.getaddrinfo = refuse

    code = 0
    try:
        exec(os.environ["BODY"])
    except SystemExit as e:
        code = e.code if isinstance(e.code, int) else 1
    with open(os.environ["MODULES_FILE"], "w") as f:
        json.dump(sorted(sys.modules), f)
    sys.exit(code)
    """,
)
_RUN_CLI = "from wetterdienst.ui.cli import cli; cli(prog_name='wetterdienst')"


def _run(body: str, *args: str, tmp_path: Path, **env: str) -> tuple[subprocess.CompletedProcess[str], set[str]]:
    """Run `body` in a clean interpreter, with `args` as its command line, and give the modules it imported."""
    modules_file = tmp_path / "modules.json"
    environment = {k: v for k, v in os.environ.items() if k not in {"_WETTERDIENST_COMPLETE", "NO_COLOR"}}
    done = subprocess.run(  # noqa: S603
        [sys.executable, "-c", _PROCESS, *args],
        env={**environment, "BODY": body, "MODULES_FILE": str(modules_file), **env},
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    return done, set(json.loads(modules_file.read_text())) if modules_file.exists() else set()


def _complete(line: str) -> dict[str, str]:
    """Give the environment that asks the command line what bash would be offered after `line`."""
    return {
        "_WETTERDIENST_COMPLETE": "bash_complete",
        "COMP_WORDS": line,
        "COMP_CWORD": str(len(line.split(" ")) - 1),
    }


def _imported(modules: set[str], names: tuple[str, ...]) -> list[str]:
    """Give which of the packages and modules are imported: the name itself, or anything below it."""
    return sorted({name for name in names for module in modules if module == name or module.startswith(f"{name}.")})


# --- what is imported where nothing is run --------------------------------------------------------------------------


def test_importing_the_package_imports_neither_polars_nor_the_settings(tmp_path: Path) -> None:
    """`import wetterdienst` reads the registry and the enums, which are names, not the models and their libraries."""
    done, modules = _run("import wetterdienst", tmp_path=tmp_path)

    assert done.returncode == 0, done.stderr
    assert _imported(modules, HEAVY) == []
    assert _imported(modules, HEAVY_OWN) == []
    assert not [module for module in modules if module.startswith("wetterdienst.provider")]


def test_the_lazy_names_of_the_package_are_found_when_asked_for(tmp_path: Path) -> None:
    """`Settings` and `Options` are imported by the first use, whether read as an attribute or imported by name."""
    body = textwrap.dedent(
        """
        import wetterdienst
        before = "wetterdienst.settings" in sys.modules or "wetterdienst.options" in sys.modules
        from wetterdienst import Options
        import wetterdienst.settings
        assert wetterdienst.Settings is wetterdienst.settings.Settings
        assert Options is wetterdienst.options.Options
        assert {"Settings", "Options"} <= set(dir(wetterdienst))
        assert not before
        try:
            wetterdienst.Nothing
        except AttributeError as e:
            assert "Nothing" in str(e)
        else:
            raise AssertionError("no such name")
        """,
    ).strip()
    done, modules = _run(body, tmp_path=tmp_path)

    assert done.returncode == 0, done.stderr
    assert "wetterdienst.settings" in modules


@pytest.mark.parametrize(
    "args",
    [
        pytest.param([], id="import"),
        pytest.param(["--version"], id="version"),
        pytest.param(["-v"], id="version-short"),
        pytest.param(["--help"], id="help"),
        pytest.param(["values", "--help"], id="values-help"),
        pytest.param(["stations", "--help"], id="stations-help"),
        pytest.param(["interpolate", "--help"], id="interpolate-help"),
        pytest.param(["summarize", "--help"], id="summarize-help"),
        pytest.param(["history", "--help"], id="history-help"),
        pytest.param(["issues", "--help"], id="issues-help"),
        pytest.param(["alerts", "--help"], id="alerts-help"),
        pytest.param(["radar", "--help"], id="radar-help"),
        pytest.param(["restapi", "--help"], id="restapi-help"),
        pytest.param(["stripes", "image", "--help"], id="stripes-image-help"),
        pytest.param(["about", "--help"], id="about-help"),
        pytest.param(["about", "coverage", "--help"], id="about-coverage-help"),
        pytest.param(["about", "glossary", "--help"], id="about-glossary-help"),
    ],
)
def test_help_and_version_import_no_heavy_package(args: list[str], tmp_path: Path) -> None:
    """The command line's import, `--version` and every `--help` load the click tree and nothing it does not print."""
    body = _RUN_CLI if args else "import wetterdienst.ui.cli"
    done, modules = _run(body, *args, tmp_path=tmp_path)

    assert done.returncode == 0, done.stderr
    assert _imported(modules, HEAVY) == []
    assert _imported(modules, HEAVY_OWN) == []
    assert not [module for module in modules if module.startswith("wetterdienst.provider")]
    assert {module for module in modules if module.split(".")[0] == "wetterdienst"} <= ALLOWED


@pytest.mark.parametrize(
    ("line", "offered"),
    [
        pytest.param("wetterdienst va", ["values"], id="command"),
        pytest.param("wetterdienst values --qu", ["--quiet"], id="option"),
        pytest.param("wetterdienst values --shape ", ["long", "wide"], id="choice"),
        pytest.param("wetterdienst values --plausibility-range ", ["hard", "soft"], id="plausibility-choice"),
        pytest.param("wetterdienst values --limits", ["--limits"], id="limits"),
        pytest.param("wetterdienst values --provider eau", ["eaufrance"], id="provider"),
        pytest.param("wetterdienst values --provider = noaa --network ", ["ghcn"], id="network-of-provider"),
        pytest.param("wetterdienst values --network mosmi", ["mosmix"], id="network"),
    ],
)
def test_a_completion_imports_no_heavy_package(line: str, offered: list[str], tmp_path: Path) -> None:
    """A TAB is the import of the command line and the answer: nothing a command needs, the providers least of all."""
    done, modules = _run(_RUN_CLI, tmp_path=tmp_path, **_complete(line))

    assert done.returncode == 0, done.stderr
    assert done.stderr == ""
    assert [row.removeprefix("plain,") for row in done.stdout.splitlines() if row] == offered
    assert _imported(modules, HEAVY) == []
    assert _imported(modules, HEAVY_OWN) == []
    assert not [module for module in modules if module.startswith("wetterdienst.provider")]
    assert {module for module in modules if module.split(".")[0] == "wetterdienst"} <= ALLOWED


# --- a command imports what it uses ---------------------------------------------------------------------------------

_DWD = ["--provider", "dwd", "--network", "observation"]
_NOAA = ["--provider", "noaa", "--network", "ghcn"]
_KL = ["--parameters", "daily/kl"]


@pytest.mark.parametrize(
    ("args", "code", "output"),
    [
        pytest.param(["cache"], 0, "wetterdienst", id="cache"),
        pytest.param(["info"], 0, "open weather data for humans", id="info"),
        pytest.param(["about", "glossary", "--limit", "1"], 0, '"unit_symbol"', id="glossary"),
        pytest.param(["about", "providers", "--provider", "dwd"], 0, '"dwd"', id="providers"),
        pytest.param(["about", "providers", "--provider", "nowhere"], 2, "nowhere", id="providers-unknown"),
        pytest.param(["about", "coverage", *_DWD, "--datasets", "climate_summary"], 0, "daily", id="coverage"),
        pytest.param(["about", "coverage", "--provider", "dwd"], 2, "Required with", id="coverage-usage"),
        pytest.param(["about", "auth", *_DWD], 0, '"valid": true', id="auth"),
        pytest.param(
            ["about", "fields", *_NOAA, "--resolution", "daily", "--dataset", "kl", "--period", "recent"],
            2,
            "observation",
            id="fields",
        ),
        pytest.param(["radar", "--dwd"], 0, "odimcode", id="radar"),
        pytest.param(["stations", *_DWD, *_KL], 2, "Missing option: one of", id="stations"),
        pytest.param(["values", *_DWD, *_KL], 2, "Missing option: one of", id="values"),
        pytest.param(["values", "--provider", "nowhere", "--network", "x", *_KL, "--all"], 2, "nowhere", id="api"),
        pytest.param(["values", *_DWD, *_KL, "--all", "--limits", "no-bounds"], 2, "--limits", id="limits"),
        pytest.param(["history", *_DWD, *_KL], 2, "Missing option: one of", id="history"),
        pytest.param(
            ["interpolate", *_DWD, "--parameters", "daily/kl/precipitation_amount"], 2, "--timestamp", id="interpolate"
        ),
        pytest.param(
            ["summarize", *_DWD, "--parameters", "daily/kl/precipitation_amount"], 2, "--timestamp", id="summarize"
        ),
        pytest.param(["issues", *_DWD, "--station", "1048"], 2, "issue", id="issues"),
        pytest.param(["alerts", "--target", "alerts.txt"], 2, "alerts.txt", id="alerts"),
        pytest.param(["stripes", "stations", "--kind", "nothing"], 1, "Invalid kind", id="stripes-stations"),
        pytest.param(["stripes", "image", "--kind", "temperature"], 2, "--station", id="stripes-image"),
        pytest.param(["values", "--stations", "1048", "--proviser", "dwd"], 2, "renamed|provider", id="mistyped"),
    ],
)
def test_a_command_in_a_clean_process_imports_what_it_uses(
    args: list[str], code: int, output: str, tmp_path: Path
) -> None:
    """Each command, run in a process that has imported nothing else, gets to the answer or the refusal it should.

    Offline, and all of them end before a request is made: the point is the imports, which a command that is run in
    the test session (with everything imported already) cannot show missing.
    """
    done, modules = _run(_RUN_CLI, *args, tmp_path=tmp_path, HOME=str(tmp_path), WD_CACHE_DIR=str(tmp_path / "cache"))

    assert done.returncode == code, (done.stdout, done.stderr)
    assert "Traceback" not in done.stderr
    assert any(part in done.stdout + done.stderr for part in output.split("|")), (done.stdout, done.stderr)
    # the command line was imported on top of what the command needed
    assert "wetterdienst.ui.cli" in modules
