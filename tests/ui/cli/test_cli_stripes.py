# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for CLI stripes command."""

from pathlib import Path
from textwrap import dedent

import pytest
from click.testing import CliRunner

from tests.conftest import IS_WINDOWS
from wetterdienst.ui.cli import cli


def test_cli_stripes() -> None:
    """Test the CLI stripes command."""
    runner = CliRunner()
    result = runner.invoke(cli, ["stripes"])
    assert result.exit_code == 0
    commands = dedent(
        """
        Commands:
          interactive  Start the Climate Stripes web service.
          stations     List stations for climate stripes.
          values       Create climate stripes for a specific station.
        """,
    )
    assert commands in result.output


@pytest.mark.remote
def test_stripes_values_default() -> None:
    """Test the summarize command with default parameters."""
    runner = CliRunner()
    result = runner.invoke(cli, ["stripes", "values", "--kind=precipitation", "--station=1048"])
    assert result.exit_code == 0
    assert result.stdout


@pytest.mark.remote
def test_stripes_values_name() -> None:
    """Test the summarize command with name."""
    runner = CliRunner()
    result = runner.invoke(cli, ["stripes", "values", "--kind=precipitation", "--name=Dresden-Klotzsche"])
    assert result.exit_code == 0
    assert result.stdout


@pytest.mark.remote
@pytest.mark.parametrize(
    "params",
    [
        {"show_title": "false"},
        {"show_years": "false"},
        {"show_data_availability": "false"},
    ],
)
def test_stripes_values_non_defaults(params: dict) -> None:
    """Test the summarize command with non-default parameters."""
    params = {
        "station": "01048",
        "show_title": "true",
        "show_years": "true",
        "show_data_availability": "true",
    } | params
    params = [f"--{k}={v}" for k, v in params.items()]
    runner = CliRunner()
    result = runner.invoke(cli, ["stripes", "values", "--kind=precipitation", *params])
    assert result.exit_code == 0
    assert result.stdout


@pytest.mark.remote
def test_stripes_values_start_year_ge_end_year() -> None:
    """Test the summarize command with start_year greater than end_year."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["stripes", "values", "--kind=precipitation", "--station=1048", "--start_year=2020", "--end_year=2019"],
    )
    assert result.exit_code == 1
    assert "Error: start_year must be less than end_year" in result.stdout


@pytest.mark.remote
def test_stripes_values_wrong_name_threshold() -> None:
    """Test the summarize command with wrong name_threshold."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["stripes", "values", "--kind=precipitation", "--station=1048", "--name_threshold=1.01"],
    )
    assert result.exit_code == 1
    assert "Error: name_threshold must be between 0.0 and 1.0" in result.stdout


@pytest.mark.remote
def test_stripes_values_target(tmp_path: Path) -> None:
    """Test the summarize command with target."""
    target = Path("foobar.png")
    if not IS_WINDOWS:
        target = tmp_path / "foobar.png"
    runner = CliRunner()
    result = runner.invoke(cli, ["stripes", "values", "--kind=precipitation", "--station=1048", f"--target={target}"])
    assert result.exit_code == 0
    assert target.exists()
    assert not result.stdout
    if IS_WINDOWS:
        target.unlink(missing_ok=True)


@pytest.mark.remote
def test_stripes_values_target_not_matching_format(tmp_path: Path) -> None:
    """Test the summarize command with wrong target format."""
    target = tmp_path / "foobar.jpg"
    runner = CliRunner()
    result = runner.invoke(cli, ["stripes", "values", "--kind=precipitation", "--station=1048", f"--target={target}"])
    assert result.exit_code == 1
    assert "Error: 'target' must have extension 'png'" in result.stdout


@pytest.mark.remote
def test_climate_stripes_target_wrong_dpi() -> None:
    """Test the summarize command with wrong DPI."""
    runner = CliRunner()
    result = runner.invoke(cli, ["stripes", "values", "--kind=precipitation", "--station=1048", "--dpi=0"])
    assert result.exit_code == 2
    assert "Error: Invalid value for '--dpi': 0 is not in the range x>0.\n" in result.stdout
