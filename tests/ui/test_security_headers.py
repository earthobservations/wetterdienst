# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""`X-Content-Type-Options: nosniff` on every answer and `Content-Security-Policy` on those that can use one (GH-3349).

Offline: the request goes through the app's routes, middleware and handlers with a client, the data stood in for.
"""

from __future__ import annotations

import os
import re
import time
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from typing import TYPE_CHECKING, Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from tests.ui.test_restapi import _OBSERVATION, _stub_result, _stub_stream, _values_result_of_shape
from wetterdienst.ui import restapi
from wetterdienst.ui.middleware import RequestContextMiddleware
from wetterdienst.ui.problems import problem_headers

if TYPE_CHECKING:
    from pathlib import Path

_VALUES = {**_OBSERVATION, "stations": "01048"}
_NOSNIFF = "X-Content-Type-Options"
_CSP = "Content-Security-Policy"


@pytest.fixture(autouse=True)
def _no_ambient_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep the WD_* variables and the `.env` of whoever runs the tests out of the settings."""
    for name in list(os.environ):
        if name.upper().startswith("WD_") and name.upper() != "WD_CACHE_DIR":
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


@pytest.fixture
def client() -> TestClient:
    """Make a client that answers an unhandled exception as the server does, with its 500."""
    return TestClient(restapi.app, raise_server_exceptions=False)


def _once(response: Any, name: str = _NOSNIFF) -> list[str]:  # noqa: ANN401
    """Give the values of a header, one for each time the response sent it."""
    return response.headers.get_list(name)


@pytest.mark.parametrize(
    ("path", "status"),
    [
        ("/", 200),
        ("/health", 200),
        ("/robots.txt", 200),
        ("/docs", 200),
        ("/redoc", 200),
        ("/openapi.json", 200),
        ("/api/version", 200),
        ("/api/v1/version", 200),
        ("/api/providers", 200),
        ("/api/glossary", 200),
        ("/api/coverage", 200),
        # the errors, each from a handler of its own: an unknown path, a route's 404 and a 422
        ("/nowhere", 404),
        ("/api/nowhere", 404),
        ("/api/v1/glossary?limit=0", 422),
    ],
)
def test_every_route_family_answers_nosniff(client: TestClient, path: str, status: int) -> None:
    """The documents, the data, the catalogues and the errors each carry the header, once."""
    response = client.get(path)

    assert response.status_code == status, response.text[:200]
    assert _once(response) == ["nosniff"]


def test_a_method_not_allowed_answers_nosniff(client: TestClient) -> None:
    """A 405 is Starlette's own, answered by a handler of the app."""
    response = client.post("/api/version")

    assert response.status_code == 405
    assert _once(response) == ["nosniff"]


@pytest.mark.parametrize("fmt", ["json", "geojson", "csv", "ndjson", "html"])
def test_values_answer_nosniff_in_every_data_format(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, fmt: str
) -> None:
    """A rendered answer and the streamed ones (csv and ndjson are sent station by station) carry it."""
    _stub_result(monkeypatch, "/api/values")

    response = client.get("/api/values", params={**_VALUES, "format": fmt})

    assert response.status_code == 200
    assert _once(response) == ["nosniff"]


