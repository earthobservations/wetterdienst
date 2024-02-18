# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
from __future__ import annotations

import functools
import json
import logging
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path
from pprint import pformat
from typing import Literal

import click
import cloup
from click_params import StringListParamType
from cloup import Section
from cloup.constraints import If, RequireExactly, accept_none
from PIL import Image

from wetterdienst import Provider, Wetterdienst, __appname__, __version__
from wetterdienst.exceptions import ProviderNotFoundError
from wetterdienst.ui.core import (
    _get_stripes_stations,
    _plot_stripes,
    get_interpolate,
    get_stations,
    get_summarize,
    get_values,
    set_logging_level,
)
from wetterdienst.util.cli import docstring_format_verbatim, setup_logging

log = logging.getLogger(__name__)

comma_separated_list = StringListParamType(",")

appname = f"{__appname__} {__version__}"

provider_opt = cloup.option_group(
    "Provider",
    click.option(
        "--provider",
        type=click.Choice([provider.name for provider in Provider], case_sensitive=False),
        required=True,
    ),
)

network_opt = cloup.option_group(
    "Network",
    click.option(
        "--network",
        type=click.STRING,
        required=True,
    ),
)

debug_opt = click.option("--debug", is_flag=True)

# Sections for click help
basic_section = Section("Basic")
data_section = Section("Data")
advanced_section = Section("Advanced")


def get_api(provider: str, network: str):
    """
    Function to get API for provider and network, if non found click.Abort()
    is casted with the error message

    :param provider:
    :param network:
    :return:
    """
    try:
        return Wetterdienst(provider, network)
    except ProviderNotFoundError as e:
        log.error(str(e))
        sys.exit(1)


def station_options_core(command):
    """
    Station options core for cli, which can be used for stations and values endpoint

    :param command:
    :return:
    """
    arguments = [
        cloup.option("--parameter", type=comma_separated_list, required=True),
        cloup.option("--resolution", type=click.STRING, required=True),
        cloup.option("--period", type=comma_separated_list),
    ]
    return functools.reduce(lambda x, opt: opt(x), reversed(arguments), command)


def station_options_extension(command):
    """
    Station options extension for cli, which can be used for stations and values endpoint

    :param command:
    :return:
    """
    arguments = [
        cloup.option_group("All stations", click.option("--all", "all_", is_flag=True)),
        cloup.option_group(
            "Station id filtering",
            cloup.option("--station", type=comma_separated_list),
        ),
        cloup.option_group(
            "Station name filtering",
            cloup.option("--name", type=click.STRING),
        ),
        cloup.option_group(
            "Latitude-Longitude rank/distance filtering",
            cloup.option("--coordinates", metavar="LATITUDE,LONGITUDE", type=click.STRING),
            cloup.option("--rank", type=click.INT),
            cloup.option("--distance", type=click.FLOAT),
            help="Provide --coordinates plus either --rank or --distance.",
        ),
        cloup.constraint(
            If("coordinates", then=RequireExactly(1), else_=accept_none),
            ["rank", "distance"],
        ),
        cloup.option_group(
            "BBOX filtering",
            cloup.option("--bbox", metavar="LEFT BOTTOM RIGHT TOP", type=click.STRING),
        ),
        cloup.option_group(
            "SQL filtering",
            click.option("--sql", type=click.STRING),
        ),
        cloup.constraint(
            RequireExactly(1),
            ["all_", "station", "name", "coordinates", "bbox", "sql"],
        ),
    ]
    return functools.reduce(lambda x, opt: opt(x), reversed(arguments), command)


def station_options_interpolate_summarize(command):
    """
    Station options for interpolate/summarize for cli, which can be used for stations and values endpoint

    :param command:
    :return:
    """
    arguments = [
        cloup.option_group(
            "Station id filtering",
            cloup.option("--station", type=comma_separated_list),
        ),
        cloup.option_group(
            "Latitude-Longitude rank/distance filtering",
            cloup.option("--coordinates", metavar="LATITUDE,LONGITUDE", type=click.STRING),
        ),
        cloup.constraint(
            RequireExactly(1),
            ["station", "coordinates"],
        ),
    ]
    return functools.reduce(lambda x, opt: opt(x), reversed(arguments), command)


