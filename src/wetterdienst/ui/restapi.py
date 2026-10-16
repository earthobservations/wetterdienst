# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Utilities for the wetterdienst package."""

from __future__ import annotations

import json
import logging
import math
import re
from http import HTTPStatus
from textwrap import dedent
from typing import TYPE_CHECKING, Annotated, Any, Literal, NotRequired

from fastapi import APIRouter, FastAPI, HTTPException, Query, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from fastapi.utils import is_body_allowed_for_status_code
from pydantic import BaseModel, ConfigDict, ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from wetterdienst import Author, Info, Settings, Wetterdienst, __version__
from wetterdienst.exceptions import (
    ApiNotFoundError,
    BufrReaderMissingError,
    ConfigurationError,
    CredentialMissingError,
    CredentialRejectedError,
    DateRequiredError,
    DownloadError,
    ImageTooLargeError,
    MissingDependencyError,
    MissingTimeIntervalError,
    NoInternetError,
    ReversedTimeIntervalError,
    UpstreamError,
    WetterdienstError,
)
from wetterdienst.io.export import require_kaleido
from wetterdienst.metadata.resolution import Resolution
from wetterdienst.model.metadata import CoverageNetwork, CoverageResolution
from wetterdienst.model.result import (
    _InterpolatedValuesDict,
    _InterpolatedValuesOgcFeatureCollection,
    _StationsDict,
    _StationsOgcFeatureCollection,
    _SummarizedValuesDict,
    _SummarizedValuesOgcFeatureCollection,
    _ValuesDict,
    _ValuesOgcFeatureCollection,
)
from wetterdienst.options import Options
from wetterdienst.settings import check_settings
from wetterdienst.ui.core import (
    SUMMARY_USE_NEARBY_STATION_DISTANCE_DEPRECATED,
    AlertsRequest,
    AuthAnswer,
    AuthRequest,
    CoverageRequest,
    GlossaryEntry,
    GlossaryRequest,
    HistoryRequest,
    InterpolationRequest,
    IssuesRequest,
    SettingsRequest,
    StationsRequest,
    StripesImageRequest,
    StripesStationsRequest,
    StripesValuesRequest,
    SummaryRequest,
    ValuesRequest,
    _caller_refusal_status,
    _get_stripes_data,
    _get_stripes_stations,
    _plot_stripes,
    check_timeseries_api,
    failure_status,
    get_auth,
    get_glossary,
    get_interpolate,
    get_issues,
    get_stations,
    get_summarize,
    get_values,
    limit_stations_to_rank,
    limit_stations_to_window,
    overlay_options,
    set_logging_level,
)
from wetterdienst.ui.mcp import is_tool_request
from wetterdienst.ui.render import (
    InterpolationSettings,
    SummarySettings,
    ValuesSettings,
    _applied_settings,
    _AppliedSettings,
    render,
    render_stations,
)
from wetterdienst.util.cli import setup_logging
from wetterdienst.util.datetime import format_timestamp, timestamps_to_string
from wetterdienst.util.extras import import_optional

if TYPE_CHECKING:
    from collections.abc import Callable, Collection, Mapping

    from fastapi.routing import APIRoute
    from starlette.types import ASGIApp, Receive, Scope, Send

    from wetterdienst.model.request import TimeseriesRequest
    from wetterdienst.model.result import InterpolatedValuesResult, SummarizedValuesResult, ValuesResult

info = Info()

# FastAPI's OpenTelemetry stays on, so it reports to a provider the operator sets up. Its startup
# export from `OTEL_EXPORTER_OTLP_*` is off: it would set up providers where the OpenTelemetry SDK
# is installed and none is, add a second exporter to one the operator set up, and where it cannot
# export (no SDK, gRPC) warn on fastapi 0.142.2 and refuse to start on 0.142.0 and 0.142.1. To
# export, set up the provider, e.g. with `opentelemetry-instrument` (GH-2407). An MCP tool's
# in-process request to this app is left out, see `is_tool_request` (GH-2432)
app = FastAPI(debug=False, telemetry={"auto_configure": False, "exclude": is_tool_request})

#: the version of the REST API contract, reported by `/api/version` as `api_version`
API_VERSION = "1"
#: where the current version is served; OpenAPI documents this prefix (GH-2561)
API_PREFIX = f"/api/v{API_VERSION}"
#: the same routes without the version, an alias of the current version: not deprecated, and not in OpenAPI
API_ALIAS_PREFIX = "/api"


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

    Checked as the server starts the app's lifespan, so it holds whatever starts it --
    `wetterdienst restapi`, `uvicorn wetterdienst.ui.restapi:app` -- unless the lifespan is turned
    off, and covers `/mcp`, which is served by this app. A failure in the app's own lifespan would
    reach the server as Starlette's formatted traceback; answering the startup here gives the log
    the variables and what is wrong with them, a line each, without the values, and the server
    exits before taking a connection. Under `--reload` it is the worker that exits; the reloader
    stays, and starts a worker again on the next change to a source file.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "lifespan":
            try:
                problems = check_settings()
            except Exception as e:  # noqa: BLE001
                # a validator failing other than by refusing the value, as the station distances'
                # did with a `TypeError` until GH-2353, is refused all the same: raised here,
                # uvicorn's default `--lifespan auto` would take it for a lifespan the app does not
                # support, and serve. Told by its type alone, as its message is not pydantic's and
                # may carry what it was given
                problems = [f"the settings could not be built: {type(e).__name__}"]
            if problems:
                await receive()
                message = "\n".join(["Refusing to start, the settings are invalid:", *problems])
                await send({"type": "lifespan.startup.failed", "message": message})
                return
        await self.app(scope, receive, send)


app.add_middleware(_RefuseInvalidSettings)

# Set to True at the bottom of this module when the optional ``[mcp]`` extra (fastmcp) is installed
# and an MCP endpoint has been mounted onto ``app`` at ``/mcp``. Read by the index page.
mcp_enabled = False

log = logging.getLogger(__name__)


