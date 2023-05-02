# -*- coding: utf-8 -*-
# Copyright (C) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import json
from datetime import datetime, timedelta
from pathlib import Path

import polars as pl
import pytest
from click.testing import CliRunner
from dirty_equals import IsDict

from wetterdienst.ui.cli import cli

# Individual settings for observation and mosmix
SETTINGS_STATIONS = (
    (
        "dwd",
        "observation",
        "--resolution=daily --parameter=kl --period=recent",
        ("01048",),
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
        ("10488",),
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
        "--resolution=daily --parameter=kl --date=2020-06-30",
        ("01047", "01048"),
        "Dresden-Klotzsche",
    ),
    (
        "dwd",
        "mosmix",
        f"--parameter=large --resolution=large "
        f"--date={datetime.strftime(datetime.today() + timedelta(days=2), '%Y-%m-%d')}",
        ("10488",),
        "DRESDEN",
    ),
)


def test_cli_help():
    """Test cli help"""
    runner = CliRunner()
    result = runner.invoke(cli, [])
    assert "Options:\n --help  Show this message and exit."
    assert (
        "Commands:\n  about\n  explorer\n  info\n  interpolate\n  radar\n  "
        "restapi\n  stations\n  summarize\n  values\n  version\n" in result.output
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
        f"stations --provider={provider} --network={network} {setting} --station=123456 --format={fmt}",
    )


def invoke_wetterdienst_stations_static(provider, network, setting, station, fmt="json"):
    runner = CliRunner()
    return runner.invoke(
        cli,
        f"stations --provider={provider} --network={network} {setting} --station={','.join(station)} --format={fmt}",
    )


def invoke_wetterdienst_stations_export(provider, network, setting, station, target):
    runner = CliRunner()
    return runner.invoke(
        cli,
        f"stations --provider={provider} --network={network} {setting} --station={','.join(station)} --target={target}",
    )


def invoke_wetterdienst_stations_geo(provider, network, setting, fmt="json"):
    runner = CliRunner()
    return runner.invoke(
        cli,
        f"stations --provider={provider} --network={network} "
        f"{setting} --coordinates=51.1280,13.7543 --rank=5 "
        f"--format={fmt}",
    )


def invoke_wetterdienst_values_static(provider, network, setting, station, fmt="json"):
    runner = CliRunner()
    return runner.invoke(
        cli,
        f"values --provider={provider} --network={network} {setting} --station={','.join(station)} "
        f"--shape=wide --format={fmt}",
    )


def invoke_wetterdienst_values_export(provider, network, setting, station, target):
    runner = CliRunner()
    return runner.invoke(
        cli,
        f"values --provider={provider} --network={network} {setting} --station={','.join(station)} "
        f"--shape=wide --target={target}",
    )


def invoke_wetterdienst_values_static_tidy(provider, network, setting, station, fmt="json"):
    runner = CliRunner()
    return runner.invoke(
        cli,
        f"values --provider={provider} --network={network} "
        f"{setting} --station={','.join(station)} --format={fmt} --shape='long'",
    )


def invoke_wetterdienst_values_geo(provider, network, setting, fmt="json"):
    runner = CliRunner()
    return runner.invoke(
        cli,
        f"values --provider={provider} --network={network} {setting} "
        f"--coordinates=51.1280,13.7543 --rank=5 --shape=wide --format={fmt}",
    )


def test_no_provider():
    runner = CliRunner()
    result = runner.invoke(cli, "stations --provider=abc --network=abc")
    assert "Error: Invalid value for '--provider': 'abc' is not one of 'DWD', 'ECCC', 'NOAA'" in result.output


def test_no_network(caplog):
    runner = CliRunner()
    runner.invoke(
        cli, "stations --provider=dwd --network=abc --parameter=precipitation_height --resolution=daily --all"
    )
    assert "No API available for provider DWD and network abc" in caplog.text


@pytest.mark.remote
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
    assert "No stations available for given constraints" in caplog.text


@pytest.mark.remote
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


@pytest.mark.remote
@pytest.mark.parametrize(
    "provider,network,setting,station_id,expected_dict,coordinates",
    SETTINGS_STATIONS,
)
def test_cli_stations_csv(provider, network, setting, station_id, expected_dict, coordinates):
    result = invoke_wetterdienst_stations_static(
        provider=provider, network=network, setting=setting, station=station_id, fmt="csv"
    )
    assert expected_dict["name"] in result.output


@pytest.mark.remote
@pytest.mark.parametrize(
    "provider,network,setting,station_id,expected_dict,coordinates",
    SETTINGS_STATIONS,
)
def test_cli_stations_excel(provider, network, setting, station_id, expected_dict, coordinates, tmp_path, is_windows):
    filename = Path("stations.xlsx")
    if not is_windows:
        filename = tmp_path.joinpath(filename)
    _ = invoke_wetterdienst_stations_export(
        provider=provider,
        network=network,
        setting=setting,
        station=station_id,
        target=f"file://{filename}",
    )
    df = pl.read_excel(source=filename, sheet_name="Sheet1")
    if is_windows:
        filename.unlink(missing_ok=True)
    assert "name" in df
    assert expected_dict["name"] in df.get_column("name")


