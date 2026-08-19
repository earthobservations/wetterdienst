# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Settings for the wetterdienst package."""

from __future__ import annotations

import json
import logging
import platform
from collections import defaultdict
from pathlib import Path
from typing import Annotated, Literal

import platformdirs
from pydantic import BaseModel, Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from wetterdienst.metadata.parameter_table import PARAMETER_TABLE, PARAMETERS
from wetterdienst.model.unit import UnitConverter

log = logging.getLogger(__name__)

_UNIT_CONVERTER_TARGETS = UnitConverter().targets.keys()


class Auth(BaseModel):
    """Authentication credentials for providers requiring API keys."""

    aemet: str | None = Field(default=None)
    knmi: str | None = Field(default=None)
    metno_frost: tuple[str, str] | None = Field(default=None)
    ceda: tuple[str, str] | None = Field(default=None)

    @field_validator("metno_frost", mode="before")
    @classmethod
    def validate_metno_frost(cls, value: tuple[str, str] | str | None) -> tuple[str, str] | None:  # noqa: D102
        if value is None:
            return None
        if isinstance(value, str):
            return value, ""
        as_tuple = tuple(value)
        if len(as_tuple) != 2:
            msg = f"metno_frost must be a (client_id, secret) pair, got {len(as_tuple)} element(s)"
            raise ValueError(msg)
        return str(as_tuple[0]), str(as_tuple[1])

    @field_validator("ceda", mode="before")
    @classmethod
    def validate_ceda(cls, value: tuple[str, str] | str | None) -> tuple[str, str] | None:
        """Parse the CEDA (username, password) pair, e.g. from ``WD_AUTH__CEDA=username:password``."""
        if value is None:
            return None
        if isinstance(value, str):
            username, sep, password = value.partition(":")
            if not sep:
                msg = "ceda must be given as 'username:password'"
                raise ValueError(msg)
            return username, password
        as_tuple = tuple(value)
        if len(as_tuple) != 2:
            msg = f"ceda must be a (username, password) pair, got {len(as_tuple)} element(s)"
            raise ValueError(msg)
        return str(as_tuple[0]), str(as_tuple[1])


#: how far a station may be from the target point to still be used, in km
_STATION_DISTANCE_HOMOGENEOUS = 40.0
#: the same for a quantity that decorrelates faster -- see `CanonicalParameter.interpolation`
_STATION_DISTANCE_HETEROGENEOUS = 20.0


def _build_geo_station_distance(
    homogeneous: float,
    heterogeneous: float,
    overrides: dict[str, float],
) -> defaultdict[str, float]:
    """Build the per-parameter search radius from the two radii, the parameter table and overrides.

    Which names get the shorter radius used to be written out here, a copy of a classification the
    table already holds. Only those names are put in the dict; the default factory answers for
    every other parameter, so the setting a user sees and overrides stays the short list of
    exceptions rather than all 514 names.
    """
    d: defaultdict[str, float] = defaultdict(lambda: homogeneous)
    for parameter in PARAMETER_TABLE:
        if parameter.interpolation == "heterogeneous":
            d[parameter.name] = heterogeneous
    d.update(overrides)
    return d


