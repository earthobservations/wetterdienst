# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A stand-in for the files of NOAA GHCN daily the climate stripes read: the station lists and one station's days.

The numbers are synthetic: a station whose annual mean temperature is 10.0 degrees in `FIRST_YEAR` and 0.2 more with
each year after it (a TMAX of 15.0 and a TMIN of 5.0, plus 0.2 a year each, that swing against each other so that
the mean of a day is the same every day), and 1.0 and 3.0 mm of rain on alternate days. So a year's temperature is
known without calculating it, and a year the rules fail is the only way it differs.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

from tests.provider.value_stubs import serve

if TYPE_CHECKING:
    from collections.abc import Iterable

    import pytest

#: the station every test of the stripes reads, and the years of its record
STATION = "USW00000001"
FIRST_YEAR = 1990
LAST_YEAR = 2020

#: 11 days of March 2000 with none next to another: more than the 10 a month may miss, in no run of more than 1
TOO_MANY_DAYS_2000 = frozenset(dt.date(2000, 3, day) for day in range(1, 22, 2))
#: 5 days of June 2005 in a row: fewer than 10, but more than the 4 a month may miss in a row
TOO_LONG_A_RUN_2005 = frozenset(dt.date(2005, 6, day) for day in range(10, 15))
#: 4 days in a row and 6 more apart, July 2010: 10 missing and none of them in a run of more than 4
JUST_ENOUGH_2010 = frozenset(
    {dt.date(2010, 7, day) for day in range(1, 5)} | {dt.date(2010, 7, day) for day in range(10, 22, 2)}
)
#: the days the stub station has no row for, in the years 2000, 2005 and 2010
MISSING_DAYS = TOO_MANY_DAYS_2000 | TOO_LONG_A_RUN_2005 | JUST_ENOUGH_2010
#: the one year that has a TAVG on every day, 1.0 degree below the (TMAX + TMIN) / 2 of the year (still between the two,
#: as the core's plausibility check wants it); it swings around that, so it is no series that has stopped. The series
#: is the midrange all the same, so this year is no step in it
TAVG_YEAR = 2015
#: the station that has TAVG and no TMAX and TMIN (its file is `station_csv(..., only_tavg=True)`)
TAVG_ONLY_STATION = "USW00000002"


def mean_temperature(year: int) -> float:
    """Give the annual mean the stub station has in `year`, by the rules, where its days make it valid."""
    return 10.0 + 0.2 * (year - FIRST_YEAR)


def _attributes(flag: str = "") -> str:
    """Write the attributes of a value: no measurement flag, `flag` as the quality flag, the source flag S."""
    return f",{flag},S"


def station_csv(
    station: str = STATION,
    *,
    failed: Iterable[dt.date] = (),
    last_year: int = LAST_YEAR,
    tavg: bool = True,
    only_tavg: bool = False,
) -> bytes:
    """Write the by-station file of the stub station, as NOAA writes them (values in tenths, attributes beside).

    `failed` are days whose TMAX and PRCP carry a quality flag, a check they failed. The record runs to `last_year`.
    A station that has no TAVG at all (`tavg=False`) has no column of it, as the files of NOAA have none. One that has
    TAVG alone (`only_tavg`) has it on every day, and no TMAX and TMIN.
    """
    failed = set(failed)
    columns = ["PRCP", *(["TAVG"] if tavg or only_tavg else []), *([] if only_tavg else ["TMAX", "TMIN"])]
    head = ["STATION", "DATE", "LATITUDE", "LONGITUDE", "ELEVATION", "NAME"]
    head += [name for column in columns for name in (column, f"{column}_ATTRIBUTES")]
    lines = [",".join(f'"{name}"' for name in head)]
    day = dt.date(FIRST_YEAR, 1, 1)
    while day.year <= last_year:
        if day not in MISSING_DAYS:
            lines.append(_row(station, day, day in failed, tavg=tavg, only_tavg=only_tavg))
        day += dt.timedelta(days=1)
    return "\n".join(lines).encode("utf8")


def rain_on(day: dt.date) -> float:
    """Give the rain of a day in mm: 3.0 on a day of odd ordinal, 1.0 on the others, so that no series is stuck."""
    return 3.0 if day.toordinal() % 2 else 1.0


def rain_of(year: int) -> float:
    """Give the annual precipitation the stub station has in `year`, by the rules, where its days make it valid."""
    days = (dt.date(year, 1, 1) + dt.timedelta(days=n) for n in range(366))
    return sum(rain_on(day) for day in days if day.year == year)


def _tavg(day: dt.date, midrange: int, *, only_tavg: bool) -> int | None:
    """Give the TAVG of a day in tenths: of every day at a station that has it alone, of `TAVG_YEAR` at the others."""
    swing = (-10, 0, 10, 0)[day.toordinal() % 4]
    if only_tavg:
        return midrange + swing
    return midrange - 10 + swing if day.year == TAVG_YEAR else None


