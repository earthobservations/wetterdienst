# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Command line interface for the Wetterdienst package."""

from __future__ import annotations

import json
import logging
import sys
import textwrap
from pathlib import Path
from pprint import pformat
from typing import TYPE_CHECKING, Any, Literal, TypeVar, get_args

import click
from click.core import ParameterSource
from pydantic import BaseModel, ValidationError
from pydantic_settings import SettingsError

from wetterdienst import Settings, Wetterdienst, __appname__, __version__
from wetterdienst.exceptions import (
    ApiNotFoundError,
    BufrReaderMissingError,
    ExportRefusedError,
    InvalidTimeIntervalError,
    NoStationsWithElevationError,
    ParameterNotCarriedError,
)
from wetterdienst.metadata.unit_type import UnitType
from wetterdienst.provider.dwd.observation import DwdObservationRequest
from wetterdienst.settings import check_settings
from wetterdienst.ui.core import (
    SUMMARY_USE_NEARBY_STATION_DISTANCE_DEPRECATED,
    HistoryRequest,
    InterpolationRequest,
    IssuesRequest,
    StationsRequest,
    StripesImageRequest,
    SummaryRequest,
    ValuesRequest,
    _get_stripes_stations,
    _is_caller_refusal,
    _plot_stripes,
    describe_fields,
    get_glossary,
    get_interpolate,
    get_issues,
    get_stations,
    get_summarize,
    get_values,
    join_names,
    limit_stations_to_rank,
    select_history_sections,
    set_logging_level,
)
from wetterdienst.util.cli import setup_logging
from wetterdienst.util.extras import missing_dependency_message
from wetterdienst.util.ui import read_list
from wetterdienst.util.url import redact_password

if TYPE_CHECKING:
    from collections.abc import Callable

    from pydantic_core import ErrorDetails

    from wetterdienst.model.request import TimeseriesRequest

log = logging.getLogger(__name__)

# `values`, `interpolate` and `summarize` all take the same date, so they say the same thing about
# it: a date covers everything it names, which is what tells `2020-05` from `2020-05-01`
_DATE_HELP = (
    "Single date or interval in ISO 8601 format, covering everything it names: 2020-05-01 is that "
    "whole day, 2020-05 the month and 2020 the year, while a date carrying a time (2020-05-01T12) "
    "is that one instant. Examples: 2020-05-01, 2020-05, 2020-05-01/2020-05-05"
)

_RequestT = TypeVar("_RequestT", bound=BaseModel)
_CommandT = TypeVar("_CommandT", bound="Callable[..., Any]")

appname = f"{__appname__} {__version__}"

# Options more than one command takes, defined once so each reads the same wherever it appears. A
# command lists the ones it takes in the order its help shows them: what is asked for, which
# stations, what is done to the values, and then the output.
provider_opt = click.option(
    "--provider",
    type=click.STRING,
    required=True,
    help=(
        "Data provider/organisation. List the provider/network combinations with: "
        "wetterdienst about coverage. Examples: dwd, eccc, noaa, wsv, ea, eaufrance, nws, geosphere"
    ),
)
network_opt = click.option(
    "--network",
    type=click.STRING,
    required=True,
    help="Data network of the provider. Examples: observation, mosmix, radar, ghcn, pegel, hydrology",
)
parameters_opt = click.option(
    "--parameters",
    type=click.STRING,
    required=True,
    help=(
        "Parameters as resolution/dataset or resolution/dataset/parameter, comma-separated. "
        "Examples: daily/kl, daily/climate_summary/precipitation_amount"
    ),
)
periods_opt = click.option(
    "--periods",
    type=click.STRING,
    help=(
        "Dataset periods, comma-separated. Inferred from the date when one is given, else every "
        "period the requested datasets publish; one they are not published under is rejected. "
        "Examples: historical, recent, now"
    ),
)
lead_time_opt = click.option(
    "--lead_time",
    type=click.Choice(["short", "long"]),
    default="short",
    help="DWD DMO forecast lead time; ignored by other networks. Default: short",
)
issue_opt = click.option(
    "--issue",
    type=click.STRING,
    help="DWD MOSMIX/DMO/SWSMOS model run (ISO 8601); list them with: wetterdienst issues. Default: the latest",
)
date_opt = click.option("--date", type=click.STRING, help=_DATE_HELP)
start_date_opt = click.option(
    "--start-date",
    "start_date",
    type=click.STRING,
    help="Start of a date range, instead of --date. Given alone, it is a single date.",
)
end_date_opt = click.option(
    "--end-date",
    "end_date",
    type=click.STRING,
    help="End of a date range. Given alone, it is a single date.",
)

# station selection for `stations` and `values`: exactly one of --all, --station, --name, a point
# or a bounding box, --sql. The request models enforce it, so the CLI, REST API and MCP share it
all_opt = click.option("--all", "all_", is_flag=True, help="Select all stations.")
station_ids_opt = click.option(
    "--station",
    type=click.STRING,
    help="Select stations by id, comma-separated. Example: 01048,04411",
)
name_opt = click.option(
    "--name",
    type=click.STRING,
    help="Select stations by fuzzy name match, the best five unless --rank says. Example: Dresden-Klotzsche",
)
name_threshold_opt = click.option(
    "--name-threshold",
    "name_threshold",
    type=click.FloatRange(min=0, max=1),
    default=0.8,
    help="Minimum fuzzy-match score for --name (0 = any match, 1 = exact). Default: 0.8",
)
latitude_opt = click.option("--latitude", type=click.FLOAT, help="Latitude of the reference point.")
longitude_opt = click.option("--longitude", type=click.FLOAT, help="Longitude of the reference point.")
rank_opt = click.option(
    "--rank",
    type=click.INT,
    help="The N stations closest to --latitude/--longitude, or the N best --name matches.",
)
distance_opt = click.option(
    "--distance",
    type=click.FLOAT,
    help="The stations within this many km of --latitude/--longitude.",
)
left_opt = click.option("--left", type=click.FLOAT, help="Select stations in a bounding box: its west longitude.")
bottom_opt = click.option("--bottom", type=click.FLOAT, help="South latitude of the bounding box.")
right_opt = click.option("--right", type=click.FLOAT, help="East longitude of the bounding box.")
top_opt = click.option("--top", type=click.FLOAT, help="North latitude of the bounding box.")
sql_opt = click.option(
    "--sql",
    type=click.STRING,
    help="Select stations by a SQL WHERE clause over their metadata. Example: region='Sachsen'",
)

sql_values_opt = click.option(
    "--sql_values",
    type=click.STRING,
    help="SQL WHERE clause applied to the values. Example: parameter='wind_gust_max' AND value > 20",
)
convert_units_opt = click.option(
    "--convert_units",
    type=click.BOOL,
    default=True,
    help=(
        "Convert values to the unit targets: the defaults, overridden per quantity by --unit_targets. "
        "Default: WD_TS_CONVERT_UNITS if set, else true"
    ),
)
unit_targets_opt = click.option(
    "--unit_targets",
    type=click.STRING,
    help='Unit targets as a JSON map of quantity to unit. Example: {"temperature":"degree_fahrenheit"}',
)
humanize_opt = click.option(
    "--humanize",
    type=click.BOOL,
    default=True,
    help="Use canonical parameter names instead of the provider's own codes. Default: WD_TS_HUMANIZE if set, else true",
)

