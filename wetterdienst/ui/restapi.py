# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING, Annotated, Any, Literal, Optional, Union

from click_params import StringListParamType
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from wetterdienst import Author, Info, Provider, Wetterdienst
from wetterdienst.core.timeseries.result import (
    _InterpolatedValuesDict,
    _InterpolatedValuesOgcFeatureCollection,
    _StationsDict,
    _StationsOgcFeatureCollection,
    _SummarizedValuesDict,
    _SummarizedValuesOgcFeatureCollection,
    _ValuesDict,
    _ValuesOgcFeatureCollection,
)
from wetterdienst.exceptions import ProviderNotFoundError
from wetterdienst.ui.cli import get_api
from wetterdienst.ui.core import (
    _get_stripes_stations,
    _thread_safe_plot_stripes,
    get_interpolate,
    get_stations,
    get_summarize,
    get_values,
    set_logging_level,
)
from wetterdienst.util.cli import read_list, setup_logging

if TYPE_CHECKING:
    from wetterdienst.core.timeseries.request import TimeseriesRequest

info = Info()

app = FastAPI(debug=False)

log = logging.getLogger(__name__)

CommaSeparator = StringListParamType(",")


@app.get("/", response_class=HTMLResponse)
def index():
    def _create_author_entry(author: Author):
        # create author string Max Mustermann (Github href, Mailto)
        return f"{author.name} (<a href='https://github.com/{author.github_handle}' target='_blank' rel='noopener'>github</a>, <a href='mailto:{author.email}'>mail</a>)"  # noqa:E501

    title = f"{info.name} restapi"
    sources = []
    for provider in Provider:
        shortname = provider.name
        _, name, country, copyright_, url = provider.value
        sources.append(
            f"<li><a href={url} target='_blank' rel='noopener'>{shortname}</a> ({name}, {country}) - {copyright_}</li>",
        )
    sources = "\n".join(sources)
    return f"""
    <html lang="en">
        <head>
            <title>{title}</title>
            <meta name="description" content="{info.slogan}">
            <meta name="keywords" content="weather, climate, data, api, open, source, wetterdienst">
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 0;
                }}

                header {{
                    background-color: #0074d9;
                    text-align: center;
                    padding: 20px;
                }}

                h1, h2 {{
                    color: #333;
                }}

                h2 {{
                    border-top: 1px solid #ccc;
                    padding-top: 20px;
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

                .container {{
                    max-width: 800px;
                    margin: 0 auto;
                    padding: 20px;
                    border-radius: 5px;
                    box-shadow: 0 0 10px rgba(0, 0, 0, 0.1);
                }}

                .box {{
                    margin-left: 20px;
                }}

                .list {{
                    display: flex;
                    flex-wrap: wrap;
                    list-style: none;
                    flex-direction: column;
                }}

                .list li {{
                    margin-left: 20px;
                    text-align: left;
                }}

            </style>
        </head>
        <body>
            <div class="container">
                <h1>{info.slogan}</h1>
                <h2>Endpoints</h2>
                <div class="list">
                    <li><a href="api/coverage" target="_blank" rel="noopener">coverage</a></li>
                    <li><a href="api/stations" target="_blank" rel="noopener">stations</a></li>
                    <li><a href="api/values" target="_blank" rel="noopener">values</a></li>
                    <li><a href="api/interpolate" target="_blank" rel="noopener">interpolation</a></li>
                    <li><a href="api/summarize" target="_blank" rel="noopener">summary</a></li>
                    <li><a href="api/stripes/stations" target="_blank" rel="noopener">stripes stations</a></li>
                    <li><a href="api/stripes/values" target="_blank" rel="noopener">stripes values</a></li>
                </div>
                <h2>Examples</h2>
                <div class="list">
                    <li><a href="api/stations?provider=dwd&network=observation&parameter=kl&resolution=daily&period=recent&all=true" target="_blank" rel="noopener">DWD Obs Daily Climate Stations</a></li>
                    <li><a href="api/values?provider=dwd&network=observation&parameter=kl&resolution=daily&period=recent&station=00011" target="_blank" rel="noopener">DWD Obs Daily Climate Values</a></li>
                    <li><a href="api/interpolate?provider=dwd&network=observation&parameter=temperature_air_mean_2m&resolution=daily&station=00071&date=1986-10-31/1986-11-01" target="_blank" rel="noopener">DWD Obs Daily Climate Interpolation</a></li>
                    <li><a href="api/summarize?provider=dwd&network=observation&parameter=temperature_air_mean_2m&resolution=daily&station=00071&date=1986-10-31/1986-11-01" target="_blank" rel="noopener">DWD Obs Daily Climate Summary</a></li>
                    <li><a href="api/stripes/stations?kind=temperature" target="_blank" rel="noopener">DWD Obs Daily Climate Stripes Stations</a></li>
                    <li><a href="api/stripes/values?kind=temperature&station=1048" target="_blank" rel="noopener">DWD Obs Daily Climate Stripes Values</a></li>
                </div>
                <h2>Producer</h2>
                <div class="List">
                    <li>Version: {info.version}</li>
                    <li>Authors: {', '.join(_create_author_entry(author) for author in info.authors)}</li>
                    <li>Repository: <a href="{info.repository}" target="_blank" rel="noopener">{info.repository}</a></li>
                    <li>Documentation: <a href="{info.documentation}" target="_blank" rel="noopener">{info.documentation}</a></li>
                </div>
                <h2>Providers</h2>
                <div class="list">
                    {sources}
                </div>
            </div>
        </body>
    </html>
    """  # noqa:B950,E501


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return """
User-agent: *
Disallow: /api/
    """.strip()


