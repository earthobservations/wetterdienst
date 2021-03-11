# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import json
import logging

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse, PlainTextResponse

from wetterdienst import __appname__, __version__
from wetterdienst.dwd.forecasts import DwdMosmixRequest
from wetterdienst.dwd.observations.api import DwdObservationRequest
from wetterdienst.util.cli import read_list

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
            <h3>List of stations</h3>
            <ul>
            <li><a href="api/dwd/stations">List of stations</a></li>
            </ul>
            <h3>Observations</h3>
            <ul>
            <li><a href="api/dwd/readings">Observations</a></li>
            </ul>
        </body>
    </html>
    """


@app.get("/robots.txt", response_class=PlainTextResponse)
def robots():
    return """
User-agent: *
Disallow: /api/
    """.strip()


@app.get("/api/dwd/{product}/stations")
def dwd_stations(
    product: str,
    parameter: str = Query(default=None),
    resolution: str = Query(default=None),
    period: str = Query(default=None),
    mosmix_type: str = Query(default=None),
    lon: float = Query(default=None),
    lat: float = Query(default=None),
    number_nearby: int = Query(default=None),
    max_distance_in_km: int = Query(default=None),
    sql: str = Query(default=None),
):
    if product not in ["observations", "mosmix"]:
        return HTTPException(status_code=404, detail=f"product {product} not found")

    # Data acquisition.
    if product == "observations":
        if parameter is None or resolution is None or period is None:
            raise HTTPException(
                status_code=400,
                detail="Query arguments 'parameter', 'resolution' "
                "and 'period' are required",
            )

        stations = DwdObservationRequest(
            parameter=parameter,
            resolution=resolution,
            period=period,
        )
    else:
        stations = DwdMosmixRequest(mosmix_type=mosmix_type)

    if lon and lat and (number_nearby or max_distance_in_km):
        if number_nearby:
            request = stations.nearby_number(
                latitude=lat, longitude=lon, number=number_nearby
            )
        else:
            request = stations.nearby_radius(
                latitude=lat, longitude=lon, max_distance_in_km=max_distance_in_km
            )
    else:
        request = stations.all()

    # Postprocessing.
    df = request.df.dwd.lower()

    if sql is not None:
        df = df.io.sql(sql)

    return make_json_response(df.fillna(-999).io.to_dict())


@app.get("/api/dwd/{product}/values")
def dwd_values(
    product: str,
    station: str = Query(default=None),
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

    :param product:     string for product, either observations or mosmix
    :param station:     Comma-separated list of station identifiers
    :param parameter:   Observation measure
    :param resolution:  Frequency/granularity of measurement interval
    :param period:      Recent or historical files
    :param mosmix_type: MOSMIX type. Either "small" or "large".
    :param date:        Date or date range
    :param sql:         SQL expression
    :param tidy:        Whether to return data in tidy format. Default: True.
    :return:
    """
    if product not in ["observations", "mosmix"]:
        return HTTPException(status_code=404, detail=f"product {product} not found")

    if station is None:
        raise HTTPException(
            status_code=400, detail="Query argument 'station' is required"
        )

    station_ids = map(str, read_list(station))

    if product == "observations":
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
            tidy_data=tidy,
        )
    else:
        if mosmix_type is None:
            raise HTTPException(
                status_code=400, detail="Query argument 'mosmix_type' is required"
            )

        request = DwdMosmixRequest(mosmix_type=mosmix_type)

    if not resolution:
        resolution = request.resolution

    # Postprocessing.
    df = request.filter(station_id=station_ids).values.all().df

    if date is not None:
        df = df.dwd.filter_by_date(date, resolution)

    df = df.dwd.lower()

    if sql is not None:
        df = df.io.sql(sql)

    data = json.loads(df.to_json(orient="records", date_format="iso"))

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


def start_service(listen_address, reload: bool = False):  # pragma: no cover
    host, port = listen_address.split(":")
    port = int(port)
    from uvicorn.main import run

    run(app="wetterdienst.service:app", host=host, port=port, reload=reload)
