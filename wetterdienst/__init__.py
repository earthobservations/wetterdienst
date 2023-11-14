# """Wetterdienst - Open weather data for humans"""
# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from wetterdienst import boot

boot.monkeypatch()

from wetterdienst.api import Wetterdienst
from wetterdienst.boot import get_info_text
from wetterdienst.metadata.kind import Kind
from wetterdienst.metadata.parameter import Parameter
from wetterdienst.metadata.period import Period
from wetterdienst.metadata.provider import Provider
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.settings import Settings

__appname__ = "wetterdienst"
__version__ = boot.get_version(__appname__)


__all__ = [
    "__appname__",
    "__version__",
    "get_info_text",
    "Kind",
    "Parameter",
    "Period",
    "Provider",
    "Resolution",
    "Settings",
    "Wetterdienst",
]
