import json

import pytest
from click.testing import CliRunner

from wetterdienst.ui.cli import cli


@pytest.mark.remote
def test_cli_summarize_no_metadata_no_stations():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "summarize",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/climate_summary/temperature_air_mean_2m",
            "--station=00071",
            "--date=1986-10-31/1986-11-01",
            "--format=json",
            "--with_metadata=false",
            "--with_stations=false",
        ],
    )
    if result.exit_code != 0:
        raise ChildProcessError(result.stderr)
    response = json.loads(result.stdout)
    assert response.keys() == {"values"}
    assert response["values"] == [
        {
            "station_id": "a87291a8",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-10-31T00:00:00+00:00",
            "value": 6.6,
            "distance": 6.97,
            "taken_station_id": "00072",
        },
        {
            "station_id": "a87291a8",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-11-01T00:00:00+00:00",
            "value": 8.7,
            "distance": 0.0,
            "taken_station_id": "00071",
        },
    ]


@pytest.mark.remote
def test_cli_summarize_geojson(metadata):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "summarize",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/climate_summary/temperature_air_mean_2m",
            "--station=00071",
            "--date=1986-10-31/1986-11-01",
            "--format=geojson",
        ],
    )
    if result.exit_code != 0:
        raise ChildProcessError(result.stderr)
    response = json.loads(result.stdout)
    assert response.keys() == {"metadata", "data"}
    assert response["metadata"] == metadata
    assert response["data"] == {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": "a87291a8", "name": "summary(48.2156,8.9784)"},
                "geometry": {"type": "Point", "coordinates": [8.9784, 48.2156]},
                "stations": [
                    {
                        "station_id": "00071",
                        "start_date": "1986-11-01T00:00:00+00:00",
                        "end_date": "2019-12-31T00:00:00+00:00",
                        "latitude": 48.2156,
                        "longitude": 8.9784,
                        "height": 759.0,
                        "name": "Albstadt-Badkap",
                        "state": "Baden-Württemberg",
                    },
                    {
                        "station_id": "00072",
                        "start_date": "1978-09-01T00:00:00+00:00",
                        "end_date": "1995-05-31T00:00:00+00:00",
                        "latitude": 48.2766,
                        "longitude": 9.0001,
                        "height": 794.0,
                        "name": "Albstadt-Onstmettingen",
                        "state": "Baden-Württemberg",
                    },
                ],
                "values": [
                    {
                        "station_id": "a87291a8",
                        "dataset": "climate_summary",
                        "parameter": "temperature_air_mean_2m",
                        "date": "1986-10-31T00:00:00+00:00",
                        "value": 6.6,
                        "distance": 6.97,
                        "taken_station_id": "00072",
                    },
                    {
                        "station_id": "a87291a8",
                        "dataset": "climate_summary",
                        "parameter": "temperature_air_mean_2m",
                        "date": "1986-11-01T00:00:00+00:00",
                        "value": 8.7,
                        "distance": 0.0,
                        "taken_station_id": "00071",
                    },
                ],
            },
        ],
    }


@pytest.mark.remote
def test_cli_summarize_custom_units():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "summarize",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/climate_summary/temperature_air_mean_2m",
            "--station=00071",
            "--date=1986-10-31/1986-11-01",
            "--format=json",
            '--unit_targets={"temperature": "degree_fahrenheit"}',
            "--with_metadata=false",
            "--with_stations=false",
        ],
    )
    if result.exit_code != 0:
        raise ChildProcessError(result.stderr)
    response = json.loads(result.stdout)
    assert response.keys() == {"values"}
    assert response["values"] == [
        {
            "station_id": "a87291a8",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-10-31T00:00:00+00:00",
            "value": 43.88,
            "distance": 6.97,
            "taken_station_id": "00072",
        },
        {
            "station_id": "a87291a8",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-11-01T00:00:00+00:00",
            "value": 47.66,
            "distance": 0.0,
            "taken_station_id": "00071",
        },
    ]


@pytest.mark.parametrize(
    "fmt",
    [
        "png",
        "jpg",
        "webp",
        "svg",
    ],
)
def test_cli_summarize_image(fmt):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "summarize",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/climate_summary/temperature_air_mean_2m",
            "--station=00071",
            "--date=1986-10-31/1986-11-01",
            "--format=json",
            f"--format={fmt}",
        ],
    )
    assert "Error" not in result.output
    assert result.exit_code == 0


@pytest.mark.remote
def test_cli_summarize_image_html():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "summarize",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/climate_summary/temperature_air_mean_2m",
            "--date=2020-06-30",
            "--station=01048",
            "--format=html",
        ],
    )
    assert result.exit_code == 0
    assert "html" in result.output


@pytest.mark.remote
def test_cli_summarize_image_pdf():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "summarize",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/climate_summary/temperature_air_mean_2m",
            "--date=2020-06-30",
            "--station=01048",
            "--format=pdf",
        ],
    )
    assert result.exit_code == 0
