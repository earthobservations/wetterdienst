# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The place filter of the DWD weather alerts (GH-4019): a point in the polygons of a warning, or a name or warn cell.

A snapshot is every warning of Germany, which is more than an assistant can read; a place keeps the few that are for it.
The tests read real messages of DWD (`stubs.py`), served as a snapshot, so that the filter is held to the polygons and
areas DWD writes, not to ones made up for it.
"""

from __future__ import annotations

import datetime as dt
import json
from typing import TYPE_CHECKING

import pytest

from wetterdienst.exceptions import RequestError
from wetterdienst.provider.dwd.alerts import DwdWeatherAlertRequest
from wetterdienst.provider.dwd.alerts.api import NO_ALERTS_FOR_PLACE
from wetterdienst.provider.dwd.alerts.parser import parse_cap_alert
from wetterdienst.provider.dwd.alerts.place import geometry_contains, is_for_place, names_match
from wetterdienst.util.response_warnings import begin_response, recorded_warnings

from .stubs import (
    CAP_COMMUNITY_KIEL,
    CAP_COMMUNITY_NORDERNEY,
    CAP_COMMUNITY_SEA,
    CAP_DISTRICT_HELGOLAND,
    CAP_DISTRICT_KIEL,
    CAP_DISTRICT_RASTATT,
    CAP_DISTRICT_RUEGEN,
    serve_snapshot,
)

if TYPE_CHECKING:
    from typing import Any

# places, as latitude and longitude
KIEL = (54.3233, 10.1228)
NORDERNEY = (53.7117, 7.1536)
HAMBURG = (53.5511, 9.9937)
MUNICH = (48.1351, 11.5820)


def _alert(document: bytes) -> dict[str, Any]:
    alert = parse_cap_alert(document)
    assert alert is not None
    return alert


def _alert_ids(request: DwdWeatherAlertRequest) -> list[str]:
    return request.query().df.get_column("alert_id").to_list()


# the places of the point test: in, out and on the edge of the polygons of real warnings
@pytest.mark.parametrize(
    ("document", "place", "contained"),
    [
        pytest.param(CAP_COMMUNITY_KIEL, KIEL, True, id="community-kiel-inside"),
        pytest.param(CAP_DISTRICT_KIEL, KIEL, True, id="district-kiel-inside"),
        pytest.param(CAP_COMMUNITY_NORDERNEY, NORDERNEY, True, id="community-norderney-inside"),
        pytest.param(CAP_COMMUNITY_KIEL, HAMBURG, False, id="community-hamburg-outside"),
        pytest.param(CAP_DISTRICT_KIEL, MUNICH, False, id="district-munich-outside"),
        pytest.param(
            CAP_COMMUNITY_NORDERNEY, KIEL, False, id="kiel-is-not-in-the-warning-for-the-coast-of-the-north-sea"
        ),
        pytest.param(CAP_COMMUNITY_KIEL, NORDERNEY, False, id="norderney-is-not-in-the-warning-for-kiel"),
        # a warning of the sea names its area by a warn cell, and has no polygon: no point is in it
        pytest.param(CAP_COMMUNITY_SEA, (53.9, 7.0), False, id="warning-without-polygon"),
    ],
)
def test_a_point_is_inside_the_polygons_of_a_warning_or_not(
    document: bytes, place: tuple[float, float], *, contained: bool
) -> None:
    """A warning is for a point if a polygon of it contains the point."""
    alert = _alert(document)
    assert geometry_contains(alert["geometry"], *place) is contained
    assert is_for_place(alert, latitude=place[0], longitude=place[1]) is contained


def test_a_point_on_the_edge_of_a_polygon_is_inside_it() -> None:
    """The edge of a polygon counts as inside: a point on the border of two warned areas is in both."""
    alert = _alert(CAP_DISTRICT_HELGOLAND)
    exterior = alert["geometry"]["coordinates"][0][0]
    # the sea polygon of Helgoland is [(8.315, 54.27917), (7.925, 54.0), (7.5, 54.0), (7.5, 54.3), (7.9, 54.4)]
    (lon0, lat0), (lon1, lat1) = exterior[1], exterior[2]
    assert (lat0, lat1) == (54.0, 54.0)
    # a vertex, and the middle of the edge between two of them: each in the polygon, and each a point on its border
    assert geometry_contains(alert["geometry"], lat0, lon0)
    assert geometry_contains(alert["geometry"], 54.0, (lon0 + lon1) / 2)
    # the west edge, from (7.5, 54.0) to (7.5, 54.3)
    assert geometry_contains(alert["geometry"], 54.15, 7.5)
    # a hair outside it is not
    assert not geometry_contains(alert["geometry"], 54.15, 7.4999)
    assert not geometry_contains(alert["geometry"], 53.9999, 7.7)


def test_a_point_on_a_vertex_of_a_polygon_of_kiel_is_inside_it() -> None:
    """The corners of a real polygon, as DWD wrote them, are inside it, whatever the float they are."""
    alert = _alert(CAP_DISTRICT_KIEL)
    for polygon in alert["geometry"]["coordinates"]:
        for lon, lat in polygon[0][:20]:
            assert geometry_contains(alert["geometry"], lat, lon)


def _rings(geometry: dict[str, Any]) -> list[int]:
    return [len(polygon) for polygon in geometry["coordinates"]]


def test_the_holes_of_an_area_with_several_polygons_are_on_the_polygon_they_lie_in() -> None:
    """Kreis Rastatt has two polygons and two holes in the one (Baden-Baden, and a small one): none is lost."""
    geometry = _alert(CAP_DISTRICT_RASTATT)["geometry"]
    # the 14 polygons of the 14 areas: the exterior alone but for the second, which has its two holes; the exclave of
    # Baden-Baden, a polygon in the hole, is a polygon of its own
    assert sorted(_rings(geometry)) == [1] * 13 + [3]
    (with_holes,) = (polygon for polygon in geometry["coordinates"] if len(polygon) == 3)
    assert [len(ring) for ring in with_holes] == [91, 39, 6]


def test_a_point_in_a_hole_of_an_area_with_several_polygons_is_outside_it() -> None:
    """Baden-Baden is not in the warning for Kreis Rastatt, which surrounds it; Rastatt and its exclave are."""
    alert = _alert(CAP_DISTRICT_RASTATT)
    geometry = alert["geometry"]
    assert geometry_contains(geometry, 48.8575, 8.2073)  # Rastatt
    assert geometry_contains(geometry, 48.8294, 8.2514)  # Kuppenheim
    assert not geometry_contains(geometry, 48.7606, 8.2398)  # Baden-Baden, in the hole
    assert not geometry_contains(geometry, 48.7010, 8.0551)  # the small hole
    # the exclave in the hole, a polygon of its own
    assert geometry_contains(geometry, 48.7387, 8.2095)
    # a corner of a hole is its edge, and inside the warning
    assert geometry_contains(geometry, 48.706317, 8.069233)
    assert is_for_place(alert, name="Rastatt")
    assert not is_for_place(alert, latitude=48.7606, longitude=8.2398)


def test_the_islands_in_the_sea_east_of_ruegen_are_holes_of_the_polygons_they_lie_in() -> None:
    """The warning has two polygons and an island in each; the second island touches its polygon at an edge."""
    geometry = _alert(CAP_DISTRICT_RUEGEN)["geometry"]
    assert _rings(geometry) == [2, 2]
    assert geometry_contains(geometry, 54.6, 14.0)  # the sea
    assert not geometry_contains(geometry, 54.3202, 13.5314)  # an island, in the first polygon
    assert not geometry_contains(geometry, 54.5544, 13.3718)  # the other, in the second
    assert geometry_contains(geometry, 54.30994, 13.523588)  # a corner of the first island: its edge


def test_an_area_with_one_polygon_keeps_its_holes_as_before() -> None:
    """Helgoland has one polygon and a hole, and its coordinates are what they were."""
    geometry = _alert(CAP_DISTRICT_HELGOLAND)["geometry"]
    assert _rings(geometry) == [2]


def test_the_hole_of_a_polygon_is_outside_it_and_its_edge_inside() -> None:
    """The island in the warning for the sea around Helgoland (`EXCLUDE_POLYGON`) is not in it, its shore is."""
    alert = _alert(CAP_DISTRICT_HELGOLAND)
    geometry = alert["geometry"]
    # the sea, west of the island
    assert geometry_contains(geometry, 54.1, 7.7)
    # the island itself: a point in the hole
    assert not geometry_contains(geometry, 54.18, 7.9)
    # a corner of the hole, which is the edge of the polygon
    assert geometry_contains(geometry, 54.189534, 7.919221)


@pytest.mark.parametrize(
    ("name", "matches"),
    [
        pytest.param("Kiel", True, id="a-word-of-the-name"),
        pytest.param("kiel", True, id="in-any-case"),
        pytest.param("  KIEL ", True, id="padded"),
        pytest.param("Stadt Kiel", True, id="the-whole-name"),
        pytest.param("stadt   kiel", True, id="white-space-is-one-gap"),
        pytest.param("Kiel-Holtenau", False, id="a-name-it-is-not"),
        pytest.param("Kie", False, id="part-of-a-word"),
        pytest.param("Neumünster", True, id="umlaut"),
        pytest.param("neumünster", True, id="umlaut-in-any-case"),
        pytest.param("Hamburg", False, id="no-area-of-that-name"),
        pytest.param("101002000", True, id="warn-cell"),
        pytest.param("01002000", True, id="municipality-key-of-the-warn-cell"),
        pytest.param("801002000", False, id="warn-cell-of-the-commune-is-not-of-the-district"),
        pytest.param("1002000", False, id="part-of-a-key"),
    ],
)
def test_a_name_is_a_name_or_a_warn_cell_of_an_area_of_the_warning(name: str, *, matches: bool) -> None:
    """The district warning of Kiel names `Stadt Kiel` (`101002000`) and `Stadt Neumünster` among its areas."""
    alert = _alert(CAP_DISTRICT_KIEL)
    assert names_match(alert["area_names"], alert["warncell_ids"], name) is matches
    assert is_for_place(alert, name=name) is matches


def test_a_word_of_a_name_is_not_a_part_of_a_longer_word() -> None:
    """`Kiel` is Kiel and not Kielstau."""
    assert not names_match(["Gemeinde Kielstau"], ["801012345"], "Kiel")
    assert not names_match(["Gemeinde Altenkiel"], ["801012345"], "Kiel")
    assert names_match(["Gemeinde Kiel am See"], ["801012345"], "kiel")


def test_the_key_of_a_warn_cell_is_the_same_for_the_commune_and_its_district() -> None:
    """`01002000` is Kiel as a commune (`801002000`) and as a district (`101002000`), a full id only the one."""
    community, district = _alert(CAP_COMMUNITY_KIEL), _alert(CAP_DISTRICT_KIEL)
    for alert in (community, district):
        assert is_for_place(alert, name="01002000")
    assert is_for_place(community, name="801002000")
    assert not is_for_place(community, name="101002000")
    assert is_for_place(district, name="101002000")
    assert not is_for_place(district, name="801002000")


def test_a_warning_for_the_sea_is_found_by_its_name() -> None:
    """A warning with no polygon is for no point, and is for the name and the warn cell of its area."""
    alert = _alert(CAP_COMMUNITY_SEA)
    assert alert["geometry"] is None
    assert is_for_place(alert, name="Ostfriesische Küste")
    assert is_for_place(alert, name="501000001")
    assert not is_for_place(alert, latitude=53.9, longitude=7.0)


def test_a_point_and_a_name_are_both_asked() -> None:
    """With both, a warning is for the place if it is for the point and for the name."""
    alert = _alert(CAP_DISTRICT_KIEL)
    assert is_for_place(alert, latitude=KIEL[0], longitude=KIEL[1], name="Kiel")
    assert not is_for_place(alert, latitude=MUNICH[0], longitude=MUNICH[1], name="Kiel")
    assert not is_for_place(alert, latitude=KIEL[0], longitude=KIEL[1], name="Hamburg")


# the request, over the snapshot of a few real warnings
SNAPSHOT = (CAP_COMMUNITY_KIEL, CAP_COMMUNITY_NORDERNEY, CAP_COMMUNITY_SEA)
DISTRICT_SNAPSHOT = (CAP_DISTRICT_KIEL, CAP_DISTRICT_HELGOLAND)


def test_without_a_place_every_warning_of_the_snapshot_is_there(monkeypatch: pytest.MonkeyPatch) -> None:
    """The answer is as it was without a filter: nothing breaks for a caller that passes no place."""
    serve_snapshot(monkeypatch, *SNAPSHOT)
    result = DwdWeatherAlertRequest().query()
    assert result.df.height == len(SNAPSHOT)


@pytest.mark.parametrize(
    ("granularity", "documents", "kiel"),
    [
        pytest.param("community", SNAPSHOT, CAP_COMMUNITY_KIEL, id="community"),
        pytest.param("district", DISTRICT_SNAPSHOT, CAP_DISTRICT_KIEL, id="district"),
    ],
)
def test_a_point_keeps_the_warnings_whose_areas_contain_it(
    monkeypatch: pytest.MonkeyPatch, granularity: str, documents: tuple[bytes, ...], kiel: bytes
) -> None:
    """For each granularity, the point of Kiel keeps its one warning and the point of Munich none."""
    serve_snapshot(monkeypatch, *documents)
    request = DwdWeatherAlertRequest(granularity=granularity, latitude=KIEL[0], longitude=KIEL[1])
    assert _alert_ids(request) == [_alert(kiel)["alert_id"]]
    assert _alert_ids(DwdWeatherAlertRequest(granularity=granularity, latitude=MUNICH[0], longitude=MUNICH[1])) == []


def test_a_point_in_two_warnings_keeps_both(monkeypatch: pytest.MonkeyPatch) -> None:
    """A point is for every warning that has it, as for a warning of each kind."""
    serve_snapshot(monkeypatch, CAP_COMMUNITY_KIEL, CAP_COMMUNITY_KIEL, CAP_COMMUNITY_NORDERNEY)
    request = DwdWeatherAlertRequest(latitude=KIEL[0], longitude=KIEL[1])
    assert len(_alert_ids(request)) == 2


@pytest.mark.parametrize(
    ("granularity", "documents", "name", "expected"),
    [
        pytest.param("community", SNAPSHOT, "Kiel", [CAP_COMMUNITY_KIEL], id="community-name"),
        pytest.param("community", SNAPSHOT, "801002000", [CAP_COMMUNITY_KIEL], id="community-warn-cell"),
        pytest.param("community", SNAPSHOT, "Norderney", [CAP_COMMUNITY_NORDERNEY], id="another-name"),
        pytest.param("community", SNAPSHOT, "Ostfriesische Küste", [CAP_COMMUNITY_SEA], id="the-sea"),
        pytest.param("community", SNAPSHOT, "Munich", [], id="no-match"),
        pytest.param("district", DISTRICT_SNAPSHOT, "Kiel", [CAP_DISTRICT_KIEL], id="district-name"),
        pytest.param("district", DISTRICT_SNAPSHOT, "101002000", [CAP_DISTRICT_KIEL], id="district-warn-cell"),
        pytest.param("district", DISTRICT_SNAPSHOT, "Helgoland", [CAP_DISTRICT_HELGOLAND], id="district-sea"),
        pytest.param("district", DISTRICT_SNAPSHOT, "Munich", [], id="district-no-match"),
    ],
)
def test_a_name_keeps_the_warnings_with_an_area_of_that_name_or_warn_cell(
    monkeypatch: pytest.MonkeyPatch, granularity: str, documents: tuple[bytes, ...], name: str, expected: list[bytes]
) -> None:
    """A name or a warn cell id keeps the warnings for it, for each granularity."""
    serve_snapshot(monkeypatch, *documents)
    request = DwdWeatherAlertRequest(granularity=granularity, name=name)
    assert _alert_ids(request) == [_alert(document)["alert_id"] for document in expected]


def test_a_place_does_not_change_the_rows_it_keeps(monkeypatch: pytest.MonkeyPatch) -> None:
    """A row of a filtered answer is the row of the unfiltered one: the filter keeps rows and does not cut them."""
    serve_snapshot(monkeypatch, *SNAPSHOT)
    everything = DwdWeatherAlertRequest().query().df
    kept = DwdWeatherAlertRequest(latitude=KIEL[0], longitude=KIEL[1]).query().df
    assert kept.equals(everything.filter(everything["alert_id"] == _alert(CAP_COMMUNITY_KIEL)["alert_id"]))


def test_no_warning_for_a_place_is_told_as_an_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """A place without a warning is no failure: the answer holds none, and says why, with the warnings it left out."""
    serve_snapshot(monkeypatch, *SNAPSHOT)
    begin_response()
    result = DwdWeatherAlertRequest(latitude=MUNICH[0], longitude=MUNICH[1]).query()
    assert result.df.is_empty()
    (warning,) = recorded_warnings()
    assert warning["code"] == NO_ALERTS_FOR_PLACE
    assert "the point 48.1351, 11.582" in warning["message"]
    assert "3 are for other places" in warning["message"]
    assert "not an error" in warning["message"]
    # a point says what it is, and nothing of names
    assert "named" not in warning["message"]
    assert "German" not in warning["message"]


def test_a_place_in_a_snapshot_without_warnings_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    """A snapshot that is empty (quiet weather) is told for the place as well."""
    serve_snapshot(monkeypatch)
    begin_response()
    DwdWeatherAlertRequest(name="Kiel").query()
    (warning,) = recorded_warnings()
    assert "'Kiel'" in warning["message"]
    assert "No warning is in force anywhere" in warning["message"]
    assert "spelling" not in warning["message"]


def test_a_name_that_matches_nothing_is_not_told_as_an_all_clear(monkeypatch: pytest.MonkeyPatch) -> None:
    """`Munich` is no name DWD uses: the message says that no area carries it, and not that nothing is in force."""
    serve_snapshot(monkeypatch, *SNAPSHOT)
    begin_response()
    assert DwdWeatherAlertRequest(name="Munich").query().df.is_empty()
    (warning,) = recorded_warnings()
    message = warning["message"]
    assert message.startswith("No warning in force lists an area named 'Munich'")
    assert "German" in message
    assert "München" in message
    assert "nothing in force" not in message
    assert "ask by point" in message


def test_a_point_and_a_name_that_no_warning_has_together_are_counted_each(monkeypatch: pytest.MonkeyPatch) -> None:
    """The point of Kiel is in one warning and the name Norderney in another: none has both, and the message says so."""
    serve_snapshot(monkeypatch, *SNAPSHOT)
    begin_response()
    result = DwdWeatherAlertRequest(latitude=KIEL[0], longitude=KIEL[1], name="Norderney").query()
    assert result.df.is_empty()
    (warning,) = recorded_warnings()
    message = warning["message"]
    assert (
        "1 warning contains the point and 1 warning lists the name, but none does both (3 in the snapshot)" in message
    )
    assert "German" not in message  # the name was found: the spelling is not the matter


def test_a_point_and_a_name_that_match_nothing_each_are_told_so(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neither the point nor the name has a warning: 0 and 0, and the name is told to be German."""
    serve_snapshot(monkeypatch, CAP_COMMUNITY_KIEL, CAP_COMMUNITY_NORDERNEY)
    begin_response()
    DwdWeatherAlertRequest(latitude=MUNICH[0], longitude=MUNICH[1], name="Munich").query()
    (warning,) = recorded_warnings()
    assert "0 warnings contain the point and 0 warnings list the name, but none does both" in warning["message"]
    assert "German" in warning["message"]


