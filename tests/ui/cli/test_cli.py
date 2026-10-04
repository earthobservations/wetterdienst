# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the command line interface."""

import itertools
import json
import os
import re
from collections.abc import Iterator
from pathlib import Path
from textwrap import dedent

import click
import pytest
from click.testing import CliRunner
from pydantic import ValidationError

from wetterdienst import Settings, Wetterdienst
from wetterdienst.model.metadata import parse_parameters
from wetterdienst.ui.cli import cli, wetterdienst_help

# Individual settings for observation and mosmix


def test_cli_help() -> None:
    """Test cli help."""
    runner = CliRunner()
    result = runner.invoke(cli, [])
    assert "--help         Show this message and exit." in result.output
    commands = dedent(
        """
        Commands:
          about        Get information about the data.
          alerts       Acquire DWD weather alerts (CAP warnings).
          cache        Display cache location.
          history      Acquire station history.
          info         Display project information.
          interpolate  Interpolate data for a point from the stations around it.
          issues       List available issue (model-run) datetimes for a station.
          radar        List radar stations.
          restapi      Start the Wetterdienst REST API web service.
          stations     Acquire stations.
          stripes      Climate stripes.
          summarize    Summarize data for a point: the nearest station's value.
          values       Acquire data.
        """,
    )
    assert commands in result.output


_OPTION = re.compile(r"(?<![\w-])--[a-z][a-z0-9_-]*")


def _commands(command: click.Command, path: tuple[str, ...] = ("wetterdienst",)) -> Iterator[tuple[str, click.Command]]:
    yield " ".join(path), command
    if isinstance(command, click.Group):
        for name, sub in command.commands.items():
            yield from _commands(sub, (*path, name))


def _declared(command: click.Command) -> set[str]:
    return {opt for param in command.params for opt in (*param.opts, *param.secondary_opts)} | {"--help"}


# the top-level help and each command's own help and examples: every text a user reads options in
_HELP_TEXTS = {
    "wetterdienst": wetterdienst_help,
    **{f"{path} (help)": command.help or "" for path, command in _commands(cli) if path != "wetterdienst"},
    **{f"{path} (examples)": command.epilog for path, command in _commands(cli) if command.epilog},
}


def _examples(text: str) -> Iterator[str]:
    """Yield each `wetterdienst ...` line of a help text, continuation lines joined on."""
    lines = iter(text.splitlines())
    for raw in lines:
        line = re.sub(r'^alias \w+="(wetterdienst .*)"$', r"\1", raw.strip())
        if not line.startswith("wetterdienst "):
            continue
        while line.endswith("\\"):
            line = f"{line[:-1].rstrip()} {next(lines).strip()}"
        yield line


def test_cli_help_names_only_declared_options() -> None:
    """Test every option a command's help names is one that command declares.

    The top-level help named `--si_units` and `--tidy` long after both were gone (GH-2021); it is
    checked against every command, since it speaks of all of them.
    """
    everything = set().union(*(_declared(command) for _, command in _commands(cli))) | {"--version"}
    assert set(_OPTION.findall(wetterdienst_help)) - everything == set()
    for path, command in _commands(cli):
        if command is not cli:
            assert set(_OPTION.findall(command.help or "")) - _declared(command) == set(), path


@pytest.mark.parametrize(
    "example",
    [example for text in _HELP_TEXTS.values() for example in _examples(text)],
)
def test_cli_help_example_resolves(example: str) -> None:
    """Test each example names a command, and only options that command takes."""
    tokens = example.split()[1:]
    command: click.Command = cli
    while tokens and isinstance(command, click.Group) and tokens[0] in command.commands:
        command = command.commands[tokens.pop(0)]
    assert not isinstance(command, click.Group), f"no command {tokens[0]!r}" if tokens else "no command"
    assert set(_OPTION.findall(example)) - _declared(command) == set()


@pytest.mark.parametrize(
    "example",
    [example for text in _HELP_TEXTS.values() for example in _examples(text) if "--parameters=" in example],
)
def test_cli_help_example_parameters_exist(example: str) -> None:
    """Test each parameter an example asks for exists in that network's metadata.

    An example asked for `hourly/precipitation_more`, which DWD has only at daily and coarser
    resolutions; the parameter parsing only logs that and drops it, so the example still ran.
    """
    options = dict(re.findall(r"--(provider|network|parameters)=(\S+)", example))
    metadata = Wetterdienst(options["provider"], options["network"]).metadata
    for parameter in options["parameters"].split(","):
        assert parse_parameters(parameter, metadata), parameter


