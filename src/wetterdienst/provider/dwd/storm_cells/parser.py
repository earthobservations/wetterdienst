# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Parser for the XML files of DWD's KONRAD3D thunderstorm cells (data model 1.7).

A file holds a `head` (the run: its reference time, the time it was written, the radar sweeps that went into it) and
`cells`, one `feature` for every cell found in the scan. An empty scan is a complete `head` and a `cells` element with
no `feature`, which is the usual case. DWD's format description allows several `cells` for several times, "in the
standard case" there is one, and several polygons for the outline of one cell, which are parts of a cell that the
projection fell apart into: both are read.

Only the attributes that answer "where is the storm and how bad is it" are read; the research detail of a cell (the
hydrometeor classification, the environment from the NWP model, the lightning history, the mesocyclone group) is left
in the XML, which `DwdRadarValues` serves as DWD wrote it.

DWD writes `-1000000000` for a number it does not have and `not-a-date-time` for a time, in every element: both are
`None` here.
"""

from __future__ import annotations

import datetime as dt
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from wetterdienst.provider.dwd.storm_cells.metadata import MISSING_NUMBER, MISSING_TIME
from wetterdienst.util.xml import parse_xml

if TYPE_CHECKING:
    from lxml.etree import _Element

UTC = ZoneInfo("UTC")

#: the mean radius of the Earth in km, for the bearing and the distance of a place from a cell
EARTH_RADIUS_KM = 6371.0088


@dataclass(frozen=True)
class Scan:
    """What a KONRAD3D file holds: when the scan was, when the file was written, and its cells."""

    #: the reference time of the run, the start of the radar scan cycle (UTC); `None` if the file states none
    reference_time: dt.datetime | None
    #: when DWD wrote the file (`creation-date`, UTC); `None` if the file states none
    created_at: dt.datetime | None
    #: one dict for each cell, in the order of the file, keyed as `CELL_COLUMNS` of the API
    cells: list[dict[str, Any]]


def _number(element: _Element | None) -> float | None:
    """Read a number, `None` for no element, an empty one and DWD's missing value."""
    if element is None or element.text is None:
        return None
    text = element.text.strip()
    if not text:
        return None
    value = float(text)
    if value == MISSING_NUMBER or not math.isfinite(value):
        return None
    return value


def _integer(element: _Element | None) -> int | None:
    """Read a whole number (a count, a flag, a severity), `None` where `_number` gives none."""
    value = _number(element)
    return None if value is None else round(value)


def _time(text: str | None) -> dt.datetime | None:
    """Read an ISO 8601 time (UTC, `Z`), `None` for no text and DWD's `not-a-date-time`."""
    if text is None:
        return None
    text = text.strip()
    if not text or text == MISSING_TIME:
        return None
    parsed = dt.datetime.fromisoformat(text)
    return parsed.replace(tzinfo=UTC) if parsed.tzinfo is None else parsed.astimezone(UTC)


def _flag(element: _Element | None) -> bool | None:
    """Read a boolean written as `true` or `false`, `None` for no element."""
    if element is None or element.text is None:
        return None
    return element.text.strip().lower() == "true"


def _ring(latitudes: str, longitudes: str) -> list[list[float]] | None:
    """Make a closed GeoJSON ring (`[longitude, latitude]` pairs) of the two lists DWD writes, `None` if it is none.

    DWD writes the vertices counter-clockwise and does not repeat the first at the end, which GeoJSON asks for.
    """
    lats = [float(value) for value in latitudes.split()]
    lons = [float(value) for value in longitudes.split()]
    if len(lats) != len(lons):
        msg = f"a polygon has {len(lats)} latitudes and {len(lons)} longitudes"
        raise ValueError(msg)
    ring = [[lon, lat] for lat, lon in zip(lats, lons, strict=True)]
    if ring and ring[0] != ring[-1]:
        ring.append(list(ring[0]))
    # a closed ring of fewer than 3 distinct vertices is a point or a line, no outline
    return ring if len(ring) >= 4 else None


def bearing_degrees(latitude1: float, longitude1: float, latitude2: float, longitude2: float) -> float | None:
    """Give the initial bearing from the first point to the second, in degrees clockwise from north, 0 up to 360.

    `None` for two points that are one.
    """
    if (latitude1, longitude1) == (latitude2, longitude2):
        return None
    phi1, phi2 = math.radians(latitude1), math.radians(latitude2)
    delta = math.radians(longitude2 - longitude1)
    x = math.sin(delta) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(delta)
    return round(math.degrees(math.atan2(x, y)) % 360, 1)


def _track(cell: _Element) -> list[dict[str, Any]]:
    """Read the forecast positions of a cell in time order: its centre ahead, each with its 1 sigma ellipse."""
    track = []
    for forecast in cell.iterfind("forecast/centroid_forecasts/centroid_forecast"):
        position = forecast.find("geodetic_coordinate")
        if position is None:
            continue
        ellipse = forecast.find("uncertainty_ellipse")
        track.append(
            {
                "time": _time(forecast.get("forecast_time")),
                "latitude": _number(position.find("latitude")),
                "longitude": _number(position.find("longitude")),
                "uncertainty_major_km": _number(ellipse.find("major_axis")) if ellipse is not None else None,
                "uncertainty_minor_km": _number(ellipse.find("minor_axis")) if ellipse is not None else None,
                "uncertainty_angle_degrees": _number(ellipse.find("angle")) if ellipse is not None else None,
            }
        )
    track.sort(key=lambda point: (point["time"] is None, point["time"]))
    return track


