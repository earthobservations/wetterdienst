# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Command line interface for the Wetterdienst package."""

from __future__ import annotations

import importlib
import json
import logging
import sys
import textwrap
from pathlib import Path
from pprint import pformat
from typing import TYPE_CHECKING, Any, Literal, TypeVar, get_args

import click
from click.core import ParameterSource
from click.shell_completion import CompletionItem

from wetterdienst import __appname__, __version__
from wetterdienst.exceptions import (
    ApiNotFoundError,
    CredentialMissingError,
    CredentialRejectedError,
    DateRequiredError,
    ExportRefusedError,
    ImageTimeoutError,
    InvalidTimeIntervalError,
    MetadataNotFoundError,
    MissingDependencyError,
    NoInternetError,
    ReversedTimeIntervalError,
)
from wetterdienst.io.formats import FORMATS, names_of
from wetterdienst.metadata.unit_type import UnitType
from wetterdienst.model.plausibility_modes import CHECKS, default_mode, forecast_note, hard_means
from wetterdienst.util.cli import no_color, setup_logging
from wetterdienst.util.extras import import_optional
from wetterdienst.util.response_warnings import RESPONSE_WARNING_RECORD, begin_response, log_counted_warnings
from wetterdienst.util.ui import read_list
from wetterdienst.util.url import ConnectionString, file_target_path, redact_password

if TYPE_CHECKING:
    from collections.abc import Callable, Iterable, Mapping

    from pydantic import BaseModel, ValidationError
    from pydantic_core import ErrorDetails

    from wetterdienst import Options, Settings
    from wetterdienst.api import StandaloneRequest
    from wetterdienst.model.plausibility_modes import Mode
    from wetterdienst.model.request import TimeseriesRequest

# Everything above is what the command line costs to import, and it is all that `--help`, `--version` and a shell
# completion load (GH-3809): click, the exceptions, and the plain tables the options are built from. The settings and
# the request models (pydantic, polars), the providers, the results and everything that renders them are imported by
# the command that uses them, as the first thing it does (`values` imports what it needs before it reads an option),
# so that a package that fails to import is told before a request is made, not in the middle of one.
# tests/ui/cli/test_cli_imports.py holds the import of this module to the modules it lists.

log = logging.getLogger(__name__)

# `values`, `interpolate` and `summarize` all take the same date, so they say the same thing about
# it: a date covers everything it names, which is what tells `2020-05` from `2020-05-01`
_TIMESTAMP_HELP = (
    "Single date or interval in ISO 8601 format, covering everything it names: 2020-05-01 is that "
    "whole day, 2020-05 the month and 2020 the year, while a date carrying a time (2020-05-01T12) "
    "is that one instant. Examples: 2020-05-01, 2020-05, 2020-05-01/2020-05-05"
)

_RequestT = TypeVar("_RequestT", bound="BaseModel")
_CommandT = TypeVar("_CommandT", bound="Callable[..., Any]")

appname = f"{__appname__} {__version__}"


# What a command reads its data from is imported when the command first calls it, not when this module is imported
# (GH-3809). These are names of this module because that is where the tests, and a caller who runs the command line in
# their own process, replace what a command reads from: the command calls whatever the name is bound to.
def _deferred(module: str, name: str) -> Callable[..., Any]:
    """Give a function of another module that is imported when it is first called, not when this module is.

    The command that calls it has imported `wetterdienst.ui.core` for its request model by then, or is about to use
    it at once, before anything is fetched.
    """

    def call(*args: Any, **kwargs: Any) -> Any:  # noqa: ANN401
        return getattr(importlib.import_module(module), name)(*args, **kwargs)

    call.__name__ = call.__qualname__ = name
    call.__doc__ = f"`{module}.{name}`, imported when it is first called."
    return call


if TYPE_CHECKING:
    # the real functions to a type checker, which holds a call to their signatures, a misspelled keyword included
    from wetterdienst.ui.core import (
        _plot_stripes,
        get_auth,
        get_glossary,
        get_interpolate,
        get_issues,
        get_stations,
        get_summarize,
        get_values,
        set_logging_level,
    )
else:
    get_auth = _deferred("wetterdienst.ui.core", "get_auth")
    get_glossary = _deferred("wetterdienst.ui.core", "get_glossary")
    get_interpolate = _deferred("wetterdienst.ui.core", "get_interpolate")
    get_issues = _deferred("wetterdienst.ui.core", "get_issues")
    get_stations = _deferred("wetterdienst.ui.core", "get_stations")
    get_summarize = _deferred("wetterdienst.ui.core", "get_summarize")
    get_values = _deferred("wetterdienst.ui.core", "get_values")
    set_logging_level = _deferred("wetterdienst.ui.core", "set_logging_level")
    _plot_stripes = _deferred("wetterdienst.ui.core", "_plot_stripes")


# Shell completion is click's own (`_WETTERDIENST_COMPLETE`, see docs/usage/cli.md). It imports this module and nothing
# else, so a completion that is not from this module's tables must not import a provider (a second on every TAB) and
# never reaches the network: the providers and networks are the keys of the registry, which is a dict of names
# (`wetterdienst.api` imports no provider and no settings, so the registry is cheap to read: GH-3809).
def _complete_provider(ctx: click.Context, param: click.Parameter, incomplete: str) -> list[CompletionItem]:  # noqa: ARG001
    """Complete `--provider` with the providers of the registry."""
    from wetterdienst.api import Wetterdienst

    return [CompletionItem(name) for name in Wetterdienst.get_provider_names() if name.startswith(incomplete.lower())]


def _complete_network(ctx: click.Context, param: click.Parameter, incomplete: str) -> list[CompletionItem]:  # noqa: ARG001
    """Complete `--network` with the networks of the `--provider` already on the line, else of every provider.

    Bash hands over `--provider=dwd` as three words, `--provider`, `=` and `dwd`: click reads the `=` as the value and
    `dwd` is left over in `ctx.args`, where the provider is taken from. The word being completed itself is not: a
    value after an `=` is not offered (zsh would replace the whole word `--provider=dw` by `dwd`, too), which the
    docs say, so a space is the spelling to complete with.
    """
    from wetterdienst.api import Wetterdienst

    provider = ctx.params.get("provider")
    if provider == "=":
        provider = next((word for word in ctx.args if word.strip().lower() in Wetterdienst.registry), None)
    if isinstance(provider, str) and provider.strip().lower() in Wetterdienst.registry:
        names = Wetterdienst.get_network_names(provider)
    else:
        names = sorted({network for networks in Wetterdienst.registry.values() for network in networks})
    return [CompletionItem(name) for name in names if name.startswith(incomplete.lower())]


# `--quiet` is a property of the process's log, and every command that has `--debug` has it. Its value is kept in the
# context and read where the level is set, so that it can be held against `--debug` whichever comes first on the line
_QUIET_KEY = "wetterdienst.quiet"


def _remember_quiet(ctx: click.Context, param: click.Parameter, value: bool) -> bool:  # noqa: ARG001, FBT001
    ctx.meta[_QUIET_KEY] = value
    return value


#: the loggers of the libraries behind an image, which write what they cleaned up as the interpreter ends
_IMAGE_LIBRARIES = ("choreographer", "kaleido")


class _QuietFilter(logging.Filter):
    """Let a handler write errors, the warnings about the answer and `NOTHING_WRITTEN`: what `--quiet` leaves."""

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno >= logging.ERROR or hasattr(record, RESPONSE_WARNING_RECORD)


def _apply_log_level(*, debug: bool) -> None:
    """Set how much the command logs: `--debug` for the package's debug lines, `--quiet` for less, else as it is.

    `--quiet` keeps the errors (`log.error`, `log.exception`), the sentence that nothing was written to the
    `--target`, and the warnings about the answer itself, the ones that are also in the `warnings` of its
    `metadata` (a file the provider let go, a station left out, readings a check rejected, a parameter without rows:
    `warn_response` marks their log records, and `log_counted_warnings` those that are only counted). It drops the
    rest: the progress (logged at INFO), the other warnings of the package and everything the libraries underneath
    write below ERROR. The levels of the root logger and of `wetterdienst` are set to INFO (`station-skipped` is
    logged there) and the handlers they have are given a filter for the rest, both for the length of the command.
    The libraries that draw an image (`choreographer`, `kaleido`) write their INFO lines when the interpreter ends,
    after the command, so they are kept at WARNING for good. The data on stdout, a usage error that click writes
    itself and the exit code are untouched. With `--debug` it is a usage error, which of the two wins is not for
    the command to guess.
    """
    ctx = click.get_current_context()
    if not ctx.meta.get(_QUIET_KEY, False):
        set_logging_level(debug=debug)
        return
    if debug:
        msg = "--quiet and --debug cannot be used together: one logs less than the default and the other more."
        raise click.UsageError(msg)
    loggers = [logging.getLogger(), logging.getLogger("wetterdienst")]
    levels = [logger.level for logger in loggers]
    handlers = list({id(h): h for logger in loggers for h in logger.handlers}.values())
    quiet = _QuietFilter()
    for name in _IMAGE_LIBRARIES:
        logging.getLogger(name).setLevel(logging.WARNING)
    for logger in loggers:
        logger.setLevel(logging.INFO)
    for handler in handlers:
        handler.addFilter(quiet)

    def restore() -> None:
        for logger, level in zip(loggers, levels, strict=True):
            logger.setLevel(level)
        for handler in handlers:
            handler.removeFilter(quiet)

    ctx.call_on_close(restore)


# Options more than one command takes, defined once so each reads the same wherever it appears. A
# command lists the ones it takes in the order its help shows them: what is asked for, which
# stations, what is done to the values, and then the output.
provider_opt = click.option(
    "--provider",
    type=click.STRING,
    shell_complete=_complete_provider,
    required=True,
    help=(
        "Data provider/organisation. List the provider/network combinations with: "
        "wetterdienst about providers. Examples: dwd, eccc, noaa, wsv, ea, eaufrance, nws, geosphere"
    ),
)
network_opt = click.option(
    "--network",
    type=click.STRING,
    shell_complete=_complete_network,
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
        "Dataset periods, comma-separated. Inferred from the timestamp when one is given, else every "
        "period the requested datasets publish; one they are not published under is rejected. "
        "Examples: historical, recent, now"
    ),
)
lead_time_opt = click.option(
    "--lead-time",
    type=click.Choice(["short", "long"]),
    default="short",
    help="DWD DMO forecast lead time; ignored by other networks. Default: short",
)
issue_opt = click.option(
    "--issue",
    type=click.STRING,
    help="DWD MOSMIX/DMO/SWSMOS model run (ISO 8601); list them with: wetterdienst issues. Default: the latest",
)
timestamp_opt = click.option("--timestamp", type=click.STRING, help=_TIMESTAMP_HELP)
# `stations` takes the same window `values` does, and lists the stations whose record overlaps it
stations_timestamp_opt = click.option(
    "--timestamp",
    type=click.STRING,
    help=(
        f"{_TIMESTAMP_HELP}. Given, only the stations whose record overlaps it are listed: one that started "
        "after the window is left out, and so is one that ended before it by more than the buffer "
        "(--station-window-end-buffer), the end a source publishes lagging a station still reporting"
    ),
)

# What an empty result says on stderr, where it is exit 0 and what REST answers with a 200 is written to
# stdout: no station or reading is no failure of the command (GH-2635)
NO_STATIONS = "No stations available for given constraints"
NO_DATA = "No data available for given constraints"
NOTHING_WRITTEN = "Nothing was written to --target."
#: marks the line as one `--quiet` keeps: a scheduled run that wrote nothing must not look like one that did
_NOTHING_WRITTEN_RECORD = {RESPONSE_WARNING_RECORD: "nothing-written"}


