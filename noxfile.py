# https://cjolowicz.github.io/posts/hypermodern-python-02-testing/
# https://cjolowicz.github.io/posts/hypermodern-python-03-linting/
import os
from typing import Any
import tempfile

import nox
from nox.sessions import Session


def install_test_packages(session):
    install_with_constraints(
        session,
        "pytest",
        "pytest-xdist[psutil]",
        "pytest-notebook",
        "pytest-dictsdiff",
        "matplotlib",
        "mock",
        "surrogate",
        "pybufrkit",
        "deprecation",
    )


@nox.session(python=["3.6", "3.7", "3.8"])
def tests(session):
    """Run tests."""
    session.run(
        "poetry",
        "install",
        "--no-dev",
        "--extras=http",
        "--extras=sql",
        "--extras=excel",
        external=True,
    )
    install_test_packages(session)
    session.run("pytest", "--numprocesses=auto")


@nox.session(python=["3.7"])
def coverage(session: Session) -> None:
    """Run tests and upload coverage data."""
    session.run(
        "poetry",
        "install",
        "--no-dev",
        "--extras=http",
        "--extras=sql",
        "--extras=excel",
        external=True,
    )
    install_test_packages(session)
    install_with_constraints(
        session,
        "coverage[toml]",
        "pytest-cov",
    )
    session.run("pytest", "--numprocesses=auto", "--cov=wetterdienst", "tests/")
    session.run("coverage", "xml")


locations = "wetterdienst", "example", "tests", "noxfile.py"


@nox.session(python=["3.6", "3.7", "3.8"])
def black(session):
    args = session.posargs or locations
    session.install("black")
    session.run("black", *args)


@nox.session(python=["3.6", "3.7", "3.8"])
def lint(session):
    args = session.posargs or locations
    session.install("flake8", "flake8-bandit", "flake8-black", "flake8-bugbear")
    session.run("flake8", *args)


def install_with_constraints(session: Session, *args: str, **kwargs: Any) -> None:
    """
    Install packages constrained by Poetry's lock file.

    This function is a wrapper for nox.sessions.Session.install. It
    invokes pip to install packages inside of the session's virtualenv.
    Additionally, pip is passed a constraints file generated from
    Poetry's lock file, to ensure that the packages are pinned to the
    versions specified in poetry.lock. This allows you to manage the
    packages as Poetry development dependencies.

    Arguments:
        session: The Session object.
        args: Command-line arguments for pip.
        kwargs: Additional keyword arguments for Session.install.
    """
    req_path = os.path.join(tempfile.gettempdir(), os.urandom(24).hex())
    session.run(
        "poetry",
        "export",
        "--dev",
        "--format=requirements.txt",
        "--without-hashes",
        f"--output={req_path}",
        external=True,
    )
    session.install(f"--constraint={req_path}", *args, **kwargs)
    os.unlink(req_path)
