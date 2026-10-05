# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Utilities for the wetterdienst package."""

from __future__ import annotations

import json
import logging
import math
from textwrap import dedent
from typing import TYPE_CHECKING, Annotated, Any, Literal, TypeVar

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response
from pydantic import BaseModel, ConfigDict, Field, ValidationError, WithJsonSchema
from typing_extensions import NotRequired

from wetterdienst import Author, Info, Settings, Wetterdienst, __version__
from wetterdienst.exceptions import (
    ApiNotFoundError,
    BufrReaderMissingError,
    InvalidTimeIntervalError,
    NoStationsWithElevationError,
    ParameterNotCarriedError,
    StartDateEndDateError,
)
from wetterdienst.metadata.resolution import Resolution

# needed at runtime: FastAPI resolves this annotation to build the query parameter's enum
from wetterdienst.metadata.unit_type import UnitType  # noqa: TC001
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
from wetterdienst.model.unit import UnitConverter
from wetterdienst.settings import SkipThreshold, check_settings
from wetterdienst.ui.core import (
    SUMMARY_USE_NEARBY_STATION_DISTANCE_DEPRECATED,
    GlossaryEntry,
    HistoryRequest,
    InterpolationRequest,
    IssuesRequest,
    SettingsRequest,
    StationsRequest,
    StripesImageRequest,
    StripesValuesRequest,
    SummaryRequest,
    ValuesRequest,
    _get_stripes_data,
    _get_stripes_stations,
    _is_caller_refusal,
    _plot_stripes,
    get_glossary,
    get_interpolate,
    get_issues,
    get_stations,
    get_summarize,
    get_values,
    limit_stations_to_rank,
    select_history_sections,
    set_logging_level,
)
from wetterdienst.util.cli import setup_logging
from wetterdienst.util.ui import read_list

if TYPE_CHECKING:
    from collections.abc import Callable, Collection

    from starlette.types import ASGIApp, Receive, Scope, Send

    from wetterdienst.model.request import TimeseriesRequest
    from wetterdienst.model.result import InterpolatedValuesResult, SummarizedValuesResult, ValuesResult

info = Info()

app = FastAPI(debug=False)


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
    "dwd_observation_daily_climate_values": "api/values?provider=dwd&network=observation&parameters=daily/kl&periods=recent&station=00011",  # noqa:E501
    "dwd_observation_daily_climate_history": "api/history?provider=dwd&network=observation&parameters=daily/kl&station=00011",  # noqa:E501
    "dwd_observation_daily_climate_interpolation": "api/interpolate?provider=dwd&network=observation&parameters=daily/kl/temperature_air_mean_2m&station=00071&date=1986-10-31/1986-11-01",  # noqa:E501
    "dwd_observation_daily_climate_summary": "api/summarize?provider=dwd&network=observation&parameters=daily/kl/temperature_air_mean_2m&station=00071&date=1986-10-31/1986-11-01",  # noqa:E501
    "dwd_observation_daily_climate_stripes_stations": "api/stripes/stations?kind=temperature",
    "dwd_observation_daily_climate_stripes_values": "api/stripes/values?kind=temperature&station=1048",
    "dwd_observation_daily_climate_stripes_image": "api/stripes/image?kind=temperature&station=1048",
    "dwd_mosmix_issues": "api/issues?provider=dwd&network=mosmix&station=10147",
    "dwd_dmo_issues": "api/issues?provider=dwd&network=dmo&station=10147",
    "dwd_swsmos_issues": "api/issues?provider=dwd&network=swsmos&station=A006",
    "dwd_weather_alerts": "api/alerts?granularity=community&format=geojson",
}


