# -*- coding: utf-8 -*-
import sys
import json
import logging
from datetime import datetime, timedelta

from docopt import docopt
from munch import Munch
import pandas as pd

from wetterdienst import (
    __version__,
    metadata_for_climate_observations,
    get_nearby_stations,
    discover_climate_observations,
)
from wetterdienst.additionals.geo_location import stations_to_geojson
from wetterdienst.additionals.time_handling import mktimerange, parse_datetime
from wetterdienst.additionals.util import normalize_options, setup_logging, read_list
from wetterdienst.api import DWDStationRequest
from wetterdienst.enumerations.column_names_enumeration import DWDMetaColumns
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution

log = logging.getLogger(__name__)


def run():
    """
    Usage:
      wetterdienst stations --parameter=<parameter> --resolution=<resolution> --period=<period> [--station=] [--latitude=] [--longitude=] [--number=] [--distance=] [--persist] [--format=<format>]
      wetterdienst readings --parameter=<parameter> --resolution=<resolution> --period=<period> --station=<station> [--persist] [--date=<date>] [--format=<format>]
      wetterdienst readings --parameter=<parameter> --resolution=<resolution> --period=<period> --latitude= --longitude= [--number=] [--distance=] [--persist] [--date=<date>] [--format=<format>]
      wetterdienst about [parameters] [resolutions] [periods]
      wetterdienst about coverage [--parameter=<parameter>] [--resolution=<resolution>] [--period=<period>]
      wetterdienst --version
      wetterdienst (-h | --help)

    Options:
      --parameter=<parameter>       Parameter/variable, e.g. "kl", "air_temperature", "precipitation", etc.
      --resolution=<resolution>     Dataset resolution: "annual", "monthly", "daily", "hourly", "minute_10", "minute_1"
      --period=<period>             Dataset period: "historical", "recent", "now"
      --station=<station>           Comma-separated list of station identifiers
      --latitude=<latitude>         Latitude for filtering by geoposition.
      --longitude=<longitude>       Longitude for filtering by geoposition.
      --number=<number>             Number of nearby stations when filtering by geoposition.
      --distance=<distance>         Maximum distance in km when filtering by geoposition.
      --persist                     Save and restore data to filesystem w/o going to the network
      --date=<date>                 Date for filtering data. Can be either a single date(time) or
                                    an ISO-8601 time interval, see https://en.wikipedia.org/wiki/ISO_8601#Time_intervals.
      --format=<format>             Output format. [Default: json]
      --version                     Show version information
      --debug                       Enable debug messages
      -h --help                     Show this screen


    Examples requesting stations:

      # Get list of all stations for daily climate summary data in JSON format
      wetterdienst stations --parameter=kl --resolution=daily --period=recent

      # Get list of all stations in CSV format
      wetterdienst stations --parameter=kl --resolution=daily --period=recent --format=csv

      # Get list of specific stations
      wetterdienst stations --resolution=daily --parameter=kl --period=recent --station=1,1048,4411

      # Get list of specific stations in GeoJSON format
      wetterdienst stations --resolution=daily --parameter=kl --period=recent --station=1,1048,4411 --format=geojson

    Examples requesting readings:

      # Get daily climate summary data for specific stations
      wetterdienst readings --station=1048,4411 --parameter=kl --resolution=daily --period=recent

      # Optionally save/restore to/from disk in order to avoid asking upstream servers each time
      wetterdienst readings --station=1048,4411 --parameter=kl --resolution=daily --period=recent --persist

      # Limit output to specific date
      wetterdienst readings --station=1048,4411 --parameter=kl --resolution=daily --period=recent --date=2020-05-01

      # Limit output to specified date range in ISO-8601 time interval format
      wetterdienst readings --station=1048,4411 --parameter=kl --resolution=daily --period=recent --date=2020-05-01/2020-05-05

      # The real power horse: Acquire data across historical+recent data sets
      wetterdienst readings --station=1048,4411 --parameter=kl --resolution=daily --period=historical,recent --date=1969-01-01/2020-06-11

      # Acquire monthly data for 2020-05
      wetterdienst readings --station=1048,4411 --parameter=kl --resolution=monthly --period=recent,historical --date=2020-05

      # Acquire monthly data from 2017-01 to 2019-12
      wetterdienst readings --station=1048,4411 --parameter=kl --resolution=monthly --period=recent,historical --date=2017-01/2019-12

      # Acquire annual data for 2019
      wetterdienst readings --station=1048,4411 --parameter=kl --resolution=annual --period=recent,historical --date=2019

      # Acquire annual data from 2010 to 2020
      wetterdienst readings --station=1048,4411 --parameter=kl --resolution=annual --period=recent,historical --date=2010/2020

      # Acquire hourly data
      wetterdienst readings --station=1048,4411 --parameter=air_temperature --resolution=hourly --period=recent --date=2020-06-15T12

    Examples using geospatial features:

      # Acquire stations and readings by geoposition, request specific number of nearby stations.
      wetterdienst stations --resolution=daily --parameter=kl --period=recent --lat=49.9195 --lon=8.9671 --num=5
      wetterdienst readings --resolution=daily --parameter=kl --period=recent --lat=49.9195 --lon=8.9671 --num=5 --date=2020-06-30

      # Acquire stations and readings by geoposition, request stations within specific radius.
      wetterdienst stations --resolution=daily --parameter=kl --period=recent --lat=49.9195 --lon=8.9671 --distance=25
      wetterdienst readings --resolution=daily --parameter=kl --period=recent --lat=49.9195 --lon=8.9671 --distance=25 --date=2020-06-30

    Examples for inquring metadata:

      # Display list of available parameters (air_temperature, precipitation, pressure, ...)
      wetterdienst about parameters

      # Display list of available resolutions (10_minutes, hourly, daily, ...)
      wetterdienst about resolutions

      # Display list of available periods (historical, recent, now)
      wetterdienst about periods

      # Display coverage/correlation between parameters, resolutions and periods.
      # This can answer questions like ...
      wetterdienst about coverage

      # Tell me all periods and resolutions available for 'air_temperature'.
      wetterdienst about coverage --parameter=air_temperature

      # Tell me all parameters available for 'daily' resolution.
      wetterdienst about coverage --resolution=daily

    """

    # Read command line options.
    options = normalize_options(
        docopt(run.__doc__, version=f"wetterdienst {__version__}")
    )

    # Setup logging.
    debug = options.get("debug")
    log_level = logging.INFO
    if debug:
        log_level = logging.DEBUG
    setup_logging(log_level)

    if options.about:
        about(options)
        return

    if options.stations:
        df = metadata_for_climate_observations(
            parameter=options.parameter,
            time_resolution=options.resolution,
            period_type=options.period,
        )

        if options.station:
            station_ids = read_list(options.station)
            df = df[df.STATION_ID.isin(station_ids)]

        elif options.latitude and options.longitude:
            df = get_nearby(options)

        if df.empty:
            log.error("No data available for given constraints")
            sys.exit(1)

    elif options.readings:

        if options.station:
            station_ids = read_list(options.station)

        elif options.latitude and options.longitude:
            df = get_nearby(options)
            station_ids = df.STATION_ID.unique()

        else:
            raise KeyError("Either --station or --lat, --lon required")

        request = DWDStationRequest(
            station_ids=station_ids,
            parameter=read_list(options.parameter),
            time_resolution=options.resolution,
            period_type=read_list(options.period),
            write_file=options.persist,
            prefer_local=options.persist,
            humanize_column_names=True,
            tidy_data=True,
        )
        data = list(request.collect_data())

        if not data:
            log.error("No data available for given constraints")
            sys.exit(1)

        df = pd.concat(data)

    if options.readings:

        if options.date:

            # Filter by time interval.
            if "/" in options.date:
                date_from, date_to = options.date.split("/")
                date_from = parse_datetime(date_from)
                date_to = parse_datetime(date_to)
                if request.time_resolution in (
                    TimeResolution.ANNUAL,
                    TimeResolution.MONTHLY,
                ):
                    date_from, date_to = mktimerange(
                        request.time_resolution, date_from, date_to
                    )
                    expression = (date_from <= df[DWDMetaColumns.FROM_DATE.value]) & (
                        df[DWDMetaColumns.TO_DATE.value] <= date_to
                    )
                else:
                    expression = (date_from <= df[DWDMetaColumns.DATE.value]) & (
                        df[DWDMetaColumns.DATE.value] <= date_to
                    )
                df = df[expression]

            # Filter by date.
            else:
                date = parse_datetime(options.date)
                if request.time_resolution in (
                    TimeResolution.ANNUAL,
                    TimeResolution.MONTHLY,
                ):
                    date_from, date_to = mktimerange(request.time_resolution, date)
                    expression = (date_from <= df[DWDMetaColumns.FROM_DATE.value]) & (
                        df[DWDMetaColumns.TO_DATE.value] <= date_to
                    )
                else:
                    expression = date == df[DWDMetaColumns.DATE.value]
                df = df[expression]

    # Make column names lowercase.
    df = df.rename(columns=str.lower)
    for attribute in DWDMetaColumns.PARAMETER, DWDMetaColumns.ELEMENT:
        attribute_name = attribute.value.lower()
        if attribute_name in df:
            df[attribute_name] = df[attribute_name].str.lower()

    # Output as JSON.
    if options.format == "json":
        output = df.to_json(orient="records", date_format="iso", indent=4)

    # Output as GeoJSON.
    elif options.format == "geojson":
        if options.readings:
            raise KeyError("GeoJSON format only available for stations output")
        output = json.dumps(stations_to_geojson(df), indent=4)

    # Output as CSV.
    elif options.format == "csv":
        output = df.to_csv(index=False, date_format="%Y-%m-%dT%H-%M-%S")

    # Output as XLSX.
    # FIXME: Make --format=excel write to a designated file.
    elif options.format == "excel":
        # TODO: Obtain output file name from command line.
        output_filename = "output.xlsx"
        log.info(f"Writing {output_filename}")
        df.to_excel(output_filename, index=False)
        return

    else:
        log.error('Output format must be one of "json", "geojson", "csv", "excel".')
        sys.exit(1)

    print(output)


