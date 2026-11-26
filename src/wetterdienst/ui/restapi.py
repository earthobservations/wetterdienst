# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Utilities for the wetterdienst package."""

from __future__ import annotations

import contextvars
import itertools
import json
import logging
import math
import os
import re
from dataclasses import replace
from textwrap import dedent
from typing import TYPE_CHECKING, Annotated, Any, Literal, NotRequired, cast, get_args, get_type_hints

import polars as pl
from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.routing import APIRoute
from fastapi.utils import is_body_allowed_for_status_code
from pydantic import BaseModel, ConfigDict, Field, ValidationError, with_config
from starlette.exceptions import HTTPException as StarletteHTTPException

# not `typing.TypedDict`: pydantic refuses that as a response model on Python below 3.12
from typing_extensions import TypedDict

from wetterdienst import Author, Info, Settings, Wetterdienst, __version__
from wetterdienst.core.station_search import find_stations_by_id
from wetterdienst.exceptions import (
    ApiNotFoundError,
    BufrReaderMissingError,
    ConfigurationError,
    CredentialMissingError,
    CredentialRejectedError,
    DateRequiredError,
    DownloadError,
    ImageTooLargeError,
    ImageTooManyPointsError,
    MissingDependencyError,
    MissingTimeIntervalError,
    NoInternetError,
    NoStationPositionsError,
    ProviderRateLimitError,
    ReversedTimeIntervalError,
    StationListingIncompleteError,
    UpstreamError,
    WetterdienstError,
)
from wetterdienst.io.formats import FORMATS, is_image
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.group_statistics import GroupsOverLimitError
from wetterdienst.model.metadata import CoverageParameter, Extent  # noqa: TC001, needed at runtime by pydantic
from wetterdienst.model.request import TimeseriesRequest
from wetterdienst.model.result import (
    StationsFilter,
    ValuesResult,
    _HistoryEntry,
    _InterpolatedValuesDictBody,
    _InterpolatedValuesOgcFeatureCollectionBody,
    _Station,
    _StationsDictBody,
    _StationsOgcFeatureCollectionBody,
    _SummarizedValuesDictBody,
    _SummarizedValuesOgcFeatureCollectionBody,
    _ValuesDictBody,
    _ValuesOgcFeatureCollectionBody,
)
from wetterdienst.model.row_selection import (
    MAX_REPORTED_SERIES,
    MAX_TOOL_SERIES,
    RowSelectionError,
    RowsOverLimitError,
    Searched,
)
from wetterdienst.options import Options
from wetterdienst.settings import check_settings, removed_settings
from wetterdienst.ui import forecast_start
from wetterdienst.ui.budget import (
    fit_alerts,
    fit_coverage,
    fit_station_ids,
    fit_stations,
    fit_statistics,
    fit_values,
)
from wetterdienst.ui.caching import (
    CATALOGUE_CACHE_CONTROL,
    HISTORY_CACHE_CONTROL,
    cached_json,
    settings_changed_at,
    validators,
)
from wetterdienst.ui.core import (
    SELECTION_EXAMPLES,
    AlertsRequest,
    AuthAnswer,
    AuthRequest,
    CoverageRequest,
    GlossaryEntry,
    GlossaryRequest,
    HistoryRequest,
    InterpolationRequest,
    IssuesRequest,
    KostraRequest,
    ProvidersRequest,
    RadarFrameRequest,
    RadarFramesRequest,
    RestInterpolationRequest,
    RestSummaryRequest,
    Selection,
    SettingsRequest,
    StationIdsRequest,
    StationsRequest,
    StatisticsRequest,
    StormCellsRequest,
    SummaryRequest,
    ValuesRequest,
    _caller_refusal_status,
    check_timeseries_api,
    coverage_needs_a_network,
    failure_status,
    get_auth,
    get_glossary,
    get_interpolate,
    get_issues,
    get_stations,
    get_statistics,
    get_summarize,
    get_values,
    join_names,
    limit_stations_to_rank,
    limit_stations_to_window,
    overlay_options,
    resolve_network,
    row_options_of,
    set_logging_level,
)
from wetterdienst.ui.limits import (
    Limits,
    check_chosen_groups,
    check_chosen_rows,
    check_point_rows,
    check_rows,
    check_series_count,
    check_station_count,
    check_stations_in_reach,
    estimate_point_rows,
    estimate_rows,
    limits_of,
    selected_station_count,
)
from wetterdienst.ui.mcp import is_tool_request
from wetterdienst.ui.middleware import RequestContextMiddleware, request_timeout, timeout_detail
from wetterdienst.ui.problems import (
    PROBLEM_MEDIA_TYPE,
    PROBLEMS,
    QUOTA_RETRY_AFTER_SECONDS,
    RETRY_AFTER_STATUSES,
    ProblemError,
    ProblemKind,
    current_request_id,
    kind_of,
    problem_body,
    problem_response,
    status_phrase,
)
from wetterdienst.ui.providers import ProvidersAnswer, get_providers
from wetterdienst.ui.radar import RadarFramesWithMetadataDict, render_radar_frames
from wetterdienst.ui.readiness import CHECKS, failed_checks
from wetterdienst.ui.render import (
    InterpolationSettings,
    StationsSettings,
    SummarySettings,
    ValuesSettings,
    _applied_settings,
    _AppliedSettings,
    ndjson_end,
    ndjson_head,
    ndjson_line,
    ndjson_refusal,
    render,
    render_alerts,
    render_history,
    render_issues,
    render_kostra,
    render_station_ids,
    render_stations,
    render_statistics,
    render_storm_cells,
)
from wetterdienst.ui.response_metadata import (
    API_VERSION,
    ResponseMetadata,
    Search,
    StationIdsMetadata,
    StatisticsMetadata,
    catalogue_headers,
    issues_metadata,
    radar_metadata,
    response_headers,
    response_metadata,
    station_ids_headers,
    statistics_metadata,
)
from wetterdienst.ui.streaming import (
    NDJSON_MEDIA_TYPE,
    STREAM_FORMATS,
    csv_stream,
    frames_in_batches,
    ndjson_stream,
    stream_response,
)
from wetterdienst.util.cli import no_color, setup_logging
from wetterdienst.util.extras import import_optional
from wetterdienst.util.hosts import is_loopback, loopback_allowed_hosts, split_listen_address
from wetterdienst.util.logging import get_one_line_logger
from wetterdienst.util.response_warnings import begin_response, record_response_warning, recorded_warnings

if TYPE_CHECKING:
    import datetime as dt
    from collections.abc import Callable, Collection, Iterator, Mapping, Sequence

    from starlette.responses import StreamingResponse
    from starlette.types import ASGIApp, Receive, Scope, Send

    from wetterdienst.api import StandaloneRequest
    from wetterdienst.model.group_statistics import StatisticsResult
    from wetterdienst.model.metadata import ParameterModel
    from wetterdienst.model.result import InterpolatedValuesResult, StationsResult, SummarizedValuesResult

info = Info()

# the groups of operations in the OpenAPI document, see `app`
TAG_CATALOGUE = "Catalogue"
TAG_STATIONS = "Stations"
TAG_VALUES = "Values"
TAG_ALERTS = "Alerts"
TAG_STORM_CELLS = "Storm cells"
TAG_KOSTRA = "Heavy rainfall"
TAG_RADAR = "Precipitation radar"
TAG_SERVER = "Server"

# FastAPI's OpenTelemetry stays on, so it reports to a provider the operator sets up. Its startup
# export from `OTEL_EXPORTER_OTLP_*` is off: it would set up providers where the OpenTelemetry SDK
# is installed and none is, add a second exporter to one the operator set up, and where it cannot
# export (no SDK, gRPC) warn on fastapi 0.142.2 and refuse to start on 0.142.0 and 0.142.1. To
# export, set up the provider, e.g. with `opentelemetry-instrument` (GH-2407). An MCP tool's
# in-process request to this app is left out, see `is_tool_request` (GH-2432)
#
# The `info` of the OpenAPI document is the project's, from `pyproject.toml` and the README (GH-3129): the version is
# the package's, the API version is in the path (`/api/v1`) and is the first thing the description says.
app = FastAPI(
    title="Wetterdienst",
    summary="Open weather data for humans",
    description=dedent(
        f"""\
        Weather, climate and hydrology data from national weather services (DWD, NOAA, ECCC and many more) through
        one interface: find a station with `stations`, read its measurements with `values`, or estimate a point
        between stations with `interpolate` and `summarize`.

        **Version.** This document describes version {API_VERSION} of the API, served under `/api/v{API_VERSION}`;
        `/api` is an alias of the current version. `info.version` is the version of wetterdienst that serves it,
        `info.x-api-version` that of the API.
        The `operationId` of an operation is stable: the name of its handler, then its path without the version and
        its method (`values_api_values_get`), and the MCP tools are found by it. A change to one is a break of the
        API version, as a removed path, parameter or member is.

        **Answers.** The JSON and GeoJSON of the data routes carry a `metadata` block next to the data: the
        provider with its licence and the credit line to give, the request as resolved, counts and warnings.

        **Errors.** Every error is an `application/problem+json` document as RFC 9457 describes it (`Problem`),
        whose `type` names the kind of error: read that, not the `detail`. A 502, 503 or 504 carries `Retry-After`.

        **Licence.** The code is MIT. The data is published under the terms of its provider, which the `metadata`
        of every answer and `providers` state.
        """
    ),
    version=__version__,
    contact={"name": "wetterdienst", "url": "https://github.com/earthobservations/wetterdienst/issues"},
    # `identifier` and `url` are mutually exclusive in OpenAPI 3.1: the SPDX identifier says which licence
    license_info={"name": "MIT", "identifier": "MIT"},
    servers=[
        {"url": "https://wetterdienst.eobs.org", "description": "The hosted instance."},
        {"url": "http://127.0.0.1:7890", "description": "A local server, as `wetterdienst restapi` starts it."},
    ],
    openapi_tags=[
        {
            "name": TAG_CATALOGUE,
            "description": "What the server offers: providers, networks, parameters, and credentials.",
        },
        {"name": TAG_STATIONS, "description": "Find stations and read their history and the runs of a forecast."},
        {
            "name": TAG_VALUES,
            "description": "Measurements of stations, estimated for a point between them, or counted, averaged and "
            "added up per year, month, day or hour.",
        },
        {"name": TAG_ALERTS, "description": "Weather warnings of the DWD."},
        {"name": TAG_STORM_CELLS, "description": "Thunderstorm cells of the DWD, detected in its radar data."},
        {
            "name": TAG_KOSTRA,
            "description": "Design rainfall of the DWD (KOSTRA-DWD-2020, return periods of heavy rain): the depth, "
            "intensity and uncertainty of a rain by duration and return period, at a point in Germany.",
        },
        {
            "name": TAG_RADAR,
            "description": "DWD's precipitation radar over Germany as map images: the frames of the last hours and "
            "DWD's forecast of the next two.",
        },
        {"name": TAG_SERVER, "description": "This instance: its version and limits, its settings, and its health."},
    ],
    debug=False,
    telemetry={"auto_configure": False, "exclude": is_tool_request},
)

#: where the current version is served; OpenAPI documents this prefix (GH-2561)
API_PREFIX = f"/api/v{API_VERSION}"
#: the same routes without the version, an alias of the current version: not deprecated, and not in OpenAPI
API_ALIAS_PREFIX = "/api"
#: where the MCP endpoint of the current version is served; the tools mirror the routes of `API_PREFIX` 1:1,
#: so the two share a version (GH-3074)
MCP_PREFIX = f"/mcp/v{API_VERSION}"
#: the same endpoint without the version, an alias of the current version, as `API_ALIAS_PREFIX` is for the routes
MCP_ALIAS_PREFIX = "/mcp"


def _operation_id(route: APIRoute) -> str:
    """Give an operation the id it had before the routes were served under a version (`values_api_values_get`).

    FastAPI builds the id from the route's name and its full path, so the prefix of the version
    would rename every operation, and with it every MCP tool, which `ui.mcp._TOOL_NAMES` finds by
    that id, and every client generated from the document. The version stays out of the id; the
    path in the document carries it.
    """
    path = route.path_format.removeprefix(API_PREFIX).removeprefix(API_ALIAS_PREFIX)
    method = min(route.methods or {"GET"}).lower()
    return re.sub(r"\W", "_", f"{route.name}{API_ALIAS_PREFIX}{path}") + f"_{method}"


#: every route under `/api`, included twice at the bottom of this module: under `API_PREFIX`, and as
#: its alias under `API_ALIAS_PREFIX`. The same handlers, so a version is one definition
router = APIRouter(generate_unique_id_function=_operation_id)


class _RefuseInvalidSettings:
    """Refuse to start the server while a `WD_*` setting is malformed, naming the variable (GH-2335).

    A variable that asks for what was removed (`WD_RESTAPI_SQL=true`, see `removed_settings`) is warned about, once,
    and the server starts: it asks for nothing the server could not do without it.

    Checked as the server starts the app's lifespan, so it holds whatever starts it --
    `wetterdienst restapi`, `uvicorn wetterdienst.ui.restapi:app` -- unless the lifespan is turned
    off, and covers `/mcp/v1` and its alias `/mcp`, which are served by this app. A failure in the
    app's own lifespan would reach the server as Starlette's formatted traceback; answering the
    startup here gives the log the variables and what is wrong with them, a line each, without the
    values, and the server exits before taking a connection. Under `--reload` it is the worker that exits; the reloader
    stays, and starts a worker again on the next change to a source file.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            try:
                problems = check_settings()
                notices = removed_settings()
            except Exception as e:  # noqa: BLE001
                # a validator failing other than by refusing the value, as the station distances'
                # did with a `TypeError` until GH-2353, is refused all the same: raised here,
                # uvicorn's default `--lifespan auto` would take it for a lifespan the app does not
                # support, and serve. Told by its type alone, as its message is not pydantic's and
                # may carry what it was given
                problems = [f"the settings could not be built: {type(e).__name__}"]
                notices = []
            for notice in notices:
                log.warning(notice)
            if problems:
                await receive()
                message = "\n".join(["Refusing to start, the settings are invalid:", *problems])
                await send({"type": "lifespan.startup.failed", "message": message})
                return
        await self.app(scope, receive, send)


app.add_middleware(_RefuseInvalidSettings)
# the request id, the timeout and the deprecation headers of every request (GH-3065); added after the check of the
# settings, so it is the outer of the two
app.add_middleware(RequestContextMiddleware)

# Set to True at the bottom of this module when the optional ``[mcp]`` extra (fastmcp) is installed
# and an MCP endpoint has been mounted onto ``app`` at ``MCP_PREFIX`` and ``MCP_ALIAS_PREFIX``. Read by the index page.
mcp_enabled = False

log = get_one_line_logger(__name__)


REQUEST_EXAMPLES = {
    "dwd_observation_daily_climate_stations": "api/stations?provider=dwd&network=observation&parameters=daily/kl&periods=recent&all=true",  # noqa:E501
    "dwd_observation_daily_climate_values": "api/values?provider=dwd&network=observation&parameters=daily/kl&periods=recent&stations=00011",  # noqa:E501
    "dwd_observation_daily_climate_history": "api/history?provider=dwd&network=observation&parameters=daily/kl&stations=00011",  # noqa:E501
    "dwd_observation_daily_climate_interpolation": "api/interpolate?provider=dwd&network=observation&parameters=daily/kl/temperature_air_mean_2m&station=00071&timestamp=1986-10-31/1986-11-01",  # noqa:E501
    "dwd_observation_daily_climate_summary": "api/summarize?provider=dwd&network=observation&parameters=daily/kl/temperature_air_mean_2m&station=00071&timestamp=1986-10-31/1986-11-01",  # noqa:E501
    "dwd_mosmix_issues": "api/issues?provider=dwd&network=mosmix&station=10147",
    "dwd_dmo_issues": "api/issues?provider=dwd&network=dmo&station=10147",
    "dwd_swsmos_issues": "api/issues?provider=dwd&network=swsmos&station=A006",
    "dwd_weather_alerts": "api/alerts?granularity=community&format=geojson",
    "dwd_storm_cells": "api/storm-cells?format=geojson&track=false",
    "dwd_kostra": "api/kostra?latitude=52.52&longitude=13.40&duration=60",
    "station_ids": "api/station-ids?wmo_id=10381",
}


def _problem_response(
    request: Request,
    status_code: int,
    detail: str,
    kind: ProblemKind | None = None,
    *,
    errors: list[Any] | None = None,
    extra: Mapping[str, Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> Response:
    """Answer a failure with the one error body of this API, an RFC 9457 problem (GH-2634, GH-3065).

    `{"type": "urn:wetterdienst:problem:<kind>", "title": <the status' phrase>, "status": <int>, "detail": <str>,
    "instance": <the request>, "request_id": <the id>}` (`ui.problems`). `detail` is always text, the whole
    reason, one line for each thing wrong where a request is wrong in several; a client that only wants a sentence
    reads that. `errors` is added where a request failed validation: the list of pydantic's entries, each with the
    `loc` of its parameter. `extra` holds the members a kind has beyond these, such as the `limit` of
    `limit-exceeded`. A 502, 503 or 504 carries `Retry-After`, and every problem `X-Request-ID`.

    An MCP tool's request is answered with the text alone, as plain text (`problem_response`).
    """
    return problem_response(request.scope, status_code, detail, kind, errors=errors, extra=extra, headers=headers)


def _problem_of(request: Request, error: StarletteHTTPException) -> Response:
    """Answer with the problem an `HTTPException` is, the kind and the members it was raised with.

    An MCP tool's request gets the `tool_detail` of the problem where it has one (`ProblemError`).
    """
    tool_detail = getattr(error, "tool_detail", None) if is_tool_request(request.scope) else None
    return _problem_response(
        request,
        error.status_code,
        tool_detail or str(error.detail),
        kind_of(error),
        extra=getattr(error, "extra", None),
        headers=error.headers,
    )


@app.exception_handler(StarletteHTTPException)
async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> Response:
    """Answer an `HTTPException`, and Starlette's own for an unknown path or a method not allowed, as a problem."""
    if exc.status_code == 405 and request.url.path in _HEAD_PROBES:
        # Starlette lists the methods of the first route that matched the path, which is the `GET`: the probes take both
        exc = StarletteHTTPException(405, exc.detail, {**(exc.headers or {}), "Allow": "GET, HEAD"})
    if not is_body_allowed_for_status_code(exc.status_code):
        return Response(status_code=exc.status_code, headers=exc.headers)
    if not isinstance(exc.detail, str):
        exc = StarletteHTTPException(exc.status_code, status_phrase(exc.status_code), exc.headers)
    return _problem_of(request, exc)


def _describe_validation_errors(errors: list[dict[str, Any]]) -> str:
    """Tell each entry of a validation error by the parameter it is located at, one line each.

    The `query` in front of a location says where the parameter came from and is left out; a rule
    about no parameter in particular is told by its message alone.
    """
    lines = []
    for error in errors:
        where = ".".join(str(part) for part in error.get("loc", ())[1:])
        lines.append(f"{where}: {error['msg']}" if where else str(error["msg"]))
    return "\n".join(lines)


#: how deep the input a validation error repeats is kept
_ERROR_INPUT_DEPTH = 16


