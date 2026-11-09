# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The months of the hourly air temperature that both methods of the scan of GH-3776 find in MEZ, as blocks.

The plain `Stundenwerte in MEZ` label of 160 stations does not tell whether the values are MEZ (UTC+1) or UTC, and at
most of them they are UTC. Two methods that do not depend on each other tell it month by month, for the analog
periods too, where the hourly values equal no report of NOAA ISD (the ISD files hold the SYNOP reports of about 60 West
German stations from 1955, three-hourly before 1973):

- the ISD fractional-offset fit: the hourly values interpolated to the time of the ISD report, shifted by an offset
  delta (hours, on a 0.1 h grid), the mean absolute difference least; UTC stations sit at delta -0.3 +- 0.2, MEZ ones
  at -0.8 to -1.3;
- the diurnal-phase test: the hour of the maximum of the first harmonic of the mean diurnal cycle of the month
  against the station's own ISD-verified UTC months (or, where it has none, against the pooled absolute profile),
  which a one-hour clock shift moves by +0.9 to +1.3 h and the analog instrument's lag by 0 to +0.4 h.

Each method gives a verdict per month through a two-state UTC/MEZ forward-backward model. A month is in the table
(`mez_blocks.csv`, one row per block of consecutive months) only if both say MEZ in the base run and in each of the six
one-at-a-time variants of the constants of the scan (the MEZ shift of the model 0.8 or 1.2 h instead of 1.0, the
probability of a switch between the clocks 0.01 or 0.08 instead of 0.03, the posterior threshold 0.8 or 0.97 instead of
0.9, one changed at a time; a full grid of all 27 combinations keeps 748 of the 854): the evidence class "both
methods, robust" of GH-3776, 854 station-months at 27 stations. The months the library shifted before
(`MEZ_BY_COMPARISON` in `download.py`: Nürnberg 1986-02 to 1988-10 and Diepholz 1995-04 to 1996-05 among them, 46 of
the 854) are no row. The months that only one method calls MEZ, or that both call MEZ in some variants only, stay as
written.

A row is the months of its stations as the stamps of the archive are written, and the shift is made as in `download.py`
for the other blocks of whole UTC days: from the stamp 01 of the first day of the first month to the stamp 00 of the
first day after the last month, both included, by -1 h. The columns:

- `station_id`, `name`, `start`, `end` (`YYYY-MM`, both months included), `n_months`;
- `confidence`: `high` (at least six months, a mean posterior of at least 0.97 for both methods, at least half of the
  months with the station's own reference), `medium` (at least three months, 0.9), else `low`; at most `medium` where
  the offset or the step is beyond what a shift of 1 h leaves (ISD delta -1.35 h or less, phase step 1.35 h or more) or
  the ISD twin is more than 3 km away;
- `batch_1973_75`: the months of 1973-01 to 1975-12 at the 13 stations that have at least 12 of those 36 months among
  the 996 months both methods call MEZ in the base run (the wider set, before the cut to the robust core: Norderney has
  9 robust months in the window, Berlin-Alexanderplatz 12 in three pieces, six stations all 36). A block that runs
  past the window is split at its edges. The edges of the batch fall on calendar boundaries, which looks like a
  processing batch. At 8 of the 13 both measures exceed 1 h (ISD delta -1.4 to -1.6 h, phase step +1.2 to +1.5 h), so
  the shift by exactly the 1 h of the clock leaves about 0.4 h, which is the lag of the analog recorder and stays as in
  every other analog year; Bad Salzuflen, Osnabrück and Feldberg sit at about -1.0 h. Their rows carry
  `zone:mez-1973-75`;
- `isd_delta` and `phase_step`: the medians over the months of the block, in hours.
"""

from __future__ import annotations

import csv
import datetime as dt
from dataclasses import dataclass
from functools import cache
from pathlib import Path

#: the token of `quality_flags` (kind `zone`) of a row shifted on the strength of the table (GH-2709, GH-3029)
ZONE_MEZ = "mez"
#: the token of the rows of the 1973-01 to 1975-12 batch: shifted by the 1 h of the clock like the others, with the
#: lag of the analog recorder (about 0.4 h at 8 of the 13 stations) left in the values (GH-3776)
ZONE_MEZ_BATCH = "mez-1973-75"

MEZ_BLOCKS_FILE = Path(__file__).with_name("mez_blocks.csv")


@dataclass(frozen=True)
class MezBlock:
    """One block of consecutive months at a station that both methods find in MEZ."""

    station_id: str
    name: str
    start: str
    end: str
    n_months: int
    confidence: str
    batch_1973_75: bool
    isd_delta: float | None
    phase_step: float | None

    @property
    def first_stamp(self) -> dt.datetime:
        """The first stamp of the block as written: 01 of the first day of the first month (00 is the hour before)."""
        year, month = _year_month(self.start)
        return dt.datetime(year, month, 1, 1, tzinfo=dt.UTC)

    @property
    def last_stamp(self) -> dt.datetime:
        """The last stamp of the block as written: 00 of the first day after its last month (the 24 of its last day)."""
        year, month = _year_month(self.end)
        return dt.datetime(year + month // 12, month % 12 + 1, 1, 0, tzinfo=dt.UTC)


def _year_month(text: str) -> tuple[int, int]:
    year, month = text.split("-")
    return int(year), int(month)


def _optional_float(text: str) -> float | None:
    return float(text) if text else None


@cache
def mez_blocks() -> tuple[MezBlock, ...]:
    """Read the table of the blocks that are MEZ in the values of a plain MEZ period, by both methods (GH-3776)."""
    with MEZ_BLOCKS_FILE.open(encoding="utf-8", newline="") as file:
        return tuple(
            MezBlock(
                station_id=row["station_id"],
                name=row["name"],
                start=row["start"],
                end=row["end"],
                n_months=int(row["n_months"]),
                confidence=row["confidence"],
                batch_1973_75=row["batch_1973_75"] == "true",
                isd_delta=_optional_float(row["isd_delta"]),
                phase_step=_optional_float(row["phase_step"]),
            )
            for row in csv.DictReader(file)
        )


Span = tuple[dt.datetime, dt.datetime]


def mez_block_spans(*, batch: bool | None = None) -> dict[str, tuple[Span, ...]]:
    """Name the stamps (first and last, both included, as written) of the blocks by station.

    Args:
        batch: ``True`` for the rows of the 1973-01 to 1975-12 batch only, ``False`` for the others, ``None`` for all.

    """
    spans: dict[str, list[Span]] = {}
    for block in mez_blocks():
        if batch is None or block.batch_1973_75 == batch:
            spans.setdefault(block.station_id, []).append((block.first_stamp, block.last_stamp))
    return {station: tuple(stamps) for station, stamps in spans.items()}
