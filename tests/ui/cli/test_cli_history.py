"""Tests for the CLI history command."""

import json

import pytest
from click.testing import CliRunner
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
        ],
    )
    assert result.exit_code == 0
    data = json.loads(result.output)
    assert data.keys() == {"metadata", "stations", "histories"}
    assert len(data["histories"]) == 1
    history = data["histories"][0]
    assert history.keys() == {"name", "parameter", "device", "geography", "missing_data"}
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
        "station_id": "2564",
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
        "station_height": 27.0,
        "station_id": "2564",
        "station_name": "Kiel-Holtenau",
    }
    assert len(history["geography"]) == 8
    assert history["geography"][0] == {
        "end_date": "1935-03-31T00:00:00+00:00",
        "latitude": 54.3767,
        "longitude": 10.1601,
        "start_date": "1927-02-01T00:00:00+00:00",
        "station_height": 4.0,
        "station_id": "2564",
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
