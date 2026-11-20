# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""How DWD's station ids are the local parts of the WIGOS ids of WMO's OSCAR/Surface (GH-4074).

`dwd/observation` and the datasets of `dwd/derived` that have DWD's station ids read their `wigos_id` by it
(`wetterdienst.model.oscar`).
"""

from __future__ import annotations

from dataclasses import replace

from wetterdienst.model.oscar import NationalWigosScheme

#: DWD's Stations_ID is the local part of the national WIGOS ids `0-276-<issue number>-<Stations_ID>` of WMO's
#: OSCAR/Surface (`0-276-3-73` is the station `00073`, which OSCAR writes without the zeros DWD pads the id with), of
#: the issue numbers 3 (secondary station), 6 (city climate) and 2, all 370 of which name a station of DWD with that id.
#: Not 0 and 1: there the local part is a WMO-like number of a radar or a profiler (`0-276-0-10103`), no id of DWD's
#: (GH-4074)
DWD_WIGOS_SCHEME = NationalWigosScheme(
    territories=("DEU",),
    issuer=276,
    issue_numbers=frozenset({2, 3, 6}),
    provider="dwd/observation",
    strip_zeros=True,
)

#: the same ids for the stations of `dwd/derived` that have DWD's station ids, which a message names as theirs
DWD_DERIVED_WIGOS_SCHEME = replace(DWD_WIGOS_SCHEME, provider="dwd/derived")
