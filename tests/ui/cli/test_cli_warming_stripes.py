import pytest
from click.testing import CliRunner

from wetterdienst.ui.cli import cli


@pytest.mark.remote
def test_warming_stripes_default():
    runner = CliRunner()
    result = runner.invoke(cli, "warming_stripes --station 1048")
    assert result.exit_code == 0
    assert result.stdout


@pytest.mark.remote
def test_warming_stripes_name():
    runner = CliRunner()
    result = runner.invoke(cli, "warming_stripes --name Dresden-Klotzsche")
    assert result.exit_code == 0
    assert result.stdout


@pytest.mark.remote
@pytest.mark.parametrize(
    "params",
    [
        {"show_title": "true"},
        {"show_years": "true"},
        {"show_data_availability": "true"},
        {"show_title": "false"},
        {"show_years": "false"},
        {"show_data_availability": "false"},
    ],
)
def test_warming_stripes_non_defaults(params):
    params = params | {
        "station": "01048",
        "show_title": "true",
        "show_years": "true",
        "show_data_availability": "true",
    }
    params_string = " ".join([f"--{k} {v}" for k, v in params.items()])
    runner = CliRunner()
    result = runner.invoke(cli, f"warming_stripes {params_string}")
    assert result.exit_code == 0
    assert result.stdout


@pytest.mark.remote
def test_warming_stripes_start_year_ge_end_year():
    runner = CliRunner()
    result = runner.invoke(cli, "warming_stripes --station 1048 --start_year 2020 --end_year 2019")
    assert result.exit_code == 1
    assert "Error: start_year must be less than end_year" in result.stdout


@pytest.mark.remote
def test_warming_stripes_wrong_name_threshold():
    runner = CliRunner()
    result = runner.invoke(cli, "warming_stripes --station 1048 --name_threshold 101")
    assert result.exit_code == 1
    assert "Error: name_threshold must be more than 0 and less than or equal to 100" in result.stdout


@pytest.mark.remote
def test_warming_stripes_target(tmp_path):
    target = tmp_path / "foobar.png"
    runner = CliRunner()
    result = runner.invoke(cli, f"warming_stripes --station 1048 --target {target}")
    assert result.exit_code == 0
    assert target.exists()
    assert not result.stdout


@pytest.mark.remote
def test_warming_stripes_target_not_matching_format(tmp_path):
    target = tmp_path / "foobar.jpg"
    runner = CliRunner()
    result = runner.invoke(cli, f"warming_stripes --station 1048 --target {target}")
    assert result.exit_code == 1
    assert "Error: 'target' must have extension 'png'" in result.stdout
