# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import json
from datetime import datetime, timedelta

import pandas as pd
import pytest
from click.testing import CliRunner

from wetterdienst.ui.cli import cli

# Individual settings for observation and mosmix
SETTINGS_STATIONS = (
    (
        "dwd",
        "observation",
        "--resolution=daily --parameter=kl --period=recent",
        "01048",
        # expected dict
        {
            "station_id": "01048",
            "height": 228.0,
            "latitude": 51.1278,
            "longitude": 13.7543,
            "from_date": "1934-01-01T00:00:00+00:00",
            "name": "Dresden-Klotzsche",
            "state": "Sachsen",
        },
        # coordinates
        [13.7543, 51.1278, 228.0],
    ),
    (
        "dwd",
        "mosmix",
        "--resolution=large --parameter=large",
        "10488",
        {
            "station_id": "10488",
            "height": 230.0,
            "icao_id": "EDDC",
            "latitude": 51.13,
            "longitude": 13.75,
            "from_date": None,
            "name": "DRESDEN/FLUGHAFEN",
            "state": None,
        },
        [13.75, 51.13, 230.0],
    ),
)

SETTINGS_VALUES = (
    (
        "dwd",
        "observation",
        "--resolution=daily --parameter=kl --period=recent --date=2020-06-30",
        "01048",
        "Dresden-Klotzsche",
    ),
    (
        "dwd",
        "mosmix",
        f"--parameter=small --resolution=large "
        f"--date={datetime.strftime(datetime.today() + timedelta(days=2), '%Y-%m-%d')}",
        "10488",
        "DRESDEN",
    ),
)


def test_cli_help():
    """Test cli help"""
    runner = CliRunner()

    result = runner.invoke(cli, [])

    assert "Options:\n --help  Show this message and exit."
    assert (
        "Commands:\n  about\n  explorer\n  info\n  radar\n  "
        "restapi\n  stations_result\n  values\n  version\n" in result.output
    )


def test_cli_about_parameters():
    """Test cli coverage of dwd parameters"""
    runner = CliRunner()

    result = runner.invoke(cli, "about coverage --provider=dwd --network=observation")

    assert "precipitation" in result.output
    assert "temperature_air" in result.output
    assert "weather_phenomena" in result.output


def test_cli_about_resolutions():
    """Test cli coverage of dwd resolutions"""
    runner = CliRunner()

    result = runner.invoke(cli, "about coverage --provider=dwd --network=observation")

    assert "minute_1" in result.output
    assert "hourly" in result.output
    assert "annual" in result.output


def test_cli_about_coverage(capsys):
    runner = CliRunner()

    result = runner.invoke(cli, "about coverage --provider=dwd --network=observation")

    assert "minute_1" in result.output
    assert "precipitation" in result.output


def invoke_wetterdienst_stations_empty(provider, network, setting, fmt="json"):
    runner = CliRunner()

    return runner.invoke(
        cli,
        f"stations_result --provider={provider} --network={network} " f"{setting} --station=123456 --format={fmt}",
    )


def invoke_wetterdienst_stations_static(provider, network, setting, station, fmt="json"):
    runner = CliRunner()

    return runner.invoke(
        cli,
        f"stations_result --provider={provider} --network={network} " f"{setting} --station={station} --format={fmt}",
    )


def invoke_wetterdienst_stations_export(provider, network, setting, station, target):
    runner = CliRunner()

    return runner.invoke(
        cli,
        f"stations_result --provider={provider} --network={network} "
        f"{setting} --station={station} --target={target}",
    )


def invoke_wetterdienst_stations_geo(provider, network, setting, fmt="json"):
    runner = CliRunner()

    return runner.invoke(
        cli,
        f"stations_result --provider={provider} --network={network} "
        f"{setting} --coordinates=51.1280,13.7543 --rank=5 "
        f"--format={fmt}",
    )


def invoke_wetterdienst_values_static(provider, network, setting, station, fmt="json"):
    runner = CliRunner()

    return runner.invoke(
        cli,
        f"values --provider={provider} --network={network} " f"{setting} --station={station} --format={fmt}",
    )


def invoke_wetterdienst_values_export(provider, network, setting, station, target):
    runner = CliRunner()

    return runner.invoke(
        cli,
        f"values --provider={provider} --network={network} " f"{setting} --station={station} --target={target}",
    )


