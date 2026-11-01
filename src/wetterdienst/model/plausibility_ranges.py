# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The one table of bounds of the ``range`` check: the same for every provider (GH-3681).

The values core judges a reading in the canonical unit of its unit type (``UnitConverter().targets``: °C, hPa, m/s,
mm, J/cm², a fraction as a decimal, seconds), whatever unit the source writes and whatever unit the caller asks for,
so a bound is written once per quantity. It is written once for all providers, too: a quantity has the bound of the
quantity and not of the network that serves it. ``bounds_for`` gives the bound of a canonical parameter at a
resolution, the lookup being, in this order, the name, the rain of the last so many hours, a family of names (by
prefix), the unit type. A quantity whose bound grows with the span it is measured over (the rain of a minute and of a
day) is given by resolution.

``tests/provider/physical_ranges.py`` reads the same table for the remote check of the provider tests and for the
parameters a test serves; it keeps no bounds of its own (GH-3681).

Where the bounds come from. A bound is the first of these that exists, rounded outward to a round number (31.2 is 40,
1,144 is 1,150, 1,825 is 1,850, 26,470 is 30,000; the irradiance of 2,000 W/m² is a round number between the 1,600
of WMO-No. 488 and the 2,141 of BSRN), so that it finds a
value that is a defect of the source and never a record:

