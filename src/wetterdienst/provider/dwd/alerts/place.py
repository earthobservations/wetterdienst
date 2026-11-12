# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Which warnings are for a place: a point inside their polygons, or a name or warn cell among their areas.

A DWD warning holds its areas twice: the polygons of the event area (the `geometry` of the row, `[longitude, latitude]`
pairs as GeoJSON has them) and the entities it is issued for, each a named area with a `WARNCELLID` (the `area_names`
and `warncell_ids`). A warning is for a point if a polygon contains it, and for a name or id if an area carries it.
Nothing here needs more than the standard library: shapely is an extra, and a point in a polygon is a few lines.

A point on the edge of a polygon is inside, so a point on the border between two warned areas is in both. A hole
(`EXCLUDE_POLYGON`, the land inside a warning for the sea) is outside, and its edge inside.
"""

from __future__ import annotations

import math
import re
import unicodedata
from itertools import pairwise
from typing import Any

from wetterdienst.exceptions import RequestError

#: where a point lies against a ring: strictly inside, on its edge, or outside
INSIDE, ON_EDGE, OUTSIDE = 1, 0, -1

#: the tolerance on the cross product of the segment and the point, which is the length of the segment times the
#: distance of the point from its line: a point within about `1e-12 / length of the segment` degrees is on it
_EDGE_TOLERANCE = 1e-12


def locate(ring: list[list[float]], x: float, y: float) -> int:
    """Tell where the point `x, y` lies against a closed ring of `[x, y]` pairs: inside, on its edge, or outside.

    The test is planar: it is wrong across the antimeridian, which no DWD warning crosses.
    """
    inside = False
    for (x1, y1), (x2, y2) in pairwise(ring):
        if (
            min(x1, x2) <= x <= max(x1, x2)
            and min(y1, y2) <= y <= max(y1, y2)
            and abs((x2 - x1) * (y - y1) - (y2 - y1) * (x - x1)) <= _EDGE_TOLERANCE
        ):
            return ON_EDGE
        # the ray to the east crosses this segment: one of its ends is above the point, the other not
        if (y1 > y) != (y2 > y) and x < x1 + (y - y1) * (x2 - x1) / (y2 - y1):
            inside = not inside
    return INSIDE if inside else OUTSIDE


def geometry_contains(geometry: dict[str, Any] | None, latitude: float, longitude: float) -> bool:
    """Tell whether a GeoJSON `MultiPolygon` (None for none) contains the point, its edge and the edge of a hole too."""
    if not geometry:
        return False
    for polygon in geometry["coordinates"]:
        exterior, *holes = polygon
        if locate(exterior, longitude, latitude) != OUTSIDE and all(
            locate(hole, longitude, latitude) != INSIDE for hole in holes
        ):
            return True
    return False


def _words(text: str) -> re.Pattern[str]:
    """Build the pattern of a name: its words in a row, in any case, never part of a longer word (`Kielstau`)."""
    words = r"\s+".join(re.escape(word) for word in text.split())
    return re.compile(rf"(?<!\w){words}(?!\w)", re.IGNORECASE)


def names_match(area_names: list[str], warncell_ids: list[str], name: str) -> bool:
    """Tell whether a warning has an area of this name, or of this warn cell id.

    A name of digits is an id: a warn cell (`101002000`, a type digit and the 8-digit municipality key, `AGS`) or only
    its key (`01002000`), which is the same for a commune and its district where one cell carries it: a city that the
    community product splits into quarters (Augsburg, `09761000`) has a cell for each, none ending in its key, so ask
    for it by name or by point. Any other name is the words of an area's name, `Kiel` for `Stadt Kiel`, whatever the
    case and the Unicode form of an umlaut (the names are DWD's German ones, and match every area with the word).
    """
    name = unicodedata.normalize("NFC", name.strip())
    if name.isdigit():
        return any(cell == name or (len(name) == 8 and cell.endswith(name)) for cell in warncell_ids)
    pattern = _words(name)
    return any(pattern.search(unicodedata.normalize("NFC", area_name)) for area_name in area_names)


def is_for_place(
    alert: dict[str, Any], *, latitude: float | None = None, longitude: float | None = None, name: str | None = None
) -> bool:
    """Tell whether a parsed alert is for the place: every criterion given must hold, those not given are no filter."""
    if (
        latitude is not None
        and longitude is not None
        and not geometry_contains(alert.get("geometry"), latitude, longitude)
    ):
        return False
    return name is None or names_match(alert.get("area_names") or [], alert.get("warncell_ids") or [], name)


def check_point(latitude: float | None, longitude: float | None) -> None:
    """Refuse half a point, or one that is no place on Earth, as a `RequestError`."""
    if (latitude is None) != (longitude is None):
        msg = "latitude and longitude are given together"
        raise RequestError(msg)
    if latitude is None or longitude is None:
        return
    if not (math.isfinite(latitude) and -90 <= latitude <= 90):
        msg = "latitude is not between -90 and 90"
        raise RequestError(msg)
    if not (math.isfinite(longitude) and -180 <= longitude <= 180):
        msg = "longitude is not between -180 and 180"
        raise RequestError(msg)