def invoke_wetterdienst_values_static_tidy(provider, network, setting, station, fmt="json"):
    runner = CliRunner()

    return runner.invoke(
        cli,
        f"values --provider={provider} --network={network} " f"{setting} --station={station} --format={fmt} --tidy",
    )


def invoke_wetterdienst_values_geo(provider, network, setting, fmt="json"):
    runner = CliRunner()

    return runner.invoke(
        cli,
        f"values --provider={provider} --network={network} {setting} "
        f"--coordinates=51.1280,13.7543 --rank=5 --format={fmt}",
    )


def test_no_provider():
    runner = CliRunner()

    result = runner.invoke(cli, "stations_result --provider=abc --network=abc")

    assert "Error: Invalid value for '--provider': 'abc' is not one of 'DWD', 'ECCC', 'NOAA'" in result.output


def test_no_network(caplog):
    runner = CliRunner()

    runner.invoke(
        cli, "stations_result --provider=dwd --network=abc --parameter=precipitation_height --resolution=daily --all"
    )

    assert "No API available for provider DWD and network abc" in caplog.text


def test_data_range():
    runner = CliRunner()

    result = runner.invoke(
        cli,
        "values --provider=eccc --network=observation --parameter=precipitation_height "
        "--resolution=daily --name=toronto",
    )

    assert isinstance(result.exception, TypeError)
    assert "Combination of provider ECCC and network OBSERVATION requires start and end date" in str(result.exception)


@pytest.mark.parametrize(
    "provider,network,setting,station_id,expected_dict,coordinates",
    SETTINGS_STATIONS,
)
def test_cli_stations_json(provider, network, setting, station_id, expected_dict, coordinates):
    result = invoke_wetterdienst_stations_static(
        provider=provider, network=network, setting=setting, station=station_id, fmt="json"
    )

    response = json.loads(result.output)

    first = response[0]
    first.pop("to_date")

    assert first == expected_dict


@pytest.mark.parametrize("provider,network,setting,station_id,expected_dict,coordinates", SETTINGS_STATIONS)
def test_cli_stations_empty(provider, network, setting, station_id, expected_dict, coordinates, caplog):

    result = invoke_wetterdienst_stations_empty(provider=provider, network=network, setting=setting, fmt="json")

    assert isinstance(result.exception, SystemExit)
    assert "ERROR" in caplog.text
    assert "No stations_result available for given constraints" in caplog.text


@pytest.mark.parametrize("provider,network,setting,station_id,expected_dict,coordinates", SETTINGS_STATIONS)
def test_cli_stations_geojson(provider, network, setting, station_id, expected_dict, coordinates):
    result = invoke_wetterdienst_stations_static(
        provider=provider, network=network, setting=setting, station=station_id, fmt="geojson"
    )

    response = json.loads(result.output)

    first = response["features"][0]

    first_prop = first["properties"]
    first_prop.pop("to_date")

    expected_dict_geo = expected_dict.copy()
    expected_dict_geo["id"] = expected_dict_geo.pop("station_id")

    assert first_prop.items() <= expected_dict_geo.items()
    assert first["geometry"]["coordinates"] == coordinates


@pytest.mark.parametrize(
    "provider,network,setting,station_id,expected_dict,coordinates",
    SETTINGS_STATIONS,
)
def test_cli_stations_csv(provider, network, setting, station_id, expected_dict, coordinates):

    result = invoke_wetterdienst_stations_static(
        provider=provider, network=network, setting=setting, station=station_id, fmt="csv"
    )

    assert expected_dict["name"] in result.output


@pytest.mark.parametrize(
    "provider,network,setting,station_id,expected_dict,coordinates",
    SETTINGS_STATIONS,
)
def test_cli_stations_excel(provider, network, setting, station_id, expected_dict, coordinates, tmpdir_factory):

    # filename = tmpdir_factory.mktemp("data").join("stations_result.xlsx")  # Noqa:E800
    filename = "stations_result.xlsx"

    _ = invoke_wetterdienst_stations_export(
        provider=provider,
        network=network,
        setting=setting,
        station=station_id,
        target=f"file://{filename}",
    )

    df = pd.read_excel("stations_result.xlsx", sheet_name="Sheet1", dtype=str)

    assert "name" in df
    assert expected_dict["name"] in df["name"].values


