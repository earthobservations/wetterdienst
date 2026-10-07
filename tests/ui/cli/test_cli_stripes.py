# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for CLI stripes command."""

import logging
from pathlib import Path
from textwrap import dedent

import pytest
from click.testing import CliRunner

from tests.conftest import IS_WINDOWS
from wetterdienst.exceptions import NotEnoughDataError, StationNotFoundError
from wetterdienst.ui.cli import cli


def test_cli_stripes() -> None:
    """Test the CLI stripes command."""
    runner = CliRunner()
    result = runner.invoke(cli, ["stripes", "--help"])
    assert result.exit_code == 0
    commands = dedent(
        """
        Commands:
          stations  List stations for climate stripes.
          values    Create climate stripes for a specific station.
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


def test_stripes_values_start_year_ge_end_year() -> None:
    """Test an end year not after the start year is a usage error, before anything is fetched."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["stripes", "values", "--kind=precipitation", "--station=1048", "--start_year=2020", "--end_year=2019"],
    )
    assert result.exit_code == 2
    assert (
        "Error: Invalid value for '--end_year': Input should be greater than '--start_year' (2020) (got 2019).\n"
        in (result.stderr)
    )


def test_stripes_values_wrong_name_threshold() -> None:
    """Test a name threshold above 1 is a usage error, before anything is fetched."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["stripes", "values", "--kind=precipitation", "--station=1048", "--name_threshold=1.01"],
    )
    assert result.exit_code == 2
    assert "Error: Invalid value for '--name_threshold': Input should be less than or equal to 1 (got 1.01).\n" in (
        result.stderr
    )


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
    assert result.exit_code == 2
    assert "Error: Invalid value for --target: must have extension '.png'" in result.stderr


@pytest.mark.remote
def test_climate_stripes_target_wrong_dpi() -> None:
    """Test the summarize command with wrong DPI."""
    runner = CliRunner()
    result = runner.invoke(cli, ["stripes", "values", "--kind=precipitation", "--station=1048", "--dpi=0"])
    assert result.exit_code == 2
    assert "Error: Invalid value for '--dpi': 0 is not in the range x>0.\n" in result.stderr


def test_stripes_values_target_in_missing_directory_is_a_readable_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Test a --target in a directory that does not exist is a runtime error naming the option, not a traceback."""

    class _Figure:
        def to_image(self, _fmt: str, scale: float) -> bytes:  # noqa: ARG002
            return b"png"

    monkeypatch.setattr("wetterdienst.ui.cli._plot_stripes", lambda _request: _Figure())
    target = tmp_path / "missing" / "stripes.png"
    runner = CliRunner()
    result = runner.invoke(cli, ["stripes", "values", "--kind=precipitation", "--station=1048", f"--target={target}"])
    assert result.exit_code == 1
    assert "Usage:" not in result.output
    assert "Error: Could not write --target: " in result.output
    assert "No such file or directory" in result.output
    assert not target.exists()