def _row(station: str, day: dt.date, failed: bool, *, tavg: bool, only_tavg: bool) -> str:  # noqa: FBT001
    steps = day.year - FIRST_YEAR
    # the two swing against each other, so that the mean of the day is the same every day (and no series is "stuck",
    # which the core's plausibility check would leave out as a sensor that has stopped)
    swing = (-15, -5, 5, 15)[day.toordinal() % 4]
    tmax, tmin = 150 + 2 * steps + swing, 50 + 2 * steps - swing
    tmax_tmin_mean = (tmax + tmin) // 2
    quality = "G" if failed else ""
    cells = {
        "PRCP": (round(rain_on(day) * 10), quality),
        "TAVG": (_tavg(day, tmax_tmin_mean, only_tavg=only_tavg), ""),
        "TMAX": (tmax, quality),
        "TMIN": (tmin, ""),
    }
    values = [f'"{station}"', f'"{day.isoformat()}"', '"40.7789"', '"-73.9692"', '"42.7"', '"STUB STATION, NY US"']
    for name, (value, flag) in cells.items():
        if (name == "TAVG" and not (tavg or only_tavg)) or (name in ("TMAX", "TMIN") and only_tavg):
            continue
        values += [
            f'"{value:>5}"' if value is not None else '""',
            f'"{_attributes(flag)}"' if value is not None else '""',
        ]
    return ",".join(values)


def _station_line(station: str, latitude: float, longitude: float, name: str) -> str:
    """Write a line of `ghcnd-stations.txt`, in its columns."""
    return f"{station:<11} {latitude:8.4f} {longitude:9.4f} {42.7:6.1f} NY {name:<30}         "


def _inventory_line(station: str, latitude: float, longitude: float, element: str, first: int, last: int) -> str:
    """Write a line of `ghcnd-inventory.txt`, in its columns."""
    return f"{station:<11} {latitude:8.4f} {longitude:9.4f} {element:<4} {first:4d} {last:4d}"


# (id, latitude, longitude, name, [(element, first year, last year)])
THIS_YEAR = dt.datetime.now(dt.UTC).year
LISTED = (
    # the station of `station_csv`: all of the elements
    (
        STATION,
        40.7789,
        -73.9692,
        "STUB STATION",
        [("TAVG", 2014, 2016), ("TMAX", 1990, 2020), ("TMIN", 1990, 2020), ("PRCP", 1990, 2020)],
    ),
    # a long record of TAVG only, still reporting: for the temperature, and no precipitation
    ("USW00000002", 41.0, -73.5, "TAVG ONLY", [("TAVG", 1950, THIS_YEAR)]),
    # TMAX and TMIN that overlap for 9 years only: no 10-year span, though each has 20
    ("USW00000003", 40.5, -74.2, "NARROW OVERLAP", [("TMAX", 1950, 1969), ("TMIN", 1961, 1980)]),
    # TMAX alone: no mean can be made of it
    ("USW00000004", 40.6, -74.1, "TMAX ONLY", [("TMAX", 1940, THIS_YEAR)]),
    # a long record of rain that ended in 2005, and one that is still reporting
    ("USW00000005", 40.9, -73.8, "RAIN CLOSED", [("PRCP", 1960, 2005)]),
    ("USW00000006", 40.4, -73.1, "RAIN OPEN", [("PRCP", 1980, THIS_YEAR)]),
    # five years: too short for either
    ("USW00000007", 40.7, -73.9, "SHORT", [("TAVG", 2018, 2022), ("PRCP", 2018, 2022)]),
    # a long record that ended last year: still active
    ("USW00000008", 51.5, -0.1, "LAST YEAR", [("TMAX", 1970, THIS_YEAR - 1), ("TMIN", 1970, THIS_YEAR - 1)]),
    # nine years of TMAX, TMIN and PRCP, whose file `station_csv` writes: below the minimum, so listed for no kind
    ("USW00000009", 40.8, -73.7, "NINE YEARS", [("TMAX", 1990, 1998), ("TMIN", 1990, 1998), ("PRCP", 1990, 1998)]),
)


def stations_text() -> str:
    """Write `ghcnd-stations.txt` for the stub stations."""
    return "\n".join(_station_line(station, lat, lon, name) for station, lat, lon, name, _ in LISTED) + "\n"


def inventory_text() -> str:
    """Write `ghcnd-inventory.txt` for the stub stations: a line for each element."""
    return (
        "\n".join(
            _inventory_line(station, lat, lon, element, first, last)
            for station, lat, lon, _, elements in LISTED
            for element, first, last in elements
        )
        + "\n"
    )


def serve_ghcn(monkeypatch: pytest.MonkeyPatch, *, failed: Iterable[dt.date] = (), tavg: bool = True) -> None:
    """Have the downloads of the GHCN provider answer with the stub's lists and the file of its station."""
    from wetterdienst.provider.noaa.ghcn import api  # noqa: PLC0415

    serve(
        monkeypatch,
        api,
        {
            "ghcnd-stations": stations_text().encode("utf8"),
            "ghcnd-inventory": inventory_text().encode("utf8"),
            f"access/{STATION}": station_csv(failed=failed, tavg=tavg),
            f"access/{TAVG_ONLY_STATION}": station_csv(TAVG_ONLY_STATION, only_tavg=True),
        },
    )
