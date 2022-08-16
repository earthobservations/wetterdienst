# -*- coding: utf-8 -*-
# Copyright (C) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import logging
import pathlib
from contextvars import ContextVar
from dataclasses import dataclass, field

import appdirs
from dataclass_wizard import property_wizard
from environs import Env

log = logging.getLogger(__name__)


@dataclass
class Settings(metaclass=property_wizard):
    """Wetterdienst class for general settings"""

    env = Env()
    env.read_env()

    with env.prefixed("WD_"):
        # cache
        # for initial printout we need to work with _cache_disable and
        # Check out this: https://florimond.dev/en/posts/2018/10/reconciling-dataclasses-and-properties-in-python/
        cache_disable: bool = env.bool("CACHE_DISABLE", False)
        _cache_disable: bool = field(init=False, repr=False)

        cache_dir: pathlib.Path = env.path("CACHE_DIR", appdirs.user_cache_dir(appname="wetterdienst"))

        # FSSPEC aiohttp client kwargs, may be used to pass extra arguments
        # such as proxies to aiohttp
        fsspec_client_kwargs: dict = env.dict("FSSPEC_CLIENT_KWARGS", {}) or field(default_factory=dict)

        with env.prefixed("SCALAR_"):
            # scalar
            humanize: bool = env.bool("HUMANIZE", True)
            tidy: bool = env.bool("TIDY", True)
            si_units: bool = env.bool("SI_UNITS", True)
            skip_empty: bool = env.bool("SKIP_EMPTY", False)
            skip_threshold: bool = env.float("SKIP_THRESHOLD", 0.95)
            dropna: bool = env.bool("DROPNA", False)

    @property
    def cache_disable(self) -> bool:
        return self._cache_disable

    @cache_disable.setter
    def cache_disable(self, value: bool) -> None:
        self._cache_disable = value
        status = "disabled" if value else "enabled"
        log.warning(f"Wetterdienst cache is {status}")

    def reset(self):
        """Reset Wetterdienst Settings to start"""
        self.env.read_env()
        self.__init__()

    def default(self):
        """Ignore environmental variables and use all default arguments as defined above"""
        # Put empty env to force using the given defaults
        self.env = Env()
        self.__init__()

    _local_settings = ContextVar("local_settings")
    _local_settings_token = None

    # Context manager for managing settings in concurrent situations
    def __enter__(self):
        settings_token = self._local_settings.set(self)
        self._local_settings.get()._local_settings_token = settings_token
        return self._local_settings.get()

    def __exit__(self, type_, value, traceback):
        self._local_settings.reset(self._local_settings_token)
        # this is not the same object as the original one
        return Settings.__init__()


Settings = Settings()