def _direction(track: list[dict[str, Any]]) -> float | None:
    """Calculate the bearing of the cell's motion from its first two forecast positions, `None` if it has not two."""
    if len(track) < 2:
        return None
    first, second = track[0], track[1]
    values = (first["latitude"], first["longitude"], second["latitude"], second["longitude"])
    if any(value is None for value in values):
        return None
    return bearing_degrees(*values)


def _predecessor_code(cell: _Element) -> str | None:
    """Give the code of the cell's predecessor in the run before: the one DWD is surest of, the first of those."""
    best: tuple[float, str] | None = None
    for predecessor in cell.iterfind("tracking/predecessors/predecessor"):
        code = (predecessor.findtext("code") or "").strip()
        if not code:
            continue
        # the probability is 100 or 0 (0 is a merger's predecessor)
        probability = _number(predecessor.find("probability"))
        score = -1.0 if probability is None else probability
        if best is None or score > best[0]:
            best = (score, code)
    return None if best is None else best[1]


def _parse_cell(cell: _Element, reference_time: dt.datetime | None) -> dict[str, Any]:
    """Read one `feature` into a flat row of the attributes the answer holds, the outline and the track nested."""
    identifier = (cell.get("identifier") or cell.findtext("metadata/identifier") or "").strip()
    split = _flag(cell.find("tracking/splits/split_event"))
    merge = _flag(cell.find("tracking/mergers/merge_event"))
    rings = []
    for polygon in cell.iterfind("geometry/polygons_projected/geodetic_coordinates/polygon"):
        ring = _ring(polygon.findtext("latitudes") or "", polygon.findtext("longitudes") or "")
        if ring is not None:
            rings.append(ring)
    track = _track(cell)
    return {
        "reference_time": _time(cell.findtext("metadata/reference_time")) or reference_time,
        "cell_id": identifier.rstrip("*#") or None,
        "code": (cell.findtext("metadata/code") or "").strip() or None,
        "predecessor_code": _predecessor_code(cell),
        # `*` and `#` after the identifier say it too, for one step: the element is the one that is read
        "split_event": identifier.endswith("*") if split is None else split,
        "merge_event": identifier.endswith("#") if merge is None else merge,
        "first_detection": _time(cell.findtext("tracking/reference_time_first_detection")),
        "number_detections": _integer(cell.find("tracking/number_detections")),
        "severity": _integer(cell.find("intensity/severity")),
        "severity_decimal": _number(cell.find("intensity/severity_decimal")),
        "hail_flag": _integer(cell.find("intensity/hail_flag")),
        "heavy_rain_flag": _integer(cell.find("intensity/heavy_rain_flag")),
        "gust_flag": _integer(cell.find("intensity/gust_flag")),
        "centroid_latitude": _number(cell.find("geometry/centroid_3d/geodetic_coordinate/latitude")),
        "centroid_longitude": _number(cell.find("geometry/centroid_3d/geodetic_coordinate/longitude")),
        "cell_speed_kmh": _number(cell.find("tracking/cell_speed")),
        "direction_degrees": _direction(track),
        "covered_area_km2": _number(cell.find("geometry/covered_area")),
        "echo_top_msl_m": _number(cell.find("geometry/echo_top_msl")),
        "max_reflectivity_dbz": _number(cell.find("intensity/max_value")),
        "vil_kg_m2": _number(cell.find("intensity/cell_based_VIL")),
        "max_estimated_gust_kmh": _number(cell.find("intensity/maximum_estimated_wind_gust")),
        "heavy_rain_potential_mm": _number(cell.find("intensity/heavy_rain_potential")),
        "rings": rings,
        "track": track,
    }


def parse_scan(content: bytes) -> Scan:
    """Parse a KONRAD3D file into its scan: the times of the run and a row for every cell of every `cells` element.

    Raises:
        ValueError: the file is no KONRAD3D document, or an element holds what is no number or time. lxml's
            `XMLSyntaxError` (a `SyntaxError`) is raised for XML that does not parse, a file read while it was written.

    """
    root = parse_xml(content)
    if root.tag != "konrad3d":
        msg = f"the document is no KONRAD3D file, its root is <{root.tag}>"
        raise ValueError(msg)
    reference_time = _time(root.findtext("head/metadata/reference_time"))
    created_at = _time(root.findtext("head/product/creation-date"))
    cells: list[dict[str, Any]] = []
    for block in root.iterfind("cells"):
        block_time = _time(block.get("reference_time")) or reference_time
        cells.extend(_parse_cell(feature, block_time) for feature in block.iterfind("feature"))
        reference_time = reference_time or block_time
    return Scan(reference_time=reference_time, created_at=created_at, cells=cells)
