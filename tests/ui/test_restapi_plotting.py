# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The charts of the REST API are a setting, off by default: `WD_RESTAPI_PLOTTING` (GH-4461).

Every image costs the server a Chrome (Kaleido), so a server draws none until its operator says so. A request for a
chart format (`html`, `png`, `jpg`, `webp`, `svg`, `pdf`) of `stations`, `values`, `interpolate` or `summarize` is a 403
problem of the kind `charts-disabled` before anything is read; with the setting on, the answers are what they were.

Offline: the data and the browser are stood in for. `tests/ui/conftest.py` switches the setting on for the other tests
of this directory, so each test here says which it holds.
"""

from __future__ import annotations

import os
import subprocess
import sys
import textwrap
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient

from tests.ui.test_restapi import (
    _IMAGE_MEDIA_TYPES,
    _IMAGE_ROUTES,
    _image_params,
    _stub_result,
    _values_result_of_shape,
)
from wetterdienst import Settings
from wetterdienst.io.formats import FORMATS, names_of
from wetterdienst.ui import restapi
from wetterdienst.ui.problems import PROBLEMS, ProblemKind

if TYPE_CHECKING:
    from pathlib import Path

CHARTS = names_of("chart")
#: the formats each route answers when it draws no chart
DATA = {
    "stations": "json, geojson, csv or ndjson",
    "values": "json, geojson, csv or ndjson",
    "interpolate": "json, geojson or csv",
    "summarize": "json, geojson or csv",
}
PREFIXES = ["/api", "/api/v1"]
#: what the browser is stood in for with
IMAGE_BYTES = b"<svg/>"


@pytest.fixture(autouse=True)
def _off(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep the `WD_*` variables and the `.env` of whoever runs the tests out, and have charts off, as they are."""
    for name in list(os.environ):
        if name.upper().startswith("WD_") and name.upper() != "WD_CACHE_DIR":
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("WD_RESTAPI_PLOTTING", "false")


@pytest.fixture
def client() -> TestClient:
    """Make a client that answers what the server would, its 500 included."""
    return TestClient(restapi.app, raise_server_exceptions=False)


def _on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("WD_RESTAPI_PLOTTING", "true")


def _unreached(*_args: object, **_kwargs: object) -> None:
    """Stand in for what a refused chart must not reach."""
    msg = "a chart that is refused went on"
    raise AssertionError(msg)