# def wetterdienst_help():
wetterdienst_help = """
Usage
=====

    wetterdienst (-h | --help)  Display this page
    wetterdienst --version      Display the version number
    wetterdienst cache          Display cache location
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
        [--shape=<shape>] [--humanize] [--si-units]
        [--dropna] [--skip_empty] [--skip_threshold=0.95]

        # Export options
        [--target=<target>]

Data computation:

    wetterdienst {interpolate,summarize}

        # Selection options
        --provider=<provider> --network=<network> --parameter=<parameter> --resolution=<resolution> --date=<date> [--period=<period>]

        # Filtering options
        --station=<station>
        --coordinates=<latitude,longitude>

        # Output options
        [--format=<format>] [--pretty]
        [--shape=<shape>] [--humanize] [--si-units]
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
    --shape                     Shape of DataFrame, "wide" or "long"
    --humanize                  Humanize parameters
    --si-units                  Convert to SI units
    --skip_empty                Skip empty stations according to ts_skip_threshold
    --skip_threshold            Skip threshold for a station to be empty (0 < ts_skip_threshold <= 1) [Default: 0.95]
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
    wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent \\
        --name=Dresden-Hosterwitz
    wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent \\
        --station=1048,4411

    # Get daily climate summary data for specific stations in CSV format
    wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent \\
        --station=1048,4411

    # Get daily climate summary data for specific stations in long format
    wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent \\
        --station=1048,4411 --shape="long"

    # Limit output to specific date
    wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --date=2020-05-01 \\
        --station=1048,4411

    # Limit output to specified date range in ISO-8601 time interval format
    wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily \\
        --date=2020-05-01/2020-05-05 --station=1048

    # The real power horse: Acquire data across historical+recent data sets
    wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily \\
        --date=1969-01-01/2020-06-11 --station=1048

    # Acquire single data point for month 2020-05
    wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=monthly --tidy \\
        --date=2020-05 --station=1048

    # Acquire monthly data from 2017 to 2019
    wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=monthly --tidy \\
        --date=2017/2019 --station=1048,4411

    # Acquire annual data for 2019
    wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=annual --tidy \\
        --date=2019 --station=1048,4411

    # Acquire annual data from 2010 to 2020
    wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=annual --tidy \\
        --date=2010/2020 --station=1048

    # Acquire hourly data for a given time range
    wetterdienst values --provider=dwd --network=observation --parameter=air_temperature --resolution=hourly \\
        --date=2020-06-15T12/2020-06-16T12 --station=1048,4411

    # Acquire data for multiple given parameters
    wetterdienst values --provider=dwd --network=observation \\
        --parameter=precipitation_height/precipitation_more,temperature_air_mean_2m/air_temperature \\
        --resolution=hourly --date=2020-06-15T12/2020-06-16T12 --station=1048,4411

Acquire MOSMIX data:

    wetterdienst values --provider=dwd --network=mosmix --parameter=ttt,ff --resolution=large --station=65510

Acquire DMO data:

    wetterdienst values --provider=dwd --network=dmo --parameter=ttt --resolution=icon_eu --station=65510

    # short lead time
    wetterdienst values --provider=dwd --network=dmo --parameter=ttt --resolution=icon --station=65510 --lead-time=short

    # long lead time
    wetterdienst values --provider=dwd --network=dmo --parameter=ttt --resolution=icon --station=65510 --lead-time=long

Compute data:

    # Compute daily interpolation of precipitation for specific station selected by id
    wetterdienst interpolate --provider=dwd --network=observation --parameter=precipitation_height --resolution=daily \\
        --date=2020-06-30 --station=01048

    # Compute daily interpolation of precipitation for specific station selected by coordinates
    wetterdienst interpolate --provider=dwd --network=observation --parameter=precipitation_height --resolution=daily \\
        --date=2020-06-30 --coordinates=49.9195,8.9671

    # Compute daily summary of precipitation for specific station selected by id
    wetterdienst summarize --provider=dwd --network=observation --parameter=precipitation_height --resolution=daily \\
        --date=2020-06-30 --station=01048

    # Compute daily summary data of precipitation for specific station selected by coordinates
    wetterdienst summarize --provider=dwd --network=observation --parameter=precipitation_height --resolution=daily \\
        --date=2020-06-30 --coordinates=49.9195,8.9671

Geospatial filtering:

    # Acquire stations and readings by geolocation, request specific number of nearby stations.
    wetterdienst stations --provider=dwd --network=observation --resolution=daily --parameter=kl --period=recent \\
        --coordinates=49.9195,8.9671 --rank=5

    wetterdienst values --provider=dwd --network=observation --resolution=daily --parameter=kl --period=recent \\
        --coordinates=49.9195,8.9671 --rank=5 --date=2020-06-30

    # Acquire stations and readings by geolocation, request stations within specific distance.
    wetterdienst stations --provider=dwd --network=observation --resolution=daily --parameter=kl --period=recent \\
        --coordinates=49.9195,8.9671 --distance=25

    wetterdienst values --provider=dwd --network=observation --resolution=daily --parameter=kl --period=recent \\
        --coordinates=49.9195,8.9671 --distance=25 --date=2020-06-30

SQL filtering:

    # Find stations by state.
    wetterdienst stations --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent \\
        --sql="SELECT * FROM data WHERE state='Sachsen'"

    # Find stations by name (LIKE query).
    wetterdienst stations --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent \\
        --sql="SELECT * FROM data WHERE lower(name) LIKE lower('%dresden%')"

    # Find stations by name (regexp query).
    wetterdienst stations --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent \\
        --sql="SELECT * FROM data WHERE regexp_matches(lower(name), lower('.*dresden.*'))"

    # Filter values: Display daily climate observation readings where the maximum temperature is below two degrees celsius.
    wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent \\
        --station=1048,4411 --sql-values="SELECT * FROM data WHERE wind_gust_max > 20.0;"

    # Filter measurements: Same as above, but use long format.
    wetterdienst values --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent \\
        --station=1048,4411 --shape="long" \\
        --sql-values="SELECT * FROM data WHERE parameter='wind_gust_max' AND value > 20.0"

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
    wetterdienst stations --provider=dwd --network=observation --parameter=kl --resolution=daily --period=recent \\
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

Create warming stripes (only DWD Observation data):

    # Create warming stripes for a specific station
    wetterdienst warming_stripes --station=1048 > warming_stripes.png

    # Create warming stripes for a specific station with approximate name
    wetterdienst warming_stripes --name=Dresden-Klotzsche  --name_treshold=70 > warming_stripes.png

    # Create warming stripes for a specific station for years 2000 to 2020
    wetterdienst warming_stripes --station=1048 --start_year=2000 --end_year=2020 > warming_stripes.png

    # Create warming stripes for a specific station and write to file
    wetterdienst warming_stripes --station=1048 --target=warming_stripes.png
"""  # noqa: E501


