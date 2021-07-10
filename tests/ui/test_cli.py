# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import json
import zipfile
from datetime import datetime, timedelta

import pytest
from click.testing import CliRunner

from wetterdienst.ui.cli import cli

# Individual settings for observation and forecast
SETTINGS_STATIONS = (
    (
        "dwd",
        "observation",
        "--resolution=daily --parameter=kl --period=recent",
        "01048",
        "Dresden-Klotzsche",
    ),
    (
        "dwd",
        "forecast",
        "--resolution=large --parameter=large",
        "10488",
        "DRESDEN",
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
        "forecast",
        f"--parameter=DD --resolution=large "
        f"--date={datetime.strftime(datetime.today() + timedelta(days=2), '%Y-%m-%d')}",
        "10488",
        "DRESDEN",
    ),
)


def test_cli_help():
    runner = CliRunner()

    result = runner.invoke(cli, [])

    assert "Options:\n --help  Show this message and exit."
    assert (
        "Commands:\n  about\n  explorer\n  radar\n  "
        "restapi\n  show\n  stations\n  values\n" in result.output
    )


# def test_cli_about_parameters(capsys):
#     runner = CliRunner()
#
#     result = runner.invoke(cli, "about coverage --provider=dwd --kind=observation")
#
#     assert "precipitation" in result.output
#     assert "temperature_air" in result.output
#     assert "weather_phenomena" in result.output


# def test_cli_about_resolutions(capsys):
#     runner = CliRunner()
#
#     result = runner.invoke(cli, "about coverage --provider=dwd --kind=observation")
#
#     sys.argv = ["wetterdienst", "dwd", "about", "resolutions"]
#     cli.cli()
#     stdout, stderr = capsys.readouterr()
#
#     response = stdout
#     assert "1_minute" in response
#     assert "hourly" in response
#     assert "annual" in response


# def test_cli_about_periods(capsys):
#
#     sys.argv = ["wetterdienst", "dwd", "about", "periods"]
#     cli.cli()
#     stdout, stderr = capsys.readouterr()
#
#     response = stdout
#     assert "historical" in response
#     assert "recent" in response
#     assert "now" in response


def test_cli_about_coverage(capsys):
    runner = CliRunner()

    result = runner.invoke(cli, "about coverage --provider=dwd --kind=observation")

    assert "minute_1" in result.output
    assert "precipitation" in result.output


def invoke_wetterdienst_stations_empty(provider, kind, setting, fmt="json"):
    runner = CliRunner()

    result = runner.invoke(
        cli,
        f"stations --provider={provider} --kind={kind} "
        f"{setting} --station=123456 --format={fmt}",
    )

    return result


def invoke_wetterdienst_stations_static(provider, kind, setting, station, fmt="json"):
    runner = CliRunner()

    result = runner.invoke(
        cli,
        f"stations --provider={provider} --kind={kind} "
        f"{setting} --station={station} --format={fmt}",
    )

    return result


def invoke_wetterdienst_stations_export(provider, kind, setting, station, target):
    runner = CliRunner()

    result = runner.invoke(
        cli,
        f"stations --provider={provider} --kind={kind} "
        f"{setting} --station={station} --target={target}",
    )

    return result


def invoke_wetterdienst_stations_geo(provider, kind, setting, fmt="json"):
    runner = CliRunner()

    result = runner.invoke(
        cli,
        f"stations --provider={provider} --kind={kind} "
        f"{setting} --coordinates=51.1280,13.7543 --rank=5 "
        f"--format={fmt}",
    )

    return result


def invoke_wetterdienst_values_static(provider, kind, setting, station, fmt="json"):
    runner = CliRunner()

    result = runner.invoke(
        cli,
        f"values --provider={provider} --kind={kind} "
        f"{setting} --station={station} --format={fmt}",
    )

    return result


def invoke_wetterdienst_values_export(provider, kind, setting, station, target):
    runner = CliRunner()

    result = runner.invoke(
        cli,
        f"values --provider={provider} --kind={kind} "
        f"{setting} --station={station} --target={target}",
    )

    return result


