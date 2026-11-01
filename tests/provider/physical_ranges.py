# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The physical range every value a provider returns is held to (GH-2615).

Sources mark a missing value with a number: -999, -99, -9999, 99.9, 9999. One that survives parsing is a value to every
caller, and the unit converter converts it: a mean over a column with a -999 in it is wrong without an error. The tests
of a provider mostly assert that a known value arrives, not that no impossible one does, so the check lives here once.
`conftest.py` applies it to the values the offline tests under `tests/provider` produce, and `test_value_stubs.py` to
the way each stubbed source writes a missing value. A remote test is left alone, since what a real source answers
with changes and a known leak would turn the CI matrix red until it is fixed; `WD_CHECK_RANGES_REMOTE=1` applies the
check to the remote tests as well, which is how a leak the offline fixtures do not hold is found.

The ranges are in the unit a value is returned in (`UnitConverter.targets`, the default of `Settings`; a unit type
converted to another unit is not checked) and are generous on purpose. They describe one reading, so a parameter whose
span grows with the resolution has a range per resolution (`RESOLUTION_RANGES`: the rain of a minute and of a day, the
sunshine of an hour and of a month, the sums of the daily snow depths over a month or a year, `snow_depth_sum`, which
only DWD has). They catch -999, not a cold night and not a hot road: a value outside is a sentinel, a unit that was
not converted or a column read from the wrong place, never a record. What they cannot catch is a sentinel that looks
like data, such as 99.9 % relative humidity, a -1 for "no snow" in a depth that may be read from a gauge, or 0 for "not
measured"; that part of #2615 is read off the source's own documentation, not off the numbers. Nor do they catch -999
where the range has to reach below it: a discharge (a tidal river runs backwards by thousands of cubic metres a
second), and a value that is converted on its way, such as -999 kJ/m² of radiation (-99.9 J/cm²) or -9999 mm of a depth
(-999.9 cm).

A range is looked up by canonical parameter name: first the one the parameter has at its resolution, then the
parameters that need their own, then a prefix, then the unit type. A parameter or unit type held to no range at all is
named with `None`, never left out, so that a new unit type fails
`test_every_unit_type_has_a_range_or_says_it_has_none` instead of going unchecked.

To hold a quantity to a different range, add it to `PARAMETER_RANGES` (one name) or `PREFIX_RANGES` (a family), or to
`RESOLUTION_RANGES` where the range depends on the resolution.

The values core judges a reading against one table of bounds per network (`model/plausibility_ranges.py`, the check
`range`, GH-2797), in the canonical unit, which is the unit this module holds a value to. A network may hold a quantity
narrower than the range here, never wider (a source whose own validated records stay far below the world's record, or
whose precision needs no slack, can say so, as an override with the argument beside it), and `test_physical_ranges.py`
holds every bound of the table to the range here. DWD observation (the wind speeds and the station and sea level
pressures) and Météo-France synop (the pressures, temperatures and amounts of rain) are judged on the quantities they
name, a bound of the world's records or inside it (GH-3135).

