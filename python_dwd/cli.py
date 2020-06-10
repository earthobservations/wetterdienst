# -*- coding: utf-8 -*-
import sys
import logging
from docopt import docopt
from dateparser import parse as parsedate

from python_dwd import collect_dwd_data, __version__, metadata_for_dwd_data
from python_dwd.additionals.util import normalize_options, setup_logging, read_list
from python_dwd.enumerations.parameter_enumeration import Parameter
from python_dwd.enumerations.period_type_enumeration import PeriodType
from python_dwd.enumerations.time_resolution_enumeration import TimeResolution
from python_dwd.exceptions import NoDataError, InvalidStationIdentifier

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
            period_type=options.period,
            write_file=options.persist,
        )

    elif options.readings:
        # TODO: Use "DWDStationRequest.collect_data" instead of "collect_dwd_data" here.
        # See also:
        # - https://github.com/gutzbenj/python_dwd/issues/8
        # - https://github.com/gutzbenj/python_dwd/blob/b5dc0c9b/python_dwd/dwd_station_request.py
        try:
            """
            station_data = collect_dwd_data(
                station_ids=[1048],
                parameter=Parameter.CLIMATE_SUMMARY,
                time_resolution=TimeResolution.DAILY,
                period_type=PeriodType.HISTORICAL,
            )
            """
            df = collect_dwd_data(
                station_ids=read_list(options.station),
                # TODO: Would like to say "climate_summary" instead of "kl" here.
                parameter=options.parameter,
                time_resolution=options.resolution,
                period_type=options.period,
                write_file=options.persist,
                prefer_local=options.persist,
            )
        except (NoDataError, InvalidStationIdentifier) as ex:
            log.error(ex)
            sys.exit(1)

    if options.readings:
        # Filter by station.
        #print(df[df['STATION_ID'] == 1048])

        if options.date:

            # Filter by time interval.
            if '/' in options.date:
                date_from, date_to = options.date.split('/')
                date_from = parsedate(date_from)
                date_to = parsedate(date_to)
                df = df[(date_from <= df['DATE']) & (df['DATE'] <= date_to)]

            # Filter by date.
            else:
                date = parsedate(options.date)
                df = df[date == df['DATE']]

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
