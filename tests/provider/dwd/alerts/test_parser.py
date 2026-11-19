# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Offline tests for the DWD CAP weather-alerts parser."""

from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from tests.provider.dwd.alerts.stubs import CAP_MUL, CAP_MUL_LANGUAGES
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


# --- the further <info> blocks of a message: the other languages of `mul` (GH-3801) --------------------------------

_TEXTS = ("event", "headline", "description", "instruction")


def test_a_message_of_one_info_has_no_translations() -> None:
    """The single-language products have one `<info>` each, and nothing is said of more."""
    alert = parse_cap_alert(CAP_XML)
    assert alert is not None
    assert alert["translations"] == []


def test_a_mul_message_is_the_first_language_and_the_seven_others_as_translations() -> None:
    """The row is the first (German) block's, as it was; the seven further blocks are kept, each by its language."""
    alert = parse_cap_alert(CAP_MUL)
    assert alert is not None
    assert alert["language"] == CAP_MUL_LANGUAGES[0] == "de-DE"
    assert alert["event"] == "NEBEL"
    assert alert["headline"] == "Amtliche WARNUNG vor NEBEL"
    assert [translation["language"] for translation in alert["translations"]] == CAP_MUL_LANGUAGES[1:]


def test_the_languages_of_a_mul_message_differ_in_four_texts_and_translations_hold_only_those() -> None:
    """The times, codes, parameter and area of the real message are the same in each block: only the texts differ."""
    alert = parse_cap_alert(CAP_MUL)
    assert alert is not None
    assert len(alert["translations"]) == 7
    for translation in alert["translations"]:
        assert set(translation) == {"language", *_TEXTS}, translation["language"]
        assert all(translation[text] != alert[text] for text in _TEXTS)
    english, french, _spanish, arabic, *_others = alert["translations"]
    assert english["event"] == "fog"
    assert english["headline"] == "Official WARNING of FOG"
    assert english["description"].startswith("There is a risk of fog (level 1 of 1).")
    # the text of the message is stripped as the first block's is, the line breaks inside it kept
    assert french["event"] == "Brouillard"
    # (DWD writes a no-break space before a colon in French)
    assert french["instruction"].startswith("Attention\xa0: fortes réductions éventuelles de la visibilité.")
    assert "\nRecommandations d'action\xa0:" in french["instruction"]
    # a right-to-left text and a non-Latin one arrive as they are written
    assert arabic["event"] == "الضباب"
    assert alert["translations"][4]["event"] == "Туман"


def test_what_the_languages_share_is_in_the_row_once() -> None:
    """A field that is in no translation is the first block's, which the row holds: the area, the codes, the times."""
    alert = parse_cap_alert(CAP_MUL)
    assert alert is not None
    assert alert["warncell_ids"] == ["115091000"]
    assert alert["area_names"] == ["Kreis Wittenberg"]
    assert alert["event_code"] == "59"
    assert alert["groups"] == ["FOG"]
    assert alert["parameters"] == [{"name": "visibility", "value": "<150 [m]"}]
    assert alert["geometry"]["type"] == "MultiPolygon"
    assert alert["onset"] == dt.datetime(2026, 11, 5, 22, 59, tzinfo=UTC)
    assert alert["expires"] == dt.datetime(2026, 11, 6, 8, 0, tzinfo=UTC)


def test_a_further_info_that_differs_in_more_than_text_says_so() -> None:
    """Nothing is dropped if DWD ever lets a block differ in more than text: the field is in its translation."""
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>x</identifier>
  <info>
    <language>de-DE</language>
    <event>FROST</event>
    <onset>2026-07-26T21:00:00+02:00</onset>
    <eventCode><valueName>II</valueName><value>22</value></eventCode>
    <parameter><valueName>min</valueName><value>-2</value></parameter>
    <area><areaDesc>Stadt Hof</areaDesc><geocode><valueName>WARNCELLID</valueName><value>1</value></geocode></area>
  </info>
  <info>
    <language>en</language>
    <event>frost</event>
    <onset>2026-07-26T22:00:00+02:00</onset>
    <eventCode><valueName>II</valueName><value>22</value></eventCode>
    <parameter><valueName>min</valueName><value>-3</value></parameter>
    <area><areaDesc>Stadt Hof</areaDesc><geocode><valueName>WARNCELLID</valueName><value>2</value></geocode></area>
  </info>
  <info>
    <language>fr</language>
    <event>gel</event>
    <onset>2026-07-26T21:00:00+02:00</onset>
    <eventCode><valueName>II</valueName><value>22</value></eventCode>
    <parameter><valueName>min</valueName><value>-2</value></parameter>
    <area><areaDesc>Stadt Hof</areaDesc><geocode><valueName>WARNCELLID</valueName><value>1</value></geocode></area>
  </info>
