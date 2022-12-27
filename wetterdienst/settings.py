# -*- coding: utf-8 -*-
# Copyright (C) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import json
import logging
import pathlib
from copy import deepcopy
from functools import partial
from typing import Optional, Union

import platformdirs
from environs import Env

log = logging.getLogger(__name__)


def _is_none(arg):
    """Function to check if arg is None"""
    return arg is None


def _decide_arg(regular_arg, env_arg, default_arg, ignore_env):
    if not _is_none(regular_arg):
        return regular_arg
    elif not ignore_env and not _is_none(env_arg):
        return env_arg
    else:
        return default_arg


class Settings:
    """Wetterdienst class for general settings"""

    _defaults = {
        "cache_disable": False,
        "cache_dir": platformdirs.user_cache_dir(appname="wetterdienst"),
        "fsspec_client_kwargs": {},
        "humanize": True,
        "tidy": True,
        "si_units": True,
        "skip_empty": False,
        "skip_threshold": 0.95,
        "dropna": False,
        "interp_use_nearby_station_until_km": 1,
    }

    def __init__(
        self,
        cache_disable: Optional[bool] = None,
        cache_dir: Optional[pathlib.Path] = None,
        fsspec_client_kwargs: Optional[dict] = None,
        humanize: Optional[bool] = None,
        tidy: Optional[bool] = None,
        si_units: Optional[bool] = None,
        skip_empty: Optional[bool] = None,
        skip_threshold: Optional[float] = None,
        dropna: Optional[bool] = None,
        interp_use_nearby_station_until_km: Optional[Union[float, int]] = None,
        ignore_env: bool = False,
    ) -> None:
        _defaults = deepcopy(self._defaults)  # make sure mutable objects are not changed
        _da = partial(_decide_arg, ignore_env=ignore_env)

        env = Env()
        # Evaluate environment variables `WD_CACHE_DISABLE` and `WD_CACHE_DIR`.
        with env.prefixed("WD_"):
            # cache
            self.cache_disable: bool = _da(cache_disable, env.bool("CACHE_DISABLE", None), _defaults["cache_disable"])
            self.cache_dir: pathlib.Path = _da(cache_dir, env.path("CACHE_DIR", None), _defaults["cache_dir"])
            # FSSPEC aiohttp client kwargs, may be used to pass extra arguments
            # such as proxies to aiohttp
            self.fsspec_client_kwargs: dict = _da(
                fsspec_client_kwargs,
                env.dict("FSSPEC_CLIENT_KWARGS", {}) or None,
                _defaults["fsspec_client_kwargs"],
            )
            with env.prefixed("SCALAR_"):
                # scalar
                self.humanize: bool = _da(humanize, env.bool("HUMANIZE", None), _defaults["humanize"])
                self.tidy: bool = _da(tidy, env.bool("TIDY", None), _defaults["tidy"])
                self.si_units: bool = _da(si_units, env.bool("SI_UNITS", None), _defaults["si_units"])
                self.skip_empty: bool = _da(skip_empty, env.bool("SKIP_EMPTY", None), _defaults["skip_empty"])
                self.skip_threshold: bool = _da(
                    skip_threshold, env.float("SKIP_THRESHOLD", None), _defaults["skip_threshold"]
                )
                self.dropna: bool = _da(dropna, env.bool("DROPNA", dropna), _defaults["dropna"])

                with env.prefixed("INTERPOLATION_"):
                    self.interp_use_nearby_station_until_km: float = _da(
                        interp_use_nearby_station_until_km,
                        env.float("USE_NEARBY_STATION_UNTIL_KM", None),
                        _defaults["interp_use_nearby_station_until_km"],
                    )

        if self.cache_disable:
            log.info("Wetterdienst cache is disabled")
        else:
            log.info(f"Wetterdienst cache is enabled [CACHE_DIR: {self.cache_dir}]")

    def __repr__(self) -> str:
        settings = ",".join([f"{k}:{v}" for k, v in self.to_dict().items()])
        settings = settings.replace(" ", "").replace("'", "")
        return f"Settings({settings})"

    def __str__(self) -> str:
        return f"Settings({json.dumps(self.to_dict(),indent=4)})"

    def __eq__(self, other: "Settings"):
        return self.to_dict() == other.to_dict()

    def to_dict(self) -> dict:
        return {
            "cache_disable": self.cache_disable,
            "cache_dir": self.cache_dir,
            "fsspec_client_kwargs": self.fsspec_client_kwargs,
            "humanize": self.humanize,
            "tidy": self.tidy,
            "si_units": self.si_units,
            "skip_empty": self.skip_empty,
            "skip_threshold": self.skip_threshold,
            "dropna": self.dropna,
            "interp_use_nearby_station_until_km": self.interp_use_nearby_station_until_km,
        }

    def reset(self) -> "Settings":
        """Reset Wetterdienst Settings to start"""
        return self.__init__()

    @classmethod
    def default(cls) -> "Settings":
        """Ignore environmental variables and use all default arguments as defined above"""
        # Put empty env to force using the given defaults
        return cls(ignore_env=True)
