# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""What `metno/frost` and `dmi/observation` share about a value whose period has not ended (GH-3856, GH-3883, GH-4087).

Both sources serve the daily, monthly and annual value of the day, month or year still running and mark nothing. A
daily one is left out of `values` and told (`leaves_open_out`). A monthly or annual one is returned marked
`completeness:Incomplete` in `quality_flags` (`incomplete_flag`), with a `window-not-closed` warning
(`tell_open_window`). An estimate (`interpolate`, `summarize`) cannot carry the mark, so the provider leaves such a
value out of the walk (it asks `TimeseriesValues._left_out_of_estimate`) and tells it with the same call, with
``returned`` false, as a cause of `source-data-left-out`. What differs between the providers is when a window closes
(Frost: the `timeOffset` of the series; DMI: the `to` of the record).
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

import polars as pl

from wetterdienst.util.response_warnings import note_open_window

if TYPE_CHECKING:
    from wetterdienst.util.network import File

#: the code of the token `completeness` for a value of a window that had not closed, the one the Environment Agency's
#: own flag uses for a value based on incomplete data (`quality_legend.py`)
INCOMPLETE = "Incomplete"


def incomplete_flag(is_open: pl.Expr) -> pl.Expr:
    """Give the code of the token `completeness` where ``is_open`` is true, and null (no token) elsewhere.

    The code is for `join_quality_flags(..., completeness=...)`. No value is marked complete: the source marks none
    either, and a closed period is no claim that it is final.
    """
    return pl.when(is_open).then(pl.lit(INCOMPLETE))


def leaves_open_out(*, daily: bool, estimate: bool) -> bool:
    """Give whether a value of a window that had not closed is left out of the answer, and not returned marked.

    A daily one always is: it looks like the day's (GH-3856, GH-4087). A monthly or annual one is returned marked
    `completeness:Incomplete`, which an estimate cannot carry, so it is left out of an estimate (``estimate``) and told
    as such (GH-3883); `values` still returns it.
    """
    return daily or estimate


def served_at(file: File, asked_at: datetime) -> datetime:
    """Give the time the answer in hand is of: when it was asked for, or when its copy was made if that was before.

    ``asked_at`` is the time taken before the download began. An answer is cached for five minutes
    (`CacheExpiry.FIVE_MINUTES`), so one read after a window closed may have been fetched before: the source's state at
    17:57 is no final value of a window that closes at 18:00, whoever reads it at 18:01. A copy that has no time (the
    cache is off, a save was skipped, a download that is stubbed) is of the time the download began, and not of the
    time it ended: a window that closes while the answer is on its way is not closed in it.
    """
    if file.cached_at is None:
        return asked_at
    return min(asked_at, datetime.fromtimestamp(file.cached_at, UTC))


def no_open_window() -> pl.DataFrame:
    """Give the frame of the values of a window that had not closed (`tell_open_window`) with none."""
    return pl.DataFrame(
        schema={"parameter": pl.String, "timestamp": pl.Datetime("us", "UTC"), "closes": pl.Datetime("us", "UTC")}
    )


def tell_open_window(
    open_window: pl.DataFrame, names: dict[str, str], start: datetime, end: datetime, *, returned: bool
) -> None:
    """Tell the walk of the values, of the parameters asked for, whose window had not closed.

    ``open_window`` has the `parameter`, the `timestamp` (the key of the date) and the time the window `closes`, one
    row for each value. ``names`` maps the parameter of the frame to the name the warning calls it by
    (`resolution/dataset/parameter`); one that is not in it is not told. ``returned`` is whether the values are in the
    answer (marked) or left out of it, so the warning says which. A value the core cuts off (beyond the window of the
    request, ``start`` to ``end``) is not counted. The warning is `window-not-closed`.
    """
    if open_window.is_empty():
        return
    inside = open_window.filter(pl.col("timestamp").is_between(start, end))
    summary = inside.group_by("parameter").agg(pl.len().alias("count"), pl.col("closes").min())
    for parameter, count, closes in summary.iter_rows():
        if parameter in names:
            note_open_window(names[parameter], count, closes, returned=returned)