@cloup.group(
    "wetterdienst",
    help=docstring_format_verbatim(wetterdienst_help),
    context_settings={"max_content_width": 120},
)
@click.version_option(__version__, "-v", "--version", message="%(version)s")
def cli():
    setup_logging()


@cli.command("cache", section=basic_section)
def cache():
    from wetterdienst import Settings

    print(Settings().cache_dir)  # noqa: T201
    return


@cli.command("info", section=basic_section)
def info():
    from wetterdienst import Info

    print(Info())  # noqa: T201
    return


@cli.command("restapi", section=advanced_section)
@cloup.option("--listen", type=click.STRING, default=None, help="HTTP server listen address")
@cloup.option("--reload", is_flag=True, help="Dynamically reload changed files")
@debug_opt
def restapi(listen: str, reload: bool, debug: bool):
    set_logging_level(debug)

    # Run HTTP service.
    log.info(f"Starting {appname}")
    log.info(f"Starting HTTP web service on http://{listen}")

    from wetterdienst.ui.restapi import start_service

    start_service(listen, reload=reload)

    return


@cli.command("explorer", section=advanced_section)
@cloup.option("--listen", type=click.STRING, default=None, help="HTTP server listen address")
@debug_opt
def explorer(listen: str, debug: bool):
    set_logging_level(debug)

    try:
        from wetterdienst.ui.streamlit.explorer import app
    except ImportError:
        log.error("Please install the explorer extras with 'pip install wetterdienst[explorer]'")
        sys.exit(1)

    address = "localhost"
    port = "8501"
    if listen:
        try:
            address, port = listen.split(":")
        except ValueError:
            log.error(
                f"Invalid listen address. Please provide address and port separated by a colon e.g. '{address}:{port}'."
            )
            sys.exit(1)

    log.info(f"Starting {appname}")
    log.info(f"Starting Explorer web service on http://{address}:{port}")

    process = None
    try:
        process = subprocess.Popen(  # noqa: S603
            ["streamlit", "run", app.__file__, "--server.address", address, "--server.port", port]  # noqa: S603, S607
        )  # noqa: S603
        process.wait()
    except KeyboardInterrupt:
        log.info("Stopping Explorer web service")
    except Exception as e:
        log.error(f"An error occurred: {str(e)}")
    finally:
        if process is not None:
            process.terminate()


