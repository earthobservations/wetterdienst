# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Metadata of the DWD KONRAD3D thunderstorm cells.

KONRAD3D detects, tracks and nowcasts convective cells in the volume scans of DWD's radar network. A run is made every
five minutes, and each run is one XML file in https://opendata.dwd.de/weather/radar/konrad3d/ , named for the start of
the radar scan cycle (UTC), kept for about 48 hours. DWD describes the format in
https://www.dwd.de/DE/leistungen/radarprodukte/formatbeschreibung_konrad3d.html (data model 1.7).
"""

from __future__ import annotations

import datetime as dt

DWD_STORM_CELLS_BASE_URL = "https://opendata.dwd.de/weather/radar/konrad3d"

#: DWD's description of the XML format, which the documentation links to for what the answer leaves out
DWD_STORM_CELLS_FORMAT_URL = "https://www.dwd.de/DE/leistungen/radarprodukte/formatbeschreibung_konrad3d.html"

#: how much older than the time asked for (now, or the `timestamp`) the scan may be before the answer says so. It is
#: counted from the reference time of the scan, and a file is on the server 4.7 to 9.4 minutes after it (the cadence
#: is 5 minutes and the listing is cached for one), so the newest scan is up to about 15 minutes old in the normal
#: course and the warning comes after about two runs are missing
SCAN_STALE_AFTER = dt.timedelta(minutes=20)

#: the severity of a cell (0 to 3) as DWD names it: "weak" (green), "moderate" (yellow), "severe" (red), "extreme"
#: (violet)
SEVERITY_LABELS: tuple[str, ...] = ("weak", "moderate", "severe", "extreme")

#: the number DWD writes for a value it does not have ("Ausfallwert"), in every numeric element
MISSING_NUMBER = -1_000_000_000.0
#: the text DWD writes for a time it does not have
MISSING_TIME = "not-a-date-time"

#: what wetterdienst did to the cells, which the `processing_note` says after the note every answer has: the outline is
#: closed, DWD's missing value is null, the track is a forecast and the direction is calculated
STORM_CELLS_NOTE = (
    "The cell outlines are closed rings, DWD's missing-value code is read as null, `track` is DWD's forecast of the "
    "cell's centre and not an observation, and `direction_degrees` is calculated from its first two positions."
)