def _nothing_is_reached(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make everything a request does after its refusals fail the test: the provider, the lookup, the answer, Chrome.

    Each is a name of the handlers' module (or of the browser's start), so a handler that went on past a refusal fails
    on the first of them it reaches; `begin_response` is the first thing the handlers do after the refusal.
    """
    for name in (
        "Wetterdienst",
        "begin_response",
        "get_stations",
        "get_values",
        "get_interpolate",
        "get_summarize",
        "_get_timeseries_api",
        "_request_options",
        "_geo_options",
        "_values",
        "_geo_values",
        "_stream_values",
        "_stream_stations",
        "render",
        "render_stations",
    ):
        monkeypatch.setattr(restapi, name, _unreached)
    monkeypatch.setattr("wetterdienst.io.export._draw", _unreached)


def _stub(monkeypatch: pytest.MonkeyPatch, endpoint: str) -> None:
    """Answer a route with a result of one station, and every image with `IMAGE_BYTES`."""
    monkeypatch.setattr("wetterdienst.io.export._draw", lambda *_args, **_kwargs: IMAGE_BYTES)
    if endpoint == "stations":
        stations = _values_result_of_shape("long").stations
        monkeypatch.setattr(restapi, "get_stations", lambda **_kwargs: stations)
    else:
        _stub_result(monkeypatch, f"/api/{endpoint}")


def _get(client: TestClient, prefix: str, endpoint: str, query: dict[str, Any], **given: Any) -> Any:  # noqa: ANN401
    return client.get(f"{prefix}/{endpoint}", params=_image_params(query, **given))


# --- off: the refusal ---------------------------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("fmt", CHARTS)
@pytest.mark.parametrize(("endpoint", "query"), _IMAGE_ROUTES, ids=[endpoint for endpoint, _ in _IMAGE_ROUTES])
def test_a_chart_is_a_403_problem_on_every_route_in_every_format_and_nothing_is_reached(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, endpoint: str, query: dict[str, str], fmt: str, prefix: str
) -> None:
    """The refusal names the format, the formats the route answers and the setting; none of the work is started."""
    _nothing_is_reached(monkeypatch)

    response = _get(client, prefix, endpoint, query, format=fmt)

    assert response.status_code == 403, response.text
    assert response.headers["Content-Type"] == "application/problem+json"
    problem = response.json()
    assert problem["type"] == "urn:wetterdienst:problem:charts-disabled"
    assert problem["status"] == 403
    assert problem["title"] == "Forbidden"
    assert problem["detail"] == (
        f"This server draws no charts, so format={fmt} is refused. It answers {DATA[endpoint]}. "
        "The request was valid: ask for one of these, or ask whoever runs this instance to switch charts on "
        "(WD_RESTAPI_PLOTTING=true)."
    )
    assert problem["instance"] == f"urn:wetterdienst:request:{problem['request_id']}"
    assert response.headers["X-Request-ID"] == problem["request_id"]
    # the parameter that is refused, where a form or a client looks for it, with what the server answers
    (entry,) = problem["errors"]
    assert entry["loc"] == ["query", "format"]
    assert entry["input"] == fmt
    assert entry["ctx"]["formats"] == [name.strip() for name in DATA[endpoint].replace(" or ", ", ").split(",")]


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize(("endpoint", "query"), _IMAGE_ROUTES, ids=[endpoint for endpoint, _ in _IMAGE_ROUTES])
def test_the_refusal_is_not_cached_and_is_no_retry(
    client: TestClient, endpoint: str, query: dict[str, str], prefix: str
) -> None:
    """The operator may switch charts on at once (a `.env` is read by every request): no cache keeps the 403."""
    response = _get(client, prefix, endpoint, query, format="png")

    assert response.status_code == 403
    assert response.headers["Cache-Control"] == "no-store"
    for header in ("ETag", "Last-Modified", "Expires", "Retry-After", "Vary"):
        assert header not in response.headers, header
    assert response.headers["X-Content-Type-Options"] == "nosniff"


def test_the_kind_is_declared_with_its_status() -> None:
    """The kind is one of the table of the docs, with the status it is answered with."""
    assert ProblemKind.CHARTS_DISABLED.value == "charts-disabled"
    assert PROBLEMS[ProblemKind.CHARTS_DISABLED].status == 403
    assert "WD_RESTAPI_PLOTTING" in PROBLEMS[ProblemKind.CHARTS_DISABLED].description


def test_charts_are_off_without_any_setting(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The default is off: with no variable and no `.env`, a chart is refused."""
    monkeypatch.delenv("WD_RESTAPI_PLOTTING")
    assert Settings().restapi_plotting is False
    _nothing_is_reached(monkeypatch)

    response = client.get("/api/stations", params=_image_params({"all": "true"}, format="svg"))

    assert response.status_code == 403
    assert response.json()["type"] == "urn:wetterdienst:problem:charts-disabled"


@pytest.mark.parametrize("endpoint", DATA)
def test_the_formats_a_refusal_names_are_those_of_the_route_without_its_charts(endpoint: str) -> None:
    """What `DATA` says is read off the request model: the formats of the route that are no chart."""
    from typing import get_args  # noqa: PLC0415

    request = {
        "stations": restapi.StationsRequest,
        "values": restapi.ValuesRequest,
        "interpolate": restapi.RestInterpolationRequest,
        "summarize": restapi.RestSummaryRequest,
    }[endpoint]
    formats = get_args(request.model_fields["format"].annotation)
    assert tuple(name for name in formats if FORMATS[name].kind == "chart") == CHARTS
    assert ", ".join(name for name in formats if FORMATS[name].kind == "data") == DATA[endpoint].replace(" or ", ", ")


