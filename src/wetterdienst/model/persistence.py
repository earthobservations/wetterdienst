# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The one table of the runs that the check ``stuck`` takes for a sensor that does not work (GH-3681).

A sensor that holds one value for as long as the weather cannot has stopped: a thermometer that reads the same tenth
of a degree for a day, a barometer that writes its station constant, an anemometer that is jammed. The check flags
every reading of a run of consecutive readings of one station and one parameter that hold one value, once the run is
as long as the table says. The table is the generic rule, for every observation network; what only one provider knows
(the dated periods of RMI's dead sunshine sensor, the quarter hours of a road sensor) stays a rule of that provider
(``model/judge.py``).

Where a limit comes from. A limit is the level at which a service calls a value *certainly wrong*, not the strictest
tolerance, so that ``suspect:stuck`` rarely falls on a good value: ECA&D's 5 days for a daily temperature and
pressure, as the maintainer decided on 2026-11-01, and not the 20 identical values GHCN-Daily takes for a temperature
or a rain. Every rule names its source, and the sources are:

- **HadISD** (Dunn et al. 2012, Climate of the Past 8, 1649-1679, table 4; Dunn et al. 2016, Geoscientific
  Instrumentation, Methods and Data Systems 5, 473-491), the streak test the GHCN hourly archive has adopted. Its
  limits depend on the resolution a station reports at: temperature 40 values at 1 K, 30 at 0.5 K and 24 at 0.1 K; the
  dew point twice that (80, 60, 48); sea level pressure 120 values at 1 hPa, 100 at 0.5 hPa and 72 at 0.1 hPa (or 28,
  21 and 14 days); wind speed 40, 30 and 24 values at 1, 0.5 and 0.1 m/s, where "all values below 0.5 m/s (or 1 m/s
  for coarse resolution) are also discounted in the streak search".
- **ECA&D** (KNMI, Algorithm Theoretical Basis Document v11, 2021, section 3, "Quality control"): a daily value is
  flagged suspect that is "not exactly the same value n days in a row", with n = 5 for TX, TN, TG and PP (pressure),
  10 for RR (rain) if more than 1.0 mm and 5 if more than 5.0 mm, 6 for FG (mean wind) if at least 2.0 m/s and 5 for
  FX (gust) if at least 4.0 m/s.
- **Durre et al.** (2010, Journal of Applied Meteorology and Climatology 49, 1615-1633, table 1), the GHCN-Daily
  checks: 20 consecutive identical values of TMAX or TMIN, 20 of PRCP (zeros skipped), 90 identical nonzero snow
  depths (a depth is not tested for duplication, because the same depth can last more than a month) and 10 identical
  nonzero new snows.
- **Zahumenský** (2004, WMO CBS/OPAG-IOS/ET AWS-3/Doc. 4(1)) has a persistence test too (under 0.1 K over 60 minutes,
  for 1-minute data); it is the strictest tolerance, written for the firmware of a station, and is not taken.