def test_a_stream_that_fails_late_still_answers_nosniff(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The headers are sent before the first row: a stream that breaks afterwards had them."""
    result = _values_result_of_shape("long")
    _stub_stream(monkeypatch, [result], error=RuntimeError("bug"))

    response = client.get("/api/v1/values", params={**_VALUES, "format": "ndjson"})

    assert _once(response) == ["nosniff"]


@pytest.mark.parametrize("fmt", ["png", "jpg", "svg", "pdf"])
def test_stripes_image_answers_nosniff_in_every_image_format(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, fmt: str
) -> None:
    """An image is a body a browser could take for something else: the header says it is the image."""

    class _Figure:
        def to_image(self, *_args: object, **_kwargs: object) -> bytes:
            return b"image"

    monkeypatch.setattr(restapi, "_plot_stripes", lambda _request: _Figure())
    response = client.get("/api/stripes/image", params={"kind": "temperature", "station": "01048", "format": fmt})

    assert response.status_code == 200
    assert _once(response) == ["nosniff"]


def test_an_unhandled_error_answers_nosniff(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """A 500 that no handler of the route wraps is answered by Starlette's outermost middleware, outside the app's."""

    class _Broken:
        def __iter__(self) -> None:
            msg = "bug"
            raise RuntimeError(msg)

    monkeypatch.setattr(restapi.Wetterdienst, "registry", _Broken())
    response = client.get("/")

    assert response.status_code == 500
    assert _once(response) == ["nosniff"]


def test_a_failure_the_route_wraps_answers_nosniff(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The 500 of a failure the endpoint turns into a problem is answered inside the middleware."""

    def broken(**_kwargs: object) -> None:
        msg = "bug"
        raise RuntimeError(msg)

    monkeypatch.setattr(restapi, "get_values", broken)
    response = client.get("/api/v1/values", params=_VALUES)

    assert response.status_code == 500
    assert _once(response) == ["nosniff"]


def test_a_timeout_answers_nosniff(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The 504 is sent by the middleware itself, past the handler that is still running."""
    monkeypatch.setenv("WD_RESTAPI_TIMEOUT", "0.2")
    monkeypatch.setattr(restapi, "get_values", lambda **_kwargs: time.sleep(0.8))

    response = client.get("/api/v1/values", params=_VALUES)

    assert response.status_code == 504
    assert _once(response) == ["nosniff"]


def test_a_refused_host_answers_nosniff(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """The 400 of a host that is not allowed is answered before the app is reached."""
    monkeypatch.setenv("WD_RESTAPI_ALLOWED_HOSTS", "only.example.org")

    response = client.get("/api/version")

    assert response.status_code == 400
    assert _once(response) == ["nosniff"]


def test_the_mcp_endpoint_answers_nosniff(client: TestClient) -> None:
    """The MCP endpoint is mounted on the app, and under the same middleware (its GET is a 405: it is stateless)."""
    if not restapi.mcp_enabled:
        pytest.skip("the [mcp] extra is not installed")

    response = client.get("/mcp/v1", headers={"Accept": "text/event-stream"})

    assert response.status_code == 405
    assert _once(response) == ["nosniff"]


def test_problem_headers_carry_nosniff_and_keep_one_given() -> None:
    """A problem has the header by itself, and a header it was raised with is neither replaced nor sent twice."""
    assert problem_headers(404, "r-1")[_NOSNIFF] == "nosniff"
    given = problem_headers(404, "r-1", {"x-content-type-options": "other"})
    assert {name.lower(): value for name, value in given.items()}["x-content-type-options"] == "other"
    assert [name for name in given if name.lower() == "x-content-type-options"] == ["x-content-type-options"]


def test_a_response_that_has_the_header_is_not_sent_it_twice() -> None:
    """A handler that sets the header itself keeps its value, and there is one header."""
    app = FastAPI()
    app.add_middleware(RequestContextMiddleware)

    @app.get("/own")
    def own() -> Any:  # noqa: ANN401
        from starlette.responses import PlainTextResponse  # noqa: PLC0415

        return PlainTextResponse("x", headers={"x-content-type-options": "own"})

    @app.get("/plain")
    def plain() -> dict[str, str]:
        return {"ok": "yes"}

    test_client = TestClient(app)

    assert _once(test_client.get("/own")) == ["own"]
    assert _once(test_client.get("/plain")) == ["nosniff"]


# --- Content-Security-Policy ------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path",
    ["/docs", "/redoc", "/openapi.json", "/health", "/robots.txt", "/api/version", "/api/providers", "/nowhere"],
)
def test_no_policy_where_it_would_break_the_page_or_say_nothing(client: TestClient, path: str) -> None:
    """Swagger UI and ReDoc load their scripts and styles from a CDN, and a JSON or text answer has nothing to guard."""
    assert _CSP not in client.get(path).headers


@pytest.mark.parametrize("fmt", ["json", "csv", "ndjson", "html"])
def test_no_policy_on_data_and_the_html_chart(client: TestClient, monkeypatch: pytest.MonkeyPatch, fmt: str) -> None:
    """The html chart is a script by design (Plotly's, in the page), so no policy is claimed for it."""
    _stub_result(monkeypatch, "/api/values")

    response = client.get("/api/values", params={**_VALUES, "format": fmt})

    assert response.status_code == 200
    assert _CSP not in response.headers


class _Elements(HTMLParser):
    """Collect the tags of a page, the attributes that run script or load something, and its inline `<style>`."""

    def __init__(self) -> None:
        super().__init__()
        self.tags: set[str] = set()
        self.loading: list[tuple[str, str, str]] = []
        self.handlers: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.add(tag)
        for name, value in attrs:
            if name.startswith("on"):
                self.handlers.append(name)
            if name in {"src", "srcset", "data", "poster", "action", "formaction", "ping"} or (
                tag == "link" and name == "href"
            ):
                self.loading.append((tag, name, value or ""))


def test_the_index_has_a_policy_and_needs_nothing_it_forbids(client: TestClient) -> None:
    """The policy allows the page's own `<style>` and nothing else; the page has no script, image, form or frame."""
    response = client.get("/")

    policy = response.headers[_CSP]
    assert policy == "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"
    page = _Elements()
    page.feed(response.text)
    # what the policy blocks, and so what the page must not use: scripts, requests, images, fonts, frames, forms
    assert not page.tags & {"script", "img", "link", "iframe", "frame", "object", "embed", "form", "base", "svg"}
    assert not page.tags & {"input", "button", "video", "audio", "source", "picture"}
    assert page.loading == []
    assert "http-equiv" not in response.text.lower()
    assert page.handlers == []
    assert "javascript:" not in response.text.lower()
    assert "@import" not in response.text
    assert "url(" not in response.text


def test_stripes_svg_has_the_policy_and_the_other_images_none(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Only the SVG is a document a browser runs script in: a policy on a PDF would break the browser's viewer."""

    class _Figure:
        def to_image(self, *_args: object, **_kwargs: object) -> bytes:
            return b"image"

    monkeypatch.setattr(restapi, "_plot_stripes", lambda _request: _Figure())
    policies = {}
    for fmt in ("png", "jpg", "svg", "pdf"):
        response = client.get("/api/stripes/image", params={"kind": "temperature", "station": "01048", "format": fmt})
        assert response.status_code == 200
        policies[fmt] = response.headers.get(_CSP)

    assert policies == {
        "png": None,
        "jpg": None,
        "svg": "default-src 'none'; style-src 'unsafe-inline'; img-src data:",
        "pdf": None,
    }


def test_a_chart_as_svg_has_the_policy(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every route that renders an image goes through the one answer: the SVG of it has the policy, the PNG none."""
    _stub_result(monkeypatch, "/api/values")
    monkeypatch.setattr("plotly.graph_objects.Figure.to_image", lambda *_args, **_kwargs: b"<svg/>")

    svg = client.get("/api/values", params={**_VALUES, "format": "svg"})
    png = client.get("/api/values", params={**_VALUES, "format": "png"})

    assert svg.status_code == png.status_code == 200
    assert svg.headers[_CSP] == "default-src 'none'; style-src 'unsafe-inline'; img-src data:"
    assert _CSP not in png.headers
    assert _once(svg) == _once(png) == ["nosniff"]


@pytest.mark.parametrize("chart", ["values", "stations"])
def test_a_real_chart_svg_needs_nothing_the_policy_forbids(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, chart: str
) -> None:
    """Render the SVG with Kaleido and read what it needs: no script, request or font, images only inlined.

    The line chart of values needs `style` (written as attributes) and nothing else; the map of the stations also
    embeds its canvas as a `data:` image, which `img-src data:` is there for. Skipped where no Chrome renders it.
    """
    if chart == "values":
        _stub_result(monkeypatch, "/api/values")
        response = client.get("/api/values", params={**_VALUES, "format": "svg", "width": 400, "height": 300})
    else:
        stations = _values_result_of_shape("long").stations
        monkeypatch.setattr(restapi, "get_stations", lambda **_kwargs: stations)
        response = client.get(
            "/api/stations", params={**_OBSERVATION, "all": "true", "format": "svg", "width": 400, "height": 300}
        )
    if response.status_code != 200:
        pytest.skip("Kaleido cannot render here (no Chrome)")

    text = response.text
    root = ET.fromstring(text)  # noqa: S314
    for element in root.iter():
        tag = element.tag.rsplit("}", 1)[-1]
        assert tag not in {"script", "foreignObject", "iframe", "link", "use"}, tag
        for name, value in element.attrib.items():
            local = name.rsplit("}", 1)[-1]
            assert not local.startswith("on"), name
            if local == "href":
                assert value.startswith(("data:", "#")), value
    assert "@import" not in text
    assert "@font-face" not in text
    # `url(#id)` is a reference inside the document: a clip path, no request
    assert all(reference.startswith("#") for reference in re.findall(r"url\(['\"]?([^)'\"]*)", text))
