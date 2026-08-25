# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for the CLI command `interpolate`."""

import datetime as dt
import json
from zoneinfo import ZoneInfo

import polars as pl
import pytest
from click.testing import CliRunner
from dirty_equals import IsStr

from wetterdienst.model.result import InterpolatedValuesResult
from wetterdienst.settings import Settings
from wetterdienst.ui.cli import cli


@pytest.mark.remote
def test_cli_interpolate_no_metadata_no_stations() -> None:
    """Test the CLI interpolate command without metadata and stations."""
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
            "station_id": "6754d04d",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-10-31T00:00:00.000000+00:00",
            "value": 6.37,
            "distance_mean": 16.99,
            "taken_station_ids": ["00072", "02074", "02638", "04703"],
        },
        {
            "station_id": "6754d04d",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-11-01T00:00:00.000000+00:00",
            "value": 8.7,
            "distance_mean": 0.0,
            "taken_station_ids": ["00071"],
        },
    ]


@pytest.mark.remote
def test_cli_interpolate_with_metadata_with_stations(metadata: dict) -> None:
    """Test the interpolate command with metadata and stations."""
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
        {
            "resolution": "daily",
            "dataset": "climate_summary",
            "station_id": "02074",
            "start_date": "1947-01-01T00:00:00.000000+00:00",
            "end_date": IsStr,
            "latitude": 48.3752,
            "longitude": 8.98,
            "height": 518.0,
            "name": "Hechingen",
            "state": "Baden-Württemberg",
        },
        {
            "resolution": "daily",
            "dataset": "climate_summary",
            "station_id": "02638",
            "start_date": "1947-01-01T00:00:00.000000+00:00",
            "end_date": IsStr,
            "latitude": 48.1054,
            "longitude": 8.7548,
            "height": 974.0,
            "name": "Klippeneck",
            "state": "Baden-Württemberg",
        },
        {
            "resolution": "daily",
            "dataset": "climate_summary",
            "station_id": "04703",
            "start_date": "1951-01-01T00:00:00.000000+00:00",
            "end_date": IsStr,
            "latitude": 48.0719,
            "longitude": 9.1943,
            "height": 581.0,
            "name": "Sigmaringen-Laiz",
            "state": "Baden-Württemberg",
        },
    ]


@pytest.mark.remote
def test_cli_interpolate_geojson(metadata: dict) -> None:
    """Test the interpolate command with GeoJSON format."""
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
            "--with_metadata=true",
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
                "properties": {"id": "6754d04d", "name": "interpolation(48.2156,8.9784)"},
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
                    {
                        "resolution": "daily",
                        "dataset": "climate_summary",
                        "station_id": "02074",
                        "start_date": "1947-01-01T00:00:00.000000+00:00",
                        "end_date": IsStr,
                        "latitude": 48.3752,
                        "longitude": 8.98,
                        "height": 518.0,
                        "name": "Hechingen",
                        "state": "Baden-Württemberg",
                    },
                    {
                        "resolution": "daily",
                        "dataset": "climate_summary",
                        "station_id": "02638",
                        "start_date": "1947-01-01T00:00:00.000000+00:00",
                        "end_date": IsStr,
                        "latitude": 48.1054,
                        "longitude": 8.7548,
                        "height": 974.0,
                        "name": "Klippeneck",
                        "state": "Baden-Württemberg",
                    },
                    {
                        "resolution": "daily",
                        "dataset": "climate_summary",
                        "station_id": "04703",
                        "start_date": "1951-01-01T00:00:00.000000+00:00",
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
                        "resolution": "daily",
                        "dataset": "climate_summary",
                        "parameter": "temperature_air_mean_2m",
                        "date": "1986-10-31T00:00:00.000000+00:00",
                        "value": 6.37,
                        "distance_mean": 16.99,
                        "taken_station_ids": ["00072", "02074", "02638", "04703"],
                    },
                    {
                        "station_id": "6754d04d",
                        "resolution": "daily",
                        "dataset": "climate_summary",
                        "parameter": "temperature_air_mean_2m",
                        "date": "1986-11-01T00:00:00.000000+00:00",
                        "value": 8.7,
                        "distance_mean": 0.0,
                        "taken_station_ids": ["00071"],
                    },
                ],
            },
        ],
    }