REQUEST_EXAMPLES = {
    "dwd_observation_daily_climate_stations": "api/stations?provider=dwd&network=observation&parameters=daily/kl&periods=recent&all=true",  # noqa:E501
    "dwd_observation_daily_climate_values": "api/values?provider=dwd&network=observation&parameters=daily/kl&periods=recent&stations=00011",  # noqa:E501
    "dwd_observation_daily_climate_history": "api/history?provider=dwd&network=observation&parameters=daily/kl&stations=00011",  # noqa:E501
    "dwd_observation_daily_climate_interpolation": "api/interpolate?provider=dwd&network=observation&parameters=daily/kl/temperature_air_mean_2m&station=00071&timestamp=1986-10-31/1986-11-01",  # noqa:E501
    "dwd_observation_daily_climate_summary": "api/summarize?provider=dwd&network=observation&parameters=daily/kl/temperature_air_mean_2m&station=00071&timestamp=1986-10-31/1986-11-01",  # noqa:E501
    "dwd_observation_daily_climate_stripes_stations": "api/stripes/stations?kind=temperature",
    "dwd_observation_daily_climate_stripes_values": "api/stripes/values?kind=temperature&station=1048",
    "dwd_observation_daily_climate_stripes_image": "api/stripes/image?kind=temperature&station=1048",
    "dwd_mosmix_issues": "api/issues?provider=dwd&network=mosmix&station=10147",
    "dwd_dmo_issues": "api/issues?provider=dwd&network=dmo&station=10147",
    "dwd_swsmos_issues": "api/issues?provider=dwd&network=swsmos&station=A006",
    "dwd_weather_alerts": "api/alerts?granularity=community&format=geojson",
}


#: the media type of every error body, RFC 9457
PROBLEM_MEDIA_TYPE = "application/problem+json"


def _problem_response(
    request: Request,
    status_code: int,
    detail: str,
    *,
    errors: list[Any] | None = None,
    headers: Mapping[str, str] | None = None,
) -> JSONResponse:
    """Answer a failure with the one error body of this API, an RFC 9457 problem (GH-2634).

    `{"type": "about:blank", "title": <the status' phrase>, "status": <int>, "detail": <str>}`, as
    the RFC has a problem with no meaning beyond its status. `detail` is always text, the whole
    reason, one line for each thing wrong where a request is wrong in several; a client that only
    wants a sentence reads that. `errors` is added where a request failed validation: the list of
    pydantic's entries, each with the `loc` of its parameter, as `detail` was for such a request
    until then, and what a client that wants the invalid fields reads.

    An MCP tool's request is answered with the text alone, as a JSON string: FastMCP puts the body
    of a failed call into the tool error as Python writes it, and a dict would read as its repr.
    """
    if is_tool_request(request.scope):
        return JSONResponse(detail, status_code=status_code, headers=headers)
    problem: dict[str, Any] = {
        "type": "about:blank",
        "title": _status_phrase(status_code),
        "status": status_code,
        "detail": detail,
    }
    if errors:
        problem["errors"] = errors
    return JSONResponse(problem, status_code=status_code, headers=headers, media_type=PROBLEM_MEDIA_TYPE)


def _status_phrase(status_code: int) -> str:
    """Give the phrase of a status, as RFC 9457 asks of the `title` of a problem with no type of its own."""
    try:
        return HTTPStatus(status_code).phrase
    except ValueError:
        return "Error"


@app.exception_handler(StarletteHTTPException)
async def _http_exception_handler(request: Request, exc: StarletteHTTPException) -> Response:
    """Answer an `HTTPException`, and Starlette's own for an unknown path or a method not allowed, as a problem."""
    if not is_body_allowed_for_status_code(exc.status_code):
        return Response(status_code=exc.status_code, headers=exc.headers)
    detail = exc.detail if isinstance(exc.detail, str) else _status_phrase(exc.status_code)
    return _problem_response(request, exc.status_code, detail, headers=exc.headers)


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


@app.exception_handler(RequestValidationError)
async def _validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """Answer a request that fails validation with a 422 problem, its entries under `errors`."""
    errors = jsonable_encoder(exc.errors())
    return _problem_response(request, 422, _describe_validation_errors(errors), errors=errors)


class _NoRequestModel(BaseModel):
    """The request model of a failure raised where no endpoint's request is at hand: it carries no field."""


@app.exception_handler(WetterdienstError)
async def _wetterdienst_error_handler(request: Request, exc: WetterdienstError) -> JSONResponse:
    """Answer an exception of the library that escaped an endpoint's own handling by its place in the hierarchy.

    The endpoints decide with `_failure` inside their handlers; this is for what is raised outside
    them, such as while a result is rendered, and gives it the status `failure_status` gives it.
    """
    error = _failure(exc, _NoRequestModel(), f"serve {request.url.path}")
    return _problem_response(request, error.status_code, error.detail)


@app.exception_handler(Exception)
async def _unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Answer a failure no endpoint handled with the 500 problem of `_server_error`, the traceback in the log.

    Starlette sends this answer and then raises the exception again, so the server logs it as it
    did when the answer was its plain-text one.
    """
    error = _server_error(exc)
    return _problem_response(request, error.status_code, error.detail)


def _dependency_missing_on_the_server(e: MissingDependencyError, what: str) -> HTTPException:
    """Report a dependency this deployment does not have as the server's lack, not the caller's error.

    The blanket handlers answered it with a 400 carrying `pip install wetterdienst[bufr]` -- an
    instruction for a machine the caller does not administer, about a request that was perfectly
    well formed. Over HTTP the missing half is a property of the deployment, and 501 is what says
    so: this server does not implement what needs the package, such as the networks published as
    BUFR, a `sql` filter or an image. The install line is not lost, it moves to where someone can
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
    return HTTPException(status_code=501, detail=detail)


@app.exception_handler(MissingDependencyError)
async def _missing_dependency_handler(request: Request, exc: MissingDependencyError) -> JSONResponse:
    """Answer a dependency the deployment lacks with a 501 wherever it was reached.

    The endpoints turn it into one inside their own handlers (`_failure`); this is for the rest,
    such as rendering an image after the values were collected.
    """
    error = _dependency_missing_on_the_server(exc, f"serve {request.url.path}")
    return _problem_response(request, error.status_code, error.detail)


