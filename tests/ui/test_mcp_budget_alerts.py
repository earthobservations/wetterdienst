# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A tool's `alerts` answer is cut to the size budget, and a name that matches no area is told (GH-4338).

A DWD warning is mostly its polygon and the areas it is issued for: on 2026-11-23 the three warnings for Kiel were
184,612 characters (REST JSON), 1.3 million for the whole of Germany, and Claude Code saved every such result to a
file, so the model got no warning at all. The answer of a tool leaves the polygon and the areas out of each warning
where it is over `ANSWER_BUDGET`, caps the areas a broad `name` keeps, and then drops the least severe warnings; the
REST API, the command line and the library answer all of it.
The snapshot is real messages of DWD (`tests/provider/dwd/alerts/stubs.py`), repeated with other identifiers and
severities where a test needs more warnings than there are messages.
"""

from __future__ import annotations

import asyncio
import json
import re
import uuid
from typing import Any
from urllib.parse import unquote

import polars as pl
import pytest
from fastapi.testclient import TestClient

from tests.provider.dwd.alerts.stubs import (
    CAP_COMMUNITY_KIEL,
    CAP_COMMUNITY_NORDERNEY,
    CAP_COMMUNITY_SEA,
    serve_snapshot,
)
from tests.ui.test_mcp_budget import _client_sees, _compact, _received, _rest_client, _tool_client
from tests.ui.test_operations import _no_ambient_settings  # noqa: F401
from wetterdienst.ui import budget, restapi
from wetterdienst.ui.budget import ANSWER_BUDGET, AREA_CAP

pytestmark = pytest.mark.usefixtures("_no_ambient_settings")

_KIEL = {"latitude": 54.3233, "longitude": 10.1228}
_SEVERITIES = ("Extreme", "Severe", "Moderate", "Minor")
_BASES = (CAP_COMMUNITY_KIEL, CAP_COMMUNITY_NORDERNEY, CAP_COMMUNITY_SEA)


def _variant(document: bytes, severity: str) -> bytes:
    """Give a message of DWD as another warning: a new identifier and the severity asked for."""
    text = document.decode("utf-8")
    text = re.sub(r"<identifier>[^<]*</identifier>", f"<identifier>{uuid.uuid4()}</identifier>", text)
    return re.sub(r"<severity>[^<]*</severity>", f"<severity>{severity}</severity>", text).encode("utf-8")


def _many(count: int) -> list[bytes]:
    """Give `count` warnings of every severity, the three real messages in turn, the least severe ones first."""
    return [
        _variant(_BASES[index % len(_BASES)], _SEVERITIES[::-1][index * len(_SEVERITIES) // count])
        for index in range(count)
    ]


def _a_coast() -> bytes:
    """Give the Kiel message as a warning for a coast: 1,500 more communes and 29 more polygons, as the real ones are.

    The real warning of 2026-11-23 for Schleswig-Holstein (frost, 1,429 areas) was 80,000 characters; the message
    of the stubs has 150 areas and one polygon, which is 12,000.
    """
    # the stub file has the line endings of the checkout (`\r\n` on Windows): the patterns below and the areas written
    # here have `\n`
    text = CAP_COMMUNITY_KIEL.decode("utf-8").replace("\r\n", "\n")
    polygon = re.search(r"    <area>\s*<areaDesc>polygonal event area</areaDesc>.*?</area>\n", text, re.DOTALL)
    assert polygon
    areas = "".join(
        f"    <area>\n      <areaDesc>Gemeinde Testort {n}</areaDesc>\n      <geocode>\n"
        f"        <valueName>WARNCELLID</valueName>\n        <value>8010{n:05d}</value>\n      </geocode>\n"
        "      <altitude>0.0</altitude>\n      <ceiling>9842.5197</ceiling>\n    </area>\n"
        for n in range(1_500)
    )
    end = text.rindex("</area>") + len("</area>\n")
    return (text[:end] + areas + polygon.group(0) * 29 + text[end:]).encode("utf-8")


def _alerts_of(response: Any) -> list[dict[str, Any]]:  # noqa: ANN401
    return response.json()["alerts"]


def _note_of(answer: dict[str, Any]) -> str:
    notes = [w["message"] for w in answer["metadata"]["warnings"] if w["code"] == "answer-truncated"]
    assert len(notes) == 1
    return notes[0]


def _the_client_gets(result: Any) -> tuple[dict[str, Any], int]:  # noqa: ANN401
    assert not result.is_error, result.content
    return result.structured_content["result"], _received(result)


@pytest.fixture
def kiel_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve one warning that is for a whole coast: whole, it is more than the budget, and Stadt Kiel is one area."""
    serve_snapshot(monkeypatch, _a_coast())


