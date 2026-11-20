# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Metadata of KOSTRA-DWD-2020, DWD's heavy-rainfall statistics for Germany.

KOSTRA-DWD is the extreme-value statistics of the rainfall of Germany, regionalised to a grid of 5 km cells: for every
cell the rainfall depth, intensity and uncertainty of a rain of a duration (5 minutes to 7 days) that comes once in
a return period (1 to 100 years). DWD publishes it at
https://opendata.dwd.de/climate_environment/CDC/grids_germany/return_periods/precipitation/KOSTRA/KOSTRA_DWD_2020/
and describes it in the Anwendungshilfe zu KOSTRA-DWD-2020 (https://www.dwd.de/DE/leistungen/kostra_dwd_rasterwerte/
kostra_dwd_rasterwerte.html). The previous edition, KOSTRA-DWD-2010R, is another grid with depths only and is not read.
"""

from __future__ import annotations

#: the edition this reads, as DWD names it
EDITION = "KOSTRA-DWD-2020"

DWD_KOSTRA_BASE_URL = (
    "https://opendata.dwd.de/climate_environment/CDC/grids_germany/return_periods/precipitation/KOSTRA/KOSTRA_DWD_2020"
)

#: DWD's page about the data and its description of it, which the documentation links to
DWD_KOSTRA_INFO_URL = "https://www.dwd.de/DE/leistungen/kostra_dwd_rasterwerte/kostra_dwd_rasterwerte.html"

#: the durations DWD publishes a table for, in minutes: 5 minutes to 7 days (`D00005` ... `D10080`)
DURATIONS: tuple[int, ...] = (
    5,
    10,
    15,
    20,
    30,
    45,
    60,
    90,
    120,
    180,
    240,
    360,
    540,
    720,
    1080,
    1440,
    2880,
    4320,
    5760,
    7200,
    8640,
    10080,
)

#: the return periods of the columns, in years: DWD's nine standard ones (`T001` ... `T100`)
RETURN_PERIODS: tuple[int, ...] = (1, 2, 3, 5, 10, 20, 30, 50, 100)

#: the box in which the cells have values (Germany and a border of about 10 km): west, south, east, north in degrees,
#: from the corners of the cells of the tables that hold values
VALUES_BBOX = (5.7, 47.18, 15.16, 55.14)

#: what wetterdienst did to the values, which the `processing_note` says after the note every answer has: they are
#: DWD's statistics of the cell and no readings, and no unit was converted
KOSTRA_NOTE = (
    "The values are DWD's KOSTRA-DWD-2020 statistics of the 5 km grid cell that holds the point, not measurements at "
    "it: wetterdienst selected the cell and read DWD's missing-value codes as null, and changed no value. The "
    "uncertainty is DWD's tolerance in plus-minus percent, for the depth and for the intensity."
)


def table_url(duration: int) -> str:
    """Give the address of the zipped table of a duration, in minutes."""
    return f"{DWD_KOSTRA_BASE_URL}/tab/StatRR_KOSTRA-DWD-2020_D{duration:05d}.csv.zip"