A value outside its range that carries the token `suspect:` is kept on purpose: a plausibility check in the mode `soft`
found it and left it, flagged (GH-3676), so the check here accepts it. Only the core's own verdict counts; a number
outside a range with no such token is still a sentinel the reader missed.
"""

from __future__ import annotations

from typing import NamedTuple

import polars as pl

from wetterdienst.metadata.parameter_table import PARAMETERS
from wetterdienst.model.plausibility import SUSPECT_TOKEN


class Bounds(NamedTuple):
    """The lowest and the highest value a quantity is returned with, both included."""

    low: float
    high: float


_INF = float("inf")

# per unit type, in the unit the default settings return it in. `None`: held to nothing, because the value is a code,
# a flag or a count whose range is the business of the single parameters below
UNIT_TYPE_RANGES: dict[str, Bounds | None] = {
    "angle": Bounds(0.0, 360.0),  # degree
    # mg/l; the one parameter of this type is `oxygen_level`, dissolved oxygen: 14.6 at saturation in water at 0 °C, a
    # little over 20 in algae-rich water in the afternoon. A substance that is dissolved in far greater amounts (the
    # 19_000 mg/l of chloride in sea water, which `wsv/pegel` declared until #3245) is no oxygen and needs a range
    # of its own in `PARAMETER_RANGES`, which this one would otherwise call a sentinel
    "concentration": Bounds(0.0, 30.0),
    "conductivity": Bounds(0.0, 80_000.0),  # µS/cm; sea water is 50_000
    # °C·day; the most of a year DMI publishes is 18_022.8 (base 19, 04416 Summit, Greenland, 2011), so the bound
    # leaves about 10 % above it
    "degree_day": Bounds(0.0, 20_000.0),
    "degree_hour": Bounds(0.0, 20_000.0),  # °C·h
    "dimensionless": None,
    "energy_per_area": Bounds(-100.0, 500_000.0),  # J/cm²; a year of global radiation is about 360_000
    "fraction": Bounds(0.0, 1.3),  # decimal; a hygrometer reads past 100 % now and then, a cloud cover does not
    "length_long": Bounds(0.0, 5_000.0),  # km
    "length_medium": Bounds(-500.0, 50_000.0),  # m; a groundwater level or a cloud base is a height
    "length_short": Bounds(-500.0, 3_000.0),  # cm
    "mass_per_volume": Bounds(0.0, 100.0),  # g/m³; saturated air at 40 °C holds 51
    "power_per_area": Bounds(-200.0, 2_000.0),  # W/m²; the solar constant is 1_361
    "precipitation": Bounds(0.0, 6_000.0),  # mm; a month of rain in the wettest places is 5_000 at most
    "precipitation_intensity": Bounds(0.0, 3_000.0),  # mm/h
    "pressure": Bounds(300.0, 1_100.0),  # hPa; Everest is 330, the highest sea level pressure 1_089 (WMO)
    "significant_weather": Bounds(0.0, 99.0),
    "speed": Bounds(0.0, 115.0),  # m/s; the fastest gust measured is 113.2 (WMO)
    "temperature": Bounds(-90.0, 100.0),  # °C; narrowed for the air below
    # a difference of temperatures, signed, in K: the spread of the coldest and the hottest places is under 150. The
    # `error_absolute_temperature_*` of MOSMIX are of this type and held to nothing below (GH-3688)
    "temperature_difference": Bounds(-150.0, 150.0),  # K
    "time": Bounds(0.0, 366 * 86_400.0),  # s; a year of sunshine is the most there is
    "turbidity": Bounds(0.0, 5_000.0),  # NTU
    # m³; the water held in a reservoir, from none to the 180 km³ of Lake Kariba, the largest reservoir by volume
    "volume": Bounds(0.0, 200_000_000_000.0),
    "volume_per_time": Bounds(-20_000.0, 300_000.0),  # m³/s; a tidal river runs backwards, the Amazon is 200_000
    "wind_scale": Bounds(0.0, 12.0),  # Beaufort
}

# a single canonical parameter, which beats its prefix and its unit type. `None`: held to nothing
PARAMETER_RANGES: dict[str, Bounds | None] = {
    # the error of a forecast against what was observed, signed and of any size
    "error_absolute_pressure_air_site": None,
    "error_absolute_temperature_air_2m": None,
    "error_absolute_temperature_dew_point_2m": None,
    "error_absolute_wind_direction": None,
    "error_absolute_wind_speed": None,
    # a change over three hours
    "pressure_air_site_delta_last_3h": Bounds(-100.0, 100.0),
    "pressure_vapor": Bounds(0.0, 100.0),  # hPa
    "pressure_vapor_mean": Bounds(0.0, 100.0),  # hPa
    # a deficit is the difference of two pressures, not a pressure of the air: 0 in saturated air, about 100 hPa (10
    # kPa) in the hottest, driest air. DMI's hourly values of the Julys of 2012 to 2026 run from -0.3 kPa (-3 hPa,
    # 06193, 2025-07-25) to 4.2 kPa (42 hPa), so the unit type's 300 to 1,100 hPa would call every one a sentinel
    # (see the page of dmi/observation)
    "vapor_pressure_deficit_mean": Bounds(-10.0, 100.0),  # hPa
    # a zenith angle runs from the sun overhead to below the horizon
    "sun_zenith_angle": Bounds(0.0, 180.0),
    "count_days_in_month": Bounds(28.0, 31.0),
    "count_hours_in_month": Bounds(672.0, 744.0),
    # a code that is a temperature or a cloud cover by name only
    "temperature_wet_ice_formation": None,
    "cloud_cover_total_measurement_method": None,
    "ph_value": Bounds(0.0, 14.0),
    "true_local_time_offset": Bounds(-86_400.0, 86_400.0),  # s
    "wave_period": Bounds(0.0, 3_600.0),  # s
    "wave_height_max": Bounds(0.0, 4_000.0),  # cm
    "wave_height_significant": Bounds(0.0, 4_000.0),  # cm
    "water_film_thickness": Bounds(0.0, 100.0),  # cm
    "snow_depth_new": Bounds(0.0, 500.0),  # cm in a day
    "snow_depth_new_max": Bounds(0.0, 500.0),
    "snow_depth_new_normal": Bounds(0.0, 500.0),
    "ice_on_water_thickness": Bounds(0.0, 500.0),  # cm
    "visibility": Bounds(0.0, 200_000.0),  # m
    "visibility_mean": Bounds(0.0, 200_000.0),  # m
    "temperature_humidex": Bounds(-90.0, 80.0),  # °C
    # the net long-wave balance of 3 hours is negative where the surface loses more than the sky returns: DWD's RadL3
    # runs down to -3,573 kJ/m² (-357 J/cm²) in the DMO data, which the -100 of the unit type would call a sentinel
    "radiation_long_wave_net_last_3h": Bounds(-1_000.0, 500.0),  # J/cm²
}

# a family of canonical parameters, by the start of its name; the first match wins
PREFIX_RANGES: tuple[tuple[str, Bounds | None], ...] = (
    # air, dew point and wet bulb are what a thermometer in a hut gives; surface, soil and road may be hotter
    ("temperature_air", Bounds(-90.0, 60.0)),
    ("temperature_dew", Bounds(-90.0, 60.0)),
    ("temperature_wet_", Bounds(-90.0, 60.0)),
    ("temperature_wind_chill", Bounds(-120.0, 60.0)),
    ("temperature_water", Bounds(-5.0, 70.0)),
    # a share of the sky or a probability: 101 % of cloud cover is a code, 9 oktas of 8 is an obscured sky
    ("cloud_cover_", Bounds(0.0, 1.0)),
    ("probability_", Bounds(0.0, 1.0)),
    # a count of days or hours: never negative, never more than a year
    ("count_days_", Bounds(0.0, 366.0)),
    ("count_hours_", Bounds(0.0, 8_784.0)),
    ("count_weather_type_", Bounds(0.0, 366.0)),
    # DWD's `Jultag`, which is the day of the year only for a date in the reference year: negative for a date before
    # it, above 366 for one after it. The 424 data files of the annual and immediate reporters, recent and historical
    # (25.3 million rows, overlapping releases counted each, 2026-10-14), run from -130 (winter rape, 24 August 2007
    # of 2008) to 443 (beech leaf fall, 20 March 1993 of 1992) and hold no sentinel, so the bounds leave a margin and
    # still keep -999 and 9999 out
    ("phenology_", Bounds(-200.0, 550.0)),
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
    ("frozen_ground_layer_thickness", Bounds(0.0, 1_000.0)),  # cm
    ("thawing_thickness_", Bounds(0.0, 1_000.0)),  # cm
)

# the range of a parameter at one resolution, which beats its range at any (`PARAMETER_RANGES`, the prefix, the unit
# type). A sum or a duration over the span of a reading has a range that grows with the span: 150 mm in 10 minutes is
# no reading, in a day it is, so 99.9 mm is a sentinel at the one and a reading at the other. Keyed by the resolution a
# dataset is declared with, then by exact canonical name: a maximum or a reading of the day, such as `snow_depth_max`,
# is no sum, and stays held to the range of one reading. A resolution that is no fixed span (`subdaily`, `6_hours`: a
# bucket of several sources' readings) has no entry, and a resolution without an entry for a name is held to the range
# of the name at any.
#
# Rain: the most that fell in 1 minute is 31 mm (Unionville, 1956), in 15 minutes 198 (Plumb Point, 1916), in an hour
# 401 (Shangdi, 1975), in a day 1,825 (Foc-Foc, 1966); a month and a year keep the 6,000 mm of the unit type. Sunshine
# cannot last longer than the span it is measured over, give or take a tenth for what a source rounds (DWD's urban
# 10-minute sunshine is written in hours with two decimals, 0.17 h for a full interval, which is 612 s). Snow: DWD's
# monthly and annual `snow_depth_sum` are the sum of the daily depths, `snow_depth_new` the sum of the new snow of the
# days; an Alpine station adds up to thousands of cm.
_DAY = 86_400.0


def _sunshine(seconds: float) -> Bounds:
    """Give the range of the sunshine of a span, which cannot be longer than the span, with a tenth to spare."""
    return Bounds(0.0, round(seconds * 1.1, 1))


RESOLUTION_RANGES: dict[str, dict[str, Bounds]] = {
    "1_minute": {"precipitation_amount": Bounds(0.0, 60.0), "sunshine_duration": _sunshine(60.0)},
    "5_minutes": {"precipitation_amount": Bounds(0.0, 150.0), "sunshine_duration": _sunshine(300.0)},
    "10_minutes": {"precipitation_amount": Bounds(0.0, 200.0), "sunshine_duration": _sunshine(600.0)},
    "15_minutes": {"precipitation_amount": Bounds(0.0, 300.0), "sunshine_duration": _sunshine(900.0)},
    "hourly": {"precipitation_amount": Bounds(0.0, 600.0), "sunshine_duration": _sunshine(3_600.0)},
    "daily": {"precipitation_amount": Bounds(0.0, 2_000.0), "sunshine_duration": _sunshine(_DAY)},
    "monthly": {
        "snow_depth_sum": Bounds(-50.0, 200_000.0),
        "snow_depth_new": Bounds(0.0, 200_000.0),
        "sunshine_duration": _sunshine(31 * _DAY),
    },
    "annual": {
        "snow_depth_sum": Bounds(-50.0, 200_000.0),
        "snow_depth_new": Bounds(0.0, 200_000.0),
    },
}


def bounds_for(name: str, resolution: str | None = None) -> Bounds | None:
    """Give the range a canonical parameter is held to at a resolution, or `None` where it is held to none.

    Without a `resolution`, or for one that has none of its own for `name`, the range is that of the parameter at any
    resolution. Raises a `KeyError` for a name that is not a canonical parameter, as that is a defect of the provider
    and not of the check.
    """
    if resolution is not None and name in RESOLUTION_RANGES.get(resolution, {}):
        return RESOLUTION_RANGES[resolution][name]
    if name in PARAMETER_RANGES:
        return PARAMETER_RANGES[name]
    unit_type = PARAMETERS[name].unit_type
    for prefix, bounds in PREFIX_RANGES:
        if name.startswith(prefix):
            return bounds
    return UNIT_TYPE_RANGES[unit_type]


def _canonical(parameter: str, names: dict[str, str] | None) -> str:
    """Give the canonical name of a `parameter` column string, read through `names` in either case."""
    return (names or {}).get(parameter) or (names or {}).get(parameter.lower()) or parameter


def out_of_range(df: pl.DataFrame, names: dict[str, str] | None = None, resolution: str | None = None) -> pl.DataFrame:
    """Give the rows of a tidy values frame whose value lies outside the range of its parameter.

    The frame needs the columns `parameter` and `value`; `resolution`, `dataset`, `station_id` and `timestamp` are
    carried along if it has them. `names` maps the strings of the `parameter` column to canonical names, for a frame
    that has not been humanized and so carries the source's own, whatever the case it is written in; without it the
    column is read as canonical names. `resolution` is that of the frame, where the frame has no such column; a frame
    of several resolutions is read at none of them unless it is given.
    """
    if df.is_empty() or "parameter" not in df.columns or "value" not in df.columns:
        return pl.DataFrame()
    parameters = [str(one) for one in df.get_column("parameter").unique().to_list()]
    low: dict[str, float] = {}
    high: dict[str, float] = {}
    resolutions = df.get_column("resolution").unique().to_list() if "resolution" in df.columns else []
    if resolution is None and len(resolutions) == 1:
        resolution = resolutions[0]
    for parameter in parameters:
        bounds = bounds_for(_canonical(parameter, names), resolution)
        if bounds is not None:
            low[parameter], high[parameter] = bounds
    if not low:
        return pl.DataFrame()
    parameter = pl.col("parameter")
    value = pl.col("value").cast(pl.Float64, strict=False)
    outside = (value < parameter.replace_strict(low, default=-_INF, return_dtype=pl.Float64)) | (
        value > parameter.replace_strict(high, default=_INF, return_dtype=pl.Float64)
    )
    keep = [
        column
        for column in ("resolution", "dataset", "station_id", "timestamp", "parameter", "value")
        if column in df.columns
    ]
    if "quality_flags" in df.columns:
        # a value that a soft plausibility check flagged `suspect:` is kept on purpose, outside its range or not
        # (GH-3676): the flag is the reader's own finding, so the number is not a sentinel the reader missed
        outside = outside & ~pl.col("quality_flags").str.contains(SUSPECT_TOKEN).fill_null(value=False)
    return df.filter(outside.fill_null(value=False)).select(keep)


def describe(
    found: pl.DataFrame, names: dict[str, str] | None = None, limit: int = 3, resolution: str | None = None
) -> str:
    """Say which parameters had values outside their range, with the lowest and the highest of each."""
    lines = []
    for (parameter,), rows in found.group_by(["parameter"], maintain_order=True):
        name = str(parameter)
        canonical = _canonical(name, names)
        values = rows.get_column("value").sort().to_list()
        shown = values[:limit] if len(values) <= 2 * limit else [*values[:limit], "...", *values[-limit:]]
        bounds = tuple(bounds_for(canonical, resolution) or ())
        lines.append(f"{canonical}: {len(values)} outside {bounds}: {shown}")
    return "; ".join(lines)
