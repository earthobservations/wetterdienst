# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The physical range every value a provider returns is held to (GH-2615).

Sources mark a missing value with a number: -999, -99, -9999, 99.9, 9999. One that survives parsing is a value to every
caller, and the unit converter converts it: a mean over a column with a -999 in it is wrong without an error. The tests
of a provider mostly assert that a known value arrives, not that no impossible one does, so the check lives here once.
`conftest.py` applies it to every values frame a provider test produces, and `test_value_stubs.py` to the way each
stubbed source writes a missing value.

The ranges are in the unit a value is returned in (`UnitConverter.targets`, the default of `Settings`) and are
generous on purpose. They catch -999, not a cold night and not a hot road: a value outside is a sentinel, a unit that
was not converted or a column read from the wrong place, never a record. What they cannot catch is a sentinel that
looks like data, such as 99.9 % relative humidity, a -1 for "no snow" in a depth that may be read from a gauge, or 0
for "not measured"; that part of #2615 is read off the source's own documentation, not off the numbers.

A range is looked up by canonical parameter name: first the parameters that need their own, then a prefix, then the
unit type. A parameter or unit type held to no range at all is named with `None`, never left out, so that a new unit
type fails `test_every_unit_type_has_a_range_or_says_it_has_none` instead of going unchecked.