def _writable(value: Any, depth: int = _ERROR_INPUT_DEPTH) -> Any:  # noqa: ANN401
    """Make an entry of a validation error one a response can write: no `inf`, no `nan`, no endless nesting.

    An entry holds the `input` it refused, which is whatever the query carried. JSON has no number for `1e999`, so the
    body of the 422 could not be written, and a mapping of thousands of levels, which a query of a few kilobytes
    makes, exhausted the stack of the encoder: the caller was answered a 500 for a request that was only malformed
    (GH-3085). A float JSON has no number for is written as its text, what is nested deeper than `depth` as `...`.
    """
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, (dict, list, tuple)):
        if depth <= 0:
            return "..."
        if isinstance(value, dict):
            return {key: _writable(item, depth - 1) for key, item in value.items()}
        return [_writable(item, depth - 1) for item in value]
    return value


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(request: Request, exc: RequestValidationError) -> Response:
    """Answer a request that fails validation with a 422 problem, its entries under `errors`.

    `coverage` with no fault but a missing `provider` or `network` is the one request that is a 400: it listed
    every provider until 1.0.0, and its answer names `providers`, which does (GH-3996).
    """
    route = request.scope.get("route")
    if getattr(route, "name", None) == "coverage" and all(
        error.get("type") == "missing" and tuple(error.get("loc", ())[1:]) in {("provider",), ("network",)}
        for error in exc.errors()
    ):
        return _problem_response(request, 400, coverage_needs_a_network(app.url_path_for("providers")))
    errors = jsonable_encoder(_writable(exc.errors()))
    return _problem_response(request, 422, _describe_validation_errors(errors), errors=errors)


class _NoRequestModel(BaseModel):
    """The request model of a failure raised where no endpoint's request is at hand: it carries no field."""


@app.exception_handler(WetterdienstError)
async def _wetterdienst_error_handler(request: Request, exc: WetterdienstError) -> Response:
    """Answer an exception of the library that escaped an endpoint's own handling by its place in the hierarchy.

    The endpoints decide with `_failure` inside their handlers; this is for what is raised outside
    them, such as while a result is rendered, and gives it the status `failure_status` gives it.
    """
    error = _failure(exc, _NoRequestModel(), f"serve {request.url.path}")
    return _problem_of(request, error)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> Response:
    """Answer a failure no endpoint handled with the 500 problem of `_server_error`, the traceback in the log.

    Starlette sends this answer and then raises the exception again, so the server logs it as it
    did when the answer was its plain-text one.
    """
    error = _server_error(exc)
    return _problem_of(request, error)


def _dependency_missing_on_the_server(e: MissingDependencyError, what: str) -> HTTPException:
    """Report a dependency this deployment does not have as the server's lack, not the caller's error.

    The blanket handlers answered it with a 400 carrying `pip install wetterdienst[bufr]` -- an
    instruction for a machine the caller does not administer, about a request that was perfectly
    well formed. Over HTTP the missing half is a property of the deployment, and 501 is what says
    so: this server does not implement what needs the package, such as the networks published as
    BUFR or an image. The install line is not lost, it moves to where someone can
    act on it -- the server log, carried there by the message itself rather than by a traceback,
    since a dependency that was never installed has no incident to show.
    """
    log.error(f"Failed to {what}, this deployment lacks an optional dependency: {e}")
    if isinstance(e, BufrReaderMissingError):
        detail = (
            "This server cannot decode BUFR, which the requested network is published as. The "
            "request was valid; the deployment is missing the eccodes and pdbufr readers that "
            "read it. Ask whoever runs this instance to install them."
        )
    else:
        detail = (
            "This server lacks an optional dependency that the request needs. The request was valid; "
            "ask whoever runs this instance to install it."
        )
    return ProblemError(501, detail, ProblemKind.DEPENDENCY_MISSING)


@app.exception_handler(MissingDependencyError)
async def _missing_dependency_handler(request: Request, exc: MissingDependencyError) -> Response:
    """Answer a dependency the deployment lacks with a 501 wherever it was reached.

    The endpoints turn it into one inside their own handlers (`_failure`); this is for the rest,
    such as rendering an image after the values were collected.
    """
    error = _dependency_missing_on_the_server(exc, f"serve {request.url.path}")
    return _problem_of(request, error)


def _credential_missing_on_the_server(e: CredentialMissingError, request: BaseModel, what: str) -> HTTPException:
    """Report a credential this deployment lacks as the server's lack, not the caller's error or a crash.

    The provider's message tells whoever runs the process which setting to change, which is no
    instruction for a caller of this API: it answered it as a 500, the server broken, with the
    environment variable named in the body. The provider exists and this instance has no key for it,
    which is a 501 as for the BUFR reader: this server does not serve the network. Not a 503, which
    the app asks once more (`RETRY_TRANSIENT` keeps it for a proxy's), and a missing key does not
    pass by itself. This is what `configured: false` reports, without the setting's name; the body
    points at `providers` for it. The request's window and parameters are parsed by the time this is
    raised, its stations are not, so the body does not vouch for the request. The message is not
    lost, it moves to the server log, as a warning: a state that lasts until someone configures the
    key is no incident.
    """
    log.warning(f"Failed to {what}, no credential is configured for the provider: {e}")
    provider, network = getattr(request, "provider", None), getattr(request, "network", None)
    of = f" for {provider}/{network}" if provider and network else ""
    return ProblemError(
        501,
        (
            f"This server has no credential{of}, which the provider requires, so it cannot serve the "
            f"request. {app.url_path_for('providers')} tells whether a provider is "
            "configured; otherwise ask whoever runs this instance."
        ),
        ProblemKind.CREDENTIAL_MISSING,
    )


def _credential_rejected_on_the_server(e: CredentialRejectedError, request: BaseModel, what: str) -> HTTPException:
    """Report a credential the provider refused as the server's lack, not the caller's error or a crash.

    The provider's message names the setting that holds the key, which is for whoever runs this
    server: it was answered as a 500 with the variable named in the body (GH-2665), the same leak as
    a missing key. The key is there and the provider does not accept it, so the server cannot serve
    the network until someone replaces it, which is the 501 of a missing key, with a body of its own
    that says the key was refused. `/api/auth` tells the same, as `valid: false`. The message moves
    to the server log as an error: a revoked or mistyped key is something to act on, and it is the
    provider's answer that is in the message, never the key.
    """
    log.error(f"Failed to {what}, the provider rejected the credential of this server: {e}")
    provider, network = getattr(request, "provider", None), getattr(request, "network", None)
    of = f" for {provider}/{network}" if provider and network else ""
    return ProblemError(
        501,
        (
            f"The provider rejected the credential of this server{of}, so it cannot serve the "
            f"request. {app.url_path_for('auth')} tells whether the credential is accepted; "
            "otherwise ask whoever runs this instance."
        ),
        ProblemKind.CREDENTIAL_REJECTED,
    )


#: the longest side, in pixels once `scale` is applied, of an image this server renders. The renderer holds the
#: whole canvas and draws it for as long as it takes: 14000 x 10000 px took 18 s in the browser the images were
#: drawn with before vl-convert, and 28000 x 20000 px 30 s and then an empty body that was answered with a 200
#: (GH-2765)
_MAX_IMAGE_SIDE = 8192
#: the size an image is drawn at when a request names none
_DEFAULT_IMAGE_WIDTH, _DEFAULT_IMAGE_HEIGHT = 700, 500


def _refuse_oversized_image(width: int | None, height: int | None, scale: float | None) -> None:
    """Refuse an image larger than `_MAX_IMAGE_SIDE` on a side, with a 400, before anything is fetched.

    The request fields only have to be positive, and the caller is whoever can reach the API: each
    image request draws its own canvas, so the size it paints is theirs to choose. The library
    and the CLI, whose caller is the host's own user, are not limited. The MCP tools are this API's
    routes, so they are limited with it. A size left out is the default size, which is what is
    measured here: the height of a chart of several parameters is 300 px for each, known only once
    they are collected, and is measured then, by `check_image_size` (`_refuse_oversized_render`).
    """
    scale = 1 if scale is None else scale
    rendered = ((width or _DEFAULT_IMAGE_WIDTH) * scale, (height or _DEFAULT_IMAGE_HEIGHT) * scale)
    if max(rendered) > _MAX_IMAGE_SIDE:
        error = ImageTooLargeError(rendered[0], rendered[1], _MAX_IMAGE_SIDE)
        raise ProblemError(400, f"{error} Lower width, height or scale.", ProblemKind.IMAGE_TOO_LARGE)


#: what a refusal of a chart is sent with: whoever runs the server may switch charts on without a restart (a `.env` is
#: read by every request), so no cache keeps the answer
_CHARTS_DISABLED_HEADERS = {"Cache-Control": "no-store"}


def _refuse_disabled_chart(request: StationsRequest | ValuesRequest | InterpolationRequest | SummaryRequest) -> None:
    """Refuse a chart format with a 403 before anything is read, where the server draws no charts (GH-4461).

    vl-convert draws a chart in the server's process, one at a time, which takes time and memory (11 s and 1.3 GB at
    100,000 points): `WD_RESTAPI_PLOTTING` is off by default (`Settings.restapi_plotting`).
    This is the first thing a handler does: no station is looked up, nothing is downloaded, and the plotting libraries
    are not imported. The request is validated by then, and `values` has refused a row option given twice (which reads
    nothing), so a request that is malformed is the 422 first; a chart that is also too large is told that charts are
    off, which is the answer that does not change by lowering `scale`. The data formats are never refused.
    """
    chart = FORMATS.get(request.format)
    if chart is None or chart.kind != "chart" or Settings().restapi_plotting:
        return
    offered = [
        name for name in get_args(type(request).model_fields["format"].annotation) if FORMATS[name].kind == "data"
    ]
    detail = (
        f"This server draws no charts, so format={request.format} is refused. "
        f"It answers {join_names(offered, last='or')}. "
        "Ask for one of these, or ask whoever runs this instance to switch charts on "
        "(WD_RESTAPI_PLOTTING=true)."
    )
    entry = {
        "type": "charts_disabled",
        "loc": ["query", "format"],
        "msg": detail,
        "input": request.format,
        "ctx": {"formats": offered},
    }
    raise ProblemError(
        403, detail, ProblemKind.CHARTS_DISABLED, extra={"errors": [entry]}, headers=_CHARTS_DISABLED_HEADERS
    )


def _refuse_oversized_chart(request: StationsRequest | ValuesRequest | InterpolationRequest | SummaryRequest) -> None:
    """Refuse the size of a chart in an image format, see `_refuse_oversized_image`."""
    if is_image(request.format):
        _refuse_oversized_image(request.width, request.height, request.scale)


@app.exception_handler(ImageTooLargeError)
async def _refuse_oversized_render(request: Request, exc: ImageTooLargeError) -> Response:
    """Answer a chart whose own height makes the image too large with a 400, as `_refuse_oversized_image` does.

    Raised by `check_image_size` once the chart is built, since a chart of several parameters is
    300 px tall for each, and before it is drawn.
    """
    log.info(f"Refused {request.url.path}: {exc}")
    return _problem_response(
        request,
        400,
        f"{exc} Lower scale, give a smaller height, or ask for fewer parameters.",
        ProblemKind.IMAGE_TOO_LARGE,
    )


@app.exception_handler(ImageTooManyPointsError)
async def _refuse_too_many_points(request: Request, exc: ImageTooManyPointsError) -> JSONResponse:
    """Answer a chart of more points than the server draws with a 400 of the kind `limit-exceeded` (GH-3238).

    Raised once the chart is built, which is where its points are counted, and before it is drawn. The page is a
    chart as well, since it embeds the points.
    """
    log.info(f"Refused {request.url.path}: {exc}")
    narrow = "Ask for fewer stations or parameters, or a shorter `timestamp` window."
    return _problem_response(
        request,
        400,
        f"{exc} {narrow} The Python API and the command line draw any number.",
        ProblemKind.LIMIT_EXCEEDED,
        extra={"limit": "image_points", "maximum": exc.max_points, "requested": exc.points},
    )


# each output format by its media type; the rest are JSON. `image/{format}` named no registered type
# for jpg or svg, and a PDF was sent as `image/pdf` (GH-2063)
_MEDIA_TYPES = {
    "csv": "text/csv",
    # only a tool's request is answered as one body in ndjson (`_is_streamed`); any other is streamed
    "ndjson": NDJSON_MEDIA_TYPE,
    "html": "text/html",
    "png": "image/png",
    "jpg": "image/jpeg",
    "svg": "image/svg+xml",
    "pdf": "application/pdf",
}


#: the policy of the index page, which needs no script, request or image: its styles are in the page. It cannot be
#: given a `<base>` to re-point its links, nor send a form (GH-3349)
_PAGE_CSP = "default-src 'none'; style-src 'unsafe-inline'; base-uri 'none'; form-action 'none'"
#: the policy of an SVG answer, which a browser shows as a document where its address is opened, and runs script in:
#: no script and no request, styles in the file, images only inlined. That is all a chart written by vl-convert has;
#: its `url(#...)` is a clip path of its own. Not for `html`, which is a script by design, and not for `pdf`, whose
#: viewer a policy breaks
_SVG_CSP = "default-src 'none'; style-src 'unsafe-inline'; img-src data:"


def _image_headers(fmt: str) -> dict[str, str]:
    """Give the `Content-Security-Policy` of an image answer, for the one format that has one: SVG."""
    return {"Content-Security-Policy": _SVG_CSP} if fmt == "svg" else {}


def _answer(content: str | bytes, fmt: str, metadata: ResponseMetadata) -> Response:
    """Send a rendered answer with the headers that say what its `metadata` block says, in the one format or the other.

    A JSON or GeoJSON answer holds the block in its body and carries the headers too, so that a proxy or a
    client that reads no body knows the licence, the credit line and the warnings of what it passes on.
    """
    return Response(
        content=content,
        media_type=_MEDIA_TYPES.get(fmt, "application/json"),
        headers={**response_headers(metadata), **_image_headers(fmt)},
    )


class ServerSettings(BaseModel):
    """What each endpoint takes for a setting a request leaves out."""

    model_config = ConfigDict(extra="forbid")

    values: ValuesSettings
    interpolate: InterpolationSettings
    summarize: SummarySettings


# what the JSON formats of the data endpoints answer with: the `metadata` block, which is always there, and,
# with `with_metadata`, the settings they were got with for the three that have settings (GH-2359, GH-2561)
class _StationsWithMetadataDict(_StationsDictBody):
    metadata: ResponseMetadata


class _StationsWithMetadataOgcFeatureCollection(_StationsOgcFeatureCollectionBody):
    metadata: ResponseMetadata


class _ValuesWithSettingsDict(_ValuesDictBody):
    metadata: ResponseMetadata
    settings: NotRequired[ValuesSettings]


class _ValuesWithSettingsOgcFeatureCollection(_ValuesOgcFeatureCollectionBody):
    metadata: ResponseMetadata
    settings: NotRequired[ValuesSettings]


class _InterpolatedValuesWithSettingsDict(_InterpolatedValuesDictBody):
    metadata: ResponseMetadata
    settings: NotRequired[InterpolationSettings]


class _InterpolatedValuesWithSettingsOgcFeatureCollection(_InterpolatedValuesOgcFeatureCollectionBody):
    metadata: ResponseMetadata
    settings: NotRequired[InterpolationSettings]


class _SummarizedValuesWithSettingsDict(_SummarizedValuesDictBody):
    metadata: ResponseMetadata
    settings: NotRequired[SummarySettings]


class _SummarizedValuesWithSettingsOgcFeatureCollection(_SummarizedValuesOgcFeatureCollectionBody):
    metadata: ResponseMetadata
    settings: NotRequired[SummarySettings]


class _StatisticsOverGroups(TypedDict):
    """The statistics over the complete groups of a series that have a value, of one aggregate."""

    groups: int
    usable: int
    min: float | None
    max: float | None
    mean: float | None


class _StatisticsSeries(TypedDict):
    """One station's series with its report, the statistics over its groups and its groups."""

    station_id: str
    name: str | None
    resolution: str
    dataset: str
    parameter: str
    unit: str
    # the unit of an aggregate where it is not `unit`: the `sum` of a temperature is in degree days (`°Cd`)
    units: NotRequired[dict[str, str]]
    first_timestamp: str | None
    last_timestamp: str | None
    searched: int
    expected: int | None
    gaps: int | None
    over_groups: dict[str, _StatisticsOverGroups]
    # `rank` (`per=none`), the columns of `by`, each aggregate (and `<aggregate>_at` for `min`, `max`, `earliest`,
    # `latest`), then `searched`, `expected` and `complete`
    groups: list[dict[str, Any]]


class _StatisticsWithMetadataDict(TypedDict):
    metadata: StatisticsMetadata
    series: list[_StatisticsSeries]


class _HistoryWithMetadataDict(TypedDict):
    metadata: ResponseMetadata
    stations: NotRequired[list[_Station]]
    # one history per station and dataset, each as the `History` model dumps it, its timestamps as text
    histories: list[_HistoryEntry]


class _IssuesWithMetadataDict(TypedDict):
    metadata: ResponseMetadata
    issues: list[str]


class _AlertsWithMetadataDict(TypedDict):
    metadata: ResponseMetadata
    # the UTC production time of the snapshot, null for the latest one
    snapshot: str | None
    # one entry per alert, with the nested `geometry` and `parameters` of DWD's CAP document
    alerts: list[dict[str, Any]]


class _AlertsWithMetadataOgcFeatureCollection(TypedDict):
    type: Literal["FeatureCollection"]
    metadata: ResponseMetadata
    snapshot: str | None
    features: list[dict[str, Any]]


class _StormCellsWithMetadataDict(TypedDict):
    metadata: ResponseMetadata
    # the UTC reference time of the scan, which an empty scan has too
    reference_time: str | None
    # one entry per cell, with the nested `geometry` and `track`
    cells: list[dict[str, Any]]


class _StormCellsWithMetadataOgcFeatureCollection(TypedDict):
    type: Literal["FeatureCollection"]
    metadata: ResponseMetadata
    reference_time: str | None
    features: list[dict[str, Any]]


class _KostraCell(TypedDict):
    # DWD's name of the cell, (row * 1000) + column in six digits
    index_rc: str
    row: int
    column: int
    # the centre of the cell, in WGS84 degrees
    latitude: float
    longitude: float


class _KostraValue(TypedDict):
    duration_minutes: int
    return_period_years: int
    depth_mm: float | None
    intensity_l_s_ha: float | None
    uncertainty_percent: float | None


class _KostraWithMetadataDict(TypedDict):
    metadata: ResponseMetadata
    edition: str
    cell: _KostraCell
    values: list[_KostraValue]


class _StationIdsStation(TypedDict):
    provider: str
    network: str
    # the station list the row comes from: another dataset of the network may list other stations
    resolution: str
    dataset: str
    station_id: str
    name: str | None
    latitude: float | None
    longitude: float | None
    elevation: float | None
    wmo_id: str | None
    wigos_id: str | None
    icao_id: str | None
    # which id of the station matched, and whether the id searched for was its own or came by an equivalence
    matched_by: Literal["wmo_id", "wigos_id", "icao_id"]
    match: Literal["direct", "equivalent"]


class _StationIdsWithMetadataDict(TypedDict):
    metadata: StationIdsMetadata
    stations: list[_StationIdsStation]