def test_importing_the_server_and_refusing_a_chart_loads_neither_plotly_nor_kaleido() -> None:
    """The refusal is before the plotting libraries: a fresh process that is refused has imported neither."""
    script = textwrap.dedent(
        """
        import os, sys
        os.environ["WD_RESTAPI_PLOTTING"] = "false"
        from fastapi.testclient import TestClient
        from wetterdienst.ui.restapi import app

        response = TestClient(app).get(
            "/api/values",
            params={"provider": "dwd", "network": "observation", "parameters": "daily/kl", "stations": "01048",
                    "format": "png"},
        )
        assert response.status_code == 403, response.text
        loaded = [name for name in ("plotly", "kaleido", "choreographer") if name in sys.modules]
        assert not loaded, loaded
        """
    )
    done = subprocess.run([sys.executable, "-I", "-c", script], capture_output=True, text=True, check=False)  # noqa: S603
    assert done.returncode == 0, done.stderr[-2000:]


# --- off: the data formats, and what else is as it was --------------------------------------------------------------


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize(("endpoint", "query"), _IMAGE_ROUTES, ids=[endpoint for endpoint, _ in _IMAGE_ROUTES])
def test_the_data_formats_are_answered_as_ever(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, endpoint: str, query: dict[str, str], prefix: str
) -> None:
    """Nothing but a chart is refused: each data format of the route is a 200."""
    _stub(monkeypatch, endpoint)
    offered = {"stations": ("json", "geojson", "csv", "ndjson"), "values": ("json", "geojson", "csv", "ndjson")}.get(
        endpoint, ("json", "geojson", "csv")
    )

    for fmt in offered:
        response = _get(client, prefix, endpoint, query, format=fmt)
        assert response.status_code == 200, (fmt, response.text[:300])


@pytest.mark.parametrize("endpoint", ["stations", "values"])
def test_a_size_with_a_data_format_is_ignored_as_it_was(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, endpoint: str
) -> None:
    """`width`, `height` and `scale` mean nothing to a data format: not measured, not refused, with charts off too."""
    _stub(monkeypatch, endpoint)
    query = dict(_IMAGE_ROUTES)[endpoint]

    response = _get(client, "/api", endpoint, query, format="json", width=100_000, height=100_000, scale=50)

    assert response.status_code == 200


@pytest.mark.parametrize("endpoint", [endpoint for endpoint, _ in _IMAGE_ROUTES])
def test_head_is_no_way_round_it(client: TestClient, monkeypatch: pytest.MonkeyPatch, endpoint: str) -> None:
    """The data routes answer `GET` alone, as they did: a `HEAD` is a 405, on or off, and reads nothing."""
    query = dict(_IMAGE_ROUTES)[endpoint]
    _nothing_is_reached(monkeypatch)

    off = client.head(f"/api/v1/{endpoint}", params=_image_params(query, format="png"))
    _on(monkeypatch)
    on = client.head(f"/api/v1/{endpoint}", params=_image_params(query, format="png"))

    assert off.status_code == on.status_code == 405


@pytest.mark.parametrize("accept", ["image/png", "image/svg+xml", "text/html", "application/pdf", "*/*", "image/*"])
def test_the_accept_header_is_no_way_round_it_and_asks_for_no_chart(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, accept: str
) -> None:
    """The format is the parameter, nothing else: an `Accept` for an image does not get one, nor a refusal for json."""
    _stub(monkeypatch, "values")
    query = dict(_IMAGE_ROUTES)["values"]

    asked_chart = client.get("/api/values", params=_image_params(query, format="png"), headers={"Accept": accept})
    asked_json = client.get("/api/values", params=_image_params(query, format="json"), headers={"Accept": accept})

    assert asked_chart.status_code == 403
    assert asked_json.status_code == 200
    assert asked_json.headers["Content-Type"] == "application/json"