@app.get("/health")
def health():
    return {"status": "OK"}


@app.get("/api/coverage")
def coverage(
    provider: Annotated[Optional[str], Query()] = None,
    network: Annotated[Optional[str], Query()] = None,
    debug: Annotated[bool, Query()] = False,
    dataset: Annotated[Optional[str], Query()] = None,
    resolution: Annotated[Optional[str], Query()] = None,
):
    set_logging_level(debug)

    if not provider or not network:
        cov = Wetterdienst.discover()
        return Response(content=json.dumps(cov, indent=4), media_type="application/json")

    api = get_api(provider=provider, network=network)

    cov = api.discover(
        dataset=dataset,
        resolution=resolution,
        flatten=False,
    )

    return Response(content=json.dumps(cov, indent=4), media_type="application/json")


# response models for the different formats are
# - _StationsDict for json
# - _StationsOgcFeatureCollection for geojson
# - str for csv
@app.get("/api/stations", response_model=Union[_StationsDict, _StationsOgcFeatureCollection, str])
def stations(
    provider: Annotated[Optional[str], Query()] = None,
    network: Annotated[Optional[str], Query()] = None,
    parameter: Annotated[Optional[str], Query()] = None,
    resolution: Annotated[Optional[str], Query()] = None,
    period: Annotated[Optional[str], Query()] = None,
    all_: Annotated[Optional[bool], Query(alias="all")] = None,
    station: Annotated[Optional[str], Query()] = None,
    name: Annotated[Optional[str], Query()] = None,
    coordinates: Annotated[Optional[str], Query()] = None,
    rank: Annotated[Optional[int], Query()] = None,
    distance: Annotated[Optional[float], Query()] = None,
    bbox: Annotated[Optional[str], Query()] = None,
    sql: Annotated[Optional[str], Query()] = None,
    fmt: Annotated[str, Query(alias="format")] = "json",
    pretty: Annotated[bool, Query()] = None,
    debug: Annotated[bool, Query()] = None,
) -> Any:
    if provider is None or network is None:
        raise HTTPException(
            status_code=400,
            detail="Query arguments 'provider' and 'network' are required",
        )
    if parameter is None or resolution is None:
        raise HTTPException(
            status_code=400,
            detail="Query arguments 'parameter', 'resolution' and 'period' are required",
        )
    if fmt not in ("json", "geojson", "csv"):
        raise HTTPException(
            status_code=400,
            detail="Query argument 'format' must be one of 'json', 'geojson' or 'csv'",
        )

    set_logging_level(debug)

    try:
        api = Wetterdienst(provider, network)
    except ProviderNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Choose provider and network from {app.url_path_for('coverage')}",
        ) from e

    parameter = read_list(parameter)
    if period:
        period = read_list(period)
    if station:
        station = read_list(station)

    try:
        stations_ = get_stations(
            api=api,
            parameter=parameter,
            resolution=resolution,
            period=period,
            lead_time="short",
            date=None,
            issue=None,
            all_=all_,
            station_id=station,
            name=name,
            coordinates=coordinates,
            rank=rank,
            distance=distance,
            bbox=bbox,
            sql=sql,
            shape="long",
            si_units=False,
            humanize=False,
            skip_empty=False,
            skip_threshold=0.95,
            skip_criteria="min",
            dropna=False,
        )
    except (KeyError, ValueError) as e:
        raise HTTPException(status_code=400, detail=str(e)) from e

    if not stations_.parameter or not stations_.resolution:
        raise HTTPException(
            status_code=400,
            detail=f"No parameter found for provider {provider}, network {network}, "
            f"parameter(s) {parameter} and resolution {resolution}.",
        )

    content = stations_.to_format(fmt=fmt, with_metadata=True, indent=pretty)

    if fmt == "csv":
        media_type = "text/csv"
    else:
        media_type = "application/json"

    return Response(content=content, media_type=media_type)