@cli.group(section=data_section)
def about():
    pass


@about.command()
@cloup.option_group(
    "Provider",
    click.option(
        "--provider",
        type=click.Choice([provider.name for provider in Provider], case_sensitive=False),
    ),
)
@cloup.option_group(
    "Network",
    click.option(
        "--network",
        type=click.STRING,
    ),
)
@cloup.option("--dataset", type=comma_separated_list, default=None)
@cloup.option("--resolution", type=click.STRING, default=None)
@debug_opt
def coverage(provider, network, dataset, resolution, debug):
    set_logging_level(debug)

    if not provider or not network:
        print(json.dumps(Wetterdienst.discover(), indent=2))  # noqa: T201
        return

    api = get_api(provider=provider, network=network)

    cov = api.discover(
        dataset=dataset,
        resolution=resolution,
        flatten=False,
        with_units=False,
    )

    # Compute more compact representation.
    result = OrderedDict()
    for resolution, labels in cov.items():
        result[resolution] = list(labels.keys())

    print(json.dumps(result, indent=2))  # noqa: T201


@about.command("fields")
@provider_opt
@network_opt
@cloup.option_group(
    "(DWD only) information from PDF documents",
    click.option("--dataset", type=comma_separated_list),
    click.option("--resolution", type=click.STRING),
    click.option("--period", type=comma_separated_list),
    click.option("--language", type=click.Choice(["en", "de"], case_sensitive=False), default="en"),
    constraint=cloup.constraints.require_all,
)
@debug_opt
def fields(provider, network, dataset, resolution, period, language, **kwargs):
    api = get_api(provider, network)

    if not (api.provider == Provider.DWD and network.lower() == "observation") and kwargs.get("fields"):
        raise click.BadParameter("'fields' command only available for provider 'DWD'")

    metadata = api.describe_fields(
        dataset=dataset,
        resolution=resolution,
        period=period,
        language=language,
    )

    output = pformat(dict(metadata))

    print(output)  # noqa: T201

    return


@cli.command("stations", section=data_section)
@provider_opt
@network_opt
@station_options_core
@station_options_extension
@cloup.option_group(
    "Format/Target",
    click.option(
        "--format",
        "fmt",
        type=click.Choice(["json", "geojson", "csv"], case_sensitive=False),
        default="json",
    ),
    cloup.option("--target", type=click.STRING),
)
@cloup.constraint(
    If("coordinates", then=RequireExactly(1), else_=accept_none),
    ["rank", "distance"],
)
@cloup.option("--pretty", type=click.BOOL, default=False)
@cloup.option("--with-metadata", type=click.BOOL, default=False)
@debug_opt
def stations(
    provider: str,
    network: str,
    parameter: list[str],
    resolution: str,
    period: list[str],
    all_: bool,
    station: list[str],
    name: str,
    coordinates: str,
    rank: int,
    distance: float,
    bbox: str,
    sql: str,
    fmt: str,
    target: str,
    pretty: bool,
    with_metadata: bool,
    debug: bool,
):
    set_logging_level(debug)

    api = get_api(provider=provider, network=network)

    stations_ = get_stations(
        api=api,
        parameter=parameter,
        resolution=resolution,
        period=period,
        lead_time="short",
        date=None,
        issue=None,
        all_=all_,
        station_id=station,
        name=name,
        coordinates=coordinates,
        rank=rank,
        distance=distance,
        bbox=bbox,
        sql=sql,
        shape="long",
        si_units=False,
        humanize=False,
        skip_empty=False,
        skip_criteria="min",
        skip_threshold=0.95,
        dropna=False,
    )

    if stations_.df.is_empty():
        log.error("No stations available for given constraints")
        sys.exit(1)

    if target:
        stations_.to_target(target)
        return

    output = stations_.to_format(fmt, indent=pretty, with_metadata=with_metadata)

    print(output)  # noqa: T201

    return


