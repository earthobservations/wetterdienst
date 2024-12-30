import json
from pathlib import Path
from unittest import mock

import polars as pl
import pytest
from click.testing import CliRunner
from dirty_equals import IsFloat, IsStr

from tests.conftest import IS_WINDOWS
from wetterdienst.ui.cli import cli

SETTINGS_STATIONS = (
    (
        "dwd",
        "observation",
        ["--parameters=daily/kl", "--periods=recent"],
        "01048",
        # expected dict
        {
            "station_id": "01048",
            "start_date": "1934-01-01T00:00:00+00:00",
            "end_date": IsStr,
            "latitude": 51.1278,
            "longitude": 13.7543,
            "height": 228.0,
            "name": "Dresden-Klotzsche",
            "state": "Sachsen",
            "distance": IsFloat(ge=0.0),
        },
        # coordinates
        [13.7543, 51.1278, 228.0],
    ),
    (
        "dwd",
        "mosmix",
        [
            "--parameters=hourly/large",
        ],
        "10488",
        {
            "station_id": "10488",
            "icao_id": "EDDC",
            "start_date": None,
            "end_date": None,
            "latitude": 51.13,
            "longitude": 13.75,
            "height": 230.0,
            "name": "DRESDEN/FLUGHAFEN",
            "state": None,
            "distance": IsFloat(ge=0.0),
        },
        [13.75, 51.13, 230.0],
    ),
    (
        "dwd",
        "dmo",
        [
            "--parameters=hourly/icon",
        ],
        "10488",
        {
            "station_id": "10488",
            "icao_id": "EDDC",
            "start_date": None,
            "end_date": None,
            "latitude": 51.08,
            "longitude": 13.45,
            "height": 230.0,
            "name": "DRESDEN/FLUGHAFEN",
            "state": None,
            "distance": IsFloat(ge=0.0),
        },
        [13.45, 51.08, 230.0],
    ),
)


def invoke_wetterdienst_stations_empty(provider, network, setting, fmt="json"):
    runner = CliRunner()
    return runner.invoke(
        cli,
        ["stations", f"--provider={provider}", f"--network={network}", "--station=123456", f"--format={fmt}"] + setting,
    )


def invoke_wetterdienst_stations_static(provider, network, setting, station, fmt="json", additional: list = None):
    runner = CliRunner()
    return runner.invoke(
        cli,
        [
            "stations",
            f"--provider={provider}",
            f"--network={network}",
            f"--station={station}",
            f"--format={fmt}",
        ]
        + setting
        + (additional or []),
    )


def invoke_wetterdienst_stations_export(provider, network, setting, station, target):
    runner = CliRunner()
    return runner.invoke(
        cli,
        [
            "stations",
            f"--provider={provider}",
            f"--network={network}",
            f"--station={station}",
            f"--target={target}",
        ]
        + setting,
    )


def invoke_wetterdienst_stations_filter_by_rank(provider, network, setting, fmt="json", additional: list = None):
    runner = CliRunner()
    return runner.invoke(
        cli,
        [
            "stations",
            f"--provider={provider}",
            f"--network={network}",
            "--coordinates=51.1278,13.7543",
            "--rank=5",
            f"--format={fmt}",
        ]
        + setting
        + (additional or []),
    )


@pytest.mark.remote
@pytest.mark.parametrize(
    "provider,network,setting,station_id,expected_dict,coordinates",
    SETTINGS_STATIONS,
)
def test_cli_stations_json(
    provider,
    network,
    setting,
    station_id,
    expected_dict,  # noqa: ARG001
    coordinates,  # noqa: ARG001
):
    result = invoke_wetterdienst_stations_static(
        provider=provider,
        network=network,
        setting=setting,
        station=station_id,
        fmt="json",
    )
    response = json.loads(result.output)
    assert response.keys() == {"stations"}
    first = response["stations"][0]
    expected_dict = expected_dict.copy()
    expected_dict.pop("distance")
    assert first == expected_dict


@pytest.mark.remote
def test_cli_stations_json_with_metadata(metadata):
    result = invoke_wetterdienst_stations_static(
        provider="dwd",
        network="observation",
        setting=["--parameters=daily/kl", "--periods=recent"],
        station="01048",
        fmt="json",
        additional=["--with_metadata=true"],
    )
    response = json.loads(result.output)
    assert response.keys() == {"stations", "metadata"}
    assert response["metadata"] == metadata


@pytest.mark.remote
@pytest.mark.parametrize("provider,network,setting,station_id,expected_dict,coordinates", SETTINGS_STATIONS)
def test_cli_stations_empty(
    provider,
    network,
    setting,
    station_id,  # noqa: ARG001
    expected_dict,  # noqa: ARG001
    coordinates,  # noqa: ARG001
    caplog,
):
    result = invoke_wetterdienst_stations_empty(provider=provider, network=network, setting=setting, fmt="json")
    assert isinstance(result.exception, SystemExit)
    assert "ERROR" in caplog.text
    assert "No stations available for given constraints" in caplog.text


