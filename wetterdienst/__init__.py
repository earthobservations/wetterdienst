# """Wetterdienst - Open weather data for humans"""
# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
__appname__ = "wetterdienst"

from pathlib import Path

import tomlkit

from wetterdienst.api import Wetterdienst
from wetterdienst.metadata.kind import Kind
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.provider import Provider
from wetterdienst.metadata.resolution import Resolution

# Single-sourcing the package version
# https://cjolowicz.github.io/posts/hypermodern-python-06-ci-cd/
from wetterdienst.util.cache import cache_dir

try:
    from importlib.metadata import PackageNotFoundError, version  # noqa
except ImportError:  # pragma: no cover
    from importlib_metadata import PackageNotFoundError, version  # noqa

try:
    __version__ = version(__name__)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"


def show() -> None:
    here = Path(__name__).parent

    with Path(here.parent / "pyproject.toml").open() as f:
        pyproject_dict = tomlkit.parse(f.read())["tool"]["poetry"]

    wd_info = {
        "version": pyproject_dict["version"],
        "authors": ", ".join(pyproject_dict["authors"]),
        "documentation": pyproject_dict["homepage"],
        "repository": pyproject_dict["homepage"],
        "cache_dir": cache_dir,
    }

    text = (
        "Wetterdienst - Open weather data for humans\n"
        "-------------------------------------------"
    )

    for key, value in wd_info.items():
        text += f"\n{key}:\t {value}"

    print(text)

    return


if __name__ == "__main__":
    show()
