from pathlib import Path

import pytest
from click.testing import CliRunner

from tests.conftest import IS_WINDOWS
from wetterdienst.ui.cli import cli


def test_cli_stripes():
    runner = CliRunner()
    result = runner.invoke(cli, ["stripes", "--help"])
    assert result.exit_code == 0
    assert "Commands:\n  interactive\n  stations\n  values\n" in result.output


@pytest.mark.remote
def test_stripes_values_default():
    runner = CliRunner()
    result = runner.invoke(cli, ["stripes", "values", "--kind=precipitation", "--station=1048"])
    assert result.exit_code == 0
    assert result.stdout


@pytest.mark.remote
def test_stripes_values_name():
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
def test_stripes_values_non_defaults(params):
    params = {
        "station": "01048",
        "show_title": "true",
        "show_years": "true",
        "show_data_availability": "true",
    } | params
    params = [f"--{k}={v}" for k, v in params.items()]
    runner = CliRunner()
    result = runner.invoke(cli, ["stripes", "values", "--kind=precipitation"] + params)
    assert result.exit_code == 0
    assert result.stdout


@pytest.mark.remote
def test_stripes_values_start_year_ge_end_year():
    runner = CliRunner()
    result = runner.invoke(
        cli, ["stripes", "values", "--kind=precipitation", "--station=1048", "--start_year=2020", "--end_year=2019"]
    )
    assert result.exit_code == 1
    assert "Error: start_year must be less than end_year" in result.stdout


@pytest.mark.remote
def test_stripes_values_wrong_name_threshold():
    runner = CliRunner()
    result = runner.invoke(
        cli, ["stripes", "values", "--kind=precipitation", "--station=1048", "--name_threshold=1.01"]
    )
    assert result.exit_code == 1
    assert "Error: name_threshold must be between 0.0 and 1.0" in result.stdout


@pytest.mark.remote
def test_stripes_values_target(tmp_path):
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
def test_stripes_values_target_not_matching_format(tmp_path):
    target = tmp_path / "foobar.jpg"
    runner = CliRunner()
    result = runner.invoke(cli, ["stripes", "values", "--kind=precipitation", "--station=1048", f"--target={target}"])
    assert result.exit_code == 1
    assert "Error: 'target' must have extension 'png'" in result.stdout


@pytest.mark.remote
def test_climate_stripes_target_wrong_dpi():
    runner = CliRunner()
    result = runner.invoke(cli, ["stripes", "values", "--kind=precipitation", "--station=1048", "--dpi=0"])
    assert result.exit_code == 1
    assert "Error: dpi must be more than 0" in result.stdout
