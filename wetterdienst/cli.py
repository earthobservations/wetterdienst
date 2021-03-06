# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import json
import logging
import sys
from pprint import pformat

import pandas as pd
from docopt import docopt
from munch import Munch

from wetterdienst import __appname__, __version__
from wetterdienst.dwd.forecasts import DwdMosmixRequest, DwdMosmixType
from wetterdienst.dwd.observations import (
    DwdObservationParameterSet,
    DwdObservationPeriod,
    DwdObservationResolution,
)
from wetterdienst.dwd.observations.api import (
    DwdObservationMetadata,
    DwdObservationRequest,
)
from wetterdienst.util.cli import normalize_options, read_list, setup_logging

log = logging.getLogger(__name__)


def run():
    """
    Usage:
      wetterdienst dwd observations stations --parameter=<parameter> --resolution=<resolution> --period=<period> [--station=<station>] [--latitude=<latitude>] [--longitude=<longitude>] [--number=<number>] [--distance=<distance>] [--sql=<sql>] [--format=<format>]
      wetterdienst dwd observations values --parameter=<parameter> --resolution=<resolution> --station=<station> [--period=<period>] [--date=<date>] [--tidy] [--sql=<sql>] [--format=<format>] [--target=<target>]
      wetterdienst dwd observations values --parameter=<parameter> --resolution=<resolution> --latitude=<latitude> --longitude=<longitude> [--period=<period>] [--number=<number>] [--distance=<distance>] [--tidy] [--date=<date>] [--sql=<sql>] [--format=<format>] [--target=<target>]
      wetterdienst dwd forecasts stations [--date=<date>] [--station=<station>] [--latitude=<latitude>] [--longitude=<longitude>] [--number=<number>] [--distance=<distance>] [--sql=<sql>] [--format=<format>]
      wetterdienst dwd forecasts values --mosmix-type=<mosmix-type> --station=<station> [--parameter=<parameter>] [--date=<date>] [--tidy] [--sql=<sql>] [--format=<format>] [--target=<target>]
      wetterdienst dwd about [parameters] [resolutions] [periods]
      wetterdienst dwd about coverage [--parameter=<parameter>] [--resolution=<resolution>] [--period=<period>]
      wetterdienst dwd about fields --parameter=<parameter> --resolution=<resolution> --period=<period> [--language=<language>]
      wetterdienst service [--listen=<listen>]
      wetterdienst --version
      wetterdienst (-h | --help)

    Options:
      --parameter=<parameter>       Parameter Set/Parameter, e.g. "kl" or "precipitation_height", etc.
      --resolution=<resolution>     Dataset resolution: "annual", "monthly", "daily", "hourly", "minute_10", "minute_1"
      --period=<period>             Dataset period: "historical", "recent", "now"
      --station=<station>           Comma-separated list of station identifiers
      --latitude=<latitude>         Latitude for filtering by geoposition.
      --longitude=<longitude>       Longitude for filtering by geoposition.
      --number=<number>             Number of nearby stations when filtering by geoposition.
      --distance=<distance>         Maximum distance in km when filtering by geoposition.
      --date=<date>                 Date for filtering data. Can be either a single date(time) or
                                    an ISO-8601 time interval, see https://en.wikipedia.org/wiki/ISO_8601#Time_intervals.
      --mosmix-type=<mosmix-type>   type of mosmix, either 'small' or 'large'
      --sql=<sql>                   SQL query to apply to DataFrame.
      --format=<format>             Output format. [Default: json]
      --target=<target>             Output target for storing data into different data sinks.
      --language=<language>         Output language. [Default: en]
      --version                     Show version information
      --debug                       Enable debug messages
      --listen=<listen>             HTTP server listen address. [Default: localhost:7890]
      -h --help                     Show this screen


    Examples requesting stations:

      # Get list of all stations for daily climate summary data in JSON format
      wetterdienst dwd stations --parameter=kl --resolution=daily --period=recent

      # Get list of all stations in CSV format
      wetterdienst dwd stations --parameter=kl --resolution=daily --period=recent --format=csv

      # Get list of specific stations
      wetterdienst dwd stations --resolution=daily --parameter=kl --period=recent --station=1,1048,4411

      # Get list of specific stations in GeoJSON format
      wetterdienst dwd stations --resolution=daily --parameter=kl --period=recent --station=1,1048,4411 --format=geojson

    Examples requesting readings:

      # Get daily climate summary data for specific stations
      wetterdienst dwd readings --station=1048,4411 --parameter=kl --resolution=daily --period=recent

      # Optionally save/restore to/from disk in order to avoid asking upstream servers each time
      wetterdienst dwd readings --station=1048,4411 --parameter=kl --resolution=daily --period=recent

      # Limit output to specific date
      wetterdienst dwd readings --station=1048,4411 --parameter=kl --resolution=daily --period=recent --date=2020-05-01

      # Limit output to specified date range in ISO-8601 time interval format
      wetterdienst dwd readings --station=1048,4411 --parameter=kl --resolution=daily --period=recent --date=2020-05-01/2020-05-05

      # The real power horse: Acquire data across historical+recent data sets
      wetterdienst dwd readings --station=1048,4411 --parameter=kl --resolution=daily --period=historical,recent --date=1969-01-01/2020-06-11

      # Acquire monthly data for 2020-05
      wetterdienst dwd readings --station=1048,4411 --parameter=kl --resolution=monthly --period=recent,historical --date=2020-05

      # Acquire monthly data from 2017-01 to 2019-12
      wetterdienst dwd readings --station=1048,4411 --parameter=kl --resolution=monthly --period=recent,historical --date=2017-01/2019-12

      # Acquire annual data for 2019
      wetterdienst dwd readings --station=1048,4411 --parameter=kl --resolution=annual --period=recent,historical --date=2019

      # Acquire annual data from 2010 to 2020
      wetterdienst dwd readings --station=1048,4411 --parameter=kl --resolution=annual --period=recent,historical --date=2010/2020

      # Acquire hourly data
      wetterdienst dwd readings --station=1048,4411 --parameter=air_temperature --resolution=hourly --period=recent --date=2020-06-15T12

    Examples using geospatial features:

      # Acquire stations and readings by geoposition, request specific number of nearby stations.
      wetterdienst dwd stations --resolution=daily --parameter=kl --period=recent --lat=49.9195 --lon=8.9671 --num=5
      wetterdienst dwd readings --resolution=daily --parameter=kl --period=recent --lat=49.9195 --lon=8.9671 --num=5 --date=2020-06-30

      # Acquire stations and readings by geoposition, request stations within specific radius.
      wetterdienst dwd stations --resolution=daily --parameter=kl --period=recent --lat=49.9195 --lon=8.9671 --distance=25
      wetterdienst dwd readings --resolution=daily --parameter=kl --period=recent --lat=49.9195 --lon=8.9671 --distance=25 --date=2020-06-30

    Examples using SQL filtering:

      # Find stations by state.
      wetterdienst dwd stations --parameter=kl --resolution=daily --period=recent --sql="SELECT * FROM data WHERE state='Sachsen'"

      # Find stations by name (LIKE query).
      wetterdienst dwd stations --parameter=kl --resolution=daily --period=recent --sql="SELECT * FROM data WHERE lower(station_name) LIKE lower('%dresden%')"

      # Find stations by name (regexp query).
      wetterdienst dwd stations --parameter=kl --resolution=daily --period=recent --sql="SELECT * FROM data WHERE regexp_matches(lower(station_name), lower('.*dresden.*'))"

      # Filter measurements: Display daily climate observation readings where the maximum temperature is below two degrees.
      wetterdienst dwd readings --station=1048,4411 --parameter=kl --resolution=daily --period=recent --sql="SELECT * FROM data WHERE element='temperature_air_max_200' AND value < 2.0;"

    Examples for inquiring metadata:

      # Display list of available parameters (air_temperature, precipitation, pressure, ...)
      wetterdienst dwd about parameters

      # Display list of available resolutions (10_minutes, hourly, daily, ...)
      wetterdienst dwd about resolutions

      # Display list of available periods (historical, recent, now)
      wetterdienst dwd about periods

      # Display coverage/correlation between parameters, resolutions and periods.
      # This can answer questions like ...
      wetterdienst dwd about coverage

      # Tell me all periods and resolutions available for 'air_temperature'.
      wetterdienst dwd about coverage --parameter=air_temperature

      # Tell me all parameters available for 'daily' resolution.
      wetterdienst dwd about coverage --resolution=daily

    Examples for exporting data to databases:

      # Shortcut command for fetching readings from DWD
      alias fetch="wetterdienst dwd readings --station=1048,4411 --parameter=kl --resolution=daily --period=recent"

      # Store readings to DuckDB
      fetch --target="duckdb://database=dwd.duckdb&table=weather"

      # Store readings to InfluxDB
      fetch --target="influxdb://localhost/?database=dwd&table=weather"

      # Store readings to CrateDB
      fetch --target="crate://localhost/?database=dwd&table=weather"

    Run as HTTP service:

      wetterdienst dwd service
      wetterdienst dwd service --listen=0.0.0.0:9999

    """
    appname = f"{__appname__} {__version__}"

    # Read command line options.
    options = normalize_options(docopt(run.__doc__, version=appname))

    # Setup logging.
    debug = options.get("debug")

    log_level = logging.INFO

    if debug:  # pragma: no cover
        log_level = logging.DEBUG

    setup_logging(log_level)

    # Run service.
    if options.service:  # pragma: no cover
        listen_address = options.listen
        log.info(f"Starting {appname}")
        log.info(f"Starting web service on {listen_address}")
        from wetterdienst.service import start_service

        start_service(listen_address)
        return

    # Output domain information.
    if options.about:
        about(options)
        return

    # Sanity checks.
    if (options["values"] or options.forecasts) and options.format == "geojson":
        raise KeyError("GeoJSON format only available for stations output")

    # Acquire station list, also used for readings if required.
    # Filtering applied for distance (a.k.a. nearby) and pre-selected stations
    stations = None
    if options.observations:
        stations = DwdObservationRequest(
            parameter=options.parameter,
            resolution=options.resolution,
            period=options.period,
            tidy_data=options.tidy,
        )
    elif options.forecasts:
        stations = DwdMosmixRequest(
            mosmix_type=DwdMosmixType.LARGE, tidy_data=options.tidy
        )

    if options.latitude and options.longitude:
        if options.number:
            stations = stations.nearby_number(
                latitude=float(options.latitude),
                longitude=float(options.longitude),
                number=int(options.number),
            )
        elif options.distance:
            stations = stations.nearby_radius(
                latitude=float(options.latitude),
                longitude=float(options.longitude),
                max_distance_in_km=int(options.distance),
            )
    elif options.station:
        stations = stations.filter(read_list(options.station))
    else:
        stations = stations.all()

    df = pd.DataFrame()

    if options.stations:
        df = stations.df
    elif options["values"]:
        try:
            df = stations.values.all().df
        except ValueError as ex:
            log.exception(ex)
            sys.exit(1)

    if df.empty:
        log.error("No data available for given constraints")
        sys.exit(1)

    # Filter readings by datetime expression.
    if options["values"] and options.date:
        df = df.dwd.filter_by_date(options.date, stations.stations.resolution)

    # Make column names lowercase.
    df = df.dwd.lower()

    # Apply filtering by SQL.
    if options.sql:
        log.info(f"Filtering with SQL: {options.sql}")
        df = df.io.sql(options.sql)

    # Emit to data sink, e.g. write to database.
    if options.target:
        log.info(f"Writing data to target {options.target}")
        df.io.export(options.target)
        return

    # Render to output format.
    try:
        output = df.dwd.format(options.format)
    except KeyError as ex:
        log.error(
            f'{ex}. Output format must be one of "json", "geojson", "csv", "excel".'
        )
        sys.exit(1)

    print(output)


def about(options: Munch):
    """
    Output possible arguments for command line options
    "--parameter", "--resolution" and "--period".

    :param options: Normalized docopt command line options.
    """

    def output(thing):
        for item in thing:
            if item:
                if hasattr(item, "value"):
                    value = item.value
                else:
                    value = item
                print("-", value)

    if options.parameters:
        output(DwdObservationParameterSet)

    elif options.resolutions:
        output(DwdObservationResolution)

    elif options.periods:
        output(DwdObservationPeriod)

    elif options.coverage:
        metadata = DwdObservationMetadata(
            resolution=options.resolution,
            parameter=read_list(options.parameter),
            period=read_list(options.period),
        )
        output = json.dumps(metadata.discover_parameter_sets(), indent=4)
        print(output)

    elif options.fields:
        metadata = DwdObservationMetadata(
            resolution=options.resolution,
            parameter=read_list(options.parameter),
            period=read_list(options.period),
        )
        output = pformat(dict(metadata.describe_fields(language=options.language)))
        print(output)

    else:
        log.error(
            'Please invoke "wetterdienst dwd about" with one of these subcommands:'
        )
        output(["parameters", "resolutions", "periods", "coverage"])
        sys.exit(1)
