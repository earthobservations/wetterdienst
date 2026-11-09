# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""How long the data files of the DWD period folders are kept in the cache (GH-3929)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from wetterdienst.metadata.cache import CacheExpiry
from wetterdienst.metadata.period import Period

if TYPE_CHECKING:
    from collections.abc import Mapping

#: the expiry of a data file of the `historical` folders: final by name (what is in a station's historical archive is
#: settled, and DWD replaces the archive only when the next year is moved into it, a few times a year), so a week
HISTORICAL_FILE_EXPIRY = CacheExpiry.ONE_WEEK
#: the expiry of the files of `recent` and `now`, which DWD appends to day by day
CURRENT_FILE_EXPIRY = CacheExpiry.FIVE_MINUTES


def file_expiry(period: Period | None) -> CacheExpiry:
    """Give the expiry a data file of the period is downloaded with: a week for `historical`, else five minutes."""
    return HISTORICAL_FILE_EXPIRY if period is Period.HISTORICAL else CURRENT_FILE_EXPIRY


def expiries_of(urls: list[str], period: Period | None) -> Mapping[str, CacheExpiry]:
    """Give the expiry of each URL of the files of one period, which is how a fetch-ahead names them."""
    expiry = file_expiry(period)
    return dict.fromkeys(urls, expiry)
