.. _cli:

Command Line Interface
**********************

::

    $ wetterdienst --help

    Usage:
      wetterdienst dwd observation stations --parameter=<parameter> --resolution=<resolution> --period=<period> [--station=<station>] [--latitude=<latitude>] [--longitude=<longitude>] [--number=<number>] [--distance=<distance>] [--sql=<sql>] [--format=<format>] [--target=<target>]
      wetterdienst dwd observation values --parameter=<parameter> --resolution=<resolution> [--station=<station>] [--period=<period>] [--date=<date>] [--tidy] [--sql=<sql>] [--format=<format>] [--target=<target>]
      wetterdienst dwd observation values --parameter=<parameter> --resolution=<resolution> --latitude=<latitude> --longitude=<longitude> [--period=<period>] [--number=<number>] [--distance=<distance>] [--tidy] [--date=<date>] [--sql=<sql>] [--format=<format>] [--target=<target>]
      wetterdienst dwd forecast stations [--parameter=<parameter>] [--mosmix-type=<mosmix-type>] [--date=<date>] [--station=<station>] [--latitude=<latitude>] [--longitude=<longitude>] [--number=<number>] [--distance=<distance>] [--sql=<sql>] [--format=<format>] [--target=<target>]
      wetterdienst dwd forecast values --parameter=<parameter> [--mosmix-type=<mosmix-type>] --station=<station> [--date=<date>] [--tidy] [--sql=<sql>] [--format=<format>] [--target=<target>]
      wetterdienst dwd about [parameters] [resolutions] [periods]
      wetterdienst dwd about coverage [--parameter=<parameter>] [--resolution=<resolution>] [--period=<period>]
      wetterdienst dwd about fields --parameter=<parameter> --resolution=<resolution> --period=<period> [--language=<language>]
      wetterdienst radar stations [--odim-code=<odim-code>] [--wmo-code=<wmo-code>] [--country-name=<country-name>]
      wetterdienst dwd radar stations
      wetterdienst restapi [--listen=<listen>] [--reload]
      wetterdienst explorer [--listen=<listen>] [--reload]
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
      --listen=<listen>             HTTP server listen address.
      --reload                      Run service and dynamically reload changed files
      -h --help                     Show this screen


    Examples requesting observation stations:

      # Get list of all stations for daily climate summary data in JSON format
      wetterdienst dwd observation stations --parameter=kl --resolution=daily --period=recent

      # Get list of all stations in CSV format
      wetterdienst dwd observation stations --parameter=kl --resolution=daily --period=recent --format=csv

      # Get list of specific stations
      wetterdienst dwd observation stations --resolution=daily --parameter=kl --period=recent --station=1,1048,4411

      # Get list of specific stations in GeoJSON format
      wetterdienst dwd observation stations --resolution=daily --parameter=kl --period=recent --station=1,1048,4411 --format=geojson

    Examples requesting observation values:

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

    Examples requesting forecast stations:

      wetterdienst dwd forecast stations

    Examples requesting forecast values:

      wetterdienst dwd forecast values --parameter=ttt,ff --station=65510

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

      # Check Parquet file
      parquet-tools schema observations.parquet
      parquet-tools head observations.parquet

      # Export readings into Zarr format
      fetch --target="file://observations.zarr"

    Examples for exporting data to databases:

      # Shortcut command for fetching readings
      alias fetch="wetterdienst dwd observation values --station=1048,4411 --parameter=kl --resolution=daily --period=recent"

      # Store readings to DuckDB
      fetch --target="duckdb:///dwd.duckdb?table=weather"

      # Store readings to InfluxDB
      fetch --target="influxdb://localhost/?database=dwd&table=weather"

      # Store readings to CrateDB
      fetch --target="crate://localhost/?database=dwd&table=weather"

    Invoke the HTTP REST API service:

      # Start service on standard port, listening on http://localhost:7890.
      wetterdienst restapi

      # Start service on standard port and watch filesystem changes.
      # This is suitable for development.
      wetterdienst restapi --reload

      # Start service on public interface and specific port.
      wetterdienst restapi --listen=0.0.0.0:8890

    Invoke the Wetterdienst Explorer UI service:

      # Start service on standard port, listening on http://localhost:7891.
      wetterdienst explorer

      # Start service on standard port and watch filesystem changes.
      # This is suitable for development.
      wetterdienst explorer --reload

      # Start service on public interface and specific port.
      wetterdienst explorer --listen=0.0.0.0:8891
