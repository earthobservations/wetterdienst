# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What to say when an optional dependency is not installed.

The package is installable in pieces, so the ordinary answer to "this is not installed" is the name
of the extra that installs it. Which extra that is, is read out of the installed metadata rather
than written into a string here, so an extra that gains or loses a package cannot leave a wrong
instruction behind.
"""

from __future__ import annotations

import importlib
import re
from typing import TYPE_CHECKING

from wetterdienst.exceptions import MissingDependencyError

if TYPE_CHECKING:
    from types import ModuleType


def extras_installing(module_name: str) -> list[str]:
    """Return the extras of wetterdienst that would install the distribution providing ``module_name``.

    Read out of the installed metadata rather than from a list kept here, so an extra that gains or
    loses a package cannot leave a wrong instruction behind. Returns nothing rather than guessing
    where the metadata cannot be read, or where the module belongs to no extra at all.
    """
    from importlib.metadata import PackageNotFoundError, metadata, packages_distributions  # noqa: PLC0415

    def canonical(name: str) -> str:
        return re.sub(r"[-_.]+", "-", name).lower()

    try:
        # the module is by definition not importable here, so its distribution is usually unknown to
        # the interpreter -- the module's own name is the fallback, which is the same for all but a
        # handful of packages
        distributions = {canonical(name) for name in packages_distributions().get(module_name, [module_name])}
        requirements = metadata("wetterdienst").get_all("Requires-Dist") or []
    except PackageNotFoundError:
        return []
    extras = set()
    for requirement in requirements:
        specifier, _, marker = requirement.partition(";")
        extra = re.search(r"""extra\s*==\s*['"]([^'"]+)['"]""", marker)
        if not extra:
            continue
        if canonical(re.split(r"[<>=!~\[ ]", specifier, maxsplit=1)[0]) in distributions:
            extras.add(extra.group(1))
    return sorted(extras)


def missing_dependency_message(what: str, module_name: str | None, *, extra: str | None = None) -> str:
    """Say what cannot be done, which package is missing, and which extra would install it.

    Args:
        what: what the caller was trying to use, as it should read at the start of a sentence.
        module_name: the module that was not importable, as the exception named it.
        extra: the extra the caller belongs to, where it has one. Several extras can install the
            same package -- `h5py` comes with both `knmi` and `radar` -- and telling someone
            reading radar files to install the KNMI extra is true and no help. Named here it is
            preferred, but only if the metadata agrees that it installs the package, so a renamed
            extra falls back to what is actually there rather than to a wrong instruction.

    Returns:
        The message, naming an install command where the package belongs to an extra.

    """
    if not module_name:
        return f"{what} is missing a dependency that is not installed."
    message = f"{what} requires {module_name}, which is not installed."
    extras = extras_installing(module_name)
    if not extras:
        return message
    if extra in extras:
        extras = [extra]
    options = " or ".join(f"pip install wetterdienst[{name}]" for name in extras)
    return f"{message} Install it with: {options}"


def import_optional(module_name: str, what: str, *, extra: str | None = None) -> ModuleType:
    """Import a module of an optional dependency, or say what to install.

    The one way the library imports a package that only an extra installs, so that its absence is
    always the same exception: a `MissingDependencyError`, whose message is the whole of what there
    is to say and which the command line prints as one line and the REST API answers with a 501.
    Without it the absence arrives as whatever the import raised -- a bare `ModuleNotFoundError`
    from DuckDB, an `ImportError` with a hint of its own from plotly -- and each reader of the
    error has to guess which of them is an instruction and which a defect.

    Only a package that is not installed counts. A module missing inside a package that is
    installed (`duckdb.duckdb`, or one of wetterdienst's own), and an `ImportError` that is not an
    absence (a name the installed version lacks, a cycle), are defects and keep their traceback.

    Args:
        module_name: the module to import, dotted where it is a submodule (`plotly.express`).
        what: what the caller was trying to do, as it should read at the start of a sentence.
        extra: the extra the caller belongs to, where several install the package; see
            `missing_dependency_message`.

    Returns:
        The imported module.

    Raises:
        MissingDependencyError: the module, or a package it needs, is not installed.

    """
    try:
        return importlib.import_module(module_name)
    except ModuleNotFoundError as e:
        # a dotted name is a module missing inside a package that is installed (`duckdb.duckdb`, a
        # module of our own): a broken install or a defect, not a package to install
        if e.name is not None and "." in e.name:
            raise
        raise MissingDependencyError(missing_dependency_message(what, e.name or module_name, extra=extra)) from e