@pytest.mark.remote
def test_cli_interpolate_interpolation_station_distance() -> None:
    """Test the interpolate command with interpolation station distance."""
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
            "station_id": "6754d04d",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-10-31T00:00:00.000000+00:00",
            "value": None,
            "distance_mean": None,
            "taken_station_ids": [],
        },
        {
            "station_id": "6754d04d",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-11-01T00:00:00.000000+00:00",
            "value": 8.7,
            "distance_mean": 0.0,
            "taken_station_ids": ["00071"],
        },
    ]


@pytest.mark.remote
def test_cli_interpolate_dont_use_nearby_station() -> None:
    """Test the interpolate command with don't use nearby station."""
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
            "station_id": "6754d04d",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-10-31T00:00:00.000000+00:00",
            "value": 6.37,
            "distance_mean": 16.99,
            "taken_station_ids": ["00072", "02074", "02638", "04703"],
        },
        {
            "station_id": "6754d04d",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-11-01T00:00:00.000000+00:00",
            "value": 8.7,
            "distance_mean": 11.33,
            "taken_station_ids": ["00071", "00072", "02074", "02638"],
        },
    ]


@pytest.mark.remote
def test_cli_interpolate_custom_units() -> None:
    """Test CLI interpolate with custom units."""
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
            """--unit_targets={"temperature": "degree_fahrenheit"}""",
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
            "station_id": "6754d04d",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-10-31T00:00:00.000000+00:00",
            "value": 43.47,
            "distance_mean": 16.99,
            "taken_station_ids": ["00072", "02074", "02638", "04703"],
        },
        {
            "station_id": "6754d04d",
            "resolution": "daily",
            "dataset": "climate_summary",
            "parameter": "temperature_air_mean_2m",
            "date": "1986-11-01T00:00:00.000000+00:00",
            "value": 47.66,
            "distance_mean": 0.0,
            "taken_station_ids": ["00071"],
        },
    ]


@pytest.mark.remote
@pytest.mark.parametrize(
    "fmt",
    [
        "png",
        "jpg",
        "webp",
        "svg",
    ],
)
def test_cli_interpolate_image(fmt: str) -> None:
    """Test the interpolate command with image format."""
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
            f"--format={fmt}",
        ],
    )
    assert result.exit_code == 0


@pytest.mark.remote
def test_cli_interpolate_image_html() -> None:
    """Test the interpolate command with HTML format."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "interpolate",
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
def test_cli_interpolate_image_pdf() -> None:
    """Test the interpolate command with PDF format."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "interpolate",
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
def test_cli_interpolate_start_date_end_date() -> None:
    """Test --start-date/--end-date as alternative to --date interval in interpolate."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "interpolate",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/kl/temperature_air_mean_2m",
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
def test_cli_interpolate_end_date_only() -> None:
    """Test --end-date without --start-date (treated as single-point date) in interpolate."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "interpolate",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/kl/temperature_air_mean_2m",
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


def test_cli_interpolate_negative_radius() -> None:
    """Test that a negative radius is reported as a bad parameter, not as a traceback."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "interpolate",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/kl/temperature_air_mean_2m",
            "--station=00071",
            "--date=1986-10-31",
            "--interpolation_station_distance_homogeneous=-1",
        ],
    )
    assert result.exit_code != 0
    assert "greater than or equal to 0" in result.output


def test_cli_interpolate_unknown_station_distance_parameter() -> None:
    """Test that a station distance for a name that is not a canonical parameter is reported.

    It used to be accepted and never read, so the parameter the user meant kept its default radius.
    """
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "interpolate",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/kl/temperature_air_mean_2m",
            "--station=00071",
            "--date=1986-10-31",
            '--interpolation_station_distance={"temperature_air_mean": 10}',
        ],
    )
    assert result.exit_code != 0
    assert "not in the canonical parameters" in result.output


def test_cli_interpolate_missing_date() -> None:
    """Test that interpolate raises an error when no date is provided."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "interpolate",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/kl/temperature_air_mean_2m",
            "--station=00071",
        ],
    )
    assert result.exit_code != 0
    assert "Provide either --date or --start-date" in result.output


