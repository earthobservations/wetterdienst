# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The precipitation radar on the REST API: the list of frames and the image of one (GH-3788).

DWD's directory of the RV composite is stood in for by a real file of 2026-11-19
(`tests/provider/dwd/radar/rv_stub.py`), so the request, the decoding, the drawing and the answer are the ones a
live answer goes through.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import io
from typing import TYPE_CHECKING, Any
from urllib.parse import unquote

import freezegun
import pytest
from fastapi.testclient import TestClient

from tests.provider.dwd.radar.rv_stub import FIXTURE_TIME, Dwd, rv_tar
from wetterdienst import exceptions
from wetterdienst.exceptions import MissingDependencyError
from wetterdienst.provider.dwd.radar import frames as frames_module
from wetterdienst.provider.dwd.radar import rv
from wetterdienst.ui import restapi

if TYPE_CHECKING:
    from pathlib import Path

UTC = dt.UTC
RUNS = [FIXTURE_TIME + dt.timedelta(minutes=5 * i) for i in range(4)]
NEWEST = RUNS[-1]
PREFIXES = ["/api/v1", "/api"]


@pytest.fixture(scope="module")
def tars(tmp_path_factory: pytest.TempPathFactory) -> dict[dt.datetime, bytes]:
    """Make the `.tar` of four runs; the newest holds a forecast of the next 20 minutes."""
    directory: Path = tmp_path_factory.mktemp("rv")
    return {run: rv_tar(run, directory, range(0, 21, 5) if run == NEWEST else range(0, 6, 5)) for run in RUNS}


@pytest.fixture
def dwd(monkeypatch: pytest.MonkeyPatch, tars: dict[dt.datetime, bytes]) -> Dwd:
    """Serve the four runs, and have the clock at the newest of them plus a few minutes."""
    return Dwd(dict(tars)).install(monkeypatch)


@pytest.fixture
def client(dwd: Dwd) -> TestClient:  # noqa: ARG001
    """Give the client of the REST app, which answers an unhandled exception with its 500."""
    return TestClient(restapi.app, raise_server_exceptions=False)


def _time(value: dt.datetime) -> str:
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


# --- the list -------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", PREFIXES)
def test_the_list_is_the_loop_the_image_and_the_legend_under_both_prefixes(client: TestClient, prefix: str) -> None:
    """The frames with their runs, where an image lies and what its colours mean, as numbers."""
    with freezegun.freeze_time(NEWEST + dt.timedelta(minutes=3)):
        response = client.get(f"{prefix}/radar/frames")

    assert response.status_code == 200
    body = response.json()
    assert body["product"] == {"id": "rv", "name": "RV composite", "step_minutes": 5, "unit": "mm/h"}
    assert body["run"] == _time(NEWEST)
    frames = body["frames"]
    assert [f["kind"] for f in frames] == ["observation"] * 4 + ["forecast"] * 24
    assert [f["time"] for f in frames[:4]] == [_time(run) for run in RUNS]
    assert frames[4] == {
        "time": _time(NEWEST + dt.timedelta(minutes=5)),
        "run": _time(NEWEST),
        "lead_minutes": 5,
        "kind": "forecast",
    }
    assert frames[-1]["lead_minutes"] == 120
    image = body["image"]
    assert image["crs"] == "EPSG:3857"
    assert image["media_type"] == "image/png"
    assert (image["width"], image["height"]) == (1200, 1169)
    bounds = image["bounds"]
    assert bounds["west"] < bounds["east"]
    assert bounds["south"] < bounds["north"]
    assert (round(bounds["west"], 4), round(bounds["east"], 4)) == (1.4633, 18.7316)
    legend = body["legend"]
    assert legend["unit"] == "mm/h"
    assert legend["transparent_below"] == 0.1
    assert [c["lower"] for c in legend["classes"]] == [0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 25.0]
    assert legend["classes"][-1]["upper"] is None
    assert all(c["color"].startswith("#") and c["label"] for c in legend["classes"])