def test_a_point_at_sea_is_told_of_the_warnings_without_a_polygon(monkeypatch: pytest.MonkeyPatch) -> None:
    """The community product has no polygon for the sea: a point there finds none, and the message says what does."""
    serve_snapshot(monkeypatch, *SNAPSHOT)
    begin_response()
    assert DwdWeatherAlertRequest(latitude=53.9, longitude=7.0).query().df.is_empty()
    (warning,) = recorded_warnings()
    message = warning["message"]
    assert "1 of them have no polygon (the sea)" in message
    assert "ask for them by name, or with granularity=district" in message
    assert "nothing in force covers it" not in message


def test_the_district_product_is_not_sent_to_the_district_product(monkeypatch: pytest.MonkeyPatch) -> None:
    """A warning with no polygon in the district product is asked for by name, not by the granularity it is in."""
    serve_snapshot(monkeypatch, CAP_COMMUNITY_SEA)
    begin_response()
    DwdWeatherAlertRequest(granularity="district", latitude=53.9, longitude=7.0).query()
    (warning,) = recorded_warnings()
    assert "ask for them by name." in warning["message"]
    assert "granularity=district" not in warning["message"]


@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({"name": "Munich"}, id="name"),
        pytest.param({"latitude": MUNICH[0], "longitude": MUNICH[1], "name": "Munich"}, id="both"),
    ],
)
def test_nothing_is_added_about_the_sea_for_a_name(
    monkeypatch: pytest.MonkeyPatch, kwargs: dict[str, float | str]
) -> None:
    """The clause is for a request by point; and none where every warning has a polygon."""
    serve_snapshot(monkeypatch, *SNAPSHOT)
    begin_response()
    DwdWeatherAlertRequest(**kwargs).query()
    (warning,) = recorded_warnings()
    assert ("no polygon" in warning["message"]) is ("latitude" in kwargs)
    begin_response()
    serve_snapshot(monkeypatch, CAP_COMMUNITY_KIEL, CAP_COMMUNITY_NORDERNEY)
    DwdWeatherAlertRequest(latitude=MUNICH[0], longitude=MUNICH[1]).query()
    (warning,) = recorded_warnings()
    assert "no polygon" not in warning["message"]
    assert "nothing in force covers it" in warning["message"]