</alert>"""
    alert = parse_cap_alert(xml)
    assert alert is not None
    assert alert["translations"] == [
        {
            "language": "en",
            "event": "frost",
            "onset": "2026-07-26T20:00:00.000000+00:00",
            "parameters": [{"name": "min", "value": "-3"}],
            "warncell_ids": ["2"],
        },
        {"language": "fr", "event": "gel"},
    ]


def test_a_further_info_without_a_text_the_first_has_says_so_with_a_null() -> None:
    """A text a block lacks is null in its translation, not the first block's text taken for it."""
    xml = b"""<?xml version="1.0" encoding="UTF-8"?>
<alert xmlns="urn:oasis:names:tc:emergency:cap:1.2">
  <identifier>x</identifier>
  <info><language>de-DE</language><event>FROST</event><instruction>Vorsicht</instruction></info>
  <info><language>en</language><event>frost</event></info>
</alert>"""
    alert = parse_cap_alert(xml)
    assert alert is not None
    assert alert["translations"] == [{"language": "en", "event": "frost", "instruction": None}]


def test_a_message_without_an_info_has_empty_translations() -> None:
    """An alert without any `<info>` is only the header, and its `translations` is `[]` like every row's, not null."""
    alert = parse_cap_alert(b"<alert xmlns='urn:oasis:names:tc:emergency:cap:1.2'><identifier>x</identifier></alert>")
    assert alert is not None
    assert alert["translations"] == []


# the rule that attaches a hole to a polygon of an area with several: the one that has most of its vertices
_SQUARE = [[0.0, 0.0], [10.0, 0.0], [10.0, 10.0], [0.0, 10.0], [0.0, 0.0]]
_NEIGHBOUR = [[10.5, 4.0], [12.0, 4.0], [12.0, 6.0], [10.5, 6.0], [10.5, 4.0]]


def test_a_hole_goes_to_the_polygon_that_has_most_of_its_vertices() -> None:
    """Not the one with its first vertex: a hole with three vertices in the square and one in the neighbour is its."""
    from wetterdienst.provider.dwd.alerts.parser import _attach_holes  # noqa: PLC0415

    # the first vertex lies in the neighbour, the other three in the square
    hole = [[11.0, 5.0], [5.0, 5.0], [6.0, 6.0], [7.0, 5.0], [11.0, 5.0]]
    assert _attach_holes([_NEIGHBOUR, _SQUARE], [hole]) == [[_NEIGHBOUR], [_SQUARE, hole]]


def test_a_hole_whose_first_vertex_is_in_no_polygon_is_still_attached() -> None:
    """The first vertex of a hole may be outside by a rounding or on an edge (east of Rügen): the rest decide."""
    from wetterdienst.provider.dwd.alerts.parser import _attach_holes  # noqa: PLC0415

    hole = [[10.0000001, 5.0], [5.0, 5.0], [6.0, 6.0], [10.0000001, 5.0]]
    assert _attach_holes([_NEIGHBOUR, _SQUARE], [hole]) == [[_NEIGHBOUR], [_SQUARE, hole]]


def test_a_hole_in_no_polygon_is_left_out_and_a_tie_goes_to_the_first() -> None:
    """A hole that touches none is dropped; one that two polygons have equally is the first's, whatever the order."""
    from wetterdienst.provider.dwd.alerts.parser import _attach_holes  # noqa: PLC0415

    far = [[50.0, 50.0], [51.0, 50.0], [51.0, 51.0], [50.0, 50.0]]
    assert _attach_holes([_SQUARE, _NEIGHBOUR], [far]) == [[_SQUARE], [_NEIGHBOUR]]
    twin = [list(point) for point in _SQUARE]
    twin_hole = [[2.0, 2.0], [3.0, 2.0], [3.0, 3.0], [2.0, 2.0]]
    assert _attach_holes([_SQUARE, twin], [twin_hole]) == [[_SQUARE, twin_hole], [twin]]