def test_the_answer_carries_the_licence_the_credit_and_the_note_like_every_answer_with_data(client: TestClient) -> None:
    """DWD's terms and what was done to its data, in the block and in the headers."""
    with freezegun.freeze_time(NEWEST + dt.timedelta(minutes=3)):
        response = client.get("/api/v1/radar/frames")

    metadata = response.json()["metadata"]
    assert metadata["provider"]["name_english"] == "German Weather Service"
    assert metadata["provider"]["license"]["spdx_id"] == "CC-BY-4.0"
    assert metadata["provider"]["attribution"] == "Source: Deutscher Wetterdienst"
    assert metadata["request"]["provider"] == "dwd"
    assert metadata["request"]["network"] == "radar"
    assert metadata["counts"] == {"stations": 0, "rows": 28}
    note = metadata["processing_note"]
    assert note.startswith("Processed by wetterdienst")
    assert "mm/h" in note
    assert "forecast" in note
    assert "drawn" not in note  # the list holds no image; the image's headers say it is
    assert response.headers["x-wetterdienst-license"] == "CC-BY-4.0"
    assert unquote(response.headers["x-wetterdienst-attribution"]) == "Source: Deutscher Wetterdienst"
    assert response.headers["link"] == '<https://creativecommons.org/licenses/by/4.0/>; rel="license"'
    assert response.headers["x-wetterdienst-rows"] == "28"


def test_the_list_is_kept_for_a_minute_and_asked_about_with_its_tag(client: TestClient) -> None:
    """The server holds DWD's list for a minute, so a client may too: a tag of the body and a 304 for the same list."""
    with freezegun.freeze_time(NEWEST + dt.timedelta(minutes=3)):
        first = client.get("/api/v1/radar/frames")
        again = client.get("/api/v1/radar/frames", headers={"If-None-Match": first.headers["etag"]})

    assert first.headers["cache-control"] == "public, max-age=60"
    assert again.status_code == 304
    assert again.content == b""


def test_an_old_run_is_a_warning_and_is_not_kept_by_a_cache(client: TestClient) -> None:
    """The loop of a feed that stopped is no answer to keep: a warning in the block and the header, no `max-age`."""
    with freezegun.freeze_time(NEWEST + dt.timedelta(minutes=50)):
        response = client.get("/api/v1/radar/frames")

    assert [w["code"] for w in response.json()["metadata"]["warnings"]] == ["radar-stale"]
    assert response.headers["x-wetterdienst-warnings"] == "radar-stale"
    assert "cache-control" not in response.headers


def test_the_past_and_the_forecast_are_the_callers_to_cut(client: TestClient) -> None:
    """`past` minutes of analysis and `forecast=false` for none of the forecast."""
    with freezegun.freeze_time(NEWEST + dt.timedelta(minutes=3)):
        short = client.get("/api/v1/radar/frames", params={"past": 5, "forecast": "false"}).json()["frames"]
        none = client.get("/api/v1/radar/frames", params={"past": 0}).json()["frames"]

    assert [f["time"] for f in short] == [_time(RUNS[-2]), _time(RUNS[-1])]
    assert [f["kind"] for f in none].count("observation") == 1


@pytest.mark.parametrize(
    "params",
    [{"past": -1}, {"past": 361}, {"past": "a lot"}, {"product": "wn"}, {"forecast": "maybe"}, {"hours": 2}],
)
def test_a_parameter_that_is_none_is_a_422_that_names_it(client: TestClient, params: dict[str, Any]) -> None:
    """The request is held to its model: a number out of range, a product not served, a parameter that is none."""
    response = client.get("/api/v1/radar/frames", params=params)

    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/problem+json")


def test_an_empty_directory_is_a_502_and_not_a_quiet_sky(monkeypatch: pytest.MonkeyPatch, client: TestClient) -> None:
    """DWD's outage is the provider's failure for the client to retry, never an answer of no frames."""
    Dwd({}).install(monkeypatch)

    response = client.get("/api/v1/radar/frames")

    assert response.status_code == 502
    assert response.headers["content-type"].startswith("application/problem+json")


# --- the image ------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", PREFIXES)
def test_a_frame_is_a_png_with_its_time_its_run_and_the_terms_in_the_headers(client: TestClient, prefix: str) -> None:
    """The picture holds no text, so the headers carry what the block of a JSON answer does, and which frame it is."""
    response = client.get(f"{prefix}/radar/frame", params={"time": _time(RUNS[1]), "run": _time(RUNS[1])})

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.content.startswith(b"\x89PNG\r\n\x1a\n")
    assert response.headers["x-wetterdienst-radar-time"] == _time(RUNS[1])
    assert response.headers["x-wetterdienst-radar-run"] == _time(RUNS[1])
    assert response.headers["x-wetterdienst-license"] == "CC-BY-4.0"
    assert unquote(response.headers["x-wetterdienst-attribution"]) == "Source: Deutscher Wetterdienst"
    assert "The image is drawn from the composite's precipitation field." in unquote(
        response.headers["x-wetterdienst-processing"]
    )
    assert response.headers["x-wetterdienst-rows"] == "1"