@pytest.mark.parametrize(
    "kwargs",
    [
        pytest.param({"latitude": MUNICH[0], "longitude": MUNICH[1]}, id="point"),
        pytest.param({"name": "Munich"}, id="name"),
        pytest.param({"latitude": MUNICH[0], "longitude": MUNICH[1], "name": "Munich"}, id="both"),
    ],
)
def test_an_empty_snapshot_is_a_true_all_clear_for_every_criterion(
    monkeypatch: pytest.MonkeyPatch, kwargs: dict[str, float | str]
) -> None:
    """With no warning in force anywhere, the message says so, and not that the spelling may be wrong."""
    serve_snapshot(monkeypatch)
    begin_response()
    DwdWeatherAlertRequest(**kwargs).query()
    (warning,) = recorded_warnings()
    assert warning["message"].startswith("No warning is in force anywhere (the snapshot holds none)")
    assert "spelling" not in warning["message"]


def test_a_name_is_matched_whatever_the_unicode_form_of_an_umlaut() -> None:
    """`ü` is one code point or a `u` and a combining diaeresis, in the name asked for or in DWD's: the same name."""
    composed, decomposed = "Neum\u00fcnster", "Neumu\u0308nster"
    assert composed != decomposed
    for asked in (composed, decomposed):
        assert names_match([f"Stadt {composed}"], ["101004000"], asked)
        assert names_match([f"Stadt {decomposed}"], ["101004000"], asked)
        assert names_match([f"Stadt {decomposed}"], ["101004000"], asked.upper())