def get_nearby(options: Munch) -> pd.DataFrame:
    """
    Convenience utility function to dispatch command
    line options related to geospatial requests.

    It will get used from both acquisition requests for station-
    and measurement data.

    It is able to handle both "number of stations nearby"
    and "maximum distance in kilometers" query flavors.

    :param options: Normalized docopt command line options.
    :return: nearby_stations
    """

    # Obtain DWIM date range for station liveness.
    # TODO: Obtain from user.
    #   However, some dates will not work and Pandas will croak with:
    #   KeyError: "None of [Int64Index([0, 0, 0, 0, 0], dtype='int64')] are in the [index]"
    # See also https://github.com/earthobservations/wetterdienst/pull/145#discussion_r487698588.

    days500 = datetime.now() + timedelta(days=-500)
    now = datetime.now() + timedelta(days=-2)

    minimal_date = datetime(days500.year, days500.month, days500.day)
    maximal_date = datetime(now.year, now.month, now.day)

    nearby_baseline_args = dict(
        latitude=float(options.latitude),
        longitude=float(options.longitude),
        minimal_available_date=minimal_date,
        maximal_available_date=maximal_date,
        parameter=options.parameter,
        time_resolution=options.resolution,
        period_type=options.period,
    )

    if options.latitude and options.longitude:
        if options.number:
            nearby_stations = get_nearby_stations(
                **nearby_baseline_args,
                num_stations_nearby=int(options.number),
            )
        elif options.distance:
            nearby_stations = get_nearby_stations(
                **nearby_baseline_args,
                max_distance_in_km=int(options.distance),
            )

        return nearby_stations

    return pd.DataFrame()


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
        output(Parameter)

    elif options.resolutions:
        output(TimeResolution)

    elif options.periods:
        output(PeriodType)

    elif options.coverage:
        print(
            discover_climate_observations(
                time_resolution=options.resolution,
                parameter=read_list(options.parameter),
                period_type=read_list(options.period),
            )
        )

    else:
        log.error('Please invoke "wetterdienst about" with one of these subcommands:')
        output(["parameters", "resolutions", "periods", "coverage"])
        sys.exit(1)