A limit that no source publishes is this library's own derivation, and the rule says so. There are four: the 10-minute
counts of the temperature, the dew point and the wind speed, which are the **span of the hourly limit** in readings
(24 hours are 144 readings), and the 36 readings (6 hours) of a pressure at 10 minutes, derived in the research for
GH-3681 and kept from GH-3680. Two limits of a coarser step are own derivations too: the 21 and 28 days of a daily
pressure (HadISD's span in days for a streak of hourly values, read as a count of daily values) and the 20 identical
values of a daily temperature (Durre's TMAX and TMIN rule, applied to every daily temperature). Zahumenský's 60
minutes are 6 readings at 10 minutes, and 18 (3 hours) as the research tripled them; both lie inside what working
sensors do (``docs/data/plausibility.md`` has the numbers).

The reporting step. A source that writes whole degrees holds one value for longer than one that writes tenths, so most
limits have three counts, for the step the series is reported at: **fine** (tenths, hundredths), **half** (the 0.5 of
the sources, a Fahrenheit degree of 0.56 K, a knot of 0.51 m/s) and **whole** (a whole number of the unit). The step
is read off the parameter's own readings in the canonical unit, by calendar year (DWD's hourly temperature is in whole
degrees until 1981 and in tenths after): ``_with_reporting_step`` of ``model/judge.py``. A count of ``None`` means
that no source gives a limit for a series at that step, and none is judged (ECA&D's daily wind rules are for series in
tenths of a metre per second, and a daily wind in whole metres per second or knots holds one value for days).

A reading below a floor is exempt: a calm wind, a dry day, no snow. It never counts and ends a run, so 5 mm on 5 days
with a dry day between them is no run.

What is **not judged**, because no source gives a limit for it: the relative humidity (only Zahumenský's 1 % over 60
minutes of 1-minute data; DWD's hourly humidity, in whole percents, holds 97 to 99 % for 41 to 160 hours and 100 % for
up to 243); the wind direction (only ECA&D's daily mean direction; DWD's hourly direction, in steps of 10 degrees,
holds one value for up to 206 hours); a gust at any resolution but the daily one; sunshine and radiation (0 is the
normal night value); cloud cover; soil temperature; the maximum and the minimum of an interval shorter than a day; the
amounts of an interval (the rain of an hour); the resolutions of 1, 5, 6 and 15 minutes, 6 hours, a subdaily report, a
month and a year; the forecasts and the derived quantities.

The run is judged in the series the core is handed (``docs/data/plausibility.md``, "The limit of a run").
"""

from __future__ import annotations

import math
from typing import NamedTuple

#: the tiers of a limit, by the reporting step of the series: fine, half and whole
FINE, HALF, WHOLE = 0, 1, 2
#: a series reported at a step below the first is fine, below the second half, else whole (the step in the unit)
STEP_BOUNDS = (0.25, 0.75)
#: a series is whole (or half) where this share of its readings are whole numbers (or multiples of 0.5) of the unit; a
#: series in tenths has about a tenth (a fifth) of them
STEP_SHARE = 0.8
SHARE_TOLERANCE = 1e-6
#: a calendar year with fewer changes of value than this tells nothing of the step: the whole series is read instead
MIN_CHANGES = 10
#: a group of one value in this many readings or more is a sensor that has stopped, whatever the step: the strictest
MIN_ROWS = 500
#: the readings are compared to this many decimals, so that the noise of a unit conversion is no change of value
DECIMALS = 6

_INF = math.inf
Counts = tuple[int | None, int | None, int | None]
Floors = tuple[float, float, float]


class Band(NamedTuple):
    """The readings that make a run, by step, for the values from a floor up (the values above it, if ``strict``)."""

    counts: Counts
    #: a value below the floor is exempt (and one equal to it, if ``strict``), by step
    floors: Floors = (-_INF, -_INF, -_INF)
    strict: bool = False


class RunRule(NamedTuple):
    """The limits of a parameter at a resolution: bands, the highest band a value reaches deciding, and the source."""

    bands: tuple[Band, ...]
    source: str
    #: the canonical unit the floors are in, for the page
    unit: str = ""


def _same(count: int) -> Counts:
    return (count, count, count)


def _floor(value: float) -> Floors:
    return (value, value, value)


_OWN_SPAN = (
    "own derivation: the span of HadISD's hourly limit in readings of 10 minutes (Zahumenský's 60 minutes of 1-minute "
    "data, 6 readings, or 18 as the research tripled them, are inside what working sensors do)"
)

_TEMPERATURE_SUBDAILY = ("temperature_air", "temperature_air_2m", "temperature_air_mean_2m")
_TEMPERATURE_DAILY = (
    "temperature_air_2m",
    "temperature_air_mean_2m",
    "temperature_air_max_2m",
    "temperature_air_min_2m",
)
_DEW_POINT = ("temperature_dew_point", "temperature_dew_point_2m", "temperature_dew_point_mean_2m")
_PRESSURE = ("pressure_air_site", "pressure_air_site_mean", "pressure_air_sea_level", "pressure_air_sea_level_mean")
_WIND_SPEED = ("wind_speed", "wind_speed_mean", "wind_speed_mean_last_10min", "wind_speed_mean_last_2min")
_WIND_SPEED_DAILY = ("wind_speed", "wind_speed_mean")

#: the rule of each canonical parameter at each resolution
RULES: dict[str, dict[str, RunRule]] = {}


def _add(names: tuple[str, ...], resolution: str, rule: RunRule) -> None:
    for name in names:
        RULES.setdefault(name, {})[resolution] = rule


# air temperature: 24, 30 and 40 values (HadISD); a day 5 (ECA&D, series in tenths) and 20 for a coarser step (own)
_add(
    _TEMPERATURE_SUBDAILY,
    "hourly",
    RunRule((Band((24, 30, 40)),), "HadISD (Dunn et al. 2012, table 4): temperature, straight repeat of values"),
)
_add(_TEMPERATURE_SUBDAILY, "10_minutes", RunRule((Band((144, 180, 240)),), _OWN_SPAN))
_add(
    _TEMPERATURE_DAILY,
    "daily",
    RunRule(
        (Band((5, 20, 20)),),
        "ECA&D (ATBD v11, section 3): TX, TN, TG not the same value 5 days in a row; own derivation for a coarser "
        "step: the 20 identical values of Durre et al. 2010 (table 1) for TMAX and TMIN, applied to every daily "
        "temperature",
    ),
)
# the dew point: twice the temperature's counts (HadISD)
_add(
    _DEW_POINT,
    "hourly",
    RunRule(
        (Band((48, 60, 80)),),
        "HadISD (Dunn et al. 2012, table 4): dew point, twice the straight repeat of a temperature",
    ),
)
_add(_DEW_POINT, "10_minutes", RunRule((Band((288, 360, 480)),), _OWN_SPAN))
# pressure: 72, 100 and 120 values (HadISD), 36 at 10 minutes (own, GH-3680), a day 5 (ECA&D), 21 and 28 (own)
_add(
    _PRESSURE,
    "hourly",
    RunRule(
        (Band((72, 100, 120)),), "HadISD (Dunn et al. 2012, table 4): sea level pressure, straight repeat of values"
    ),
)
_add(
    _PRESSURE,
    "10_minutes",
    RunRule(
        (Band(_same(36)),),
        "own derivation: 6 hours, from the research for GH-3681 and kept from GH-3680 (the longest run of one pressure "
        "in 13.3 million readings of 8 DWD stations is 31)",
    ),
)
_add(
    _PRESSURE,
    "daily",
    RunRule(
        (Band((5, 21, 28)),),
        "ECA&D (ATBD v11, section 3): PP not the same value 5 days in a row; own derivation for a coarser step: "
        "HadISD's 21 and 28 days at 0.5 and 1 hPa (table 4), read as counts of daily values",
    ),
)
# wind speed: 24, 30 and 40 values (HadISD), a reading below 0.5 m/s (1 m/s at a whole step) is a calm and exempt
_add(
    _WIND_SPEED,
    "hourly",
    RunRule(
        (Band((24, 30, 40), floors=(0.5, 0.5, 1.0)),),
        "HadISD (Dunn et al. 2012, table 4): wind speed, straight repeat of values; values below 0.5 m/s (1 m/s at a "
        "whole step) discounted",
        "m/s",
    ),
)
_add(_WIND_SPEED, "10_minutes", RunRule((Band((144, 180, 240), floors=(0.5, 0.5, 1.0)),), _OWN_SPAN, "m/s"))
# the daily mean wind 6 days from 2 m/s, the daily gust 5 days from 4 m/s (ECA&D, series in tenths of a m/s)
_add(
    _WIND_SPEED_DAILY,
    "daily",
    RunRule(
        (Band((6, None, None), floors=_floor(2.0)),),
        "ECA&D (ATBD v11, section 3): FG not the same value 6 days in a row if at least 2.0 m/s",
        "m/s",
    ),
)
_add(
    ("wind_gust_max",),
    "daily",
    RunRule(
        (Band((5, None, None), floors=_floor(4.0)),),
        "ECA&D (ATBD v11, section 3): FX not the same value 5 days in a row if at least 4.0 m/s",
        "m/s",
    ),
)
# the rain of a day: 10 days of one value above 1.0 mm, 5 above 5.0 mm (ECA&D); a dry day and a trace are exempt
_add(
    ("precipitation_amount",),
    "daily",
    RunRule(
        (Band(_same(10), floors=_floor(1.0), strict=True), Band(_same(5), floors=_floor(5.0), strict=True)),
        "ECA&D (ATBD v11, section 3): RR not the same value 10 days in a row if more than 1.0 mm, 5 days if more than "
        "5.0 mm",
        "mm",
    ),
)
# snow: 90 identical nonzero depths and 10 identical nonzero new snows (Durre et al.)
_add(
    ("snow_depth",),
    "daily",
    RunRule(
        (Band(_same(90), floors=_floor(0.0), strict=True),),
        "Durre et al. 2010 (table 1): SNWD, 90 consecutive identical nonzero values",
        "cm",
    ),
)
_add(
    ("snow_depth_new",),
    "daily",
    RunRule(
        (Band(_same(10), floors=_floor(0.0), strict=True),),
        "Durre et al. 2010 (table 1): SNOW, 10 consecutive identical nonzero values",
        "cm",
    ),
)


def rule_for(name: str, resolution: str) -> RunRule | None:
    """Give the rule of a canonical parameter at a resolution, or ``None`` where no source gives a limit for it."""
    return RULES.get(name, {}).get(resolution)


def shortest_run(rule: RunRule) -> int:
    """Give the fewest readings that make a run in any band at any step: a shorter run is no run, whatever the step."""
    return min(count for band in rule.bands for count in band.counts if count is not None)


def exemption(band: Band, unit: str = "") -> str:
    """Say which readings count for a band: all of them, or those from (above) a floor, as the page words it."""
    if all(math.isinf(floor) for floor in band.floors):
        return "all"
    word = "above" if band.strict else "from"
    suffix = f" {unit}" if unit else ""
    if len(set(band.floors)) == 1:
        return f"{word} {band.floors[0]:g}{suffix}"
    return f"{word} {band.floors[0]:g}{suffix} ({band.floors[2]:g} at a whole step)"
