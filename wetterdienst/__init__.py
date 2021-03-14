# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Wetterdienst - Open weather data for humans"""
__appname__ = "wetterdienst"

from wetterdienst.api import Wetterdienst  # rather use this as entry point
from wetterdienst.metadata.kind import Kind
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.provider import Provider
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.provider import dwd  # remove at some point

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
