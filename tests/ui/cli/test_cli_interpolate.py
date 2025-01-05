import json

import pytest
from click.testing import CliRunner
from dirty_equals import IsStr

from wetterdienst.ui.cli import cli


@pytest.mark.remote
def test_cli_interpolate():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "interpolate",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/kl/temperature_air_mean_2m",
            "--station=00071",
            "--date=1986-10-31/1986-11-01",
            "--format=json",
        ],
    )
    if result.exit_code != 0:
        raise ChildProcessError(result.stderr)
    response = json.loads(result.stdout)
    assert response.keys() == {"values"}
    assert response["values"] == [
        {
            "station_id": "6754d04d",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-10-31T00:00:00+00:00",
            "value": 6.37,
            "distance_mean": 16.99,
            "taken_station_ids": ["00072", "02074", "02638", "04703"],
        },
        {
            "station_id": "6754d04d",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-11-01T00:00:00+00:00",
            "value": 8.7,
            "distance_mean": 0.0,
            "taken_station_ids": ["00071"],
        },
    ]


@pytest.mark.remote
def test_cli_interpolate_with_metadata_with_stations(metadata):
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "interpolate",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/climate_summary/temperature_air_mean_2m",
            "--station=00071",
            "--date=1986-10-31/1986-11-01",
            "--format=json",
            "--with_metadata=true",
            "--with_stations=true",
        ],
    )
    if result.exit_code != 0:
        raise ChildProcessError(result.stderr)
    response = json.loads(result.stdout)
    assert response.keys() == {"metadata", "stations", "values"}
    assert response["metadata"] == metadata
    assert response["stations"] == [
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
        {
            "station_id": "02074",
            "start_date": "1947-01-01T00:00:00+00:00",
            "end_date": IsStr,
            "latitude": 48.3752,
            "longitude": 8.98,
            "height": 518.0,
            "name": "Hechingen",
            "state": "Baden-Württemberg",
        },
        {
            "station_id": "02638",
            "start_date": "1947-01-01T00:00:00+00:00",
            "end_date": IsStr,
            "latitude": 48.1054,
            "longitude": 8.7548,
            "height": 974.0,
            "name": "Klippeneck",
            "state": "Baden-Württemberg",
        },
        {
            "station_id": "04703",
            "start_date": "1951-01-01T00:00:00+00:00",
            "end_date": IsStr,
            "latitude": 48.0719,
            "longitude": 9.1943,
            "height": 581.0,
            "name": "Sigmaringen-Laiz",
            "state": "Baden-Württemberg",
        },
    ]


@pytest.mark.remote
def test_cli_interpolate_geojson():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "interpolate",
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
    assert response.keys() == {"data"}
    assert response["data"] == {
        "type": "FeatureCollection",
        "features": [
            {
                "type": "Feature",
                "properties": {"id": "6754d04d", "name": "interpolation(48.2156,8.9784)"},
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
                    {
                        "station_id": "02074",
                        "start_date": "1947-01-01T00:00:00+00:00",
                        "end_date": IsStr,
                        "latitude": 48.3752,
                        "longitude": 8.98,
                        "height": 518.0,
                        "name": "Hechingen",
                        "state": "Baden-Württemberg",
                    },
                    {
                        "station_id": "02638",
                        "start_date": "1947-01-01T00:00:00+00:00",
                        "end_date": IsStr,
                        "latitude": 48.1054,
                        "longitude": 8.7548,
                        "height": 974.0,
                        "name": "Klippeneck",
                        "state": "Baden-Württemberg",
                    },
                    {
                        "station_id": "04703",
                        "start_date": "1951-01-01T00:00:00+00:00",
                        "end_date": IsStr,
                        "latitude": 48.0719,
                        "longitude": 9.1943,
                        "height": 581.0,
                        "name": "Sigmaringen-Laiz",
                        "state": "Baden-Württemberg",
                    },
                ],
                "values": [
                    {
                        "station_id": "6754d04d",
                        "parameter": "temperature_air_mean_2m",
                        "date": "1986-10-31T00:00:00+00:00",
                        "value": 6.37,
                        "distance_mean": 16.99,
                        "taken_station_ids": ["00072", "02074", "02638", "04703"],
                    },
                    {
                        "station_id": "6754d04d",
                        "date": "1986-11-01T00:00:00+00:00",
                        "parameter": "temperature_air_mean_2m",
                        "value": 8.7,
                        "distance_mean": 0.0,
                        "taken_station_ids": ["00071"],
                    },
                ],
            },
        ],
    }


@pytest.mark.remote
def test_cli_interpolate_interpolation_station_distance():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "interpolate",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/kl/temperature_air_mean_2m",
            "--station=00071",
            "--date=1986-10-31/1986-11-01",
            "--format=json",
            '--interpolation_station_distance={"temperature_air_mean_2m": 10}',
        ],
    )
    if result.exit_code != 0:
        raise ChildProcessError(result.stderr)
    response = json.loads(result.stdout)
    assert response.keys() == {"values"}
    assert response["values"] == [
        {
            "station_id": "6754d04d",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-10-31T00:00:00+00:00",
            "value": None,
            "distance_mean": None,
            "taken_station_ids": [],
        },
        {
            "station_id": "6754d04d",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-11-01T00:00:00+00:00",
            "value": 8.7,
            "distance_mean": 0.0,
            "taken_station_ids": ["00071"],
        },
    ]


@pytest.mark.remote
def test_cli_interpolate_dont_use_nearby_station():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "interpolate",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/kl/temperature_air_mean_2m",
            "--station=00071",
            "--date=1986-10-31/1986-11-01",
            "--format=json",
            "--use_nearby_station_distance=0",
        ],
    )
    if result.exit_code != 0:
        raise ChildProcessError(result.stderr)
    response = json.loads(result.stdout)
    assert response.keys() == {"values"}
    assert response["values"] == [
        {
            "station_id": "6754d04d",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-10-31T00:00:00+00:00",
            "value": 6.37,
            "distance_mean": 16.99,
            "taken_station_ids": ["00072", "02074", "02638", "04703"],
        },
        {
            "station_id": "6754d04d",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-11-01T00:00:00+00:00",
            "value": 8.7,
            "distance_mean": 11.33,
            "taken_station_ids": ["00071", "00072", "02074", "02638"],
        },
    ]


@pytest.mark.remote
def test_cli_interpolate_custom_units():
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "interpolate",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/kl/temperature_air_mean_2m",
            "--station=00071",
            "--date=1986-10-31/1986-11-01",
            "--format=json",
            '--unit_targets={"temperature": "degree_fahrenheit"}',
        ],
    )
    if result.exit_code != 0:
        raise ChildProcessError(result.stderr)
    response = json.loads(result.stdout)
    assert response.keys() == {"values"}
    assert response["values"] == [
        {
            "station_id": "6754d04d",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-10-31T00:00:00+00:00",
            "value": 43.47,
            "distance_mean": 16.99,
            "taken_station_ids": ["00072", "02074", "02638", "04703"],
        },
        {
            "station_id": "6754d04d",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-11-01T00:00:00+00:00",
            "value": 47.66,
            "distance_mean": 0.0,
            "taken_station_ids": ["00071"],
        },
    ]
