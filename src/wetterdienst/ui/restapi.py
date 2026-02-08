# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Utilities for the wetterdienst package."""

from __future__ import annotations

import json
import logging
from textwrap import dedent
from typing import Annotated, Literal

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response

from wetterdienst import Author, Info, Settings, Wetterdienst, __version__
from wetterdienst.exceptions import ApiNotFoundError, StartDateEndDateError
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
    HistoryRequest,
    InterpolationRequest,
    StationsRequest,
    SummaryRequest,
    ValuesRequest,
    _get_stripes_data,
    _get_stripes_stations,
    _plot_stripes,
    get_interpolate,
    get_stations,
    get_summarize,
    get_values,
    set_logging_level,
)
from wetterdienst.util.cli import setup_logging
from wetterdienst.util.ui import read_list

info = Info()

app = FastAPI(debug=False)

log = logging.getLogger(__name__)


REQUEST_EXAMPLES = {
    "dwd_observation_daily_climate_stations": "api/stations?provider=dwd&network=observation&parameters=daily/kl&periods=recent&all=true",  # noqa:E501
    "dwd_observation_daily_climate_values": "api/values?provider=dwd&network=observation&parameters=daily/kl&periods=recent&station=00011",  # noqa:E501
    "dwd_observation_daily_climate_interpolation": "api/interpolate?provider=dwd&network=observation&parameters=daily/kl/temperature_air_mean_2m&station=00071&date=1986-10-31/1986-11-01",  # noqa:E501
    "dwd_observation_daily_climate_summary": "api/summarize?provider=dwd&network=observation&parameters=daily/kl/temperature_air_mean_2m&station=00071&date=1986-10-31/1986-11-01",  # noqa:E501
    "dwd_observation_daily_climate_stripes_stations": "api/stripes/stations?kind=temperature",
    "dwd_observation_daily_climate_stripes_values": "api/stripes/values?kind=temperature&station=1048",
    "dwd_observation_daily_climate_stripes_image": "api/stripes/image?kind=temperature&station=1048",
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
                    <li><a href="api/stations" target="_blank" rel="noopener">stations</a></li>
                    <li><a href="api/values" target="_blank" rel="noopener">values</a></li>
                    <li><a href="api/interpolate" target="_blank" rel="noopener">interpolation</a></li>
                    <li><a href="api/summarize" target="_blank" rel="noopener">summary</a></li>
                    <li><a href="api/stripes/stations" target="_blank" rel="noopener">stripes stations</a></li>
                    <li><a href="api/stripes/values" target="_blank" rel="noopener">stripes values</a></li>
                    <li><a href="api/stripes/image" target="_blank" rel="noopener">stripes image</a></li>
                </ul>
                <h2>Examples</h2>
                <ul>
                    <li><a href="{REQUEST_EXAMPLES["dwd_observation_daily_climate_stations"]}" target="_blank" rel="noopener">DWD Observation Daily Climate Stations</a></li>
                    <li><a href="{REQUEST_EXAMPLES["dwd_observation_daily_climate_values"]}" target="_blank" rel="noopener">DWD Observation Daily Climate Values</a></li>
                    <li><a href="{REQUEST_EXAMPLES["dwd_observation_daily_climate_interpolation"]}" target="_blank" rel="noopener">DWD Observation Daily Climate Interpolation</a></li>
                    <li><a href="{REQUEST_EXAMPLES["dwd_observation_daily_climate_summary"]}" target="_blank" rel="noopener">DWD Observation Daily Climate Summary</a></li>
                    <li><a href="{REQUEST_EXAMPLES["dwd_observation_daily_climate_stripes_stations"]}" target="_blank" rel="noopener">DWD Observation Daily Climate Stripes Stations</a></li>
                    <li><a href="{REQUEST_EXAMPLES["dwd_observation_daily_climate_stripes_values"]}" target="_blank" rel="noopener">DWD Observation Daily Climate Stripes Values</a></li>
                    <li><a href="{REQUEST_EXAMPLES["dwd_observation_daily_climate_stripes_image"]}" target="_blank" rel="noopener">DWD Observation Daily Climate Stripes Image</a></li>
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
    """Wrap around Wetterdienst.discover to provide results via restapi."""
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
        api = Wetterdienst(provider, network)
    except KeyError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Choose provider and network from {app.url_path_for('coverage')}",
        ) from e

    if resolutions:
        resolutions = read_list(resolutions)

    if datasets:
        datasets = read_list(datasets)

    cov = api.discover(
        resolutions=resolutions,
        datasets=datasets,
    )

    return Response(content=json.dumps(cov, indent=4 if pretty else None), media_type="application/json")


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
    """Wrap get_stations to provide results via restapi."""
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

    # build kwargs dynamically
    kwargs = {
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
    """Wrap get_values to provide results via restapi."""
    set_logging_level(debug=request.debug)

    try:
        api = Wetterdienst(request.provider, request.network)
    except ApiNotFoundError as e:
        msg = f"{e} Use {app.url_path_for('coverage')} to discover available providers and networks."
        log.exception(msg)
        raise HTTPException(status_code=404, detail=msg) from e

    settings = Settings(
        ts_convert_units=request.convert_units,
        ts_unit_targets=request.unit_targets,
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
    kwargs = {
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
    """Wrap around get_interpolate to provide results via restapi."""
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
        ts_unit_targets=request.unit_targets,
        ts_geo_station_distance=request.interpolation_station_distance,
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
    kwargs = {
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
    """Wrap around get_summarize to provide results via restapi."""
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
        ts_unit_targets=request.unit_targets,
        ts_geo_station_distance=request.summary_station_distance,
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
    kwargs = {
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
    """Wrap get_history to provide station history via restapi.

    Support querying multiple stations or using 'all' to collect histories for
    multiple stations.
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

    data = {}
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


def start_service(listen_address: str | None = None, *, reload: bool | None = False) -> None:
    """Start the REST API service."""
    from uvicorn.main import run  # noqa: PLC0415

    setup_logging()

    if listen_address is None:
        listen_address = "127.0.0.1:7890"

    host, port = listen_address.split(":")
    port = int(port)

    run(app="wetterdienst.ui.restapi:app", host=host, port=port, reload=reload)