@pytest.fixture
def small(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve a snapshot that is within the budget: the warning of Norderney and the one of the sea."""
    serve_snapshot(monkeypatch, CAP_COMMUNITY_NORDERNEY, CAP_COMMUNITY_SEA)


@pytest.fixture
def broad(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve three warnings for a coast (1,650 areas each) of three severities, the least severe first."""
    serve_snapshot(monkeypatch, *(_variant(_a_coast(), severity) for severity in ("Minor", "Extreme", "Moderate")))


@pytest.fixture
def many(monkeypatch: pytest.MonkeyPatch) -> None:
    """Serve 80 warnings of every severity: slimmed, they are still more than the budget."""
    serve_snapshot(monkeypatch, *_many(80))


# --- an answer that fits is untouched ---------------------------------------------------------------------------


@pytest.mark.parametrize("params", [{}, {"name": "Norderney"}, {"latitude": 53.9, "longitude": 7.0}])
@pytest.mark.parametrize("fmt", ["json", "geojson", "csv"])
@pytest.mark.usefixtures("small")
def test_an_answer_within_the_budget_is_what_the_rest_api_answers(params: dict[str, Any], fmt: str) -> None:
    """Nothing is cut that fits: the tool's bytes are the REST API's, polygons and areas included."""
    tool = _tool_client().get("/api/alerts", params={**params, "format": fmt})
    rest = _rest_client().get("/api/alerts", params={**params, "format": fmt})
    assert tool.status_code == 200
    # but for the time it was retrieved
    now = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d+\+00:00(?=[\",])")
    assert now.sub("T", tool.text, count=1) == now.sub("T", rest.text, count=1)
    assert "answer-truncated" not in tool.headers.get("x-wetterdienst-warnings", "")


# --- the cut ----------------------------------------------------------------------------------------------------


@pytest.mark.usefixtures("kiel_only")
def test_the_warning_of_a_place_is_over_the_budget_whole_and_within_it_for_a_tool() -> None:
    """The point of the issue: one warning of 80,000 characters is no answer a client hands on; slimmed, it is."""
    assert _compact(_rest_client().get("/api/alerts", params=_KIEL).text) > ANSWER_BUDGET

    answer, size = _the_client_gets(_client_sees("alerts", _KIEL))

    assert size <= ANSWER_BUDGET
    (alert,) = answer["alerts"]
    assert alert["event"] == "wind gusts"
    # the polygon and the areas are what is left out, the rest of the warning is whole
    assert alert["geometry"] is None
    assert alert["area_names"] == []
    assert alert["warncell_ids"] == []
    assert alert["description"]
    assert alert["instruction"]
    assert alert["severity"] == "Minor"
    assert answer["metadata"]["counts"]["rows"] == 1
    note = _note_of(answer)
    assert "`geometry`" in note
    assert "`area_names`" in note
    assert "The warning is returned." in note
    assert "All 1 warnings" not in note


@pytest.mark.usefixtures("kiel_only")
def test_the_areas_that_match_the_name_are_kept() -> None:
    """For a name the area it asked for is the one thing of the lists worth keeping: Stadt Kiel of 150 areas."""
    answer, size = _the_client_gets(_client_sees("alerts", {"name": "Kiel"}))

    assert size <= ANSWER_BUDGET
    (alert,) = answer["alerts"]
    assert alert["area_names"] == ["Stadt Kiel"]
    assert alert["warncell_ids"] == []
    assert "the areas that match the name are kept" in _note_of(answer)


@pytest.mark.usefixtures("kiel_only")
def test_a_warn_cell_id_keeps_the_cell() -> None:
    """A name of digits is a warn cell: that one is kept, and no area name, which the id does not match."""
    answer, _ = _the_client_gets(_client_sees("alerts", {"name": "801002000"}))
    (alert,) = answer["alerts"]
    assert alert["warncell_ids"] == ["801002000"]
    assert alert["area_names"] == []


@pytest.mark.parametrize("fmt", ["json", "geojson", "csv"])
@pytest.mark.usefixtures("many")
def test_what_the_client_receives_is_within_the_budget(fmt: str) -> None:
    """For each format, as the client counts it: the JSON of the structured content, the sentence of a CSV included."""
    result = _client_sees("alerts", {"format": fmt})

    assert not result.is_error, result.content
    assert _received(result) <= ANSWER_BUDGET
    # an answer that is within the budget by being empty is no answer: warnings are in it, and the note says it was cut
    text = json.dumps(result.structured_content)
    if fmt == "csv":
        assert text.count("\\n") > 5
        assert "answer-truncated" in text
    else:
        answer = result.structured_content["result"]
        assert len(answer["alerts" if fmt == "json" else "features"]) > 5
        assert _note_of(answer)
    # the whole snapshot is far more than a client takes
    assert _compact(_rest_client().get("/api/alerts", params={"format": "json"}).text) > 10 * ANSWER_BUDGET


@pytest.mark.usefixtures("many")
def test_the_worst_warnings_are_kept_and_whole() -> None:
    """The most severe first, whole (every field of a slimmed warning), and the rest named and counted."""
    response = _tool_client().get("/api/alerts")
    assert response.status_code == 200
    answer = response.json()
    kept = answer["alerts"]
    full = _alerts_of(_rest_client().get("/api/alerts"))

    assert 0 < len(kept) < len(full) == 80
    assert _compact(response.text) <= ANSWER_BUDGET
    ranks = [_SEVERITIES.index(alert["severity"]) for alert in kept]
    assert ranks == sorted(ranks)
    # what was left out is no worse than what was kept
    left_out = [alert for alert in full if alert["alert_id"] not in {a["alert_id"] for a in kept}]
    assert len(left_out) == 80 - len(kept)
    assert max(ranks) <= min(_SEVERITIES.index(alert["severity"]) for alert in left_out)
    # every Extreme warning is kept before a Severe one is dropped
    assert {alert["alert_id"] for alert in full if alert["severity"] == "Extreme"} <= {a["alert_id"] for a in kept}
    # whole: the fields of a warning are all there, only the bulky three are emptied
    for alert in kept:
        assert alert.keys() == full[0].keys()
        assert alert["geometry"] is None
        assert alert["area_names"] == [] == alert["warncell_ids"]
        assert alert["headline"]
        assert alert["description"]
    note = _note_of(answer)
    assert f"Of 80 warnings the first {len(kept):,} warnings are returned, the most severe first" in note
    assert f"The {80 - len(kept):,} left out are: " in note
    assert "Pass a place" in note
    assert answer["metadata"]["counts"]["rows"] == len(kept)
    assert response.headers["x-wetterdienst-warnings"] == "answer-truncated"


@pytest.mark.usefixtures("many")
def test_the_note_names_the_warnings_left_out_and_how_many_more() -> None:
    """Eight are named as `event (severity)`; the others are counted."""
    answer = _tool_client().get("/api/alerts").json()
    note = _note_of(answer)
    left = 80 - len(answer["alerts"])
    named = re.search(r"left out are: (.*?)\. Pass", note)
    assert named
    assert re.fullmatch(
        r"(?:[a-z ]+ \((?:Severe|Moderate|Minor)\), ){7}[a-z ]+ \((?:Severe|Moderate|Minor)\) and \d+ more",
        named.group(1),
    )
    assert f"and {left - 8:,} more" in named.group(1)


@pytest.mark.usefixtures("many")
def test_a_place_that_is_over_the_budget_says_how_to_narrow_it(monkeypatch: pytest.MonkeyPatch) -> None:
    """For a place the advice is a smaller one, not the place the request already has."""
    monkeypatch.setattr(budget, "ANSWER_BUDGET", 9_000)
    answer = _tool_client().get("/api/alerts", params={"name": "Kiel"}).json()
    note = _note_of(answer)
    assert "Ask for a smaller place: a more specific `name`, one area or its warn cell id." in note
    assert "Pass a place" not in note
    # a name-only request has no point to speak of
    assert "point" not in note.split("left out are:")[1]
    assert "the areas that match the name are kept" in note


@pytest.mark.usefixtures("many")
def test_the_advice_for_a_point_is_a_name_and_for_a_name_a_better_one(monkeypatch: pytest.MonkeyPatch) -> None:
    """A point cannot be narrowed but by a name (both must hold); a name by a more specific one."""
    monkeypatch.setattr(budget, "ANSWER_BUDGET", 9_000)
    answer = _tool_client().get("/api/alerts", params=_KIEL).json()
    assert "add a `name` of one area to the point (both must hold)" in _note_of(answer)


@pytest.mark.parametrize("fmt", ["json", "geojson", "csv"])
@pytest.mark.usefixtures("broad")
def test_a_broad_name_keeps_all_its_warnings_with_a_capped_list_of_areas(fmt: str) -> None:
    """`Gemeinde` is in 1,644 areas of each of three warnings: full lists are 150,000 characters, capped ones fit."""
    arguments = {"name": "Gemeinde", "format": fmt}
    whole = _rest_client().get("/api/alerts", params=arguments)
    # even slimmed of the polygon, the areas that match are over the budget: that is what the cap is for
    assert len(whole.text) > 3 * ANSWER_BUDGET

    result = _client_sees("alerts", arguments)

    assert not result.is_error, result.content
    assert _received(result) <= ANSWER_BUDGET
    if fmt == "csv":
        response = _tool_client().get("/api/alerts", params=arguments)
        assert response.headers["x-wetterdienst-rows"] == "3"
        assert f"the first {AREA_CAP} of the areas that match the name" in unquote(
            response.headers["x-wetterdienst-truncated"]
        )
        return
    answer = result.structured_content["result"]
    alerts = answer["alerts"] if fmt == "json" else [f["properties"] for f in answer["features"]]
    # every warning is kept, the worst first, and each has its areas capped
    assert [alert["severity"] for alert in alerts] == ["Extreme", "Moderate", "Minor"]
    assert [len(alert["area_names"]) for alert in alerts] == [AREA_CAP] * 3
    assert all(name.startswith("Gemeinde") for alert in alerts for name in alert["area_names"])
    assert answer["metadata"]["counts"]["rows"] == 3
    note = _note_of(answer)
    assert f"the first {AREA_CAP} of the areas that match the name are kept for each warning" in note
    assert "wind gusts (1,644 match), wind gusts (1,644 match), wind gusts (1,644 match) have more" in note
    assert "left out" in note
    assert "The warning is returned" not in note
    assert "All 3 warnings are returned." in note


@pytest.mark.usefixtures("kiel_only")
def test_a_name_with_few_areas_is_not_capped() -> None:
    """The cap is for the names that would spill over: one area, or twenty, is kept as it is."""
    answer = _tool_client().get("/api/alerts", params={"name": "Kiel"}).json()
    assert "the first" not in _note_of(answer).split("(")[1]
    assert answer["alerts"][0]["area_names"] == ["Stadt Kiel"]


@pytest.mark.usefixtures("kiel_only")
def test_where_not_even_one_warning_fits_the_worst_is_kept_and_the_note_says_so(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A budget no warning fits is no reason for an empty answer: one warning is kept, and the note is honest."""
    monkeypatch.setattr(budget, "ANSWER_BUDGET", 1_000)
    answer = _tool_client().get("/api/alerts", params=_KIEL).json()
    assert len(answer["alerts"]) == 1
    assert _note_of(answer).startswith("The answer was cut as far as it goes and is still over 1,000 characters")


def test_the_order_is_severity_then_urgency_then_onset() -> None:
    """The sort that keeps the worst: ties keep the order of the snapshot, a word that is no severity goes last."""
    df = pl.DataFrame(
        {
            "severity": ["Minor", "Extreme", "minor", "Severe", "Unknown", "Severe", None],
            "urgency": ["Immediate", "Future", "Immediate", "Future", "Immediate", "Immediate", "Immediate"],
            "onset": [3, 3, 1, 3, 3, 3, 3],
            "name": list("abcdefg"),
        }
    )
    ordered = budget._worst_first(df)["name"].to_list()  # noqa: SLF001
    assert ordered == ["b", "f", "d", "c", "a", "e", "g"]


# --- every format keeps its shape ---------------------------------------------------------------------------------


@pytest.mark.usefixtures("kiel_only")
def test_a_cut_geojson_has_its_features_without_geometry() -> None:
    """A cut GeoJSON keeps its feature collection: each feature has no geometry and the note is in its block."""
    answer = _tool_client().get("/api/alerts", params={**_KIEL, "format": "geojson"}).json()
    (feature,) = answer["features"]
    assert answer["type"] == "FeatureCollection"
    assert feature["geometry"] is None
    assert feature["properties"]["event"] == "wind gusts"
    assert _note_of(answer)


@pytest.mark.usefixtures("kiel_only")
def test_a_cut_csv_says_so_in_its_header_and_has_no_polygon() -> None:
    """A CSV has no block, so the note is the `X-Wetterdienst-Truncated` header, and no polygon is in its body."""
    response = _tool_client().get("/api/alerts", params={**_KIEL, "format": "csv"})
    assert response.status_code == 200
    assert response.headers["x-wetterdienst-warnings"] == "answer-truncated"
    assert "`geometry`" in unquote(response.headers["x-wetterdienst-truncated"])
    assert response.headers["x-wetterdienst-rows"] == "1"
    assert "MultiPolygon" not in response.text
    assert len(response.text) < ANSWER_BUDGET


# --- the other surfaces are not cut -------------------------------------------------------------------------------


@pytest.mark.usefixtures("kiel_only")
def test_the_rest_api_answers_all_of_the_alerts(monkeypatch: pytest.MonkeyPatch) -> None:
    """The REST API never asks for the cut, and its answer has the polygon and the 1,650 areas."""

    def refuse(*_args: Any, **_kwargs: Any) -> None:  # noqa: ANN401
        msg = "the REST API's answer must not be cut"
        raise AssertionError(msg)

    monkeypatch.setattr(restapi, "fit_alerts", refuse)
    answer = _rest_client().get("/api/alerts", params=_KIEL).json()
    (alert,) = answer["alerts"]
    assert alert["geometry"]["type"] == "MultiPolygon"
    assert len(alert["area_names"]) == 1_650
    assert answer["metadata"]["warnings"] == []


@pytest.mark.usefixtures("kiel_only")
def test_python_and_the_command_line_answer_all_of_the_alerts() -> None:
    """The library and the command line answer the polygon and every area, with no note."""
    from click.testing import CliRunner  # noqa: PLC0415

    from wetterdienst.provider.dwd.alerts import DwdWeatherAlertRequest  # noqa: PLC0415
    from wetterdienst.ui.cli import cli  # noqa: PLC0415

    result = DwdWeatherAlertRequest(**_KIEL).query()
    assert result.to_dict()["alerts"][0]["geometry"]["type"] == "MultiPolygon"
    output = CliRunner().invoke(cli, ["alerts", "--latitude=54.3233", "--longitude=10.1228"])
    assert output.exit_code == 0, output.output
    (alert,) = json.loads(output.output)["alerts"]
    assert len(alert["area_names"]) == 1_650
    assert "answer-truncated" not in output.output


# --- a name that matches no area ----------------------------------------------------------------------------------


def _codes(response: Any) -> list[str]:  # noqa: ANN401
    return [w["code"] for w in response.json()["metadata"]["warnings"]]


@pytest.mark.parametrize(
    ("fmt_params", "advice"),
    [
        pytest.param({}, "Ask by point (`latitude` and `longitude`) to be sure.", id="name-only"),
        pytest.param(
            {"latitude": 54.3233, "longitude": 10.1228},
            "The point alone gives the warnings for the place: ask again without the name.",
            id="with-a-point",
        ),
    ],
)
@pytest.mark.usefixtures("small")
def test_a_name_that_matches_no_area_is_told_to_a_tool_and_never_reads_as_no_warning(
    fmt_params: dict[str, Any], advice: str
) -> None:
    """`Kiel, Stadt` is no area of any warning: the answer says the name matched nothing, in a warning of its own."""
    response = _tool_client().get("/api/alerts", params={**fmt_params, "name": "Kiel, Stadt"})
    assert response.status_code == 200
    answer = response.json()
    assert answer["alerts"] == []
    assert _codes(response) == ["no-alerts-for-place", "no-area-matched"]
    message = answer["metadata"]["warnings"][1]["message"]
    assert "'Kiel, Stadt'" in message
    assert 'That is not "no warning" for the place' in message
    assert advice in message
    # a request that has a point is not told to ask by one
    assert ("Ask by point" in message) is (not fmt_params)


@pytest.mark.usefixtures("small")
def test_the_unmatched_name_is_in_the_header_of_a_csv_too() -> None:
    """A CSV says it in `X-Wetterdienst-Warnings`."""
    response = _tool_client().get("/api/alerts", params={"name": "Munich", "format": "csv"})
    assert response.headers["x-wetterdienst-warnings"] == "no-alerts-for-place, no-area-matched"


@pytest.mark.usefixtures("small")
def test_the_rest_api_does_not_tell_the_unmatched_name_apart() -> None:
    """MCP only: REST says `no-alerts-for-place` as it always did."""
    response = _rest_client().get("/api/alerts", params={"name": "Munich"})
    assert _codes(response) == ["no-alerts-for-place"]


@pytest.mark.parametrize(
    "params",
    [
        pytest.param({"name": "Norderney"}, id="a-name-that-matches"),
        pytest.param({"latitude": 48.1351, "longitude": 11.582}, id="a-place-without-a-warning"),
        pytest.param({}, id="no-place"),
        pytest.param({"name": "Norderney", "latitude": 48.1351, "longitude": 11.582}, id="name-and-point-without-both"),
    ],
)
@pytest.mark.usefixtures("small")
def test_no_area_matched_is_not_told_where_the_name_matched_or_none_was_asked(params: dict[str, Any]) -> None:
    """The name found an area (even where a point then keeps no warning), or there was no name to match."""
    assert "no-area-matched" not in _codes(_tool_client().get("/api/alerts", params=params))


def test_no_area_matched_is_not_told_for_a_snapshot_without_a_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    """Nothing in force is the all-clear that `no-alerts-for-place` says, and nothing could have matched."""
    serve_snapshot(monkeypatch)
    response = _tool_client().get("/api/alerts", params={"name": "Kiel"})
    assert _codes(response) == ["no-alerts-for-place"]


@pytest.mark.parametrize(
    ("kwargs", "matched"),
    [
        ({"name": "Kiel"}, True),
        ({"name": "Munich"}, False),
        ({"name": "801002000"}, True),
        ({"name": "999"}, False),
        ({}, None),
        ({"latitude": 48.1, "longitude": 11.5}, None),
        ({"name": "Norderney", "latitude": 48.1, "longitude": 11.5}, True),
    ],
)
def test_the_result_tells_whether_the_name_matched_an_area_of_the_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    kwargs: dict[str, Any],
    matched: bool | None,  # noqa: FBT001
) -> None:
    """`name_matched` is about the whole snapshot, which the filtered warnings of a result cannot tell."""
    from wetterdienst.provider.dwd.alerts import DwdWeatherAlertRequest  # noqa: PLC0415

    serve_snapshot(monkeypatch, *_BASES)
    assert DwdWeatherAlertRequest(**kwargs).query().name_matched is matched


def test_the_tool_description_says_what_is_left_out() -> None:
    """The contract names the cut and the warning, so a model that reads the description is not surprised by them."""
    pytest.importorskip("fastmcp")
    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def read() -> str:
        tools = await build_mcp_server(restapi.app).list_tools()
        return next(tool for tool in tools if tool.name == "alerts").description or ""

    description = asyncio.run(read())
    assert "answer-truncated" in description
    assert "no-area-matched" in description
    # the REST document does not carry the tool's advice
    rest = TestClient(restapi.app).get("/openapi.json").json()["paths"]["/api/v1/alerts"]["get"]["description"]
    assert "answer-truncated" not in rest
    assert "no-area-matched" not in rest
