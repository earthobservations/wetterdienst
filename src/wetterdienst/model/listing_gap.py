# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A listing of the provider that the lookup of the stations went without, and what it can still say (GH-3834)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ListingGap:
    """Why the lookup of the stations went without one directory of the provider, and which stations it may hold.

    `dwd/observation` and `dwd/derived` skip a directory that came back empty or missing, or that lists files and no
    description of its stations. Nothing says which stations an empty or missing directory holds (`station_ids` is
    None: any station may be one). A directory with files and no description does say: the files carry the station
    ids, and `station_ids` are those, so a station that is not among them is not one this directory would have
    listed.
    """

    #: why the directory was skipped, as the warning and `StationListingIncompleteError` word it
    reason: str
    #: the stations the directory names in its files, None where it can say nothing of them
    station_ids: frozenset[str] | None = None

    def may_list(self, station_id: str) -> bool:
        """Tell whether a station may be one the skipped directory lists."""
        return self.station_ids is None or station_id in self.station_ids
