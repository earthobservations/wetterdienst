# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""The REST API's contract (GH-2561): the version it is served under, and the one answer to a failure.

Offline: a reader is replaced by one raising a real exception of the library, and the request goes
through the app's routes and handlers.
"""

from __future__ import annotations

import asyncio
from http import HTTPStatus
from typing import TYPE_CHECKING, Any

import pytest
from fastapi.testclient import TestClient

from wetterdienst import exceptions
from wetterdienst.ui import restapi

if TYPE_CHECKING:
    from collections.abc import Callable

#: both ways in: the current version and its alias
PREFIXES = ["/api/v1", "/api"]

_VALUES = {
    "provider": "dwd",
    "network": "observation",
    "parameters": "daily/kl/temperature_air_mean_2m",
    "stations": "01048",
}


_STATIONS = {"provider": "dwd", "network": "observation", "parameters": "daily/kl", "all": "true"}


@pytest.fixture
def client() -> TestClient:
    """Make a client that answers an unhandled exception as the server does, with its 500."""
    return TestClient(restapi.app, raise_server_exceptions=False)


def _raising(error: BaseException) -> Callable[..., None]:
    def raises(**_kwargs: object) -> None:
        raise error

    return raises


def _download_error(cause: BaseException | None = None) -> exceptions.DownloadError:
    error = exceptions.DownloadError("https://opendata.example.org/file.zip", "reason")
    error.__cause__ = cause
    return error


def _timeout() -> exceptions.DownloadError:
    return _download_error(TimeoutError())


# every status of the contract, by a real exception of the library: the reader raising it, the status
# the route answers, and the title of RFC 9457's `title`
STATUS_TABLE = [
    pytest.param(exceptions.RequestError("the request cannot be served"), 400, id="400-request"),
    pytest.param(exceptions.InvalidParameterError("unknown parameter"), 400, id="400-invalid-parameter"),
    pytest.param(OverflowError("date value out of range"), 400, id="400-overflow"),
    pytest.param(exceptions.StationNotFoundError("no such station"), 404, id="404-station"),
    pytest.param(exceptions.ProviderNotFoundError("no such provider"), 404, id="404-provider"),
    pytest.param(exceptions.CredentialMissingError("set WD_AUTH__X"), 501, id="501-credential-missing"),
    pytest.param(exceptions.CredentialRejectedError("WD_AUTH__X was rejected"), 501, id="501-credential-rejected"),
    pytest.param(exceptions.MissingDependencyError("pip install x"), 501, id="501-dependency"),
    pytest.param(exceptions.ConfigurationError("not set up"), 501, id="501-configuration"),
    pytest.param(_download_error(), 502, id="502-download"),
    pytest.param(exceptions.MetaFileFormatError("not the layout"), 502, id="502-format"),
    pytest.param(exceptions.NoInternetError("No internet: could not reach https://x"), 503, id="503-no-internet"),
    pytest.param(_timeout(), 504, id="504-timeout"),
    pytest.param(RuntimeError("/srv/secret/path"), 500, id="500-bug"),
    pytest.param(exceptions.WetterdienstError("unplaced"), 500, id="500-unplaced"),
]


def _is_a_problem(response: Any, status: int) -> dict[str, Any]:  # noqa: ANN401
    """Assert the body RFC 9457 describes and return it."""
    assert response.status_code == status, response.text
    assert response.headers["content-type"] == "application/problem+json"
    body = response.json()
    assert {"type", "title", "status", "detail"} <= set(body)
    assert body["type"] == "about:blank"
    assert body["status"] == status
    assert body["title"] == HTTPStatus(status).phrase
    assert isinstance(body["detail"], str)
    return body


# --- the version -------------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", PREFIXES)
def test_the_version_reports_the_api_version(client: TestClient, prefix: str) -> None:
    """`/api/version` and `/api/v1/version` both report `api_version`, next to the package's version."""
    body = client.get(f"{prefix}/version").json()

    assert body["api_version"] == "1"
    assert body["version"]
    assert isinstance(body["mcp_enabled"], bool)


def _untimed(body: Any) -> Any:  # noqa: ANN401
    """Give an answer without the time its `metadata` says it was made at, which no two requests share."""
    if isinstance(body, dict) and isinstance(body.get("metadata"), dict):
        return {**body, "metadata": {**body["metadata"], "retrieved_at": ""}}
    return body


