# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""MCP server for wetterdienst, generated from the REST API.

The tools are generated from the REST API's OpenAPI schema (via FastMCP's ``OpenAPIProvider``), so
the MCP transport stays in lockstep with the HTTP API. To make that surface usable by small/cheap
LLM agents -- which otherwise guess parameters and thrash -- this module adds:

- a core ``instructions`` block describing the station -> values workflow, the DWD defaults, the
  parameter syntax and how to read results (so agents don't re-request the same data in different
  formats),
- clean tool names (``values`` instead of ``values_api_values_get``),
- a ``title`` and the annotations (read-only, not destructive, idempotent, open world or not) on every
  tool, which the Claude connectors directory requires and clients use to skip a confirmation (GH-3482),
- the refusal of an argument a tool does not take, which FastMCP would drop,
- an error that reads as prose: the REST API answers a tool's request with the text of its problem,
  not the object, so that the tool error does not carry a Python repr (``restapi._problem_response``), and
- exclusion of the non-data endpoints (index, robots, health, version, settings) so the tool
  list stays focused. The settings a data tool used come back in its own answer with
  ``with_metadata``.

The endpoint docstrings become the tool descriptions and the request-model field descriptions
become the parameter descriptions, so those live with the endpoints in ``restapi.py`` / ``core.py``.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from wetterdienst import __version__

if TYPE_CHECKING:
    from collections.abc import MutableMapping
    from typing import Any

    from fastapi import FastAPI
    from fastmcp import FastMCP
    from fastmcp.server.middleware import CallNext, Middleware, MiddlewareContext
    from fastmcp.server.providers.openapi import (
        OpenAPIProvider,
        OpenAPIResource,
        OpenAPIResourceTemplate,
        OpenAPITool,
    )
    from fastmcp.tools import ToolResult
    from fastmcp.utilities.openapi import HTTPRoute
    from starlette.types import ASGIApp, Receive, Scope, Send

# Internal ASGI base URL for the in-process httpx2 client that backs the tools.
_ASGI_BASE_URL = "http://wetterdienst.local"

# The ASGI scope key that marks a tool's in-process request to the REST app.
_TOOL_REQUEST_SCOPE_KEY = "wetterdienst.mcp_tool_request"


def is_tool_request(scope: MutableMapping[str, Any]) -> bool:
    """Tell whether an ASGI request is an MCP tool's in-process request to the REST app.

    The REST app's fastapi telemetry gives these no server span, no `http.server.*` metrics and no
    exception log of their own (GH-2432): their spans would start a trace of their own, cut off from
    the tool call's, and the metrics would count each tool call twice. A tool called over `/mcp/v1`
    (or its alias `/mcp`) runs in that request's context, so fastapi records the tool request's operation spans, its
    telemetry data and a validation failure of its parameters as the MCP request's, the spans
    beneath the tool call's span. The middleware of `opentelemetry-instrumentation-fastapi`, where
    it runs, does not read fastapi's `exclude` and still records them.

    A scope key, not the Host header or `server`, tells them apart, because a client sets its own
    Host header, some ASGI servers build `server` from it, and no client can set a scope key.
    """
    return scope.get(_TOOL_REQUEST_SCOPE_KEY) is True


def _mark_tool_requests(app: ASGIApp) -> ASGIApp:
    """Wrap the REST app so each request the tools send it carries the scope key `is_tool_request` checks."""

    async def marked(scope: Scope, receive: Receive, send: Send) -> None:
        scope[_TOOL_REQUEST_SCOPE_KEY] = True
        await app(scope, receive, send)

    return marked


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
            stations="01975", periods="recent")

The same two steps serve a network of any `kind` (`observation`, `forecast`, ...; see `coverage`). Without \
a name, give `stations` a point: `latitude`, `longitude` and `rank` (the N nearest) or `distance` (km):
     stations(provider=<provider>, network=<network>, parameters=<parameters>, latitude=<lat>, longitude=<lon>, rank=3)
A provider's `country` is its operator's, NOT the extent of its data: never conclude from it that a network \
cannot serve a place; look at its `kind`, its `extent` and at what `stations` returns near the place.

## Choosing a tool
For "what was/is the weather at <place>" ALWAYS use `stations` then `values` -- that is the only \
path to measured weather, and the correct default. This holds even when the request names a \
specific past date (e.g. "how was the weather in Kiel on 26.12.2025"): find Kiel's nearest station \
with `stations`, then read its `values` for that date. Do NOT reach for `interpolate` or \
`summarize` here.

