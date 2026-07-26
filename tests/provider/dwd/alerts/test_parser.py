# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Offline tests for the DWD CAP weather-alerts parser."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from wetterdienst.provider.dwd.alerts.parser import parse_cap_alert

# A minimal but representative CAP v1.2 document following the DWD profile: one polygon area (with a
# hole), two named entity areas carrying WARNCELLIDs, event codes and parameters, and an expires.
CAP_XML = b"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>2.49.0.0.276.0.DWD.PVW.1785050580000.6bd1534c-24c8-4860-84a8-e89bab416fcd.ENG</identifier>
  <sender>opendata@dwd.de</sender>
  <sent>2026-07-26T09:23:00+02:00</sent>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <source>PVW</source>
  <scope>Public</scope>
  <code>id:2.49.0.0.276.0.DWD.PVW.1785050580000.6bd1534c-24c8-4860-84a8-e89bab416fcd</code>
  <references>opendata@dwd.de,2.49.0.0.276.0.DWD.PVW.1.x.ENG,2026-07-26T09:00:00+02:00</references>
  <info>
    <language>en</language>
    <category>Met</category>
    <event>gale-force gusts</event>
    <responseType>Prepare</responseType>
    <urgency>Immediate</urgency>
    <severity>Moderate</severity>
    <certainty>Likely</certainty>
    <eventCode><valueName>PROFILE_VERSION</valueName><value>2.1.14</value></eventCode>
    <eventCode><valueName>II</valueName><value>52</value></eventCode>
    <eventCode><valueName>GROUP</valueName><value>WIND</value></eventCode>
    <eventCode><valueName>AREA_COLOR</valueName><value>251 140 0</value></eventCode>
    <effective>2026-07-26T09:23:00+02:00</effective>
    <onset>2026-07-26T21:00:00+02:00</onset>
    <expires>2026-07-27T14:00:00+02:00</expires>
    <senderName>Deutscher Wetterdienst</senderName>
    <headline>Official WARNING of GALE-FORCE GUSTS</headline>
    <description>There is a risk of gale-force gusts (level 2 of 4).</description>
    <instruction>Secure free-standing objects.</instruction>
    <web>https://dwd.de/warnungen</web>
    <contact>Deutscher Wetterdienst</contact>
    <parameter><valueName>gusts</valueName><value>65-75 [km/h]</value></parameter>
    <parameter><valueName>wind direction</valueName><value>west</value></parameter>
    <area>
      <areaDesc>polygonal event area</areaDesc>
      <polygon>49.0,12.0 49.0,13.0 50.0,13.0 50.0,12.0 49.0,12.0</polygon>
      <geocode>
        <valueName>EXCLUDE_POLYGON</valueName>
        <value>49.4,12.4 49.4,12.6 49.6,12.6 49.6,12.4 49.4,12.4</value>
      </geocode>
    </area>
    <area>
      <areaDesc>Gemeinde Grainet</areaDesc>
      <geocode><valueName>WARNCELLID</valueName><value>809272121</value></geocode>
    </area>
    <area>
      <areaDesc>Stadt Zwiesel</areaDesc>
      <geocode><valueName>WARNCELLID</valueName><value>809276148</value></geocode>
    </area>
  </info>
