# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the CLI alerts command."""

import json
from pathlib import Path

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
    result = runner.invoke(
        cli, ["alerts", "--granularity=district", f"--timestamp={target.strftime('%Y-%m-%dT%H:%M:%S')}"]
    )
    assert result.exit_code == 0
    assert "alerts" in json.loads(result.output)


@pytest.mark.remote
def test_cli_alerts_date_before_window() -> None:
    """Test the alerts command rejects a date older than the rolling window."""
    runner = CliRunner()
    result = runner.invoke(cli, ["alerts", "--timestamp=2000-01-01T00:00:00"])
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


def test_cli_alerts_date_before_window_is_a_date_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test a date before DWD's rolling window is reported as an invalid --timestamp, with exit status 2."""
    from wetterdienst.exceptions import InvalidTimeIntervalError  # noqa: PLC0415
    from wetterdienst.provider.dwd.alerts import DwdWeatherAlertRequest  # noqa: PLC0415

    def query(_self: DwdWeatherAlertRequest) -> None:
        msg = "no weather-alerts snapshot available at or before 2000-01-01T00:00:00+00:00"
        raise InvalidTimeIntervalError(msg)

    monkeypatch.setattr(DwdWeatherAlertRequest, "query", query)
    runner = CliRunner()
    result = runner.invoke(cli, ["alerts", "--timestamp=2000-01-01T00:00:00"])
    assert result.exit_code == 2
    assert "Usage:" in result.output
    assert "Invalid value for --timestamp: no weather-alerts snapshot available" in result.output


def test_cli_alerts_unreadable_feed_is_not_a_usage_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test a ValueError from reading DWD's feed is a runtime error with exit status 1, not a usage error."""
    from wetterdienst.provider.dwd.alerts import DwdWeatherAlertRequest  # noqa: PLC0415

    def query(_self: DwdWeatherAlertRequest) -> None:
        msg = "Invalid isoformat string: 'not-a-timestamp'"
        raise ValueError(msg)

    monkeypatch.setattr(DwdWeatherAlertRequest, "query", query)
    runner = CliRunner()
    result = runner.invoke(cli, ["alerts"])
    assert result.exit_code == 1
    assert "Usage:" not in result.output
    assert "Invalid value" not in result.output
    assert "Error: Invalid isoformat string: 'not-a-timestamp'" in result.output


@pytest.mark.parametrize(
    ("date", "message"),
    [
        # an offset carries it out of what a datetime holds: an `OverflowError`, not a `ValueError`
        ("0001-01-01T00:00:00+01:00", "date value out of range"),
        ("notadate", "Invalid isoformat string: 'notadate'"),
    ],
)
def test_cli_alerts_bad_date_is_a_date_usage_error(date: str, message: str) -> None:
    """Test a date that does not parse, or that leaves a datetime's range, is reported as an invalid --timestamp."""
    runner = CliRunner()
    result = runner.invoke(cli, ["alerts", f"--timestamp={date}"])
    assert result.exit_code == 2
    assert "Usage:" in result.output
    assert f"Invalid value for --timestamp: {message}" in result.output


def test_cli_alerts_does_not_blame_the_command_line_for_the_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Test a WD_* environment variable Settings refuses is not told as an invalid option of the command."""
    monkeypatch.setenv("WD_CACHE_DISABLE", "notabool")
    runner = CliRunner()
    result = runner.invoke(cli, ["alerts", "--timestamp=2000-01-01T00:00:00"])
    assert result.exit_code == 1, result.output
    assert "Error: WD_CACHE_DISABLE is invalid: " in result.output
    assert "Usage:" not in result.output
    assert "--timestamp" not in result.output


def test_cli_alerts_unwritable_target_is_a_readable_error(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test a --target that cannot be written is a runtime error naming the option, not a traceback."""
    from wetterdienst.provider.dwd.alerts import DwdWeatherAlertRequest  # noqa: PLC0415

    class _Result:
        def to_format(self, _fmt: str, *, indent: bool) -> str:  # noqa: ARG002
            return "{}"

    monkeypatch.setattr(DwdWeatherAlertRequest, "query", lambda _self: _Result())
    target = tmp_path / "missing" / "alerts.json"
    runner = CliRunner()
    result = runner.invoke(cli, ["alerts", f"--target=file://{target}"])
    assert result.exit_code == 1
    assert "Usage:" not in result.output
    assert "Error: Could not write --target: " in result.output
    assert "No such file or directory" in result.output
    assert not target.exists()
