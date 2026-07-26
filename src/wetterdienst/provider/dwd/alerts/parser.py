# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Parser for DWD Common Alerting Protocol (CAP) v1.2 warning documents.

Each CAP file holds exactly one ``<alert>`` with one or more ``<info>`` blocks (one per language)
and one or more ``<area>`` blocks. We flatten a single alert into one row: the alert/info fields
plus the union of all polygon areas as a GeoJSON ``MultiPolygon`` geometry, and the list of the
entity areas' ``WARNCELLID`` geocodes and names. See the official "CAP DWD Profile" for the schema.
"""

from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING, Any
from zoneinfo import ZoneInfo

from lxml.etree import XMLParser, fromstring

if TYPE_CHECKING:
    from lxml.etree import _Element

# Disable entity resolution and network access -- DWD is first-party, but there is no reason to
# fetch external entities/DTDs and it guards against XXE (matching the DWD mosmix KML reader and
# the FMI parser).
_XML_PARSER = XMLParser(resolve_entities=False, no_network=True)


def _local_name(tag: object) -> str:
    """Return an element's local name, stripping lxml's ``{namespace}`` prefix.

    lxml yields non-element nodes (comments, processing instructions) with a callable ``tag``
    during iteration; those are reported as an empty local name so callers skip them.
    """
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1]


def _text(element: _Element | None) -> str | None:
    """Return the stripped text of an element, or ``None`` if empty/absent."""
    if element is None or element.text is None:
        return None
    return element.text.strip() or None


def _parse_datetime(text: str | None) -> dt.datetime | None:
    """Parse a CAP timestamp (local time with offset, e.g. ``2026-07-26T09:23:00+02:00``) to UTC."""
    if not text:
        return None
    parsed = dt.datetime.fromisoformat(text)
    return parsed.astimezone(ZoneInfo("UTC"))


def _parse_polygon(text: str) -> list[list[float]]:
    """Parse a CAP polygon (whitespace-delimited ``lat,lon`` pairs) into a GeoJSON ring.

    CAP orders coordinates as ``latitude,longitude`` while GeoJSON expects ``[longitude, latitude]``,
    so the pair is swapped here.
    """
    ring = []
    for pair in text.split():
        lat, lon = pair.split(",")
        ring.append([float(lon), float(lat)])
    return ring


def _collect_key_values(info: _Element, container: str) -> list[tuple[str, str]]:
    """Return the ``(valueName, value)`` pairs of every ``container`` child of ``info``.

    Used for both ``<eventCode>`` and ``<parameter>`` elements, which share the same
    ``<valueName>``/``<value>`` layout.
    """
    pairs = []
    for element in info:
        if _local_name(element.tag) != container:
            continue
        name = value = None
        for child in element:
            tag = _local_name(child.tag)
            if tag == "valueName":
                name = _text(child)
            elif tag == "value":
                value = _text(child)
        if name is not None:
            pairs.append((name, value or ""))
    return pairs


def _parse_area(area: _Element) -> dict[str, Any]:  # noqa: C901
    """Parse a single ``<area>`` block.

    Returns its ``areaDesc``, the exterior polygon rings it defines, the ``EXCLUDE_POLYGON`` holes,
    and any ``WARNCELLID`` geocodes. A DWD area is either polygon-based (``areaDesc`` = "polygonal
    event area") or entity-based (a named Gemeinde/Landkreis carrying a ``WARNCELLID``).
    """
    area_desc = None
    polygons: list[list[list[float]]] = []
    holes: list[list[list[float]]] = []
    warncell_ids: list[str] = []
    for element in area:
        tag = _local_name(element.tag)
        if tag == "areaDesc":
            area_desc = _text(element)
        elif tag == "polygon":
            text = _text(element)
            if text:
                polygons.append(_parse_polygon(text))
        elif tag == "geocode":
            name = value = None
            for child in element:
                child_tag = _local_name(child.tag)
                if child_tag == "valueName":
                    name = _text(child)
                elif child_tag == "value":
                    value = _text(child)
            if name == "WARNCELLID" and value:
                warncell_ids.append(value)
            elif name == "EXCLUDE_POLYGON" and value:
                holes.append(_parse_polygon(value))
    return {
        "area_desc": area_desc,
        "polygons": polygons,
        "holes": holes,
        "warncell_ids": warncell_ids,
    }


def _build_multipolygon(areas: list[dict[str, Any]]) -> dict[str, Any] | None:
    """Combine all polygon areas into a single GeoJSON ``MultiPolygon`` (or ``None`` if there are none).

    Per the DWD profile, an area with a hole (``EXCLUDE_POLYGON``) carries exactly one ``<polygon>``,
    so holes are attached to that polygon; areas with multiple polygons get one GeoJSON polygon each
    without holes.
    """
    coordinates: list[list[list[list[float]]]] = []
    for area in areas:
        polygons = area["polygons"]
        holes = area["holes"]
        if not polygons:
            continue
        if len(polygons) == 1:
            coordinates.append([polygons[0], *holes])
        else:
            coordinates.extend([polygon] for polygon in polygons)
    if not coordinates:
        return None
    return {"type": "MultiPolygon", "coordinates": coordinates}


def parse_cap_alert(content: bytes) -> dict[str, Any] | None:  # noqa: C901
    """Parse one CAP XML document into a flat alert row, or ``None`` if it is not an alert.

    Only the first ``<info>`` block is honoured, which for the single-language products is the only
    one; for the ``MUL`` product it is the first bundled language.
    """
    root = fromstring(content, parser=_XML_PARSER)
    if _local_name(root.tag) != "alert":
        return None

    alert: dict[str, Any] = {
        "alert_id": None,
        "status": None,
        "msg_type": None,
        "references": None,
    }
    info = None
    for element in root:
        tag = _local_name(element.tag)
        if tag == "identifier":
            alert["alert_id"] = _text(element)
        elif tag == "status":
            alert["status"] = _text(element)
        elif tag == "msgType":
            alert["msg_type"] = _text(element)
        elif tag == "sent":
            alert["sent"] = _parse_datetime(_text(element))
        elif tag == "references":
            alert["references"] = _text(element)
        elif tag == "info" and info is None:
            info = element

    if info is None:
        return alert

    simple_fields = {
        "language": "language",
        "category": "category",
        "event": "event",
        "responseType": "response_type",
        "urgency": "urgency",
        "severity": "severity",
        "certainty": "certainty",
        "senderName": "sender_name",
        "headline": "headline",
        "description": "description",
        "instruction": "instruction",
        "web": "web",
        "contact": "contact",
    }
    datetime_fields = {"effective": "effective", "onset": "onset", "expires": "expires"}
    for key in (*simple_fields.values(), *datetime_fields.values()):
        alert.setdefault(key, None)

    areas: list[dict[str, Any]] = []
    for element in info:
        tag = _local_name(element.tag)
        if tag in simple_fields:
            alert[simple_fields[tag]] = _text(element)
        elif tag in datetime_fields:
            alert[datetime_fields[tag]] = _parse_datetime(_text(element))
        elif tag == "area":
            areas.append(_parse_area(element))

    event_codes = _collect_key_values(info, "eventCode")
    groups = [value for name, value in event_codes if name == "GROUP"]
    event_code_map = dict(event_codes)
    alert["event_code"] = event_code_map.get("II")
    alert["groups"] = groups
    alert["area_color"] = event_code_map.get("AREA_COLOR")
    # Kept as an ordered list of {name, value} rather than a dict: the DWD profile allows a
    # <parameter> valueName to repeat within one alert (e.g. a veering "wind direction" given
    # several times), which a dict would silently collapse to the last value.
    alert["parameters"] = [{"name": name, "value": value} for name, value in _collect_key_values(info, "parameter")]

    warncell_ids = [warncell_id for area in areas for warncell_id in area["warncell_ids"]]
    area_names = [area["area_desc"] for area in areas if area["warncell_ids"] and area["area_desc"] is not None]
    alert["warncell_ids"] = warncell_ids
    alert["area_names"] = area_names
    alert["geometry"] = _build_multipolygon(areas)

    return alert