format_opt = click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "geojson", "csv", "html", "png", "jpg", "webp", "svg", "pdf"], case_sensitive=False),
    default="json",
    help="Output format: json, geojson or csv for data, html, png, jpg, webp, svg or pdf for a chart. Default: json",
)
target_opt = click.option(
    "--target",
    type=click.STRING,
    help="Export target URI, instead of stdout. Examples: file://data.csv, duckdb:///obs.duckdb?table=weather",
)
# what a target that already holds data does with the next write. `to_target` has taken this since
# it was written, and the docs advertise it, but no command passed it, so every CLI export replaced
# -- which is only the wrong default for a schedule, where the point is usually to accumulate
if_exists_opt = click.option(
    "--if_exists",
    type=click.Choice(["replace", "append", "fail", "skip"]),
    default="replace",
    help=(
        "What to do when --target already holds data: 'replace' (drop and rewrite, default), "
        "'append' (add to it), 'fail' or 'skip'. Not every sink takes every value: files refuse "
        "'append', and InfluxDB refuses 'fail' and 'skip' and accumulates under both of the "
        "others, nothing there clearing a measurement. Default: replace"
    ),
)
pretty_opt = click.option(
    "--pretty",
    type=click.BOOL,
    default=False,
    help="Pretty-print JSON with 4-space indentation. Default: false",
)
with_metadata_opt = click.option(
    "--with_metadata",
    type=click.BOOL,
    default=False,
    help="Include the provider metadata block in JSON/GeoJSON output. Default: false",
)
with_stations_opt = click.option(
    "--with_stations",
    type=click.BOOL,
    default=False,
    help="Include the stations in JSON/GeoJSON output. Default: false",
)
debug_opt = click.option("--debug", is_flag=True, help="Log at debug level.")

# the reference point `interpolate` and `summarize` estimate for: exactly one of a station or a point,
# which their request models enforce
reference_station_opt = click.option(
    "--station",
    type=click.STRING,
    help="Station id whose location to estimate for, instead of --latitude/--longitude.",
)
elevation_opt = click.option(
    "--elevation",
    type=click.FLOAT,
    help=(
        "Elevation of the reference point in metres above sea level. Given, a quantity that "
        "falls with height -- air temperature, dew point -- is brought from each station's "
        "altitude to this one, which is what tells a valley reading from a summit one. "
        "Applies to --station as well, where it is the elevation asked about rather than "
        "the station's own."
    ),
)
use_nearby_station_distance_opt = click.option(
    "--use_nearby_station_distance",
    type=click.FLOAT,
    default=1,
    help=(
        "Use a station's own values when it is within this many km of the point. "
        "Default: WD_TS_GEO_USE_NEARBY_STATION_DISTANCE if set, else 1"
    ),
)
# accepted by `summarize` still, so that an invocation giving it is warned rather than refused (GH-2333)
summary_use_nearby_station_distance_opt = click.option(
    "--use_nearby_station_distance",
    type=click.FLOAT,
    default=1,
    deprecated=SUMMARY_USE_NEARBY_STATION_DISTANCE_DEPRECATED,
)
# a flag here, where stations/values/history take a value: changing either breaks invocations
pretty_flag_opt = click.option("--pretty", is_flag=True, help="Pretty-print JSON with 4-space indentation.")


def station_distance_opts(kind: str) -> Callable[[_CommandT], _CommandT]:
    """Apply the `--<kind>_station_distance*` options, which each estimating command names after itself."""
    options = [
        click.option(
            f"--{kind}_station_distance",
            type=click.STRING,
            help=(
                "Per-parameter maximum station distance in km as JSON, overriding the radii. "
                'Example: {"precipitation_amount":10}'
            ),
        ),
        click.option(
            f"--{kind}_station_distance_homogeneous",
            type=click.FLOAT,
            help="Maximum station distance in km for a parameter that varies slowly, such as air temperature. "
            "Default: WD_TS_GEO_STATION_DISTANCE_HOMOGENEOUS if set, else 40",
        ),
        click.option(
            f"--{kind}_station_distance_heterogeneous",
            type=click.FLOAT,
            help="The same for one that decorrelates faster, such as precipitation, at hourly resolution. "
            "Default: WD_TS_GEO_STATION_DISTANCE_HETEROGENEOUS if set, else 20",
        ),
    ]

    def apply(command: _CommandT) -> _CommandT:
        for option in reversed(options):
            command = option(command)
        return command

    return apply


def get_api(provider: str, network: str) -> type[TimeseriesRequest]:
    """Get API for provider and network.

    A provider or network that does not exist is the command line's mistake, so it is a usage error
    naming where the existing ones are listed, as the REST API answers it with a 404 and that hint.
    """
    try:
        return Wetterdienst(provider, network)
    except ApiNotFoundError as e:
        msg = f"{e} `wetterdienst about coverage`, without --provider and --network, lists the available ones."
        raise click.UsageError(msg) from e


def _validate_request(model: type[_RequestT], values: dict[str, Any]) -> _RequestT:
    """Build a request model, reporting a rejected value as a usage error rather than a traceback.

    Every field here comes from a command option, so a validation error is the user's input being
    out of range -- a negative distance, say -- not a bug to show a stack trace for. It is told in
    click's terms, by the options involved, as click tells its own errors.
    """
    try:
        return model.model_validate(values)
    except ValidationError as e:
        ctx = click.get_current_context()
        raise click.UsageError(_describe_validation_error(e, ctx), ctx=ctx) from e


def _build_settings(options: dict[str, tuple[str, Any]]) -> Settings:
    """Build a command's settings from the environment and the options given on the command line.

    `options` maps each option's parameter to the setting it sets and the value it sets it to. An
    option is passed only when given on the command line: an init argument outranks the
    environment, so passing its default would hide the `WD_TS_*` variable set for that setting.

    Should they fail, the environment's settings are checked on their own, and an error there is
    raised as it is: a malformed `WD_*` variable is not the command line's to fix. Where an error is
    located would not tell, as pydantic-settings merges a dict the environment sets into the one an
    option gives. A variable an option replaces is left out of that check. With the environment's
    valid, the error is the options', told by the option as click tells an invalid value, with the
    value the option gave rather than the one merged with the environment's.
    """
    ctx = click.get_current_context()
    # each setting given by the option that sets it
    given = {
        setting: (param, value)
        for param, (setting, value) in options.items()
        if ctx.get_parameter_source(param) is not ParameterSource.DEFAULT
    }
    try:
        return Settings(**{setting: value for setting, (_, value) in given.items()})
    except ValidationError as e:
        # a dict is merged with the environment's, anything else replaces it
        replaced = {setting for setting, (_, value) in given.items() if not isinstance(value, dict)}
        try:
            Settings()
        except ValidationError as environment:
            if any(not problem["loc"] or problem["loc"][0] not in replaced for problem in environment.errors()):
                raise environment from None
        problems = e.errors(include_url=False)
        if any(not problem["loc"] or problem["loc"][0] not in given for problem in problems):
            raise
        params = {param.name: param for param in ctx.command.params if param.name}
        lines = []
        for problem in problems:
            param, value = given[str(problem["loc"][0])]
            # an entry within a dict is the option's, the environment's being valid on their own
            input_ = value if len(problem["loc"]) == 1 else problem["input"]
            lines.append(
                _describe_problem({**problem, "loc": (param, *problem["loc"][1:]), "input": input_}, params, ctx)
            )
        raise click.UsageError("\n".join(lines), ctx=ctx) from e


def _describe_validation_error(error: ValidationError, ctx: click.Context) -> str:
    """Tell a request model's validation errors as click tells its own, a line each.

    The model reports a rule over several fields -- which stations to select -- by its type, the
    field it is located at and, in `ctx`, the other fields involved; each is named here by its
    option. pydantic's echo of the whole input is left out, which for such a rule is every option
    the command took.
    """
    # each field by the option that sets it: `format` comes from --format, whose parameter is `fmt`
    params: dict[str, click.Parameter] = {}
    for param in ctx.command.params:
        for opt in param.opts:
            if opt.startswith("--"):
                params.setdefault(opt.removeprefix("--").replace("-", "_"), param)
    problems = error.errors(include_url=False)
    # a conflict is reported at each field involved, and told once for them all
    conflicting = [
        field
        for problem in problems
        if problem["type"] == "mutually_exclusive"
        for field in (str(problem["loc"][0]), *problem["ctx"]["conflicts_with"])
    ]
    lines = [_describe_problem(problem, params, ctx) for problem in problems if problem["type"] != "mutually_exclusive"]
    if conflicting:
        options = join_names([_option_hint(field, params, ctx) for field in dict.fromkeys(conflicting)])
        lines.insert(0, f"Options {options} cannot be used together.")
    return "\n".join(lines)


