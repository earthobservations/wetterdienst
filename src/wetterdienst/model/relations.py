# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The one table of the relations of one row that the check ``relations`` holds readings to (GH-3681).

A maximum is not below the mean of its interval, and the mean is not below the minimum; the dew point is not above the
air temperature; a gust is not below the mean wind of its interval; the sunshine of a day is no longer than the day. A
reading that breaks such a relation is a reading that is no reading, however plausible each number is by itself. The
check judges the relations in **one row**: the same station, the same timestamp, the same file (a dataset the provider
declares ``grouped``). It never downloads a partner: a relation whose two parameters are in different files (the hourly
air temperature and the hourly gust of DWD, which are two datasets) is not judged, and the page says so for each
dataset.

Which reading of a broken pair is flagged. Nothing says which of two readings is wrong, so **both are flagged** (the
maintainer's decision of 2026-11-05, as Durre et al. 2010 flag every value of an inconsistency, and as MADIS flags both
of a dew point above the air temperature): the flagged readings of a triple are those of the broken *pair* (a maximum
below the mean flags the maximum and the mean, and not the minimum). The sunshine of a day has no partner reading, and
that one reading is flagged.

Where a relation holds by the source's own definition, and only there. A relation is stated for the readings of one
period: a maximum, a mean and a minimum are of the same interval. The table therefore names the parameters by their
canonical names, which say the interval, and pairs what the name pairs: ``wind_gust_max`` (the gust of the resolution's
interval) with ``wind_speed_mean`` (its mean) and not with ``wind_speed_mean_last_10min`` (a mean of ten minutes
beside the gust of an hour), and the instantaneous ``temperature_air_2m`` is no mean and no partner of an hourly maximum
(a thermometer read at the end of the hour is a sample, not an average: the maximum of the sensor's own samples need
not reach it). A reading that is a **code** of the source (``raw:-999``) or that another check has judged bad
(``range``, ``elevation``, ``source``, ``stuck``, ``consistency``, ``limits``) is no partner, and the relation stands
aside, as it does for a null.

Tolerances. A relation holds with no tolerance, with one exception: the dew point may exceed the air temperature by
``DEW_POINT_TOLERANCE``. Numbers are compared after rounding to six decimals, so that 8.0 K is not 8.000000000000002.
Rounding in the source cannot break a relation: a rounding is monotone, so a mean that is not above the maximum before
rounding is not above it after, whatever the step the source writes in.

The sources are:

- **WMO-No. 100** (Guide to Climatological Practices, 2018, 3.3.6, "Consistency tests"): "a maximum value must be equal
  to or higher than a minimum value", dew point and dry bulb, and "sunshine duration is limited by the duration of the
  day".
- **Durre et al.** (2010, Journal of Applied Meteorology and Climatology 49, 1615-1633), the GHCN-Daily checks: the
  internal consistency of TMAX, TMIN and the observed temperature, with every value involved flagged.
- **ECA&D** (Klein Tank et al. 2002; the ECA&D quality control): the daily mean temperature between the minimum and the
  maximum, and sunshine duration of at most the maximum day length for the day of the year and the latitude plus 5 %.
- **Zahumenský** (2004, WMO CBS/OPAG-IOS/ET AWS-3/Doc. 4(1), II.c and III): the dew point at most the air temperature
  and the gust at least the wind speed, for data of up to 10 minutes. The draft states the gust rule as "gust >= wind
  speed" in II.c and as "erroneous if gust <= wind speed" in III(a); the table takes the first: a gust *below* the
  mean is the break, and equal is calm.
- **Vejen et al.** (2002, NORDKLIM / MET Report 8/2002, 3.2.1 to 3.2.3): the dew point may exceed the air temperature
  by gamma, 0.2 K recommended; the maximum and the minimum against the air temperature are *certain* errors.
