# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import json
import logging
from typing import Annotated, Any, Literal, Optional, Union

from click_params import StringListParamType
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from wetterdienst import Provider, Wetterdienst, __appname__, __version__
from wetterdienst.core.timeseries.request import TimeseriesRequest
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
    get_interpolate,
    get_stations,
    get_summarize,
    get_values,
    set_logging_level,
)
from wetterdienst.util.cli import read_list, setup_logging

app = FastAPI(debug=False)

log = logging.getLogger(__name__)

PRODUCER_NAME = "Wetterdienst"
PRODUCER_LINK = "https://github.com/earthobservations/wetterdienst"

CommaSeparator = StringListParamType(",")


@app.get("/", response_class=HTMLResponse)
def index():
    appname = f"{__appname__} {__version__}"
    about = "Wetterdienst - Open weather data for humans."
    sources = []
    for provider in Provider:
        shortname = provider.name
        _, name, country, copyright_, url = provider.value
        sources.append(
            f"<li><a href={url} target='_blank' rel='noopener'>{shortname}</a> ({name}, {country}) - {copyright_}</li>"
        )
    sources = "\n".join(sources)
    return f"""
    <html>
        <head>
            <title>{appname}</title>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    margin: 0;
                    padding: 0;
                    background-color: #f0f0f0;
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
                <h1>{about}</h1>
                <h2>Producer</h2>
                <div class="box">
                    {PRODUCER_NAME} - <a href="{PRODUCER_LINK}" target="_blank" rel="noopener">{PRODUCER_LINK}</a></li>
                </div>
                <h2>Providers</h2>
                <div class="list">
                    {sources}
                </div>
                <h2>Endpoints</h2>
                <div class="list">
                    <li><a href="api/coverage" target="_blank" rel="noopener">coverage</a></li>
                    <li><a href="api/stations" target="_blank" rel="noopener">stations</a></li>
                    <li><a href="api/values" target="_blank" rel="noopener">values</a></li>
                    <li><a href="api/interpolate" target="_blank" rel="noopener">interpolation</a></li>
                    <li><a href="api/summarize" target="_blank" rel="noopener">summary</a></li>
                </div>
                <h2>Examples</h2>
                <div class="list">
                    <li><a href="api/stations?provider=dwd&network=observation&parameter=kl&resolution=daily&period=recent&all=true" target="_blank" rel="noopener">DWD Observation Stations</a></li>
                    <li><a href="api/values?provider=dwd&network=observation&parameter=kl&resolution=daily&period=recent&station=00011" target="_blank" rel="noopener">DWD Observation Values</a></li>
                    <li><a href="api/interpolate?provider=dwd&network=observation&parameter=kl&resolution=daily&station=00071&date=1986-10-31/1986-11-01" target="_blank" rel="noopener">DWD Observation Interpolation</a></li>
                    <li><a href="api/summarize?provider=dwd&network=observation&parameter=kl&resolution=daily&station=00071&date=1986-10-31/1986-11-01" target="_blank" rel="noopener">DWD Observation Summary</a></li>
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
    lead_time: Annotated[Optional[Literal["short", "long"]], Query()] = None,
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
    "/api/interpolate", response_model=Union[_InterpolatedValuesDict, _InterpolatedValuesOgcFeatureCollection, str]
)
def interpolate(
    provider: Annotated[Optional[str], Query()] = None,
    network: Annotated[Optional[str], Query()] = None,
    parameter: Annotated[Optional[str], Query()] = None,
    resolution: Annotated[Optional[str], Query()] = None,
    period: Annotated[Optional[str], Query()] = None,
    lead_time: Annotated[Optional[Literal["short", "long"]], Query()] = None,
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
    lead_time: Annotated[Optional[Literal["short", "long"]], Query()] = None,
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


def start_service(listen_address: Optional[str] = None, reload: Optional[bool] = False):  # pragma: no cover
    from uvicorn.main import run

    setup_logging()

    if listen_address is None:
        listen_address = "127.0.0.1:7890"

    host, port = listen_address.split(":")
    port = int(port)

    run(app="wetterdienst.ui.restapi:app", host=host, port=port, reload=reload)