def test_cli_interpolate_date_and_start_date_conflict() -> None:
    """Test that --date and --start-date together raise an error in interpolate."""
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "interpolate",
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/kl/temperature_air_mean_2m",
            "--station=00071",
            "--date=1986-10-31",
            "--start-date=1986-10-31",
        ],
    )
    assert result.exit_code != 0
    assert "Use either --date or --start-date" in result.output


def _capture_settings(monkeypatch: pytest.MonkeyPatch, command: str) -> list[Settings]:
    """Record the settings the CLI hands to the interpolation or the summary, without querying."""
    captured = []
    df = pl.DataFrame(
        {
            "date": [dt.datetime(1986, 10, 31, tzinfo=ZoneInfo("UTC"))],
            "resolution": ["daily"],
            "dataset": ["climate_summary"],
            "parameter": ["temperature_air_mean_2m"],
            "value": [1.0],
        },
    )

    def fake(api: object, request: object, settings: Settings) -> InterpolatedValuesResult:  # noqa: ARG001
        captured.append(settings)
        return InterpolatedValuesResult(df=df, stations=None, latlon=(0.0, 0.0))  # ty: ignore[invalid-argument-type]

    monkeypatch.setattr(f"wetterdienst.ui.cli.get_{command}", fake)
    return captured


@pytest.mark.parametrize("command", ["interpolate", "summarize"])
def test_cli_interpolation_settings_from_environment(monkeypatch: pytest.MonkeyPatch, command: str) -> None:
    """Test that the environment configures the settings the options do not name.

    The CLI passed the model defaults for all three of these along whether or not they were given,
    so a `WD_TS_GEO_*` variable was overwritten by the library default on every call.
    """
    monkeypatch.setenv("WD_TS_GEO_USE_NEARBY_STATION_DISTANCE", "5")
    monkeypatch.setenv("WD_TS_GEO_MIN_GAIN_OF_VALUE_PAIRS", "0.5")
    monkeypatch.setenv("WD_TS_GEO_NUM_ADDITIONAL_STATIONS", "7")
    captured = _capture_settings(monkeypatch, command)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            command,
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/kl/temperature_air_mean_2m",
            "--station=00071",
            "--date=1986-10-31",
            "--format=json",
        ],
    )
    if result.exit_code != 0:
        raise ChildProcessError(result.output)
    settings = captured[0]
    assert settings.ts_geo_use_nearby_station_distance == 5.0
    assert settings.ts_geo_min_gain_of_value_pairs == 0.5
    assert settings.ts_geo_num_additional_stations == 7


@pytest.mark.parametrize("command", ["interpolate", "summarize"])
def test_cli_interpolation_settings_from_options(monkeypatch: pytest.MonkeyPatch, command: str) -> None:
    """Test that the options win over the environment, and that all three of them exist."""
    monkeypatch.setenv("WD_TS_GEO_USE_NEARBY_STATION_DISTANCE", "5")
    monkeypatch.setenv("WD_TS_GEO_MIN_GAIN_OF_VALUE_PAIRS", "0.5")
    monkeypatch.setenv("WD_TS_GEO_NUM_ADDITIONAL_STATIONS", "7")
    captured = _capture_settings(monkeypatch, command)
    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            command,
            "--provider=dwd",
            "--network=observation",
            "--parameters=daily/kl/temperature_air_mean_2m",
            "--station=00071",
            "--date=1986-10-31",
            "--format=json",
            "--use_nearby_station_distance=0",
            "--min_gain_of_value_pairs=0.25",
            "--num_additional_stations=1",
        ],
    )
    if result.exit_code != 0:
        raise ChildProcessError(result.output)
    settings = captured[0]
    assert settings.ts_geo_use_nearby_station_distance == 0.0
    assert settings.ts_geo_min_gain_of_value_pairs == 0.25
    assert settings.ts_geo_num_additional_stations == 1