@app.get(
    "/",
    response_class=HTMLResponse,
    tags=[TAG_SERVER],
    responses={200: {"content": {"text/html": {"schema": {"type": "string"}}}}},
)
def index() -> HTMLResponse:
    """Provide index page."""

    def _create_author_entry(author: Author) -> str:
        # create author string Max Mustermann (Github href, Mailto)
        mail = f"<a href='mailto:{author.email}'>mail</a>"
        if not author.github_handle:
            return f"{author.name} ({mail})"
        return f"{author.name} (<a href='https://github.com/{author.github_handle}' target='_blank' rel='noopener'>github</a>, {mail})"  # noqa:E501

    title = f"{info.slogan} | {info.name}"
    provider_rows = []

    for provider in Wetterdienst.registry:
        # take the first network api
        first_network = next(iter(Wetterdienst.registry[provider].keys()))
        try:
            api = Wetterdienst.resolve(provider, first_network)
        except ImportError:
            # one provider whose module does not import is not a reason for the page to be a 5xx (GH-2801)
            log.warning(
                f"Left {provider} out of the index, {provider}/{first_network} cannot be imported.", exc_info=True
            )
            continue
        shortname = api.metadata.name_short
        name = api.metadata.name_local
        country = api.metadata.country
        copyright_ = api.metadata.copyright
        url = api.metadata.url
        provider_rows.append(
            f"<tr><td><a href='{url}' target='_blank' rel='noopener'>{shortname}</a></td>"
            f"<td>{name}</td>"
            f"<td>{country}</td>"
            f"<td>{copyright_}</td></tr>"
        )
    providers_table = (
        "<table>"
        "<thead><tr><th>Provider</th><th>Name</th><th>Country</th><th>Copyright</th></tr></thead>"
        f"<tbody>{''.join(provider_rows)}</tbody>"
        "</table>"
    )
    return HTMLResponse(
        content=f"""
    <html lang="en">
        <head>
            <title>{title}</title>
            <meta name="description" content="{info.name} - {info.slogan}">
            <meta name="keywords" content="weather, climate, data, api, open, source, wetterdienst">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 20px;
                    background-color: #f4f4f4;
                }}
                .container {{
                    max-width: 800px;
                    margin: 50px auto;
                    padding: 20px;
                    background-color: #fff;
                    border-radius: 8px;
                    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                }}
                h1 {{
                    color: #333;
                    border-bottom: 2px solid #0074d9;
                    padding-bottom: 10px;
                }}
                p {{
                    margin-bottom: 10px;
                    line-height: 1.6;
                }}
                li {{
                    margin-bottom: 10px;
                }}
                a {{
                    text-decoration: none;
                    color: #0074d9;
                }}
                a:hover {{
                    text-decoration: underline;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                }}
                th, td {{
                    border: 1px solid #ddd;
                    padding: 8px;
                    text-align: left;
                }}
                th {{
                    background-color: #f2f2f2;
                }}
            </style>
        </head>
        <body>
            <div class="container">
                <h1>{info.slogan}</h1>
                <h2>Endpoints</h2>
                <ul>
                    <li><a href="api/providers" target="_blank" rel="noopener">providers</a></li>
                    <li><a href="api/coverage?provider=dwd&amp;network=observation" target="_blank" rel="noopener">coverage</a></li>
                    <li><a href="api/glossary" target="_blank" rel="noopener">glossary</a></li>
                    <li><a href="api/settings" target="_blank" rel="noopener">settings</a></li>
                    <li><a href="api/stations" target="_blank" rel="noopener">stations</a></li>
                    <li><a href="api/values" target="_blank" rel="noopener">values</a></li>
                    <li><a href="api/interpolate" target="_blank" rel="noopener">interpolation</a></li>
                    <li><a href="api/summarize" target="_blank" rel="noopener">summary</a></li>
                    <li><a href="api/alerts" target="_blank" rel="noopener">weather alerts</a></li>
                    <li><a href="api/storm-cells" target="_blank" rel="noopener">storm cells</a></li>
                    <li><a href="api/kostra" target="_blank" rel="noopener">heavy rainfall (KOSTRA)</a></li>
                    <li><a href="api/station-ids" target="_blank" rel="noopener">station by WMO, WIGOS or ICAO id</a></li>
                    {f"<li>MCP endpoint (streamable HTTP): <code>{MCP_PREFIX}</code> (<code>{MCP_ALIAS_PREFIX}</code> follows the current version)</li>" if mcp_enabled else ""}
                </ul>
                <h2>Examples</h2>
                <ul>
                    <li><a href="{REQUEST_EXAMPLES["dwd_observation_daily_climate_stations"]}" target="_blank" rel="noopener">DWD Observation Daily Climate Stations</a></li>
                    <li><a href="{REQUEST_EXAMPLES["dwd_observation_daily_climate_values"]}" target="_blank" rel="noopener">DWD Observation Daily Climate Values</a></li>
                    <li><a href="{REQUEST_EXAMPLES["dwd_observation_daily_climate_history"]}" target="_blank" rel="noopener">DWD Observation Daily Climate History</a></li>
                    <li><a href="{REQUEST_EXAMPLES["dwd_observation_daily_climate_interpolation"]}" target="_blank" rel="noopener">DWD Observation Daily Climate Interpolation</a></li>
                    <li><a href="{REQUEST_EXAMPLES["dwd_observation_daily_climate_summary"]}" target="_blank" rel="noopener">DWD Observation Daily Climate Summary</a></li>
                    <li><a href="{REQUEST_EXAMPLES["dwd_weather_alerts"]}" target="_blank" rel="noopener">DWD Weather Alerts</a></li>
                    <li><a href="{REQUEST_EXAMPLES["dwd_storm_cells"]}" target="_blank" rel="noopener">DWD Storm Cells</a></li>
                    <li><a href="{REQUEST_EXAMPLES["dwd_kostra"]}" target="_blank" rel="noopener">DWD Heavy Rainfall (KOSTRA)</a></li>
                    <li><a href="{REQUEST_EXAMPLES["station_ids"]}" target="_blank" rel="noopener">Station 10381 at every provider</a></li>
                </ul>
                <h2>Producer</h2>
                <ul>
                    <li>Version: {info.version}</li>
                    <li>Authors: {", ".join(_create_author_entry(author) for author in info.authors)}</li>
                    <li>Repository: <a href="{info.repository}" target="_blank" rel="noopener">{info.repository}</a></li>
                    <li>Documentation: <a href="{info.documentation}" target="_blank" rel="noopener">{info.documentation}</a></li>
                </ul>
                <h2>Providers</h2>
                {providers_table}
                <h2>Legal</h2>
                <ul>
                    <li><a href="/impressum" target="_blank" rel="noopener">Impressum</a></li>
                </ul>
            </div>
        </body>
    </html>
    """,  # noqa:E501
        headers={"Content-Security-Policy": _PAGE_CSP},
    )


@app.get(
    "/robots.txt",
    response_class=PlainTextResponse,
    tags=[TAG_SERVER],
    responses={200: {"content": {"text/plain": {"schema": {"type": "string"}}}}},
)
def robots() -> PlainTextResponse:
    """Provide robots.txt."""
    return PlainTextResponse(
        content=dedent(
            """
            User-agent: *
            Disallow: /api/
            """.strip(),
        ),
    )


#: a probe is never reused: what it answered is not what it would answer now
_NO_STORE = {"Cache-Control": "no-store"}


class Health(BaseModel):
    """The answer of the liveness probe."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"status": "OK"}]})

    status: Literal["OK"] = Field(description="Always `OK`: the server is up and answers. It reads no setting.")


@app.get("/health", response_model=Health, tags=[TAG_SERVER])
def health() -> Health:
    """Health check: liveness, for a probe. It is `OK` as long as the server answers; it checks nothing else."""
    return Health(status="OK")


class Ready(BaseModel):
    """The answer of the readiness probe."""

    model_config = ConfigDict(extra="forbid", json_schema_extra={"examples": [{"status": "ready"}]})

    status: Literal["ready"] = Field(
        description="Always `ready`: the server can serve a data request. Where it cannot the answer is a 503 problem "
        "of the kind `not-ready`, with the `checks` that failed."
    )


@app.get(
    "/ready",
    response_model=Ready,
    tags=[TAG_SERVER],
    responses={200: {"headers": {"Cache-Control": {"description": "`no-store`", "schema": {"type": "string"}}}}},
)
def ready() -> Response:
    """Readiness check, for a probe that decides whether to send traffic to the server.

    Can it serve a data request? `ready` where the settings are valid and the cache directory is one the server can
    write to or make. A 503 problem of the kind `not-ready` where not, its `checks` naming `settings` or `cache`. No
    provider is asked, so one that is down does not make the server not ready, and no credential is needed. `/health`
    is the liveness probe: it answers while the process does, and says nothing of this.
    """
    if failed := failed_checks():
        raise ProblemError(
            503,
            f"The server is running but is not ready to serve data: {' and '.join(failed)} failed. "
            "The server log says what is wrong.",
            ProblemKind.NOT_READY,
            extra={"checks": failed},
            headers=_NO_STORE,
        )
    return JSONResponse(Ready(status="ready").model_dump(), headers=_NO_STORE)


def _head_of(answer: Response) -> Response:
    """Give the answer of a `GET` as the `HEAD` of it is: its status and headers (`Content-Length` too), no body."""
    return Response(status_code=answer.status_code, headers=dict(answer.headers))


#: the routes that answer `HEAD` as their `GET` does
_HEAD_PROBES = ("/health", "/ready")

_HEAD_ANSWER = {
    "description": "The status and the headers of the `GET`, with no body.",
}


@app.head(
    "/health",
    tags=[TAG_SERVER],
    response_class=Response,
    summary="Health check, headers only",
    responses={200: _HEAD_ANSWER},
)
def health_head() -> Response:
    """Health check as `GET /health` answers it, without a body: for a monitor that probes with `HEAD`."""
    return _head_of(JSONResponse(health().model_dump()))


@app.head(
    "/ready",
    tags=[TAG_SERVER],
    response_class=Response,
    summary="Readiness check, headers only",
    responses={
        200: {**_HEAD_ANSWER, "headers": {"Cache-Control": {"description": "`no-store`", "schema": {"type": "string"}}}}
    },
)
def ready_head(request: Request) -> Response:
    """Readiness check as `GET /ready` answers it, without a body: the 200 or the 503, with `no-store`."""
    try:
        return _head_of(ready())
    except ProblemError as e:
        return _head_of(_problem_of(request, e))


class VersionAnswer(BaseModel):
    """What an instance is: the versions it serves, whether it serves MCP and draws charts, and its limits."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "version": "0.159.0",
                    "api_version": "1",
                    "mcp_enabled": True,
                    "mcp_path": "/mcp/v1",
                    "mcp_alias_path": "/mcp",
                    "plotting": False,
                    "limits": {
                        "max_stations": 100,
                        "max_rows": 500000,
                        "max_stream_rows": 10000000,
                        "max_groups": 50000,
                        "timeout": 60.0,
                        "max_concurrent": 32,
                    },
                }
            ]
        },
    )

    version: str = Field(description="The version of wetterdienst this instance runs, e.g. `0.159.0`.")
    api_version: str = Field(description="The version of the REST API contract, the `v1` of `/api/v1`.")
    mcp_enabled: bool = Field(description="Whether the MCP endpoint is served: it needs the `mcp` extra.")
    mcp_path: str | None = Field(description="The MCP endpoint of the contract version (`/mcp/v1`); null without MCP.")
    mcp_alias_path: str | None = Field(
        description="The MCP endpoint that follows the current version (`/mcp`); null without MCP."
    )
    plotting: bool = Field(
        description="Whether this instance draws charts (`WD_RESTAPI_PLOTTING`, off by default): false means a chart "
        "format of `stations`, `values`, `interpolate` or `summarize` is a 403 `charts-disabled`."
    )
    limits: Limits = Field(description="The limits and the timeout this instance holds requests to.")


@router.get("/version", response_model=VersionAnswer, tags=[TAG_SERVER])
def version() -> VersionAnswer:
    """Get version information, what this instance serves, and the limits it holds requests to.

    `api_version` is the version of the REST API contract the routes are served under
    (`/api/v1/...`; `/api/...` is an alias of the current version), `version` that of wetterdienst.

    `mcp_enabled` is read at request time rather than captured at import: `_mount_mcp` sets it at
    the bottom of this module, after the routes are declared. It is reported here because the
    endpoint is optional -- an instance installed without the `[mcp]` extra has no MCP route --
    and a client has no other way to find out short of probing `/mcp`, which on the streamable-HTTP
    transport means opening a session rather than asking a question. When it is enabled,
    `mcp_path` is the endpoint of the contract version (`/mcp/v1`), the one to configure, and
    `mcp_alias_path` the alias that follows the current version (`/mcp`); both are `null`
    otherwise.

    `plotting` says whether the instance draws charts: `WD_RESTAPI_PLOTTING` (`Settings.restapi_plotting`, off by
    default) is read for every request, as the refusal reads it, so a client learns before it asks for a chart
    (`format=html`, `png`, `jpg`, `svg` or `pdf`) whether it would get the 403 `charts-disabled`.

    `limits` are the limits of this instance, as a request meets them (`WD_RESTAPI_*`): `max_stations`
    and `max_rows` for an answer sent as one body, `max_stream_rows` for one streamed as `ndjson` or
    `csv`, `max_groups` for the groups of `statistics`, and the `timeout` in seconds. A request that passes one is a
    400 problem of the kind `limit-exceeded`, the timeout a 504; 0 means the instance sets none.
    """
    settings = Settings()
    return VersionAnswer(
        version=__version__,
        api_version=API_VERSION,
        mcp_enabled=mcp_enabled,
        mcp_path=MCP_PREFIX if mcp_enabled else None,
        mcp_alias_path=MCP_ALIAS_PREFIX if mcp_enabled else None,
        plotting=settings.restapi_plotting,
        limits=limits_of(settings),
    )


# each endpoint's settings, by the request it takes them from
_ENDPOINT_SETTINGS: tuple[tuple[str, type[BaseModel], type[_AppliedSettings]], ...] = (
    ("values", ValuesRequest, ValuesSettings),
    ("interpolate", RestInterpolationRequest, InterpolationSettings),
    ("summarize", RestSummaryRequest, SummarySettings),
)


@router.get("/settings", response_model=ServerSettings, tags=[TAG_SERVER])
def server_settings(request: Annotated[SettingsRequest, Query()], http_request: Request) -> Response:
    """Get the settings `/api/values`, `/api/interpolate` and `/api/summarize` take, for the query parameters given.

    Each is the server's `WD_TS_*` variable where it sets one, else wetterdienst's default, keyed
    by endpoint and named as the endpoint's query parameters are; the ones an endpoint has no query
    parameter for are the server's alone. `unit_targets` names the unit of every quantity, and
    `station_distance_resolution_factors` the factor of every resolution. Each is the one in effect,
    as a request leaving out every setting gets it: the server's wide shape turns `drop_nulls` off.

    The query parameters are those of the three endpoints' settings, and a parameter given here is
    laid over the server's for each endpoint that takes it, as a request to it giving the parameter
    gets it: `humanize`, `convert_units` and `unit_targets` for all three, `min_gain_of_value_pairs`
    and `num_additional_stations` for `interpolate` and `summarize`. A request's `unit_targets` or
    station distance dict is merged into the server's, an entry it gives winning. A value an
    endpoint refuses is refused here, as that endpoint refuses it. Nothing is stored: the parameters
    apply to this answer alone.
    """
    given = http_request.query_params.keys()
    # a malformed server setting is the app's unhandled 500, which does not read its value back
    Settings()
    # built once for the endpoints no parameter given applies to, as each build reads the
    # environment and the `.env` again
    server = Options()
    reported: dict[str, _AppliedSettings] = {}
    refused: list[str] = []
    for endpoint, taking, applied in _ENDPOINT_SETTINGS:
        # a parameter applies to every endpoint whose request takes it, and to no other
        taken = [name for name in given if name in taking.model_fields]
        try:
            options = _request_options(request, taken, applied) if taken else server
        except HTTPException as e:
            # a value two endpoints refuse is told once
            refused.extend(line for line in str(e.detail).split("\n") if line not in refused)
            continue
        reported[endpoint] = _applied_settings(applied, options)
    if refused:
        raise HTTPException(status_code=400, detail="\n".join(refused))
    content = ServerSettings.model_validate(reported)
    return Response(content=content.model_dump_json(), media_type="application/json")


#: what a route can answer beyond its 200 and the 422 of a malformed request, by the path under `API_PREFIX`. The
#: statuses are the table of `docs/usage/restapi.md`, and `tests/ui/test_openapi_snapshot.py` holds each route to what
#: its handler answers. A route that reads from a provider can answer all that `_failure` does: a 400 for a request
#: it refuses (a limit, a window, an image too large), a 404, a 501 for what this server lacks or does not implement
#: and a 502 for a provider that failed
_DATA_ANSWERS = (400, 404, 501, 502)
#: the routes that draw a chart, which a server that has `WD_RESTAPI_PLOTTING` off refuses with a 403
_CHART_ANSWERS = (*_DATA_ANSWERS, 403)
_ROUTE_ANSWERS: dict[str, tuple[int, ...]] = {
    "version": (),
    "settings": (400,),
    "auth": (404, 501),
    "coverage": (400, 404, 501),
    "providers": (404,),
    "glossary": (),
    "stations": _CHART_ANSWERS,
    "issues": _DATA_ANSWERS,
    "history": _DATA_ANSWERS,
    "values": _CHART_ANSWERS,
    "statistics": _DATA_ANSWERS,
    "interpolate": _CHART_ANSWERS,
    "summarize": _CHART_ANSWERS,
    "alerts": _DATA_ANSWERS,
    "storm-cells": _DATA_ANSWERS,
    "kostra": _DATA_ANSWERS,
    "station-ids": _DATA_ANSWERS,
    "radar/frames": _DATA_ANSWERS,
    "radar/frame": _DATA_ANSWERS,
}
#: what every route under `API_PREFIX` can answer: a `Host` that is not allowed (400), a defect (500), the cap on
#: requests served at once (503) and the request timeout (504), see `ui.middleware`
_EVERY_ROUTE_ANSWERS = (400, 500, 503, 504)
#: the routes outside it that the host check holds to: the index and `robots.txt`; `/health` answers to any host
_HOST_CHECKED_ROUTES = ("/", "/robots.txt")

#: the component each status of a problem is described in, with the text of its title, spelt out so that the
#: document is the same on every Python. The 422 is not here: FastAPI adds it, `_declare_problem_schema` completes it
_PROBLEM_COMPONENTS = {
    400: ("BadRequest", "Bad Request"),
    403: ("Forbidden", "Forbidden"),
    404: ("NotFound", "Not Found"),
    500: ("InternalError", "Internal Server Error"),
    501: ("NotImplemented", "Not Implemented"),
    502: ("BadGateway", "Bad Gateway"),
    503: ("Unavailable", "Service Unavailable"),
    504: ("GatewayTimeout", "Gateway Timeout"),
}

_RETRY_AFTER_HEADER = {
    "Retry-After": {
        "description": "Seconds after which the same request may be made again.",
        "schema": {"type": "integer"},
    }
}


def _problem_components() -> dict[str, dict[str, Any]]:
    """Describe each status a problem is answered with, and the kinds of problem it is, from `PROBLEMS`."""
    problem = {PROBLEM_MEDIA_TYPE: {"schema": {"$ref": "#/components/schemas/Problem"}}}
    components: dict[str, dict[str, Any]] = {}
    for status, (name, title) in _PROBLEM_COMPONENTS.items():
        kinds = "\n".join(
            f"- `{kind.value}`: {spec.description}" for kind, spec in PROBLEMS.items() if spec.status == status
        )
        components[name] = {
            "description": f"{title}. The body is a problem (`Problem`) of one of the kinds:\n\n{kinds}",
            "content": problem,
        }
        if status in RETRY_AFTER_STATUSES:
            components[name]["headers"] = _RETRY_AFTER_HEADER
    return components


