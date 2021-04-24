# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import json
import logging
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse

from wetterdienst import __appname__, __version__
from wetterdienst.provider.dwd.forecast import DwdMosmixRequest
from wetterdienst.provider.dwd.observation.api import DwdObservationRequest
from wetterdienst.util.cli import read_list, setup_logging

app = FastAPI(debug=False)

log = logging.getLogger(__name__)

dwd_source = "https://opendata.dwd.de/climate_environment/CDC/"
dwd_copyright = "© Deutscher Wetterdienst (DWD), Climate Data Center (CDC)"
producer_name = "Wetterdienst"
producer_link = "https://github.com/earthobservations/wetterdienst"


@app.get("/", response_class=HTMLResponse)
def index():
    appname = f"{__appname__} {__version__}"
    about = "Wetterdienst - Open weather data for humans."
    return f"""
    <html>
        <head>
            <title>{appname}</title>
        </head>
        <body>
            <h3>About</h3>
            {about}
            <ul>
            <li>Source: DWD » CDC - <a href="{dwd_source}">{dwd_source}</a></li>
            <li>
                Producer: {producer_name}
                -
                <a href="{producer_link}">{producer_link}</a></li>
            <li>Data copyright: {dwd_copyright}</li>
            </ul>
            <h3>Examples</h3>
            <ul>
            <li><a href="api/dwd/observation/stations?parameter=kl&resolution=daily&period=recent">Observation stations</a></li>
            <li><a href="api/dwd/observation/values?parameter=kl&resolution=daily&period=recent&stations=00011">Observation values</a></li>
            </ul>
        </body>
    </html>
    """  # noqa:E501,B950


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return """
User-agent: *
Disallow: /api/
    """.strip()


@app.get("/api/dwd/{kind}/stations")
def dwd_stations(
    kind: str,
    parameter: str = Query(default=None),
    resolution: str = Query(default=None),
    period: str = Query(default=None),
    mosmix_type: str = Query(default=None),
    longitude: float = Query(default=None),
    latitude: float = Query(default=None),
    rank: int = Query(default=None),
    distance: int = Query(default=None),
    sql: str = Query(default=None),
):
    if kind not in ["observation", "forecast"]:
        return HTTPException(status_code=404, detail=f"product {kind} not found")

    # Data acquisition.
    if kind == "observation":
        if parameter is None or resolution is None or period is None:
            raise HTTPException(
                status_code=400,
                detail="Query arguments 'parameter', 'resolution' "
                "and 'period' are required",
            )

        stations = DwdObservationRequest(
            parameter=parameter, resolution=resolution, period=period, si_units=False
        )
    else:
        stations = DwdMosmixRequest(
            parameter=parameter, mosmix_type=mosmix_type, si_units=False
        )

    if longitude and latitude and (rank or distance):
        if rank:
            results = stations.filter_by_rank(
                latitude=latitude, longitude=longitude, rank=rank
            )
        else:
            results = stations.filter_by_distance(
                latitude=latitude, longitude=longitude, distance=distance, unit="km"
            )
    else:
        results = stations.all()

    # Postprocessing.
    if sql is not None:
        results.filter_by_sql(sql)
    results.fill_gaps()

    return make_json_response(results.to_dict())


@app.get("/api/dwd/{kind}/values")
def dwd_values(
    kind: str,
    stations: str = Query(default=None),
    parameter: str = Query(default=None),
    resolution: str = Query(default=None),
    period: str = Query(default=None),
    mosmix_type: str = Query(default=None),
    date: str = Query(default=None),
    sql: str = Query(default=None),
    tidy: bool = Query(default=True),
):
    """
    Acquire data from DWD.

    # TODO: Obtain lat/lon distance/number information.

    :param provider:
    :param kind:        string for product, either observation or forecast
    :param stations:     Comma-separated list of station identifiers.
    :param parameter:   Observation measure
    :param resolution:  Frequency/granularity of measurement interval
    :param period:      Recent or historical files
    :param mosmix_type: MOSMIX type. Either "small" or "large".
    :param date:        Date or date range
    :param sql:         SQL expression
    :param tidy:        Whether to return data in tidy format. Default: True.
    :return:
    """
    if kind not in ["observation", "mosmix"]:
        return HTTPException(
            status_code=404,
            detail=f"Unknown value for query argument 'kind={kind}' {kind}",
        )

    if stations is None:
        raise HTTPException(
            status_code=400, detail="Query argument 'stations' is required"
        )

    station_ids = map(str, read_list(stations))

    if kind == "observation":
        if parameter is None or resolution is None or period is None:
            raise HTTPException(
                status_code=400,
                detail="Query arguments 'parameter', 'resolution' "
                "and 'period' are required",
            )

        # Data acquisition.
        request = DwdObservationRequest(
            parameter=parameter,
            resolution=resolution,
            period=period,
            tidy=tidy,
            si_units=False,
        )
    else:
        if parameter is None or mosmix_type is None:
            raise HTTPException(
                status_code=400, detail="Query argument 'mosmix_type' is required"
            )

        request = DwdMosmixRequest(
            parameter=parameter, mosmix_type=mosmix_type, si_units=False
        )

    # Postprocessing.
    results = request.filter_by_station_id(station_id=station_ids).values.all()

    if date is not None:
        results.filter_by_date(date)

    if sql is not None:
        results.filter_by_sql(sql)

    data = json.loads(results.to_json())

    return make_json_response(data)


def make_json_response(data):
    response = {
        "meta": {
            "source": dwd_source,
            "copyright": dwd_copyright,
            "producer": f"{producer_name} - {producer_link}",
        },
        "data": data,
    }
    return response


def start_service(
    listen_address: Optional[str] = None, reload: Optional[bool] = False
):  # pragma: no cover

    setup_logging()

    if listen_address is None:
        listen_address = "127.0.0.1:7890"

    host, port = listen_address.split(":")
    port = int(port)
    from uvicorn.main import run

    run(app="wetterdienst.ui.restapi:app", host=host, port=port, reload=reload)