def _option_hint(field: str, params: dict[str, click.Parameter], ctx: click.Context) -> str:
    """Name a field by its option, quoted as click quotes one in an error."""
    return params[field].get_error_hint(ctx) if field in params else repr(field)


def _describe_problem(problem: ErrorDetails, params: dict[str, click.Parameter], ctx: click.Context) -> str:
    """Tell one validation error in click's terms: a missing option, or an invalid value for one."""
    kind, info = problem["type"], problem.get("ctx", {})
    field = str(problem["loc"][0]) if problem["loc"] else ""

    def hint(field: str) -> str:
        return _option_hint(field, params, ctx)

    if kind == "missing_one_of":
        required_with = info.get("required_with")
        suffix = f", required with {join_names([hint(f) for f in required_with])}" if required_with else ""
        return f"Missing option: one of {describe_fields(info['one_of'], hint)}{suffix}."
    if kind == "missing_with" and field in params:
        message = f"Required with {join_names([hint(f) for f in info['required_with']])}."
        return click.MissingParameter(message, ctx, params[field]).format_message()
    if kind == "greater_than_field" and field in params:
        message = f"Input should be greater than {hint(info['field'])} ({info['gt']}) (got {problem['input']!r})."
        return click.BadParameter(message, ctx, params[field]).format_message()
    if kind == "requires":
        return f"Option {hint(field)} requires {describe_fields(info['requires'], hint)}."
    if field in params:
        # a position within the value is left out -- --sections is a set, so it points nowhere --
        # and the value refused is shown instead; a key within a mapping stays
        within = "".join(f"{part}: " for part in problem["loc"][1:] if not isinstance(part, int))
        # a field validator's ValueError comes with pydantic's prefix, which says nothing click would
        message = f"{within}{problem['msg'].removeprefix('Value error, ')} (got {problem['input']!r})."
        return click.BadParameter(message, ctx, params[field]).format_message()
    return problem["msg"].removeprefix("Value error, ")


def _require_one_of(**given: bool) -> None:
    """Refuse none or several of alternative options, as a request model's refusal is told.

    For the commands with no request model; each option is keyed by its parameter's name.
    """
    ctx = click.get_current_context()
    hints = {param.name: param.get_error_hint(ctx) for param in ctx.command.params}
    made = [hints[name] for name, is_set in given.items() if is_set]
    if not made:
        msg = f"Missing option: one of {join_names([hints[name] for name in given], last='or')}."
        raise click.UsageError(msg, ctx)
    if len(made) > 1:
        msg = f"Options {join_names(made)} cannot be used together."
        raise click.UsageError(msg, ctx)


def _resolve_date(date: str | None, start_date: str | None, end_date: str | None) -> str | None:
    """Resolve --date from either --date or the --start-date/--end-date pair.

    If only --end-date is given, it is treated as a single-point date (start == end).
    Raises click.UsageError when conflicting options are supplied.
    """
    if date and (start_date or end_date):
        msg = "Use either --date or --start-date / --end-date, not both."
        raise click.UsageError(msg)
    if start_date or end_date:
        start = start_date or end_date
        end = end_date or start_date
        return f"{start}/{end}" if start != end else start
    return date


# the top-level help is an overview and nothing more: each command's options are in its own help,
# generated from the options themselves, and its examples in its epilog. The page this replaces
# restated every option by hand, and named several that no longer existed (GH-2021)
wetterdienst_help = """\
Weather, climate and hydrology data from national weather services, in one interface.

A typical session finds a provider's network, then a station, then reads its data:

\b
    wetterdienst about coverage
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl --name=Dresden-Klotzsche
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --station=01048 --date=2020-05

Run `wetterdienst COMMAND --help` for a command's options and examples.
"""


def _examples(text: str) -> str:
    """Format a command's examples for its epilog, keeping each block's lines as written.

    Click rewraps a paragraph unless a line holding only a backspace character opens it, and a
    paragraph ends at a blank line, so each block of examples gets its own.
    """
    blocks = textwrap.dedent(text).strip().split("\n\n")
    return "\n\n".join(["Examples:", *(f"\b\n{block}" for block in blocks)])


# each command's examples, shown after its options. tests/ui/cli/test_cli.py checks that every one
# names a command that exists and only options that command takes
STATIONS_EXAMPLES = r"""
    # all stations with daily climate summaries, as JSON, CSV or GeoJSON
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl --all
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl --all --format=csv
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl --all --format=geojson

    # stations by id, or by fuzzy name
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl --station=1048,4411
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl --name=Dresden

    # the five stations closest to a point, or those within 25 km of it
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl \
        --latitude=49.9195 --longitude=8.9671 --rank=5
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl \
        --latitude=49.9195 --longitude=8.9671 --distance=25

    # stations by region, or by a pattern in their name
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl --sql="region='Sachsen'"
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl \
        --sql="lower(name) LIKE lower('%dresden%')"

    # MOSMIX forecast stations
    wetterdienst stations --provider=dwd --network=mosmix --parameters=hourly/large --all

    # export to a spreadsheet
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl --all \
        --target=file://stations.xlsx
"""

HISTORY_EXAMPLES = r"""
    wetterdienst history --provider=dwd --network=observation --parameters=daily/kl --station=1048

    # only the name and geography sections
    wetterdienst history --provider=dwd --network=observation --parameters=daily/kl --station=1048 \
        --sections=name,geography
"""

VALUES_EXAMPLES = r"""
    # recent daily climate summaries for two stations, or for one found by name
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent \
        --station=1048,4411
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent \
        --name=Dresden-Hosterwitz

    # a date covers everything it names: a day, a month, a year
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --date=2020-05-01 --station=1048
    wetterdienst values --provider=dwd --network=observation --parameters=monthly/kl --date=2020-05 --station=1048
    wetterdienst values --provider=dwd --network=observation --parameters=annual/kl --date=2019 --station=1048,4411

    # a range, as an ISO 8601 interval or as --start-date/--end-date; historical and recent data are joined
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl \
        --date=1969-01-01/2020-06-11 --station=1048
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl \
        --start-date=2020-05-01 --end-date=2020-05-05 --station=1048

    # two parameters from different datasets, hourly, one column each
    wetterdienst values --provider=dwd --network=observation \
        --parameters=hourly/precipitation/precipitation_amount,hourly/air_temperature/temperature_air_mean_2m \
        --date=2020-06-15T12/2020-06-16T12 --station=1048,4411 --shape=wide

    # the days with a wind gust above 20 m/s, one row per value or, filtering on the column, one per day
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent \
        --station=1048,4411 --sql_values="parameter='wind_gust_max' AND value > 20.0"
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent \
        --station=1048,4411 --shape=wide --sql_values="wind_gust_max > 20.0"

    # the five stations closest to a point that have data for the date
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl \
        --latitude=49.9195 --longitude=8.9671 --rank=5 --date=2020-06-30

    # MOSMIX and DMO forecasts
    wetterdienst values --provider=dwd --network=mosmix --parameters=hourly/large/ttt,hourly/large/ff --station=65510
    wetterdienst values --provider=dwd --network=dmo --parameters=hourly/icon/ttt --station=65510 --lead_time=long

    # export to a file or a database
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent \
        --station=1048,4411 --target=file://observations.parquet
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent \
        --station=1048,4411 --target="duckdb:///observations.duckdb?table=weather"
"""

INTERPOLATE_EXAMPLES = r"""
    # daily precipitation where a station stands, from the stations around it
    wetterdienst interpolate --provider=dwd --network=observation \
        --parameters=daily/climate_summary/precipitation_amount --date=2020-06-30 --station=01048

    # the same for a point
    wetterdienst interpolate --provider=dwd --network=observation \
        --parameters=daily/climate_summary/precipitation_amount --date=2020-06-30 --latitude=49.9195 --longitude=8.9671
"""

