.. _cli:

Command Line Interface
**********************

::

    $ wetterdienst --help

    Usage:

        wetterdienst (-h | --help)
        wetterdienst version
        wetterdienst info

        wetterdienst radar [--dwd=<dwd>] [--all=<all>] [--odim-code=<odim-code>] [--wmo-code=<wmo-code>] [--country-name=<country-name>]

        wetterdienst about coverage --provider=<provider> --network=<network> [--parameter=<parameter>] [--resolution=<resolution>] [--period=<period>]
        wetterdienst about fields --provider=dwd --network=observation --parameter=<parameter> --resolution=<resolution> --period=<period> [--language=<language>]

        wetterdienst stations --provider=<provider> --network=<network> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --all=<all> [--target=<target>] [--format=<format>] [--pretty=<pretty>] [--debug=<debug>]
        wetterdienst stations --provider=<provider> --network=<network> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --station=<station> [--target=<target>] [--format=<format>] [--pretty=<pretty>] [--debug=<debug>]
        wetterdienst stations --provider=<provider> --network=<network> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --name=<name> [--target=<target>] [--format=<format>] [--pretty=<pretty>] [--debug=<debug>]
        wetterdienst stations --provider=<provider> --network=<network> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --coordinates=<latitude,longitude> --rank=<rank> [--sql=<sql>] [--target=<target>] [--format=<format>] [--pretty=<pretty>] [--debug=<debug>]
        wetterdienst stations --provider=<provider> --network=<network> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --coordinates=<latitude,longitude> --distance=<distance> [--target=<target>] [--format=<format>] [--pretty=<pretty>] [--debug=<debug>]
        wetterdienst stations --provider=<provider> --network=<network> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --bbox=<left,lower,right,top> [--target=<target>] [--format=<format>] [--pretty=<pretty>] [--debug=<debug>]
        wetterdienst stations --provider=<provider> --network=<network> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --sql=<sql> [--target=<target>] [--format=<format>] [--pretty=<pretty>] [--debug=<debug>]

        wetterdienst values --provider=<provider> --network=<network> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --all=<all> [--target=<target>] [--format=<format>] [--tidy=<tidy>] [--si-units=<si-units>] [--pretty=<pretty>] [--debug=<debug>]
        wetterdienst values --provider=<provider> --network=<network> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --station=<station> [--target=<target>] [--format=<format>] [--tidy=<tidy>] [--si-units=<si-units>] [--pretty=<pretty>] [--debug=<debug>]
        wetterdienst values --provider=<provider> --network=<network> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --name=<name> [--target=<target>] [--format=<format>] [--tidy=<tidy>] [--si-units=<si-units>] [--pretty=<pretty>] [--debug=<debug>]
        wetterdienst values --provider=<provider> --network=<network> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --coordinates=<latitude,longitude> --rank=<rank>  [--sql=<sql>] [--target=<target>] [--format=<format>] [--tidy=<tidy>] [--si-units=<si-units>] [--pretty=<pretty>] [--debug=<debug>]
        wetterdienst values --provider=<provider> --network=<network> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --coordinates=<latitude,longitude> --distance=<distance> [--target=<target>] [--format=<format>] [--tidy=<tidy>] [--si-units=<si-units>] [--pretty=<pretty>] [--debug=<debug>]
        wetterdienst values --provider=<provider> --network=<network> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --bbox=<left,lower,right,top> [--target=<target>] [--format=<format>] [--tidy=<tidy>] [--si-units=<si-units>] [--pretty=<pretty>] [--debug=<debug>]
        wetterdienst values --provider=<provider> --network=<network> --parameter=<parameter> --resolution=<resolution> [--period=<period>] --sql=<sql> [--target=<target>] [--format=<format>] [--tidy=<tidy>] [--si-units=<si-units>] [--pretty=<pretty>] [--debug=<debug>]

    Options:
        --parameter=<parameter>               Parameter Set/Parameter, e.g. "kl" or "precipitation_height", etc.
        --resolution=<resolution>             Dataset resolution: "annual", "monthly", "daily", "hourly", "minute_10", "minute_1", for DWD Mosmix: type of mosmix, either 'small' or 'large'
        --period=<period>                     Dataset period: "historical", "recent", "now"
        --all=<all>                           Bool for all stations
        --station=<station>                   Comma-separated list of station identifiers
        --name=<name>                         Name of queried station
        --coordinates=<latitude,longitude>    Latitude-longitude pair for filtering by geoposition.
        --rank=<rank>                         Rank of nearby stations when filtering by geoposition.
        --distance=<distance>                 Maximum distance in km when filtering by geoposition.
        --bbox=<left,bottom,right,top>        Quadruple of left, bottom, right and top corners of bbox
        --sql=<sql>                           SQL filter to apply for stations
        --date=<date>                         Date for filtering data. Can be either a single date(time) or
                                              an ISO-8601 time interval, see https://en.wikipedia.org/wiki/ISO_8601#Time_intervals.
        --sql-values=<sql-values>             SQL query to apply to values
        --target=<target>                     Output target for storing data into different data sinks.
        --format=<format>                     Output format. [Default: json]
        --language=<language>                 Output language. [Default: en]
        --tidy                                Tidy DataFrame
        --humanize                            Humanize parameters
        --si-units                            Convert to SI units
        --pretty                              Pretty json with indent 4
        --debug                               Enable debug messages
        --listen=<listen>                     HTTP server listen address.
        --reload                              Run service and dynamically reload changed files
        -h --help                             Show this screen

    Examples requesting observation stations:

        # Get list of all stations for daily climate summary data in JSON format
        wetterdienst stations --provider=dwd --network=observation --parameter=kl --resolution=daily

        # Get list of all stations in CSV format
        wetterdienst stations --provider=dwd --network=observation --parameter=kl --resolution=daily --format=csv

        # Get list of specific stations
        wetterdienst stations --provider=dwd --network=observation --resolution=daily --parameter=kl --station=1,1048,4411

        # Get list of specific stations in GeoJSON format
        wetterdienst stations --provider=dwd --network=observation --resolution=daily --parameter=kl --station=1,1048,4411 --format=geojson

    Examples requesting forecast stations:

        wetterdienst stations --provider=dwd --network=mosmix --parameter=large --resolution=large

    Examples requesting observation values:

        # Get daily climate summary data for specific stations
        wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent --station=1048,4411

        # Get daily climate summary data for specific stations in CSV format
        wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent --station=1048,4411

        # Get daily climate summary data for specific stations in tidy format
        wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent --station=1048,4411 --tidy

        # Limit output to specific date
        wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent --date=2020-05-01 --station=1048,4411

        # Limit output to specified date range in ISO-8601 time interval format
        wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent --date=2020-05-01/2020-05-05

        # The real power horse: Acquire data across historical+recent data sets
        wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --date=1969-01-01/2020-06-11

        # Acquire monthly data for 2020-05
        wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=monthly --date=2020-05

        # Acquire monthly data from 2017-01 to 2019-12
        wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=monthly --date=2017-01/2019-12 --station=1048,4411

        # Acquire annual data for 2019
        wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=annual --date=2019 --station=1048,4411

        # Acquire annual data from 2010 to 2020
        wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=annual --date=2010/2020

        # Acquire hourly data
        wetterdienst values --provider=dwd --network=observation --parameter=air_temperature --resolution=hourly --period=recent --date=2020-06-15T12 --station=1048,4411

    Examples requesting forecast values:

        wetterdienst values --provider=dwd --network=mosmix --parameter=ttt,ff --resolution=large --station=65510

    Examples using geospatial features:

        # Acquire stations and readings by geoposition, request specific number of nearby stations.
        wetterdienst stations --provider=dwd --network=observation --resolution=daily --parameter=kl --period=recent --coordinates=49.9195,8.9671 --rank=5
        wetterdienst values --provider=dwd --network=observation --resolution=daily --parameter=kl --period=recent --date=2020-06-30 --coordinates=49.9195,8.9671 --rank=5

        # Acquire stations and readings by geoposition, request stations within specific distance.
        wetterdienst stations --provider=dwd --network=observation --resolution=daily --parameter=kl --period=recent --coordinates=49.9195,8.9671 --distance=25
        wetterdienst values --provider=dwd --network=observation --resolution=daily --parameter=kl --period=recent --date=2020-06-30 --coordinates=49.9195,8.9671 --distance=25

    Examples using SQL filtering:

        # Find stations by state.
        wetterdienst stations --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent --sql="SELECT * FROM data WHERE state='Sachsen'"

        # Find stations by name (LIKE query).
        wetterdienst stations --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent --sql="SELECT * FROM data WHERE lower(station_name) LIKE lower('%dresden%')"

        # Find stations by name (regexp query).
        wetterdienst stations --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent --sql="SELECT * FROM data WHERE regexp_matches(lower(station_name), lower('.*dresden.*'))"

        # Filter values: Display daily climate observation readings where the maximum temperature is below two degrees celsius.
        wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent --station=1048,4411 --sql-values="SELECT * FROM data WHERE temperature_air_max_200 < 2.0;"

        # Filter measurements: Same as above, but use tidy format.
        # FIXME: Currently, this does not work, see https://github.com/earthobservations/wetterdienst/issues/377.
        wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent --station=1048,4411 --sql-values="SELECT * FROM data WHERE parameter='temperature_air_max_200' AND value < 2.0;" --tidy

    Examples for inquiring metadata:

        # Display coverage/correlation between parameters, resolutions and periods.
        # This can answer questions like ...
        wetterdienst about coverage --provider=dwd --network=observation

        # Tell me all periods and resolutions available for 'air_temperature'.
        wetterdienst about coverage --provider=dwd --network=observation --parameter=air_temperature

        # Tell me all parameters available for 'daily' resolution.
        wetterdienst about coverage --provider=dwd --network=observation --resolution=daily

    Examples for exporting data to files:

        # Export list of stations into spreadsheet
        wetterdienst stations --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent --target=file://stations.xlsx

        # Shortcut command for fetching readings
        alias fetch="wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent --station=1048,4411"

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
        alias fetch="wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent --station=1048,4411"

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