def _head_answer_of(status: int) -> dict[str, Any]:
    """Describe the answer of a `HEAD` to a problem: the status and headers of the `GET`'s, and no body."""
    name, title = _PROBLEM_COMPONENTS[status]
    answer: dict[str, Any] = {
        "description": f"{title}, as `GET` answers it, without the body (the problem of the component `{name}`).",
    }
    if status in RETRY_AFTER_STATUSES:
        answer["headers"] = _RETRY_AFTER_HEADER
    return answer


def _declare_problem_schema(schema: dict[str, Any]) -> None:
    """Describe the error body in the schema: the problem of `_problem_response`, and the routes that can answer it.

    FastAPI documents the 422 it adds to every operation with a query as `HTTPValidationError`,
    `{"detail": [ValidationError]}`, which this API no longer answers: its `detail` is text and the
    entries are under `errors`. Changed in place, and the same when it runs again. Each route also lists the statuses it
    can answer beyond its 200 (`_ROUTE_ANSWERS`, `_EVERY_ROUTE_ANSWERS`), each a reference to the component of that
    status, which lists the kinds of problem it is (GH-3065, GH-3129).
    """
    components = schema.setdefault("components", {})
    schemas = components.setdefault("schemas", {})
    schemas.pop("HTTPValidationError", None)
    kinds = ", ".join(f"`{kind.value}`" for kind in PROBLEMS)
    schemas["Problem"] = {
        "title": "Problem",
        "description": "An error, as RFC 9457 describes it (`application/problem+json`).",
        "type": "object",
        "properties": {
            "type": {
                "type": "string",
                "description": f"`urn:wetterdienst:problem:<kind>`, the kind being one of {kinds}. A client "
                "branches on it; the docs list when each is answered.",
            },
            "title": {"type": "string", "description": "The phrase of the status."},
            "status": {"type": "integer", "description": "The HTTP status."},
            "detail": {"type": "string", "description": "The reason, one line for each thing wrong in a request."},
            "instance": {
                "type": "string",
                "description": "`urn:wetterdienst:request:<id>`: the request this problem answers.",
            },
            "request_id": {"type": "string", "description": "The id of the request, also sent as `X-Request-ID`."},
            "errors": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/ValidationError"},
                "description": "The invalid parameters, each with the `loc` of its parameter, of a 422; the `format` "
                "of a `charts-disabled`, with the `formats` the server answers in its `ctx`.",
            },
            "limit": {
                "type": "string",
                "enum": ["stations", "rows", "stream_rows", "groups", "series", "image_points"],
                "description": "Of `limit-exceeded`: the limit the request passes.",
            },
            "maximum": {"type": "integer", "description": "Of `limit-exceeded`: the value of that limit."},
            "requested": {
                "type": "integer",
                "description": "Of `limit-exceeded`: what the request comes to (estimated for the rows).",
            },
            "checks": {
                "type": "array",
                "items": {"type": "string", "enum": list(CHECKS)},
                "description": "Of `not-ready`: the checks of `/ready` that failed.",
            },
        },
        "required": ["type", "title", "status", "detail", "instance", "request_id"],
        "examples": [
            {
                "type": "urn:wetterdienst:problem:request-refused",
                "title": "Bad Request",
                "status": 400,
                "detail": "the interval in timestamp ends before it starts",
                "instance": "urn:wetterdienst:request:4f1f6c5c0f4e4e2b9a1d7c1c0d9b7a11",
                "request_id": "4f1f6c5c0f4e4e2b9a1d7c1c0d9b7a11",
            }
        ],
    }
    components["responses"] = _problem_components()
    for path, item in schema.get("paths", {}).items():
        route = path.removeprefix(API_PREFIX).strip("/") if path.startswith(f"{API_PREFIX}/") else None
        if route is not None:
            answers = {*_EVERY_ROUTE_ANSWERS, *_ROUTE_ANSWERS[route]}
        elif path in _HOST_CHECKED_ROUTES:
            answers = {400}
        elif path == "/ready":
            answers = {503}
        else:
            answers = set()
        for method, operation in item.items():
            responses = operation.get("responses", {})
            if (invalid := responses.get("422")) is not None:
                # the one status that FastAPI adds, kept as it describes it, with the problem as its content
                invalid["content"] = {PROBLEM_MEDIA_TYPE: {"schema": {"$ref": "#/components/schemas/Problem"}}}
            declared = {key: value for key, value in responses.items() if key not in map(str, _PROBLEM_COMPONENTS)}
            declared.update(
                {
                    str(status): (
                        _head_answer_of(status)
                        if method == "head"
                        else {"$ref": f"#/components/responses/{_PROBLEM_COMPONENTS[status][0]}"}
                    )
                    for status in sorted(answers)
                }
            )
            operation["responses"] = declared


def _declare_list_parameters(schema: dict[str, Any]) -> None:
    """Describe a list in a query as one comma-separated value, which is how this API takes one (GH-2561).

    FastAPI documents a list as a repeated key (`?parameters=a&parameters=b`, OpenAPI's `explode`
    default for a query). The contract is the comma-separated list, `?parameters=a,b`, which the
    parameters' descriptions already give and a client generated from the document now sends too:
    `explode: false`. The repeated key is still read, and left out of the document, so that a client
    that sends it keeps working and none is told to.
    """
    for path in schema.get("paths", {}).values():
        for operation in path.values():
            for parameter in operation.get("parameters", []):
                options = parameter.get("schema", {}).get("anyOf", [parameter.get("schema", {})])
                if parameter.get("in") == "query" and any(option.get("type") == "array" for option in options):
                    parameter["style"] = "form"
                    parameter["explode"] = False


def _selection_of(route: APIRoute) -> Selection | None:
    """Give the exclusive parameters of the request model a route takes, if its model has some."""
    for hint in get_type_hints(route.endpoint).values():
        selection = getattr(hint, "selection", None)
        if isinstance(selection, Selection):
            return selection
    return None


def _declare_selections(schema: dict[str, Any]) -> None:
    """State the exclusive parameters of each operation in the document, and an example of each (GH-3134).

    Which parameters a request may not combine is a rule over several query parameters, and OpenAPI 3.1 cannot
    say it of them: `oneOf` is a keyword of one schema, and the one thing that holds a schema for several
    query parameters is one object parameter (`style: form`, `explode: true`), which takes the parameters away from
    the operation, as they are there to a generated client, to the tools of the MCP server and to the check against
    the last release. So the parameters stay as they are, and each operation whose request model has a `Selection`
    says it in the three ways a document can carry:

    - `x-wetterdienst-selection`, an extension of the operation: `exactly_one_of` the groups of parameters,
      `then` the groups that one of them asks for in turn (a point wants a `rank` or a `distance`), and `requires`,
      the parameters that need a group beside them. It is `Selection.document`, the definition the model's
      validator checks the request by;
    - the `description` of each parameter it names, in the words of the refusal (`Selection.sentences`). Only the
      parameter's own `description` is changed, not that of its schema, which a tool of the MCP server is built
      from, so the tools' schemas do not grow;
    - the `examples` of each parameter, one value it takes (`SELECTION_EXAMPLES`), of the type of its
      schema, a list as a list, which `explode: false` has a client write comma-separated. It is `examples`
      and not `example`, which the MCP server copies into the schema of its tool: 745 characters more in the list
      of the tools, which `examples` of the parameter does not.
    """
    # the routes of the router, which `app` includes under the prefix of the version (it holds them as an
    # included router, not as routes), and not the alias, which the document leaves out
    for route in router.routes:
        if not isinstance(route, APIRoute) or not route.include_in_schema:
            continue
        selection = _selection_of(route)
        if selection is None:
            continue
        for method in route.methods or ():
            operation = schema["paths"][f"{API_PREFIX}{route.path}"][method.lower()]
            operation["x-wetterdienst-selection"] = selection.document()
            sentences = selection.sentences()
            for parameter in operation["parameters"]:
                name = parameter["name"]
                if name in sentences:
                    parameter["description"] = " ".join([parameter["description"].rstrip(), *sentences[name]])
                    parameter["examples"] = {"example": {"value": SELECTION_EXAMPLES[name]}}


def _openapi() -> dict[str, Any]:
    """Build the OpenAPI schema, giving each settings query parameter the server's value as its default (GH-2393).

    A settings parameter a request to `/api/values`, `/api/interpolate`, `/api/summarize` or
    `/api/settings` leaves out takes the server's value, but the schema advertised wetterdienst's,
    which a client filling in the defaults then sent, hiding the server's. Each default is now the
    one `/api/settings` reports for the endpoint without parameters, worked out as it does it:
    `_applied_settings` over `Options()`. `drop_nulls` alone is the server's as set, not the one
    in effect that `/api/settings` reports: leaving it out means the value set whatever the shape,
    which decides only whether it applies, so a client that fills it in and asks for the long
    shape on a wide server still drops nulls. A parameter for `/api/settings` takes the value of
    the endpoint it applies to. The request models keep wetterdienst's defaults in Python, which
    the CLI builds its requests with, and FastAPI fills in for a parameter left out, which the
    endpoints do not pass on (`_request_options`).

    A parameter whose request field defaults to None has no schema default and keeps none: the
    radii and the JSON-encoded dicts (`unit_targets`, the station distances). A dict given is
    merged into the server's, so a client leaving it out gets the server's already, and the
    server's whole dict, a unit for every quantity, would be sent back as a request's own were it
    the default; `/api/settings` reports it.

    Built once per process: with the `[mcp]` extra, as the module is imported, by the MCP endpoint,
    whose tools' defaults are then the server's too, and else on the first request for the schema.
    It is kept as FastAPI keeps it, and a recent FastAPI builds it again, reading `Options()`
    anew, only for a route added. A `.env` edited after the build reaches the requests and
    `/api/settings`, which read `Options()` each time, but not the schema, until the server is
    restarted.
    """
    kept = app.openapi_schema
    schema = FastAPI.openapi(app)
    if schema is kept:
        return schema
    # the version of the contract, next to `info.version` which is the package's: an extension of the Info object
    schema["info"]["x-api-version"] = API_VERSION
    _declare_problem_schema(schema)
    _declare_list_parameters(schema)
    _declare_selections(schema)
    try:
        server = Options()
    except Exception:  # noqa: BLE001
        # malformed, which the server refuses to start for, naming each variable without its
        # value (`_RefuseInvalidSettings`). Reached as the module is imported, by the MCP build,
        # which would log the error with the values. Built with wetterdienst's defaults then,
        # and not kept, so that a later call takes the server's
        app.openapi_schema = None
        return schema
    defaults = {
        f"{API_PREFIX}/{endpoint}": {
            field: value
            for field, value in _applied_settings(applied, server).model_dump().items()
            if field in taking.model_fields and taking.model_fields[field].default is not None
        }
        for endpoint, taking, applied in _ENDPOINT_SETTINGS
    }
    defaults[f"{API_PREFIX}/values"]["drop_nulls"] = server.drop_nulls
    # a parameter several endpoints take sets one setting, which each reports alike
    defaults[f"{API_PREFIX}/settings"] = {
        field: value
        for values in defaults.values()
        for field, value in values.items()
        if field in SettingsRequest.model_fields
    }
    for path, values in defaults.items():
        for parameter in schema["paths"][path]["get"]["parameters"]:
            if parameter["name"] not in values:
                continue
            value = values[parameter["name"]]
            if isinstance(value, float) and not math.isfinite(value):
                # JSON has no number for it, and the string `/api/settings` writes is no default of a
                # number: left out, as absent means the server's
                del parameter["schema"]["default"]
            else:
                parameter["schema"]["default"] = value
    return schema


# FastAPI's documented way to extend the schema, which the route serving it calls on the app
# (the assignment replaces a method, which a type checker rejects whatever the right-hand side is)
app.openapi = _openapi  # ty: ignore[invalid-assignment]


# OAuth discovery endpoints. The MCP server (`/mcp/v1`, and `/mcp` as its alias) is open (no auth),
# so MCP clients such as Claude Desktop must receive a 404 here to conclude "no authorization
# server" and connect anonymously; a 200 (e.g. from a catch-all serving HTML) makes them attempt --
# and fail -- Dynamic Client Registration. FastAPI already 404s unknown paths (including the
# resource-specific sub-paths like `.../oauth-protected-resource/mcp/v1`, which RFC 9728 derives
# from the endpoint's path), but declaring these explicitly documents the no-auth contract and
# keeps it correct if a static/SPA catch-all is ever mounted ahead of these routes.
# `include_in_schema=False` keeps them out of the OpenAPI schema so they do not become MCP tools.
def oauth_metadata_not_found() -> None:
    """Return 404 for OAuth discovery so the open MCP server is treated as no-auth."""
    raise HTTPException(status_code=404, detail="Not Found")


for _discovery in ("oauth-authorization-server", "oauth-protected-resource"):
    # the bare document, then the one for each MCP endpoint, as a client derives it from the URL it was given
    for _resource in ("", MCP_PREFIX, MCP_ALIAS_PREFIX):
        app.get(f"/.well-known/{_discovery}{_resource}", include_in_schema=False)(oauth_metadata_not_found)


_VALIDATOR_HEADERS = {
    "ETag": {
        "description": "A weak tag of the body without the time it was made (`retrieved_at`): send it back as "
        "`If-None-Match` to be answered with a 304 while the answer is the same.",
        "schema": {"type": "string"},
    },
    "Cache-Control": {
        "description": "How long the answer may be reused without asking again, `public, max-age=<seconds>`.",
        "schema": {"type": "string"},
    },
}
_LAST_MODIFIED_HEADER = {
    "Last-Modified": {
        "description": "When the server, which these answers change with, last changed (it started, or its `.env` "
        "did): send it back as `If-Modified-Since` where there is no `ETag` to send.",
        "schema": {"type": "string", "format": "http-date"},
    }
}


def _revalidatable(*, last_modified: bool) -> dict[int | str, dict[str, Any]]:
    """Describe the cache headers of a route that answers `If-None-Match`, with the 304 it answers (GH-3134)."""
    headers = {**_VALIDATOR_HEADERS, **(_LAST_MODIFIED_HEADER if last_modified else {})}
    return {
        200: {"headers": headers},
        304: {
            "description": "Not Modified: the copy the client holds is still the answer, apart from its "
            "`retrieved_at`. There is no body; the headers are those of the 200 that say how it is cached.",
            "headers": headers,
        },
    }


def _catalogue_answer(request: Request, content: str) -> Response:
    """Answer with a catalogue document, to be kept and asked about again, or with the 304 where it is held."""
    return cached_json(request, content, cache_control=CATALOGUE_CACHE_CONTROL, last_modified=settings_changed_at())


def _resolve_listed_network(provider: str, network: str, what: str) -> type[TimeseriesRequest] | StandaloneRequest:
    """Resolve the network `/api/auth` and `/api/coverage` are asked about, telling why one does not resolve.

    A provider or network that is not listed is a 404 pointing at the listing. A network whose
    optional extra is not installed is not that: it is listed, and this deployment lacks what it
    needs, so it is the 501 the data routes answer (`_dependency_missing_on_the_server`). Any other
    `ImportError` is not that either: the network is listed and the package is there, so a module
    that fails to import is a defect or a broken install, and it is let through as the 500 the data
    routes answer, logged with its traceback, rather than told as a network that does not exist (GH-2800).
    """
    try:
        return resolve_network(provider, network)
    except MissingDependencyError as e:
        raise _dependency_missing_on_the_server(e, f"{what} {provider}/{network}") from e
    except ApiNotFoundError as e:
        raise ProblemError(
            404, f"Choose provider and network from {app.url_path_for('providers')}", ProblemKind.UNKNOWN_NETWORK
        ) from e


@router.get("/auth", response_model=AuthAnswer, tags=[TAG_CATALOGUE])
def auth(
    request: Annotated[AuthRequest, Query()],
) -> AuthAnswer:
    """Check whether the credentials for an auth-required provider are present and valid.

    Returns `{"provider": ..., "network": ..., "auth": bool, "configured": bool, "valid": bool | null}`.
    For providers that do not require authentication, `auth` is false and `configured`/`valid` are true.
    `configured` reflects whether credentials are present (false as well while the settings are invalid);
    `valid` whether a probe request showed them accepted (true) or rejected (false). It is null when
    the probe could not tell (no network, a timeout, a rate limit, an outage of the provider): that is
    not a rejection, so treat null as unknown.
    `valid` is false whenever `configured` is false (a probe cannot be performed without credentials).

    This is the one call that probes the provider, for the one network asked about: one attempt that
    gives up after a few seconds. The answer may be up to a minute old: the provider is probed at most
    once a minute per network (5 seconds after a `valid` of null). `/api/providers` does not probe, so
    ask here whether the credentials of a network it lists as `configured` are accepted. The MCP tool
    and the CLI command (`wetterdienst auth`) are this call.
    """
    provider, network = request.provider, request.network

    api = _resolve_listed_network(str(provider), str(network), "check the credentials of")

    return get_auth(api, provider, network)


# What `/api/coverage` answers is what `TimeseriesRequest.discover()` builds, described by the `Coverage*` models of
# `wetterdienst.model.metadata` and the two below. The answer is still sent as `discover()` returns it, so the models
# only describe it. It is one answer (the resolutions of the network asked about, GH-3996), so the document types it
# as one object, which a client generator can follow; the list of every provider and its networks is `/api/providers`.


# The datasets and resolutions as the route describes them. They are `CoverageDataset` and `CoverageResolution` of
# `wetterdienst.model.metadata` but for the extent of a dataset: `discover()` gives it as a plain dict (`ExtentDict`,
# so that what its annotation says is what it holds), and the schema of the answer names the one `Extent` of
# `/api/providers`, so that a client generator sees one type (GH-3456)
@with_config(ConfigDict(extra="forbid"))
class CoverageDataset(TypedDict):
    """A dataset of a resolution."""

    description: str | None
    parameters: list[CoverageParameter]
    extent: Extent


@with_config(ConfigDict(extra="forbid"))
class CoverageResolution(TypedDict):
    """A resolution of a network."""

    description: str | None
    datasets: dict[str, CoverageDataset]


# the answer: the resolutions the network has, which a filter that matches none of leaves out
CoverageResolutions = dict[Resolution, CoverageResolution]