SUMMARIZE_EXAMPLES = r"""
    # daily precipitation where a station stands, from the nearest station with a value
    wetterdienst summarize --provider=dwd --network=observation \
        --parameters=daily/climate_summary/precipitation_amount --date=2020-06-30 --station=01048

    # the same for a point
    wetterdienst summarize --provider=dwd --network=observation \
        --parameters=daily/climate_summary/precipitation_amount --date=2020-06-30 --latitude=49.9195 --longitude=8.9671
"""

COVERAGE_EXAMPLES = r"""
    # every provider and network
    wetterdienst about coverage

    # the resolutions, datasets and parameters of one network, or of part of it
    wetterdienst about coverage --provider=dwd --network=observation
    wetterdienst about coverage --provider=dwd --network=observation --resolutions=1_minute
    wetterdienst about coverage --provider=dwd --network=observation --datasets=climate_summary
"""

RESTAPI_EXAMPLES = r"""
    # listen on http://127.0.0.1:7890; with the mcp extra, it also serves MCP at /mcp
    wetterdienst restapi

    # listen on every interface, and reload on source changes
    wetterdienst restapi --listen=0.0.0.0:8890 --reload
"""

RADAR_EXAMPLES = r"""
    wetterdienst radar --all
    wetterdienst radar --dwd
    wetterdienst radar --country_name=france
    wetterdienst radar --odim-code=deasb
    wetterdienst radar --wmo_code=10103
"""

ALERTS_EXAMPLES = r"""
    # current warnings per community (Gemeinde), as JSON
    wetterdienst alerts

    # per district (Landkreis), as GeoJSON, in German
    wetterdienst alerts --granularity=district --language=de --format=geojson

    # the warnings active at a past time: replace YYYY-MM-DDTHH:MM with one within the last
    # ~48 hours, all DWD keeps
    wetterdienst alerts --granularity=district --date=YYYY-MM-DDTHH:MM

    # to a GeoJSON file
    wetterdienst alerts --format=geojson --target=file://alerts.geojson
"""

STRIPES_EXAMPLES = r"""
    # warming stripes for a station, by id or by name
    wetterdienst stripes values --kind=temperature --station=1048 > warming_stripes.png
    wetterdienst stripes values --kind=temperature --name=Dresden-Klotzsche --name_threshold=0.7 > warming_stripes.png

    # for the years 2000 to 2020
    wetterdienst stripes values --kind=temperature --station=1048 --start_year=2000 --end_year=2020 \
        > warming_stripes.png

    # precipitation stripes, to a file
    wetterdienst stripes values --kind=precipitation --station=1048 --target=precipitation_stripes.png
"""


def _refuse_if_callers(e: Exception, request: BaseModel) -> None:
    """Raise a failure caught from a request as a usage error if it is the caller's own mistake.

    A refusal the caller can rephrase -- one the REST API answers with a 4xx -- is told in one line,
    exit 2, as a mistyped option is (GH-2426). Anything else -- an upstream failure or a defect -- is
    left to the handler, and keeps its traceback and exit 1.
    """
    if _is_caller_refusal(e, request):
        raise click.UsageError(str(e)) from e


def _collect_or_exit(
    get: Callable[..., Any],
    *,
    api: Any,  # noqa: ANN401
    request: Any,  # noqa: ANN401
    settings: Settings,
    what: str,
) -> Any:  # noqa: ANN401
    """Run one of the values getters, reporting the failures a caller can do something about.

    Three kinds can be acted on rather than debugged: an optional reader that is not installed, a
    request the caller can rephrase, and a window that holds no readings. Each is a sentence the
    caller needs and a traceback buries, so each is printed and nothing else. A request to rephrase
    -- one this provider cannot serve as phrased, a point an estimate cannot be made at (beyond the
    latitudes UTM covers, or a station without a position), or any refusal the REST API answers
    with a 4xx -- is the command line's mistake, so it is a usage error, exit 2 (GH-2426).
    """
    try:
        values_ = get(api=api, request=request, settings=settings)
    except BufrReaderMissingError as e:
        # the message names what to install: the whole of what is to be done about it. Narrow on
        # purpose -- a bare `ImportError` would swallow a cycle or a typo inside a provider module,
        # which is a defect and wants its traceback, not an instruction. The command line was right,
        # the environment lacks the reader, so this is exit 1 rather than a usage error
        log.error(str(e))  # noqa: TRY400
        sys.exit(1)
    except (NoStationsWithElevationError, ParameterNotCarriedError) as e:
        # the message names what to ask instead; the REST API answers these with a 400 of their own
        raise click.UsageError(str(e)) from e
    except Exception as e:
        _refuse_if_callers(e, request)
        if not isinstance(e, ValueError):
            # not caught here: click re-raises it, and Python prints its traceback and exits 1
            raise
        log.exception(f"Error during {what}")
        sys.exit(1)
    if values_.df.is_empty():
        log.error("No data available for given constraints")
        sys.exit(1)
    return values_


def _export_or_exit(result: Any, target: str, if_exists: str) -> None:  # noqa: ANN401
    """Write to the target, telling a sink that refuses apart from a sink that broke.

    A refusal is a finished sentence and wants nothing else -- `Append mode is not supported for
    file exports.` Anything else a sink raises is a defect or an environment problem, where the
    detail is the whole of what is useful, so it keeps its traceback and names the target.

    Which is which is `ExportRefusedError`'s job to say, and it is a separate class because this
    used to be inferred here: `fail` arrives from DuckDB as one exception and from the SQLAlchemy
    sinks as another, both classes are also how a sink breaks, and no rule over types and messages
    got that right for long. A `KeyError` from inside a sink was reported as advice and printed its
    own argument and nothing else -- exporting a stations frame to InfluxDB pops a `timestamp` column
    that only values carry, and the whole report was `ERROR date`, as the column was then called.
    """
    try:
        result.to_target(target, if_exists=if_exists)
    except ExportRefusedError as e:
        log.error(str(e))  # noqa: TRY400
        sys.exit(1)
    except Exception:
        log.exception(f"Failed to export to {redact_password(target)}")
        sys.exit(1)


def _refuse_non_file_target(target: str | None, command: str) -> None:
    """Refuse a --target with a scheme other than `file://`, for a command that writes plain text.

    `alerts` and `history` write their output with `Path.write_text`, not the timeseries commands'
    `to_target()`, so only a local path or a `file://` URI is a target they can write. Called before
    the fetch, so that `s3://...` or `duckdb://...` is a usage error at once, rather than a write to
    the path read off the URI (`s3:/bucket/...`) that fails once the whole fetch has run.
    """
    if target and "://" in target and not target.startswith("file://"):
        msg = f"--target only supports a local path or a file:// URI for {command}."
        raise click.BadParameter(msg)


class _Cli(click.Group):
    """The command group, telling a malformed `WD_*` setting by its variable (GH-2335).

    A command builds its settings where it needs them, and each used to end in pydantic's traceback
    when the environment's were malformed, naming the field rather than the variable and repeating
    the value. Whatever command it comes from, such an error is told here instead, a line each, with
    exit status 1: the environment is not the command line's to fix. An error the settings from
    the environment alone do not reproduce is the options', and is left as it is.
    """

    def invoke(self, ctx: click.Context) -> Any:  # noqa: ANN401
        try:
            return super().invoke(ctx)
        except (ValidationError, SettingsError) as e:
            # another model's error is not the settings', even beside a malformed variable an
            # option overrode
            if isinstance(e, ValidationError) and e.title != Settings.__name__:
                raise
            problems = check_settings()
            if not problems:
                raise
            raise click.ClickException("\n".join(problems)) from None


@click.group(
    "wetterdienst",
    cls=_Cli,
    help=wetterdienst_help,
    context_settings={"max_content_width": 120},
)
@click.version_option(__version__, "-v", "--version", message="%(version)s")
def cli() -> None:
    """Command line interface for the Wetterdienst package."""
    setup_logging()


@cli.command("cache")
def cache() -> None:
    """Display cache location."""
    from wetterdienst import Settings  # noqa: PLC0415

    print(Settings().cache_dir)  # noqa: T201


