# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for CLI values command."""

import datetime as dt
import json
import logging
from pathlib import Path
from types import SimpleNamespace
from unittest import mock
from unittest.mock import MagicMock
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from click.testing import CliRunner, Result
from dirty_equals import IsInstance, IsStr

from tests.conftest import IS_WINDOWS, is_html_document
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
            f"--date={dt.datetime.strftime(dt.datetime.now(ZoneInfo('UTC')) + dt.timedelta(days=2), '%Y-%m-%d')}",
        ],
        "10488",
        "DRESDEN",
    ),
    (
        "dwd",
        "dmo",
        [
            "--parameters=hourly/icon",
            f"--date={dt.datetime.strftime(dt.datetime.now(ZoneInfo('UTC')) + dt.timedelta(days=2), '%Y-%m-%d')}",
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
            f"--date={dt.datetime.strftime(dt.datetime.now(ZoneInfo('UTC')) + dt.timedelta(days=5), '%Y-%m-%d')}",
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
            "--latitude=51.1280",
            "--longitude=13.7543",
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
    provider, network, setting, station_id, _station_name = setting
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
        "date": "2020-06-30T00:00:00.000000+00:00",
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
            "start_date": "1828-01-01T00:00:00.000000+00:00",
            "end_date": "1915-12-31T00:00:00.000000+00:00",
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
            "start_date": "1934-01-01T00:00:00.000000+00:00",
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
        # with_metadata now defaults to false; request it explicitly to test the metadata block
        additional=["--with_metadata=true"],
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
                    "start_date": "1934-01-01T00:00:00.000000+00:00",
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
    # every row is this station's: MOSMIX and DMO are hourly, and `--date` names a day, so the
    # export holds that day's readings rather than the single one at midnight
    assert df.get_column("station_id").unique().to_list() == [station_id]


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
        "date": "2022-01-01T00:00:00.000000+00:00",
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
    assert is_html_document(result.output)


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


@pytest.mark.remote
def test_cli_values_start_date_end_date() -> None:
    """Test --start-date/--end-date as alternative to --date interval."""
    result = invoke_wetterdienst_values_static(
        provider="dwd",
        network="observation",
        setting=[
            "--parameters=daily/kl",
            "--start-date=2020-06-30",
            "--end-date=2020-06-30",
        ],
        station="01048",
        fmt="json",
    )
    assert result.exit_code == 0
    response = json.loads(result.output)
    first = response["values"][0]
    assert first["station_id"] == "01048"
    assert first["date"].startswith("2020-06-30")


@pytest.mark.remote
def test_cli_values_start_date_only() -> None:
    """Test --start-date without --end-date (single-point date)."""
    result = invoke_wetterdienst_values_static(
        provider="dwd",
        network="observation",
        setting=[
            "--parameters=daily/kl",
            "--start-date=2020-06-30",
        ],
        station="01048",
        fmt="json",
    )
    assert result.exit_code == 0
    response = json.loads(result.output)
    assert response["values"]


@pytest.mark.remote
def test_cli_values_end_date_only() -> None:
    """Test --end-date without --start-date (treated as single-point date)."""
    result = invoke_wetterdienst_values_static(
        provider="dwd",
        network="observation",
        setting=[
            "--parameters=daily/kl",
            "--end-date=2020-06-30",
        ],
        station="01048",
        fmt="json",
    )
    assert result.exit_code == 0
    response = json.loads(result.output)
    assert response["values"][0]["date"].startswith("2020-06-30")


@pytest.mark.remote
def test_cli_values_name_filter() -> None:
    """Test --name filtering in values without a prior stations lookup."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "values",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/kl",
            "--name=Dresden-Klotzsche",
            "--date=2020-06-30",
            "--format=json",
        ],
    )
    assert result.exit_code == 0
    response = json.loads(result.output)
    station_ids = {v["station_id"] for v in response["values"]}
    assert "01048" in station_ids


def test_cli_values_date_and_start_date_conflict() -> None:
    """Test that --date and --start-date together raise an error."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "values",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/kl",
            "--station=01048",
            "--date=2020-06-30",
            "--start-date=2020-06-30",
        ],
    )
    assert result.exit_code != 0
    assert "Use either --date or --start-date" in result.output