def _credential_missing_on_the_server(e: CredentialMissingError, request: BaseModel, what: str) -> HTTPException:
    """Report a credential this deployment lacks as the server's lack, not the caller's error or a crash.

    The provider's message tells whoever runs the process which setting to change, which is no
    instruction for a caller of this API: it answered it as a 500, the server broken, with the
    environment variable named in the body. The provider exists and this instance has no key for it,
    which is a 501 as for the BUFR reader: this server does not serve the network. Not a 503, which
    the app asks once more (`RETRY_TRANSIENT` keeps it for a proxy's), and a missing key does not
    pass by itself. This is what `configured: false` reports, without the setting's name; the body
    points at `coverage` for it. The request's window and parameters are parsed by the time this is
    raised, its stations are not, so the body does not vouch for the request. The message is not
    lost, it moves to the server log, as a warning: a state that lasts until someone configures the
    key is no incident.
    """
    log.warning(f"Failed to {what}, no credential is configured for the provider: {e}")
    provider, network = getattr(request, "provider", None), getattr(request, "network", None)
    of = f" for {provider}/{network}" if provider and network else ""
    return HTTPException(
        status_code=501,
        detail=(
            f"This server has no credential{of}, which the provider requires, so it cannot serve the "
            f"request. {app.url_path_for('coverage')} tells whether a provider is "
            "configured; otherwise ask whoever runs this instance."
        ),
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
    return HTTPException(
        status_code=501,
        detail=(
            f"The provider rejected the credential of this server{of}, so it cannot serve the "
            f"request. {app.url_path_for('auth')} tells whether the credential is accepted; "
            "otherwise ask whoever runs this instance."
        ),
    )


def _refuse_sql_unless_enabled(
    request: StationsRequest | ValuesRequest | InterpolationRequest | SummaryRequest,
) -> None:
    """Refuse a `sql` or `sql_values` clause unless whoever runs this server has enabled them.

    The clause runs in DuckDB on this host. Its connection cannot read files, reach the network or
    load extensions, but its limits are per request: it can still read DuckDB's settings, run for as
    long as it likes on one core, and allocate outside DuckDB's memory limit. Whether to take that
    from anyone who can reach the API is the operator's decision, so it is off until they set
    `WD_RESTAPI_SQL=true`. A 403, as for the BUFR reader's 501: the request is well formed and this
    deployment declines it, which a 400 would blame on the caller. Checked before anything is
    fetched, so a refused request costs nothing. The MCP tools are this API's routes, so they are
    gated with it; the library and the CLI are not.
    """
    given = [name for name in ("sql", "sql_values") if getattr(request, name, None)]
    if given and not Settings().restapi_sql:
        raise HTTPException(
            status_code=403,
            detail=(
                f"SQL filtering is disabled on this server, so {' and '.join(given)} cannot be used. "
                "Whoever runs this instance can enable it with the setting restapi_sql "
                "(environment variable WD_RESTAPI_SQL=true); otherwise filter the response yourself."
            ),
        )


#: the formats a chart is rendered to by the browser; `html` is the figure itself and has no size
_IMAGE_FORMATS = frozenset({"png", "jpg", "webp", "svg", "pdf"})

#: the longest side, in pixels once `scale` is applied, of an image this server renders. Chromium
#: renders it for as long as it takes and holds the whole canvas: 14000 x 10000 px took 18 s, and
#: 28000 x 20000 px 30 s and then an empty body that was answered with a 200 (GH-2765)
_MAX_IMAGE_SIDE = 8192
#: the size plotly renders at when a request names none
_DEFAULT_IMAGE_WIDTH, _DEFAULT_IMAGE_HEIGHT = 700, 500


def _refuse_oversized_image(
    width: int | None, height: int | None, scale: float | None, *, lower: str = "width, height or scale"
) -> None:
    """Refuse an image larger than `_MAX_IMAGE_SIDE` on a side, with a 400, before anything is fetched.

    The request fields only have to be positive, and the caller is whoever can reach the API: each
    image request starts its own browser, so the size it paints is theirs to choose. The library
    and the CLI, whose caller is the host's own user, are not limited. The MCP tools are this API's
    routes, so they are limited with it. A size left out is plotly's default, which is what is
    measured here: the height of a chart of several parameters is 300 px for each, known only once
    they are collected, and is measured then, by `check_image_size` (`_refuse_oversized_render`).
    """
    scale = 1 if scale is None else scale
    rendered = ((width or _DEFAULT_IMAGE_WIDTH) * scale, (height or _DEFAULT_IMAGE_HEIGHT) * scale)
    if max(rendered) > _MAX_IMAGE_SIDE:
        error = ImageTooLargeError(rendered[0], rendered[1], _MAX_IMAGE_SIDE)
        raise HTTPException(status_code=400, detail=f"{error} Lower {lower}.")


def _refuse_oversized_chart(request: StationsRequest | ValuesRequest | InterpolationRequest | SummaryRequest) -> None:
    """Refuse the size of a chart in an image format, see `_refuse_oversized_image`."""
    if request.format in _IMAGE_FORMATS:
        _refuse_oversized_image(request.width, request.height, request.scale)


@app.exception_handler(ImageTooLargeError)
async def _refuse_oversized_render(request: Request, exc: ImageTooLargeError) -> JSONResponse:
    """Answer a chart whose own height makes the image too large with a 400, as `_refuse_oversized_image` does.

    Raised by `check_image_size` once the figure is built, since a chart of several parameters is
    300 px tall for each, and before the browser is started.
    """
    log.info(f"Refused {request.url.path}: {exc}")
    return _problem_response(request, 400, f"{exc} Lower scale, give a smaller height, or ask for fewer parameters.")


# each output format by its media type; the rest are JSON. `image/{format}` named no registered type
# for jpg or svg, and the stripes image sent `image/pdf` for a PDF (GH-2063)
_MEDIA_TYPES = {
    "csv": "text/csv",
    "html": "text/html",
    "png": "image/png",
    "jpg": "image/jpeg",
    "webp": "image/webp",
    "svg": "image/svg+xml",
    "pdf": "application/pdf",
}


class ServerSettings(BaseModel):
    """What each endpoint takes for a setting a request leaves out."""

    model_config = ConfigDict(extra="forbid")

    values: ValuesSettings
    interpolate: InterpolationSettings
    summarize: SummarySettings


# what the JSON formats of the three endpoints answer with: their results' own, and, with
# `with_metadata`, the settings they were got with (GH-2359)
class _ValuesWithSettingsDict(_ValuesDict):
    settings: NotRequired[ValuesSettings]


class _ValuesWithSettingsOgcFeatureCollection(_ValuesOgcFeatureCollection):
    settings: NotRequired[ValuesSettings]


class _InterpolatedValuesWithSettingsDict(_InterpolatedValuesDict):
    settings: NotRequired[InterpolationSettings]


class _InterpolatedValuesWithSettingsOgcFeatureCollection(_InterpolatedValuesOgcFeatureCollection):
    settings: NotRequired[InterpolationSettings]


class _SummarizedValuesWithSettingsDict(_SummarizedValuesDict):
    settings: NotRequired[SummarySettings]


class _SummarizedValuesWithSettingsOgcFeatureCollection(_SummarizedValuesOgcFeatureCollection):
    settings: NotRequired[SummarySettings]


@app.get("/")
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
            api = Wetterdienst(provider, first_network)
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
                    <li><a href="api/coverage" target="_blank" rel="noopener">coverage</a></li>
                    <li><a href="api/glossary" target="_blank" rel="noopener">glossary</a></li>
                    <li><a href="api/settings" target="_blank" rel="noopener">settings</a></li>
                    <li><a href="api/stations" target="_blank" rel="noopener">stations</a></li>
                    <li><a href="api/values" target="_blank" rel="noopener">values</a></li>
                    <li><a href="api/interpolate" target="_blank" rel="noopener">interpolation</a></li>
                    <li><a href="api/summarize" target="_blank" rel="noopener">summary</a></li>
                    <li><a href="api/stripes/stations" target="_blank" rel="noopener">stripes stations</a></li>
                    <li><a href="api/stripes/values" target="_blank" rel="noopener">stripes values</a></li>
                    <li><a href="api/stripes/image" target="_blank" rel="noopener">stripes image</a></li>
                    <li><a href="api/alerts" target="_blank" rel="noopener">weather alerts</a></li>
                    {"<li>MCP endpoint (streamable HTTP): <code>/mcp</code></li>" if mcp_enabled else ""}
                </ul>
                <h2>Examples</h2>
                <ul>
                    <li><a href="{REQUEST_EXAMPLES["dwd_observation_daily_climate_stations"]}" target="_blank" rel="noopener">DWD Observation Daily Climate Stations</a></li>
                    <li><a href="{REQUEST_EXAMPLES["dwd_observation_daily_climate_values"]}" target="_blank" rel="noopener">DWD Observation Daily Climate Values</a></li>
                    <li><a href="{REQUEST_EXAMPLES["dwd_observation_daily_climate_history"]}" target="_blank" rel="noopener">DWD Observation Daily Climate History</a></li>
                    <li><a href="{REQUEST_EXAMPLES["dwd_observation_daily_climate_interpolation"]}" target="_blank" rel="noopener">DWD Observation Daily Climate Interpolation</a></li>
                    <li><a href="{REQUEST_EXAMPLES["dwd_observation_daily_climate_summary"]}" target="_blank" rel="noopener">DWD Observation Daily Climate Summary</a></li>
                    <li><a href="{REQUEST_EXAMPLES["dwd_observation_daily_climate_stripes_stations"]}" target="_blank" rel="noopener">DWD Observation Daily Climate Stripes Stations</a></li>
                    <li><a href="{REQUEST_EXAMPLES["dwd_observation_daily_climate_stripes_values"]}" target="_blank" rel="noopener">DWD Observation Daily Climate Stripes Values</a></li>
                    <li><a href="{REQUEST_EXAMPLES["dwd_observation_daily_climate_stripes_image"]}" target="_blank" rel="noopener">DWD Observation Daily Climate Stripes Image</a></li>
                    <li><a href="{REQUEST_EXAMPLES["dwd_weather_alerts"]}" target="_blank" rel="noopener">DWD Weather Alerts</a></li>
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
    )