@cli.command("values", section=data_section)
@provider_opt
@network_opt
@station_options_core
@cloup.option("--lead-time", type=click.Choice(["short", "long"]), default="short", help="used only for DWD DMO")
@station_options_extension
@cloup.option("--date", type=click.STRING)
@cloup.option("--sql-values", type=click.STRING)
@cloup.option_group(
    "Format/Target",
    cloup.option(
        "--format",
        "fmt",
        type=click.Choice(["json", "geojson", "csv"], case_sensitive=False),
        default="json",
    ),
    cloup.option("--target", type=click.STRING),
    help="Provide either --format or --target.",
)
@cloup.option("--issue", type=click.STRING)
@cloup.option("--shape", type=click.Choice(["long", "wide"]), default="long")
@cloup.option("--si-units", type=click.BOOL, default=True)
@cloup.option("--humanize", type=click.BOOL, default=True)
@cloup.option("--pretty", type=click.BOOL, default=False)
@cloup.option("--skip_empty", type=click.BOOL, default=False)
@cloup.option("--skip_criteria", type=click.Choice(["min", "mean", "max"]), default="min")
@cloup.option("--skip_threshold", type=click.FloatRange(min=0, min_open=True, max=1), default=0.95)
@cloup.option("--dropna", type=click.BOOL, default=False)
@cloup.option("--with-metadata", type=click.BOOL, default=False)
@cloup.option("--with-stations", type=click.BOOL, default=False)
@debug_opt
def values(
    provider: str,
    network: str,
    parameter: list[str],
    resolution: str,
    period: list[str],
    lead_time: Literal["short", "long"],
    date: str,
    issue: str,
    all_: bool,
    station,
    name: str,
    coordinates: str,
    rank: int,
    distance: float,
    bbox: str,
    sql: str,
    sql_values,
    fmt: str,
    target: str,
    shape: Literal["long", "wide"],
    si_units: bool,
    humanize: bool,
    skip_empty: bool,
    skip_criteria: Literal["min", "mean", "max"],
    skip_threshold: float,
    dropna: bool,
    pretty: bool,
    with_metadata: bool,
    with_stations: bool,
    debug: bool,
):
    set_logging_level(debug)

    api = get_api(provider, network)

    try:
        values_ = get_values(
            api=api,
            parameter=parameter,
            resolution=resolution,
            period=period,
            lead_time=lead_time,
            date=date,
            issue=issue,
            all_=all_,
            station_id=station,
            name=name,
            coordinates=coordinates,
            rank=rank,
            distance=distance,
            bbox=bbox,
            sql=sql,
            sql_values=sql_values,
            si_units=si_units,
            shape=shape,
            humanize=humanize,
            skip_empty=skip_empty,
            skip_criteria=skip_criteria,
            skip_threshold=skip_threshold,
            dropna=dropna,
        )
    except ValueError as e:
        log.exception(e)
        sys.exit(1)
    else:
        if values_.df.is_empty():
            log.error("No data available for given constraints")
            sys.exit(1)

    if target:
        values_.to_target(target)
        return

    output = values_.to_format(fmt, indent=pretty, with_metadata=with_metadata, with_stations=with_stations)

    print(output)  # noqa: T201

    return