def test_cli_values_date_and_end_date_conflict() -> None:
    """Test that --date and --end-date together raise an error."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "values",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/kl",
            "--station=01048",
            "--date=2020-06-30",
            "--end-date=2020-06-30",
        ],
    )
    assert result.exit_code != 0
    assert "Use either --date or --start-date" in result.output


def test_cli_values_without_the_bufr_reader_says_what_to_install(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A network that needs an optional reader says so, rather than ending in a traceback.

    `require_bufr` raises `BufrReaderMissingError` at the request, and the CLI caught `ValueError`
    -- which that is not -- so the message naming the extra to install, the whole of what a caller
    can do about it, arrived as the last line of a stack trace.

    Raised from a stubbed `get_values` rather than by asking DWD for a road station: this is about
    what the CLI does with the error, and the real path downloads a station list on the way to it,
    which would make an offline run fail here for a reason that has nothing to do with the test.
    """
    from wetterdienst.exceptions import BufrReaderMissingError  # noqa: PLC0415

    msg = (
        "DWD road weather data is published as BUFR, which needs eccodes and pdbufr to read: "
        "`pip install wetterdienst[bufr]` installs both."
    )

    def refuse(**_kwargs: object) -> None:
        raise BufrReaderMissingError(msg)

    monkeypatch.setattr("wetterdienst.ui.cli.get_values", refuse)
    with caplog.at_level(logging.ERROR):
        result = CliRunner().invoke(
            cli,
            [
                "values",
                "--provider=dwd",
                "--network=road",
                "--parameters=15_minutes/data/temperature_air_mean_2m",
                "--station=A006",
                "--start-date=2024-01-01",
                "--end-date=2024-01-02",
            ],
        )
    assert result.exit_code == 1
    assert "pip install wetterdienst[bufr]" in caplog.text
    # handled rather than propagated: the command chose to exit, and the error did not escape it.
    # `CliRunner` never renders a traceback into `output`, so looking for one there proves nothing
    assert isinstance(result.exception, SystemExit)


def test_cli_values_reports_an_empty_window_once(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A window holding no readings is one sentence, not the same one twice.

    `core.get_values` logged "No data available for given constraints" and handed the empty frame
    back, and the CLI logged the identical line again on its way to exiting -- so the caller read
    it twice for a single empty result. Reporting it belongs to the caller: the CLI says it and
    exits, the REST API returns the empty result, and `.all()` already notes it at info level on
    the way out of the library.

    Stubbed at `get_stations` rather than asked of DWD: this is about how many times the CLI says
    it, and a real empty window would need the network to arrive at.
    """
    stations = SimpleNamespace(values=SimpleNamespace(all=lambda: SimpleNamespace(df=pl.DataFrame())))
    monkeypatch.setattr("wetterdienst.ui.core.get_stations", lambda **_kwargs: stations)

    with caplog.at_level(logging.ERROR):
        result = CliRunner().invoke(
            cli,
            [
                "values",
                "--provider=dwd",
                "--network=observation",
                "--parameters=daily/kl",
                "--station=01048",
                "--date=2020-06-30",
            ],
        )

    assert result.exit_code == 1
    messages = [record.message for record in caplog.records]
    assert messages.count("No data available for given constraints") == 1


@pytest.mark.remote
@pytest.mark.parametrize(
    ("given", "expected"),
    [
        pytest.param([], "replace", id="default"),
        pytest.param(["--if_exists=append"], "append", id="append"),
        pytest.param(["--if_exists=skip"], "skip", id="skip"),
    ],
)
@mock.patch("wetterdienst.io.export.ExportMixin.to_target")
def test_cli_values_target_passes_if_exists_to_the_sink(
    to_target: MagicMock,
    given: list[str],
    expected: str,
) -> None:
    """What the option says has to arrive at the sink, which is the whole of what was missing.

    `to_target` has taken `if_exists` since it was written, but the CLI called it with the target
    alone, so every scheduled export replaced what the last run wrote -- a nightly timer pointed at
    `duckdb:///obs.duckdb?table=weather` held one run's rows rather than a history.
    """
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "values",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/kl/temperature_air_mean_2m",
            "--periods=recent",
            "--station=01048",
            "--target=duckdb:///obs.duckdb?table=weather",
            *given,
        ],
    )

    assert result.exit_code == 0, result.output
    assert to_target.call_args.kwargs["if_exists"] == expected


@pytest.mark.remote
def test_cli_values_target_reports_a_pairing_the_sink_refuses(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Appending to a file is not implemented, and a schedule needs to be told so in one line.

    The option offers all four values because which ones a sink takes is the sink's business, so
    the refusal arrives as an exception from `to_target`. Unhandled it would be a traceback, which
    for an unattended run is the failure buried in the noise rather than reported.
    """
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "values",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/kl/temperature_air_mean_2m",
            "--periods=recent",
            "--station=01048",
            f"--target=file://{tmp_path / 'kl.csv'}",
            "--if_exists=append",
        ],
    )

    assert result.exit_code == 1
    assert "Append mode is not supported for file exports." in caplog.text
    assert not isinstance(result.exception, NotImplementedError)
    assert not (tmp_path / "kl.csv").exists()


