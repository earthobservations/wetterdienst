# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import json
import logging
from typing import Optional

import numpy as np
import pandas as pd
from click_params import StringListParamType
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse, Response

from wetterdienst import Provider, Wetterdienst, __appname__, __version__
from wetterdienst.core.scalar.request import ScalarRequestCore
from wetterdienst.exceptions import ProviderError
from wetterdienst.metadata.columns import Columns
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

    sources = ""
    for provider in Provider:
        shortname = provider.name
        _, name, country, copyright_, url = provider.value
        sources += f"<li><a href={url}>{shortname}</a> ({name}, {country}) - {copyright_}</li>"

    return f"""
    <html>
        <head>
            <title>{appname}</title>
        </head>
        <body>
            <h3>About</h3>
            <h3>{about}</h3>
            <h4>Providers</h4>
            <ul>
                {sources}
            </ul>
            <h4>Providers</h4>
            <ul>
                <li><a href=restapi/coverage>coverage</a></li>
                <li><a href=restapi/stations>stations</a></li>
                <li><a href=restapi/values>values</a></li>
                <li><a href=restapi/interpolate>interpolation</a></li>
                <li><a href=restapi/summarize>summary</a></li>
            </ul>
            <h4>Producer</h4>
            {PRODUCER_NAME} - <a href="{PRODUCER_LINK}">{PRODUCER_LINK}</a></li>
            <h4>Examples</h4>
            <ul>
            <li><a href="restapi/stations?provider=dwd&network=observation&parameter=kl&resolution=daily&period=recent&all=true">DWD Observation stations</a></li>
            <li><a href="restapi/values?provider=dwd&network=observation&parameter=kl&resolution=daily&period=recent&station=00011">DWD Observation values</a></li>
            <li><a href="restapi/interpolate?provider=dwd&network=observation&parameter=kl&resolution=daily&station=00071&date=1986-10-31/1986-11-01">DWD Observation values</a></li>
            <li><a href="restapi/summarize?provider=dwd&network=observation&parameter=kl&resolution=daily&station=00071&date=1986-10-31/1986-11-01">DWD Observation values</a></li>
            </ul>
        </body>
    </html>
    """  # noqa:B950,E501


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return """
User-agent: *
Disallow: /api/
    """.strip()


@app.get("/restapi/coverage")
def coverage(
    provider: str = Query(default=None),
    network: str = Query(default=None),
    debug: bool = Query(default=False),
    filter_=Query(alias="filter", default=None),
):
    set_logging_level(debug)

    if not provider or not network:
        cov = Wetterdienst.discover()

        return Response(content=json.dumps(cov, indent=4), media_type="application/json")

    api = get_api(provider=provider, network=network)

    cov = api.discover(
        filter_=filter_,
        flatten=False,
    )

    return Response(content=json.dumps(cov, indent=4), media_type="application/json")


@app.get("/restapi/stations")
def stations(
    provider: str = Query(default=None),
    network: str = Query(default=None),
    parameter: str = Query(default=None),
    resolution: str = Query(default=None),
    period: str = Query(default=None),
    all_: str = Query(alias="all", default=False),
    station_id: str = Query(default=None),
    name: str = Query(default=None),
    coordinates: str = Query(default=None),
    rank: int = Query(default=None),
    distance: float = Query(default=None),
    bbox: str = Query(default=None),
    sql: str = Query(default=None),
    fmt: str = Query(alias="format", default="json"),
    debug: bool = Query(default=False),
    pretty: bool = Query(default=False),
):
    if provider is None or network is None:
        raise HTTPException(
            status_code=400,
            detail="Query arguments 'provider' and 'network' are required",
        )

    if parameter is None or resolution is None:
        raise HTTPException(
            status_code=400,
            detail="Query arguments 'parameter', 'resolution' " "and 'period' are required",
        )

    if fmt not in ("json", "geojson"):
        raise HTTPException(
            status_code=400,
            detail="format argument must be one of json, geojson",
        )

    set_logging_level(debug)

    try:
        api = Wetterdienst(provider, network)
    except ProviderError:
        return HTTPException(
            status_code=404,
            detail=f"Choose provider and network from {app.url_path_for('coverage')}",
        )

    parameter = read_list(parameter)
    if period:
        period = read_list(period)
    if station_id:
        station_id = read_list(station_id)

    try:
        stations_ = get_stations(
            api=api,
            parameter=parameter,
            resolution=resolution,
            period=period,
            date=None,
            issue=None,
            all_=all_,
            station_id=station_id,
            name=name,
            coordinates=coordinates,
            rank=rank,
            distance=distance,
            bbox=bbox,
            sql=sql,
            tidy=False,
            si_units=False,
            humanize=False,
            skip_empty=False,
            skip_threshold=0.95,
            dropna=False,
        )
    except (KeyError, ValueError) as e:
        return HTTPException(status_code=404, detail=str(e))

    if not stations_.parameter or not stations_.resolution:
        return HTTPException(
            status_code=404,
            detail=f"No parameter found for provider {provider}, network {network}, "
            f"parameter(s) {parameter} and resolution {resolution}.",
        )

    stations_.df = stations_.df.replace({np.nan: None, pd.NA: None})

    indent = None
    if pretty:
        indent = 4

    if fmt == "json":
        output = stations_.to_dict()
    elif fmt == "geojson":
        output = stations_.to_ogc_feature_collection()

    output = make_json_response(output, api.provider)

    output = json.dumps(output, indent=indent, ensure_ascii=False)

    return Response(content=output, media_type="application/json")