To hold a quantity to a different range, add it to `PARAMETER_RANGES` (one name) or `PREFIX_RANGES` (a family).
"""

from __future__ import annotations

from typing import NamedTuple

import polars as pl

from wetterdienst.metadata.parameter_table import PARAMETERS


class Bounds(NamedTuple):
    """The lowest and the highest value a quantity is returned with, both included."""

    low: float
    high: float


_INF = float("inf")

# per unit type, in the unit the default settings return it in. `None`: held to nothing, because the value is a code,
# a flag or a count whose range is the business of the single parameters below
UNIT_TYPE_RANGES: dict[str, Bounds | None] = {
    "angle": Bounds(0.0, 360.0),  # degree
    "concentration": Bounds(0.0, 40_000.0),  # mg/l; sea water carries 19_000 mg/l of chloride
    "conductivity": Bounds(0.0, 80_000.0),  # µS/cm; sea water is 50_000
    "degree_day": Bounds(0.0, 20_000.0),  # °C·day; a year of heating in the cold north is below 10_000
    "degree_hour": Bounds(0.0, 20_000.0),  # °C·h
    "dimensionless": None,
    "energy_per_area": Bounds(-100.0, 200_000.0),  # J/cm²; a year of global radiation is 60_000 to 100_000
    "fraction": Bounds(0.0, 1.3),  # decimal; a hygrometer reads past 100 % now and then
    "length_long": Bounds(0.0, 5_000.0),  # km
    "length_medium": Bounds(-500.0, 50_000.0),  # m; a groundwater level or a cloud base is a height
    "length_short": Bounds(-500.0, 3_000.0),  # cm
    "mass_per_volume": Bounds(0.0, 100.0),  # g/m³; saturated air at 40 °C holds 51
    "power_per_area": Bounds(-200.0, 2_000.0),  # W/m²; the solar constant is 1_361
    "precipitation": Bounds(0.0, 6_000.0),  # mm; a month of rain in the wettest places is 5_000 at most
    "precipitation_intensity": Bounds(0.0, 3_000.0),  # mm/h
    "pressure": Bounds(300.0, 1_100.0),  # hPa; Everest is 330, the highest sea level pressure 1_084
    "significant_weather": Bounds(0.0, 99.0),
    "speed": Bounds(0.0, 115.0),  # m/s; the fastest gust measured is 113
    "temperature": Bounds(-90.0, 100.0),  # °C; narrowed for the air below
    "time": Bounds(0.0, 366 * 86_400.0),  # s; a year of sunshine is the most there is
    "turbidity": Bounds(0.0, 5_000.0),  # NTU
    "volume_per_time": Bounds(-20_000.0, 300_000.0),  # m³/s; a tidal river runs backwards, the Amazon is 200_000
    "wind_scale": Bounds(0.0, 12.0),  # Beaufort
}

# a single canonical parameter, which beats its prefix and its unit type. `None`: held to nothing
PARAMETER_RANGES: dict[str, Bounds | None] = {
    # the error of a forecast against what was observed, signed and of any size
    "error_absolute_pressure_air_site": None,
    "error_absolute_temperature_air_mean_2m": None,
    "error_absolute_temperature_dew_point_mean_2m": None,
    "error_absolute_wind_direction": None,
    "error_absolute_wind_speed": None,
    # a change over three hours
    "pressure_air_site_delta_last_3h": Bounds(-100.0, 100.0),
    "pressure_vapor": Bounds(0.0, 100.0),  # hPa
    # a zenith angle runs from the sun overhead to below the horizon
    "sun_zenith_angle": Bounds(0.0, 180.0),
    "count_days_in_month": Bounds(28.0, 31.0),
    "count_hours_in_month": Bounds(672.0, 744.0),
    # a code that is a temperature by name only
    "temperature_wet_ice_formation": None,
    "ph_value": Bounds(0.0, 14.0),
    "oxygen_level": Bounds(0.0, 30.0),  # mg/l
    "true_local_time_offset": Bounds(-86_400.0, 86_400.0),  # s
    "wave_period": Bounds(0.0, 3_600.0),  # s
    "wave_height_max": Bounds(0.0, 4_000.0),  # cm
    "wave_height_significant": Bounds(0.0, 4_000.0),  # cm
    "water_film_thickness": Bounds(0.0, 100.0),  # cm
    "snow_depth_new": Bounds(0.0, 500.0),  # cm in a day
    "snow_depth_new_max": Bounds(0.0, 500.0),
    "snow_depth_new_normal": Bounds(0.0, 500.0),
    "visibility": Bounds(0.0, 200_000.0),  # m
    "cloud_base_convective": Bounds(0.0, 25_000.0),  # m
    "temperature_humidex": Bounds(-90.0, 80.0),  # °C
}

# a family of canonical parameters, by the start of its name; the first match wins
PREFIX_RANGES: tuple[tuple[str, Bounds | None], ...] = (
    # air, dew point and wet bulb are what a thermometer in a hut gives; surface, soil and road may be hotter
    ("temperature_air", Bounds(-90.0, 60.0)),
    ("temperature_dew", Bounds(-90.0, 60.0)),
    ("temperature_wet_", Bounds(-90.0, 60.0)),
    ("temperature_wind_chill", Bounds(-120.0, 60.0)),
    ("temperature_water", Bounds(-5.0, 70.0)),
    # a count of days or hours, a day of the year: never negative, never more than a year
    ("count_days_", Bounds(0.0, 366.0)),
    ("count_hours_", Bounds(0.0, 8_784.0)),
    ("count_weather_type_", Bounds(0.0, 366.0)),
    ("phenology_", Bounds(0.0, 366.0)),
    # the share of field capacity, which saturated soil goes past
    ("soil_moisture_", Bounds(0.0, 3.0)),
    # a gauge reads from a datum of its own, and a reservoir's level may be given in metres above the sea: -9999 is
    # outside, a reading of -999 cm is not
    ("stage", Bounds(-5_000.0, 100_000.0)),  # cm
    ("groundwater_level", Bounds(-500.0, 5_000.0)),  # m
    # MeteoSwiss' automatic gauge at PLF reads -1 to -5 cm in 11 % of its hours, a spread and not a code, so a -1 cannot
    # be told from a reading here (the -1 of Geosphere's "no snow" is found by its stub)
    ("snow_depth", Bounds(-50.0, 1_500.0)),  # cm
    ("water_equivalent_snow_depth", Bounds(0.0, 5_000.0)),  # mm
)


def bounds_for(name: str) -> Bounds | None:
    """Give the range a canonical parameter is held to, or `None` where it is held to none.

    Raises a `KeyError` for a name that is not a canonical parameter, as that is a defect of the provider and not
    of the check.
    """
    if name in PARAMETER_RANGES:
        return PARAMETER_RANGES[name]
    unit_type = PARAMETERS[name].unit_type
    for prefix, bounds in PREFIX_RANGES:
        if name.startswith(prefix):
            return bounds
    return UNIT_TYPE_RANGES[unit_type]


def out_of_range(df: pl.DataFrame, names: dict[str, str] | None = None) -> pl.DataFrame:
    """Give the rows of a tidy values frame whose value lies outside the range of its parameter.

    The frame needs the columns `parameter` and `value`; `resolution`, `dataset`, `station_id` and `timestamp` are
    carried along if it has them. `names` maps the strings of the `parameter` column to canonical names, for a frame
    that has not been humanized and so carries the source's own; without it the column is read as canonical names.
    """
    if df.is_empty() or "parameter" not in df.columns or "value" not in df.columns:
        return pl.DataFrame()
    parameters = [str(one) for one in df.get_column("parameter").cast(pl.String).unique().to_list()]
    low: dict[str, float] = {}
    high: dict[str, float] = {}
    for parameter in parameters:
        bounds = bounds_for((names or {}).get(parameter, parameter))
        if bounds is not None:
            low[parameter], high[parameter] = bounds
    if not low:
        return pl.DataFrame()
    parameter = pl.col("parameter").cast(pl.String)
    value = pl.col("value").cast(pl.Float64, strict=False)
    outside = (value < parameter.replace_strict(low, default=-_INF, return_dtype=pl.Float64)) | (
        value > parameter.replace_strict(high, default=_INF, return_dtype=pl.Float64)
    )
    keep = [
        column
        for column in ("resolution", "dataset", "station_id", "timestamp", "parameter", "value")
        if column in df.columns
    ]
    return df.filter(outside.fill_null(value=False)).select(keep)


def describe(found: pl.DataFrame, names: dict[str, str] | None = None, limit: int = 3) -> str:
    """Say which parameters had values outside their range, with the lowest and the highest of each."""
    lines = []
    for (parameter,), rows in found.group_by(["parameter"], maintain_order=True):
        canonical = (names or {}).get(str(parameter), str(parameter))
        values = rows.get_column("value").sort().to_list()
        shown = values[:limit] if len(values) <= 2 * limit else [*values[:limit], "...", *values[-limit:]]
        lines.append(f"{canonical}: {len(values)} outside {tuple(bounds_for(canonical) or ())}: {shown}")
    return "; ".join(lines)