@app.get("/robots.txt")
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


@app.get("/health")
def health() -> JSONResponse:
    """Health check."""
    return JSONResponse(content={"status": "OK"})


@router.get("/version")
def version() -> JSONResponse:
    """Get version information, and whether this instance serves an MCP endpoint.

    `api_version` is the version of the REST API contract the routes are served under
    (`/api/v1/...`; `/api/...` is an alias of the current version), `version` that of wetterdienst.

    `mcp_enabled` is read at request time rather than captured at import: `_mount_mcp` sets it at
    the bottom of this module, after the routes are declared. It is reported here because the
    endpoint is optional -- an instance installed without the `[mcp]` extra has no `/mcp` route --
    and a client has no other way to find out short of probing `/mcp`, which on the streamable-HTTP
    transport means opening a session rather than asking a question.
    """
    return JSONResponse(content={"version": __version__, "api_version": API_VERSION, "mcp_enabled": mcp_enabled})


# each endpoint's settings, by the request it takes them from
_ENDPOINT_SETTINGS: tuple[tuple[str, type[BaseModel], type[_AppliedSettings]], ...] = (
    ("values", ValuesRequest, ValuesSettings),
    ("interpolate", InterpolationRequest, InterpolationSettings),
    ("summarize", SummaryRequest, SummarySettings),
)


@router.get("/settings", response_model=ServerSettings)
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


def _declare_problem_schema(schema: dict[str, Any]) -> None:
    """Describe the error body in the schema: the 422 of each operation is the `Problem` of `_problem_response`.

    FastAPI documents the 422 it adds to every operation with a query as `HTTPValidationError`,
    `{"detail": [ValidationError]}`, which this API no longer answers: its `detail` is text and the
    entries are under `errors`. Changed in place, and the same when it runs again.
    """
    schemas = schema.setdefault("components", {}).setdefault("schemas", {})
    schemas.pop("HTTPValidationError", None)
    schemas["Problem"] = {
        "title": "Problem",
        "description": "An error, as RFC 9457 describes it (`application/problem+json`).",
        "type": "object",
        "properties": {
            "type": {"type": "string", "default": "about:blank", "description": "Always `about:blank` for now."},
            "title": {"type": "string", "description": "The phrase of the status."},
            "status": {"type": "integer", "description": "The HTTP status."},
            "detail": {"type": "string", "description": "The reason, one line for each thing wrong in a request."},
            "errors": {
                "type": "array",
                "items": {"$ref": "#/components/schemas/ValidationError"},
                "description": "The invalid parameters, each with the `loc` of its parameter, of a 422.",
            },
        },
        "required": ["type", "title", "status", "detail"],
    }
    for path in schema.get("paths", {}).values():
        for operation in path.values():
            response = operation.get("responses", {}).get("422")
            if response is not None:
                response["content"] = {PROBLEM_MEDIA_TYPE: {"schema": {"$ref": "#/components/schemas/Problem"}}}


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
    _declare_problem_schema(schema)
    _declare_list_parameters(schema)
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


