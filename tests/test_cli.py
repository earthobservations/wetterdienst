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
    assert "wetterdienst dwd stations" in response
    assert "wetterdienst dwd readings" in response
    assert "wetterdienst dwd about" in response


def test_cli_about_parameters(capsys):

    sys.argv = ["wetterdienst", "dwd", "about", "parameters"]
    cli.run()
    stdout, stderr = capsys.readouterr()

    response = stdout
    assert "precipitation" in response
    assert "air_temperature" in response
    assert "weather_phenomena" in response
    assert "radolan" in response
    assert "wx" in response
    assert "rx" in response
    assert "sweep_vol_z" in response


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
    assert "TimeResolution.ANNUAL" in response
    assert "Parameter.CLIMATE_SUMMARY" in response
    assert "PeriodType.HISTORICAL" in response


def invoke_wetterdienst_stations_empty(format="json"):
    argv = shlex.split(
        f"wetterdienst dwd stations --resolution=daily --parameter=kl --period=recent --station=123456 --format={format}"  # noqa:E501,B950
    )
    sys.argv = argv
    cli.run()


def invoke_wetterdienst_stations_static(format="json"):
    argv = shlex.split(
        f"wetterdienst dwd stations --resolution=daily --parameter=kl --period=recent --station=4411,7341 --format={format}"  # noqa:E501,B950
    )
    sys.argv = argv
    cli.run()


def invoke_wetterdienst_stations_geo(format="json"):
    argv = shlex.split(
        f"wetterdienst dwd stations --resolution=daily --parameter=kl --period=recent --lat=49.9195 --lon=8.9671 --num=5 --format={format}"  # noqa:E501,B950
    )
    sys.argv = argv
    cli.run()


def invoke_wetterdienst_readings_static(format="json"):
    argv = shlex.split(
        f"wetterdienst dwd readings --resolution=daily --parameter=kl --period=recent --station=4411,7341 --date=2020-06-30 --format={format}"  # noqa:E501,B950
    )
    sys.argv = argv
    cli.run()


def invoke_wetterdienst_readings_geo(format="json"):
    argv = shlex.split(
        f"wetterdienst dwd readings --resolution=daily --parameter=kl --period=recent --lat=49.9195 --lon=8.9671 --num=5 --date=2020-06-30 --format={format}"  # noqa:E501,B950
    )
    sys.argv = argv
    cli.run()


def test_cli_stations_json(capsys):

    invoke_wetterdienst_stations_static(format="json")

    stdout, stderr = capsys.readouterr()
    response = json.loads(stdout)

    station_names = [station["station_name"] for station in response]

    assert "Schaafheim-Schlierbach" in station_names
    assert "Offenbach-Wetterpark" in station_names


def test_cli_stations_empty(caplog):

    with pytest.raises(SystemExit):
        invoke_wetterdienst_stations_empty(format="json")

    assert "ERROR" in caplog.text
    assert "No data available for given constraints" in caplog.text


def test_cli_stations_geojson(capsys):

    invoke_wetterdienst_stations_static(format="geojson")

    stdout, stderr = capsys.readouterr()
    response = json.loads(stdout)

    assert len(response["features"]) == 2

    station_names = [station["properties"]["name"] for station in response["features"]]

    assert "Schaafheim-Schlierbach" in station_names
    assert "Offenbach-Wetterpark" in station_names


def test_cli_stations_csv(capsys):

    invoke_wetterdienst_stations_static(format="csv")

    stdout, stderr = capsys.readouterr()

    assert "Schaafheim-Schlierbach" in stdout
    assert "Offenbach-Wetterpark" in stdout


def test_cli_stations_excel(capsys):

    invoke_wetterdienst_stations_static(format="excel")

    # FIXME: Make --format=excel write to a designated file.
    filename = "output.xlsx"
    with zipfile.ZipFile(filename, "r") as zip:
        payload = zip.read("xl/worksheets/sheet1.xml")

        assert b"Schaafheim-Schlierbach" in payload
        assert b"Offenbach-Wetterpark" in payload


def test_cli_readings_json(capsys):

    invoke_wetterdienst_readings_static(format="json")

    stdout, stderr = capsys.readouterr()
    response = json.loads(stdout)

    station_ids = list(set([reading["station_id"] for reading in response]))

    assert 4411 in station_ids
    assert 7341 in station_ids


def test_cli_readings_geojson(capsys):

    with pytest.raises(KeyError) as excinfo:
        invoke_wetterdienst_readings_static(format="geojson")

    assert excinfo.typename == "KeyError"
    assert str(excinfo.value) == "'GeoJSON format only available for stations output'"


def test_cli_readings_csv(capsys):

    invoke_wetterdienst_readings_static(format="csv")

    stdout, stderr = capsys.readouterr()

    assert str(4411) in stdout
    assert str(7341) in stdout


def test_cli_readings_excel(capsys):

    invoke_wetterdienst_readings_static(format="excel")

    # FIXME: Make --format=excel write to a designated file.
    filename = "output.xlsx"
    with zipfile.ZipFile(filename, "r") as zip:
        payload = zip.read("xl/worksheets/sheet1.xml")

        assert b"4411" in payload
        assert b"7341" in payload


def test_cli_readings_format_unknown(caplog):

    with pytest.raises(SystemExit):
        invoke_wetterdienst_readings_static(format="foobar")

    assert "ERROR" in caplog.text
    assert "Unknown output format" in caplog.text


def test_cli_stations_geospatial(capsys):

    invoke_wetterdienst_stations_geo(format="json")

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


def test_cli_readings_geospatial(capsys):

    invoke_wetterdienst_readings_geo(format="json")

    stdout, stderr = capsys.readouterr()
    response = json.loads(stdout)

    station_ids = list(set([reading["station_id"] for reading in response]))

    assert 4411 in station_ids
    assert 7341 in station_ids