def test_a_name_finds_every_area_that_has_the_word() -> None:
    """The name is a word, so `Hamburg` is also the commune near it: a point is the reliable way to ask."""
    assert names_match(["Gemeinde Wentorf bei Hamburg"], ["801062000"], "Hamburg")
    assert names_match(["Kirchheim b. München"], ["809184000"], "München")


def test_a_place_with_a_warning_tells_nothing(monkeypatch: pytest.MonkeyPatch) -> None:
    """A warning that is found is the answer; no further word."""
    serve_snapshot(monkeypatch, *SNAPSHOT)
    begin_response()
    DwdWeatherAlertRequest(name="Kiel").query()
    assert recorded_warnings() == []


def test_a_request_without_a_place_tells_nothing_of_an_empty_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without a place an empty snapshot is as it was: no warning in force, and no word."""
    serve_snapshot(monkeypatch)
    begin_response()
    assert DwdWeatherAlertRequest().query().df.is_empty()
    assert recorded_warnings() == []


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        pytest.param({"latitude": 54.3}, "together", id="latitude-alone"),
        pytest.param({"longitude": 10.1}, "together", id="longitude-alone"),
        pytest.param({"latitude": 91.0, "longitude": 10.1}, "latitude", id="latitude-too-far-north"),
        pytest.param({"latitude": 54.3, "longitude": 181.0}, "longitude", id="longitude-too-far-east"),
        pytest.param({"latitude": float("nan"), "longitude": 10.1}, "latitude", id="latitude-not-a-number"),
    ],
)
def test_half_a_point_or_one_off_the_earth_is_refused(kwargs: dict[str, float], message: str) -> None:
    """The coordinates are a point of the Earth, both of them, which is the request's to fix."""
    with pytest.raises(RequestError, match=message):
        DwdWeatherAlertRequest(**kwargs)