@pytest.mark.remote
def test_cli_values_target_reports_a_sink_failure_that_is_not_about_if_exists(
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Appending onto a table whose columns have changed is the likeliest way this option fails.

    `--shape=wide` puts one column per parameter, so a second run asking for a different set of
    parameters names a column the table does not have, and DuckDB answers `Binder Error: Table
    "weather" does not have a column with name "precipitation_height"`. That derives from `Exception`
    alone, so it is not an `ExportRefusedError` and must not be reported as one -- an unattended run
    would otherwise end in a traceback out of click rather than a logged failure naming the target.
    """
    target = f"duckdb:///{tmp_path / 'obs.duckdb'}?table=weather"
    runner = CliRunner()
    common = [
        "values",
        "--provider=dwd",
        "--network=observation",
        "--periods=recent",
        "--station=01048",
        "--shape=wide",
        f"--target={target}",
    ]

    first = runner.invoke(cli, [*common, "--parameters=daily/kl/temperature_air_mean_2m"])
    assert first.exit_code == 0, first.output

    second = runner.invoke(
        cli,
        [*common, "--parameters=daily/kl/temperature_air_mean_2m,daily/kl/precipitation_height", "--if_exists=append"],
    )

    assert second.exit_code == 1
    assert f"Failed to export to {target}" in caplog.text


@pytest.mark.remote
@pytest.mark.parametrize("given", [[], ["--if_exists=fail"], ["--if_exists=skip"]])
def test_cli_values_target_reports_an_unwritable_format_the_same_way_in_every_mode(
    given: list[str],
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """An extension nothing writes is a refusal, and `--if_exists` has no bearing on it.

    It used to depend on the mode, because the CLI inferred a refusal from the exception class and
    `KeyError` was on the list: with `--if_exists=fail` this printed one line, and without it the
    same command printed a traceback. `ExportRefusedError` says which it is, so the mode cannot
    change the answer.
    """
    target = f"file://{tmp_path / 'out.txt'}"
    runner = CliRunner()

    result = runner.invoke(
        cli,
        [
            "values",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/kl/temperature_air_mean_2m",
            "--periods=recent",
            "--station=01048",
            f"--target={target}",
            *given,
        ],
    )

    assert result.exit_code == 1
    assert f"Unknown export file type for target '{target}'" in caplog.text
    # a refusal, so no traceback and no "Failed to export" preamble
    assert "Traceback" not in caplog.text
    assert "Failed to export" not in caplog.text