def invoke_wetterdienst_values_static_tidy(
    provider, kind, setting, station, fmt="json"
):
    runner = CliRunner()

    result = runner.invoke(
        cli,
        f"values --provider={provider} --kind={kind} "
        f"{setting} --station={station} --format={fmt} --tidy",
    )

    return result


def invoke_wetterdienst_values_geo(provider, kind, setting, fmt="json"):
    runner = CliRunner()

    result = runner.invoke(
        cli,
        f"values --provider={provider} --kind={kind} {setting} "
        f"--coordinates=51.1280,13.7543 --rank=5 --format={fmt}",
    )

    return result


def test_no_provider():
    runner = CliRunner()

    result = runner.invoke(cli, "stations --provider=abc --kind=abc")

    assert (
        "Error: Invalid value for '--provider': invalid choice: abc." in result.output
    )


def test_no_kind():
    runner = CliRunner()

    result = runner.invoke(cli, "stations --provider=dwd --kind=abc")

    assert "Invalid value for '--kind': invalid choice: abc." in result.output


def test_data_range(capsys):
    runner = CliRunner()

    result = runner.invoke(
        cli,
        "values --provider=eccc --kind=observation --parameter=precipitation_height "
        "--resolution=daily --name=toronto",
    )

    assert isinstance(result.exception, TypeError)
    assert (
        "Combination of provider ECCC and kind OBSERVATION requires start and end date"
        in str(result.exception)
    )


@pytest.mark.parametrize(
    "provider,kind,setting,station_id,station_name",
    SETTINGS_STATIONS,
)
def test_cli_stations_json(provider, kind, setting, station_id, station_name):
    result = invoke_wetterdienst_stations_static(
        provider=provider, kind=kind, setting=setting, station=station_id, fmt="json"
    )

    response = json.loads(result.output)

    station_names = [station["name"] for station in response]

    assert station_name in station_names


@pytest.mark.parametrize(
    "provider,kind,setting,station_id,station_name", SETTINGS_STATIONS
)
def test_cli_stations_empty(provider, kind, setting, station_id, station_name, caplog):

    result = invoke_wetterdienst_stations_empty(
        provider=provider, kind=kind, setting=setting, fmt="json"
    )

    assert isinstance(result.exception, SystemExit)
    assert "ERROR" in caplog.text
    assert "No stations available for given constraints" in caplog.text


@pytest.mark.parametrize(
    "provider,kind,setting,station_id,station_name",
    SETTINGS_STATIONS,
)
def test_cli_stations_geojson(provider, kind, setting, station_id, station_name):

    result = invoke_wetterdienst_stations_static(
        provider=provider, kind=kind, setting=setting, station=station_id, fmt="geojson"
    )

    response = json.loads(result.output)

    assert len(response["features"]) == 1

    station_names = [station["properties"]["name"] for station in response["features"]]

    assert station_name in station_names


@pytest.mark.parametrize(
    "provider,kind,setting,station_id,station_name",
    SETTINGS_STATIONS,
)
def test_cli_stations_csv(provider, kind, setting, station_id, station_name):

    result = invoke_wetterdienst_stations_static(
        provider=provider, kind=kind, setting=setting, station=station_id, fmt="csv"
    )

    assert station_name in result.output


@pytest.mark.parametrize(
    "provider,kind,setting,station_id,station_name",
    SETTINGS_STATIONS,
)
def test_cli_stations_excel(
    provider, kind, setting, station_id, station_name, tmpdir_factory
):

    # filename = tmpdir_factory.mktemp("data").join("stations.xlsx")
    filename = "stations.xlsx"

    _ = invoke_wetterdienst_stations_export(
        provider=provider,
        kind=kind,
        setting=setting,
        station=station_id,
        target=f"file://{filename}",
    )

    with zipfile.ZipFile(filename, "r") as zip_file:
        payload = zip_file.read("xl/worksheets/sheet1.xml")

        assert bytes(station_name, encoding="utf8") in payload


