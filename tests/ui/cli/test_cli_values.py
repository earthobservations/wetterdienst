import json
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

import polars as pl
import pytest
from click.testing import CliRunner
from dirty_equals import IsInstance, IsStr

from tests.conftest import IS_WINDOWS
from wetterdienst.ui.cli import cli

SETTINGS_VALUES = (
    (
        "dwd",
        "observation",
        ["--parameters=daily/kl", "--date=2020-06-30"],
        "01048",
        "Dresden-Klotzsche",
    ),
    (
        "dwd",
        "mosmix",
        ["--parameters=hourly/large", f"--date={datetime.strftime(datetime.today() + timedelta(days=2), '%Y-%m-%d')}"],
        "10488",
        "DRESDEN",
    ),
    (
        "dwd",
        "dmo",
        ["--parameters=hourly/icon", f"--date={datetime.strftime(datetime.today() + timedelta(days=2), '%Y-%m-%d')}"],
        "10488",
        "DRESDEN",
    ),
    (
        "dwd",
        "dmo",
        [
            "--parameters=hourly/icon",
            "--lead_time=long",
            f"--date={datetime.strftime(datetime.today() + timedelta(days=3), '%Y-%m-%d')}",
        ],
        "10488",
        "DRESDEN",
    ),
)


def invoke_wetterdienst_values_static(provider, network, setting: list, station, fmt="json", additional: list = None):
    runner = CliRunner()
    return runner.invoke(
        cli,
        [
            "values",
            f"--provider={provider}",
            f"--network={network}",
            f"--station={station}",
            f"--format={fmt}",
            "--shape=long",
        ]
        + setting
        + (additional or []),
    )


def invoke_wetterdienst_values_static_wide(
    provider, network, setting: list, station, fmt="json", additional: list = None
):
    runner = CliRunner()
    return runner.invoke(
        cli,
        [
            "values",
            f"--provider={provider}",
            f"--network={network}",
            f"--station={station}",
            "--shape=wide",
            f"--format={fmt}",
        ]
        + setting
        + (additional or []),
    )


def invoke_wetterdienst_values_export_wide(provider, network, setting: list, station, target):
    runner = CliRunner()
    return runner.invoke(
        cli,
        [
            "values",
            f"--provider={provider}",
            f"--network={network}",
            f"--station={station}",
            "--shape=wide",
            f"--target={target}",
        ]
        + setting,
    )


def invoke_wetterdienst_values_filter_by_rank(provider, network, setting: list, fmt="json", additional: list = None):
    runner = CliRunner()
    return runner.invoke(
        cli,
        [
            "values",
            f"--provider={provider}",
            f"--network={network}",
            "--coordinates=51.1280,13.7543",
            "--rank=10",
            "--shape=wide",
            f"--format={fmt}",
        ]
        + setting
        + (additional or []),
    )


@pytest.mark.remote
@pytest.mark.parametrize(
    "setting",
    SETTINGS_VALUES,
)
def test_cli_values_json_wide(setting):
    provider, network, setting, station_id, station_name = setting
    result = invoke_wetterdienst_values_static_wide(
        provider=provider,
        network=network,
        setting=setting,
        station=station_id,
        fmt="json",
    )
    response = json.loads(result.stdout)
    station_ids = {reading["station_id"] for reading in response["values"]}
    assert station_id in station_ids
    default_columns = {"station_id", "dataset", "date"}
    first = response["values"][0]
    assert default_columns.issubset(first.keys())
    assert set(first.keys()) - default_columns


def test_cli_values_json_multiple_stations():
    result = invoke_wetterdienst_values_static_wide(
        provider="dwd",
        network="observation",
        setting=[
            "--parameters=daily/kl",
            "--periods=historical",
        ],
        station="01047,01048",
        fmt="json",
    )
    response = json.loads(result.stdout)
    station_ids = {reading["station_id"] for reading in response["values"]}
    assert {"01047", "01048"}.issubset(station_ids)