# response models for the different formats are
# - _ValuesDict for json
# - _ValuesOgcFeatureCollection for geojson
# - str for csv
@app.get("/api/values", response_model=Union[_ValuesDict, _ValuesOgcFeatureCollection, str])
def values(
    provider: Annotated[Optional[str], Query()] = None,
    network: Annotated[Optional[str], Query()] = None,
    parameter: Annotated[Optional[str], Query()] = None,
    resolution: Annotated[Optional[str], Query()] = None,
    period: Annotated[Optional[str], Query()] = None,
    lead_time: Annotated[Literal["short", "long"] | None, Query()] = None,
    date: Annotated[Optional[str], Query()] = None,
    issue: Annotated[Optional[str], Query()] = None,
    all_: Annotated[Optional[bool], Query(alias="all")] = None,
    station: Annotated[Optional[str], Query()] = None,
    name: Annotated[Optional[str], Query()] = None,
    coordinates: Annotated[Optional[str], Query()] = None,
    rank: Annotated[Optional[int], Query()] = None,
    distance: Annotated[Optional[float], Query()] = None,
    bbox: Annotated[Optional[str], Query()] = None,
    sql: Annotated[Optional[str], Query()] = None,
    sql_values: Annotated[Optional[str], Query(alias="sql-values")] = None,
    humanize: Annotated[bool, Query()] = True,
    shape: Annotated[str, Query()] = "long",
    si_units: Annotated[bool, Query(alias="si-units")] = True,
    skip_empty: Annotated[bool, Query(alias="skip-empty")] = False,
    skip_threshold: Annotated[float, Query(alias="skip-threshold", gt=0, le=1)] = 0.95,
    skip_criteria: Annotated[str, Query(alias="skip-criteria")] = "min",
    dropna: Annotated[bool, Query(alias="dropna")] = False,
    fmt: Annotated[str, Query(alias="format")] = "json",
    pretty: Annotated[bool, Query()] = False,
    debug: Annotated[bool, Query()] = False,
) -> Any:
    if provider is None or network is None:
        raise HTTPException(
            status_code=400,
            detail="Query arguments 'provider' and 'network' are required",
        )
    if parameter is None or resolution is None:
        raise HTTPException(
            status_code=400,
            detail="Query arguments 'parameter', 'resolution' and 'date' are required",
        )
    if fmt not in ("json", "geojson", "csv"):
        raise HTTPException(
            status_code=400,
            detail="Query argument 'format' must be one of 'json', 'geojson' or 'csv'",
        )

    set_logging_level(debug)

    try:
        api: TimeseriesRequest = Wetterdienst(provider, network)
    except ProviderNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Given combination of provider and network not available. "
            f"Choose provider and network from {Wetterdienst.discover()}",
        ) from e

    parameter = read_list(parameter)
    if period:
        period = read_list(period)
    if station:
        station = read_list(station)

    try:
        values_ = get_values(
            api=api,
            parameter=parameter,
            resolution=resolution,
            date=date,
            issue=issue,
            period=period,
            lead_time=lead_time,
            all_=all_,
            station_id=station,
            name=name,
            coordinates=coordinates,
            rank=rank,
            distance=distance,
            bbox=bbox,
            sql=sql,
            sql_values=sql_values,
            si_units=si_units,
            skip_empty=skip_empty,
            skip_threshold=skip_threshold,
            skip_criteria=skip_criteria,
            dropna=dropna,
            shape=shape,
            humanize=humanize,
        )
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=400, detail=str(e)) from e

    content = values_.to_format(fmt=fmt, with_metadata=True, indent=pretty)

    if fmt == "csv":
        media_type = "text/csv"
    else:
        media_type = "application/json"

    return Response(content=content, media_type=media_type)


