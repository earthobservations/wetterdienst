# -*- coding: utf-8 -*-
import sys
import logging

from docopt import docopt
import pandas as pd

from wetterdienst import __version__, metadata_for_dwd_data
from wetterdienst.additionals.time_handling import mktimerange, parse_datetime
from wetterdienst.additionals.util import normalize_options, setup_logging, read_list
from wetterdienst.dwd_station_request import DWDStationRequest
from wetterdienst.enumerations.column_names_enumeration import DWDMetaColumns
from wetterdienst.enumerations.parameter_enumeration import Parameter
from wetterdienst.enumerations.period_type_enumeration import PeriodType
from wetterdienst.enumerations.time_resolution_enumeration import TimeResolution

log = logging.getLogger(__name__)


def run():
    """
    Usage:
      dwd stations --parameter=<parameter> --resolution=<resolution> --period=<period> [--persist] [--format=<format>]
      dwd readings --station=<station> --parameter=<parameter> --resolution=<resolution> --period=<period> [--persist] [--date=<date>] [--format=<format>]
      dwd about [parameters] [resolutions] [periods]
      dwd --version
      dwd (-h | --help)

    Options:
      --station=<station>           Comma-separated list of station identifiers
      --parameter=<parameter>       Parameter/variable, e.g. "kl", "air_temperature", "precipitation", etc.
      --resolution=<resolution>     Dataset resolution: "annual", "monthly", "daily", "hourly", "minute_10", "minute_1"
      --period=<period>             Dataset period: "historical", "recent", "now"
      --persist                     Save and restore data to filesystem w/o going to the network
      --date=<date>                 Date for filtering data. Can be either a single date(time) or
                                    an ISO-8601 time interval, see https://en.wikipedia.org/wiki/ISO_8601#Time_intervals.
      --format=<format>             Output format. [Default: json]
      --version                     Show version information
      --debug                       Enable debug messages
      -h --help                     Show this screen


    Examples:

      # Get list of stations for daily climate summary data in JSON format
      dwd stations --parameter=kl --resolution=daily --period=recent

      # Get list of stations for daily climate summary data in CSV format
      dwd stations --parameter=kl --resolution=daily --period=recent --format=csv

      # Get daily climate summary data for stations 44 and 1048
      dwd readings --station=44,1048 --parameter=kl --resolution=daily --period=recent

      # Optionally save/restore to/from disk in order to avoid asking upstream servers each time
      dwd readings --station=44,1048 --parameter=kl --resolution=daily --period=recent --persist

      # Limit output to specific date
      dwd readings --station=44,1048 --parameter=kl --resolution=daily --period=recent --date=2020-05-01

      # Limit output to specified date range in ISO-8601 time interval format
      dwd readings --station=44,1048 --parameter=kl --resolution=daily --period=recent --date=2020-05-01/2020-05-05

      # The real power horse: Acquire data across historical+recent data sets
      dwd readings --station=44,1048 --parameter=kl --resolution=daily --period=historical,recent --date=1969-01-01/2020-06-11

      # Acquire monthly data for 2020-05
      dwd readings --station=44,1048 --parameter=kl --resolution=monthly --period=recent,historical --date=2020-05

      # Acquire monthly data from 2017-01 to 2019-12
      dwd readings --station=44,1048 --parameter=kl --resolution=monthly --period=recent,historical --date=2017-01/2019-12

      # Acquire annual data for 2019
      dwd readings --station=44,1048 --parameter=kl --resolution=annual --period=recent,historical --date=2019

      # Acquire annual data from 2010 to 2020
      dwd readings --station=44,1048 --parameter=kl --resolution=annual --period=recent,historical --date=2010/2020

      # Acquire hourly data
      dwd readings --station=44,1048 --parameter=air_temperature --resolution=hourly --period=recent --date=2020-06-15T12

    """

    # Read command line options.
    options = normalize_options(docopt(run.__doc__, version=f'dwd {__version__}'))

    # Setup logging.
    debug = options.get('debug')
    log_level = logging.INFO
    if debug:
        log_level = logging.DEBUG
    setup_logging(log_level)

    if options.about:
        about(options)
        return

    if options.stations:
        df = metadata_for_dwd_data(
            parameter=options.parameter,
            time_resolution=options.resolution,
            period_type=options.period
        )
        if options.persist:
            df.to_csv(f"metadata_{options.parameter}_{options.resolution}_{options.period}.csv")

    elif options.readings:
        request = DWDStationRequest(
            station_ids=read_list(options.station),
            # TODO: Would like to say "climate_summary" instead of "kl" here.
            parameter=options.parameter,
            time_resolution=options.resolution,
            period_type=read_list(options.period),
            write_file=options.persist,
            prefer_local=options.persist,
            humanize_column_names=True,
        )
        data = request.collect_data()
        data = list(data)
        if not data:
            log.error('No data available for given constraints')
            sys.exit(1)
        df = pd.concat(data)

    if options.readings:

        if options.date:

            # Filter by time interval.
            if '/' in options.date:
                date_from, date_to = options.date.split('/')
                date_from = parse_datetime(date_from)
                date_to = parse_datetime(date_to)
                if request.time_resolution in (TimeResolution.ANNUAL, TimeResolution.MONTHLY):
                    date_from, date_to = mktimerange(request.time_resolution, date_from, date_to)
                    expression = (date_from <= df[DWDMetaColumns.FROM_DATE.value]) & \
                                 (df[DWDMetaColumns.TO_DATE.value] <= date_to)
                else:
                    expression = (date_from <= df[DWDMetaColumns.DATE.value]) & \
                                 (df[DWDMetaColumns.DATE.value] <= date_to)
                df = df[expression]

            # Filter by date.
            else:
                date = parse_datetime(options.date)
                if request.time_resolution in (TimeResolution.ANNUAL, TimeResolution.MONTHLY):
                    date_from, date_to = mktimerange(request.time_resolution, date)
                    expression = (date_from <= df[DWDMetaColumns.FROM_DATE.value]) & \
                                 (df[DWDMetaColumns.TO_DATE.value] <= date_to)
                else:
                    expression = (date == df[DWDMetaColumns.DATE.value])
                df = df[expression]

    # Make column names lowercase.
    df = df.rename(columns=str.lower)

    # Output as JSON.
    if options.format == 'json':
        output = df.to_json(orient='records', date_format='iso', indent=4)

    # Output as CSV.
    elif options.format == 'csv':
        output = df.to_csv(index=False, date_format='%Y-%m-%dT%H-%M-%S')

    # Output as XLSX.
    elif options.format == 'excel':
        # TODO: Obtain output file name from command line.
        log.info('Writing "output.xlsx"')
        df.to_excel('output.xlsx', index=False)
        return

    else:
        log.error('Output format must be one of "json", "csv", "excel".')
        sys.exit(1)

    print(output)


def about(options):

    def output(thing):
        for item in thing:
            if item:
                print('-', item.value)

    if options.parameters:
        output(Parameter)

    elif options.resolutions:
        output(TimeResolution)

    elif options.periods:
        output(PeriodType)

    else:
        log.error('Invoke "dwd about" with one of "parameter", "resolution" or "period"')
        sys.exit(1)
