# """Wetterdienst - Open weather data for humans"""
# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
__appname__ = "wetterdienst"

from wetterdienst.api import Wetterdienst
from wetterdienst.metadata.kind import Kind
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.provider import Provider
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.util.cache import cache_dir

# Single-sourcing the package version
# https://cjolowicz.github.io/posts/hypermodern-python-06-ci-cd/
try:
    from importlib.metadata import PackageNotFoundError, version  # noqa
except ImportError:  # pragma: no cover
    from importlib_metadata import PackageNotFoundError, version  # noqa

try:
    __version__ = version(__appname__)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"


def info() -> None:
    """ Function that prints some basic information about the wetterdienst instance """
    wd_info = {
        "version": __version__,
        "authors": "Benjamin Gutzmann <gutzemann@gmail.com>, "
        "Andreas Motl <andreas.motl@panodata.org>",
        "documentation": "https://wetterdienst.readthedocs.io/",
        "repository": "https://github.com/earthobservations/wetterdienst",
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