`interpolate` and `summarize` estimate values for a point *between* stations (spatial interpolation \
and nearest-station-with-data respectively); both introduce inaccuracy and are opt-in. Use them \
ONLY when the user explicitly asks for an interpolated / between-stations estimate, or when \
`stations` -> `values` genuinely returns no station with data near the location. They are not a \
plain-language "summary". `history` is different again: it returns a station's *metadata* history \
(name/location/sensor changes), not weather.

`glossary` answers what a parameter *means* and which unit its values come back in -- use it when \
the user asks what something is, or what unit a number is in. It is not a way to find data: it \
knows nothing about providers or stations, so `coverage` remains the tool for "which parameters \
does this provider have". `providers` answers what a provider *is* -- the country of its operator (not \
where its stations are), the licence its data is published under and the credit line to give, and what \
its networks offer, with the `extent` of each (where its stations are) -- and is the tool for "may I reuse this \
data" and "which providers' networks reach a place".

`auth` checks the credentials this server holds for one provider and network that needs them \
(e.g. aemet/observation): `valid` is true when the provider accepted them, false when it rejected \
them or none are configured, and null when that could not be told (treat it as unknown, not as \
rejected). `coverage` does not check them and has no `valid`: it says whether they are `configured`.

## Conventions
- provider/network: use "dwd"/"observation" for German ground observations (the common case). Call \
`coverage` with no arguments to list every provider/network.
- parameters: "resolution/dataset" (e.g. "daily/kl") for a whole dataset, or \
"resolution/dataset/parameter" (e.g. "daily/climate_summary/temperature_air_mean_2m") for a single \
measurement. Prefer the single-measurement form to keep responses small. Parameter names are \
snake_case; `coverage(provider="dwd", network="observation", datasets="climate_summary")` lists them. \
Its answer is keyed by resolution, then `datasets`, then each dataset's `parameters`, and every one \
of those three levels carries a `description` saying what the source means by it. `unit` is what `values` \
return; `unit_source` only if it differs.
- elevation: for `interpolate` and `summarize` only, the elevation of the point in metres above sea \
level. Air temperature falls about 0.65 K per 100 m, so a point in a valley and one on the ridge \
above it get different answers from the same stations; without it the readings are used as they \
come. Naming a station instead of coordinates answers at that station's own altitude.
- periods: leave it out unless the provider splits its record into releases. dwd/observation does \
-- "recent" is roughly the last 1.5 years, "historical" reaches further back -- as do dwd/derived and \
dwd/phenology. Most other providers publish everything under a single period, and asking for one \
their datasets do not have is an error, not a narrower answer.
- lists: an argument that takes several (`parameters`, `stations`, `periods`) is plural and takes them \
comma-separated, e.g. stations="01975,04411". `interpolate` and `summarize` take one reference `station`.
- Handy DWD datasets: daily/kl (= climate_summary: temperature, precipitation, wind, sunshine), \
hourly/air_temperature, hourly/precipitation.