@pytest.mark.remote
def test_cli_values_json_multiple_datasets():
    result = invoke_wetterdienst_values_static(
        provider="dwd",
        network="observation",
        setting=[
            "--parameters=daily/kl,daily/more_precip",
            "--date=2020-06-30",
        ],
        station="01048",
        fmt="json",
    )
    response = json.loads(result.stdout)
    item = response["values"][12]
    assert item == {
        "station_id": "01048",
        "dataset": "climate_summary",
        "parameter": "wind_gust_max",
        "date": "2020-06-30T00:00:00+00:00",
        "value": 15.3,
        "quality": 10.0,
    }


@pytest.mark.remote
@pytest.mark.parametrize("provider,network,setting,station_id,station_name", SETTINGS_VALUES)
def test_cli_values_json(
    provider,
    network,
    setting,
    station_id,
    station_name,  # noqa: ARG001
):
    result = invoke_wetterdienst_values_static(
        provider=provider,
        network=network,
        setting=setting,
        station=station_id,
        fmt="json",
    )
    response = json.loads(result.output)
    first = response["values"][0]
    assert station_id in first.values()
    assert set(first.keys()).issuperset(
        {
            "station_id",
            "date",
            "parameter",
            "value",
            "quality",
        },
    )


@pytest.mark.remote
def test_cli_values_json_with_metadata_with_stations(metadata):
    result = invoke_wetterdienst_values_static(
        provider="dwd",
        network="observation",
        setting=[
            "--parameters=daily/kl",
            "--periods=historical",
        ],
        station="01047,01048",
        fmt="json",
        additional=[
            "--with_metadata=true",
            "--with_stations=true",
        ],
    )
    response = json.loads(result.output)
    assert response.keys() == {"values", "metadata", "stations"}
    assert response["metadata"] == metadata
    assert response["stations"] == [
        {
            "station_id": "01047",
            "start_date": "1828-01-01T00:00:00+00:00",
            "end_date": "1915-12-31T00:00:00+00:00",
            "latitude": 51.0557,
            "longitude": 13.7274,
            "height": 112.0,
            "name": "Dresden (Mitte)",
            "state": "Sachsen",
        },
        {
            "station_id": "01048",
            "start_date": "1934-01-01T00:00:00+00:00",
            "end_date": IsStr,
            "latitude": 51.1278,
            "longitude": 13.7543,
            "height": 228.0,
            "name": "Dresden-Klotzsche",
            "state": "Sachsen",
        },
    ]


@pytest.mark.remote
@mock.patch("json.dumps", create=True)
def test_cli_values_json_indent_false(json_dumps_mock):
    invoke_wetterdienst_values_static(
        provider="dwd",
        network="observation",
        setting=[
            "--parameters=daily/kl",
            "--periods=recent",
        ],
        station="01048",
        fmt="json",
        additional=[
            "--pretty=false",
        ],
    )
    assert json_dumps_mock.call_args.kwargs["indent"] is None


@pytest.mark.remote
@mock.patch("json.dumps", create=True)
def test_cli_values_json_indent_true(json_dumps_mock):
    invoke_wetterdienst_values_static(
        provider="dwd",
        network="observation",
        setting=[
            "--parameters=daily/kl",
            "--periods=recent",
        ],
        station="01048",
        fmt="json",
        additional=[
            "--pretty=true",
        ],
    )
    assert json_dumps_mock.call_args.kwargs["indent"] == 4


@pytest.mark.remote
def test_cli_values_geojson():
    result = invoke_wetterdienst_values_static(
        provider="dwd",
        network="observation",
        setting=[
            "--parameters=daily/kl",
            "--periods=recent",
        ],
        station="01048",
        fmt="geojson",
    )
    response = json.loads(result.output)
    assert response.keys() == {"data"}
    data = response["data"]
    assert data == {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "id": "01048",
                    "name": "Dresden-Klotzsche",
                    "state": "Sachsen",
                    "start_date": "1934-01-01T00:00:00+00:00",
                    "end_date": IsStr,
                },
                "geometry": {"type": "Point", "coordinates": [13.7543, 51.1278, 228.0]},
                "values": IsInstance(list),
            },
        ],
    }


@pytest.mark.remote
def test_cli_values_geojson_with_metadata(metadata):
    result = invoke_wetterdienst_values_static(
        provider="dwd",
        network="observation",
        setting=[
            "--parameters=daily/kl",
            "--periods=recent",
        ],
        station="01048",
        fmt="geojson",
        additional=[
            "--with_metadata=true",
        ],
    )
    response = json.loads(result.output)
    assert response.keys() == {"data", "metadata"}
    assert response["metadata"] == metadata