# OAuth discovery endpoints. The `/mcp` server is open (no auth), so MCP clients such as Claude
# Desktop must receive a 404 here to conclude "no authorization server" and connect anonymously;
# a 200 (e.g. from a catch-all serving HTML) makes them attempt -- and fail -- Dynamic Client
# Registration. FastAPI already 404s unknown paths (including the resource-specific sub-paths like
# `.../oauth-protected-resource/mcp`), but declaring these explicitly documents the no-auth contract
# and keeps it correct if a static/SPA catch-all is ever mounted ahead of these routes.
# `include_in_schema=False` keeps them out of the OpenAPI schema so they do not become MCP tools.
@app.get("/.well-known/oauth-authorization-server", include_in_schema=False)
@app.get("/.well-known/oauth-protected-resource", include_in_schema=False)
def oauth_metadata_not_found() -> None:
    """Return 404 for OAuth discovery so the open `/mcp` server is treated as no-auth."""
    raise HTTPException(status_code=404, detail="Not Found")


def _resolve_listed_network(provider: str, network: str, what: str) -> type[TimeseriesRequest]:
    """Resolve the network `/api/auth` and `/api/coverage` are asked about, telling why one does not resolve.

    A provider or network that is not listed is a 404 pointing at the listing. A network whose
    optional extra is not installed is not that: it is listed, and this deployment lacks what it
    needs, so it is the 501 the data routes answer (`_dependency_missing_on_the_server`). Any other
    `ImportError` is not that either: the network is listed and the package is there, so a module
    that fails to import is a defect or a broken install, and it is let through as the 500 the data
    routes answer, logged with its traceback, rather than told as a network that does not exist (GH-2800).
    """
    try:
        return Wetterdienst(provider, network)
    except MissingDependencyError as e:
        raise _dependency_missing_on_the_server(e, f"{what} {provider}/{network}") from e
    except ApiNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Choose provider and network from {app.url_path_for('coverage')}",
        ) from e