@router.get(
    "/coverage",
    response_model=CoverageResolutions,
    tags=[TAG_CATALOGUE],
    responses=_revalidatable(last_modified=True),
)
def coverage(
    request: Annotated[CoverageRequest, Query()],
    http_request: Request,
) -> Response:
    """List the resolutions, datasets and parameters of one network.

    `provider` and `network` are required (e.g. provider="dwd", network="observation"); `providers` lists the
    providers and their networks, with whether each needs credentials and has them (`configured`). Narrow the
    answer with resolutions=... or datasets=... (e.g. datasets="climate_summary") to discover parameter names. It
    is keyed by resolution, then `datasets`, then each dataset's `parameters`. Nothing is downloaded, so it answers
    at once. A standalone network (`dwd/radar`, `dwd/alerts`, `dwd/storm_cells`) has none: a 404.

    Each dataset has its `extent` (where its stations are: `scope`, `continents`, `bbox`, and `country_codes` for a
    regional one): the dataset's own where it is narrower than its network's, else the network's. Whether the
    network needs credentials and has them is `auth` and `configured` of `providers`, and whether the provider
    accepts them is `auth`'s.

    `unit` of a parameter is the unit its `values` come back in when the request gives no `unit_targets` or
    `convert_units`, the one `glossary` gives for its `unit_type` (`degree_celsius`, never Kelvin; `percent`
    for a percentage). `unit_source` is the unit the provider publishes it in, which the values come in with
    `convert_units=false`; it is there only where it differs from `unit`, and absent means the same. This takes no
    options: a `unit_targets` of your own changes what `values` return, not this answer.

    `aggregation` of a parameter is what its value is relative to its interval: `mean`, `max`, `min`, `sum` and the
    others of `glossary`, or `instant` for a single reading, which the provider declares for a plain name where its
    source states it. `timestamp_position` is where its timestamp sits in the row's interval: `instant`
    (the timestamp is when the value was observed), `start`, `end` or `middle` of it. Both are always there, and `null`
    means the source does not state it: not a reading, not a mean.
    """
    provider, network = request.provider, request.network

    # `provider=` is as good as none, as it is for the MCP tool and the command (GH-3996)
    if not provider or not network:
        raise HTTPException(status_code=400, detail=coverage_needs_a_network(app.url_path_for("providers")))

    api = _resolve_listed_network(provider, network, "list the coverage of")

    # Standalone networks (e.g. dwd/radar, dwd/alerts) have no metadata model and thus no per-network
    # discover(); report that cleanly instead of raising an uncaught AttributeError (HTTP 500).
    if not issubclass(api, TimeseriesRequest):
        raise HTTPException(
            status_code=404,
            detail=f"Coverage is not available for provider '{provider}' and network '{network}'.",
        )

    cov = api.discover(
        resolutions=request.resolutions,
        datasets=request.datasets,
    )

    if is_tool_request(http_request.scope):
        # an assistant reads the answer in its context: cut to the budget, with a note in its first `description`
        # (GH-4024); a JSON answer reaches the client as its body alone, so no header would
        cov, _ = fit_coverage(cov)
    return _catalogue_answer(http_request, json.dumps(cov, indent=4 if request.pretty else None))


@router.get(
    "/providers", response_model=ProvidersAnswer, tags=[TAG_CATALOGUE], responses=_revalidatable(last_modified=True)
)
def providers(
    request: Annotated[ProvidersRequest, Query()],
    http_request: Request,
) -> Response:
    """List the providers and their networks, and describe what each provider is: name, country, licence, credit line.

    For every provider, or the one named with `provider`: the names it goes by, the country of the agency
    that runs it (`country_code` is the ISO 3166-1 alpha-2 code; it is the operator's country, not the extent
    of its data), the terms it publishes its data under (`license`, null where it states none) and the credit
    line to cite (`attribution`; a network's `copyright` is the rights holder's notice, for information), and its
    networks, each with its `kind`, its `extent` (where its stations are: `scope`, `continents`,
    `country_codes`, `bbox`), source `url`, whether it needs credentials (`auth`) and has them (`configured`),
    whether a request has to give a date (`date_required`) and its number of `parameters`.

    `kind` is `observation`, `forecast` or `derived` for a timeseries network, which has stations and values
    (every network but three); `radar`, `alerts` and `storm_cells` are standalone (`dwd/radar`, `dwd/alerts`,
    `dwd/storm_cells`): the other
    endpoints answer 404 for them. `configured` says whether the credentials of a network that needs them are
    present; whether the provider accepts them is not checked here, `/api/auth` (the MCP `auth` tool) does, for
    one network.

    Nothing is downloaded and no credential is probed, so it answers at once. The resolutions, datasets and
    parameters of one network are `coverage`'s.
    """
    begin_response()

    try:
        answer = get_providers(request.provider)
    except ApiNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"{e} Use {app.url_path_for('providers')} to list the providers.",
        ) from e
    content = answer.model_dump_json(indent=4 if request.pretty else None)
    return cached_json(
        http_request,
        content,
        cache_control=CATALOGUE_CACHE_CONTROL,
        last_modified=settings_changed_at(),
        ignoring=[answer.metadata.retrieved_at],
        headers=catalogue_headers(answer.metadata),
    )


@router.get(
    "/glossary",
    response_model=list[GlossaryEntry],
    tags=[TAG_CATALOGUE],
    responses=_revalidatable(last_modified=True),
)
def glossary(
    request: Annotated[GlossaryRequest, Query()],
    http_request: Request,
    response: Response,
) -> Response | list[GlossaryEntry]:
    """Look up what a parameter measures and which unit it is returned in.

    Filter with parameter="radiation" to match names containing that text, or
    unit_type="temperature" for every parameter of one quantity. Both can be combined. Use limit to
    cap the number of entries: the vocabulary runs to several hundred parameters, so an unfiltered call is a
    large response and a broad filter can still be a wide one (parameter="temperature" matches
    nearly two hundred).

    These are the parameters the networks offer. The quality marks of the sources (`quality`, `quality_wind`, ...)
    are not parameters and are not listed: they come back in the `quality_flags` column of the values, which the
    quality-flags page of the documentation explains.

    This complements coverage: coverage says which parameters a given provider offers, this says
    what any of them means. The unit reported is the one a values request would actually return,
    including any `unit_targets` option override.

    `aggregation` is what the name says the value is relative to its interval (`mean`, `max`, `min`, `sum`, `count`,
    ...), `null` for a plain name that states none. It is the canonical value: `coverage` has the one of each
    provider and the `timestamp_position`, which the glossary does not know.
    """
    # a malformed server setting is the app's unhandled 500, as for the data endpoints
    Settings()

    entries = get_glossary(parameter=request.parameter, unit_type=request.unit_type, limit=request.limit)
    checked = validators(
        http_request,
        json.dumps(jsonable_encoder(entries)),
        cache_control=CATALOGUE_CACHE_CONTROL,
        last_modified=settings_changed_at(),
    )
    if checked.matched:
        return checked.not_modified()
    response.headers.update(checked.headers)
    return entries


def _get_timeseries_api(provider: str, network: str, *, history: bool = False) -> type[TimeseriesRequest]:
    """Get the API of a network the timeseries endpoints serve, refusing one they cannot with a 404.

    A standalone network (dwd/radar, dwd/alerts, dwd/storm_cells) or, with `history`, a network without station
    history has nothing to answer these with, as a provider or network that does not exist.
    """
    try:
        return check_timeseries_api(resolve_network(provider, network), provider, network, history=history)
    except ApiNotFoundError as e:
        msg = f"{e} Use {app.url_path_for('providers')} to discover available providers and networks."
        log.info(f"Refused a provider and network without an API for the request: {msg}")
        raise ProblemError(404, msg, ProblemKind.UNKNOWN_NETWORK) from e
    except NotImplementedError as e:
        # a network without station history: the server does not implement it, as `failure_status` says (GH-3065)
        raise _failure(e, _NoRequestModel(), "serve the station history") from e


#: the media types `format=csv` and `format=ndjson` of `stations` and `values` are sent as, which are streamed
_STREAM_RESPONSES: dict[int | str, dict[str, Any]] = {
    200: {
        "content": {
            NDJSON_MEDIA_TYPE: {
                "schema": {"type": "string"},
                "example": '{"metadata":{...}}\n{"station_id":"01048","...":"..."}\n{"end":{"counts":{}}}\n',
            },
            "text/csv": {"schema": {"type": "string"}},
        }
    }
}


def _check_values_limits(
    stations: StationsResult,
    limits: Limits,
    *,
    streamed: bool,
    chooses: bool = False,
    holds: bool = False,
    one_body: bool = False,
) -> None:
    """Refuse a values request that reads too many stations or would return too many rows, before any download.

    Counted from the selection of stations, which the server holds already; the rows are an estimate and an upper
    bound (`ui.limits`). A request that `chooses` rows with `first` or a `filter` is held to what it reads, not to what
    it sends: it may read up to the stream limit, whatever its format, and what is sent is held to the limit of its
    format after (`check_chosen_rows`). A request that `holds` every row it reads (a `sort` with neither) is told that a
    stream does not help it. `one_body` is a request whose answer is one body (`values`): what it reads is held to the
    larger of `rows` and `stream_rows`, so a server that sets the stream limit below `rows` does not refuse what the
    request without a `filter` is answered (0 for either is no limit); `statistics` reads under `stream_rows` alone.
    """
    check_station_count(
        selected_station_count(stations),
        limits,
        by_region=stations._stations_filter is StationsFilter.BY_REGION,  # noqa: SLF001
    )
    if one_body and chooses and not streamed:
        if limits.max_rows and limits.max_stream_rows:
            widest = max(limits.max_rows, limits.max_stream_rows)
            check_rows(estimate_rows(stations), limits, streamed=True, reads=True, read_maximum=widest)
        return
    reads_streamed = streamed or chooses
    if limits.max_stream_rows if reads_streamed else limits.max_rows:
        check_rows(estimate_rows(stations), limits, streamed=reads_streamed, holds=holds, reads=chooses)


def _geo_limit_check(limits: Limits) -> Callable[[TimeseriesRequest], None]:
    """Give the check of `interpolate` and `summarize`: the readings of the window, for each parameter, at one point."""

    def check(request: TimeseriesRequest) -> None:
        if limits.max_rows:
            rows = estimate_point_rows(
                cast("Sequence[ParameterModel]", request.parameters),
                cast("dt.datetime | None", request.start),
                cast("dt.datetime | None", request.end),
            )
            check_point_rows(rows, limits)

    return check


def _geo_reach_check(limits: Limits, distance: str) -> Callable[[int], None]:
    """Give the check of `interpolate` and `summarize` of the stations within the radius around the point.

    `distance` is the name of the field that sets the radius of the endpoint, which a refusal names.
    """

    def check(count: int) -> None:
        check_stations_in_reach(count, limits, distance=distance)

    return check


def _is_streamed(request: ValuesRequest, http_request: Request) -> bool:
    """Tell whether a values request is answered as a stream: ndjson and csv.

    ndjson is refused with `with_stations`. An MCP tool's request is never streamed: a tool answers one body, held to
    `rows` in every format (GH-3464).
    """
    if request.format == "ndjson":
        if (refusal := ndjson_refusal(request)) is not None:
            raise ProblemError(400, refusal)
        return not is_tool_request(http_request.scope)
    return request.format == "csv" and not is_tool_request(http_request.scope)


def _stream_headers(metadata: ResponseMetadata) -> dict[str, str]:
    """Give the headers of a stream: those of the `metadata` block, but the rows, which are not known as it begins."""
    return {name: value for name, value in response_headers(metadata).items() if name != "X-Wetterdienst-Rows"}


def _stream_failure(request: BaseModel, what: str) -> Callable[[Exception], dict[str, Any]]:
    """Give what turns an exception after a stream began into its problem: logged and told as any failure is."""
    request_id = current_request_id() or ""

    def fail(e: Exception) -> dict[str, Any]:
        error = _failure(e, request, what)
        return problem_body(
            error.status_code, str(error.detail), kind_of(error), request_id, extra=getattr(error, "extra", None)
        )

    return fail


def _stream_response(
    chunks: Iterator[bytes], media_type: str, metadata: ResponseMetadata, *, ndjson: bool
) -> StreamingResponse:
    """Answer with the chunks of a stream, ending it with the error of a timeout where the format can say it."""
    request_id = current_request_id() or ""
    seconds = request_timeout()

    def on_timeout() -> bytes | None:
        log.warning(f"Request {request_id} timed out after {seconds:g} seconds while it was streamed.")
        if not ndjson:
            return None
        problem = problem_body(504, timeout_detail(seconds or 0), ProblemKind.REQUEST_TIMEOUT, request_id)
        return ndjson_line({"error": problem})

    return stream_response(
        chunks,
        media_type,
        _stream_headers(metadata),
        context=contextvars.copy_context(),
        timeout=seconds,
        on_timeout=on_timeout,
    )


def _stream_end(stations: int, rows: int, search: Callable[[], dict[str, Any]] | None = None) -> dict[str, Any]:
    """Give the `end` line of a stream: what was sent, and every warning raised while it was.

    `search` gives what the row options searched where the stream has them: it is known only at the end, so the line
    that ends the stream carries it, as it carries the warnings.
    """
    # the search first: it may say that `max_rows` cut the answer, a warning the line carries
    report = search() if search is not None else None
    return ndjson_end(stations, rows, recorded_warnings(), report)


def _stream_stations(
    stations: StationsResult, request: StationsRequest, metadata: ResponseMetadata
) -> StreamingResponse:
    """Stream a listing of stations, a batch of rows at a time (`ui.streaming`)."""
    frames = frames_in_batches(stations.df)
    if request.format == "ndjson":
        chunks = ndjson_stream(
            ndjson_head(metadata),
            frames,
            lambda df: cast("list[dict[str, Any]]", replace(stations, df=df).to_dict()["stations"]),
            _stream_end,
            _stream_failure(request, "stream stations"),
        )
        return _stream_response(chunks, NDJSON_MEDIA_TYPE, metadata, ndjson=True)
    failure = _stream_failure(request, "stream stations")
    chunks = csv_stream(
        frames,
        lambda df, header: replace(stations, df=df).to_csv(include_header=header),
        lambda: stations.df,
        failure,
    )
    return _stream_response(chunks, "text/csv", metadata, ndjson=False)


def _stream_values(
    api: type[TimeseriesRequest],
    request: ValuesRequest,
    settings: Settings,
    options: Options,
    limits: Limits,
) -> StreamingResponse:
    """Stream the values of the stations of a request, one station at a time (`ui.streaming`).

    The stations are selected and the limits checked as for the other formats. The first station is read before the
    response begins, so that a failure on it has its status; one on a later station comes as the last line of
    NDJSON, and cuts a CSV.

    A `sort` or a `first` makes the answer of the whole read: the order is that of all the rows and the groups may span
    stations, so the rows are chosen first, and sent in batches with the report of what was searched in the first line
    (`_stream_chosen_values`). A `filter` alone is applied to each station as it is read, and the report is the last
    line's.
    """
    rows = row_options_of(request)
    if "sort" in rows or "first" in rows:
        return _stream_chosen_values(api, request, settings, options, limits)
    try:
        stations = get_stations(
            api=api, request=request, timestamp=request.timestamp, settings=settings, options=options
        )
        _check_values_limits(stations, limits, streamed=True, chooses="filter" in rows)
        reader = stations.values()
        results = reader.query(**rows)
        first = next(results, None)
    except (AssertionError, HTTPException):
        raise
    except Exception as e:
        raise _failure(e, request, "get values") from e
    results = itertools.chain([first], results) if first is not None else iter(())
    # the block as far as it is known before the first reading: the stations selected, no rows yet
    preview = limit_stations_to_rank(stations)
    # no `data_updated_at`: the newest date of the stations is not known before the last is read, and a list of
    # stations has none
    metadata = response_metadata(preview, request, rows=0)
    searched: list[pl.DataFrame] = []

    cap = request.max_rows
    # the rows the options chose and the rows sent, as frames count them: a wide row counts once, whatever its columns
    counted = {"sent": 0, "matched": 0}

    def frames_of(read: Iterator[ValuesResult]) -> Iterator[pl.DataFrame]:
        # `max_rows` cuts the answer over all stations: what is sent stops at it, the walk goes on to count the rest
        for result in read:
            frame, search = result.df, result.search
            if cap is not None:
                frame = frame.head(max(cap - counted["sent"], 0))
                search = search.with_returned(frame) if search is not None else None
            counted["sent"] += frame.height
            if search is not None:
                counted["matched"] += search.matched_rows or 0
                searched.append(search.series)
            yield frame

    frames = frames_of(results)
    failure = _stream_failure(request, "stream values")

    def search_report() -> dict[str, Any]:
        selection = reader._row_selection(rows, whole=True)  # noqa: SLF001
        assert selection is not None  # noqa: S101 -- search_report is asked for only where row options are given
        window = (stations.start, stations.end)
        read = reader._stations_read  # noqa: SLF001
        report = (
            Searched(
                series=pl.concat(searched),
                selection=selection,
                window=window,
                matched_rows=counted["matched"],
                returned_rows=counted["sent"],
                stations_read=read,
            )
            if searched
            else Searched.nothing(selection, window, read)
        )
        report.warn_if_capped()
        return Search.model_validate(report.to_dict()).model_dump(mode="json")

    if request.format == "ndjson":
        settings_ = _applied_settings(ValuesSettings, options) if request.with_metadata else None
        chunks = ndjson_stream(
            ndjson_head(metadata, settings_),
            frames,
            lambda df: cast("list[dict[str, Any]]", ValuesResult._to_dict(df)),  # noqa: SLF001
            lambda stations_, rows_: _stream_end(stations_, rows_, search_report if rows else None),
            failure,
        )
        return _stream_response(chunks, NDJSON_MEDIA_TYPE, metadata, ndjson=True)
    chunks = csv_stream(
        frames,
        lambda df, header: ValuesResult(stations=stations, df=df).to_csv(include_header=header),
        reader._empty_values_df,  # noqa: SLF001
        failure,
        # the header is written with the first station, which lacks the parameters only a later one has
        schema=None if options.tidy else reader._wide_schema(),  # noqa: SLF001
    )
    return _stream_response(chunks, "text/csv", metadata, ndjson=False)


def _stream_chosen_values(
    api: type[TimeseriesRequest],
    request: ValuesRequest,
    settings: Settings,
    options: Options,
    limits: Limits,
) -> StreamingResponse:
    """Stream the rows a `sort` or a `first` chose: all of them are held before the first is sent.

    So they are held to the limit of one body (`rows`), as the answer of `json` is, and not to the one of a stream: a
    stream does not hold its rows, this one does. Read as the other formats are, under the stream limit where `first`
    is given (a record is searched). The `metadata` block is whole, with the search, as the rows are all known. The
    timeout of the server holds for the whole read here, as no chunk goes out before the last station is read.
    """
    values_ = _values(api=api, request=request, settings=settings, options=options, limits=limits)
    metadata = response_metadata(values_, request)
    frames = frames_in_batches(values_.df)
    failure = _stream_failure(request, "stream values")
    if request.format == "ndjson":
        settings_ = _applied_settings(ValuesSettings, options) if request.with_metadata else None
        chunks = ndjson_stream(
            ndjson_head(metadata, settings_),
            frames,
            lambda df: cast("list[dict[str, Any]]", ValuesResult._to_dict(df)),  # noqa: SLF001
            _stream_end,
            failure,
        )
        return _stream_response(chunks, NDJSON_MEDIA_TYPE, metadata, ndjson=True)
    chunks = csv_stream(
        frames,
        lambda df, header: ValuesResult(stations=values_.stations, df=df).to_csv(include_header=header),
        lambda: values_.df,
        failure,
    )
    return _stream_response(chunks, "text/csv", metadata, ndjson=False)