# response models for the different formats are
# - _InterpolatedValuesDict for json
# - _InterpolatedValuesOgcFeatureCollection for geojson
# - str for csv
@app.get(
    "/api/interpolate",
    response_model=Union[_InterpolatedValuesDict, _InterpolatedValuesOgcFeatureCollection, str],
)
def interpolate(
    provider: Annotated[Optional[str], Query()] = None,
    network: Annotated[Optional[str], Query()] = None,
    parameter: Annotated[Optional[str], Query()] = None,
    resolution: Annotated[Optional[str], Query()] = None,
    period: Annotated[Optional[str], Query()] = None,
    lead_time: Annotated[Literal["short", "long"] | None, Query()] = None,
    date: Annotated[Optional[str], Query()] = None,
    issue: Annotated[Optional[str], Query()] = None,
    station: Annotated[Optional[str], Query()] = None,
    coordinates: Annotated[Optional[str], Query()] = None,
    sql_values: Annotated[Optional[str], Query(alias="sql-values")] = None,
    humanize: Annotated[bool, Query()] = True,
    si_units: Annotated[bool, Query(alias="si-units")] = True,
    use_nearby_station_distance: Annotated[float, Query()] = 1.0,
    fmt: Annotated[Literal["json", "geojson", "csv"], Query(alias="format")] = "json",
    pretty: Annotated[bool, Query()] = False,
    debug: Annotated[bool, Query()] = False,
) -> Any:
    """Wrapper around get_interpolate to provide results via restapi"""
    if provider is None or network is None:
        raise HTTPException(
            status_code=400,
            detail="Query arguments 'provider' and 'network' are required",
        )
    if parameter is None or resolution is None:
        raise HTTPException(
            status_code=400,
            detail="Query arguments 'parameter', 'resolution' and 'date' are required",
        )
    if fmt not in ("json", "geojson", "csv"):
        raise HTTPException(
            status_code=400,
            detail="Query argument 'format' must be one of 'json', 'geojson' or 'csv'",
        )

    set_logging_level(debug)

    try:
        api: TimeseriesRequest = Wetterdienst(provider, network)
    except ProviderNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Given combination of provider and network not available. "
            f"Choose provider and network from {Wetterdienst.discover()}",
        ) from e

    parameter = read_list(parameter)
    if period:
        period = read_list(period)
    if station:
        station = read_list(station)

    try:
        values_ = get_interpolate(
            api=api,
            parameter=parameter,
            resolution=resolution,
            period=period,
            lead_time=lead_time,
            date=date,
            issue=issue,
            station_id=station,
            coordinates=coordinates,
            sql_values=sql_values,
            si_units=si_units,
            humanize=humanize,
            use_nearby_station_distance=use_nearby_station_distance,
        )
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=404, detail=str(e)) from e

    content = values_.to_format(fmt=fmt, with_metadata=True, indent=pretty)

    if fmt == "csv":
        media_type = "text/csv"
    else:
        media_type = "application/json"

    return Response(content=content, media_type=media_type)


# response models for the different formats are
# - _SummarizedValuesDict for json
# - _SummarizedValuesOgcFeatureCollection for geojson
# - str for csv
@app.get("/api/summarize", response_model=Union[_SummarizedValuesDict, _SummarizedValuesOgcFeatureCollection, str])
def summarize(
    provider: Annotated[Optional[str], Query()] = None,
    network: Annotated[Optional[str], Query()] = None,
    parameter: Annotated[Optional[str], Query()] = None,
    resolution: Annotated[Optional[str], Query()] = None,
    period: Annotated[Optional[str], Query()] = None,
    lead_time: Annotated[Literal["short", "long"] | None, Query()] = None,
    date: Annotated[Optional[str], Query()] = None,
    issue: Annotated[Optional[str], Query()] = "latest",
    station: Annotated[Optional[str], Query()] = None,
    coordinates: Annotated[Optional[str], Query()] = None,
    sql_values: Annotated[Optional[str], Query(alias="sql-values")] = None,
    humanize: Annotated[bool, Query()] = True,
    si_units: Annotated[bool, Query(alias="si-units")] = True,
    fmt: Annotated[Literal["json", "geojson", "csv"], Query(alias="format")] = "json",
    pretty: Annotated[bool, Query()] = False,
    debug: Annotated[bool, Query()] = False,
) -> Any:
    """Wrapper around get_summarize to provide results via restapi"""
    if provider is None or network is None:
        raise HTTPException(
            status_code=400,
            detail="Query arguments 'provider' and 'network' are required",
        )
    if parameter is None or resolution is None:
        raise HTTPException(
            status_code=400,
            detail="Query arguments 'parameter', 'resolution' " "and 'date' are required",
        )
    if fmt not in ("json", "geojson", "csv"):
        raise HTTPException(
            status_code=400,
            detail="Query argument 'format' must be one of 'json', 'geojson' or 'csv'",
        )

    set_logging_level(debug)

    try:
        api: TimeseriesRequest = Wetterdienst(provider, network)
    except ProviderNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=f"Given combination of provider and network not available. "
            f"Choose provider and network from {Wetterdienst.discover()}",
        ) from e

    parameter = read_list(parameter)
    if period:
        period = read_list(period)
    if station:
        station = read_list(station)

    try:
        values_ = get_summarize(
            api=api,
            parameter=parameter,
            resolution=resolution,
            period=period,
            lead_time=lead_time,
            date=date,
            issue=issue,
            station_id=station,
            coordinates=coordinates,
            sql_values=sql_values,
            si_units=si_units,
            humanize=humanize,
        )
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=404, detail=str(e)) from e

    content = values_.to_format(fmt=fmt, with_metadata=True, indent=pretty)

    if fmt == "csv":
        media_type = "text/csv"
    else:
        media_type = "application/json"

    return Response(content=content, media_type=media_type)


