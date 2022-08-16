# """Wetterdienst - Open weather data for humans"""
# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
__appname__ = "wetterdienst"


# TODO: MONKEY PATCH FSSPEC
def monkey_patch():
    import wetterdienst.util.fsspec_monkeypatch


monkey_patch()


from importlib.metadata import PackageNotFoundError, version  # noqa

from wetterdienst.api import Wetterdienst
from wetterdienst.metadata.kind import Kind
from wetterdienst.metadata.parameter import Parameter
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.provider import Provider
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.settings import Settings

try:
    __version__ = version(__appname__)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"


def info() -> None:
    """Function that prints some basic information about the wetterdienst instance"""
    wd_info = {
        "version": __version__,
        "authors": "Benjamin Gutzmann <gutzemann@gmail.com>, " "Andreas Motl <andreas.motl@panodata.org>",
        "documentation": "https://wetterdienst.readthedocs.io/",
        "repository": "https://github.com/earthobservations/wetterdienst",
        "cache_dir": Settings.cache_dir,
    }

    text = "Wetterdienst - Open weather data for humans-------------------------------------------"

    for key, value in wd_info.items():
        text += f"\n{key}:\t {value}"

    print(text)  # noqa: T201

    return
