# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The one table of the changes that the check ``step`` takes for a reading that is no reading (GH-3681).

The air does not change by 20 K in an hour, and a barometer that reads 100 hPa too low for one hour and the right
value the next has made a mistake, however plausible each number is by itself. The check judges two things, in every
observation network, for one station and one parameter:

- a **step**: a reading that differs from the one before it by more than the limit for the time between two readings;
- a **spike**: a reading that jumps away from the one before it by more than the limit and back to the one after it by
  more than the limit, in the opposite direction, so that it returns within one step. The spike is flagged on the
  middle reading only; a step is flagged on the later reading of the pair (the reading that arrives with the jump:
  nothing says which of the two is wrong, and the earlier one has been accepted already).

Where a limit comes from. A limit is the level at which a service calls a value *certainly wrong*, not the strictest
tolerance, so that ``suspect:step`` rarely falls on a good value (the maintainer's decision of 2026-11-01): an hourly
air temperature of 8 K as a spike (ISD, and DMI's "certain error" of 6 to 8 K) and not the 4 K that WMO-No. 305 (1993,
withdrawn) tolerates. Every rule names its source, and the sources are:

- **ISD** (Lott 2004, "The quality control of the Integrated Surface Hourly database", 84th AMS Annual Meeting,
  section 4): a rise of 8 degrees C in one hour triggers a look at the next report, and if the temperature falls back
  by 8 degrees C or more the value in the middle is an improbable spike. The same continuity test is applied to the dew
  point, the wind speed and the pressure, with limits the paper does not give.
- **DMI** (Vejen et al. 2002, "Quality control of meteorological observations. Automatic methods used in the Nordic
  countries", NORDKLIM / MET Report 8/2002, table 3.1): the step limits per month, flag 3 being a "certain error": for
  one hour, 6 K (December to March) to 8 K (May to August) of the air temperature, 5 to 8 hPa of the pressure and 15
  m/s of the wind speed. The pressure limit is not taken (below).
- **MADIS** (NOAA / NWS, "MADIS surface data QC", temporal consistency): 35 F (19.4 K) per hour of the air and the dew
  point temperature, 50 % of the relative humidity, 15 hPa of the sea level pressure, 10.3 m/s of the wind speed and
  5 F (2.8 K) of the soil temperature. A reading that fails is *questioned*.
- **DNMI** (MET Norway, Vejen et al. 2002, 3.1.2.1): a dip test for hourly data with ``delta`` 30 % of the relative
  humidity, 7.46 m/s of the wind speed and 5.0 degrees C of the temperature; it is not in operation and flags nothing.
- **Durre et al.** (2010, Journal of Applied Meteorology and Climatology 49, 1615-1633, table 3), the GHCN-Daily
  checks: a daily TMAX or TMIN that is at least 25 K above or below both the day before and the day after is a
  spike or dip.
- **Zahumenský** (2004, WMO CBS/OPAG-IOS/ET AWS-3/Doc. 4(1)) has step limits for 1-minute data (3 K for the air
  temperature, 0.5 hPa for the pressure) and the **WMO-No. 305** (1993, withdrawn) tolerances of 4 K and 3 hPa per
  hour: the strictest tolerances, written for the firmware of a station and for the checks of a forecast centre, and
  not the level at which a value is certainly wrong. They are not used. WMO-No. 100 (2018, 3.3.6) says that a drop of
  10 K in an hour "may be suspect, but could be quite realistic if associated with the passage of a cold front or
  onset of a sea breeze", which is why the spike limit is the lower and the step limit the higher.
- **Own data** (GH-3681): the limit of a pressure, for the step and for the spike, is 60 hPa an hour. It lies between
  the 43 hPa an hour that Hurricane Irma changed the pressure at Saint-Barthélemy (2017-09-06: 977.1, 936.0, 917.4,
  960.4 hPa in four hours, a good reading whose minimum is 18.6 hPa below the hour before) and the 64 hPa an hour of the
  smallest of the 19 keying slips found in DWD's hourly station pressure. The limits of the sources (DMI's 5 to 8 hPa,
  MADIS's 15 hPa questioned) would flag that hurricane, and 5 hPa also flags 759 more readings of DWD's hourly
  pressure that jump 5 to 60 hPa away and back (1018.9, 1008.0, 1019.3 hPa), which look like typing slips: the pressure
  is the one parameter where the sourced limit and the rule that a good reading is rarely flagged part ways
  (``docs/data/plausibility.md``).

A limit that **no source publishes** is this library's own derivation, and the rule says so: the limits at 10 minutes
are those of the hour (a change in 10 minutes cannot be larger than the one the weather makes in an hour, so the hourly
limit is the more lenient there), and the limits of the dew point and of a daily mean are those of the temperature.

Time steps. A limit is for the time between two consecutive readings of the resolution of the dataset: 10 minutes,
one hour or one day. A pair or a triple of readings is judged when each interval is **no longer than that step**, which
is the case for a series of the resolution; a missing reading (a null, a gap) between them leaves two readings two steps
apart, and the check stands aside, as ISD's and DNMI's checks do on a series without good coverage. A reading that is
closer to its neighbour than the step (an irregular series) is judged with the limit of the step, which is the more
lenient: a change larger than the limit in less time is no likelier.

The first reading of a series has no predecessor and is no step and no spike; the last has no successor and is no
spike. The series is the one the core is handed (``docs/data/plausibility.md``, "What step judges"), as for ``stuck``.

What is **not judged**, because no source gives a limit, or because real data shows the limit that a source gives to
flag good readings (``docs/data/plausibility.md`` has the numbers, read on 2026-11-05 from DWD's open data, the whole
histories of 10 stations):

- the **relative humidity**: the only limits are DNMI's dip test of 30 % (not in operation) and MADIS's 50 % an hour
  (a reading that is questioned, not rejected), and fog and cloud move it that far at the summits: 30 % as a spike and
  50 % as a step flag 1,452 of 6.3 million hourly readings, 1,309 of them at the Zugspitze and the Feldberg;
- the **gusts**: no source (the research's 15 m/s is its own derivation), and a thunderstorm gust is a real step: a step
  of 15 m/s flags 376 of 2.3 million hourly readings, 7.0 to 29 m/s in an hour among them;
- the **soil temperature**: MADIS's 2.8 K an hour is a questioned reading, and the sun on bare soil moves the
  temperature at 5 cm more than that (a step of 3 K flags 17,690 of 2.1 million hourly readings);
- **radiation**, and the amounts and sums of an interval (rain, sunshine, snow, which jump from 0 and back and which no
  Nordic service tests for a step);
- the **wind direction** (circular: 350 degrees to 10 is a change of 20);
- the extremes of an interval, cloud cover and weather codes (steps of a scale);
- the resolutions of 1, 5, 6 and 15 minutes, 6 hours, a subdaily report, a month and a year; forecasts and derived
  quantities.
"""

from __future__ import annotations

from typing import NamedTuple


class StepRule(NamedTuple):
    """The limits of a parameter at a resolution, in its canonical unit, and where they come from."""

    #: a reading that departs from both neighbours by more than this, in the opposite direction, is a spike
    spike: float | None
    #: a change between two consecutive readings of more than this is a step (the later reading is flagged)
    step: float | None
    source: str
    #: the canonical unit of the limits, for the page
    unit: str


_TEMPERATURE = ("temperature_air", "temperature_air_2m", "temperature_air_mean_2m")
_DEW_POINT = ("temperature_dew_point", "temperature_dew_point_2m", "temperature_dew_point_mean_2m")
_TEMPERATURE_DAILY = (
    "temperature_air_2m",
    "temperature_air_mean_2m",
    "temperature_air_max_2m",
    "temperature_air_min_2m",
)
_PRESSURE = ("pressure_air_site", "pressure_air_site_mean", "pressure_air_sea_level", "pressure_air_sea_level_mean")
_WIND_SPEED = ("wind_speed", "wind_speed_mean", "wind_speed_mean_last_10min", "wind_speed_mean_last_2min")

#: the resolutions the table has a limit for, and no other: they are the ones with a step that is a fixed span
RESOLUTIONS = ("10_minutes", "hourly", "daily")

#: the rule of each canonical parameter at each resolution
RULES: dict[str, dict[str, StepRule]] = {}

_AT_10_MINUTES = (
    "own derivation: the limits of the hour, which a change in 10 minutes cannot exceed by the weather (Zahumenský's "
    "step limits are for 1-minute data and the strictest tolerance, and are not used)"
)


def _add(names: tuple[str, ...], resolution: str, rule: StepRule) -> None:
    for name in names:
        RULES.setdefault(name, {})[resolution] = rule


def _hourly_and_10_minutes(
    names: tuple[str, ...], spike: float | None, step: float | None, source: str, unit: str
) -> None:
    _add(names, "hourly", StepRule(spike, step, source, unit))
    _add(names, "10_minutes", StepRule(spike, step, _AT_10_MINUTES, unit))


# air temperature: a spike of 8 K (ISD, and DMI's certain error of 6 to 8 K), a step of 20 K (MADIS, 19.4 K)
_hourly_and_10_minutes(
    _TEMPERATURE,
    8.0,
    20.0,
    "ISD (Lott 2004, section 4): a rise of 8 K in an hour that falls back by 8 K is a spike; MADIS (temporal "
    "consistency): 35 F (19.4 K) in an hour",
    "°C",
)
# the dew point is judged like the air: ISD applies its continuity test to both, and MADIS has 35 F for both
_hourly_and_10_minutes(
    _DEW_POINT,
    8.0,
    20.0,
    "ISD (Lott 2004, section 4): the continuity test of the temperature, applied to the dew point as well; MADIS "
    "(temporal consistency): 35 F (19.4 K) in an hour",
    "°C",
)
# the pressure: 60 hPa for the spike and for the step (own data); DMI's 5 to 8 hPa would flag a hurricane
_hourly_and_10_minutes(
    _PRESSURE,
    60.0,
    60.0,
    "own derivation from data: 60 hPa, between 43 hPa an hour of Hurricane Irma at Saint-Barthélemy (2017-09-06; the "
    "minimum of 917.4 hPa is 18.6 hPa below the hour before) and 64 hPa an hour of the smallest of the 19 keying slips "
    "found in DWD's hourly station pressure; the limits of the sources would flag that hurricane (DMI: a change of "
    "5 hPa (May to August) to 8 hPa (October to March) in an hour is a certain error; MADIS: 15 hPa questioned)",
    "hPa",
)
# the mean wind speed: a spike of 10 m/s (MADIS, 10.3 m/s an hour), a step of 15 m/s (DMI's certain error)
_hourly_and_10_minutes(
    _WIND_SPEED,
    10.0,
    15.0,
    "MADIS (temporal consistency): 20 kt (10.3 m/s) of the wind speed in an hour; DMI (Vejen et al. 2002, table 3.1): "
    "a change of 15 m/s in an hour is a certain error",
    "m/s",
)
# a day: Durre et al.'s spike and dip of 25 K for TMAX and TMIN, applied to every daily temperature; no step
_add(
    _TEMPERATURE_DAILY,
    "daily",
    StepRule(
        25.0,
        None,
        "Durre et al. 2010 (table 3): a daily TMAX or TMIN at least 25 K above or below both the day before and the "
        "day after; own derivation for the daily mean, which is smoother than an extreme: the same limit",
        "°C",
    ),
)
_add(
    _DEW_POINT,
    "daily",
    StepRule(
        25.0,
        None,
        "own derivation: the spike of Durre et al. 2010 (table 3), 25 K for a daily TMAX or TMIN, applied to the "
        "daily dew point",
        "°C",
    ),
)


def rule_for(name: str, resolution: str) -> StepRule | None:
    """Give the rule of a canonical parameter at a resolution, or ``None`` where no source gives a limit for it."""
    return RULES.get(name, {}).get(resolution)