@pytest.mark.parametrize(
    "setting,expected_columns",
    zip(
        SETTINGS_VALUES,
        (("precipitation_height", "temperature_air_max_200"), ("wind_direction",)),
    ),
)
def test_cli_values_json(setting, expected_columns, capsys, caplog):
    provider, network, setting, station_id, station_name = setting

    result = invoke_wetterdienst_values_static(
        provider=provider, network=network, setting=setting, station=station_id, fmt="json"
    )

    response = json.loads(result.stdout)

    station_ids = {reading["station_id"] for reading in response}

    assert station_id in station_ids

    expected_columns = {"station_id", "date"}.union(expected_columns)

    first = response[0]

    assert set(first.keys()).issuperset(expected_columns)


@pytest.mark.parametrize("provider,network,setting,station_id,station_name", SETTINGS_VALUES)
def test_cli_values_json_tidy(provider, network, setting, station_id, station_name):

    result = invoke_wetterdienst_values_static_tidy(
        provider=provider, network=network, setting=setting, station=station_id, fmt="json"
    )

    response = json.loads(result.output)

    station_ids = {reading["station_id"] for reading in response}

    assert station_id in station_ids

    first = response[0]

    assert set(first.keys()).issuperset(
        {
            "station_id",
            "date",
            "parameter",
            "value",
            "quality",
        }
    )


@pytest.mark.parametrize(
    "provider,network,setting,station_id,expected_dict,coordinates",
    SETTINGS_STATIONS,
)
def test_cli_values_geojson_failure(provider, network, setting, station_id, expected_dict, coordinates, capsys):
    result = invoke_wetterdienst_values_static(
        provider=provider, network=network, setting=setting, station=station_id, fmt="geojson"
    )

    assert "Error: Invalid value for '--format': 'geojson' is not one of 'json', 'csv'" in result.output


@pytest.mark.parametrize(
    "provider,network,setting,station_id,station_name",
    SETTINGS_VALUES,
)
def test_cli_values_csv(provider, network, setting, station_id, station_name):

    result = invoke_wetterdienst_values_static(
        provider=provider, network=network, setting=setting, station=station_id, fmt="csv"
    )
    assert station_id in result.output


@pytest.mark.parametrize(
    "provider,network,setting,station_id,station_name",
    SETTINGS_VALUES,
)
def test_cli_values_excel(provider, network, setting, station_id, station_name, tmpdir_factory):

    # filename = tmpdir_factory.mktemp("data").join("values.xlsx") # Noqa:E800
    filename = "values.xlsx"

    _ = invoke_wetterdienst_values_export(
        provider=provider,
        network=network,
        setting=setting,
        station=station_id,
        target=f"file://{filename}",
    )

    df = pd.read_excel("values.xlsx", sheet_name="Sheet1", dtype=str)

    assert "station_id" in df
    assert station_id in df["station_id"].values


@pytest.mark.parametrize(
    "provider,network,setting,station_id,station_name",
    SETTINGS_VALUES,
)
def test_cli_values_format_unknown(provider, network, setting, station_id, station_name):
    result = invoke_wetterdienst_values_static(
        provider=provider, network=network, setting=setting, station=station_id, fmt="foobar"
    )

    assert "Error: Invalid value for '--format': 'foobar' is not one of 'json', 'csv'" in result.output


@pytest.mark.parametrize(
    "provider,network,setting,station_id,expected_dict,coordinates",
    SETTINGS_STATIONS,
)
def test_cli_stations_geospatial(provider, network, setting, station_id, expected_dict, coordinates):

    result = invoke_wetterdienst_stations_geo(provider=provider, network=network, setting=setting, fmt="json")

    response = json.loads(result.output)

    first = response[0]

    first_filtered = {k: first[k] for k in expected_dict.keys()}

    assert first_filtered == expected_dict


@pytest.mark.parametrize(
    "provider,network,setting,station_id,station_name",
    SETTINGS_VALUES,
)
def test_cli_values_geospatial(provider, network, setting, station_id, station_name):

    result = invoke_wetterdienst_values_geo(provider=provider, network=network, setting=setting, fmt="json")

    response = json.loads(result.output)

    station_ids = {reading["station_id"] for reading in response}

    assert station_id in station_ids


def test_cli_radar_stations_opera():
    runner = CliRunner()

    result = runner.invoke(cli, "radar --odim-code=ukdea")

    response = json.loads(result.output)

    assert isinstance(response, dict)

    assert response["location"] == "Dean Hill"


def test_cli_radar_stations_dwd():
    runner = CliRunner()

    result = runner.invoke(cli, "radar --dwd")

    response = json.loads(result.output)

    assert isinstance(response, list)

    assert len(response) == 20