def _reader_missing_on_the_server(e: BufrReaderMissingError, what: str) -> HTTPException:
    """Report a reader this deployment does not have as the server's lack, not the caller's error.

    The blanket handlers answered it with a 400 carrying `pip install wetterdienst[bufr]` -- an
    instruction for a machine the caller does not administer, about a request that was perfectly
    well formed. Over HTTP the missing half is a property of the deployment, and 501 is what says
    so: this server does not implement the networks published as BUFR. The install line is not
    lost, it moves to where someone can act on it -- the server log, carried there by the message
    itself rather than by a traceback, since a dependency that was never installed has no incident
    to show.
    """
    log.error(f"Failed to {what}, this deployment cannot decode BUFR: {e}")
    return HTTPException(
        status_code=501,
        detail=(
            "This server cannot decode BUFR, which the requested network is published as. The "
            "request was valid; the deployment is missing the eccodes and pdbufr readers that "
            "read it. Ask whoever runs this instance to install them."
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


#: a radius, factor or gain, which the settings take as infinite or NaN too, written then as a string
_Unbounded = Annotated[
    float,
    WithJsonSchema(
        {"anyOf": [{"type": "number"}, {"type": "string", "enum": ["Infinity", "NaN"]}]}, mode="serialization"
    ),
]


# The settings a request to `/api/values`, `/api/interpolate` and `/api/summarize` is answered with,
# by the request field that sets each, and with the setting it sets as its validation alias. The REST
# API's one list of them: an endpoint takes these from its request (GH-2325), reports the ones it
# used with its metadata, and `/api/settings` reports the server's defaults for them (GH-2359), or
# what the query parameters it is given resolve to over those (GH-2383).
# Listed one by one rather than read from `Settings`, so that neither report reaches a credential or
# the cache.
class _AppliedSettings(BaseModel):
    """The settings every one of the three endpoints is answered with."""

    # by name too, so that a report, which is written by name, reads back. A radius, factor or gain
    # the settings take as infinite is written as the string "Infinity", which JSON has no number for
    model_config = ConfigDict(extra="forbid", populate_by_name=True, ser_json_inf_nan="strings")

    humanize: bool = Field(validation_alias="ts_humanize")
    convert_units: bool = Field(validation_alias="ts_convert_units")
    unit_targets: dict[str, str] = Field(
        validation_alias="ts_unit_targets",
        description="The unit values of each quantity are converted to, for every quantity, where `convert_units` "
        "is on; off, they come in the unit the source publishes.",
    )
    skip_empty: bool = Field(validation_alias="ts_skip_empty")
    skip_threshold: SkipThreshold = Field(validation_alias="ts_skip_threshold")
    skip_criteria: Literal["min", "mean", "max"] = Field(validation_alias="ts_skip_criteria")
    drop_nulls: bool = Field(
        validation_alias="ts_drop_nulls",
        description="Whether rows without a value are dropped. The wide shape, the server's or the request's, "
        "turns it off.",
    )


class ValuesSettings(_AppliedSettings):
    """The settings of `/api/values`."""

    shape: Literal["long", "wide"] = Field(validation_alias="ts_shape")


_STATION_DISTANCE_DESCRIPTION = (
    "The radius (km) set for a parameter by name, which applies at every resolution. A parameter it "
    "leaves out takes the homogeneous or the heterogeneous radius."
)
_STATION_DISTANCE_HETEROGENEOUS_DESCRIPTION = (
    "The radius (km) of a parameter that decorrelates fast, at hourly resolution: at another "
    "resolution it is multiplied by that resolution's factor."
)


class _GeoSettings(_AppliedSettings):
    """The settings `/api/interpolate` and `/api/summarize` share."""

    min_gain_of_value_pairs: _Unbounded = Field(validation_alias="ts_geo_min_gain_of_value_pairs")
    num_additional_stations: int = Field(validation_alias="ts_geo_num_additional_stations")
    # set by the server alone, as are the skipping of sparse stations and the dropping of nulls
    # here: neither request has a field for them, and the stations' values are read with them
    station_distance_resolution_factors: dict[str, _Unbounded] = Field(
        validation_alias="ts_geo_station_distance_resolution_factors",
        description="The factor the heterogeneous radius is multiplied by, for every resolution. Set by the "
        "server alone.",
    )


class InterpolationSettings(_GeoSettings):
    """The settings of `/api/interpolate`."""

    # not read for a summary, which has nothing for it to decide: its field is only accepted there,
    # and deprecated (GH-2333), so a summary neither passes nor reports it
    use_nearby_station_distance: _Unbounded | None = Field(validation_alias="ts_geo_use_nearby_station_distance")
    interpolation_station_distance: dict[str, _Unbounded] = Field(
        validation_alias="ts_geo_station_distance",
        description=_STATION_DISTANCE_DESCRIPTION,
    )
    interpolation_station_distance_homogeneous: _Unbounded = Field(
        validation_alias="ts_geo_station_distance_homogeneous"
    )
    interpolation_station_distance_heterogeneous: _Unbounded = Field(
        validation_alias="ts_geo_station_distance_heterogeneous",
        description=_STATION_DISTANCE_HETEROGENEOUS_DESCRIPTION,
    )


class SummarySettings(_GeoSettings):
    """The settings of `/api/summarize`."""

    summary_station_distance: dict[str, _Unbounded] = Field(
        validation_alias="ts_geo_station_distance",
        description=_STATION_DISTANCE_DESCRIPTION,
    )
    summary_station_distance_homogeneous: _Unbounded = Field(validation_alias="ts_geo_station_distance_homogeneous")
    summary_station_distance_heterogeneous: _Unbounded = Field(
        validation_alias="ts_geo_station_distance_heterogeneous",
        description=_STATION_DISTANCE_HETEROGENEOUS_DESCRIPTION,
    )


_M = TypeVar("_M", bound=_AppliedSettings)


class ServerSettings(BaseModel):
    """What each endpoint takes for a setting a request leaves out."""

    model_config = ConfigDict(extra="forbid")

    values: ValuesSettings
    interpolate: InterpolationSettings
    summarize: SummarySettings


def _applied_settings(model: type[_M], settings: Settings) -> _M:
    """Report `settings` by the fields of `model`.

    The unit targets and the resolution factors hold only the entries that depart from
    wetterdienst's, and are reported whole: the unit of every quantity and the factor of every
    resolution. The per-parameter radii are reported as given, as `Settings` dumps them, since a
    parameter they leave out takes one of the two radii reported next to them. `drop_nulls` is
    reported as in effect, which the wide shape turns off.
    """

    def unit_targets() -> dict[str, str]:
        converter = UnitConverter()
        converter.update_targets(settings.ts_unit_targets)
        return {quantity: unit.name for quantity, unit in converter.targets.items()}

    reported: dict[str, Callable[[], object]] = {
        "ts_unit_targets": unit_targets,
        "ts_drop_nulls": lambda: settings.ts_drop_nulls_effective,
        "ts_geo_station_distance": lambda: settings.model_dump(include={"ts_geo_station_distance"})[
            "ts_geo_station_distance"
        ],
        "ts_geo_station_distance_resolution_factors": lambda: {
            resolution.value: settings.ts_geo_station_distance_resolution_factor(resolution.value)
            for resolution in Resolution
        },
    }
    return model.model_validate(
        {
            setting: reported[setting]() if setting in reported else getattr(settings, setting)
            for setting in (str(field.validation_alias) for field in model.model_fields.values())
        },
    )


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
        return f"{author.name} (<a href='https://github.com/{author.github_handle}' target='_blank' rel='noopener'>github</a>, <a href='mailto:{author.email}'>mail</a>)"  # noqa:E501

    title = f"{info.slogan} | {info.name}"
    provider_rows = []

    for provider in Wetterdienst.registry:
        # take the first network api
        first_network = next(iter(Wetterdienst.registry[provider].keys()))
        api = Wetterdienst(provider, first_network)
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


@app.get("/api/version")
def version() -> JSONResponse:
    """Get version information, and whether this instance serves an MCP endpoint.

    `mcp_enabled` is read at request time rather than captured at import: `_mount_mcp` sets it at
    the bottom of this module, after the routes are declared. It is reported here because the
    endpoint is optional -- an instance installed without the `[mcp]` extra has no `/mcp` route --
    and a client has no other way to find out short of probing `/mcp`, which on the streamable-HTTP
    transport means opening a session rather than asking a question.
    """
    return JSONResponse(content={"version": __version__, "mcp_enabled": mcp_enabled})


# each endpoint's settings, by the request it takes them from
_ENDPOINT_SETTINGS: tuple[tuple[str, type[BaseModel], type[_AppliedSettings]], ...] = (
    ("values", ValuesRequest, ValuesSettings),
    ("interpolate", InterpolationRequest, InterpolationSettings),
    ("summarize", SummaryRequest, SummarySettings),
)


@app.get("/api/settings", response_model=ServerSettings)
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
    # a malformed server setting is the bare 500 FastAPI answers, which does not read its value back.
    # Built once for the endpoints no parameter given applies to, as each build reads the
    # environment and the `.env` again, and logs where the cache is
    server = Settings()
    reported: dict[str, _AppliedSettings] = {}
    refused: list[str] = []
    for endpoint, taking, applied in _ENDPOINT_SETTINGS:
        # a parameter applies to every endpoint whose request takes it, and to no other
        taken = [name for name in given if name in taking.model_fields]
        try:
            settings = _request_settings(request, taken, applied) if taken else server
        except HTTPException as e:
            # a value two endpoints refuse is told once
            refused.extend(line for line in str(e.detail).split("\n") if line not in refused)
            continue
        reported[endpoint] = _applied_settings(applied, settings)
    if refused:
        raise HTTPException(status_code=400, detail="\n".join(refused))
    content = ServerSettings.model_validate(reported)
    return Response(content=content.model_dump_json(), media_type="application/json")


def _openapi() -> dict[str, Any]:
    """Build the OpenAPI schema, giving each settings query parameter the server's value as its default (GH-2393).

    A settings parameter a request to `/api/values`, `/api/interpolate`, `/api/summarize` or
    `/api/settings` leaves out takes the server's value, but the schema advertised wetterdienst's,
    which a client filling in the defaults then sent, hiding the server's. Each default is now the
    one `/api/settings` reports for the endpoint without parameters, worked out as it does it:
    `_applied_settings` over `Settings()`. `drop_nulls` alone is the server's as set, not the one
    in effect that `/api/settings` reports: leaving it out means the value set whatever the shape,
    which decides only whether it applies, so a client that fills it in and asks for the long
    shape on a wide server still drops nulls. A parameter for `/api/settings` takes the value of
    the endpoint it applies to. The request models keep wetterdienst's defaults in Python, which
    the CLI builds its requests with, and FastAPI fills in for a parameter left out, which the
    endpoints do not pass on (`_request_settings`).

    A parameter whose request field defaults to None has no schema default and keeps none: the
    radii and the JSON-encoded dicts (`unit_targets`, the station distances). A dict given is
    merged into the server's, so a client leaving it out gets the server's already, and the
    server's whole dict, a unit for every quantity, would be sent back as a request's own were it
    the default; `/api/settings` reports it.

    Built once per process: with the `[mcp]` extra, as the module is imported, by the MCP endpoint,
    whose tools' defaults are then the server's too, and else on the first request for the schema.
    It is kept as FastAPI keeps it, and a recent FastAPI builds it again, reading `Settings()`
    anew, only for a route added. A `.env` edited after the build reaches the requests and
    `/api/settings`, which read `Settings()` each time, but not the schema, until the server is
    restarted.
    """
    kept = app.openapi_schema
    schema = FastAPI.openapi(app)
    if schema is kept:
        return schema
    try:
        server = Settings()
    except Exception:  # noqa: BLE001
        # malformed, which the server refuses to start for, naming each variable without its
        # value (`_RefuseInvalidSettings`). Reached as the module is imported, by the MCP build,
        # which would log the error with the values. Built with wetterdienst's defaults then,
        # and not kept, so that a later call takes the server's
        app.openapi_schema = None
        return schema
    defaults = {
        f"/api/{endpoint}": {
            field: value
            for field, value in _applied_settings(applied, server).model_dump().items()
            if field in taking.model_fields and taking.model_fields[field].default is not None
        }
        for endpoint, taking, applied in _ENDPOINT_SETTINGS
    }
    defaults["/api/values"]["drop_nulls"] = server.ts_drop_nulls
    # a parameter several endpoints take sets one setting, which each reports alike
    defaults["/api/settings"] = {
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


@app.get("/api/auth")
def auth(
    provider: str,
    network: str,
    *,
    debug: bool = False,
) -> JSONResponse:
    """Check whether the credentials for an auth-required provider are present and valid.

    Returns `{"provider": ..., "network": ..., "auth": bool, "configured": bool, "valid": bool}`.
    For providers that do not require authentication, `auth` is false and `configured`/`valid` are true.
    `configured` reflects whether credentials are present; `valid` whether a probe request succeeded.
    `valid` is false whenever `configured` is false (a probe cannot be performed without credentials).
    """
    set_logging_level(debug=debug)

    try:
        api = Wetterdienst(str(provider), str(network))
    except (ApiNotFoundError, ImportError) as e:
        raise HTTPException(
            status_code=404,
            detail=f"Choose provider and network from {app.url_path_for('coverage')}",
        ) from e

    metadata = getattr(api, "metadata", None)
    requires_auth = metadata.auth if metadata is not None else False
    is_configured = getattr(api, "is_configured", lambda: True)
    is_valid = getattr(api, "is_valid", lambda: True)
    configured = is_configured() if requires_auth else True
    if not requires_auth:
        valid = True
    elif not configured:
        valid = False
    else:
        try:
            valid = is_valid()
        except Exception:  # noqa: BLE001
            valid = False
    return JSONResponse(
        content={
            "provider": provider,
            "network": network,
            "auth": requires_auth,
            "configured": configured,
            "valid": valid,
        }
    )


@app.get("/api/coverage")
def coverage(
    provider: str | None = None,
    network: str | None = None,
    resolutions: str | None = None,
    datasets: str | None = None,
    *,
    pretty: bool = False,
    debug: bool = False,
) -> Response:
    """List available data: providers/networks, or the resolutions, datasets and parameters within one.

    Call with no arguments to list every provider and its networks. Pass provider+network (e.g.
    provider="dwd", network="observation") to list its resolutions/datasets/parameters; narrow with
    resolutions=... or datasets=... (e.g. datasets="climate_summary") to discover parameter names.
    """
    set_logging_level(debug=debug)

    if (provider and not network) or (not provider and network):
        raise HTTPException(
            status_code=400,
            detail="Either both or none of 'provider' and 'network' must be given. If none are given, all providers "
            "and networks are returned.",
        )

    if not provider and not network:
        cov = Wetterdienst.discover()
        return Response(content=json.dumps(cov, indent=4), media_type="application/json")

    try:
        api = Wetterdienst(str(provider), str(network))
    except KeyError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Choose provider and network from {app.url_path_for('coverage')}",
        ) from e

    # Standalone networks (e.g. dwd/radar, dwd/alerts) have no metadata model and thus no per-network
    # discover(); report that cleanly instead of raising an uncaught AttributeError (HTTP 500).
    if not hasattr(api, "discover"):
        raise HTTPException(
            status_code=404,
            detail=f"Coverage is not available for provider '{provider}' and network '{network}'.",
        )

    resolutions_list: list[str] | None = read_list(resolutions) if resolutions else None
    datasets_list: list[str] | None = read_list(datasets) if datasets else None

    cov = api.discover(
        resolutions=resolutions_list,
        datasets=datasets_list,
    )

    return Response(content=json.dumps(cov, indent=4 if pretty else None), media_type="application/json")


@app.get("/api/glossary", response_model=list[GlossaryEntry])
def glossary(
    parameter: str | None = None,
    unit_type: UnitType | None = None,
    limit: int | None = None,
    *,
    debug: bool = False,
) -> list[GlossaryEntry]:
    """Look up what a parameter measures and which unit it is returned in.

    Filter with parameter="radiation" to match names containing that text, or
    unit_type="temperature" for every parameter of one quantity. Both can be combined. Use limit to
    cap the number of entries: the vocabulary runs to several hundred parameters, so an unfiltered call is a
    large response and a broad filter can still be a wide one (parameter="temperature" matches
    nearly two hundred).

    This complements coverage: coverage says which parameters a given provider offers, this says
    what any of them means. The unit reported is the one a values request would actually return,
    including any ts_unit_targets override.
    """
    set_logging_level(debug=debug)

    return get_glossary(parameter=parameter, unit_type=unit_type, limit=limit)


# response models for the different formats are
# - _StationsDict for json
# - _StationsOgcFeatureCollection for geojson
# - str for csv
@app.get(
    "/api/stations",
    response_model=_StationsDict | _StationsOgcFeatureCollection | str,
)
def stations(
    request: Annotated[StationsRequest, Query()],
) -> Response:
    """Find weather stations and their `station_id` (step 1 of the station -> values workflow).

    Requires provider, network and parameters (e.g. provider="dwd", network="observation",
    parameters="daily/kl"), and exactly one way of selecting stations: `name` for a place (e.g.
    name="Hamburg Fuhlsbüttel", optionally with `rank` for how many matches), `station` id(s),
    lat/lon with `rank` or `distance`, a bounding box, `sql` (where the server enables it), or
    all=true for the full list. Returns station metadata including `station_id`, which you pass to
    `values`.
    """
    set_logging_level(debug=request.debug)
    _refuse_sql_unless_enabled(request)

    try:
        api = Wetterdienst(request.provider, request.network)
    except ApiNotFoundError as e:
        msg = f"{e} Use {app.url_path_for('coverage')} to discover available providers and networks."
        log.exception(msg)
        raise HTTPException(status_code=404, detail=msg) from e

    # outside the handler below: nothing of the caller's reaches these settings, so a malformed
    # server setting is the bare 500 FastAPI answers, which does not read its value back
    settings = Settings()
    try:
        stations_ = get_stations(
            api=api,
            request=request,
            date=None,
            settings=settings,
        )
    except AssertionError:
        # a request its model should have refused reached the lookup: our bug, which FastAPI answers
        # as a 500, not the caller's to fix
        raise
    except Exception as e:
        log.exception("Failed to get stations.")
        raise HTTPException(status_code=400 if _is_caller_refusal(e, request) else 500, detail=str(e)) from e

    # A rank filter keeps all stations in the frame (rank is applied lazily during value collection);
    # for a plain listing return just the N closest the caller asked for instead of every station.
    stations_ = limit_stations_to_rank(stations_)

    # build kwargs dynamically
    kwargs: dict[str, Any] = {
        "fmt": request.format,
        "with_metadata": request.with_metadata,
    }
    if request.format in ("json", "geojson"):
        kwargs["indent"] = request.pretty
    if request.format in ("png", "jpg", "webp", "svg", "pdf"):
        kwargs["width"] = request.width
        kwargs["height"] = request.height
        kwargs["scale"] = request.scale

    content = stations_.to_format(**kwargs)

    media_type = _MEDIA_TYPES.get(request.format, "application/json")

    return Response(content=content, media_type=media_type)


@app.get("/api/issues")
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
        log.exception(msg)
        raise HTTPException(status_code=404, detail=msg) from e

    # outside the handler below, as for `/api/stations`
    settings = Settings()
    try:
        issue_list = get_issues(api=api, request=request, settings=settings)
    except NotImplementedError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.exception("Failed to get issues.")
        raise HTTPException(status_code=400 if _is_caller_refusal(e, request) else 500, detail=str(e)) from e

    return JSONResponse(content={"issues": issue_list})


# response models for the different formats are
# - _ValuesWithSettingsDict for json
# - _ValuesWithSettingsOgcFeatureCollection for geojson
# - str for csv
@app.get(
    "/api/values",
    response_model=_ValuesWithSettingsDict | _ValuesWithSettingsOgcFeatureCollection | str,
)
def values(
    request: Annotated[ValuesRequest, Query()],
    http_request: Request,
) -> Response:
    """Get measured values for station(s) (step 2 of the station -> values workflow).

    Requires provider, network, parameters and exactly one station selection, as for `stations`.
    Use parameters as "resolution/dataset/parameter" (e.g.
    "daily/climate_summary/temperature_air_mean_2m") to keep the response small, and `station` with
    an id from `stations` (e.g. station="01975"). `periods` is optional and provider-specific --
    "recent" for dwd/observation, while a provider that publishes under a single period rejects any
    other one. In the JSON of shape="long", the default unless the server's WD_TS_SHAPE says
    otherwise, the `values` items are grouped by station, then by
    resolution, dataset and parameter, in timestamp order within each group: a parameter's latest
    timestamp is the last item of its group, not of the array. With shape="wide" an item is one
    timestamp of a station and resolution, with a key per parameter (prefixed with the full dataset
    name, e.g. "climate_summary_", when datasets of more than one name are requested) and its
    `_quality` key, no `parameter` key, and a null `dataset` where several datasets of its resolution
    are requested. With format="geojson" the items sit under each feature's `values`, keeping their
    order but not `station_id`; a feature is one resolution and dataset of one station (one
    resolution in the wide shape), so a station can have several. Do not re-request in other formats.
    """
    set_logging_level(debug=request.debug)
    _refuse_sql_unless_enabled(request)

    try:
        api = Wetterdienst(request.provider, request.network)
    except ApiNotFoundError as e:
        msg = f"{e} Use {app.url_path_for('coverage')} to discover available providers and networks."
        log.exception(msg)
        raise HTTPException(status_code=404, detail=msg) from e

    # a unit target given for a quantity or unit the converter has none for is the request's 400
    settings = _request_settings(request, http_request.query_params.keys(), ValuesSettings)

    values_ = _values(api=api, request=request, settings=settings)

    # build kwargs dynamically
    kwargs: dict[str, Any] = {
        "fmt": request.format,
        "with_metadata": request.with_metadata,
        "with_stations": request.with_stations,
    }
    if request.format in ("json", "geojson"):
        kwargs["indent"] = request.pretty
    if request.format in ("png", "jpg", "webp", "svg", "pdf"):
        kwargs["width"] = request.width
        kwargs["height"] = request.height
        kwargs["scale"] = request.scale

    content = _render(values_, request, kwargs, ValuesSettings, settings)

    media_type = _MEDIA_TYPES.get(request.format, "application/json")

    return Response(content=content, media_type=media_type)


def _request_settings(request: BaseModel, given: Collection[str], applied: type[_AppliedSettings]) -> Settings:
    """Build an endpoint's settings from the server's and the fields the request gave.

    `applied` lists the endpoint's settings by the request field that sets each, and `given` names
    the query parameters the request came with. A field is passed only when given: FastAPI fills
    one the query leaves out with its default, and an init argument outranks the environment, so
    passing that default would hide the `WD_TS_*` variable the server sets for the setting.

    The server's own settings are built first, and outside the handler: one malformed there is the
    bare 500 FastAPI answers, which does not read its value back. Where an error is located would
    not tell, as pydantic-settings merges a dict the environment sets into the one the request
    gives. With the server's valid on their own, an error once the request's fields are added is
    the request's, and is told by its field with the value the request gave, not the dict merged
    from it and the server's.
    """
    Settings()
    # each setting given by the field that sets it
    passed = {
        str(setting.validation_alias): (field, value)
        for field, setting in applied.model_fields.items()
        # not a setting the request has no field for, which the server sets alone
        if field in type(request).model_fields and field in given and (value := getattr(request, field)) is not None
    }
    try:
        return Settings(**{setting: value for setting, (_, value) in passed.items()})
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


def _render(
    result: ValuesResult | InterpolatedValuesResult | SummarizedValuesResult,
    request: ValuesRequest | InterpolationRequest | SummaryRequest,
    kwargs: dict[str, Any],
    applied: type[_AppliedSettings],
    settings: Settings,
) -> str | bytes:
    """Render a result in the format `kwargs` names, the JSON formats with the settings `applied`.

    The settings go next to the metadata, with `with_metadata` alone, and the rest is written as
    `to_json` and `to_geojson` write it.
    """
    if not request.with_metadata or request.format not in ("json", "geojson"):
        return result.to_format(**kwargs)
    if request.format == "json":
        data: dict[str, Any] = dict(result.to_dict(with_metadata=True, with_stations=request.with_stations))
    else:
        data = dict(result.to_ogc_feature_collection(with_metadata=True))
    report = json.loads(_applied_settings(applied, settings).model_dump_json())
    data = {"metadata": data.pop("metadata"), "settings": report, **data}
    return json.dumps(data, indent=4 if request.pretty else None, ensure_ascii=request.format == "json")


def _geo_settings(
    request: InterpolationRequest | SummaryRequest,
    given: Collection[str],
    kind: Literal["interpolation", "summary"],
) -> Settings:
    """Build the settings shared by the interpolation and the summary endpoint.

    `kind` picks the endpoint's settings, which name its request's station distance fields.
    """
    # a distance given for a name that is not a canonical parameter, or a unit target for an
    # unknown quantity or unit, is the request's 400
    return _request_settings(request, given, InterpolationSettings if kind == "interpolation" else SummarySettings)


def _values(
    api: type[TimeseriesRequest],
    request: ValuesRequest,
    settings: Settings,
) -> ValuesResult:
    """Collect values, telling the caller which failures are theirs to fix.

    The sibling of `_geo_values` for the plain values endpoint, and lifted out of the endpoint for
    the same reason: which failure earns which status is a decision of its own, and the endpoint --
    which also assembles a response format, a target and a set of kwargs -- is not where it belongs.
    """
    try:
        return get_values(api=api, request=request, settings=settings)
    except ParameterNotCarriedError as e:
        # the message is the whole of it: which parameters, and the lead time that carries them
        log.info(f"Failed to get values: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except StartDateEndDateError as e:
        log.exception("Failed to get values.")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except BufrReaderMissingError as e:
        raise _reader_missing_on_the_server(e, "get values") from e
    except AssertionError:
        # a request its model should have refused reached the lookup: our bug, which FastAPI answers
        # as a 500, not the caller's to fix
        raise
    except Exception as e:
        log.exception("Failed to get values.")
        raise HTTPException(status_code=400 if _is_caller_refusal(e, request) else 500, detail=str(e)) from e


def _geo_values(
    get: Callable[..., InterpolatedValuesResult | SummarizedValuesResult],
    api: type[TimeseriesRequest],
    request: InterpolationRequest | SummaryRequest,
    settings: Settings,
    what: str,
) -> InterpolatedValuesResult | SummarizedValuesResult:
    """Run an interpolation or a summary, telling the caller which failures are theirs to fix.

    Both endpoints answered every failure with a 404, which reads as "no such thing" for a request
    that was understood and simply cannot be served as phrased -- an elevation no station in reach
    can be placed against, or a window that ends before it starts. Those are 400s, and a reader
    missing on the server is a 501; the same three in both places, so they are decided here rather
    than twice over.
    """
    try:
        return get(api=api, request=request, settings=settings)
    except (NoStationsWithElevationError, ParameterNotCarriedError) as e:
        # the message is the whole of it: which parameters lost their stations, and that asking
        # without an elevation gets them back; or which parameters the run does not carry, and the
        # lead time that does
        log.info(f"Failed to {what}: {e}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except StartDateEndDateError as e:
        log.exception(f"Failed to {what}")
        raise HTTPException(status_code=400, detail=str(e)) from e
    except BufrReaderMissingError as e:
        raise _reader_missing_on_the_server(e, what) from e
    except AssertionError:
        # a request its model should have refused reached the lookup: our bug, which FastAPI answers
        # as a 500, not the caller's to fix
        raise
    except Exception as e:
        log.exception(f"Failed to {what}")
        raise HTTPException(status_code=404 if _is_caller_refusal(e, request) else 500, detail=str(e)) from e


# response models for the different formats are
# - _InterpolatedValuesWithSettingsDict for json
# - _InterpolatedValuesWithSettingsOgcFeatureCollection for geojson
# - str for csv
@app.get(
    "/api/interpolate",
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
    network, parameters and a `date`.
    """
    set_logging_level(debug=request.debug)
    _refuse_sql_unless_enabled(request)

    try:
        api = Wetterdienst(request.provider, request.network)
    except ApiNotFoundError as e:
        msg = f"{e} Use {app.url_path_for('coverage')} to discover available providers and networks."
        log.exception(msg)
        raise HTTPException(status_code=404, detail=msg) from e

    settings = _geo_settings(request, http_request.query_params.keys(), "interpolation")

    values_ = _geo_values(get_interpolate, api, request, settings, "interpolate")

    # build kwargs dynamically
    kwargs: dict[str, Any] = {
        "fmt": request.format,
        "with_metadata": request.with_metadata,
        "with_stations": request.with_stations,
    }
    if request.format in ("json", "geojson"):
        kwargs["indent"] = request.pretty
    if request.format in ("png", "jpg", "webp", "svg", "pdf"):
        kwargs["width"] = request.width
        kwargs["height"] = request.height
        kwargs["scale"] = request.scale

    content = _render(values_, request, kwargs, InterpolationSettings, settings)

    media_type = _MEDIA_TYPES.get(request.format, "application/json")

    return Response(content=content, media_type=media_type)


# response models for the different formats are
# - _SummarizedValuesWithSettingsDict for json
# - _SummarizedValuesWithSettingsOgcFeatureCollection for geojson
# - str for csv
@app.get(
    "/api/summarize",
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
    `date`.
    """
    set_logging_level(debug=request.debug)
    _refuse_sql_unless_enabled(request)
    # dumped rather than read: reading a deprecated field warns of itself, a DeprecationWarning nobody sees
    if request.model_dump(include={"use_nearby_station_distance"})["use_nearby_station_distance"] is not None:
        log.warning(f"use_nearby_station_distance is deprecated. {SUMMARY_USE_NEARBY_STATION_DISTANCE_DEPRECATED}")

    try:
        api = Wetterdienst(request.provider, request.network)
    except ApiNotFoundError as e:
        msg = f"{e} Use {app.url_path_for('coverage')} to discover available providers and networks."
        log.exception(msg)
        raise HTTPException(status_code=404, detail=msg) from e

    settings = _geo_settings(request, http_request.query_params.keys(), "summary")

    values_ = _geo_values(get_summarize, api, request, settings, "summarize")

    # build kwargs dynamically
    kwargs: dict[str, Any] = {
        "fmt": request.format,
        "with_metadata": request.with_metadata,
        "with_stations": request.with_stations,
    }
    if request.format in ("json", "geojson"):
        kwargs["indent"] = request.pretty
    if request.format in ("png", "jpg", "webp", "svg", "pdf"):
        kwargs["width"] = request.width
        kwargs["height"] = request.height
        kwargs["scale"] = request.scale

    content = _render(values_, request, kwargs, SummarySettings, settings)

    media_type = _MEDIA_TYPES.get(request.format, "application/json")

    return Response(content=content, media_type=media_type)


@app.get("/api/stripes/stations")
def stripes_stations(
    kind: Annotated[Literal["temperature", "precipitation"], Query()],
    active: Annotated[bool, Query()] = True,  # noqa: FBT002
    fmt: Annotated[Literal["json", "geojson", "csv"], Query(alias="format")] = "json",
    pretty: Annotated[bool, Query()] = False,  # noqa: FBT002
    debug: Annotated[bool, Query()] = False,  # noqa: FBT002
) -> Response:
    """Wrap get_climate_stripes_temperature_request to provide results via restapi."""
    set_logging_level(debug=debug)

    # the provider request below builds its settings from the environment inside the handler: checked
    # here first, a malformed server setting is the bare 500 FastAPI answers, which does not read its
    # value back
    Settings()
    try:
        stations = _get_stripes_stations(kind=kind, active=active)
    except Exception as e:
        # nothing of the caller's reaches the lookup but a kind and a flag its signature has checked,
        # so a failure here is the server's or the data source's, whatever its type
        log.exception("Failed to get stripes stations")
        raise HTTPException(status_code=500, detail=str(e)) from e
    content = stations.to_format(fmt=fmt, with_metadata=True, indent=pretty)
    media_type = "text/csv" if fmt == "csv" else "application/json"
    return Response(content=content, media_type=media_type)


@app.get("/api/stripes/values")
def stripes_values(
    request: Annotated[StripesValuesRequest, Query()],
) -> Response:
    """Get climate stripes data values with timestamps and metadata."""
    set_logging_level(debug=request.debug)

    # checked outside the handler below, as for `/api/stripes/stations`
    Settings()
    try:
        stripes_data = _get_stripes_data(request)
    except AssertionError:
        # a request its model should have refused: our bug, which FastAPI answers as a 500
        raise
    except Exception as e:
        log.exception("Failed to get stripes data")
        raise HTTPException(status_code=400 if _is_caller_refusal(e, request) else 500, detail=str(e)) from e

    if request.format == "csv":
        content = stripes_data.df.write_csv()
        media_type = "text/csv"
    else:
        data = {
            "metadata": stripes_data.metadata.model_dump(),
            "values": [
                {
                    "timestamp": row["timestamp"].isoformat() if row["timestamp"] else None,
                    "value": row["value"],
                }
                for row in stripes_data.df.select("timestamp", "value").iter_rows(named=True)
            ],
        }
        content = json.dumps(data, indent=4 if request.pretty else None)
        media_type = "application/json"

    return Response(content=content, media_type=media_type)


@app.get("/api/stripes/image")
def stripes_image(
    request: Annotated[StripesImageRequest, Query()],
) -> Response:
    """Generate climate stripes image for a station."""
    set_logging_level(debug=request.debug)

    # checked outside the handler below, as for `/api/stripes/stations`
    Settings()
    try:
        fig = _plot_stripes(request)
    except AssertionError:
        # a request its model should have refused: our bug, which FastAPI answers as a 500
        raise
    except Exception as e:
        log.exception("Failed to plot stripes")
        raise HTTPException(status_code=400 if _is_caller_refusal(e, request) else 500, detail=str(e)) from e
    return Response(
        content=fig.to_image(request.format, scale=request.dpi / 100),
        media_type=_MEDIA_TYPES.get(request.format, "application/octet-stream"),
    )


@app.get("/api/history")
def history(
    request: Annotated[HistoryRequest, Query()],
) -> Response:
    """Return a station's metadata history -- how the station itself changed over time (not weather).

    Provides the record of a station's name, position, sensors/devices and data-gap sections across
    its lifetime, for auditing station changes. This is NOT weather or measurement history: for past
    measurements use the stations -> values workflow with a `date` or interval. Requires provider,
    network, parameters and either `station` id(s) or all=true.
    """
    set_logging_level(debug=request.debug)

    try:
        api = Wetterdienst(request.provider, request.network)
    except ApiNotFoundError as e:
        msg = f"{e} Use {app.url_path_for('coverage')} to discover available providers and networks."
        log.exception(msg)
        raise HTTPException(status_code=404, detail=msg) from e

    # outside the handler below, as for `/api/stations`
    settings = Settings()
    try:
        stations_ = get_stations(
            api=api,
            request=request,
            date=None,
            settings=settings,
        )
    except AssertionError:
        # a request its model should have refused reached the lookup: our bug, which FastAPI answers
        # as a 500, not the caller's to fix
        raise
    except Exception as e:
        log.exception("Failed to get stations for history.")
        raise HTTPException(status_code=400 if _is_caller_refusal(e, request) else 500, detail=str(e)) from e

    try:
        history_provider = stations_.history
    except NotImplementedError as e:
        log.exception("History not implemented for provider/network")
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        # past the station lookup the request has nothing left to refuse: what fails from here on
        # is the server's or the data source's, whatever its type
        log.exception("Failed to acquire history provider")
        raise HTTPException(status_code=500, detail=str(e)) from e

    data: dict[str, Any] = {}
    if request.with_metadata:
        data["metadata"] = stations_.get_metadata()
    if request.with_stations:
        data["stations"] = stations_.to_dict(with_metadata=False)["stations"]
    data["histories"] = []
    try:
        for history_result in history_provider.query():
            history = history_result.history.model_dump()
            data["histories"].append(select_history_sections(history, request.sections))
    except Exception as e:
        log.exception("Failed to collect station history")
        raise HTTPException(status_code=500, detail=str(e)) from e
    return Response(
        content=json.dumps(
            data,
            indent=4 if request.pretty else None,
            default=lambda o: o.isoformat() if hasattr(o, "isoformat") else str(o),
        ),
        media_type="application/json",
    )


@app.get("/api/alerts")
def alerts(
    granularity: Annotated[Literal["community", "district"], Query()] = "community",
    language: Annotated[Literal["de", "en", "es", "fr", "mul"], Query()] = "en",
    date: Annotated[str | None, Query()] = None,
    fmt: Annotated[Literal["json", "geojson", "csv"], Query(alias="format")] = "json",
    pretty: Annotated[bool, Query()] = False,  # noqa: FBT002
    debug: Annotated[bool, Query()] = False,  # noqa: FBT002
) -> Response:
    """Provide DWD weather alerts (CAP warnings) via restapi.

    Returns all warnings active at the selected time, one entry per alert, with a GeoJSON
    MultiPolygon geometry. ``date`` (ISO 8601, UTC if no offset) selects a historical snapshot from
    DWD's rolling ~48-hour window; omit it for the latest snapshot. An empty result simply means
    there were no active warnings.
    """
    from wetterdienst.provider.dwd.alerts import DwdWeatherAlertRequest  # noqa: PLC0415

    set_logging_level(debug=debug)

    # outside the handlers below, as for `/api/stations`: a `ValidationError` is a `ValueError`
    settings = Settings()
    try:
        request = DwdWeatherAlertRequest(granularity=granularity, language=language, date=date, settings=settings)
    except (ValueError, OverflowError) as e:
        # a date that does not parse, or one an offset carries out of what a datetime holds
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        result = request.query()
    except InvalidTimeIntervalError as e:
        # a date before DWD's rolling window, the one refusal of the request's own `query` raises
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        # a feed that does not list, download or read, and an alert in it the parser does not
        # expect: the date was converted already, so not even an `OverflowError` is the caller's
        log.exception("Failed to get weather alerts")
        raise HTTPException(status_code=500, detail=str(e)) from e

    content = result.to_format(fmt, indent=pretty)
    media_type = "text/csv" if fmt == "csv" else "application/json"
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


mcp_enabled = _mount_mcp(app)


def start_service(listen_address: str | None = None, *, reload: bool | None = False) -> None:
    """Start the REST API service."""
    from uvicorn.main import run  # noqa: PLC0415

    setup_logging()

    if listen_address is None:
        listen_address = "127.0.0.1:7890"

    host, port = listen_address.split(":")
    port = int(port)

    run(app="wetterdienst.ui.restapi:app", host=host, port=port, reload=reload or False)
