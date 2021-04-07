# -*- coding: utf-8 -*-
# Copyright (c) 2018-2021, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
import json
import shlex
import sys
import zipfile
from datetime import datetime, timedelta

import docopt
import pytest

from wetterdienst.ui import cli

# Individual settings for observation and forecast
SETTINGS_STATIONS = [
    "observation stations --resolution=daily --parameter=kl --period=recent",
    "forecast stations --parameter=large",
]

SETTINGS_READINGS = [
    "observation values --resolution=daily --parameter=kl --period=recent "
    "--date=2020-06-30",
    f"forecast values --parameter=DD --mosmix-type=large"
    f"--date={datetime.strftime(datetime.today() + timedelta(days=2), '%Y-%m-%d')}",
]

SETTINGS_STATION = [
    "01048",  # observation stations
    "10488",  # mosmix forecast stations
]

EXPECTED_STATION_NAME = [
    "Dresden-Klotzsche",
    "DRESDEN",
]


def test_cli_help():

    with pytest.raises(docopt.DocoptExit) as excinfo:
        cli.run()

    response = str(excinfo.value)
    assert "wetterdienst dwd observation stations" in response
    assert "wetterdienst dwd observation values" in response
    assert "wetterdienst dwd forecast stations" in response
    assert "wetterdienst dwd forecast values" in response
    assert "wetterdienst dwd about" in response


def test_cli_about_parameters(capsys):

    sys.argv = ["wetterdienst", "dwd", "about", "parameters"]
    cli.run()
    stdout, stderr = capsys.readouterr()

    response = stdout
    assert "precipitation" in response
    assert "air_temperature" in response
    assert "weather_phenomena" in response


def test_cli_about_resolutions(capsys):

    sys.argv = ["wetterdienst", "dwd", "about", "resolutions"]
    cli.run()
    stdout, stderr = capsys.readouterr()

    response = stdout
    assert "1_minute" in response
    assert "hourly" in response
    assert "annual" in response


def test_cli_about_periods(capsys):

    sys.argv = ["wetterdienst", "dwd", "about", "periods"]
    cli.run()
    stdout, stderr = capsys.readouterr()

    response = stdout
    assert "historical" in response
    assert "recent" in response
    assert "now" in response


def test_cli_about_coverage(capsys):

    sys.argv = ["wetterdienst", "dwd", "about", "coverage"]
    cli.run()
    stdout, stderr = capsys.readouterr()

    response = stdout
    assert "minute_1" in response
    assert "precipitation" in response


def invoke_wetterdienst_stations_empty(setting, fmt="json"):
    argv = shlex.split(f"wetterdienst dwd {setting} --station=123456 --format={fmt}")
    sys.argv = argv
    cli.run()


def invoke_wetterdienst_stations_static(setting, station, fmt="json"):
    argv = shlex.split(f"wetterdienst dwd {setting} --station={station} --format={fmt}")
    sys.argv = argv
    cli.run()


def invoke_wetterdienst_stations_export(setting, station, target):
    argv = shlex.split(
        f"wetterdienst dwd {setting} --station={station} --target={target}"
    )
    sys.argv = argv
    cli.run()


def invoke_wetterdienst_stations_geo(setting, fmt="json"):
    argv = shlex.split(
        f"wetterdienst dwd {setting} --latitude=51.1280 --longitude=13.7543 --rank=5 "
        f"--format={fmt}"
    )
    sys.argv = argv
    cli.run()


def invoke_wetterdienst_values_static(setting, station, fmt="json"):
    argv = shlex.split(f"wetterdienst dwd {setting} --station={station} --format={fmt}")
    sys.argv = argv
    cli.run()


def invoke_wetterdienst_values_export(setting, station, target):
    argv = shlex.split(
        f"wetterdienst dwd {setting} --station={station} --target={target}"
    )
    sys.argv = argv
    cli.run()