@pytest.mark.parametrize(
    "setting,expected_columns",
    zip(
        SETTINGS_VALUES,
        (("precipitation_height", "temperature_air_max_200"), ("wind_direction",)),
    ),
)
def test_cli_values_json(setting, expected_columns, capsys, caplog):
    provider, kind, setting, station_id, station_name = setting

    result = invoke_wetterdienst_values_static(
        provider=provider, kind=kind, setting=setting, station=station_id, fmt="json"
    )

    response = json.loads(result.stdout)

    station_ids = list(set([reading["station_id"] for reading in response]))

    assert station_id in station_ids

    expected_columns = {"station_id", "date"}.union(expected_columns)

    first = response[0]
    assert set(list(first.keys())).issuperset(expected_columns)


@pytest.mark.parametrize(
    "provider,kind,setting,station_id,station_name", SETTINGS_VALUES
)
def test_cli_values_json_tidy(provider, kind, setting, station_id, station_name):

    result = invoke_wetterdienst_values_static_tidy(
        provider=provider, kind=kind, setting=setting, station=station_id, fmt="json"
    )

    response = json.loads(result.output)

    station_ids = list(set([reading["station_id"] for reading in response]))

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
    "provider,kind,setting,station_id,station_name",
    SETTINGS_STATIONS,
)
def test_cli_values_geojson(provider, kind, setting, station_id, station_name, capsys):
    result = invoke_wetterdienst_values_static(
        provider=provider, kind=kind, setting=setting, station=station_id, fmt="geojson"
    )

    assert (
        "Error: Invalid value for '--format': invalid choice: "
        "geojson. (choose from json, csv)" in result.output
    )


@pytest.mark.parametrize(
    "provider,kind,setting,station_id,station_name",
    SETTINGS_VALUES,
)
def test_cli_values_csv(provider, kind, setting, station_id, station_name):

    result = invoke_wetterdienst_values_static(
        provider=provider, kind=kind, setting=setting, station=station_id, fmt="csv"
    )

    assert station_id in result.output


@pytest.mark.parametrize(
    "provider,kind,setting,station_id,station_name",
    SETTINGS_VALUES,
)
def test_cli_values_excel(
    provider, kind, setting, station_id, station_name, tmpdir_factory
):

    # filename = tmpdir_factory.mktemp("data").join("values.xlsx")
    filename = "values.xlsx"

    _ = invoke_wetterdienst_values_export(
        provider=provider,
        kind=kind,
        setting=setting,
        station=station_id,
        target=f"file://{filename}",
    )

    # pd.read_excel("values.xlsx")

    with zipfile.ZipFile(filename, "r") as zip_file:
        payload = zip_file.read("xl/worksheets/sheet1.xml")

        assert bytes(station_id, encoding="utf8") in payload


@pytest.mark.parametrize(
    "provider,kind,setting,station_id,station_name",
    SETTINGS_VALUES,
)
def test_cli_values_format_unknown(provider, kind, setting, station_id, station_name):
    result = invoke_wetterdienst_values_static(
        provider=provider, kind=kind, setting=setting, station=station_id, fmt="foobar"
    )

    assert (
        "Error: Invalid value for '--format': "
        "invalid choice: foobar. (choose from json, csv)" in result.output
    )


@pytest.mark.parametrize(
    "provider,kind,setting,station_id,station_name",
    SETTINGS_STATIONS,
)
def test_cli_stations_geospatial(provider, kind, setting, station_id, station_name):

    result = invoke_wetterdienst_stations_geo(
        provider=provider, kind=kind, setting=setting, fmt="json"
    )

    response = json.loads(result.output)

    station_names = [station["name"] for station in response]

    assert station_name in station_names


@pytest.mark.parametrize(
    "provider,kind,setting,station_id,station_name",
    SETTINGS_VALUES,
)
def test_cli_values_geospatial(provider, kind, setting, station_id, station_name):

    result = invoke_wetterdienst_values_geo(
        provider=provider, kind=kind, setting=setting, fmt="json"
    )

    response = json.loads(result.output)

    station_ids = list(set([reading["station_id"] for reading in response]))

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