def _renamed_opt(old: str, new: str) -> Callable[[_CommandT], _CommandT]:
    """Refuse an option renamed for 1.0 by naming the new one, where click would only say it has none."""

    def refuse(ctx: click.Context, _param: click.Parameter, value: object) -> None:
        if value is not None:
            msg = f"{old} was renamed to {new}."
            raise click.UsageError(msg, ctx)

    # hidden, and its value is optional, so that the option alone is refused by its new name too
    return click.option(
        old, type=click.STRING, is_flag=False, flag_value="", hidden=True, expose_value=False, callback=refuse
    )


def _bool_opt(
    name: str,
    *,
    default: bool,
    help: str,  # noqa: A002
    dest: str | None = None,
    **kwargs: Any,  # noqa: ANN401
) -> Callable[[_CommandT], _CommandT]:
    """Make a boolean option, spelled one way on every command: bare it is on, and it takes `=true` or `=false`.

    A value is read as the REST API reads one of its boolean query parameters, which is what
    `click.BOOL` accepts as well: `1`, `true`, `t`, `yes`, `y`, `on`, and their opposites (GH-2561).
    A bare option is `true`, so that `--pretty` and `--pretty=true` are one, and `--all`, which was a
    flag, takes `--all=true` as REST's `all=true`.
    """
    names = (name, dest) if dest else (name,)
    return click.option(*names, type=click.BOOL, is_flag=False, flag_value="true", default=default, help=help, **kwargs)


# GH-2438: --date, the old name of --timestamp, on the commands that had it in 0.139.0 (not `stations`: GH-3869)
renamed_date_opt = _renamed_opt("--date", "--timestamp")
start_opt = click.option(
    "--start",
    type=click.STRING,
    help="Start of a time window, instead of --timestamp. Given alone, it is read as --timestamp.",
)
end_opt = click.option(
    "--end",
    type=click.STRING,
    help="End of a time window. Given alone, it is read as --timestamp.",
)
# GH-2437: the window is a pair of UTC timestamps, not of dates; on the commands that had `--start-date` in 0.139.0
start_date_renamed_opt = _renamed_opt("--start-date", "--start")
end_date_renamed_opt = _renamed_opt("--end-date", "--end")

# station selection for `stations` and `values`: exactly one of --all, --stations, --name, a point
# or a bounding box, --sql. The request models enforce it, so the CLI, REST API and MCP share it
all_opt = _bool_opt("--all", dest="all_", default=False, help="Select all stations. Default: false")
stations_opt = click.option(
    "--stations",
    type=click.STRING,
    help="Select stations by id, comma-separated. Example: 01048,04411",
)
name_opt = click.option(
    "--name",
    type=click.STRING,
    help=(
        "Select stations by fuzzy name match: the best five for `stations`, which lists candidates, "
        "the best one for `values`, unless --rank says, among the stations with a record in --timestamp "
        "if given. Example: Dresden-Klotzsche"
    ),
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
    help="The N stations closest to --latitude/--longitude, or the N best --name matches, best first.",
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

station_window_end_buffer_opt = click.option(
    "--station-window-end-buffer",
    type=click.IntRange(min=0, max=3660),
    help=(
        "Days after the end its catalogue publishes that a station is still kept for the window: 0 compares "
        "the end exactly. The start is compared exactly. Default: WD_TS_STATION_WINDOW_END_BUFFER if set, else "
        "two days up to daily, 62 for monthly and 732 for annual"
    ),
)


def _plausibility_option(check: str) -> Callable[[_CommandT], _CommandT]:
    """Make the option that sets the mode of a plausibility check: `--plausibility-<check> soft|hard`."""
    return click.option(
        f"--plausibility-{check}",
        type=click.Choice(["hard", "soft"]),
        default=default_mode(check),
        help=(
            f"What the check '{check}' does to a value it finds implausible: hard {hard_means(check)}, soft keeps it "
            f"and flags it `suspect:{check}`. {forecast_note(check)} "
            f"Default: WD_TS_PLAUSIBILITY__{check.upper()} if set, else {default_mode(check)}"
        ),
    )


def plausibility_opts(command: _CommandT) -> _CommandT:
    """Add `--plausibility`, the mode of every check, and the options that set one: `--plausibility-range`..."""
    for check in reversed(CHECKS):
        command = _plausibility_option(check)(command)
    return click.option(
        "--plausibility",
        type=click.Choice(["hard", "soft"]),
        help=(
            "One mode for every plausibility check: soft keeps what a check finds implausible, flagged "
            "`suspect:<check>`, hard nulls it and keeps the number as `rejected:<check>,raw:<number>`. A check "
            "given beside it by --plausibility-<check> wins. The suspect level of source stays flagged. A forecast "
            "network (kind forecast) is soft in every "
            "check but floor and limits, whatever is given. Default: WD_TS_PLAUSIBILITY if set, else the mode of "
            "each check"
        ),
    )(command)


def _read_limits(ctx: click.Context, _param: click.Parameter, values: tuple[str, ...]) -> dict[str, Any] | None:
    """Read the `--limits` given, each a JSON object or `name=low:high`, as one mapping; the later wins for a name."""
    if not values or ctx.resilient_parsing:
        # click calls a callback with the default too, and with a line that is being completed (`resilient_parsing`):
        # neither reads a limit, and neither pays for the import of the model that does (GH-3809)
        return None
    from wetterdienst.model.limits import read_limit_text

    limits: dict[str, Any] = {}
    for text in values:
        try:
            if text.lstrip().startswith("{"):
                given = json.loads(text)
                if not isinstance(given, dict):
                    msg = f"{text!r} is not a JSON object"
                    raise ValueError(msg)  # noqa: TRY301
                pairs = list(given.items())
            else:
                pairs = [read_limit_text(text)]
            for name, pair in pairs:
                # a name given again goes to the end, so that the last of its spellings given is the later
                limits.pop(name, None)
                limits[name] = pair
        except ValueError as e:
            raise click.BadParameter(str(e), param_hint="--limits") from e
    return limits or None


limits_opt = click.option(
    "--limits",
    "limits",
    multiple=True,
    callback=_read_limits,
    help=(
        "Bounds of your own for the plausibility check limits, in the unit the values come back in (see "
        "--unit-targets): a JSON map of a parameter to [low, high], null for no bound at one end "
        '({"temperature_air_mean_2m":[-30,45],"precipitation_amount":[null,200]}), or name=low:high with an end '
        "left empty for none (temperature_air_mean_2m=-30:45, precipitation_amount=:200). Repeat it for more "
        "parameters. A name is a canonical parameter (every dataset that serves it) or resolution/dataset/parameter "
        "(that dataset only, which wins where both name a parameter). A value outside is judged by "
        "--plausibility-limits: hard (the default) nulls it and keeps the number as `rejected:limits,raw:<number>`, "
        "soft keeps it and flags it `suspect:limits`. A forecast network follows this mode too. Default: "
        "WD_TS_LIMITS if set, else none; a name given here replaces the one of WD_TS_LIMITS"
    ),
)

sql_values_opt = click.option(
    "--sql-values",
    type=click.STRING,
    help="SQL WHERE clause applied to the values. Example: parameter='wind_gust_max' AND value > 20",
)
convert_units_opt = _bool_opt(
    "--convert-units",
    default=True,
    help=(
        "Convert values to the unit targets: the defaults, overridden per quantity by --unit-targets. "
        "Default: WD_TS_CONVERT_UNITS if set, else true"
    ),
)
unit_targets_opt = click.option(
    "--unit-targets",
    type=click.STRING,
    help='Unit targets as a JSON map of quantity to unit. Example: {"temperature":"degree_fahrenheit"}',
)
humanize_opt = _bool_opt(
    "--humanize",
    default=True,
    help="Use canonical parameter names instead of the provider's own codes. Default: WD_TS_HUMANIZE if set, else true",
)


def _or_list(names: Iterable[str]) -> str:
    """Write names as a list ending in "or": `json, geojson or csv`."""
    *head, last = names
    return f"{', '.join(head)} or {last}"


# the formats of a command that answers in one body: `ndjson`, which `to_format` has, is the stream of `stations` and
# `values` only, as `interpolate` and `summarize` name no stations to stream by (GH-3590)
_BODY_FORMATS = [name for name in FORMATS if name != "ndjson"]
_BODY_DATA_FORMATS = [name for name in names_of("data") if name != "ndjson"]

format_opt = click.option(
    "--format",
    "fmt",
    type=click.Choice(_BODY_FORMATS, case_sensitive=False),
    default="json",
    help=f"Output format: {_or_list(_BODY_DATA_FORMATS)} for data, {_or_list(names_of('chart'))} for a chart. "
    "Default: json",
)
# of `stations` and `values`, whose csv is streamed by the REST API and which have ndjson (GH-3065)
stream_format_opt = click.option(
    "--format",
    "fmt",
    type=click.Choice(list(FORMATS), case_sensitive=False),
    default="json",
    help=f"Output format: {_or_list(names_of('data'))} (the metadata, a line for each row, then the end) "
    f"for data, {_or_list(names_of('chart'))} for a chart. Default: json",
)
# the size of a chart, for --format of html, png, jpg, webp, svg or pdf
width_opt = click.option("--width", type=click.IntRange(min=1), help="Width of a rendered chart in pixels.")
height_opt = click.option("--height", type=click.IntRange(min=1), help="Height of a rendered chart in pixels.")
scale_opt = click.option(
    "--scale", type=click.FloatRange(min=0, min_open=True), help="Scale factor of a rendered chart image."
)
target_opt = click.option(
    "--target",
    type=click.STRING,
    help="Export target URI, instead of stdout. Examples: file://data.csv, duckdb:///obs.duckdb?table=weather",
)
# what a target that already holds data does with the next write. `to_target` has taken this since
# it was written, and the docs advertise it, but no command passed it, so every CLI export replaced
# -- which is only the wrong default for a schedule, where the point is usually to accumulate.
# `replace` is the default of a result's `to_target`, which the command writes: one frame, written as a whole,
# where `TimeseriesValues.to_target` defaults to `fail` as it fills one table station by station
if_exists_opt = click.option(
    "--if-exists",
    type=click.Choice(["replace", "append", "fail", "skip"]),
    default="replace",
    help=(
        "What to do when --target already holds data: 'replace' (drop and rewrite, default), "
        "'append' (add to it), 'fail' or 'skip'. Not every sink takes every value: files refuse "
        "'append', and InfluxDB refuses 'fail' and 'skip' and accumulates under both of the "
        "others, nothing there clearing a measurement. Default: replace"
    ),
)
# the one spelling, for every command that writes JSON: `--pretty` alone turns it on, and `--pretty=false`
# and `--pretty=true` still say it outright, as `stations`, `values` and `history` took it before and
# `interpolate` and `summarize` did not (GH-2635)
pretty_opt = _bool_opt(
    "--pretty",
    default=False,
    help="Pretty-print JSON with 4-space indentation, as REST's pretty=true. Default: false",
)
with_metadata_opt = _bool_opt(
    "--with-metadata",
    default=False,
    help=(
        "Add the units, the aggregation and timestamp position of the parameters and the quality flags to "
        "the metadata block of JSON/GeoJSON output, "
        "which is always there. Default: false"
    ),
)
# for the commands that write a result to a `--target`: it reaches the file as `to_target(..., with_metadata=True)`
with_metadata_target_opt = _bool_opt(
    "--with-metadata",
    default=False,
    help=(
        "Add the units, the aggregation and timestamp position of the parameters and the quality flags to "
        "the metadata block of JSON/GeoJSON output, "
        "which is always there. With a file --target it writes the block beside the file as "
        "<file>.metadata.json (CSV, Excel, JSON, GeoJSON and the other bare types) and adds those parts to the "
        "block in a Parquet, NetCDF or Zarr file; a database --target is refused. Default: false"
    ),
)
with_stations_opt = _bool_opt(
    "--with-stations",
    default=False,
    help="Include the stations in JSON/GeoJSON output. Default: false",
)
# of `interpolate` and `summarize`, whose stations are the ones the rows were made from
with_estimate_stations_opt = _bool_opt(
    "--with-stations",
    default=False,
    help=(
        "Include in JSON output the stations used, one entry per dataset, with their distance from the point (km) and "
        "elevation difference to it (m; null if the point has no elevation). The rows' ids say which gave a value. "
        "GeoJSON always lists them. Default: false"
    ),
)
_debug_only_opt = _bool_opt("--debug", default=False, help="Log at debug level. Default: false")
_quiet_opt = _bool_opt(
    "--quiet",
    default=False,
    help="Log errors and warnings about the answer only: no progress. Not with --debug. Default: false",
    expose_value=False,
    callback=_remember_quiet,
)


def debug_opt(command: _CommandT) -> _CommandT:
    """Give a command `--debug` and `--quiet`, the two ends of how much it logs; `restapi` has `--debug` alone."""
    return _debug_only_opt(_quiet_opt(command))


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
    "--use-nearby-station-distance",
    type=click.FLOAT,
    default=1,
    help=(
        "Use a station's own values when it is within this many km of the point. "
        "Default: WD_TS_GEO_USE_NEARBY_STATION_DISTANCE if set, else 1"
    ),
)
min_gain_of_value_pairs_opt = click.option(
    "--min-gain-of-value-pairs",
    type=click.FloatRange(min=0),
    default=0.1,
    help=(
        "Minimum relative gain in value pairs required to add another station. "
        "Default: WD_TS_GEO_MIN_GAIN_OF_VALUE_PAIRS if set, else 0.1"
    ),
)
num_additional_stations_opt = click.option(
    "--num-additional-stations",
    type=click.IntRange(min=0),
    default=3,
    help=(
        "Number of additional nearby stations to consider. Default: WD_TS_GEO_NUM_ADDITIONAL_STATIONS if set, else 3"
    ),
)