def invoke_wetterdienst_values_static_tidy(setting, station, fmt="json"):
    argv = shlex.split(
        f"wetterdienst dwd {setting} --station={station} --format={fmt} --tidy"
    )
    sys.argv = argv
    cli.run()


def invoke_wetterdienst_values_geo(setting, fmt="json"):
    argv = shlex.split(
        f"wetterdienst dwd {setting} --latitude=51.1280 --longitude=13.7543 --rank=5 "
        f"--format={fmt}"
    )
    sys.argv = argv
    cli.run()


@pytest.mark.parametrize(
    "setting,station,expected_station_name",
    zip(SETTINGS_STATIONS, SETTINGS_STATION, EXPECTED_STATION_NAME),
)
def test_cli_stations_json(setting, station, expected_station_name, capsys):

    invoke_wetterdienst_stations_static(setting=setting, station=station, fmt="json")

    stdout, stderr = capsys.readouterr()
    response = json.loads(stdout)

    station_names = [station["name"] for station in response]

    assert expected_station_name in station_names


@pytest.mark.parametrize("setting", SETTINGS_STATIONS)
def test_cli_stations_empty(setting, caplog):

    with pytest.raises(SystemExit):
        invoke_wetterdienst_stations_empty(setting=setting, fmt="json")

    assert "ERROR" in caplog.text
    assert "No data available for given constraints" in caplog.text


# TODO: make forecast formattable as GEOJSON/make to_geojson compatible with WMO_ID
@pytest.mark.parametrize(
    "setting,station,expected_station_name",
    zip(SETTINGS_STATIONS[:1], SETTINGS_STATION[:1], EXPECTED_STATION_NAME[:1]),
)
def test_cli_stations_geojson(setting, station, expected_station_name, capsys):

    invoke_wetterdienst_stations_static(setting=setting, station=station, fmt="geojson")

    stdout, stderr = capsys.readouterr()
    response = json.loads(stdout)

    assert len(response["features"]) == 1

    station_names = [station["properties"]["name"] for station in response["features"]]

    assert expected_station_name in station_names


@pytest.mark.parametrize(
    "setting,station,expected_station_name",
    zip(SETTINGS_STATIONS, SETTINGS_STATION, EXPECTED_STATION_NAME),
)
def test_cli_stations_csv(setting, station, expected_station_name, capsys):

    invoke_wetterdienst_stations_static(setting=setting, station=station, fmt="csv")

    stdout, stderr = capsys.readouterr()

    assert expected_station_name in stdout


@pytest.mark.parametrize(
    "setting,station,expected_station_name",
    zip(SETTINGS_STATIONS, SETTINGS_STATION, EXPECTED_STATION_NAME),
)
def test_cli_stations_excel(
    setting, station, expected_station_name, capsys, tmpdir_factory
):

    # filename = tmpdir_factory.mktemp("data").join("stations.xlsx")
    filename = "stations.xlsx"

    invoke_wetterdienst_stations_export(
        setting=setting, station=station, target=f"file://{filename}"
    )

    with zipfile.ZipFile(filename, "r") as zip_file:
        payload = zip_file.read("xl/worksheets/sheet1.xml")

        assert bytes(expected_station_name, encoding="utf8") in payload


@pytest.mark.parametrize(
    "setting,station", zip(SETTINGS_READINGS[:1], SETTINGS_STATION[:1])
)
def test_cli_readings_json(setting, station, capsys):

    invoke_wetterdienst_values_static(setting=setting, station=station, fmt="json")

    stdout, stderr = capsys.readouterr()
    response = json.loads(stdout)

    station_ids = list(set([reading["station_id"] for reading in response]))

    assert station in station_ids

    first = response[0]
    assert set(first.keys()).issuperset(
        (
            "station_id",
            "date",
            # "quality_wind",
            "wind_gust_max",
            "wind_speed",
            # "quality_general",
            "precipitation_height",
            "precipitation_form",
            "sunshine_duration",
            "snow_depth",
            "cloud_cover_total",
            "pressure_vapor",
            "pressure_air",
            "temperature_air_200",
            "humidity",
            "temperature_air_max_200",
            "temperature_air_min_200",
            "temperature_air_min_005",
        )
    )