## Reading results
- By default (shape="long" unless the server is configured otherwise, format="json") `values` \
returns JSON with a `values` array of \
{station_id, resolution, dataset, parameter, timestamp, value, quality_flags}, grouped by station, then by \
resolution, dataset and parameter, in timestamp order within each group. `quality_flags` is null or the \
source's own flags as a string: the plain quality flag first, then `kind:code` tokens (`G,measurement:T,source:7`), \
and a last `raw:<text>` token holds the source's text of a value it mapped from a missing-value code. \
A parameter's LATEST timestamp is the LAST item of its group, not the last item of the array.
- Responses are compact by default (just the `values`). Keep them small (and answer in fewer calls) \
by querying a single "resolution/dataset/parameter" and -- if you only need one day -- a \
`timestamp` (e.g. timestamp="2026-07-25"; a station's most recent day is its `end_timestamp` from \
`stations` where it has one; a null one means the provider gives no end, not that the data reaches \
today). A date covers everything it names, so a day of hourly data is that day's 24 readings, \
"2026-07" is the month and "2026" the year; name the hour (timestamp="2026-07-25T12") for a single \
reading.
- An empty `values` or `stations` is an answer, not an error: a day with no reading yet, a name nothing \
matches, or ids in the `stations` argument the network has no station for (they are left out of the list and the \
rest is answered). Do not retry the same request; widen the `timestamp`, check the spelling, or look for another \
station. `stations` takes the same `timestamp` as `values` and lists only the stations that have a record \
in it, so the nearest ones are not stations that closed long ago. A `name` gives `stations` its best five \
matches and `values` the one best match; `rank` asks for another number.
- The default JSON is already machine-readable — do NOT re-request the same data in a different \
format (csv/wide/pretty) or with unrelated flags; that just wastes calls.

## Example — recent mean air temperature at Hamburg-Fuhlsbüttel
  stations(provider="dwd", network="observation", parameters="daily/kl", name="Hamburg Fuhlsbüttel")
    -> station_id "01975"
  values(provider="dwd", network="observation",
         parameters="daily/climate_summary/temperature_air_mean_2m", stations="01975", periods="recent")
    -> last item ≈ {"timestamp": "2026-07-25T00:00:00.000000+00:00", "value": 19.2}  (i.e. 19.2 °C)
"""

# Non-data endpoints that only add noise to an agent's tool list.
_EXCLUDE_PATTERNS = (
    r"^/$",
    r"^/robots\.txt$",
    r"^/health$",
    r"^/api(/v1)?/version$",
    r"^/api(/v1)?/settings$",
)

# Clean, agent-friendly names for the auto-generated tools (auto name -> friendly name).
_TOOL_NAMES = {
    "auth_api_auth_get": "auth",
    "coverage_api_coverage_get": "coverage",
    "glossary_api_glossary_get": "glossary",
    "providers_api_providers_get": "providers",
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

# The title of every tool, and whether it reaches a service outside wetterdienst (the ``openWorldHint``).
# Every tool is a GET that only reads, so the other hints are the same for all. A tool without an entry here
# is a tool the server must not ship: `_annotate_tool` raises for it, and FastMCP, which logs and swallows the
# exception, would leave the tool without annotations, which `tests/ui/test_mcp_annotations.py` catches.
#
# False: the tool answers from wetterdienst's own metadata (`coverage`, `glossary`, `providers`) and never
# makes a request to a provider. True: it fetches from a provider's service -- a station list, a file
# listing or the values -- or probes it (`auth`, the one call that does so to check the credentials).
_TOOL_TITLES: dict[str, tuple[str, bool]] = {
    "auth": ("Check provider credentials", True),
    "coverage": ("List available data", False),
    "glossary": ("Look up a parameter", False),
    "providers": ("Describe data providers", False),
    "stations": ("Find stations", True),
    "values": ("Get station values", True),
    "interpolate": ("Interpolate values for a point", True),
    "summarize": ("Get nearest-station values for a point", True),
    "history": ("Get a station's metadata history", True),
    "issues": ("List forecast issues", True),
    "alerts": ("Get weather alerts", True),
    "stripes_stations": ("Find climate stripes stations", True),
    "stripes_values": ("Get climate stripes values", True),
    "stripes_image": ("Render climate stripes", True),
}


def _annotate_tool(
    route: HTTPRoute,  # noqa: ARG001
    component: OpenAPITool | OpenAPIResource | OpenAPIResourceTemplate,
) -> None:
    """Give a tool its title and annotations, as the Claude connectors directory requires of every tool.

    FastMCP calls this for each route it turns into a component, with the tool's friendly name already
    set, and logs and swallows what it raises: a name without a `_TOOL_TITLES` entry leaves its tool
    bare, which the tests refuse.
    """
    from fastmcp.server.providers.openapi import OpenAPITool  # noqa: PLC0415
    from mcp_types import ToolAnnotations  # noqa: PLC0415

    if not isinstance(component, OpenAPITool):
        msg = f"{component.name} is a {type(component).__name__}, and every route is meant to be a tool"
        raise TypeError(msg)
    if component.name not in _TOOL_TITLES:
        msg = f"the MCP tool {component.name} has no entry in _TOOL_TITLES"
        raise KeyError(msg)
    title, open_world = _TOOL_TITLES[component.name]
    component.title = title
    # keyword arguments, which the type checker holds to the fields; they go out on the wire as
    # `readOnlyHint` and so on
    component.annotations = ToolAnnotations(
        title=title,
        read_only_hint=True,
        destructive_hint=False,
        idempotent_hint=True,
        open_world_hint=open_world,
    )


def _refuse_unknown_arguments(provider: OpenAPIProvider) -> Middleware:
    """Build the middleware that refuses a tool argument the tool does not take.

    A tool's arguments are its REST endpoint's query parameters, and FastMCP sends the endpoint
    only the ones the tool's schema names, dropping the rest: an argument the tool does not take
    never reached the endpoint's refusal, and the call was answered as if it had not been given
    (GH-2479). An argument by a name since renamed is refused naming the new one, where the tool
    takes it, as its endpoint does (GH-2438), and one that was removed with what to do instead (GH-3336).

    The input schemas are left without `additionalProperties: false`: a client checking a call
    against that would refuse a renamed argument itself, without the name it was renamed to.
    """
    from fastmcp.exceptions import ToolError  # noqa: PLC0415
    from fastmcp.server.middleware import Middleware  # noqa: PLC0415

    from wetterdienst.ui.core import (  # noqa: PLC0415
        REMOVED_REQUEST_PARAMETERS,
        RENAMED_REQUEST_PARAMETERS,
        join_names,
        removed_parameter_message,
    )

    class RefuseUnknownArguments(Middleware):
        async def on_call_tool(
            self,
            context: MiddlewareContext[Any],
            call_next: CallNext[Any, ToolResult],
        ) -> ToolResult:
            arguments = context.message.arguments or {}
            # a call without arguments has none to refuse, and one to no tool is FastMCP's to refuse
            tool = await provider.get_tool(context.message.name) if arguments else None
            if tool is not None:
                taken = tool.parameters.get("properties", {})
                unknown = [name for name in arguments if name not in taken]
                renamed = [name for name in unknown if RENAMED_REQUEST_PARAMETERS.get(name) in taken]
                refused = [f"{name} was renamed to {RENAMED_REQUEST_PARAMETERS[name]}" for name in renamed]
                removed = [name for name in unknown if name in REMOVED_REQUEST_PARAMETERS]
                refused += [removed_parameter_message(name) for name in removed]
                if others := [name for name in unknown if name not in renamed and name not in removed]:
                    verb = "is not an argument" if len(others) == 1 else "are not arguments"
                    refused.append(
                        f"{join_names(others)} {verb} of {tool.name}, which takes {join_names(sorted(taken))}"
                    )
                if refused:
                    raise ToolError("; ".join(refused))
            return await call_next(context)

    return RefuseUnknownArguments()


def build_mcp_server(rest_app: FastAPI) -> FastMCP:
    """Build the wetterdienst MCP server from the REST API app.

    Wraps every data endpoint as an MCP tool and attaches the workflow ``instructions``, clean tool
    names and the noise-endpoint exclusions described in the module docstring.

    This drives the ``OpenAPIProvider`` directly (rather than ``FastMCP.from_fastapi``) so the route
    maps, tool names and lifespan can be configured in one place. Output validation is left on (the
    default): the endpoints' ``response_model`` types match what they actually serialise, so FastMCP
    derives accurate output schemas and validating the results catches real drift.
    """
    from contextlib import asynccontextmanager  # noqa: PLC0415

    import httpx2  # noqa: PLC0415
    from fastmcp import FastMCP  # noqa: PLC0415
    from fastmcp.server.providers.openapi import MCPType, OpenAPIProvider, RouteMap  # noqa: PLC0415

    route_maps = [RouteMap(pattern=pattern, mcp_type=MCPType.EXCLUDE) for pattern in _EXCLUDE_PATTERNS]
    # httpx2, not httpx: FastMCP 4 types ``OpenAPIProvider.client`` as ``httpx2.AsyncClient`` and
    # drives it directly, so the two clients are not interchangeable here. The requests are marked so
    # the REST app leaves them out of fastapi's telemetry (GH-2432)
    #
    # `raise_app_exceptions=False`: an exception no endpoint handled is answered by the app as its
    # 500 problem, a fixed sentence, as it is over HTTP. The default raises it into FastMCP, whose
    # tool error then carries the exception's own text -- a path of the server, say -- which the
    # REST API deliberately hides (GH-2767, GH-2984)
    client = httpx2.AsyncClient(
        transport=httpx2.ASGITransport(app=_mark_tool_requests(rest_app), raise_app_exceptions=False),
        base_url=_ASGI_BASE_URL,
    )
    provider = OpenAPIProvider(
        openapi_spec=rest_app.openapi(),
        client=client,
        route_maps=route_maps,
        mcp_names=_TOOL_NAMES,
        mcp_component_fn=_annotate_tool,
    )

    @asynccontextmanager
    async def lifespan(_server: FastMCP):  # noqa: ANN202
        # Tie the in-process httpx2 client to the server lifespan so it is closed on shutdown; this
        # lifespan is composed into the REST app's lifespan when the MCP endpoint is mounted (see restapi.py).
        try:
            yield
        finally:
            await client.aclose()

    # `version` is the wetterdienst version rather than FastMCP's: left unset, a client's
    # server info reports the FastMCP release as the server's own version.
    return FastMCP(
        name="Wetterdienst",
        version=__version__,
        instructions=INSTRUCTIONS,
        providers=[provider],
        lifespan=lifespan,
        middleware=[_refuse_unknown_arguments(provider)],
    )