@pytest.mark.remote
@mock.patch("json.dumps", create=True)
def test_cli_values_geojson_pretty_false(json_dumps_mock):
    invoke_wetterdienst_values_static(
        provider="dwd",
        network="observation",
        setting=[
            "--parameters=daily/kl",
            "--periods=recent",
        ],
        station="01048",
        fmt="geojson",
        additional=[
            "--pretty=false",
        ],
    )
    assert json_dumps_mock.call_args.kwargs["indent"] is None


@pytest.mark.remote
@mock.patch("json.dumps", create=True)
def test_cli_values_geojson_pretty_true(json_dumps_mock):
    invoke_wetterdienst_values_static(
        provider="dwd",
        network="observation",
        setting=[
            "--parameters=daily/kl",
            "--periods=recent",
        ],
        station="01048",
        fmt="geojson",
        additional=[
            "--pretty=true",
        ],
    )
    assert json_dumps_mock.call_args.kwargs["indent"] == 4


@pytest.mark.remote
@pytest.mark.parametrize(
    "provider,network,setting,station_id,station_name",
    SETTINGS_VALUES,
)
def test_cli_values_csv(
    provider,
    network,
    setting,
    station_id,
    station_name,  # noqa: ARG001
):
    result = invoke_wetterdienst_values_static_wide(
        provider=provider,
        network=network,
        setting=setting,
        station=station_id,
        fmt="csv",
    )
    assert station_id in result.output


@pytest.mark.remote
@pytest.mark.parametrize(
    "provider,network,setting,station_id,station_name",
    SETTINGS_VALUES,
)
def test_cli_values_excel(
    provider,
    network,
    setting,
    station_id,
    station_name,  # noqa: ARG001
    tmp_path,
):
    filename = Path("values.xlsx")
    if not IS_WINDOWS:
        filename = tmp_path.joinpath(filename)
    _ = invoke_wetterdienst_values_export_wide(
        provider=provider,
        network=network,
        setting=setting,
        station=station_id,
        target=f"file://{filename}",
    )
    df = pl.read_excel(filename, sheet_name="Sheet1", infer_schema_length=0)
    if IS_WINDOWS:
        filename.unlink(missing_ok=True)
    assert "station_id" in df.columns
    assert df.get_column("station_id").item() == station_id


@pytest.mark.parametrize(
    "provider,network,setting,station_id,station_name",
    SETTINGS_VALUES,
)
def test_cli_values_format_unknown(
    provider,
    network,
    setting,
    station_id,
    station_name,  # noqa: ARG001
):
    result = invoke_wetterdienst_values_static_wide(
        provider=provider,
        network=network,
        setting=setting,
        station=station_id,
        fmt="foobar",
    )
    assert "Error: Invalid value for '--format': 'foobar' is not one of 'json', 'geojson', 'csv'" in result.output


@pytest.mark.remote
@pytest.mark.parametrize(
    "provider,network,setting,station_id,station_name",
    SETTINGS_VALUES,
)
def test_cli_values_filter_by_rank(
    provider,
    network,
    setting,
    station_id,
    station_name,  # noqa: ARG001
):
    result = invoke_wetterdienst_values_filter_by_rank(provider=provider, network=network, setting=setting, fmt="json")
    response = json.loads(result.output)
    station_ids = {reading["station_id"] for reading in response["values"]}
    assert station_id in station_ids


@pytest.mark.remote
def test_cli_values_custom_units():
    result = invoke_wetterdienst_values_static(
        provider="dwd",
        network="observation",
        setting=[
            "--parameters=daily/kl/temperature_air_mean_2m",
            "--date=2022-01-01",
        ],
        station="01048",
        fmt="json",
        additional=['--unit_targets={"temperature":"degree_fahrenheit"}'],
    )
    data = json.loads(result.output)
    first = data["values"][0]
    assert first == {
        "station_id": "01048",
        "dataset": "climate_summary",
        "parameter": "temperature_air_mean_2m",
        "date": "2022-01-01T00:00:00+00:00",
        "value": 52.52,
        "quality": 10.0,
    }
