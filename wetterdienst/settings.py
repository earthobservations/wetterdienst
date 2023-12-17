# -*- coding: utf-8 -*-
# Copyright (C) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import json
import logging
import pathlib
from copy import deepcopy
from functools import partial
from typing import Dict, Literal, Optional, Union

import platformdirs
from environs import Env
from marshmallow.validate import OneOf

from wetterdienst import Parameter

log = logging.getLogger(__name__)


def _decide_arg(regular_arg, env_arg, default_arg, ignore_env):
    if regular_arg is not None:
        return regular_arg
    elif not ignore_env and env_arg is not None:
        return env_arg
    else:
        return default_arg


class Settings:
    """Wetterdienst class for general settings"""

    _defaults = {
        "cache_disable": False,
        "cache_dir": platformdirs.user_cache_dir(appname="wetterdienst"),
        "fsspec_client_kwargs": {},
        "ts_humanize": True,
        "ts_shape": "long",
        "ts_si_units": True,
        "ts_skip_empty": False,
        "ts_skip_threshold": 0.95,
        "ts_skip_criteria": "min",
        "ts_dropna": False,
        "ts_interpolation_station_distance": {
            "default": 40.0,
            Parameter.PRECIPITATION_HEIGHT.name.lower(): 20.0,
        },
        "ts_interpolation_use_nearby_station_distance": 1,
    }

    def __init__(
        self,
        cache_disable: Optional[bool] = None,
        cache_dir: Optional[pathlib.Path] = None,
        fsspec_client_kwargs: Optional[dict] = None,
        ts_humanize: Optional[bool] = None,
        ts_shape: Optional[Literal["wide", "long"]] = None,
        ts_si_units: Optional[bool] = None,
        ts_skip_empty: Optional[bool] = None,
        ts_skip_threshold: Optional[float] = None,
        ts_skip_criteria: Optional[Literal["min", "mean", "max"]] = None,
        ts_dropna: Optional[bool] = None,
        ts_interpolation_use_nearby_station_distance: Optional[Union[float, int]] = None,
        ts_interpolation_station_distance: Optional[Dict[str, float]] = None,
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
            with env.prefixed("TS_"):
                # timeseries
                self.ts_humanize: bool = _da(ts_humanize, env.bool("HUMANIZE", None), _defaults["ts_humanize"])
                self.ts_shape: str = _da(
                    ts_shape, env.str("SHAPE", None, validate=OneOf(["long", "wide"])), _defaults["ts_shape"]
                )
                self.ts_si_units: bool = _da(ts_si_units, env.bool("SI_UNITS", None), _defaults["ts_si_units"])
                self.ts_skip_empty: bool = _da(ts_skip_empty, env.bool("SKIP_EMPTY", None), _defaults["ts_skip_empty"])
                self.ts_skip_threshold: float = _da(
                    ts_skip_threshold, env.float("SKIP_THRESHOLD", None), _defaults["ts_skip_threshold"]
                )
                self.ts_skip_criteria: str = _da(
                    ts_skip_criteria,
                    env.str("SKIP_CRITERIA", None, validate=OneOf(["min", "mean", "max"])),
                    _defaults["ts_skip_criteria"],
                )
                self.ts_dropna: bool = _da(ts_dropna, env.bool("DROPNA", ts_dropna), _defaults["ts_dropna"])

                with env.prefixed("INTERPOLATION_"):
                    _ts_interpolation_station_distance = _defaults["ts_interpolation_station_distance"]
                    _ts_interpolation_station_distance.update(
                        {k: float(v) for k, v in env.dict("STATION_DISTANCE", {}).items()} if not ignore_env else {}
                    )
                    _ts_interpolation_station_distance.update(ts_interpolation_station_distance or {})
                    self.ts_interpolation_station_distance = _ts_interpolation_station_distance

                    self.ts_interpolation_use_nearby_station_distance: float = _da(
                        ts_interpolation_use_nearby_station_distance,
                        env.float("USE_NEARBY_STATION_DISTANCE", None),
                        _defaults["ts_interpolation_use_nearby_station_distance"],
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
            "ts_humanize": self.ts_humanize,
            "ts_shape": self.ts_shape,
            "ts_si_units": self.ts_si_units,
            "ts_skip_empty": self.ts_skip_empty,
            "ts_skip_threshold": self.ts_skip_threshold,
            "ts_skip_criteria": self.ts_skip_criteria,
            "ts_dropna": self.ts_dropna,
            "ts_interpolation_station_distance": self.ts_interpolation_station_distance,
            "ts_interpolation_use_nearby_station_distance": self.ts_interpolation_use_nearby_station_distance,
        }

    def reset(self) -> "Settings":
        """Reset Wetterdienst Settings to start"""
        return self.__init__()

    @classmethod
    def default(cls) -> "Settings":
        """Ignore environmental variables and use all default arguments as defined above"""
        # Put empty env to force using the given defaults
        return cls(ignore_env=True)
