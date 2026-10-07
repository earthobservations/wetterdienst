# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the CLI command `stations`."""

import json
import logging
from pathlib import Path
from unittest import mock
from unittest.mock import MagicMock

import polars as pl
import pytest
from click.testing import CliRunner, Result
from dirty_equals import IsFloat, IsStr

from tests.conftest import IS_WINDOWS, is_html_document
from wetterdienst.ui.cli import cli

SETTINGS_STATIONS = (
    (
        "dwd",
        "observation",
        ["--parameters=daily/kl", "--periods=recent"],
        "01048",
        # expected dict
        {
            "resolution": "daily",
            "dataset": "climate_summary",
            "station_id": "01048",
            "start_timestamp": "1934-01-01T00:00:00.000000+00:00",
            "end_timestamp": IsStr,
            "latitude": 51.1278,
            "longitude": 13.7543,
            "elevation": 228.0,
            "name": "Dresden-Klotzsche",
            "region": "Sachsen",
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
            "resolution": "hourly",
            "dataset": "large",
            "station_id": "10488",
            "icao_id": "EDDC",
            "start_timestamp": None,
            "end_timestamp": None,
            "latitude": 51.13,
            "longitude": 13.75,
            "elevation": 230.0,
            "name": "DRESDEN/FLUGHAFEN",
            "region": None,
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
            "resolution": "hourly",
            "dataset": "icon",
            "station_id": "10488",
            "icao_id": "EDDC",
            "start_timestamp": None,
            "end_timestamp": None,
            "latitude": 51.13,
            "longitude": 13.75,
            "elevation": 230.0,
            "name": "DRESDEN/FLUGHAFEN",
            "region": None,
            "distance": IsFloat(ge=0.0),
        },
        [13.75, 51.13, 230.0],
    ),
)


def invoke_wetterdienst_stations_empty(provider: str, network: str, setting: list[str], fmt: str = "json") -> Result:
    """Invoke the CLI command `stations` with empty station."""
    runner = CliRunner()
    return runner.invoke(
        cli,
        ["stations", f"--provider={provider}", f"--network={network}", "--station=123456", f"--format={fmt}", *setting],
    )


def invoke_wetterdienst_stations_static(
    provider: str,
    network: str,
    setting: list[str],
    station: str,
    fmt: str = "json",
    additional: list | None = None,
) -> Result:
    """Invoke the CLI command `stations` with static station."""
    runner = CliRunner()
    return runner.invoke(
        cli,
        [
            "stations",
            f"--provider={provider}",
            f"--network={network}",
            f"--station={station}",
            f"--format={fmt}",
            "--with_metadata=false",
        ]
        + setting
        + (additional or []),
    )


def invoke_wetterdienst_stations_export(
    provider: str,
    network: str,
    setting: list[str],
    station: str,
    target: str,
) -> Result:
    """Invoke the CLI command `stations` with export."""
    runner = CliRunner()
    return runner.invoke(
        cli,
        [
            "stations",
            f"--provider={provider}",
            f"--network={network}",
            f"--station={station}",
            f"--target={target}",
            *setting,
        ],
    )


def invoke_wetterdienst_stations_filter_by_rank(
    provider: str,
    network: str,
    setting: list[str],
    fmt: str = "json",
    additional: list | None = None,
) -> Result:
    """Invoke the CLI command `stations` with filter by rank."""
    runner = CliRunner()
    return runner.invoke(
        cli,
        [
            "stations",
            f"--provider={provider}",
            f"--network={network}",
            "--latitude=51.1278",
            "--longitude=13.7543",
            "--rank=5",
            f"--format={fmt}",
        ]
        + setting
        + (additional or []),
    )


