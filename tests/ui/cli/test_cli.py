# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the command line interface."""

import json
from textwrap import dedent

import pytest
from click.testing import CliRunner

from wetterdienst.ui.cli import cli

# Individual settings for observation and mosmix


def test_cli_help() -> None:
    """Test cli help."""
    runner = CliRunner()
    result = runner.invoke(cli, [])
    assert "--help         Show this message and exit." in result.output
    commands = dedent(
        """
        Basic:
          cache        Display cache location.
          info         Display project information.

        Advanced:
          restapi      Start the Wetterdienst REST API web service.

        Data:
          about        Get information about the data.
          stations     Acquire stations.
          issues       List available issue (model-run) datetimes for a station.
          history      Acquire station history.
          values       Acquire data.
          interpolate  Interpolate data.
          summarize    Summarize data.
          radar        List radar stations.
          alerts       Acquire DWD weather alerts (CAP warnings).
          stripes      Climate stripes.
        """,
    )
    assert commands in result.output


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
    assert "precipitation_height" in result.output


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


def test_no_combination_of_provider_and_network(caplog: pytest.CaptureFixture) -> None:
    """Test cli coverage of dwd parameters."""
    runner = CliRunner()
    runner.invoke(
        cli,
        [
            "stations",
            "--provider=dwd",
            "--network=abc",
            "--parameters=daily/climate_summary/precipitation_height",
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
    assert "precipitation" in response["1_minute"]
    assert len(response["1_minute"]["precipitation"]) > 0
    parameters = [p["name"] for p in response["1_minute"]["precipitation"]]
    assert parameters == [
        "precipitation_height",
        "precipitation_height_droplet",
        "precipitation_height_rocker",
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
    assert response["daily"].keys() == {"climate_summary"}
    assert response["monthly"].keys() == {"climate_summary"}
    assert response["annual"].keys() == {"climate_summary"}


def test_cli_radar_stations_opera() -> None:
    """Test cli radar stations."""
    runner = CliRunner()
    result = runner.invoke(cli, ["radar", "--odim-code=ukdea"])
    response = json.loads(result.output)
    assert isinstance(response, dict)
    assert response["location"] == "Dean Hill"


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
