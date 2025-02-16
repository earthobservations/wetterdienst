# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Settings for the wetterdienst package."""

from __future__ import annotations

import json
import logging
import platform
from pathlib import Path  # noqa: TCH003
from typing import Literal

import platformdirs
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from wetterdienst.core.timeseries.unit import UnitConverter
from wetterdienst.metadata.parameter import Parameter

log = logging.getLogger(__name__)

_UNIT_CONVERTER_TARGETS = UnitConverter().targets.keys()


class Settings(BaseSettings):
    """Settings for the wetterdienst package."""

    model_config = SettingsConfigDict(env_ignore_empty=True, env_prefix="WD_")

    cache_disable: bool = Field(default=False)
    cache_dir: Path = Field(default_factory=lambda: platformdirs.user_cache_dir(appname="wetterdienst"))
    fsspec_client_kwargs: dict = Field(
        default_factory=lambda: {
            "headers": {"User-Agent": f"wetterdienst/{__import__('wetterdienst').__version__} ({platform.system()})"},
        },
    )
    ts_humanize: bool = True
    ts_shape: Literal["wide", "long"] = "long"
    ts_convert_units: bool = True
    ts_unit_targets: dict[str, str] = Field(default_factory=dict)
    ts_skip_empty: bool = False
    ts_skip_threshold: float = 0.95
    ts_skip_criteria: Literal["min", "mean", "max"] = "min"
    ts_complete: bool = False
    ts_drop_nulls: bool = True
    ts_interpolation_station_distance: dict[str, float] = Field(
        default_factory=lambda: {
            "default": 40.0,
            Parameter.PRECIPITATION_HEIGHT.value.lower(): 20.0,
        },
    )
    ts_interpolation_use_nearby_station_distance: float = 1.0

    @field_validator("ts_unit_targets", mode="before")
    @classmethod
    def validate_ts_unit_targets_before(cls, values: dict[str, str] | None) -> dict[str, str]:
        """Validate the unit targets."""
        return values or {}

    @field_validator("ts_unit_targets", mode="after")
    @classmethod
    def validate_ts_unit_targets_after(cls, values: dict[str, str]) -> dict[str, str]:
        """Validate the unit targets."""
        if not values.keys() <= _UNIT_CONVERTER_TARGETS:
            msg = f"Invalid unit targets: one of {set(values.keys())} not in {set(_UNIT_CONVERTER_TARGETS)}"
            raise ValueError(msg)
        return values

    # make ts_interpolation_station_distance update but not replace the default values
    @field_validator("ts_interpolation_station_distance", mode="before")
    @classmethod
    def validate_ts_interpolation_station_distance(cls, values: dict[str, float] | None) -> dict[str, float]:
        """Validate the interpolation station distance settings."""
        default = cls.model_fields["ts_interpolation_station_distance"].default_factory()
        if not values:
            return default
        return default | values

    @model_validator(mode="after")
    def validate(self) -> Settings:
        """Validate the settings."""
        if self.cache_disable:
            log.info("Wetterdienst cache is disabled")
        else:
            log.info(f"Wetterdienst cache is enabled [CACHE_DIR:{self.cache_dir}]")
        return self

    def __repr__(self) -> str:
        """Return the settings as a JSON string."""
        return json.dumps(self.model_dump(mode="json"))

    def __str__(self) -> str:
        """Return the settings as a string."""
        return f"""Settings({json.dumps(self.model_dump(mode="json"), indent=4)})"""
