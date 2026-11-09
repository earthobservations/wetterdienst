# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What every provider's ``timestamp`` column has to look like, and the check for it."""

import polars as pl

#: the one type the ``timestamp`` column has, whichever provider it comes from and whether the frame
#: holds values, interpolated values or a summary: UTC, to the microsecond. A source that stamps in
#: local time or in nanoseconds is converted by its provider, not passed on.
TIMESTAMP_DTYPE = pl.Datetime(time_unit="us", time_zone="UTC")


def timestamp_problem(df: pl.DataFrame) -> str | None:
    """Say what is wrong with the ``timestamp`` column of a result frame, or None when nothing is.

    A frame that has no such column is a problem too: even a request that collected nothing carries
    the column's schema.
    """
    if "timestamp" not in df.columns:
        return "there is no timestamp column"
    dtype = df.schema["timestamp"]
    if dtype == TIMESTAMP_DTYPE:
        return None
    return f"the timestamp column is {dtype}, not {TIMESTAMP_DTYPE}"


#: The datasets that are declared `timestamp_position: start` on no ground but the library's own: the provider's
#: documentation does not state where its stamp sits (`unverified` on `docs/data/time_reference.md`), but the reader
#: builds the stamp itself, as the first day of the period it names (GH-3134). A month the source names as
#: `YYYY-MM`, a year as `YYYY`, a phenology phase by its reference year: the reader has to put a stamp on them, and
#: the first day is the one it puts. Keyed by (provider, network, resolution) and giving the datasets of the
#: resolution it holds for (None: all of them) and where the reader builds the stamp.
#:
#: A dataset whose own file carries the stamp (DWD's `MESS_DATUM_BEGINN`, the API's list of timestamps at Geosphere)
#: does not belong here, whatever the day: the source says it, or does not, and the page records which. The claim
#: is held to the code twice: `library_built_problem` checks every frame of a listed dataset that a test builds
#: (`tests/provider/conftest.py`), and `test_timestamp_position.py` sees to it that one is built for each entry.
LIBRARY_BUILT_START: dict[tuple[str, str, str], tuple[tuple[str, ...] | None, str]] = {
    ("aemet", "observation", "monthly"): (None, "`_collect_monthly_or_annual` makes the 1st of month X of `fecha`"),
    ("aemet", "observation", "annual"): (None, "`_collect_monthly_or_annual` makes 1 January of the year of `fecha`"),
    ("chmi", "observation", "monthly"): (None, "`parse_chmi_values_aggregate` makes the 1st of `MONTH` in `YEAR`"),
    ("chmi", "observation", "annual"): (None, "`parse_chmi_values_aggregate` makes 1 January of `YEAR`"),
    ("dwd", "derived", "monthly"): (("soil",), "`_parse_climate_derived_data` reads the file's `monat` (`YYYYMM`)"),
    ("dwd", "phenology", "annual"): (None, "`_parse_values` dates a phase to 1 January of `Referenzjahr`"),
    ("imgw", "meteorology", "monthly"): (
        ("climate", "precipitation"),
        "`_unpivot` makes the 1st of the `month` of the row",
    ),
}

_PERIOD_START = {"monthly": ("1mo", "month"), "annual": ("1y", "year")}


def library_built_problem(df: pl.DataFrame, resolution: str) -> str | None:
    """Say which stamps of a monthly or annual frame are not the first moment of their period, or None when all are."""
    unit, period = _PERIOD_START[resolution]
    if "timestamp" not in df.columns or df.is_empty():
        return None
    stamps = df.get_column("timestamp").drop_nulls().unique()
    off = stamps.filter(stamps != stamps.dt.truncate(unit))
    if off.is_empty():
        return None
    shown = ", ".join(stamp.isoformat() for stamp in off.sort().head(3).to_list())
    return f"{off.len()} of {stamps.len()} stamps are not the first moment of their {period}: {shown}"