def test_an_empty_name_is_no_filter() -> None:
    """A name that is present and empty (`?name=`) is the whole snapshot, as an empty `timestamp` is the latest."""
    assert DwdWeatherAlertRequest(name="  ").name is None
    assert DwdWeatherAlertRequest(name="").name is None
    assert DwdWeatherAlertRequest(name=" Kiel ").name == "Kiel"


def test_a_coordinate_of_zero_is_a_point() -> None:
    """The equator and the Greenwich meridian are places: 0 is given, not left out."""
    request = DwdWeatherAlertRequest(latitude=0.0, longitude=0.0)
    assert (request.latitude, request.longitude) == (0.0, 0.0)
    assert "latitude=0.0" in repr(request)


def test_the_answers_of_a_place_are_json(monkeypatch: pytest.MonkeyPatch) -> None:
    """The rows of a place go to the same writers as the whole snapshot's."""
    serve_snapshot(monkeypatch, *SNAPSHOT)
    result = DwdWeatherAlertRequest(name="Norderney").query()
    assert [alert["event"] for alert in json.loads(result.to_json())["alerts"]] == ["wind gusts"]
    assert len(result.to_ogc_feature_collection()["features"]) == 1
    assert "Stadt Norderney" in result.to_csv()
    assert "Stadt Kiel" not in result.to_csv()


