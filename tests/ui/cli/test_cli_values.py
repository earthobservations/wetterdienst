# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for CLI values command."""

import datetime as dt
import json
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from click.testing import CliRunner, Result
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
        [
            "--parameters=hourly/large",
            f'--date={dt.datetime.strftime(dt.datetime.now(ZoneInfo("UTC")) + dt.timedelta(days=2), "%Y-%m-%d")}',
        ],
        "10488",
        "DRESDEN",
    ),
    (
        "dwd",
        "dmo",
        [
            "--parameters=hourly/icon",
            f'--date={dt.datetime.strftime(dt.datetime.now(ZoneInfo("UTC")) + dt.timedelta(days=2), "%Y-%m-%d")}',
        ],
        "10488",
        "DRESDEN",
    ),
    (
        "dwd",
        "dmo",
        [
            "--parameters=hourly/icon",
            "--lead_time=long",
            f'--date={dt.datetime.strftime(dt.datetime.now(ZoneInfo("UTC")) + dt.timedelta(days=3), "%Y-%m-%d")}',
        ],
        "10488",
        "DRESDEN",
    ),
)


def invoke_wetterdienst_values_static(
    provider: str,
    network: str,
    setting: list,
    station: str,
    fmt: str = "json",
    additional: list | None = None,
) -> Result:
    """Invoke CLI."""
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
    provider: str,
    network: str,
    setting: list,
    station: str,
    fmt: str = "json",
    additional: list | None = None,
) -> Result:
    """Invoke CLI with wide format."""
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


def invoke_wetterdienst_values_export_wide(
    provider: str,
    network: str,
    setting: list,
    station: str,
    target: str,
) -> Result:
    """Invoke CLI with wide format."""
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
            *setting,
        ],
    )


def invoke_wetterdienst_values_filter_by_rank(
    provider: str,
    network: str,
    setting: list,
    fmt: str = "json",
    additional: list | None = None,
) -> Result:
    """Invoke CLI with rank filter."""
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
def test_cli_values_json_wide(setting: list) -> None:
    """Test JSON export in wide format."""
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


def test_cli_values_json_multiple_stations() -> None:
    """Test multiple stations."""
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
def test_cli_values_json_multiple_datasets() -> None:
    """Test multiple datasets."""
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
        "resolution": "daily",
        "dataset": "climate_summary",
        "parameter": "wind_gust_max",
        "date": "2020-06-30T00:00:00+00:00",
        "value": 15.3,
        "quality": 10.0,
    }


@pytest.mark.remote
@pytest.mark.parametrize(("provider", "network", "setting", "station_id", "station_name"), SETTINGS_VALUES)
def test_cli_values_json(
    provider: str,
    network: str,
    setting: list,
    station_id: str,
    station_name: str,  # noqa: ARG001
) -> None:
    """Test JSON export."""
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
def test_cli_values_json_with_metadata_with_stations(metadata: dict) -> None:
    """Test JSON export with metadata and stations."""
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
            "resolution": "daily",
            "dataset": "climate_summary",
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
            "resolution": "daily",
            "dataset": "climate_summary",
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
def test_cli_values_json_indent_false(json_dumps_mock: MagicMock) -> None:
    """Test pretty print."""
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
def test_cli_values_json_indent_true(json_dumps_mock: MagicMock) -> None:
    """Test pretty print."""
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
def test_cli_values_geojson(metadata: dict) -> None:
    """Test GeoJSON export."""
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
    assert response.keys() == {"metadata", "data"}
    assert response["metadata"] == metadata
    assert response["data"] == {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {
                    "resolution": "daily",
                    "dataset": "climate_summary",
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
def test_cli_values_geojson_no_metadata() -> None:
    """Test GeoJSON export without metadata."""
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
            "--with_metadata=false",
        ],
    )
    response = json.loads(result.output)
    assert response.keys() == {"data"}


@pytest.mark.remote
@mock.patch("json.dumps", create=True)
def test_cli_values_geojson_pretty_false(json_dumps_mock: MagicMock) -> None:
    """Test pretty print."""
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
def test_cli_values_geojson_pretty_true(json_dumps_mock: MagicMock) -> None:
    """Test pretty print."""
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
    ("provider", "network", "setting", "station_id", "station_name"),
    SETTINGS_VALUES,
)
def test_cli_values_csv(
    provider: str,
    network: str,
    setting: list,
    station_id: str,
    station_name: str,  # noqa: ARG001
) -> None:
    """Test CSV export."""
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
    ("provider", "network", "setting", "station_id", "station_name"),
    SETTINGS_VALUES,
)
def test_cli_values_excel(
    provider: str,
    network: str,
    setting: list,
    station_id: str,
    station_name: str,  # noqa: ARG001
    tmp_path: Path,
) -> None:
    """Test Excel export."""
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
    ("provider", "network", "setting", "station_id", "station_name"),
    SETTINGS_VALUES,
)
def test_cli_values_format_unknown(
    provider: str,
    network: str,
    setting: list,
    station_id: str,
    station_name: str,  # noqa: ARG001
) -> None:
    """Test unknown format."""
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
    ("provider", "network", "setting", "station_id", "station_name"),
    SETTINGS_VALUES,
)
def test_cli_values_filter_by_rank(
    provider: str,
    network: str,
    setting: list,
    station_id: str,
    station_name: str,  # noqa: ARG001
) -> None:
    """Test filtering by rank."""
    result = invoke_wetterdienst_values_filter_by_rank(provider=provider, network=network, setting=setting, fmt="json")
    response = json.loads(result.output)
    station_ids = {reading["station_id"] for reading in response["values"]}
    assert station_id in station_ids


@pytest.mark.remote
def test_cli_values_custom_units() -> None:
    """Test custom units."""
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
        "resolution": "daily",
        "dataset": "climate_summary",
        "parameter": "temperature_air_mean_2m",
        "date": "2022-01-01T00:00:00+00:00",
        "value": 52.52,
        "quality": 10.0,
    }


@pytest.mark.remote
@pytest.mark.parametrize(
    "fmt",
    [
        "png",
        "jpg",
        "webp",
        "svg",
    ],
)
def test_cli_values_image(fmt: str) -> None:
    """Test image formats."""
    result = invoke_wetterdienst_values_static(
        provider="dwd",
        network="observation",
        setting=[
            "--parameters=daily/kl",
            "--date=2020-06-30",
        ],
        station="01048",
        fmt=fmt,
    )
    assert result.exit_code == 0


@pytest.mark.remote
def test_cli_values_image_html() -> None:
    """Test image output in HTML format."""
    result = invoke_wetterdienst_values_static(
        provider="dwd",
        network="observation",
        setting=[
            "--parameters=daily/kl",
            "--date=2020-06-30",
        ],
        station="01048",
        fmt="html",
    )
    assert result.exit_code == 0
    assert result.output.startswith("<html>")


@pytest.mark.remote
def test_cli_values_image_pdf() -> None:
    """Test PDF export."""
    result = invoke_wetterdienst_values_static(
        provider="dwd",
        network="observation",
        setting=[
            "--parameters=daily/kl",
            "--date=2020-06-30",
        ],
        station="01048",
        fmt="pdf",
    )
    assert result.exit_code == 0