@app.get("/restapi/values")
def values(
    provider: str = Query(default=None),
    network: str = Query(default=None),
    parameter: str = Query(default=None),
    resolution: str = Query(default=None),
    period: str = Query(default=None),
    date: str = Query(default=None),
    issue: str = Query(default="latest"),
    all_: str = Query(alias="all", default=False),
    station: str = Query(default=None),
    name: str = Query(default=None),
    coordinates: str = Query(default=None),
    rank: int = Query(default=None),
    distance: float = Query(default=None),
    bbox: str = Query(default=None),
    sql: str = Query(default=None),
    sql_values: str = Query(alias="sql-values", default=None),
    humanize: bool = Query(default=True),
    tidy: bool = Query(default=True),
    si_units: bool = Query(alias="si-units", default=True),
    skip_empty: bool = Query(alias="skip-empty", default=False),
    skip_threshold: float = Query(alias="skip-threshold", default=0.95, gt=0, le=1),
    dropna: bool = Query(alias="dropna", default=False),
    pretty: bool = Query(default=False),
    debug: bool = Query(default=False),
):
    """
    Acquire data from DWD.

    :param provider:
    :param network:        string for network of provider
    :param parameter:   Observation measure
    :param resolution:  Frequency/granularity of measurement interval
    :param period:      Recent or historical files
    :param date:        Date or date range
    :param issue:
    :param all_:
    :param station:
    :param name:
    :param coordinates:
    :param rank:
    :param distance:
    :param bbox:
    :param sql:         SQL expression
    :param sql_values:
    :param fmt:
    :param humanize:
    :param tidy:        Whether to return data in tidy format. Default: True.
    :param si_units:
    :param skip_empty:
    :param skip_threshold:
    :param dropna:
    :param pretty:
    :param debug:
    :return:
    """
    # TODO: Add geojson support
    fmt = "json"

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

    if fmt not in ("json", "geojson"):
        raise HTTPException(
            status_code=400,
            detail="format argument must be one of json, geojson",
        )

    set_logging_level(debug)

    try:
        api: ScalarRequestCore = Wetterdienst(provider, network)
    except ProviderError:
        return HTTPException(
            status_code=404,
            detail=f"Given combination of provider and network not available. "
            f"Choose provider and network from {Wetterdienst.discover()}",
        )

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
            dropna=dropna,
            tidy=tidy,
            humanize=humanize,
        )
    except Exception as e:
        log.exception(e)

        return HTTPException(status_code=404, detail=str(e))

    indent = None
    if pretty:
        indent = 4

    output = values_.df

    output[Columns.DATE.value] = output[Columns.DATE.value].apply(lambda ts: ts.isoformat())

    output = output.replace({np.NaN: None, pd.NA: None})

    output = output.to_dict(orient="records")

    output = make_json_response(output, api.provider)

    output = json.dumps(output, indent=indent, ensure_ascii=False)

    return Response(content=output, media_type="application/json")