@pytest.mark.remote
@pytest.mark.parametrize("provider,network,setting,station_id,expected_dict,coordinates", SETTINGS_STATIONS)
def test_cli_stations_geojson(provider, network, setting, station_id, expected_dict, coordinates):
    result = invoke_wetterdienst_stations_static(
        provider=provider,
        network=network,
        setting=setting,
        station=station_id,
        fmt="geojson",
    )
    response = json.loads(result.output)
    assert response.keys() == {"data"}
    first = response["data"]["features"][0]
    first_prop = first["properties"]
    first_prop.pop("end_date")
    expected_dict_geo = expected_dict.copy()
    expected_dict_geo["id"] = expected_dict_geo.pop("station_id")
    assert first_prop.items() <= expected_dict_geo.items()
    assert first["geometry"]["coordinates"] == coordinates


@pytest.mark.remote
def test_cli_stations_geojson_with_metadata(metadata):
    result = invoke_wetterdienst_stations_static(
        provider="dwd",
        network="observation",
        setting=["--parameters=daily/kl", "--periods=recent"],
        station="01048",
        fmt="geojson",
        additional=["--with_metadata=true"],
    )
    response = json.loads(result.output)
    assert response.keys() == {"data", "metadata"}
    assert response["metadata"] == metadata


@pytest.mark.remote
@pytest.mark.parametrize(
    "provider,network,setting,station_id,expected_dict,coordinates",
    SETTINGS_STATIONS,
)
def test_cli_stations_csv(
    provider,
    network,
    setting,
    station_id,
    expected_dict,
    coordinates,  # noqa: ARG001
):
    result = invoke_wetterdienst_stations_static(
        provider=provider,
        network=network,
        setting=setting,
        station=station_id,
        fmt="csv",
    )
    assert expected_dict["name"] in result.output


@pytest.mark.remote
@pytest.mark.parametrize(
    "provider,network,setting,station_id,expected_dict,coordinates",
    SETTINGS_STATIONS,
)
def test_cli_stations_excel(
    provider,
    network,
    setting,
    station_id,
    expected_dict,
    coordinates,  # noqa: ARG001
    tmp_path,
):
    filename = Path("stations.xlsx")
    if not IS_WINDOWS:
        filename = tmp_path.joinpath(filename)
    _ = invoke_wetterdienst_stations_export(
        provider=provider,
        network=network,
        setting=setting,
        station=station_id,
        target=f"file://{filename}",
    )
    df = pl.read_excel(source=filename, sheet_name="Sheet1")
    if IS_WINDOWS:
        filename.unlink(missing_ok=True)
    assert "name" in df
    assert expected_dict["name"] in df.get_column("name")


@pytest.mark.remote
@pytest.mark.parametrize(
    "provider,network,setting,station_id,expected_dict,coordinates",
    SETTINGS_STATIONS,
)
def test_cli_stations_geospatial(
    provider,
    network,
    setting,
    station_id,
    expected_dict,
    coordinates,  # noqa: ARG001
):
    result = invoke_wetterdienst_stations_filter_by_rank(
        provider=provider,
        network=network,
        setting=setting,
        fmt="json",
    )
    response = json.loads(result.output)
    station = [item for item in response["stations"] if item["station_id"] == station_id][0]
    assert station == expected_dict


@pytest.mark.remote
@mock.patch("json.dumps", create=True)
def test_cli_stations_json_pretty_false(json_dumps_mock):
    invoke_wetterdienst_stations_static(
        provider="dwd",
        network="observation",
        setting=["--parameters=daily/kl", "--periods=recent"],
        station="01048",
        fmt="json",
        additional=["--pretty=false"],
    )
    assert json_dumps_mock.call_args.kwargs["indent"] is None


@pytest.mark.remote
@mock.patch("json.dumps", create=True)
def test_cli_stations_json_pretty_true(json_dumps_mock):
    invoke_wetterdienst_stations_static(
        provider="dwd",
        network="observation",
        setting=["--parameters=daily/kl", "--periods=recent"],
        station="01048",
        fmt="json",
        additional=["--pretty=true"],
    )
    assert json_dumps_mock.call_args.kwargs["indent"] == 4


@pytest.mark.remote
@mock.patch("json.dumps", create=True)
def test_cli_stations_geojson_pretty_false(json_dumps_mock):
    invoke_wetterdienst_stations_static(
        provider="dwd",
        network="observation",
        setting=["--parameters=daily/kl", "--periods=recent"],
        station="01048",
        fmt="geojson",
        additional=["--pretty=false"],
    )
    assert json_dumps_mock.call_args.kwargs["indent"] is None


@pytest.mark.remote
@mock.patch("json.dumps", create=True)
def test_cli_stations_geojson_pretty_true(json_dumps_mock):
    invoke_wetterdienst_stations_static(
        provider="dwd",
        network="observation",
        setting=["--parameters=daily/kl", "--periods=recent"],
        station="01048",
        fmt="geojson",
        additional=["--pretty=true"],
    )
    assert json_dumps_mock.call_args.kwargs["indent"] == 4