@cli.command("interpolate", section=data_section)
@provider_opt
@network_opt
@station_options_core
@cloup.option("--lead-time", type=click.Choice(["short", "long"]), default="short", help="used only for DWD DMO")
@station_options_interpolate_summarize
@cloup.option("--use_nearby_station_distance", type=click.FLOAT, default=1)
@cloup.option("--date", type=click.STRING, required=True)
@cloup.option("--sql-values", type=click.STRING)
@cloup.option_group(
    "Format/Target",
    cloup.option(
        "--format",
        "fmt",
        type=click.Choice(["json", "geojson", "csv"], case_sensitive=False),
        default="json",
    ),
    cloup.option("--target", type=click.STRING),
    help="Provide either --format or --target.",
)
@cloup.option("--issue", type=click.STRING)
@cloup.option("--si-units", type=click.BOOL, default=True)
@cloup.option("--humanize", type=click.BOOL, default=True)
@cloup.option("--pretty", is_flag=True)
@cloup.option("--with-metadata", type=click.BOOL, default=False)
@cloup.option("--with-stations", type=click.BOOL, default=False)
@debug_opt
def interpolate(
    provider: str,
    network: str,
    parameter: list[str],
    resolution: str,
    period: list[str],
    lead_time: Literal["short", "long"],
    use_nearby_station_distance: float,
    date: str,
    issue: str,
    station: str,
    coordinates: str,
    sql_values,
    fmt: str,
    target: str,
    si_units: bool,
    humanize: bool,
    pretty: bool,
    with_metadata: bool,
    with_stations: bool,
    debug: bool,
):
    set_logging_level(debug)

    api = get_api(provider, network)

    try:
        values_ = get_interpolate(
            api=api,
            parameter=parameter,
            resolution=resolution,
            period=period,
            lead_time=lead_time,
            date=date,
            issue=issue,
            station_id=station,
            coordinates=coordinates,
            sql_values=sql_values,
            si_units=si_units,
            humanize=humanize,
            use_nearby_station_distance=use_nearby_station_distance,
        )
    except ValueError as e:
        log.exception(e)
        sys.exit(1)
    else:
        if values_.df.is_empty():
            log.error("No data available for given constraints")
            sys.exit(1)

    if target:
        values_.to_target(target)
        return

    output = values_.to_format(fmt, indent=pretty, with_metadata=with_metadata, with_stations=with_stations)

    print(output)  # noqa: T201

    return


@cli.command("summarize", section=data_section)
@provider_opt
@network_opt
@station_options_core
@cloup.option("--lead-time", type=click.Choice(["short", "long"]), default="short", help="used only for DWD DMO")
@station_options_interpolate_summarize
@cloup.option("--date", type=click.STRING, required=True)
@cloup.option("--sql-values", type=click.STRING)
@cloup.option_group(
    "Format/Target",
    cloup.option(
        "--format",
        "fmt",
        type=click.Choice(["json", "geojson", "csv"], case_sensitive=False),
        default="json",
    ),
    cloup.option("--target", type=click.STRING),
    help="Provide either --format or --target.",
)
@cloup.option("--issue", type=click.STRING)
@cloup.option("--si-units", type=click.BOOL, default=True)
@cloup.option("--humanize", type=click.BOOL, default=True)
@cloup.option("--pretty", is_flag=True)
@cloup.option("--with-metadata", type=click.BOOL, default=False)
@cloup.option("--with-stations", type=click.BOOL, default=False)
@debug_opt
def summarize(
    provider: str,
    network: str,
    parameter: list[str],
    resolution: str,
    period: list[str],
    lead_time: Literal["short", "long"],
    date: str,
    issue: str,
    station: str,
    coordinates: str,
    sql_values,
    fmt: str,
    target: str,
    si_units: bool,
    humanize: bool,
    pretty: bool,
    with_metadata: bool,
    with_stations: bool,
    debug: bool,
):
    set_logging_level(debug)

    api = get_api(provider, network)

    try:
        values_ = get_summarize(
            api=api,
            parameter=parameter,
            resolution=resolution,
            period=period,
            lead_time=lead_time,
            date=date,
            issue=issue,
            station_id=station,
            coordinates=coordinates,
            sql_values=sql_values,
            si_units=si_units,
            humanize=humanize,
        )
    except ValueError as e:
        log.exception(e)
        sys.exit(1)
    else:
        if values_.df.is_empty():
            log.error("No data available for given constraints")
            sys.exit(1)

    if target:
        values_.to_target(target)
        return

    output = values_.to_format(fmt, indent=pretty, with_metadata=with_metadata, with_stations=with_stations)

    print(output)  # noqa: T201

    return


@cli.command("radar", section=data_section)
@cloup.option("--dwd", is_flag=True)
@cloup.option("--all", "all_", is_flag=True)
@cloup.option("--odim-code", type=click.STRING)
@cloup.option("--wmo-code", type=click.STRING)
@cloup.option("--country-name", type=click.STRING)
@cloup.constraint(
    RequireExactly(1),
    ["dwd", "all_", "odim_code", "wmo_code", "country_name"],
)
@cloup.option("--indent", type=click.INT, default=4)
def radar(
    dwd: bool,
    all_: bool,
    odim_code: str,
    wmo_code: int,
    country_name: str,
    indent: int,
):
    from wetterdienst.provider.dwd.radar.api import DwdRadarSites
    from wetterdienst.provider.eumetnet.opera.sites import OperaRadarSites

    if dwd:
        data = DwdRadarSites().all()
    else:
        if all_:
            data = OperaRadarSites().all()
        elif odim_code:
            data = OperaRadarSites().by_odim_code(odim_code)
        elif wmo_code:
            data = OperaRadarSites().by_wmo_code(wmo_code)
        elif country_name:
            data = OperaRadarSites().by_country_name(country_name)
        else:
            raise KeyError("No valid option provided")

    output = json.dumps(data, indent=indent)

    print(output)  # noqa: T201

    return


