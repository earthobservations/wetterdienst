.. _cli:

.. highlight:: sh

Command Line Interface
**********************

::

    $ wetterdienst --help

    Usage
    =====

        wetterdienst (-h | --help)  Display this page
        wetterdienst --version      Display the version number
        wetterdienst info           Display project information


    Overview
    ========

    This section roughly outlines the different families of command line
    options. More detailed information is available within subsequent sections
    of this page.

    Coverage information:

        wetterdienst about coverage --provider=<provider> --network=<network>
            [--parameter=<parameter>] [--resolution=<resolution>] [--period=<period>]

        wetterdienst about fields --provider=<provider> --network=<network>
            --parameter=<parameter> --resolution=<resolution> --period=<period> [--language=<language>]

    Data acquisition:

        wetterdienst {stations,values}

            # Selection options
            --provider=<provider> --network=<network> --parameter=<parameter> --resolution=<resolution> [--period=<period>]

            # Filtering options
            --all
            --date=<date>
            --station=<station>
            --name=<name>
            --coordinates=<latitude,longitude> --rank=<rank>
            --coordinates=<latitude,longitude> --distance=<distance>
            --bbox=<left,lower,right,top>
            --sql=<sql>

            # Output options
            [--format=<format>] [--pretty]
            [--tidy] [--humanize] [--si-units]
            [--dropna] [--skip_empty] [--skip_threshold=0.95]

            # Export options
            [--target=<target>]


    Options
    =======

    This section explains all command line options in detail.

    Selection options:

        --provider                  The data provider / organisation.
                                    Examples: dwd, eccc, noaa, wsv, ea, eaufrance, nws, geosphere

        --network                   The network of the data provider
                                    Examples: observation, mosmix, radar, ghcn, pegel, hydrology

        --parameter                 Data parameter or parameter set
                                    Examples: kl, precipitation_height

        --resolution                Dataset resolution / product
                                    Examples: annual, monthly, daily, hourly, minute_10, minute_1
                                    For DWD MOSMIX: small, large

        [--period]                  Dataset period
                                    Examples: "historical", "recent", "now"

    Filtering options:

        --all                       Flag to process all data

        --date                      Date for filtering data
                                    A single date(time) or interval in RFC3339/ISO8601 format.
                                    See also:
                                    - https://en.wikipedia.org/wiki/ISO_8601#Combined_date_and_time_representations
                                    - https://en.wikipedia.org/wiki/ISO_8601#Time_intervals

        --name                      Name of station

        --station                   Comma-separated list of station identifiers

        --coordinates               Geolocation point for geospatial filtering
                                    Format: <latitude,longitude>

        --rank                      Rank of nearby stations when filtering by geolocation point
                                    To be used with `--coordinates`.

        --distance                  Maximum distance in km when filtering by geolocation point
                                    To be used with `--coordinates`.

        --bbox                      Bounding box for geospatial filtering
                                    Format: <lon1,lat1,lon2,lat2> aka. <left,bottom,right,top>

        --sql                       SQL filter statement

        --sql-values                SQL filter to apply to values

    Transformation options:
        --tidy                      Tidy DataFrame
        --humanize                  Humanize parameters
        --si-units                  Convert to SI units
        --skip_empty                Skip empty stations according to skip_threshold
        --skip_threshold            Skip threshold for a station to be empty (0 < skip_threshold <= 1) [Default: 0.95]
        --dropna                    Whether to drop nan values from the result

    Output options:
        --format                    Output format. [Default: json]
        --language                  Output language. [Default: en]
        --pretty                    Pretty-print JSON

    Export options:
        --target                    Output target for storing data into different data sinks.

    Other options:
        -h --help                   Show this screen
        --debug                     Enable debug messages
        --listen                    HTTP server listen address.
        --reload                    Run service and dynamically reload changed files


    Examples
    ========

    This section includes example invocations to get you started quickly. Most
    of them can be used verbatim in your terminal. For displaying JSON output
    more conveniently, you may want to pipe the output of Wetterdienst into the
    excellent ``jq`` program, which can also be used for subsequent filtering
    and transforming.

    Acquire observation stations:

        # Get list of all stations for daily climate summary data in JSON format
        wetterdienst stations --provider=dwd --network=observation --parameter=kl --resolution=daily --all

        # Get list of all stations in CSV format
        wetterdienst stations --provider=dwd --network=observation --parameter=kl --resolution=daily --all --format=csv

        # Get list of specific stations
        wetterdienst stations --provider=dwd --network=observation --resolution=daily --parameter=kl --station=1,1048,4411

        # Get list of specific stations in GeoJSON format
        wetterdienst stations --provider=dwd --network=observation --resolution=daily --parameter=kl --station=1,1048,4411 --format=geojson

    Acquire MOSMIX stations:

        wetterdienst stations --provider=dwd --network=mosmix --parameter=large --resolution=large --all
        wetterdienst stations --provider=dwd --network=mosmix --parameter=large --resolution=large --all --format=csv

    Acquire observation data:

        # Get daily climate summary data for specific stations, selected by name and station id
        wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent --name=Dresden-Hosterwitz
        wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent --station=1048,4411

        # Get daily climate summary data for specific stations in CSV format
        wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent --station=1048,4411

        # Get daily climate summary data for specific stations in tidy format
        wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent --station=1048,4411 --tidy

        # Limit output to specific date
        wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent --date=2020-05-01 --station=1048,4411

        # Limit output to specified date range in ISO-8601 time interval format
        wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --date=2020-05-01/2020-05-05 --station=1048

        # The real power horse: Acquire data across historical+recent data sets
        wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --date=1969-01-01/2020-06-11 --station=1048

        # Acquire monthly data for 2020-05
        wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=monthly --date=2020-05 --station=1048

        # Acquire monthly data from 2017-01 to 2019-12
        wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=monthly --date=2017-01/2019-12 --station=1048,4411

        # Acquire annual data for 2019
        wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=annual --date=2019 --station=1048,4411

        # Acquire annual data from 2010 to 2020
        wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=annual --date=2010/2020 --station=1048

        # Acquire hourly data for a given time range
        wetterdienst values --provider=dwd --network=observation --parameter=air_temperature --resolution=hourly \
            --date=2020-06-15T12/2020-06-16T12 --station=1048,4411

        # Acquire data for specific parameter and dataset
        wetterdienst values --provider=dwd --network=observation \
            --parameter=precipitation_height/precipitation_more,temperature_air_200/kl \
            --resolution=hourly --date=2020-06-15T12/2020-06-16T12 --station=1048,4411

    Acquire MOSMIX data:

        wetterdienst values --provider=dwd --network=mosmix --parameter=ttt,ff --resolution=large --station=65510

    Geospatial filtering:

        # Acquire stations and readings by geolocation, request specific number of nearby stations.
        wetterdienst stations --provider=dwd --network=observation --resolution=daily --parameter=kl --period=recent \
            --coordinates=49.9195,8.9671 --rank=5

        wetterdienst values --provider=dwd --network=observation --resolution=daily --parameter=kl --period=recent \
            --coordinates=49.9195,8.9671 --rank=5 --date=2020-06-30

        # Acquire stations and readings by geolocation, request stations within specific distance.
        wetterdienst stations --provider=dwd --network=observation --resolution=daily --parameter=kl --period=recent \
            --coordinates=49.9195,8.9671 --distance=25

        wetterdienst values --provider=dwd --network=observation --resolution=daily --parameter=kl --period=recent \
            --coordinates=49.9195,8.9671 --distance=25 --date=2020-06-30

    SQL filtering:

        # Find stations by state.
        wetterdienst stations --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent \
            --sql="SELECT * FROM data WHERE state='Sachsen'"

        # Find stations by name (LIKE query).
        wetterdienst stations --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent \
            --sql="SELECT * FROM data WHERE lower(name) LIKE lower('%dresden%')"

        # Find stations by name (regexp query).
        wetterdienst stations --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent \
            --sql="SELECT * FROM data WHERE regexp_matches(lower(name), lower('.*dresden.*'))"

        # Filter values: Display daily climate observation readings where the maximum temperature is below two degrees celsius.
        wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent \
            --station=1048,4411 --sql-values="SELECT * FROM data WHERE wind_gust_max > 20.0;"

        # Filter measurements: Same as above, but use tidy format.
        wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent \
            --station=1048,4411 \
            --tidy --sql-values="SELECT * FROM data WHERE parameter='wind_gust_max' AND value > 20.0;"

    Inquire metadata:

        # Display coverage/correlation between parameters, resolutions and periods.
        # This can answer questions like ...
        wetterdienst about coverage --provider=dwd --network=observation

        # Tell me all periods and resolutions available for given dataset labels.
        wetterdienst about coverage --provider=dwd --network=observation --dataset=climate_summary
        wetterdienst about coverage --provider=dwd --network=observation --dataset=temperature_air

        # Tell me all parameters available for given resolutions.
        wetterdienst about coverage --provider=dwd --network=observation --resolution=daily
        wetterdienst about coverage --provider=dwd --network=observation --resolution=hourly

    Export data to files:

        # Export list of stations into spreadsheet
        wetterdienst stations \
            --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent \
            --all --target=file://stations_result.xlsx

        # Shortcut command for fetching readings.
        # It will be used for the next invocations.
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

    Export data to databases:

        # Shortcut command for fetching readings.
        # It will be used for the next invocations.
        alias fetch="wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent --station=1048,4411"

        # Store readings to DuckDB
        fetch --target="duckdb:///observations.duckdb?table=weather"

        # Store readings to InfluxDB
        fetch --target="influxdb://localhost/?database=observations&table=weather"

        # Store readings to CrateDB
        fetch --target="crate://localhost/?database=observations&table=weather"

    The HTTP REST API service:

        # Start service on standard port, listening on http://localhost:7890.
        wetterdienst restapi

        # Start service on standard port and watch filesystem changes.
        # This is suitable for development.
        wetterdienst restapi --reload

        # Start service on public interface and specific port.
        wetterdienst restapi --listen=0.0.0.0:8890

    The Wetterdienst Explorer UI service:

        # Start service on standard port, listening on http://localhost:7891.
        wetterdienst explorer

        # Start service on standard port and watch filesystem changes.
        # This is suitable for development.
        wetterdienst explorer --reload

        # Start service on public interface and specific port.
        wetterdienst explorer --listen=0.0.0.0:8891

    Explore OPERA radar stations:

        # Display all radar stations.
        wetterdienst radar --all

        # Display radar stations filtered by country.
        wetterdienst radar --country-name=france

        # Display OPERA radar stations operated by DWD.
        wetterdienst radar --dwd

        # Display radar station with specific ODIM- or WMO-code.
        wetterdienst radar --odim-code=deasb
        wetterdienst radar --wmo-code=10103

