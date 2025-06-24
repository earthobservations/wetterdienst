# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Bootstrapping utilities."""


def get_version(appname: str) -> str:
    """Get version of package."""
    from importlib.metadata import PackageNotFoundError, version  # noqa: PLC0415

    try:
        return version(appname)
    except PackageNotFoundError:  # pragma: no cover
        return "unknown"
