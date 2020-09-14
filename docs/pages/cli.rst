######################
Command line interface
######################
::

    $ wetterdienst --help

        Usage:
          wetterdienst stations --parameter=<parameter> --resolution=<resolution> --period=<period> [--station=] [--latitude=] [--longitude=] [--number=] [--distance=] [--persist] [--format=<format>]
          wetterdienst readings --parameter=<parameter> --resolution=<resolution> --period=<period> --station=<station> [--persist] [--date=<date>] [--format=<format>]
          wetterdienst readings --parameter=<parameter> --resolution=<resolution> --period=<period> --latitude= --longitude= [--number=] [--distance=] [--persist] [--date=<date>] [--format=<format>]
          wetterdienst about [parameters] [resolutions] [periods]
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