def test_a_frame_of_a_run_may_be_kept_for_an_hour_and_one_of_the_newest_for_a_minute(client: TestClient) -> None:
    """With its run the frame is the same as long as DWD keeps the run; without it a forecast frame is the newest's."""
    named = client.get("/api/v1/radar/frame", params={"time": _time(RUNS[0]), "run": _time(RUNS[0])})
    unnamed = client.get("/api/v1/radar/frame", params={"time": _time(NEWEST + dt.timedelta(minutes=10))})

    assert named.headers["cache-control"] == "public, max-age=3600"
    assert unnamed.headers["cache-control"] == "public, max-age=60"
    assert unnamed.headers["x-wetterdienst-radar-run"] == _time(NEWEST)


def test_a_frame_is_asked_about_with_its_tag(client: TestClient) -> None:
    """The same frame is a 304 for the tag it came with, and a 200 for a tag that is not its."""
    params = {"time": _time(RUNS[0]), "run": _time(RUNS[0])}
    first = client.get("/api/v1/radar/frame", params=params)
    again = client.get("/api/v1/radar/frame", params=params, headers={"If-None-Match": first.headers["etag"]})
    other = client.get(
        "/api/v1/radar/frame",
        params=params,
        headers={"If-None-Match": 'W/"the-tag-of-another-image"'},
    )

    assert again.status_code == 304
    assert again.content == b""
    assert again.headers["cache-control"] == "public, max-age=3600"
    assert other.status_code == 200


def test_the_image_of_a_frame_is_the_same_each_time(client: TestClient, dwd: Dwd) -> None:
    """One decode serves every reader: the second request reads nothing of DWD."""
    params = {"time": _time(RUNS[2]), "run": _time(RUNS[2])}
    first = client.get("/api/v1/radar/frame", params=params)
    asked = len(dwd.ranged)
    second = client.get("/api/v1/radar/frame", params=params)

    assert second.content == first.content
    assert len(dwd.ranged) == asked == 1


def test_the_picture_is_the_one_the_decoder_draws(client: TestClient) -> None:
    """What the endpoint serves is `rv.draw` of the file, to the byte, in the size the list announced."""
    from tests.provider.dwd.radar.rv_stub import FIXTURE  # noqa: PLC0415

    response = client.get("/api/v1/radar/frame", params={"time": _time(FIXTURE_TIME), "run": _time(FIXTURE_TIME)})

    assert response.content == rv.draw(rv.read_field(FIXTURE.read_bytes())).png


@pytest.mark.parametrize(
    ("params", "status"),
    [
        ({"time": "nonsense"}, 400),
        ({"time": _time(FIXTURE_TIME + dt.timedelta(minutes=1))}, 400),
        ({"time": _time(FIXTURE_TIME), "run": "yesterday"}, 400),
        ({"time": _time(FIXTURE_TIME), "run": _time(FIXTURE_TIME + dt.timedelta(hours=1))}, 400),
        ({"time": _time(FIXTURE_TIME - dt.timedelta(days=3)), "run": _time(FIXTURE_TIME - dt.timedelta(days=3))}, 404),
        ({"time": _time(RUNS[0] + dt.timedelta(minutes=15)), "run": _time(RUNS[0])}, 404),
        ({}, 422),
        ({"time": _time(FIXTURE_TIME), "product": "wn"}, 422),
        ({"time": _time(FIXTURE_TIME), "format": "jpg"}, 422),
    ],
    ids=[
        "no-time",
        "not-5-minutes",
        "no-run",
        "run-after-time",
        "run-gone",
        "lead-not-in-tar",
        "no-time-given",
        "product",
        "format",
    ],
)
def test_a_request_that_is_no_frame_is_a_problem_of_the_status_that_says_whose_it_is(
    client: TestClient, params: dict[str, str], status: int
) -> None:
    """A time that does not parse or is not a frame is the caller's, a run DWD no longer holds a 404."""
    response = client.get("/api/v1/radar/frame", params=params)

    assert response.status_code == status
    assert response.headers["content-type"].startswith("application/problem+json")
    assert "etag" not in response.headers
    assert "cache-control" not in response.headers