def test_every_documented_route_is_served_under_the_alias_too(client: TestClient) -> None:
    """Each path OpenAPI lists under `/api/v1` is answered under `/api` alike: one definition of a version.

    Asked without its parameters, a route answers a 422 or, where it needs none, its answer; the
    alias must not be a 404 or a 405, and gives the very body of the versioned route.
    """
    paths = [path for path in client.get("/openapi.json").json()["paths"] if path.startswith("/api/v1/")]

    assert {"/api/v1/version", "/api/v1/values", "/api/v1/stations", "/api/v1/alerts", "/api/v1/stripes/image"} <= set(
        paths
    )
    for path in paths:
        if path.endswith("/alerts"):
            # needs no parameter, and so goes to the feed
            continue
        versioned, alias = client.get(path), client.get(path.replace("/api/v1/", "/api/", 1))
        assert alias.status_code == versioned.status_code, path
        assert alias.status_code not in (404, 405), path
        assert _untimed(alias.json()) == _untimed(versioned.json()), path


@pytest.mark.parametrize("path", ["/version", "/glossary?parameter=temperature_air_mean_2m", "/coverage"])
def test_both_prefixes_answer_alike(client: TestClient, path: str) -> None:
    """The alias is not another API: a request gives the same answer under both."""
    versioned, alias = client.get(f"/api/v1{path}"), client.get(f"/api{path}")

    assert versioned.status_code == alias.status_code == 200
    assert versioned.json() == alias.json()


def test_the_errors_are_the_same_under_both_prefixes(client: TestClient) -> None:
    """A failure is the same problem whichever way the request came in."""
    answers = [client.get(f"{prefix}/glossary", params={"limit": 0}) for prefix in PREFIXES]

    assert [answer.status_code for answer in answers] == [422, 422]
    assert answers[0].json() == answers[1].json()


def test_the_openapi_document_describes_the_versioned_routes_alone(client: TestClient) -> None:
    """OpenAPI documents `/api/v1`; the alias is served and not listed, so a document has one path to each operation."""
    paths = client.get("/openapi.json").json()["paths"]
    api_paths = {path for path in paths if path.startswith("/api")}

    assert api_paths
    assert all(path.startswith("/api/v1/") for path in api_paths), api_paths
    assert "/api/v1/values" in api_paths
    assert "/api/values" not in paths


def test_the_operation_ids_do_not_carry_the_version(client: TestClient) -> None:
    """A client generated from the document, and an MCP tool, find an operation by an id without the version."""
    operations = {
        operation["operationId"]
        for path, item in client.get("/openapi.json").json()["paths"].items()
        if path.startswith("/api/")
        for operation in item.values()
    }

    assert "values_api_values_get" in operations
    assert "stripes_image_api_stripes_image_get" in operations
    assert not [operation for operation in operations if "v1" in operation]


def test_the_mcp_tools_are_the_endpoints_under_their_names() -> None:
    """The versioned paths give the same tools, one each, under the names agents call (GH-2561)."""
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    async def names() -> list[str]:
        async with Client(build_mcp_server(restapi.app)) as mcp_client:
            return [tool.name for tool in await mcp_client.list_tools()]

    tools = asyncio.run(names())

    assert sorted(tools) == sorted(
        [
            "alerts",
            "auth",
            "coverage",
            "glossary",
            "history",
            "interpolate",
            "issues",
            "providers",
            "stations",
            "stripes_image",
            "stripes_stations",
            "stripes_values",
            "summarize",
            "values",
        ]
    )


def test_an_unknown_version_is_a_404_problem(client: TestClient) -> None:
    """A version that does not exist is not served as the current one."""
    _is_a_problem(client.get("/api/v2/version"), 404)


# --- the errors --------------------------------------------------------------------------------


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize(("error", "status"), STATUS_TABLE)
def test_a_failure_is_answered_with_the_status_of_its_place_in_the_hierarchy(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, prefix: str, error: BaseException, status: int
) -> None:
    """Every status of the contract, by a real exception raised where the values are read, under both prefixes."""
    monkeypatch.setattr("wetterdienst.ui.restapi.get_values", _raising(error))

    body = _is_a_problem(client.get(f"{prefix}/values", params=_VALUES), status)

    if status in (400, 404):
        # the caller's to act on, so the sentence is the exception's
        assert body["detail"] == str(error)
    else:
        # the server's, the provider's or ours: the text is the log's, which names a setting, a path or a URL
        for secret in ("WD_AUTH", "pip install", "/srv/secret", "opendata.example.org", "No internet", "reason"):
            assert secret not in _text_of(body), secret


def _text_of(body: dict[str, Any]) -> str:
    """Give the text of a problem a caller reads."""
    return " ".join(str(value) for value in body.values())


def test_the_statuses_of_the_table_are_all_covered() -> None:
    """The table above is the contract's: 400, 404, 501, 502, 503, 504 and 500 each by an exception, and 422 below."""
    assert {param.values[1] for param in STATUS_TABLE} == {400, 404, 500, 501, 502, 503, 504}


def test_a_request_of_the_wrong_shape_is_a_422_problem_with_its_errors(client: TestClient) -> None:
    """A parameter that does not validate is a 422 problem: its lines in `detail`, the entries under `errors`."""
    body = _is_a_problem(client.get("/api/v1/glossary", params={"limit": 0}), 422)

    assert body["detail"] == "limit: Input should be greater than or equal to 1"
    assert [error["loc"] for error in body["errors"]] == [["query", "limit"]]


