# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The position of the sun and the length of the day, as polars expressions of a timestamp column (GH-3624, GH-3681).

``sun_elevation`` is the rule of ``dwd/road`` that tells night (the sun more than six degrees below the horizon), moved
here so that the check ``relations`` can use the same sun for the sunshine of a day. ``daylight_hours`` is the longest
time the sun is above the horizon on the day of a reading, at a latitude.

Both use the low-precision formulas of the Astronomical Almanac, which place the sun within 0.01 degrees: far inside
the margins the two rules need (a sunshine duration is held to the day length plus 5 %, a road to six degrees of
twilight).
"""

from __future__ import annotations

import math

import polars as pl

#: the seconds of a day, and of the epoch J2000 (2000-01-01 12:00 UTC) the sun's position is counted from
_DAY = 86_400.0
_J2000_EPOCH_SECONDS = 946_728_000.0
#: the altitude of the centre of the sun at sunrise and sunset, in degrees: the radius of the disc (0.267) and the
#: refraction at the horizon (0.567) together, as the Almanac and the national weather services count the day
SUNRISE_ALTITUDE = -0.833
#: the dip of the horizon seen from a height, in degrees per square root of a metre: 1.76 minutes of arc times the root
#: of the height in metres (the standard formula of the Almanac, which counts the refraction in), so that a summit sees
#: the sun rise earlier and set later than a place at sea level
HORIZON_DIP_PER_ROOT_METRE = 1.76 / 60.0
#: the latitude the day length is computed at the most, so that the poles do not divide by zero
_MAX_LATITUDE = 89.999


def _position(days: pl.Expr) -> tuple[pl.Expr, pl.Expr]:
    """Give the declination and the right ascension of the sun in radians, at ``days`` since J2000."""
    mean_longitude = 280.460 + 0.9856474 * days
    mean_anomaly = (357.528 + 0.9856003 * days).radians()
    ecliptic_longitude = (mean_longitude + 1.915 * mean_anomaly.sin() + 0.020 * (2 * mean_anomaly).sin()).radians()
    obliquity = (23.439 - 4.0e-7 * days).radians()
    right_ascension = pl.arctan2(obliquity.cos() * ecliptic_longitude.sin(), ecliptic_longitude.cos())
    declination = (obliquity.sin() * ecliptic_longitude.sin()).arcsin()
    return declination, right_ascension


def sun_elevation(timestamp: pl.Expr, latitude: float, longitude: float) -> pl.Expr:
    """Give the elevation of the sun above the horizon in degrees, at a UTC instant and a place.

    The refraction is not added, which is half a degree at the horizon and nothing six degrees below it.

    Args:
        timestamp: the instant, a datetime in UTC.
        latitude: the latitude of the place in degrees north.
        longitude: the longitude of the place in degrees east.

    """
    days = (timestamp.dt.epoch("s").cast(pl.Float64) - _J2000_EPOCH_SECONDS) / _DAY
    declination, right_ascension = _position(days)
    # the Greenwich mean sidereal time in hours, and from it the hour angle of the sun at the place
    sidereal_hours = (18.697374558 + 24.06570982441908 * days) % 24
    hour_angle = (sidereal_hours * 15 + longitude).radians() - right_ascension
    sine = math.sin(math.radians(latitude)) * declination.sin() + (
        math.cos(math.radians(latitude)) * declination.cos() * hour_angle.cos()
    )
    return sine.arcsin().degrees()


def daylight_hours(timestamp: pl.Expr, latitude: float, elevation: float = 0.0) -> pl.Expr:
    """Give the longest time in hours the sun is above the horizon on the day of an instant and the days beside it.

    The day length is the hours the centre of the sun is higher than ``SUNRISE_ALTITUDE``, lowered by the dip of the
    horizon at the elevation of the station (``HORIZON_DIP_PER_ROOT_METRE``): 0 in the polar night, 24 in the polar
    day. The Zugspitze, at 2,962 m, sees the sun 1.6 degrees below the sea-level horizon, which makes a November day an
    hour longer than at the foot of the mountain.

    It is the longest of three days: the day of the instant (its UTC date), the day before and the one after. The date
    of a reading is the date of the source's clock and not necessarily of UTC, and near the polar circles the day grows
    or shrinks by an hour or more a day: a sunshine duration is held to a day length that the date, read one day off,
    cannot make too short.

    Args:
        timestamp: the instant, a datetime in UTC; it is the day it falls in that counts.
        latitude: the latitude of the place in degrees north.
        elevation: the elevation of the place in metres above sea level; a place below sea level has no dip.

    """
    phi = math.radians(max(-_MAX_LATITUDE, min(_MAX_LATITUDE, latitude)))
    altitude = SUNRISE_ALTITUDE - HORIZON_DIP_PER_ROOT_METRE * math.sqrt(max(0.0, elevation))
    noon = timestamp.dt.truncate("1d").dt.epoch("s").cast(pl.Float64) + _DAY / 2
    hours = []
    for offset in (-1.0, 0.0, 1.0):
        days = (noon + offset * _DAY - _J2000_EPOCH_SECONDS) / _DAY
        declination, _ = _position(days)
        # the hour angle of the sunrise: above 1 the sun does not rise (polar night), below -1 it does not set
        cosine = (math.sin(math.radians(altitude)) - math.sin(phi) * declination.sin()) / (
            math.cos(phi) * declination.cos()
        )
        hours.append(cosine.clip(-1.0, 1.0).arccos().degrees() * 2.0 / 15.0)
    return pl.max_horizontal(*hours)
