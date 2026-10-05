"""Tests for the CLI history command."""

import json
from pathlib import Path

import pytest
from click.testing import CliRunner, Result
from dirty_equals import IsApprox, IsStr

from wetterdienst.ui.cli import cli


@pytest.mark.remote
def test_history_dwd_observation() -> None:
    """Test dwd observation parameter."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "history",
            "--provider",
            "dwd",
            "--network",
            "observation",
            "--parameters",
            "daily/climate_summary",
            "--station",
            "02564",
            # with_metadata/with_stations now default to false; request them explicitly here
            "--with_metadata=true",
            "--with_stations=true",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data.keys() == {"metadata", "stations", "histories"}
    assert len(data["histories"]) == 1
    history = data["histories"][0]
    assert history.keys() == {
        "station_id",
        "resolution",
        "dataset",
        "name",
        "parameter",
        "device",
        "geography",
        "missing_data",
    }
    assert (history["station_id"], history["resolution"], history["dataset"]) == ("02564", "daily", "climate_summary")
    assert len(history["name"]) == 2
    assert history["name"].keys() == {"station", "operator"}
    assert history["name"]["station"][0] == {
        "station_id": "02564",
        "station_name": "Kiel-Holtenau",
        "start_date": "1927-02-01T00:00:00+00:00",
        "end_date": None,
    }
    assert history["name"]["operator"][0] == {
        "station_id": "02564",
        "operator_name": "Wetterdienst",
        "start_date": "1927-02-01T00:00:00+00:00",
        "end_date": "1951-01-16T00:00:00+00:00",
    }
    assert len(history["parameter"]) == 30
    assert history["parameter"][0] == {
        "data_source": "Winddaten (Stundenmittel, maximale Windspitze 00:00-23:59 "
        "MEZ) generiert aus analogen Registrierungen. Richtungsangaben "
        "in der 32-teiligen Windrose.",
        "description": "Tagesmittel der Windgeschwindigkeit m/s  Messnetz 3",
        "end_date": "1974-12-31T00:00:00+00:00",
        "extra_info": "arithm.Mittel aus mind. 21 Stundenwerten",
        "literature": "",
        "parameter": "FM",
        "special": "",
        "start_date": "1974-01-01T00:00:00+00:00",
        "station_id": "02564",
        "station_name": "Kiel-Holtenau",
        "unit": "m/sec",
    }
    assert len(history["device"]) == 49
    assert history["device"][0] == {
        "device_height": 31.0,
        "device_type": "Stationsbarometer",
        "end_date": "2009-11-17T00:00:00+00:00",
        "latitude": 54.38,
        "longitude": 10.14,
        "method": "Luftdruckmessung, konv.",
        "start_date": "1986-06-01T00:00:00+00:00",
        "station_elevation": 27.0,
        "station_id": "02564",
        "station_name": "Kiel-Holtenau",
    }
    assert len(history["geography"]) == 8
    assert history["geography"][0] == {
        "end_date": "1935-03-31T00:00:00+00:00",
        "latitude": 54.3767,
        "longitude": 10.1601,
        "start_date": "1927-02-01T00:00:00+00:00",
        "station_elevation": 4.0,
        "station_id": "02564",
        "station_name": "Kiel-Holtenau",
    }
    assert len(history["missing_data"]) == 2
    assert history["missing_data"].keys() == {"summary", "periods"}
    assert history["missing_data"]["summary"][0] == {
        "description": "Gesamt_Messzeitraum",
        "end_date": IsStr,
        "missing_count": IsApprox(147, delta=50),
        "parameter": "TMK",
        "start_date": "1974-01-01T00:00:00+00:00",
        "station_id": "02564",
        "station_name": "Kiel-Holtenau",
    }
    assert len(history["missing_data"]["periods"]) == IsApprox(398, delta=100)
    assert history["missing_data"]["periods"][0] == {
        "description": "",
        "end_date": "2007-03-12T00:00:00+00:00",
        "missing_count": 1,
        "parameter": "TMK",
        "start_date": "2007-03-12T00:00:00+00:00",
        "station_id": "02564",
        "station_name": "Kiel-Holtenau",
    }


@pytest.mark.remote
@pytest.mark.parametrize("sections", ["geography,name", "name,geography"])
def test_history_sections(sections: str) -> None:
    """Test --sections keeps only the sections asked for, in the history's own order."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "history",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/climate_summary",
            "--station=02564",
            f"--sections={sections}",
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.stdout)
    assert [list(history) for history in data["histories"]] == [
        ["station_id", "resolution", "dataset", "name", "geography"]
    ]


