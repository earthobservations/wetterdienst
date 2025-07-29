# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Settings for the wetterdienst package."""

from __future__ import annotations

import json
import logging
import platform
from collections import defaultdict
from pathlib import Path  # noqa: TC003
from typing import Literal

import platformdirs
from pydantic import Field, confloat, conint, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from wetterdienst.metadata.parameter import Parameter
from wetterdienst.model.unit import UnitConverter

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
    # this setting is used to define for each parameter how far away a station can be to be used for interpolation
    # the default is 40km, but for precipitation height it is 20km
    # parameters such as precipitation height are more local and thus need a smaller distance, while parameters such as
    # temperature can be interpolated over a larger distance
    ts_interp_station_distance: defaultdict[str, float] = Field(
        default_factory=lambda: defaultdict(lambda: 40) | {Parameter.PRECIPITATION_HEIGHT.value.lower(): 20}
    )
    # this setting is used to define how far away a station can be so that no interpolation is done
    # but instead the station is used directly
    ts_interp_use_nearby_station_distance: confloat(ge=0) | None = 1.0
    # this rather complicated setting is used in the process of figuring out how many additional stations will be used
    # the gain defines how many additional timestamps can be interpolated by adding the specific station and thus
    # getting more timestamps with the required minimum of four values
    # so basically this setting considers the extra effort against the gain of additional interpolated timestamps
    ts_interp_min_gain_of_value_pairs: confloat(gt=0.0) = 0.10
    # this settings defines how many additional stations are used in the interpolation process independent from the gain
    # of value pairs, so if the gain is not reached anymore, there at least `num` more stations added to the list
    ts_interp_num_additional_stations: conint(ge=0) = 3

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

    # make ts_interp_station_distance update but not replace the default values
    @field_validator("ts_interp_station_distance", mode="before")
    @classmethod
    def validate_ts_interp_station_distance(cls, values: dict[str, float] | None) -> dict[str, float]:
        """Validate the interpolation station distance settings."""
        default = cls.model_fields["ts_interp_station_distance"].default_factory()
        if not values:
            return default
        return default | values

    @property
    def ts_tidy(self) -> bool:
        """Return whether the time series is in tidy format."""
        return self.ts_shape == "long"

    @model_validator(mode="after")
    def validate(self) -> Settings:
        """Validate the settings."""
        if self.ts_shape != "long":
            self.ts_drop_nulls = False
            log.info(
                "option 'ts_drop_nulls' is only available with option 'ts_shape=long' and "
                "is thus ignored in this request.",
            )
        if self.ts_drop_nulls:
            self.ts_complete = False
            log.info(
                "option 'ts_complete' is only available with option 'ts_drop_nulls=False' and "
                "is thus ignored in this request.",
            )
        # skip empty stations
        if not self.ts_complete:
            self.ts_skip_empty = False
            log.info(
                "option 'skip_empty' is only available with options `ts_drop_nulls=False` and 'ts_complete=True' "
                "and is thus ignored in this request.",
            )
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
