# -*- coding: utf-8 -*-
# Copyright (C) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import logging
import pathlib
from contextvars import ContextVar

import platformdirs
from environs import Env

log = logging.getLogger(__name__)


class Settings:
    """Wetterdienst class for general settings"""

    env = Env()
    env.read_env()

    def __init__(self):
        with self.env.prefixed("WD_"):
            # cache
            # for initial printout we need to work with _cache_disable and
            # Check out this: https://florimond.dev/en/posts/2018/10/reconciling-dataclasses-and-properties-in-python/
            self.cache_disable: bool = self.env.bool("CACHE_DISABLE", False)

            self.cache_dir: pathlib.Path = self.env.path(
                "CACHE_DIR", platformdirs.user_cache_dir(appname="wetterdienst")
            )

            # FSSPEC aiohttp client kwargs, may be used to pass extra arguments
            # such as proxies to aiohttp
            self.fsspec_client_kwargs: dict = self.env.dict("FSSPEC_CLIENT_KWARGS", {})

            with self.env.prefixed("SCALAR_"):
                # scalar
                self.humanize: bool = self.env.bool("HUMANIZE", True)
                self.tidy: bool = self.env.bool("TIDY", True)
                self.si_units: bool = self.env.bool("SI_UNITS", True)
                self.skip_empty: bool = self.env.bool("SKIP_EMPTY", False)
                self.skip_threshold: bool = self.env.float("SKIP_THRESHOLD", 0.95)
                self.dropna: bool = self.env.bool("DROPNA", False)

                with self.env.prefixed("INTERPOLATION_"):
                    self.interp_use_nearby_station_until_km: float = self.env.float("USE_NEARBY_STATION_UNTIL_KM", 1)

    @property
    def cache_disable(self) -> bool:
        return self._cache_disable

    @cache_disable.setter
    def cache_disable(self, value: bool) -> None:
        self._cache_disable = value
        status = "disabled" if value else "enabled"
        log.info(f"Wetterdienst cache is {status}")

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