@cli.command("info")
def info() -> None:
    """Display project information."""
    from wetterdienst import Info  # noqa: PLC0415

    print(Info())  # noqa: T201


@cli.command("restapi", epilog=_examples(RESTAPI_EXAMPLES))
@click.option("--listen", type=click.STRING, default=None, help="Listen address as host:port. Default: 127.0.0.1:7890")
@click.option("--reload", is_flag=True, help="Reload the service when a source file changes, for development.")
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

    try:
        from wetterdienst.ui.restapi import start_service  # noqa: PLC0415
    except ImportError as e:
        msg = missing_dependency_message("The REST API", e.name, extra="restapi")
        raise ImportError(msg) from e

    start_service(listen, reload=reload)


@cli.group()
def about() -> None:
    """Get information about the data."""


@about.command(epilog=_examples(COVERAGE_EXAMPLES))
@click.option("--provider", type=click.STRING, help="Data provider. Without it and --network, every combination.")
@click.option("--network", type=click.STRING, help="Data network of the provider.")
@click.option("--resolutions", type=click.STRING, help="Only these resolutions, comma-separated. Example: daily,hourly")
@click.option("--datasets", type=click.STRING, help="Only these datasets, comma-separated. Example: climate_summary")
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

    resolutions_list = read_list(resolutions)
    datasets_list = read_list(datasets)

    api = get_api(provider=provider, network=network)

    # Standalone networks (e.g. dwd/radar, dwd/alerts) have no metadata model and thus no per-network
    # discover(); report that cleanly instead of crashing with an AttributeError.
    if not hasattr(api, "discover"):
        log.error(f"Coverage is not available for provider '{provider}' and network '{network}'.")
        sys.exit(1)

    cov = api.discover(
        resolutions=resolutions_list,
        datasets=datasets_list,
    )

    print(json.dumps(cov, indent=2))  # noqa: T201


@about.command("glossary")
@click.option(
    "--parameter",
    type=click.STRING,
    help="Match canonical parameter names containing this text, e.g. radiation.",
)
@click.option(
    "--unit-type",
    # a closed vocabulary, so an unknown one is a usage error rather than an empty result
    type=click.Choice(get_args(UnitType)),
    help="Restrict to one quantity, e.g. temperature.",
)
@click.option(
    "--limit",
    type=click.IntRange(min=1),
    help="Return at most this many entries; the full vocabulary runs to several hundred parameters.",
)
@debug_opt
def glossary(
    parameter: str | None,
    unit_type: UnitType | None,
    limit: int | None,
    debug: bool,  # noqa: FBT001
) -> None:
    """Look up what a parameter measures and which unit it is returned in.

    The unit shown is the one a values request would return, including any WD_TS_UNIT_TARGETS
    override.
    """
    set_logging_level(debug=debug)

    entries = get_glossary(parameter=parameter, unit_type=unit_type, limit=limit)

    if not entries:
        log.error("No canonical parameter matches the given filters.")
        sys.exit(1)

    # ensure_ascii=False so unit symbols print as °C and J/cm² rather than escapes; this command
    # exists to show them
    print(json.dumps(entries, indent=2, ensure_ascii=False))  # noqa: T201


@about.command("fields")
@provider_opt
@network_opt
@click.option(
    "--resolution",
    type=click.STRING,
    required=True,
    help="Resolution name, e.g. daily or hourly.",
)
@click.option(
    "--dataset",
    type=click.STRING,
    required=True,
    help="Dataset name, e.g. climate_summary or precipitation.",
)
@click.option("--period", type=click.STRING, required=True, help="Period name, e.g. historical, recent or now.")
@click.option(
    "--language",
    type=click.Choice(["en", "de"], case_sensitive=False),
    default="en",
    help="Language of the field descriptions. Default: en",
)
@debug_opt
def fields(
    provider: str,
    network: str,
    dataset: str,
    resolution: str,
    period: str,
    language: Literal["en", "de"],
    debug: bool,  # noqa: FBT001
) -> None:
    """Describe the fields of a dataset's files, from the provider's own documentation.

    DWD observation only: no other provider publishes such a description.
    """
    set_logging_level(debug=debug)
    api = get_api(provider, network)
    if not issubclass(api, DwdObservationRequest):
        msg = f"Fields are described for provider 'dwd', network 'observation' only, not {provider}/{network}."
        raise click.UsageError(msg)

    try:
        metadata = api.describe_fields(
            dataset=(resolution, dataset),
            period=period,
            language=language,
        )
    except ImportError:
        msg = "Could not retrieve fields."
        log.exception(msg)
        sys.exit(1)

    output = pformat(dict(metadata))

    print(output)  # noqa: T201