# the date of the data is that of the whole snapshot, whatever the place keeps (the sea warning is the newest, 08:44)
_SNAPSHOT_UPDATED_AT = dt.datetime(2026, 11, 12, 8, 44, tzinfo=dt.UTC)


@pytest.mark.parametrize(
    ("kwargs", "kept"),
    [
        pytest.param({}, 3, id="unfiltered"),
        pytest.param({"latitude": KIEL[0], "longitude": KIEL[1]}, 1, id="filtered-with-a-match"),
        pytest.param({"name": "Kiel"}, 1, id="filtered-by-name"),
        pytest.param({"latitude": MUNICH[0], "longitude": MUNICH[1]}, 0, id="filtered-with-no-match"),
    ],
)
def test_the_date_of_the_data_is_that_of_the_whole_snapshot(
    monkeypatch: pytest.MonkeyPatch, kwargs: dict[str, float | str], kept: int
) -> None:
    """A place keeps a few warnings or none, and the data it checked is as current as the snapshot is."""
    serve_snapshot(monkeypatch, *SNAPSHOT)
    result = DwdWeatherAlertRequest(**kwargs).query()
    assert result.df.height == kept
    assert result.data_updated_at == _SNAPSHOT_UPDATED_AT


def test_the_date_of_an_empty_snapshot_is_none_with_or_without_a_place(monkeypatch: pytest.MonkeyPatch) -> None:
    """A snapshot without a warning has no date, as before."""
    serve_snapshot(monkeypatch)
    assert DwdWeatherAlertRequest().query().data_updated_at is None
    assert DwdWeatherAlertRequest(name="Kiel").query().data_updated_at is None
