# Copyright (C) 2018-2025, earthobservations developers.
# Distributed under the MIT License. See LICENSE for more info.
"""Tests for Météo-France observation API ("Données climatologiques de base")."""

from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from wetterdienst.provider.meteofrance.observation import MeteoFranceObservationRequest


@pytest.mark.remote
def test_meteofrance_observation_api_interleaved_datasets_no_duplicate_stations() -> None:
    """Test that requesting datasets in interleaved order doesn't duplicate station rows.

    itertools.groupby() only groups consecutive items; since parameter order is preserved from
    user input, interleaving datasets (here: core, others, core) used to produce a separate group
    -- and a duplicated station row -- for the second "core" occurrence.
    """
    request = MeteoFranceObservationRequest(
        parameters=[
            ("daily", "core", "precipitation_height"),
            ("daily", "others", "humidity"),
            ("daily", "core", "wind_speed"),
        ],
    ).filter_by_station_id("31069001")
    df = request.df
    assert len(df) == 2
    assert sorted(df.get_column("dataset").to_list()) == ["core", "others"]


@pytest.mark.remote
def test_meteofrance_observation_api_daily_stations() -> None:
    """Test that the daily resolution's much larger climatological station network resolves.

    Station discovery for daily/monthly is built from Météo-France's canonical station metadata
    registry rather than scanning every French department's climatological archive.
    """
    request = MeteoFranceObservationRequest(
        parameters=[("daily", "core", "temperature_air_mean_2m")],
    ).filter_by_station_id("31069001")
    df = request.df
    assert not df.is_empty()
    assert df.get_column("name").to_list() == ["TOULOUSE-BLAGNAC"]
    # regression check: start_date must be populated, since the frontend seeds its date-range
    # picker from it; end_date is legitimately null here since the station is still open (the
    # frontend already falls back to "today" for a null end_date)
    assert df.get_column("start_date").is_not_null().all()


@pytest.mark.remote
@pytest.mark.parametrize(
    ("dataset", "parameter"),
    [
        ("core", "temperature_air_mean_2m"),
        ("core", "wind_gust_max"),
        ("core", "wind_direction_gust_max"),
        ("others", "radiation_global"),
        ("others", "humidity"),
    ],
)
def test_meteofrance_observation_api_daily(dataset: str, parameter: str) -> None:
    """Test daily climatological values ("Données climatologiques de base - quotidiennes").

    Also guards against the parameter-name case mismatch bug: the source columns are uppercase
    (e.g. "RR", "TN"), and the base class matches requested parameters against name_original
    using an exact, case-sensitive comparison.
    """
    request = MeteoFranceObservationRequest(
        parameters=[("daily", dataset, parameter)],
        start_date=datetime(2023, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=datetime(2023, 1, 31, tzinfo=ZoneInfo("UTC")),
    ).filter_by_station_id("31069001")
    df = next(request.values.query()).df
    assert df.get_column("value").is_not_null().sum() > 0


@pytest.mark.remote
@pytest.mark.parametrize(
    "parameter",
    [
        "precipitation_height",
        "temperature_air_max_2m_mean",
        "wind_gust_max",
        "sunshine_duration",
    ],
)
def test_meteofrance_observation_api_monthly(parameter: str) -> None:
    """Test monthly climatological values ("Données climatologiques de base - mensuelles")."""
    request = MeteoFranceObservationRequest(
        parameters=[("monthly", "data", parameter)],
        start_date=datetime(2023, 1, 1, tzinfo=ZoneInfo("UTC")),
        end_date=datetime(2023, 6, 1, tzinfo=ZoneInfo("UTC")),
    ).filter_by_station_id("31069001")
    df = next(request.values.query()).df
    assert df.get_column("value").is_not_null().sum() > 0


@pytest.mark.remote
@pytest.mark.parametrize(
    ("dataset", "parameter"),
    [
        ("core", "temperature_air_mean_2m"),
        ("core", "precipitation_height"),
        ("core", "wind_direction_gust_max"),
        ("others", "cloud_cover_total"),
        ("others", "visibility_range"),
    ],
)
def test_meteofrance_observation_api_hourly(dataset: str, parameter: str) -> None:
    """Test hourly climatological values ("Données climatologiques de base - horaires").

    Also guards against the AAAAMMJJHH date format regression: polars' strptime requires a
    minute whenever an hour is present in the format string, but this date column has none.
    """
    request = MeteoFranceObservationRequest(
        parameters=[("hourly", dataset, parameter)],
        start_date=datetime(2025, 6, 1, tzinfo=ZoneInfo("UTC")),
        end_date=datetime(2025, 6, 7, tzinfo=ZoneInfo("UTC")),
    ).filter_by_station_id("31069001")
    df = next(request.values.query()).df
    assert df.get_column("value").is_not_null().sum() > 0


@pytest.mark.remote
def test_meteofrance_observation_api_6_minutes() -> None:
    """Test 6-minute climatological values ("Données climatologiques de base -  6 minutes").

    Only precipitation is published at this resolution.
    """
    request = MeteoFranceObservationRequest(
        parameters=[("6_minutes", "data", "precipitation_height")],
        start_date=datetime(2025, 6, 1, tzinfo=ZoneInfo("UTC")),
        end_date=datetime(2025, 6, 2, tzinfo=ZoneInfo("UTC")),
    ).filter_by_station_id("31069001")
    df = next(request.values.query()).df
    assert not df.is_empty()
    # 6-minute intervals within a day: exercise that the date column parses to real, distinct
    # timestamps rather than e.g. all collapsing to midnight
    assert df.get_column("date").n_unique() > 1