@cli.group("stripes", section=data_section)
def stripes():
    pass


@stripes.command("stations")
@cloup.option("--kind", type=click.STRING, required=True)
@cloup.option("--active", type=click.BOOL, default=True)
@cloup.option("--format", "fmt", type=click.Choice(["json", "geojson", "csv"], case_sensitive=False), default="json")
@cloup.option("--pretty", type=click.BOOL, default=False)
def stripes_stations(kind: str, active: bool, fmt: str, pretty: bool):
    if kind not in ["temperature", "precipitation"]:
        raise click.ClickException(f"Invalid kind '{kind}'")

    stations = _get_stripes_stations(kind=kind, active=active)

    output = stations.to_format(fmt, indent=pretty)

    print(output)  # noqa: T201


@stripes.command("values")
@cloup.option("--kind", type=click.STRING, required=True)
@cloup.option("--station", type=click.STRING)
@cloup.option("--name", type=click.STRING)
@cloup.option("--start_year", type=click.INT)
@cloup.option("--end_year", type=click.INT)
@cloup.option("--name_threshold", type=click.FLOAT, default=0.90)
@cloup.option("--show_title", type=click.BOOL, default=True)
@cloup.option("--show_years", type=click.BOOL, default=True)
@cloup.option("--show_data_availability", type=click.BOOL, default=True)
@cloup.option("--format", "fmt", type=click.Choice(["png", "jpg", "svg", "pdf"], case_sensitive=False), default="png")
@cloup.option("--dpi", type=click.INT, default=300)
@cloup.option("--target", type=click.Path(dir_okay=False, path_type=Path))
@debug_opt
@cloup.constraint(
    RequireExactly(1),
    ["station", "name"],
)
def stripes_values(
    kind: Literal["temperature", "precipitation"],
    station: str,
    name: str,
    start_year: int,
    end_year: int,
    name_threshold: float,
    show_title: bool,
    show_years: bool,
    show_data_availability: bool,
    fmt: str,
    dpi: int,
    target: Path,
    debug: bool,
):
    if target:
        if not target.name.lower().endswith(fmt):
            raise click.ClickException(f"'target' must have extension '{fmt}'")

    import matplotlib.pyplot as plt

    set_logging_level(debug)

    try:
        buf = _plot_stripes(
            kind=kind,
            station_id=station,
            name=name,
            start_year=start_year,
            end_year=end_year,
            name_threshold=name_threshold,
            show_title=show_title,
            show_years=show_years,
            show_data_availability=show_data_availability,
            fmt=fmt,
            dpi=dpi,
        )
    except Exception as e:
        log.exception(e)
        raise click.ClickException(str(e)) from e

    if target:
        image = Image.open(buf, formats=["png"])
        plt.imshow(image)
        plt.axis("off")
        plt.savefig(target, dpi=300, bbox_inches="tight")
        return

    click.echo(buf.getvalue(), nl=False)


@stripes.command("interactive")
@debug_opt
def interactive(debug: bool):
    set_logging_level(debug)

    try:
        from wetterdienst.ui.streamlit.stripes import app
    except ImportError:
        log.error("Please install the stripes extras from stripes/requirements.txt")
        sys.exit(1)

    log.info(f"Starting {appname}")
    log.info("Starting Stripes web service on http://localhost:8501")

    process = None
    try:
        process = subprocess.Popen(["streamlit", "run", app.__file__])  # noqa: S603, S607
        process.wait()
    except KeyboardInterrupt:
        log.info("Stopping Climate Stripes web service")
    except Exception as e:
        log.error(f"An error occurred: {str(e)}")
    finally:
        if process is not None:
            process.terminate()


if __name__ == "__main__":
    cli()