</alert>
"""

UTC = ZoneInfo("UTC")


def test_parse_cap_alert_scalar_fields() -> None:
    """Verify the alert/info scalar fields are extracted and timestamps normalised to UTC."""
    alert = parse_cap_alert(CAP_XML)
    assert alert is not None
    assert alert["alert_id"] == "2.49.0.0.276.0.DWD.PVW.1785050580000.6bd1534c-24c8-4860-84a8-e89bab416fcd.ENG"
    assert alert["status"] == "Actual"
    assert alert["msg_type"] == "Alert"
    assert alert["language"] == "en"
    assert alert["category"] == "Met"
    assert alert["event"] == "gale-force gusts"
    assert alert["response_type"] == "Prepare"
    assert alert["urgency"] == "Immediate"
    assert alert["severity"] == "Moderate"
    assert alert["certainty"] == "Likely"
    assert alert["headline"] == "Official WARNING of GALE-FORCE GUSTS"
    assert alert["sender_name"] == "Deutscher Wetterdienst"
    assert alert["references"].startswith("opendata@dwd.de,")
    # 09:23:00+02:00 -> 07:23:00Z
    assert alert["sent"] == dt.datetime(2026, 7, 26, 7, 23, tzinfo=UTC)
    assert alert["effective"] == dt.datetime(2026, 7, 26, 7, 23, tzinfo=UTC)
    assert alert["onset"] == dt.datetime(2026, 7, 26, 19, 0, tzinfo=UTC)
    assert alert["expires"] == dt.datetime(2026, 7, 27, 12, 0, tzinfo=UTC)


def test_parse_cap_alert_event_codes_and_parameters() -> None:
    """Verify event codes (II, GROUP, AREA_COLOR) and parameters are mapped correctly."""
    alert = parse_cap_alert(CAP_XML)
    assert alert is not None
    assert alert["event_code"] == "52"
    assert alert["groups"] == ["WIND"]
    assert alert["area_color"] == "251 140 0"
    assert alert["parameters"] == [
        {"name": "gusts", "value": "65-75 [km/h]"},
        {"name": "wind direction", "value": "west"},
    ]


def test_parse_cap_alert_areas_and_warncells() -> None:
    """Verify entity areas expose their WARNCELLIDs and names, in document order."""
    alert = parse_cap_alert(CAP_XML)
    assert alert is not None
    assert alert["warncell_ids"] == ["809272121", "809276148"]
    assert alert["area_names"] == ["Gemeinde Grainet", "Stadt Zwiesel"]


def test_parse_cap_alert_geometry_is_multipolygon_with_hole() -> None:
    """Verify polygon areas become a GeoJSON MultiPolygon with lon/lat order and the hole attached."""
    alert = parse_cap_alert(CAP_XML)
    assert alert is not None
    geometry = alert["geometry"]
    assert geometry["type"] == "MultiPolygon"
    # one polygon area -> one member polygon, with exterior ring + one hole ring
    assert len(geometry["coordinates"]) == 1
    polygon = geometry["coordinates"][0]
    assert len(polygon) == 2  # exterior + hole
    exterior = polygon[0]
    # CAP "49.0,12.0" (lat,lon) -> GeoJSON [12.0, 49.0] (lon,lat)
    assert exterior[0] == [12.0, 49.0]
    assert exterior[0] == exterior[-1]  # ring is closed
    hole = polygon[1]
    assert hole[0] == [12.4, 49.4]


def test_parse_cap_alert_without_polygon_has_null_geometry() -> None:
    """Verify an alert with only entity (WARNCELLID) areas yields a null geometry."""
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>x</identifier>
  <status>Actual</status>
  <msgType>Alert</msgType>
  <info>
    <event>near gale</event>
    <area>
      <areaDesc>Ostlich Rugen</areaDesc>
      <geocode><valueName>WARNCELLID</valueName><value>501000008</value></geocode>
    </area>
  </info>
</alert>"""
    alert = parse_cap_alert(xml)
    assert alert is not None
    assert alert["geometry"] is None
    assert alert["warncell_ids"] == ["501000008"]


def test_parse_cap_alert_keeps_repeated_parameters() -> None:
    """Verify a <parameter> valueName repeated within one alert is preserved (not collapsed)."""
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>x</identifier>
  <info>
    <event>gale-force gusts</event>
    <parameter><valueName>wind direction</valueName><value>west</value></parameter>
    <parameter><valueName>wind direction</valueName><value>north-west</value></parameter>
    <parameter><valueName>wind direction</valueName><value>north</value></parameter>
  </info>
</alert>"""
    alert = parse_cap_alert(xml)
    assert alert is not None
    assert alert["parameters"] == [
        {"name": "wind direction", "value": "west"},
        {"name": "wind direction", "value": "north-west"},
        {"name": "wind direction", "value": "north"},
    ]


def test_parse_cap_alert_non_alert_returns_none() -> None:
    """Verify a non-alert document is rejected."""
    assert parse_cap_alert(b"<something xmlns='urn:x'><child/></something>") is None
