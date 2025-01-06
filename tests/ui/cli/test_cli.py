# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import json

from click.testing import CliRunner

from wetterdienst.ui.cli import cli

# Individual settings for observation and mosmix


def test_cli_help():
    """Test cli help"""
    runner = CliRunner()
    result = runner.invoke(cli, [])
    assert "Options:\n --help  Show this message and exit."
    assert (
        "Basic:\n"
        "  cache\n"
        "  info\n"
        "\n"
        "Advanced:\n"
        "  restapi\n"
        "  explorer\n"
        "\n"
        "Data:\n"
        "  about\n"
        "  stations\n"
        "  values\n"
        "  interpolate\n"
        "  summarize\n"
        "  radar\n"
        "  stripes\n" in result.output
    )


def test_cli_about_parameters():
    """Test cli coverage of dwd parameters"""
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


def test_no_combination_of_provider_and_network(caplog):
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
    assert "No API available for provider dwd and network abc" in caplog.text


def test_coverage():
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


def test_coverage_resolution_1_minute():
    runner = CliRunner()
    result = runner.invoke(
        cli, ["about", "coverage", "--provider=dwd", "--network=observation", "--resolutions=1_minute"]
    )
    assert result.exit_code == 0
    response = json.loads(result.stdout)
    assert response.keys() == {"1_minute"}


def test_coverage_dataset_climate_summary():
    runner = CliRunner()
    result = runner.invoke(
        cli, ["about", "coverage", "--provider=dwd", "--network=observation", "--datasets=climate_summary"]
    )
    assert result.exit_code == 0
    response = json.loads(result.stdout)
    assert response.keys() == {"daily", "monthly", "annual"}
    assert response["daily"].keys() == {"climate_summary"}
    assert response["monthly"].keys() == {"climate_summary"}
    assert response["annual"].keys() == {"climate_summary"}


def test_cli_radar_stations_opera():
    runner = CliRunner()
    result = runner.invoke(cli, ["radar", "--odim-code=ukdea"])
    response = json.loads(result.output)
    assert isinstance(response, dict)
    assert response["location"] == "Dean Hill"


def test_cli_radar_stations_dwd():
    runner = CliRunner()
    result = runner.invoke(cli, ["radar", "--dwd"])
    response = json.loads(result.output)
    assert isinstance(response, list)
    assert len(response) == 20