@app.get("/api/stripes/stations")
def stripes_stations(
    kind: Annotated[str, Query()],
    active: Annotated[bool, Query()] = True,
    fmt: Annotated[str, Query(alias="format")] = "json",
    pretty: Annotated[bool, Query()] = False,
    debug: Annotated[bool, Query()] = False,
) -> Any:
    """Wrapper around get_climate_stripes_temperature_request to provide results via restapi"""
    set_logging_level(debug)
    if kind not in ["temperature", "precipitation"]:
        raise HTTPException(
            status_code=400,
            detail="Query argument 'kind' must be one of 'temperature' or 'precipitation'",
        )
    if fmt not in ["json", "geojson", "csv"]:
        raise HTTPException(
            status_code=400,
            detail="Query argument 'format' must be one of 'json', 'geojson' or 'csv'",
        )
    try:
        stations = _get_stripes_stations(kind=kind, active=active)
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=400, detail=str(e)) from e
    content = stations.to_format(fmt=fmt, with_metadata=True, indent=pretty)
    if fmt == "csv":
        media_type = "text/csv"
    else:
        media_type = "application/json"
    return Response(content=content, media_type=media_type)


@app.get("/api/stripes/values")
def stripes_values(
    kind: Annotated[str, Query()],
    station: Annotated[Optional[str], Query()] = None,
    name: Annotated[Optional[str], Query()] = None,
    start_year: Annotated[Optional[int], Query()] = None,
    end_year: Annotated[Optional[int], Query()] = None,
    name_threshold: Annotated[Optional[float], Query()] = 0.9,
    show_title: Annotated[bool, Query()] = True,
    show_years: Annotated[bool, Query()] = True,
    show_data_availability: Annotated[bool, Query()] = True,
    fmt: Annotated[str, Query(alias="format")] = "png",
    dpi: Annotated[int, Query()] = 300,
    debug: Annotated[bool, Query()] = False,
) -> Any:
    """Wrapper around get_summarize to provide results via restapi"""
    set_logging_level(debug)
    if kind not in ["temperature", "precipitation"]:
        raise HTTPException(
            status_code=400,
            detail="Query argument 'kind' must be one of 'temperature' or 'precipitation'",
        )
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
    if start_year and end_year:
        if start_year >= end_year:
            raise HTTPException(
                status_code=400,
                detail="Query argument 'start_year' must be less than 'end_year'",
            )
    if name_threshold < 0 or name_threshold > 1:
        raise HTTPException(
            status_code=400,
            detail="Query argument 'name_threshold' must be between 0.0 and 1.0",
        )
    if fmt not in ["png", "jpg", "svg", "pdf"]:
        raise HTTPException(
            status_code=400,
            detail="Query argument 'format' must be one of 'png', 'jpg', 'svg' or 'pdf'",
        )
    if dpi <= 0:
        raise HTTPException(
            status_code=400,
            detail="Query argument 'dpi' must be more than 0",
        )
    try:
        buf = _thread_safe_plot_stripes(
            kind=kind,
            station_id=station,
            name=name,
            start_year=start_year,
            end_year=end_year,
            name_threshold=name_threshold,
            show_title=show_title,
            show_years=show_years,
            show_data_availability=show_data_availability,
            fmt=fmt,
            dpi=dpi,
        )
    except Exception as e:
        log.exception(e)
        raise HTTPException(status_code=400, detail=str(e)) from e
    media_type = f"image/{fmt}"
    return Response(content=buf.getvalue(), media_type=media_type)


def start_service(listen_address: str | None = None, reload: bool | None = False):  # pragma: no cover
    from uvicorn.main import run

    setup_logging()

    if listen_address is None:
        listen_address = "127.0.0.1:7890"

    host, port = listen_address.split(":")
    port = int(port)

    run(app="wetterdienst.ui.restapi:app", host=host, port=port, reload=reload)
