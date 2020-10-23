# -*- coding: utf-8 -*-
import json
import logging

from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse

from wetterdienst import __appname__, __version__
from wetterdienst.dwd.observations import (
    DWDObservationPeriod,
    DWDObservationParameterSet,
    DWDObservationData,
    DWDObservationResolution,
)
from wetterdienst.dwd.observations.api import DWDObservationSites
from wetterdienst.util.enumeration import parse_enumeration_from_template
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


@app.get("/api/dwd/stations")
def dwd_stations(
    parameter: str = Query(default=None),
    resolution: str = Query(default=None),
    period: str = Query(default=None),
    sql: str = Query(default=None),
):

    parameter = parse_enumeration_from_template(parameter, DWDObservationParameterSet)
    resolution = parse_enumeration_from_template(resolution, DWDObservationResolution)
    period = parse_enumeration_from_template(period, DWDObservationPeriod)

    # Data acquisition.
    df = DWDObservationSites(
        parameter_set=parameter,
        resolution=resolution,
        period=period,
    ).all()

    # Postprocessing.
    df = df.dwd.lower()

    if sql is not None:
        df = df.io.sql(sql)

    return make_json_response(df.io.to_dict())


@app.get("/api/dwd/readings")
def dwd_readings(
    station: str = Query(default=None),
    parameter: str = Query(default=None),
    resolution: str = Query(default=None),
    period: str = Query(default=None),
    date: str = Query(default=None),
    sql: str = Query(default=None),
):
    """
    Acquire data from DWD.

    # TODO: Obtain lat/lon distance/number information.

    :param station:     Comma-separated list of station identifiers.
    :param parameter:   Observation measure
    :param resolution:  Frequency/granularity of measurement interval
    :param period:      Recent or historical files
    :param date:        Date or date range
    :param sql:         SQL expression
    :return:
    """

    if station is None:
        raise HTTPException(
            status_code=400, detail="Query argument 'station' is required"
        )

    if parameter is None or resolution is None or period is None:
        raise HTTPException(
            status_code=400,
            detail="Query arguments 'parameter', 'resolution' "
            "and 'period' are required",
        )

    station_ids = map(int, read_list(station))
    parameter = parse_enumeration_from_template(parameter, DWDObservationParameterSet)
    resolution = parse_enumeration_from_template(resolution, DWDObservationResolution)
    period = parse_enumeration_from_template(period, DWDObservationPeriod)

    # Data acquisition.
    observations = DWDObservationData(
        station_ids=station_ids,
        parameters=parameter,
        resolution=resolution,
        periods=period,
        tidy_data=True,
        humanize_column_names=True,
    )

    # Postprocessing.
    df = observations.collect_safe()

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


def start_service(listen_address):  # pragma: no cover
    host, port = listen_address.split(":")
    port = int(port)
    from uvicorn.main import run

    run(app="wetterdienst.service:app", host=host, port=port, reload=True)