@app.get("/restapi/interpolate")
def interpolate(
    provider: str = Query(default=None),
    network: str = Query(default=None),
    parameter: str = Query(default=None),
    resolution: str = Query(default=None),
    period: str = Query(default=None),
    use_nearby_station_until_km: float = Query(default=1.0),
    date: str = Query(default=None),
    issue: str = Query(default="latest"),
    station: str = Query(default=None),
    coordinates: str = Query(default=None),
    sql_values: str = Query(alias="sql-values", default=None),
    humanize: bool = Query(default=True),
    si_units: bool = Query(alias="si-units", default=True),
    pretty: bool = Query(default=False),
    debug: bool = Query(default=False),
):
    """
    Wrapper around get_interpolate to provide results via restapi

    :param provider:
    :param network:        string for network of provider
    :param parameter:   Observation measure
    :param resolution:  Frequency/granularity of measurement interval
    :param period:      Recent or historical files
    :param date:        Date or date range
    :param issue:
    :param station:
    :param coordinates:
    :param sql_values:
    :param humanize:
    :param si_units:
    :param pretty:
    :param debug:
    :return:
    """
    # TODO: Add geojson support
    fmt = "json"

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

    if fmt not in ("json", "geojson"):
        raise HTTPException(
            status_code=400,
            detail="format argument must be one of json, geojson",
        )

    set_logging_level(debug)

    try:
        api: ScalarRequestCore = Wetterdienst(provider, network)
    except ProviderError:
        return HTTPException(
            status_code=404,
            detail=f"Given combination of provider and network not available. "
            f"Choose provider and network from {Wetterdienst.discover()}",
        )

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
            date=date,
            issue=issue,
            period=period,
            station_id=station,
            coordinates=coordinates,
            sql_values=sql_values,
            si_units=si_units,
            humanize=humanize,
            use_nearby_station_until_km=use_nearby_station_until_km,
        )
    except Exception as e:
        log.exception(e)

        return HTTPException(status_code=404, detail=str(e))

    indent = None
    if pretty:
        indent = 4

    output = values_.df

    output[Columns.DATE.value] = output[Columns.DATE.value].apply(lambda ts: ts.isoformat())

    output = output.replace({np.NaN: None, pd.NA: None})

    output = output.to_dict(orient="records")

    output = make_json_response(output, api.provider)

    output = json.dumps(output, indent=indent, ensure_ascii=False)

    return Response(content=output, media_type="application/json")


@app.get("/restapi/summarize")
def summarize(
    provider: str = Query(default=None),
    network: str = Query(default=None),
    parameter: str = Query(default=None),
    resolution: str = Query(default=None),
    period: str = Query(default=None),
    date: str = Query(default=None),
    issue: str = Query(default="latest"),
    station: str = Query(default=None),
    coordinates: str = Query(default=None),
    sql_values: str = Query(alias="sql-values", default=None),
    humanize: bool = Query(default=True),
    si_units: bool = Query(alias="si-units", default=True),
    pretty: bool = Query(default=False),
    debug: bool = Query(default=False),
):
    """
    Wrapper around get_summarize to provide results via restapi

    :param provider:
    :param network:        string for network of provider
    :param parameter:   Observation measure
    :param resolution:  Frequency/granularity of measurement interval
    :param period:      Recent or historical files
    :param date:        Date or date range
    :param issue:
    :param station:
    :param coordinates:
    :param sql_values:
    :param humanize:
    :param si_units:
    :param pretty:
    :param debug:
    :return:
    """
    # TODO: Add geojson support
    fmt = "json"

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

    if fmt not in ("json", "geojson"):
        raise HTTPException(
            status_code=400,
            detail="format argument must be one of json, geojson",
        )

    set_logging_level(debug)

    try:
        api: ScalarRequestCore = Wetterdienst(provider, network)
    except ProviderError:
        return HTTPException(
            status_code=404,
            detail=f"Given combination of provider and network not available. "
            f"Choose provider and network from {Wetterdienst.discover()}",
        )

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
            date=date,
            issue=issue,
            period=period,
            station_id=station,
            coordinates=coordinates,
            sql_values=sql_values,
            si_units=si_units,
            humanize=humanize,
        )
    except Exception as e:
        log.exception(e)

        return HTTPException(status_code=404, detail=str(e))

    indent = None
    if pretty:
        indent = 4

    output = values_.df

    output[Columns.DATE.value] = output[Columns.DATE.value].apply(lambda ts: ts.isoformat())

    output = output.replace({np.NaN: None, pd.NA: None})

    output = output.to_dict(orient="records")

    output = make_json_response(output, api.provider)

    output = json.dumps(output, indent=indent, ensure_ascii=False)

    return Response(content=output, media_type="application/json")


def make_json_response(data, provider):
    """
    Function to add wetterdienst metadata information, citation, etc as well as
    information about the data provider

    :param data:
    :param provider:
    :return:
    """
    name_local, name_english, country, copyright_, url = provider.value

    return {
        "meta": {
            "provider": {
                "name_local": name_local,
                "name_english": name_english,
                "country": country,
                "copyright": copyright_,
                "url": url,
            },
            "producer": {
                "name": PRODUCER_NAME,
                "url": PRODUCER_LINK,
                "doi": "10.5281/zenodo.3960624",
            },
        },
        "data": data,
    }


def start_service(listen_address: Optional[str] = None, reload: Optional[bool] = False):  # pragma: no cover
    from uvicorn.main import run

    setup_logging()

    if listen_address is None:
        listen_address = "127.0.0.1:7890"

    host, port = listen_address.split(":")
    port = int(port)

    run(app="wetterdienst.ui.restapi:app", host=host, port=port, reload=reload)
