# Copyright (C) 2018-2022, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import json
import logging
from copy import deepcopy
from pathlib import Path  # noqa: TCH003
from typing import Literal

import platformdirs
from environs import Env
from pydantic import BaseModel, Field, model_validator

from wetterdienst import Parameter

log = logging.getLogger(__name__)


class Settings(BaseModel):
    """Pydantic model for Wetterdienst general settings"""

    cache_disable: bool | None = Field(default=False)
    cache_dir: Path | None = Field(default=platformdirs.user_cache_dir(appname="wetterdienst"))
    fsspec_client_kwargs: dict | None = Field(default_factory=dict)
    ts_humanize: bool | None = Field(default=True)
    ts_shape: Literal["wide", "long"] | None = Field(default="long")
    ts_si_units: bool | None = Field(default=True)
    ts_skip_empty: bool | None = Field(default=False)
    ts_skip_threshold: float | None = Field(default=0.95)
    ts_skip_criteria: Literal["min", "mean", "max"] | None = Field(default="min")
    ts_dropna: bool | None = Field(default=False)
    ts_interpolation_station_distance: dict[str, float] | None = Field(
        default_factory=lambda: {
            "default": 40.0,
            Parameter.PRECIPITATION_HEIGHT.value.lower(): 20.0,
        }
    )
    ts_interpolation_use_nearby_station_distance: float | None = Field(default=1)
    ignore_env: bool | None = Field(default=False)

    @model_validator(mode="before")
    def set_values(cls, values):
        _defaults = deepcopy(cls.__fields__)
        _defaults = {k: v.default_factory() if callable(v.default_factory) else v.default for k, v in _defaults.items()}

        env = Env()
        env.read_env()

        ignore_env = values.get("ignore_env", False)

        def decide_arg(regular_arg, env_var_name, default_arg):
            return regular_arg if regular_arg is not None else (not ignore_env and env_var_name) or default_arg

        with env.prefixed("WD_"):
            values["cache_disable"] = decide_arg(
                values.get("cache_disable"),
                env.bool("CACHE_DISABLE", None),
                _defaults["cache_disable"],
            )
            values["cache_dir"] = decide_arg(
                values.get("cache_dir"), env.path("CACHE_DIR", None), _defaults["cache_dir"]
            )
            values["fsspec_client_kwargs"] = decide_arg(
                values.get("fsspec_client_kwargs"),
                env.dict("FSSPEC_CLIENT_KWARGS", {}),
                _defaults["fsspec_client_kwargs"],
            )
            with env.prefixed("TS_"):
                values["ts_humanize"] = decide_arg(
                    values.get("ts_humanize"), env.bool("HUMANIZE", None), _defaults["ts_humanize"]
                )
                values["ts_shape"] = decide_arg(values.get("ts_shape"), env.str("SHAPE", None), _defaults["ts_shape"])
                values["ts_si_units"] = decide_arg(
                    values.get("ts_si_units"), env.bool("SI_UNITS", None), _defaults["ts_si_units"]
                )
                values["ts_skip_empty"] = decide_arg(
                    values.get("ts_skip_empty"), env.bool("SKIP_EMPTY", None), _defaults["ts_skip_empty"]
                )
                values["ts_skip_threshold"] = decide_arg(
                    values.get("ts_skip_threshold"), env.float("SKIP_THRESHOLD", None), _defaults["ts_skip_threshold"]
                )
                values["ts_skip_criteria"] = decide_arg(
                    values.get("ts_skip_criteria"), env.str("SKIP_CRITERIA", None), _defaults["ts_skip_criteria"]
                )
                values["ts_dropna"] = decide_arg(
                    values.get("ts_dropna"), env.bool("DROPNA", None), _defaults["ts_dropna"]
                )
                with env.prefixed("INTERPOLATION_"):
                    ts_interpolation_station_distance = _defaults["ts_interpolation_station_distance"].copy()
                    if not ignore_env:
                        ts_interpolation_station_distance.update(env.dict("STATION_DISTANCE", {}, subcast_values=float))
                    ts_interpolation_station_distance.update(values.get("ts_interpolation_station_distance", {}))
                    values["ts_interpolation_station_distance"] = ts_interpolation_station_distance
                    values["ts_interpolation_use_nearby_station_distance"] = decide_arg(
                        values.get("ts_interpolation_use_nearby_station_distance"),
                        env.float("USE_NEARBY_STATION_DISTANCE", None),
                        _defaults["ts_interpolation_use_nearby_station_distance"],
                    )

        if values["cache_disable"]:
            log.info("Wetterdienst cache is disabled")
        else:
            log.info(f"Wetterdienst cache is enabled [CACHE_DIR: {values['cache_dir']}]")

        return values

    def __repr__(self) -> str:
        return json.dumps(self.model_dump(mode="json"))

    def __str__(self) -> str:
        return f"""Settings({json.dumps(self.model_dump(mode="json"), indent=4)})"""

    def reset(self) -> Settings:
        """Reset Wetterdienst Settings to start"""
        return self.__class__()

    @classmethod
    def default(cls) -> Settings:
        """Ignore environmental variables and use all default arguments as defined above"""
        return cls(ignore_env=True)