def test_history_sections_unknown() -> None:
    """Test a section the history does not have is a usage error, not a traceback."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "history",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/climate_summary",
            "--station=02564",
            "--sections=geo",
        ],
    )
    assert result.exit_code == 2
    assert "Input should be 'name', 'parameter', 'device', 'geography' or 'missing_data'" in result.output


def test_history_no_station_selection() -> None:
    """Test a history request with neither --all nor --station is a usage error, not a traceback."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["history", "--provider=dwd", "--network=observation", "--parameters=daily/climate_summary"],
    )
    assert result.exit_code == 2
    assert "Error: Missing option: one of '--all' or '--station'." in result.output


def _unwritable_history_target(monkeypatch: pytest.MonkeyPatch, target: Path) -> Result:
    """Run history for one station with the fetch stubbed out, writing to `target`."""

    class _History:
        def query(self) -> list:
            return []

    class _Stations:
        history = _History()

    monkeypatch.setattr("wetterdienst.ui.cli.get_stations", lambda **_kwargs: _Stations())
    runner = CliRunner()
    return runner.invoke(
        cli,
        [
            "history",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/climate_summary",
            "--station=02564",
            f"--target={target}",
        ],
    )


def test_history_target_in_missing_directory_is_a_readable_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Test a --target in a directory that does not exist is a runtime error naming the option, not a traceback."""
    target = tmp_path / "missing" / "history.json"
    result = _unwritable_history_target(monkeypatch, target)
    assert result.exit_code == 1
    assert "Usage:" not in result.output
    assert "Error: Could not write --target: " in result.output
    assert "No such file or directory" in result.output
    assert not target.exists()


def test_history_target_naming_a_directory_is_a_readable_error(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Test a --target naming a directory is a runtime error naming the option, not a traceback."""
    target = tmp_path / "history.json"
    target.mkdir()
    result = _unwritable_history_target(monkeypatch, target)
    assert result.exit_code == 1
    assert "Usage:" not in result.output
    assert "Error: Could not write --target: " in result.output
    assert target.is_dir()


def _history_to_target(monkeypatch: pytest.MonkeyPatch, target: str) -> Result:
    """Run history for one station with the fetch stubbed out to no histories, writing to `target`."""

    class _History:
        def query(self) -> list:
            return []

    class _Stations:
        history = _History()

    monkeypatch.setattr("wetterdienst.ui.cli.get_stations", lambda **_kwargs: _Stations())
    return CliRunner().invoke(
        cli,
        [
            "history",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/climate_summary",
            "--station=02564",
            f"--target={target}",
        ],
    )


def test_history_target_relative_file_uri(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test the documented `--target file://history.json` writes history.json in the working directory."""
    monkeypatch.chdir(tmp_path)
    result = _history_to_target(monkeypatch, "file://history.json")
    assert result.exit_code == 0, result.output
    assert json.loads((tmp_path / "history.json").read_text()) == {"histories": []}
    # not a file inside a directory `file:`, which is where the unstripped URI pointed
    assert not (tmp_path / "file:").exists()


def test_history_target_absolute_file_uri(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test a `file://` URI holding an absolute path writes to that path."""
    target = tmp_path / "history.json"
    result = _history_to_target(monkeypatch, f"file://{target}")
    assert result.exit_code == 0, result.output
    assert json.loads(target.read_text()) == {"histories": []}


def test_history_target_file_uri_without_json_suffix(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Test the `.json` check still applies to a `file://` URI, read on the path it names."""
    monkeypatch.chdir(tmp_path)
    result = _history_to_target(monkeypatch, "file://history.txt")
    assert result.exit_code == 2
    assert "--target for history endpoint must end with .json" in result.output
    assert list(tmp_path.iterdir()) == []