def test_a_path_that_does_not_exist_is_a_404_problem(client: TestClient) -> None:
    """Starlette's own 404 and 405 are problems too."""
    _is_a_problem(client.get("/api/v1/nope"), 404)
    _is_a_problem(client.post("/api/v1/version"), 405)


def test_an_unknown_provider_is_a_404_problem(client: TestClient) -> None:
    """A provider that does not exist is a 404 that points at the listing."""
    body = _is_a_problem(
        client.get(
            "/api/v1/stations", params={"provider": "nope", "network": "nope", "parameters": "x", "all": "true"}
        ),
        404,
    )

    assert "coverage" in body["detail"]


def test_a_problem_has_the_members_the_schema_declares(client: TestClient) -> None:
    """The members of every problem are the ones the OpenAPI `Problem` lists."""
    schema = client.get("/openapi.json").json()["components"]["schemas"]["Problem"]
    body = _is_a_problem(client.get("/api/v1/glossary", params={"limit": 0}), 422)

    assert set(body) <= set(schema["properties"])
    assert set(schema["required"]) <= set(body)


def test_an_unhandled_exception_is_the_fixed_500_over_http_and_through_mcp(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An exception no endpoint handled is a 500 naming its type; a tool error says the same, not its text (GH-2984)."""
    pytest.importorskip("fastmcp")
    from fastmcp import Client  # noqa: PLC0415
    from fastmcp.exceptions import ToolError  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    monkeypatch.setattr("wetterdienst.ui.restapi.get_glossary", _raising(RuntimeError("/srv/secret/path")))
    sentence = "Internal server error (RuntimeError). The cause is in the server log."

    body = _is_a_problem(client.get("/api/v1/glossary"), 500)
    assert body["detail"] == sentence

    async def call() -> None:
        async with Client(build_mcp_server(restapi.app)) as mcp_client:
            await mcp_client.call_tool("glossary", {})

    with pytest.raises(ToolError) as error:
        asyncio.run(call())
    assert "HTTP error 500" in str(error.value)
    assert sentence in str(error.value)
    assert "/srv/secret/path" not in str(error.value)


# --- the endpoints that decided by themselves --------------------------------------------------


class _AlertsRaising:
    """Stand in for the alerts request, raising `error` where the snapshot is collected."""

    def __init__(self, error: BaseException) -> None:
        self.error = error

    def __call__(self, **_kwargs: object) -> _AlertsRaising:
        return self

    def query(self) -> None:
        raise self.error


@pytest.mark.parametrize("prefix", PREFIXES)
@pytest.mark.parametrize(
    ("error", "status"),
    [
        pytest.param(exceptions.InvalidTimeIntervalError("before the window"), 400, id="interval"),
        pytest.param(exceptions.NotFoundError("no such thing"), 404, id="not-found"),
        pytest.param(exceptions.ConfigurationError("not set up"), 501, id="configuration"),
        pytest.param(_download_error(), 502, id="download"),
        pytest.param(_timeout(), 504, id="timeout"),
        pytest.param(exceptions.NoInternetError("No internet"), 503, id="no-internet"),
        # a `ValueError` from the provider is not the caller's mistake unless it says it is (GH-2985)
        pytest.param(ValueError("a defect of the parser"), 500, id="plain-value-error"),
    ],
)
def test_alerts_decides_by_the_hierarchy_too(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, prefix: str, error: BaseException, status: int
) -> None:
    """`alerts` asks the hierarchy like every endpoint, not a list of the exceptions it knew of (GH-2985)."""
    monkeypatch.setattr("wetterdienst.provider.dwd.alerts.DwdWeatherAlertRequest", _AlertsRaising(error))

    _is_a_problem(client.get(f"{prefix}/alerts"), status)


def test_alerts_a_date_that_does_not_parse_is_still_the_callers(client: TestClient) -> None:
    """The one refusal `alerts` made itself stays a 400 with the date in it, now by the hierarchy's `RequestError`."""
    body = _is_a_problem(client.get("/api/v1/alerts", params={"timestamp": "yesterday"}), 400)

    assert "yesterday" in body["detail"]


def test_stations_does_not_take_with_stations(client: TestClient) -> None:
    """A listing of stations is the stations, so `with_stations` is not offered nor read (GH-3034)."""
    parameters = {
        parameter["name"]
        for parameter in client.get("/openapi.json").json()["paths"]["/api/v1/stations"]["get"]["parameters"]
    }
    assert "with_stations" not in parameters
    assert "with_metadata" in parameters

    body = _is_a_problem(
        client.get("/api/v1/stations", params={**_STATIONS, "with_stations": "true"}),
        422,
    )
    assert "with_stations" in body["detail"]