# --- the order of the refusals -------------------------------------------------------------------------------------


@pytest.mark.parametrize(("endpoint", "query"), _IMAGE_ROUTES, ids=[endpoint for endpoint, _ in _IMAGE_ROUTES])
def test_a_request_that_is_malformed_is_the_422_first(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, endpoint: str, query: dict[str, str]
) -> None:
    """Validation is before the handler, so a chart that is also malformed is told what is wrong with it, as ever."""
    _nothing_is_reached(monkeypatch)

    for wrong in ({"width": 0}, {"scale": -1}, {"nonsense": "1"}, {"provider": None}):
        params = {k: v for k, v in _image_params(query, format="png", **wrong).items() if v is not None}
        response = client.get(f"/api/{endpoint}", params=params)
        assert response.status_code == 422, (wrong, response.text[:200])
        assert response.json()["type"] == "urn:wetterdienst:problem:invalid-parameters"


@pytest.mark.parametrize("fmt", ["PNG", "Png", "HTML", "pDf", " png", "png ", "jpeg", "gif", ""])
def test_a_format_that_is_none_is_the_422_it_was_whatever_the_setting(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, fmt: str
) -> None:
    """The formats are compared as they are written: another case is no format, as before, and no way round the 403."""
    query = dict(_IMAGE_ROUTES)["values"]
    off = client.get("/api/values", params=_image_params(query, format=fmt))
    _on(monkeypatch)
    on = client.get("/api/values", params=_image_params(query, format=fmt))

    assert off.status_code == on.status_code == 422
    assert off.json()["errors"][0]["loc"] == ["query", "format"]
    assert [e["msg"] for e in off.json()["errors"]] == [e["msg"] for e in on.json()["errors"]]


@pytest.mark.parametrize("endpoint", ["values", "stations"])
def test_a_chart_too_large_is_told_that_charts_are_off_not_to_lower_the_scale(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, endpoint: str
) -> None:
    """Off, the size is moot: the 403 comes first. On, it is the 400 of `image-too-large` it was."""
    query = dict(_IMAGE_ROUTES)[endpoint]
    off = _get(client, "/api", endpoint, query, format="png", width=100_000)
    _on(monkeypatch)
    monkeypatch.setattr(restapi, "Wetterdienst", _unreached)
    on = _get(client, "/api", endpoint, query, format="png", width=100_000)

    assert off.status_code == 403
    assert off.json()["type"] == "urn:wetterdienst:problem:charts-disabled"
    assert on.status_code == 400
    assert on.json()["type"] == "urn:wetterdienst:problem:image-too-large"


@pytest.mark.parametrize("endpoint", ["values", "stations"])
def test_a_chart_for_a_network_that_is_not_served_is_the_403_not_the_404(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, endpoint: str
) -> None:
    """Nothing is looked up for a refused chart: the provider and network are not asked for. On, they are."""
    query = dict(_IMAGE_ROUTES)[endpoint]
    off = _get(client, "/api", endpoint, query, network="nowhere", format="png")
    _on(monkeypatch)
    on = _get(client, "/api", endpoint, query, network="nowhere", format="png")

    assert off.status_code == 403
    assert on.status_code == 404


@pytest.mark.parametrize("first", ["json", "png"])
def test_a_format_given_twice_is_refused_by_the_one_the_route_answers(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, first: str
) -> None:
    """The route reads one `format`, and that is what is checked and what is answered: neither order is a way round."""
    second = "png" if first == "json" else "json"
    query = "provider=dwd&network=observation&parameters=daily/kl/temperature_air_mean_2m&stations=01048"
    _stub(monkeypatch, "values")
    off = client.get(f"/api/values?{query}&format={first}&format={second}")
    _on(monkeypatch)
    on = client.get(f"/api/values?{query}&format={first}&format={second}")

    answered_chart = on.headers["Content-Type"] == "image/png"
    assert on.status_code == 200
    assert off.status_code == (403 if answered_chart else 200)


