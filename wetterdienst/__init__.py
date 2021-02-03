# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Wetterdienst - Open weather data for humans"""
__appname__ = "wetterdienst"

from wetterdienst import dwd
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.resolution import Resolution

# Single-sourcing the package version
# https://cjolowicz.github.io/posts/hypermodern-python-06-ci-cd/
try:
    from importlib.metadata import PackageNotFoundError, version  # noqa
except ImportError:  # pragma: no cover
    from importlib_metadata import PackageNotFoundError, version  # noqa

try:
    __version__ = version(__name__)
except PackageNotFoundError:  # pragma: no cover
    __version__ = "unknown"