@pytest.mark.remote
@pytest.mark.parametrize(
    ("provider", "network", "setting", "station_id", "expected_dict", "coordinates"),
    SETTINGS_STATIONS,
)
def test_cli_stations_json(
    provider: str,
    network: str,
    setting: list[str],
    station_id: str,
    expected_dict: dict,
    coordinates: tuple[float, float, float],  # noqa: ARG001
) -> None:
    """Test the CLI command `stations` with JSON format."""
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
def test_cli_stations_json_with_metadata(metadata: dict) -> None:
    """Test the CLI command `stations` with JSON format and metadata."""
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
@pytest.mark.parametrize(
    ("provider", "network", "setting", "station_id", "expected_dict", "coordinates"),
    SETTINGS_STATIONS,
)
def test_cli_stations_empty(
    provider: str,
    network: str,
    setting: list[str],
    station_id: str,  # noqa: ARG001
    expected_dict: dict,  # noqa: ARG001
    coordinates: tuple[float, float, float],  # noqa: ARG001
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the CLI command `stations` with empty station."""
    result = invoke_wetterdienst_stations_empty(provider=provider, network=network, setting=setting, fmt="json")
    assert isinstance(result.exception, SystemExit)
    assert "ERROR" in caplog.text
    assert "No stations available for given constraints" in caplog.text


@pytest.mark.remote
@pytest.mark.parametrize(
    ("provider", "network", "setting", "station_id", "expected_dict", "coordinates"),
    SETTINGS_STATIONS,
)
def test_cli_stations_geojson(
    provider: str,
    network: str,
    setting: list[str],
    station_id: str,
    expected_dict: dict,
    coordinates: tuple[float, float, float],
) -> None:
    """Test the CLI command `stations` with GeoJSON format."""
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
    first_prop.pop("end_timestamp")
    expected_dict_geo = expected_dict.copy()
    expected_dict_geo["id"] = expected_dict_geo.pop("station_id")
    assert first_prop.items() <= expected_dict_geo.items()
    assert first["geometry"]["coordinates"] == coordinates


@pytest.mark.remote
def test_cli_stations_geojson_with_metadata(metadata: dict) -> None:
    """Test the CLI command `stations` with GeoJSON format and metadata."""
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
    ("provider", "network", "setting", "station_id", "expected_dict", "coordinates"),
    SETTINGS_STATIONS,
)
def test_cli_stations_csv(
    provider: str,
    network: str,
    setting: list[str],
    station_id: str,
    expected_dict: dict,
    coordinates: tuple[float, float],  # noqa: ARG001
) -> None:
    """Test the CLI command `stations` with CSV format."""
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
    ("provider", "network", "setting", "station_id", "expected_dict", "coordinates"),
    SETTINGS_STATIONS,
)
def test_cli_stations_excel(
    provider: str,
    network: str,
    setting: list[str],
    station_id: str,
    expected_dict: dict,
    coordinates: tuple[float, float],  # noqa: ARG001
    tmp_path: Path,
) -> None:
    """Test the CLI command `stations` with Excel format."""
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
    ("provider", "network", "setting", "station_id", "expected_dict", "coordinates"),
    SETTINGS_STATIONS,
)
def test_cli_stations_geospatial(
    provider: str,
    network: str,
    setting: list[str],
    station_id: str,
    expected_dict: dict,
    coordinates: tuple[float, float],  # noqa: ARG001
) -> None:
    """Test the CLI command `stations` with geospatial format."""
    result = invoke_wetterdienst_stations_filter_by_rank(
        provider=provider,
        network=network,
        setting=setting,
        fmt="json",
    )
    response = json.loads(result.output)
    station = next(item for item in response["stations"] if item["station_id"] == station_id)
    assert station == expected_dict


@pytest.mark.remote
@mock.patch("json.dumps", create=True)
def test_cli_stations_json_pretty_false(json_dumps_mock: MagicMock) -> None:
    """Test the CLI command `stations` with JSON format and pretty false."""
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
def test_cli_stations_json_pretty_true(json_dumps_mock: MagicMock) -> None:
    """Test the CLI command `stations` with JSON format and pretty true."""
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
def test_cli_stations_geojson_pretty_false(json_dumps_mock: MagicMock) -> None:
    """Test the CLI command `stations` with GeoJSON format and pretty false."""
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
def test_cli_stations_geojson_pretty_true(json_dumps_mock: MagicMock) -> None:
    """Test the CLI command `stations` with GeoJSON format and pretty true."""
    invoke_wetterdienst_stations_static(
        provider="dwd",
        network="observation",
        setting=["--parameters=daily/kl", "--periods=recent"],
        station="01048",
        fmt="geojson",
        additional=["--pretty=true"],
    )
    assert json_dumps_mock.call_args.kwargs["indent"] == 4


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
def test_cli_stations_image(fmt: str) -> None:
    """Test the summarize command with image formats."""
    result = invoke_wetterdienst_stations_static(
        provider="dwd",
        network="observation",
        setting=["--parameters=daily/kl", "--periods=recent"],
        station="01048",
        fmt=fmt,
    )
    assert result.exit_code == 0


@pytest.mark.remote
def test_cli_stations_image_html() -> None:
    """Test the summarize command with HTML format."""
    result = invoke_wetterdienst_stations_static(
        provider="dwd",
        network="observation",
        setting=["--parameters=daily/kl", "--periods=recent"],
        station="01048",
        fmt="html",
    )
    assert result.exit_code == 0
    assert is_html_document(result.output)


@pytest.mark.remote
def test_cli_stations_image_pdf() -> None:
    """Test the summarize command with PDF format."""
    result = invoke_wetterdienst_stations_static(
        provider="dwd",
        network="observation",
        setting=["--parameters=daily/kl", "--periods=recent"],
        station="01048",
        fmt="pdf",
    )
    assert "ERROR" not in result.output
    assert result.exit_code == 0


@pytest.mark.parametrize(
    ("arguments", "message"),
    [
        pytest.param(
            ["--parameters=daily/nonexistent", "--all"],
            "No valid parameters could be parsed from ['daily/nonexistent'] for DwdObservationRequest",
            id="parameter",
        ),
        pytest.param(
            ["--parameters=daily/kl", "--left=10", "--bottom=50", "--right=5", "--top=52"],
            "bbox left border should be smaller then right",
            id="bbox",
        ),
    ],
)
def test_cli_stations_refusal_is_a_usage_error(
    arguments: list[str], message: str, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a request the caller can rephrase is a one-line usage error, not a traceback (GH-2465)."""
    with caplog.at_level(logging.ERROR):
        result = CliRunner().invoke(cli, ["stations", "--provider=dwd", "--network=observation", *arguments])

    assert result.exit_code == 2, result.output
    assert result.stderr.endswith(f"\n\nError: {message}\n")
    assert not caplog.records


def test_cli_stations_keeps_the_traceback_for_an_upstream_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a station lookup failing upstream is logged with its traceback and exits 1, unlike a refusal (GH-2465)."""

    def get_stations(**_kwargs: object) -> None:
        msg = "upstream station list unreachable"
        raise FileNotFoundError(msg)

    monkeypatch.setattr("wetterdienst.ui.cli.get_stations", get_stations)
    with caplog.at_level(logging.ERROR):
        result = CliRunner().invoke(
            cli, ["stations", "--provider=dwd", "--network=observation", "--parameters=daily/kl", "--all"]
        )

    assert result.exit_code == 1, result.output
    assert "Usage:" not in result.output
    assert "Failed to get stations." in caplog.text
    assert "FileNotFoundError: upstream station list unreachable" in caplog.text


def test_cli_stations_sql_refused_by_duckdb_is_a_usage_error(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Test a --sql DuckDB refuses as a statement is a one-line usage error, not a traceback (GH-2465)."""
    duckdb = pytest.importorskip("duckdb")
    refusal = duckdb.BinderException('Binder Error: Referenced column "nope" not found in FROM clause!')

    def get_stations(**_kwargs: object) -> None:
        raise refusal

    monkeypatch.setattr("wetterdienst.ui.cli.get_stations", get_stations)
    with caplog.at_level(logging.ERROR):
        result = CliRunner().invoke(
            cli,
            ["stations", "--provider=dwd", "--network=observation", "--parameters=daily/kl", "--sql=nope = 1"],
        )

    assert result.exit_code == 2, result.output
    assert result.stderr.endswith(f"\n\nError: {refusal}\n")
    assert not caplog.records
