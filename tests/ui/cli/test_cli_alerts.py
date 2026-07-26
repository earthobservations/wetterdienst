# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the CLI alerts command."""

import json

import pytest
from click.testing import CliRunner

from wetterdienst.ui.cli import cli


def test_cli_alerts_help() -> None:
    """Test the alerts command help lists its options."""
    runner = CliRunner()
    result = runner.invoke(cli, ["alerts", "--help"])
    assert result.exit_code == 0
    assert "--granularity" in result.output
    assert "--language" in result.output


def test_cli_alerts_invalid_granularity() -> None:
    """Test the alerts command rejects an unknown granularity."""
    runner = CliRunner()
    result = runner.invoke(cli, ["alerts", "--granularity=bogus"])
    assert result.exit_code != 0


def test_cli_alerts_rejects_non_file_target() -> None:
    """Test the alerts command rejects a non-file:// target scheme instead of writing a stray file."""
    runner = CliRunner()
    result = runner.invoke(cli, ["alerts", "--target=duckdb:///x.duckdb?table=t"])
    assert result.exit_code != 0
    assert "file://" in result.output


@pytest.mark.remote
def test_cli_alerts_json() -> None:
    """Test the alerts command returns a JSON alert collection."""
    runner = CliRunner()
    result = runner.invoke(cli, ["alerts", "--granularity=community"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert "alerts" in data


@pytest.mark.remote
def test_cli_alerts_geojson() -> None:
    """Test the alerts command returns a GeoJSON FeatureCollection."""
    runner = CliRunner()
    result = runner.invoke(cli, ["alerts", "--granularity=district", "--format=geojson"])
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data["type"] == "FeatureCollection"


@pytest.mark.remote
def test_cli_alerts_date_snapshot() -> None:
    """Test the alerts command accepts a historical date within the rolling window."""
    import datetime as dt  # noqa: PLC0415
    from zoneinfo import ZoneInfo  # noqa: PLC0415

    target = dt.datetime.now(ZoneInfo("UTC")) - dt.timedelta(hours=6)
    runner = CliRunner()
    result = runner.invoke(cli, ["alerts", "--granularity=district", f"--date={target.strftime('%Y-%m-%dT%H:%M:%S')}"])
    assert result.exit_code == 0
    assert "alerts" in json.loads(result.output)


@pytest.mark.remote
def test_cli_alerts_date_before_window() -> None:
    """Test the alerts command rejects a date older than the rolling window."""
    runner = CliRunner()
    result = runner.invoke(cli, ["alerts", "--date=2000-01-01T00:00:00"])
    assert result.exit_code != 0


@pytest.mark.remote
def test_cli_alerts_target_file(tmp_path) -> None:  # noqa: ANN001
    """Test the alerts command writes output to a file target."""
    runner = CliRunner()
    target = tmp_path / "alerts.geojson"
    result = runner.invoke(
        cli,
        ["alerts", "--format=geojson", f"--target=file://{target}"],
    )
    assert result.exit_code == 0
    data = json.loads(target.read_text(encoding="utf-8"))
    assert data["type"] == "FeatureCollection"