1. **W**: the extreme the WMO World Weather and Climate Extremes Archive lists, table of 31 July 2025
   (https://public.wmo.int/sites/default/files/2025-07/Table_Records_25Jul2025.pdf);
2. **D**: a limit that follows from the definition of the quantity (a share is 0 to 100 %, a duration is not longer than
   its span, a count of days is not more than the days there are) or from a derivation, stated beside it;
3. **N**: a named source, cited beside the bound.

A quantity with neither a record nor a definition that bounds it above is held to its definition alone, at least 0, and
has no upper end. A quantity that is derived from others (wind chill, humidex, evaporation, the forecast errors
``error_absolute_*``, the net radiation of DMO) or that is a code or a flag is not checked: its inputs are, and a code
has no range. Nor are hydrology gauges: a stage, a discharge, a groundwater level, a distance to the gauge and a flow
speed have a datum of their own, and a tidal river runs backwards.

No WMO guide sets a fixed table for every provider: the limits of WMO-No. 488 (2010, updated 2017) Appendix VI.2 are for
the 1-minute values of an automatic weather station and cut records the Archive lists (wind speed 75 m/s against 95 m/s
of Typhoon Nancy), the tests of WMO-No. 1269 (2021) are relative to the station (percentiles of its own last 30 years)
and the current WMO-No. 305 has no chapter on quality control. The table is compared with them, not taken from them.

The sources, by quantity:

- Air temperature -90 to 60 °C (W): 56.7 °C (Furnace Creek, 1913-07-10), -89.2 °C (Vostok, 1983-07-21). The wet bulb
  lies between the dew point and the air (D), so it has the same bounds. The dew point is -100 to 60 °C (N): HadISD
  (Dunn et al. 2012) holds a minimum of -100.0 and ISD one of -98.2 °C, the upper end is the air's.
- Soil, surface, concrete and radiant temperature -90 to 100 °C (N): the lower end is the air's (D); the highest
  ground temperature is 93.9 °C (201 °F, Furnace Creek, 1972-07-15, US National Park Service; Wikipedia calls it
  unverified). Water temperature -5 to 50 °C (N): MADIS holds the sea surface to -2.0 to 40 °C, rounded outward; the
  bound is applied to river water and the evaporation pan as well, for which no source is named.
- Pressure at sea level, and the altimeter setting of the METAR (``pressure_air_site_reduced``, a station pressure
  corrected to sea level), 850 to 1100 hPa (W): the highest is 1,089.1 hPa (Tosontsengel, 2004-12-30, above 750 m;
  1,083.8 hPa, Agata, 1968-12-31, below 750 m), the lowest 870 hPa (Typhoon Tip, 1979-10-12). At the station 300 to
  1100 hPa (D, N): the upper end is the sea level class, for the lower end Everest reads about 330 hPa and WMO-No. 305
  (1993, withdrawn) called a station pressure below 300 or above 1100 hPa erroneous. A pressure change over 3 hours is
  -50 to 50 hPa (N): MADIS holds 0 to 30.5 and WMO-No. 305 (1993) 9 hPa. Vapour pressure 0 to 60 hPa (D): the
  saturation pressure at 35 °C, the highest dew point on record (Dhahran, 2003-07-08, NOAA).
  The vapour pressure deficit is -10 to 200 hPa (D): the saturation pressure at the 60 °C of the air bound is 199 hPa
  by Magnus, and DMI's slightly negative hours (-3 hPa) stay.
- Wind: the highest gust is 113.2 m/s (W, Barrow Island, 1996-04-10), so a gust and a mean wind (which cannot exceed
  the gust of its interval, D) are 0 to 115 m/s; a direction is 0 to 360 and a zenith angle 0 to 180 degrees, Beaufort
  0 to 12 (D); the run of wind in a day is 115 m/s for 86,400 s, 9,936 km (D).
- Rain, by the span it fell in (W): 31.2 mm in 1 minute (Unionville MD, 1956-07-04), so 40; 305 mm in 60 minutes (Holt
  MO, 1947-06-22), so 350, which also holds the 5 to 30 minutes in it; 1,144 mm in 12 hours (Foc-Foc, 1966-01-07/08),
  so 1,150, which also holds the 2 to 12 hours in it; 1,825 mm in 24 hours (Foc-Foc), so 1,850; 2,493, 3,930 and 4,936
  mm in 48, 72 and 96 hours, so 2,500, 4,000 and 5,000; 26,470 mm in 12 months (Cherrapunji, 1860/61), so 30,000 a
  year. A month is 10,000 mm (N): 9,300 mm fell in July 1861 at Cherrapunji (Bureau of Meteorology, "World's record
  rainfall", secondary). The one documented exceedance is Shangdi (Inner Mongolia, 1975-08-01): 401 mm in 60 minutes,
  which is in the lists of the Bureau of Meteorology and the NWS but not in the WMO table. A rain intensity is 31.2 mm
  in a minute, 1,872 mm/h, so 2,000 (W).
- Snow depth -10 to 1,200 cm (N): the ISD field runs to 1,200 cm and Durre et al. (2010) hold 1,146 cm (Tamarack CA);
  the automatic gauge of MeteoSwiss at PLF reads -1 to -5 cm in 11 % of its hours, though the definition says 0. New
  snow in a day 0 to 200 cm (N, Durre et al. 192.5 cm); sums of the daily depths over a month and a year (ECCC's
  normal snowfall of a month included) are the bound times the days (D). Water equivalent, thicknesses of frozen
  ground, thawing and ice are at least 0 (D).
- Sunshine and the duration of precipitation: not longer than the span they are measured over, and 5 % more for a
  reading of a resolution (D, the day-length margin of ECA&D; DWD's urban 10-minute sunshine is written in hours with
  two decimals, 0.17 h for a full interval, which is 612 s, and RMI's 63.86 min in an hour, 3,831.6 s, is above
  3,780).
- Relative humidity 0 to 100 % (D), cloud cover, the probabilities of a model, the relative sunshine and the snow
  cover 0 to 100 % (D); soil moisture is a share of the field capacity, which saturated soil goes past (D, at least 0).
- Radiation: the short-wave irradiance 0 to 2,000 W/m² (N): WMO-No. 488 (App. VI.2) holds 0 to 1,600 and BSRN 1.5
  times the solar constant (1,361 W/m²) times the cosine of the zenith angle to the 1.2 plus 100 W/m², 2,141 at the
  zenith; the lower bound is 0 as the definition says. A sum of short-wave radiation is at most the solar constant
  times the span in 10 minutes and an hour (D): 100 J/cm² (82 by that) and 500 (490); a day is 6,000 J/cm², 60 MJ/m²
  (the top of the atmosphere at 82 degrees north in midsummer is 48), and a month and a year are that times their
  days, 186,000 and 2,200,000 (the sunniest places receive about 900,000 J/cm² in a year); the long-wave radiation
  from the sky is at least 0.
- Degree days: the heating of a day is at most the 25 °C base plus the air record (D), 115, a month 3,600, a year
  42,100; the cooling of a day is the air bound (60 °C) less a base of 15 °C, 45, rounded up to 50 (D), a month 1,600,
  a year 18,300. A degree hour, a volume, a conductivity, a turbidity and a dissolved substance are at least 0 (D).
- Counts: of days at most 31 in a month and 366 otherwise, of hours 744 in a month and 8,784 otherwise (D); the days
  of a month 28 to 31 and its hours 672 to 744. A pH is 0 to 14 (D).
- Visibility 0 to 200 km (N, ISD 160 km, MADIS 160.9 km), the height of a cloud 0 to 25 km (N, ISD 22 km), absolute
  humidity 0 to 40 g/m³ (D, saturated air at the dew point record holds 39.5), the offset of solar time from UTC 12
  hours and the equation of time (D).
- Phenology: the day number of DWD's ``Jultag`` runs from -130 (winter rape, 2007-08-24 of the reference year 2008) to
  443 (beech leaf fall, 1993-03-20 of 1992) in the 424 data files of the immediate and annual reporters (25.3 million
  rows, 2026-10-14, N), so -200 to 550.

The bounds find a value that is a defect of the source; they do not find a value that is wrong and plausible, a regional
defect a world table cannot see (a gust of 81.5 m/s in Belgium) or a number the source marks itself (DMI's
``validity: false``). What only a provider knows it hands the core as rules (``model/judge.py``), and
``docs/data/plausibility.md`` lists what the table cannot catch.
"""

from __future__ import annotations

import math
import re
from collections.abc import Mapping
from typing import NamedTuple

from wetterdienst.metadata.parameter_table import PARAMETERS


class Bounds(NamedTuple):
    """The lowest and the highest value a quantity may have, both included."""

    low: float
    high: float


Range = Bounds | Mapping[str, Bounds] | None
"""A bound for any resolution, a bound by resolution (``"*"`` for the others), or none: held to nothing."""

_INF = math.inf
_DAY = 86_400.0
#: the hours a reading of each resolution stands for, for the quantities that grow with the span; a subdaily value is
#: the bucket of the 3-hourly readings of DWD and the SYNOP of Météo-France
SPAN_HOURS: dict[str, float] = {
    "1_minute": 1 / 60,
    "5_minutes": 5 / 60,
    "6_minutes": 0.1,
    "10_minutes": 10 / 60,
    "15_minutes": 0.25,
    "hourly": 1.0,
    "6_hours": 6.0,
    "subdaily": 3.0,
    "daily": 24.0,
    "monthly": 31 * 24.0,
    "annual": 366 * 24.0,
}
_DAYS = {"monthly": 31, "annual": 366}


def _rain(hours: float) -> float:
    """Give the most rain that fell in a span of hours, from the records of the WMO (rounded outward)."""
    if hours <= 1 / 60:
        return 40.0  # 31.2 mm in 1 minute
    if hours <= 1:
        return 350.0  # 305 mm in 60 minutes; the 5 to 30 minutes are inside it
    if hours <= 12:
        return 1_150.0  # 1,144 mm in 12 hours; the 2 to 12 hours are inside it
    if hours <= 24:
        return 1_850.0  # 1,825 mm in 24 hours
    if hours <= 48:
        return 2_500.0  # 2,493 mm in 48 hours
    if hours <= 72:
        return 4_000.0  # 3,930 mm in 72 hours
    if hours <= 96:
        return 5_000.0  # 4,936 mm in 96 hours
    return 30_000.0  # 26,470 mm in 12 months


#: the rain of a reading by its span: a month is 10,000 mm (Cherrapunji, July 1861, 9,300) and a year 30,000 (12 months)
_RAIN_BY_SPAN: dict[str, Bounds] = {
    **{resolution: Bounds(0.0, _rain(hours)) for resolution, hours in SPAN_HOURS.items() if hours <= 24},
    "monthly": Bounds(0.0, 10_000.0),
    "annual": Bounds(0.0, 30_000.0),
}
#: a duration is not longer than its span, and 5 % more (the margin for the day length of ECA&D)
_DURATION_BY_SPAN: dict[str, Bounds] = {
    resolution: Bounds(0.0, round(hours * 3600.0 * 1.05, 1)) for resolution, hours in SPAN_HOURS.items()
}
_NON_NEGATIVE = Bounds(0.0, _INF)
_SHARE = Bounds(0.0, 1.0)
_AIR = Bounds(-90.0, 60.0)
_SEA_LEVEL = Bounds(850.0, 1_100.0)
_WIND = Bounds(0.0, 115.0)


def _count(per_month: float, otherwise: float) -> dict[str, Bounds]:
    """Give the bound of a count that is at most so many in a month and so many otherwise (a year, a day, a decade)."""
    return {"*": Bounds(0.0, otherwise), "monthly": Bounds(0.0, per_month)}


def _by_days(per_day: float) -> dict[str, Bounds]:
    """Give the bound of a sum of daily readings: the bound of a day times the days of the span (month, year)."""
    return {"*": Bounds(0.0, per_day), **{res: Bounds(0.0, per_day * days) for res, days in _DAYS.items()}}


#: by canonical name. ``None``: held to nothing
PARAMETER_RANGES: dict[str, Range] = {
    # the code of a measurement method, in a name that starts like a fraction
    "cloud_cover_total_measurement_method": None,
    "temperature_wet_ice_formation": None,
    # a quantity is derived from others, which are checked (wind chill, humidex), or is no measurement
    "temperature_wind_chill": None,
    "temperature_humidex": None,
    "radiation_global_uncertainty": None,
    "radiation_long_wave_net_last_3h": None,
    "radiation_short_wave_net_last_3h": None,
    "flow_speed": None,
    # the direction of the current: WSV writes it in a unit the documentation does not explain (MGN), perhaps gon (0 to
    # 400) and from magnetic north, so with no definition to bound it it is held to nothing
    "flow_direction": None,
    # the days and hours a month has
    "count_days_in_month": Bounds(28.0, 31.0),
    "count_hours_in_month": Bounds(672.0, 744.0),
    "ph_value": Bounds(0.0, 14.0),
    # a change over three hours: MADIS 0 to 30.5, WMO-No. 305 (1993) 9 hPa
    "pressure_air_site_delta_last_3h": Bounds(-50.0, 50.0),
    # the station pressure: Everest 330 hPa, WMO-No. 305 (1993) erroneous below 300 and above 1100
    "pressure_air_site": Bounds(300.0, 1_100.0),
    "pressure_air_site_mean": Bounds(300.0, 1_100.0),
    "pressure_air_site_min": Bounds(300.0, 1_100.0),
    "pressure_air_site_max": Bounds(300.0, 1_100.0),
    "sun_zenith_angle": Bounds(0.0, 180.0),
    "wind_movement_multiday": _NON_NEGATIVE,
    "wind_movement": Bounds(0.0, 9_936.0),  # 115 m/s for a day, in km
    # rain per span; what is no sum of the span in hand has a record of its own
    "precipitation_amount_max": Bounds(0.0, 1_850.0),  # the largest day in the span
    "precipitation_amount_max_30min": Bounds(0.0, 350.0),  # inside the 60 minutes
    "precipitation_amount_since_last_routine_report": Bounds(0.0, 1_850.0),
    "precipitation_amount_multiday": Bounds(0.0, 30_000.0),
    "precipitation_amount_normal": Bounds(0.0, 10_000.0),  # a month
    "precipitation_amount_day": {"daily": Bounds(0.0, 1_150.0), "*": Bounds(0.0, 10_000.0)},  # the 12 hours of a day
    "precipitation_amount_night": {"daily": Bounds(0.0, 1_150.0), "*": Bounds(0.0, 10_000.0)},
    "precipitation_intensity": Bounds(0.0, 2_000.0),  # 31.2 mm in a minute is 1,872 mm/h
    "precipitation_intensity_mean": Bounds(0.0, 2_000.0),
    # new snow: at most 200 cm in a day (Durre et al. 192.5), the sums of the daily depths the days of the span
    "snow_depth_new": _by_days(200.0),
    "snow_depth_new_max": Bounds(0.0, 200.0),
    "snow_depth_new_normal": Bounds(0.0, 6_200.0),  # a month: 200 cm a day times 31 (ECCC's normal of the month)
    "snow_depth_new_multiday": _NON_NEGATIVE,
    "snow_depth_sum": _by_days(1_200.0),
    # the share of the ground covered by snow, 0 to 100 % (D)
    "snow_cover": _SHARE,
    # sunshine, the duration of precipitation and of a wet leaf: the span and 5 % more (D5). DMI's daily leaf wetness is
    # a sum of minutes, 0 to 1,440
    "sunshine_duration": _DURATION_BY_SPAN,
    "leaf_wetness_duration": _DURATION_BY_SPAN,
    "precipitation_duration": _DURATION_BY_SPAN,
    # these three are the span itself, with no margin: they are not a reading of a resolution
    "sunshine_duration_last_3h": Bounds(0.0, 3 * 3_600.0),
    "sunshine_duration_yesterday": Bounds(0.0, _DAY),
    "sunshine_duration_normal": Bounds(0.0, 31 * _DAY),
    "sunshine_duration_uncertainty": Bounds(0.0, 3_600.0),  # (D) the uncertainty of an hour is not more than the hour
    "true_local_time_offset": Bounds(-45_000.0, 45_000.0),  # 12 hours and the equation of time
    # the heat the air lacks to 25 degrees over a day at the air record, and the cold it brings over one
    "heating_degree_day": {
        "daily": Bounds(0.0, 115.0),
        "monthly": Bounds(0.0, 3_600.0),
        "annual": Bounds(0.0, 42_100.0),
    },
    "cooling_degree_day": {
        "daily": Bounds(0.0, 50.0),
        "monthly": Bounds(0.0, 1_600.0),
        "annual": Bounds(0.0, 18_300.0),
    },
    # the share of the global radiation of an hour, and the long-wave irradiance from the sky: no upper end
    "radiation_global_relative_last_1h": _NON_NEGATIVE,
    "radiation_sky_long_wave_intensity_mean": _NON_NEGATIVE,  # in W/m²
    "humidity_absolute": Bounds(0.0, 40.0),
    # a deficit is the difference of two pressures and not a pressure of the air, so the 0 to 60 hPa of the vapour
    # pressure is not its bound. Its definition is at least 0 and its upper end the saturation pressure at the 60 °C of
    # the air bound, 199 hPa by Magnus (0.611 exp(17.27 t / (t + 237.3)) kPa), so 200 (D). The lower end is -10 hPa and
    # not 0: DMI writes its deficit to one decimal of a kPa from a humidity that may read past 100 %, and publishes
    # negatives marked valid (`validity: true`, `qcStatus: none`): -0.3 kPa (-3 hPa) at 06193 at 06:00 UTC on
    # 2025-07-25, -0.2 in the six hours before (read 2026-11-01; see the page of dmi/observation)
    "vapor_pressure_deficit_mean": Bounds(-10.0, 200.0),
    "visibility_index": None,
    "visibility_measurement_method": None,
    # the quantities of a body of water or a structure, at least 0
    "clearance_height": _NON_NEGATIVE,
    "water_film_thickness": _NON_NEGATIVE,
    "wave_height_max": _NON_NEGATIVE,
    "wave_height_significant": _NON_NEGATIVE,
    "wave_period": _NON_NEGATIVE,
    "volume_reservoir": _NON_NEGATIVE,
}

#: by the start of a canonical name; the first that matches wins, so a prefix that starts another comes after it
PREFIX_RANGES: tuple[tuple[str, Range], ...] = (
    # a code, a flag or an index: no range
    ("weather", None),
    ("cloud_type_", None),
    ("road_surface_condition", None),
    ("precipitation_form", None),
    ("precipitation_type_flags", None),
    ("precipitation_index", None),
    ("soil_state_index", None),
    ("cloud_density", None),
    ("climate_correction_factor", None),
    # derived from checked quantities, or a forecast error in the unit of its quantity (#3688 for the kelvin)
    ("error_absolute_", None),
    ("evaporation_", None),
    ("evapotranspiration", None),
    # hydrology: a datum of its own, and a tidal river runs backwards
    ("stage", None),
    ("discharge", None),
    ("groundwater_level", None),
    ("distance_river_gauge", None),
    # DWD's `Jultag`, the day of the year of the reference year, negative before it and above 366 after it
    ("phenology_", Bounds(-200.0, 550.0)),
    ("count_days_", _count(31.0, 366.0)),
    ("count_weather_type_", _count(31.0, 366.0)),
    ("count_hours_", _count(744.0, 8_784.0)),
    ("cloud_cover_", _SHARE),
    ("probability_", _SHARE),
    ("sunshine_duration_relative", _SHARE),
    ("humidity_relative", _SHARE),
    ("soil_moisture_", _NON_NEGATIVE),
    ("temperature_air", _AIR),
    ("temperature_dew", Bounds(-100.0, 60.0)),
    ("temperature_wet_", _AIR),
    ("temperature_water", Bounds(-5.0, 50.0)),
    ("temperature_soil", Bounds(-90.0, 100.0)),
    ("temperature_surface", Bounds(-90.0, 100.0)),
    ("temperature_concrete", Bounds(-90.0, 100.0)),
    ("temperature_radiant", Bounds(-90.0, 100.0)),
    ("pressure_vapor", Bounds(0.0, 60.0)),  # the saturation at the 35 degrees of the dew point record
    ("pressure_air_sea_level", _SEA_LEVEL),
    ("pressure_air_site_reduced", _SEA_LEVEL),
    ("wind_direction", Bounds(0.0, 360.0)),
    ("wind_force_beaufort", Bounds(0.0, 12.0)),
    ("wind_gust", _WIND),
    ("wind_speed", _WIND),
    ("water_equivalent_snow_depth", _NON_NEGATIVE),
    ("precipitation_amount", _RAIN_BY_SPAN),
    ("snow_depth_new", Bounds(0.0, 200.0)),  # a name not listed above, before the depth that starts the same
    ("snow_depth", Bounds(-10.0, 1_200.0)),
    ("frozen_ground", _NON_NEGATIVE),
    ("thawing_thickness", _NON_NEGATIVE),
    ("ice_on_water", _NON_NEGATIVE),
    ("radiation_sky_long_wave", _NON_NEGATIVE),
    ("visibility", Bounds(0.0, 200_000.0)),
    ("cloud_height", Bounds(0.0, 25_000.0)),
)

#: a sum of short-wave radiation is at most the solar constant (1,361 W/m²) times the span, rounded outward, in 10
#: minutes and an hour; a day is 60 MJ/m² at most (the top of the atmosphere at 82 degrees north in midsummer is 48),
#: and a month and a year are that times their days
_ENERGY_BY_SPAN: dict[str, Bounds] = {
    "*": _NON_NEGATIVE,
    "10_minutes": Bounds(0.0, 100.0),
    "hourly": Bounds(0.0, 500.0),
    "daily": Bounds(0.0, 6_000.0),
    "monthly": Bounds(0.0, 186_000.0),
    "annual": Bounds(0.0, 2_200_000.0),
}

#: by unit type, for what the tables above do not name. ``None``: held to nothing, a code, a flag or a quantity that has
#: its own bound (or none) by name above. Every unit type is named, so that a new one fails the test that says so
UNIT_TYPE_RANGES: dict[str, Range] = {
    "angle": None,
    "concentration": _NON_NEGATIVE,  # dissolved oxygen
    "conductivity": _NON_NEGATIVE,
    "degree_day": None,
    "degree_hour": _NON_NEGATIVE,
    "dimensionless": None,
    "energy_per_area": _ENERGY_BY_SPAN,
    "fraction": None,
    "length_long": None,
    "length_medium": None,
    "length_short": None,
    "mass_per_volume": None,
    "power_per_area": Bounds(0.0, 2_000.0),  # WMO-No. 488: 1,600; BSRN: 2,141 at the zenith
    "precipitation": None,
    "precipitation_intensity": None,
    "pressure": None,
    "significant_weather": None,
    "speed": None,
    "temperature": None,
    "time": _NON_NEGATIVE,
    "turbidity": _NON_NEGATIVE,
    "volume": _NON_NEGATIVE,
    "volume_per_time": None,
    "wind_scale": None,
}

_LAST_HOURS = re.compile(r"^precipitation_amount.*_last_(\d+)h$")


def _at(range_: Range, resolution: str | None) -> Bounds | None:
    """Give the bound a range has at a resolution: the one of the resolution, else the one for any, else none.

    Without a resolution the bound is the widest the quantity has at any (the rain of a year), which is what a frame of
    several resolutions, or of none, is held to.
    """
    if range_ is None or isinstance(range_, Bounds):
        return range_
    if resolution is None:
        return Bounds(min(bound.low for bound in range_.values()), max(bound.high for bound in range_.values()))
    if resolution in range_:
        return range_[resolution]
    return range_.get("*")


def bounds_for(name: str, resolution: str | None = None, unit_type: str | None = None) -> Bounds | None:
    """Give the bound a canonical parameter is held to at a resolution, or ``None`` where it is held to none.

    The name decides first, then the rain of the last so many hours (the span is in the name), then the family of the
    name (its start), and the unit type last. At a resolution the bound does not depend on, the bound is that for any;
    a quantity that depends on the span and is given a resolution that has none is held to nothing. Without a
    ``resolution`` the bound is the widest the quantity has at any. The unit type is that of the canonical parameter
    unless given. Raises a ``KeyError`` for a name that is not canonical and needs its unit type, as that is a defect
    of the provider and not of the check.
    """
    if name in PARAMETER_RANGES:
        return _at(PARAMETER_RANGES[name], resolution)
    last = _LAST_HOURS.match(name)
    if last is not None:
        return Bounds(0.0, _rain(float(last.group(1))))
    for prefix, range_ in PREFIX_RANGES:
        if name.startswith(prefix):
            return _at(range_, resolution)
    return _at(UNIT_TYPE_RANGES[unit_type or PARAMETERS[name].unit_type], resolution)