@pytest.mark.parametrize(
    "name", [name for name in _HELP_TEXTS if name == "wetterdienst" or name.endswith("(examples)")]
)
def test_cli_help_example_continues(name: str) -> None:
    """Test an example's continuation line follows a backslash, so it pastes into a shell whole.

    Without one the shell runs the first line alone, dropping the options on the second -- which
    five examples did before GH-2021, and which the option check above cannot see.
    """
    lines = _HELP_TEXTS[name].splitlines()
    for previous, line in itertools.pairwise(lines):
        # any indentation: _examples dedents each block, leaving a continuation line at four spaces
        if re.match(r"\s+(--|>)", line):
            assert previous.rstrip().endswith("\\"), previous


def test_cli_about_parameters() -> None:
    """Test cli coverage of dwd parameters."""
    runner = CliRunner()
    result = runner.invoke(cli, ["about", "coverage", "--provider=dwd", "--network=observation"])
    # resolution
    assert "1_minute" in result.output
    # datasets
    assert "precipitation" in result.output
    assert "temperature_air" in result.output
    assert "weather_phenomena" in result.output
    # parameters
    assert "precipitation_amount" in result.output


@pytest.mark.remote
def test_cli_about_fields_dwd_observation() -> None:
    """Test cli about fields for dwd observation (regression: resolution + dataset args)."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "about",
            "fields",
            "--provider=dwd",
            "--network=observation",
            "--dataset=precipitation",
            "--resolution=hourly",
            "--period=historical",
        ],
    )
    assert result.exit_code == 0
    assert "parameters" in result.output
    assert "quality_information" in result.output


_ABOUT_FIELDS = ["about", "fields", "--resolution=daily", "--dataset=daily", "--period=historical"]


def test_cli_about_fields_refuses_other_providers() -> None:
    """Test about fields refuses a network without field descriptions, rather than failing on it.

    Its check looked for an option the command does not have, so it never refused, and NOAA GHCN
    ended in an AttributeError traceback.
    """
    runner = CliRunner()
    result = runner.invoke(cli, [*_ABOUT_FIELDS, "--provider=noaa", "--network=ghcn"])
    assert result.exit_code == 2, result.output
    assert (
        "Error: Fields are described for provider 'dwd', network 'observation' only, not noaa/ghcn.\n" in result.output
    )


def test_cli_about_fields_applies_debug(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test about fields applies --debug, which its `**kwargs` used to swallow."""
    levels = []
    monkeypatch.setattr("wetterdienst.ui.cli.set_logging_level", lambda *, debug: levels.append(debug))
    monkeypatch.setattr(
        "wetterdienst.provider.dwd.observation.DwdObservationRequest.describe_fields",
        lambda **_kwargs: {"parameters": {}},
    )
    runner = CliRunner()
    result = runner.invoke(cli, [*_ABOUT_FIELDS, "--provider=dwd", "--network=observation", "--debug"])
    assert result.exit_code == 0, result.output
    assert levels == [True]


def test_no_combination_of_provider_and_network(caplog: pytest.CaptureFixture) -> None:
    """Test cli coverage of dwd parameters."""
    runner = CliRunner()
    runner.invoke(
        cli,
        [
            "stations",
            "--provider=dwd",
            "--network=abc",
            "--parameters=daily/climate_summary/precipitation_amount",
            "--all",
        ],
    )
    assert "No API available for provider dwd and network abc." in caplog.text


def test_coverage() -> None:
    """Test coverage."""
    runner = CliRunner()
    result = runner.invoke(cli, ["about", "coverage", "--provider=dwd", "--network=observation"])
    assert result.exit_code == 0
    response = json.loads(result.stdout)
    assert "1_minute" in response
    assert "precipitation" in response["1_minute"]["datasets"]
    assert len(response["1_minute"]["datasets"]["precipitation"]["parameters"]) > 0
    parameters = [p["name"] for p in response["1_minute"]["datasets"]["precipitation"]["parameters"]]
    assert parameters == [
        "precipitation_amount",
        "precipitation_amount_droplet",
        "precipitation_amount_rocker",
        "precipitation_index",
    ]