def test_stripes_values_target_naming_a_directory_is_a_usage_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Test a --target naming a directory is refused as an invalid option, before anything is plotted."""

    def _plot_stripes(_request: object) -> None:
        pytest.fail("plotted although --target names a directory")

    monkeypatch.setattr("wetterdienst.ui.cli._plot_stripes", _plot_stripes)
    target = tmp_path / "stripes.png"
    target.mkdir()
    runner = CliRunner()
    result = runner.invoke(cli, ["stripes", "values", "--kind=precipitation", "--station=1048", f"--target={target}"])
    assert result.exit_code == 2
    assert "Invalid value for '--target'" in result.output
    assert "is a directory" in result.output


class _StubFigure:
    def to_image(self, fmt: str, scale: float) -> bytes:  # noqa: ARG002
        return fmt.encode()


@pytest.mark.parametrize(
    ("fmt", "name"),
    [
        pytest.param("png", "stripes.png", id="png"),
        pytest.param("png", "stripes.PNG", id="png-upper"),
        pytest.param("jpg", "stripes.jpg", id="jpg"),
        pytest.param("jpg", "stripes.jpeg", id="jpeg"),
        pytest.param("JPG", "stripes.JPEG", id="jpeg-upper"),
        pytest.param("svg", "stripes.svg", id="svg"),
        pytest.param("pdf", "stripes.pdf", id="pdf"),
    ],
)
def test_stripes_values_target_with_the_format_suffix_is_written(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fmt: str,
    name: str,
) -> None:
    """Test a --target whose suffix names --format, `.jpeg` included for jpg, is written."""
    monkeypatch.setattr("wetterdienst.ui.cli._plot_stripes", lambda _request: _StubFigure())
    target = tmp_path / name
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["stripes", "values", "--kind=precipitation", "--station=1048", f"--format={fmt}", f"--target={target}"],
    )
    assert result.exit_code == 0, result.output
    assert target.read_bytes() == fmt.lower().encode()


@pytest.mark.parametrize(
    ("fmt", "name", "expected"),
    [
        pytest.param("png", "stripespng", "'.png'", id="no-dot"),
        pytest.param("png", "stripes.xpng", "'.png'", id="longer-suffix"),
        pytest.param("png", "stripes", "'.png'", id="no-suffix"),
        pytest.param("png", "stripes.jpg", "'.png'", id="other-format"),
        pytest.param("jpg", "stripes.xjpeg", "'.jpg' or '.jpeg'", id="longer-jpeg-suffix"),
        pytest.param("svg", "stripes.svg.png", "'.svg'", id="last-suffix-counts"),
    ],
)
def test_stripes_values_target_without_the_format_suffix_is_refused(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    fmt: str,
    name: str,
    expected: str,
) -> None:
    """Test a --target whose suffix is not the dot plus --format is refused, naming the suffixes, before plotting."""

    def _plot_stripes(_request: object) -> None:
        pytest.fail("plotted although --target has the wrong suffix")

    monkeypatch.setattr("wetterdienst.ui.cli._plot_stripes", _plot_stripes)
    target = tmp_path / name
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["stripes", "values", "--kind=precipitation", "--station=1048", f"--format={fmt}", f"--target={target}"],
    )
    assert result.exit_code == 2
    assert f"Error: Invalid value for --target: must have extension {expected}\n" in result.output
    assert not target.exists()


@pytest.mark.parametrize(
    "refusal",
    [
        pytest.param(StationNotFoundError("No station with a station_id similar to '99999' found"), id="station"),
        pytest.param(NotEnoughDataError("At least two years with data are required"), id="years"),
    ],
)
def test_stripes_values_tells_a_refusal_in_one_line(
    refusal: Exception, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Test `stripes values` reports a request the caller can rephrase as a usage error, exit 2 (GH-2426)."""

    def plot(_request: object) -> None:
        raise refusal

    monkeypatch.setattr("wetterdienst.ui.cli._plot_stripes", plot)
    with caplog.at_level(logging.ERROR):
        result = CliRunner().invoke(cli, ["stripes", "values", "--kind=temperature", "--station=99999"])

    assert result.exit_code == 2, result.output
    assert result.stderr.endswith(f"\n\nError: {refusal}\n")
    assert not caplog.records


def test_stripes_values_keeps_the_traceback_for_an_upstream_failure(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Test an upstream failure is logged with its traceback and exits 1, unlike a refusal (GH-2426)."""

    def plot(_request: object) -> None:
        msg = "upstream file unreachable"
        raise FileNotFoundError(msg)

    monkeypatch.setattr("wetterdienst.ui.cli._plot_stripes", plot)
    with caplog.at_level(logging.ERROR):
        result = CliRunner().invoke(cli, ["stripes", "values", "--kind=temperature", "--station=1048"])

    assert result.exit_code == 1, result.output
    assert "Usage:" not in result.output
    assert "Error: upstream file unreachable" in result.output
    assert "FileNotFoundError: upstream file unreachable" in caplog.text


@pytest.mark.parametrize(
    "target",
    [
        pytest.param("s3://bucket/stripes.png", id="s3"),
        pytest.param("duckdb:///stripes.png", id="duckdb"),
        pytest.param("file://stripes.png", id="file"),
        pytest.param("s3://bucket/stripes", id="no-suffix"),
    ],
)
def test_stripes_values_target_with_a_uri_scheme_is_refused_before_plotting(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    target: str,
) -> None:
    """Test a --target holding `://` is a usage error before anything is fetched or rendered (GH-2450)."""

    def _plot_stripes(_request: object) -> None:
        pytest.fail("plotted although --target is a URI")

    monkeypatch.setattr("wetterdienst.ui.cli._plot_stripes", _plot_stripes)
    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(
        cli, ["stripes", "values", "--kind=precipitation", "--station=1048", f"--target={target}"]
    )
    assert result.exit_code == 2, result.output
    assert "Invalid value for --target: only a local path is supported here, not a URI.\n" in result.output
    assert list(tmp_path.iterdir()) == []