@pytest.mark.parametrize(
    ("error", "status"),
    [
        pytest.param(exceptions.DownloadError("https://opendata.dwd.de/x.tar", "502"), 502, id="download"),
        pytest.param(rv.RadarFormatError("DWD changed the file"), 502, id="format"),
        pytest.param(exceptions.NoInternetError("No internet"), 503, id="no-internet"),
        pytest.param(exceptions.ProviderRateLimitError("https://x/", "rate limited", 7), 503, id="rate-limit"),
        pytest.param(MissingDependencyError("Drawing the radar composite requires numpy"), 501, id="no-extra"),
        pytest.param(ValueError("a defect"), 500, id="defect"),
    ],
)
def test_a_failure_is_answered_by_the_hierarchy_and_a_wait_is_passed_on(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, error: BaseException, status: int
) -> None:
    """The one table of statuses: DWD that fails or sends what the decoder is not written for is a 502."""

    def fail(*_args: object, **_kwargs: object) -> None:
        raise error

    monkeypatch.setattr(frames_module.DwdRadarFrames, "frame", fail)
    monkeypatch.setattr(frames_module.DwdRadarFrames, "frames", fail)

    for path, params in (("frame", {"time": _time(FIXTURE_TIME)}), ("frames", {})):
        response = client.get(f"/api/v1/radar/{path}", params=params)
        assert response.status_code == status, path
        assert response.headers["content-type"].startswith("application/problem+json")
        if isinstance(error, exceptions.ProviderRateLimitError):
            assert response.headers["retry-after"] == "7"


def test_the_extra_missing_on_the_server_is_a_501_that_names_no_package(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A server without the `radar` extra declines, and does not tell a client what to install on it."""
    from wetterdienst.util import extras  # noqa: PLC0415

    def missing(name: str, what: str, *, extra: str | None = None) -> None:
        raise MissingDependencyError(extras.missing_dependency_message(what, name, extra=extra))

    monkeypatch.setattr(rv, "import_optional", missing)

    response = client.get("/api/v1/radar/frame", params={"time": _time(RUNS[0]), "run": _time(RUNS[0])})

    assert response.status_code == 501
    assert "h5py" not in response.text
    assert "pip install" not in response.text


# --- the document and the tools -------------------------------------------------------------------------------------


def test_the_routes_are_in_the_openapi_document_under_a_tag_of_their_own(client: TestClient) -> None:
    """What the app's types are generated from: the list, its answer, and the image with the statuses it can answer."""
    schema = client.get("/openapi.json").json()
    frames = schema["paths"]["/api/v1/radar/frames"]["get"]
    frame = schema["paths"]["/api/v1/radar/frame"]["get"]

    assert frames["tags"] == frame["tags"] == ["Precipitation radar"]
    assert {p["name"] for p in frames["parameters"]} == {"product", "past", "forecast", "pretty"}
    assert {p["name"]: p["required"] for p in frame["parameters"]} == {"product": False, "time": True, "run": False}
    assert "image/png" in frame["responses"]["200"]["content"]
    assert {"304", "400", "404", "501", "502"} <= set(frame["responses"])
    assert "radar-stale" in frames["description"]
    answer = frames["responses"]["200"]["content"]["application/json"]["schema"]
    assert answer["$ref"].endswith("RadarFramesWithMetadataDict")
    assert "/api/radar/frames" not in schema["paths"]  # the alias is no part of the document


def test_the_images_are_no_tool_of_an_assistant() -> None:
    """A map overlay is nothing a model can read: neither route is an MCP tool."""
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def names() -> list[str]:
        async with Client(build_mcp_server(restapi.app)) as session:
            return [tool.name for tool in await session.list_tools()]

    assert not [name for name in asyncio.run(names()) if "radar" in name]


def test_a_png_made_of_the_stand_in_is_no_larger_than_a_map_overlay_should_be(client: TestClient) -> None:
    """A loop is 49 of them: an indexed PNG of a rainy evening is some 30 KB, so the loop is a megabyte and a half."""
    response = client.get("/api/v1/radar/frame", params={"time": _time(FIXTURE_TIME), "run": _time(FIXTURE_TIME)})

    assert len(response.content) < 60_000
    assert io.BytesIO(response.content).read(4) == b"\x89PNG"