class Settings(BaseSettings):
    """Settings for the wetterdienst package."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_ignore_empty=True,
        env_prefix="WD_",
        env_nested_delimiter="__",
    )

    cache_disable: bool = Field(default=False)
    cache_dir: Path = Field(default_factory=lambda: Path(platformdirs.user_cache_dir(appname="wetterdienst")))
    fsspec_client_kwargs: dict = Field(
        default_factory=lambda: {
            "headers": {"User-Agent": f"wetterdienst/{__import__('wetterdienst').__version__} ({platform.system()})"},
            "timeout": 30,
        },
    )
    auth: Auth = Field(default_factory=Auth)
    use_certifi: bool = Field(default=False)
    # opt-in: parse DWD radar BUFR files into a polars DataFrame (RadarResult.df). Requires the
    # optional eccodes + pdbufr dependencies; off by default because parsing is expensive.
    read_bufr: bool = Field(default=False)
    ts_humanize: bool = True
    ts_shape: Literal["wide", "long"] = "long"
    ts_convert_units: bool = True
    ts_unit_targets: dict[str, str] = Field(default_factory=dict)
    ts_skip_empty: bool = False
    ts_skip_threshold: float = 0.95
    ts_skip_criteria: Literal["min", "mean", "max"] = "min"
    ts_complete: bool = False
    ts_drop_nulls: bool = True
    # how far a station may be from the target point to still be interpolated or summarized from.
    # the two radii follow `CanonicalParameter.interpolation`: a homogeneous quantity such as air
    # temperature varies slowly across a region and may be drawn from farther away than a
    # heterogeneous one such as precipitation, which decorrelates within a few tens of kilometres
    ts_geo_station_distance_homogeneous: Annotated[float, Field(ge=0)] = _STATION_DISTANCE_HOMOGENEOUS
    ts_geo_station_distance_heterogeneous: Annotated[float, Field(ge=0)] = _STATION_DISTANCE_HETEROGENEOUS
    # per-parameter overrides of the two radii above, given as canonical parameter names. holds the
    # overrides alone while validating and the effective mapping -- radii, table and overrides --
    # from `expand_ts_geo_station_distance` on
    ts_geo_station_distance: defaultdict[str, float] = Field(default_factory=dict)
    # this setting is used to define how far away a station can be so that no interpolation is done
    # but instead the station is used directly
    ts_geo_use_nearby_station_distance: Annotated[float, Field(strict=True, ge=0)] | None = 1.0
    # this rather complicated setting is used in the process of figuring out how many additional stations will be used
    # the gain defines how many additional timestamps can be interpolated by adding the specific station and thus
    # getting more timestamps with the required minimum of four values
    # so basically this setting considers the extra effort against the gain of additional interpolated timestamps
    ts_geo_min_gain_of_value_pairs: Annotated[float, Field(strict=True, ge=0)] = 0.10
    # this setting defines how many additional stations are used in the interpolation process independent of the gain
    # of value pairs, so if the gain is not reached anymore, there at least `num` more stations added to the list
    ts_geo_num_additional_stations: Annotated[int, Field(strict=True, ge=0)] = 3

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

    @field_validator("ts_geo_station_distance", mode="before")
    @classmethod
    def validate_ts_geo_station_distance_keys(cls, values: dict[str, float] | None) -> dict[str, float]:
        """Check the overridden parameter names, which used to be taken on trust.

        A name that is not a canonical parameter can never be looked up, so the override silently
        did nothing and the parameter the user meant kept its default radius -- a typo was
        indistinguishable from having set nothing at all.
        """
        if not values:
            return {}
        if "default" in values:
            msg = (
                "the 'default' key of ts_geo_station_distance is gone, as it replaced the fallback radius and "
                "the pre-populated per-parameter ones alike; set ts_geo_station_distance_homogeneous and "
                "ts_geo_station_distance_heterogeneous instead"
            )
            raise ValueError(msg)
        unknown = sorted(set(values) - PARAMETERS.keys())
        if unknown:
            msg = f"Invalid parameters in ts_geo_station_distance: {unknown} not in the canonical parameters"
            raise ValueError(msg)
        never_interpolated = sorted(name for name in values if not PARAMETERS[name].interpolation)
        if never_interpolated:
            log.warning(
                f"option 'ts_geo_station_distance' sets a radius for {never_interpolated}, which are never "
                "interpolated, and is thus ignored for them in this request.",
            )
        return values

    @field_validator("ts_geo_station_distance", mode="after")
    @classmethod
    def validate_ts_geo_station_distance_values(cls, values: dict[str, float]) -> dict[str, float]:
        """Reject negative radii, as `ts_geo_use_nearby_station_distance` next to it already does."""
        negative = sorted(name for name, distance in values.items() if distance < 0)
        if negative:
            msg = f"Negative distances in ts_geo_station_distance: {negative}"
            raise ValueError(msg)
        return values

    @model_validator(mode="after")
    def expand_ts_geo_station_distance(self) -> Settings:
        """Layer the per-parameter overrides onto the two radii and the parameter table.

        Built here rather than in the field's default so that the two radii, which are fields of
        their own and may themselves be overridden, are already known.
        """
        self.ts_geo_station_distance = _build_geo_station_distance(
            self.ts_geo_station_distance_homogeneous,
            self.ts_geo_station_distance_heterogeneous,
            self.ts_geo_station_distance,
        )
        return self

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
