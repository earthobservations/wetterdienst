"""A vector basemap for the station map, cut out of a GeoJSON file of country polygons.

The Plotly station map draws raster tiles that its browser fetches from the net while it renders. A static
vector chart has none, so the prototype draws the country borders of a file the caller names (Natural Earth,
public domain, `ne_50m_admin_0_countries.geojson`), cut down to the countries that touch the view.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _bounds(geometry: dict[str, Any]) -> tuple[float, float, float, float]:
    """Return west, south, east, north of a GeoJSON (Multi)Polygon."""
    polygons = geometry["coordinates"] if geometry["type"] == "MultiPolygon" else [geometry["coordinates"]]
    xs = [x for polygon in polygons for ring in polygon for x, _ in ring]
    ys = [y for polygon in polygons for ring in polygon for _, y in ring]
    return min(xs), min(ys), max(xs), max(ys)


def load_features(path: Path, west: float, south: float, east: float, north: float) -> list[dict[str, Any]]:
    """Return the features of the file whose bounding box meets the view, with their properties dropped."""
    collection = json.loads(Path(path).read_text(encoding="utf-8"))
    features = []
    for feature in collection["features"]:
        w, s, e, n = _bounds(feature["geometry"])
        if w <= east and e >= west and s <= north and n >= south:
            features.append({"type": "Feature", "properties": {}, "geometry": feature["geometry"]})
    return features
