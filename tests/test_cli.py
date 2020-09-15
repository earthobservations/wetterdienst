import json
import shlex
import sys
import zipfile

import pytest
import docopt
from wetterdienst import cli


def test_cli_help():

    with pytest.raises(docopt.DocoptExit) as excinfo:
        cli.run()

    response = str(excinfo.value)
    assert "wetterdienst stations" in response
    assert "wetterdienst readings" in response
    assert "wetterdienst about" in response


def test_cli_about_parameters(capsys):

    sys.argv = ["wetterdienst", "about", "parameters"]
    cli.run()
    stdout, stderr = capsys.readouterr()

    response = stdout
    assert "precipitation" in response
    assert "air_temperature" in response
    assert "weather_phenomena" in response
    assert "radolan" in response


def test_cli_about_resolutions(capsys):

    sys.argv = ["wetterdienst", "about", "resolutions"]
    cli.run()
    stdout, stderr = capsys.readouterr()

    response = stdout
    assert "1_minute" in response
    assert "hourly" in response
    assert "annual" in response


def test_cli_about_periods(capsys):

    sys.argv = ["wetterdienst", "about", "periods"]
    cli.run()
    stdout, stderr = capsys.readouterr()

    response = stdout
    assert "historical" in response
    assert "recent" in response
    assert "now" in response


def invoke_wetterdienst_stations(format="json"):
    argv = shlex.split(
        f"wetterdienst stations --resolution=daily --parameter=kl --period=recent --lat=49.9195 --lon=8.9671 --num=5 --format={format}"  # noqa:E501,B950
    )
    sys.argv = argv
    cli.run()


def invoke_wetterdienst_readings(format="json"):
    argv = shlex.split(
        f"wetterdienst readings --resolution=daily --parameter=kl --period=recent --lat=49.9195 --lon=8.9671 --num=5 --date=2020-06-30 --format={format}"  # noqa:E501,B950
    )
    sys.argv = argv
    cli.run()


def test_cli_stations_json(capsys):

    invoke_wetterdienst_stations(format="json")

    stdout, stderr = capsys.readouterr()
    response = json.loads(stdout)

    station_names = [station["station_name"] for station in response]

    assert "Schaafheim-Schlierbach" in station_names
    assert "Offenbach-Wetterpark" in station_names

    # Please remove if too flakey.
    assert station_names == [
        "Schaafheim-Schlierbach",
        "Kahl/Main",
        "Michelstadt-Vielbrunn",
        "Offenbach-Wetterpark",
        "Michelstadt",
    ]


def test_cli_stations_geojson(capsys):

    invoke_wetterdienst_stations(format="geojson")

    stdout, stderr = capsys.readouterr()
    response = json.loads(stdout)

    assert len(response["features"]) == 5

    station_names = [station["properties"]["name"] for station in response["features"]]

    assert "Schaafheim-Schlierbach" in station_names
    assert "Offenbach-Wetterpark" in station_names


def test_cli_stations_csv(capsys):

    invoke_wetterdienst_stations(format="csv")

    stdout, stderr = capsys.readouterr()

    assert "Schaafheim-Schlierbach" in stdout
    assert "Offenbach-Wetterpark" in stdout


def test_cli_stations_excel(capsys):

    invoke_wetterdienst_stations(format="excel")

    # FIXME: Make --format=excel write to a designated file.
    filename = "output.xlsx"
    with zipfile.ZipFile(filename, "r") as zip:
        payload = zip.read("xl/worksheets/sheet1.xml")

        assert b"Schaafheim-Schlierbach" in payload
        assert b"Offenbach-Wetterpark" in payload


def test_cli_readings_json(capsys):

    invoke_wetterdienst_readings(format="json")

    stdout, stderr = capsys.readouterr()
    response = json.loads(stdout)

    station_ids = list(set([reading["station_id"] for reading in response]))

    assert 2480 in station_ids
    assert 4411 in station_ids


def test_cli_readings_csv(capsys):

    invoke_wetterdienst_readings(format="csv")

    stdout, stderr = capsys.readouterr()

    assert str(2480) in stdout
    assert str(4411) in stdout


def test_cli_readings_excel(capsys):

    invoke_wetterdienst_stations(format="excel")

    # FIXME: Make --format=excel write to a designated file.
    filename = "output.xlsx"
    with zipfile.ZipFile(filename, "r") as zip:
        payload = zip.read("xl/worksheets/sheet1.xml")

        assert b"2480" in payload
        assert b"4411" in payload
