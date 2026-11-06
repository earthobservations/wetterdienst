# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Package for accessing weather data from various APIs."""

import importlib
from dataclasses import dataclass
from email.utils import getaddresses
from importlib.metadata import PackageNotFoundError
from importlib.metadata import metadata as package_metadata  # `wetterdienst.metadata` is a subpackage
from pathlib import Path
from textwrap import dedent
from typing import TYPE_CHECKING, Any, TypedDict

from wetterdienst import boot
from wetterdienst.api import Wetterdienst
from wetterdienst.exceptions import (
    ConfigurationError,
    ExportRefusedError,
    NotFoundError,
    RequestError,
    UpstreamError,
    WetterdienstError,
)
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution

if TYPE_CHECKING:
    from wetterdienst.options import Options
    from wetterdienst.settings import Settings

# `Options` and `Settings` are pydantic models, and importing them imports pydantic-settings and polars, which
# `import wetterdienst` does not need to pay for: the command line's `--help`, `--version` and shell completion import
# this package and little else (GH-3809). They are read from their modules on first use, so `from wetterdienst import
# Settings` and `wetterdienst.Settings` are what they were.
_LAZY = {"Options": "wetterdienst.options", "Settings": "wetterdienst.settings"}


def __getattr__(name: str) -> Any:  # noqa: ANN401
    """Give `Options` and `Settings`, importing the module that defines the one asked for."""
    if name in _LAZY:
        value = getattr(importlib.import_module(_LAZY[name]), name)
        globals()[name] = value  # found directly from now on
        return value
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def __dir__() -> list[str]:
    """List the lazily imported names too, as `dir(wetterdienst)` always had them."""
    return sorted({*globals(), *_LAZY})


__appname__ = "wetterdienst"
__version__ = boot.get_version(__appname__)


@dataclass
class Author:
    """Data class for author information."""

    name: str
    email: str
    github_handle: str


# The metadata of the package names an author and an address, not a GitHub account.
_GITHUB_HANDLES = {"Benjamin Gutzmann": "gutzbenj", "Andreas Motl": "amotl"}


def _read_authors(appname: str) -> list[Author]:
    """Read the authors from the installed package's metadata, i.e. `[project] authors` of pyproject.toml.

    One source rather than a copy of it here, which named a different address for the first author
    than the package does (GH-2954). Empty where there is no installed package to ask, a source
    checkout that was never installed, or none that names an address; an editable install reports
    what pyproject.toml said when it was last installed.
    """
    try:
        header = package_metadata(appname).get_all("Author-email") or []
    except PackageNotFoundError:  # pragma: no cover
        return []
    return [
        Author(name or email, email, _GITHUB_HANDLES.get(name, "")) for name, email in getaddresses(header) if email
    ]


class _AuthorDict(TypedDict):
    """An author as `Info.to_dict` gives it."""

    name: str
    email: str
    github_handle: str


class _InfoDict(TypedDict):
    """What `Info.to_dict` gives."""

    name: str
    version: str
    authors: list[_AuthorDict]
    repository: str
    documentation: str
    cache_dir: Path


class Info:
    """Class for package information."""

    def __init__(self) -> None:
        """Initialize Info object."""
        self.name = __appname__
        self.slogan = "open weather data for humans"
        self.version = __version__
        self.authors = _read_authors(__appname__)
        self.repository = "https://github.com/earthobservations/wetterdienst"
        self.documentation = "https://wetterdienst.readthedocs.io"

    @property
    def cache_dir(self) -> Path:
        """Return the cache directory the settings name.

        Read when asked for rather than when built: the REST API builds an `Info` on import, which a
        malformed `WD_*` setting then stopped with a traceback, before the server could refuse it
        by its variable (GH-2335).
        """
        from wetterdienst.settings import Settings  # noqa: PLC0415

        return Settings().cache_dir

    def __str__(self) -> str:
        """Return string representation of Info object."""
        return dedent(f"""
        ===========================================
        {self.name} - open weather data for humans
        ===========================================
        version:                {self.version}
        authors:                {", ".join(f"{author.name} <{author.email}>" for author in self.authors) or "unknown"}
        documentation:          {self.documentation}
        repository:             {self.repository}
        cache_dir (default):    {self.cache_dir}
        """).strip()

    def to_dict(self) -> _InfoDict:
        """Return dictionary representation of Info object."""
        return {
            "name": self.name,
            "version": self.version,
            "authors": [{"name": a.name, "email": a.email, "github_handle": a.github_handle} for a in self.authors],
            "repository": self.repository,
            "documentation": self.documentation,
            "cache_dir": self.cache_dir,
        }


__all__ = [
    "Author",
    "ConfigurationError",
    "ExportRefusedError",
    "Info",
    "NotFoundError",
    "Options",
    "Period",
    "RequestError",
    "Resolution",
    "Settings",
    "UpstreamError",
    "Wetterdienst",
    "WetterdienstError",
    "__appname__",
    "__version__",
]