@cli.command("stations", epilog=_examples(STATIONS_EXAMPLES))
@provider_opt
@network_opt
@parameters_opt
@periods_opt
@all_opt
@station_ids_opt
@name_opt
@name_threshold_opt
@latitude_opt
@longitude_opt
@rank_opt
@distance_opt
@left_opt
@bottom_opt
@right_opt
@top_opt
@sql_opt
@format_opt
@target_opt
@if_exists_opt
@pretty_opt
@with_metadata_opt
@debug_opt
def stations(
    provider: str,
    network: str,
    parameters: list[str],
    periods: list[str],
    all_: bool,  # noqa: FBT001
    station: list[str],
    name: str,
    name_threshold: float,
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
    if_exists: Literal["replace", "append", "fail", "skip"],
    pretty: bool,  # noqa: FBT001
    with_metadata: bool,  # noqa: FBT001
    debug: bool,  # noqa: FBT001
) -> None:
    """Acquire stations.

    Select them with exactly one of --all, --station, --name, --latitude/--longitude with --rank or
    --distance, --left/--bottom/--right/--top, or --sql.
    """
    request = _validate_request(
        StationsRequest,
        {
            "provider": provider,
            "network": network,
            "parameters": parameters,
            "periods": periods,
            "all": all_,
            "station": station,
            "name": name,
            "name_threshold": name_threshold,
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

    # A rank filter keeps all stations in the frame (rank is applied lazily during value collection);
    # for a plain listing return just the N closest the caller asked for instead of every station.
    stations_ = limit_stations_to_rank(stations_)

    if target:
        _export_or_exit(stations_, target, if_exists)
        return

    # build kwargs dynamically
    kwargs: dict[str, Any] = {
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


@cli.command("issues")
@provider_opt
@network_opt
@click.option("--station", type=click.STRING, required=True, help="Station id to list the model runs of.")
@click.option(
    "--dataset",
    type=click.Choice(["icon", "icon_eu"]),
    default=None,
    help="DWD DMO product; DMO only, refused for MOSMIX and SWSMOS. Default: icon",
)
@click.option(
    "--lead_time",
    type=click.Choice(["short", "long"]),
    default=None,
    help="DWD DMO forecast lead time; DMO only, refused for MOSMIX and SWSMOS. Default: short",
)
@debug_opt
def issues_cmd(
    provider: str,
    network: str,
    station: str,
    dataset: str | None,
    lead_time: str | None,
    debug: bool,  # noqa: FBT001
) -> None:
    """List available issue (model-run) datetimes for a station.

    Currently supported: --provider dwd --network mosmix|dmo|swsmos

    A DMO run exists for a product, so --dataset and --lead_time decide which runs are listed. They
    default to what a `values` request defaults to, which is what makes the answer one that request
    accepts.
    """
    set_logging_level(debug=debug)

    api = get_api(provider=provider, network=network)
    request = IssuesRequest.model_validate(
        {
            "provider": provider,
            "network": network,
            "station": station,
            "dataset": dataset,
            "lead_time": lead_time,
        },
    )

    # built outside the catch-all below, so that a malformed `WD_*` setting is told by its variable
    settings = Settings()
    try:
        issue_list = get_issues(api=api, request=request, settings=settings)
    except NotImplementedError as e:
        # a network without an issue listing, which the message names: `/api/issues` answers a 400
        raise click.UsageError(str(e)) from e
    except Exception as e:
        # a request the caller can rephrase, such as a DMO-only option on MOSMIX, is told in one
        # line, as `/api/issues` answers it with a 400; an upstream failure keeps its traceback
        _refuse_if_callers(e, request)
        log.exception("Failed to get issues.")
        sys.exit(1)

    print(json.dumps({"issues": issue_list}, indent=2))  # noqa: T201


@cli.command("history", epilog=_examples(HISTORY_EXAMPLES))
@provider_opt
@network_opt
@parameters_opt
@all_opt
@station_ids_opt
@click.option(
    "--sections",
    type=click.STRING,
    help="History sections to include, comma-separated: name, parameter, device, geography, missing_data. "
    "Default: all. Each history gives its station_id, resolution and dataset, whichever are included",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json"], case_sensitive=False),
    default="json",
    help="Output format. Default: json",
)
@click.option(
    "--target",
    type=click.STRING,
    help="Write the output to this .json file instead of stdout. Example: file://history.json",
)
@pretty_opt
@with_metadata_opt
@with_stations_opt
@debug_opt
def history(
    provider: str,
    network: str,
    parameters: list[str],
    all_: bool,  # noqa: FBT001
    station: str,
    sections: str | None,
    fmt: str,  # noqa: ARG001
    target: str,
    *,
    with_metadata: bool,
    with_stations: bool,
    pretty: bool,
    debug: bool,
) -> None:
    """Acquire station history.

    Select the stations with exactly one of --all or --station.
    """
    _refuse_non_file_target(target, "history")
    # a local path, or a `file://` URI with its prefix removed as `alerts` removes it; the `.json` check reads the rest
    path = target.removeprefix("file://") if target else None
    if path is not None and not path.endswith(".json"):
        msg = "--target for history endpoint must end with .json"
        raise click.BadParameter(msg)

    request = _validate_request(
        HistoryRequest,
        {
            "provider": provider,
            "network": network,
            "parameters": parameters,
            "all": all_,
            "station": station,
            "sections": sections,
            "with_metadata": with_metadata,
            "with_stations": with_stations,
            "pretty": pretty,
            "debug": debug,
        },
    )

    set_logging_level(debug=debug)

    api = get_api(provider=provider, network=network)

    # built outside the catch-all below, so that a malformed `WD_*` setting is told by its variable
    settings = Settings()
    try:
        stations_ = get_stations(api=api, request=request, date=None, settings=settings)
    except Exception as e:
        # a parameter or station the caller can rephrase is told in one line, as `/api/history`
        # answers it with a 400; an upstream failure keeps its traceback
        _refuse_if_callers(e, request)
        log.exception("Failed to get stations for history.")
        sys.exit(1)

    try:
        history_provider = stations_.history
    except NotImplementedError:
        log.exception("History not implemented for provider/network")
        sys.exit(1)

    data: dict[str, Any] = {}
    if request.with_metadata:
        data["metadata"] = stations_.get_metadata()
    if request.with_stations:
        data["stations"] = stations_.to_dict(with_metadata=False)["stations"]
    data["histories"] = []
    try:
        for history_result in history_provider.query():
            history_result_data = history_result.history.model_dump(mode="python")
            data["histories"].append(select_history_sections(history_result_data, request.sections))
    except Exception:
        log.exception("Failed to collect station history")
        sys.exit(1)

    output = json.dumps(data, indent=4 if pretty else None, default=lambda dt: dt.isoformat())

    if path is not None:
        try:
            Path(path).write_text(output)
        except OSError as e:
            # a directory that does not exist or cannot be written, or a path naming a directory
            msg = f"Could not write --target: {e}"
            raise click.ClickException(msg) from e
        return

    print(output)  # noqa: T201

    return


@cli.command("values", epilog=_examples(VALUES_EXAMPLES))
@provider_opt
@network_opt
@parameters_opt
@periods_opt
@date_opt
@start_date_opt
@end_date_opt
@lead_time_opt
@issue_opt
@all_opt
@station_ids_opt
@name_opt
@name_threshold_opt
@latitude_opt
@longitude_opt
@rank_opt
@distance_opt
@left_opt
@bottom_opt
@right_opt
@top_opt
@sql_opt
@sql_values_opt
@click.option(
    "--shape",
    type=click.Choice(["long", "wide"]),
    default="long",
    help=(
        "Output shape: 'long' (one row per value) or 'wide' (one column per parameter). "
        "Default: WD_TS_SHAPE if set, else long"
    ),
)
@convert_units_opt
@unit_targets_opt
@humanize_opt
@click.option(
    "--skip_empty",
    type=click.BOOL,
    default=False,
    help="Skip stations whose coverage falls below --skip_threshold. Default: WD_TS_SKIP_EMPTY if set, else false",
)
@click.option(
    "--skip_criteria",
    type=click.Choice(["min", "mean", "max"]),
    default="min",
    help=(
        "Aggregation over the requested parameters' coverage: min, mean or max. "
        "Default: WD_TS_SKIP_CRITERIA if set, else min"
    ),
)
@click.option(
    "--skip_threshold",
    type=click.FloatRange(min=0, min_open=True, max=1),
    default=0.95,
    help="Coverage fraction below which --skip_empty skips a station. Default: WD_TS_SKIP_THRESHOLD if set, else 0.95",
)
@click.option(
    "--drop_nulls",
    type=click.BOOL,
    default=True,
    help="Drop rows with null values from the output. Default: WD_TS_DROP_NULLS if set, else true",
)
@format_opt
@target_opt
@if_exists_opt
@pretty_opt
@with_metadata_opt
@with_stations_opt
@debug_opt
def values(
    provider: str,
    network: str,
    parameters: list[str],
    periods: list[str],
    lead_time: Literal["short", "long"],
    date: str,
    start_date: str,
    end_date: str,
    issue: str,
    all_: bool,  # noqa: FBT001
    station: list[str],
    name: str,
    name_threshold: float,
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
    if_exists: Literal["replace", "append", "fail", "skip"],
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
    """Acquire data.

    Select the stations with exactly one of --all, --station, --name, --latitude/--longitude with
    --rank or --distance, --left/--bottom/--right/--top, or --sql.
    """
    date_resolved = _resolve_date(date, start_date, end_date)
    request = _validate_request(
        ValuesRequest,
        {
            "provider": provider,
            "network": network,
            "parameters": parameters,
            "periods": periods,
            "lead_time": lead_time,
            "date": date_resolved,
            "issue": issue,
            "all": all_,
            "station": station,
            "name": name,
            "name_threshold": name_threshold,
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

    # a unit target given for a quantity the unit converter does not know is a usage error
    settings = _build_settings(
        {
            "humanize": ("ts_humanize", request.humanize),
            "shape": ("ts_shape", request.shape),
            "convert_units": ("ts_convert_units", request.convert_units),
            "unit_targets": ("ts_unit_targets", request.unit_targets or {}),
            "skip_empty": ("ts_skip_empty", request.skip_empty),
            "skip_criteria": ("ts_skip_criteria", request.skip_criteria),
            "skip_threshold": ("ts_skip_threshold", request.skip_threshold),
            "drop_nulls": ("ts_drop_nulls", request.drop_nulls),
        }
    )

    values_ = _collect_or_exit(get_values, api=api, request=request, settings=settings, what="data acquisition")

    if target:
        _export_or_exit(values_, target, if_exists)
        return

    # build kwargs dynamically
    kwargs: dict[str, Any] = {
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


@cli.command("interpolate", epilog=_examples(INTERPOLATE_EXAMPLES))
@provider_opt
@network_opt
@parameters_opt
@periods_opt
@date_opt
@start_date_opt
@end_date_opt
@lead_time_opt
@issue_opt
@reference_station_opt
@latitude_opt
@longitude_opt
@elevation_opt
@station_distance_opts("interpolation")
@use_nearby_station_distance_opt
@sql_values_opt
@convert_units_opt
@unit_targets_opt
@humanize_opt
@format_opt
@target_opt
@if_exists_opt
@pretty_flag_opt
@with_metadata_opt
@with_stations_opt
@debug_opt
def interpolate(
    provider: str,
    network: str,
    parameters: list[str],
    periods: list[str],
    lead_time: Literal["short", "long"],
    interpolation_station_distance: str,
    interpolation_station_distance_homogeneous: float | None,
    interpolation_station_distance_heterogeneous: float | None,
    use_nearby_station_distance: float,
    date: str,
    start_date: str,
    end_date: str,
    issue: str,
    station: str,
    latitude: float,
    longitude: float,
    elevation: float | None,
    sql_values: str,
    fmt: str,
    target: str,
    if_exists: Literal["replace", "append", "fail", "skip"],
    convert_units: bool,  # noqa: FBT001
    unit_targets: str,
    humanize: bool,  # noqa: FBT001
    pretty: bool,  # noqa: FBT001
    with_metadata: bool,  # noqa: FBT001
    with_stations: bool,  # noqa: FBT001
    debug: bool,  # noqa: FBT001
) -> None:
    """Interpolate data for a point from the stations around it.

    Give the point as exactly one of --station or --latitude/--longitude.
    """
    date_resolved = _resolve_date(date, start_date, end_date)
    if not date_resolved:
        msg = "Provide either --date or --start-date."
        raise click.UsageError(msg)
    request = _validate_request(
        InterpolationRequest,
        {
            "provider": provider,
            "network": network,
            "parameters": parameters,
            "periods": periods,
            "lead_time": lead_time,
            "interpolation_station_distance": interpolation_station_distance,
            "interpolation_station_distance_homogeneous": interpolation_station_distance_homogeneous,
            "interpolation_station_distance_heterogeneous": interpolation_station_distance_heterogeneous,
            "use_nearby_station_distance": use_nearby_station_distance,
            "date": date_resolved,
            "issue": issue,
            "station": station,
            "latitude": latitude,
            "longitude": longitude,
            "elevation": elevation,
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

    # a distance given for a name that is not a canonical parameter, or a negative one, or a unit
    # target for a quantity the unit converter does not know is a usage error
    settings = _build_settings(
        {
            "humanize": ("ts_humanize", request.humanize),
            "convert_units": ("ts_convert_units", request.convert_units),
            "unit_targets": ("ts_unit_targets", request.unit_targets or {}),
            "interpolation_station_distance": ("ts_geo_station_distance", request.interpolation_station_distance or {}),
            "interpolation_station_distance_homogeneous": (
                "ts_geo_station_distance_homogeneous",
                request.interpolation_station_distance_homogeneous,
            ),
            "interpolation_station_distance_heterogeneous": (
                "ts_geo_station_distance_heterogeneous",
                request.interpolation_station_distance_heterogeneous,
            ),
            "use_nearby_station_distance": ("ts_geo_use_nearby_station_distance", request.use_nearby_station_distance),
        }
    )

    values_ = _collect_or_exit(get_interpolate, api=api, request=request, settings=settings, what="interpolation")

    if target:
        _export_or_exit(values_, target, if_exists)
        return
    # build kwargs dynamically
    kwargs: dict[str, Any] = {
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


@cli.command("summarize", epilog=_examples(SUMMARIZE_EXAMPLES))
@provider_opt
@network_opt
@parameters_opt
@periods_opt
@date_opt
@start_date_opt
@end_date_opt
@lead_time_opt
@issue_opt
@reference_station_opt
@latitude_opt
@longitude_opt
@elevation_opt
@station_distance_opts("summary")
@summary_use_nearby_station_distance_opt
@sql_values_opt
@convert_units_opt
@unit_targets_opt
@humanize_opt
@format_opt
@target_opt
@if_exists_opt
@pretty_flag_opt
@with_metadata_opt
@with_stations_opt
@debug_opt
def summarize(
    provider: str,
    network: str,
    parameters: list[str],
    periods: list[str],
    lead_time: Literal["short", "long"],
    summary_station_distance: str,
    summary_station_distance_homogeneous: float | None,
    summary_station_distance_heterogeneous: float | None,
    use_nearby_station_distance: float,
    date: str,
    start_date: str,
    end_date: str,
    issue: str,
    station: str,
    latitude: float,
    longitude: float,
    elevation: float | None,
    sql_values: str,
    fmt: str,
    target: str,
    if_exists: Literal["replace", "append", "fail", "skip"],
    convert_units: bool,  # noqa: FBT001
    unit_targets: str,
    humanize: bool,  # noqa: FBT001
    pretty: bool,  # noqa: FBT001
    with_metadata: bool,  # noqa: FBT001
    with_stations: bool,  # noqa: FBT001
    debug: bool,  # noqa: FBT001
) -> None:
    """Summarize data for a point: the nearest station's value.

    Give the point as exactly one of --station or --latitude/--longitude.
    """
    date_resolved = _resolve_date(date, start_date, end_date)
    if not date_resolved:
        msg = "Provide either --date or --start-date."
        raise click.UsageError(msg)
    request = _validate_request(
        SummaryRequest,
        {
            "provider": provider,
            "network": network,
            "parameters": parameters,
            "periods": periods,
            "lead_time": lead_time,
            "summary_station_distance": summary_station_distance,
            "summary_station_distance_homogeneous": summary_station_distance_homogeneous,
            "summary_station_distance_heterogeneous": summary_station_distance_heterogeneous,
            "use_nearby_station_distance": use_nearby_station_distance,
            "date": date_resolved,
            "issue": issue,
            "station": station,
            "latitude": latitude,
            "longitude": longitude,
            "elevation": elevation,
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

    # a distance given for a name that is not a canonical parameter, or a negative one, or a unit
    # target for a quantity the unit converter does not know is a usage error
    settings = _build_settings(
        {
            "humanize": ("ts_humanize", request.humanize),
            "convert_units": ("ts_convert_units", request.convert_units),
            "unit_targets": ("ts_unit_targets", request.unit_targets or {}),
            "summary_station_distance": ("ts_geo_station_distance", request.summary_station_distance or {}),
            "summary_station_distance_homogeneous": (
                "ts_geo_station_distance_homogeneous",
                request.summary_station_distance_homogeneous,
            ),
            "summary_station_distance_heterogeneous": (
                "ts_geo_station_distance_heterogeneous",
                request.summary_station_distance_heterogeneous,
            ),
        }
    )

    values_ = _collect_or_exit(get_summarize, api=api, request=request, settings=settings, what="summarize")

    if target:
        _export_or_exit(values_, target, if_exists)
        return

    # build kwargs dynamically
    kwargs: dict[str, Any] = {
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


def _radar_sites(
    *,
    dwd: bool,
    all_: bool,
    odim_code: str | None,
    wmo_code: int | None,
    country_name: str | None,
) -> dict | list[dict]:
    """Look up the radar sites the one given selector names, raising KeyError where none match."""
    from wetterdienst.provider.dwd.radar.api import DwdRadarSites  # noqa: PLC0415
    from wetterdienst.provider.eumetnet.opera.sites import OperaRadarSites  # noqa: PLC0415

    if dwd:
        return DwdRadarSites().all()
    if all_:
        return OperaRadarSites().all()
    if odim_code:
        return OperaRadarSites().by_odim_code(odim_code)
    if wmo_code is not None:
        return OperaRadarSites().by_wmo_code(wmo_code)
    if country_name:
        return OperaRadarSites().by_country_name(country_name)
    msg = "No valid option provided"
    raise KeyError(msg)


@cli.command("radar", epilog=_examples(RADAR_EXAMPLES))
@click.option("--dwd", is_flag=True, help="Select the radar sites DWD operates.")
@click.option("--all", "all_", is_flag=True, help="Select all OPERA radar sites.")
@click.option("--odim-code", type=click.STRING, help="Select the site with this ODIM code. Example: deasb")
@click.option("--wmo_code", type=click.INT, help="Select the site with this WMO code. Example: 10103")
@click.option("--country_name", type=click.STRING, help="Select the sites in this country. Example: france")
@click.option("--indent", type=click.INT, default=4, help="JSON indentation. Default: 4")
def radar(
    dwd: bool,  # noqa: FBT001
    all_: bool,  # noqa: FBT001
    odim_code: str | None,
    wmo_code: int | None,
    country_name: str | None,
    indent: int,
) -> None:
    """List radar stations.

    Select the sites with exactly one of --dwd, --all, --odim-code, --wmo_code or --country_name.
    """
    # an empty code or country, e.g. from an unset shell variable, selects nothing rather than a lookup
    _require_one_of(
        dwd=dwd,
        all_=all_,
        odim_code=bool(odim_code),
        wmo_code=wmo_code is not None,
        country_name=bool(country_name),
    )
    try:
        data = _radar_sites(dwd=dwd, all_=all_, odim_code=odim_code, wmo_code=wmo_code, country_name=country_name)
    except ValueError as e:
        # a code of the wrong shape, which by_odim_code refuses before looking
        raise click.BadParameter(str(e)) from e
    except KeyError as e:
        # a lookup that finds nothing is an answer about the input, not a crash
        raise click.ClickException(e.args[0]) from e

    output = json.dumps(data, indent=indent)

    print(output)  # noqa: T201


@cli.command("alerts", epilog=_examples(ALERTS_EXAMPLES))
@click.option(
    "--granularity",
    type=click.Choice(["community", "district"], case_sensitive=False),
    default="community",
    help="Spatial granularity: 'community' (per Gemeinde, default) or 'district' (per Landkreis).",
)
@click.option(
    "--language",
    type=click.Choice(["de", "en", "es", "fr", "mul"], case_sensitive=False),
    default="en",
    help="Language of the warning texts. Default: en",
)
@click.option(
    "--date",
    type=click.STRING,
    default=None,
    help=(
        "Point in time (ISO 8601, UTC if no offset) to select the active-warnings snapshot for. "
        "Defaults to the latest snapshot. Must fall within DWD's rolling ~48-hour window."
    ),
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "geojson", "csv"], case_sensitive=False),
    default="json",
    help="Output format. Default: json",
)
@click.option(
    "--target",
    type=click.STRING,
    help="Write output to this file instead of stdout. Example: file://alerts.geojson",
)
@click.option(
    "--pretty",
    type=click.BOOL,
    default=False,
    help="Pretty-print JSON/GeoJSON with 4-space indentation. Default: false",
)
@debug_opt
def alerts(
    granularity: str,
    language: str,
    date: str,
    fmt: str,
    target: str,
    pretty: bool,  # noqa: FBT001
    debug: bool,  # noqa: FBT001
) -> None:
    """Acquire DWD weather alerts (CAP warnings).

    Returns all warnings active at the selected time (the latest snapshot by default), one row per
    alert, with a GeoJSON MultiPolygon geometry. An empty result means there were no active warnings.
    """
    set_logging_level(debug=debug)

    from wetterdienst.provider.dwd.alerts import DwdWeatherAlertRequest  # noqa: PLC0415

    _refuse_non_file_target(target, "alerts")

    # outside the handler below, as in `stations` and `values`: the `ValidationError` of a malformed `WD_*`
    # variable is a `ValueError`, and not the command line's to fix
    settings = Settings()
    # granularity, language and format are click choices, so only the date reaches this refusal: one
    # that does not parse, or one an offset carries out of what a datetime holds
    try:
        request = DwdWeatherAlertRequest(granularity=granularity, language=language, date=date, settings=settings)
    except (ValueError, OverflowError) as e:
        raise click.BadParameter(str(e), param_hint="--date") from e

    try:
        result = request.query()
    except InvalidTimeIntervalError as e:
        # a date before DWD's rolling window, the one refusal of the request's own `query` raises;
        # any other `ValueError` comes from DWD's feed (a timestamp, polygon or filename it cannot read)
        raise click.BadParameter(str(e), param_hint="--date") from e
    except Exception as e:
        log.exception("Failed to acquire weather alerts")
        raise click.ClickException(str(e)) from e

    output = result.to_format(fmt, indent=pretty)

    if target:
        path = target.removeprefix("file://")
        try:
            Path(path).write_text(output, encoding="utf-8")
        except OSError as e:
            # a directory that does not exist or cannot be written, or a path naming a directory
            msg = f"Could not write --target: {e}"
            raise click.ClickException(msg) from e
        return

    print(output)  # noqa: T201


@cli.group("stripes")
def stripes() -> None:
    """Climate stripes."""


@stripes.command("stations")
@click.option("--kind", type=click.STRING, required=True, help="Kind of stripes: temperature or precipitation.")
@click.option("--active", type=click.BOOL, default=True, help="Only stations still reporting. Default: true")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "geojson", "csv"], case_sensitive=False),
    default="json",
    help="Output format. Default: json",
)
@click.option("--pretty", type=click.BOOL, default=False, help="Pretty-print JSON. Default: false")
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


@stripes.command("values", epilog=_examples(STRIPES_EXAMPLES))
@click.option("--kind", type=click.STRING, required=True, help="Kind of stripes: temperature or precipitation.")
@click.option("--station", type=click.STRING, help="Station id, instead of --name.")
@click.option("--name", type=click.STRING, help="Station name, matched fuzzily, instead of --station.")
@click.option("--name_threshold", type=click.FLOAT, default=0.80, help="Minimum fuzzy-match score. Default: 0.8")
@click.option("--start_year", type=click.INT, help="First year. Default: the station's first")
@click.option("--end_year", type=click.INT, help="Last year. Default: the station's last")
@click.option("--show_title", type=click.BOOL, default=True, help="Show the station name. Default: true")
@click.option("--show_years", type=click.BOOL, default=True, help="Show the first and last year. Default: true")
@click.option(
    "--show_data_availability",
    type=click.BOOL,
    default=True,
    help="Mark the years without data. Default: true",
)
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["png", "jpg", "svg", "pdf"], case_sensitive=False),
    default="png",
    help="Image format. Default: png",
)
@click.option("--dpi", type=click.IntRange(min=0, min_open=True), default=300, help="Resolution. Default: 300")
@click.option(
    "--target",
    type=click.Path(dir_okay=False, path_type=Path),
    help="Write the image to this file instead of stdout.",
)
@debug_opt
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
    """Create climate stripes for a specific station.

    Select the station with exactly one of --station or --name.
    """
    request = _validate_request(
        StripesImageRequest,
        {
            "kind": kind,
            "station": station,
            "name": name,
            "name_threshold": name_threshold,
            "start_year": start_year,
            "end_year": end_year,
            "show_title": show_title,
            "show_years": show_years,
            "show_data_availability": show_data_availability,
            "format": fmt,
            "dpi": dpi,
            "debug": debug,
        },
    )
    # the suffix, dot included, so `stripespng` is refused; `.jpeg` is as usual for JPEG as `.jpg`
    suffixes = (".jpg", ".jpeg") if fmt == "jpg" else (f".{fmt}",)
    if target and target.suffix.lower() not in suffixes:
        msg = f"'target' must have extension {' or '.join(f'{suffix!r}' for suffix in suffixes)}"
        raise click.ClickException(msg)

    set_logging_level(debug=debug)

    # the provider request builds its settings from the environment inside the catch-all below:
    # checked here first, a malformed `WD_*` setting is told by its variable
    Settings()
    try:
        fig = _plot_stripes(request)
    except Exception as e:
        # a station that is not found, or years holding too little data, is told in one line, as
        # `/api/stripes/image` answers it with a 400; an upstream failure keeps its traceback
        _refuse_if_callers(e, request)
        log.exception("Error while plotting warming stripes")
        raise click.ClickException(str(e)) from e

    image = fig.to_image(fmt, scale=dpi / 100)

    if target:
        # rendered outside the handler: talking to the renderer's browser can raise an `OSError` of its own
        # (choreographer's `ChannelClosedError`), which says nothing about --target
        try:
            target.write_bytes(image)
        except OSError as e:
            # a directory that does not exist or cannot be written; `--target` itself refuses a directory
            msg = f"Could not write --target: {e}"
            raise click.ClickException(msg) from e
        return

    click.echo(image, nl=False)


if __name__ == "__main__":
    cli()
