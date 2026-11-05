# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the CLI alerts command."""

import json
from pathlib import Path

import polars as pl
import pytest
from click.testing import CliRunner

from wetterdienst.provider.dwd.alerts.api import _SCHEMA, DwdWeatherAlertResult
from wetterdienst.provider.dwd.alerts.metadata import DwdWeatherAlertGranularity, DwdWeatherAlertLanguage
from wetterdienst.ui.cli import cli


def _no_alerts() -> DwdWeatherAlertResult:
    """Make the result of a snapshot that holds no warning."""
    return DwdWeatherAlertResult(
        pl.DataFrame(schema=_SCHEMA), DwdWeatherAlertGranularity.COMMUNITY, DwdWeatherAlertLanguage.ENGLISH
    )


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


def test_cli_alerts_unreachable_feed_is_one_line_and_exit_1(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    """Test no connection to DWD's feed is the one line of `NoInternetError`, without a traceback (GH-2640)."""
    import logging  # noqa: PLC0415

    from wetterdienst.exceptions import NoInternetError  # noqa: PLC0415
    from wetterdienst.provider.dwd.alerts import DwdWeatherAlertRequest  # noqa: PLC0415

    msg = "No internet connection: could not reach https://opendata.dwd.de/weather/alerts/cap/ (Cannot connect)"

    def query(_self: DwdWeatherAlertRequest) -> None:
        raise NoInternetError(msg)

    monkeypatch.setattr(DwdWeatherAlertRequest, "query", query)
    with caplog.at_level(logging.ERROR):
        result = CliRunner().invoke(cli, ["alerts"])

    assert result.exit_code == 1
    assert [record.getMessage() for record in caplog.records if record.levelno >= logging.ERROR] == [msg]
    assert all(record.exc_info is None for record in caplog.records)
    assert "Usage:" not in result.output


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

    monkeypatch.setattr(DwdWeatherAlertRequest, "query", lambda _self: _no_alerts())
    target = tmp_path / "missing" / "alerts.json"
    runner = CliRunner()
    result = runner.invoke(cli, ["alerts", f"--target=file://{target}"])
    assert result.exit_code == 1
    assert "Usage:" not in result.output
    assert "Error: Could not write --target: " in result.output
    assert "No such file or directory" in result.output
    assert not target.exists()


def test_cli_alerts_percent_encoded_file_uri_target(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test a `file://` URI as `Path.as_uri()` gives it, `%20` for a space, writes to the path it names (GH-2454)."""
    from wetterdienst.provider.dwd.alerts import DwdWeatherAlertRequest  # noqa: PLC0415

    monkeypatch.setattr(DwdWeatherAlertRequest, "query", lambda _self: _no_alerts())
    directory = tmp_path / "my data"
    directory.mkdir()
    target = directory / "alerts.json"
    result = CliRunner().invoke(cli, ["alerts", f"--target={target.as_uri()}"])
    assert result.exit_code == 0, result.output
    written = json.loads(target.read_text(encoding="utf-8"))
    assert written["alerts"] == []
    assert written["metadata"]["request"]["network"] == "alerts"
    assert not (tmp_path / "my%20data").exists()


# --- --target, --if-exists and --with-metadata (GH-3706) -----------------------------------------------------------


def _serve(monkeypatch: pytest.MonkeyPatch, result: DwdWeatherAlertResult) -> list[int]:
    """Make the request answer `result`, and count the times it is asked: a refusal before the fetch asks none."""
    from wetterdienst.provider.dwd.alerts import DwdWeatherAlertRequest  # noqa: PLC0415

    asked: list[int] = []

    def query(_self: DwdWeatherAlertRequest) -> DwdWeatherAlertResult:
        asked.append(1)
        return result

    monkeypatch.setattr(DwdWeatherAlertRequest, "query", query)
    return asked


def _two_alerts() -> DwdWeatherAlertResult:
    """Parse two real-shaped CAP documents as `query` does."""
    from tests.provider.dwd.alerts.test_parser import CAP_XML  # noqa: PLC0415
    from tests.provider.dwd.alerts.test_to_target import CAP_TWO_INFOS, _result  # noqa: PLC0415

    return _result(CAP_XML, CAP_TWO_INFOS)


@pytest.mark.parametrize("name", ["alerts.json", "alerts.geojson", "alerts.csv"])
@pytest.mark.parametrize("scheme", ["file://", ""])
def test_cli_alerts_target_writes_the_file_its_extension_names(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str, scheme: str
) -> None:
    """The extension decides the format, for a `file://` URI and for a plain path, as for `stations` and `values`."""
    result = _two_alerts()
    _serve(monkeypatch, result)
    file = tmp_path / name
    run = CliRunner().invoke(cli, ["alerts", f"--target={scheme}{file}"])
    assert run.exit_code == 0, run.output
    assert run.stdout == ""
    written = file.read_text(encoding="utf-8")
    if name.endswith(".csv"):
        assert written == result.to_csv()
    elif name.endswith(".geojson"):
        assert json.loads(written)["type"] == "FeatureCollection"
        assert len(json.loads(written)["features"]) == 2
    else:
        assert len(json.loads(written)["alerts"]) == 2
        assert json.loads(written)["metadata"]["provider"]["license"]["spdx_id"] == "CC-BY-4.0"
    assert not (tmp_path / f"{name}.metadata.json").exists()


def test_cli_alerts_target_reads_a_percent_of_a_plain_path_as_it_is(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A path without the scheme is a path, `%20` and all, where a `file://` URI would decode it."""
    _serve(monkeypatch, _two_alerts())
    directory = tmp_path / "a%20b"
    directory.mkdir()
    run = CliRunner().invoke(cli, ["alerts", f"--target={directory / 'alerts.csv'}"])
    assert run.exit_code == 0, run.output
    assert (directory / "alerts.csv").exists()


def test_cli_alerts_with_metadata_writes_the_block_beside_the_file(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """`--with-metadata` is `<file>.metadata.json` with the licence, the credit line and the date of the data."""
    _serve(monkeypatch, _two_alerts())
    file = tmp_path / "alerts.csv"
    run = CliRunner().invoke(cli, ["alerts", f"--target={file}", "--with-metadata"])
    assert run.exit_code == 0, run.output
    sidecar = json.loads((tmp_path / "alerts.csv.metadata.json").read_text(encoding="utf-8"))
    assert sidecar["provider"]["license"]["spdx_id"] == "CC-BY-4.0"
    assert sidecar["provider"]["attribution"] == "Source: Deutscher Wetterdienst"
    assert sidecar["data_updated_at"] == "2026-07-26T07:23:00.000000+00:00"
    assert sidecar["counts"]["rows"] == 2


def test_cli_alerts_with_metadata_needs_a_target_and_is_told_before_the_fetch(monkeypatch: pytest.MonkeyPatch) -> None:
    """Without a file there is nothing to write beside, and the JSON on stdout has the block always: a usage error."""
    asked = _serve(monkeypatch, _two_alerts())
    run = CliRunner().invoke(cli, ["alerts", "--with-metadata"])
    assert run.exit_code == 2
    assert "needs --target" in run.output
    assert asked == []


def test_cli_alerts_a_format_that_names_another_file_type_is_a_usage_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Neither the format nor the extension silently wins: the old `--format=geojson --target=x.json` is refused."""
    asked = _serve(monkeypatch, _two_alerts())
    run = CliRunner().invoke(cli, ["alerts", "--format=geojson", f"--target={tmp_path / 'alerts.json'}"])
    assert run.exit_code == 2
    assert "--format=geojson does not match .json" in run.output
    assert not (tmp_path / "alerts.json").exists()
    assert asked == []
    # the same format as the extension says is no conflict, in any case
    run = CliRunner().invoke(cli, ["alerts", "--format=CSV", f"--target={tmp_path / 'alerts.csv'}"])
    assert run.exit_code == 0, run.output
    assert (tmp_path / "alerts.csv").exists()


@pytest.mark.parametrize("name", ["alerts.txt", "alerts.parquet", "alerts.xlsx", "alerts"])
def test_cli_alerts_a_file_of_none_of_the_three_is_a_usage_error_before_the_fetch(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, name: str
) -> None:
    """Parquet, a spreadsheet and the rest are refused naming the three the alerts are written as."""
    asked = _serve(monkeypatch, _two_alerts())
    run = CliRunner().invoke(cli, ["alerts", f"--target={tmp_path / name}"])
    assert run.exit_code == 2
    assert ".json, .geojson, .csv" in run.output
    assert asked == []
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize(
    "target", ["duckdb:///x.duckdb?table=t", "sqlite:///x.sqlite?table=t", "s3://bucket/alerts.csv"]
)
def test_cli_alerts_a_database_target_is_refused_before_the_fetch(monkeypatch: pytest.MonkeyPatch, target: str) -> None:
    """An alert is nested and has no table yet: the refusal is a usage error, as it was for any non-file target."""
    asked = _serve(monkeypatch, _two_alerts())
    run = CliRunner().invoke(cli, ["alerts", f"--target={target}", "--with-metadata"])
    assert run.exit_code == 2
    assert "file://" in run.output
    assert asked == []


def test_cli_alerts_if_exists_fail_and_append_are_one_line_with_exit_1(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A refusal of the sink is its message and exit code 1, and the file that is there stays."""
    _serve(monkeypatch, _two_alerts())
    file = tmp_path / "alerts.csv"
    file.write_text("old")
    run = CliRunner().invoke(cli, ["alerts", f"--target={file}", "--if-exists=fail"])
    assert run.exit_code == 1
    assert "already exists" in run.output
    assert "Traceback" not in run.output
    run = CliRunner().invoke(cli, ["alerts", f"--target={file}", "--if-exists=append"])
    assert run.exit_code == 1
    assert "Append mode is not supported" in run.output
    assert file.read_text() == "old"
    run = CliRunner().invoke(cli, ["alerts", f"--target={file}", "--if-exists=skip"])
    assert run.exit_code == 0
    assert file.read_text() == "old"
    run = CliRunner().invoke(cli, ["alerts", f"--target={file}"])
    assert run.exit_code == 0
    assert file.read_text(encoding="utf-8").startswith("alert_id,")


def test_cli_alerts_a_directory_that_is_not_there_is_exit_1(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A path that cannot be written is told in one line, as it was before `to_target`."""
    _serve(monkeypatch, _two_alerts())
    run = CliRunner().invoke(cli, ["alerts", f"--target={tmp_path / 'missing' / 'alerts.json'}"])
    assert run.exit_code == 1
    assert "Could not write --target" in run.output


def test_cli_alerts_no_warning_writes_the_empty_file_and_exits_0(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Where the other commands leave a target alone, no warning is the answer of a snapshot and the file says it."""
    _serve(monkeypatch, _no_alerts())
    (tmp_path / "alerts.csv").write_text("old warnings")
    run = CliRunner().invoke(cli, ["alerts", f"--target={tmp_path / 'alerts.csv'}"])
    assert run.exit_code == 0, run.output
    assert (tmp_path / "alerts.csv").read_text(encoding="utf-8").startswith("alert_id,status,")
    assert len((tmp_path / "alerts.csv").read_text(encoding="utf-8").splitlines()) == 1
    run = CliRunner().invoke(cli, ["alerts", f"--target={tmp_path / 'alerts.json'}"])
    assert run.exit_code == 0, run.output
    assert json.loads((tmp_path / "alerts.json").read_text(encoding="utf-8"))["alerts"] == []


def test_cli_alerts_without_a_target_still_prints_the_answer_with_its_block(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stdout is what it was: the format asked for, the JSON with the `metadata` block."""
    _serve(monkeypatch, _two_alerts())
    run = CliRunner().invoke(cli, ["alerts"])
    assert run.exit_code == 0, run.output
    data = json.loads(run.output)
    assert list(data) == ["metadata", "snapshot", "alerts"]
    run = CliRunner().invoke(cli, ["alerts", "--format=csv"])
    assert run.exit_code == 0, run.output
    assert run.output.startswith("alert_id,")
