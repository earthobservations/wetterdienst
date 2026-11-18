# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Which cells are for a place: a point that an outline contains or is near, or a box that a cell is in.

A cell is a few to a few hundred km2 wide and a point asks about one place, so the outline is what counts and not the
centre: the centre of a large cell is miles from the rain over a house. A cell is for a point if its outline contains
the point (an edge counts) or comes within `distance` km of it, and for a box if its outline reaches into the box.

The distance is measured on the plane that touches the Earth at the point (an equirectangular projection of the
outline around it), which is exact at the point and within about 1 % of the great-circle distance up to some hundreds
of km: cells are far smaller than that, and the distance of a request is not meant to be exact to the metre.
Nothing here needs more than the standard library.
"""

from __future__ import annotations

import math
from itertools import pairwise
from typing import Any

from wetterdienst.exceptions import RequestError
from wetterdienst.provider.dwd.alerts.place import OUTSIDE, check_point, locate
from wetterdienst.provider.dwd.storm_cells.parser import EARTH_RADIUS_KM

__all__ = ["check_bbox", "check_distance", "check_place", "is_for_box", "is_for_point", "outline_distance_km"]

_KM_PER_DEGREE = math.pi * EARTH_RADIUS_KM / 180


def check_distance(distance: float | None) -> None:
    """Refuse a distance that is no length: negative, infinite or not a number."""
    if distance is not None and not (math.isfinite(distance) and distance >= 0):
        msg = "distance is not a length in km (zero or more)"
        raise RequestError(msg)


def check_bbox(left: float | None, bottom: float | None, right: float | None, top: float | None) -> bool:
    """Refuse a box that is given in part or is no area on Earth; tell whether one is given at all."""
    edges = {"left": left, "bottom": bottom, "right": right, "top": top}
    given = [name for name, edge in edges.items() if edge is not None]
    if not given:
        return False
    if len(given) < len(edges):
        msg = "left, bottom, right and top are given together, as the four edges of a box"
        raise RequestError(msg)
    if left is None or bottom is None or right is None or top is None:  # for the type checker
        return False
    if not all(math.isfinite(edge) for edge in (left, bottom, right, top)):
        msg = "left, bottom, right and top are numbers"
        raise RequestError(msg)
    if not (-90 <= bottom <= top <= 90):
        msg = "bottom and top are latitudes between -90 and 90, bottom not above top"
        raise RequestError(msg)
    if not (-180 <= left <= right <= 180):
        msg = "left and right are longitudes between -180 and 180, left not east of right"
        raise RequestError(msg)
    return True


def check_place(
    latitude: float | None,
    longitude: float | None,
    distance: float | None,
    left: float | None,
    bottom: float | None,
    right: float | None,
    top: float | None,
) -> None:
    """Refuse a place that is half a point, a distance without a point, half a box, or a point and a box together."""
    check_point(latitude, longitude)
    check_distance(distance)
    has_box = check_bbox(left, bottom, right, top)
    if distance is not None and latitude is None:
        msg = "distance is the radius around the point of latitude and longitude, which are given with it"
        raise RequestError(msg)
    if has_box and latitude is not None:
        msg = "give a point (latitude, longitude and distance) or a box (left, bottom, right and top), not both"
        raise RequestError(msg)


def _segment_distance(x1: float, y1: float, x2: float, y2: float) -> float:
    """Give the distance of the origin from the segment from `x1, y1` to `x2, y2`."""
    dx, dy = x2 - x1, y2 - y1
    length = dx * dx + dy * dy
    # a segment of no length is its end; otherwise the foot of the perpendicular, kept on the segment
    t = 0.0 if length == 0 else max(0.0, min(1.0, -(x1 * dx + y1 * dy) / length))
    return math.hypot(x1 + t * dx, y1 + t * dy)


def outline_distance_km(geometry: dict[str, Any] | None, latitude: float, longitude: float) -> float | None:
    """Give the distance in km from a point to a cell's outline: 0 where the outline contains it, `None` for no outline.

    `geometry` is the GeoJSON `Polygon` or `MultiPolygon` of a cell (rings of `[longitude, latitude]`, closed).
    """
    if not geometry:
        return None
    polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    scale = math.cos(math.radians(latitude))
    nearest = math.inf
    for polygon in polygons:
        exterior = polygon[0]
        if locate(exterior, longitude, latitude) != OUTSIDE:
            return 0.0
        projected = [
            ((lon - longitude) * scale * _KM_PER_DEGREE, (lat - latitude) * _KM_PER_DEGREE) for lon, lat in exterior
        ]
        nearest = min(nearest, *(_segment_distance(*a, *b) for a, b in pairwise(projected)))
    return None if math.isinf(nearest) else nearest


def is_for_point(geometry: dict[str, Any] | None, latitude: float, longitude: float, distance: float = 0.0) -> bool:
    """Tell whether an outline contains the point or is within `distance` km of it; no outline is never for a point."""
    nearest = outline_distance_km(geometry, latitude, longitude)
    return nearest is not None and nearest <= distance


def is_for_box(
    geometry: dict[str, Any] | None,
    left: float,
    bottom: float,
    right: float,
    top: float,
) -> bool:
    """Tell whether an outline reaches into a box: an edge with a part in it, or the outline around it.

    The test is planar in degrees, as the box is.
    """
    if not geometry:
        return False
    polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
    for polygon in polygons:
        exterior = polygon[0]
        lons = [lon for lon, _ in exterior]
        lats = [lat for _, lat in exterior]
        if max(lons) < left or min(lons) > right or max(lats) < bottom or min(lats) > top:
            continue
        # the boxes of outline and box meet. The outline reaches into the box if one of its edges has a part in it (a
        # vertex in the box is the end of two), or, with no edge in it, if it goes around the box: then any corner of
        # the box is inside it
        if any(_crosses_box(a, b, left, bottom, right, top) for a, b in pairwise(exterior)):
            return True
        if locate(exterior, left, bottom) != OUTSIDE:
            return True
    return False


def _crosses_box(a: list[float], b: list[float], left: float, bottom: float, right: float, top: float) -> bool:
    """Tell whether the segment from `a` to `b` crosses an edge of the box (Liang-Barsky clipping)."""
    x1, y1 = a
    x2, y2 = b
    dx, dy = x2 - x1, y2 - y1
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x1 - left), (dx, right - x1), (-dy, y1 - bottom), (dy, top - y1)):
        if p == 0:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return True
