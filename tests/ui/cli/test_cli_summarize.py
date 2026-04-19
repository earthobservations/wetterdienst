# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for CLI summarize command."""

import json

import pytest
from click.testing import CliRunner

from wetterdienst.ui.cli import cli


@pytest.mark.remote
def test_cli_summarize_no_metadata_no_stations() -> None:
    """Test the CLI summarize command without metadata and stations."""
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
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-10-31T00:00:00.000000+00:00",
            "value": 6.6,
            "distance": 6.97,
            "taken_station_id": "00072",
        },
        {
            "station_id": "a87291a8",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-11-01T00:00:00.000000+00:00",
            "value": 8.7,
            "distance": 0.0,
            "taken_station_id": "00071",
        },
    ]


@pytest.mark.remote
def test_cli_summarize_geojson(metadata: dict) -> None:
    """Test CLI summarize with GeoJSON output."""
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
                        "resolution": "daily",
                        "dataset": "climate_summary",
                        "station_id": "00071",
                        "start_date": "1986-11-01T00:00:00.000000+00:00",
                        "end_date": "2019-12-31T00:00:00.000000+00:00",
                        "latitude": 48.2156,
                        "longitude": 8.9784,
                        "height": 759.0,
                        "name": "Albstadt-Badkap",
                        "state": "Baden-Württemberg",
                    },
                    {
                        "resolution": "daily",
                        "dataset": "climate_summary",
                        "station_id": "00072",
                        "start_date": "1978-09-01T00:00:00.000000+00:00",
                        "end_date": "1995-05-31T00:00:00.000000+00:00",
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
                        "resolution": "daily",
                        "dataset": "climate_summary",
                        "parameter": "temperature_air_mean_2m",
                        "date": "1986-10-31T00:00:00.000000+00:00",
                        "value": 6.6,
                        "distance": 6.97,
                        "taken_station_id": "00072",
                    },
                    {
                        "station_id": "a87291a8",
                        "resolution": "daily",
                        "dataset": "climate_summary",
                        "parameter": "temperature_air_mean_2m",
                        "date": "1986-11-01T00:00:00.000000+00:00",
                        "value": 8.7,
                        "distance": 0.0,
                        "taken_station_id": "00071",
                    },
                ],
            },
        ],
    }


@pytest.mark.remote
def test_cli_summarize_custom_units() -> None:
    """Test CLI summarize with custom units."""
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
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-10-31T00:00:00.000000+00:00",
            "value": 43.88,
            "distance": 6.97,
            "taken_station_id": "00072",
        },
        {
            "station_id": "a87291a8",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-11-01T00:00:00.000000+00:00",
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
def test_cli_summarize_image(fmt: str) -> None:
    """Test the summarize command with image formats."""
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
            f"--format={fmt}",
        ],
    )
    assert result.exit_code == 0


@pytest.mark.remote
def test_cli_summarize_image_html() -> None:
    """Test the summarize command with HTML format."""
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
    assert result.output.startswith("<html>")


@pytest.mark.remote
def test_cli_summarize_image_pdf() -> None:
    """Test the summarize command with PDF format."""
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


@pytest.mark.remote
def test_cli_summarize_start_date_end_date() -> None:
    """Test --start-date/--end-date as alternative to --date interval in summarize."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "summarize",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/climate_summary/temperature_air_mean_2m",
            "--station=00071",
            "--start-date=1986-10-31",
            "--end-date=1986-11-01",
            "--format=json",
            "--with_metadata=false",
            "--with_stations=false",
        ],
    )
    if result.exit_code != 0:
        raise ChildProcessError(result.output)
    response = json.loads(result.stdout)
    dates = [v["date"][:10] for v in response["values"]]
    assert "1986-10-31" in dates
    assert "1986-11-01" in dates


@pytest.mark.remote
def test_cli_summarize_end_date_only() -> None:
    """Test --end-date without --start-date (treated as single-point date) in summarize."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "summarize",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/climate_summary/temperature_air_mean_2m",
            "--station=00071",
            "--end-date=1986-11-01",
            "--format=json",
            "--with_metadata=false",
            "--with_stations=false",
        ],
    )
    if result.exit_code != 0:
        raise ChildProcessError(result.output)
    response = json.loads(result.stdout)
    assert response["values"][0]["date"].startswith("1986-11-01")


def test_cli_summarize_missing_date() -> None:
    """Test that summarize raises an error when no date is provided."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "summarize",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/climate_summary/temperature_air_mean_2m",
            "--station=00071",
        ],
    )
    assert result.exit_code != 0
    assert "Provide either --date or --start-date" in result.output


def test_cli_summarize_date_and_start_date_conflict() -> None:
    """Test that --date and --start-date together raise an error in summarize."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "summarize",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/climate_summary/temperature_air_mean_2m",
            "--station=00071",
            "--date=1986-10-31",
            "--start-date=1986-10-31",
        ],
    )
    assert result.exit_code != 0
    assert "Use either --date or --start-date" in result.output