@router.get("/auth", response_model=AuthAnswer)
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
    gives up after a few seconds. `/api/coverage` does not probe, so ask here whether the credentials
    of a network it lists as `configured` are accepted. The MCP tool and the CLI command
    (`wetterdienst about auth`) are this call.
    """
    set_logging_level(debug=request.debug)
    provider, network = request.provider, request.network

    api = _resolve_listed_network(str(provider), str(network), "check the credentials of")

    return get_auth(api, provider, network)


# What `/api/coverage` answers is what `Wetterdienst.discover()` and `TimeseriesRequest.discover()` build,
# described by the `Coverage*` models of `wetterdienst.model.metadata`. The answer is still sent as those return it, so
# the models only describe it.
# the answer without a provider and network: every provider, its networks and whether each needs
# credentials; the answer for one: its resolutions, which a filter that matches none of leaves out
CoverageProviders = dict[str, dict[str, CoverageNetwork]]
CoverageResolutions = dict[Resolution, CoverageResolution]
# What the route declares: one object holding either, as a union of the two would make the
# schema's top level `anyOf`, and the MCP `coverage` tool, which takes its output schema from
# this, would wrap its result in `{"result": ...}` and drop `pretty`. The two above are the exact
# shapes, which the tests hold the answers to
CoverageAnswer = dict[str, dict[str, CoverageNetwork] | CoverageResolution]


@router.get("/coverage", response_model=CoverageAnswer)
def coverage(
    request: Annotated[CoverageRequest, Query()],
) -> Response:
    """List available data: providers/networks, or the resolutions, datasets and parameters within one.

    Call with no arguments to list every provider and its networks. Pass provider+network (e.g.
    provider="dwd", network="observation") to list its resolutions/datasets/parameters; narrow with
    resolutions=... or datasets=... (e.g. datasets="climate_summary") to discover parameter names.

    The list of every provider downloads nothing, so it answers at once. Per network it gives
    `name_short`, `country`, `url` and `kind`. `kind` is `observation`, `forecast` or `derived` for a
    timeseries network, which has stations and values (every network but two); `radar` and `alerts`
    are standalone (`dwd/radar`, `dwd/alerts`): the other endpoints answer 404 for them. For a network
    that needs credentials, `configured` says whether they are present; whether the provider accepts
    them is not checked here, `/api/auth` (the MCP `auth` tool) does, for one network.
    """
    set_logging_level(debug=request.debug)
    provider, network = request.provider, request.network

    if (provider and not network) or (not provider and network):
        raise HTTPException(
            status_code=400,
            detail="Either both or none of 'provider' and 'network' must be given. If none are given, all providers "
            "and networks are returned.",
        )

    if not provider and not network:
        # the list of every provider has no resolutions or datasets to narrow; answering it
        # unfiltered would let the caller believe the filter applied
        if request.resolutions or request.datasets:
            raise HTTPException(
                status_code=400,
                detail="'resolutions' and 'datasets' narrow the coverage of one provider and network, so "
                "'provider' and 'network' must be given with them.",
            )
        cov = Wetterdienst.discover()
        return Response(content=json.dumps(cov, indent=4 if request.pretty else None), media_type="application/json")

    api = _resolve_listed_network(str(provider), str(network), "list the coverage of")

    # Standalone networks (e.g. dwd/radar, dwd/alerts) have no metadata model and thus no per-network
    # discover(); report that cleanly instead of raising an uncaught AttributeError (HTTP 500).
    if not hasattr(api, "discover"):
        raise HTTPException(
            status_code=404,
            detail=f"Coverage is not available for provider '{provider}' and network '{network}'.",
        )

    cov = api.discover(
        resolutions=request.resolutions,
        datasets=request.datasets,
    )

    return Response(content=json.dumps(cov, indent=4 if request.pretty else None), media_type="application/json")


@router.get("/glossary", response_model=list[GlossaryEntry])
def glossary(
    request: Annotated[GlossaryRequest, Query()],
) -> list[GlossaryEntry]:
    """Look up what a parameter measures and which unit it is returned in.

    Filter with parameter="radiation" to match names containing that text, or
    unit_type="temperature" for every parameter of one quantity. Both can be combined. Use limit to
    cap the number of entries: the vocabulary runs to several hundred parameters, so an unfiltered call is a
    large response and a broad filter can still be a wide one (parameter="temperature" matches
    nearly two hundred).

    This complements coverage: coverage says which parameters a given provider offers, this says
    what any of them means. The unit reported is the one a values request would actually return,
    including any `unit_targets` option override.
    """
    set_logging_level(debug=request.debug)
    # a malformed server setting is the app's unhandled 500, as for the data endpoints
    Settings()

    return get_glossary(parameter=request.parameter, unit_type=request.unit_type, limit=request.limit)


def _get_timeseries_api(provider: str, network: str, *, history: bool = False) -> type[TimeseriesRequest]:
    """Get the API of a network the timeseries endpoints serve, refusing one they cannot with a 404.

    A standalone network (dwd/radar, dwd/alerts) or, with `history`, a network without station
    history has nothing to answer these with, as a provider or network that does not exist.
    """
    try:
        api = Wetterdienst(provider, network)
        check_timeseries_api(api, provider, network, history=history)
    except ApiNotFoundError as e:
        msg = f"{e} Use {app.url_path_for('coverage')} to discover available providers and networks."
        log.info(f"Refused a provider and network without an API for the request: {msg}")
        raise HTTPException(status_code=404, detail=msg) from e
    except NotImplementedError as e:
        log.info(f"Refused a request for station history: {e}")
        raise HTTPException(status_code=404, detail=str(e)) from e
    return api


# response models for the different formats are
# - _StationsDict for json
# - _StationsOgcFeatureCollection for geojson
# - str for csv
@router.get(
    "/stations",
    response_model=_StationsDict | _StationsOgcFeatureCollection | str,
)
def stations(
    request: Annotated[StationsRequest, Query()],
) -> Response:
    """Find weather stations and their `station_id` (step 1 of the station -> values workflow).

    Requires provider, network and parameters (e.g. provider="dwd", network="observation",
    parameters="daily/kl"), and exactly one way of selecting stations: `name` for a place (e.g.
    name="Hamburg Fuhlsbüttel", optionally with `rank` for how many matches), `stations` ids,
    lat/lon with `rank` or `distance`, a bounding box, `sql` (where the server enables it), or
    all=true for the full list. `name` gives the best five matches unless `rank` says otherwise.
    Returns station metadata including `station_id`, which you pass to `values`.

    A `timestamp`, a date or an interval as for `values`, lists only the stations whose record
    overlaps it, so the nearest stations are not ones that closed decades ago. An id of `stations`
    the network has no station for is left out of the list, which is then empty or shorter, and
    named in a warning in the server's log; an empty list is a 200, not an error.
    """
    set_logging_level(debug=request.debug)
    _refuse_sql_unless_enabled(request)
    _refuse_oversized_chart(request)

    api = _get_timeseries_api(request.provider, request.network)

    # outside the handler below: nothing of the caller's reaches these settings, so a malformed
    # server setting is the app's unhandled 500, which does not read its value back
    settings = Settings()
    try:
        stations_ = get_stations(
            api=api,
            request=request,
            timestamp=request.timestamp,
            settings=settings,
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

    content = render_stations(stations_, request, max_side=_MAX_IMAGE_SIDE)

    media_type = _MEDIA_TYPES.get(request.format, "application/json")

    return Response(content=content, media_type=media_type)


@router.get("/issues")
def issues(
    request: Annotated[IssuesRequest, Query()],
) -> JSONResponse:
    """Return available issue datetimes for a provider/network/station combination.

    Currently supported: provider=dwd, network=mosmix|dmo|swsmos.
    """
    set_logging_level(debug=request.debug)

    try:
        api = Wetterdienst(request.provider, request.network)
    except ApiNotFoundError as e:
        msg = f"{e} Use {app.url_path_for('coverage')} to discover available providers and networks."
        log.info(f"Refused a provider and network without an API for the request: {msg}")
        raise HTTPException(status_code=404, detail=msg) from e

    # outside the handler below, as for `/api/stations`
    settings = Settings()
    try:
        issue_list = get_issues(api=api, request=request, settings=settings)
    except NotImplementedError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        raise _failure(e, request, "get issues") from e

    return JSONResponse(content={"issues": issue_list})


# response models for the different formats are
# - _ValuesWithSettingsDict for json
# - _ValuesWithSettingsOgcFeatureCollection for geojson
# - str for csv
@router.get(
    "/values",
    response_model=_ValuesWithSettingsDict | _ValuesWithSettingsOgcFeatureCollection | str,
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
    resolution, dataset and parameter, in timestamp order within each group: a parameter's latest
    timestamp is the last item of its group, not of the array. With shape="wide" an item is one
    timestamp of a station and resolution, with a key per parameter (prefixed with the full dataset
    name, e.g. "climate_summary_", when datasets of more than one name are requested), its
    `_quality_flags` key, no `parameter` key, and a null `dataset` where
    several datasets of its resolution are requested. With format="geojson" the items sit under each
    feature's `values`, keeping their order but not `station_id`; a feature is one resolution and
    dataset of one station (one resolution in the wide shape), so a station can have several. Do not
    re-request in other formats.
    """
    set_logging_level(debug=request.debug)
    _refuse_sql_unless_enabled(request)
    _refuse_oversized_chart(request)

    api = _get_timeseries_api(request.provider, request.network)

    # outside the handlers: nothing of the caller's reaches the server's settings, so a malformed one
    # is the app's unhandled 500, which does not read its value back
    settings = Settings()
    # a unit target given for a quantity or unit the converter has none for is the request's 400
    options = _request_options(request, http_request.query_params.keys(), ValuesSettings)

    values_ = _values(api=api, request=request, settings=settings, options=options)

    content = render(values_, request, ValuesSettings, options, max_side=_MAX_IMAGE_SIDE)

    media_type = _MEDIA_TYPES.get(request.format, "application/json")

    return Response(content=content, media_type=media_type)


def _request_options(request: BaseModel, given: Collection[str], applied: type[_AppliedSettings]) -> Options:
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