# response models for the different formats are
# - _StationsWithMetadataDict for json
# - _StationsWithMetadataOgcFeatureCollection for geojson
# - str for csv
@router.get(
    "/stations",
    response_model=_StationsWithMetadataDict | _StationsWithMetadataOgcFeatureCollection | str,
    responses=_STREAM_RESPONSES,
    tags=[TAG_STATIONS],
)
def stations(
    request: Annotated[StationsRequest, Query()],
    http_request: Request,
) -> Response:
    """Find weather stations and their `station_id` (step 1 of the station -> values workflow).

    Requires provider, network and parameters (e.g. provider="dwd", network="observation",
    parameters="daily/kl"), and exactly one way of selecting stations: `name` for a place (e.g.
    name="Hamburg Fuhlsbüttel", optionally with `rank` for how many matches), `region` for every station
    the source lists under a state or province (region="Hamburg", offshore stations included), `stations` ids,
    lat/lon with `rank` or `distance`, a bounding box, or
    all=true for the full list. `name` gives the best five matches unless `rank` says otherwise.
    Returns station metadata including `station_id`, which you pass to `values`.

    A `timestamp`, a date or an interval as for `values`, lists only the stations whose record
    overlaps it, so the nearest stations are not ones that closed decades ago. An id of `stations`
    the network has no station for is left out of the list, which is then empty or shorter, and
    named in a warning of the `metadata` block and in the server's log; an empty list is a 200, not an error.
    """
    _refuse_disabled_chart(request)
    begin_response()
    _refuse_oversized_chart(request)

    api = _get_timeseries_api(request.provider, request.network)

    # outside the handler below: nothing of the caller's reaches these settings, so a malformed
    # server setting is the app's unhandled 500, which does not read its value back
    settings = Settings()
    # a buffer out of range is the request's 400
    options = _request_options(request, http_request.query_params.keys(), StationsSettings)
    try:
        stations_ = get_stations(
            api=api,
            request=request,
            timestamp=request.timestamp,
            settings=settings,
            options=options,
        )
    except AssertionError:
        # a request its model should have refused reached the lookup: our bug, which FastAPI answers
        # as a 500, not the caller's to fix
        raise
    except Exception as e:
        raise _failure(e, request, "get stations") from e

    # a window leaves out the stations that cannot have a reading in it, before a rank keeps the N
    # closest of those that can; a rank filter keeps all stations in the frame, as it is applied
    # lazily during value collection, and a plain listing returns just the N closest asked for
    stations_ = limit_stations_to_rank(limit_stations_to_window(stations_))

    # a tool's request is answered as one body in every format, held to `rows` (GH-3464)
    streamed = request.format in STREAM_FORMATS and not is_tool_request(http_request.scope)
    check_rows(stations_.df.height, limits_of(settings), streamed=streamed)

    metadata = response_metadata(stations_, request)
    if streamed:
        return _stream_stations(stations_, request, metadata)
    content = render_stations(stations_, request, max_side=_MAX_IMAGE_SIDE, metadata=metadata)
    if is_tool_request(http_request.scope):
        # an assistant reads the answer in its context: cut to the budget, with a note (GH-4022)
        content, metadata = fit_stations(
            stations_,
            request,
            content,
            metadata,
            lambda cut, block, asked: render_stations(cut, asked, max_side=_MAX_IMAGE_SIDE, metadata=block),
        )

    return _answer(content, request.format, metadata)


@router.get("/station-ids", response_model=_StationIdsWithMetadataDict | str, tags=[TAG_STATIONS])
def station_ids(
    request: Annotated[StationIdsRequest, Query()],
    http_request: Request,
) -> Response:
    """Find one WMO number, WIGOS identifier or ICAO code at every provider that lists stations with it.

    Pass `wmo_id`, `wigos_id` or `icao_id` (one or several, comma-separated, at least one) and get one row for
    each station that carries one of them, at every network that publishes the id with its stations (the
    `searched` list of the `metadata` block names them): `provider`, `network`, the `resolution` and `dataset` of the
    station list it comes from (another dataset of the network may list other stations), `station_id` (what you pass
    to `values`), `name`, `latitude`, `longitude`, `elevation`, `wmo_id`, `wigos_id`, `icao_id`, and `matched_by`
    with `match`. One WMO number can sit on several stations of one provider (NOAA GHCN has up to four), so the
    answer is a list.

    The ids are equivalent: the WIGOS identifier `0-20000-0-10381` and the WMO number `10381` find each other, and
    an ICAO code also searches the WMO numbers of the stations it finds, so `icao_id=EDDH` finds Hamburg's DWD
    station `01975` and NOAA GHCN `GM000010147`, which list no ICAO code. `matched_by` says which id of the station
    matched (`wmo_id`, `wigos_id` or `icao_id`), and `match` whether it was the id asked for (`direct`) or one
    equivalent to it (`equivalent`).

    Every network that declares id columns is asked, with no narrowing by region. The first search reads their station
    lists, about 30 MB: it takes about 9 s on a good connection and longer on a slow one or when a provider is slow;
    the same search again takes about a second, from the server's cache. Do not repeat it within a conversation. A
    network that cannot be read is left out and named in `warnings` (`network-failed`) and in `searched`, and keyed
    networks without credentials are named in a warning too (`network-not-configured`), and one that answers 429 is
    named with the wait it asks for (`network-rate-limited`); the others answer. If every network that was asked
    fails it is a 502 and no answer, and if every one failed or was rate-limited, with at least one 429, it is the
    503 of a provider's rate limit with `Retry-After`, since an outage is no station that does not exist. A
    station of `noaa/ghcn` that has no data file is left out. No row means no listed station has the id, not an error.
    A tool's answer is cut to 40,000 characters, with an `answer-truncated` warning: ask for fewer ids.
    """
    begin_response()

    # outside the handler below, as for `/api/stations`
    settings = Settings()
    try:
        result = find_stations_by_id(
            wmo_id=request.wmo_id, wigos_id=request.wigos_id, icao_id=request.icao_id, settings=settings
        )
    except AssertionError:
        raise
    except Exception as e:
        raise _failure(e, request, "find stations by id") from e

    content, metadata = render_station_ids(result, request.format, pretty=request.pretty)
    if is_tool_request(http_request.scope):
        # an assistant reads the answer in its context: cut to the budget, with a note (GH-4022)
        content, metadata = fit_station_ids(
            result,
            request.format,
            content,
            metadata,
            lambda cut: render_station_ids(cut, request.format, pretty=request.pretty),
        )
    return Response(
        content=content,
        media_type=_MEDIA_TYPES.get(request.format, "application/json"),
        headers=station_ids_headers(metadata),
    )


@router.get("/issues", response_model=_IssuesWithMetadataDict, tags=[TAG_STATIONS])
def issues(
    request: Annotated[IssuesRequest, Query()],
) -> Response:
    """Return available issue datetimes for a provider/network/station combination.

    Currently supported: provider=dwd, network=mosmix|dmo|swsmos. `dataset` names the product whose runs are
    listed: MOSMIX large (default), small or snow, DMO icon (default) or icon_eu.
    """
    begin_response()

    try:
        api = resolve_network(request.provider, request.network)
    except ApiNotFoundError as e:
        msg = f"{e} Use {app.url_path_for('providers')} to discover available providers and networks."
        log.info(f"Refused a provider and network without an API for the request: {msg}")
        raise ProblemError(404, msg, ProblemKind.UNKNOWN_NETWORK) from e

    # outside the handler below, as for `/api/stations`
    settings = Settings()
    try:
        issue_list = get_issues(api=api, request=request, settings=settings)
    except Exception as e:
        raise _failure(e, request, "get issues") from e

    metadata = issues_metadata(api, request, issue_list)
    return _answer(render_issues(issue_list, metadata), "json", metadata)


# response models for the different formats are
# - _ValuesWithSettingsDict for json
# - _ValuesWithSettingsOgcFeatureCollection for geojson
# - str for csv
@router.get(
    "/values",
    response_model=_ValuesWithSettingsDict | _ValuesWithSettingsOgcFeatureCollection | str,
    responses=_STREAM_RESPONSES,
    tags=[TAG_VALUES],
)
def values(
    request: Annotated[ValuesRequest, Query()],
    http_request: Request,
) -> Response:
    """Get measured values for station(s) (step 2 of the station -> values workflow).

    Requires provider, network, parameters and exactly one station selection, as for `stations`,
    except that a `name` selects its one best match, where `stations` lists the best five; `rank`
    asks for more. A window without readings is a 200 with an empty `values`, not an error.
    Use parameters as "resolution/dataset/parameter" (e.g.
    "daily/climate_summary/temperature_air_mean_2m") to keep the response small, and `stations` with
    an id from `stations` (e.g. stations="01975"). `periods` is optional and provider-specific --
    "recent" for dwd/observation, while a provider that publishes under a single period rejects any
    other one. In the JSON of shape="long", the default unless the server's WD_TS_SHAPE says
    otherwise, the `values` items are grouped by station, then by
    resolution, dataset and parameter, in timestamp order within each group (unless `filter`, `sort` or `first`
    choose the rows): a parameter's latest timestamp is the last item of its group, not of the array. With
    shape="wide" an item is one timestamp of a station and resolution, with a key per parameter (prefixed with the
    full dataset name, e.g. "climate_summary_", when datasets of more than one name are requested), its
    `_quality_flags` key, no `parameter` key, and a null `dataset` where
    several datasets of its resolution are requested. With format="geojson" the items sit under each
    feature's `values`, keeping their order but not `station_id`; a feature is one resolution and
    dataset of one station (one resolution in the wide shape), so a station can have several. Do not
    re-request in other formats.

    To find a record or a rare value, have the server choose the rows instead of reading the series:
    `sort=value&first=1` is the lowest value of each station in the window (`sort=-value` the highest),
    `filter=value<=-20,month=12` the readings at or below -20 in a December. An extreme can be a faulty reading:
    read its `quality_flags`, ask `first=3`, or filter the sign (`value>=0` for a flow). A tie can be many rows
    (every dry day is 0.0 mm): `max_rows` cuts the answer to its first rows. `metadata.search` says from when to when
    and how many values were searched, so that a record the data lacks is told from one not looked for. To meet two
    parameters at one time (one resolution), name them: `filter=temperature_air_min_2m<0,wind_gust_max>=17.2` is the
    days of frost and strong gusts, with all parameters' rows.

    With `with_metadata`, `metadata.parameters` gives each parameter its `unit`, its `aggregation` (what the value is
    relative to its interval: `mean`, `max`, `sum`, ..., `instant` for a single reading) and its `timestamp_position`
    (where the timestamp sits in the row's interval: `instant`, `start`, `end` or `middle`); `null` in
    either means the source does not state it.
    """
    # a row option given twice is malformed whatever the format: refused first, and it reads nothing
    _refuse_repeated_row_options(http_request)
    _refuse_disabled_chart(request)
    begin_response()
    _refuse_oversized_chart(request)

    api = _get_timeseries_api(request.provider, request.network)

    # outside the handlers: nothing of the caller's reaches the server's settings, so a malformed one
    # is the app's unhandled 500, which does not read its value back
    settings = Settings()
    # a unit target given for a quantity or unit the converter has none for is the request's 400
    options = _request_options(request, http_request.query_params.keys(), ValuesSettings)
    limits = limits_of(settings)

    if _is_streamed(request, http_request):
        return _stream_values(api, request, settings, options, limits)
    values_ = _values(api=api, request=request, settings=settings, options=options, limits=limits)
    tool = is_tool_request(http_request.scope)
    if tool and values_.search is not None:
        # an assistant reads the report inside the budget of its answer: the first series, the totals of all
        values_ = replace(values_, search=replace(values_.search, listed=MAX_TOOL_SERIES))
    if tool and forecast_start.applies(api, request):
        # a forecast without a window, or with one of days around now, starts at now, before the budget counts (GH-4025)
        values_ = forecast_start.forecast_from_now(values_, floor=forecast_start.lower_bound(request))

    metadata = response_metadata(values_, request)
    content = render(values_, request, ValuesSettings, options, max_side=_MAX_IMAGE_SIDE, metadata=metadata)
    if tool:
        # an assistant reads the answer in its context: cut to the budget, with a note (GH-4022)
        content, metadata = fit_values(
            values_,
            request,
            content,
            metadata,
            lambda cut, block, asked: render(
                cut, asked, ValuesSettings, options, max_side=_MAX_IMAGE_SIDE, metadata=block
            ),
        )

    return _answer(content, request.format, metadata)


def _check_statistics_limits(stations: StationsResult, limits: Limits) -> None:
    """Refuse a statistics request that reads too much or names more series than an answer reports, before a download.

    The stations and the readings are held as for a request with `first`: up to the stream limit, whatever the format.
    """
    _check_values_limits(stations, limits, streamed=False, chooses=True)
    check_series_count(selected_station_count(stations) * len(stations.parameters), MAX_REPORTED_SERIES)


def _statistics(
    api: type[TimeseriesRequest],
    request: StatisticsRequest,
    settings: Settings,
    options: Options,
    limits: Limits,
) -> StatisticsResult:
    """Collect the statistics, telling the caller which failures are theirs to fix.

    The sibling of `_values`: the stations are read under the stream limit, as a request that `first` chooses rows of
    is (a record is searched), and the groups kept are held to the limit of one body (`check_chosen_groups`), as soon
    as a station makes them more than that, and not after the last.
    """
    try:
        result = get_statistics(
            api=api,
            request=request,
            settings=settings,
            options=options,
            check=lambda stations_: _check_statistics_limits(stations_, limits),
            held_groups_limit=limits.max_groups or None,
        )
        check_chosen_groups(sum(series.frame.height for series in result.series), limits)
    except GroupsOverLimitError as e:
        check_chosen_groups(e.groups, limits, so_far=True)
        raise
    except (AssertionError, HTTPException):
        raise
    except Exception as e:
        raise _failure(e, request, "get statistics") from e
    return result


# response models for the different formats are
# - _StatisticsWithMetadataDict for json
# - str for csv and ndjson
@router.get(
    "/statistics",
    response_model=_StatisticsWithMetadataDict | str,
    tags=[TAG_VALUES],
)
def statistics(
    request: Annotated[StatisticsRequest, Query()],
    http_request: Request,
) -> Response:
    """Count, average, add up or find the extremes of each station's values per year, month, day or hour.

    Stations and `timestamp` as in `values`; the groups are in `series[].groups`. `aggregate`: up to five of `count`,
    `mean`, `sum`, `min`, `max`, `earliest`, `latest`; `by`: `year`, `month`, `day`, `hour` (UTC). `filter=value<0`
    counts values below 0. A group says how many values it has (`searched`) and should have (`expected`) and is
    `complete` or not: a gap, a year the window cuts or that is not over leaves `mean` and `sum` null unless
    `max_missing` allows it. `having`, `sort`, `first` choose groups (`aggregate=mean&by=year&sort=-mean&first=5`: the
    five warmest years; `per=none` ranks across stations). `over_groups` is the min, max and mean over the complete
    groups. For single readings use `values`. A `min` or `max` can be a faulty reading: leave impossible values out
    with `filter`.
    """
    begin_response()
    _refuse_repeated_row_options(http_request, _STATISTICS_OPTIONS)

    api = _get_timeseries_api(request.provider, request.network)

    # outside the handlers: nothing of the caller's reaches the server's settings
    settings = Settings()
    # the shape is always long, whatever the server's default says
    options = overlay_options(Options(), {"shape": "long"})
    limits = limits_of(settings)

    result = _statistics(api, request, settings, options, limits)
    metadata = statistics_metadata(result, provider=request.provider, network=request.network)
    content, metadata = render_statistics(result, request, metadata=metadata)
    if is_tool_request(http_request.scope):
        # an assistant reads the answer in its context: the first groups that fit, with a note (GH-4022)
        content, metadata = fit_statistics(
            result,
            request.format,
            content,
            metadata,
            lambda cut, block: render_statistics(cut, request, metadata=block),
        )
    return _answer(content, request.format, metadata)


_ROW_OPTIONS = ("filter", "sort", "first", "by", "max_rows")
_JOINED_EXAMPLE = {"filter": "filter=value<=-20,month=12", "having": "having=count>=100,searched<360"}
#: the options of `statistics` that are given once, as the row options are
_STATISTICS_OPTIONS = (
    "aggregate",
    "by",
    "filter",
    "year_start",
    "max_missing",
    "having",
    "sort",
    "first",
    "per",
    "max_rows",
)


def _refuse_repeated_row_options(http_request: Request, names: tuple[str, ...] = _ROW_OPTIONS) -> None:
    """Refuse a row option given more than once: the query would keep one of them and the answer would not say which.

    `filter=value<0&filter=month=1` is the conditions `value<0,month=1` in the grammar, which joins them by a comma;
    a second `sort` or `by` has no such reading. A 422 located at the option, as an option that cannot be read is.
    """
    entries: list[dict[str, Any]] = [
        {
            "type": "repeated",
            "loc": ["query", name],
            "msg": (
                f"`{name}` is given {len(values)} times and a request takes it once: "
                + (
                    f"join the conditions of `{name}` with a comma, as in {_JOINED_EXAMPLE[name]}"
                    if name in {"filter", "having"}
                    else f"give one number to `{name}`"
                    if name in {"first", "max_rows", "year_start", "max_missing"}
                    else f"give one value of `{name}`, columns joined by commas where it takes several"
                )
            ),
            "input": values,
        }
        for name in names
        if len(values := http_request.query_params.getlist(name)) > 1
    ]
    if entries:
        raise ProblemError(422, str(entries[0]["msg"]), ProblemKind.INVALID_PARAMETERS, extra={"errors": entries})


def _request_options(
    request: BaseModel,
    given: Collection[str],
    applied: type[_AppliedSettings | StationsSettings],
) -> Options:
    """Build an endpoint's options from the server's and the fields the request gave.

    `applied` lists the endpoint's settings by the request field that sets each, and `given` names
    the query parameters the request came with. A field is laid over the server's only when given:
    FastAPI fills one the query leaves out with its default, which would hide the `WD_TS_*` variable
    the server sets for the option.

    The server's own options are built first, and outside the handler: one malformed there is the
    unhandled 500, which does not read its value back. Where an error is located would
    not tell, as the request's dicts are merged into the ones the server sets. With the server's
    valid on their own, an error once the request's fields are added is the request's, and is told
    by its field with the value the request gave, not the dict merged from it and the server's.

    """
    server = Options()
    # each option given by the field that sets it
    passed = {
        str(option.validation_alias): (field, value)
        for field, option in applied.model_fields.items()
        # not an option the request has no field for, which the server sets alone
        if field in type(request).model_fields and field in given and (value := getattr(request, field)) is not None
    }
    # one mode for every check, which a `plausibility_<check>` given beside it overrides
    every = getattr(request, "plausibility", None)
    if every is not None and "plausibility" in given:
        passed["plausibility"] = ("plausibility", every)
    try:
        return overlay_options(server, {option: value for option, (_, value) in passed.items()})
    except ValidationError as e:
        problems = e.errors(include_url=False)
        if any(not problem["loc"] or problem["loc"][0] not in passed for problem in problems):
            raise
        lines = []
        for problem in problems:
            field, value = passed[str(problem["loc"][0])]
            # an entry within a dict is the request's, the server's being valid on their own
            input_ = value if len(problem["loc"]) == 1 else problem["input"]
            within = "".join(f"{part}: " for part in problem["loc"][1:])
            # a field validator's ValueError comes with pydantic's prefix, which tells the caller nothing
            message = problem["msg"].removeprefix("Value error, ")
            lines.append(f"Invalid value for '{field}': {within}{message} (got {json.dumps(input_, default=str)})")
        raise HTTPException(status_code=400, detail="\n".join(lines)) from e


def _geo_options(
    request: InterpolationRequest | SummaryRequest,
    given: Collection[str],
    kind: Literal["interpolation", "summary"],
) -> Options:
    """Build the options shared by the interpolation and the summary endpoint.

    `kind` picks the endpoint's settings, which name its request's station distance fields.
    """
    # a distance given for a name that is not a canonical parameter, or a unit target for an
    # unknown quantity or unit, is the request's 400
    return _request_options(request, given, InterpolationSettings if kind == "interpolation" else SummarySettings)


