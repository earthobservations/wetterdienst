# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Utilities for the wetterdienst package."""

from __future__ import annotations

import json
import logging
from textwrap import dedent
from typing import Annotated, Any, Literal, cast

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response

from wetterdienst import Author, Info, Settings, Wetterdienst, __version__
from wetterdienst.exceptions import ApiNotFoundError, StartDateEndDateError

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
from wetterdienst.ui.core import (
    GlossaryEntry,
    HistoryRequest,
    InterpolationRequest,
    IssuesRequest,
    StationsRequest,
    SummaryRequest,
    ValuesRequest,
    _get_stripes_data,
    _get_stripes_stations,
    _plot_stripes,
    get_glossary,
    get_interpolate,
    get_issues,
    get_stations,
    get_summarize,
    get_values,
    limit_stations_to_rank,
    set_logging_level,
)
from wetterdienst.util.cli import setup_logging
from wetterdienst.util.ui import read_list

info = Info()

app = FastAPI(debug=False)

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
    "dwd_weather_alerts": "api/alerts?granularity=community&format=geojson",
}


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
    """Get version information."""
    return JSONResponse(content={"version": __version__})


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
    cap the number of entries: the vocabulary is 504 parameters, so an unfiltered call is a large
    response and a broad filter can still be a wide one (parameter="temperature" matches 184).

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
    parameters="daily/kl"). Filter by `name` for a place (e.g. name="Hamburg Fuhlsbüttel"), by
    `station` id(s), by lat/lon with `rank` or `distance`, by bounding box, or pass all=true for the
    full list. Returns station metadata including `station_id`, which you pass to `values`.
    """
    set_logging_level(debug=request.debug)

    try:
        api = Wetterdienst(request.provider, request.network)
    except ApiNotFoundError as e:
        msg = f"{e} Use {app.url_path_for('coverage')} to discover available providers and networks."
        log.exception(msg)
        raise HTTPException(status_code=404, detail=msg) from e

    try:
        stations_ = get_stations(
            api=api,
            request=request,
            date=None,
            settings=Settings(),
        )
    except StartDateEndDateError as e:
        log.exception("Failed to get stations.")
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e
    except Exception as e:
        log.exception("Failed to get stations.")
        raise HTTPException(status_code=400, detail=str(e)) from e

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

    if request.format == "csv":
        media_type = "text/csv"
    elif request.format == "html":
        media_type = "text/html"
    elif request.format in ("png", "jpg", "webp", "svg"):
        media_type = f"image/{request.format}"
    elif request.format == "pdf":
        media_type = "application/pdf"
    else:
        media_type = "application/json"

    return Response(content=content, media_type=media_type)


@app.get("/api/issues")
def issues(
    request: Annotated[IssuesRequest, Query()],
) -> JSONResponse:
    """Return available issue datetimes for a provider/network/station combination.

    Currently supported: provider=dwd, network=mosmix|dmo.
    """
    set_logging_level(debug=request.debug)

    try:
        api = Wetterdienst(request.provider, request.network)
    except ApiNotFoundError as e:
        msg = f"{e} Use {app.url_path_for('coverage')} to discover available providers and networks."
        log.exception(msg)
        raise HTTPException(status_code=404, detail=msg) from e

    try:
        issue_list = get_issues(api=api, request=request, settings=Settings())
    except NotImplementedError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.exception("Failed to get issues.")
        raise HTTPException(status_code=400, detail=str(e)) from e

    return JSONResponse(content={"issues": issue_list})


# response models for the different formats are
# - _ValuesDict for json
# - _ValuesOgcFeatureCollection for geojson
# - str for csv
@app.get(
    "/api/values",
    response_model=_ValuesDict | _ValuesOgcFeatureCollection | str,
)
def values(
    request: Annotated[ValuesRequest, Query()],
) -> Response:
    """Get measured values for station(s) (step 2 of the station -> values workflow).

    Requires provider, network, parameters and a station selection. Use parameters as
    "resolution/dataset/parameter" (e.g. "daily/climate_summary/temperature_air_mean_2m") to keep
    the response small, and `station` with an id from `stations` (e.g. station="01975"). `periods`
    is usually "recent". The response `values` array is sorted by date; the most recent reading for
    a parameter is the last item with that parameter. Do not re-request in other formats.
    """
    set_logging_level(debug=request.debug)

    try:
        api = Wetterdienst(request.provider, request.network)
    except ApiNotFoundError as e:
        msg = f"{e} Use {app.url_path_for('coverage')} to discover available providers and networks."
        log.exception(msg)
        raise HTTPException(status_code=404, detail=msg) from e

    settings = Settings(
        ts_convert_units=request.convert_units,
        ts_unit_targets=request.unit_targets or {},
        ts_shape=request.shape,
        ts_humanize=request.humanize,
        ts_skip_empty=request.skip_empty,
        ts_skip_criteria=request.skip_criteria,
        ts_skip_threshold=request.skip_threshold,
        ts_drop_nulls=request.drop_nulls,
    )

    try:
        values_ = get_values(
            api=api,
            request=request,
            settings=settings,
        )
    except StartDateEndDateError as e:
        log.exception("Failed to get values.")
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e
    except Exception as e:
        log.exception("Failed to get values.")
        raise HTTPException(status_code=400, detail=str(e)) from e

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

    content = values_.to_format(**kwargs)

    if request.format == "csv":
        media_type = "text/csv"
    elif request.format == "html":
        media_type = "text/html"
    elif request.format in ("png", "jpg", "webp", "svg"):
        media_type = f"image/{request.format}"
    elif request.format == "pdf":
        media_type = "application/pdf"
    else:
        media_type = "application/json"

    return Response(content=content, media_type=media_type)


# response models for the different formats are
# - _InterpolatedValuesDict for json
# - _InterpolatedValuesOgcFeatureCollection for geojson
# - str for csv
@app.get(
    "/api/interpolate",
    response_model=_InterpolatedValuesDict | _InterpolatedValuesOgcFeatureCollection | str,
)
def interpolate(
    request: Annotated[InterpolationRequest, Query()],
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

    try:
        api = Wetterdienst(request.provider, request.network)
    except ApiNotFoundError as e:
        msg = f"{e} Use {app.url_path_for('coverage')} to discover available providers and networks."
        log.exception(msg)
        raise HTTPException(status_code=404, detail=msg) from e

    settings = Settings(
        ts_humanize=request.humanize,
        ts_convert_units=request.convert_units,
        ts_unit_targets=request.unit_targets or {},
        ts_geo_station_distance=cast("Any", request.interpolation_station_distance or {}),
        ts_geo_use_nearby_station_distance=request.use_nearby_station_distance,
        ts_geo_min_gain_of_value_pairs=request.min_gain_of_value_pairs,
        ts_geo_num_additional_stations=request.num_additional_stations,
    )

    try:
        values_ = get_interpolate(
            api=api,
            request=request,
            settings=settings,
        )
    except StartDateEndDateError as e:
        log.exception("Failed to interpolate")
        raise HTTPException(
            status_code=400,
            detail=str(e),
        ) from e
    except Exception as e:
        log.exception("Failed to interpolate")
        raise HTTPException(status_code=404, detail=str(e)) from e

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

    content = values_.to_format(**kwargs)

    if request.format == "csv":
        media_type = "text/csv"
    elif request.format == "html":
        media_type = "text/html"
    elif request.format in ("png", "jpg", "webp", "svg"):
        media_type = f"image/{request.format}"
    elif request.format == "pdf":
        media_type = "application/pdf"
    else:
        media_type = "application/json"

    return Response(content=content, media_type=media_type)


# response models for the different formats are
# - _SummarizedValuesDict for json
# - _SummarizedValuesOgcFeatureCollection for geojson
# - str for csv
@app.get("/api/summarize", response_model=_SummarizedValuesDict | _SummarizedValuesOgcFeatureCollection | str)
def summarize(
    request: Annotated[SummaryRequest, Query()],
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

    try:
        api = Wetterdienst(request.provider, request.network)
    except ApiNotFoundError as e:
        msg = f"{e} Use {app.url_path_for('coverage')} to discover available providers and networks."
        log.exception(msg)
        raise HTTPException(status_code=404, detail=msg) from e

    settings = Settings(
        ts_humanize=request.humanize,
        ts_convert_units=request.convert_units,
        ts_unit_targets=request.unit_targets or {},
        ts_geo_station_distance=cast("Any", request.summary_station_distance or {}),
        ts_geo_use_nearby_station_distance=request.use_nearby_station_distance,
        ts_geo_min_gain_of_value_pairs=request.min_gain_of_value_pairs,
        ts_geo_num_additional_stations=request.num_additional_stations,
    )

    try:
        values_ = get_summarize(
            api=api,
            request=request,
            settings=settings,
        )
    except Exception as e:
        log.exception("Failed to summarize")
        raise HTTPException(status_code=404, detail=str(e)) from e

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

    content = values_.to_format(**kwargs)

    if request.format == "csv":
        media_type = "text/csv"
    elif request.format == "html":
        media_type = "text/html"
    elif request.format in ("png", "jpg", "webp", "svg"):
        media_type = f"image/{request.format}"
    elif request.format == "pdf":
        media_type = "application/pdf"
    else:
        media_type = "application/json"

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

    try:
        stations = _get_stripes_stations(kind=kind, active=active)
    except Exception as e:
        log.exception("Failed to get stripes stations")
        raise HTTPException(status_code=400, detail=str(e)) from e
    content = stations.to_format(fmt=fmt, with_metadata=True, indent=pretty)
    media_type = "text/csv" if fmt == "csv" else "application/json"
    return Response(content=content, media_type=media_type)


@app.get("/api/stripes/values")
def stripes_values(
    kind: Annotated[Literal["temperature", "precipitation"], Query()],
    station: Annotated[str | None, Query()] = None,
    name: Annotated[str | None, Query()] = None,
    start_year: Annotated[int | None, Query()] = None,
    end_year: Annotated[int | None, Query()] = None,
    name_threshold: Annotated[float, Query()] = 0.9,
    fmt: Annotated[Literal["json", "csv"], Query(alias="format")] = "json",
    pretty: Annotated[bool, Query()] = False,  # noqa: FBT002
    debug: Annotated[bool, Query()] = False,  # noqa: FBT002
) -> Response:
    """Get climate stripes data values with timestamps and metadata."""
    set_logging_level(debug=debug)

    if not station and not name:
        raise HTTPException(
            status_code=400,
            detail="Query argument 'station' or 'name' is required",
        )
    if station and name:
        raise HTTPException(
            status_code=400,
            detail="Query arguments 'station' and 'name' are mutually exclusive",
        )
    if start_year and end_year and start_year >= end_year:
        raise HTTPException(
            status_code=400,
            detail="Query argument 'start_year' must be less than 'end_year'",
        )
    if name_threshold < 0 or name_threshold > 1:
        raise HTTPException(
            status_code=400,
            detail="Query argument 'name_threshold' must be between 0.0 and 1.0",
        )

    try:
        stripes_data = _get_stripes_data(
            kind=kind,
            station_id=station,
            name=name,
            start_year=start_year,
            end_year=end_year,
            name_threshold=name_threshold,
        )
    except Exception as e:
        log.exception("Failed to get stripes data")
        raise HTTPException(status_code=400, detail=str(e)) from e

    if fmt == "csv":
        content = stripes_data.df.write_csv()
        media_type = "text/csv"
    else:
        data = {
            "metadata": stripes_data.metadata.model_dump(),
            "values": [
                {
                    "date": row["date"].isoformat() if row["date"] else None,
                    "value": row["value"],
                }
                for row in stripes_data.df.select("date", "value").iter_rows(named=True)
            ],
        }
        content = json.dumps(data, indent=4 if pretty else None)
        media_type = "application/json"

    return Response(content=content, media_type=media_type)


@app.get("/api/stripes/image")
def stripes_image(
    kind: Annotated[Literal["temperature", "precipitation"], Query()],
    station: Annotated[str | None, Query()] = None,
    name: Annotated[str | None, Query()] = None,
    start_year: Annotated[int | None, Query()] = None,
    end_year: Annotated[int | None, Query()] = None,
    name_threshold: Annotated[float, Query()] = 0.9,
    show_title: Annotated[bool, Query()] = True,  # noqa: FBT002
    show_years: Annotated[bool, Query()] = True,  # noqa: FBT002
    show_data_availability: Annotated[bool, Query()] = True,  # noqa: FBT002
    fmt: Annotated[Literal["png", "jpg", "svg", "pdf"], Query(alias="format")] = "png",
    dpi: Annotated[int, Query(gt=0)] = 300,
    debug: Annotated[bool, Query()] = False,  # noqa: FBT002
) -> Response:
    """Generate climate stripes image for a station."""
    set_logging_level(debug=debug)

    if not station and not name:
        raise HTTPException(
            status_code=400,
            detail="Query argument 'station' or 'name' is required",
        )
    if station and name:
        raise HTTPException(
            status_code=400,
            detail="Query arguments 'station' and 'name' are mutually exclusive",
        )
    if start_year and end_year and start_year >= end_year:
        raise HTTPException(
            status_code=400,
            detail="Query argument 'start_year' must be less than 'end_year'",
        )
    if name_threshold < 0 or name_threshold > 1:
        raise HTTPException(
            status_code=400,
            detail="Query argument 'name_threshold' must be between 0.0 and 1.0",
        )

    try:
        fig = _plot_stripes(
            kind=kind,
            station_id=station,
            name=name,
            start_year=start_year,
            end_year=end_year,
            name_threshold=name_threshold,
            show_title=show_title,
            show_years=show_years,
            show_data_availability=show_data_availability,
        )
    except Exception as e:
        log.exception("Failed to plot stripes")
        raise HTTPException(status_code=400, detail=str(e)) from e
    media_type = f"image/{fmt}"
    return Response(content=fig.to_image(fmt, scale=dpi / 100), media_type=media_type)


@app.get("/api/history")
def history(  # noqa: C901
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

    if not request.station and not request.all:
        raise HTTPException(
            status_code=400,
            detail="Either 'station' or 'all' parameter must be provided to query history.",
        )

    try:
        stations_ = get_stations(
            api=api,
            request=request,
            date=None,
            settings=Settings(),
        )
    except Exception as e:
        log.exception("Failed to get stations for history.")
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        history_provider = stations_.history
    except NotImplementedError as e:
        log.exception("History not implemented for provider/network")
        raise HTTPException(status_code=404, detail=str(e)) from e
    except Exception as e:
        log.exception("Failed to acquire history provider")
        raise HTTPException(status_code=400, detail=str(e)) from e

    data: dict[str, Any] = {}
    if request.with_metadata:
        data["metadata"] = stations_.get_metadata()
    if request.with_stations:
        data["stations"] = stations_.to_dict(with_metadata=False)["stations"]
    data["histories"] = []
    try:
        for history_result in history_provider.query():
            history = history_result.history.model_dump()
            if request.sections:
                history = {section: history.get(section) for section in request.sections if section in history}
            data["histories"].append(history)
    except Exception as e:
        log.exception("Failed to collect station history")
        raise HTTPException(status_code=400, detail=str(e)) from e
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

    try:
        request = DwdWeatherAlertRequest(granularity=granularity, language=language, date=date, settings=Settings())
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    try:
        result = request.query()
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except Exception as e:
        log.exception("Failed to get weather alerts")
        raise HTTPException(status_code=400, detail=str(e)) from e

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
    except ModuleNotFoundError:
        # optional [mcp] extra (fastmcp) not installed -> plain REST API, no /mcp route
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