@pytest.mark.remote
@pytest.mark.parametrize(
    "setting,expected_columns",
    zip(
        SETTINGS_VALUES,
        (("precipitation_height", "temperature_air_max_200"), ("wind_direction",)),
    ),
)
def test_cli_values_json(setting, expected_columns):
    provider, network, setting, station_id, station_name = setting
    result = invoke_wetterdienst_values_static(
        provider=provider, network=network, setting=setting, station=station_id, fmt="json"
    )
    response = json.loads(result.stdout)
    station_ids = {reading["station_id"] for reading in response}
    assert set(station_id).issubset(station_ids)
    expected_columns = {"station_id", "date"}.union(expected_columns)
    first = response[0]
    assert set(first.keys()).issuperset(expected_columns)


@pytest.mark.remote
def test_cli_values_json_multiple_datasets(capsys, caplog):
    result = invoke_wetterdienst_values_static(
        provider="dwd",
        network="observation",
        setting="--resolution=daily --parameter=kl,more_precip --date=2020-06-30",
        station=("01048",),
        fmt="json",
    )
    response = json.loads(result.stdout)
    first = response[0]
    assert first == IsDict(
        {
            "station_id": "01048",
            "dataset": "climate_summary",
            "parameter": "wind_gust_max",
            "date": "2020-06-30T00:00:00+00:00",
            "value": 15.3,
            "quality": 10.0,
        }
    )


@pytest.mark.remote
@pytest.mark.parametrize("provider,network,setting,station_id,station_name", SETTINGS_VALUES)
def test_cli_values_json_tidy(provider, network, setting, station_id, station_name):
    result = invoke_wetterdienst_values_static_tidy(
        provider=provider, network=network, setting=setting, station=station_id, fmt="json"
    )
    response = json.loads(result.output)
    station_ids = {reading["station_id"] for reading in response}
    assert set(station_id).issubset(station_ids)
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


@pytest.mark.remote
@pytest.mark.parametrize(
    "provider,network,setting,station_id,station_name",
    SETTINGS_VALUES,
)
def test_cli_values_csv(provider, network, setting, station_id, station_name):
    result = invoke_wetterdienst_values_static(
        provider=provider, network=network, setting=setting, station=station_id, fmt="csv"
    )
    for s in station_id:
        assert s in result.output


@pytest.mark.remote
@pytest.mark.parametrize(
    "provider,network,setting,station_id,station_name",
    SETTINGS_VALUES,
)
def test_cli_values_excel(provider, network, setting, station_id, station_name, tmp_path, is_windows):
    filename = Path("values.xlsx")
    if not is_windows:
        filename = tmp_path.joinpath(filename)
    _ = invoke_wetterdienst_values_export(
        provider=provider,
        network=network,
        setting=setting,
        station=station_id,
        target=f"file://{filename}",
    )
    df = pl.read_excel(filename, sheet_name="Sheet1")
    if is_windows:
        filename.unlink(missing_ok=True)
    assert "station_id" in df.columns
    assert df.get_column("station_id").cast(str).apply(lambda s: any(s in sid for sid in station_id)).any()


@pytest.mark.parametrize(
    "provider,network,setting,station_id,station_name",
    SETTINGS_VALUES,
)
def test_cli_values_format_unknown(provider, network, setting, station_id, station_name):
    result = invoke_wetterdienst_values_static(
        provider=provider, network=network, setting=setting, station=station_id, fmt="foobar"
    )
    assert "Error: Invalid value for '--format': 'foobar' is not one of 'json', 'csv'" in result.output


@pytest.mark.remote
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


@pytest.mark.remote
@pytest.mark.parametrize(
    "provider,network,setting,station_id,station_name",
    SETTINGS_VALUES,
)
def test_cli_values_geospatial(provider, network, setting, station_id, station_name):
    result = invoke_wetterdienst_values_geo(provider=provider, network=network, setting=setting, fmt="json")
    response = json.loads(result.output)
    station_ids = {reading["station_id"] for reading in response}
    assert set(station_id).issubset(station_ids)


@pytest.mark.remote
def test_cli_interpolate():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        "interpolate --provider=dwd --network=observation "
        "--parameter=temperature_air_mean_200 --resolution=daily "
        "--station=00071 --date=1986-10-31/1986-11-01 --format=json",
    )
    if result.exit_code != 0:
        raise ChildProcessError(result.stderr)
    response = json.loads(result.stdout)
    assert response == [
        {
            "date": "1986-10-31T00:00:00+00:00",
            "parameter": "temperature_air_mean_200",
            "value": 279.52,
            "distance_mean": 16.99,
            "station_ids": ["00072", "02074", "02638", "04703"],
        },
        {
            "date": "1986-11-01T00:00:00+00:00",
            "parameter": "temperature_air_mean_200",
            "value": 281.85,
            "distance_mean": 0.0,
            "station_ids": ["00071"],
        },
    ]


@pytest.mark.remote
def test_cli_summarize():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        "summarize --provider=dwd --network=observation "
        "--parameter=temperature_air_mean_200 --resolution=daily "
        "--station=00071 --date=1986-10-31/1986-11-01 --format=json",
    )
    if result.exit_code != 0:
        raise ChildProcessError(result.stderr)
    response = json.loads(result.stdout)
    assert response == [
        {
            "date": "1986-10-31T00:00:00+00:00",
            "parameter": "temperature_air_mean_200",
            "value": 279.75,
            "distance": 6.97,
            "station_id": "00072",
        },
        {
            "date": "1986-11-01T00:00:00+00:00",
            "parameter": "temperature_air_mean_200",
            "value": 281.85,
            "distance": 0.0,
            "station_id": "00071",
        },
    ]


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