def _refusal_detail(e: Exception, what: str, request: BaseModel | None = None) -> str:
    """Word a refusal for a caller of this API, who passes the window as one `timestamp`.

    A request refuses a window that is missing or ends before it starts in terms of its `start` and
    `end`, and so does `_get_stations_request` for a dataset that is queried by a window and given
    none. A REST or MCP caller cannot pass either. Any other refusal is worded the request's way.
    """
    if isinstance(e, ReversedTimeIntervalError):
        return "the interval in timestamp ends before it starts"
    if isinstance(e, DateRequiredError):
        detail = "timestamp is required for this dataset"
        if any(getattr(request, name, None) is not None for name in ("filter", "sort", "first", "by")):
            # a search of the record asks for a window that spans it, which is the only way to say "everything"
            detail += ": give a window that spans the record, such as timestamp=1883/2026 (a later end is fine)"
        return detail
    if isinstance(e, MissingTimeIntervalError):
        return f"timestamp is required to {what}"
    return str(e)


_UPSTREAM_UNREACHABLE = (
    "The server could not reach the data provider (no network connection). The request was valid; try again later."
)
_UPSTREAM_TIMED_OUT = "The data provider did not answer in time. The request was valid; try again later."
_UPSTREAM_FAILED = (
    "The data provider failed, or sent an answer this server cannot read. The request was valid; try again later."
)


def _upstream_failure(e: UpstreamError, what: str) -> HTTPException:
    """Answer a provider that failed with the status of `failure_status`: 503, 504 or 502, an outage and not a crash.

    Neither the caller's mistake nor a defect of ours: the request was well formed and the same one
    can succeed once the provider is back, which is what these statuses say and a client may retry
    on. A 503 is no connection to the provider (GH-2640), a 504 a provider that did not answer in
    time, a 502 one that failed or sent what the parser does not expect. The message names the
    provider's URL, which is for whoever runs the server, so it goes to the log, and the body
    carries a fixed sentence. An outage is a warning without a traceback to read; a layout the
    parser does not expect (any `UpstreamError` that is no failed download) might be our parser's
    defect, so it is an error with one.
    """
    status = failure_status(e)
    if isinstance(e, ProviderRateLimitError):
        return _quota_exhausted(e, what)
    if isinstance(e, (NoInternetError, DownloadError, StationListingIncompleteError)):
        log.warning(f"Failed to {what}: {e}")
    else:
        log.error(f"Failed to {what}.", exc_info=e)
    detail = {503: _UPSTREAM_UNREACHABLE, 504: _UPSTREAM_TIMED_OUT}.get(status, _UPSTREAM_FAILED)
    if isinstance(e, StationListingIncompleteError):
        # names the directories of DWD's public tree that the lookup went without, and the id the caller asked for:
        # what a 404 hid, and what `file-skipped` tells an answer that has a place for it (GH-3834)
        detail = str(e)
    kind = {503: ProblemKind.UPSTREAM_UNREACHABLE, 504: ProblemKind.UPSTREAM_TIMEOUT}.get(
        status, ProblemKind.UPSTREAM_FAILED
    )
    return ProblemError(status, detail, kind)


def _quota_exhausted(e: ProviderRateLimitError, what: str) -> HTTPException:
    """Answer a provider that limits the rate or whose quota is used up with a 503, `upstream-quota-exhausted`.

    A 429 of any provider is this, not a 502: the request was valid and the key is accepted, only limited for now, so
    it is no rejected credential (a 501) and no failed provider. The same request can succeed once the limit resets,
    which `Retry-After` says (the provider's own wait where it sent one, a minute for a 429 that says none, else
    `QUOTA_RETRY_AFTER_SECONDS` for a quota). The `reason` holds no URL and no key and says to try again later, so the
    body carries it.
    """
    log.warning(f"Failed to {what}: {e}")
    return ProblemError(
        503,
        f"{e.reason.rstrip('.')}. The request was valid.",
        ProblemKind.UPSTREAM_QUOTA_EXHAUSTED,
        headers={"Retry-After": str(e.retry_after or QUOTA_RETRY_AFTER_SECONDS)},
    )


def _server_error(e: Exception) -> HTTPException:
    """Answer a failure that is the server's with a 500 that names its type and nothing else (GH-2767).

    The text of an exception is whatever the library underneath wrote: a cache directory that cannot
    be created names its path, an `OSError` of any kind the file it met, a failed download the URL.
    The caller of an unauthenticated API has no use for the server's file system layout, so the
    body carries a fixed sentence and the exception's class, and the text stays where the traceback
    is, in the server log. The body is the problem of `_problem_response`, with that text as its `detail`.

    Only a defect is this. A provider that failed is a 502, 503 or 504 (`_upstream_failure`), a lack
    of this deployment a 501.
    """
    return ProblemError(
        500,
        f"Internal server error ({type(e).__name__}). The cause is in the server log.",
        ProblemKind.INTERNAL_ERROR,
    )


def _logged_server_error(e: Exception, what: str) -> HTTPException:
    """Log a failure that is not the request's and answer it with the status it deserves: a 501, 502, 503, 504 or 500.

    For the catch-alls past the point where the request has nothing left to refuse: what fails from
    there is the deployment's, the provider's or ours, by the exception's place in the hierarchy
    (`_server_side_failure`), a defect with its traceback in the log and a 500.
    """
    return _server_side_failure(e, _NoRequestModel(), what)


def _configuration_missing_on_the_server(e: ConfigurationError, what: str) -> HTTPException:
    """Report a lack of this deployment that no more specific answer names as a 501, not a crash.

    The message names a setting or a package of the server, which is for whoever runs it, so it moves
    to the log, as it does for a missing dependency or credential (`_dependency_missing_on_the_server`).
    """
    log.error(f"Failed to {what}, this deployment is not configured to serve it: {e}")
    return ProblemError(
        501,
        "This server is not configured to serve the request. The request was valid; ask whoever runs this instance.",
        ProblemKind.NOT_CONFIGURED,
    )


def _not_implemented(e: Exception, what: str) -> HTTPException:
    """Report what this server does not implement, a `NotImplementedError`, as a 501 (`failure_status`, GH-3065).

    The library raises it, with a sentence for the caller, where a network has no station history or no issues to
    list: neither is the caller's mistake and neither is missing from the deployment, the server does not do it.
    """
    log.info(f"Failed to {what}: {e}")
    return ProblemError(501, str(e) or "This server does not implement what the request asks for.")


def _server_side_failure(e: Exception, request: BaseModel, what: str) -> HTTPException:
    """Answer a failure that is not the request's own by its place in the hierarchy (`failure_status`).

    A credential or an optional dependency the server lacks, and what it does not implement, is a 501 (the more
    specific answers say which); a provider that failed is a 502, 503 or 504; anything else is a logged traceback and a
    500 that does not repeat the exception's text (`_server_error`).
    """
    if isinstance(e, MissingDependencyError):
        return _dependency_missing_on_the_server(e, what)
    if isinstance(e, CredentialMissingError):
        return _credential_missing_on_the_server(e, request, what)
    if isinstance(e, CredentialRejectedError):
        return _credential_rejected_on_the_server(e, request, what)
    if isinstance(e, ConfigurationError):
        return _configuration_missing_on_the_server(e, what)
    if isinstance(e, UpstreamError):
        return _upstream_failure(e, what)
    if failure_status(e) == 501:
        return _not_implemented(e, what)
    log.error(f"Failed to {what}.", exc_info=e)
    return _server_error(e)


def _failure(e: Exception, request: BaseModel, what: str) -> HTTPException:
    """Log a failure at the level it deserves and answer it with the status it deserves.

    One decision for every catch-all, made from the exception's place in the `WetterdienstError`
    hierarchy (`failure_status`), which the MCP tools share through this API: a request the caller
    phrased wrong is theirs to fix, so an info line without a traceback and a 400, and a provider,
    network, station or issue that does not exist a 404; the rest is `_server_side_failure`.
    """
    status = _caller_refusal_status(e, request)
    if status is not None:
        detail = _refusal_detail(e, what, request)
        log.info(f"Failed to {what}: {detail}")
        if isinstance(e, NoStationPositionsError):
            return _unplaceable_format(detail, getattr(request, "format", None))
        if isinstance(e, RowSelectionError):
            return _unreadable_option(e, request)
        return HTTPException(status_code=status, detail=detail)
    return _server_side_failure(e, request, what)


def _unplaceable_format(detail: str, fmt: str | None) -> ProblemError:
    """Answer a map of stations none of which has a position as the 422 `invalid-parameters` it is (GH-4206).

    The `format` is the parameter that cannot be served for these stations, so it is the entry of `errors` that
    the kind promises, located as pydantic locates a query parameter. `input` is what was asked for, where the
    request is at hand.
    """
    entry: dict[str, Any] = {"type": "no_positions", "loc": ["query", "format"], "msg": detail}
    if fmt is not None:
        entry["input"] = fmt
    return ProblemError(422, detail, ProblemKind.INVALID_PARAMETERS, extra={"errors": [entry]})


def _unreadable_option(e: RowSelectionError, request: BaseModel) -> ProblemError:
    """Answer a `filter` or `sort` that the request's parameters refuse as the 422 of a text that cannot be read.

    A word that is no parameter's name, or that names several, is known to be wrong only once the request's
    parameters are (GH-4419); it is the same fault as a text that cannot be read, so it is answered the same way: a 422
    `invalid-parameters` whose `errors` locate it at the option, with what was written in `input`.
    """
    entry: dict[str, Any] = {
        "type": "row_selection",
        "loc": ["query", e.option],
        "msg": str(e),
        "input": getattr(request, e.option, None),
        "ctx": {},
    }
    return ProblemError(422, f"{e.option}: {e}", ProblemKind.INVALID_PARAMETERS, extra={"errors": [entry]})


def _values(
    api: type[TimeseriesRequest],
    request: ValuesRequest,
    settings: Settings,
    options: Options,
    limits: Limits,
) -> ValuesResult:
    """Collect values, telling the caller which failures are theirs to fix.

    The sibling of `_geo_values` for the plain values endpoint, and lifted out of the endpoint for
    the same reason: which failure earns which status is a decision of its own, and the endpoint --
    which also assembles a response format, a target and a set of kwargs -- is not where it belongs.
    """
    # a `first` or a `filter` chooses rows from the whole record: read up to the stream limit, held to `rows`. A `sort`
    # alone holds all it reads, so it is held to `rows` for what it reads too (GH-4436)
    chooses = request.first is not None or request.filter is not None
    # told to drop a `sort` only where the `sort` is what holds everything it reads
    holds = not chooses and request.sort is not None
    # what the refusal of the rows chosen says to change: what the request has already is not asked for again
    has = (request.first is not None, request.sort is not None, request.max_rows)
    try:
        values_ = get_values(
            api=api,
            request=request,
            settings=settings,
            options=options,
            check=lambda stations_: _check_values_limits(
                stations_, limits, streamed=False, chooses=chooses, holds=holds, one_body=True
            ),
            held_rows_limit=limits.max_rows if chooses else None,
        )
        if chooses:
            # read under the stream limit, so that a record can be searched; sent under the limit of one body
            check_chosen_rows(values_.df.height, limits, first=has[0], sort=has[1], max_rows=has[2])
    except RowsOverLimitError as e:
        check_chosen_rows(e.rows, limits, so_far=True, first=has[0], sort=has[1], max_rows=has[2])
        raise
    except (AssertionError, HTTPException):
        # a request its model should have refused reached the lookup: our bug, which FastAPI answers
        # as a 500, not the caller's to fix; and a limit that refused the request, which is its 400
        raise
    except Exception as e:
        raise _failure(e, request, "get values") from e
    return values_


def _geo_values(
    get: Callable[..., InterpolatedValuesResult | SummarizedValuesResult],
    api: type[TimeseriesRequest],
    request: InterpolationRequest | SummaryRequest,
    settings: Settings,
    options: Options,
    what: str,
    limits: Limits,
) -> InterpolatedValuesResult | SummarizedValuesResult:
    """Run an interpolation or a summary, telling the caller which failures are theirs to fix.

    Both endpoints answered every failure with a 404, which reads as "no such thing" for a request
    that was understood and simply cannot be served as phrased -- an elevation no station in reach
    can be placed against, a station without a position, a point an interpolation cannot place
    beyond the latitudes UTM covers (a summary converts nothing to UTM), a window that ends before
    it starts, a date or an issue that does not parse. Those are 400s, as `/api/values` answers
    them, and each is logged here as an info line: the caller's to fix, so no traceback of ours. A
    station the lookup does not know, or an issue the source does not list, is a 404, "no such
    thing", as `/api/values` answers an issue. A reader missing on the server is a 501; the same
    decisions in both places, so they are made here rather than twice over.
    """
    distance = (
        "interpolation_station_distance" if isinstance(request, InterpolationRequest) else "summary_station_distance"
    )
    try:
        return get(
            api=api,
            request=request,
            settings=settings,
            options=options,
            check=_geo_limit_check(limits),
            check_reach=_geo_reach_check(limits, distance),
        )
    except (AssertionError, HTTPException):
        # a request its model should have refused reached the lookup: our bug, which FastAPI answers
        # as a 500, not the caller's to fix; and a limit that refused the request, which is its 400
        raise
    except Exception as e:
        raise _failure(e, request, what) from e


# response models for the different formats are
# - _InterpolatedValuesWithSettingsDict for json
# - _InterpolatedValuesWithSettingsOgcFeatureCollection for geojson
# - str for csv
@router.get(
    "/interpolate",
    response_model=_InterpolatedValuesWithSettingsDict | _InterpolatedValuesWithSettingsOgcFeatureCollection | str,
    tags=[TAG_VALUES],
)
def interpolate(
    request: Annotated[RestInterpolationRequest, Query()],
    http_request: Request,
) -> Response:
    """Estimate a value series at a point between stations by spatial interpolation (opt-in; adds inaccuracy).

    Do NOT use this for the weather at a named place (city, town, station) -- that is ALWAYS the
    `stations` -> `values` workflow, even when a specific past date is given (e.g. "the weather in
    Kiel on 26.12.2025": find Kiel's nearest station, then read its values for that date). Only reach
    for interpolate when the user explicitly asks for an interpolated / between-stations estimate, or
    when `stations` -> `values` genuinely finds no station with data near the location. It blends up
    to four surrounding stations for a `latitude`/`longitude` (or reference `station`) that has no
    station of its own, so the result is a modelled estimate, not a measurement. Requires provider,
    network, parameters and a `timestamp`.
    """
    _refuse_disabled_chart(request)
    begin_response()
    _refuse_oversized_chart(request)

    api = _get_timeseries_api(request.provider, request.network)

    # outside the handlers, as for `/api/values`
    settings = Settings()
    options = _geo_options(request, http_request.query_params.keys(), "interpolation")

    values_ = _geo_values(get_interpolate, api, request, settings, options, "interpolate", limits_of(settings))

    metadata = response_metadata(values_, request)
    content = render(values_, request, InterpolationSettings, options, max_side=_MAX_IMAGE_SIDE, metadata=metadata)
    if is_tool_request(http_request.scope):
        # an assistant reads the answer in its context: cut to the budget, with a note (GH-4024)
        content, metadata = fit_values(
            values_,
            request,
            content,
            metadata,
            lambda cut, block, asked: render(
                cut, asked, InterpolationSettings, options, max_side=_MAX_IMAGE_SIDE, metadata=block
            ),
        )

    return _answer(content, request.format, metadata)


# response models for the different formats are
# - _SummarizedValuesWithSettingsDict for json
# - _SummarizedValuesWithSettingsOgcFeatureCollection for geojson
# - str for csv
@router.get(
    "/summarize",
    response_model=_SummarizedValuesWithSettingsDict | _SummarizedValuesWithSettingsOgcFeatureCollection | str,
    tags=[TAG_VALUES],
)
def summarize(
    request: Annotated[RestSummaryRequest, Query()],
    http_request: Request,
) -> Response:
    """Build a value series at a point from the nearest stations with data (opt-in; not a text summary).

    Do NOT use this for the weather at a named place (city, town, station) -- that is ALWAYS the
    `stations` -> `values` workflow, even when a specific past date is given. Despite the name this
    is NOT a plain-language weather summary. Only reach for it when the user explicitly asks for a
    nearest-station estimate at an arbitrary point, or when `stations` -> `values` genuinely finds no
    station with data near the location. Per parameter and date it takes the value of the closest
    station that reported it (the result names the `taken_station_id` and its `distance`), so the
    result may stitch together different stations. Requires provider, network, parameters and a
    `timestamp`.
    """
    _refuse_disabled_chart(request)
    begin_response()
    _refuse_oversized_chart(request)

    api = _get_timeseries_api(request.provider, request.network)

    # outside the handlers, as for `/api/values`
    settings = Settings()
    options = _geo_options(request, http_request.query_params.keys(), "summary")

    values_ = _geo_values(get_summarize, api, request, settings, options, "summarize", limits_of(settings))

    metadata = response_metadata(values_, request)
    content = render(values_, request, SummarySettings, options, max_side=_MAX_IMAGE_SIDE, metadata=metadata)
    if is_tool_request(http_request.scope):
        # an assistant reads the answer in its context: cut to the budget, with a note (GH-4024)
        content, metadata = fit_values(
            values_,
            request,
            content,
            metadata,
            lambda cut, block, asked: render(
                cut, asked, SummarySettings, options, max_side=_MAX_IMAGE_SIDE, metadata=block
            ),
        )

    return _answer(content, request.format, metadata)


@router.get(
    "/history",
    response_model=_HistoryWithMetadataDict,
    tags=[TAG_STATIONS],
    responses=_revalidatable(last_modified=False),
)
def history(
    request: Annotated[HistoryRequest, Query()],
    http_request: Request,
) -> Response:
    """Return a station's metadata history -- how the station itself changed over time (not weather).

    Provides the record of a station's name, position, sensors/devices and data-gap sections across
    its lifetime, for auditing station changes. This is NOT weather or measurement history: for past
    measurements use the stations -> values workflow with a `timestamp` or interval. Requires provider,
    network, parameters and either `stations` ids or all=true.
    """
    begin_response()

    api = _get_timeseries_api(request.provider, request.network, history=True)

    # outside the handler below, as for `/api/stations`
    settings = Settings()
    try:
        stations_ = get_stations(
            api=api,
            request=request,
            timestamp=None,
            settings=settings,
        )
    except AssertionError:
        # a request its model should have refused reached the lookup: our bug, which FastAPI answers
        # as a 500, not the caller's to fix
        raise
    except Exception as e:
        raise _failure(e, request, "get stations for history") from e
    check_station_count(selected_station_count(stations_), limits_of(settings))

    try:
        history_provider = stations_.history()
    except Exception as e:
        # past the station lookup the request has nothing left to refuse: what fails from here on
        # is the server's or the data source's, whatever its type
        raise _logged_server_error(e, "acquire history provider") from e

    try:
        content, metadata = render_history(stations_, history_provider, request)
    except Exception as e:
        raise _logged_server_error(e, "collect station history") from e
    if not metadata.counts.rows or metadata.warnings:
        # an empty history, or one that came with warnings, may be a source that answered nothing for the moment, or
        # ids left out: the next request can give another, so it is not kept (a listing that came back empty is a
        # `file-skipped` warning, a station with no file in a listing that is there is the source's answer)
        return _answer(content, "json", metadata)
    return cached_json(
        http_request,
        content,
        cache_control=HISTORY_CACHE_CONTROL,
        ignoring=[metadata.retrieved_at],
        headers=response_headers(metadata),
    )


