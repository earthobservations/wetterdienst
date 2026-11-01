# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""A point that is NaN or infinite is refused by `interpolate` and `summarize` on every surface (GH-3689).

An elevation of NaN or infinity was accepted, written into the name and id of the point
(`interpolation(51.0000,13.0000,nanm)`) and into the z of its GeoJSON position, which is no position of RFC 7946.
Latitude and longitude were refused already, by their bounds; they are held here so that stays so.

Offline: the station list raises where it would be built, so a request that gets that far is a failure.
"""

from __future__ import annotations

import json
import math

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from wetterdienst import exceptions
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.ui import restapi
from wetterdienst.ui.cli import cli
from wetterdienst.ui.core import InterpolationRequest, SummaryRequest

_OBSERVATION = {"provider": "dwd", "network": "observation", "parameters": "daily/kl/temperature_air_mean_2m"}
_POINT = {"latitude": 50.0, "longitude": 10.0, "timestamp": "2020-01-01/2020-01-03"}
_KINDS = ["interpolate", "summarize"]
_NON_FINITE = [math.nan, math.inf, -math.inf]
#: how a query string and the command line write the number
_SPELLINGS = {"nan": math.nan, "inf": math.inf, "-inf": -math.inf}
_FIELDS = ["elevation", "latitude", "longitude"]


@pytest.fixture(autouse=True)
def _no_station_list(monkeypatch: pytest.MonkeyPatch) -> None:
    """Fail a request that reaches the station list: a refused point is refused before one is built."""

    def all_(*_: object) -> None:
        msg = "the station list was built"
        raise AssertionError(msg)

    monkeypatch.setattr(DwdObservationRequest, "all", all_)


@pytest.fixture
def client() -> TestClient:
    """Make a client that answers an unhandled exception as the server does, with its 500."""
    return TestClient(restapi.app, raise_server_exceptions=False)


def _request() -> DwdObservationRequest:
    return DwdObservationRequest(parameters="daily/kl/temperature_air_mean_2m", start="2020-01-01", end="2020-01-03")


# --- Python ------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize("elevation", _NON_FINITE, ids=_SPELLINGS)
def test_python_refuses_a_non_finite_elevation(kind: str, elevation: float) -> None:
    """The library raises a `RequestError` (a `ValueError`) that says what to do instead."""
    with pytest.raises(exceptions.RequestError, match=r"finite number of metres.*leave it out"):
        getattr(_request(), kind)((50.0, 10.0), elevation)


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize("elevation", _NON_FINITE, ids=_SPELLINGS)
def test_python_refuses_a_non_finite_elevation_given_with_a_station(kind: str, elevation: float) -> None:
    """The `_by_station_id` methods take the elevation asked about, and refuse it before the station is looked up."""
    with pytest.raises(exceptions.RequestError, match="finite number of metres"):
        getattr(_request(), f"{kind}_by_station_id")("00001", elevation)


# --- the request models: REST, CLI and MCP build them ------------------------------------------------------------


@pytest.mark.parametrize("model", [InterpolationRequest, SummaryRequest])
@pytest.mark.parametrize("value", _NON_FINITE, ids=_SPELLINGS)
@pytest.mark.parametrize("field", _FIELDS)
def test_the_request_model_refuses_a_non_finite_point(
    model: type[InterpolationRequest | SummaryRequest], field: str, value: float
) -> None:
    """The field is a finite number: pydantic accepts NaN and infinity for a float unless told not to."""
    with pytest.raises(ValueError, match=field):
        model(**{**_OBSERVATION, **_POINT, field: value})


# --- REST --------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize("field", _FIELDS)
@pytest.mark.parametrize("spelling", _SPELLINGS)
def test_rest_answers_a_non_finite_point_with_the_422_of_a_malformed_parameter(
    client: TestClient, kind: str, field: str, spelling: str
) -> None:
    """A 422 of the usual problem shape that names the parameter, and not a 500."""
    response = client.get(f"/api/v1/{kind}", params={**_OBSERVATION, **_POINT, field: spelling})

    assert response.status_code == 422, response.text
    body = response.json()
    assert body["type"] == "urn:wetterdienst:problem:invalid-parameters"
    assert body["errors"][0]["loc"] == ["query", field]


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize("spelling", _SPELLINGS)
def test_rest_refuses_a_non_finite_elevation_given_with_a_station(client: TestClient, kind: str, spelling: str) -> None:
    """The elevation asked about at a station's point is held to the same rule."""
    response = client.get(
        f"/api/v1/{kind}",
        params={**_OBSERVATION, "station": "00001", "timestamp": _POINT["timestamp"], "elevation": spelling},
    )

    assert response.status_code == 422, response.text
    assert response.json()["errors"][0]["loc"] == ["query", "elevation"]


# --- CLI ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize("field", _FIELDS)
@pytest.mark.parametrize("spelling", _SPELLINGS)
def test_cli_refuses_a_non_finite_point_as_a_usage_error(kind: str, field: str, spelling: str) -> None:
    """Exit 2, the option named, no traceback."""
    point = {"latitude": "50.0", "longitude": "10.0", field: spelling}
    arguments = [f"--{key}={value}" for key, value in {**_OBSERVATION, **point}.items()]

    result = CliRunner().invoke(cli, [kind, *arguments, "--timestamp=2020-01-01/2020-01-03"])

    assert result.exit_code == 2, result.output
    assert f"--{field}" in result.output


# --- MCP ---------------------------------------------------------------------------------------------------------


@pytest.mark.parametrize("kind", _KINDS)
@pytest.mark.parametrize("field", _FIELDS)
@pytest.mark.parametrize("literal", ["NaN", "Infinity", "-Infinity"])
def test_mcp_refuses_a_non_finite_point_written_on_the_wire(kind: str, field: str, literal: str) -> None:
    """A client that writes the number as the JSON literal gets the refusal of the route, with the field named.

    The call is posted as JSON-RPC to the server's HTTP app. The client library of the SDK writes NaN and infinity as
    `null` before it sends them, which the server cannot tell from an argument that was left out.
    """
    pytest.importorskip("fastmcp")
    from starlette.testclient import TestClient as StarletteClient  # noqa: PLC0415

    from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

    arguments = json.dumps({**_OBSERVATION, **_POINT, field: 0.0})
    arguments = arguments.replace(f'"{field}": 0.0', f'"{field}": {literal}')
    call = '{"name": "' + kind + '", "arguments": ' + arguments + "}"
    body = '{"jsonrpc": "2.0", "id": 1, "method": "tools/call", "params": ' + call + "}"
    assert f'"{field}": {literal}' in body
    app = build_mcp_server(restapi.app).http_app(stateless_http=True, json_response=True)

    with StarletteClient(app) as client:
        response = client.post(
            "/mcp", content=body, headers={"content-type": "application/json", "accept": "application/json"}
        )

    result = response.json()["result"]
    assert result["isError"] is True
    assert "422" in result["content"][0]["text"]
    assert f"{field}: Input should be" in result["content"][0]["text"]
