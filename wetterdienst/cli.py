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
from wetterdienst.provider.dwd.forecast import DwdMosmixRequest, DwdMosmixType
from wetterdienst.provider.dwd.observation import (
    DwdObservationDataset,
    DwdObservationPeriod,
    DwdObservationResolution,
)
from wetterdienst.provider.dwd.observation.api import DwdObservationRequest
from wetterdienst.provider.dwd.radar.api import DwdRadarSites
from wetterdienst.provider.eumetnet.opera.sites import OperaRadarSites
from wetterdienst.util.cli import normalize_options, read_list, setup_logging

log = logging.getLogger(__name__)


def run():
    """
    Usage:
      wetterdienst dwd observation stations --parameter=<parameter> --resolution=<resolution> --period=<period> [--station=<station>] [--latitude=<latitude>] [--longitude=<longitude>] [--number=<number>] [--distance=<distance>] [--sql=<sql>] [--format=<format>] [--target=<target>]
      wetterdienst dwd observation values --parameter=<parameter> --resolution=<resolution> [--station=<station>] [--period=<period>] [--date=<date>] [--tidy] [--sql=<sql>] [--format=<format>] [--target=<target>]
      wetterdienst dwd observation values --parameter=<parameter> --resolution=<resolution> --latitude=<latitude> --longitude=<longitude> [--period=<period>] [--number=<number>] [--distance=<distance>] [--tidy] [--date=<date>] [--sql=<sql>] [--format=<format>] [--target=<target>]
      wetterdienst dwd forecast stations --parameter=<parameter> [--mosmix-type=<mosmix-type>] [--date=<date>] [--station=<station>] [--latitude=<latitude>] [--longitude=<longitude>] [--number=<number>] [--distance=<distance>] [--sql=<sql>] [--format=<format>] [--target=<target>]
      wetterdienst dwd forecast values --parameter=<parameter> [--mosmix-type=<mosmix-type>] --station=<station> [--date=<date>] [--tidy] [--sql=<sql>] [--format=<format>] [--target=<target>]
      wetterdienst dwd about [parameters] [resolutions] [periods]
      wetterdienst dwd about coverage [--parameter=<parameter>] [--resolution=<resolution>] [--period=<period>]
      wetterdienst dwd about fields --parameter=<parameter> --resolution=<resolution> --period=<period> [--language=<language>]
      wetterdienst radar stations [--odim-code=<odim-code>] [--wmo-code=<wmo-code>] [--country-name=<country-name>]
      wetterdienst dwd radar stations
      wetterdienst service [--listen=<listen>] [--reload]
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
      --reload                      Run service and dynamically reload changed files
      -h --help                     Show this screen


    Examples requesting stations:

      # Get list of all stations for daily climate summary data in JSON format
      wetterdienst dwd observation stations --parameter=kl --resolution=daily --period=recent

      # Get list of all stations in CSV format
      wetterdienst dwd observation stations --parameter=kl --resolution=daily --period=recent --format=csv

      # Get list of specific stations
      wetterdienst dwd observation stations --resolution=daily --parameter=kl --period=recent --station=1,1048,4411

      # Get list of specific stations in GeoJSON format
      wetterdienst dwd observation stations --resolution=daily --parameter=kl --period=recent --station=1,1048,4411 --format=geojson

    Examples requesting readings:

      # Get daily climate summary data for specific stations
      wetterdienst dwd observation values --station=1048,4411 --parameter=kl --resolution=daily --period=recent

      # Get daily climate summary data for specific stations in CSV format
      wetterdienst dwd observation values --station=1048,4411 --parameter=kl --resolution=daily --period=recent

      # Get daily climate summary data for specific stations in tidy format
      wetterdienst dwd observation values --station=1048,4411 --parameter=kl --resolution=daily --period=recent --tidy

      # Limit output to specific date
      wetterdienst dwd observation values --station=1048,4411 --parameter=kl --resolution=daily --period=recent --date=2020-05-01

      # Limit output to specified date range in ISO-8601 time interval format
      wetterdienst dwd observation values --station=1048,4411 --parameter=kl --resolution=daily --period=recent --date=2020-05-01/2020-05-05

      # The real power horse: Acquire data across historical+recent data sets
      wetterdienst dwd observation values --station=1048,4411 --parameter=kl --resolution=daily --date=1969-01-01/2020-06-11

      # Acquire monthly data for 2020-05
      wetterdienst dwd observation values --station=1048,4411 --parameter=kl --resolution=monthly --date=2020-05

      # Acquire monthly data from 2017-01 to 2019-12
      wetterdienst dwd observation values --station=1048,4411 --parameter=kl --resolution=monthly --date=2017-01/2019-12

      # Acquire annual data for 2019
      wetterdienst dwd observation values --station=1048,4411 --parameter=kl --resolution=annual --date=2019

      # Acquire annual data from 2010 to 2020
      wetterdienst dwd observation values --station=1048,4411 --parameter=kl --resolution=annual --date=2010/2020

      # Acquire hourly data
      wetterdienst dwd observation values --station=1048,4411 --parameter=air_temperature --resolution=hourly --period=recent --date=2020-06-15T12

    Examples using geospatial features:

      # Acquire stations and readings by geoposition, request specific number of nearby stations.
      wetterdienst dwd observation stations --resolution=daily --parameter=kl --period=recent --lat=49.9195 --lon=8.9671 --num=5
      wetterdienst dwd observation values --resolution=daily --parameter=kl --period=recent --lat=49.9195 --lon=8.9671 --num=5 --date=2020-06-30

      # Acquire stations and readings by geoposition, request stations within specific distance.
      wetterdienst dwd observation stations --resolution=daily --parameter=kl --period=recent --lat=49.9195 --lon=8.9671 --distance=25
      wetterdienst dwd observation values --resolution=daily --parameter=kl --period=recent --lat=49.9195 --lon=8.9671 --distance=25 --date=2020-06-30

    Examples using SQL filtering:

      # Find stations by state.
      wetterdienst dwd observation stations --parameter=kl --resolution=daily --period=recent --sql="SELECT * FROM data WHERE state='Sachsen'"

      # Find stations by name (LIKE query).
      wetterdienst dwd observation stations --parameter=kl --resolution=daily --period=recent --sql="SELECT * FROM data WHERE lower(station_name) LIKE lower('%dresden%')"

      # Find stations by name (regexp query).
      wetterdienst dwd observation stations --parameter=kl --resolution=daily --period=recent --sql="SELECT * FROM data WHERE regexp_matches(lower(station_name), lower('.*dresden.*'))"

      # Filter measurements: Display daily climate observation readings where the maximum temperature is below two degrees celsius.
      wetterdienst dwd observation values --station=1048,4411 --parameter=kl --resolution=daily --period=recent --sql="SELECT * FROM data WHERE temperature_air_max_200 < 2.0;"

      # Filter measurements: Same as above, but use tidy format.
      # FIXME: Currently, this does not work, see https://github.com/earthobservations/wetterdienst/issues/377.
      wetterdienst dwd observation values --station=1048,4411 --parameter=kl --resolution=daily --period=recent --sql="SELECT * FROM data WHERE parameter='temperature_air_max_200' AND value < 2.0;" --tidy

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

    Examples for exporting data to files:

      # Export list of stations into spreadsheet
      wetterdienst dwd observations stations --parameter=kl --resolution=daily --period=recent --target=file://stations.xlsx

      # Shortcut command for fetching readings
      alias fetch="wetterdienst dwd observations values --station=1048,4411 --parameter=kl --resolution=daily --period=recent"

      # Export readings into spreadsheet (Excel-compatible)
      fetch --target="file://observations.xlsx"

      # Export readings into Parquet format and display head of Parquet file
      fetch --target="file://observations.parquet"
      parquet-tools head observations.parquet

    Examples for exporting data to databases:

      # Shortcut command for fetching readings
      alias fetch="wetterdienst dwd observation values --station=1048,4411 --parameter=kl --resolution=daily --period=recent"

      # Store readings to DuckDB
      fetch --target="duckdb:///dwd.duckdb?table=weather"

      # Store readings to InfluxDB
      fetch --target="influxdb://localhost/?database=dwd&table=weather"

      # Store readings to CrateDB
      fetch --target="crate://localhost/?database=dwd&table=weather"

    Run as HTTP service:

      # Start service on standard port, listening on http://localhost:7890.
      wetterdienst service

      # Start service on standard port and watch filesystem changes.
      # This is suitable for development.
      wetterdienst service --reload

      # Start service on public interface and specific port.
      wetterdienst service --listen=0.0.0.0:9999

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

        start_service(listen_address, reload=options.reload)
        return

    # Handle radar data inquiry. Currently, "stations only".
    if options.radar:
        if options.dwd:
            data = DwdRadarSites().all()
        else:
            if options.odim_code:
                data = OperaRadarSites().by_odimcode(options.odim_code)
            elif options.wmo_code:
                data = OperaRadarSites().by_wmocode(options.wmo_code)
            elif options.country_name:
                data = OperaRadarSites().by_countryname(options.country_name)
            else:
                data = OperaRadarSites().all()

        output = json.dumps(data, indent=4)
        print(output)

        return

    # Output domain information.
    if options.about:
        about(options)
        return

    # Sanity checks.
    if (options["values"] or options.forecast) and options.format == "geojson":
        raise KeyError("GeoJSON format only available for stations output")

    # Acquire station list, also used for readings if required.
    # Filtering applied for distance (a.k.a. nearby) and pre-selected stations
    stations = None
    if options.observation:
        stations = DwdObservationRequest(
            parameter=options.parameter,
            resolution=options.resolution,
            period=options.period,
            tidy=options.tidy,
        )
    elif options.forecast:
        stations = DwdMosmixRequest(
            parameter=options.parameter,
            mosmix_type=DwdMosmixType.LARGE,
            tidy=options.tidy,
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
            # TODO: Add stream-based processing here.
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

    # Apply filtering by SQL.
    if options.sql:
        log.info(f"Filtering with SQL: {options.sql}")
        df = df.io.sql(options.sql)

    # Emit to data sink, e.g. write to database.
    if options.target:
        df.io.export(options.target)
        return

    # Render to output format.
    try:
        output = df.dwd.format(options.format)
    except KeyError as ex:
        log.error(f'{ex}. Output format must be one of "json", "geojson", "csv".')
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
        output(DwdObservationDataset)

    elif options.resolutions:
        output(DwdObservationResolution)

    elif options.periods:
        output(DwdObservationPeriod)

    elif options.coverage:
        metadata = DwdObservationRequest.discover(
            filter_=options.resolution,
            dataset=read_list(options.parameter),
            flatten=False,
        )
        output = json.dumps(metadata, indent=4)
        print(output)

    elif options.fields:
        metadata = DwdObservationRequest.describe_fields(
            dataset=read_list(options.parameter),
            resolution=options.resolution,
            period=read_list(options.period),
            language=options.language,
        )
        output = pformat(dict(metadata))
        print(output)

    else:
        log.error(
            'Please invoke "wetterdienst dwd about" with one of these subcommands:'
        )
        output(["parameters", "resolutions", "periods", "coverage"])
        sys.exit(1)