@router.get(
    "/alerts",
    response_model=_AlertsWithMetadataDict | _AlertsWithMetadataOgcFeatureCollection | str,
    tags=[TAG_ALERTS],
)
def alerts(
    request: Annotated[AlertsRequest, Query()],
    http_request: Request,
) -> Response:
    """Provide DWD weather alerts (CAP warnings) via restapi.

    Returns the warnings active at the selected time, one entry per alert, with a GeoJSON MultiPolygon geometry.
    Without a place that is every warning of Germany (over 100 KB, more than an assistant can read): pass
    ``latitude`` and ``longitude`` for the warnings whose areas contain the point, the reliable way to ask about one
    place, and/or ``name`` for an area of that name (DWD's German one, ``München`` and not ``Munich``, matched as words
    in every area that has it) or warn cell id. ``timestamp`` (ISO 8601, UTC if no offset) selects a historical
    snapshot from DWD's rolling ~48-hour window; omit it for the latest snapshot. An empty result is an answer, not
    an error: no warning is active, or none is for the place, which a ``no-alerts-for-place`` warning in ``metadata``
    says in the words of what was asked.
    """
    from wetterdienst.provider.dwd.alerts import DwdWeatherAlertRequest  # noqa: PLC0415
    from wetterdienst.provider.dwd.alerts.api import NO_AREA_MATCHED, no_area_matched_message  # noqa: PLC0415

    begin_response()

    # outside the handlers below, as for `/api/stations`
    settings = Settings()
    try:
        alerts_request = DwdWeatherAlertRequest(
            granularity=request.granularity,
            language=request.language,
            timestamp=request.timestamp,
            settings=settings,
            latitude=request.latitude,
            longitude=request.longitude,
            name=request.name,
        )
        result = alerts_request.query()
    except Exception as e:
        # a date that does not parse, one an offset carries out of what a datetime holds, or one
        # before DWD's rolling window is the request's; a feed that does not list, download or read,
        # and an alert in it the parser does not expect, is the provider's (GH-2985)
        raise _failure(e, request, "get weather alerts") from e

    tool = is_tool_request(http_request.scope)
    name = alerts_request.name
    if tool and name is not None and result.name_matched is False:
        # an assistant read an empty answer for a name that found no area as "no warning" (GH-4338)
        record_response_warning(NO_AREA_MATCHED, no_area_matched_message(name, point=request.latitude is not None))
    content, metadata = render_alerts(result, request.format, pretty=request.pretty)
    if tool:
        # an assistant reads the answer in its context: cut to the budget, with a note (GH-4338)
        content, metadata = fit_alerts(
            result,
            request.format,
            content,
            metadata,
            lambda cut, block: render_alerts(cut, request.format, pretty=request.pretty, metadata=block)[0],
            name=name,
            point=request.latitude is not None,
        )
    return _answer(content, request.format, metadata)


@router.get(
    "/storm-cells",
    response_model=_StormCellsWithMetadataDict | _StormCellsWithMetadataOgcFeatureCollection | str,
    tags=[TAG_STORM_CELLS],
)
def storm_cells(
    request: Annotated[StormCellsRequest, Query()],
) -> Response:
    """Provide DWD's thunderstorm cells (KONRAD3D) via restapi.

    Returns the cells of the newest radar scan, or of the newest at or before ``timestamp`` (ISO 8601, UTC if no
    offset) within the ~48 hours DWD keeps, one entry per cell: its severity (0 weak to 3 extreme), warning flags for
    hail, heavy rain and gusts, size, speed, the ``direction_degrees`` of its motion (calculated), its outline and its
    forecast ``track`` of 12 positions to 60 minutes ahead. Without a place that is every cell of Germany (several
    hundred KB on a day of storms, more than an assistant can read): pass ``latitude``, ``longitude`` and ``distance``
    (km) for the cells whose outline contains the point or comes within the distance, or ``left``, ``bottom``,
    ``right`` and ``top`` for a box, and ``min_severity``. ``track=false`` and ``geometry=centroid`` make a long list
    small. Most scans hold no cell: an empty ``cells`` is an answer, not an error, and ``reference_time`` says which
    scan it is of. A filter that leaves no cell of a scan that has some carries a ``no-storm-cells-for-place`` warning
    in ``metadata``, and a scan that is more than 20 minutes older than the time asked for a ``scan-stale`` warning:
    an empty answer is then no all-clear. Scans come every 5 minutes and the newest is 5 to 10 minutes old when it
    appears.
    """
    from wetterdienst.provider.dwd.storm_cells import DwdStormCellsRequest  # noqa: PLC0415

    begin_response()

    # outside the handlers below, as for `/api/stations`
    settings = Settings()
    try:
        cells_request = DwdStormCellsRequest(
            timestamp=request.timestamp,
            latitude=request.latitude,
            longitude=request.longitude,
            distance=request.distance,
            left=request.left,
            bottom=request.bottom,
            right=request.right,
            top=request.top,
            min_severity=request.min_severity,
            track=request.track,
            geometry=request.geometry,
            settings=settings,
        )
        result = cells_request.query()
    except Exception as e:
        # a time that does not parse, or one before DWD's rolling window, or a box that is no box, is the request's; a
        # listing that does not list, a file that does not download or parse is the provider's
        raise _failure(e, request, "get storm cells") from e

    content, metadata = render_storm_cells(result, request.format, pretty=request.pretty)
    return _answer(content, request.format, metadata)


@router.get(
    "/kostra",
    response_model=_KostraWithMetadataDict | str,
    tags=[TAG_KOSTRA],
)
def kostra(
    request: Annotated[KostraRequest, Query()],
) -> Response:
    """Provide DWD's design rainfall (KOSTRA-DWD-2020: the rain of a duration that returns every N years) of a point.

    Returns the table of the cell of DWD's 5 km grid that holds the point: for each duration of a rain (5 minutes to
    7 days) and each return period (1 to 100 years) its depth in mm (``depth_mm``), its intensity in l/(s ha)
    (``intensity_l_s_ha``) and DWD's uncertainty in plus-minus percent (``uncertainty_percent``, a tolerance of both),
    with the cell's ``index_rc`` and the position of its centre. Engineers size drains and retention basins with these
    values. Pass ``duration`` (and ``return_period``) for the one value you need: a duration reads one table of DWD,
    without it all 22 are read (2 s the first time, then from the cache). The values are DWD's estimates for the cell,
    not measurements at the point. A point outside Germany and a border of about 10 km, or in the sea, is refused.
    """
    from wetterdienst.provider.dwd.kostra import DwdKostraRequest  # noqa: PLC0415

    begin_response()

    # outside the handlers below, as for `/api/stations`
    settings = Settings()
    try:
        result = DwdKostraRequest(
            latitude=request.latitude,
            longitude=request.longitude,
            duration=request.duration,
            return_period=request.return_period,
            settings=settings,
        ).query()
    except Exception as e:
        # a point outside the grid or in a cell without values is the request's (a 400); a table that does not
        # download or read is the provider's
        raise _failure(e, request, "get KOSTRA statistics") from e

    content, metadata = render_kostra(result, request.format, pretty=request.pretty)
    return _answer(content, request.format, metadata)


#: how long the list of the frames of the radar may be reused: the server holds the list of DWD's runs for a minute
RADAR_FRAMES_CACHE_CONTROL = "public, max-age=60"
#: how long the image of a frame is reused where the request names its run, which never changes (DWD keeps a run for
#: about 48 hours, and the server draws a frame the same every time), and where it does not (a forecast frame is that of
#: the newest run, which comes every 5 minutes)
RADAR_FRAME_OF_A_RUN_CACHE_CONTROL = "public, max-age=3600"
RADAR_FRAME_OF_THE_NEWEST_CACHE_CONTROL = "public, max-age=60"


@router.get(
    "/radar/frames",
    response_model=RadarFramesWithMetadataDict,
    tags=[TAG_RADAR],
    responses=_revalidatable(last_modified=False),
)
def radar_frames(
    request: Annotated[RadarFramesRequest, Query()],
    http_request: Request,
) -> Response:
    """List the frames of DWD's precipitation radar, a loop of the last hours and the forecast of the next two.

    DWD's RV composite: the precipitation over Germany of every 5 minutes. Each frame has the `time` it is valid at
    (UTC), the `run` of DWD it is read from, and is `observation` (the radar analysis, `past` minutes of it, 2 hours by
    default) or `forecast` (DWD's extrapolation of the recent movement of the rain, 24 frames to 2 hours after the
    newest run, unless `forecast=false`). Fetch the image of a frame from `/radar/frame` with its `time` and `run`.
    `image` says where the images lie: `bounds` in WGS84, which a Leaflet `ImageOverlay` takes as they are (the images
    are in Web Mercator, `crs`, so a map of another projection must not stretch them), and `legend` the colours of the
    classes of the rate in mm/h, as numbers. The newest run is 3 to 8 minutes old when it appears on DWD's server; a
    `radar-stale` warning in `metadata` says that it is much older.
    """
    from wetterdienst.provider.dwd.radar.frames import DwdRadarFrames  # noqa: PLC0415

    begin_response()

    # outside the handler below, as for `/api/stations`
    settings = Settings()
    try:
        listing = DwdRadarFrames(settings).frames(history_minutes=request.past, forecast=request.forecast)
    except Exception as e:
        # a directory that does not list, or lists no run, is the provider's
        raise _failure(e, request, "list radar frames") from e

    content, metadata = render_radar_frames(listing, pretty=request.pretty)
    if metadata.warnings:
        # an old run is a source that is behind for the moment: the next request may give another
        return _answer(content, "json", metadata)
    return cached_json(
        http_request,
        content,
        cache_control=RADAR_FRAMES_CACHE_CONTROL,
        ignoring=[metadata.retrieved_at],
        headers=response_headers(metadata),
    )


@router.get(
    "/radar/frame",
    response_class=Response,
    tags=[TAG_RADAR],
    responses={
        200: {
            "description": "The frame as an image: an indexed PNG whose colours are the classes of the legend of "
            "`/radar/frames` and whose background is transparent. The licence, the credit line and the note on what "
            "was done to the data are in the headers, as for every answer that holds no `metadata` block; "
            "`X-Wetterdienst-Radar-Time` and `X-Wetterdienst-Radar-Run` say which frame it is.",
            "content": {"image/png": {}},
            "headers": {
                **_VALIDATOR_HEADERS,
                "X-Wetterdienst-Radar-Time": {
                    "description": "The UTC time the frame is valid at.",
                    "schema": {"type": "string"},
                },
                "X-Wetterdienst-Radar-Run": {
                    "description": "The UTC time of the run of DWD the frame is read from.",
                    "schema": {"type": "string"},
                },
            },
        },
        304: _revalidatable(last_modified=False)[304],
    },
)
def radar_frame(
    request: Annotated[RadarFrameRequest, Query()],
    http_request: Request,
) -> Response:
    """Get the image of one frame of DWD's precipitation radar, as a PNG that a map draws over Germany.

    The `time` (UTC, a multiple of 5 minutes) and the `run` are those of a frame of `/radar/frames`. The image is the
    precipitation of the 5 minutes that end at `time` as a rate, in the classes of the legend of `/radar/frames`;
    where there is no rain, and where the composite has no data, it is transparent. It lies over the `bounds` of that
    answer and is in Web Mercator (EPSG:3857). One decoded frame serves every reader, so a frame is drawn once.
    Given `run`, the image is the same for as long as DWD keeps the run (about 48 hours) and may be reused for an hour;
    without it, a time after the newest run is a forecast frame of the newest run, which changes every 5 minutes. The
    forecast of a run is served for the newest three runs DWD lists, and a run it does not list is a 404. Load frames a
    few at a time (4 to 6): the server serves 32 requests at once.
    """
    from wetterdienst.provider.dwd.radar.frames import DwdRadarFrames, format_instant, parse_instant  # noqa: PLC0415

    begin_response()

    # outside the handler below, as for `/api/stations`
    settings = Settings()
    try:
        image = DwdRadarFrames(settings).frame(
            parse_instant(request.time, name="time"),
            parse_instant(request.run, name="run") if request.run else None,
        )
    except Exception as e:
        # a time that does not parse or is not a frame is the request's, a run DWD does not hold a 404, and a file that
        # does not download or decode the provider's
        raise _failure(e, request, "draw a radar frame") from e

    metadata = radar_metadata(1, image=True)
    checked = validators(
        http_request,
        image.png,
        cache_control=RADAR_FRAME_OF_A_RUN_CACHE_CONTROL if request.run else RADAR_FRAME_OF_THE_NEWEST_CACHE_CONTROL,
    )
    if checked.matched:
        return checked.not_modified()
    return Response(
        content=image.png,
        media_type="image/png",
        headers={
            **response_headers(metadata),
            "X-Wetterdienst-Radar-Time": format_instant(image.frame.time),
            "X-Wetterdienst-Radar-Run": format_instant(image.frame.run),
            **checked.headers,
        },
    )


def _mount_mcp(rest_app: FastAPI) -> bool:
    """Mount the MCP endpoint at ``/mcp/v1`` and its alias ``/mcp`` onto ``rest_app``, if ``[mcp]`` is installed.

    The MCP server (see :mod:`wetterdienst.ui.mcp`) is generated from the REST API's own routes, so
    the MCP transport stays in lockstep with the HTTP API, with a workflow ``instructions``
    block and clean tool names layered on for agent usability. ``/mcp/v1`` is the endpoint of the
    contract version, and ``/mcp`` is an alias of the current one, as ``/api`` is of ``/api/v1``.
    Both paths are routes to the one endpoint, so they share the session manager and
    the server is built once, and a tool answers alike on either (GH-3074). The endpoint is stateless (GH-3088):
    every request stands alone, no session is kept, and a request needs no `initialize` before it. An `initialize`
    is answered with an `Mcp-Session-Id` that the server neither stores nor checks (GH-4341). The MCP
    streamable-http session manager runs via the sub-app's lifespan, which is *composed* with
    ``rest_app``'s existing lifespan here (not replaced), so any current or future app
    startup/shutdown still runs; the existing REST routes keep working with or without the
    lifespan running.

    Returns ``True`` when the endpoint was mounted, ``False`` when the optional ``[mcp]`` extra is not
    installed or the MCP server could not be built (so the MCP routes are strictly optional and a
    build error never takes down the plain REST API).
    """
    try:
        from fastmcp.utilities.lifespan import combine_lifespans  # noqa: PLC0415
        from starlette.routing import Route  # noqa: PLC0415

        from wetterdienst.ui.mcp import AnnounceSessionId, build_mcp_server  # noqa: PLC0415

        # stateless: the tools hold no session state, so no session is kept (GH-3088)
        mcp_app = build_mcp_server(rest_app).http_app(path=MCP_PREFIX, stateless_http=True)
    except ModuleNotFoundError as exc:
        # optional [mcp] extra (fastmcp, httpx2) not installed -> plain REST API, no MCP route.
        # Said out loud, because an instance missing /mcp for want of a dependency otherwise looks
        # exactly like one that was never meant to have it.
        log.info("No MCP endpoint: %s is not installed (optional [mcp] extra), continuing without it", exc.name)
        return False
    except Exception:
        # never let an MCP build/version error take down the whole REST API; degrade to no MCP route
        log.exception("Failed to build the MCP endpoint; continuing without it")
        return False

    # Add the MCP route(s) to the existing app and compose the MCP session-manager lifespan with the
    # app's existing lifespan (rather than replacing it, which would drop any app startup/shutdown).
    # The alias is a second route to the pinned route's own endpoint: not a second `http_app`, whose
    # lifespan would start a second session manager and enter the server's lifespan a second time
    # the endpoint answers an `initialize` with an `Mcp-Session-Id` that nothing keeps or checks (GH-4341)
    mcp_routes = [
        Route(
            route.path,
            endpoint=AnnounceSessionId(route.endpoint),
            methods=sorted(route.methods) if route.methods else None,
            name=route.name,
        )
        if isinstance(route, Route) and route.path == MCP_PREFIX
        else route
        for route in mcp_app.router.routes
    ]
    rest_app.router.routes.extend(mcp_routes)
    rest_app.router.routes.extend(
        Route(MCP_ALIAS_PREFIX, endpoint=route.endpoint, methods=sorted(route.methods) if route.methods else None)
        for route in mcp_routes
        if isinstance(route, Route) and route.path == MCP_PREFIX
    )
    rest_app.router.lifespan_context = combine_lifespans(
        rest_app.router.lifespan_context,
        mcp_app.router.lifespan_context,
    )
    log.info("MCP endpoint mounted at %s, and %s as its alias", MCP_PREFIX, MCP_ALIAS_PREFIX)
    return True


# the alias first, so that a route's name resolves to `/api/...` (`url_path_for`), the path the messages
# of the errors send a caller to and the one the app and the docs use. Which comes first does not
# matter to OpenAPI, which lists the versioned routes alone
app.include_router(router, prefix=API_ALIAS_PREFIX, include_in_schema=False)
app.include_router(router, prefix=API_PREFIX)

mcp_enabled = _mount_mcp(app)


ALLOWED_HOSTS_VARIABLE = "WD_RESTAPI_ALLOWED_HOSTS"


def _answer_to_loopback_names_only(listen_host: str) -> None:
    """Have a server on the loopback interface answer to its loopback names alone, unless told otherwise (GH-3087).

    A web page that a hostile DNS name re-points at `127.0.0.1` reaches a local server with its own name in `Host`.
    Done for this process through its environment, which a reloaded worker inherits, and only where the setting is
    not given: a server on a loopback address that is reached through a tunnel or a port mapping lists its names.
    """
    try:
        if Settings().restapi_allowed_hosts:
            return
    except Exception:  # noqa: BLE001
        # a malformed setting is refused as the server starts, naming the variable
        return
    os.environ[ALLOWED_HOSTS_VARIABLE] = ",".join(loopback_allowed_hosts(listen_host))
    log.info(
        f"Listening on the loopback interface: answering to the hosts {os.environ[ALLOWED_HOSTS_VARIABLE]} only. "
        f"Set {ALLOWED_HOSTS_VARIABLE} to reach the server by another name."
    )


#: Set by `start_service` for the process of the server when the logger `wetterdienst` was at DEBUG, as the command
#: line's `--debug` leaves it. Internal: a reloaded worker is spawned, so it has the environment of the server and
#: nothing of its logging (GH-3390).
_DEBUG_VARIABLE = "_WETTERDIENST_RESTAPI_DEBUG"


def _worker_app() -> ASGIApp:
    """Configure the logging as the server did and give back the app: the factory that uvicorn's worker calls (GH-3390).

    `--reload` runs the app in a process that uvicorn spawns, which imports the app by its name and so has none of the
    logging that `start_service` set up in the process that started it: the root logger would stay at WARNING, and the
    INFO lines of the package and the DEBUG ones of `--debug` would not be written. Done here and not as the module is
    imported, so that an app that another server hosts keeps its own logging.
    """
    setup_logging()
    if os.environ.get(_DEBUG_VARIABLE) == "1":
        set_logging_level(debug=True)
    return app


def start_service(listen_address: str | None = None, *, reload: bool | None = False) -> None:
    """Start the REST API service."""
    run = import_optional("uvicorn.main", "The REST API", extra="restapi").run

    setup_logging()
    if logging.getLogger("wetterdienst").isEnabledFor(logging.DEBUG):
        os.environ[_DEBUG_VARIABLE] = "1"
    else:
        os.environ.pop(_DEBUG_VARIABLE, None)

    if listen_address is None:
        listen_address = "127.0.0.1:7890"

    host, port = split_listen_address(listen_address)
    if is_loopback(host):
        _answer_to_loopback_names_only(host)

    # uvicorn colours the level of its log lines on a terminal and does not read NO_COLOR itself; None leaves it to
    # its terminal check
    run(
        app="wetterdienst.ui.restapi:_worker_app",
        factory=True,
        host=host,
        port=port,
        reload=reload or False,
        use_colors=False if no_color() else None,
    )