@pytest.mark.parametrize("network", ["alerts", "radar"])
def test_coverage_standalone_network_reports_cleanly(network: str) -> None:
    """Test coverage for a metadata-less standalone network fails cleanly instead of crashing."""
    runner = CliRunner()
    result = runner.invoke(cli, ["about", "coverage", "--provider=dwd", f"--network={network}"])
    assert result.exit_code == 1
    assert not isinstance(result.exception, AttributeError)


def test_coverage_resolution_1_minute() -> None:
    """Test coverage for resolution 1_minute."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["about", "coverage", "--provider=dwd", "--network=observation", "--resolutions=1_minute"],
    )
    assert result.exit_code == 0
    response = json.loads(result.stdout)
    assert response.keys() == {"1_minute"}


def test_coverage_dataset_climate_summary() -> None:
    """Test coverage for dataset climate_summary."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["about", "coverage", "--provider=dwd", "--network=observation", "--datasets=climate_summary"],
    )
    assert result.exit_code == 0
    response = json.loads(result.stdout)
    assert response.keys() == {"daily", "monthly", "annual"}
    assert response["daily"]["datasets"].keys() == {"climate_summary"}
    assert response["monthly"]["datasets"].keys() == {"climate_summary"}
    assert response["annual"]["datasets"].keys() == {"climate_summary"}


def test_cli_radar_stations_opera() -> None:
    """Test cli radar stations."""
    runner = CliRunner()
    result = runner.invoke(cli, ["radar", "--odim-code=ukdea"])
    response = json.loads(result.output)
    assert isinstance(response, dict)
    assert response["location"] == "Dean Hill"


def test_cli_radar_stations_opera_wmo_code() -> None:
    """Test cli radar stations looked up by WMO code, which the sites hold as an integer."""
    runner = CliRunner()
    result = runner.invoke(cli, ["radar", "--wmo_code=11038"])
    assert result.exit_code == 0
    response = json.loads(result.output)
    assert response["odimcode"] == "atrau"
    assert response["wmocode"] == 11038


def test_cli_radar_stations_opera_not_found() -> None:
    """Test cli radar stations reports a code no site carries as an error, not a traceback."""
    runner = CliRunner()
    result = runner.invoke(cli, ["radar", "--wmo_code=99999"])
    assert result.exit_code == 1
    assert "Error: Radar site not found" in result.output
    assert not isinstance(result.exception, KeyError)


def test_cli_radar_stations_opera_malformed_code() -> None:
    """Test an ODIM code of the wrong shape is a usage error, not a traceback."""
    runner = CliRunner()
    result = runner.invoke(cli, ["radar", "--odim-code=de"])
    assert result.exit_code == 2
    assert "ODIM code must be three or five letters" in result.output
    assert not isinstance(result.exception, ValueError)


def test_cli_radar_stations_dwd() -> None:
    """Test cli radar stations."""
    runner = CliRunner()
    result = runner.invoke(cli, ["radar", "--dwd"])
    response = json.loads(result.output)
    assert isinstance(response, list)
    assert len(response) == 20


