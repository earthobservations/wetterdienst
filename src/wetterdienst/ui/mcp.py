# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""MCP server for wetterdienst, generated from the REST API.

The tools mirror the REST endpoints one-to-one (via FastMCP's ``from_fastapi``), so the MCP
transport stays in lockstep with the HTTP API. To make that surface usable by small/cheap LLM
agents -- which otherwise guess parameters and thrash -- this module adds:

- a core ``instructions`` block describing the station -> values workflow, the DWD defaults, the
  parameter syntax and how to read results (so agents don't re-request the same data in different
  formats),
- clean tool names (``values`` instead of ``values_api_values_get``), and
- exclusion of the non-data endpoints (index, robots, health, version, auth) so the tool list stays
  focused.

The endpoint docstrings become the tool descriptions and the request-model field descriptions
become the parameter descriptions, so those live with the endpoints in ``restapi.py`` / ``core.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fastapi import FastAPI
    from fastmcp import FastMCP

# Internal ASGI base URL for the in-process httpx client that backs the tools.
_ASGI_BASE_URL = "http://wetterdienst.local"

INSTRUCTIONS = """\
Wetterdienst provides weather & climate data from national weather services (Germany's DWD by \
default, plus NOAA, ECCC, Météo-France and more). These tools mirror its REST API.

## Typical workflow: weather for a place
1. `stations` — find the station id:
     stations(provider="dwd", network="observation", parameters="daily/kl", name="Hamburg Fuhlsbüttel")
   Take the `station_id` (e.g. "01975") from the result.
2. `values` — get the measurements for that station:
     values(provider="dwd", network="observation",
            parameters="daily/climate_summary/temperature_air_mean_2m",
            station="01975", periods="recent")

## Conventions
- provider/network: use "dwd"/"observation" for German ground observations (the common case). Call \
`coverage` with no arguments to list every provider/network.
- parameters: "resolution/dataset" (e.g. "daily/kl") for a whole dataset, or \
"resolution/dataset/parameter" (e.g. "daily/climate_summary/temperature_air_mean_2m") for a single \
measurement. Prefer the single-measurement form to keep responses small. Parameter names are \
snake_case; `coverage(provider="dwd", network="observation", datasets="climate_summary")` lists them.
- periods: "recent" (roughly the last 1.5 years) is the usual choice; "historical" for older data.
- Handy DWD datasets: daily/kl (= climate_summary: temperature, precipitation, wind, sunshine), \
hourly/air_temperature, hourly/precipitation.

## Reading results
- `values` returns JSON with a `values` array of {station_id, parameter, date, value}, sorted by \
date. The MOST RECENT value for a parameter is the LAST item with that parameter name.
- Responses are compact by default (just the `values`). Keep them small (and answer in fewer calls) \
by querying a single "resolution/dataset/parameter" and -- if you only need the latest reading -- a \
`date` (e.g. date="2026-07-25"; a station's most recent day is its `end_date` from `stations`).
- The default JSON is already machine-readable — do NOT re-request the same data in a different \
format (csv/wide/pretty) or with unrelated flags; that just wastes calls.

## Example — recent mean air temperature at Hamburg-Fuhlsbüttel
  stations(provider="dwd", network="observation", parameters="daily/kl", name="Hamburg Fuhlsbüttel")
    -> station_id "01975"
  values(provider="dwd", network="observation",
         parameters="daily/climate_summary/temperature_air_mean_2m", station="01975", periods="recent")
    -> last item ≈ {"date": "2026-07-25", "value": 19.2}  (i.e. 19.2 °C)
"""

# Non-data endpoints that only add noise to an agent's tool list.
_EXCLUDE_PATTERNS = (r"^/$", r"^/robots\.txt$", r"^/health$", r"^/api/version$", r"^/api/auth$")

# Clean, agent-friendly names for the auto-generated tools (auto name -> friendly name).
_TOOL_NAMES = {
    "coverage_api_coverage_get": "coverage",
    "stations_api_stations_get": "stations",
    "values_api_values_get": "values",
    "interpolate_api_interpolate_get": "interpolate",
    "summarize_api_summarize_get": "summarize",
    "history_api_history_get": "history",
    "issues_api_issues_get": "issues",
    "alerts_api_alerts_get": "alerts",
    "stripes_stations_api_stripes_stations_get": "stripes_stations",
    "stripes_values_api_stripes_values_get": "stripes_values",
    "stripes_image_api_stripes_image_get": "stripes_image",
}


def build_mcp_server(rest_app: FastAPI) -> FastMCP:
    """Build the wetterdienst MCP server from the REST API app.

    Wraps every data endpoint as an MCP tool and attaches the workflow ``instructions``, clean tool
    names and the noise-endpoint exclusions described in the module docstring.

    This drives the ``OpenAPIProvider`` directly (rather than ``FastMCP.from_fastapi``) so it can pass
    ``validate_output=False``: the REST endpoints return a raw JSON string but declare rich
    ``response_model`` unions, which FastMCP turns into inaccurate output schemas (numeric measurement
    values typed as strings). With the default validation that makes ``values`` reject perfectly good
    results with "9.0 is not of type 'string'"; ``validate_output=False`` replaces those schemas with
    a permissive object schema so the tools work.
    """
    import httpx  # noqa: PLC0415
    from fastmcp import FastMCP  # noqa: PLC0415
    from fastmcp.server.providers.openapi import MCPType, OpenAPIProvider, RouteMap  # noqa: PLC0415

    route_maps = [RouteMap(pattern=pattern, mcp_type=MCPType.EXCLUDE) for pattern in _EXCLUDE_PATTERNS]
    client = httpx.AsyncClient(transport=httpx.ASGITransport(app=rest_app), base_url=_ASGI_BASE_URL)
    provider = OpenAPIProvider(
        openapi_spec=rest_app.openapi(),
        client=client,
        route_maps=route_maps,
        mcp_names=_TOOL_NAMES,
        validate_output=False,
    )
    return FastMCP(name="Wetterdienst", instructions=INSTRUCTIONS, providers=[provider])