def station_distance_opts(kind: str) -> Callable[[_CommandT], _CommandT]:
    """Apply the `--<kind>_station_distance*` options, which each estimating command names after itself."""
    options = [
        click.option(
            f"--{kind}-station-distance",
            type=click.STRING,
            help=(
                "Per-parameter maximum station distance in km as JSON, overriding the radii. "
                'Example: {"precipitation_amount":10}'
            ),
        ),
        click.option(
            f"--{kind}-station-distance-homogeneous",
            type=click.FLOAT,
            help="Maximum station distance in km for a parameter that varies slowly, such as air temperature. "
            "Default: WD_TS_GEO_STATION_DISTANCE_HOMOGENEOUS if set, else 40",
        ),
        click.option(
            f"--{kind}-station-distance-heterogeneous",
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


_PROVIDERS_HINT = "`wetterdienst about providers` lists the available ones."


def get_api(provider: str, network: str) -> type[TimeseriesRequest] | StandaloneRequest:
    """Get API for provider and network, of a standalone network (dwd/radar, dwd/alerts) too.

    A provider or network that does not exist is the command line's mistake, so it is a usage error
    naming where the existing ones are listed, as the REST API answers it with a 404 and that hint.
    """
    from wetterdienst.ui.core import resolve_network

    try:
        return resolve_network(provider, network)
    except ApiNotFoundError as e:
        msg = f"{e} {_PROVIDERS_HINT}"
        raise click.UsageError(msg) from e


def get_timeseries_api(provider: str, network: str, *, history: bool = False) -> type[TimeseriesRequest]:
    """Get the API of a network the timeseries commands serve, refusing one they cannot.

    A standalone network (dwd/radar, dwd/alerts) or, with `history`, a network without station
    history is the command line's mistake, so a usage error naming the cause, as the REST API answers
    it with a 404.
    """
    from wetterdienst.ui.core import check_timeseries_api

    api = get_api(provider, network)
    try:
        return check_timeseries_api(api, provider, network, history=history)
    except ApiNotFoundError as e:
        msg = f"{e} {_PROVIDERS_HINT}"
        raise click.UsageError(msg) from e
    except NotImplementedError as e:
        raise click.UsageError(str(e)) from e


def _lead_time_named(lead_time: str | None) -> str | None:
    """Give the lead time the caller named on the command line, and None for the `short` the option defaults to.

    The option defaults to `short`, which is what a DMO request reads where none is named; passed on as if it were
    named, a request said it had asked for `short` (`parameter-without-rows` names what was asked for).
    """
    context = click.get_current_context()
    return None if context.get_parameter_source("lead_time") is ParameterSource.DEFAULT else lead_time


def _validate_request(model: type[_RequestT], values: dict[str, Any]) -> _RequestT:
    """Build a request model, reporting a rejected value as a usage error rather than a traceback.

    Every field here comes from a command option, so a validation error is the user's input being
    out of range -- a negative distance, say -- not a bug to show a stack trace for. It is told in
    click's terms, by the options involved, as click tells its own errors.
    """
    from pydantic import ValidationError

    try:
        return model.model_validate(values)
    except ValidationError as e:
        ctx = click.get_current_context()
        raise click.UsageError(_describe_validation_error(e, ctx), ctx=ctx) from e


def _build_options(options: dict[str, tuple[str, Any]]) -> Options:
    """Build a command's options from the environment and the options given on the command line.

    `options` maps each command line option's parameter to the option of `Options` it sets and the
    value it sets it to. An option is passed only when given on the command line: an argument
    outranks the environment, so passing its default would hide the `WD_TS_*` variable set for it.

    An option given replaces the variable set for it, whatever that is: a malformed variable an
    option outranks is not read. A dict an option gives -- the unit targets, the station distances --
    is merged into the one the environment sets instead, so the environment's must be valid. Should
    the options fail, an error in what the environment sets is raised as it is: a malformed `WD_TS_*`
    variable is not the command line's to fix. The options' is told by the option as click tells an
    invalid value, with the value the option gave rather than the one merged with the environment's.
    """
    from pydantic import ValidationError

    from wetterdienst.options import Options
    from wetterdienst.ui.core import PLAUSIBILITY_OPTIONS, overlay_options

    ctx = click.get_current_context()
    # each option given by the command line option that sets it
    given = {
        option: (param, value)
        for param, (option, value) in options.items()
        if ctx.get_parameter_source(param) is not ParameterSource.DEFAULT
    }
    # a dict, and the mode of a plausibility check, which lays itself over the modes the environment sets
    merged_kinds = [
        option for option, (_, value) in given.items() if isinstance(value, dict) or option in PLAUSIBILITY_OPTIONS
    ]
    replacing = {option: value for option, (_, value) in given.items() if option not in merged_kinds}
    merging = {option: value for option, (_, value) in given.items() if option in merged_kinds}
    try:
        # the environment is read here for what no option replaces
        built = Options(**replacing)
    except ValidationError as e:
        _raise_unless_options(e, replacing)
        raise _options_usage_error(e, given, ctx) from e
    if not merging:
        return built
    try:
        return overlay_options(built, merging)
    except ValidationError as e:
        _raise_unless_options(e, merging)
        raise _options_usage_error(e, given, ctx) from e


def _raise_unless_options(error: ValidationError, given: Mapping[str, Any]) -> None:
    """Raise the error as it is where some of its problems are not with the options given, but the environment's."""
    if any(not problem["loc"] or problem["loc"][0] not in given for problem in error.errors(include_url=False)):
        raise error


def _options_usage_error(
    error: ValidationError,
    given: Mapping[str, tuple[str, Any]],
    ctx: click.Context,
) -> click.UsageError:
    """Tell the problems with the options given by the command line option that gave each."""
    params = {param.name: param for param in ctx.command.params if param.name}
    lines = []
    for problem in error.errors(include_url=False):
        param, value = given[str(problem["loc"][0])]
        # an entry within a dict is the option's, the environment's being valid on their own
        input_ = value if len(problem["loc"]) == 1 else problem["input"]
        lines.append(_describe_problem({**problem, "loc": (param, *problem["loc"][1:]), "input": input_}, params, ctx))
    return click.UsageError("\n".join(lines), ctx=ctx)


def _describe_validation_error(error: ValidationError, ctx: click.Context) -> str:
    """Tell a request model's validation errors as click tells its own, a line each.

    The model reports a rule over several fields -- which stations to select -- by its type, the
    field it is located at and, in `ctx`, the other fields involved; each is named here by its
    option. pydantic's echo of the whole input is left out, which for such a rule is every option
    the command took.
    """
    from wetterdienst.ui.core import describe_fields, join_names

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
        # the alternatives are named, as the model names them to the REST API and MCP
        one_of = next(problem["ctx"]["one_of"] for problem in problems if problem["type"] == "mutually_exclusive")
        alternatives = describe_fields(one_of, lambda field: _option_hint(field, params, ctx))
        lines.insert(0, f"Options {options} cannot be used together, give exactly one of {alternatives}.")
    return "\n".join(lines)


def _option_hint(field: str, params: dict[str, click.Parameter], ctx: click.Context) -> str:
    """Name a field by its option, quoted as click quotes one in an error."""
    return params[field].get_error_hint(ctx) if field in params else repr(field)


def _describe_problem(problem: ErrorDetails, params: dict[str, click.Parameter], ctx: click.Context) -> str:
    """Tell one validation error in click's terms: a missing option, or an invalid value for one."""
    from wetterdienst.ui.core import describe_fields, join_names

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
    from wetterdienst.ui.core import join_names

    ctx = click.get_current_context()
    hints = {param.name: param.get_error_hint(ctx) for param in ctx.command.params}
    made = [hints[name] for name, is_set in given.items() if is_set]
    if not made:
        msg = f"Missing option: one of {join_names([hints[name] for name in given], last='or')}."
        raise click.UsageError(msg, ctx)
    if len(made) > 1:
        msg = (
            f"Options {join_names(made)} cannot be used together, "
            f"give exactly one of {join_names([hints[name] for name in given], last='or')}."
        )
        raise click.UsageError(msg, ctx)


def _resolve_timestamp(timestamp: str | None, start: str | None, end: str | None) -> str | None:
    """Resolve the timestamp from either --timestamp or the --start/--end pair.

    If only --end is given, it is treated as a single-point date (start == end).
    Raises click.UsageError when conflicting options are supplied.
    """
    if timestamp and (start or end):
        msg = "Use either --timestamp or --start / --end, not both."
        raise click.UsageError(msg)
    if start or end:
        first = start or end
        last = end or start
        return f"{first}/{last}" if first != last else first
    return timestamp


# the top-level help is an overview and nothing more: each command's options are in its own help,
# generated from the options themselves, and its examples in its epilog. The page this replaces
# restated every option by hand, and named several that no longer existed (GH-2021)
wetterdienst_help = """\
Weather, climate and hydrology data from national weather services, in one interface.

A typical session finds a provider's network, then a station, then reads its data:

\b
    wetterdienst about providers
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl --name=Dresden-Klotzsche
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --stations=01048 --timestamp=2020-05

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
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl --stations=1048,4411
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl --name=Dresden

    # the five stations closest to a point, or those within 25 km of it
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl \
        --latitude=49.9195 --longitude=8.9671 --rank=5
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl \
        --latitude=49.9195 --longitude=8.9671 --distance=25

    # only the stations with a record in a window, so the closest are not ones that closed long ago
    wetterdienst stations --provider=dwd --network=observation --parameters=daily/kl \
        --latitude=49.9195 --longitude=8.9671 --rank=5 --timestamp=2020-05

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
    wetterdienst history --provider=dwd --network=observation --parameters=daily/kl --stations=1048

    # only the name and geography sections
    wetterdienst history --provider=dwd --network=observation --parameters=daily/kl --stations=1048 \
        --sections=name,geography
"""

VALUES_EXAMPLES = r"""
    # recent daily climate summaries for two stations, or for one found by name
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent \
        --stations=1048,4411
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent \
        --name=Dresden-Hosterwitz

    # a date covers everything it names: a day, a month, a year
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl \
        --timestamp=2020-05-01 --stations=1048
    wetterdienst values --provider=dwd --network=observation --parameters=monthly/kl \
        --timestamp=2020-05 --stations=1048
    wetterdienst values --provider=dwd --network=observation --parameters=annual/kl \
        --timestamp=2019 --stations=1048,4411

    # a range, as an ISO 8601 interval or as --start/--end; historical and recent data are joined
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl \
        --timestamp=1969-01-01/2020-06-11 --stations=1048
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl \
        --start=2020-05-01 --end=2020-05-05 --stations=1048

    # two parameters from different datasets, hourly, one column each
    wetterdienst values --provider=dwd --network=observation \
        --parameters=hourly/precipitation/precipitation_amount,hourly/air_temperature/temperature_air_2m \
        --timestamp=2020-06-15T12/2020-06-16T12 --stations=1048,4411 --shape=wide

    # the days with a wind gust above 20 m/s, one row per value or, filtering on the column, one per day
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent \
        --stations=1048,4411 --sql-values="parameter='wind_gust_max' AND value > 20.0"
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent \
        --stations=1048,4411 --shape=wide --sql-values="wind_gust_max > 20.0"

    # the five stations closest to a point that have data for the date
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl \
        --latitude=49.9195 --longitude=8.9671 --rank=5 --timestamp=2020-06-30

    # keep a number a plausibility check finds implausible, flagged `suspect:range`, instead of nulling it
    wetterdienst values --provider=dwd --network=observation --parameters=hourly/moisture/pressure_air_site \
        --stations=1048 --timestamp=2024-01 --plausibility-range=soft --plausibility-stuck=hard

    # null a temperature outside -30 to 45 degrees (in the unit asked for) and a daily rain above 200 mm, keeping what
    # the source wrote as `rejected:limits,raw:<number>`; `--plausibility-limits=soft` keeps the value and flags it
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl \
        --stations=1048 --timestamp=2024-01 --limits=temperature_air_mean_2m=-30:45 --limits=precipitation_amount=:200

    # MOSMIX and DMO forecasts
    wetterdienst values --provider=dwd --network=mosmix --parameters=hourly/large/ttt,hourly/large/ff --stations=65510
    wetterdienst values --provider=dwd --network=dmo --parameters=hourly/icon/ttt --stations=65510 --lead-time=long

    # export to a file or a database
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent \
        --stations=1048,4411 --target=file://observations.parquet
    wetterdienst values --provider=dwd --network=observation --parameters=daily/kl --periods=recent \
        --stations=1048,4411 --target="duckdb:///observations.duckdb?table=weather"
"""

INTERPOLATE_EXAMPLES = r"""
    # daily precipitation where a station stands, from the stations around it
    wetterdienst interpolate --provider=dwd --network=observation \
        --parameters=daily/climate_summary/precipitation_amount --timestamp=2020-06-30 --station=01048

    # the same for a point
    wetterdienst interpolate --provider=dwd --network=observation \
        --parameters=daily/climate_summary/precipitation_amount --timestamp=2020-06-30 \
        --latitude=49.9195 --longitude=8.9671
"""

SUMMARIZE_EXAMPLES = r"""
    # daily precipitation where a station stands, from the nearest station with a value
    wetterdienst summarize --provider=dwd --network=observation \
        --parameters=daily/climate_summary/precipitation_amount --timestamp=2020-06-30 --station=01048

    # the same for a point
    wetterdienst summarize --provider=dwd --network=observation \
        --parameters=daily/climate_summary/precipitation_amount --timestamp=2020-06-30 \
        --latitude=49.9195 --longitude=8.9671
"""

COVERAGE_EXAMPLES = r"""
    # the resolutions, datasets and parameters of one network, or of part of it
    wetterdienst about coverage --provider=dwd --network=observation
    wetterdienst about coverage --provider=dwd --network=observation --resolutions=1_minute
    wetterdienst about coverage --provider=dwd --network=observation --datasets=climate_summary
"""

AUTH_EXAMPLES = r"""
    # whether the credentials this installation holds for a provider are present and accepted
    wetterdienst about auth --provider=aemet --network=observation

    # a network that needs none is configured and valid without a request
    wetterdienst about auth --provider=dwd --network=observation
"""

RESTAPI_EXAMPLES = r"""
    # listen on http://127.0.0.1:7890; with the mcp extra, it also serves MCP at /mcp/v1 (and /mcp)
    wetterdienst restapi

    # listen on every interface, and reload on source changes
    wetterdienst restapi --listen=0.0.0.0:8890 --reload
"""

RADAR_EXAMPLES = r"""
    wetterdienst radar --all
    wetterdienst radar --dwd
    wetterdienst radar --country-name=france
    wetterdienst radar --odim-code=deasb
    wetterdienst radar --wmo-code=10103
"""

ALERTS_EXAMPLES = r"""
    # current warnings per community (Gemeinde), as JSON
    wetterdienst alerts

    # per district (Landkreis), as GeoJSON, in German
    wetterdienst alerts --granularity=district --language=de --format=geojson

    # the warnings active at a past time: replace YYYY-MM-DDTHH:MM with one within the last
    # ~48 hours, all DWD keeps
    wetterdienst alerts --granularity=district --timestamp=YYYY-MM-DDTHH:MM

    # to a GeoJSON file
    wetterdienst alerts --format=geojson --target=file://alerts.geojson
"""

STRIPES_EXAMPLES = r"""
    # warming stripes for a station, by id or by name
    wetterdienst stripes image --kind=temperature --station=1048 > warming_stripes.png
    wetterdienst stripes image --kind=temperature --name=Dresden-Klotzsche --name-threshold=0.7 > warming_stripes.png

    # for the years 2000 to 2020
    wetterdienst stripes image --kind=temperature --station=1048 --start-year=2000 --end-year=2020 \
        > warming_stripes.png

    # precipitation stripes, to a file
    wetterdienst stripes image --kind=precipitation --station=1048 --target=precipitation_stripes.png
"""


def _refuse_if_callers(e: Exception, request: BaseModel) -> None:
    """Raise a failure caught from a request as a usage error if it is the caller's own mistake.

    Also the one place the catch-alls below tell a provider whose credential is missing, which is
    the environment's lack and no mistake of the command line's, as the last paragraph says.

    A refusal the caller can rephrase -- a `RequestError` or a `NotFoundError`, which the REST API
    answers with a 400 or a 404 -- is told in one line, exit 2, as a mistyped option is (GH-2426).
    Anything else -- an upstream failure or a defect -- is left to the handler, and keeps its
    traceback and exit 1.

    A request refuses a window that ends before it starts, or one that a dataset needs and is not
    given, in terms of its `start` and `end`, which the command line spells `--timestamp` or
    `--start` / `--end`.

    An optional dependency that is not installed (`MissingDependencyError`) is the environment's to
    fix, not the command line's: it is let through, to `_Cli.invoke`, which prints its message -- what
    to install -- as the one line it is, exit 1. So is a provider that could not be reached
    (`NoInternetError`), whose message names the URL (GH-2640).

    A provider that needs a credential none is configured for, or whose credential it rejected, is
    told in one line, exit 1: the message names the setting to change, which is what the person at
    the command line can do, and the command line was right, so it is no usage error (GH-2665).
    """
    from wetterdienst.ui.core import _is_caller_refusal

    if isinstance(e, (MissingDependencyError, NoInternetError)):
        raise e
    if isinstance(e, (CredentialMissingError, CredentialRejectedError)):
        raise click.ClickException(str(e)) from e
    if not _is_caller_refusal(e, request):
        return
    if isinstance(e, ReversedTimeIntervalError):
        msg = "the interval in --timestamp or --start / --end ends before it starts"
        raise click.UsageError(msg) from e
    if isinstance(e, DateRequiredError):
        msg = "--timestamp or --start / --end is required for this dataset"
        raise click.UsageError(msg) from e
    raise click.UsageError(str(e)) from e


def _collect_or_exit(
    get: Callable[..., Any],
    *,
    api: Any,  # noqa: ANN401
    request: Any,  # noqa: ANN401
    settings: Settings,
    options: Options,
    what: str,
) -> Any:  # noqa: ANN401
    """Run one of the values getters, reporting the failures a caller can do something about.

    Two kinds can be acted on rather than debugged: an optional reader that is not installed, and a
    request the caller can rephrase. Each is a sentence the caller needs and a traceback buries, so
    each is printed and nothing else. A request to rephrase -- one this provider cannot serve as
    phrased, a point an estimate cannot be made at (beyond the latitudes UTM covers, or a station
    without a position), or any refusal the REST API answers with a 4xx -- is the command line's
    mistake, so it is a usage error, exit 2 (GH-2426).

    A window that holds no readings is not one of them: it is an answer, as REST's 200 is. It comes back
    empty, and `_finish` says so and writes what REST would send.
    """
    try:
        return get(api=api, request=request, settings=settings, options=options)
    except MissingDependencyError as e:
        # the message names what to install: the whole of what is to be done about it. Narrow on
        # purpose -- a bare `ImportError` would swallow a cycle or a typo inside a provider module,
        # which is a defect and wants its traceback, not an instruction. The command line was right,
        # the environment lacks the reader, so this is exit 1 rather than a usage error
        log.error(str(e))  # noqa: TRY400
        sys.exit(1)
    except Exception as e:
        _refuse_if_callers(e, request)
        if not isinstance(e, ValueError):
            # not caught here: click re-raises it, and Python prints its traceback and exits 1
            raise
        log.exception(f"Error during {what}")
        sys.exit(1)


def _echo(output: str | bytes) -> None:
    """Write a rendered result to stdout: text as a line, a chart's image as the bytes it is.

    `print` wrote the image as its `repr`, `b'<svg ...'`, where the REST API sends the bytes.
    """
    click.echo(output, nl=isinstance(output, str))


def _finish(
    values_: Any,  # noqa: ANN401
    request: Any,  # noqa: ANN401
    applied: Any,  # noqa: ANN401
    options: Options,
    *,
    target: str | None,
    if_exists: str,
) -> None:
    """Write a values result to its target or to stdout, as REST sends it, and say so where it is empty.

    An empty result is exit 0: the sentence goes to stderr, and stdout gets what the REST API answers
    with (the result's empty JSON, or the header of its CSV) -- the command line renders through the
    one function the REST API does, so `--with-metadata` gives the `settings` block here as there
    (GH-2635). A target is left as it is, since nothing is there to write: replacing a table with an
    empty one is not what a schedule that found no reading yet is after.
    """
    from wetterdienst.ui.render import render

    # the sums of the warnings that count something, which only the answer's metadata carries otherwise
    # the sums of the warnings that count something, which only the answer's metadata carries otherwise
    log_counted_warnings(log)
    empty = values_.df.is_empty()
    if empty:
        log.warning(NO_DATA)
    if target:
        if empty:
            log.warning(NOTHING_WRITTEN, extra=_NOTHING_WRITTEN_RECORD)
            return
        _export_or_exit(values_, target, if_exists, with_metadata=request.with_metadata)
        return
    _echo(render(values_, request, applied, options))


def _export_or_exit(result: Any, target: str, if_exists: str, *, with_metadata: bool = False) -> None:  # noqa: ANN401
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

    `--with-metadata` goes to `to_target` as it is: a file target gets `<file>.metadata.json` beside it, or the
    heavy parts in the block of a Parquet, NetCDF or Zarr file, and a database target is refused (GH-3704).
    """
    try:
        result.to_target(target, if_exists=if_exists, with_metadata=with_metadata)
    except (ExportRefusedError, MissingDependencyError) as e:
        # a refusal, or a sink whose package is not installed: the message is the whole of it
        log.error(str(e))  # noqa: TRY400
        sys.exit(1)
    except Exception:
        log.exception(f"Failed to export to {redact_password(target)}")
        sys.exit(1)


def _refuse_database_metadata(target: str | None, *, with_metadata: bool) -> None:
    """Refuse `--with-metadata` with a database `--target`, before the fetch (GH-3711).

    The metadata goes beside a file, and a database has none: the refusal depends on the target's scheme and the
    flag alone, so it is told at once, where `to_target` would tell it after the whole request was downloaded. It
    is told for an empty result too, which is never written: the combination is invalid whatever the data.
    """
    if not (target and with_metadata):
        return
    from wetterdienst.io.sinks import refuse_metadata_without_file

    try:
        refuse_metadata_without_file(target, ConnectionString(target))
    except ValueError:
        # a target `urlparse` cannot read (`duckdb://[x/obs.duckdb`): the export tells it, as it always did
        return
    except ExportRefusedError as e:
        log.error(str(e))  # noqa: TRY400
        sys.exit(1)


def _target_path(target: str) -> str:
    """Give the path a `--target` names, or tell it cannot name one: a NUL (`%00`) is in no file name, exit 1.

    Told before the fetch, as the other refusals of a target are for `history` and `alerts`, which write the file
    themselves.
    """
    try:
        return file_target_path(target)
    except ExportRefusedError as e:
        raise click.ClickException(str(e)) from e


def _alerts_target(target: str | None, fmt: str, *, with_metadata: bool) -> str | None:
    """Check the `--target` of `alerts` before the fetch and give it as `to_target` takes it, a `file://` URI.

    The extension decides what is written, as it does for `stations` and `values`, so an explicit `--format` that
    names another format is a usage error instead of one of the two silently winning. `--with-metadata` writes beside
    a file, and the JSON and GeoJSON on stdout carry the block always, so it needs a `--target`.

    Raises:
        click.BadParameter: An extension of none of the three, or a `--format` that disagrees with it.
        click.UsageError: `--with-metadata` without `--target`.

    """
    from wetterdienst.io.sinks import ALERT_FILE_FORMATS

    if not target:
        if with_metadata:
            msg = (
                "--with-metadata writes <file>.metadata.json beside the --target file, so it needs --target; "
                "the JSON and GeoJSON on stdout carry the metadata block always"
            )
            raise click.UsageError(msg)
        return None
    path = _target_path(target)
    extension = next((ext for ext in ALERT_FILE_FORMATS if path.lower().endswith(ext)), None)
    if extension is None:
        msg = (
            f"{path!r} is none of the files alerts are written as ({', '.join(ALERT_FILE_FORMATS)}): the extension "
            "decides the format. Leave out --target to write to stdout"
        )
        raise click.BadParameter(msg, param_hint="--target")
    context = click.get_current_context()
    if (
        context.get_parameter_source("fmt") is not ParameterSource.DEFAULT
        and fmt.lower() != ALERT_FILE_FORMATS[extension]
    ):
        msg = (
            f"--format={fmt.lower()} does not match {extension}, which is written as "
            f"{ALERT_FILE_FORMATS[extension]}: the extension decides what --target holds"
        )
        raise click.BadParameter(msg, param_hint="--format")
    # a file named without the scheme is read as a path, `%` and all: only the two characters the URI reads are written
    # as it reads them, and the rest, a name that is not UTF-8 included (`quote` raises on its surrogates), as it is
    return target if target.startswith("file://") else "file://" + path.replace("%", "%25").replace("?", "%3F")


def _refuse_non_file_target(target: str | None, command: str) -> None:
    """Refuse a --target with a scheme other than `file://`, for a command that writes plain text.

    `history` writes its output with `Path.write_text`, and `alerts` through a `to_target` that takes files only
    (GH-3706), not the timeseries commands' one, so only a local path or a `file://` URI is a target they can
    write. Called before
    the fetch, so that `s3://...` or `duckdb://...` is a usage error at once, rather than a write to
    the path read off the URI (`s3:/bucket/...`) that fails once the whole fetch has run.
    """
    if target and "://" in target and not target.startswith("file://"):
        msg = f"--target only supports a local path or a file:// URI for {command}."
        raise click.BadParameter(msg)


def _route_of(ctx: click.Context) -> str:
    """Name the route a command is, as its MCP tool is: `stations`, `stripes_image`, `coverage` for `about coverage`."""
    names = []
    while ctx.parent is not None:
        names.append(ctx.info_name or "")
        ctx = ctx.parent
    return "_".join(name for name in reversed(names) if name != "about")


def _renamed_to(command: click.Command, option: str, route: str) -> str | None:
    """Tell the option a renamed one is now spelled, where the rename is mechanical, else None.

    An option was renamed for 1.0 if the command has it with its underscores as hyphens
    (`--convert_units`, now `--convert-units`) or in the plural (`--station`, now `--stations`): the
    spellings a command line is free to mistake for the new one, and the only ones it can have kept.
    Either is a rename only on a route that had the old spelling in 0.139.0 (`OLD_NAMES_OF_ROUTE`,
    `OLD_UNDERSCORE_OPTIONS_OF_ROUTE`): `about providers` never had `--dataset`, nor `stations` `--date`
    or `--name_threshold`.
    """
    # a hidden option is itself a refusal, such as `--start-date`, and no name to send the caller to
    taken = {
        opt
        for param in command.params
        if not getattr(param, "hidden", False)
        for opt in (*param.opts, *param.secondary_opts)
    }
    # only a mistyped option gets here, so only a mistyped option waits for the table of what was renamed to import
    from wetterdienst.ui.core import RENAMED_REQUEST_PARAMETERS, old_names_of_route, old_underscore_options_of_route

    name = option.removeprefix("--")
    # the plural is the rename of the singular a list had, not of any word a typo is one letter short of
    plural = f"{option}s" if name in RENAMED_REQUEST_PARAMETERS and name in old_names_of_route(route) else None
    hyphenated = option.replace("_", "-") if name in old_underscore_options_of_route(route) else None
    candidates = (hyphenated, plural)
    return next((candidate for candidate in candidates if candidate != option and candidate in taken), None)


class _Command(click.Command):
    """A command refusing an option it no longer has by naming the one that replaces it (GH-2561).

    Click would say only that the command has no such option, and guess a similar one by its
    spelling. The old spelling is refused, not read: a rename for 1.0 is a hard one.
    """

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        try:
            return super().parse_args(ctx, args)
        except click.NoSuchOption as e:
            renamed = _renamed_to(self, e.option_name, _route_of(ctx))
            if renamed is None:
                # click guesses among every option the command registered, the hidden refusals too (GH-3167): one
                # of them as a suggestion would send the caller to an option that says it was renamed
                refused = {opt for param in self.params if getattr(param, "hidden", False) for opt in param.opts}
                possibilities = [option for option in e.possibilities or () if option not in refused]
                raise click.NoSuchOption(e.option_name, e.message, possibilities, e.ctx) from e
            msg = f"{e.option_name} was renamed to {renamed}."
            raise click.UsageError(msg, ctx) from e


class _CoverageCommand(_Command):
    """`about coverage`, which says what to call instead where it is given no provider or network (GH-3996).

    It listed every provider and network before 1.0.0; that is `about providers` now. Click would say only
    that the option is missing, which tells a caller of the old form nothing.
    """

    def parse_args(self, ctx: click.Context, args: list[str]) -> list[str]:
        try:
            return super().parse_args(ctx, args)
        except click.MissingParameter as e:
            from wetterdienst.ui.core import coverage_needs_a_network

            raise click.UsageError(coverage_needs_a_network("`wetterdienst about providers`"), ctx) from e


class _Group(click.Group):
    """A group of commands that refuse a renamed option by its new name."""

    command_class = _Command


class _Cli(_Group):
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
        except MissingDependencyError as e:
            # whatever the command was doing when it reached for a package that is not installed,
            # such as rendering an image: the message names what to install, and is the whole of it
            log.error(str(e))  # noqa: TRY400
            sys.exit(1)
        except ImageTimeoutError as e:
            # whatever image the command was drawing: the browser did not finish, and was closed. One line, as
            # for an outage, where a traceback says nothing the line does not (GH-3723)
            log.error(str(e))  # noqa: TRY400
            sys.exit(1)
        except NoInternetError as e:
            # whatever the command was fetching: no connection to the provider could be made, which
            # is told in the one line it is, naming the URL, and not as a traceback. An empty result
            # would be exit 0, and would not say why (GH-2640)
            log.error(str(e))  # noqa: TRY400
            sys.exit(1)
        except Exception as e:
            # Only what pydantic's classes are told apart by is looked at, and only if they are imported: an error
            # that cannot be pydantic's is not the settings' (`--help`, `--version` and a usage error come through
            # here without it: GH-3809), and importing the settings here would run an import that failed in the
            # command again and show its error twice
            pydantic_core = sys.modules.get("pydantic_core")
            pydantic_settings = sys.modules.get("pydantic_settings")
            settings = sys.modules.get("wetterdienst.settings")
            options = sys.modules.get("wetterdienst.options")
            if pydantic_core is None or pydantic_settings is None or settings is None:
                raise
            if not isinstance(e, (pydantic_core.ValidationError, pydantic_settings.SettingsError)):
                raise
            # another model's error is not the settings', even beside a malformed variable an
            # option overrode
            titles = {settings.Settings.__name__, *([options.Options.__name__] if options else [])}
            if isinstance(e, pydantic_core.ValidationError) and e.title not in titles:
                raise
            problems = settings.check_settings()
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
@click.pass_context
def cli(ctx: click.Context) -> None:
    """Command line interface for the Wetterdienst package."""
    setup_logging()
    if no_color():
        # nothing here styles its output, but click does for what it writes itself (the deprecation of a command or an
        # option is red): with NO_COLOR it strips every escape code from what `click.echo` writes, on a terminal too
        ctx.color = False


@cli.command("cache")
def cache() -> None:
    """Display cache location."""
    from wetterdienst import Settings

    print(Settings().cache_dir)  # noqa: T201


@cli.command("info")
def info() -> None:
    """Display project information."""
    from wetterdienst import Info

    print(Info())  # noqa: T201


@cli.command("restapi", epilog=_examples(RESTAPI_EXAMPLES))
@click.option("--listen", type=click.STRING, default=None, help="Listen address as host:port. Default: 127.0.0.1:7890")
@_bool_opt(
    "--reload", default=False, help="Reload the service when a source file changes, for development. Default: false"
)
@_debug_only_opt
def restapi(
    listen: str,
    reload: bool,  # noqa: FBT001
    debug: bool,  # noqa: FBT001
) -> None:
    """Start the Wetterdienst REST API web service."""
    _apply_log_level(debug=debug)

    # Run HTTP service.
    log.info(f"Starting {appname}")
    log.info(f"Starting HTTP web service on http://{listen}")

    restapi_module = import_optional("wetterdienst.ui.restapi", "The REST API", extra="restapi")

    restapi_module.start_service(listen, reload=reload)


@cli.group(cls=_Group)
def about() -> None:
    """Get information about the data."""


@about.command(cls=_CoverageCommand, epilog=_examples(COVERAGE_EXAMPLES))
@provider_opt
@network_opt
@click.option(
    "--resolutions",
    type=click.STRING,
    help="Only these resolutions, comma-separated. Example: daily,hourly",
)
@click.option(
    "--datasets",
    type=click.STRING,
    help="Only these datasets, comma-separated. Example: climate_summary",
)
@debug_opt
def coverage(
    provider: str,
    network: str,
    resolutions: str,
    datasets: str,
    debug: bool,  # noqa: FBT001
) -> None:
    """Get the resolutions, datasets and parameters of one network.

    --provider and --network are required; `about providers` lists the providers and their networks, with
    their `kind` (`observation`, `forecast` or `derived` for a timeseries network, which has stations and
    values, and `radar` or `alerts` for a standalone one, which `stations` and `values` refuse) and whether
    they need credentials and have them. A parameter's `unit` is the unit its values come
    back in when no unit target is given (the one `about glossary` gives; `degree_celsius`, `percent` for a
    percentage). `unit_source`, the unit the provider publishes it in (`degree_kelvin`, `one_eighth`), is there
    only where it differs from `unit`; absent, it is the same. A unit target of your own changes the values,
    not this answer. `aggregation` is what the value is relative to its interval (`mean`, `max`, `sum`, ...,
    `instant` for a single reading) and `timestamp_position` where its timestamp sits in the row's interval
    (`instant`, `start`, `end`, `middle`); `null` in either: the source does not state it.
    """
    from wetterdienst import Settings
    from wetterdienst.model.request import TimeseriesRequest

    _apply_log_level(debug=debug)

    resolutions_list = read_list(resolutions)
    datasets_list = read_list(datasets)

    api = get_api(provider=provider, network=network)

    # Standalone networks (e.g. dwd/radar, dwd/alerts) have no metadata model and thus no per-network
    # discover(); a usage error, as `/api/coverage` answers it with a 404, not an AttributeError.
    if not issubclass(api, TimeseriesRequest):
        msg = f"Coverage is not available for provider '{provider}' and network '{network}'."
        raise click.UsageError(msg)

    # one network's metadata reads no setting, and a malformed one is told the same as for the other commands,
    # after the usage errors above as in `stations` and `values` (GH-2619)
    Settings()
    try:
        cov = api.discover(
            resolutions=resolutions_list,
            datasets=datasets_list,
        )
    except MetadataNotFoundError as e:
        # a resolution or dataset that does not exist is the command line's mistake, which
        # `/api/coverage` answers with a 404
        raise click.UsageError(str(e)) from e

    print(json.dumps(cov, indent=2))  # noqa: T201


@about.command("providers")
@click.option(
    "--provider",
    type=click.STRING,
    shell_complete=_complete_provider,
    help="Only this provider. Without it, every provider. Example: dwd",
)
@debug_opt
def providers(
    provider: str,
    debug: bool,  # noqa: FBT001
) -> None:
    """List the providers and their networks, and describe what each provider is.

    Per provider: the names it goes by, its country and ISO 3166-1 alpha-2 `country_code`, the terms it publishes
    its data under (`license`, null where it states none), the credit line to cite (`attribution`; the `copyright`
    of a network is the rights holder's notice, for information), and its networks with their `kind`
    (`observation`, `forecast` or `derived` for a timeseries network, which has stations and values; `radar` or
    `alerts` for a standalone one, which `stations` and `values` refuse), `extent`, source `url`, whether they need
    credentials (`auth`) and have them (`configured`), whether a request has to give a date and their number of
    parameters. Nothing is downloaded and no credential is probed. `about coverage` lists the resolutions, datasets
    and parameters of one network.
    """
    from wetterdienst import Settings
    from wetterdienst.ui.core import ProvidersRequest
    from wetterdienst.ui.providers import get_providers

    _apply_log_level(debug=debug)
    begin_response()

    # the listing marks a provider unconfigured where the settings are invalid, but this command tells them,
    # and exits 1, as the listing of every network did (GH-2335)
    Settings()

    request = ProvidersRequest.model_validate({"provider": provider})
    try:
        answer = get_providers(request.provider)
    except ApiNotFoundError as e:
        msg = f"{e} List them with: wetterdienst about providers"
        raise click.UsageError(msg) from e
    print(answer.model_dump_json(indent=2))  # noqa: T201


@about.command("auth", epilog=_examples(AUTH_EXAMPLES))
@provider_opt
@network_opt
@debug_opt
def auth(
    provider: str,
    network: str,
    debug: bool,  # noqa: FBT001
) -> None:
    """Check whether the credentials for a provider and network are present and accepted.

    Prints `{"provider", "network", "auth", "configured", "valid"}`. `auth` is whether the network
    needs credentials, `configured` whether they are present, and `valid` whether the provider
    accepted (true) or rejected (false) them. `valid` is false where they are not configured, and
    null where the check could not tell (no network, a timeout, a rate limit, an outage of the
    provider): unknown, not rejected. A network that needs none is configured and valid.

    This is the one command that probes the provider, for the one network asked about: a single
    attempt that gives up after a few seconds. `about providers` does not probe and has no `valid`, only
    whether the credentials are `configured`. The exit code is 0 whatever `valid` is: read the answer.
    """
    from wetterdienst import Settings

    _apply_log_level(debug=debug)

    # a malformed server setting is refused by its variable, as for the other commands
    Settings()
    api = get_api(provider=provider, network=network)

    print(json.dumps(get_auth(api, provider, network), indent=2))  # noqa: T201


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
    override. `aggregation` is what the name says the value is relative to its interval (`mean`, `max`, `sum`, ...),
    null for a plain name; `coverage` has the one of each parameter of a network.
    """
    from wetterdienst import Settings

    _apply_log_level(debug=debug)

    # a malformed server setting is refused by its variable, as it is for the other commands
    Settings()
    entries = get_glossary(parameter=parameter, unit_type=unit_type, limit=limit)

    if not entries:
        # an empty list is an answer, as `/api/glossary`'s 200 is, and no failure (GH-2635)
        log.warning("No parameter matches the given filters.")

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
    from wetterdienst.provider.dwd.observation import DwdObservationRequest

    _apply_log_level(debug=debug)
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
    except MissingDependencyError:
        # the PDF reader is not installed: the message names what to install, which `_Cli.invoke`
        # prints as the one line it is, not under "Could not retrieve fields." and a traceback
        raise
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
@stations_timestamp_opt
@start_opt
@end_opt
@all_opt
@stations_opt
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
@station_window_end_buffer_opt
@stream_format_opt
@width_opt
@height_opt
@scale_opt
@target_opt
@if_exists_opt
@pretty_opt
@with_metadata_target_opt
@debug_opt
def stations(
    provider: str,
    network: str,
    parameters: list[str],
    periods: list[str],
    timestamp: str,
    start: str,
    end: str,
    all_: bool,  # noqa: FBT001
    stations: list[str],
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
    station_window_end_buffer: int | None,
    fmt: str,
    width: int | None,
    height: int | None,
    scale: float | None,
    target: str,
    if_exists: Literal["replace", "append", "fail", "skip"],
    pretty: bool,  # noqa: FBT001
    with_metadata: bool,  # noqa: FBT001
    debug: bool,  # noqa: FBT001
) -> None:
    """Acquire stations.

    Select them with exactly one of --all, --stations, --name, --latitude/--longitude with --rank or
    --distance, --left/--bottom/--right/--top, or --sql. Given a window, with --timestamp or --start /
    --end, only the stations whose record overlaps it are listed.

    A selection that finds no station is no failure: the list is empty, the command says so on stderr
    and exits 0. A station id of --stations the network has no station for is named in a warning and left out.
    """
    from wetterdienst import Settings
    from wetterdienst.ui.core import StationsRequest, limit_stations_to_rank, limit_stations_to_window
    from wetterdienst.ui.render import render_stations

    timestamp_resolved = _resolve_timestamp(timestamp, start, end)
    request = _validate_request(
        StationsRequest,
        {
            "provider": provider,
            "network": network,
            "parameters": parameters,
            "periods": periods,
            "timestamp": timestamp_resolved,
            "all": all_,
            "stations": stations,
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
            "station_window_end_buffer": station_window_end_buffer,
            "format": fmt,
            "width": width,
            "height": height,
            "scale": scale,
            "pretty": pretty,
            "with_metadata": with_metadata,
        },
    )
    _apply_log_level(debug=debug)
    begin_response()
    _refuse_database_metadata(target, with_metadata=request.with_metadata)

    api = get_timeseries_api(provider=provider, network=network)

    # built outside the catch-all below, so that a malformed `WD_*` setting is told by its variable
    settings = Settings()
    options = _build_options(
        {"station_window_end_buffer": ("station_window_end_buffer", request.station_window_end_buffer)}
    )
    try:
        stations_ = get_stations(
            api=api, request=request, timestamp=request.timestamp, settings=settings, options=options
        )
    except Exception as e:
        # a parameter, bounding box or --sql the caller can rephrase is told in one line, as
        # `/api/stations` answers it with a 400; an upstream failure keeps its traceback
        _refuse_if_callers(e, request)
        log.exception("Failed to get stations.")
        sys.exit(1)

    # a window leaves out the stations that cannot have a reading in it, before a rank keeps the N
    # closest of those that can; a rank filter keeps all stations in the frame, as it is applied
    # lazily during value collection, and a plain listing returns just the N closest asked for
    stations_ = limit_stations_to_rank(limit_stations_to_window(stations_))

    # an empty list is an answer, as REST's 200 is, and no failure: it is said on stderr, and what
    # REST would send is written to stdout (GH-2635)
    empty = stations_.df.is_empty()
    if empty:
        log.warning(NO_STATIONS)

    if target:
        if empty:
            log.warning(NOTHING_WRITTEN, extra=_NOTHING_WRITTEN_RECORD)
            return
        _export_or_exit(stations_, target, if_exists, with_metadata=request.with_metadata)
        return

    _echo(render_stations(stations_, request))


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
    "--lead-time",
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

    A DMO run exists for a product, so --dataset and --lead-time decide which runs are listed. They
    default to what a `values` request defaults to, which is what makes the answer one that request
    accepts.
    """
    from wetterdienst import Settings
    from wetterdienst.ui.core import IssuesRequest
    from wetterdienst.ui.render import render_issues
    from wetterdienst.ui.response_metadata import issues_metadata

    _apply_log_level(debug=debug)
    begin_response()

    api = get_api(provider=provider, network=network)
    request = _validate_request(
        IssuesRequest,
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

    _echo(render_issues(issue_list, issues_metadata(api, request, issue_list), pretty=True))


@cli.command("history", epilog=_examples(HISTORY_EXAMPLES))
@provider_opt
@network_opt
@parameters_opt
@all_opt
@stations_opt
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
    stations: str,
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

    Select the stations with exactly one of --all or --stations.
    """
    from wetterdienst import Settings
    from wetterdienst.ui.core import HistoryRequest
    from wetterdienst.ui.render import render_history

    _refuse_non_file_target(target, "history")
    # a local path, or a `file://` URI read as `alerts` reads it; the `.json` check reads the path it names
    path = _target_path(target) if target else None
    if path is not None and not path.lower().endswith(".json"):
        msg = "--target for history endpoint must end with .json"
        raise click.BadParameter(msg)

    request = _validate_request(
        HistoryRequest,
        {
            "provider": provider,
            "network": network,
            "parameters": parameters,
            "all": all_,
            "stations": stations,
            "sections": sections,
            "with_metadata": with_metadata,
            "with_stations": with_stations,
            "pretty": pretty,
        },
    )

    _apply_log_level(debug=debug)
    begin_response()

    api = get_timeseries_api(provider=provider, network=network, history=True)

    # built outside the catch-all below, so that a malformed `WD_*` setting is told by its variable
    settings = Settings()
    try:
        stations_ = get_stations(api=api, request=request, timestamp=None, settings=settings)
    except Exception as e:
        # a parameter or station the caller can rephrase is told in one line, as `/api/history`
        # answers it with a 400; an upstream failure keeps its traceback
        _refuse_if_callers(e, request)
        log.exception("Failed to get stations for history.")
        sys.exit(1)

    history_provider = stations_.history()

    try:
        output, _ = render_history(stations_, history_provider, request)
    except NoInternetError:
        # told by `_Cli.invoke` in one line
        raise
    except Exception:
        log.exception("Failed to collect station history")
        sys.exit(1)

    if path is not None:
        try:
            Path(path).write_text(output, encoding="utf-8")
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
@timestamp_opt
@renamed_date_opt
@start_opt
@end_opt
@start_date_renamed_opt
@end_date_renamed_opt
@lead_time_opt
@issue_opt
@all_opt
@stations_opt
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
@_bool_opt(
    "--skip-empty",
    default=False,
    help="Skip stations whose coverage falls below --skip-threshold. Default: WD_TS_SKIP_EMPTY if set, else false",
)
@click.option(
    "--skip-criteria",
    type=click.Choice(["min", "mean", "max"]),
    default="min",
    help=(
        "Aggregation over the requested parameters' coverage: min, mean or max. "
        "Default: WD_TS_SKIP_CRITERIA if set, else min"
    ),
)
@click.option(
    "--skip-threshold",
    type=click.FloatRange(min=0, min_open=True, max=1),
    default=0.95,
    help="Coverage fraction below which --skip-empty skips a station. Default: WD_TS_SKIP_THRESHOLD if set, else 0.95",
)
@_bool_opt(
    "--drop-nulls",
    default=True,
    help="Drop rows with null values from the output. Default: WD_TS_DROP_NULLS if set, else true",
)
@station_window_end_buffer_opt
@plausibility_opts
@limits_opt
@stream_format_opt
@width_opt
@height_opt
@scale_opt
@target_opt
@if_exists_opt
@pretty_opt
@with_metadata_target_opt
@with_stations_opt
@debug_opt
def values(
    provider: str,
    network: str,
    parameters: list[str],
    periods: list[str],
    lead_time: Literal["short", "long"],
    timestamp: str,
    start: str,
    end: str,
    issue: str,
    all_: bool,  # noqa: FBT001
    stations: list[str],
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
    width: int | None,
    height: int | None,
    scale: float | None,
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
    station_window_end_buffer: int | None,
    plausibility: Mode | None,
    plausibility_range: Mode,
    plausibility_elevation: Mode,
    plausibility_stuck: Mode,
    plausibility_consistency: Mode,
    plausibility_floor: Mode,
    plausibility_limits: Mode,
    plausibility_source: Mode,
    plausibility_step: Mode,
    plausibility_relations: Mode,
    limits: dict[str, Any] | None,
    pretty: bool,  # noqa: FBT001
    with_metadata: bool,  # noqa: FBT001
    with_stations: bool,  # noqa: FBT001
    debug: bool,  # noqa: FBT001
) -> None:
    """Acquire data.

    Select the stations with exactly one of --all, --stations, --name, --latitude/--longitude with
    --rank or --distance, --left/--bottom/--right/--top, or --sql.
    """
    from wetterdienst import Settings
    from wetterdienst.ui.core import PLAUSIBILITY_OPTIONS, ValuesRequest
    from wetterdienst.ui.render import ValuesSettings, ndjson_refusal

    timestamp_resolved = _resolve_timestamp(timestamp, start, end)
    request = _validate_request(
        ValuesRequest,
        {
            "provider": provider,
            "network": network,
            "parameters": parameters,
            "periods": periods,
            "lead_time": _lead_time_named(lead_time),
            "timestamp": timestamp_resolved,
            "issue": issue,
            "all": all_,
            "stations": stations,
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
            "width": width,
            "height": height,
            "scale": scale,
            "shape": shape,
            "convert_units": convert_units,
            "unit_targets": unit_targets,
            "humanize": humanize,
            "skip_empty": skip_empty,
            "skip_criteria": skip_criteria,
            "skip_threshold": skip_threshold,
            "drop_nulls": drop_nulls,
            "station_window_end_buffer": station_window_end_buffer,
            "plausibility": plausibility,
            "plausibility_range": plausibility_range,
            "plausibility_elevation": plausibility_elevation,
            "plausibility_stuck": plausibility_stuck,
            "plausibility_consistency": plausibility_consistency,
            "plausibility_floor": plausibility_floor,
            "plausibility_limits": plausibility_limits,
            "plausibility_source": plausibility_source,
            "plausibility_step": plausibility_step,
            "plausibility_relations": plausibility_relations,
            "limits": limits,
            "pretty": pretty,
            "with_metadata": with_metadata,
            "with_stations": with_stations,
        },
    )
    _apply_log_level(debug=debug)
    begin_response()
    _refuse_database_metadata(target, with_metadata=request.with_metadata)
    if request.format == "ndjson" and (refusal := ndjson_refusal(request)) is not None:
        raise click.UsageError(refusal)

    api = get_timeseries_api(request.provider, request.network)

    # built first: a malformed host setting is not the command line's to fix, whatever the options say
    settings = Settings()
    # a unit target given for a quantity the unit converter does not know is a usage error
    options = _build_options(
        {
            "humanize": ("humanize", request.humanize),
            "shape": ("shape", request.shape),
            "convert_units": ("convert_units", request.convert_units),
            "unit_targets": ("unit_targets", request.unit_targets or {}),
            "skip_empty": ("skip_empty", request.skip_empty),
            "skip_criteria": ("skip_criteria", request.skip_criteria),
            "skip_threshold": ("skip_threshold", request.skip_threshold),
            "drop_nulls": ("drop_nulls", request.drop_nulls),
            "station_window_end_buffer": ("station_window_end_buffer", request.station_window_end_buffer),
            "plausibility": ("plausibility", request.plausibility),
            **{name: (name, getattr(request, name)) for name in PLAUSIBILITY_OPTIONS},
            "limits": ("limits", request.limits or {}),
        }
    )

    values_ = _collect_or_exit(
        get_values, api=api, request=request, settings=settings, options=options, what="data acquisition"
    )

    _finish(values_, request, ValuesSettings, options, target=target, if_exists=if_exists)


@cli.command("interpolate", epilog=_examples(INTERPOLATE_EXAMPLES))
@provider_opt
@network_opt
@parameters_opt
@periods_opt
@timestamp_opt
@renamed_date_opt
@start_opt
@end_opt
@start_date_renamed_opt
@end_date_renamed_opt
@lead_time_opt
@issue_opt
@reference_station_opt
@latitude_opt
@longitude_opt
@elevation_opt
@station_distance_opts("interpolation")
@min_gain_of_value_pairs_opt
@num_additional_stations_opt
@use_nearby_station_distance_opt
@sql_values_opt
@convert_units_opt
@unit_targets_opt
@humanize_opt
@format_opt
@width_opt
@height_opt
@scale_opt
@target_opt
@if_exists_opt
@pretty_opt
@with_metadata_target_opt
@with_estimate_stations_opt
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
    min_gain_of_value_pairs: float,
    num_additional_stations: int,
    use_nearby_station_distance: float,
    timestamp: str,
    start: str,
    end: str,
    issue: str,
    station: str,
    latitude: float,
    longitude: float,
    elevation: float | None,
    sql_values: str,
    fmt: str,
    width: int | None,
    height: int | None,
    scale: float | None,
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
    from wetterdienst import Settings
    from wetterdienst.ui.core import InterpolationRequest
    from wetterdienst.ui.render import InterpolationSettings

    timestamp_resolved = _resolve_timestamp(timestamp, start, end)
    if not timestamp_resolved:
        msg = "Provide either --timestamp or --start / --end."
        raise click.UsageError(msg)
    request = _validate_request(
        InterpolationRequest,
        {
            "provider": provider,
            "network": network,
            "parameters": parameters,
            "periods": periods,
            "lead_time": _lead_time_named(lead_time),
            "interpolation_station_distance": interpolation_station_distance,
            "interpolation_station_distance_homogeneous": interpolation_station_distance_homogeneous,
            "interpolation_station_distance_heterogeneous": interpolation_station_distance_heterogeneous,
            "min_gain_of_value_pairs": min_gain_of_value_pairs,
            "num_additional_stations": num_additional_stations,
            "use_nearby_station_distance": use_nearby_station_distance,
            "timestamp": timestamp_resolved,
            "issue": issue,
            "station": station,
            "latitude": latitude,
            "longitude": longitude,
            "elevation": elevation,
            "sql_values": sql_values,
            "format": fmt,
            "width": width,
            "height": height,
            "scale": scale,
            "convert_units": convert_units,
            "unit_targets": unit_targets,
            "humanize": humanize,
            "with_metadata": with_metadata,
            "with_stations": with_stations,
            "pretty": pretty,
        },
    )

    _apply_log_level(debug=debug)
    begin_response()
    _refuse_database_metadata(target, with_metadata=request.with_metadata)

    api = get_timeseries_api(request.provider, request.network)

    # built first: a malformed host setting is not the command line's to fix, whatever the options say
    settings = Settings()
    # a distance given for a name that is not a canonical parameter, or a negative one, or a unit
    # target for a quantity the unit converter does not know is a usage error
    options = _build_options(
        {
            "humanize": ("humanize", request.humanize),
            "convert_units": ("convert_units", request.convert_units),
            "unit_targets": ("unit_targets", request.unit_targets or {}),
            "interpolation_station_distance": ("geo_station_distance", request.interpolation_station_distance or {}),
            "interpolation_station_distance_homogeneous": (
                "geo_station_distance_homogeneous",
                request.interpolation_station_distance_homogeneous,
            ),
            "interpolation_station_distance_heterogeneous": (
                "geo_station_distance_heterogeneous",
                request.interpolation_station_distance_heterogeneous,
            ),
            "min_gain_of_value_pairs": ("geo_min_gain_of_value_pairs", request.min_gain_of_value_pairs),
            "num_additional_stations": ("geo_num_additional_stations", request.num_additional_stations),
            "use_nearby_station_distance": ("geo_use_nearby_station_distance", request.use_nearby_station_distance),
        }
    )

    values_ = _collect_or_exit(
        get_interpolate, api=api, request=request, settings=settings, options=options, what="interpolation"
    )

    _finish(values_, request, InterpolationSettings, options, target=target, if_exists=if_exists)


@cli.command("summarize", epilog=_examples(SUMMARIZE_EXAMPLES))
@provider_opt
@network_opt
@parameters_opt
@periods_opt
@timestamp_opt
@renamed_date_opt
@start_opt
@end_opt
@start_date_renamed_opt
@end_date_renamed_opt
@lead_time_opt
@issue_opt
@reference_station_opt
@latitude_opt
@longitude_opt
@elevation_opt
@station_distance_opts("summary")
@min_gain_of_value_pairs_opt
@num_additional_stations_opt
@sql_values_opt
@convert_units_opt
@unit_targets_opt
@humanize_opt
@format_opt
@width_opt
@height_opt
@scale_opt
@target_opt
@if_exists_opt
@pretty_opt
@with_metadata_target_opt
@with_estimate_stations_opt
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
    min_gain_of_value_pairs: float,
    num_additional_stations: int,
    timestamp: str,
    start: str,
    end: str,
    issue: str,
    station: str,
    latitude: float,
    longitude: float,
    elevation: float | None,
    sql_values: str,
    fmt: str,
    width: int | None,
    height: int | None,
    scale: float | None,
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
    from wetterdienst import Settings
    from wetterdienst.ui.core import SummaryRequest
    from wetterdienst.ui.render import SummarySettings

    timestamp_resolved = _resolve_timestamp(timestamp, start, end)
    if not timestamp_resolved:
        msg = "Provide either --timestamp or --start / --end."
        raise click.UsageError(msg)
    request = _validate_request(
        SummaryRequest,
        {
            "provider": provider,
            "network": network,
            "parameters": parameters,
            "periods": periods,
            "lead_time": _lead_time_named(lead_time),
            "summary_station_distance": summary_station_distance,
            "summary_station_distance_homogeneous": summary_station_distance_homogeneous,
            "summary_station_distance_heterogeneous": summary_station_distance_heterogeneous,
            "min_gain_of_value_pairs": min_gain_of_value_pairs,
            "num_additional_stations": num_additional_stations,
            "timestamp": timestamp_resolved,
            "issue": issue,
            "station": station,
            "latitude": latitude,
            "longitude": longitude,
            "elevation": elevation,
            "sql_values": sql_values,
            "format": fmt,
            "width": width,
            "height": height,
            "scale": scale,
            "convert_units": convert_units,
            "unit_targets": unit_targets,
            "humanize": humanize,
            "with_metadata": with_metadata,
            "with_stations": with_stations,
            "pretty": pretty,
        },
    )
    _apply_log_level(debug=debug)
    begin_response()
    _refuse_database_metadata(target, with_metadata=request.with_metadata)

    api = get_timeseries_api(request.provider, request.network)

    # built first: a malformed host setting is not the command line's to fix, whatever the options say
    settings = Settings()
    # a distance given for a name that is not a canonical parameter, or a negative one, or a unit
    # target for a quantity the unit converter does not know is a usage error
    options = _build_options(
        {
            "humanize": ("humanize", request.humanize),
            "convert_units": ("convert_units", request.convert_units),
            "unit_targets": ("unit_targets", request.unit_targets or {}),
            "summary_station_distance": ("geo_station_distance", request.summary_station_distance or {}),
            "summary_station_distance_homogeneous": (
                "geo_station_distance_homogeneous",
                request.summary_station_distance_homogeneous,
            ),
            "summary_station_distance_heterogeneous": (
                "geo_station_distance_heterogeneous",
                request.summary_station_distance_heterogeneous,
            ),
            "min_gain_of_value_pairs": ("geo_min_gain_of_value_pairs", request.min_gain_of_value_pairs),
            "num_additional_stations": ("geo_num_additional_stations", request.num_additional_stations),
        }
    )

    values_ = _collect_or_exit(
        get_summarize, api=api, request=request, settings=settings, options=options, what="summarize"
    )

    _finish(values_, request, SummarySettings, options, target=target, if_exists=if_exists)


def _radar_sites(
    *,
    dwd: bool,
    all_: bool,
    odim_code: str | None,
    wmo_code: int | None,
    country_name: str | None,
) -> dict | list[dict]:
    """Look up the radar sites the one given selector names, raising KeyError where none match."""
    from wetterdienst.provider.dwd.radar.api import DwdRadarSites
    from wetterdienst.provider.eumetnet.opera.sites import OperaRadarSites

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
@_bool_opt("--dwd", default=False, help="Select the radar sites DWD operates. Default: false")
@_bool_opt("--all", dest="all_", default=False, help="Select all OPERA radar sites. Default: false")
@click.option("--odim-code", type=click.STRING, help="Select the site with this ODIM code. Example: deasb")
@click.option("--wmo-code", type=click.INT, help="Select the site with this WMO code. Example: 10103")
@click.option("--country-name", type=click.STRING, help="Select the sites in this country. Example: france")
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

    Select the sites with exactly one of --dwd, --all, --odim-code, --wmo-code or --country-name.
    """
    from wetterdienst import Settings

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

    # the sites are read from a file shipped with the package, but a malformed `WD_*` setting is refused
    # by its variable here as it is for every other command, after the usage errors above as in `stations`
    # and `values`, so that the exit status says whether the environment is valid, not whether this
    # command happens to read it (GH-2619)
    Settings()
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
    help="Language of the warning texts; mul holds eight, the other seven as 'translations'. Default: en",
)
@click.option(
    "--timestamp",
    type=click.STRING,
    default=None,
    help=(
        "Point in time (ISO 8601, UTC if no offset) to select the active-warnings snapshot for. "
        "Defaults to the latest snapshot. Must fall within DWD's rolling ~48-hour window."
    ),
)
@renamed_date_opt
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
    help=(
        "Write the alerts to this file instead of stdout, in the format its extension names: .json, .geojson or "
        ".csv. Databases are refused. A snapshot without a warning still writes the file. Example: file://alerts.csv"
    ),
)
@click.option(
    "--if-exists",
    type=click.Choice(["replace", "append", "fail", "skip"]),
    default="replace",
    help=(
        "What to do when the --target file is there: 'replace' (default), 'fail' or 'skip'. A file takes "
        "no 'append'. Default: replace"
    ),
)
@pretty_opt
@_bool_opt(
    "--with-metadata",
    default=False,
    help=(
        "Write the metadata block (provider, licence, credit line, date of the data) beside the --target file as "
        "<file>.metadata.json. A .json or .geojson file holds it already; a .csv file does not. Needs --target. "
        "Default: false"
    ),
)
@debug_opt
def alerts(
    granularity: str,
    language: str,
    timestamp: str,
    fmt: str,
    target: str,
    if_exists: Literal["replace", "append", "fail", "skip"],
    pretty: bool,  # noqa: FBT001
    with_metadata: bool,  # noqa: FBT001
    debug: bool,  # noqa: FBT001
) -> None:
    """Acquire DWD weather alerts (CAP warnings).

    Returns all warnings active at the selected time (the latest snapshot by default), one row per
    alert, with a GeoJSON MultiPolygon geometry. An empty result means there were no active warnings.

    With --target the extension decides the format (.json, .geojson, .csv), as for the other commands.
    """
    from wetterdienst import Settings
    from wetterdienst.provider.dwd.alerts import DwdWeatherAlertRequest
    from wetterdienst.ui.render import render_alerts

    _apply_log_level(debug=debug)
    begin_response()

    _refuse_non_file_target(target, "alerts")
    target_url = _alerts_target(target, fmt, with_metadata=with_metadata)

    # outside the handler below, as in `stations` and `values`: the `ValidationError` of a malformed `WD_*`
    # variable is a `ValueError`, and not the command line's to fix
    settings = Settings()
    # granularity, language and format are click choices, so only the timestamp reaches this refusal:
    # one that does not parse, or one an offset carries out of what a datetime holds
    try:
        request = DwdWeatherAlertRequest(
            granularity=granularity, language=language, timestamp=timestamp, settings=settings
        )
    except (ValueError, OverflowError) as e:
        raise click.BadParameter(str(e), param_hint="--timestamp") from e

    try:
        result = request.query()
    except InvalidTimeIntervalError as e:
        # a date before DWD's rolling window, the one refusal of the request's own `query` raises;
        # any other `ValueError` comes from DWD's feed (a timestamp, polygon or filename it cannot read)
        raise click.BadParameter(str(e), param_hint="--timestamp") from e
    except NoInternetError:
        # told by `_Cli.invoke` in one line
        raise
    except Exception as e:
        log.exception("Failed to acquire weather alerts")
        raise click.ClickException(str(e)) from e

    if target_url:
        # an empty snapshot is written as it is, as no warning is an answer a file should say, where a table of
        # stations or values is left alone (a schedule that rewrites the file must not keep yesterday's warnings)
        try:
            result.to_target(target_url, if_exists=if_exists, with_metadata=with_metadata, pretty=pretty)
        except (ExportRefusedError, MissingDependencyError) as e:
            # a refusal, the message the whole of it: `--if-exists=fail` on a file that is there, `append`
            raise click.ClickException(str(e)) from e
        except OSError as e:
            # a directory that does not exist or cannot be written, or a path naming a directory
            msg = f"Could not write --target: {e}"
            raise click.ClickException(msg) from e
        return

    output, _ = render_alerts(result, fmt, pretty=pretty)
    print(output)  # noqa: T201


@cli.group("stripes", cls=_Group)
def stripes() -> None:
    """Climate stripes."""


@stripes.command("stations")
@click.option("--kind", type=click.STRING, required=True, help="Kind of stripes: temperature or precipitation.")
@_bool_opt("--active", default=True, help="Only stations still reporting. Default: true")
@click.option(
    "--format",
    "fmt",
    type=click.Choice(["json", "geojson", "csv"], case_sensitive=False),
    default="json",
    help="Output format. Default: json",
)
@pretty_opt
@debug_opt
def stripes_stations(
    kind: str,
    active: bool,  # noqa: FBT001
    fmt: str,
    pretty: bool,  # noqa: FBT001
    debug: bool,  # noqa: FBT001
) -> None:
    """List stations for climate stripes."""
    from wetterdienst.ui.core import StripesStationsRequest, _get_stripes_stations
    from wetterdienst.ui.render import render_stripes_stations
    from wetterdienst.ui.response_metadata import result_metadata

    _apply_log_level(debug=debug)
    begin_response()
    if kind not in ["temperature", "precipitation"]:
        msg = f"Invalid kind '{kind}'"
        raise click.ClickException(msg)

    stations = _get_stripes_stations(kind=kind, active=active)

    request = StripesStationsRequest.model_validate({"kind": kind, "active": active, "format": fmt, "pretty": pretty})
    metadata = result_metadata(stations, provider="dwd", network="observation", heavy=False)
    _echo(render_stripes_stations(stations, request, metadata))


@stripes.command("image", epilog=_examples(STRIPES_EXAMPLES))
@click.option("--kind", type=click.STRING, required=True, help="Kind of stripes: temperature or precipitation.")
@click.option("--station", type=click.STRING, help="Station id, instead of --name.")
@click.option("--name", type=click.STRING, help="Station name, matched fuzzily, instead of --station.")
@click.option("--name-threshold", type=click.FLOAT, default=0.80, help="Minimum fuzzy-match score. Default: 0.8")
@click.option("--start-year", type=click.INT, help="First year. Default: the station's first")
@click.option("--end-year", type=click.INT, help="Last year. Default: the station's last")
@_bool_opt("--show-title", default=True, help="Show the station name. Default: true")
@_bool_opt("--show-years", default=True, help="Show the first and last year. Default: true")
@_bool_opt("--show-data-availability", default=True, help="Mark the years without data. Default: true")
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
    # a string, not a `Path`: a `Path` collapses the `//` of a URI before it can be refused
    type=click.Path(dir_okay=False, path_type=str),
    help="Write the image to this local file instead of stdout.",
)
@debug_opt
def stripes_image(
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
    target: str | None,
    debug: bool,  # noqa: FBT001
) -> None:
    """Create the climate stripes image for a specific station.

    Select the station with exactly one of --station or --name.
    """
    from wetterdienst import Settings
    from wetterdienst.io.export import render_image, require_kaleido
    from wetterdienst.ui.core import StripesImageRequest

    # the image is written with `Path.write_bytes`, so only a local path is a target: a URI, `file://` included,
    # would be written to the path read off it (`s3:/bucket/...`) once the station is fetched and the plot rendered
    if target and "://" in target:
        msg = "only a local path is supported here, not a URI."
        raise click.BadParameter(msg, param_hint="--target")
    # `is not None`: an empty `--target=` is a path to refuse below, not the absence of one that writes to stdout
    target_path = Path(target) if target is not None else None
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
        },
    )
    # the suffix, dot included, so `stripespng` is refused; `.jpeg` is as usual for JPEG as `.jpg`
    suffixes = (".jpg", ".jpeg") if fmt == "jpg" else (f".{fmt}",)
    if target_path is not None and target_path.suffix.lower() not in suffixes:
        msg = f"must have extension {' or '.join(f'{suffix!r}' for suffix in suffixes)}"
        raise click.BadParameter(msg, param_hint="--target")

    _apply_log_level(debug=debug)

    # the provider request builds its settings from the environment inside the catch-all below:
    # checked here first, a malformed `WD_*` setting is told by its variable
    Settings()
    try:
        fig = _plot_stripes(request)
    except Exception as e:
        # a station that is not found, or years holding too little data, is told in one line, as
        # `/api/stripes/image` answers it with a 4xx; an upstream failure keeps its traceback
        _refuse_if_callers(e, request)
        log.exception("Error while plotting warming stripes")
        raise click.ClickException(str(e)) from e

    require_kaleido()
    image = render_image(fig, fmt, scale=dpi / 100)

    if target_path is not None:
        # rendered outside the handler: talking to the renderer's browser can raise an `OSError` of its own
        # (choreographer's `ChannelClosedError`), which says nothing about --target
        try:
            target_path.write_bytes(image)
        except OSError as e:
            # a directory that does not exist or cannot be written; `--target` itself refuses a directory
            msg = f"Could not write --target: {e}"
            raise click.ClickException(msg) from e
        return

    click.echo(image, nl=False)


if __name__ == "__main__":
    cli()