# --- on: as ever ----------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize("fmt", CHARTS)
@pytest.mark.parametrize(("endpoint", "query"), _IMAGE_ROUTES, ids=[endpoint for endpoint, _ in _IMAGE_ROUTES])
def test_with_the_setting_on_every_chart_is_answered_on_every_route_under_both_prefixes(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, endpoint: str, query: dict[str, str], fmt: str, prefix: str
) -> None:
    """The answer of each format is what it was: its media type, the image the browser drew, no `Cache-Control`."""
    _on(monkeypatch)
    _stub(monkeypatch, endpoint)

    response = _get(client, prefix, endpoint, query, format=fmt)

    assert response.status_code == 200, response.text[:300]
    if fmt == "html":
        assert response.headers["Content-Type"] == "text/html; charset=utf-8"
        assert "<html" in response.text
    else:
        assert response.headers["Content-Type"] == _IMAGE_MEDIA_TYPES[fmt]
        assert response.content == IMAGE_BYTES
    assert "Cache-Control" not in response.headers
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert ("Content-Security-Policy" in response.headers) == (fmt == "svg")


@pytest.mark.parametrize(
    "text",
    ["true", "1", "on", "yes", "TRUE"],
)
def test_the_setting_is_read_for_every_request_from_the_environment(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, text: str
) -> None:
    """Switching it on or off needs no restart: the next request is answered by what is set then."""
    _stub(monkeypatch, "stations")
    query = dict(_IMAGE_ROUTES)["stations"]

    refused = _get(client, "/api", "stations", query, format="png")
    monkeypatch.setenv("WD_RESTAPI_PLOTTING", text)
    answered = _get(client, "/api", "stations", query, format="png")
    monkeypatch.setenv("WD_RESTAPI_PLOTTING", "false")
    refused_again = _get(client, "/api", "stations", query, format="png")

    assert [refused.status_code, answered.status_code, refused_again.status_code] == [403, 200, 403]