def _refusal_detail(e: Exception, what: str) -> str:
    """Word a refusal for a caller of this API, who passes the window as one `timestamp`.

    A request refuses a window that is missing or ends before it starts in terms of its `start` and
    `end`, and so does `_get_stations_request` for a dataset that is queried by a window and given
    none. A REST or MCP caller cannot pass either. Any other refusal is worded the request's way.
    """
    if isinstance(e, ReversedTimeIntervalError):
        return "the interval in timestamp ends before it starts"
    if isinstance(e, DateRequiredError):
        return "timestamp is required for this dataset"
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
    if isinstance(e, (NoInternetError, DownloadError)):
        log.warning(f"Failed to {what}: {e}")
    else:
        log.error(f"Failed to {what}.", exc_info=e)
    detail = {503: _UPSTREAM_UNREACHABLE, 504: _UPSTREAM_TIMED_OUT}.get(status, _UPSTREAM_FAILED)
    return HTTPException(status_code=status, detail=detail)


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
    return HTTPException(
        status_code=500,
        detail=f"Internal server error ({type(e).__name__}). The cause is in the server log.",
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
    return HTTPException(
        status_code=501,
        detail="This server is not configured to serve the request. The request was valid; "
        "ask whoever runs this instance.",
    )


def _server_side_failure(e: Exception, request: BaseModel, what: str) -> HTTPException:
    """Answer a failure that is not the request's own by its place in the hierarchy (`failure_status`).

    A credential or an optional dependency the server lacks is a 501 (the more specific answers say
    which); a provider that failed is a 502, 503 or 504; anything else is a logged traceback and a
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
        detail = _refusal_detail(e, what)
        log.info(f"Failed to {what}: {detail}")
        return HTTPException(status_code=status, detail=detail)
    return _server_side_failure(e, request, what)


def _values(
    api: type[TimeseriesRequest],
    request: ValuesRequest,
    settings: Settings,
    options: Options,
) -> ValuesResult:
    """Collect values, telling the caller which failures are theirs to fix.

    The sibling of `_geo_values` for the plain values endpoint, and lifted out of the endpoint for
    the same reason: which failure earns which status is a decision of its own, and the endpoint --
    which also assembles a response format, a target and a set of kwargs -- is not where it belongs.
    """
    try:
        return get_values(api=api, request=request, settings=settings, options=options)
    except AssertionError:
        # a request its model should have refused reached the lookup: our bug, which FastAPI answers
        # as a 500, not the caller's to fix
        raise
    except Exception as e:
        raise _failure(e, request, "get values") from e


def _geo_values(
    get: Callable[..., InterpolatedValuesResult | SummarizedValuesResult],
    api: type[TimeseriesRequest],
    request: InterpolationRequest | SummaryRequest,
    settings: Settings,
    options: Options,
    what: str,
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
    try:
        return get(api=api, request=request, settings=settings, options=options)
    except AssertionError:
        # a request its model should have refused reached the lookup: our bug, which FastAPI answers
        # as a 500, not the caller's to fix
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
)
def interpolate(
    request: Annotated[InterpolationRequest, Query()],
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
    set_logging_level(debug=request.debug)
    _refuse_sql_unless_enabled(request)
    _refuse_oversized_chart(request)

    api = _get_timeseries_api(request.provider, request.network)

    # outside the handlers, as for `/api/values`
    settings = Settings()
    options = _geo_options(request, http_request.query_params.keys(), "interpolation")

    values_ = _geo_values(get_interpolate, api, request, settings, options, "interpolate")

    content = render(values_, request, InterpolationSettings, options, max_side=_MAX_IMAGE_SIDE)

    media_type = _MEDIA_TYPES.get(request.format, "application/json")

    return Response(content=content, media_type=media_type)


# response models for the different formats are
# - _SummarizedValuesWithSettingsDict for json
# - _SummarizedValuesWithSettingsOgcFeatureCollection for geojson
# - str for csv
@router.get(
    "/summarize",
    response_model=_SummarizedValuesWithSettingsDict | _SummarizedValuesWithSettingsOgcFeatureCollection | str,
)
def summarize(
    request: Annotated[SummaryRequest, Query()],
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
    set_logging_level(debug=request.debug)
    _refuse_sql_unless_enabled(request)
    _refuse_oversized_chart(request)
    # dumped rather than read: reading a deprecated field warns of itself, a DeprecationWarning nobody sees
    if request.model_dump(include={"use_nearby_station_distance"})["use_nearby_station_distance"] is not None:
        log.warning(f"use_nearby_station_distance is deprecated. {SUMMARY_USE_NEARBY_STATION_DISTANCE_DEPRECATED}")

    api = _get_timeseries_api(request.provider, request.network)

    # outside the handlers, as for `/api/values`
    settings = Settings()
    options = _geo_options(request, http_request.query_params.keys(), "summary")

    values_ = _geo_values(get_summarize, api, request, settings, options, "summarize")

    content = render(values_, request, SummarySettings, options, max_side=_MAX_IMAGE_SIDE)

    media_type = _MEDIA_TYPES.get(request.format, "application/json")

    return Response(content=content, media_type=media_type)


@router.get("/stripes/stations")
def stripes_stations(
    request: Annotated[StripesStationsRequest, Query()],
) -> Response:
    """Wrap get_climate_stripes_temperature_request to provide results via restapi."""
    set_logging_level(debug=request.debug)

    # the provider request below builds its settings from the environment inside the handler: checked
    # here first, a malformed server setting is the app's unhandled 500, which does not read its
    # value back
    Settings()
    try:
        stations = _get_stripes_stations(kind=request.kind, active=request.active)
    except Exception as e:
        # nothing of the caller's reaches the lookup but a kind and a flag its request has checked,
        # so a failure here is the server's or the data source's, whatever its type
        raise _logged_server_error(e, "get stripes stations") from e
    content = stations.to_format(fmt=request.format, with_metadata=True, indent=request.pretty)
    media_type = "text/csv" if request.format == "csv" else "application/json"
    return Response(content=content, media_type=media_type)


@router.get("/stripes/values")
def stripes_values(
    request: Annotated[StripesValuesRequest, Query()],
) -> Response:
    """Get climate stripes data values with timestamps and metadata.

    The JSON metadata names the unit of the values in `unit`, e.g. "degree_celsius". The server's
    WD_TS_CONVERT_UNITS and WD_TS_UNIT_TARGETS set it, which a stripes request has no parameter
    for: the target of the quantity where the values are converted, the source's unit where not.
    """
    set_logging_level(debug=request.debug)

    # checked outside the handler below, as for `/api/stripes/stations`
    Settings()
    try:
        stripes_data = _get_stripes_data(request)
    except AssertionError:
        # a request its model should have refused: our bug, which FastAPI answers as a 500
        raise
    except Exception as e:
        raise _failure(e, request, "get stripes data") from e

    if request.format == "csv":
        content = timestamps_to_string(stripes_data.df).write_csv()
        media_type = "text/csv"
    else:
        data = {
            "metadata": stripes_data.metadata.model_dump(),
            "values": [
                {
                    "timestamp": format_timestamp(row["timestamp"]) if row["timestamp"] else None,
                    "value": row["value"],
                }
                for row in stripes_data.df.select("timestamp", "value").iter_rows(named=True)
            ],
        }
        content = json.dumps(data, indent=4 if request.pretty else None)
        media_type = "application/json"

    return Response(content=content, media_type=media_type)


@router.get("/stripes/image")
def stripes_image(
    request: Annotated[StripesImageRequest, Query()],
) -> Response:
    """Generate climate stripes image for a station."""
    set_logging_level(debug=request.debug)
    # the image is rendered at `dpi / 100` times plotly's default size
    _refuse_oversized_image(None, None, request.dpi / 100, lower="dpi")

    # checked outside the handler below, as for `/api/stripes/stations`
    Settings()
    try:
        fig = _plot_stripes(request)
    except AssertionError:
        # a request its model should have refused: our bug, which FastAPI answers as a 500
        raise
    except Exception as e:
        raise _failure(e, request, "plot stripes") from e
    require_kaleido()
    return Response(
        content=fig.to_image(request.format, scale=request.dpi / 100),
        media_type=_MEDIA_TYPES.get(request.format, "application/octet-stream"),
    )


@router.get("/history")
def history(
    request: Annotated[HistoryRequest, Query()],
) -> Response:
    """Return a station's metadata history -- how the station itself changed over time (not weather).

    Provides the record of a station's name, position, sensors/devices and data-gap sections across
    its lifetime, for auditing station changes. This is NOT weather or measurement history: for past
    measurements use the stations -> values workflow with a `timestamp` or interval. Requires provider,
    network, parameters and either `stations` ids or all=true.
    """
    set_logging_level(debug=request.debug)

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

    try:
        history_provider = stations_.history()
    except Exception as e:
        # past the station lookup the request has nothing left to refuse: what fails from here on
        # is the server's or the data source's, whatever its type
        raise _logged_server_error(e, "acquire history provider") from e

    try:
        content = history_provider.to_json(
            with_metadata=request.with_metadata,
            with_stations=request.with_stations,
            sections=request.sections,
            indent=4 if request.pretty else None,
        )
    except Exception as e:
        raise _logged_server_error(e, "collect station history") from e
    return Response(content=content, media_type="application/json")


@router.get("/alerts")
def alerts(
    request: Annotated[AlertsRequest, Query()],
) -> Response:
    """Provide DWD weather alerts (CAP warnings) via restapi.

    Returns all warnings active at the selected time, one entry per alert, with a GeoJSON
    MultiPolygon geometry. ``timestamp`` (ISO 8601, UTC if no offset) selects a historical snapshot from
    DWD's rolling ~48-hour window; omit it for the latest snapshot. An empty result simply means
    there were no active warnings.
    """
    from wetterdienst.provider.dwd.alerts import DwdWeatherAlertRequest  # noqa: PLC0415

    set_logging_level(debug=request.debug)

    # outside the handlers below, as for `/api/stations`
    settings = Settings()
    try:
        alerts_request = DwdWeatherAlertRequest(
            granularity=request.granularity, language=request.language, timestamp=request.timestamp, settings=settings
        )
        result = alerts_request.query()
    except Exception as e:
        # a date that does not parse, one an offset carries out of what a datetime holds, or one
        # before DWD's rolling window is the request's; a feed that does not list, download or read,
        # and an alert in it the parser does not expect, is the provider's (GH-2985)
        raise _failure(e, request, "get weather alerts") from e

    content = result.to_format(request.format, indent=request.pretty)
    media_type = "text/csv" if request.format == "csv" else "application/json"
    return Response(content=content, media_type=media_type)


def _mount_mcp(rest_app: FastAPI) -> bool:
    """Mount an MCP endpoint at ``/mcp`` onto ``rest_app``, if the optional ``[mcp]`` extra is present.

    The MCP server (see :mod:`wetterdienst.ui.mcp`) is generated from the REST API's own routes, so
    the ``/mcp`` transport stays in lockstep with the HTTP API, with a workflow ``instructions``
    block and clean tool names layered on for agent usability. The MCP streamable-http session
    manager runs via the sub-app's lifespan, which is *composed* with ``rest_app``'s existing
    lifespan here (not replaced), so any current or future app startup/shutdown still runs; the
    existing REST routes keep working with or without the lifespan running.

    Returns ``True`` when the endpoint was mounted, ``False`` when the optional ``[mcp]`` extra is not
    installed or the MCP server could not be built (so the ``/mcp`` route is strictly optional and a
    build error never takes down the plain REST API).
    """
    try:
        from fastmcp.utilities.lifespan import combine_lifespans  # noqa: PLC0415

        from wetterdienst.ui.mcp import build_mcp_server  # noqa: PLC0415

        mcp_app = build_mcp_server(rest_app).http_app(path="/mcp")
    except ModuleNotFoundError as exc:
        # optional [mcp] extra (fastmcp, httpx2) not installed -> plain REST API, no /mcp route.
        # Said out loud, because an instance missing /mcp for want of a dependency otherwise looks
        # exactly like one that was never meant to have it.
        log.info("No MCP endpoint: %s is not installed (optional [mcp] extra), continuing without /mcp", exc.name)
        return False
    except Exception:
        # never let an MCP build/version error take down the whole REST API; degrade to no /mcp
        log.exception("Failed to build the MCP endpoint; continuing without /mcp")
        return False

    # Add the /mcp route(s) to the existing app and compose the MCP session-manager lifespan with the
    # app's existing lifespan (rather than replacing it, which would drop any app startup/shutdown).
    rest_app.router.routes.extend(mcp_app.router.routes)
    rest_app.router.lifespan_context = combine_lifespans(
        rest_app.router.lifespan_context,
        mcp_app.router.lifespan_context,
    )
    log.info("MCP endpoint mounted at /mcp")
    return True


# the alias first, so that a route's name resolves to `/api/...` (`url_path_for`), the path the messages
# of the errors send a caller to and the one the app and the docs use. Which comes first does not
# matter to OpenAPI, which lists the versioned routes alone
app.include_router(router, prefix=API_ALIAS_PREFIX, include_in_schema=False)
app.include_router(router, prefix=API_PREFIX)

mcp_enabled = _mount_mcp(app)


def start_service(listen_address: str | None = None, *, reload: bool | None = False) -> None:
    """Start the REST API service."""
    run = import_optional("uvicorn.main", "The REST API", extra="restapi").run

    setup_logging()

    if listen_address is None:
        listen_address = "127.0.0.1:7890"

    host, port = listen_address.split(":")
    port = int(port)

    run(app="wetterdienst.ui.restapi:app", host=host, port=port, reload=reload or False)
