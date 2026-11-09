# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The months of the East German hourly air temperature whose `MEZ (MD)` stamps are in mean local time (GH-3910).

The library shifts the stamps of the periods DWD's `Metadaten_Parameter` calls `Stundenwerte in MEZ (MD)` by -1 h
(GH-2709). Against NOAA ISD that is right to the whole hour from 1962-01-01 at every station: the fitted offset is
-1.0 h in every year from 1962 to 1991 at every station with an ISD twin (37 stations to 1975, 47 from 1976). The
10xxxx (WMO block 10) files of ISD hold FM-12 SYNOP of the East German stations from 1952 (the 09xxxx files only from
1973 or 1976), which makes the years before checkable. In the months of this table the offset is not -1.0 h: at 16
stations in the west and centre (10.1 to 13.0 degrees east) it is -0.5 to -0.8 h in 1952 to 1961, ordered by longitude
(a slope of -0.096 h per degree against -0.067 for mean local time, a residual of +0.08 h with a spread of 0.05 h, no
pattern of the equation of time), and at Potsdam it is -0.7 h from 1973-01 to 1975-05 (the hourly values were not yet
anchored to the SYNOP terms; the term file of DWD has the stamp S+1 equal to the term S from 1967-01). The stamps are
the mean local time of the station, UTC plus its longitude over 15, 0.6 to 0.9 h, not a whole hour from UTC, so the
shift by -1 h leaves them 0.2 to 0.5 h early (the median is 0.3 h), which an hourly grid cannot correct. The regime
ends on 1962-01-01 at every station (read off the monthly offset at Brocken, Kaltennordheim and Magdeburg and off the
phase of 15 more).

The values and their timestamps are not changed: the shift by -1 h stays the best whole-hour choice (no shift would be
wrong by 0.6 to 0.9 h). The rows are flagged `zone:mez-local-mean-time` instead of `zone:mez`, so that a caller can
leave them out or know that they are 0.2 to 0.5 h early. The months, `local_mean_time_blocks.csv` (one row per block of
consecutive months, both included), are those the model of three states (MEZ at -1.0 h, local time at
`-longitude / 15 + 0.08` h, UTC at 0.0) puts in local time from the monthly offset to ISD, a 0.1 h grid, a twin within
8 km, at least 30 pairs a month and a mean absolute difference of at most 0.9 h. 1,321 station-months at 17 stations.
The 8,024 months that the diurnal phase alone puts in "not UTC" (65 stations) and the 856 that stay undecided are
not in it; the months before 1951 (Potsdam, Rostock-Warnemünde, Wahnsdorf) were not checked. The columns:

- `station_id`, `name`, `start`, `end` (`YYYY-MM`, both months included), `n_months`;
- `longitude`: degrees east, as the station list has it;
- `isd_delta`: the median over the months of the block of the offset of the hourly values to ISD in hours (UTC at an
  East German station 0.0, MEZ -1.0, mean local time `-longitude / 15`);
- `phase_vs_mez`: the median of the phase of the first harmonic of the month's mean diurnal cycle (April to September)
  against the station's own ISD-verified MEZ years of 1976 to 1990, in hours (a UTC month would be about -1.0);
- `early_by`: hours the stamp is still early after the shift, the library's stamp against the true UTC time. At
  Gardelegen 1952-01 to 1952-05 the offset of the block is -1.00 h, which is MEZ, but the three-state model returned
  the five months as local time (the station is MEZ from 1952-06 to 1953-02) and they are in the table as it returned
  them.

A row is whole UTC days like those of `mez_blocks.csv`: from the stamp 01 of the first day of the first month to the
stamp 00 after the last month, both included, as the stamps are written. Only a row that the `MEZ (MD)` period shifts is
flagged (`DwdObservationValues._tidy_up_df`); the months lie inside the periods of the stations, which a test holds
the table to.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING

from wetterdienst.provider.dwd.observation.mez_blocks import Span, first_stamp_of, last_stamp_of

if TYPE_CHECKING:
    import datetime as dt

#: the token of `quality_flags` (kind `zone`) of a shifted row whose stamp was in mean local time, which no whole-hour
#: shift turns into UTC: the stamp is still 0.2 to 0.5 h early (GH-3910)
ZONE_LOCAL_MEAN_TIME = "mez-local-mean-time"

LOCAL_MEAN_TIME_BLOCKS_FILE = Path(__file__).with_name("local_mean_time_blocks.csv")


@dataclass(frozen=True)
class LocalMeanTimeBlock:
    """One block of consecutive months at a station whose stamps are in mean local time."""

    station_id: str
    name: str
    start: str
    end: str
    n_months: int
    longitude: float
    isd_delta: float
    phase_vs_mez: float
    early_by: float

    @property
    def first_stamp(self) -> dt.datetime:
        """The first stamp of the block as written: 01 of the first day of the first month (00 is the hour before)."""
        return first_stamp_of(self.start)

    @property
    def last_stamp(self) -> dt.datetime:
        """The last stamp of the block as written: 00 of the first day after its last month (the 24 of its last day)."""
        return last_stamp_of(self.end)


@cache
def local_mean_time_blocks() -> tuple[LocalMeanTimeBlock, ...]:
    """Read the table of the blocks whose `MEZ (MD)` stamps are mean local time (GH-3910)."""
    with LOCAL_MEAN_TIME_BLOCKS_FILE.open(encoding="utf-8", newline="") as file:
        return tuple(
            LocalMeanTimeBlock(
                station_id=row["station_id"],
                name=row["name"],
                start=row["start"],
                end=row["end"],
                n_months=int(row["n_months"]),
                longitude=float(row["longitude"]),
                isd_delta=float(row["isd_delta"]),
                phase_vs_mez=float(row["phase_vs_mez"]),
                early_by=float(row["early_by"]),
            )
            for row in csv.DictReader(file)
        )


def local_mean_time_spans() -> dict[str, tuple[Span, ...]]:
    """Name the stamps (first and last, both included, as written) of the blocks by station."""
    spans: dict[str, list[Span]] = {}
    for block in local_mean_time_blocks():
        spans.setdefault(block.station_id, []).append((block.first_stamp, block.last_stamp))
    return {station: tuple(stamps) for station, stamps in spans.items()}