def test_the_env_file_switches_charts_on_and_the_environment_overrules_it(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`.env` is read as for every setting; a variable of the process wins, as it does everywhere."""
    _stub(monkeypatch, "stations")
    query = dict(_IMAGE_ROUTES)["stations"]
    monkeypatch.delenv("WD_RESTAPI_PLOTTING")
    (tmp_path / ".env").write_text("WD_RESTAPI_PLOTTING=true\n")

    from_file = _get(client, "/api", "stations", query, format="png")
    monkeypatch.setenv("WD_RESTAPI_PLOTTING", "false")
    overruled = _get(client, "/api", "stations", query, format="png")

    assert from_file.status_code == 200
    assert overruled.status_code == 403


def test_a_malformed_setting_is_the_server_error_it_is_for_every_setting(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The value is the operator's: a variable that is no boolean fails the request as the other settings do."""
    monkeypatch.setenv("WD_RESTAPI_PLOTTING", "secret-ish")

    response = client.get("/api/stations", params=_image_params({"all": "true"}, format="png"))

    assert response.status_code == 500
    assert "secret-ish" not in response.text


# --- the OpenAPI document, the tools and the app ----------------------------------------------------------------


@pytest.mark.parametrize("endpoint", DATA)
def test_the_document_keeps_the_charts_in_the_enum_and_says_they_need_the_setting(endpoint: str) -> None:
    """One document for every server: the enum is whole, the description says a chart is for a server that has it on."""
    operation = restapi.app.openapi()["paths"][f"/api/v1/{endpoint}"]["get"]
    parameter = next(p for p in operation["parameters"] if p["name"] == "format")

    assert set(CHARTS) <= set(parameter["schema"]["enum"])
    assert "WD_RESTAPI_PLOTTING" in parameter["description"]
    assert "403" in operation["responses"]


def test_no_other_route_can_answer_a_403() -> None:
    """Only the four routes that draw a chart declare the refusal."""
    paths = restapi.app.openapi()["paths"]
    declared = {
        path.removeprefix("/api/v1/")
        for path, item in paths.items()
        if path.startswith("/api/v1/") and "403" in item["get"]["responses"]
    }
    assert declared == set(DATA)


def _mcp_call(tool: str, arguments: dict[str, Any], seen: list[dict[str, str]]) -> Any:  # noqa: ANN401
    """Call a tool of the real server, built on a stand-in for the REST app that records what is asked of it."""
    pytest.importorskip("fastmcp")
    from tests.ui.test_mcp_formats import _calls  # noqa: PLC0415
    from tests.ui.test_mcp_slim_schemas import _stand_in  # noqa: PLC0415

    app, requests = _stand_in()
    ((result, _),) = _calls(app, [(tool, arguments)])
    seen.extend(requests)
    return result


_VALUES_CALL = {
    "provider": "dwd",
    "network": "observation",
    "parameters": "daily/climate_summary/temperature_air_mean_2m",
    "stations": "01048",
}


@pytest.mark.parametrize("fmt", CHARTS)
def test_a_tool_offers_no_chart_and_says_so_where_the_server_draws_none(
    monkeypatch: pytest.MonkeyPatch, fmt: str
) -> None:
    """A tool asked for a chart is refused by the tool, nothing is requested, and no model is sent to a 403."""
    seen: list[dict[str, str]] = []

    off = _mcp_call("values", {**_VALUES_CALL, "format": fmt}, seen)
    _on(monkeypatch)
    on = _mcp_call("values", {**_VALUES_CALL, "format": fmt}, seen)

    assert off.is_error
    assert off.content[0].text == (
        f"format={fmt} is not offered by the tool values, which answers json, geojson, csv or ndjson. "
        "This server draws no charts."
    )
    assert on.is_error
    assert on.content[0].text == (
        f"format={fmt} is not offered by the tool values, which answers json, geojson, csv or ndjson. "
        f"Charts are drawn by the REST API: /api/v1/values takes format={fmt}."
    )
    assert seen == []


@pytest.mark.parametrize("option", ["width", "height", "scale"])
def test_a_tool_given_an_image_size_says_so_too(monkeypatch: pytest.MonkeyPatch, option: str) -> None:
    """The size of a chart image is refused by the tool, and the pointer to REST follows the setting."""
    seen: list[dict[str, str]] = []

    off = _mcp_call("values", {**_VALUES_CALL, "format": "csv", option: 5}, seen)
    _on(monkeypatch)
    on = _mcp_call("values", {**_VALUES_CALL, "format": "csv", option: 5}, seen)

    assert off.is_error
    assert off.content[0].text.endswith("and the tool answers data only. This server draws no charts.")
    assert on.content[0].text.endswith(f"Charts are drawn by the REST API: /api/v1/values takes {option}.")
    assert seen == []


@pytest.mark.parametrize("tool", ["stations", "values", "interpolate", "summarize"])
def test_a_tool_answers_its_data_formats_with_the_charts_off(tool: str) -> None:
    """The tools are unchanged: a call in a data format reaches the route and is answered."""
    from tests.ui.test_mcp_slim_schemas import _required  # noqa: PLC0415

    pytest.importorskip("fastmcp")
    seen: list[dict[str, str]] = []

    result = _mcp_call(tool, {**_required(tool), "format": "csv"}, seen)

    assert not result.is_error, result.content
    assert [request["format"] for request in seen] == ["csv"]


def test_the_charts_of_the_tools_are_refused_in_the_tools_not_by_a_route(monkeypatch: pytest.MonkeyPatch) -> None:
    """With the real app, a tool call for a chart never reaches a handler: the tool refuses it first."""
    pytest.importorskip("fastmcp")
    from tests.ui.test_mcp_formats import _calls  # noqa: PLC0415

    _nothing_is_reached(monkeypatch)
    ((result, _),) = _calls(restapi.app, [("stations", {**_image_params({"all": True}), "format": "png"})])

    assert result.is_error
    assert result.content[0].text.startswith("format=png is not offered by the tool stations")