@pytest.mark.remote
def test_issues_dwd_mosmix() -> None:
    """Test issues command for DWD MOSMIX returns sorted UTC ISO datetimes."""
    runner = CliRunner()
    result = runner.invoke(cli, ["issues", "--provider=dwd", "--network=mosmix", "--station=10147"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "issues" in data
    issues = data["issues"]
    assert len(issues) > 0
    assert issues == sorted(issues)
    assert all(issue.endswith("+00:00") for issue in issues)


@pytest.mark.remote
def test_issues_dwd_dmo() -> None:
    """Test issues command for DWD DMO returns sorted UTC ISO datetimes."""
    runner = CliRunner()
    result = runner.invoke(cli, ["issues", "--provider=dwd", "--network=dmo", "--station=10147"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "issues" in data
    issues = data["issues"]
    assert len(issues) > 0
    assert issues == sorted(issues)
    assert all(issue.endswith("+00:00") for issue in issues)


def test_issues_unsupported_provider() -> None:
    """Test issues command exits with error for unsupported providers."""
    runner = CliRunner()
    result = runner.invoke(cli, ["issues", "--provider=dwd", "--network=observation", "--station=00011"])
    assert result.exit_code == 1


def test_cli_glossary() -> None:
    """Test that the glossary reports what a parameter measures and its returned unit."""
    runner = CliRunner()
    result = runner.invoke(cli, ["about", "glossary", "--parameter=radiation_global_intensity"])
    assert result.exit_code == 0
    entries = json.loads(result.stdout)
    assert entries == [
        {
            "name": "radiation_global_intensity",
            "unit_type": "power_per_area",
            "unit": "watt_per_square_meter",
            "unit_symbol": "W/m²",
            "description": "Global irradiance on a horizontal surface, reported as power rather than energy.",
        },
    ]


def test_cli_glossary_unit_type() -> None:
    """Test that filtering by unit type returns only parameters of that quantity."""
    runner = CliRunner()
    result = runner.invoke(cli, ["about", "glossary", "--unit-type=turbidity"])
    assert result.exit_code == 0
    entries = json.loads(result.stdout)
    assert [entry["name"] for entry in entries] == ["turbidity"]


def test_cli_glossary_no_match() -> None:
    """Test that a filter matching nothing exits non-zero, as grep does.

    The REST endpoint answers the same query with 200 and an empty list, because an empty result is
    not an HTTP error. The exit code is what makes the difference visible to a shell script.
    """
    runner = CliRunner()
    result = runner.invoke(cli, ["about", "glossary", "--parameter=not_a_parameter"])
    assert result.exit_code == 1


def test_cli_glossary_unknown_unit_type() -> None:
    """Test that an unknown unit type is a usage error listing the valid ones.

    click.Choice turns the closed vocabulary into a message naming every option, so a typo tells
    the user what to type instead of returning nothing.
    """
    runner = CliRunner()
    result = runner.invoke(cli, ["about", "glossary", "--unit-type=celsius"])
    assert result.exit_code == 2
    assert "'celsius' is not one of" in result.output
    assert "temperature" in result.output


def test_cli_glossary_limit() -> None:
    """Test that --limit bounds the output."""
    runner = CliRunner()
    result = runner.invoke(cli, ["about", "glossary", "--limit=3"])
    assert result.exit_code == 0
    assert len(json.loads(result.stdout)) == 3


def test_issues_dmo_passes_the_product_and_lead_time_through(monkeypatch: pytest.MonkeyPatch) -> None:
    """The command that says which issues exist has to answer for the request it is about.

    A DMO run belongs to a product and a lead time, and this listed one product's directory
    whatever the caller went on to ask for -- so it named issues the values path then rejected
    (GH-1956).
    """
    from wetterdienst.provider.dwd.dmo import DwdDmoRequest  # noqa: PLC0415

    asked = {}

    def available_issues(station_id: str, _settings: object, **kwargs: object) -> list:
        asked.update({"station_id": station_id, **kwargs})
        return []

    monkeypatch.setattr(DwdDmoRequest, "available_issues", available_issues)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["issues", "--provider=dwd", "--network=dmo", "--station=01001", "--dataset=icon_eu", "--lead_time=long"],
    )

    assert result.exit_code == 0
    assert asked == {"station_id": "01001", "dataset": "icon_eu", "lead_time": "long"}


def test_issues_mosmix_says_the_dmo_options_do_not_apply(caplog: pytest.LogCaptureFixture) -> None:
    """Named rather than ignored: answering a different question than the one asked is the fault here."""
    import logging  # noqa: PLC0415

    runner = CliRunner()
    with caplog.at_level(logging.ERROR):
        result = runner.invoke(
            cli,
            ["issues", "--provider=dwd", "--network=mosmix", "--station=10147", "--lead_time=long"],
        )

    assert result.exit_code == 1
    assert "lead_time applies to DWD DMO only" in caplog.text


def test_every_export_command_can_say_what_to_do_with_an_existing_target() -> None:
    """A command that writes to a target offers `--if_exists`, or its schedule can only replace.

    `to_target` has taken `if_exists` since it was written and the export docs advertise it, but no
    command passed it, so every CLI export replaced -- a nightly timer pointed at a database held
    one run's rows. This walks the command tree rather than naming the four commands, because the
    gap was a command gaining `--target` without the option that says what a second run does.

    Three commands are excluded because their `--target` never reaches a sink: `alerts` and
    `history` write text with `Path.write_text`, and `stripes values` writes an image with
    `fig.write_image`. There is nothing for them to ask what to do with an existing target.
    """
    import click  # noqa: PLC0415

    writes_directly = {"alerts", "history", "stripes values"}

    def walk(command: click.Command, path: tuple[str, ...] = ()) -> list[tuple[str, click.Command]]:
        here = (*path, command.name)
        if isinstance(command, click.Group):
            return [entry for sub in command.commands.values() for entry in walk(sub, here)]
        return [(" ".join(here[1:]), command)]

    missing = []
    for name, command in walk(cli):
        options = {option.name for option in command.params}
        if "target" in options and name not in writes_directly and "if_exists" not in options:
            missing.append(name)

    assert not missing, f"commands exporting through to_target without --if_exists: {missing}"


@pytest.mark.parametrize("command", ["stations", "values", "interpolate", "summarize"])
def test_if_exists_defaults_to_replace(command: str) -> None:
    """The default is what the CLI did before the option existed, so no schedule changes under it."""
    from wetterdienst.ui.cli import cli as root  # noqa: PLC0415

    subcommand = root.commands[command]
    option = next(param for param in subcommand.params if param.name == "if_exists")

    assert option.default == "replace"
    assert set(option.type.choices) == {"replace", "append", "fail", "skip"}


_DWD_KL = ["--provider=dwd", "--network=observation", "--parameters=daily/kl"]


_RADAR_ONE_OF = "Missing option: one of '--dwd', '--all', '--odim-code', '--wmo_code' or '--country_name'."


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (
            ["stations", *_DWD_KL],
            (
                "Error: Missing option: one of '--all', '--station', '--name', ('--latitude' and '--longitude'), "
                "('--left', '--bottom', '--right' and '--top') or '--sql'.\n"
            ),
        ),
        (
            ["stations", *_DWD_KL, "--station=01048", "--name=Hamburg"],
            "Error: Options '--station' and '--name' cannot be used together.\n",
        ),
        (
            ["values", *_DWD_KL, "--latitude=51.0", "--rank=5"],
            "Error: Missing option '--longitude'. Required with '--latitude'.\n",
        ),
        (
            ["values", *_DWD_KL, "--latitude=51.0", "--longitude=13.7"],
            "Error: Missing option: one of '--rank' or '--distance', required with '--latitude' and '--longitude'.\n",
        ),
        (
            ["values", *_DWD_KL, "--latitude=51.0", "--longitude=13.7", "--rank=5", "--distance=25"],
            "Error: Options '--rank' and '--distance' cannot be used together.\n",
        ),
        (
            ["stations", *_DWD_KL, "--left=13", "--top=52"],
            (
                "Error: Missing option '--bottom'. Required with '--left' and '--top'.\n"
                "Missing option '--right'. Required with '--left' and '--top'.\n"
            ),
        ),
        (
            ["stations", *_DWD_KL, "--station=01048", "--rank=5"],
            "Error: Option '--rank' requires ('--latitude' and '--longitude') or '--name'.\n",
        ),
        (
            ["stations", *_DWD_KL, "--name=Dresden", "--distance=25"],
            "Error: Option '--distance' requires '--latitude' and '--longitude'.\n",
        ),
        (["history", *_DWD_KL], "Error: Missing option: one of '--all' or '--station'.\n"),
        (
            ["interpolate", *_DWD_KL, "--date=2020-06-30", "--station=01048", "--latitude=51", "--longitude=13.7"],
            "Error: Options '--station' and '--latitude' cannot be used together.\n",
        ),
        (
            ["summarize", *_DWD_KL, "--date=2020-06-30"],
            "Error: Missing option: one of '--station' or ('--latitude' and '--longitude').\n",
        ),
        (["radar"], f"Error: {_RADAR_ONE_OF}\n"),
        (["radar", "--dwd", "--all"], "Error: Options '--dwd' and '--all' cannot be used together.\n"),
        # an empty value, e.g. from an unset shell variable, selects nothing
        (["radar", "--odim-code="], f"Error: {_RADAR_ONE_OF}\n"),
        (["radar", "--country_name="], f"Error: {_RADAR_ONE_OF}\n"),
        (["stripes", "values", "--kind=temperature"], "Error: Missing option: one of '--station' or '--name'.\n"),
        (
            ["stripes", "values", "--kind=temperature", "--station=1048", "--name=Dresden"],
            "Error: Options '--station' and '--name' cannot be used together.\n",
        ),
        # a single value's error is told as click tells an invalid value, with the value refused;
        # --sections is a set, so the position pydantic gives within it points nowhere and is left out
        (
            ["values", *_DWD_KL, "--station=01048", "--distance=-1"],
            "Error: Invalid value for '--distance': Input should be greater than or equal to 0 (got -1.0).\n",
        ),
        (
            ["history", *_DWD_KL, "--station=01048", "--sections=name,foo"],
            (
                "Error: Invalid value for '--sections': Input should be 'name', 'parameter', 'device', 'geography' "
                "or 'missing_data' (got 'foo').\n"
            ),
        ),
        (
            ["values", *_DWD_KL, "--station=01048", '--unit_targets={"temperature": 5}'],
            "Error: Invalid value for '--unit_targets': temperature: Input should be a valid string (got 5).\n",
        ),
        # a field validator's ValueError, told without pydantic's "Value error, " in front of it
        (
            ["values", *_DWD_KL, "--station=01048", "--unit_targets={bad"],
            (
                "Error: Invalid value for '--unit_targets': Expecting property name enclosed in double quotes: "
                "line 1 column 2 (char 1) (got '{bad').\n"
            ),
        ),
        (
            ["about", "fields", "--provider=dwd", "--network=observation", "--resolution=daily", "--dataset=kl"],
            "Error: Missing option '--period'.",
        ),
    ],
)
def test_cli_refuses_selection(args: list[str], message: str) -> None:
    """Test each rule over several options is a usage error, before anything is fetched."""
    runner = CliRunner()
    result = runner.invoke(cli, args)
    assert result.exit_code == 2, result.output
    assert message in result.output
    # one line per problem, without pydantic's echo of every option the command took
    assert "input_value" not in result.output


def test_cli_values_refuses_unknown_unit_targets_quantity() -> None:
    """Test a unit target for a quantity the converter does not know is a usage error, not a traceback."""
    runner = CliRunner()
    result = runner.invoke(cli, ["values", *_DWD_KL, "--station=01048", '--unit_targets={"foo": "bar"}'])
    assert result.exit_code == 2, result.output
    assert "Error: Invalid value for '--unit_targets': Invalid unit targets: one of {'foo'} not in" in result.output
    # one line, without pydantic's echo of the input
    assert "input_value" not in result.output


def test_cli_values_does_not_blame_the_command_line_for_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test a WD_* environment variable Settings refuses is not told as a bad --unit_targets."""
    monkeypatch.setenv("WD_CACHE_DISABLE", "notabool")
    runner = CliRunner()
    result = runner.invoke(
        cli, ["values", *_DWD_KL, "--station=01048", '--unit_targets={"temperature": "degree_fahrenheit"}']
    )
    assert isinstance(result.exception, ValidationError)
    assert "--unit_targets" not in result.output


def test_cli_values_does_not_blame_an_absent_unit_targets_for_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test a WD_TS_UNIT_TARGETS that Settings refuses is not told as a bad --unit_targets nobody gave."""
    monkeypatch.setenv("WD_TS_UNIT_TARGETS", '{"foo": "bar"}')
    runner = CliRunner()
    result = runner.invoke(cli, ["values", *_DWD_KL, "--station=01048"])
    assert isinstance(result.exception, ValidationError)
    assert "--unit_targets" not in result.output


_POINT_ARGS = [
    "--provider=dwd",
    "--network=observation",
    "--parameters=daily/kl/temperature_air_mean_2m",
    "--station=00071",
    "--date=1986-10-31",
]


@pytest.fixture
def _no_ambient_settings(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Keep the WD_* variables and the `.env` of whoever runs the tests out of the settings."""
    for name in list(os.environ):
        if name.startswith("WD_"):
            monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


class _SettingsTaken(Exception):  # noqa: N818
    """Raised in place of fetching, carrying the settings a command built."""


def _settings_of(monkeypatch: pytest.MonkeyPatch, args: list[str], env: dict[str, str]) -> Settings:
    """Run a command up to its fetch, and return the settings it would fetch with."""

    def take(_get: object, *, settings: Settings, **_kwargs: object) -> None:
        raise _SettingsTaken(settings)

    monkeypatch.setattr("wetterdienst.ui.cli._collect_or_exit", take)
    result = CliRunner().invoke(cli, args, env=env)
    assert isinstance(result.exception, _SettingsTaken), result.output
    return result.exception.args[0]


@pytest.mark.usefixtures("_no_ambient_settings")
def test_cli_values_leaves_a_setting_no_option_was_given_for_to_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the WD_TS_* variables set what `values` was given no option for, and an option given outranks one."""
    env = {
        "WD_TS_SHAPE": "wide",
        "WD_TS_HUMANIZE": "false",
        "WD_TS_CONVERT_UNITS": "false",
        "WD_TS_UNIT_TARGETS": '{"temperature": "degree_fahrenheit"}',
        "WD_TS_SKIP_EMPTY": "true",
        "WD_TS_SKIP_CRITERIA": "max",
        "WD_TS_SKIP_THRESHOLD": "0.5",
        "WD_TS_DROP_NULLS": "false",
    }
    settings = _settings_of(monkeypatch, ["values", *_DWD_KL, "--station=01048"], env)
    assert settings.ts_shape == "wide"
    assert settings.ts_humanize is False
    assert settings.ts_convert_units is False
    assert settings.ts_unit_targets == {"temperature": "degree_fahrenheit"}
    assert settings.ts_skip_empty is True
    assert settings.ts_skip_criteria == "max"
    assert settings.ts_skip_threshold == 0.5
    assert settings.ts_drop_nulls is False
    # an option given at its default value is given all the same
    settings = _settings_of(
        monkeypatch,
        [
            "values",
            *_DWD_KL,
            "--station=01048",
            "--shape=long",
            "--humanize=true",
            "--convert_units=true",
            "--skip_empty=false",
            "--skip_criteria=min",
            "--skip_threshold=0.95",
            "--drop_nulls=true",
        ],
        env,
    )
    assert settings.ts_shape == "long"
    assert settings.ts_humanize is True
    assert settings.ts_convert_units is True
    assert settings.ts_skip_empty is False
    assert settings.ts_skip_criteria == "min"
    assert settings.ts_skip_threshold == 0.95
    assert settings.ts_drop_nulls is True


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize(("command", "kind"), [("interpolate", "interpolation"), ("summarize", "summary")])
def test_cli_estimate_leaves_a_setting_no_option_was_given_for_to_the_environment(
    monkeypatch: pytest.MonkeyPatch,
    command: str,
    kind: str,
) -> None:
    """Test the WD_TS_* variables set what `interpolate` and `summarize` were given no option for."""
    env = {
        "WD_TS_HUMANIZE": "false",
        "WD_TS_CONVERT_UNITS": "false",
        "WD_TS_GEO_STATION_DISTANCE_HOMOGENEOUS": "60",
        "WD_TS_GEO_STATION_DISTANCE_HETEROGENEOUS": "15",
    }
    settings = _settings_of(monkeypatch, [command, *_POINT_ARGS], env)
    assert settings.ts_humanize is False
    assert settings.ts_convert_units is False
    assert settings.ts_geo_station_distance_homogeneous == 60
    assert settings.ts_geo_station_distance_heterogeneous == 15
    settings = _settings_of(
        monkeypatch,
        [
            command,
            *_POINT_ARGS,
            "--humanize=true",
            "--convert_units=true",
            f"--{kind}_station_distance_homogeneous=40",
            f"--{kind}_station_distance_heterogeneous=20",
            "--use_nearby_station_distance=0.5",
        ],
        env,
    )
    assert settings.ts_humanize is True
    assert settings.ts_convert_units is True
    assert settings.ts_geo_station_distance_homogeneous == 40
    assert settings.ts_geo_station_distance_heterogeneous == 20
    assert settings.ts_geo_use_nearby_station_distance == 0.5


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize(
    ("args", "message"),
    [
        (
            ["interpolate", *_POINT_ARGS, '--interpolation_station_distance={"temperature_air_mean": 10}'],
            (
                "Error: Invalid value for '--interpolation_station_distance': Invalid parameters in "
                "ts_geo_station_distance: ['temperature_air_mean'] not in the canonical parameters "
                "(got {'temperature_air_mean': 10.0}).\n"
            ),
        ),
        (
            ["summarize", *_POINT_ARGS, '--summary_station_distance={"temperature_air_mean_2m": -1}'],
            (
                "Error: Invalid value for '--summary_station_distance': temperature_air_mean_2m: "
                "Input should be greater than or equal to 0 (got -1).\n"
            ),
        ),
        (
            ["summarize", *_POINT_ARGS, '--unit_targets={"foo": "bar"}'],
            "Error: Invalid value for '--unit_targets': Invalid unit targets: one of {'foo'} not in",
        ),
    ],
)
def test_cli_estimate_refuses_a_setting_by_its_option(args: list[str], message: str) -> None:
    """Test a setting an option of `interpolate` or `summarize` gives is refused by that option, in a line."""
    result = CliRunner().invoke(cli, args)
    assert result.exit_code == 2, result.output
    assert message in result.output
    assert "input_value" not in result.output
    assert "Value error, " not in result.output


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize(
    ("env", "option"),
    [
        ({"WD_CACHE_DISABLE": "notabool"}, '--unit_targets={"temperature": "degree_fahrenheit"}'),
        # merged into the dict the option gives, so where pydantic locates the error does not tell
        ({"WD_TS_GEO_STATION_DISTANCE": '{"foo": 5}'}, '--KIND_station_distance={"precipitation_amount": 5}'),
        ({"WD_TS_UNIT_TARGETS": '{"foo": "bar"}'}, '--unit_targets={"temperature": "degree_fahrenheit"}'),
    ],
)
@pytest.mark.parametrize(("command", "kind"), [("interpolate", "interpolation"), ("summarize", "summary")])
def test_cli_estimate_does_not_blame_the_command_line_for_the_environment(
    env: dict[str, str],
    option: str,
    command: str,
    kind: str,
) -> None:
    """Test a WD_* variable Settings refuses is not told as a usage error of `interpolate` or `summarize`."""
    result = CliRunner().invoke(cli, [command, *_POINT_ARGS, option.replace("KIND", kind)], env=env)
    assert isinstance(result.exception, ValidationError)
    assert "Usage:" not in result.output


@pytest.mark.usefixtures("_no_ambient_settings")
def test_cli_values_does_not_blame_a_given_unit_targets_for_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test a WD_TS_UNIT_TARGETS that Settings refuses is not told as a bad --unit_targets given beside it."""
    monkeypatch.setenv("WD_TS_UNIT_TARGETS", '{"foo": "bar"}')
    result = CliRunner().invoke(
        cli, ["values", *_DWD_KL, "--station=01048", '--unit_targets={"temperature": "degree_fahrenheit"}']
    )
    assert isinstance(result.exception, ValidationError)
    assert "--unit_targets" not in result.output


@pytest.mark.usefixtures("_no_ambient_settings")
@pytest.mark.parametrize(
    "args",
    [["values", *_DWD_KL, "--station=01048"], ["interpolate", *_POINT_ARGS], ["summarize", *_POINT_ARGS]],
)
def test_cli_passes_settings_no_option_was_given_for(monkeypatch: pytest.MonkeyPatch, args: list[str]) -> None:
    """Test a command left its options out passes Settings nothing, which the environment then sets.

    Among them are the settings no option sets at all, such as `ts_geo_num_additional_stations`.
    """
    calls: list[dict] = []

    def record(**kwargs: object) -> Settings:
        calls.append(kwargs)
        return Settings(**kwargs)

    monkeypatch.setattr("wetterdienst.ui.cli.Settings", record)
    _settings_of(monkeypatch, args, {})
    assert calls
    assert all(not kwargs for kwargs in calls)


@pytest.mark.usefixtures("_no_ambient_settings")
def test_cli_values_option_outranks_a_malformed_variable_for_its_setting(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test an option given on the command line replaces a WD_TS_* variable Settings would refuse."""
    settings = _settings_of(
        monkeypatch, ["values", *_DWD_KL, "--station=01048", "--shape=long"], {"WD_TS_SHAPE": "bogus"}
    )
    assert settings.ts_shape == "long"


@pytest.mark.usefixtures("_no_ambient_settings")
def test_cli_estimate_refuses_an_option_with_the_value_it_gave(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test a refused dict is shown as the option gave it, not merged with the environment's."""
    monkeypatch.setenv("WD_TS_GEO_STATION_DISTANCE", '{"precipitation_amount": 5}')
    result = CliRunner().invoke(cli, ["summarize", *_POINT_ARGS, '--summary_station_distance={"foo": 1}'])
    assert result.exit_code == 2, result.output
    assert (
        "Error: Invalid value for '--summary_station_distance': Invalid parameters in ts_geo_station_distance: "
        "['foo'] not in the canonical parameters (got {'foo': 1.0}).\n"
    ) in result.output
