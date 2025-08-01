# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Command line interface for the Wetterdienst package."""

from __future__ import annotations

import functools
import json
import logging
import subprocess
import sys
from pathlib import Path
from pprint import pformat
from typing import TYPE_CHECKING, Literal

import click
import cloup
from cloup import Section
from cloup.constraints import AllSet, If, RequireExactly, accept_none

from wetterdienst import Settings, Wetterdienst, __appname__, __version__
from wetterdienst.exceptions import ApiNotFoundError
from wetterdienst.ui.core import (
    InterpolationRequest,
    StationsRequest,
    SummaryRequest,
    ValuesRequest,
    _get_stripes_stations,
    _plot_stripes,
    get_interpolate,
    get_stations,
    get_summarize,
    get_values,
    set_logging_level,
)
from wetterdienst.util.cli import docstring_format_verbatim, setup_logging
from wetterdienst.util.ui import read_list

if TYPE_CHECKING:
    from wetterdienst.model.request import TimeseriesRequest

log = logging.getLogger(__name__)

appname = f"{__appname__} {__version__}"

provider_opt = cloup.option_group(
    "Provider",
    click.option(
        "--provider",
        type=click.STRING,
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


def get_api(provider: str, network: str) -> type[TimeseriesRequest]:
    """Get API for provider and network.

    If non found click.Abort() is casted with the error message
    """
    try:
        return Wetterdienst(provider, network)
    except ApiNotFoundError:
        log.exception("No API found.")
        sys.exit(1)


def station_options_core(command: click.Command) -> click.Command:
    """Prepare station options core for cli, which can be used for stations and values endpoint."""
    arguments = [
        cloup.option("--parameters", type=str, required=True),
        cloup.option("--periods", type=str),
    ]
    return functools.reduce(lambda x, opt: opt(x), reversed(arguments), command)


def station_options_extension(command: click.Command) -> click.Command:
    """Prepare station options extension for cli, which can be used for stations and values endpoint."""
    arguments = [
        cloup.option_group("All stations", click.option("--all", "all_", is_flag=True)),
        cloup.option_group(
            "Station id filtering",
            cloup.option("--station", type=str),
        ),
        cloup.option_group(
            "Station name filtering",
            cloup.option("--name", type=click.STRING),
        ),
        cloup.option_group(
            "Latitude-Longitude rank/distance filtering",
            cloup.option("--latitude", type=click.FLOAT),
            cloup.option("--longitude", type=click.FLOAT),
            cloup.option("--rank", type=click.INT),
            cloup.option("--distance", type=click.FLOAT),
            help="Provide --latitude and --longitude plus either --rank or --distance.",
        ),
        cloup.constraint(
            If(AllSet("latitude", "longitude"), then=RequireExactly(1), else_=accept_none),
            ["rank", "distance"],
        ),
        cloup.option_group(
            "BBOX filtering",
            cloup.option("--left", type=click.FLOAT),
            cloup.option("--bottom", type=click.FLOAT),
            cloup.option("--right", type=click.FLOAT),
            cloup.option("--top", type=click.FLOAT),
            constraint=cloup.constraints.all_or_none,
            help="Provide --left, --bottom, --right and --top to filter by bounding box.",
        ),
        cloup.option_group(
            "SQL filtering",
            click.option("--sql", type=click.STRING),
        ),
        cloup.constraint(
            RequireExactly(1),
            ["all_", "station", "name", "latitude", "left", "sql"],
        ),
    ]
    return functools.reduce(lambda x, opt: opt(x), reversed(arguments), command)


def station_options_interpolate_summarize(command: click.Command) -> click.Command:
    """Prepare station options for interpolate/summarize for cli, which can be used for stations and values endpoint."""
    arguments = [
        cloup.option_group(
            "Station id filtering",
            cloup.option("--station", type=str),
        ),
        cloup.option_group(
            "Latitude-Longitude rank/distance filtering",
            cloup.option("--latitude", type=click.FLOAT, help="Latitude of the station"),
            cloup.option("--longitude", type=click.FLOAT, help="Longitude of the station"),
            constraint=cloup.constraints.all_or_none,
        ),
        cloup.constraint(
            RequireExactly(1),
            ["station", "latitude"],
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

    wetterdienst about coverage --provider=<provider> --network=<network>  [--resolutions=<resolutions>] [--datasets=<datasets>]

    wetterdienst about fields --provider=<provider> --network=<network> --dataset=<dataset> --period=<period>
        [--language=<language>]

Data acquisition:

    wetterdienst {stations,values}

        # Selection options
        --provider=<provider> --network=<network> --parameters=<resolution/parameter> [--periods=<periods>]

        # Filtering options
        --all
        --date=<date>
        --station=<station>
        --name=<name>
        --latitude=<latitude> --longitude=<longitude> --rank=<rank>
        --latitude=<latitude> --longitude=<longitude> --distance=<distance>
        --left=<left> --bottom=<bottom> --right=<right> --top=<top>
        --sql=<sql>

        # Output options
        [--format=<format>] [--pretty]
        [--shape=<shape>] [--humanize] [--si_units]
        [--drop_nulls] [--skip_empty] [--skip_threshold=0.95]

        # Export options
        [--target=<target>]

Data computation:

    wetterdienst {interpolate,summarize}

        # Selection options
        --provider=<provider> --network=<network> --parameters=<resolution/parameter> --date=<date> [--periods=<periods>]

        # Filtering options
        --station=<station>
        --latitude=<latitude> --longitude=<longitude>

        # Interpolation options
        --interpolation_station_distance=<distance>
        --use_nearby_station_distance=<distance>

        # Output options
        [--format=<format>] [--pretty]
        [--shape=<shape>] [--humanize] [--si_units]
        [--drop_nulls] [--skip_empty] [--skip_threshold=0.95]

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

    --parameters                The parameters to be requested concatenated by a slash.
                                Examples: daily/climate_summary, daily/climate_summary/precipitation_height

    [--periods]                 Dataset periods
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

    --latitude                  Latitude of geolocation point for filtering stations or values
    --longitude                 Longitude of geolocation point for filtering stations or values

    --rank                      Rank of nearby stations when filtering by geolocation point
                                To be used with `--latitude` and `--longitude`.

    --distance                  Maximum distance in km when filtering by geolocation point
                                To be used with `--latitude` and `--longitude`.

    --left                      Left longitude of bounding box
    --bottom                    Bottom latitude of bounding box
    --right                     Right longitude of bounding box
    --top                       Top latitude of bounding box

    --sql                       SQL filter statement

    --sql_values                SQL filter to apply to values

Transformation options:
    --shape                     Shape of DataFrame, "wide" or "long"
    --humanize                  Humanize parameters
    --si_units                  Convert to SI units
    --skip_empty                Skip empty stations according to ts_skip_threshold
    --skip_threshold            Skip threshold for a station to be empty (0 < ts_skip_threshold <= 1) [Default: 0.95]
    --drop_nulls                    Whether to drop nan values from the result

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
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl --all

    # Get list of all stations in CSV format
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl --all --format=csv

    # Get list of specific stations
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl --station=1,1048,4411

    # Get list of specific stations in GeoJSON format
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl --station=1,1048,4411 --format=geojson

Acquire MOSMIX stations:

    wetterdienst stations --provider=dwd --network=mosmix --parameters=hourly/large --all
    wetterdienst stations --provider=dwd --network=mosmix --parameters=hourly/large --all --format=csv

Acquire observation data:

    # Get daily climate summary data for specific stations, selected by name and station id
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent \\
        --name=Dresden-Hosterwitz
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent \\
        --station=1048,4411

    # Get daily climate summary data for specific stations in CSV format
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent \\
        --station=1048,4411

    # Get daily climate summary data for specific stations in long format
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent \\
        --station=1048,4411 --shape="long"

    # Limit output to specific date
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --date=2020-05-01 \\
        --station=1048,4411

    # Limit output to specified date range in ISO-8601 time interval format
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --date=2020-05-01/2020-05-05
        --station=1048

    # The real power horse: Acquire data across historical+recent data sets
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --date=1969-01-01/2020-06-11
        --station=1048

    # Acquire single data point for month 2020-05
    wetterdienst values --provider=dwd --network=observation --parameters=monthly/kl --tidy --date=2020-05
        --station=1048

    # Acquire monthly data from 2017 to 2019
    wetterdienst values --provider=dwd --network=observation --parameters=monthly/kl --tidy \\
        --date=2017/2019 --station=1048,4411

    # Acquire annual data for 2019
    wetterdienst values --provider=dwd --network=observation --parameters=annual/kl --tidy --date=2019
        --station=1048,4411

    # Acquire annual data from 2010 to 2020
    wetterdienst values --provider=dwd --network=observation --parameters=annual/kl --tidy \\
        --date=2010/2020 --station=1048

    # Acquire hourly data for a given time range
    wetterdienst values --provider=dwd --network=observation --parameters=hourly/air_temperature \\
        --date=2020-06-15T12/2020-06-16T12 --station=1048,4411

    # Acquire data for multiple given parameters
    wetterdienst values --provider=dwd --network=observation \\
        --parameters=hourly/precipitation_more/precipitation_height,hourly/air_temperature/temperature_air_mean_2m \\
        --date=2020-06-15T12/2020-06-16T12 --station=1048,4411

Acquire MOSMIX data:

    wetterdienst values --provider=dwd --network=mosmix --parameters=hourly/large/ttt,hourly/large/ff --station=65510

Acquire DMO data:

    wetterdienst values --provider=dwd --network=dmo --parameters=hourly/icon_eu/ttt --station=65510

    # short lead time
    wetterdienst values --provider=dwd --network=dmo --parameters=hourly/icon/ttt --station=65510 --lead_time=short

    # long lead time
    wetterdienst values --provider=dwd --network=dmo --parameters=hourly/icon/ttt --station=65510 --lead_time=long

Compute data:

    # Compute daily interpolation of precipitation for specific station selected by id
    wetterdienst interpolate --provider=dwd --network=observation --parameters=daily/climate_summary/precipitation_height \\
        --date=2020-06-30 --station=01048

    # Compute daily interpolation of precipitation for specific station selected by coordinates
    wetterdienst interpolate --provider=dwd --network=observation --parameters=daily/kl/precipitation_height \\
        --date=2020-06-30 --latitude=49.9195 --longitude=8.9671

    # Compute daily summary of precipitation for specific station selected by id
    wetterdienst summarize --provider=dwd --network=observation --parameters=daily/kl/precipitation_height \\
        --date=2020-06-30 --station=01048

    # Compute daily summary data of precipitation for specific station selected by coordinates
    wetterdienst summarize --provider=dwd --network=observation --parameters=daily/kl/precipitation_height \\
        --date=2020-06-30 --latitude=49.9195 --longitude=8.9671

Geospatial filtering:

    # Acquire stations and readings by geolocation, request specific number of nearby stations.
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl --periods=recent \\
        --latitude=49.9195 --longitude=8.9671 --rank=5

    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent \\
        --latitude=49.9195 --longitude=8.9671 --rank=5 --date=2020-06-30

    # Acquire stations and readings by geolocation, request stations within specific distance.
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl --periods=recent \\
        --latitude=49.9195 --longitude=8.9671 --distance=25

    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent \\
        --latitude=49.9195 --longitude=8.9671 --distance=25 --date=2020-06-30

SQL filtering:

    # Find stations by state.
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl --periods=recent \\
        --sql="state='Sachsen'"

    # Find stations by name (LIKE query).
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl --periods=recent \\
        --sql="lower(name) LIKE lower('%dresden%')"

    # Find stations by name (regexp query).
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl --periods=recent \\
        --sql="regexp_matches(lower(name), lower('.*dresden.*'))"

    # Filter values: Display daily climate observation readings where the maximum temperature is below two degrees celsius.
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent \\
        --station=1048,4411 --sql_values="wind_gust_max > 20.0;"

    # Filter measurements: Same as above, but use long format.
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent \\
        --station=1048,4411 --shape="long" \\
        --sql_values="parameter='wind_gust_max' AND value > 20.0"

Inquire metadata:

    # Display coverage/correlation between parameters, resolutions and periods.
    # This can answer questions like ...
    wetterdienst about coverage --provider=dwd --network=observation

    # Tell me all available datasets of resolution 1_minute
    wetterdienst about coverage --provider=dwd --network=observation --resolutions=1_minute

    # Tell me all available climate_summary datasets with their parameters
    wetterdienst about coverage --provider=dwd --network=observation --datasets=climate_summary

Export data to files:

    # Export list of stations into spreadsheet
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl --periods=recent \\
        --all --target=file://stations_result.xlsx

    # Shortcut command for fetching readings.
    # It will be used for the next invocations.
    alias fetch="wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent --station=1048,4411"

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
    alias fetch="wetterdienst values --provider=dwd --network=observation --parameters=kl --resolution=daily --period=recent --station=1048,4411"

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
def cli() -> None:
    """Command line interface for the Wetterdienst package."""
    setup_logging()


@cli.command("cache", section=basic_section)
def cache() -> None:
    """Display cache location."""
    from wetterdienst import Settings  # noqa: PLC0415

    print(Settings().cache_dir)  # noqa: T201


@cli.command("info", section=basic_section)
def info() -> None:
    """Display project information."""
    from wetterdienst import Info  # noqa: PLC0415

    print(Info())  # noqa: T201


@cli.command("restapi", section=advanced_section)
@cloup.option("--listen", type=click.STRING, default=None, help="HTTP server listen address")
@cloup.option("--reload", is_flag=True, help="Dynamically reload changed files")
@debug_opt
def restapi(
    listen: str,
    reload: bool,  # noqa: FBT001
    debug: bool,  # noqa: FBT001
) -> None:
    """Start the Wetterdienst REST API web service."""
    set_logging_level(debug=debug)

    # Run HTTP service.
    log.info(f"Starting {appname}")
    log.info(f"Starting HTTP web service on http://{listen}")

    from wetterdienst.ui.restapi import start_service  # noqa: PLC0415

    start_service(listen, reload=reload)


@cli.command("explorer", section=advanced_section)
@cloup.option("--listen", type=click.STRING, default=None, help="HTTP server listen address")
@debug_opt
def explorer(
    listen: str,
    debug: bool,  # noqa: FBT001
) -> None:
    """Start the Wetterdienst Explorer web service."""
    set_logging_level(debug=debug)

    try:
        from wetterdienst.ui.streamlit.explorer import app  # noqa: PLC0415
    except ImportError:
        msg = "Please install the explorer extras with 'pip install wetterdienst[explorer]'"
        log.exception(msg)
        sys.exit(1)

    address = "localhost"
    port = "8501"
    if listen:
        try:
            address, port = listen.split(":")
        except ValueError:
            msg = (
                f"Invalid listen address. Please provide address and port separated by a colon e.g. '{address}:{port}'."
            )
            log.exception(
                msg,
            )
            sys.exit(1)

    log.info(f"Starting {appname}")
    log.info(f"Starting Explorer web service on http://{address}:{port}")

    process = None
    try:
        process = subprocess.Popen(  # noqa: S603
            ["streamlit", "run", app.__file__, "--server.address", address, "--server.port", port],  # noqa: S607
        )
        process.wait()
    except KeyboardInterrupt:
        log.info("Stopping Explorer web service")
    finally:
        if process is not None:
            process.terminate()


@cli.group(section=data_section)
def about() -> None:
    """Get information about the data."""


@about.command()
@cloup.option_group(
    "Provider",
    click.option(
        "--provider",
        type=click.STRING,
    ),
)
@cloup.option_group(
    "Network",
    click.option(
        "--network",
        type=click.STRING,
    ),
)
@cloup.option_group(
    "Resolutions",
    click.option(
        "--resolutions",
        type=click.STRING,
    ),
)
@cloup.option_group(
    "Datasets",
    click.option(
        "--datasets",
        type=click.STRING,
    ),
)
@debug_opt
def coverage(
    provider: str,
    network: str,
    resolutions: str,
    datasets: str,
    debug: bool,  # noqa: FBT001
) -> None:
    """Get coverage information."""
    set_logging_level(debug=debug)

    if not provider or not network:
        print(json.dumps(Wetterdienst.discover(), indent=2))  # noqa: T201
        return

    resolutions = read_list(resolutions)
    datasets = read_list(datasets)

    api = get_api(provider=provider, network=network)

    cov = api.discover(
        resolutions=resolutions,
        datasets=datasets,
    )

    print(json.dumps(cov, indent=2))  # noqa: T201


@about.command("fields")
@provider_opt
@network_opt
@cloup.option_group(
    "(DWD only) information from PDF documents",
    click.option("--dataset", type=click.STRING),
    click.option("--resolution", type=click.STRING),
    click.option("--period", type=click.STRING),
    click.option("--language", type=click.Choice(["en", "de"], case_sensitive=False), default="en"),
    constraint=cloup.constraints.require_all,
)
@debug_opt
def fields(
    provider: str,
    network: str,
    dataset: str,
    resolution: str,
    period: str,
    language: str,
    **kwargs: dict,
) -> None:
    """Get information about fields."""
    api = get_api(provider, network)

    if not (api.metadata.name_short == "DWD" and api.metadata.kind == "observation") and kwargs.get("fields"):
        msg = "'fields' command only available for provider 'DWD'"
        raise click.BadParameter(msg)

    metadata = api.describe_fields(
        dataset=dataset,
        resolution=resolution,
        period=period,
        language=language,
    )

    output = pformat(dict(metadata))

    print(output)  # noqa: T201


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
        type=click.Choice(["json", "geojson", "csv", "html", "png", "jpg", "webp", "svg", "pdf"], case_sensitive=False),
        default="json",
    ),
    cloup.option("--target", type=click.STRING),
)
@cloup.option("--with_metadata", type=click.BOOL, default=True)
@cloup.option("--pretty", type=click.BOOL, default=False)
@debug_opt
def stations(
    provider: str,
    network: str,
    parameters: list[str],
    periods: list[str],
    all_: bool,  # noqa: FBT001
    station: list[str],
    name: str,
    latitude: float,
    longitude: float,
    rank: int,
    distance: float,
    left: float,
    bottom: float,
    right: float,
    top: float,
    sql: str,
    fmt: str,
    target: str,
    pretty: bool,  # noqa: FBT001
    with_metadata: bool,  # noqa: FBT001
    debug: bool,  # noqa: FBT001
) -> None:
    """Acquire stations."""
    request = StationsRequest.model_validate(
        {
            "provider": provider,
            "network": network,
            "parameters": parameters,
            "periods": periods,
            "all": all_,
            "station": station,
            "name": name,
            "latitude": latitude,
            "longitude": longitude,
            "rank": rank,
            "distance": distance,
            "left": left,
            "bottom": bottom,
            "right": right,
            "top": top,
            "sql": sql,
            "format": fmt,
            "pretty": pretty,
            "with_metadata": with_metadata,
            "debug": debug,
        },
    )
    set_logging_level(debug=debug)

    api = get_api(provider=provider, network=network)

    stations_ = get_stations(
        api=api,
        request=request,
        date=None,
        settings=Settings(),
    )

    if stations_.df.is_empty():
        log.error("No stations available for given constraints")
        sys.exit(1)

    if target:
        stations_.to_target(target)
        return

    # build kwargs dynamically
    kwargs = {
        "fmt": request.format,
        "with_metadata": request.with_metadata,
    }
    if request.format in ("json", "geojson"):
        kwargs["indent"] = request.pretty
    if request.format in ("png", "jpg", "webp", "svg", "pdf"):
        kwargs["width"] = request.width
        kwargs["height"] = request.height
        kwargs["scale"] = request.scale

    output = stations_.to_format(**kwargs)

    print(output)  # noqa: T201

    return


@cli.command("values", section=data_section)
@provider_opt
@network_opt
@station_options_core
@cloup.option("--lead_time", type=click.Choice(["short", "long"]), default="short", help="used only for DWD DMO")
@station_options_extension
@cloup.option("--date", type=click.STRING)
@cloup.option("--sql_values", type=click.STRING)
@cloup.option_group(
    "Format/Target",
    cloup.option(
        "--format",
        "fmt",
        type=click.Choice(["json", "geojson", "csv", "html", "png", "jpg", "webp", "svg", "pdf"], case_sensitive=False),
        default="json",
    ),
    cloup.option("--target", type=click.STRING),
    help="Provide either --format or --target.",
)
@cloup.option("--issue", type=click.STRING)
@cloup.option("--shape", type=click.Choice(["long", "wide"]), default="long")
@cloup.option("--convert_units", type=click.BOOL, default=True)
@cloup.option("--unit_targets", type=click.STRING, default=None)
@cloup.option("--humanize", type=click.BOOL, default=True)
@cloup.option("--skip_empty", type=click.BOOL, default=False)
@cloup.option("--skip_criteria", type=click.Choice(["min", "mean", "max"]), default="min")
@cloup.option("--skip_threshold", type=click.FloatRange(min=0, min_open=True, max=1), default=0.95)
@cloup.option("--drop_nulls", type=click.BOOL, default=True)
@cloup.option("--with_metadata", type=click.BOOL, default=True)
@cloup.option("--with_stations", type=click.BOOL, default=True)
@cloup.option("--pretty", type=click.BOOL, default=False)
@debug_opt
def values(
    provider: str,
    network: str,
    parameters: list[str],
    periods: list[str],
    lead_time: Literal["short", "long"],
    date: str,
    issue: str,
    all_: bool,  # noqa: FBT001
    station: list[str],
    name: str,
    latitude: float,
    longitude: float,
    rank: int,
    distance: float,
    left: float,
    bottom: float,
    right: float,
    top: float,
    sql: str,
    sql_values: str,
    fmt: str,
    target: str,
    shape: Literal["long", "wide"],
    convert_units: bool,  # noqa: FBT001
    unit_targets: str,
    humanize: bool,  # noqa: FBT001
    skip_empty: bool,  # noqa: FBT001
    skip_criteria: Literal["min", "mean", "max"],
    skip_threshold: float,
    drop_nulls: bool,  # noqa: FBT001
    pretty: bool,  # noqa: FBT001
    with_metadata: bool,  # noqa: FBT001
    with_stations: bool,  # noqa: FBT001
    debug: bool,  # noqa: FBT001
) -> None:
    """Acquire data."""
    request = ValuesRequest.model_validate(
        {
            "provider": provider,
            "network": network,
            "parameters": parameters,
            "periods": periods,
            "lead_time": lead_time,
            "date": date,
            "issue": issue,
            "all": all_,
            "station": station,
            "name": name,
            "latitude": latitude,
            "longitude": longitude,
            "rank": rank,
            "distance": distance,
            "left": left,
            "bottom": bottom,
            "right": right,
            "top": top,
            "sql": sql,
            "sql_values": sql_values,
            "format": fmt,
            "shape": shape,
            "convert_units": convert_units,
            "unit_targets": unit_targets,
            "humanize": humanize,
            "skip_empty": skip_empty,
            "skip_criteria": skip_criteria,
            "skip_threshold": skip_threshold,
            "drop_nulls": drop_nulls,
            "pretty": pretty,
            "with_metadata": with_metadata,
            "with_stations": with_stations,
            "debug": debug,
        },
    )
    set_logging_level(debug=debug)

    api = get_api(request.provider, request.network)

    settings = Settings(
        ts_humanize=request.humanize,
        ts_shape=request.shape,
        ts_convert_units=request.convert_units,
        ts_unit_targets=request.unit_targets,
        ts_skip_empty=request.skip_empty,
        ts_skip_criteria=request.skip_criteria,
        ts_skip_threshold=request.skip_threshold,
        ts_drop_nulls=request.drop_nulls,
    )

    try:
        values_ = get_values(
            api=api,
            request=request,
            settings=settings,
        )
    except ValueError:
        log.exception("Error during data acquisition")
        sys.exit(1)
    else:
        if values_.df.is_empty():
            log.error("No data available for given constraints")
            sys.exit(1)

    if target:
        values_.to_target(target)
        return

    # build kwargs dynamically
    kwargs = {
        "fmt": request.format,
        "with_metadata": request.with_metadata,
        "with_stations": request.with_stations,
    }
    if request.format in ("json", "geojson"):
        kwargs["indent"] = request.pretty
    if request.format in ("png", "jpg", "webp", "svg", "pdf"):
        kwargs["width"] = request.width
        kwargs["height"] = request.height
        kwargs["scale"] = request.scale

    output = values_.to_format(**kwargs)

    print(output)  # noqa: T201

    return


@cli.command("interpolate", section=data_section)
@provider_opt
@network_opt
@station_options_core
@cloup.option("--lead_time", type=click.Choice(["short", "long"]), default="short", help="used only for DWD DMO")
@station_options_interpolate_summarize
@cloup.option("--interpolation_station_distance", type=click.STRING, default=None)
@cloup.option("--use_nearby_station_distance", type=click.FLOAT, default=1)
@cloup.option("--date", type=click.STRING, required=True)
@cloup.option("--sql_values", type=click.STRING)
@cloup.option_group(
    "Format/Target",
    cloup.option(
        "--format",
        "fmt",
        type=click.Choice(["json", "geojson", "csv", "html", "png", "jpg", "webp", "svg", "pdf"], case_sensitive=False),
        default="json",
    ),
    cloup.option("--target", type=click.STRING),
    help="Provide either --format or --target.",
)
@cloup.option("--issue", type=click.STRING)
@cloup.option("--convert_units", type=click.BOOL, default=True)
@cloup.option("--unit_targets", type=click.STRING, default=None)
@cloup.option("--humanize", type=click.BOOL, default=True)
@cloup.option("--pretty", is_flag=True)
@cloup.option("--with_metadata", type=click.BOOL, default=True)
@cloup.option("--with_stations", type=click.BOOL, default=True)
@debug_opt
def interpolate(
    provider: str,
    network: str,
    parameters: list[str],
    periods: list[str],
    lead_time: Literal["short", "long"],
    interpolation_station_distance: str,
    use_nearby_station_distance: float,
    date: str,
    issue: str,
    station: str,
    latitude: float,
    longitude: float,
    sql_values: str,
    fmt: str,
    target: str,
    convert_units: bool,  # noqa: FBT001
    unit_targets: str,
    humanize: bool,  # noqa: FBT001
    pretty: bool,  # noqa: FBT001
    with_metadata: bool,  # noqa: FBT001
    with_stations: bool,  # noqa: FBT001
    debug: bool,  # noqa: FBT001
) -> None:
    """Interpolate data."""
    request = InterpolationRequest.model_validate(
        {
            "provider": provider,
            "network": network,
            "parameters": parameters,
            "periods": periods,
            "lead_time": lead_time,
            "interpolation_station_distance": interpolation_station_distance,
            "use_nearby_station_distance": use_nearby_station_distance,
            "date": date,
            "issue": issue,
            "station": station,
            "latitude": latitude,
            "longitude": longitude,
            "sql_values": sql_values,
            "format": fmt,
            "convert_units": convert_units,
            "unit_targets": unit_targets,
            "humanize": humanize,
            "with_metadata": with_metadata,
            "with_stations": with_stations,
            "pretty": pretty,
            "debug": debug,
        },
    )

    set_logging_level(debug=debug)

    api = get_api(request.provider, request.network)

    settings = Settings(
        ts_humanize=request.humanize,
        ts_convert_units=request.convert_units,
        ts_unit_targets=request.unit_targets,
        ts_interp_station_distance=request.interpolation_station_distance,
        ts_interp_use_nearby_station_distance=request.use_nearby_station_distance,
    )

    try:
        values_ = get_interpolate(
            api=api,
            request=request,
            settings=settings,
        )
    except ValueError:
        log.exception("Error during interpolation")
        sys.exit(1)
    else:
        if values_.df.is_empty():
            log.error("No data available for given constraints")
            sys.exit(1)

    if target:
        values_.to_target(target)
        return
    # build kwargs dynamically
    kwargs = {
        "fmt": request.format,
        "with_metadata": request.with_metadata,
        "with_stations": request.with_stations,
    }
    if request.format in ("json", "geojson"):
        kwargs["indent"] = request.pretty
    if request.format in ("png", "jpg", "webp", "svg", "pdf"):
        kwargs["width"] = request.width
        kwargs["height"] = request.height
        kwargs["scale"] = request.scale

    output = values_.to_format(**kwargs)

    print(output)  # noqa: T201

    return


@cli.command("summarize", section=data_section)
@provider_opt
@network_opt
@station_options_core
@cloup.option("--lead_time", type=click.Choice(["short", "long"]), default="short", help="used only for DWD DMO")
@station_options_interpolate_summarize
@cloup.option("--date", type=click.STRING, required=True)
@cloup.option("--sql_values", type=click.STRING)
@cloup.option_group(
    "Format/Target",
    cloup.option(
        "--format",
        "fmt",
        type=click.Choice(["json", "geojson", "csv", "html", "png", "jpg", "webp", "svg", "pdf"], case_sensitive=False),
        default="json",
    ),
    cloup.option("--target", type=click.STRING),
    help="Provide either --format or --target.",
)
@cloup.option("--issue", type=click.STRING)
@cloup.option("--convert_units", type=click.BOOL, default=True)
@cloup.option("--unit_targets", type=click.STRING, default=None)
@cloup.option("--humanize", type=click.BOOL, default=True)
@cloup.option("--pretty", is_flag=True)
@cloup.option("--with_metadata", type=click.BOOL, default=True)
@cloup.option("--with_stations", type=click.BOOL, default=True)
@debug_opt
def summarize(
    provider: str,
    network: str,
    parameters: list[str],
    periods: list[str],
    lead_time: Literal["short", "long"],
    date: str,
    issue: str,
    station: str,
    latitude: float,
    longitude: float,
    sql_values: str,
    fmt: str,
    target: str,
    convert_units: bool,  # noqa: FBT001
    unit_targets: str,
    humanize: bool,  # noqa: FBT001
    pretty: bool,  # noqa: FBT001
    with_metadata: bool,  # noqa: FBT001
    with_stations: bool,  # noqa: FBT001
    debug: bool,  # noqa: FBT001
) -> None:
    """Summarize data."""
    request = SummaryRequest.model_validate(
        {
            "provider": provider,
            "network": network,
            "parameters": parameters,
            "periods": periods,
            "lead_time": lead_time,
            "date": date,
            "issue": issue,
            "station": station,
            "latitude": latitude,
            "longitude": longitude,
            "sql_values": sql_values,
            "format": fmt,
            "convert_units": convert_units,
            "unit_targets": unit_targets,
            "humanize": humanize,
            "with_metadata": with_metadata,
            "with_stations": with_stations,
            "pretty": pretty,
            "debug": debug,
        },
    )
    set_logging_level(debug=debug)

    api = get_api(request.provider, request.network)

    settings = Settings(
        ts_humanize=request.humanize,
        ts_convert_units=request.convert_units,
        ts_unit_targets=request.unit_targets,
    )

    try:
        values_ = get_summarize(
            api=api,
            request=request,
            settings=settings,
        )
    except ValueError:
        log.exception("Error during summarize")
        sys.exit(1)
    else:
        if values_.df.is_empty():
            log.exception("No data available for given constraints")
            sys.exit(1)

    if target:
        values_.to_target(target)
        return

    # build kwargs dynamically
    kwargs = {
        "fmt": request.format,
        "with_metadata": request.with_metadata,
        "with_stations": request.with_stations,
    }
    if request.format in ("json", "geojson"):
        kwargs["indent"] = request.pretty
    if request.format in ("png", "jpg", "webp", "svg", "pdf"):
        kwargs["width"] = request.width
        kwargs["height"] = request.height
        kwargs["scale"] = request.scale

    output = values_.to_format(**kwargs)

    print(output)  # noqa: T201

    return


@cli.command("radar", section=data_section)
@cloup.option("--dwd", is_flag=True)
@cloup.option("--all", "all_", is_flag=True)
@cloup.option("--odim-code", type=click.STRING)
@cloup.option("--wmo_code", type=click.STRING)
@cloup.option("--country_name", type=click.STRING)
@cloup.constraint(
    RequireExactly(1),
    ["dwd", "all_", "odim_code", "wmo_code", "country_name"],
)
@cloup.option("--indent", type=click.INT, default=4)
def radar(
    dwd: bool,  # noqa: FBT001
    all_: bool,  # noqa: FBT001
    odim_code: str,
    wmo_code: int,
    country_name: str,
    indent: int,
) -> None:
    """List radar stations."""
    from wetterdienst.provider.dwd.radar.api import DwdRadarSites  # noqa: PLC0415
    from wetterdienst.provider.eumetnet.opera.sites import OperaRadarSites  # noqa: PLC0415

    if dwd:
        data = DwdRadarSites().all()
    elif all_:
        data = OperaRadarSites().all()
    elif odim_code:
        data = OperaRadarSites().by_odim_code(odim_code)
    elif wmo_code:
        data = OperaRadarSites().by_wmo_code(wmo_code)
    elif country_name:
        data = OperaRadarSites().by_country_name(country_name)
    else:
        msg = "No valid option provided"
        raise KeyError(msg)

    output = json.dumps(data, indent=indent)

    print(output)  # noqa: T201


@cli.group("stripes", section=data_section)
def stripes() -> None:
    """Climate stripes."""


@stripes.command("stations")
@cloup.option("--kind", type=click.STRING, required=True)
@cloup.option("--active", type=click.BOOL, default=True)
@cloup.option("--format", "fmt", type=click.Choice(["json", "geojson", "csv"], case_sensitive=False), default="json")
@cloup.option("--pretty", type=click.BOOL, default=False)
def stripes_stations(
    kind: str,
    active: bool,  # noqa: FBT001
    fmt: str,
    pretty: bool,  # noqa: FBT001
) -> None:
    """List stations for climate stripes."""
    if kind not in ["temperature", "precipitation"]:
        msg = f"Invalid kind '{kind}'"
        raise click.ClickException(msg)

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
@cloup.option("--dpi", type=click.IntRange(min=0, min_open=True), default=300)
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
    show_title: bool,  # noqa: FBT001
    show_years: bool,  # noqa: FBT001
    show_data_availability: bool,  # noqa: FBT001
    fmt: str,
    dpi: int,
    target: Path,
    debug: bool,  # noqa: FBT001
) -> None:
    """Create climate stripes for a specific station."""
    if target and not target.name.lower().endswith(fmt):
        msg = f"'target' must have extension '{fmt}'"
        raise click.ClickException(msg)

    set_logging_level(debug=debug)

    try:
        fig = _plot_stripes(
            kind=kind,
            station_id=station,
            name=name,
            start_year=start_year,
            end_year=end_year,
            name_threshold=name_threshold,
            show_title=show_title,
            show_years=show_years,
            show_data_availability=show_data_availability,
        )
    except Exception as e:
        log.exception("Error while plotting warming stripes")
        raise click.ClickException(str(e)) from e

    if target:
        fig.write_image(target, fmt, scale=dpi / 100)
        return

    click.echo(fig.to_image(fmt, scale=dpi / 100), nl=False)


@stripes.command("interactive")
@debug_opt
def interactive(*, debug: bool) -> None:
    """Start the Climate Stripes web service."""
    set_logging_level(debug=debug)

    try:
        from wetterdienst.ui.streamlit.stripes import app  # noqa: PLC0415
    except ImportError:
        log.exception("Please install the stripes extras from stripes/requirements.txt")
        sys.exit(1)

    log.info(f"Starting {appname}")
    log.info("Starting Stripes web service on http://localhost:8501")

    process = None
    try:
        process = subprocess.Popen(["streamlit", "run", app.__file__])  # noqa: S603, S607
        process.wait()
    except KeyboardInterrupt:
        log.info("Stopping Climate Stripes web service")
    finally:
        if process is not None:
            process.terminate()


if __name__ == "__main__":
    cli()
