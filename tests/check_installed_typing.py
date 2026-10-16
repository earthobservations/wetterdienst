# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Type-check the caller script against the package as a caller installs it (`poe typecheck:installed`).

`tests/typed_caller.py` states what a type checker is to make of each result of the documented API.
`tests/test_typed_surface.py` runs it against the checkout, where the checker reads `src/` as the
project's own code, which says nothing of what the wheel ships or of the marker (PEP 561) that makes a
caller's checker read the annotations at all. This builds the wheel, installs it into a clean virtual
environment, bare as `pip install wetterdienst` leaves it (an extra changes no signature the script
uses), and checks a copy of the script in a directory of its own, so that the only `wetterdienst` the
checker can find is the installed one, at the oldest Python the package supports.

It needs the network (the dependencies are installed) and takes a minute, so it is a task and a CI job
rather than part of the test suite.
"""

import os
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).parent.parent
CALLER = Path(__file__).parent / "typed_caller.py"

#: the oldest Python the package supports, which the checker assumes whatever the environment runs
PYTHON_FLOOR = "3.11"
MARKER = "wetterdienst/py.typed"


def _bin(venv: Path, name: str) -> Path:
    """Name an executable of a virtual environment."""
    return venv / ("Scripts" if os.name == "nt" else "bin") / (name + (".exe" if os.name == "nt" else ""))


def main() -> int:
    """Build, install, check; return the exit code."""
    uv = shutil.which("uv")
    if uv is None:
        print("uv is needed to build and install the wheel")  # noqa: T201
        return 2
    with tempfile.TemporaryDirectory() as tmp_name:
        tmp = Path(tmp_name)
        subprocess.run([uv, "build", "--wheel", "--out-dir", str(tmp / "dist"), str(ROOT)], check=True)  # noqa: S603
        wheel = next((tmp / "dist").glob("*.whl"))
        with zipfile.ZipFile(wheel) as archive:
            names = archive.namelist()
        if MARKER not in names:
            print(f"{wheel.name} does not contain {MARKER}: a caller's checker would read the package as untyped")  # noqa: T201
            return 1
        caller_dir = tmp / "caller"
        caller_dir.mkdir()
        shutil.copy(CALLER, caller_dir / CALLER.name)
        venv = tmp / "venv"
        python = _bin(venv, "python")
        version = f"{sys.version_info.major}.{sys.version_info.minor}"
        subprocess.run([uv, "venv", "--quiet", "--python", version, str(venv)], check=True)  # noqa: S603
        subprocess.run(  # noqa: S603
            [uv, "pip", "install", "--quiet", "--python", str(python), f"wetterdienst @ {wheel.as_uri()}"],
            check=True,
        )
        print(f"ty check of {CALLER.name} against {wheel.name} installed into a clean environment")  # noqa: T201
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
                str(venv),
                "--python-version",
                PYTHON_FLOOR,
                CALLER.name,
            ],
            check=False,
            cwd=caller_dir,
        )
        failed = completed.returncode != 0
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