- **HadISD** (Dunn et al. 2012, Climate of the Past 8, 1649-1679, test 11) and **MADIS** (NOAA / NWS, "MADIS surface
  data QC", internal consistency): a dew point above the air temperature is flagged (MADIS: both readings).
"""

from __future__ import annotations

from itertools import pairwise
from typing import NamedTuple

#: the resolutions a relation is judged at: the readings of an interval of a day or less (a report is one instant). A
#: month or a year is a mean of days whose maximum, mean and minimum are each computed from the days by the source's
#: own rule, which this library does not know for every provider
RESOLUTIONS = ("1_minute", "5_minutes", "10_minutes", "15_minutes", "hourly", "subdaily", "daily")

#: the dew point may exceed the air temperature by this many kelvin before a pair is broken
DEW_POINT_TOLERANCE = 0.2

#: sunshine may last the longest day length of the date plus this share: the margin of ECA&D's day length
DAYLIGHT_MARGIN = 0.05


class Relation(NamedTuple):
    """A pair of canonical parameters of one dataset, of which ``high`` is not below ``low`` less the tolerance."""

    high: str
    low: str
    tolerance: float
    #: the kind of the relation, for the page: ``extremes`` (a maximum, a mean, a minimum), ``dew point``, ``gust``
    kind: str
    #: the rung between the two, for a pair that skips one (a maximum and a minimum beside a mean): the pair is judged
    #: only at the timestamps where that rung has no reading to judge, so that the readings of a triple that is judged
    #: are the readings of the broken pair and no more
    via: str | None = None


class Ladder(NamedTuple):
    """The parameters of one quantity from the highest to the lowest, of which the ones a dataset has are compared.

    Each rung is the names that can stand for it (the first a dataset has is its member), and a rung that a dataset
    has none of is left out: a dataset with a maximum and a minimum and no mean judges the maximum against the minimum.
    Two neighbours that are both there are compared; a rung that is null at a timestamp leaves the pairs it is in
    unjudged there, the check stands aside. The two rungs on either side of a middle one are compared too, but only at
    the timestamps where the middle one has no reading to judge (``Relation.via``): a daily maximum and minimum are
    held to each other where the mean is missing, as GHCN-Daily has it for most stations.
    """

    quantity: str
    rungs: tuple[tuple[str, ...], ...]
    kind: str


#: the quantities that have a maximum and a minimum, and the mean between them, of the same period
LADDERS: tuple[Ladder, ...] = (
    Ladder(
        "air temperature (2 m)",
        (
            ("temperature_air_max_2m",),
            ("temperature_air_mean_2m", "temperature_air_mean_minmax_2m"),
            ("temperature_air_min_2m",),
        ),
        "extremes",
    ),
    Ladder(
        "air temperature (5 cm)",
        (("temperature_air_max_0_05m",), ("temperature_air_mean_0_05m",), ("temperature_air_min_0_05m",)),
        "extremes",
    ),
    Ladder(
        "relative humidity",
        (("humidity_relative_max",), ("humidity_relative_mean",), ("humidity_relative_min",)),
        "extremes",
    ),
    Ladder(
        "pressure (site)",
        (("pressure_air_site_max",), ("pressure_air_site_mean",), ("pressure_air_site_min",)),
        "extremes",
    ),
    Ladder(
        "pressure (sea level)",
        (("pressure_air_sea_level_max",), ("pressure_air_sea_level_mean",), ("pressure_air_sea_level_min",)),
        "extremes",
    ),
    # the gust of an interval is above the mean wind of the interval, and the mean is below the highest mean of ten
    # minutes in it and above the lowest. The gust is *not* held to the highest mean of ten minutes: that mean is a
    # rolling one, whose windows begin before the interval does, and DWD's 10-minute files break the order in 1.4 % of
    # 9.8 million readings (137,356, mostly by 0.1 to 0.5 m/s) (`docs/data/plausibility.md`)
    Ladder("wind speed (interval)", (("wind_gust_max",), ("wind_speed_mean",)), "gust"),
    Ladder("wind speed (highest rolling mean)", (("wind_speed_rolling_mean_max",), ("wind_speed_mean",)), "gust"),
    Ladder("wind speed (lowest rolling mean)", (("wind_speed_rolling_mean_max",), ("wind_speed_min",)), "gust"),
    # the gust and the mean of the same ten minutes (the names say the window: a gust of the last ten minutes beside a
    # mean of the last ten, as FMI and the Met Office write them)
    Ladder("wind speed (10 minutes)", (("wind_gust_max_last_10min",), ("wind_speed_mean_last_10min",)), "gust"),
)

#: the dew point and the air temperature of the same instant (or the same interval's means): the dew point is not
#: above the air by more than the tolerance
DEW_POINTS: tuple[tuple[str, str], ...] = (
    ("temperature_air_2m", "temperature_dew_point_2m"),
    ("temperature_air_mean_2m", "temperature_dew_point_mean_2m"),
    ("temperature_air", "temperature_dew_point"),
)

#: the sunshine durations that are held to the day length at the station's position
SUNSHINE: tuple[str, ...] = ("sunshine_duration",)


#: where the parameters of a ladder are not of one window by the source's own definition, by network and resolution:
#: the ladder (its quantity) and the names that are left out of it (``GH-3681``).
#:
#: - **Météo-France**, `daily/core`: ``TM`` is the "daily mean of the hourly temperatures", while ``TN`` and ``TX`` are
#:   the extremes "under shelter" of a window the description of the fields does not give (the description gives one
#:   only for the rain, 06h to 06h), and the extremes of its climatological day are not those of the hours of the mean:
#:   at Bordeaux-Mérignac (33281001) on 2023-12-01 TX is 9.3, TM 8.3 and TN 8.5, the lowest value from 18 UTC of the
#:   evening before to 18 UTC and not of the day that the mean averages (the hourly series falls to 5.8 °C by 23 UTC).
#:   All three are left out, the maximum against the minimum too, since no window is given that makes it hold.
#: - **FMI**, `daily/data`: ``tday`` is "mean over 1 day" (aggregation period P1D), ``tmax`` and ``tmin`` are over
#:   "24 hours" (PT24H): two periods of the source's own naming. The mean is left out, the maximum and the minimum, both
#:   of PT24H, stay.
NOT_ONE_WINDOW: dict[tuple[str, str], dict[str, frozenset[str]]] = {
    ("meteofrance/observation", "daily"): {
        "air temperature (2 m)": frozenset(
            {
                "temperature_air_max_2m",
                "temperature_air_mean_2m",
                "temperature_air_mean_minmax_2m",
                "temperature_air_min_2m",
            }
        )
    },
    ("fmi/observation", "daily"): {
        "air temperature (2 m)": frozenset({"temperature_air_mean_2m", "temperature_air_mean_minmax_2m"})
    },
}


def relations_for(
    names: set[str] | frozenset[str], resolution: str, network: str | None = None
) -> tuple[Relation, ...]:
    """Give the pairs of canonical parameters the check judges in a dataset that has ``names``, at a resolution.

    ``network`` is ``provider/network``: a few networks have a ladder whose rungs are not of one window by the source's
    own definition (``NOT_ONE_WINDOW``), which is left out for them.
    """
    if resolution not in RESOLUTIONS:
        return ()
    dropped = NOT_ONE_WINDOW.get((network or "", resolution), {})
    found: list[Relation] = []
    for ladder in LADDERS:
        present_names = names - dropped.get(ladder.quantity, frozenset())
        members = [next((name for name in rung if name in present_names), None) for rung in ladder.rungs]
        present = [name for name in members if name is not None]
        found.extend(Relation(high, low, 0.0, ladder.kind) for high, low in pairwise(present))
        found.extend(
            Relation(high, low, 0.0, ladder.kind, via)
            for high, via, low in zip(present, present[1:], present[2:], strict=False)
        )
    found.extend(
        Relation(air, dew, DEW_POINT_TOLERANCE, "dew point") for air, dew in DEW_POINTS if air in names and dew in names
    )
    return tuple(found)


def daylight_for(names: set[str] | frozenset[str], resolution: str) -> tuple[str, ...]:
    """Give the sunshine durations of a dataset that are held to the day length, at a resolution."""
    if resolution not in RESOLUTIONS:
        return ()
    return tuple(name for name in SUNSHINE if name in names)