@pytest.mark.parametrize("setting,station", zip(SETTINGS_READINGS, SETTINGS_STATION))
def test_cli_readings_json_tidy(setting, station, capsys):

    invoke_wetterdienst_values_static_tidy(setting=setting, station=station, fmt="json")

    stdout, stderr = capsys.readouterr()
    response = json.loads(stdout)

    station_ids = list(set([reading["station_id"] for reading in response]))

    assert station in station_ids

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


@pytest.mark.parametrize("setting,station", zip(SETTINGS_READINGS, SETTINGS_STATION))
def test_cli_readings_geojson(setting, station):

    with pytest.raises(KeyError) as excinfo:
        invoke_wetterdienst_values_static(
            setting=setting, station=station, fmt="geojson"
        )

    assert excinfo.typename == "KeyError"
    assert str(excinfo.value) == "'GeoJSON format only available for stations output'"


@pytest.mark.parametrize("setting,station", zip(SETTINGS_READINGS, SETTINGS_STATION))
def test_cli_readings_csv(setting, station, capsys):

    invoke_wetterdienst_values_static(setting=setting, station=station, fmt="csv")

    stdout, stderr = capsys.readouterr()

    assert station in stdout


@pytest.mark.parametrize("setting,station", zip(SETTINGS_READINGS, SETTINGS_STATION))
def test_cli_readings_excel(setting, station, tmpdir_factory):

    # filename = tmpdir_factory.mktemp("data").join("readings.xlsx")
    filename = "readings.xlsx"

    invoke_wetterdienst_values_export(
        setting=setting, station=station, target=f"file://{filename}"
    )

    with zipfile.ZipFile(filename, "r") as zip_file:
        payload = zip_file.read("xl/worksheets/sheet1.xml")

        assert bytes(station, encoding="utf8") in payload


@pytest.mark.parametrize("setting,station", zip(SETTINGS_READINGS, SETTINGS_STATION))
def test_cli_readings_format_unknown(setting, station, caplog):

    with pytest.raises(SystemExit):
        invoke_wetterdienst_values_static(
            setting=setting, station=station, fmt="foobar"
        )

    assert "ERROR" in caplog.text
    assert "Unknown output format" in caplog.text


@pytest.mark.parametrize(
    "setting,station", zip(SETTINGS_STATIONS, EXPECTED_STATION_NAME)
)
def test_cli_stations_geospatial(setting, station, capsys):

    invoke_wetterdienst_stations_geo(setting=setting, fmt="json")

    stdout, stderr = capsys.readouterr()
    response = json.loads(stdout)

    station_names = [station["name"] for station in response]

    assert station in station_names


@pytest.mark.parametrize(
    "setting,station", zip(SETTINGS_READINGS[:1], SETTINGS_STATION[:1])
)
def test_cli_readings_geospatial(setting, station, capsys):

    invoke_wetterdienst_values_geo(setting=setting, fmt="json")

    stdout, stderr = capsys.readouterr()
    response = json.loads(stdout)

    station_ids = list(set([reading["station_id"] for reading in response]))

    assert station in station_ids


def test_cli_radar_stations_opera(capsys):

    sys.argv = ["wetterdienst", "radar", "stations", "--odim-code=ukdea"]
    cli.run()
    stdout, stderr = capsys.readouterr()

    response = json.loads(stdout)
    assert isinstance(response, dict)
    assert response["location"] == "Dean Hill"


def test_cli_radar_stations_dwd(capsys):

    sys.argv = ["wetterdienst", "dwd", "radar", "stations"]
    cli.run()
    stdout, stderr = capsys.readouterr()

    response = json.loads(stdout)
    assert isinstance(response, list)
    assert len(response) == 20
